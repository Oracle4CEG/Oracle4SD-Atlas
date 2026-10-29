"""Read-back validation and bounded time-window checks for UTC annotations."""
import argparse,csv,json,hashlib
from pathlib import Path
from itertools import zip_longest
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.compute as pc
import pandas as pd
import duckdb

ap=argparse.ArgumentParser();ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--metadata',type=Path,required=True);a=ap.parse_args()
manifest=list(csv.DictReader((a.metadata/'normalized_file_manifest.csv').open()))
checks=[]
def check(name,passed,detail):
    checks.append(dict(check=name,passed=bool(passed),detail=detail))
    assert passed,(name,detail)
for entry in manifest:
    src=pq.ParquetFile(a.source_root/entry['path']);out=pq.ParquetFile(a.output/entry['path'])
    check(entry['table']+': rows',src.metadata.num_rows==out.metadata.num_rows,str(out.metadata.num_rows))
    same=True
    for x,y in zip_longest(src.iter_batches(batch_size=131072),out.iter_batches(batch_size=131072,columns=src.schema_arrow.names)):
        if x is None or y is None or not x.equals(y):same=False;break
    check(entry['table']+': complete native read-back',same,'Every original field, value, null and row position compared after serialization')
    check(entry['table']+': UTC storage',out.schema_arrow.field('event_time_utc').type==pa.timestamp('ns',tz='UTC'),'Timestamp[ns, UTC]')
    print(entry['table']+' verified',flush=True)

# Independent integer check: nanoseconds in the serialized output must equal
# native milliseconds times exactly 1,000,000 for every Tellor report.
p=a.output/'data/curated/parquet/tellor_micro_reports.parquet'
bad=0;fractional=0;rows=0;rounding_changes=0;max_abs_rounding_ns=0
windows=[('day','2026-06-24T00:00:00Z','2026-06-25T00:00:00Z'),('week','2026-06-22T00:00:00Z','2026-06-29T00:00:00Z')]
pilot={k:dict(native=0,utc=0) for k,_,_ in windows}
for batch in pq.ParquetFile(p).iter_batches(columns=['timestamp_ms','event_time_utc'],batch_size=262144):
    raw=batch.column(0);ns=pc.cast(batch.column(1),pa.int64());expected=pc.multiply(raw,pa.scalar(1000000,pa.int64()))
    bad+=pc.sum(pc.cast(pc.not_equal(ns,expected),pa.int64())).as_py() or 0
    vals=raw.to_numpy();s=ns.to_numpy();fractional+=int((vals%1000!=0).sum());rows+=len(vals)
    # The previous DuckDB integer cast rounds rather than truncates. Values
    # are positive Unix milliseconds; half-second ties round to the even second.
    old=(vals.astype('float64')/1000).round().astype('int64')*1_000_000_000
    gap=abs(old-s);rounding_changes+=int((gap!=0).sum());max_abs_rounding_ns=max(max_abs_rounding_ns,int(gap.max()))
    for k,start,end in windows:
        lo=pd.Timestamp(start).value;hi=pd.Timestamp(end).value
        pilot[k]['native']+=int(((vals>=lo//1000000)&(vals<hi//1000000)).sum())
        pilot[k]['utc']+=int(((s>=lo)&(s<hi)).sum())
check('Tellor full millisecond preservation',bad==0,f'{rows} rows; {fractional} carry nonzero subsecond parts')
for k,_,_ in windows:check('UTC '+k+' window membership',pilot[k]['native']==pilot[k]['utc'],str(pilot[k]))
first=next(pq.ParquetFile(p).iter_batches(columns=['timestamp_ms','event_time_utc'],batch_size=1)).to_pylist()[0]
check('Worked Tellor record',pd.Timestamp(first['event_time_utc']).value==1746801845665*1_000_000,'1746801845665 ms -> 2025-05-09T14:44:05.665Z')
epochs=[]
for n,key,duration in [('flare_reward_epochs','reward_epoch_id',302400),('pyth_ois_reward_epochs','epoch_id',604800)]:
    d=pq.read_table(a.output/f'data/curated/parquet/{n}.parquet').to_pandas()
    valid=(d.epoch_end_utc-d.epoch_start_utc).dt.total_seconds().eq(duration)
    check(n+': retained duration',valid.all(),f'{len(d)} retained epochs, {duration} seconds each')
    check(n+': epoch is not event',d.event_time_utc.isna().all(),'Event clock remains null for epoch records')
    check(n+': closed by cutoff',(d.epoch_end_utc<=pd.Timestamp('2026-06-30T23:59:59Z')).all(),'No incomplete epoch promoted to complete')
    for _,r in d.iterrows():epochs.append(dict(table=n,epoch_id=r[key],start_utc=r.epoch_start_utc.isoformat(),end_utc=r.epoch_end_utc.isoformat(),duration_seconds=duration))
d=pq.read_table(a.output/'data/curated/parquet/pyth_ois_reward_epochs.parquet').to_pandas()
e=d[d.epoch_id==2898].iloc[0];f=d[d.epoch_id==2899].iloc[0]
boundary=e.epoch_end_utc
check('Half-open epoch boundary',boundary==f.epoch_start_utc and not(e.epoch_start_utc<=boundary<e.epoch_end_utc) and f.epoch_start_utc<=boundary<f.epoch_end_utc,'2025-07-24T00:00:00Z belongs to epoch 2899, not epoch 2898')
check('Late snapshot retained separately',(d.snapshot_time_utc>pd.Timestamp('2026-06-30T23:59:59Z')).all() and d.event_time_utc.isna().all(),'Pyth 21 July snapshot is not a pre-cutoff event or availability claim')

con=duckdb.connect();con.execute("SET TimeZone='UTC'")
pop=[]
for n,where in [('uma_dvm_voter_payoffs','true'),('chainlink_staking_v02_events',"event IN ('Staked','Unstaked','RewardClaimed','RewardFinalized','ForfeitedRewardDistributed')")]:
    file=str(a.output/f'data/curated/parquet/{n}.parquet')
    for kind,w in [('all native rows','true'),('legacy common-projection eligible rows',where)]:
        total,timed=con.execute('select count(*),count(event_time_utc) from read_parquet(?) where '+w,[file]).fetchone()
        pop.append(dict(table=n,population=kind,rows=total,utc_available=timed,utc_missing=total-timed,utc_fraction=timed/total))
with (a.metadata/'time_recovery_populations.csv').open('w',newline='') as o:
    w=csv.DictWriter(o,fieldnames=list(pop[0]));w.writeheader();w.writerows(pop)
pd.DataFrame(epochs).to_csv(a.metadata/'validated_epoch_intervals.csv',index=False)
pd.DataFrame(checks).to_csv(a.metadata/'temporal_validation_checks.csv',index=False)
report=dict(checks=len(checks),passed=sum(x['passed'] for x in checks),full_native_readback_tables=len(manifest),tellor_rows=rows,tellor_nonzero_subsecond_rows=fractional,tellor_integer_roundtrip_mismatches=bad,legacy_rounding_changed_rows=rounding_changes,legacy_rounding_max_abs_seconds=max_abs_rounding_ns/1e9,window_pilots=pilot,populations=pop,fresh_rpc_acquisition=False)
(a.metadata/'temporal_validation_report.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))

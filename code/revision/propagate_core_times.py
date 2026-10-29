"""Propagate native UTC support into the five core common/economic tables.

Legacy time columns are retained verbatim. New event clocks use native block
identities; epochs and snapshots never become instantaneous events.
"""
import argparse,json
from pathlib import Path
import duckdb,pandas as pd,pyarrow as pa,pyarrow.parquet as pq
def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--rebuilt',required=True);p.add_argument('--lookup',required=True);p.add_argument('--out',required=True);a=p.parse_args();b=Path(a.native)/'data/curated/parquet';src=Path(a.rebuilt)/'data/curated/parquet';out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect(config={'threads':2,'memory_limit':'8GB','temp_directory':str(out/'scratch')});c.execute("SET TimeZone='UTC'")
    def t(n):return f"read_parquet('{b/(n+'.parquet')}')"
    maps=[f"SELECT chain,block,timestamp_s*1000000000::BIGINT ns FROM read_parquet('{a.lookup}')"]
    for n,chain,block in [('polygon_oov2_events','Polygon','source_block'),('flare_reward_claim_events','Flare','source_block'),('flare_beneficiary_chill_events','Flare','source_block'),('dia_staking_events','DIA','block_number'),('dia_staking_withdrawals','DIA','block_number'),('pyth_ois_instructions','Solana','slot')]:
        maps.append(f"SELECT '{chain}' AS chain,{block} AS block,epoch_ns(event_time_utc) AS ns FROM {t(n)} WHERE event_time_utc IS NOT NULL GROUP BY ALL")
    # Preserve Tellor nanoseconds from textual values without DuckDB's microsecond coercion.
    tells=[]
    for n,block,clock in [('tellor_disputes','source_block','dispute_start_time'),('tellor_dispute_payments','source_block','block_time'),('tellor_dispute_votes','source_block','block_time'),('tellor_tip_withdrawals_realized','height','block_time'),('tellor_reporter_reward_accruals_full','height','block_time'),('tellor_jail_events','height','block_time')]:
        df=pd.read_parquet(b/(n+'.parquet'),columns=[block,clock]).drop_duplicates();df=pd.DataFrame({'chain':'Tellor','block':df[block].astype('int64'),'ns':pd.to_datetime(df[clock],utc=True,format='mixed').astype('int64')});tells.append(df)
    c.register('tellor_precise',pd.concat(tells,ignore_index=True));maps.append('SELECT * FROM tellor_precise')
    c.execute('CREATE TABLE block_clock AS SELECT chain,block,min(ns) ns FROM ('+' UNION ALL '.join(maps)+') GROUP BY 1,2 HAVING count(DISTINCT ns)=1')
    # A native micro-report carries millisecond precision even when a different source has more digits.
    c.execute(f"CREATE TABLE report_clock AS SELECT block_number block,min(try_cast(timestamp_ms AS BIGINT))*1000000::BIGINT ns FROM {t('tellor_micro_reports')} GROUP BY 1 HAVING count(DISTINCT timestamp_ms)=1")
    assert c.execute('SELECT count(*) FROM report_clock').fetchone()[0]==11193939
    c.execute(f"CREATE VIEW flare_epoch AS SELECT reward_epoch_id,epoch_ns(epoch_start_utc) a,epoch_ns(epoch_end_utc) b FROM {t('flare_reward_epochs')}")
    c.execute(f"CREATE VIEW pyth_epoch AS SELECT epoch_id,epoch_ns(epoch_start_utc) a,epoch_ns(epoch_end_utc) b FROM {t('pyth_ois_reward_epochs')}")
    reports=[]
    epoch_tables="'flare_reward_claims','flare_provider_conditions','flare_provider_feed_performance','pyth_ois_publisher_epoch_factors'"
    for name in ['accountability_events','sample_b_observable_accountability','sample_c_strict_honesty_events','economic_semantics_events','realized_reward_slash_events']:
        common=name in ['accountability_events','sample_b_observable_accountability','sample_c_strict_honesty_events'];field='native_table' if common else 'source_table';ident='accountability_event_id' if common else 'evidence_id'
        ch=f"CASE WHEN s.{field} LIKE 'polygon_%' THEN 'Polygon' WHEN s.{field} LIKE 'tellor_%' THEN 'Tellor' WHEN s.{field} LIKE 'flare_%' THEN 'Flare' WHEN s.{field} LIKE 'pyth_%' THEN 'Solana' WHEN s.{field} LIKE 'dia_%' THEN 'DIA' ELSE 'Ethereum' END"
        non_event=f"s.{field} IN ({epoch_tables},'flare_beneficiary_chill_state')"+ (" OR s.native_table='chainlink_eth_usd_reports'" if common else " OR s.source_table='tellor_disputes'")
        tim="coalesce(CASE WHEN s.native_table='tellor_micro_reports' THEN rc.ns ELSE bc.ns END,NULL)" if common else 'bc.ns'
        joins=f"LEFT JOIN block_clock bc ON bc.chain=({ch}) AND bc.block=s.source_block"
        if common:
            joins+=" LEFT JOIN report_clock rc ON rc.block=CASE WHEN s.native_table='tellor_micro_reports' THEN s.source_block END LEFT JOIN flare_epoch fe ON fe.reward_epoch_id=CASE WHEN s.native_table IN ('flare_reward_claims','flare_provider_conditions','flare_provider_feed_performance') THEN try_cast(split_part(s.accountability_unit_id,':',1) AS BIGINT) END LEFT JOIN pyth_epoch pe ON pe.epoch_id=CASE WHEN s.native_table='pyth_ois_publisher_epoch_factors' THEN try_cast(split_part(s.accountability_unit_id,':',1) AS BIGINT) END"
        ep="coalesce(fe.a,pe.a) epoch_start_ns,coalesce(fe.b,pe.b) epoch_end_ns" if common else 'NULL::BIGINT epoch_start_ns,NULL::BIGINT epoch_end_ns'
        query=f"SELECT s.{ident},CASE WHEN {non_event} THEN NULL ELSE {tim} END event_ns,{ep},CASE WHEN s.{field} IN ({epoch_tables}) THEN 'native_epoch_support' WHEN s.{field}='flare_beneficiary_chill_state' THEN 'snapshot_not_event' WHEN {non_event} THEN 'source_time_not_economic_execution' WHEN {tim} IS NULL THEN 'missing_native_event_clock' ELSE 'native_block_clock' END event_time_status FROM read_parquet('{src/(name+'.parquet')}') s {joins}"
        print('Propagating '+name,flush=True);reader=c.execute(query).fetch_record_batch(100000);dest=out/(name+'_clocks.parquet');writer=None;n=0
        for batch in reader:
            table=pa.Table.from_batches([batch]);names=table.column_names
            for old,new in [('event_ns','event_time_utc'),('epoch_start_ns','epoch_start_utc'),('epoch_end_ns','epoch_end_utc')]:
                i=names.index(old);table=table.set_column(i,new,table[old].cast(pa.timestamp('ns',tz='UTC')));names=table.column_names
            if writer is None:writer=pq.ParquetWriter(dest,table.schema,compression='zstd')
            writer.write_table(table,row_group_size=100000);n+=table.num_rows
        if writer:writer.close()
        original=pq.read_metadata(src/(name+'.parquet')).num_rows;assert n==original
        check=c.execute(f"SELECT count(*) FILTER(WHERE event_time_utc>to_timestamp(1782863999)),count(*) FILTER(WHERE event_time_status IN ('native_epoch_support','snapshot_not_event','source_time_not_economic_execution') AND event_time_utc IS NOT NULL),bit_xor(hash({ident})) FROM read_parquet('{dest}')").fetchone()
        oldhash=c.execute(f"SELECT bit_xor(hash({ident})) FROM read_parquet('{src/(name+'.parquet')}')").fetchone()[0]
        stats=c.execute(f"SELECT event_time_status,count(*) n FROM read_parquet('{dest}') GROUP BY 1").fetchall();report={'table':name,'rows':n,'row_count_preserved':n==original,'native_key_hash_preserved':check[2]==oldhash,'post_cutoff_event_clocks':check[0],'non_event_clock_violations':check[1],'time_status_counts':dict(stats),'parent_table':name,'parent_key':ident,'legacy_fields':'source table remains unchanged; join this clock companion by parent_key','passed':check[0]==0 and check[1]==0 and check[2]==oldhash};reports.append(report);print(json.dumps(report),flush=True)
        (out/'validation.json').write_text(json.dumps({'passed':all(x['passed'] for x in reports),'tables':reports,'scope':'Five core tables; legacy model/application views remain archived and use earlier clocks.'},indent=2))
    assert all(x['passed'] for x in reports)
if __name__=='__main__':main()

"""Lossless UTC annotations for the 64 hash-pinned retained Atlas inputs.

Run with --source-root containing the original data/ tree. Original fields and
row order are preserved. This is an archived-input transformation, not an RPC
reacquisition or a replay of the 31 downstream canonical tables.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import platform

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

CUTOFF = pd.Timestamp('2026-06-30T23:59:59Z')
UTC_TYPE = pa.timestamp('ns', tz='UTC')
CODE_VERSION = 'oracle4sd-temporal-v1-20261026'

def digest(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''): h.update(b)
    return h.hexdigest()

def dump_csv(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with p.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)

def iso(x):
    return '' if pd.isna(x) else pd.Timestamp(x).isoformat().replace('+00:00', 'Z')

def branch(n):
    if n.startswith('chainlink'): return 'Chainlink', 'Ethereum'
    if n.startswith('chronicle_redstone') or n in ['ecosystem_observability_evidence', 'phase4_oracle_economic_interfaces']: return 'Multiple', 'row-specific'
    if n.startswith('chronicle'): return 'Chronicle', 'Ethereum'
    if n.startswith('redstone'): return 'RedStone Push', 'Ethereum'
    if n.startswith('dia'): return 'DIA', 'Lasernet'
    if n.startswith('flare'): return 'Flare FTSOv2', 'Flare'
    if n.startswith('pyth'): return 'Pyth', 'Solana'
    if n.startswith('tellor'): return 'Tellor', 'tellor-1'
    if n.startswith('uma_dvm') or n.startswith('uma_phase2_dvm'): return 'UMA', 'Ethereum'
    if n.startswith('uma_polygon'): return 'UMA', 'Polygon + Ethereum'
    return 'UMA', 'Polygon'

def make_rules(name, fields):
    """Explicit clock families; unit is not inferred from numeric magnitude."""
    rules = []
    def add(target, field, unit, meaning):
        if field in fields: rules.append(dict(target=target, source=field, unit=unit, meaning=meaning))
    if name.startswith('polygon_') and 'block_time' in fields:
        add('event_time_utc', 'block_time', 's', 'Native Polygon event registration/execution block time')
    if name in ['chronicle_ethereum_events', 'redstone_ethereum_push_events']:
        add('event_time_utc', 'block_timestamp', 's', 'Native Ethereum execution block time')
        add('oracle_timestamp_utc', 'oracle_timestamp', 's', 'Oracle payload timestamp; not independently verified real-world observation time')
    add('event_time_utc', 'block_time_unix', 's', 'Native execution block time')
    if name.startswith('tellor_') and 'block_time' in fields:
        add('event_time_utc', 'block_time', 'iso', 'Native Tellor execution block time; timezone-naive retained values are UTC by ingestion code')
    if name == 'tellor_micro_reports':
        add('event_time_utc', 'timestamp_ms', 'ms', 'Report timestamp emitted in native new_report event')
    if name == 'tellor_aggregate_height_index':
        add('aggregate_time_utc', 'aggregate_timestamp_ms', 'ms', 'Aggregate index timestamp, not a constituent report or payment time')
    if name == 'tellor_disputes':
        add('event_time_utc', 'dispute_start_time', 'iso', 'Dispute start recorded by native dispute state')
        add('dispute_end_time_utc', 'dispute_end_time', 'iso', 'Native dispute-end field; not assumed payment or tally time')
        add('report_reference_time_utc', 'report_timestamp_ms', 'ms', 'Timestamp of the challenged report')
    if name == 'tellor_jail_lifecycles':
        add('event_time_utc', 'jail_start_time', 'iso', 'Jail-start event time')
        add('release_time_utc', 'unjail_time', 'iso', 'Observed unjail event time')
        add('scheduled_release_time_utc', 'jail_end_scheduled_time', 'iso', 'Scheduled release; not evidence of actual release')
    add('epoch_start_utc', 'epoch_start_time_unix', 's', 'Inclusive beginning of retained epoch support')
    add('epoch_end_utc', 'epoch_end_time_unix', 's', 'Exclusive end of retained epoch support; not payment or claimability time')
    add('snapshot_time_utc', 'snapshot_time_unix', 's', 'State snapshot time; can be later than event cutoff')
    add('snapshot_time_utc', 'metadata_snapshot_time_utc', 'iso', 'Metadata snapshot, not historical event or decision-time availability')
    add('retrieval_time_utc', 'retrieved_at_utc', 'iso', 'Retained retrieval timestamp')
    add('decision_time_utc', 'decision_time_unix', 's', 'Proposal-time decision landmark; not a universal availability guarantee')
    add('challenge_deadline_utc', 'challenge_deadline_unix', 's', 'Configured challenge deadline, not execution time')
    add('evidence_label_time_utc', 'evidence_snapshot_time_unix', 's', 'Legacy evidence label; not independently established acquisition or availability time')
    add('capture_time_utc', 'capture_time_unix', 's', 'Archived webpage capture clock')
    if name == 'chainlink_eth_usd_reports':
        add('oracle_update_time_utc', 'updated_at', 's', 'AnswerUpdated updatedAt payload; separate from execution block time')
    for f in ['request_time', 'request_time_unix', 'request_timestamp']:
        if f in fields:
            add('request_reference_time_utc', f, 's', 'Request reference timestamp encoded in object identity; not necessarily event emission')
            break
    add('expiration_time_utc', 'expiration_time', 's', 'Configured proposal expiration, not settlement time')
    add('dvm_reference_time_utc', 'dvm_time', 's', 'DVM request identity timestamp, not Ethereum adjudication time')
    if name in ['polymarket_gamma_markets', 'polygon_uma_gamma_links']:
        for f, t in [('createdAt','metadata_created_utc'), ('updatedAt','metadata_updated_utc'), ('closedTime','metadata_closed_utc'), ('endDate','market_end_utc')]:
            add(t, f, 'iso', 'Off-chain market metadata clock; not on-chain execution or availability evidence')
    # Audit metadata can retain its existing UTC field; do not duplicate that name.
    if name == 'phase4_oracle_economic_interfaces':
        add('metadata_audit_time_utc', 'audit_time_utc', 'iso', 'Interface audit time, not a historical economic event')
    return rules

def parse_clock(s, unit):
    # Numeric conversion must retain integer precision. Numeric strings in this
    # dataset are seconds/milliseconds, within exact int64 range.
    if unit in ['s', 'ms']:
        numeric = pd.to_numeric(s, errors='coerce')
        scale = 1_000_000_000 if unit == 's' else 1_000_000
        valid = numeric.notna() & numeric.between(-9223372036854775807 / scale, 9223372036854775807 / scale)
        out = pd.Series(pd.NaT, index=s.index, dtype='datetime64[ns, UTC]')
        # Do not pass nullable float arrays to the unit converter: unmatched
        # block joins are null, not floating-point timestamps. Integer values
        # are converted without multiplication in floating-point arithmetic.
        v = numeric.loc[valid]
        if len(v):
            if (v == np.floor(v)).all():
                out.loc[valid] = pd.to_datetime(v.astype('int64'), unit=unit, utc=True)
            else:
                from decimal import Decimal
                ns = v.map(lambda x: int(Decimal(str(x)) * scale)).astype('int64')
                out.loc[valid] = pd.to_datetime(ns, unit='ns', utc=True)
        return out
    return pd.to_datetime(s, utc=True, errors='coerce', format='mixed')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--source-root', type=Path, required=True)
    ap.add_argument('--atlas-root', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--metadata', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True); args.metadata.mkdir(parents=True, exist_ok=True)
    pinned = list(csv.DictReader((args.atlas_root/'metadata/full_source_register_20261012.csv').open()))
    inputs = [x for x in pinned if x['component'] == 'native']
    inp = {Path(x['path']).stem:x for x in inputs}
    paths = {k:args.source_root/v['path'] for k,v in inp.items()}
    for n, r in inp.items():
        assert paths[n].exists(), paths[n]
        assert digest(paths[n]) == r['sha256'], f'Input checksum mismatch: {n}'
    def frame(n, columns=None): return pq.read_table(paths[n], columns=columns).to_pandas()

    # Resolve only exact same-chain block matches from hash-verified retained
    # records that already carry a timestamp. No interpolation or external RPC.
    block_frames = []
    definitions = [
        ('chronicle_ethereum_events','Ethereum','block_number','block_timestamp'),
        ('redstone_ethereum_push_events','Ethereum','block_number','block_timestamp'),
        ('polygon_oov2_events','Polygon','source_block','block_time'),
        ('polygon_adapter_events','Polygon','source_block','block_time'),
        ('polygon_child_tunnel_events','Polygon','source_block','block_time')]
    for n, chain, b, t in definitions:
        d = frame(n, [b,t]).rename(columns={b:'block',t:'timestamp_s'}).dropna().drop_duplicates()
        d['chain'] = chain; d['source_table'] = n; block_frames.append(d)
    blocks = pd.concat(block_frames, ignore_index=True)
    conflicts = blocks.groupby(['chain','block']).timestamp_s.nunique()
    assert (conflicts <= 1).all(), 'Conflicting retained timestamps for the same chain/block'
    blocks = blocks.sort_values(['chain','block','source_table']).drop_duplicates(['chain','block'])
    blocks.to_parquet(args.metadata/'retained_block_time_lookup.parquet', index=False)
    block_maps = {c:g.set_index('block').timestamp_s for c,g in blocks.groupby('chain')}
    # Retained epoch IDs must identify exactly one support interval.
    flare_epoch = frame('flare_reward_epochs', ['reward_epoch_id','epoch_start_time_unix','epoch_end_time_unix'])
    assert not flare_epoch.reward_epoch_id.duplicated().any()
    flare_epoch = flare_epoch.set_index('reward_epoch_id')
    pyth_epoch = frame('pyth_ois_reward_epochs', ['epoch_id','epoch_start_time_unix','epoch_end_time_unix'])
    assert not pyth_epoch.epoch_id.duplicated().any()
    pyth_epoch = pyth_epoch.set_index('epoch_id')
    manifests = {}
    for p in (args.atlas_root/'metadata/historical_source_manifests').glob('*.json'):
        manifests[p.stem] = json.loads(p.read_text()).get('metadata',{})
    pyth_snapshot = pd.Timestamp(manifests['source_pyth_ois_rolling_state']['snapshot_time'])
    reg = []; dictionaries = []; stats = []; samples = []; outputs = []; checks = []
    for n, r in inp.items():
        b, chain = branch(n); pf = pq.ParquetFile(paths[n]); fields = pf.schema_arrow.names
        rules = make_rules(n,fields)
        block_field = next((f for f in ['source_block','block_number'] if f in fields),None)
        direct_event = any(x['target']=='event_time_utc' for x in rules)
        join_block = not direct_event and block_field is not None and chain in block_maps and n not in ['polymarket_decision_time_web_evidence','polymarket_decision_time_web_provenance']
        join_epoch = n.startswith('flare_') and 'reward_epoch_id' in fields
        epoch_only = ('epoch_end_time_unix' in fields or join_epoch) and not direct_event
        metadata_only = not direct_event and not join_block and not epoch_only
        status_default = 'epoch_record_not_an_instant_event' if epoch_only else 'no_event_clock_for_this_record'
        relevant = {x['target']:x for x in rules}
        if join_block:
            relevant['event_time_utc'] = dict(target='event_time_utc',source=f'{chain}:{block_field} -> retained_block_time_lookup',unit='s',meaning='Exact same-chain block join from retained native records; unresolved blocks remain null')
        if join_epoch:
            for target,field in [('epoch_start_utc','epoch_start_time_unix'),('epoch_end_utc','epoch_end_time_unix')]:
                if target not in relevant:
                    relevant[target]=dict(target=target,source=f'flare_reward_epochs.{field} via reward_epoch_id',unit='s',meaning='Many-to-one historical epoch support; not registration, payment or eligibility time')
        snapshot_manifest = n in ['pyth_ois_reward_epochs','pyth_ois_publisher_epoch_factors']
        snapshot_cutoff = n in ['flare_beneficiary_chill_state','flare_reward_claim_epoch_qc']
        if snapshot_manifest or snapshot_cutoff:
            relevant['snapshot_time_utc']=dict(target='snapshot_time_utc',source='source_pyth_ois_rolling_state.snapshot_time' if snapshot_manifest else 'source_flare_fsp_rewards.cutoff_block_time',unit='iso',meaning='State snapshot clock from retained acquisition manifest')
        payment = n in ['pyth_ois_economic_events','dia_staking_withdrawals','flare_reward_claim_events','chainlink_staking_v02_events','chronicle_ethereum_events']
        if payment:
            relevant['payment_time_utc']=dict(target='payment_time_utc',source='event_time_utc with documented payment-event condition',unit='ns',meaning='Observed payment-event clock; no matching of epoch entitlement to payment is implied')
        # A fixed, nullable canonical event field is present even for epoch-only
        # and metadata records, with an explicit reason rather than imputation.
        if 'event_time_utc' not in relevant:
            relevant['event_time_utc']=dict(target='event_time_utc',source='',unit='',meaning=status_default)
        clocks=list(relevant)
        counts={f:dict(valid=0,invalid=0,minimum=None,maximum=None,post_cutoff=0,subsecond=0) for f in clocks}
        event_status_counts={}; nrows=0; sample_n=0; original_preserved=True
        out=args.output/r['path']; out.parent.mkdir(parents=True,exist_ok=True)
        writer=None
        for batch in pf.iter_batches(batch_size=131072):
            # Only time/key columns enter pandas; original Arrow columns are
            # appended unchanged, including strings, nullability and keys.
            need={x['source'] for x in rules}
            need.update(x for x in [block_field,'reward_epoch_id','event','event_name','is_fee_burn','payment_exact'] if x in fields)
            d=pa.Table.from_batches([batch]).select(sorted(need)).to_pandas()
            length=batch.num_rows
            null=pd.Series(pd.NaT,index=range(length),dtype='datetime64[ns, UTC]')
            values={f:null.copy() for f in clocks}
            status=pd.Series(status_default,index=range(length),dtype='string')
            for rule in rules:
                f=rule['target']; raw=d[rule['source']]; converted=parse_clock(raw,rule['unit'])
                invalid=raw.notna() & converted.isna()
                counts[f]['invalid']+=int(invalid.sum())
                if invalid.any():
                    # Empty source strings are missing, not a successful parse.
                    pass
                values[f]=converted
            if direct_event:
                status[:]='missing_native_event_time'; status[values['event_time_utc'].notna()]='native_clock'
            if join_block:
                sec=d[block_field].map(block_maps[chain])
                values['event_time_utc']=parse_clock(sec,'s')
                status[:]='missing_retained_block_time'; status[sec.notna()]='retained_same_chain_block_join'
            if join_epoch:
                for f,s in [('epoch_start_utc','epoch_start_time_unix'),('epoch_end_utc','epoch_end_time_unix')]:
                    v=parse_clock(d.reward_epoch_id.map(flare_epoch[s]),'s')
                    existing=values.get(f,null)
                    mismatch=existing.notna() & v.notna() & existing.ne(v)
                    assert not mismatch.any(), f'Epoch support disagreement: {n}/{f}'
                    values[f]=existing.fillna(v)
            if snapshot_manifest:values['snapshot_time_utc']=pd.Series(pyth_snapshot,index=range(length))
            if snapshot_cutoff:values['snapshot_time_utc']=pd.Series(CUTOFF,index=range(length))
            if payment:
                cond=pd.Series(True,index=range(length))
                if n=='flare_reward_claim_events':cond=~d.is_fee_burn.fillna(True)
                if n=='dia_staking_withdrawals':cond=d.payment_exact.fillna(False)
                if n=='chainlink_staking_v02_events':cond=d.event.eq('RewardClaimed')
                if n=='chronicle_ethereum_events':cond=d.event_name.eq('OpChallengeRewardPaid')
                values['payment_time_utc']=values['event_time_utc'].where(cond)
            table=pa.Table.from_batches([batch])
            for f in clocks:
                v=values[f]; valid=v.dropna(); s=counts[f]; s['valid']+=len(valid)
                if len(valid):
                    mn,mx=valid.min(),valid.max()
                    s['minimum']=mn if s['minimum'] is None else min(s['minimum'],mn)
                    s['maximum']=mx if s['maximum'] is None else max(s['maximum'],mx)
                    s['post_cutoff']+=int((valid>CUTOFF).sum())
                    s['subsecond']+=int((valid.astype('int64')%1_000_000_000!=0).sum())
                table=table.append_column(f,pa.array(v,type=UTC_TYPE))
            table=table.append_column('event_time_status',pa.array(status,type=pa.string()))
            assert table.select(fields).equals(pa.Table.from_batches([batch])), n
            for k,v in status.value_counts().items():event_status_counts[k]=event_status_counts.get(k,0)+int(v)
            if writer is None:writer=pq.ParquetWriter(out,table.schema,compression='zstd')
            writer.write_table(table)
            if sample_n<2:
                for j in range(min(2-sample_n,length)):
                    native=pa.Table.from_batches([batch]).slice(j,1).to_pylist()[0]
                    keys={k:v for k,v in native.items() if any(t in k for t in ['tx','signature','block','height','log_index','instruction','epoch_id','request_id','query_id','meta_id','reporter']) and not isinstance(v,list)}
                    for f,rr in relevant.items():
                        raw=native.get(rr['source'],'')
                        samples.append(dict(table=n,source_row_ordinal=nrows+j,source_sha256=r['sha256'],native_keys=json.dumps(keys,default=str,ensure_ascii=False),target_field=f,raw_field=rr['source'],raw_value=str(raw),utc_value=iso(values[f].iloc[j]),meaning=rr['meaning'],event_time_status=status.iloc[j]))
                    sample_n+=1
            nrows+=length
        if writer is not None:writer.close()
        else:
            table=pq.read_table(paths[n])
            for f in clocks:table=table.append_column(f,pa.array([],type=UTC_TYPE))
            table=table.append_column('event_time_status',pa.array([],type=pa.string()));pq.write_table(table,out,compression='zstd')
        assert nrows==pf.metadata.num_rows
        for f,rr in relevant.items():
            s=counts[f]
            stats.append(dict(table=n,branch=b,chain=chain,field=f,rows=nrows,valid_rows=s['valid'],null_rows=nrows-s['valid'],invalid_source_values=s['invalid'],first_utc=iso(s['minimum']),last_utc=iso(s['maximum']),post_cutoff_rows=s['post_cutoff'],subsecond_rows=s['subsecond']))
            dictionaries.append(dict(table=n,branch=b,field=f,arrow_type=str(UTC_TYPE),original_field=rr['source'],original_unit=rr['unit'],conversion_rule=('Exact integer unit conversion to UTC nanoseconds' if rr['unit'] in ['s','ms'] else 'UTC parsing or explicit documented join; original value retained'),temporal_meaning=rr['meaning'],precision_policy='Storage nanoseconds do not increase source precision; raw source retained',missingness='Null preserved; no date interpolation, epoch allocation or retrieval-time substitution',input_sha256=r['sha256'],source_code=CODE_VERSION))
        epoch_text='; epoch support is retained separately' if epoch_only or join_epoch else ''
        basis={
            'UMA':'Version-specific retained Polygon or Ethereum history; native source keys determine available records',
            'Chainlink':'Staking v0.2 deployment-bound scan; ETH/USD history is phase-specific',
            'Chronicle':'Historical validated Ethereum contract set; scan begins at block 0, which is not deployment',
            'RedStone Push':'Pinned Ethereum Push-adapter set; scan begins at block 0, excluding Pull and AVS',
            'DIA':'Lasernet staking contract deployment-bound scan; first withdrawal is not deployment',
            'Tellor':'tellor-1 historical acquisition and module-specific events; public opening is not the scan start',
            'Flare FTSOv2':'Historical reward implementation and retained official artifacts; epochs 228-410, minimum conditions from 251',
            'Pyth':'OIS transaction archive begins 2024-09-11; rolling state supports epochs 2898-2946 only',
            'Multiple':'Interface/evidence metadata; no protocol-wide event observation interval'
        }[b]
        if n.startswith('polymarket_') or n in ['decision_samples','splits']:
            basis='Derived selected UMA-linked sample or off-chain metadata; beginning is cohort/interface availability, not deployment'
        if n.startswith('pyth_') and ('epoch' in n or n.endswith('slash_counters')):basis='Circular-buffer retention/current snapshot limitation; not complete deployment history'
        es=counts['event_time_utc']
        reg.append(dict(table=n,path=r['path'],branch=b,chain=chain,rows=nrows,source_layer='64 frozen reconstruction inputs',audit_status='full row-preserving UTC annotation completed',source_revision=r['revision'],input_sha256=r['sha256'],output_sha256=digest(out),event_rows=es['valid'],event_null_rows=nrows-es['valid'],first_event_utc=iso(es['minimum']),last_event_utc=iso(es['maximum']),event_time_status_counts=json.dumps(event_status_counts,sort_keys=True),start_rationale=basis+epoch_text,deployment_time_utc='',deployment_time_status='Not backfilled from a first event; see contract-specific Appendix A register',scan_boundaries_reference='Appendix A and supplementary/implementation_register.csv; not inferred from retained endpoints',native_order_keys=';'.join(x for x in fields if any(t in x for t in ['block','height','tx_index','transaction_index','log_index','instruction_index','signature','epoch_id','source_event_index'])),native_cadence='epoch support' if epoch_only else 'record-specific/event-driven; no inferred fixed sampling rate',coverage_status='retained_rows_verified; acquisition_continuity_not_reaudited',coverage_fraction='',coverage_denominator_kind='unknown unless acquisition interval receipts establish the expected population',cutoff_utc=iso(CUTOFF),snapshot_policy='Retain actual later snapshots; do not treat as pre-cutoff feature availability'))
        outputs.append(dict(table=n,path=r['path'],rows=nrows,bytes=out.stat().st_size,sha256=digest(out),source_sha256=r['sha256']))
        checks.append(dict(table=n,rows_preserved=True,all_original_fields_and_order_preserved=True,source_hash_verified=True,output_row_count=pq.ParquetFile(out).metadata.num_rows,invalid_clock_inputs=sum(s['invalid'] for s in counts.values())))
        print(f'{n}: {nrows:,} rows; event clock {es["valid"]:,}; added {len(clocks)} clocks',flush=True)
    # Audit the entire 95-table catalogue without falsely calling a downstream
    # model/application rebuild part of this native-clock transformation.
    known={r['path'] for r in reg}
    canonical=list(csv.DictReader((args.atlas_root/'metadata/repaired_full_data_inventory.csv').open()))
    for r in canonical:
        if r['path'] not in known:
            reg.append(dict(table=Path(r['path']).stem,path=r['path'],rows=r['rows'],source_layer='canonical downstream projection/application',audit_status='catalogued; dependent rebuild not executed in this temporal pass',source_revision='57ab1e2409652291c75f02c9e066c52011d8b4ad',input_sha256=r['sha256'],start_rationale='Inherited from source objects and cohort filters; no separate deployment date',coverage_status='not_recomputed',cutoff_utc=iso(CUTOFF)))
    dump_csv(args.metadata/'temporal_registry.csv',reg)
    dump_csv(args.metadata/'temporal_clock_dictionary.csv',dictionaries)
    dump_csv(args.metadata/'clock_statistics.csv',stats)
    dump_csv(args.metadata/'worked_records.csv',samples)
    dump_csv(args.metadata/'normalized_file_manifest.csv',outputs)
    dump_csv(args.metadata/'native_preservation_checks.csv',checks)
    (args.metadata/'transformation_report.json').write_text(json.dumps(dict(code_version=CODE_VERSION,script_sha256=digest(Path(__file__)),source_atlas_commit='1dc0dfc3bc919e64f43a110bf29b75ef0e34459c',native_inputs=len(inputs),catalogue_tables=len(reg),annotated_rows=sum(x['rows'] for x in outputs),derived_tables_not_rebuilt=len(reg)-len(inputs),block_lookup_rows=len(blocks),block_lookup_conflicts=0,original_fields_and_order_preserved=True,invalid_inputs=sum(x['invalid_clock_inputs'] for x in checks),fresh_rpc_acquisition=False,python=platform.python_version(),pandas=pd.__version__,pyarrow=pa.__version__,output_bytes=sum(x['bytes'] for x in outputs)),indent=2))

if __name__=='__main__':main()

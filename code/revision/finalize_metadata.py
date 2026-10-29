"""Refresh revised files, document derived fields and validate portable metadata."""
from pathlib import Path
import argparse,json,hashlib,shutil,datetime
import pandas as pd
import pyarrow as pa,pyarrow.parquet as pq

DEFS = {
'accountability_event_id':'Unique retained common-record identifier; primary key joining the clock companion to its parent.',
'evidence_id':'Unique retained economic-component identifier; primary key joining the clock companion to its parent.',
'aggregate_time_utc':'UTC conversion of the native aggregate timestamp; distinct from acquisition time.',
'capture_time_utc':'UTC time at which web evidence was captured; not proof that its content was available at the proposal.',
'retrieval_time_utc':'UTC retrieval time of the source response; not the time of its underlying market observation.',
'child_bridge_block':'Polygon child-tunnel block retained by the identity-link source; null if the bridge event is unmatched.',
'child_pushed_price_raw':'Resolved integer carried by a matched Polygon child-tunnel push; missing without a matched push.',
'child_request_hash':'Request hash retained from the Polygon child-tunnel evidence, scoped to its deployment.',
'child_request_hash_exact':'Whether the reconstructed child request hash equals the retained child-tunnel hash.',
'child_tunnel_link_mode':'Evidence mode used to associate the request with a child-tunnel event.',
'computed_child_request_hash':'Deterministically reconstructed request hash using the registered native hashing transformation.',
'cohort':'Named inclusion population; retained_request_panel includes all retained OOv2 request lifecycles.',
'correct_vote_redistribution_raw':'Nonnegative accrued redistribution assigned to the voter for a request, in integer UMA units; not a wallet payment.',
'wrong_or_no_vote_slash_raw':'Accrued adjustment for wrong or absent voting, in integer UMA units; application to stake requires separate evidence.',
'cross_chain_match_grade':'Strength of the native identity match across chains, as defined in the linkage rule register.',
'dispute_end_time_utc':'UTC conversion of the recorded dispute-end time; not automatically the economic application time.',
'dispute_id':'Native Tellor dispute identifier; scoped to the Layer dispute module.',
'dispute_winner_reward_raw':'Gain component assigned to the dispute winner after separating returned principal, in request-currency integer units.',
'disputer':'Native address initiating the challenge; an address does not identify an independent organization.',
'duration_hours':'Elapsed hours from the request event to settlement, or to the common cutoff for an unresolved request.',
'dvm_reference_time_utc':'UTC rendering of the DVM request-reference timestamp used in identity; not an execution clock.',
'dvm_resolved_price_raw':'Resolved signed integer in the Ethereum DVM request; special values preserve native meaning.',
'dvm_status':'Lifecycle status of the matched Ethereum DVM request under the retained evidence.',
'dvm_time':'Native DVM request-reference timestamp retained in the identity link, as an integer-second string.',
'economic_status':'Accounting qualification of the request under the recorded economic rule.',
'effective_bond_raw':'Reconstructed effective bond in integer request-currency units; decision-time use requires historical parameter binding.',
'end_label_allocation_raw':'Hypothetical full epoch entitlement assigned to the UTC end-label day; not an observed payment.',
'epoch_amount_raw':'Total retained entitlement assigned to the reward epoch in integer native units.',
'epoch_seconds':'Duration of the native half-open reward-epoch interval in seconds.',
'expiration_time_utc':'UTC conversion of the proposal expiry or recorded deadline; not a later execution event.',
'explicit_report_reward_raw':'Configured reward attributed to the settlement under the retained flow rule, separately from winner gain.',
'final_fee_raw':'Final fee parameter in integer request-currency units; a parameter alone does not prove payment.',
'followup_end_utc':'Observed settlement time, or the common cutoff if settlement is unobserved.',
'gross_payout_raw':'Gross settlement payout in integer request-currency units, before separating returned principal and gain.',
'identifier':'Native oracle identifier for the requested question type, retained for cross-chain identity matching.',
'market_end_utc':'Scheduled market end from application metadata; distinct from oracle resolution and metadata retrieval.',
'metadata_audit_time_utc':'UTC time of the retained interface audit; not a native economic-event time.',
'metadata_closed_utc':'Application metadata closed-time label; not independently established as oracle settlement.',
'metadata_created_utc':'Creation-time label supplied by application metadata; not a blockchain execution time.',
'metadata_updated_utc':'Update-time label supplied by application metadata; not proof of proposal-time availability.',
'observed_event_days':'Number of distinct UTC dates with retained eligible events in this weekly typed group; not observed exposure days.',
'oo_settled_price_raw':'Native integer price recorded in Polygon OOv2 settlement.',
'oracle_timestamp_utc':'UTC rendering of the oracle payload timestamp, distinct from the block execution clock.',
'oracle_update_time_utc':'UTC conversion of the feed updated-at label; not a separately verified transaction timestamp.',
'overlap_seconds':'Seconds of overlap between the native epoch interval and this UTC day.',
'parent_request_hash':'Ethereum parent-side request identity retained by the cross-chain linkage rule.',
'payment_time_utc':'UTC execution clock of an event qualifying under the table payment rule; null when no supported payment clock exists.',
'payout_qc_gap_raw':'Observed payout minus the amount expected under the retained settlement rule, in integer request-currency units.',
'principal_returned_raw':'Principal component returned within the gross payout; nonadditive with that gross transfer.',
'proposed_price_raw':'Proposed signed native integer at the proposal event; special values are preserved.',
'proposer':'Address recorded as proposer at the OOv2 proposal event.',
'requester':'Address requesting the OOv2 observation; role histories use requester occurrences only.',
'protocol_fee_raw':'Fee component assigned to the protocol recipient under the retained settlement rule, in integer request-currency units.',
'question_id':'Application question identifier linked to the native request; not a substitute for the OOv2 request key.',
'release_time_utc':'Observed release event time for a Tellor jail lifecycle; distinct from the scheduled release.',
'scheduled_release_time_utc':'Native scheduled end of the Tellor jail interval; not proof that release executed then.',
'report_reference_time_utc':'UTC conversion of the challenged report reference timestamp; distinct from dispute initiation.',
'reporter':'Native Tellor reporter address associated with the challenged observation.',
'request_index':'Native VotingV2 request index used to attribute an accrued voter adjustment.',
'request_reference_time_utc':'UTC rendering of the request payload timestamp used in native identity; not request-event execution time.',
'request_time':'Native OOv2 request-reference timestamp, retained as an integer-second string for identity reconstruction.',
'request_utc':'UTC execution time of the RequestPrice event starting lifecycle follow-up.',
'resolved_price_consistent':'Whether the linked Ethereum resolution and Polygon settled integer agree exactly.',
'reward_epoch_id':'Native Flare reward-epoch identifier; support boundaries are supplied separately.',
'reward_refunded_or_rolled_raw':'Configured reward removed from settlement attribution by the recorded refund or rollover rule.',
'right_censored':'True when no settlement is retained by the common cutoff; not a failure label.',
'sample_tier':'Retained source-cohort classification; interpretation is defined in the source sample register.',
'settlement_flow_exact':'Whether observed token flows reconcile exactly to the request settlement under the registered rule.',
'settlement_transfer_raw':'Observed qualifying token-transfer sum in the settlement transaction, in integer request-currency units.',
'settlement_utc':'UTC execution time of the Settle event; null for unresolved requests.',
'signing_policy_address':'Address assigned an integer signing weight by the archived epoch policy.',
'snapshot_time_utc':'UTC time associated with a retained state snapshot; not a historical execution event.',
'stamped_ancillary_exact':'Exact equality under the registered transformation from child ancillary data to the stamped parent request.',
'start_voting_round_id':'First voting-round identifier supported by the archived signing policy.',
'status':'Native lifecycle status carried from the retained request table.',
'uniform_allocation_raw_display':'Floating-point display of epoch_amount_raw * overlap_seconds / epoch_seconds; hypothetical, with exact numerator and denominator retained.',
'unmatched_reason':'Reason no evidence match was made; null when no unmatched reason is recorded.',
'vote_result':'Native Tellor dispute outcome; not independent factual truth.',
'voter':'Native voter/staker address associated with a request accrual or net stake application.',
'week_start_utc':'Inclusive Monday midnight UTC starting the half-open weekly aggregation interval.',
}

def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--deposit',required=True);a=ap.parse_args();root=Path(a.root).resolve();dep=Path(a.deposit).resolve();meta=dep/'metadata'
    # Regenerated sensitivity tables replace only their corresponding deposit links.
    for src in (root/'data/sensitivity').glob('*.parquet'):
        dst=dep/'data/sensitivity'/src.name
        if dst.exists():dst.unlink()
        shutil.copyfile(src,dst)
    cat=json.loads((meta/'table_catalog.json').read_text());cro=json.loads((dep/'croissant.json').read_text());dic=pd.read_csv(meta/'field_dictionary.csv',keep_default_na=False);lookup={(x['table_path'],x['field']):i for i,x in dic.iterrows()}
    for row in cat:
        file=dep/row['path'];row['bytes']=file.stat().st_size;row['sha256']=sha(file);row['rows']=pq.read_metadata(file).num_rows
        for f in pq.read_schema(file):dic.loc[lookup[(row['path'],f.name)],'arrow_type']=str(f.type)
    for i,row in dic.iterrows():
        if row['definition_status']=='requires_additional_semantic_review' and row['field'] in DEFS:
            dic.loc[i,['definition','definition_status']]=[DEFS[row['field']],'defined_by_revision_rule']
    desc={(x.table_path,x.field):x.definition for x in dic.itertuples()}
    distributions={x['@id']:x for x in cro['distribution']}
    for row in cat:distributions['files/'+row['path']]['sha256']=row['sha256']
    cro['@context']['subField']='cr:subField';cro['@context']['readLines']='cr:readLines'
    # Flattened Parquet mirrors provide portable extraction of two nested Parquet structures.
    for rec in cro['recordSet']:
        path=rec['@id'].removeprefix('records/')+'.parquet'
        for field in rec['field']:field['description']=desc[(path,field['name'])]
        if rec['name'] not in ['tellor_dispute_votes','tellor_disputes']:continue
        table=pq.read_table(dep/path);mirror=meta/'croissant_sources'/(rec['name']+'.parquet');mirror.parent.mkdir(exist_ok=True)
        flat=table
        while any(pa.types.is_struct(f.type) for f in flat.schema):flat=flat.flatten()
        pq.write_table(flat,mirror,compression='zstd')
        mid='files/'+str(mirror.relative_to(dep));cro['distribution'].append({'@type':'cr:FileObject','@id':mid,'name':str(mirror.relative_to(dep)),'description':'Flattened leaf-value mirror for nested Croissant extraction; original structured Parquet remains authoritative.','contentUrl':str(mirror.relative_to(dep)),'encodingFormat':'application/x-parquet','sha256':sha(mirror)})
        def nested(f,id,pathparts):
            x={'@type':'cr:Field','@id':id,'name':f.name,'description':'Retained native component '+'.'.join(pathparts)+'.'}
            if pa.types.is_struct(f.type):x['subField']=[nested(child,id+'/'+child.name,pathparts+[child.name]) for child in f.type]
            else:
                x['dataType']='sc:Boolean' if pa.types.is_boolean(f.type) else 'sc:Integer' if pa.types.is_integer(f.type) else 'sc:DateTime' if pa.types.is_timestamp(f.type) else 'sc:Float' if pa.types.is_floating(f.type) else 'sc:Text'
                x['source']={'fileObject':{'@id':mid},'extract':{'column':'.'.join(pathparts)}}
            return x
        rec['field']=[{**nested(f,rec['@id']+'/'+f.name,[f.name]),'description':desc[(path,f.name)]} for f in table.schema]
    # Version describes a local draft and is not a published release assertion.
    cro['version']='0.1.0-local.20261026'
    (meta/'table_catalog.json').write_text(json.dumps(cat,indent=2));pd.DataFrame([{**x,'products':';'.join(x['products'])} for x in cat]).to_csv(meta/'file_manifest.csv',index=False);dic.to_csv(meta/'field_dictionary.csv',index=False);(dep/'croissant.json').write_text(json.dumps(cro,indent=2))
    for f in ['key_validation.json','validation.json']:shutil.copy2(dep.parent/'temporal_core'/f,meta/('core_'+f))
    source=root/'code/load_core_with_utc.py';(dep/'code').mkdir(exist_ok=True);shutil.copy2(source,dep/'code'/source.name)
    old=meta/'temporal_native/remaining_tasks.csv'
    if old.exists():old.rename(old.with_name('remaining_tasks_at_guide2_historical.csv'))
    status={'logical_products':10,'viewer_configs':10,'physical_parquet_tables':len(cat),'croissant_recordsets':len(cro['recordSet']),'croissant_nested_leaf_mirrors':2,'dictionary_entries':len(dic),'all_paths_exist':all((dep/x['path']).is_file() for x in cat),'unique_paths':len({x['path'] for x in cat})==len(cat),'field_count_matches':len(dic)==sum(len(pq.read_schema(dep/x['path'])) for x in cat),'definition_status_counts':dic.definition_status.value_counts().to_dict(),'human_semantic_review':'not_completed'}
    (meta/'consistency_validation.json').write_text(json.dumps(status,indent=2));print(json.dumps(status))

if __name__=='__main__':main()

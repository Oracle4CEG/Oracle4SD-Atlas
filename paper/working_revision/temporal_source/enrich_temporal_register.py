"""Attach acquisition boundaries and original source bindings to time audits."""
from pathlib import Path
import argparse,csv,json
import pyarrow.parquet as pq
import pandas as pd

ap=argparse.ArgumentParser();ap.add_argument('--atlas-root',type=Path,required=True);ap.add_argument('--source-root',type=Path,required=True);ap.add_argument('--project-root',type=Path,required=True);a=ap.parse_args()
meta=a.project_root/'supplementary/temporal'
def read(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
def write(p,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('w',newline='',encoding='utf-8') as f:w=csv.DictWriter(f,fieldnames=keys);w.writeheader();w.writerows(rows)
scopes={r['branch']:r for r in read(a.project_root/'supplementary/implementation_register.csv')}
canonical={r['path']:r for r in read(a.atlas_root/'metadata/repaired_full_data_inventory.csv')}
fd=json.loads((a.atlas_root/'metadata/repaired_atlas_20261012/field_dictionary.json').read_text())
code={}
for r in fd:code.setdefault(r['path'],set()).update(r.get('source_code_references',[]))
units={
'chainlink_eth_usd_reports':'native feed log',
'chainlink_event_link_flow_qc':'staking event and token-flow reconciliation',
'chainlink_link_flows':'LINK transfer log',
'chainlink_staking_v02_events':'staking configuration, accounting or action log',
'chronicle_ethereum_events':'Scribe/ScribeOptimistic log',
'chronicle_redstone_settlement_interfaces':'protocol interface assessment',
'dia_staking_events':'staking log',
'dia_staking_withdrawals':'reconciled staking-position withdrawal',
'ecosystem_observability_evidence':'protocol observability assessment',
'flare_beneficiary_chill_events':'BeneficiaryChilled event',
'flare_beneficiary_chill_state':'beneficiary state at cutoff',
'flare_provider_conditions':'provider and reward epoch',
'flare_provider_failures':'provider failure and reward epoch',
'flare_provider_feed_performance':'provider, feed and reward epoch',
'flare_provider_passes':'provider and reward epoch',
'flare_reward_claim_epoch_qc':'reward epoch reconciliation at cutoff',
'flare_reward_claim_events':'RewardClaimed event, including separately marked fee burns',
'flare_reward_claims':'beneficiary claim-type entitlement in reward epoch',
'flare_reward_component_attribution':'provider, reward component and epoch',
'flare_reward_epochs':'reward epoch',
'flare_voter_registrations':'voter registration in reward epoch',
'phase4_oracle_economic_interfaces':'protocol interface audit',
'polygon_adapter_events':'adapter event log',
'polygon_child_tunnel_events':'child-tunnel event log',
'polygon_oov2_events':'OOv2 event log',
'polygon_uma_gamma_links':'request and off-chain market-metadata link',
'polygon_uma_request_flow_qc':'request settlement-flow reconciliation',
'polygon_uma_request_rounds':'OOv2 request lifecycle',
'polygon_uma_token_flows':'token transfer log',
'polymarket_decision_time_price_onchain_validation':'sample-side price comparison',
'polymarket_decision_time_price_provenance':'sample price-acquisition provenance',
'polymarket_decision_time_prices':'selected request at proposal-time landmark',
'polymarket_decision_time_web_evidence':'selected request and archived web page',
'polymarket_decision_time_web_provenance':'sample-page acquisition provenance',
'polymarket_gamma_markets':'off-chain market metadata record',
'pyth_ois_economic_events':'reward SPL-token transfer',
'pyth_ois_historical_observability':'historical-field observability assessment',
'pyth_ois_instructions':'outer program instruction, including retained failed calls',
'pyth_ois_publisher_epoch_factors':'publisher and reward epoch',
'pyth_ois_reward_epochs':'retained reward epoch',
'pyth_ois_slash_counters':'publisher lifetime counter at snapshot',
'pyth_ois_stake_events':'stake-position mutation instruction',
'redstone_ethereum_push_events':'Push-adapter event log',
'tellor_aggregate_height_index':'query aggregate index entry',
'tellor_dispute_payments':'dispute payment-related execution record',
'tellor_dispute_votes':'dispute vote execution record',
'tellor_disputes':'dispute state record',
'tellor_jail_events':'jail or release event',
'tellor_jail_lifecycles':'paired jail/release lifecycle',
'tellor_legacy_selector_reward_accruals':'legacy selector accrual event (empty retained table)',
'tellor_liveness_reward_distributions_full':'liveness reward distribution',
'tellor_micro_reports':'native new_report event',
'tellor_query_tip_funding':'tip funding event',
'tellor_reporter_reward_accruals_full':'reporter reward accrual component',
'tellor_tip_withdrawals_realized':'tip-to-stake withdrawal execution',
'uma_dvm_requests':'DVM request',
'uma_dvm_staking_events':'DVM staking or accounting log',
'uma_dvm_voter_payoffs':'voter-level signed accrual event',
'uma_dvm_votes_events':'commit or reveal event',
'uma_phase2_dvm_negative_slash_panel':'negative DVM accrual record',
'uma_phase2_request_panel':'selected request analytical record',
'uma_polygon_ethereum_grade_a_links':'attempted Polygon/Ethereum request link',
'decision_samples':'eligible UMA prediction request',
'splits':'prediction-sample partition membership'}
rows=read(meta/'temporal_registry.csv')
for r in rows:
    can=canonical[r['path']];r['canonical_release_sha256']=can['sha256'];r['canonical_release_url']=can['download_url']
    r['canonical_identity_matches_input']=str(can['sha256']==r['input_sha256']).lower()
    r['native_builder_references']=';'.join(sorted(code.get(r['path'],[])))
    if r['audit_status'] != 'full row-preserving UTC annotation completed':
        r['observation_unit']='downstream table-defined cohort/projection; see canonical dictionary'
        continue
    r['observation_unit']=units[r['table']]
    scope=scopes.get(r.get('branch',''))
    if scope:
        r['mechanism_version']=scope['mechanism_version'];r['historical_source_versions']=scope['historical_source_versions']
        r['registered_native_start']=scope['declared_start_boundary'];r['registered_native_end']=scope['declared_end_boundary']
        r['registered_boundary_scope']='Branch register context; individual table support is in clock_statistics.csv'
        r['source_manifest_files']=scope['manifest_files']
    fields=pq.ParquetFile(a.source_root/r['path']).schema_arrow.names
    r['event_class_field']=';'.join(x for x in ['event','event_name','event_type','semantic_class','instruction'] if x in fields)
    r['actor_role_fields']=';'.join(x for x in ['actor','actor_role','beneficiary','voter','reporter','publisher','staker','owner','reward_role'] if x in fields)
    r['native_identity_fields']=';'.join(x for x in fields if x in ['source_tx','transaction_hash','tx_hash','signature','log_index','source_log_index','source_tx_index','source_event_index','outer_instruction_index','inner_transfer_index','oo_request_id','dvm_request_id','query_id','reporter','meta_id','reward_epoch_id','epoch_id','publisher','voter_address','sample_id','staking_store_index'])
    r['identity_note']='Retained identity fields; composite uniqueness is table-specific, not newly asserted by this conversion'
write(meta/'temporal_registry.csv',rows)

# Keep the frozen 21 common projections separate from the 64 annotated inputs.
old=read(a.atlas_root/'metadata/repaired_atlas_20261012/time_coverage.csv')
for r in old:
    r['timestamp_fraction']=int(r['timed_rows'])/int(r['rows'])
    r['source_release']='atlas-repaired-20261012; frozen common projection'
    n=r['native_table']
    r['clock_meaning']=('epoch_end_label' if n in ['flare_provider_conditions','flare_reward_claims','pyth_ois_publisher_epoch_factors'] else 'cutoff_state_label' if n=='flare_beneficiary_chill_state' else 'absent' if int(r['timed_rows'])==0 else 'request_reference_time' if n=='polygon_uma_request_rounds' else 'service_window_current_update' if n=='chainlink_eth_usd_reports' else 'native event label; integer seconds')
    r['coverage_interpretation']='Availability among retained projected rows; not a continuous-coverage percentage'
write(meta/'legacy_projection_time_audit.csv',old)

# Coverage is not inferred from valid timestamps. Preserve declared intervals
# and the level of evidence without assigning an unsupported coverage fraction.
intervals=[]
for b,r in scopes.items():
    intervals.append(dict(branch=b,interval_kind='registered acquisition boundary',start=r['declared_start_boundary'],end=r['declared_end_boundary'],boundary_inclusivity='see per-contract/source manifest; EVM scan endpoints inclusive where registered',clock='native block/height/epoch or archive time',evidence=r['manifest_files'],evidence_status='historical manifest retained; complete acquisition receipts not reaudited here',verified_coverage_fraction='',first_event_is_not_scan_start=True))
write(meta/'coverage_interval_evidence.csv',intervals)
dictionary=[r for r in read(meta/'temporal_clock_dictionary.csv') if r['field']!='event_time_status']
for r in rows:
    if r['audit_status'] != 'full row-preserving UTC annotation completed':continue
    dictionary.append(dict(table=r['table'],branch=r['branch'],field='event_time_status',arrow_type='string',original_field='native clock presence and explicit transformation route',original_unit='category',conversion_rule='Deterministic clock status assignment',temporal_meaning='native_clock; retained_same_chain_block_join; missing_native_event_time; missing_retained_block_time; epoch_record_not_an_instant_event; no_event_clock_for_this_record',precision_policy='not applicable',missingness='No null status; does not measure acquisition completeness',input_sha256=r['input_sha256'],source_code='oracle4sd-temporal-v1-20261026'))
write(meta/'temporal_clock_dictionary.csv',dictionary)
print('Enriched 95-table register and clock/status dictionary; retained 21-projection baseline audit.')

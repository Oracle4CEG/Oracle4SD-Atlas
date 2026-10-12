"""Materialize file, field and source documentation from a validated release."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
DEFINITIONS={
 'schema_version':'Version of the common economic interpretation and field contract.',
 'accountability_event_id':'SHA-256 identity derived from protocol-native keys; identifies this representation, not a person or a factual proposition.',
 'oracle_network':'Oracle protocol branch; not necessarily the chain that stores or settles the observation.',
 'protocol':'Oracle protocol branch of the observation.',
 'mechanism_family':'Registered protocol incentive/adjudication mechanism category.',
 'security_chain':'Chain or native execution system recording the security or settlement evidence.',
 'delivery_chain':'Chain receiving the oracle result, when observed.',
 'accountability_unit_type':'Protocol-native unit family; interpretations are enumerated in semantic_decisions.json.',
 'accountability_unit_id':'Native object identity; one object can contribute multiple typed events.',
 'event_granularity':'Specific kind of native action/component represented by this row.',
 'event_time_unix':'Observed native event timestamp in UTC Unix seconds; null when the retained source has no time.',
 'actor':'Public pseudonymous address or protocol identifier associated with this row, qualified by actor_role.',
 'actor_role':'Role of the actor for this observation; may be outcome-derived and is excluded from T0 predictive features.',
 'counterparty':'Other protocol participant or contract, when identified by native evidence.',
 'counterparty_role':'Role of the counterparty relative to the recorded action.',
 'reward_class':'Reward mechanism and economic stage; accrued, claimable and paid classes must not be combined.',
 'reward_amount_raw':'Integer amount associated with reward_class; this field alone does not imply payment.',
 'reward_asset':'Token contract, symbol or denomination for reward_amount_raw.',
 'reward_asset_decimals':'Number of decimal places for the reward asset; divide raw token units by 10**decimals.',
 'reward_accrual_time_unix':'UTC Unix seconds at which the entitlement accrues, if observed.',
 'reward_payment_time_unix':'UTC Unix seconds of an observed reward payment, if observed.',
 'penalty_class':'Penalty mechanism and realization stage; accrued penalties are not applied principal losses.',
 'penalty_accrued_raw':'Calculated negative accrual magnitude; not realized loss and not additive to the later applied net change.',
 'principal_slashed_raw':'Applied principal loss supported by native state/settlement evidence. Null means no quantified applied loss is established.',
 'bond_forfeited_raw':'Posted bond amount forfeited under the settled protocol outcome, separate from returned principal and fees.',
 'fee_forfeited_raw':'Protocol fee component lost by the affected participant, separate from the bond.',
 'reward_forfeited_raw':'Previously eligible/accrued reward lost under protocol rules; not principal slashing.',
 'penalty_asset':'Token identifier or denomination for the penalty amount.',
 'penalty_asset_decimals':'Decimal precision of the penalty token.',
 'nonmonetary_penalty':'Native restriction such as jail/chill, distinct from a quantified token loss.',
 'principal_locked_raw':'Observable participant principal at risk; for UMA the effective bond plus final fee, for Tellor the escrow amount, never report power.',
 'principal_returned_raw':'Participant principal included in a settlement return; excluded from token gain and reward.',
 'principal_asset':'Token identifier or denomination of posted/returned principal.',
 'principal_asset_decimals':'Decimal precision of the principal token.',
 'truth_basis':'What the evidence establishes; protocol adjudication, signatures and state transitions are not independent factual truth.',
 'outcome_status':'Protocol-native outcome or classified state; interpretation requires native_table and rule_id.',
 'external_truth_available':'Whether an independent factual reference is supplied, not merely a protocol vote.',
 'service_window_seconds':'Elapsed seconds in the observed service interval.',
 'service_threshold_seconds':'Registered protocol service threshold in seconds.',
 'source_event':'Name of the native log, instruction or state evidence used.',
 'source_tx':'Source transaction hash/signature; chain identity must also be retained.',
 'source_block':'Native block number/height, not a wall-clock timestamp.',
 'source_log_index':'Position of the source log within its transaction/block convention.',
 'source_contract':'Contract/program address emitting or governing the evidence.',
 'rule_id':'Versioned transformation or interpretation rule identifier.',
 'parameter_version':'Protocol configuration or parameter version used for interpretation.',
 'observability_grade':'Evidence/coverage grade A, B, C or U; not a factual truth or economic validity guarantee.',
 'confidence_grade':'Registered linkage/interpretation grade A, B, C or U.',
 'native_table':'Name of the native input table to which the observation can be traced.',
 'sample_tier':'Declared cohort or scope category; cohorts can overlap.',
 'interpretation_note':'Source-specific meaning, stage distinction or limitation retained with the record.',
 'episode_id':'Deterministic identity of a native lifecycle or actor/request episode.',
 'unit_id':'Native request, dispute, publisher epoch or actor identifier for the episode.',
 'episode_type':'Protocol-specific definition of the lifecycle observation unit.',
 'start_time':'Native request/epoch time in UTC Unix seconds; unavailable event timestamps are retained as null.',
 'end_time':'Observed terminal timestamp when available; a Tellor deadline is not substituted for execution time.',
 'right_censored':'Lifecycle was not observed to complete before the common cutoff; not a zero payoff.',
 'challenged':'Observed request/dispute challenge or protocol-specific accountability condition; consult episode_type.',
 'transfer_confirmed':'Native payment evidence satisfies the specified reconciliation rule.',
 'state_change_confirmed':'Native applied state change is established; an accrual alone is false.',
 'cross_chain_flag':'Verified cross-chain link in the completed observation; outcome-derived and excluded from T0 model inputs.',
 'gross_payout_raw':'Total observed payout including returned principal and incremental token gain.',
 'reward_paid_raw':'Incremental reward/gain component of a verified payment, excluding returned principal.',
 'reward_accrued_raw':'Quantified accrued reward entitlement; not a rate or evidence of payment.',
 'reward_claimable_raw':'Quantified entitlement eligible for claim; absence of a claim is not a zero payout.',
 'configured_reward_raw':'Configured incentive, retained separately from accrued or paid amounts.',
 'configured_reward_rate_raw':'Fixed-point Pyth reward-rate parameter; not a token amount.',
 'signed_accrual_delta_raw':'Signed DVM accounting adjustment before application, in raw token units.',
 'signed_stake_delta_raw':'Signed applied stake adjustment where observed; null for request-level DVM accruals.',
 'total_profit_raw':'Total economic profit after all costs; null because complete off-chain and opportunity costs are unavailable.',
 'voter_reward_pool_raw':'Tellor reward pool for dispute voters; not income of the reporter in this row.',
 'protocol_dispute_deadline':'Recorded Tellor dispute deadline, retained separately from observed execution time.',
 'report_power':'Native reporting/voting weight; not a token balance or locked principal.',
 'state_sequence':'Canonical interpreted states; order alone does not provide decision-time evidence availability.',
}


def describe(field):
    if field in DEFINITIONS:return DEFINITIONS[field]
    if field.endswith('_raw'):
        return 'Protocol-native '+field[:-4].replace('_',' ')+' as an exact decimal integer string. Interpret its stage and asset using the native table and source rule; do not infer realization from a nonzero value.'
    if field.endswith(('_tx','_transaction','_hash','_signature')):
        return field.replace('_',' ')+' identifier from native source evidence; meaningful only with the chain/program context.'
    if field.endswith(('_time_unix','_timestamp_unix')):
        return field.replace('_',' ')+' in UTC Unix seconds; null represents an unobserved value, not zero.'
    if field.endswith('_decimals'):
        return 'Base-10 precision for the associated token amount or fixed-point parameter; not a conversion across assets.'
    if field.endswith('_outcome_only'):
        return 'Post-decision '+field[:-13].replace('_',' ')+'; evaluation only and excluded from predictive features.'
    if field.startswith('state_'):
        return 'Indicator/count for the canonical state '+field[6:].upper()+'. This retrospective state feature is not automatically available at decision time.'
    return 'Native or derived '+field.replace('_',' ')+'. Retained with its Arrow type and table-specific source references below; cross-protocol comparability is not implied.'


def build(release):
    release=Path(release);metadata=release/'metadata';metadata.mkdir(exist_ok=True)
    inventory=json.loads((metadata/'file_manifest.json').read_text())
    code={str(p.relative_to(ROOT)):p.read_text() for p in (ROOT/'code/reconstruction').rglob('*.py')}
    dictionaries=[];catalog=[]
    for item in inventory:
        path=release/item['path'];name=path.stem;schema=pq.read_schema(path)
        refs=[key for key,text in code.items() if name in text]
        stage='rebuilt_application' if '/applications/oata/' in item['path'] or '/financial_benchmark/' in item['path'] else 'native_or_curated_snapshot'
        if name in {'accountability_events','sample_b_observable_accountability','sample_c_strict_honesty_events','economic_semantics_events','realized_reward_slash_events'}:stage='rebuilt_common_or_economic_layer'
        catalog.append(dict(**item,table=name,stage=stage,code_references=refs,
                            cutoff='2026-06-30T23:59:59Z',original_snapshot_inventory='metadata/full_data_inventory.csv',
                            human_agent_roles='Native observations are protocol records; transformations and classifications are software-generated. Revision rules and regression checks are retained in source control.'))
        for field in schema:
            dictionaries.append(dict(table=name,path=item['path'],field=field.name,arrow_type=str(field.type),
                                     nullable=field.nullable,definition=describe(field.name),
                                     definition_scope='reviewed_common_or_episode_field' if field.name in DEFINITIONS else 'native_field_with_source_code_reference',
                                     missing_rule='Null is missing/unknown/not applicable according to native context; only explicit verified zero is zero. Right censoring is a separate lifecycle state.',
                                     source_code_references=refs))
    (metadata/'table_catalog.json').write_text(json.dumps(catalog,indent=2)+'\n')
    (metadata/'field_dictionary.json').write_text(json.dumps(dictionaries,indent=2)+'\n')
    con=duckdb.connect(config={'threads':2,'memory_limit':'2GB'})
    common=release/'data/curated/parquet/accountability_events.parquet'
    con.read_parquet(str(common)).create_view('common')
    coverage=con.execute('SELECT oracle_network,native_table,count(*) AS rows,count(event_time_unix) AS timed_rows,min(event_time_unix) AS first_time,max(event_time_unix) AS last_time FROM common GROUP BY ALL ORDER BY 1,2').fetchdf()
    coverage.to_csv(metadata/'time_coverage.csv',index=False)
    schema=json.loads((ROOT/'schemas/accountability_events_v2.schema.json').read_text())
    for name,properties in schema['properties'].items(): properties['description']=describe(name)
    (metadata/'accountability_events.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
    report=dict(tables=len(catalog),fields=len(dictionaries),blank_definitions=sum(not x['definition'].strip() for x in dictionaries),
                scope='Full field/type/source-reference coverage; native field documentation is not an independent scientific provenance attestation.')
    (metadata/'documentation_validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--release',required=True)
    build(p.parse_args().release)

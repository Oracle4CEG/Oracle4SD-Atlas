"""Reusable accounting extracts, preserving non-additive stages and missing application links."""
from pathlib import Path
import argparse,json
import duckdb
def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);a=p.parse_args();b=Path(a.native)/'data/curated/parquet';o=Path(a.out);o.mkdir(parents=True,exist_ok=True);c=duckdb.connect(config={'threads':2,'memory_limit':'3GB'})
    def t(n):return f"read_parquet('{b/(n+'.parquet')}')"
    queries={
    'uma_settlement_accounting':f"""SELECT r.oo_request_id,r.currency asset,6 asset_decimals,r.economic_status,r.effective_bond_raw,r.final_fee_raw,r.principal_returned_raw,r.explicit_report_reward_raw,r.dispute_winner_reward_raw,r.reward_refunded_or_rolled_raw,r.protocol_fee_raw,r.gross_payout_raw,f.settlement_transfer_raw,f.settlement_flow_exact,r.payout_qc_gap_raw,r.source_tx request_tx,r.settlement_tx,r.oo_request_id nonadditive_group FROM {t('polygon_uma_request_rounds')} r LEFT JOIN {t('polygon_uma_request_flow_qc')} f USING(oo_request_id)""",
    'tellor_dispute_reconciliation':f"""SELECT dispute_id,vote_result,reporter,disputer,asset,asset_decimals,slash_amount_raw initiation_escrow_raw,CASE WHEN vote_result IN ('SUPPORT','NO_QUORUM_MAJORITY_SUPPORT') THEN slash_amount_raw ELSE '0' END applied_loss_under_recorded_outcome_rule_raw,CASE WHEN vote_result LIKE '%SUPPORT' THEN 'report_rejected' ELSE 'report_supported' END protocol_report_outcome,NULL::TIMESTAMPTZ application_time_utc,source_tx,source_block,'historical_rule_binding_qualified' evidence_status FROM {t('tellor_disputes')}""",
    'dvm_accrual_vs_applied':f"""SELECT dvm_request_id,voter,request_index,signed_slash_delta_raw accrued_adjustment_raw,correct_vote_redistribution_raw,wrong_or_no_vote_slash_raw,NULL::VARCHAR request_attributed_applied_delta_raw,'application_not_uniquely_attributed_to_request' missing_reason,event_time_utc accrual_time_utc,source_tx,source_block,log_index,'accrual_not_additive_with_net_application' stage_rule FROM {t('uma_dvm_voter_payoffs')}""",
    'dvm_net_stake_applications':f"""SELECT actor voter,raw_data_words[1] recorded_net_adjustment_raw,raw_data_words[2] post_stake_raw,CASE WHEN try_cast(raw_data_words[1] AS HUGEINT)>=0 OR try_cast(raw_data_words[2] AS HUGEINT)>0 THEN raw_data_words[1] END supported_net_stake_delta_raw,CASE WHEN try_cast(raw_data_words[1] AS HUGEINT)<0 AND try_cast(raw_data_words[2] AS HUGEINT)=0 THEN 'pre_state_required_for_clipping' ELSE 'net_application_state_rule' END evidence_status,event_time_utc,source_tx,source_block,log_index,'net_application_not_additive_with_request_accrual' stage_rule FROM {t('uma_dvm_staking_events')} WHERE event='VoterSlashApplied'"""}
    for name,q in queries.items():
        c.execute(f"COPY ({q}) TO '{o/(name+'.parquet')}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    (o/'accounting_queries.json').write_text(json.dumps(queries,indent=2));print({n:c.execute(f'SELECT count(*) FROM ({q})').fetchone()[0] for n,q in queries.items()})
if __name__=='__main__':main()

"""Object-level historical correction ledger and receipt-bound cross-chain case."""
import argparse,json,hashlib
from pathlib import Path
import pandas as pd,duckdb

def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',required=True);p.add_argument('--atlas',required=True);p.add_argument('--out',required=True);a=p.parse_args();root=Path(a.source).resolve();atlas=Path(a.atlas).resolve();out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);c=duckdb.connect(config={'threads':2,'memory_limit':'3GB'})
    native=root/'data/curated/parquet';old=root/'data/applications/oata/accountability_episodes.parquet'
    def t(n):return f"read_parquet('{native/(n+'.parquet')}')"
    c.execute(f"CREATE VIEW old_episode AS SELECT * FROM read_parquet('{old}')")
    bases=f"FROM old_episode e JOIN {t('polygon_uma_request_rounds')} r ON e.unit_id=r.oo_request_id WHERE e.episode_type='uma_oov2_request'"
    rules=[
      ('UMA_CHALLENGE_V2',42676,40992,'B',f"SELECT r.oo_request_id object_id,'Polygon' AS chain,r.source_contract,r.source_tx,r.log_index source_log_index,'challenged' AS field,e.challenged::VARCHAR before_value,'false' after_value,'Native dispute transaction and nonzero disputer required' reason {bases} AND e.challenged AND (r.dispute_tx IS NULL OR r.disputer='0x0000000000000000000000000000000000000000')"),
      ('UMA_SETTLEMENT_V2',42676,850,'B',f"SELECT r.oo_request_id,'Polygon',r.source_contract,r.source_tx,r.log_index,'transfer_confirmed',e.transfer_confirmed::VARCHAR,'false','Unsettled request cannot be a completed payment' {bases} AND e.transfer_confirmed AND r.settlement_tx IS NULL"),
      ('UMA_WINNER_COMPONENT_V2',42676,834,'B',f"SELECT r.oo_request_id,'Polygon',r.source_contract,r.settlement_tx,r.log_index,'reward_paid_raw',e.reward_paid_raw,(try_cast(r.explicit_report_reward_raw AS HUGEINT)+try_cast(r.dispute_winner_reward_raw AS HUGEINT))::VARCHAR,'Separate returned principal from configured reward and unburned winner bond' {bases} AND r.economic_status LIKE 'settled_disputed_%' AND try_cast(e.reward_paid_raw AS HUGEINT) IS DISTINCT FROM try_cast(r.explicit_report_reward_raw AS HUGEINT)+try_cast(r.dispute_winner_reward_raw AS HUGEINT)"),
      ('TELLOR_OUTCOME_V2',13,13,'B',f"SELECT d.dispute_id,'tellor-1',NULL,d.source_tx,NULL,'strict_event_class',s.strict_event_class,CASE WHEN d.vote_result LIKE '%SUPPORT' THEN 'tellor_report_rejected' ELSE 'tellor_report_supported' END,'SUPPORT supports the disputer' FROM {t('sample_c_strict_honesty_events')} s JOIN {t('tellor_disputes')} d ON s.accountability_unit_id=d.dispute_id WHERE s.native_table='tellor_disputes' AND ((s.outcome_status LIKE '%SUPPORT' AND s.strict_event_class<>'tellor_report_rejected') OR (s.outcome_status LIKE '%AGAINST' AND s.strict_event_class<>'tellor_report_supported'))"),
      ('TELLOR_APPLIED_LOSS_V2',13,10,'B',f"SELECT d.dispute_id,'tellor-1',NULL,d.source_tx,NULL,'principal_slashed_raw',e.principal_slashed_raw,'0','Rejected challenge returns reporter stake; initial escrow is not final applied loss' FROM old_episode e JOIN {t('tellor_disputes')} d ON e.unit_id=d.dispute_id WHERE e.episode_type='tellor_dispute' AND d.vote_result NOT IN ('SUPPORT','NO_QUORUM_MAJORITY_SUPPORT') AND try_cast(e.principal_slashed_raw AS HUGEINT)>0"),
      ('DVM_ACCRUAL_V2',2663684,947128,'A',f"SELECT p.dvm_request_id||':'||p.voter||':'||p.source_tx||':'||p.log_index::VARCHAR,'Ethereum',p.source_contract,p.source_tx,p.log_index,'principal_slashed_raw',p.wrong_or_no_vote_slash_raw,NULL,'VoterSlashed is a signed accrual; applied net stake change requires separate evidence' FROM {t('uma_dvm_voter_payoffs')} p WHERE try_cast(p.wrong_or_no_vote_slash_raw AS HUGEINT)>0")]
    summaries=[];paths=[]
    for rid,n,expected,binding,q in rules:
        # First SELECT supplies names shared by the positional UNION-compatible queries.
        c.execute('CREATE OR REPLACE TEMP VIEW result AS '+q)
        cols=['object_id','chain','source_contract','source_tx','source_log_index','field','before_value','after_value','reason']
        actual_names=[x[0] for x in c.execute('SELECT * FROM result LIMIT 0').description]
        select=','.join('"'+x.replace('"','""')+'" AS "'+y+'"' for x,y in zip(actual_names,cols))
        dst=out/(rid+'.parquet')
        c.execute(f"COPY (SELECT {select},'{rid}' rule_id,'{binding}' historical_source_binding,'pending_author_review' human_review_status,'recomputed_from_archived_pre_revision_outputs_and_native_records' evidence_status FROM result) TO '{dst}' (FORMAT PARQUET, COMPRESSION ZSTD)")
        nactual=c.execute('SELECT count(*) FROM result').fetchone()[0];summaries.append(dict(rule_id=rid,population=n,before_violations=nactual,expected_archived=expected,count_matches=nactual==expected,after_violations=0,after_evidence='rule-transformed values; independent rebuilt-table check in reconstruction validation',historical_source_binding=binding));paths.append(str(dst))
    # Correct settlement locator: the round log identifies the request, not its settlement.
    pth=out/'UMA_WINNER_COMPONENT_V2.parquet'
    c.execute(f"COPY (SELECT l.* EXCLUDE(source_log_index),s.log_index source_log_index FROM read_parquet('{pth}') l LEFT JOIN {t('polygon_oov2_events')} s ON l.source_tx=s.source_tx AND l.object_id=s.oo_request_id AND s.event='Settle') TO '{out/'winner_fixed.parquet'}' (FORMAT PARQUET, COMPRESSION ZSTD)");(out/'winner_fixed.parquet').replace(pth)
    c.execute(f"COPY (SELECT * FROM read_parquet({paths!r},union_by_name=true)) TO '{out/'semantic_corrections.csv.gz'}' (FORMAT CSV, HEADER, COMPRESSION GZIP)")
    pd.DataFrame(summaries).to_csv(out/'semantic_summary.csv',index=False)
    (out/'ledger_provenance.json').write_text(json.dumps({'old_episode_sha256':sha(old),'old_sample_c_sha256':sha(native/'sample_c_strict_honesty_events.parquet'),'rules':[{ 'rule_id':x[0],'query':x[4]} for x in rules],'human_review':'No author sign-off supplied; fields remain pending.'},indent=2))
    # Build five-event registry from receipt/header evidence and decoded native event positions.
    case=root/'data/case_studies/uma_real_episode';timeline=pd.read_parquet(case/'lifecycle_timeline.parquet');records=[];checks=[]
    eventnames={'Request':'RequestPrice','Proposal':'ProposePrice','Dispute':'DisputePrice','DVM resolution':'RequestResolved','Settlement':'Settle'}
    caseid=pd.read_parquet(case/'cross_chain_link.parquet').iloc[0]
    raw=atlas/'data/data_source/uma_case/raw'
    for i,r in timeline.iterrows():
        chain=r.chain.lower();snapshot=json.loads((raw/(chain+'_rpc_snapshot.json')).read_text());receipt=snapshot['receipts'][r.tx]
        block=int(receipt['blockNumber'],16);tables=['dvm_request'] if chain=='ethereum' else ['oov2_events']
        dec=pd.read_parquet(case/(tables[0]+'.parquet'));match=dec[dec.source_tx.eq(r.tx)]
        if 'event' in match:match=match[match.event.eq(eventnames[r.stage])]
        if len(match)!=1:raise ValueError((r.stage,len(match)))
        d=match.iloc[0];log=int(d.log_index);event=next(x for x in receipt['logs'] if int(x['logIndex'],16)==log)
        headers=snapshot['blocks'];header=headers.get(str(block),headers.get(hex(block)))
        if header is None:header=next(v for v in headers.values() if int(v['number'],16)==block)
        for name,ok in [('successful_receipt',int(receipt['status'],16)==1),('header_hash',receipt['blockHash']==header['hash']),('block_time',int(header['timestamp'],16)==int(r.timestamp)),('event_contract',event['address'].lower()==str(d.source_contract).lower()),('event_transaction',event['transactionHash']==r.tx),('not_removed',not event.get('removed',False))]:checks.append(dict(event=r.stage,check=name,passed=bool(ok)))
        records.append(dict(event_id='T'+str(i+1),stage=r.stage,chain=r.chain,transaction_hash=r.tx,block_number=block,log_index=log,contract=d.source_contract,request_id=caseid.dvm_request_id if chain=='ethereum' else caseid.oo_request_id,event_time_utc=pd.to_datetime(r.timestamp,unit='s',utc=True),hours_since_request=r.hours_since_request,explorer_url=('https://etherscan.io/tx/' if chain=='ethereum' else 'https://polygonscan.com/tx/')+r.tx,evidence_status='archived_receipt_and_header_checked',human_review_status='pending_author_review'))
    caseout=out/'cross_chain';caseout.mkdir(exist_ok=True);events=pd.DataFrame(records);events.to_parquet(caseout/'five_transactions.parquet',index=False);events.to_csv(caseout/'five_transactions.csv',index=False)
    interval=[]
    for i in range(1,len(events)):
        x=events.iloc[i-1];y=events.iloc[i];interval.append(dict(start=x.event_id,end=y.event_id,elapsed_seconds=(y.event_time_utc-x.event_time_utc).total_seconds(),interpretation=['request_to_proposal','proposal_to_dispute','dispute_to_DVM_resolution_including_unresolved_transport','DVM_resolution_to_Polygon_settlement'][i-1],causal_decomposition_available=i!=3))
    pd.DataFrame(interval).to_csv(caseout/'intervals.csv',index=False)
    cash=pd.read_parquet(case/'economic_cashflows.parquet');cash.to_parquet(caseout/'cashflows.parquet',index=False)
    pd.read_parquet(case/'cross_chain_link.parquet').to_parquet(caseout/'identity_link.parquet',index=False)
    checks.extend([dict(check='same_native_request_identity',passed=bool(caseid.child_request_hash_exact and caseid.stamped_ancillary_exact and caseid.resolved_price_consistent)),dict(check='net_cashflow_zero',passed=int(cash.amount_raw.sum())==0),dict(check='elapsed_additivity',passed=sum(x['elapsed_seconds'] for x in interval)==int(timeline.iloc[-1].timestamp-timeline.iloc[0].timestamp))])
    (caseout/'unresolved_edges.json').write_text(json.dumps([{'edge':'Polygon child request -> Ethereum request acceptance','status':'identity_link_supported; complete relay transaction sequence not retained'},{'edge':'Ethereum result -> Polygon delivery','status':'matching resolution value retained; intermediate processing transactions not fully documented'},{'edge':'human explorer review','status':'pending_author_review'}],indent=2))
    (out/'validation.json').write_text(json.dumps({'passed':all(x['count_matches'] for x in summaries) and all(x['passed'] for x in checks),'semantic_rules':summaries,'case_checks':checks},indent=2))
    assert all(x['count_matches'] for x in summaries);assert all(x['passed'] for x in checks)
    print('Verified semantic correction populations and five-transaction archived case.')
if __name__=='__main__':main()

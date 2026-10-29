"""Construct the request-level UMA task; no model fitting or performance reporting."""
from pathlib import Path
import argparse,json,hashlib,heapq,math
from collections import defaultdict
import pandas as pd,numpy as np,duckdb

FEATURES=['log_bond_raw','log_final_fee_raw','log_reward_plus1_raw','reward_to_bond_ratio','liveness_hours','proposal_latency_hours','ancillary_bytes','proposer_prior_completed','proposer_prior_dispute_rate','proposer_prior_rejection_rate','requester_prior_completed','requester_prior_dispute_rate','requester_prior_rejection_rate','requester_is_polymarket_adapter','proposed_price_class','adapter_version']
EARLY=str(-(2**255))
def priceclass(v):return {'0':'binary_zero',str(10**18):'binary_one',str(5*10**17):'indeterminate_half',EARLY:'early_expiration'}.get(str(v),'other')
def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);a=p.parse_args();base=Path(a.native)/'data/curated/parquet';out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect();c.execute("SET TimeZone='UTC'")
    def t(n):return f"read_parquet('{base/(n+'.parquet')}')"
    query=f"""SELECT r.*,p.event_time_utc proposal_utc,p.transaction_index proposal_tx_index,p.log_index proposal_log_index,
    d.event_time_utc dispute_utc,s.event_time_utc settlement_utc,s.transaction_index settlement_tx_index,s.log_index settlement_log_index,
    l.cross_chain_match_grade,l.resolved_price_consistent,l.dvm_request_id,f.settlement_flow_exact
    FROM {t('polygon_uma_request_rounds')} r
    LEFT JOIN {t('polygon_oov2_events')} p ON r.oo_request_id=p.oo_request_id AND p.event='ProposePrice'
    LEFT JOIN {t('polygon_oov2_events')} d ON r.oo_request_id=d.oo_request_id AND d.event='DisputePrice'
    LEFT JOIN {t('polygon_oov2_events')} s ON r.oo_request_id=s.oo_request_id AND s.event='Settle'
    LEFT JOIN {t('uma_polygon_ethereum_grade_a_links')} l ON r.oo_request_id=l.oo_request_id
    LEFT JOIN {t('polygon_uma_request_flow_qc')} f ON r.oo_request_id=f.oo_request_id"""
    frame=c.execute(query).fetchdf();assert frame.oo_request_id.is_unique
    hist=frame[frame.sample_tier.eq('primary') & frame.proposal_utc.notna() & frame.settlement_utc.notna()].copy()
    hist=hist.sort_values(['proposal_utc','proposal_block','proposal_tx_index','proposal_log_index','oo_request_id']).reset_index(drop=True)
    # Separate role histories, strict full execution order. A request contributes once per role.
    def order(r,kind):
        if kind=='proposal':return (r.proposal_utc.value,int(r.proposal_block),int(r.proposal_tx_index),int(r.proposal_log_index))
        return (r.settlement_utc.value,int(r.settlement_block),int(r.settlement_tx_index),int(r.settlement_log_index))
    end=sorted((order(r,'settlement'),i) for i,r in hist.iterrows());j=0;stats=defaultdict(lambda:[0,0,0]);prior=[];history_evidence=[]
    for i,r in hist.iterrows():
        key=order(r,'proposal')
        while j<len(end) and end[j][0]<key:
            _,idx=end[j];q=hist.iloc[idx];disputed=int(pd.notna(q.dispute_tx));rejected=int(disputed and str(q.proposed_price_raw)!=str(q.resolved_price_raw))
            for role in ['proposer','requester']:
                addr=str(q[role]).lower();s=stats[(role,addr)];s[0]+=1;s[1]+=disputed;s[2]+=rejected
            j+=1
        rec={}
        for role in ['proposer','requester']:
            n,d,y=stats[(role,str(r[role]).lower())];rec[role+'_prior_completed']=n;rec[role+'_prior_dispute_rate']=d/n if n else np.nan;rec[role+'_prior_rejection_rate']=y/n if n else np.nan
        prior.append(rec)
    hist=pd.concat([hist,pd.DataFrame(prior)],axis=1)
    filters=[('primary_with_proposal_and_settlement',len(hist))]
    mask=hist.dispute_utc.notna();filters.append(('observed_challenge',int(mask.sum())))
    for name,m in [('grade_A_link',hist.cross_chain_match_grade.eq('A')),('consistent_resolution',hist.resolved_price_consistent.fillna(False)),('matched_settlement_transfer',hist.settlement_flow_exact.fillna(False)),('prices_present',hist.proposed_price_raw.notna()&hist.resolved_price_raw.notna()),('challenge_within_liveness',(hist.proposal_utc<=hist.dispute_utc)&(hist.dispute_utc<=hist.expiration_time_utc))]:
        mask &= m;filters.append((name,int(mask.sum())))
    strict=hist[mask].copy();old=pd.read_parquet(Path(a.native)/'data/applications/trustworthy_ai_challenge/decision_samples.parquet').set_index('sample_id')
    assert set(strict.oo_request_id)==set(old.index)
    rows=[];evidence=[];changes=[]
    for _,r in strict.iterrows():
        B=int(r.effective_bond_raw);F=int(r.final_fee_raw);R=int(r.question_reward_raw);sid=r.oo_request_id
        q=dict(sample_id=sid,decision_time_utc=r.proposal_utc,request_event_time_utc=r.event_time_utc,challenge_time_outcome_only=r.dispute_utc,settlement_time_outcome_only=r.settlement_utc,challenge_deadline_utc=r.expiration_time_utc,proposer=r.proposer,requester=r.requester,asset=r.currency,asset_decimals=6,proposal_tx=r.proposal_tx,request_tx=r.source_tx,settlement_tx_outcome_only=r.settlement_tx,dvm_request_id_outcome_only=r.dvm_request_id,proposed_price_raw=str(r.proposed_price_raw),resolved_price_raw_outcome_only=str(r.resolved_price_raw),resolution_class_outcome_only=priceclass(r.resolved_price_raw),proposal_rejected_by_protocol=int(str(r.proposed_price_raw)!=str(r.resolved_price_raw)),log_bond_raw=math.log1p(B),log_final_fee_raw=math.log1p(F),log_reward_plus1_raw=math.log1p(R),reward_to_bond_ratio=R/B if B else np.nan,liveness_hours=(r.expiration_time_utc-r.proposal_utc).total_seconds()/3600,proposal_latency_hours=(r.proposal_utc-r.event_time_utc).total_seconds()/3600,ancillary_bytes=len(r.ancillary_data_hex.removeprefix('0x'))//2,requester_is_polymarket_adapter=bool(r.requester_is_polymarket_adapter),proposed_price_class=priceclass(r.proposed_price_raw),adapter_version=str(r.adapter_version),cohort_basis='retrospective_challenged_grade_A_settled',independent_truth_available=False)
        for f in FEATURES:
            if '_prior_' in f:q[f]=r[f]
        rows.append(q)
        for f in FEATURES:
            status='observed_at_or_before_proposal';src=r.proposal_tx;reason='Native request/proposal event.'
            if '_prior_' in f:status='reconstructed_past_settlements';src='historical_request_population';reason='Separate role; settlement execution order strictly before proposal; retained primary history only.'
            if f in ['log_bond_raw','log_reward_plus1_raw','reward_to_bond_ratio','adapter_version']:status='historical_parameter_binding_required';src=r.source_tx;reason='Reconstructed adapter/bond parameter requires applicable historical source binding for a prospectively certified feature.'
            evidence.append(dict(sample_id=sid,feature=f,availability_status=status,source_key=src,missing=bool(pd.isna(q[f])),reason=reason))
            ov=old.loc[sid,f];nv=q[f]
            equal=(pd.isna(ov) and pd.isna(nv)) or (not pd.isna(ov) and not pd.isna(nv) and (str(ov)==str(nv) or (isinstance(nv,(float,int,np.number)) and np.isclose(float(ov),float(nv),equal_nan=True))))
            if not equal:changes.append(dict(sample_id=sid,feature=f,before=str(ov),after=None if pd.isna(nv) else str(nv),rule='separate_role_strict_prior_history_null_empty_v1' if '_prior_' in f else 'request_event_clock_and_defined_ratio_v1'))
    samples=pd.DataFrame(rows).sort_values(['decision_time_utc','sample_id']);samples.to_parquet(out/'uma_prediction_tasks.parquet',index=False);samples.to_csv(out/'uma_prediction_tasks.csv.gz',index=False)
    pd.DataFrame(evidence).to_parquet(out/'feature_availability.parquet',index=False);pd.DataFrame(changes).to_parquet(out/'feature_corrections.parquet',index=False)
    pd.DataFrame(filters,columns=['cumulative_selection','requests']).to_csv(out/'cohort_selection.csv',index=False)
    definitions={
    'log_bond_raw':('log(1+B)','dimensionless','effective bond, smallest asset units','null if historical parameter missing'),
    'log_final_fee_raw':('log(1+F)','dimensionless','final fee, smallest asset units','null if absent'),
    'log_reward_plus1_raw':('log(1+R)','dimensionless','configured adapter reward, smallest asset units','null if absent'),
    'reward_to_bond_ratio':('R/B','ratio','configured reward / effective bond','null for B=0 or missing parameter'),
    'liveness_hours':('(expiry-T0)/3600','hours','proposal expiry and proposal event UTC','null if either endpoint absent'),
    'proposal_latency_hours':('(T0-request event UTC)/3600','hours','event times, not oracle reference timestamp','null if either endpoint absent'),
    'ancillary_bytes':('length(decoded ancillary bytes)','bytes','request ancillary_data_hex','null if unavailable'),
    'requester_is_polymarket_adapter':('registered requester membership','binary','registered requester contract','unknown if not historically bound'),
    'proposed_price_class':('map native proposed integer to named class','category','proposal price: zero/one/half/early-expiration/other','null if absent'),
    'adapter_version':('registered adapter version','category','requester implementation register','unknown if unresolved')}
    for role in ['proposer','requester']:
        definitions[role+'_prior_completed']=(f'N({role}, settlement before T0)','requests','retained primary settled requests in same role','0 denotes no retained prior settlement')
        definitions[role+'_prior_dispute_rate']=(f'D({role})/N({role})','ratio','challenged prior settlements / prior settlements','null when N=0')
        definitions[role+'_prior_rejection_rate']=(f'J({role})/N({role})','ratio','challenged prior settlements with changed price / prior settlements','null when N=0')
    dic=[]
    for f in FEATURES:
        formula,unit,source,missing=definitions[f];dic.append(dict(feature=f,formula=formula,unit=unit,source=source,missingness=missing,availability_status=next(x['availability_status'] for x in evidence if x['feature']==f)))
    pd.DataFrame(dic).to_csv(out/'feature_dictionary.csv',index=False)
    checks=[dict(check='unique_request_unit',passed=samples.sample_id.is_unique),dict(check='same_retrospective_cohort',passed=set(samples.sample_id)==set(old.index)),dict(check='target_price_identity',passed=(samples.proposal_rejected_by_protocol==(samples.proposed_price_raw!=samples.resolved_price_raw_outcome_only).astype(int)).all()),dict(check='nonnegative_event_latency',passed=samples.proposal_latency_hours.ge(0).all()),dict(check='no_outcome_in_allowlist',passed=not any('outcome' in f or f=='proposal_rejected_by_protocol' for f in FEATURES))]
    # Independent direct filter validation for every task history count/rate.
    discrepancies=0
    for _,r in strict.iterrows():
        before=(hist.settlement_utc<r.proposal_utc) | (hist.settlement_utc.eq(r.proposal_utc) & ((hist.settlement_block<r.proposal_block) | (hist.settlement_block.eq(r.proposal_block) & ((hist.settlement_tx_index<r.proposal_tx_index) | (hist.settlement_tx_index.eq(r.proposal_tx_index) & (hist.settlement_log_index<r.proposal_log_index))))))
        for role in ['proposer','requester']:
            h=hist[before & hist[role].str.lower().eq(str(r[role]).lower())];n=len(h);d=h.dispute_tx.notna();y=d & h.proposed_price_raw.astype(str).ne(h.resolved_price_raw.astype(str))
            actual=[r[role+'_prior_completed'],r[role+'_prior_dispute_rate'],r[role+'_prior_rejection_rate']];expected=[n,float(d.sum())/n if n else np.nan,float(y.sum())/n if n else np.nan]
            if not np.allclose(actual,expected,equal_nan=True):discrepancies+=1
    checks.append(dict(check='independent_full_cohort_history',passed=discrepancies==0,discrepancies=discrepancies))
    summary=dict(passed=all(x['passed'] for x in checks),checks=checks,requests=len(samples),target_counts=samples.proposal_rejected_by_protocol.value_counts().to_dict(),features=FEATURES,changed_feature_cells=len(changes),changed_requests=len({x['sample_id'] for x in changes}),interpretation='Retrospectively selected challenged requests; no fitted models; no independent factual labels.')
    (out/'validation.json').write_text(json.dumps(summary,indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)))
    (out/'construction_query.sql').write_text(query)
    assert summary['passed'];print(json.dumps({k:v for k,v in summary.items() if k not in ['checks','features']}))
if __name__=='__main__':main()

"""Temporal aggregation and task-label sensitivity, without fitted models."""
import argparse,json
from pathlib import Path
import duckdb,pandas as pd,numpy as np
def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--native',required=True);a=p.parse_args();r=Path(a.root);b=Path(a.native)/'data/curated/parquet';out=r/'data/sensitivity';out.mkdir(parents=True,exist_ok=True);c=duckdb.connect(config={'threads':2,'memory_limit':'3GB'});checks=[]
    c.execute("SET TimeZone='UTC'")
    d=pd.read_parquet(r/'data/daily/daily_measurements.parquet');keys=['branch','mechanism_version','actor_role','observation_unit','economic_stage','metric','asset','asset_decimals'];d['week_start_utc']=pd.to_datetime(d.date_utc,utc=True)-pd.to_timedelta(pd.to_datetime(d.date_utc,utc=True).dt.weekday,unit='D')
    rows=[]
    for key,g in d.groupby(['week_start_utc']+keys,dropna=False):
        x=dict(zip(['week_start_utc']+keys,key));x.update(source_count=int(g.source_count.sum()),value_raw=str(sum(int(x) for x in g.value_raw.dropna())),observed_event_days=g.date_utc.nunique(),coverage_status='partial');rows.append(x)
    weekly=pd.DataFrame(rows);weekly.to_parquet(out/'weekly_measurements.parquet',index=False)
    checks.append({'check':'weekly_integer_mass','passed':weekly.groupby(keys,dropna=False).value_raw.apply(lambda x:sum(map(int,x))).to_dict()==d.groupby(keys,dropna=False).value_raw.apply(lambda x:sum(map(int,x.dropna()))).to_dict()});checks.append({'check':'weekly_event_count','passed':int(weekly.source_count.sum())==int(d.source_count.sum())})
    # A calendar-envelope diagnostic is not a continuity or strict-coverage estimate.
    envelopes=d.groupby('branch').date_utc.agg(['min','max']);start=envelopes['min'].max();end=envelopes['max'].min();restricted=d[d.date_utc.between(start,end)];contrast=[]
    for key,g in d.groupby(keys,dropna=False):
        sub=g[g.date_utc.between(start,end)];x=dict(zip(keys,key));x.update(full_source_count=int(g.source_count.sum()),restricted_source_count=int(sub.source_count.sum()),full_value_raw=str(sum(map(int,g.value_raw.dropna()))),restricted_value_raw=str(sum(map(int,sub.value_raw.dropna()))),start_utc=str(start),end_utc=str(end),window_basis='intersection_of_retained_first_last_envelopes_not_continuity',strict_coverage_estimate=None,strict_status='not_estimable_without_interval_receipts');contrast.append(x)
    pd.DataFrame(contrast).to_csv(out/'calendar_envelope_sensitivity.csv',index=False)
    # Keep unsupported daily allocation separate from the observed daily product.
    epochs=pd.read_parquet(b/'flare_reward_epochs.parquet')[['reward_epoch_id','epoch_start_utc','epoch_end_utc']];claims=pd.read_parquet(b/'flare_reward_claims.parquet',columns=['reward_epoch_id','amount_raw']);sums=claims.groupby('reward_epoch_id').amount_raw.apply(lambda x:sum(map(int,x)));alloc=[]
    for _,e in epochs.iterrows():
        amount=sums.get(e.reward_epoch_id,0);duration=(e.epoch_end_utc-e.epoch_start_utc).total_seconds()
        for day in pd.date_range(e.epoch_start_utc.floor('D'),e.epoch_end_utc.floor('D'),freq='D'):
            seconds=max(0,(min(day+pd.Timedelta(days=1),e.epoch_end_utc)-max(day,e.epoch_start_utc)).total_seconds());alloc.append({'reward_epoch_id':e.reward_epoch_id,'date_utc':day,'epoch_amount_raw':str(amount),'overlap_seconds':int(seconds),'epoch_seconds':int(duration),'uniform_allocation_raw_display':float(amount)*seconds/duration,'end_label_allocation_raw':str(amount if day==e.epoch_end_utc.floor('D') else 0),'evidence_status':'hypothetical_allocation_of_real_epoch_entitlement_not_daily_payment'})
    allocation=pd.DataFrame(alloc);allocation.to_parquet(out/'epoch_allocation_sensitivity.parquet',index=False)
    checks.append({'check':'epoch_overlap_duration_conservation','passed':all(g.overlap_seconds.sum()==g.epoch_seconds.iloc[0] for _,g in allocation.groupby('reward_epoch_id'))})
    checks.append({'check':'epoch_end_label_amount_conservation','passed':sum(map(int,allocation.end_label_allocation_raw))==int(sums.sum())})
    # Request-level follow-up supports explicit completed/censored populations.
    rr=b/'polygon_uma_request_rounds.parquet';ee=b/'polygon_oov2_events.parquet'
    life=c.execute(f"SELECT r.oo_request_id,r.event_time_utc request_utc,e.event_time_utc settlement_utc,r.currency asset,r.status,r.sample_tier FROM read_parquet('{rr}') r LEFT JOIN read_parquet('{ee}') e ON r.oo_request_id=e.oo_request_id AND e.event='Settle'").fetchdf();cutoff=pd.Timestamp('2026-06-30T23:59:59Z');life['right_censored']=life.settlement_utc.isna();life['followup_end_utc']=life.settlement_utc.fillna(cutoff);life['duration_hours']=(life.followup_end_utc-life.request_utc).dt.total_seconds()/3600;life['cohort']='retained_request_panel';life.to_parquet(out/'uma_request_followup.parquet',index=False)
    checks.extend([{'check':'lifecycle_unique','passed':life.oo_request_id.is_unique},{'check':'lifecycle_nonnegative_followup','passed':life.duration_hours.ge(0).all()},{'check':'censored_population','passed':int(life.right_censored.sum())==850}])
    pred=pd.read_parquet(r/'data/prediction/uma_prediction_tasks.parquet');label=[]
    cohorts={'all_native_outcomes':pd.Series(True,index=pred.index),'exclude_early_expiration':pred.resolution_class_outcome_only.ne('early_expiration'),'binary_resolutions_only':pred.resolution_class_outcome_only.isin(['binary_zero','binary_one'])}
    for name,mask in cohorts.items():
        q=pred[mask];label.append({'cohort':name,'requests':len(q),'changed_proposal':int(q.proposal_rejected_by_protocol.sum()),'unchanged_proposal':int((1-q.proposal_rejected_by_protocol).sum()),'changed_fraction':q.proposal_rejected_by_protocol.mean(),'interpretation':'label/cohort sensitivity, not factual correctness'})
    pd.DataFrame(label).to_csv(out/'special_resolution_sensitivity.csv',index=False)
    (out/'validation.json').write_text(json.dumps({'passed':all(x['passed'] for x in checks),'checks':checks,'limitation':'No complete-coverage subset can be certified from first/last retained events; strict-coverage estimates remain missing.'},indent=2,default=lambda x:x.item() if hasattr(x,'item') else str(x)));assert all(x['passed'] for x in checks);print('Aggregation, follow-up and special-resolution sensitivity checks passed.')
if __name__=='__main__':main()

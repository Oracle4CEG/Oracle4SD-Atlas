"""Integrate observed OOv2 escrow balances for unambiguous closed request flows.

Unlike posted-amount times settlement delay, this removes fees when they leave
escrow. It includes funded rewards while held. It is not participant wealth.
"""
import argparse,json
from pathlib import Path
import duckdb,pandas as pd
def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);a=p.parse_args();b=Path(a.native)/'data/curated/parquet';out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect(config={'threads':2,'memory_limit':'3GB'});c.execute("SET TimeZone='UTC'")
    def t(n):return f"read_parquet('{b/(n+'.parquet')}')"
    c.execute(f"CREATE VIEW requests AS SELECT r.*,f.settlement_flow_exact FROM {t('polygon_uma_request_rounds')} r LEFT JOIN {t('polygon_uma_request_flow_qc')} f USING(oo_request_id)")
    c.execute(f"CREATE VIEW txmap AS SELECT DISTINCT oo_request_id,source_tx FROM {t('polygon_oov2_events')} WHERE event IN ('RequestPrice','ProposePrice','DisputePrice','Settle')")
    c.execute("CREATE VIEW ambiguous AS SELECT source_tx FROM txmap GROUP BY source_tx HAVING count(DISTINCT oo_request_id)>1")
    c.execute("CREATE VIEW candidates AS SELECT * FROM requests r WHERE settlement_flow_exact AND NOT EXISTS(SELECT 1 FROM txmap x JOIN ambiguous a USING(source_tx) WHERE x.oo_request_id=r.oo_request_id)")
    c.execute(f"""CREATE VIEW flows AS SELECT r.oo_request_id,r.currency asset,f.source_tx,f.source_block,f.log_index,f.event_time_utc,
       CASE WHEN lower(f.receiver)=lower(r.source_contract) THEN try_cast(f.amount_raw AS HUGEINT) ELSE -try_cast(f.amount_raw AS HUGEINT) END delta_raw
       FROM candidates r JOIN txmap m USING(oo_request_id) JOIN {t('polygon_uma_token_flows')} f ON m.source_tx=f.source_tx AND lower(f.token)=lower(r.currency)
       WHERE (lower(f.sender)=lower(r.source_contract) OR lower(f.receiver)=lower(r.source_contract)) AND lower(f.sender)<>lower(f.receiver)""")
    c.execute("CREATE VIEW balance AS SELECT *,sum(delta_raw) OVER(PARTITION BY oo_request_id ORDER BY source_block,log_index ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) balance_raw,lead(event_time_utc) OVER(PARTITION BY oo_request_id ORDER BY source_block,log_index) next_time FROM flows")
    c.execute("CREATE VIEW qc AS SELECT oo_request_id,count(*) transfer_count,count(event_time_utc)=count(*) all_timed,min(balance_raw)>=0 nonnegative,sum(delta_raw)=0 closes_to_zero,sum(delta_raw) FILTER(WHERE delta_raw>0)>0 funded FROM balance GROUP BY 1")
    qc=c.execute('SELECT * FROM qc').fetchdf();qc['eligible']=qc[['all_timed','nonnegative','closes_to_zero','funded']].all(axis=1);qc.to_parquet(out/'uma_escrow_eligibility.parquet',index=False)
    c.execute("CREATE VIEW eligible AS SELECT b.* FROM balance b JOIN qc q USING(oo_request_id) WHERE q.all_timed AND q.nonnegative AND q.closes_to_zero AND q.funded")
    c.execute(f"COPY (SELECT oo_request_id,asset,source_tx,source_block,log_index,event_time_utc,next_time,delta_raw::VARCHAR delta_raw,balance_raw::VARCHAR balance_raw FROM eligible) TO '{out/'uma_escrow_flow_intervals.parquet'}' (FORMAT PARQUET,COMPRESSION ZSTD)")
    query="""WITH expanded AS (SELECT *,unnest(generate_series(date_trunc('day',event_time_utc),date_trunc('day',next_time),INTERVAL 1 DAY)) d FROM eligible WHERE next_time>event_time_utc AND balance_raw>0)
    SELECT CAST(d AS DATE) date_utc,asset,count(DISTINCT oo_request_id) requests,sum(balance_raw*greatest(0,date_diff('second',greatest(d,event_time_utc),least(d+INTERVAL 1 DAY,next_time))))::VARCHAR raw_token_seconds
    FROM expanded WHERE d<next_time AND d+INTERVAL 1 DAY>event_time_utc GROUP BY 1,2 ORDER BY 1,2"""
    daily=c.execute(query).fetchdf();daily['asset_decimals']=6;daily['coverage_status']='partial_unambiguous_closed_request_flows';daily['measure']='observed_escrow_including_funded_rewards';daily.to_parquet(out/'uma_daily_escrow_exposure.parquet',index=False)
    expected=c.execute('select sum(balance_raw*date_diff(\'second\',event_time_utc,next_time))::VARCHAR from eligible where next_time>event_time_utc').fetchone()[0]
    checks=[{'check':'exposure_conservation','passed':sum(map(int,daily.raw_token_seconds))==int(expected),'raw_token_seconds':expected},{'check':'eligible_native_flow_unique','passed':c.execute('select count(*)=count(distinct (source_tx,log_index)) from eligible').fetchone()[0]},{'check':'no_negative_interval','passed':c.execute('select count(*) from eligible where next_time<event_time_utc').fetchone()[0]==0}]
    report={'passed':all(x['passed'] for x in checks),'candidate_requests':c.execute('select count(*) from candidates').fetchone()[0],'flow_observed_requests':len(qc),'eligible_requests':int(qc.eligible.sum()),'checks':checks,'scope':'Closed requests with unambiguous lifecycle-transaction attribution, observed nonnegative balances and zero closing balance; excludes unresolved and ambiguous histories.'}
    (out/'escrow_validation.json').write_text(json.dumps(report,indent=2));(out/'escrow_aggregation.sql').write_text(query);assert report['passed'];print(json.dumps(report))
if __name__=='__main__':main()

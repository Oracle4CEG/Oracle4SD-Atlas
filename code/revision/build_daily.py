"""Build conservative daily measurements directly from UTC-annotated native inputs.

No calendar expansion or missing-to-zero conversion. Amounts never mix assets or
economic stages. All totals concern retained evidence, not complete chain history.
"""
from pathlib import Path
import argparse, json, hashlib
import duckdb, pandas as pd, numpy as np

def sha(p):
    with open(p,'rb') as f: return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',required=True);ap.add_argument('--out',required=True);ap.add_argument('--raw-root',required=True);a=ap.parse_args()
    b=Path(a.native).resolve()/ 'data/curated/parquet';out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    c=duckdb.connect(config={'threads':2,'memory_limit':'3GB'});c.execute("SET TimeZone='UTC'")
    sources={};results=[];actors=[];checks=[];specs=[]
    def table(n):
        p=b/(n+'.parquet');sources[n]={'path':str(p),'sha256':sha(p)}
        return "read_parquet('"+str(p).replace("'","''")+"')"
    def measure(branch,mechanism,role,unit,stage,metric,query,asset='none',decimals=0,kind='count',note=''):
        # Query returns time, actor, amount. Exact raw amounts are aggregated in SQL.
        v='m'+str(len(specs));c.execute(f'CREATE TEMP VIEW {v} AS {query}')
        n,nt,na=c.execute(f'SELECT count(*),count(t),count(amount) FROM {v}').fetchone()
        population={'branch':branch,'mechanism_version':mechanism,'actor_role':role,'observation_unit':unit,'economic_stage':stage,'metric':metric,'source_rows':n,'timed_rows':nt,'amount_rows':na,'asset':asset,'asset_decimals':decimals,'kind':kind,'note':note,'query':query}
        specs.append(population)
        if not nt:return
        d=c.execute(f"SELECT CAST(t AS DATE) date_utc,count(*) source_count,count(DISTINCT actor) active_accounts,sum(amount)::VARCHAR value_raw FROM {v} WHERE t IS NOT NULL GROUP BY 1 ORDER BY 1").fetchdf()
        for k in ['branch','mechanism_version','actor_role','observation_unit','economic_stage','metric','asset','asset_decimals','kind']:d[k]=population[k]
        d['value']=d.value_raw.map(lambda x:float(x)/10**decimals if x is not None else np.nan)
        d['coverage_status']='partial';d['denominator_kind']='retained_timed_'+unit;d['denominator']=d.source_count;d['source_population_count']=n;d['source_timed_count']=nt
        d['coverage_reason']='Native events retained; interval completeness not independently established.'+(' Untimed eligible records excluded from daily assignment.' if n!=nt else '')
        d['rule_id']='DAILY_'+metric.upper()+'_V1';d['allocation']='event_time';results.append(d)
        checks.append({'check':branch+':'+metric+':count_conservation','passed':int(d.source_count.sum())==nt,'expected':nt,'actual':int(d.source_count.sum())})
        if kind=='amount':
            total=c.execute(f'SELECT sum(amount)::VARCHAR FROM {v} WHERE t IS NOT NULL').fetchone()[0]
            checks.append({'check':branch+':'+metric+':integer_sum','passed':sum(int(x) for x in d.value_raw.dropna())==int(total or 0),'expected':total})
            ad=c.execute(f"SELECT CAST(t AS DATE) date_utc,actor,sum(amount)::VARCHAR amount_raw FROM {v} WHERE t IS NOT NULL AND actor IS NOT NULL GROUP BY 1,2").fetchdf()
            for k in ['branch','mechanism_version','actor_role','economic_stage','metric','asset','asset_decimals']:ad[k]=population[k]
            actors.append(ad)
    r=table('polygon_uma_request_rounds');e=table('polygon_oov2_events');f=table('polygon_uma_request_flow_qc')
    c.execute(f"CREATE TEMP VIEW uma AS SELECT r.*,s.event_time_utc settlement_utc,p.event_time_utc proposal_utc,d.event_time_utc dispute_utc,f.settlement_flow_exact FROM {r} r LEFT JOIN {e} s ON r.oo_request_id=s.oo_request_id AND s.event='Settle' LEFT JOIN {e} p ON r.oo_request_id=p.oo_request_id AND p.event='ProposePrice' LEFT JOIN {e} d ON r.oo_request_id=d.oo_request_id AND d.event='DisputePrice' LEFT JOIN {f} f ON r.oo_request_id=f.oo_request_id")
    assert c.execute('select count(*)=count(distinct oo_request_id) from uma').fetchone()[0]
    for role,ev in [('requester','RequestPrice'),('proposer','ProposePrice'),('disputer','DisputePrice')]:
        measure('UMA','Polygon OOv2',role,'request_action','participation','actions_'+role,f"select event_time_utc t,{role} actor,1::HUGEINT amount from {e} where event='{ev}'")
    for currency,symbol in [('0x2791bca1f2de4661ed88a30c99a7a9449aa84174','USDC.e'),('0x3c499c542cef5e3811e1192ce70d8cc03d5c3359','USDC')]:
        where=f"settlement_flow_exact AND currency='{currency}'"
        for metric,stage,expr,actor in [('reward_paid','realized_reward','coalesce(try_cast(explicit_report_reward_raw AS HUGEINT),0)+coalesce(try_cast(dispute_winner_reward_raw AS HUGEINT),0)',"CASE WHEN economic_status='settled_disputed_disputer_wins' THEN disputer ELSE proposer END"),('bond_forfeited','applied_bond_loss','try_cast(bond_forfeited_raw AS HUGEINT)',"CASE WHEN economic_status='settled_disputed_disputer_wins' THEN proposer ELSE disputer END"),('principal_returned','principal_return','try_cast(principal_returned_raw AS HUGEINT)',"CASE WHEN economic_status='settled_disputed_disputer_wins' THEN disputer ELSE proposer END")]:
            measure('UMA','Polygon OOv2','settlement_participant','request_settlement',stage,metric,f'select settlement_utc t,{actor} actor,{expr} amount from uma where {where}',symbol,6,'amount')
    dv=table('uma_dvm_staking_events')
    measure('UMA','Ethereum VotingV2','voter','stake_application','applied_stake_loss','stake_loss_applied',f"select event_time_utc t,actor,abs(try_cast(raw_data_words[1] AS HUGEINT)) amount from {dv} where event='VoterSlashApplied' AND try_cast(raw_data_words[1] AS HUGEINT)<0 AND try_cast(raw_data_words[2] AS HUGEINT)>0",'UMA',18,'amount','Net applied state change; request accruals excluded. Zero post-stake would require pre-state to resolve clipping.')
    measure('UMA','Ethereum VotingV2','voter','stake_application','applied_stake_increase','stake_redistribution_applied',f"select event_time_utc t,actor,try_cast(raw_data_words[1] AS HUGEINT) amount from {dv} where event='VoterSlashApplied' AND try_cast(raw_data_words[1] AS HUGEINT)>0",'UMA',18,'amount','Applied net redistribution; not a liquid wallet transfer.')
    st=table('chainlink_staking_v02_events');qc=table('chainlink_event_link_flow_qc')
    # Flow QC has no time field of its own. Same transaction and event family provide exact event time.
    c.execute(f"CREATE TEMP VIEW link_clock AS SELECT source_tx,event,min(event_time_utc) event_time_utc FROM {st} GROUP BY 1,2 HAVING count(DISTINCT event_time_utc)<=1")
    measure('Chainlink','Staking v0.2','staker','staking_action','participation','staking_actions',f"select event_time_utc t,staker actor,1::HUGEINT amount from {st} where event IN ('Staked','Unstaked','RewardClaimed')")
    measure('Chainlink','Staking v0.2','staker','reward_claim','realized_reward','reward_paid',f"select t.event_time_utc t,q.actor,try_cast(q.expected_amount_raw AS HUGEINT) amount from {qc} q left join link_clock t USING(source_tx,event) where q.event='RewardClaimed' and q.flow_expected and q.flow_exact",'LINK',18,'amount')
    tr=table('tellor_micro_reports');tw=table('tellor_tip_withdrawals_realized')
    measure('Tellor','tellor-1','reporter','micro_report','participation','report_submissions',f'select event_time_utc t,reporter actor,1::HUGEINT amount from {tr}')
    measure('Tellor','tellor-1','selector','tip_withdrawal','realized_reward_to_stake','tip_reward_paid',f'select event_time_utc t,selector actor,try_cast(reward_withdrawn_to_stake_loya_raw AS HUGEINT) amount from {tw} where cashflow_verified AND escrow_coin_spent_matches','TRB',6,'amount','Paid into staking, not liquid wallet income.')
    fc=table('flare_reward_claim_events')
    measure('Flare FTSOv2','RewardManager','reward_owner','claim','realized_reward','reward_paid',f'select event_time_utc t,reward_owner actor,try_cast(amount_raw AS HUGEINT) amount from {fc} where NOT is_fee_burn','FLR',18,'amount','Aggregate claim components are not assigned to unsupported subprotocols.')
    pe=table('pyth_ois_economic_events');ps=table('pyth_ois_stake_events')
    measure('Pyth','OIS','beneficiary','reward_transfer','realized_reward_to_custody','reward_paid',f'select event_time_utc t,beneficiary actor,try_cast(amount_raw AS HUGEINT) amount from {pe}','PYTH',6,'amount')
    measure('Pyth','OIS','stake_owner','stake_instruction','participation','stake_actions',f'select event_time_utc t,owner actor,1::HUGEINT amount from {ps}')
    ch=table('chronicle_ethereum_events')
    measure('Chronicle','Ethereum Scribe','caller','update','participation','update_actions',f"select event_time_utc t,caller actor,1::HUGEINT amount from {ch} where event_name IN ('Poked','OpPoked')")
    measure('Chronicle','Ethereum Scribe','challenger','challenge_reward','realized_reward','challenge_reward_paid',f"select event_time_utc t,challenger actor,try_cast(reward_amount_raw AS HUGEINT) amount from {ch} where event_name='OpChallengeRewardPaid'",'ETH',18,'amount')
    re=table('redstone_ethereum_push_events')
    measure('RedStone Push','Ethereum Push','delivery_contract','update','delivery','delivery_updates',f'select event_time_utc t,contract_address actor,1::HUGEINT amount from {re}',note='Active contract addresses are not publisher identities.')
    de=table('dia_staking_events');dw=table('dia_staking_withdrawals')
    measure('DIA','Lasernet staking','staker','staking_action','participation','staking_actions',f"select event_time_utc t,actor,1::HUGEINT amount from {de} where event IN ('Staked','UnstakeRequested')")
    measure('DIA','Lasernet staking','withdrawal_position','withdrawal','realized_reward','reward_paid',f'select event_time_utc t,NULL::VARCHAR actor,try_cast(total_reward_raw AS HUGEINT) amount from {dw} where payment_exact','wDIA',18,'amount','Reward can be split across beneficiary and principal wallet; no single-recipient attribution.')
    daily=pd.concat(results,ignore_index=True);daily.to_parquet(out/'daily_measurements.parquet',index=False);daily.to_csv(out/'daily_measurements.csv.gz',index=False)
    ad=pd.concat(actors,ignore_index=True);ad.to_parquet(out/'daily_recipient_amounts.parquet',index=False)
    concentration=[]
    keys=['date_utc','branch','mechanism_version','actor_role','economic_stage','metric','asset','asset_decimals']
    for key,g in ad[ad.economic_stage.str.startswith('realized_reward')].groupby(keys,dropna=False):
        vals=np.array([int(x) for x in g.amount_raw if x is not None and int(x)>0],dtype=float)
        if not len(vals):continue
        vals.sort();n=len(vals);s=vals.sum();row=dict(zip(keys,key));row.update(recipient_count=n,gini=float(2*np.dot(np.arange(1,n+1),vals)/(n*s)-(n+1)/n),top_decile_share=float(vals[-int(np.ceil(.1*n)):].sum()/s),population='positive observed recipient amounts',coverage_status='partial');concentration.append(row)
    pd.DataFrame(concentration).to_parquet(out/'daily_reward_concentration.parquet',index=False)
    # Completion delays are assigned to the completion day, with the completed-only risk set stated explicitly.
    latency=c.execute("SELECT CAST(settlement_utc AS DATE) date_utc,currency asset,count(*) completed_requests,median(epoch(settlement_utc-event_time_utc)/3600) median_hours,quantile_cont(epoch(settlement_utc-event_time_utc)/3600,.9) p90_hours FROM uma WHERE settlement_flow_exact AND settlement_utc>=event_time_utc GROUP BY 1,2 ORDER BY 1,2").fetchdf()
    latency['population']='flow-reconciled completed requests';latency['coverage_status']='partial';latency.to_parquet(out/'uma_daily_completion_delay.parquet',index=False)
    # Historical policy weights are recovered from the archived epoch artifact, not inferred from report frequency.
    epoch=pd.read_parquet(b/'flare_reward_epochs.parquet').set_index('reward_epoch_id');reg=pd.read_parquet(b/'flare_voter_registrations.parquet');policies=[];weights=[]
    for eid,row in epoch.iterrows():
        p=Path(a.raw_root)/'data/raw/flare_fsp'/str(eid)/'reward-epoch-info.json'
        if not p.exists():continue
        j=json.loads(p.read_text());sp=j['signingPolicy'];w=np.array(sp['weights'],dtype=float);total=int(sum(sp['weights']));threshold=int(sp['threshold']);hhi=float(np.sum((w/total)**2));order=sorted(sp['weights'],reverse=True)
        n_gt=next((i+1 for i,x in enumerate(np.cumsum(order)) if x>threshold),None);n_ge=next((i+1 for i,x in enumerate(np.cumsum(order)) if x>=threshold),None)
        matches=reg[reg.reward_epoch_id.eq(eid)].set_index('signing_policy_address');mapped=all(v.lower() in matches.index for v in sp['voters'])
        policies.append(dict(reward_epoch_id=int(eid),epoch_start_utc=row.epoch_start_utc,epoch_end_utc=row.epoch_end_utc,start_voting_round_id=sp['startVotingRoundId'],registered_signers=len(w),weight_total=total,threshold_raw=threshold,hhi=hhi,effective_signers=1/hhi,min_signers_strictly_above_threshold=n_gt,min_signers_at_least_threshold=n_ge,registration_mapping_complete=mapped,source_sha256=sha(p),source_path=str(p),historical_bytecode_binding='not_independently_verified',weight_type='signing_policy',entity_identity='addresses_not_entities'))
        for v,wt in zip(sp['voters'],sp['weights']):weights.append(dict(reward_epoch_id=int(eid),signing_policy_address=v,weight_raw=int(wt),threshold_raw=threshold,weight_total=total,source_sha256=sha(p)))
        checks.append({'check':f'flare_policy_{eid}_mapping','passed':bool(mapped and len(w)==len(sp['voters']) and total>threshold and len(set(sp['voters']))==len(w))})
    pd.DataFrame(policies).to_parquet(out/'flare_historical_signing_policy.parquet',index=False);pd.DataFrame(weights).to_parquet(out/'flare_signer_weights.parquet',index=False)
    (out/'daily_source_rules.json').write_text(json.dumps({'sources':sources,'queries':specs,'cutoff':'2026-06-30T23:59:59Z'},indent=2,default=str))
    checks.extend([{'check':'eight_branches','passed':daily.branch.nunique()==8},{'check':'no_post_cutoff_day','passed':str(daily.date_utc.max())[:10]<='2026-06-30'},{'check':'no_unsubstantiated_complete_coverage','passed':daily.coverage_status.eq('partial').all()}])
    (out/'validation.json').write_text(json.dumps({'passed':all(x['passed'] for x in checks),'checks':checks,'daily_rows':len(daily),'signing_epochs':len(policies)},indent=2,default=str))
    if not all(x['passed'] for x in checks):raise RuntimeError('Daily validation failed')
    print(json.dumps({'daily_rows':len(daily),'signing_epochs':len(policies),'checks':len(checks)}))

if __name__=='__main__':main()

"""Read-only bounded public-interface probes; never a full historical collection."""
from pathlib import Path
import argparse,json,time,concurrent.futures,hashlib
from datetime import datetime,timezone
import duckdb,requests,pandas as pd
def main():
    p=argparse.ArgumentParser();p.add_argument('--native',required=True);p.add_argument('--out',required=True);a=p.parse_args();b=Path(a.native)/'data/curated/parquet';out=Path(a.out);out.mkdir(parents=True,exist_ok=True);c=duckdb.connect();jobs=[]
    def first(name,tx,col,where='TRUE'):
        return c.execute(f"SELECT {tx},{col} FROM read_parquet('{b/(name+'.parquet')}') WHERE {where} LIMIT 1").fetchone()
    for branch,n,tx,col,ep,where in [
    ('UMA','polygon_oov2_events','source_tx','source_block','https://polygon.drpc.org',"event='Settle'"),
    ('Chainlink','chainlink_staking_v02_events','source_tx','source_block','https://ethereum-rpc.publicnode.com',"event='RewardClaimed'"),
    ('Flare FTSOv2','flare_reward_claim_events','source_tx','source_block','https://flare-api.flare.network/ext/C/rpc','NOT is_fee_burn'),
    ('Chronicle','chronicle_ethereum_events','transaction_hash','block_number','https://ethereum-rpc.publicnode.com',"event_name='OpChallengeRewardPaid'"),
    ('RedStone Push','redstone_ethereum_push_events','transaction_hash','block_number','https://ethereum-rpc.publicnode.com','TRUE'),
    ('DIA','dia_staking_withdrawals','transaction_hash','block_number','https://rpc.diadata.org','payment_exact')]:
        key,block=first(n,tx,col,where);jobs.append(dict(branch=branch,source=n,endpoint=ep,method='eth_getTransactionReceipt',params=[key],expected_block=int(block),key=key))
    key,block=first('pyth_ois_economic_events','signature','slot');jobs.append(dict(branch='Pyth',source='pyth_ois_economic_events',endpoint='https://api.mainnet-beta.solana.com',method='getTransaction',params=[key,{'encoding':'json','maxSupportedTransactionVersion':0}],expected_block=int(block),key=key))
    key,block=first('tellor_disputes','source_tx','source_block');jobs.append(dict(branch='Tellor',source='tellor_disputes',endpoint='https://mainnet.tellorlayer.com/rpc/block_results',method='GET',params={'height':str(block)},expected_block=int(block),key=key))
    def run(j):
        start=time.monotonic();name=j['branch'].lower().replace(' ','_');report={**j,'retrieval_utc':datetime.now(timezone.utc).isoformat(),'scope':'one historical transaction or height','source_mode':'fresh_public_probe'}
        try:
            response=requests.get(j['endpoint'],params=j['params'],timeout=25) if j['method']=='GET' else requests.post(j['endpoint'],json={'jsonrpc':'2.0','id':1,'method':j['method'],'params':j['params']},timeout=25)
            report['http_status']=response.status_code;response.raise_for_status();obj=response.json();result=obj.get('result');path=out/(name+'_response.json');path.write_text(json.dumps(obj,indent=2));report['response_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            if obj.get('error'):report.update(status='rpc_error',error=obj['error'])
            elif result is None:report.update(status='historical_record_unavailable')
            else:
                if j['method']=='eth_getTransactionReceipt':ok=result.get('transactionHash','').lower()==j['key'].lower() and int(result['blockNumber'],16)==j['expected_block'] and int(result['status'],16)==1
                elif j['method']=='getTransaction':ok=result['slot']==j['expected_block'] and result['meta']['err'] is None
                else:ok=int(result['height'])==j['expected_block']
                report.update(status='verified_native_locator' if ok else 'locator_mismatch',locator_verified=ok)
        except Exception as e:report.update(status='interface_unavailable',error=type(e).__name__+': '+str(e)[:400])
        report['elapsed_seconds']=round(time.monotonic()-start,3);return report
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:reports=list(pool.map(run,jobs))
    # Small missing-time pilot; results remain separate until integrated and validated.
    blocks=c.execute(f"SELECT DISTINCT source_block FROM read_parquet('{b/'chainlink_staking_v02_events.parquet'}') WHERE event_time_utc IS NULL ORDER BY source_block LIMIT 16").fetchall()
    batch=[{'jsonrpc':'2.0','id':i,'method':'eth_getBlockByNumber','params':[hex(int(x[0])),False]} for i,x in enumerate(blocks)];pilot={'blocks_requested':len(batch),'endpoint':'https://ethereum-rpc.publicnode.com','integrated_into_daily_release':False}
    start=time.monotonic()
    try:
        rr=requests.post(pilot['endpoint'],json=batch,timeout=35);rr.raise_for_status();obj=rr.json();(out/'ethereum_header_pilot.json').write_text(json.dumps(obj,indent=2));n=sum(bool(x.get('result')) for x in obj) if isinstance(obj,list) else 0;pilot.update(headers_returned=n,status='available' if n==len(batch) else 'partial_or_error')
    except Exception as e:pilot.update(headers_returned=0,status='interface_unavailable',error=str(e)[:400])
    pilot['elapsed_seconds']=round(time.monotonic()-start,3)
    (out/'acquisition_report.json').write_text(json.dumps({'branch_probes':reports,'missing_time_pilot':pilot,'claim':'Bounded locator checks only; does not establish acquisition continuity or complete relay paths.'},indent=2))
    pd.DataFrame([{k:x.get(k) for k in ['branch','source','method','expected_block','status','locator_verified','elapsed_seconds']} for x in reports]).to_csv(out/'acquisition_summary.csv',index=False)
    print(json.dumps({'branches':{x['branch']:x['status'] for x in reports},'header_pilot':pilot}))
if __name__=='__main__':main()

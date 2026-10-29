"""Bounded AVS discovery probe, kept outside the Ethereum Push dataset."""
import argparse,json,hashlib,time
from pathlib import Path
import requests
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    url='https://mainnet.base.org';contract='0x2B766957ce3dbab9eC4b227f5086855CeE7a1ad6';cutoff=1782863999;calls=[]
    def rpc(method,params):
        rr=requests.post(url,json={'jsonrpc':'2.0','id':len(calls)+1,'method':method,'params':params},timeout=20);rr.raise_for_status();j=rr.json();calls.append({'method':method,'params':params,'response':j});
        if 'error' in j:raise RuntimeError(str(j['error']))
        return j['result']
    report={'branch':'RedStone AVS extension','included_in_push_sample':False,'contract':contract,'chain':'Base','chain_id':8453,'documentation':'https://docs.redstone.finance/docs/network-tokenomics/restaking-avs/service-components/','historical_implementation_binding':'unverified','cutoff_utc':'2026-06-30T23:59:59Z'}
    try:
        high=int(rpc('eth_blockNumber',[]),16);low=0
        while low<high:
            mid=(low+high+1)//2;block=rpc('eth_getBlockByNumber',[hex(mid),False]);timestamp=int(block['timestamp'],16)
            if timestamp<=cutoff:low=mid
            else:high=mid-1
        report['to_block']=low;report['from_block']=max(0,low-999)
        code=rpc('eth_getCode',[contract,hex(low)]);report['code_present_at_cutoff']=code not in ['0x',None];report['runtime_sha256']=hashlib.sha256(bytes.fromhex(code.removeprefix('0x'))).hexdigest()
        slot='0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc';implementation=rpc('eth_getStorageAt',[contract,slot,hex(low)]);report['eip1967_implementation_slot']=implementation
        logs=rpc('eth_getLogs',[{'address':contract,'fromBlock':hex(report['from_block']),'toBlock':hex(low)}]);report['logs_returned']=len(logs);report['status']='bounded_history_collected';report['interpretation']='Raw logs and runtime evidence only; no reward, weight or slashing amount inferred without historical ABI and rule binding.'
    except Exception as e:report['status']='interface_or_archive_limit';report['error']=str(e)[:500]
    (out/'raw_calls.json').write_text(json.dumps(calls,indent=2));(out/'pilot_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
if __name__=='__main__':main()

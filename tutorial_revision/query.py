from pathlib import Path
import argparse,json,hashlib,requests,shutil,time
def query(root, branch, mode='archived_raw', output_root=None):
    root=Path(root)
    if mode=='native':
        import sys
        sys.path.insert(0,str(root/'processing_code'))
        from replay import run_branch
        return run_branch(root,branch)
    p=next(x for x in json.loads((root/'metadata/raw_profiles.json').read_text()) if x['branch']==branch)
    if mode=='archived_raw':
        src=root/p['raw_input'];assert hashlib.sha256(src.read_bytes()).hexdigest()==p['raw_sha256'];obj=json.loads(src.read_text())
    elif mode=='live':
        rr=requests.get(p['endpoint'],params=p['params'],timeout=25) if p['method']=='GET' else requests.post(p['endpoint'],json={'jsonrpc':'2.0','id':1,'method':p['method'],'params':p['params']},timeout=25)
        rr.raise_for_status();obj=rr.json()
        if obj.get('error') or obj.get('result') is None:raise RuntimeError('Historical evidence unavailable from this interface; preserve the failure separately.')
    else:raise ValueError(mode)
    result=obj.get('result')
    if not isinstance(result,dict):raise ValueError('Missing native response')
    if p['method']=='eth_getTransactionReceipt':
        valid=int(result['blockNumber'],16)==int(p['expected_block']) and result['transactionHash'].lower()==p['key'].lower()
    elif p['method']=='getTransaction':
        valid=int(result['slot'])==int(p['expected_block']) and p['key'] in result['transaction']['signatures']
    else:valid=int(result['height'])==int(p['expected_block'])
    if not valid:raise ValueError('Native locator does not match the registered bounded query')
    destination=Path(output_root) if output_root is not None else root/'queried_data'
    out=destination/branch.lower().replace(' ','_')/(mode+'_response.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(obj,indent=2))
    return {'branch':branch,'mode':mode,'result_keys':list(result),'output':str(out.relative_to(destination)),'expected_native_block':p['expected_block'],'locator_verified':True,'run_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'warning':'Locator verification alone is not historical runtime binding or continuous coverage.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--root',default='.');p.add_argument('--branch',required=True);p.add_argument('--mode',choices=['archived_raw','native','live'],default='archived_raw');p.add_argument('--output-root');a=p.parse_args()
    start=time.monotonic()
    try:
        result=query(a.root,a.branch,a.mode,a.output_root)
        result['status']='passed'
    except Exception as exc:
        result={'branch':a.branch,'mode':a.mode,'status':'failed','error_type':type(exc).__name__,'error':str(exc),'locator_verified':False}
    result['elapsed_seconds']=round(time.monotonic()-start,3)
    result['timeout_seconds']=25;result['retry_count']=0;result['stop_condition']='one registered transaction or height; no pagination'
    if a.output_root:
        dest=Path(a.output_root);dest.mkdir(parents=True,exist_ok=True)
        (dest/'acquisition.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    if result['status']=='failed':raise SystemExit(1)

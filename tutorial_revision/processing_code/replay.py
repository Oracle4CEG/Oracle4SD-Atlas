from pathlib import Path
import hashlib,json,shutil
import pyarrow.parquet as pq
def run_branch(root, branch):
    root=Path(root);profiles=json.loads((root/'metadata/profiles.json').read_text());p=next(x for x in profiles if x['branch']==branch)
    src=root/p['input']
    with src.open('rb') as f: digest=hashlib.file_digest(f,'sha256').hexdigest()
    assert digest==p['sample_sha256']
    q=root/p['query_output'];q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,q)
    tab=pq.read_table(q);assert tab.num_rows==p['sample_rows']
    utc=[n for n in tab.column_names if n.endswith('_utc')]
    result={'branch':branch,'rows':tab.num_rows,'clock_fields':utc,'source_mode':p['source_mode'],'source_sha256':digest,'parent_sha256':p['parent_sha256'],'source_unit':p['parent_native_table'],'missing_event_time':tab['event_time_utc'].null_count,'check':'sample_identity_and_clock_schema'}
    out=root/p['processed_output'];out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(result,indent=2));return result

"""Finalize the audited native build in a new directory with explicit lineage.

The original build and its failed rule-ID check remain intact. This bounded
second activity changes only unsettled-request mapping, the conservative masked
view, and the financial experiment. Fresh users run rebuild_atlas.py directly.
"""
import argparse
import json
import os
import resource
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from rebuild_atlas import ROOT, sha256, sqlpath, rewrite, validate, write_json
from build_release_metadata import build as build_metadata


def finalize(baseline, output, resume=False):
    baseline=Path(baseline).resolve();output=Path(output).resolve()
    original=json.loads((baseline/'validation/full_release.json').read_text())
    unexpected=[c for c in original['checks'] if not c['passed'] and c['name']!='schema_field_rule_id']
    if unexpected:raise ValueError('Baseline has unrelated validation failures: '+str(unexpected))
    inventory=json.loads((baseline/'metadata/file_manifest.json').read_text())
    for item in inventory:
        if sha256(baseline/item['path'])!=item['sha256']:
            raise ValueError('Baseline output changed: '+item['path'])
    checkpoint_path=output/'validation/finalization_checkpoint.json'
    checkpoint={}
    if resume:
        checkpoint=json.loads(checkpoint_path.read_text())
        current=json.loads((output/'validation/full_release.json').read_text())
        current_failures=[c['name'] for c in current['checks'] if not c['passed']]
        if current.get('code_commit')!=original['code_commit']:
            if current_failures!=['financial_models_complete']:
                raise ValueError('A completed finalization can only resume its isolated financial check')
            current_manifest=json.loads((output/'metadata/file_manifest.json').read_text())
            for item in current_manifest:
                if sha256(output/item['path'])!=item['sha256']:
                    raise ValueError('Completed data changed before financial retry')
            checkpoint['repaired_hashes']={x['path']:x['sha256'] for x in current_manifest}
            shutil.copy2(output/'validation/full_release.json',output/'validation/financial_feasibility_initial.json')
        if checkpoint['baseline_code_commit']!=original['code_commit']:
            raise ValueError('Checkpoint belongs to a different native build')
        for item in inventory:
            expected=checkpoint.get('repaired_hashes',{}).get(item['path'],item['sha256'])
            if sha256(output/item['path'])!=expected:
                raise ValueError('Partial output differs from checkpoint: '+item['path'])
    elif output.exists():raise FileExistsError(output)
    else:output.mkdir(parents=True)
    started=time.monotonic()
    for source in ([] if resume else baseline.rglob('*')):
        relative=source.relative_to(baseline)
        if 'scratch' in relative.parts or not source.is_file():continue
        target=output/relative;target.parent.mkdir(parents=True,exist_ok=True)
        if relative.parts[0]=='data':os.link(source,target)
        else:shutil.copy2(source,target)
    shutil.copy2(baseline/'validation/full_release.json',output/'validation/baseline_full_release.json')
    shutil.copy2(baseline/'metadata/file_manifest.json',output/'metadata/baseline_file_manifest.json')
    os.environ['ORACLE_WORKSPACE']=str(output)
    os.environ['MPLBACKEND']='Agg'
    sys.path.insert(0,str(ROOT/'code/reconstruction'))
    from scripts.revision_semantics import UNSETTLED_RULE_EXPR, MAPPING_RULES
    from scripts.applications.financial import common as financial
    from scripts.applications.oata import common as oata
    sources=sorted((ROOT/'code/reconstruction').rglob('*.py'))+sorted((ROOT/'scripts').glob('*.py'))
    sources += [p for base in ('schemas','code/reconstruction/schemas','data/data_source/full_build_metadata','data/data_source/pyth_historical') for p in (ROOT/base).rglob('*') if p.is_file()]
    hashes={str(p.relative_to(ROOT)):sha256(p) for p in sources}
    con=duckdb.connect(config={'threads':2,'memory_limit':'4GB','temp_directory':str(output/'scratch')})
    corrected=checkpoint.get('rule_corrections',[])
    repaired_hashes=checkpoint.get('repaired_hashes',{})
    for name in ['accountability_events','sample_b_observable_accountability','sample_c_strict_honesty_events']:
        path=output/'data/curated/parquet'/(name+'.parquet')
        count=con.execute(f"SELECT count(*) FROM read_parquet({sqlpath(path)}) WHERE native_table='polygon_uma_request_rounds' AND outcome_status='not_settled' AND rule_id IS NULL").fetchone()[0]
        if count:
            print('Repairing unsettled rule:',name,count,flush=True)
            rewrite(con,f'SELECT * REPLACE ({UNSETTLED_RULE_EXPR}) FROM read_parquet({sqlpath(path)})',path)
        if count or not any(x['table']==name for x in corrected):
            corrected.append(dict(table=name,corrected_rows=count))
        if count:repaired_hashes[str(path.relative_to(output))]=sha256(path)
        write_json(checkpoint_path,dict(baseline_code_commit=original['code_commit'],rule_corrections=corrected,repaired_hashes=repaired_hashes,
                                       scope='Only completed rule repairs are resumable; other baseline data must retain its exact hash'))
    print('Rebuilding masked view',flush=True)
    oata.build_prefix_view(con,output/'data/applications/oata/accountability_episodes.parquet')
    # Benchmark output is staged separately so hardlinked baseline bytes cannot
    # be truncated by a library's direct Parquet writer.
    target=output/'data/applications/financial_benchmark'
    staging=output/'financial_experiment_stage';staging.mkdir()
    for name in ['landmark_prefixes.parquet','splits.parquet']:os.link(target/name,staging/name)
    financial.OUT=staging
    print('Running stable financial benchmark',flush=True)
    financial.run_benchmark()
    for path in staging.iterdir():
        if path.name not in ['landmark_prefixes.parquet','splits.parquet']:path.replace(target/path.name)
        else:path.unlink()
    staging.rmdir()
    shutil.copy2(ROOT/'code/reconstruction/schemas/accountability_events.sql',output/'schemas/accountability_events.sql')
    semantics=json.loads((output/'metadata/semantic_decisions.json').read_text())
    semantics['mapping_rules']=MAPPING_RULES
    write_json(output/'metadata/semantic_decisions.json',semantics)
    print('Validating all final layers',flush=True)
    checks,after=validate(con,output)
    metrics=con.execute(f"SELECT * FROM read_parquet({sqlpath(target/'metrics.parquet')})").fetchdf()
    completed=metrics[(metrics['status']=='completed') & metrics['harrell_c_index'].notna()]
    failures=metrics[metrics['status']!='completed']
    checks.append(dict(name='financial_models_complete',passed=len(completed)==21 and failures.empty,
                       completed_model_track_fits=len(completed),failed_or_unestimable=len(failures),
                       scope='Seven fitted models on three tasks; protocol-balanced sampling and evaluation split are recorded; undefined time-dependent metrics remain null'))
    permitted={'data/curated/parquet/accountability_events.parquet','data/curated/parquet/sample_b_observable_accountability.parquet',
               'data/applications/oata/prefix_episodes.parquet'}
    before={x['path']:x for x in inventory};final=[];unexpected_changes=[]
    for path in sorted((output/'data').rglob('*.parquet')):
        relative=str(path.relative_to(output));digest=sha256(path)
        if relative in before and digest!=before[relative]['sha256'] and relative not in permitted and not relative.startswith('data/applications/financial_benchmark/'):
            unexpected_changes.append(relative)
        final.append(dict(path=relative,sha256=digest,bytes=path.stat().st_size,rows=pq.read_metadata(path).num_rows))
    checks.append(dict(name='unrelated_baseline_data_preserved',passed=not unexpected_changes,changed_files=unexpected_changes))
    changed_sources=[name for name,digest in hashes.items() if sha256(ROOT/name)!=digest]
    checks.append(dict(name='finalization_source_unchanged',passed=not changed_sources,changed_files=changed_sources))
    write_json(output/'metadata/file_manifest.json',final)
    write_json(output/'validation/semantic_after.json',after)
    build_metadata(output)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    report=dict(release='atlas-repaired-20261012',passed=all(c['passed'] for c in checks),checks=checks,
                input_files=original['input_files'],output_files=len(final),output_file_bytes=sum(x['bytes'] for x in final),
                code_commit=commit,source_sha256=hashes,
                lineage=dict(native_build='validation/baseline_full_release.json',native_code_commit=original['code_commit'],
                             finalization='scripts/finalize_revision.py',rule_corrections=corrected,
                             preserved_failed_check='The native build exposed 850 absent rule IDs; its original failure report is retained.'),
                scope='Frozen native reconstruction plus explicit corrections; no fresh historical network collection or independent scientific replication claimed',
                steps=original['steps']+[dict(name='finalize_revision',code_commit=commit,elapsed_seconds=round(time.monotonic()-started,3))],
                elapsed_seconds=round(original['elapsed_seconds']+time.monotonic()-started,3),
                max_rss_kib=max(original['max_rss_kib'],resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
                finished_utc=datetime.now(timezone.utc).isoformat())
    write_json(output/'validation/full_release.json',report)
    print(json.dumps(dict(passed=report['passed'],checks=len(checks),output=str(output)),indent=2))
    if not report['passed']:raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline',required=True);p.add_argument('--output',required=True)
    p.add_argument('--resume',action='store_true',help='Resume only a hash-bound rule-repair checkpoint')
    a=p.parse_args();finalize(a.baseline,a.output,a.resume)

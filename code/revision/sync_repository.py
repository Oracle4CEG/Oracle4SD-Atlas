"""Prepare the local repository companion without changing any remote."""
from pathlib import Path
import argparse,shutil,json,hashlib
import pandas as pd

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--deposit',required=True);a=p.parse_args();r=Path(a.root).resolve();dep=Path(a.deposit).resolve();repo=r/'Oracle4SD_Atlas_Repository';meta=repo/'metadata/revision';meta.mkdir(exist_ok=True)
    for src in (dep/'metadata').iterdir():
        dst=meta/src.name
        if src.is_dir():shutil.copytree(src,dst,dirs_exist_ok=True)
        else:shutil.copy2(src,dst)
    for src in (r/'metadata').iterdir():
        if src.is_file():shutil.copy2(src,meta/src.name);shutil.copy2(src,dep/'metadata'/src.name)
    shutil.copy2(dep/'croissant.json',meta/'croissant.json');shutil.copy2(dep/'README.md',meta/'DATASET_CARD.md')
    for f in ['code/revise_paper.py','code/enhance_tutorial.py']:
        src=r/f
        if src.exists():
            dst=r/'archive/authoring_scripts'/src.name;dst.parent.mkdir(exist_ok=True);shutil.move(src,dst)
    (r/'archive/authoring_scripts/README.txt').write_text('Intermediate authoring scripts retained for provenance. Final LaTeX and tutorial/query.py include subsequent reviewed edits and are authoritative. Do not rerun these scripts over the final manuscript or notebook.\n')
    shutil.copytree(r/'code',repo/'code/revision',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    shutil.copytree(r/'tutorial',repo/'tutorial_revision',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    hist=repo/'notebooks/historical';hist.mkdir(exist_ok=True)
    old=repo/'notebooks/Oracle4SD_Atlas_Tutorial.ipynb'
    if old.exists():shutil.move(old,hist/old.name)
    shutil.copy2(r/'tutorial/Oracle4SD_Atlas_Tutorial.ipynb',repo/'notebooks/Oracle4SD_Atlas_Tutorial.ipynb')
    (hist/'README.txt').write_text('Predecessor tutorial. The current entry is notebooks/Oracle4SD_Atlas_Tutorial.ipynb and loads tutorial_revision. Historical execution reports do not validate the current revision.\n')
    paper=repo/'paper/working_revision';shutil.copytree(r/'Oracle4SD_Atlas',paper,ignore=shutil.ignore_patterns('*.aux','*.log','*.out','*.synctex.gz'),dirs_exist_ok=True)
    shutil.copytree(r/'reports',repo/'reports/local_revision',dirs_exist_ok=True)
    shutil.copytree(r/'archive/model_experiments',repo/'reports/historical_model_experiments',dirs_exist_ok=True)
    # Only the small archived policy artifacts used by the weight reconstruction.
    raw=repo/'reproduction_inputs/data/raw/flare_fsp'
    pol=pd.read_parquet(r/'data/daily/flare_historical_signing_policy.parquet');manifest=[]
    for eid in pol.reward_epoch_id:
        src=r.parent/'data/raw/flare_fsp'/str(eid)/'reward-epoch-info.json';dst=raw/str(eid)/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);manifest.append({'epoch':int(eid),'path':str(dst.relative_to(repo)),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
    (meta/'policy_input_manifest.json').write_text(json.dumps(manifest,indent=2))
    legacy=r.parent/'overleaf_revision_20261026_guide2/temporal_data/data/applications/trustworthy_ai_challenge/decision_samples.parquet';dst=dep/'reproduction_inputs';dst.mkdir(exist_ok=True);shutil.copy2(legacy,dst/legacy.name)
    # Older rule inputs are provenance inputs, not new product observations.
    legacyroot=dst/'legacy';base=r.parent
    for rel in ['data/applications/oata/accountability_episodes.parquet','data/curated/parquet/sample_c_strict_honesty_events.parquet']:
        target=legacyroot/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(base/rel,target)
    shutil.copytree(base/'data/case_studies/uma_real_episode',legacyroot/'data/case_studies/uma_real_episode',dirs_exist_ok=True)
    (dst/'README.txt').write_text('Historical reconstruction inputs, excluded from the 100-table current-product catalogue. decision_samples is the frozen earlier cohort used only for comparison and feature corrections. legacy holds earlier semantic classifications and the retained case. Current features and labels are in data/prediction. Source fingerprints are in support/evidence/ledger_provenance.json and the native preservation manifests.\n')
    folders=pd.read_csv(r/'metadata/folder_role_map.csv');navigation='\n'.join('| '+x.folder_role+' | '+x.purpose+' |' for x in folders.itertuples())
    readme='''# Oracle4SD Atlas — local coordinated revision

This checkout prepares the remaining manuscript revisions for review. It has not been pushed to GitHub and does not identify a new public dataset release. The pinned input repository is `1dc0dfc3bc919e64f43a110bf29b75ef0e34459c`; the template input is `2ca64c50c43e189aa9cfc2cacd03520b71119301`.

Start with `paper/working_revision/main.pdf` and `tutorial_revision/Oracle4SD_Atlas_Tutorial_executed.ipynb`. The paper describes eight protocol branches, a UMA prediction task and a daily measurement product. See `metadata/revision/logical_products.json` for ten-product membership and `metadata/revision/file_manifest.csv` for the separate full dataset. Large data are not embedded in this code checkout.

The current tutorial has eight bounded archived native examples and actual frozen raw responses. Run it from `tutorial_revision`, or run `notebooks/Oracle4SD_Atlas_Tutorial.ipynb` with the repository as the working directory. Install `tutorial_revision/requirements.txt` first. Its saved execution used a local Python kernel. Independent-reader and Google-hosted Colab execution remain pending.

The existing UMA case demonstrates three acquisition modes in distinct fresh directories:

```sh
python code/query_data/query.py --run-dir /tmp/oracle-bundled --mode bundled
python code/query_data/query.py --run-dir /tmp/oracle-public --mode public-download
python code/query_data/query.py --run-dir /tmp/oracle-live --mode live
python code/process_data/process.py --run-dir /tmp/oracle-live
python code/technical_validation/validate.py --run-dir /tmp/oracle-live
```

Run processing and validation for each directory. Live mode checks chain, block, receipt and retained runtime identity, then records the new response hash; it does not require a provider response envelope to match a frozen byte hash. The three modes were executed in this revision for the same five-transaction case. A bounded case is not continuous full-history acquisition. Eight-branch raw and native replay are provided separately by `tutorial_revision/query.py`.

To rebuild current daily or task tables from the full data deposit, first create its expected native layout:

```sh
python code/revision/prepare_native_layout.py --deposit /path/to/dataset_deposit --output /tmp/oracle-native
python code/revision/build_prediction.py --native /tmp/oracle-native --out /tmp/oracle-task
python code/revision/build_daily.py --native /tmp/oracle-native --raw-root reproduction_inputs --out /tmp/oracle-daily
python code/revision/build_escrow.py --native /tmp/oracle-native --out /tmp/oracle-daily
```

The policy input manifest identifies the archived Flare inputs in `reproduction_inputs`. For common or economic records, `code/revision/load_core_with_utc.py` creates views joining the unchanged parent records to validated clock companions. Use supported UTC fields for time selection. The older integer-second fields and model application outputs remain historical representations.

The dictionary records definitions and their completion status. Source-reference definitions are retained where deeper semantic review remains necessary. Missing evidence is not filled with zero; epoch entitlements, realized payments and applied losses retain distinct stages. Addresses are not independently identified entities. The prediction target is a protocol resolution rather than external factual truth.

## Navigation

| Folder role | Purpose |
| --- | --- |
'''+navigation+'''

`metadata/revision/eight_branch_source_to_output.csv` maps each branch from source and query to native processing and paper use. Finished artifacts in `tutorial_revision` and `paper/working_revision` fill the template roles. Fourteen roles are preserved even when the completed artifact replaces a blank template.

`metadata/revision/revision_response.csv` answers the forty review items. `remaining_work.csv` records missing headers, interval receipts, historical binding and author review, relay evidence, the bounded AVS limitation, independent-reader execution and public release. Old reports and the original tutorial under historical directories describe predecessor versions, not acceptance of this revision.

Public predecessor: [data](https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1), [organization repository](https://github.com/Oracle4CEG/Oracle4SD-Atlas). New public version fields remain empty until publication actually occurs.
'''
    (repo/'README.md').write_text(readme)
    for folder in ['templates','reports']:
        (repo/folder).mkdir(exist_ok=True);(repo/folder/'CURRENT_REVISION.txt').write_text('Current revision navigation: root README.md and metadata/revision/revision_response.csv. Existing dated reports are historical evidence.\n')
    if not (r/'dataset_deposit').exists():(r/'dataset_deposit').symlink_to(dep,target_is_directory=True)
    print('Local repository synchronized; no remote was changed.')
if __name__=='__main__':main()

"""Feasibility, bounded tutorial inputs, acquisition profiles and release documentation."""
from pathlib import Path
import argparse,json,hashlib,shutil
import pandas as pd,pyarrow.parquet as pq,duckdb

BRANCHES=['UMA','Chainlink','Tellor','Flare FTSOv2','Pyth','Chronicle','RedStone Push','DIA']
METRICS=['role_participation','realized_rewards','applied_losses','committed_capital','capital_hours','completion_delay','due_obligations','completion_fraction','execution_fees','reward_gini','top_decile_reward_share','control_weight_hhi','effective_control_actors','reward_accrual','claimable_rewards','payment_delay','slashable_capital','historical_threshold','minimum_threshold_coalition','independent_deviation']
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--native',required=True);ap.add_argument('--out',required=True);ap.add_argument('--atlas',required=True);a=ap.parse_args();root=Path(a.out).resolve();native=Path(a.native).resolve();atlas=Path(a.atlas).resolve()
    d={x:set() for x in BRANCHES}
    d['UMA']=set('role_participation realized_rewards applied_losses committed_capital capital_hours completion_delay reward_gini top_decile_reward_share'.split())
    d['Chainlink']=set('role_participation realized_rewards reward_gini top_decile_reward_share'.split())
    d['Tellor']=set('role_participation realized_rewards reward_accrual reward_gini top_decile_reward_share'.split())
    d['Flare FTSOv2']=set('role_participation realized_rewards claimable_rewards reward_gini top_decile_reward_share control_weight_hhi effective_control_actors historical_threshold minimum_threshold_coalition'.split())
    d['Pyth']=set('role_participation realized_rewards reward_gini top_decile_reward_share'.split())
    d['Chronicle']=set('role_participation realized_rewards reward_gini top_decile_reward_share'.split())
    d['DIA']=set('role_participation realized_rewards'.split())
    reason={
    'UMA':'Polygon OOv2 only for daily money and completion; completed positions for capital exposure; DVM accrued/applied stages remain separate.',
    'Chainlink':'Only dated, transfer-reconciled v0.2 claims; substantial missing block times. Feed update intervals are not reward completion delays.',
    'Tellor':'Micro-reporters and verified tip withdrawals into stake. Applied dispute loss lacks a separately verified application time for daily assignment.',
    'Flare FTSOv2':'Claims by reward owner; policy weights/thresholds remain epoch-supported. Registered signers are addresses, not independent entities.',
    'Pyth':'OIS transfers to stake custody and observed stake actions. Historical epoch factors are not reward amounts.',
    'Chronicle':'Registered Scribe update callers and observed challenge rewards only. Publisher compensation is outside this collection.',
    'RedStone Push':'Delivery contract activity only; publisher identities and AVS economics require independent evidence and a separately registered scope.',
    'DIA':'Observed Lasernet staking/withdrawals. Total reward is split across beneficiary/principal wallet; no recipient inequality until allocation is reconstructed.'}
    rows=[]
    for branch in BRANCHES:
        for m in METRICS:
            status='derivable' if m in d[branch] else 'additional_acquisition'
            if m=='independent_deviation':status='unknown'
            if branch=='RedStone Push' and m in ['due_obligations','completion_fraction','payment_delay']:status='inapplicable_to_sampled_delivery_unit'
            if branch in ['Chronicle','RedStone Push'] and m=='reward_accrual':status='unknown'
            temporal='event_day'
            if branch=='Flare FTSOv2' and m in ['control_weight_hhi','effective_control_actors','historical_threshold','minimum_threshold_coalition','claimable_rewards']:temporal='epoch_only'
            if branch=='Tellor' and m=='reward_accrual':temporal='event_day_not_materialized_in_daily_summary'
            rows.append(dict(branch=branch,variable=m,feasibility=status,temporal_support=temporal,coverage='retained_scope_only',reason=reason[branch],human_rule_review='pending_author_review'))
    pd.DataFrame(rows).to_csv(root/'metadata/variable_feasibility.csv',index=False)
    # Small native samples serve eight executable archived demonstrations; they do not masquerade as fresh acquisition.
    choices={'UMA':'polygon_uma_request_rounds','Chainlink':'chainlink_staking_v02_events','Tellor':'tellor_disputes','Flare FTSOv2':'flare_reward_epochs','Pyth':'pyth_ois_economic_events','Chronicle':'chronicle_ethereum_events','RedStone Push':'redstone_ethereum_push_events','DIA':'dia_staking_withdrawals'}
    pipe=root/'tutorial';reg=[];c=duckdb.connect()
    for branch,n in choices.items():
        slug=branch.lower().replace(' ','_');src=native/'data/curated/parquet'/(n+'.parquet');target=pipe/'data_source'/slug/'native_sample.parquet';target.parent.mkdir(parents=True,exist_ok=True)
        # First bounded native sample, preserving physical ordering and exact fields.
        first=next(pq.ParquetFile(src).iter_batches(batch_size=8));pq.write_table(__import__('pyarrow').Table.from_batches([first]),target,compression='zstd')
        profile={'branch':branch,'source_mode':'archived_native_replay','parent_native_table':n,'parent_sha256':sha(src),'sample_sha256':sha(target),'sample_rows':first.num_rows,'acquisition_scope':'Native retained subset; fresh chain re-acquisition is a separate optional step.','input':'data_source/'+slug+'/native_sample.parquet','query_output':'queried_data/'+slug+'/native_sample.parquet','processed_output':'processed_data/'+slug+'/summary.json','processing':'processing_code/replay.py'}
        reg.append(profile)
    (pipe/'processing_code').mkdir(exist_ok=True);(pipe/'metadata').mkdir(exist_ok=True)
    (pipe/'metadata/profiles.json').write_text(json.dumps(reg,indent=2))
    replay='''from pathlib import Path
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
'''
    (pipe/'processing_code/replay.py').write_text(replay)
    import nbformat
    nb=nbformat.v4.new_notebook();cells=[nbformat.v4.new_markdown_cell('# Oracle4SD: eight bounded native demonstrations\nEach section replays retained records, verifies input identity and examines native UTC clocks. It does not reacquire a full protocol history. The ten logical products consist of eight branches, the UMA prediction task and the daily measurements.'),nbformat.v4.new_code_cell("from pathlib import Path\nimport sys\nroot=Path.cwd()\nsys.path.insert(0,str(root/'processing_code'))\nfrom replay import run_branch")]
    for branch in BRANCHES:cells.extend([nbformat.v4.new_markdown_cell('## '+branch+'\n'+reason[branch]),nbformat.v4.new_code_cell(f"run_branch(root, {branch!r})")])
    cells.append(nbformat.v4.new_markdown_cell('## Reuse boundaries\nDaily counts do not establish complete coverage. Economic amounts retain asset and stage. Account counts do not identify independent organizations. Prediction outcomes are protocol decisions, and retrospective cohort membership is not known at proposal time.'))
    nb.cells=cells;nb.metadata.kernelspec={'display_name':'Python 3','language':'python','name':'python3'};nbformat.write(nb,pipe/'Oracle4SD_Atlas_Tutorial.ipynb')
    from nbclient import NotebookClient
    executed=NotebookClient(nb,timeout=120,kernel_name='python3',resources={'metadata':{'path':str(pipe)}}).execute();nbformat.write(executed,pipe/'Oracle4SD_Atlas_Tutorial_executed.ipynb')
    (pipe/'README.txt').write_text('Run Oracle4SD_Atlas_Tutorial.ipynb from this directory. Requires pyarrow, nbformat, nbclient. All eight sections use bounded archived native inputs. No network credentials are required. Each sample is linked by SHA-256 to its full retained parent. Fresh acquisition success is documented separately in the release acquisition report.\n')
    # Keep original model outputs available without presenting them as new task validation.
    arc=root/'archive/model_experiments';arc.mkdir(parents=True,exist_ok=True)
    for n in ['decision_benchmark','financial_benchmark']:
        shutil.copytree(atlas/'reports/revision_20261012'/n,arc/n,dirs_exist_ok=True)
    (arc/'README.txt').write_text('Historical model outputs retained for provenance only. They used the earlier feature definitions and are not validation of the revised prediction task. No models were fitted in this revision.\n')
    (root/'metadata/ai_assistance_log.json').write_text(json.dumps({'assistant':'Codex','model_family_disclosed_by_environment':'GPT-6','exact_backend_model_version':'not_exposed','revision_date':'2026-10-26','user_instruction':'Complete remaining mentor revisions; use natural scholarly prose; browse primary writing guidance before drafting.','tasks':['source inspection','Python/SQL drafting','data recomputation','LaTeX revision','vector figure generation','automated checks'],'human_rule_approval':'not_supplied','historical_prompt_transcripts':'not_reconstructed','author_review_required':['historical implementation binding','six semantic rules','feature availability at proposal time','case interpretation','final scientific wording'],'limitations':'Automated checks and model assistance do not constitute human verification.'},indent=2))
    print('Feasibility matrix and eight executed archived tutorial demonstrations created.')
if __name__=='__main__':main()

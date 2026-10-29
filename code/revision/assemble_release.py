"""Assemble a local ten-product dataset deposit and matching machine-readable metadata."""
from pathlib import Path
import argparse,json,hashlib,os,shutil,re
import pyarrow as pa,pyarrow.parquet as pq,pandas as pd

PRODUCTS=['UMA','Chainlink','Tellor','Flare FTSOv2','Pyth','Chronicle','RedStone Push','DIA','UMA prediction','Daily measurements']
def sha(p):
    with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def branch(name):
    for prefix,branch in [('polygon','UMA'),('uma','UMA'),('chainlink','Chainlink'),('tellor','Tellor'),('flare','Flare FTSOv2'),('pyth','Pyth'),('chronicle','Chronicle'),('redstone','RedStone Push'),('dia','DIA'),('polymarket','UMA')]:
        if name.startswith(prefix):return [branch]
    return PRODUCTS[:8]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--root',required=True);ap.add_argument('--native',required=True);ap.add_argument('--atlas',required=True);ap.add_argument('--core',required=True);ap.add_argument('--deposit',required=True);a=ap.parse_args();r=Path(a.root).resolve();native=Path(a.native).resolve();atlas=Path(a.atlas).resolve();core=Path(a.core).resolve();out=Path(a.deposit).resolve();out.mkdir(parents=True,exist_ok=True)
    assert json.loads((core/'validation.json').read_text())['passed']
    assert len(json.loads((core/'validation.json').read_text())['tables'])==5
    meta=out/'metadata';meta.mkdir(exist_ok=True);entries=[]
    def add(src,dst,products,layer,unit):
        dest=out/dst;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():dest.unlink()
        try:os.link(src,dest)
        except OSError:shutil.copyfile(src,dest)
        entries.append({'path':str(dst),'products':products,'layer':layer,'observation_unit':unit,'rows':pq.read_metadata(dest).num_rows,'bytes':dest.stat().st_size,'sha256':sha(dest),'input_path':str(src)})
    registry=pd.read_csv(r/'Oracle4SD_Atlas/supplementary/temporal/temporal_registry.csv');unitmap=dict(zip(registry.table,registry.observation_unit))
    for src in sorted((native/'data/curated/parquet').glob('*.parquet')):add(src,Path('data/native')/src.name,branch(src.stem),'native_utc',str(unitmap.get(src.stem,'table-defined native observation')))
    for src in sorted(core.glob('*.parquet')):
        add(src,Path('data/core_clocks')/src.name,PRODUCTS[:8],'core_clock_companion','UTC clock annotation joined to its parent by the retained record identifier')
        parent=src.name.replace('_clocks.parquet','.parquet');add(r/'rebuilt/data/curated/parquet'/parent,Path('data/core')/parent,PRODUCTS[:8],'common_or_economic','typed native projection or economic component; clocks are supplied by the linked companion')
    for area in ['daily','prediction','evidence','sensitivity']:
        for src in sorted((r/'data'/area).rglob('*.parquet')):
            products=['Daily measurements'] if area in ['daily','sensitivity'] else ['UMA prediction'] if area=='prediction' else branch(src.stem)
            unit='date, branch, mechanism, role, asset, stage and measure' if src.stem=='daily_measurements' else 'request' if src.stem=='uma_prediction_tasks' else 'table-defined supporting observation; see field dictionary'
            if src.stem.startswith('TELLOR'):products=['Tellor']
            elif src.stem.startswith(('UMA','DVM')):products=['UMA']
            add(src,Path('data')/area/src.relative_to(r/'data'/area),products,area,unit)
    old=json.loads((atlas/'metadata/repaired_atlas_20261012/field_dictionary.json').read_text());oldmap={(x['table'],x['field']):x for x in old};feature=pd.read_csv(r/'data/prediction/feature_dictionary.csv').set_index('feature').to_dict('index')
    definitions={
      'date_utc':'UTC calendar date of the eligible event or interval overlap.',
      'branch':'Registered oracle branch; the implementation scope is narrower than the protocol ecosystem.',
      'mechanism_version':'Named mechanism or implementation scope of this measurement.',
      'actor_role':'Role counted or paid within the registered mechanism; an address is not an independent entity.',
      'observation_unit':'Native object defining the measurement population.',
      'economic_stage':'State in the accounting process; stages must not be added indiscriminately.',
      'metric':'Named measurement with a source query and acceptance rule.',
      'source_count':'Number of eligible timed native observations contributing to this daily row.',
      'active_accounts':'Number of distinct non-null observed addresses in the stated role and daily group.',
      'value_raw':'Exact sum in integer native units, serialized as a decimal string.',
      'value':'Display conversion of value_raw by 10 raised to asset_decimals; authoritative arithmetic uses value_raw.',
      'asset':'Asset identifier retained by the source; assets are not pooled or converted to USD.',
      'asset_decimals':'Number of decimal places used to convert smallest integer asset units.',
      'kind':'Whether the measure is an event count or an amount.',
      'coverage_status':'Coverage qualification for this retained population; partial is not complete acquisition.',
      'denominator_kind':'Description of the population used as the row denominator.',
      'denominator':'Number of eligible retained timed source observations, not total protocol exposure.',
      'source_population_count':'Eligible source observations before excluding missing event clocks.',
      'source_timed_count':'Eligible source observations with a supported event clock.',
      'coverage_reason':'Evidence explaining the coverage qualification or exclusion.',
      'allocation':'Assignment rule: instantaneous event day or documented interval overlap.',
      'rule_id':'Versioned rule used to classify or aggregate the observation.',
      'event_time_utc':'Supported native event time in UTC; epoch and snapshot records remain null.',
      'event_time_status':'Basis for the UTC clock or the reason no event clock is assigned.',
      'epoch_start_utc':'Inclusive start of the native epoch support interval in UTC.',
      'epoch_end_utc':'Exclusive end of the native epoch support interval in UTC.',
      'amount_raw':'Exact amount in the smallest native units of the stated asset.',
      'actor':'Observed address or delivery-contract identifier in the stated role.',
      'recipient_count':'Number of recipients with positive observed rewards in the group.',
      'gini':'Gini coefficient across positive observed recipient totals in the same day, asset and economic stage.',
      'top_decile_share':'Share paid to the largest ceil(0.1*n) positive observed recipient totals.',
      'population':'Description of the observations included in this statistic.',
      'completed_requests':'Flow-reconciled requests completed on this UTC date.',
      'median_hours':'Median elapsed request-event to settlement time among the included completed requests.',
      'p90_hours':'90th percentile of elapsed request-event to settlement time in the same completed population.',
      'raw_token_seconds':'Sum of observed escrow balance multiplied by seconds of overlap; divide by asset precision and 3600 for token-hours.',
      'requests':'Distinct eligible requests contributing positive escrow exposure on this date.',
      'measure':'Interpretation of the balance exposure or measured quantity.',
      'transfer_count':'Number of observed token movements assigned to this request.',
      'all_timed':'All included token movements have supported execution times.',
      'nonnegative':'Running balance implied by included token movements never becomes negative.',
      'closes_to_zero':'Signed token movements sum to zero for the completed request.',
      'funded':'At least one positive transfer into escrow is retained.',
      'eligible':'All explicit inclusion conditions for the escrow-exposure cohort are satisfied.',
      'next_time':'Execution time of the next included token movement in the request.',
      'delta_raw':'Signed token movement into (positive) or out of (negative) OOv2 escrow.',
      'balance_raw':'Running observed OOv2 escrow balance after this movement, in integer native units.',
      'registered_signers':'Number of signer addresses in the retained epoch signing policy.',
      'weight_total':'Sum of integer weights in the retained signing policy.',
      'threshold_raw':'Integer threshold in the archived policy; operative interpretation requires historical implementation binding.',
      'weight_raw':'Integer signing-policy weight for this address and epoch.',
      'weight_type':'Mechanism-specific type of weight; signing weight is not deposited capital.',
      'hhi':'Sum of squared normalized signing-policy weights.',
      'effective_signers':'Reciprocal of signing-weight HHI; addresses are not independently identified organizations.',
      'min_signers_strictly_above_threshold':'Fewest largest-weight addresses whose cumulative weight strictly exceeds the recorded threshold.',
      'min_signers_at_least_threshold':'Fewest largest-weight addresses whose cumulative weight is at least the recorded threshold.',
      'registration_mapping_complete':'All policy signers match retained registration addresses for the same epoch.',
      'source_sha256':'SHA-256 of the input artifact used for this observation.',
      'source_path':'Recorded local input locator; use the source fingerprint and release lineage for portability.',
      'historical_bytecode_binding':'Status of independent historical runtime/source binding.',
      'entity_identity':'Whether identity concerns addresses or independently established entities.',
      'sample_id':'Native OOv2 request identifier; one eligible request per task row.',
      'decision_time_utc':'Proposal event time T0 in UTC.',
      'request_event_time_utc':'Execution time of the request event, distinct from the request-reference timestamp.',
      'challenge_time_outcome_only':'Observed challenge time used for retrospective selection; excluded from feature allowlist.',
      'settlement_time_outcome_only':'Settlement time used as later outcome evidence; excluded from feature allowlist.',
      'challenge_deadline_utc':'Expiry recorded by the proposal, expressed in UTC.',
      'resolution_class_outcome_only':'Native resolved-price class, retaining early expiration and indeterminate states.',
      'proposal_rejected_by_protocol':'One if native resolved and proposed integers differ; zero otherwise; not independent truth.',
      'cohort_basis':'Retrospective eligibility restriction used to construct the task.',
      'independent_truth_available':'Whether a separately validated factual reference is available; false for this task.',
      'feature':'Feature name in the sixteen-field allowlist.',
      'availability_status':'Native event, strictly prior reconstruction or historical parameter-binding requirement.',
      'source_key':'Native transaction or defined historical population supporting a feature.',
      'missing':'True when the task feature is missing for the request.',
      'reason':'Reason for a correction, missing value or evidence qualification.',
      'before':'Retained earlier feature value.',
      'after':'Recomputed feature value; null is preserved for undefined ratios.',
      'rule':'Versioned transformation responsible for the feature change.',
      'object_id':'Native object locator affected by the stated semantic rule.',
      'chain':'Network on which the source evidence executes.',
      'field':'Name of the affected field in the earlier derived representation.',
      'before_value':'Value in the earlier measurement of the same native object.',
      'after_value':'Value after applying the registered correction rule; null can mean an unsupported applied loss.',
      'historical_source_binding':'Retained source-binding grade; A and B describe different strength of historical evidence.',
      'human_review_status':'Author sign-off status, distinct from automated checks.',
      'evidence_status':'Evidence supporting the measurement or unresolved binding.',
      'event_id':'T1--T5 locator for an endpoint of the worked case.',
      'stage':'Request, proposal, challenge, Ethereum resolution or Polygon settlement.',
      'hours_since_request':'Elapsed UTC hours from the first case endpoint.',
      'explorer_url':'Direct public transaction locator; it does not imply human explorer review.',
      'component':'Economic component represented by this cashflow row.',
      'amount_token':'Human-readable token amount using the specified asset precision.',
      'role':'Participant or fee-recipient role in the cashflow record.',
      'nonadditive_group':'Native request tying overlapping representations to the same settlement.',
      'initiation_escrow_raw':'Reporter stake amount associated with dispute initiation, distinct from final applied loss.',
      'applied_loss_under_recorded_outcome_rule_raw':'Loss supported by the retained final-outcome rule; application time is separately unknown.',
      'protocol_report_outcome':'Support/rejection of the challenged report under protocol adjudication.',
      'application_time_utc':'Execution time of applying a loss; unknown when no matched application event is retained.',
      'accrued_adjustment_raw':'Signed request-level voter adjustment; not a uniquely attributed applied stake change.',
      'request_attributed_applied_delta_raw':'Applied stake change uniquely matched to this request; null when unmatched.',
      'missing_reason':'Evidence-specific reason a value is unavailable.',
      'accrual_time_utc':'Execution time of the accrual event, not application to stake.',
      'stage_rule':'Non-additivity rule separating request accrual and net stake application.',
      'recorded_net_adjustment_raw':'Signed adjustment emitted by VoterSlashApplied.',
      'post_stake_raw':'Stake value emitted after the application, in integer UMA units.',
      'supported_net_stake_delta_raw':'Applied signed change where the retained state rule resolves clipping; null if pre-state is needed.'}
    dictionary=[];oldkeys={(x['table'],x['field']) for x in old}
    old_context=json.loads((atlas/'metadata/huggingface_review_20261012/croissant.json').read_text())['@context'];old_context['isArray']='cr:isArray'
    cro={'@context':old_context,'@type':'sc:Dataset','name':'Oracle4SD Atlas: ten logical products, local revision','description':'Native oracle evidence with UTC annotations, common economic representations, a UMA prediction task and coverage-qualified daily measurements. Local review deposit; no new public version is claimed.','license':'https://creativecommons.org/licenses/by/4.0/','version':'atlas-local-revision-20261026','conformsTo':'http://mlcommons.org/croissant/1.1','isLiveDataset':False,'distribution':[],'recordSet':[]}
    def datatype(tp):
        isarr=pa.types.is_list(tp) or pa.types.is_large_list(tp)
        if isarr:tp=tp.value_type
        dt='sc:Boolean' if pa.types.is_boolean(tp) else 'sc:Integer' if pa.types.is_integer(tp) else 'sc:Float' if pa.types.is_floating(tp) or pa.types.is_decimal(tp) else 'sc:DateTime' if pa.types.is_timestamp(tp) else 'sc:Date' if pa.types.is_date(tp) else 'sc:StructuredValue' if pa.types.is_struct(tp) else 'sc:Text'
        return dt,isarr
    for row in entries:
        path=out/row['path'];name=path.stem;fileid='files/'+row['path'];recordid='records/'+row['path'].removesuffix('.parquet');cro['distribution'].append({'@type':'cr:FileObject','@id':fileid,'name':row['path'],'description':'Physical table in '+', '.join(row['products'])+'.','contentUrl':row['path'],'encodingFormat':'application/x-parquet','sha256':row['sha256']});fields=[]
        for f in pq.read_schema(path):
            prior=oldmap.get((name,f.name),{});review='defined_by_revision_rule'
            if f.name in feature:desc=feature[f.name]['formula']+'; '+feature[f.name]['source']+'. Missingness: '+feature[f.name]['missingness']+'.'
            elif f.name in definitions:desc=definitions[f.name]
            elif prior:desc=prior['definition'];review=prior.get('definition_scope','inherited')
            elif f.name.endswith('_outcome_only'):desc='Later outcome evidence corresponding to '+f.name.removesuffix('_outcome_only')+'; excluded from candidate features.'
            elif f.name.endswith('_tx') or f.name in ['transaction_hash','source_tx']:desc='Native transaction identifier for the named event on its recorded chain.'
            elif f.name in ['block_number','source_block']:desc='Native execution block number or height; not comparable across chains.'
            elif f.name in ['log_index','source_log_index']:desc='Native event position within the chain-specific transaction/block log ordering.'
            elif f.name in ['request_id','oo_request_id','dvm_request_id']:desc='Native or deterministically reconstructed request identity, scoped to mechanism and chain.'
            elif f.name in ['contract','source_contract']:desc='Source contract or module identifier on the recorded chain.'
            else:desc='Native or derived '+f.name+'; the exact Arrow representation and source transformation are retained in the linked table and code.';review='requires_additional_semantic_review'
            dictionary.append({'table_path':row['path'],'field':f.name,'arrow_type':str(f.type),'nullable':f.nullable,'definition':desc,'definition_status':review,'missing_rule':'Null means missing, unresolved or inapplicable under the table rule; no general zero imputation.'})
            typ,arr=datatype(f.type);ff={'@type':'cr:Field','@id':recordid+'/'+f.name,'name':f.name,'description':desc,'dataType':typ,'source':{'fileObject':{'@id':fileid},'extract':{'column':f.name}}}
            if arr:ff['isArray']=True
            fields.append(ff)
        cro['recordSet'].append({'@type':'cr:RecordSet','@id':recordid,'name':name,'description':row['observation_unit']+'; products: '+', '.join(row['products'])+'.','field':fields})
    (meta/'table_catalog.json').write_text(json.dumps(entries,indent=2));pd.DataFrame([{**x,'products':';'.join(x['products'])} for x in entries]).to_csv(meta/'file_manifest.csv',index=False)
    pd.DataFrame(dictionary).to_csv(meta/'field_dictionary.csv',index=False);(out/'croissant.json').write_text(json.dumps(cro,indent=2))
    membership=[{'product_id':f'P{i+1:02}','name':name,'physical_tables':[x['path'] for x in entries if name in x['products']]} for i,name in enumerate(PRODUCTS)];(meta/'logical_products.json').write_text(json.dumps(membership,indent=2))
    for name in ['variable_feasibility.csv','ai_assistance_log.json']:
        if (r/'metadata'/name).exists():shutil.copy2(r/'metadata'/name,meta/name)
    shutil.copytree(r/'Oracle4SD_Atlas/supplementary/temporal',meta/'temporal_native',dirs_exist_ok=True)
    for area in ['daily','prediction','evidence','sensitivity','acquisition']:
        for src in (r/'data'/area).rglob('*'):
            if src.is_file() and src.suffix in ['.json','.csv','.sql']:
                dest=meta/'support'/area/src.relative_to(r/'data'/area);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dest)
    shutil.copy2(core/'validation.json',meta/'core_temporal_validation.json');shutil.copy2(r/'rebuilt/validation/full_release.json',meta/'full_reconstruction_validation.json')
    reps=['polygon_uma_request_rounds','chainlink_staking_v02_events','tellor_disputes','flare_reward_epochs','pyth_ois_reward_epochs','chronicle_ethereum_events','redstone_ethereum_push_events','dia_staking_withdrawals']
    configs=[(PRODUCTS[i],f'data/native/{n}.parquet') for i,n in enumerate(reps)]+[('UMA prediction','data/prediction/uma_prediction_tasks.parquet'),('Daily measurements','data/daily/daily_measurements.parquet')]
    yaml='---\nlicense: cc-by-4.0\ntask_categories:\n- tabular-classification\nlanguage:\n- en\nconfigs:\n'
    for name,path in configs:yaml+=f"- config_name: {name.lower().replace(' ','_')}\n  data_files:\n  - split: train\n    path: {path}\n"
    yaml+='---\n'
    card=yaml+'''# Oracle4SD Atlas: local coordinated revision

This deposit contains ten logical products: eight native oracle branches, a request-level UMA prediction task and coverage-qualified daily measurements. The ten Viewer configurations expose representative tables; the full physical-table inventory and relationships are in the catalogue. A Viewer `train` split here is a file-loading label, not a declared modelling partition.

The daily product retains date, branch, mechanism, actor role, asset, unit, economic stage, denominator and coverage. Missing days are not zero-filled. Signing policies remain epoch-supported. Escrow exposure uses observed closed-request balances; it is not protocol-wide collateral or participant wealth.

The UMA task is retrospectively restricted to challenged, deterministically linked, settled and transfer-reconciled requests. The target compares the protocol's resolved and proposed integers, including special values. Sixteen candidate features have explicit missingness and availability records. No fitted model or model performance is part of this revision.

Native UTC tables preserve original fields. Core parent tables retain legacy fields. Keyed clock companions supply authoritative supported UTC event clocks and are joined by the retained record identifier. Epochs and snapshots remain distinct from events. Older application/model views are archived with the reconstruction and are not relabelled as updated decision-time data.

Semantic corrections preserve previous values, new values and native source locators. Machine checks do not constitute author sign-off. Contract/runtime binding, incomplete acquisition intervals, unmatched relay steps and independent factual truth remain qualified in the evidence records.

This is a local review deposit, not a newly published Hugging Face version. Public predecessor: https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1 . Processing repository: https://github.com/Oracle4CEG/Oracle4SD-Atlas . Publication should preserve the file manifest, physical recordsets, product membership and tutorial together.
'''
    (out/'README.md').write_text(card)
    checks={'logical_products':len(membership),'viewer_configs':len(configs),'physical_tables':len(entries),'croissant_recordsets':len(cro['recordSet']),'dictionary_entries':len(dictionary),'all_paths_exist':all((out/x['path']).is_file() for x in entries),'unique_paths':len({x['path'] for x in entries})==len(entries),'field_count_matches':len(dictionary)==sum(len(x['field']) for x in cro['recordSet']),'definition_status_counts':pd.Series([x['definition_status'] for x in dictionary]).value_counts().to_dict()};(meta/'consistency_validation.json').write_text(json.dumps(checks,indent=2));print(json.dumps(checks))
if __name__=='__main__':main()

"""Final structural checks on manuscript, products and actual execution evidence."""
from pathlib import Path
import argparse,json,hashlib,ast,re
import pandas as pd,pyarrow.parquet as pq,fitz

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--deposit',required=True);a=p.parse_args();r=Path(a.root).resolve();dep=Path(a.deposit).resolve();checks=[]
    def add(name,ok,scope):checks.append({'check':name,'passed':bool(ok),'scope':scope})
    for rel in ['data/daily/validation.json','data/daily/escrow_validation.json','data/prediction/validation.json','data/evidence/validation.json','data/sensitivity/validation.json']:
        d=json.loads((r/rel).read_text());add(rel,d['passed'],'Previously executed actual data checks')
    for rel in ['metadata/core_validation.json','metadata/core_key_validation.json']:
        d=json.loads((dep/rel).read_text());add(rel,d['passed'],'Five full core companion populations')
    x=json.loads((dep/'metadata/full_reconstruction_validation.json').read_text());add('full_reconstruction',all(y['passed'] for y in x['checks']),'Full 90-table reconstruction and 48 checks')
    c=json.loads((dep/'metadata/table_catalog.json').read_text());d=pd.read_csv(dep/'metadata/field_dictionary.csv',keep_default_na=False);expected={(x['path'],f.name,str(f.type)) for x in c for f in pq.read_schema(dep/x['path'])};actual=set(zip(d.table_path,d.field,d.arrow_type));add('physical_dictionary_exact',actual==expected,'All 100 product tables; schema names and Arrow types')
    add('ten_logical_products',len(json.loads((dep/'metadata/logical_products.json').read_text()))==10,'Eight branches, one task, one daily product')
    f=json.loads((r/'metadata/figure_final_validation.json').read_text());add('vector_fonts_and_text',all(x['font_check'] and x['raster_images']==0 and x['editable_svg_text'] for x in f),'Eight new figures; Times New Roman, vector-only PDFs and editable SVG text')
    tutorial=json.loads((r/'tutorial/metadata/execution_summary.json').read_text());add('tutorial_executed',tutorial['errors']==0 and tutorial['code_cells']>=16,'Local Python kernel; no hosted or independent-reader assertion')
    modes=json.loads((r/'data/acquisition/acquisition_mode_comparison.json').read_text());add('three_acquisition_modes',len(modes)==3 and all(x['passed'] for x in modes),'Same bounded case, 28 checks per mode')
    cr=json.loads((dep/'metadata/croissant_sample_load.json').read_text());add('croissant_sample_loads',len(cr)==4 and all(x['loaded'] for x in cr),'Two nested native tables and two derived products; metadata parser covers 100 RecordSets')
    paper=r/'Oracle4SD_Atlas';log=(paper/'main.log').read_text();add('latex_references',not any(x in log for x in ['undefined references','undefined citations','Overfull \\hbox','Overfull \\vbox']),'Latest local Tectonic compile')
    main=(paper/'main.tex').read_text();add('appendices_A_to_I',all('sections/appendix_'+x+'_' in main for x in 'abcdefghi'),'Nine included appendix sections')
    body=main+'\n'+'\n'.join(x.read_text() for x in (paper/'sections').glob('*.tex'));add('no_old_model_results',not re.search(r'AUROC|LightGBM|XGBoost|logistic regression|reports/|supplementary/|not rebuilt in this pass',body,re.I),'Paper prose and active section files')
    pdf=fitz.open(paper/'main.pdf');add('compiled_pdf',len(pdf)>0,'Compiled manuscript')
    roles=pd.read_csv(r/'metadata/folder_role_map.csv');add('fourteen_folder_roles',len(roles)==14 and all((r/'Oracle4SD_Atlas_Repository'/x).is_dir() for x in roles.folder_role),'Current local repository navigation')
    for file in (r/'code').glob('*.py'):ast.parse(file.read_text())
    result={'passed':all(x['passed'] for x in checks),'checks':checks,'paper_pages':len(pdf),'public_release_created':False,'human_signoff_completed':False,'independent_reader_completed':False,'full_historical_acquisition_completed':False};(r/'metadata/final_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2));assert result['passed']
if __name__=='__main__':main()

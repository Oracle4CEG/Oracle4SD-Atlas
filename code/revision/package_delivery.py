"""Create compact Overleaf, vector figure and research companion archives."""
from pathlib import Path
import argparse,shutil,json,hashlib,zipfile

def zip_tree(folder,dest,exclude=()):
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for f in sorted(folder.rglob('*')):
            if not f.is_file() or any(part in ['__pycache__','.git'] for part in f.parts):continue
            if f.suffix in exclude or f.name.endswith('.synctex.gz'):continue
            z.write(f,f.relative_to(folder))

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();r=Path(a.root).resolve();paper=r/'Oracle4SD_Atlas';repo=r/'Oracle4SD_Atlas_Repository'
    shutil.copy2(paper/'main.pdf',r/'Oracle4SD_Atlas_Revised.pdf')
    for f in (r/'figures').glob('*'):
        if f.suffix in ['.csv','.gz','.json']:shutil.copy2(f,paper/'figure_source/source_data'/f.name)
    for name in ['build_figures.py','build_extra_figures.py']:shutil.copy2(r/'code'/name,paper/'figure_source'/name)
    (paper/'figure_source/README.txt').write_text('The current figure files are vector PDF and text-based SVG. Ecosystem/epoch sources retain their existing scripts. New gallery scripts accept --root (the research delivery root) and --fonts (a directory containing the licensed Times.TTF font). Native and derived input references are recorded in the companion metadata; source-data summaries are in source_data. Full generation of all sixteen distributions uses the task Parquet in the separate deposit.\n')
    zip_tree(paper,r/'Oracle4SD_Atlas_Overleaf.zip',exclude=('.aux','.log','.out'))
    figures=r/'Figure_Delivery';figures.mkdir(exist_ok=True)
    for file in (r/'figures').iterdir():
        if file.is_file():shutil.copy2(file,figures/file.name)
    for name in ['ecosystem_scope','temporal_epoch_support']:
        for ext in ['pdf','svg','png']:
            f=paper/'figures'/(name+'.'+ext)
            if f.exists():shutil.copy2(f,figures/f.name)
    shutil.copytree(paper/'figure_source',figures/'source',dirs_exist_ok=True)
    (figures/'README.txt').write_text('PDF files contain vectors and embedded Times New Roman for the revised galleries. SVG files retain editable text and font styling; imported applications may require Times New Roman to be installed. PNG files are previews only. Main-text figures use 166 mm source width; the full feature grid is an appendix figure. Captions and evidence qualifications are in the manuscript, not small-print blocks inside the artwork.\n')
    zip_tree(figures,r/'Oracle4SD_Atlas_Figures_PDF_SVG.zip')
    shutil.copytree(paper,repo/'paper/working_revision',ignore=shutil.ignore_patterns('*.aux','*.log','*.out','*.synctex.gz'),dirs_exist_ok=True)
    zip_tree(repo,r/'Oracle4SD_Atlas_Research_Companion.zip',exclude=('.aux','.log','.out','.pyc'))
    manifest=[]
    for f in [r/'Oracle4SD_Atlas_Revised.pdf',*sorted(r.glob('Oracle4SD_Atlas_*.zip'))]:
        with f.open('rb') as h:digest=hashlib.file_digest(h,'sha256').hexdigest()
        manifest.append({'file':f.name,'bytes':f.stat().st_size,'sha256':digest})
    (r/'metadata/delivery_packages.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest))
if __name__=='__main__':main()

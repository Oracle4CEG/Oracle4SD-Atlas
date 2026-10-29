"""Create the native input layout expected by revision scripts from a deposit."""
from pathlib import Path
import argparse,os,shutil
def main():
    p=argparse.ArgumentParser();p.add_argument('--deposit',required=True);p.add_argument('--output',required=True);a=p.parse_args();dep=Path(a.deposit).resolve();out=Path(a.output).resolve()
    if out.exists():raise FileExistsError('Use a new input-layout directory')
    target=out/'data/curated/parquet';target.mkdir(parents=True)
    for src in (dep/'data/native').glob('*.parquet'):os.symlink(src,target/src.name)
    legacy=dep/'reproduction_inputs/decision_samples.parquet'
    if legacy.exists():
        dst=out/'data/applications/trustworthy_ai_challenge';dst.mkdir(parents=True);shutil.copy2(legacy,dst/legacy.name)
    print(out)
if __name__=='__main__':main()

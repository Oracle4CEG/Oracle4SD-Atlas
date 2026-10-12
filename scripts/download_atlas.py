"""Download a pinned Atlas component or selected files, verifying every byte."""
import argparse
import hashlib
import json
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()


def download(manifest,component,output,include=None):
    registry=json.loads(Path(manifest).read_text())
    release=registry['components'][component]
    files=release['files']
    if include:
        wanted=set(include);files=[f for f in files if f['path'] in wanted]
        missing=wanted-{f['path'] for f in files}
        if missing:raise ValueError('Unknown requested paths: '+str(sorted(missing)))
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    for index,item in enumerate(files):
        relative=Path(item['path'])
        if relative.is_absolute() or '..' in relative.parts:raise ValueError('Unsafe manifest path')
        target=output/relative
        if not target.resolve().is_relative_to(output):raise ValueError('Output symlink escapes root')
        target.parent.mkdir(parents=True,exist_ok=True)
        if target.exists():
            if target.stat().st_size==item['bytes'] and digest(target)==item['sha256']:
                print(f"Verified existing {index+1}/{len(files)}: {relative}",flush=True);continue
            raise ValueError(f'Existing file differs: {target}; use a new output directory')
        url=item.get('url')
        if not url or '/resolve/main/' in url:raise ValueError('Missing immutable download URL: '+str(relative))
        temp=target.with_suffix(target.suffix+'.download')
        h=hashlib.sha256();size=0
        with requests.get(url,stream=True,timeout=(30,120)) as response:
            response.raise_for_status()
            with temp.open('wb') as f:
                for block in response.iter_content(8*1024*1024):
                    if block:f.write(block);h.update(block);size+=len(block)
        if size!=item['bytes'] or h.hexdigest()!=item['sha256']:
            raise ValueError(f'Download identity mismatch: {relative}; partial file retained at {temp}')
        temp.replace(target)
        print(f"Downloaded and verified {index+1}/{len(files)}: {relative}",flush=True)
    (output/'download_identity.json').write_text(json.dumps(dict(component=component,dataset_revision=release['revision'],files=files),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',default=str(ROOT/'configs/data_releases.json'))
    p.add_argument('--component',choices=['native','repaired'],default='native')
    p.add_argument('--output',required=True)
    p.add_argument('--include',action='append',help='Exact dataset-relative file path; may be repeated')
    a=p.parse_args();download(a.manifest,a.component,a.output,a.include)

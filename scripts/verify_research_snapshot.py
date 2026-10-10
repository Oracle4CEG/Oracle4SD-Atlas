"""Verify public selected Atlas tables against the historical full-file inventory.

Identity and Parquet footer checks do not certify unresolved full-core semantics.
The archive is inspected in a temporary directory and never replaces local data.
"""
import argparse
import csv
import hashlib
import json
import shutil
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def verify(output):
    pin = json.loads((ROOT/'metadata/research_snapshot.json').read_text())
    inventory = {r['path']: r for r in csv.DictReader((ROOT/'metadata/full_data_inventory.csv').open())}
    spec = pin['archive']
    url = f"https://huggingface.co/datasets/{pin['dataset_id']}/resolve/{pin['revision']}/{spec['path']}"
    findings = []
    with tempfile.TemporaryDirectory(prefix='atlas-selected-') as tmp:
        temporary = Path(tmp)
        archive_path = temporary/'selected.tar.gz'
        with urlopen(url, timeout=120) as source, archive_path.open('wb') as target:
            shutil.copyfileobj(source, target)
        if digest(archive_path) != spec['sha256'] or archive_path.stat().st_size != spec['bytes']:
            raise ValueError('Public selected-input archive changed')
        with tarfile.open(archive_path, 'r:gz') as archive:
            members = archive.getmembers()
            names = [m.name for m in members]
            expected = {r['archive_member'] for r in pin['files']}|{'artifact_manifest.json'}
            if len(names) != len(set(names)) or set(names) != expected or any(not m.isfile() for m in members):
                raise ValueError('Unexpected archive paths or non-regular files')
            for number, record in enumerate(pin['files']):
                # Controlled local filename: never use archive paths for extraction.
                path = temporary/f'{number}.parquet'
                with archive.extractfile(record['archive_member']) as source, path.open('wb') as target:
                    shutil.copyfileobj(source, target)
                original = inventory[record['inventory_path']]
                sha = digest(path); rows = pq.read_metadata(path).num_rows
                passed = (sha == record['sha256'] == original['sha256'] and
                          rows == record['rows'] == int(original['rows']) and
                          path.stat().st_size == record['bytes'] == int(original['bytes']))
                findings.append(dict(path=record['inventory_path'], sha256=sha, rows=rows, passed=passed))
    receipt = dict(status='PASS' if all(r['passed'] for r in findings) else 'FAIL',
                   dataset_revision=pin['revision'], authentication='anonymous HTTPS',
                   scope='Four selected file identities and row counts; not full Atlas semantic validation',
                   files=findings)
    output = Path(output); output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2)+'\n')
    if receipt['status'] != 'PASS':
        raise ValueError('Selected source identity differs from historical inventory')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, default=ROOT/'runs/selected-public-verification.json')
    verify(p.parse_args().output)

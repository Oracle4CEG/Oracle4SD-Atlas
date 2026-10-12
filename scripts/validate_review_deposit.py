"""Load all 15 review record sets from their public immutable Croissant URLs."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import mlcroissant as mlc

ROOT=Path(__file__).resolve().parents[1]


def validate(output):
    output=Path(output)
    if output.exists():raise FileExistsError(output)
    base=ROOT/'metadata/huggingface_review_20261012'
    reference=json.loads((base/'validation.json').read_text())
    expected={x['recordset']:x['expected_rows'] for x in reference['recordsets']}
    dataset=mlc.Dataset(jsonld=base/'croissant.json')
    checks=[]
    for record in dataset.metadata.record_sets:
        rows=sum(1 for _ in dataset.records(record_set=record.id))
        checks.append(dict(recordset=record.id,rows=rows,expected_rows=expected[record.id],passed=rows==expected[record.id]))
        print(record.id,rows,flush=True)
    report=dict(passed=all(x['passed'] for x in checks),recordsets=checks,
                mlcroissant_version=importlib.metadata.version('mlcroissant'),
                source='Public immutable URLs; no local mapping override',
                scope='Download, file identity, JSON-LD/schema parsing and loading; not independent scientific provenance')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    if not report['passed']:raise RuntimeError('Public review record count mismatch')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    validate(p.parse_args().output)

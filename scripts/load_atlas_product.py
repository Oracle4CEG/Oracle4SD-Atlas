"""List or retrieve Atlas product tables without combining incompatible schemas."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]


def product_tables(config, include_shared=False):
    products = json.loads((ROOT / 'metadata/revision/logical_products.json').read_text())
    product = next((p for p in products if p['config_name'] == config), None)
    if product is None:
        raise ValueError('Unknown configuration: ' + config)
    catalog = json.loads((ROOT / 'metadata/revision/table_catalog.json').read_text())
    members = set(product['physical_tables'])
    rows = [r for r in catalog if r['path'] in members]
    if not include_shared:
        rows = [r for r in rows if len(r['products']) == 1]
    return rows


def download(config, output, *, include_shared=False, table=None):
    from huggingface_hub import hf_hub_download
    release = json.loads((ROOT / 'configs/atlas_utc_release.json').read_text())
    rows = product_tables(config, include_shared)
    if table is not None:
        rows = [r for r in rows if r['path'] == table]
        if not rows:
            raise ValueError('Table not in selected product scope; shared tables require --include-shared.')
    output = Path(output).resolve()
    receipts = []
    for row in rows:
        target = (output / row['path']).resolve()
        if not target.is_relative_to(output):
            raise ValueError('Table path leaves output directory')
        if target.exists():
            source = target
        else:
            source = Path(hf_hub_download(
                repo_id=release['repo_id'], repo_type='dataset',
                revision=release['revision'], filename=release['prefix']+'/'+row['path']))
        with source.open('rb') as handle:
            observed = hashlib.file_digest(handle, 'sha256').hexdigest()
        if observed != row['sha256']:
            raise ValueError(f"Checksum differs: {row['path']}; existing files are not overwritten")
        if source != target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        receipts.append({'path': row['path'], 'sha256': observed, 'rows': row['rows']})
    output.mkdir(parents=True,exist_ok=True)
    (output / f'{config}_download_receipt.json').write_text(json.dumps({
        'release': release, 'config': config, 'include_shared': include_shared,
        'files': receipts, 'note': 'Shared tables require branch/key filtering; overlapping layers are not additive.'},indent=2)+'\n')
    return receipts


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--include-shared', action='store_true')
    parser.add_argument('--table', help='One release-relative table path')
    args = parser.parse_args()
    result = (download(args.config, args.output, include_shared=args.include_shared, table=args.table)
              if args.output else product_tables(args.config, args.include_shared))
    print(json.dumps(result, indent=2))

"""Download and restore pinned public source registries without executing them."""
import argparse
import hashlib
import json
import tarfile
from pathlib import Path

from download_atlas import download, ROOT


def restore(output, manifest=ROOT/'configs/data_releases.json'):
    output=Path(output).resolve()
    if output.exists():
        raise FileExistsError('Use a fresh source workspace')
    download(manifest,'source_registries',output)
    archive_dir=output/'data/source_archives'
    registry=json.loads((archive_dir/'source_registry_manifest.json').read_text())
    records=[]
    for item in registry:
        destination=output/item['restore_directory']
        if not destination.resolve().is_relative_to(output):
            raise ValueError('Registry destination escapes output')
        expected={m['path']:m for m in item['members']}
        observed=set()
        with tarfile.open(archive_dir/item['path']) as archive:
            for member in archive:
                # Archives retain upstream symlinks, but restoration never follows them.
                if not member.isfile():
                    continue
                relative=Path(*Path(member.name).parts[1:])
                target=destination/relative
                if '..' in relative.parts or not target.resolve().is_relative_to(destination):
                    raise ValueError('Unsafe source archive member')
                data=archive.extractfile(member).read()
                reference=expected[member.name]
                if len(data)!=reference['bytes'] or hashlib.sha256(data).hexdigest()!=reference['sha256']:
                    raise ValueError('Source archive member identity differs')
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(data)
                observed.add(member.name)
        if observed!=set(expected):
            raise ValueError('Incomplete source registry extraction')
        records.append(dict(repository=item['repository'],source_commit=item['source_commit'],files=len(observed),passed=True))
    (output/'source_restore_validation.json').write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(records,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True)
    p.add_argument('--manifest',default=str(ROOT/'configs/data_releases.json'))
    a=p.parse_args();restore(a.output,a.manifest)

"""Repair the 15-table review deposit's metadata against immutable file bytes."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import mlcroissant as mlc
import pyarrow as pa
import pyarrow.parquet as pq

HF = "https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1"


def repair(source, revision, output):
    source, output = Path(source), Path(output)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Use an immutable full dataset revision")
    output.mkdir(parents=True, exist_ok=False)
    metadata = json.loads((source/"croissant.json").read_text())
    context = mlc.Metadata(name="context").to_json()["@context"]
    context.update(prov="http://www.w3.org/ns/prov#")
    metadata["@context"] = context
    metadata["version"] = "1.5.0-review-metadata-repair-20261012"
    metadata["dateModified"] = "2026-10-12"
    metadata["prov:wasDerivedFrom"] = {"@id": HF+"/tree/"+revision}
    metadata["prov:wasGeneratedBy"] = {
        "@id": "urn:oracle-atlas:historical-review-build-v1.5",
        "@type": "prov:Activity",
        "sc:description": "Historical generation of the archived review tables; exact original execution commit is not established for every table. Byte identity is pinned; retrospective source mappings must not be mistaken for a fresh scientific rerun.",
    }
    # This flag covers the deposited predictions as well as original observations.
    metadata["rai:hasSyntheticData"] = True
    metadata["rai:dataLimitations"].append("Observed chain records are real; model predictions and derived evaluation outputs are machine-generated. Core metadata validation does not establish independent factual truth or full-Atlas completeness.")
    metadata["rai:personalSensitiveInformation"].append("Public wallet addresses can be linked across transactions and may be re-identified using outside information; do not treat pseudonymity as anonymity.")
    metadata["rai:dataReleaseMaintenancePlan"] = "Keep immutable historical revisions; publish corrected outputs with new manifests, code identities and before/after validation. Contact the repository issue tracker for reproducible data issues."
    files = {}
    checks = []
    for item in metadata["distribution"]:
        relative = "data/"+item["name"]
        path = source/relative
        observed = hashlib.sha256(path.read_bytes()).hexdigest()
        if item.get("sha256") != observed:
            raise ValueError("Historical declared file hash differs: "+relative)
        item["contentUrl"] = HF+"/resolve/"+revision+"/"+relative
        item["encodingFormat"] = "application/x-parquet"
        files[item["@id"]] = path
        checks.append(dict(check="immutable_file_identity",path=relative,sha256=observed,rows=pq.read_metadata(path).num_rows,passed=True))
    provenance=[]
    for record in metadata["recordSet"]:
        record_sources=set()
        for field in record["field"]:
            file_id=field["source"]["fileObject"]["@id"] if isinstance(field["source"]["fileObject"],dict) else field["source"]["fileObject"]
            path=files[file_id]
            name=field["source"]["extract"]["column"]
            dtype=pq.read_schema(path).field(name).type
            if pa.types.is_boolean(dtype) or name=="correct_if_automated":
                field["dataType"]="sc:Boolean"
            elif pa.types.is_integer(dtype): field["dataType"]="sc:Integer"
            elif pa.types.is_floating(dtype): field["dataType"]="sc:Float"
            record_sources.add(file_id)
        record["prov:wasDerivedFrom"]=[{"@id":HF+"/resolve/"+revision+"/data/"+files[i].name} for i in sorted(record_sources)]
        record["prov:wasGeneratedBy"]={"@id":"urn:oracle-atlas:historical-review-build-v1.5"}
        provenance.append(dict(recordset=record["@id"],dataset_revision=revision,
                               source_files=[str(files[i].relative_to(source)) for i in sorted(record_sources)],
                               observation_cutoff="2026-06-30T23:59:59Z",
                               original_execution_identity="not established for all historical contributions",
                               quality_control="Current full-file hashes, Parquet schema and row counts; scientific generation history remains separately documented."))
    target=output/"croissant.json"
    target.write_text(json.dumps(metadata,indent=2)+"\n")
    # The official parser checks JSON-LD bindings and every recordset. Map pinned
    # URLs to the downloaded, independently hashed files for an offline load test.
    mapping={item["@id"]:str(files[item["@id"]]) for item in metadata["distribution"]}
    ds=mlc.Dataset(jsonld=target,mapping=mapping)
    record_checks=[]
    for record in ds.metadata.record_sets:
        count=sum(1 for _ in ds.records(record_set=record.id))
        expected=pq.read_metadata(source/"data"/(record.name+".parquet")).num_rows
        if count != expected:
            raise ValueError(f"Record count mismatch for {record.id}: {count} != {expected}")
        record_checks.append(dict(recordset=record.id,loaded_rows=count,expected_rows=expected,passed=True))
    report=dict(data_revision=revision,mlcroissant_version="1.1.0",files=checks,recordsets=record_checks,
                passed=True,scope="Format, pinned file identity, schema and record loading; not complete historical scientific provenance")
    (output/"provenance.json").write_text(json.dumps(provenance,indent=2)+"\n")
    (output/"validation.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",required=True)
    p.add_argument("--revision",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    print(json.dumps(repair(a.source,a.revision,a.output),indent=2))

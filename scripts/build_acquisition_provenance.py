"""Bind frozen native inputs to retained records without inventing collection history.

Requires the original acquisition workspace; ordinary users consume the archived
output. Hash verification establishes file identity, not the truth of old claims.
"""

import argparse
import csv
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def sanitized(value, workspace, key=""):
    if re.search(r"(^|_)(api_?key|password|secret|authorization|access_token)($|_)", key, re.I):
        return "[redacted]"
    if isinstance(value, dict):
        return {k: sanitized(v, workspace, k) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitized(v, workspace, key) for v in value]
    if isinstance(value, str):
        value = value.replace(str(workspace.resolve()), "workspace:")
        value = value.replace("/mnt/sda/hy/oracle-nature-data", "data:")
        # Preserve public endpoint paths but never query credentials or userinfo.
        def clean(match):
            url = urlsplit(match.group(0))
            return urlunsplit((url.scheme, url.netloc.split("@")[-1], url.path, "", ""))
        return re.sub(r"https?://[^\s\"<>]+", clean, value)
    return value


def historical_fields(value, prefix=""):
    """Extract cited metadata; these are recorded claims, not fresh RPC checks."""
    result = {}
    if isinstance(value, dict):
        for k, v in value.items():
            field = f"{prefix}.{k}" if prefix else k
            if re.search(r"generated_at|snapshot_time|snapshot_slot|fixed_cutoff|cutoff_|source_commit|source_repository|rpc_host|api_host|source_method", k):
                result[field] = v
            elif isinstance(v, dict):
                result.update(historical_fields(v, field))
    return result


def build(workspace, native_root, output):
    import pyarrow.parquet as pq

    if output.exists():
        raise ValueError("Use a new output directory to preserve prior audit evidence")
    groups = json.loads((ROOT / "configs/provenance_groups.json").read_text())["groups"]
    release = json.loads((ROOT / "configs/data_releases.json").read_text())
    inputs = release["components"]["native"]["files"]
    mapping = {}
    for group in groups:
        for table in group["tables"]:
            if table in mapping:
                raise ValueError(f"Duplicate table binding: {table}")
            mapping[table] = group
    if set(mapping) != {Path(x["path"]).stem for x in inputs}:
        raise ValueError("Provenance bindings must cover exactly the frozen native inputs")
    historical = {r["path"]: r for r in csv.DictReader(
        (workspace / "data/releases/economic_research_v1/checksums.csv").open())}
    older = {}
    for path in (ROOT / "metadata/historical_source_manifests").glob("*.json"):
        doc = json.loads(path.read_text())
        older[doc["original_relative_path"]] = doc["original_sha256"]
    paths = sorted({p for g in groups for p in g["manifests"]} | {
        "data/manifests/curated_parquet.json", "data/manifests/accountability_events.json"})
    manifests = {}
    original_docs = {}
    for relative in paths:
        source = workspace / relative
        doc = json.loads(source.read_text())
        original_docs[relative] = doc
        name = relative.replace("/", "__")
        archived = output / "manifests" / name
        archive_doc = sanitized(doc, workspace)
        write(archived, {"original_relative_path": relative,
                        "original_sha256": digest(source),
                        "sanitization": "Workspace roots normalized; sensitive key values and URL query/userinfo removed. This wrapper is not the original file.",
                        "metadata": archive_doc})
        previous = older.get(relative)
        manifests[relative] = {
            "archive": "manifests/" + name, "archive_sha256": digest(archived),
            "original_sha256": digest(source), "original_bytes": source.stat().st_size,
            "prior_archived_original_sha256": previous,
            "matches_prior_archive": None if previous is None else previous == digest(source),
            "recorded_fields": historical_fields(archive_doc),
            "claim_status": "retained historical record; not recollected or independently attested",
        }
    write(output / "manifest_index.json", manifests)
    conversion = {Path(x["parquet"]).stem: sanitized(x, workspace)
                  for x in original_docs["data/manifests/curated_parquet.json"]["files"]}
    tables = []
    producers = {}
    for group in groups:
        for relative in group["producer_files"]:
            original = workspace / relative
            counterpart = ROOT / "code/reconstruction" / relative
            preserved = ROOT / "code/production" / relative
            if preserved.is_file() and digest(preserved) == digest(original):
                archive_path = str(preserved.relative_to(ROOT))
            else:
                archived_source = output / "historical_producers" / relative
                archived_source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(original, archived_source)
                archive_path = "historical_producers/" + relative
            producers[relative] = {
                "available_source_sha256": digest(original),
                "available_source_archive": archive_path,
                "archive_base": "repository" if archive_path.startswith("code/") else "supplement",
                "current_reconstruction_path": str(counterpart.relative_to(ROOT)) if counterpart.exists() else None,
                "current_reconstruction_sha256": digest(counterpart) if counterpart.exists() else None,
                "historical_executed_commit": None,
                "limit": "Available source is not proof that this exact code ran during original acquisition.",
            }
    write(output / "producer_index.json", producers)
    for item in inputs:
        source = native_root / item["path"]
        name = source.stem
        group = mapping[name]
        actual = {"sha256": digest(source), "bytes": source.stat().st_size,
                  "rows": pq.ParquetFile(source).metadata.num_rows}
        checks = {k: actual[k] == item[k] for k in actual}
        past = historical.get(item["path"])
        tables.append({
            "table": name, "group": group["id"], "input": item,
            "rechecked": actual, "identity_checks": checks,
            "historical_checksum": past,
            "matches_historical_checksum": None if past is None else past["sha256"] == actual["sha256"],
            "historical_manifests": group["manifests"],
            "recorded_conversion": conversion.get(name),
            "available_producers": group["producer_files"],
            "transformation": group["transformation"],
            "historical_collection_operator": None,
            "historical_collector_execution_commit": None,
            "historical_agent_assistance": "unknown",
            "original_acquisition_attestation": "not established",
            "historical_records_are_independent_validation": False,
        })
    write(output / "native_table_provenance.json", tables)
    raw = []
    flare = original_docs["data/manifests/flare_fsp_rewards.json"]
    for relative, expected in sorted(flare["raw_sha256"].items()):
        # Official repository keys use flare/<epoch>; retained local cache omits
        # that one prefix. Preserve both identities and verify the recorded hash.
        local_relative = relative.removeprefix("flare/")
        source = workspace / "data/raw/flare_fsp" / local_relative
        actual = digest(source)
        raw.append({"group": "flare_fsp", "path": "data/raw/flare_fsp/" + local_relative,
                    "historical_manifest_key": relative,
                    "bytes": source.stat().st_size, "expected_sha256": expected,
                    "actual_sha256": actual, "passed": actual == expected,
                    "expected_from": "data/manifests/flare_fsp_rewards.json"})
    for group, manifest, source, field in [
        ("pyth_rolling", "data/manifests/pyth_ois_rolling_state.json",
         ROOT / "data/data_source/pyth_historical/rolling_program_state.json.gz", "raw_snapshot_sha256"),
        ("polygon_flows", "data/manifests/polygon_uma_token_flow_receipts.json",
         workspace / "data/raw/polygon/uma_token_flows/settlement_receipt_fallback.jsonl.gz", "sha256"),
    ]:
        expected = original_docs[manifest][field]
        actual = digest(source)
        raw.append({"group": group, "path": sanitized(str(source), workspace),
                    "bytes": source.stat().st_size, "expected_sha256": expected,
                    "actual_sha256": actual, "passed": actual == expected, "expected_from": manifest})
    write(output / "raw_hash_audit.json", raw)
    # Output lineage is a conservative build-level dependency set, not an invented
    # row-level join graph. Existing revision_provenance records actual activity commits.
    outputs = []
    by_path = {i["path"]: i for i in inputs}
    for item in release["components"]["repaired"]["files"]:
        if not item["path"].endswith(".parquet") or item["path"].startswith("experiments/"):
            continue
        same = by_path.get(item["path"], {}).get("sha256") == item["sha256"]
        outputs.append({"output": item, "lineage_kind": "byte-identical native input" if same else "reconstructed or rewritten output",
                        "native_dependencies": [item["path"]] if same else [i["path"] for i in inputs],
                        "additional_build_inputs": [] if same else [
                            "data/data_source/pyth_historical/rolling_program_state.json.gz",
                            "configs/data_releases.json#components.source_registries",
                            "code/reconstruction/data/dictionaries", "schemas"],
                        "dependency_precision": "exact file copy" if same else "conservative build-level input set; not minimal or row-level ancestry",
                        "execution_provenance": "metadata/repaired_atlas_20261012/revision_provenance.json"})
    write(output / "output_lineage.json", outputs)
    gaps = [
        {"scope": "all 64 native inputs", "field": "historical operator / agent use / executed collector commit",
         "status": "unknown", "needed": "Original job logs, execution commit receipts and collector attestation; DOI authors do not establish collectors."},
        {"scope": "raw acquisition outside the 688 explicitly audited files", "field": "raw file completeness and identities",
         "status": "not exhaustively checked", "needed": "Inventory every raw segment and bind each to historical requests/responses and output rows."},
        {"scope": "derived outputs", "field": "row-level ancestry",
         "status": "build-level lineage only", "needed": "Protocol-specific event/join ancestry for every derived row; preserved identifiers support targeted audits."},
        {"scope": "mutable Gamma and Pyth state", "field": "historical availability",
         "status": "limited by recorded snapshot times", "needed": "Contemporaneous archive evidence for unavailable historical fields; do not substitute later snapshots."},
    ]
    write(output / "remaining_gaps.json", gaps)
    failures = [t["table"] for t in tables if not all(t["identity_checks"].values()) or t["matches_historical_checksum"] is False]
    failures += [r["path"] for r in raw if not r["passed"]]
    failures += [p for p, m in manifests.items() if m["matches_prior_archive"] is False]
    report = {
        "verified_at_utc": datetime.now(timezone.utc).isoformat(), "release": release["release"],
        "native_tables": len(tables), "bound_tables": len(mapping), "groups": len(groups),
        "archived_manifests": len(manifests), "available_producer_files": len(producers),
        "native_bytes_rehashed": sum(t["rechecked"]["bytes"] for t in tables),
        "native_historical_hash_matches": sum(t["matches_historical_checksum"] is True for t in tables),
        "prior_manifest_hash_matches": sum(m["matches_prior_archive"] is True for m in manifests.values()),
        "raw_files_rehashed": len(raw), "raw_bytes_rehashed": sum(r["bytes"] for r in raw),
        "output_tables_bound": len(outputs), "failures": failures, "identity_and_binding_checks_passed": not failures,
        "complete_historical_acquisition_provenance": False,
        "scope": "This audit rechecks stored bytes and explicit document bindings; it does not independently validate past acquisition statements.",
    }
    write(output / "verification.json", report)
    print(json.dumps(report, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.workspace, args.native_root, args.output)

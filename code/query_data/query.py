"""Acquire a real UMA case; default replays checksum-pinned public evidence."""

import argparse, json, os, shutil, sys, time
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (
    ROOT,
    case_module,
    contained,
    load_config,
    require,
    sha256,
    write_json,
)

HF = "https://huggingface.co/datasets/Oracle4CEG/OracleEconLab-Oracle-Incentives-v1/resolve/aabcff2e1492df35f0aaa9abef657133fffe9b81/public_evidence/"


def acquire(config, run_dir, mode="bundled"):
    cfg = load_config(config)
    run_dir = Path(run_dir).resolve()
    out = run_dir / "queried_data/uma_case"
    require(not out.exists(), "Acquisition output exists; choose a fresh run")
    require(mode in {"bundled", "public-download", "live"}, "Unknown acquisition mode")
    out.mkdir(parents=True)
    entries = []
    for item in cfg["sources"]:
        src = contained(ROOT, item["path"])
        dest = contained(out, item["filename"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        require(
            src.is_file() and sha256(src) == item["sha256"],
            "Bundled source checksum mismatch: " + item["source_id"],
        )
        require(
            src.stat().st_size <= item["max_bytes"], "Source exceeds recorded bound"
        )
        origin = item["path"]
        attempts = 0
        if mode == "public-download" and item["filename"].startswith("raw/"):
            origin = HF + Path(item["filename"]).name
            for attempt in range(4):
                attempts = attempt + 1
                try:
                    with requests.get(origin, timeout=30, stream=True) as response:
                        response.raise_for_status()
                        parts = []
                        size = 0
                        for part in response.iter_content(65536):
                            size += len(part)
                            require(
                                size <= item["max_bytes"],
                                "Download exceeds recorded bound",
                            )
                            parts.append(part)
                    dest.write_bytes(b"".join(parts))
                    break
                except requests.RequestException:
                    if attempt == 3:
                        raise RuntimeError(
                            "Public snapshot fetch failed after 4 attempts; use bundled replay"
                        ) from None
                    time.sleep(2**attempt)
        else:
            shutil.copyfile(src, dest)
        require(
            sha256(dest) == item["sha256"],
            "Acquired bytes differ from frozen source: " + item["source_id"],
        )
        entries.append(
            {
                "source_id": item["source_id"],
                "origin": origin,
                "path": str(dest.relative_to(run_dir)),
                "bytes": dest.stat().st_size,
                "sha256": sha256(dest),
                "attempts": attempts,
                "frozen_hash_matches": True,
            }
        )
    if mode == "live":
        module = case_module()
        spec = json.loads((out / "case_spec.json").read_text())
        for name in ["polygon", "ethereum"]:
            contracts = [
                v
                for v in spec["contracts"].values()
                if v["chain"] == name and "runtime_code_hash" in v
            ]
            snapshot = module.fetch_live_chain(
                name,
                spec["chains"][name],
                contracts,
                os.environ.get("PUBLIC_" + name.upper() + "_RPC_URL"),
            )
            module.validate_chain_snapshot(snapshot, spec["chains"][name])
            require(
                all(x["hash_matches"] for x in snapshot["contract_code_evidence"]),
                "Runtime code hash mismatch",
            )
            dest = out / "raw" / f"{name}_rpc_snapshot.json"
            write_json(dest, snapshot)
            for e in entries:
                if e["source_id"] == f"raw/{name}_rpc_snapshot.json":
                    e.update(
                        origin="live public JSON-RPC; provider host "
                        + snapshot["public_provider"],
                        sha256=sha256(dest),
                        bytes=dest.stat().st_size,
                        frozen_hash_matches=False,
                        attempts="bounded retries in imported Rpc.call",
                    )
    spec = json.loads((out / "case_spec.json").read_text())
    counts = {k: len(v["transactions"]) for k, v in spec["chains"].items()}
    report = {
        "data_version": cfg["data_version"],
        "mode": mode,
        "files": entries,
        "source_transactions": sum(counts.values()),
        "transactions_by_chain": counts,
        "fixed_cutoff": cfg["fixed_cutoff"],
        "scope": "one real request; not full protocol histories",
        "failure_policy": "fail closed; no empty response imputed as zero",
        "network_scope": (
            "no network"
            if mode == "bundled"
            else (
                "two pinned HTTPS snapshot downloads"
                if mode == "public-download"
                else "five fixed transactions plus headers/code; envelope bytes vary"
            )
        ),
    }
    write_json(run_dir / "reports/acquisition.json", report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "configs/project.json"))
    p.add_argument("--run-dir", required=True)
    p.add_argument(
        "--mode", choices=["bundled", "public-download", "live"], default="bundled"
    )
    a = p.parse_args()
    print(json.dumps(acquire(a.config, a.run_dir, a.mode), indent=2))

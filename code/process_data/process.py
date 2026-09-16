"""Reconstruct acquired receipts and pinned sources using existing project code."""

import argparse, json, os, subprocess, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (
    ROOT,
    contained,
    load_config,
    read_json,
    require,
    sha256,
    write_csv,
    write_json,
)


def process(config, run_dir):
    cfg = load_config(config)
    run = Path(run_dir).resolve()
    acq = read_json(run / "reports/acquisition.json")
    require(
        acq["data_version"] == cfg["data_version"],
        "Acquisition belongs to another release",
    )
    for f in acq["files"]:
        p = contained(run, f["path"])
        require(
            p.is_file() and sha256(p) == f["sha256"],
            "Acquired source changed: " + f["source_id"],
        )
    inputs = run / "queried_data/uma_case"
    out = run / "reconstruction"
    require(not out.exists(), "Use a new reconstruction directory")
    cmd = [
        sys.executable,
        str(
            ROOT
            / "code/production/scripts/case_studies/reproduce_uma_public_rpc_case.py"
        ),
        "--spec",
        str(inputs / "case_spec.json"),
        "--snapshot-dir",
        str(inputs / "raw"),
        "--source-cache",
        str(inputs / "source"),
        "--offline-sources",
        "--output",
        str(out),
    ]
    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"
    env["MPLCONFIGDIR"] = str(run / "runtime/matplotlib")
    result = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    (run / "reports/reconstruction.stderr.log").write_text(result.stderr)
    require(result.returncode == 0, "Reconstruction failed: " + result.stderr[-6000:])
    (run / "reports/reconstruction.log").write_text(result.stdout)
    ep = read_json(out / "processed/economic_episode.json")
    manifest = read_json(out / "manifest.json")
    require(manifest["all_required_assertions_pass"], "Case builder assertions failed")
    row = {
        k: json.dumps(v, separators=(",", ":")) if isinstance(v, (list, dict)) else v
        for k, v in ep.items()
    }
    write_csv(run / "processed_data/economic_episodes.csv", [row])
    write_json(run / "processed_data/economic_episode.json", ep)
    conversions = {
        "source_events": "validated/polygon_decoded_events.parquet",
        "token_flows": "validated/token_flows.parquet",
        "canonical_chain_qc": "validated/canonical_chain_qc.parquet",
        "economic_link_qc": "validated/economic_link_qc.parquet",
        "variable_provenance": "economic/variable_provenance.parquet",
        "lifecycle_timeline": "statistics/lifecycle_timeline.parquet",
        "economic_cashflows": "statistics/economic_cashflows.parquet",
        "abc_economic_measures": "economic/abc_economic_measures.parquet",
    }
    counts = {"economic_episodes": 1}
    for name, rel in conversions.items():
        frame = pd.read_parquet(out / rel)
        counts[name] = len(frame)
        frame.to_csv(run / "processed_data" / f"{name}.csv", index=False)
    record = {
        "data_version": cfg["data_version"],
        "counts": counts,
        "source_transactions": acq["source_transactions"],
        "operation": "multi-event cross-chain linking -> one request lifecycle; transfers remain child rows",
        "rule_implementation": "code/production/scripts/case_studies/reproduce_uma_public_rpc_case.py",
        "scope": "one preregistered real request; no missing-value imputation",
        "amount_policy": "raw integers + asset + decimals; no cross-token sum",
    }
    write_json(run / "reports/processing.json", record)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "configs/project.json"))
    p.add_argument("--run-dir", required=True)
    a = p.parse_args()
    print(json.dumps(process(a.config, a.run_dir), indent=2))

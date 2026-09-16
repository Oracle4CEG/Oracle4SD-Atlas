"""Validate a declared case scope against raw-derived checks and a frozen reference."""

import argparse, json, sys
from pathlib import Path
from jsonschema import Draft202012Validator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common import (
    ROOT,
    contained,
    load_config,
    read_csv,
    read_json,
    require,
    sha256,
    write_json,
)


def validate(config, run_dir):
    cfg = load_config(config)
    run = Path(run_dir)
    ep = read_json(run / "processed_data/economic_episode.json")
    manifest = read_json(run / "reconstruction/manifest.json")
    summary = read_json(run / "reconstruction/statistics/summary.json")
    reference = read_json(ROOT / "tests/reference/uma_case_summary.json")
    checks = []

    def add(name, ok, unit, den, scope):
        checks.append(
            {
                "check": name,
                "passed": bool(ok),
                "unit": unit,
                "denominator": den,
                "scope": scope,
            }
        )

    errors = list(
        Draft202012Validator(
            read_json(ROOT / "metadata/economic_episode.schema.json")
        ).iter_errors(ep)
    )
    add(
        "episode_schema",
        not errors,
        "episode",
        1,
        "85-field case schema; not full common schema",
    )
    add(
        "frozen_reference_values",
        summary == reference,
        "case",
        1,
        "previous reconstruction values; not independent factual truth",
    )
    add(
        "episode_identity",
        ep["episode_id"].endswith(cfg["case_id"]),
        "episode",
        1,
        "fixed preregistered request",
    )
    add(
        "principal_not_profit",
        int(ep["gross_payout_raw"])
        == int(ep["principal_returned_raw"]) + int(ep["realized_payoff_raw"]),
        "settlement",
        1,
        "integer equality",
    )
    add(
        "asset_precision",
        ep["asset_decimals"] == 6 and ep["asset_symbol"] == "USDC.e",
        "asset",
        1,
        "this case only",
    )
    for name, ok in manifest["assertions"].items():
        add(name, ok, "case assertion", 1, "raw-derived case assertion")
    for name in ["canonical_chain_qc", "economic_link_qc"]:
        rows = read_csv(run / "processed_data" / f"{name}.csv")
        add(
            name,
            bool(rows) and all(r["passed"].lower() == "true" for r in rows),
            "check",
            len(rows),
            "retained receipt/header or economic link",
        )
    for item in read_json(run / "reports/acquisition.json")["files"]:
        add(
            "source_hash:" + item["source_id"],
            sha256(contained(run, item["path"])) == item["sha256"],
            "file",
            1,
            "run input identity",
        )
    add(
        "config_version",
        all(
            read_json(run / "reports" / f"{n}.json")["data_version"]
            == cfg["data_version"]
            for n in ["acquisition", "processing"]
        ),
        "stage",
        2,
        "one sample version",
    )
    report = {
        "data_version": cfg["data_version"],
        "review_bundle": cfg["review_bundle"],
        "scope": cfg["scope"],
        "passed": all(r["passed"] for r in checks),
        "checks": checks,
        "passed_checks": sum(r["passed"] for r in checks),
        "failed_checks": sum(not r["passed"] for r in checks),
        "schema_errors": [e.message for e in errors],
        "not_evaluated": [
            "all-protocol recollection",
            "population representativeness",
            "independent external truth",
            "full-core schema/application issues",
        ],
        "known_core_failures": "reports/core_audit_20260915/known_issues.csv",
    }
    write_json(run / "reports/validation.json", report)
    require(report["passed"], "Validation failed; inspect reports/validation.json")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "configs/project.json"))
    p.add_argument("--run-dir", required=True)
    a = p.parse_args()
    print(json.dumps(validate(a.config, a.run_dir), indent=2))

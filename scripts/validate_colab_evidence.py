"""Validate the pinned tutorial's saved notebook and evidence ZIP, without executing them.

Runtime labels are self-reported. Passing this check is not Google-signed proof
of hosting or independent scientific replication; retain an operator attestation.
"""

import argparse
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
CODE_COMMIT = "d558c4669b1020b2664af2bf852658828a1c1da6"
NOTEBOOK_COMMIT = "7060311b563beb1fc963d59433ae6b968913662a"
DATA_VERSION = "uma-public-rpc-case-v1"
SUCCESS = "SUCCESS: two deterministic case replays; see separate full-release validation for the full dataset."


def source(cell):
    value = cell.get("source", "")
    return "".join(value) if isinstance(value, list) else value


def validate(notebook, evidence, require_hosted=True):
    checks = []

    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})

    template = json.loads((ROOT / "notebooks/Oracle4SD_Atlas_Tutorial.ipynb").read_text())
    saved = json.loads(notebook.read_text())
    cells = [c for c in saved["cells"] if c["cell_type"] == "code"]
    expected = [c for c in template["cells"] if c["cell_type"] == "code"]
    check("all_nine_code_cells_unchanged", len(cells) == 9 and [source(c) for c in cells] == [source(c) for c in expected])
    counts = [c.get("execution_count") for c in cells]
    check("all_cells_executed_in_order", len(counts) == 9 and all(type(n) is int and n > 0 for n in counts)
          and len(set(counts)) == len(counts) and counts == sorted(counts))
    outputs = [o for c in cells for o in c.get("outputs", [])]
    check("no_notebook_error_outputs", not any(o.get("output_type") == "error" for o in outputs))
    text_output = "\n".join("".join(o.get("text", "")) for o in outputs)
    check("final_success_output", SUCCESS in text_output)
    runtime = "unreadable"
    with zipfile.ZipFile(evidence) as archive:
        entries = archive.infolist()
        if len(entries) > 2000 or sum(i.file_size for i in entries) > 200_000_000:
            raise ValueError("Unexpected evidence archive size")
        names = [i.filename for i in entries]
        if len(names) != len(set(names)) or any(
            PurePosixPath(n).is_absolute() or ".." in PurePosixPath(n).parts or "\\" in n for n in names
        ):
            raise ValueError("Duplicate or unsafe archive member")

        def read(name):
            return json.loads(archive.read(name))

        identity = read("identity.json")
        runtime = identity.get("runtime_kind")
        check("pinned_code_and_data", identity.get("code_commit") == CODE_COMMIT and identity.get("data_version") == DATA_VERSION)
        check("runtime_kind", runtime == "hosted_colab" if require_hosted else runtime in ("hosted_colab", "local_jupyter_kernel"))
        environment = read("environment.json")
        check("managed_python_and_successful_bootstrap", environment.get("passed") is True
              and environment.get("scientific", {}).get("python") == "3.12.12"
              and bool(environment.get("commands")) and all(c.get("exit_code") == 0 for c in environment["commands"]))
        for name in ("bootstrap.log", "execution.log", "scientific.freeze.txt", "host.freeze.txt"):
            check("retained:" + name, bool(archive.read(name).strip()))
        tutorial = read("run1/reports/tutorial_identity.json")
        check("identity_consistency", all(tutorial.get(k) == identity.get(k) for k in ("code_commit", "data_version", "runtime_kind"))
              and tutorial.get("cutoff") == "2026-06-30T23:59:59Z")
        cfg = json.loads((ROOT / "configs/project.json").read_text())
        summaries = []
        for run in ("run1", "run2"):
            validation = read(run + "/reports/validation.json")
            detail = validation.get("checks", [])
            check(run + ":28_checks_passed", validation.get("passed") is True
                  and validation.get("passed_checks") == 28 and validation.get("failed_checks") == 0
                  and validation.get("data_version") == DATA_VERSION
                  and len(detail) == 28 and len({c.get("check") for c in detail}) == 28
                  and all(c.get("passed") is True for c in detail))
            for item in cfg["sources"]:
                blob = archive.read(run + "/queried_data/uma_case/" + item["filename"])
                check(run + ":source:" + item["filename"], len(blob) == item["bytes"] and hashlib.sha256(blob).hexdigest() == item["sha256"])
            summary = read(run + "/reconstruction/statistics/summary.json")
            summaries.append(summary)
            check(run + ":case_counts", summary.get("source_transactions") == 5 and summary.get("decoded_polygon_events") == 9
                  and summary.get("usdc_transfer_rows") == 8 and summary.get("all_required_assertions_pass") is True)
            analysis = read(run + "/analysis/summary.json")
            check(run + ":payment_decomposition", analysis.get("data_version") == DATA_VERSION
                  and analysis.get("observations") == 1 and analysis.get("asset") == "USDC.e"
                  and analysis.get("asset_decimals") == 6
                  and (analysis.get("principal_returned_raw"), analysis.get("realized_payoff_raw"), analysis.get("gross_payout_raw"))
                  == ("750000000", "250000000", "1000000000"))
        check("deterministic_summaries", summaries[0] == summaries[1])
        log = archive.read("execution.log").decode()
        check("28_regression_tests_succeeded", re.search(r"Ran 28 tests in [\d.]+s\s+OK(?:\s|$)", log) is not None
              and "FAILED (" not in log)
    return {"passed": all(c["passed"] for c in checks), "checks": checks,
            "runtime_kind_reported": runtime, "hosted_runtime_required": require_hosted,
            "hosting_independently_attested": False,
            "scope": "Pinned small-case tutorial and saved regression evidence; not full Atlas or independent replication."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notebook", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-local", action="store_true", help="Diagnostic only; does not accept a hosted Colab run")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Choose a new output path to preserve the prior receipt")
    try:
        result = validate(args.notebook, args.evidence, not args.allow_local)
    except (KeyError, ValueError, OSError, zipfile.BadZipFile) as exc:
        result = {"passed": False, "error": str(exc), "hosting_independently_attested": False}
    result.update({"verified_at_utc": datetime.now(timezone.utc).isoformat(),
                   "notebook_delivery_commit": NOTEBOOK_COMMIT, "expected_code_commit": CODE_COMMIT,
                   "artifact_sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in (args.notebook, args.evidence) if p.exists()}})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()

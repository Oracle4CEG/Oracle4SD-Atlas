"""Verify a separately obtained full candidate; never infer absent files as empty."""

import argparse
import sys
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from common import read_csv, require, sha256, write_json


def verify(root, output, allow_external_symlinks=False):
    root = Path(root).resolve()
    findings = []
    for record in read_csv(ROOT / "metadata/full_data_inventory.csv"):
        relative = Path(record["path"])
        require(
            not relative.is_absolute() and ".." not in relative.parts,
            "Invalid inventory path",
        )
        p = (root / relative).resolve()
        row = {
            "path": record["path"],
            "expected_sha256": record["sha256"],
            "passed": False,
        }
        if not allow_external_symlinks and not p.is_relative_to(root):
            row["error"] = (
                "symlink leaves root; use an authorized self-contained copy or explicitly allow mounted author data"
            )
        elif not p.is_file():
            row["error"] = "missing; obtain an authorized immutable copy from authors"
        else:
            row["observed_sha256"] = sha256(p)
            row["rows"] = pq.read_metadata(p).num_rows
            row["passed"] = row["observed_sha256"] == record["sha256"] and row[
                "rows"
            ] == int(record["rows"])
        findings.append(row)
    report = {
        "scope": "71 inventoried candidate files; identity/footer checks, not semantic validation",
        "passed": all(x["passed"] for x in findings),
        "allow_external_symlinks": allow_external_symlinks,
        "files": findings,
    }
    write_json(output, report)
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", required=True)
    p.add_argument("--output", required=True)
    p.add_argument(
        "--allow-external-symlinks",
        action="store_true",
        help="For an explicitly authorized mounted author-data layout only",
    )
    a = p.parse_args()
    r = verify(a.root, a.output, a.allow_external_symlinks)
    print("passed:", r["passed"])
    sys.exit(0 if r["passed"] else 1)

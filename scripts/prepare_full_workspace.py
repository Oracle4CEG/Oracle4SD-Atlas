"""Copy historical source into a fresh isolated workspace; never launch collection."""

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from common import fresh_output

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--output", required=True)
    a = p.parse_args()
    out = fresh_output(a.output)
    shutil.copytree(
        ROOT / "code/production",
        out,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ["reports", "data/raw", "data/curated", "data/manifests"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    print(
        "Historical code staged at", out, "; read docs/FULL_DATA.md before collection."
    )

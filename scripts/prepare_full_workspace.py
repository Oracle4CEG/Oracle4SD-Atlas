"""Stage revised or historical source in a fresh isolated workspace."""

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
    p.add_argument("--historical", action="store_true", help="Stage the unchanged September import instead of revised code")
    a = p.parse_args()
    out = fresh_output(a.output)
    shutil.copytree(
        ROOT / ("code/production" if a.historical else "code/reconstruction"),
        out,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for name in ["reports", "data/raw", "data/curated", "data/manifests"]:
        (out / name).mkdir(parents=True, exist_ok=True)
    print(
        "Code staged at", out, "; use scripts/rebuild_atlas.py for offline full-snapshot reproduction."
    )

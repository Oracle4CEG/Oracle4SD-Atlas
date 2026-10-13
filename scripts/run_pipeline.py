"""Query -> process -> describe -> validate one real, version-bound case."""

import argparse, json, platform, subprocess, sys, time, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from common import fresh_output, load_config, read_json, sha256, write_json


def run(config, output=None, mode="bundled"):
    cfg = load_config(config)
    output = fresh_output(output or ROOT / "runs" / ("uma-" + uuid.uuid4().hex[:10]))
    start = time.monotonic()
    for folder, script in [
        ("query_data", "query.py"),
        ("process_data", "process.py"),
        ("analyze_data", "analyze.py"),
        ("technical_validation", "validate.py"),
    ]:
        cmd = [
            sys.executable,
            str(ROOT / "code" / folder / script),
            "--config",
            str(Path(config).resolve()),
            "--run-dir",
            str(output),
        ]
        if folder == "query_data":
            cmd += ["--mode", mode]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        (output / "reports").mkdir(parents=True, exist_ok=True)
        (output / "reports" / f"{folder}.stderr.log").write_text(result.stderr)
        if result.returncode:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            raise RuntimeError(
                f"{folder} failed; see {output}/reports/{folder}.stderr.log"
            )
        (output / "reports" / f"{folder}.log").write_text(result.stdout)
        print(folder, "completed", flush=True)
    git = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    )
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True
    )
    write_json(
        output / "reports/run_environment.json",
        {
            "data_version": cfg["data_version"],
            "review_bundle": cfg["review_bundle"],
            "code_commit": git.stdout.strip() if git.returncode == 0 else None,
            "worktree_dirty": bool(dirty.stdout.strip()),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "config_sha256": sha256(config),
            "mode": mode,
            "scope": cfg["scope"],
            "source_hashes": {
                p.relative_to(ROOT).as_posix(): sha256(p)
                for p in sorted((ROOT / "code").rglob("*.py"))
            },
        },
    )
    print(
        json.dumps(
            {
                "run_dir": str(output),
                "data_version": cfg["data_version"],
                "validation_passed": read_json(output / "reports/validation.json")[
                    "passed"
                ],
            },
            indent=2,
        )
    )
    return output


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--config", default=str(ROOT / "configs/project.json"))
    p.add_argument("--output")
    p.add_argument(
        "--mode", choices=["bundled", "public-download", "live"], default="bundled"
    )
    a = p.parse_args()
    run(a.config, a.output, a.mode)

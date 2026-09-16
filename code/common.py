"""Identity helpers adapted from the mentor's MIT-licensed template."""

from pathlib import Path
import csv, hashlib, importlib.util, json

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def sha256(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def contained(root, relative):
    root = Path(root).resolve()
    rel = Path(relative)
    require(
        not rel.is_absolute() and ".." not in rel.parts and bool(rel.parts),
        "Expected nonempty relative path",
    )
    current = root
    for part in rel.parts:
        current = current / part
        require(not current.is_symlink(), "Symlinks are not release inputs")
    path = current.resolve()
    path.relative_to(root)
    return path


def fresh_output(path):
    path = Path(path).resolve()
    require(
        path != ROOT
        and not ROOT.is_relative_to(path)
        and not path.is_relative_to(ROOT / "data"),
        "Outputs must not replace the repository, its parent, or bundled data",
    )
    if path.exists():
        raise FileExistsError("Choose a new output directory: " + str(path))
    path.mkdir(parents=True)
    return path


def load_config(path):
    cfg = read_json(path)
    require(
        cfg.get("pipeline") == "uma_public_rpc_case_v1",
        "Unsupported pipeline; see configs/project.json",
    )
    require(
        cfg.get("data_version") == "uma-public-rpc-case-v1", "Unexpected data version"
    )
    require(
        cfg.get("fixed_cutoff") == "2026-06-30T23:59:59Z", "Observation cutoff changed"
    )
    require(bool(cfg.get("sources")), "No source inputs")
    names = [r["filename"] for r in cfg["sources"]]
    require(len(names) == len(set(names)), "Duplicate source destination")
    return cfg


def write_csv(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(bool(rows), "Empty table without schema")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def read_csv(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def case_module():
    path = (
        ROOT / "code/production/scripts/case_studies/reproduce_uma_public_rpc_case.py"
    )
    spec = importlib.util.spec_from_file_location("oracle_atlas_case_builder", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

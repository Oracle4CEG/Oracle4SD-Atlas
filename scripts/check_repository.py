"""Check release inputs, imported-code identities and project documentation locally."""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from common import contained, load_config, read_csv, require, sha256


def check():
    cfg = load_config(ROOT / "configs/project.json")
    for item in cfg["sources"]:
        require(
            sha256(contained(ROOT, item["path"])) == item["sha256"],
            "Case source changed: " + item["path"],
        )
    for item in read_csv(ROOT / "metadata/file_manifest.csv"):
        require(
            sha256(contained(ROOT, item["path"])) == item["sha256"],
            "Archived case file changed: " + item["path"],
        )
    for item in read_csv(ROOT / "metadata/production_code_imports.csv"):
        require(
            sha256(contained(ROOT, item["repository_path"])) == item["imported_sha256"],
            "Imported code identity mismatch: " + item["repository_path"],
        )
    schema = json.loads((ROOT / "metadata/economic_episode.schema.json").read_text())
    dictionary = read_csv(ROOT / "metadata/data_dictionary.csv")
    require(
        {x["field_name"] for x in dictionary} == set(schema["properties"]),
        "Dictionary/schema fields differ",
    )
    require(all(x["definition"].strip() for x in dictionary), "Empty definition")
    # Validate authored Markdown file links, excluding historical copied code/audit evidence.
    failures = []
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT)
        if any(x in rel.parts for x in [".git", ".venv", "runs"]) or rel.parts[:2] in [
            ("code", "production"),
            ("reports", "core_audit_20260915"),
        ]:
            continue
        for target in re.findall(r"\]\(([^\s)]+)\)", p.read_text()):
            if ":" in target or target.startswith("#"):
                continue
            dest = target.split("#")[0]
            if dest and not (p.parent / dest).exists():
                failures.append(f"{rel}: {target}")
    require(not failures, "Broken local links: " + "; ".join(failures))
    print(
        json.dumps(
            {
                "source_files": len(cfg["sources"]),
                "case_dictionary_fields": len(dictionary),
                "imported_code_files": len(
                    read_csv(ROOT / "metadata/production_code_imports.csv")
                ),
                "local_links_valid": True,
            }
        )
    )


if __name__ == "__main__":
    check()

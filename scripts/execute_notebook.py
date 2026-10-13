"""Execute the real tutorial in a fresh kernel and retain complete scoped evidence."""

import argparse
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
import nbformat
from nbclient import NotebookClient


def execute(notebook, output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Choose a fresh report directory")
    output.mkdir(parents=True)
    with tempfile.TemporaryDirectory(prefix="oracle-atlas-kernel-") as tmp:
        work = Path(tmp)
        kernel = work / "jupyter/kernels/atlas-fresh"
        kernel.mkdir(parents=True)
        (kernel / "kernel.json").write_text(
            json.dumps(
                {
                    "argv": [
                        sys.executable,
                        "-m",
                        "ipykernel_launcher",
                        "-f",
                        "{connection_file}",
                    ],
                    "display_name": "Atlas fresh isolated kernel",
                    "language": "python",
                }
            )
        )
        os.environ["JUPYTER_PATH"] = str(work / "jupyter")
        book = nbformat.read(notebook, as_version=4)
        start = time.monotonic()
        error = None
        try:
            NotebookClient(
                book,
                timeout=600,
                kernel_name="atlas-fresh",
                resources={"metadata": {"path": str(work)}},
                allow_errors=False,
            ).execute()
        except Exception as exc:
            error = str(exc)
        nbformat.write(book, output / "tutorial.executed.ipynb")
        code_cells = [c for c in book.cells if c.cell_type == "code"]
        report = {
            "data_version": "uma-public-rpc-case-v1",
            "scope": "all eight tutorial sections; one real case; deterministic repeat and negative tests",
            "runtime_kind": "fresh local Jupyter kernel; not hosted Google Colab UI",
            "python": platform.python_version(),
            "kernel_executable": sys.executable,
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "code_cells": len(code_cells),
            "executed_code_cells": sum(
                c.execution_count is not None for c in code_cells
            ),
            "passed": error is None,
            "error": error,
        }
        (output / "notebook_execution.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        (output / "environment.freeze.txt").write_text(
            subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
        )
        print(json.dumps(report, indent=2), flush=True)
        if error:
            raise RuntimeError(error)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--notebook", default="notebooks/Oracle4SD_Atlas_Tutorial.ipynb")
    p.add_argument("--output", required=True)
    a = p.parse_args()
    execute(a.notebook, a.output)

"""Acceptance rejects damaged evidence and never upgrades the retained local run."""

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("colab_evidence", ROOT / "scripts/validate_colab_evidence.py")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)
EVIDENCE = ROOT / "reports/revision_20261012/notebook/case-evidence.zip"
NOTEBOOK = ROOT / "reports/revision_20261012/notebook/tutorial.executed.ipynb"


class ColabEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)

    def changed_archive(self, member, transform):
        destination = self.directory / "evidence.zip"
        with zipfile.ZipFile(EVIDENCE) as original, zipfile.ZipFile(destination, "w") as edited:
            for name in original.namelist():
                content = original.read(name)
                edited.writestr(name, transform(content) if name == member else content)
        return destination

    def test_retained_local_run_passes_diagnostic_only(self):
        result = validator.validate(NOTEBOOK, EVIDENCE, require_hosted=False)
        self.assertTrue(result["passed"])
        self.assertFalse(result["hosting_independently_attested"])

    def test_local_run_cannot_clear_hosted_acceptance(self):
        result = validator.validate(NOTEBOOK, EVIDENCE)
        self.assertFalse(result["passed"])
        self.assertEqual([c["check"] for c in result["checks"] if not c["passed"]], ["runtime_kind"])

    def test_changed_second_run_source_is_rejected(self):
        archive = self.changed_archive("run2/queried_data/uma_case/raw/polygon_rpc_snapshot.json", lambda b: b + b"\n")
        self.assertFalse(validator.validate(NOTEBOOK, archive, False)["passed"])

    def test_changed_payment_is_rejected_even_with_passed_validation(self):
        def alter(blob):
            doc = json.loads(blob)
            doc["principal_returned_raw"] = "1000000000"
            return json.dumps(doc).encode()
        archive = self.changed_archive("run2/analysis/summary.json", alter)
        self.assertFalse(validator.validate(NOTEBOOK, archive, False)["passed"])

    def test_unexecuted_cell_is_rejected(self):
        doc = json.loads(NOTEBOOK.read_text())
        next(c for c in doc["cells"] if c["cell_type"] == "code")["execution_count"] = None
        notebook = self.directory / "partial.ipynb"
        notebook.write_text(json.dumps(doc))
        self.assertFalse(validator.validate(notebook, EVIDENCE, False)["passed"])

    def test_modified_code_is_rejected(self):
        doc = json.loads(NOTEBOOK.read_text())
        next(c for c in doc["cells"] if c["cell_type"] == "code")["source"] = ["print('SUCCESS')"]
        notebook = self.directory / "modified.ipynb"
        notebook.write_text(json.dumps(doc))
        self.assertFalse(validator.validate(notebook, EVIDENCE, False)["passed"])

    def test_archive_path_escape_is_rejected_without_extraction(self):
        archive = self.changed_archive("identity.json", lambda b: b)
        with zipfile.ZipFile(archive, "a") as edited:
            edited.writestr("../outside.json", "{}")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            validator.validate(NOTEBOOK, archive, False)


if __name__ == "__main__":
    unittest.main()

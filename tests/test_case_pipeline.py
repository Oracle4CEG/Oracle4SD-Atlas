"""Real reconstruction and meaningful failures; reference values remain immutable."""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from common import case_module, contained, fresh_output, read_json, write_json


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


class CaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.run_dir = Path(cls.temp.name) / "real-case"
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_pipeline.py"),
                "--output",
                str(cls.run_dir),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cls.builder = case_module()
        cls.spec = read_json(ROOT / "data/data_source/uma_case/case_spec.json")

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_case_values_and_scope(self):
        report = read_json(self.run_dir / "reports/validation.json")
        self.assertTrue(report["passed"])
        self.assertEqual(report["passed_checks"], 28)
        summary = read_json(self.run_dir / "analysis/summary.json")
        self.assertEqual(summary["observations"], 1)
        self.assertEqual(summary["principal_returned_raw"], "750000000")
        self.assertEqual(summary["realized_payoff_raw"], "250000000")
        self.assertEqual(summary["external_truth"], "protocol_resolution_only")

    def test_changed_input_fails_before_processing(self):
        cfg = read_json(ROOT / "configs/project.json")
        cfg["sources"][0]["sha256"] = "0" * 64
        path = Path(self.temp.name) / "bad-config.json"
        write_json(path, cfg)
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            module("query_case", "code/query_data/query.py").acquire(
                path, Path(self.temp.name) / "bad-source"
            )

    def test_wrong_chain_rejected(self):
        snapshot = read_json(
            ROOT / "data/data_source/uma_case/raw/polygon_rpc_snapshot.json"
        )
        snapshot["chain_id"] = 1
        with self.assertRaises(RuntimeError):
            self.builder.validate_chain_snapshot(
                snapshot, self.spec["chains"]["polygon"]
            )

    def test_missing_receipt_rejected(self):
        snapshot = read_json(
            ROOT / "data/data_source/uma_case/raw/polygon_rpc_snapshot.json"
        )
        snapshot["receipts"] = {}
        with self.assertRaisesRegex(RuntimeError, "missing"):
            self.builder.validate_chain_snapshot(
                snapshot, self.spec["chains"]["polygon"]
            )

    def test_removed_event_rejected(self):
        snapshot = read_json(
            ROOT / "data/data_source/uma_case/raw/polygon_rpc_snapshot.json"
        )
        next(iter(snapshot["receipts"].values()))["logs"][0]["removed"] = True
        with self.assertRaises(RuntimeError):
            self.builder.validate_chain_snapshot(
                snapshot, self.spec["chains"]["polygon"]
            )

    def test_integer_payment_mismatch_rejected(self):
        out = Path(self.temp.name) / "bad-amount"
        ep = read_json(self.run_dir / "processed_data/economic_episode.json")
        ep["gross_payout_raw"] = "999999999"
        write_json(out / "processed_data/economic_episode.json", ep)
        with self.assertRaisesRegex(ValueError, "Gross payout"):
            module("analyze_case", "code/analyze_data/analyze.py").analyze(
                ROOT / "configs/project.json", out
            )

    def test_changed_scientific_summary_rejected(self):
        p = self.run_dir / "reconstruction/statistics/summary.json"
        original = p.read_text()
        report_path = self.run_dir / "reports/validation.json"
        report_original = report_path.read_text()
        s = json.loads(original)
        s["unexpected_result"] = True
        write_json(p, s)
        try:
            with self.assertRaisesRegex(ValueError, "Validation failed"):
                module(
                    "validate_case", "code/technical_validation/validate.py"
                ).validate(ROOT / "configs/project.json", self.run_dir)
            self.assertFalse(
                read_json(self.run_dir / "reports/validation.json")["passed"]
            )
        finally:
            p.write_text(original)
            report_path.write_text(report_original)

    def test_no_overwrite_or_path_escape(self):
        with self.assertRaises(FileExistsError):
            fresh_output(self.run_dir)
        with self.assertRaises(ValueError):
            fresh_output(ROOT / "data" / "overwrite")
        with self.assertRaises(ValueError):
            contained(ROOT, "../outside")
        link = Path(self.temp.name) / "linked"
        link.symlink_to(ROOT)
        with self.assertRaises(ValueError):
            contained(Path(self.temp.name), "linked/README.md")

    def test_full_verifier_rejects_external_symlink_by_default(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as outside:
            directory = Path(root) / "data"
            directory.symlink_to(Path(outside), target_is_directory=True)
            result = module(
                "full_verify_symlink", "scripts/verify_full_data.py"
            ).verify(root, Path(root) / "report.json")
            self.assertFalse(result["passed"])
            self.assertIn("symlink leaves root", result["files"][0]["error"])

    def test_missing_full_data_is_failure(self):
        result = module("full_verify", "scripts/verify_full_data.py").verify(
            self.temp.name, Path(self.temp.name) / "full-missing.json"
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["files"]), 71)


if __name__ == "__main__":
    unittest.main()

"""End-to-end: main.run() on the real dataset (if present), writing to a temporary folder."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

import main
from src import data_loader as dl


class TestEndToEnd(unittest.TestCase):
    def test_main_run_on_real_data(self):
        if not dl.RAW_DATA_PATH.exists():
            self.skipTest("raw dataset not present")
        before = hashlib.sha256(dl.RAW_DATA_PATH.read_bytes()).hexdigest()
        with tempfile.TemporaryDirectory() as tmp:
            out = main.run(output_root=Path(tmp), fast=True, skip_tests=True, skip_notebook=True,
                           skip_excel_check=True, verbose=False)
            self.assertTrue((Path(tmp) / "data/processed/cleaned_student_spending.csv").exists())
            for f in ["data_quality_report.md", "project_report.md", "verification_report.md"]:
                self.assertTrue((Path(tmp) / "reports" / f).exists(), f)
            self.assertEqual(len(list((Path(tmp) / "visualizations/generated_charts").glob("*.png"))), 15)
            self.assertTrue((Path(tmp) / "excel/student_spending_analysis.xlsx").exists())
            self.assertEqual(len(out["cleaned"]), 1000)
            self.assertEqual(out["facts"]["raw_unchanged"]["status"], "PASS")
        self.assertEqual(before, hashlib.sha256(dl.RAW_DATA_PATH.read_bytes()).hexdigest())

    def test_missing_file_returns_error_code(self):
        self.assertEqual(main.main(["--data", "definitely_missing.csv", "--skip-tests"]), 1)


if __name__ == "__main__":
    unittest.main()

"""Output tests: cleaned CSV, reports, charts, Excel, SQL files. The pipeline writes to a temp folder."""
import tempfile
import unittest
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import pandas as pd

from src import data_loader as dl
from src import visualizations, excel_export, reports, pipeline, verification
from src.data_cleaning import clean_data
from tests.test_data_validation import make_df


def sample(n=60):
    base = make_df(n)
    # vary values so charts/tests have something to work with
    base["monthly_income"] = 600 + (base.index * 13) % 900
    base["financial_aid"] = (base.index * 17) % 1000
    base["tuition"] = 3000 + (base.index * 37) % 3000
    base["major"] = [["Biology", "Economics", "Psychology"][i % 3] for i in range(n)]
    base["year_in_school"] = [["Freshman", "Sophomore", "Junior", "Senior"][i % 4] for i in range(n)]
    base["gender"] = [["Male", "Female", "Non-binary"][i % 3] for i in range(n)]
    base["preferred_payment_method"] = [["Cash", "Credit/Debit Card", "Mobile Payment App"][(i * 7) % 3] for i in range(n)]
    for j, c in enumerate(dl.EXPENSE_COLUMNS[1:]):
        base[c] = 100 + ((base.index * (j + 3)) % 97)
    base["age"] = 18 + base.index % 8
    return base


class TestOutputs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name)
        cls.df, cls.report = clean_data(sample())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_charts_saved(self):
        charts = visualizations.make_all_charts(self.df, self.out / "charts")
        self.assertEqual(len(charts), 15)
        for info in charts.values():
            self.assertTrue(Path(info["file"]).exists())
            self.assertGreater(Path(info["file"]).stat().st_size, 1000)

    def test_chart_values_match_pandas(self):
        charts = visualizations.make_all_charts(self.df, self.out / "charts2")
        facts = verification.check_chart_data(self.df, charts)
        self.assertEqual(int((facts["status"] == "FAIL").sum()), 0, facts.to_string())

    def test_charts_refuse_empty_data(self):
        with self.assertRaises(ValueError):
            visualizations.make_all_charts(self.df.iloc[0:0], self.out / "x")

    def test_excel_workbook_opens_with_expected_structure(self):
        path = self.out / "t.xlsx"
        info = excel_export.build_workbook(self.df, self.report, path)
        check = verification.check_excel_file(path)
        self.assertEqual(check["status"], "PASS", check)
        self.assertEqual(check["rows"], len(self.df))
        self.assertGreater(len(info["checks"]), 100)

    def test_excel_formulas_recalculate_to_pandas_values(self):
        res = verification.check_excel_recalculation(self.df, self.report)
        if res["status"] == "NOT TESTED":
            self.skipTest(res["detail"])
        self.assertEqual(res["status"], "PASS", res["mismatches"])

    def test_reports_generated(self):
        res = pipeline.run_analysis(self.df, n_perm=100, corr_perm=50)
        res["quality"] = {"missing": 0, "invalid": 0, "dups": 0}
        charts = visualizations.make_all_charts(self.df, self.out / "c3")
        from src import sql_check
        sql_df = sql_check.verify_sql_against_pandas(self.df)
        info = {"file_name": "t.csv", "size_bytes": 1, "sha256": "0" * 64, "delimiter": ",", "encoding": "utf-8",
                "data_lines": len(self.df)}
        dq = reports.write_data_quality_report(self.report, info, self.out / "dq.md")
        pr = reports.write_project_report(self.df, self.report, res, charts, sql_df, {"status": "NOT TESTED"}, info,
                                          self.out / "pr.md")
        for p in (dq, pr):
            self.assertTrue(p.exists())
        text = pr.read_text(encoding="utf-8")
        for n in range(1, 21):
            self.assertIn(f"## {n}. ", text)
        self.assertNotIn("| nan |", text)

    def test_required_files_exist(self):
        for f in ["create_database.sql", "create_tables.sql", "import_data.sql", "analysis_queries.sql"]:
            self.assertTrue((dl.SQL_DIR / f).is_file(), f)
        for f in ["main.py", "requirements.txt", "README.md", ".gitignore", "LICENSE"]:
            self.assertTrue((dl.PROJECT_ROOT / f).is_file(), f)

    def test_output_paths_inside_project(self):
        for p in (dl.PROCESSED_DATA_PATH, dl.CHARTS_DIR, dl.REPORTS_DIR, dl.EXCEL_PATH):
            self.assertTrue(str(p).startswith(str(dl.PROJECT_ROOT)))

    def test_no_machine_specific_paths(self):
        self.assertEqual(verification.check_hardcoded_paths()["hits"], [])


if __name__ == "__main__":
    unittest.main()

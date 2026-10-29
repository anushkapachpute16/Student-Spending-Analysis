"""Loading, validation and cleaning tests. Synthetic rows are used ONLY here, in temporary files."""
import hashlib
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from src import data_cleaning as dc
from src import data_loader as dl

COLS = ["Unnamed: 0", "age", "gender", "year_in_school", "major", "monthly_income", "financial_aid", "tuition",
        "housing", "food", "transportation", "books_supplies", "entertainment", "personal_care", "technology",
        "health_wellness", "miscellaneous", "preferred_payment_method"]


def make_df(n=4) -> pd.DataFrame:
    rows = []
    for i in range(n):
        rows.append([i, 19 + i, ["Male", "Female"][i % 2], ["Freshman", "Senior"][i % 2], ["Biology", "Economics"][i % 2],
                     900 + i, 100 + i, 4000 + i, 600, 250, 120, 150, 80, 60, 170, 110, 100, ["Cash", "Credit/Debit Card"][i % 2]])
    return pd.DataFrame(rows, columns=COLS)


class TempCsv(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, name, text=None, df=None, **kw):
        path = self.dir / name
        if df is not None:
            df.to_csv(path, index=False, **kw)
        else:
            path.write_text(text, encoding="utf-8")
        return path


class TestLoading(TempCsv):
    def test_valid_csv_loads(self):
        df = dl.load_raw_csv(self.write("ok.csv", df=make_df()))
        self.assertEqual(df.shape, (4, 18))

    def test_missing_file_gives_clear_error(self):
        with self.assertRaises(FileNotFoundError) as cm:
            dl.load_raw_csv(self.dir / "nope.csv")
        self.assertIn("Dataset not found", str(cm.exception))

    def test_empty_file(self):
        with self.assertRaises(dl.DataValidationError):
            dl.load_raw_csv(self.write("empty.csv", text=""))

    def test_header_only_file(self):
        with self.assertRaises(dl.DataValidationError):
            dl.load_raw_csv(self.write("h.csv", text=",".join(COLS) + "\n"))

    def test_duplicate_column_names_rejected(self):
        with self.assertRaises(dl.DataValidationError):
            dl.load_raw_csv(self.write("d.csv", text="a,a,b\n1,2,3\n"))

    def test_semicolon_delimiter_detected(self):
        path = self.write("semi.csv", df=make_df(), sep=";")
        self.assertEqual(dl.load_raw_csv(path).shape, (4, 18))

    def test_missing_required_column_detected(self):
        df = make_df().drop(columns=["food"])
        with self.assertRaises(dl.DataValidationError) as cm:
            dl.validate_schema(df)
        self.assertIn("food", str(cm.exception))

    def test_unexpected_column_reported_and_excluded(self):
        df = make_df()
        df["extra"] = 1
        self.assertEqual(dl.validate_schema(df)["unexpected"], ["extra"])
        cleaned, rep = dc.clean_data(df)
        self.assertNotIn("extra", cleaned.columns)
        self.assertIn("extra", [e["column"] for e in rep["columns_excluded"]])

    def test_describe_file_counts_data_lines(self):
        info = dl.describe_file(self.write("ok.csv", df=make_df(5)))
        self.assertEqual(info["data_lines"], 5)

    def test_project_paths_are_relative_to_project(self):
        self.assertEqual(dl.RAW_DATA_PATH.relative_to(dl.PROJECT_ROOT).as_posix(), "data/raw/student_spending.csv")


class TestCleaning(unittest.TestCase):
    def test_original_not_modified(self):
        raw = make_df()
        raw.loc[1, "gender"] = "  Male "
        before = raw.copy(deep=True)
        dc.clean_data(raw)
        pd.testing.assert_frame_equal(raw, before)

    def test_schema_of_cleaned_output(self):
        cleaned, _ = dc.clean_data(make_df())
        self.assertEqual(list(cleaned.columns), dl.CLEAN_COLUMNS)
        self.assertNotIn("Unnamed: 0", cleaned.columns)

    def test_index_column_confirmed(self):
        _, rep = dc.clean_data(make_df())
        self.assertTrue(rep["index_column"]["confirmed_row_index"])

    def test_non_index_column_is_not_called_index(self):
        df = make_df()
        df["Unnamed: 0"] = [5, 3, 9, 1]
        _, rep = dc.clean_data(df)
        self.assertFalse(rep["index_column"]["confirmed_row_index"])

    def test_missing_values_detected_and_rows_removed_without_imputation(self):
        raw = make_df(5)
        raw.loc[2, "food"] = None
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(rep["raw_missing"]["food"]["count"], 1)
        self.assertEqual(rep["rows_removed_missing"], 1)
        self.assertEqual(len(cleaned), 4)
        self.assertNotIn(2, cleaned["record_id"].tolist())

    def test_duplicates_keep_first(self):
        raw = make_df(3)
        raw = pd.concat([raw, raw.iloc[[0]].assign(**{"Unnamed: 0": 3})], ignore_index=True)
        raw["Unnamed: 0"] = range(len(raw))
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(rep["rows_removed_duplicates"], 1)
        self.assertEqual(len(cleaned), 3)
        self.assertEqual(cleaned["record_id"].tolist(), [0, 1, 2])

    def test_invalid_numeric_text_becomes_missing_then_removed(self):
        raw = make_df(4).astype({"tuition": object})
        raw.loc[1, "tuition"] = "abc"
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(rep["numeric_cells_unparseable"], 1)
        self.assertEqual(len(cleaned), 3)

    def test_negative_amount_removed(self):
        raw = make_df(4)
        raw.loc[0, "housing"] = -5
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(rep["rows_removed_invalid"], 1)
        self.assertEqual(len(cleaned), 3)

    def test_zero_age_removed_but_zero_aid_kept(self):
        raw = make_df(4)
        raw.loc[0, "age"] = 0
        raw.loc[1, "financial_aid"] = 0
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(rep["rows_removed_invalid"], 1)
        self.assertIn(0, cleaned["financial_aid"].tolist())

    def test_unexpected_categories_flagged_not_deleted(self):
        raw = make_df(4)
        raw.loc[0, "year_in_school"] = "Graduate"
        raw.loc[1, "gender"] = "male"
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(len(cleaned), 4)
        self.assertEqual(rep["categorical_validation"]["year_in_school"]["unexpected_labels"], ["Graduate"])
        self.assertTrue(rep["categorical_validation"]["gender"]["spelling_variants"])

    def test_implausible_age_flagged_not_deleted(self):
        raw = make_df(4)
        raw.loc[0, "age"] = 99
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(len(cleaned), 4)
        self.assertEqual(rep["numeric_validation"]["age"]["outside_plausible_range"], 1)

    def test_whitespace_trimmed(self):
        raw = make_df(2)
        raw.loc[0, "major"] = "  Biology "
        cleaned, rep = dc.clean_data(raw)
        self.assertEqual(cleaned.loc[0, "major"], "Biology")
        self.assertEqual(rep["text_cells_trimmed"], 1)

    def test_empty_input_rejected(self):
        with self.assertRaises(dl.DataValidationError):
            dc.clean_data(make_df(0))

    def test_rows_reconcile(self):
        raw = make_df(6)
        raw.loc[1, "age"] = None
        raw.loc[2, "food"] = -1
        cleaned, rep = dc.clean_data(raw)
        removed = rep["rows_removed_missing"] + rep["rows_removed_invalid"] + rep["rows_removed_duplicates"]
        self.assertEqual(len(raw) - removed, len(cleaned))

    def test_save_cleaned_refuses_to_overwrite_raw(self):
        with self.assertRaises(dl.DataValidationError):
            dc.save_cleaned(make_df(), dl.RAW_DATA_PATH)

    def test_save_cleaned_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            cleaned, _ = dc.clean_data(make_df())
            out = dc.save_cleaned(cleaned, Path(tmp) / "sub" / "c.csv")
            self.assertTrue(out.exists())
            self.assertEqual(len(pd.read_csv(out)), 4)


class TestRealDataset(unittest.TestCase):
    """Runs only if the dataset is present (it is not committed to GitHub by default)."""

    @classmethod
    def setUpClass(cls):
        if not dl.RAW_DATA_PATH.exists():
            raise unittest.SkipTest("raw dataset not present")
        cls.raw = dl.load_raw_csv()
        cls.cleaned, cls.report = dc.clean_data(cls.raw)

    def test_shape(self):
        self.assertEqual(self.raw.shape, (1000, 18))
        self.assertEqual(self.cleaned.shape, (1000, 18))

    def test_raw_file_hash_unchanged_by_cleaning(self):
        before = hashlib.sha256(dl.RAW_DATA_PATH.read_bytes()).hexdigest()
        dc.clean_data(dl.load_raw_csv())
        self.assertEqual(before, hashlib.sha256(dl.RAW_DATA_PATH.read_bytes()).hexdigest())

    def test_no_rows_lost(self):
        self.assertEqual(self.report["rows_removed_missing"] + self.report["rows_removed_invalid"]
                         + self.report["rows_removed_duplicates"], 0)


if __name__ == "__main__":
    unittest.main()

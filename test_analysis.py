"""Analysis, statistics, DSA, SQL and Excel logic on small hand-checkable fixtures."""
import math
import unittest

import numpy as np
import pandas as pd

from src import analysis as an
from src import dsa_demo, inference, sql_check
from src.data_cleaning import clean_data
from tests.test_data_validation import make_df


def fixture() -> pd.DataFrame:
    df, _ = clean_data(make_df(4))
    return df


class TestDescriptive(unittest.TestCase):
    def test_hand_computed_statistics(self):
        df = pd.DataFrame({"x": [2, 4, 4, 4, 5, 5, 7, 9]})
        s = an.descriptive_stats(df, ["x"]).loc["x"]
        self.assertEqual(s["count"], 8)
        self.assertAlmostEqual(s["mean"], 5.0)
        self.assertAlmostEqual(s["median"], 4.5)
        self.assertEqual(s["mode"], 4)
        self.assertAlmostEqual(s["variance"], 32 / 7)            # sample variance, n-1
        self.assertAlmostEqual(s["std"], math.sqrt(32 / 7))
        self.assertEqual(s["range"], 7)
        self.assertAlmostEqual(s["q1"], 4.0)
        self.assertAlmostEqual(s["q3"], 5.5)
        self.assertAlmostEqual(s["iqr"], 1.5)

    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            an.descriptive_stats(pd.DataFrame({"age": []}), ["age"])
        with self.assertRaises(ValueError):
            an.category_spending_summary(fixture().iloc[0:0])
        with self.assertRaises(ValueError):
            an.financial_consistency_checks(fixture().iloc[0:0])

    def test_frequency_percent_denominator(self):
        s = pd.Series(["a", "a", "b", None], name="k")
        t = an.frequency_table(s)
        self.assertEqual(t.loc["a", "count"], 2)
        self.assertAlmostEqual(t.loc["a", "percent"], 200 / 3)    # 3 non-missing values, not 4
        self.assertAlmostEqual(t["percent"].sum(), 100)

    def test_counts_reconcile_with_cleaned_data(self):
        df = fixture()
        for col in ["gender", "major", "preferred_payment_method"]:
            self.assertEqual(an.frequency_table(df[col])["count"].sum(), len(df))

    def test_year_order(self):
        df = fixture()
        self.assertEqual(list(an.frequency_table(df["year_in_school"], an.YEAR_ORDER).index), ["Freshman", "Senior"])


class TestTotals(unittest.TestCase):
    def test_recorded_totals_use_intended_columns(self):
        df = fixture()
        t = an.recorded_totals(df)
        row = df.iloc[0]
        expected_all = sum(row[c] for c in an.EXPENSE_COLUMNS)
        self.assertEqual(t["total_recorded_all"].iloc[0], expected_all)
        self.assertEqual(t["total_recorded_excl_tuition"].iloc[0], expected_all - row["tuition"])
        self.assertNotIn("monthly_income", an.EXPENSE_COLUMNS)
        self.assertNotIn("financial_aid", an.EXPENSE_COLUMNS)
        self.assertEqual(len(an.EXPENSE_COLUMNS), 10)

    def test_category_shares_sum_to_100(self):
        self.assertAlmostEqual(an.category_spending_summary(fixture())["share_of_recorded_pct"].sum(), 100)

    def test_consistency_checks(self):
        c = an.financial_consistency_checks(fixture())
        self.assertEqual(c["tuition_gt_income_pct"], 100.0)       # fixture: tuition ~4000 > income ~900

    def test_group_means_and_crosstab(self):
        df = fixture()
        g = an.group_means(df, "major", ["tuition"])
        self.assertEqual(g["n"].sum(), len(df))
        counts, pct = an.crosstab_percent(df, "year_in_school", "preferred_payment_method")
        self.assertTrue(np.allclose(pct.sum(axis=1), 100))

    def test_outlier_fences(self):
        df = pd.DataFrame({"v": [1, 2, 3, 4, 5, 100]})
        o = an.iqr_outliers(df, ["v"]).loc["v"]
        self.assertEqual(o["n_above"], 1)
        self.assertEqual(o["n_below"], 0)


class TestInference(unittest.TestCase):
    def test_holm_adjustment(self):
        adj = inference.holm_adjust([0.01, 0.04, 0.03])
        self.assertTrue(np.allclose(adj, [0.03, 0.06, 0.06]))

    def test_anova_detects_obvious_difference(self):
        df = pd.DataFrame({"y": [1, 2, 3, 11, 12, 13] * 10, "g": ["a", "a", "a", "b", "b", "b"] * 10})
        r = inference.permutation_anova(df, "y", "g", n_perm=500)
        self.assertLess(r["p_value"], 0.01)
        self.assertGreater(r["effect_size"], 0.8)

    def test_anova_no_difference(self):
        rng = np.random.default_rng(1)
        df = pd.DataFrame({"y": rng.normal(size=300), "g": rng.choice(list("abc"), 300)})
        self.assertGreater(inference.permutation_anova(df, "y", "g", n_perm=500)["p_value"], 0.05)

    def test_chi_square_detects_association(self):
        df = pd.DataFrame({"a": ["x"] * 50 + ["y"] * 50, "b": ["u"] * 50 + ["v"] * 50})
        r = inference.permutation_chi_square(df, "a", "b", n_perm=300)
        self.assertLess(r["p_value"], 0.01)
        self.assertAlmostEqual(r["effect_size"], 1.0)

    def test_reproducible_with_seed(self):
        df = pd.DataFrame({"y": np.arange(60.0), "g": list("abc") * 20})
        a = inference.permutation_anova(df, "y", "g", n_perm=200, seed=7)
        b = inference.permutation_anova(df, "y", "g", n_perm=200, seed=7)
        self.assertEqual(a["p_value"], b["p_value"])

    def test_bootstrap_ci_contains_mean(self):
        v = np.arange(100.0)
        lo, hi = inference.bootstrap_ci_mean(v, n_boot=500)
        self.assertLess(lo, v.mean())
        self.assertGreater(hi, v.mean())

    def test_single_group_rejected(self):
        with self.assertRaises(ValueError):
            inference.permutation_anova(pd.DataFrame({"y": [1, 2], "g": ["a", "a"]}), "y", "g", n_perm=10)


class TestDsa(unittest.TestCase):
    def test_count_frequencies(self):
        self.assertEqual(dsa_demo.count_frequencies(list("abca")), {"a": 2, "b": 1, "c": 1})

    def test_min_max(self):
        self.assertEqual(dsa_demo.find_min_max([3, 1, 9, 4]), (1, 9))
        self.assertEqual(dsa_demo.find_min_max([5]), (5, 5))
        with self.assertRaises(ValueError):
            dsa_demo.find_min_max([])

    def test_searches(self):
        self.assertEqual(dsa_demo.linear_search(["a", "b"], "b"), 1)
        self.assertEqual(dsa_demo.linear_search(["a"], "z"), -1)
        self.assertEqual(dsa_demo.binary_search([1, 3, 5, 7], 5), 2)
        self.assertEqual(dsa_demo.binary_search([1, 3, 5, 7], 4), -1)

    def test_insertion_sort_and_input_untouched(self):
        data = [("a", 3), ("b", 1), ("c", 2)]
        self.assertEqual(dsa_demo.insertion_sort(data), [("b", 1), ("c", 2), ("a", 3)])
        self.assertEqual(dsa_demo.insertion_sort(data, descending=True)[0], ("a", 3))
        self.assertEqual(data[0], ("a", 3))

    def test_demo_agrees_with_pandas(self):
        r = dsa_demo.run_demo(fixture())
        self.assertTrue(r["frequencies_match_pandas"] and r["sort_matches_pandas"] and r["min_max_match_pandas"])


class TestSqlLogic(unittest.TestCase):
    def test_all_queries_parse_and_match_pandas(self):
        from tests.test_outputs import sample
        df, _ = clean_data(sample(90))   # 3 majors x 30 rows, so the HAVING >= 30 query returns rows
        res = sql_check.verify_sql_against_pandas(df)
        self.assertEqual(len(res), 15)
        self.assertTrue((res["status"] == "PASS").all(), res[res["status"] != "PASS"].to_string())

    def test_comparison_detects_difference(self):
        a = pd.DataFrame({"x": [1, 2]})
        b = pd.DataFrame({"x": [1, 3]})
        self.assertFalse(sql_check.compare_frames(a, b)[0])


if __name__ == "__main__":
    unittest.main()

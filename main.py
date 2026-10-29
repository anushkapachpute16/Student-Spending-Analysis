"""Run the complete Student Spending Analysis workflow.

    python main.py                 # everything
    python main.py --data PATH     # use a CSV stored elsewhere
    python main.py --fast          # fewer permutations (quick smoke run; do not use for the final report)
    python main.py --skip-tests --skip-notebook --skip-excel-check   # skip slow verification steps

Steps: load raw CSV -> validate and clean -> save cleaned CSV -> analyse -> charts -> Excel ->
SQL check -> reports -> unit tests -> notebook -> verification report.
The raw file is never modified.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import pandas as pd  # noqa: E402

from src import data_loader as dl  # noqa: E402
from src import data_cleaning as dc  # noqa: E402
from src import excel_export, pipeline, reports, sql_check, verification, visualizations  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(data_path: Path | str | None = None, output_root: Path | str | None = None, fast: bool = False,
        skip_tests: bool = False, skip_notebook: bool = False, skip_excel_check: bool = False,
        verbose: bool = True) -> dict:
    """Run the workflow. output_root lets tests write somewhere else than the repository."""
    log = print if verbose else (lambda *a, **k: None)
    root = Path(output_root) if output_root else dl.PROJECT_ROOT
    data_path = Path(data_path) if data_path else dl.RAW_DATA_PATH
    cleaned_path = root / "data" / "processed" / "cleaned_student_spending.csv"
    charts_dir = root / "visualizations" / "generated_charts"
    reports_dir = root / "reports"
    excel_path = root / "excel" / "student_spending_analysis.xlsx"

    log(f"[1/9] Loading {data_path}")
    hash_before = sha256(data_path) if data_path.exists() else None
    file_info = dl.describe_file(data_path)
    raw = dl.load_raw_csv(data_path)
    log(f"      {len(raw):,} rows x {raw.shape[1]} columns")

    log("[2/9] Validating and cleaning")
    cleaned, report = dc.clean_data(raw)
    dc.save_cleaned(cleaned, cleaned_path)
    log(f"      cleaned: {len(cleaned):,} rows x {cleaned.shape[1]} columns -> {cleaned_path}")

    log("[3/9] Analysing (descriptive + permutation tests; takes several seconds)")
    n_perm, corr_perm = (500, 300) if fast else (10_000, 5_000)
    res = pipeline.run_analysis(cleaned, n_perm=n_perm, corr_perm=corr_perm)
    removed = report["rows_removed_missing"] + report["rows_removed_invalid"] + report["rows_removed_duplicates"]
    res["quality"] = {"missing": report["rows_removed_missing"], "invalid": report["rows_removed_invalid"],
                      "dups": report["rows_removed_duplicates"]}

    log("[4/9] Drawing charts")
    charts = visualizations.make_all_charts(cleaned, charts_dir)
    log(f"      {len(charts)} charts -> {charts_dir}")

    log("[5/9] Building Excel workbook")
    excel_export.build_workbook(cleaned, report, excel_path)

    log("[6/9] Running SQL queries (SQLite) and comparing with pandas")
    sql_df = sql_check.verify_sql_against_pandas(cleaned)
    log(f"      {int((sql_df['status'] == 'PASS').sum())}/{len(sql_df)} queries match pandas")

    log("[7/9] Verifying Excel formulas by independent recalculation")
    if skip_excel_check:
        excel_recalc = {"status": "NOT TESTED", "detail": "skipped (--skip-excel-check)", "n_checked": 0, "mismatches": []}
    else:
        excel_recalc = verification.check_excel_recalculation(cleaned, report)
    log(f"      {excel_recalc['status']}: {excel_recalc['detail']}")

    log("[8/9] Writing reports")
    reports.write_data_quality_report(report, file_info, reports_dir / "data_quality_report.md")
    reports.write_project_report(cleaned, report, res, charts, sql_df, excel_recalc, file_info,
                                 reports_dir / "project_report.md")
    if output_root is None:
        reports.update_readme_findings(root / "README.md", reports.key_findings(cleaned, res))

    log("[9/9] Verification")
    reread = pd.read_csv(cleaned_path)
    same_csv = (list(reread.columns) == list(cleaned.columns) and len(reread) == len(cleaned) and
                all((reread[c].astype(str).to_numpy() == cleaned[c].astype(str).to_numpy()).all() for c in cleaned.columns))
    hash_after = sha256(data_path)
    sql_dir = dl.SQL_DIR
    needed = ["create_database.sql", "create_tables.sql", "import_data.sql", "analysis_queries.sql"]
    missing_sql = [f for f in needed if not (sql_dir / f).exists()]
    dsa = res["dsa"]
    dsa_ok = all([dsa["frequencies_match_pandas"], dsa["min_max_match_pandas"], dsa["sort_matches_builtin"],
                  dsa["sort_matches_pandas"], dsa["linear_search_matches_pandas"], dsa["binary_search_found"]])
    if skip_tests:
        unit = {"status": "NOT TESTED", "n_tests": 0, "seconds": 0.0, "failures": [], "tail": "skipped"}
    else:
        unit = verification.run_unit_tests()
    notebook = {"status": "NOT TESTED", "detail": "skipped (--skip-notebook)"}
    if not skip_notebook and output_root is None:
        from src import notebook_builder
        notebook = notebook_builder.build_and_execute()
    facts = {
        "ingest": {"status": "PASS" if file_info["data_lines"] == len(raw) else "FAIL",
                   "detail": f"{file_info['data_lines']:,} data lines in file, {len(raw):,} rows imported, {raw.shape[1]} columns"},
        "raw_unchanged": {"status": "PASS" if hash_before == hash_after else "FAIL",
                          "detail": f"SHA-256 {hash_after[:16]}... before and after"},
        "reconcile": {"status": "PASS" if len(raw) - removed == len(cleaned) else "FAIL",
                      "detail": f"{len(raw):,} - {removed} = {len(cleaned):,}"},
        "cleaned_csv": {"status": "PASS" if same_csv else "FAIL", "detail": f"{len(reread):,} rows re-read"},
        "unit_tests": unit, "sql": sql_df,
        "sql_files": {"status": "PASS" if not missing_sql else "FAIL",
                      "detail": "all 4 SQL files present" if not missing_sql else f"missing {missing_sql}"},
        "excel_recalc": excel_recalc,
        "excel_file": verification.check_excel_file(excel_path),
        "charts": verification.check_chart_data(cleaned, charts),
        "cross": verification.check_python_vs_excel_vs_sql(cleaned),
        "dsa": dsa_ok, "paths": verification.check_hardcoded_paths(),
        "notebook": notebook,
        "fixed_during_build": FIXED_DURING_BUILD,
    }
    verification.write_verification_report(reports_dir / "verification_report.md", facts)
    log(f"Done. Unit tests: {unit['status']} ({unit['n_tests']}). Reports in {reports_dir}")
    return {"cleaned": cleaned, "report": report, "results": res, "facts": facts}


# Issues found and fixed while building (kept here so the verification report is honest about them).
FIXED_DURING_BUILD = [
    "Excel recalculation: LibreOffice kept XlsxWriter's stored zero results instead of recalculating, so the first comparison "
    "reported 303 of 306 mismatches. Fixed by recalculating a copy with no cached results under a forced-recalculation profile; "
    "after that all 306 formula cells matched.",
    "Unit test failure (test_all_queries_parse_and_match_pandas): the pandas reference for SQL query Q10 assumed all three payment "
    "methods exist and raised KeyError on a fixture with two. Fixed by reindexing to the three methods with zero fill (and a richer fixture).",
    "Matplotlib 3.11 deprecation of boxplot(vert=False): replaced by a helper that uses orientation='horizontal' and falls back for older versions.",
    "Correlation heatmap: the 1.00 diagonal dominated the colour scale. Redrawn as the lower triangle without the diagonal.",
]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", help="path to the raw CSV (default: data/raw/student_spending.csv)")
    ap.add_argument("--fast", action="store_true", help="fewer permutations (smoke test only)")
    ap.add_argument("--skip-tests", action="store_true")
    ap.add_argument("--skip-notebook", action="store_true")
    ap.add_argument("--skip-excel-check", action="store_true")
    args = ap.parse_args(argv)
    try:
        run(args.data, fast=args.fast, skip_tests=args.skip_tests, skip_notebook=args.skip_notebook,
            skip_excel_check=args.skip_excel_check)
    except (FileNotFoundError, dl.DataValidationError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

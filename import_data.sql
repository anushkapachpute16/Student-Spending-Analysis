-- =====================================================================
-- Step 3 of 4: import data/processed/cleaned_student_spending.csv
-- (created by `python main.py`)
--
-- OPTION A - MySQL Workbench wizard (no SQL needed)
--   1. In the Navigator, expand student_spending_db > Tables.
--   2. Right-click student_spending > "Table Data Import Wizard".
--   3. Choose data/processed/cleaned_student_spending.csv, "Use existing table",
--      keep the column mapping (names match), then Next > Finish.
--
-- OPTION B - LOAD DATA (edit the path first; use forward slashes on Windows)
--   MySQL 8 disables LOCAL INFILE by default. Enable it on the server with
--       SET GLOBAL local_infile = 1;
--   and in Workbench add  OPT_LOCAL_INFILE=1  under
--   Connection > Advanced > "Others", then reconnect.
-- =====================================================================
USE student_spending_db;

LOAD DATA LOCAL INFILE 'C:/path/to/student-spending-analysis/data/processed/cleaned_student_spending.csv'
INTO TABLE student_spending
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'          -- use '\r\n' if the file was saved with Windows line endings
IGNORE 1 LINES
(record_id, age, gender, year_in_school, major, monthly_income, financial_aid, tuition, housing,
 food, transportation, books_supplies, entertainment, personal_care, technology, health_wellness,
 miscellaneous, preferred_payment_method);

-- Sanity check: this must equal the "Final rows" figure in reports/data_quality_report.md
SELECT COUNT(*) AS rows_loaded FROM student_spending;

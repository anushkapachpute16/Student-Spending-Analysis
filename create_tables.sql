-- =====================================================================
-- Step 2 of 4: create the table
--
-- The data is ONE flat table (one row per student record), so one table is used.
-- No second table is invented just to demonstrate joins.
--
-- record_id : 0-based row position in the raw CSV (the saved "Unnamed: 0" index).
--             It identifies a ROW, it is not a student characteristic.
-- Amount columns are INT because every value in the source file is a whole number.
-- Switch them to DECIMAL(10,2) if your data ever contains fractions.
-- The dataset does not document the currency or the time period of any amount.
-- CHECK constraints are enforced by MySQL 8.0.16+ (parsed but ignored by older versions).
-- =====================================================================
USE student_spending_db;

DROP TABLE IF EXISTS student_spending;

CREATE TABLE student_spending (
    record_id                 INT          NOT NULL,
    age                       TINYINT UNSIGNED NOT NULL,
    gender                    VARCHAR(20)  NOT NULL,
    year_in_school            VARCHAR(20)  NOT NULL,
    major                     VARCHAR(50)  NOT NULL,
    monthly_income            INT          NOT NULL,
    financial_aid             INT          NOT NULL,
    tuition                   INT          NOT NULL,
    housing                   INT          NOT NULL,
    food                      INT          NOT NULL,
    transportation            INT          NOT NULL,
    books_supplies            INT          NOT NULL,
    entertainment             INT          NOT NULL,
    personal_care             INT          NOT NULL,
    technology                INT          NOT NULL,
    health_wellness           INT          NOT NULL,
    miscellaneous             INT          NOT NULL,
    preferred_payment_method  VARCHAR(30)  NOT NULL,
    PRIMARY KEY (record_id),
    CONSTRAINT chk_age_positive CHECK (age > 0),
    CONSTRAINT chk_amounts_non_negative CHECK (
        monthly_income >= 0 AND financial_aid >= 0 AND tuition >= 0 AND housing >= 0 AND
        food >= 0 AND transportation >= 0 AND books_supplies >= 0 AND entertainment >= 0 AND
        personal_care >= 0 AND technology >= 0 AND health_wellness >= 0 AND miscellaneous >= 0)
);

-- Helpful indexes for the GROUP BY columns used in analysis_queries.sql
CREATE INDEX idx_major  ON student_spending (major);
CREATE INDEX idx_year   ON student_spending (year_in_school);
CREATE INDEX idx_payment ON student_spending (preferred_payment_method);

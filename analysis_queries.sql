-- =====================================================================
-- Step 4 of 4: analysis queries
--
-- Written in portable standard SQL (aggregates, GROUP BY / HAVING, CASE, subqueries,
-- window functions). Window functions need MySQL 8.0+ / MariaDB 10.2+.
-- Each query starts with a "-- @query Qnn" marker so src/sql_check.py can run it and
-- compare the output with the equivalent pandas calculation.
--
-- Amounts have no documented currency or period, so no query here calls anything
-- "monthly spending" or "savings".
-- =====================================================================
USE student_spending_db;

-- @query Q01 | Total number of student records
SELECT COUNT(*) AS n_students
FROM student_spending;

-- @query Q02 | Preferred payment method: count and percentage
SELECT preferred_payment_method,
       COUNT(*) AS n_students,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM student_spending), 2) AS pct
FROM student_spending
GROUP BY preferred_payment_method
ORDER BY n_students DESC, preferred_payment_method;

-- @query Q03 | Gender distribution: count and percentage
SELECT gender,
       COUNT(*) AS n_students,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM student_spending), 2) AS pct
FROM student_spending
GROUP BY gender
ORDER BY n_students DESC, gender;

-- @query Q04 | Average income and financial aid by year in school
SELECT year_in_school,
       COUNT(*) AS n_students,
       ROUND(AVG(monthly_income), 2) AS avg_monthly_income,
       ROUND(AVG(financial_aid), 2)  AS avg_financial_aid
FROM student_spending
GROUP BY year_in_school
ORDER BY CASE year_in_school
             WHEN 'Freshman' THEN 1 WHEN 'Sophomore' THEN 2
             WHEN 'Junior' THEN 3 WHEN 'Senior' THEN 4 ELSE 5 END;

-- @query Q05 | Majors with at least 30 students: average income, aid and tuition (HAVING)
SELECT major,
       COUNT(*) AS n_students,
       ROUND(AVG(monthly_income), 2) AS avg_monthly_income,
       ROUND(AVG(financial_aid), 2)  AS avg_financial_aid,
       ROUND(AVG(tuition), 2)        AS avg_tuition
FROM student_spending
GROUP BY major
HAVING COUNT(*) >= 30
ORDER BY avg_monthly_income DESC, major;

-- @query Q06 | Per-category statistics (AVG, MIN, MAX, SUM of recorded values)
SELECT category, avg_value, min_value, max_value, total_value
FROM (
    SELECT 'tuition' AS category, ROUND(AVG(tuition), 2) AS avg_value, MIN(tuition) AS min_value, MAX(tuition) AS max_value, SUM(tuition) AS total_value FROM student_spending
    UNION ALL SELECT 'housing', ROUND(AVG(housing), 2), MIN(housing), MAX(housing), SUM(housing) FROM student_spending
    UNION ALL SELECT 'food', ROUND(AVG(food), 2), MIN(food), MAX(food), SUM(food) FROM student_spending
    UNION ALL SELECT 'transportation', ROUND(AVG(transportation), 2), MIN(transportation), MAX(transportation), SUM(transportation) FROM student_spending
    UNION ALL SELECT 'books_supplies', ROUND(AVG(books_supplies), 2), MIN(books_supplies), MAX(books_supplies), SUM(books_supplies) FROM student_spending
    UNION ALL SELECT 'entertainment', ROUND(AVG(entertainment), 2), MIN(entertainment), MAX(entertainment), SUM(entertainment) FROM student_spending
    UNION ALL SELECT 'personal_care', ROUND(AVG(personal_care), 2), MIN(personal_care), MAX(personal_care), SUM(personal_care) FROM student_spending
    UNION ALL SELECT 'technology', ROUND(AVG(technology), 2), MIN(technology), MAX(technology), SUM(technology) FROM student_spending
    UNION ALL SELECT 'health_wellness', ROUND(AVG(health_wellness), 2), MIN(health_wellness), MAX(health_wellness), SUM(health_wellness) FROM student_spending
    UNION ALL SELECT 'miscellaneous', ROUND(AVG(miscellaneous), 2), MIN(miscellaneous), MAX(miscellaneous), SUM(miscellaneous) FROM student_spending
) AS category_stats
ORDER BY avg_value DESC, category;

-- @query Q07 | Median monthly income (window functions; averages the two middle rows when n is even)
SELECT AVG(monthly_income) AS median_monthly_income
FROM (
    SELECT monthly_income,
           ROW_NUMBER() OVER (ORDER BY monthly_income) AS rn,
           COUNT(*) OVER () AS cnt
    FROM student_spending
) AS ranked
WHERE rn >= cnt / 2.0 AND rn <= cnt / 2.0 + 1;

-- @query Q08 | Students whose financial aid is above the overall average (subquery)
SELECT COUNT(*) AS n_above_average_aid
FROM student_spending
WHERE financial_aid > (SELECT AVG(financial_aid) FROM student_spending);

-- @query Q09 | Majors whose average income is above the overall average (HAVING + subquery)
SELECT major, ROUND(AVG(monthly_income), 2) AS avg_monthly_income
FROM student_spending
GROUP BY major
HAVING AVG(monthly_income) > (SELECT AVG(monthly_income) FROM student_spending)
ORDER BY avg_monthly_income DESC, major;

-- @query Q10 | Payment method by year in school (conditional counts with CASE)
SELECT year_in_school,
       SUM(CASE WHEN preferred_payment_method = 'Cash' THEN 1 ELSE 0 END)               AS cash_n,
       SUM(CASE WHEN preferred_payment_method = 'Credit/Debit Card' THEN 1 ELSE 0 END)  AS card_n,
       SUM(CASE WHEN preferred_payment_method = 'Mobile Payment App' THEN 1 ELSE 0 END) AS mobile_n
FROM student_spending
GROUP BY year_in_school
ORDER BY CASE year_in_school
             WHEN 'Freshman' THEN 1 WHEN 'Sophomore' THEN 2
             WHEN 'Junior' THEN 3 WHEN 'Senior' THEN 4 ELSE 5 END;

-- @query Q11 | The ten highest tuition values (ties broken by record_id)
SELECT record_id, major, year_in_school, tuition
FROM student_spending
ORDER BY tuition DESC, record_id ASC
LIMIT 10;

-- @query Q12 | Students recorded with zero financial aid (filtering)
SELECT COUNT(*) AS n_zero_aid
FROM student_spending
WHERE financial_aid = 0;

-- @query Q13 | Consistency check (NOT a savings calculation): students whose nine non-tuition values sum to more than monthly_income
SELECT COUNT(*) AS n_nontuition_sum_exceeds_income,
       ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM student_spending), 2) AS pct
FROM student_spending
WHERE (housing + food + transportation + books_supplies + entertainment
       + personal_care + technology + health_wellness + miscellaneous) > monthly_income;

-- @query Q14 | Income bands: number of students and average financial aid
SELECT CASE WHEN monthly_income < 750  THEN '1: under 750'
            WHEN monthly_income < 1250 THEN '2: 750 to 1249'
            ELSE '3: 1250 and above' END AS income_band,
       COUNT(*) AS n_students,
       ROUND(AVG(financial_aid), 2) AS avg_financial_aid
FROM student_spending
GROUP BY CASE WHEN monthly_income < 750  THEN '1: under 750'
              WHEN monthly_income < 1250 THEN '2: 750 to 1249'
              ELSE '3: 1250 and above' END
ORDER BY income_band;

-- @query Q15 | Students per age
SELECT age, COUNT(*) AS n_students
FROM student_spending
GROUP BY age
ORDER BY age;

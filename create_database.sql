-- =====================================================================
-- Student Spending Analysis - step 1 of 4: create the database
-- Target: MySQL 8.0+ (MySQL Workbench / XAMPP-MariaDB 10.2+ should also work)
-- Run order: create_database.sql -> create_tables.sql -> import_data.sql -> analysis_queries.sql
-- =====================================================================
CREATE DATABASE IF NOT EXISTS student_spending_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE student_spending_db;

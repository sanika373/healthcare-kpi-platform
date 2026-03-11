-- ============================================================
--  Healthcare KPI Intelligence Platform
--  Star Schema DDL  |  Snowflake
-- ============================================================

-- Raw landing schema
CREATE SCHEMA IF NOT EXISTS RAW;
CREATE SCHEMA IF NOT EXISTS ANALYTICS;

-- ── RAW LAYER ─────────────────────────────────────────────────

CREATE OR REPLACE TABLE RAW.hospital_quality (
    provider_id         VARCHAR(10),
    hospital_name       VARCHAR(200),
    address             VARCHAR(200),
    city                VARCHAR(100),
    state               VARCHAR(2),
    zip_code            VARCHAR(10),
    county_name         VARCHAR(100),
    phone_number        VARCHAR(20),
    hospital_type       VARCHAR(100),
    hospital_ownership  VARCHAR(100),
    measure_id          VARCHAR(50),
    measure_name        VARCHAR(300),
    score               FLOAT,
    sample              INT,
    footnote            VARCHAR(500),
    start_date          DATE,
    end_date            DATE,
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- ── DIMENSION TABLES ──────────────────────────────────────────

CREATE OR REPLACE TABLE ANALYTICS.dim_hospital (
    hospital_key        INT AUTOINCREMENT PRIMARY KEY,
    provider_id         VARCHAR(10) NOT NULL UNIQUE,
    hospital_name       VARCHAR(200),
    address             VARCHAR(200),
    city                VARCHAR(100),
    state               VARCHAR(2),
    zip_code            VARCHAR(10),
    county_name         VARCHAR(100),
    region              VARCHAR(50),   -- derived: Northeast / South / Midwest / West
    hospital_type       VARCHAR(100),
    hospital_ownership  VARCHAR(100),
    is_active           BOOLEAN DEFAULT TRUE,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE ANALYTICS.dim_diagnosis (
    diagnosis_key       INT AUTOINCREMENT PRIMARY KEY,
    measure_id          VARCHAR(50) NOT NULL UNIQUE,
    measure_name        VARCHAR(300),
    category            VARCHAR(100),  -- e.g. Readmission, Infection, Mortality
    sub_category        VARCHAR(100),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE TABLE ANALYTICS.dim_date (
    date_key            INT PRIMARY KEY,     -- YYYYMMDD format
    full_date           DATE NOT NULL UNIQUE,
    year                INT,
    quarter             INT,
    month               INT,
    month_name          VARCHAR(20),
    week                INT,
    day_of_week         INT,
    day_name            VARCHAR(20),
    is_weekend          BOOLEAN,
    fiscal_year         INT,
    fiscal_quarter      INT
);

-- Populate dim_date for 2018–2026
INSERT INTO ANALYTICS.dim_date
SELECT
    TO_NUMBER(TO_CHAR(d.dt, 'YYYYMMDD'))        AS date_key,
    d.dt                                         AS full_date,
    YEAR(d.dt)                                   AS year,
    QUARTER(d.dt)                                AS quarter,
    MONTH(d.dt)                                  AS month,
    TO_CHAR(d.dt, 'MMMM')                        AS month_name,
    WEEKOFYEAR(d.dt)                             AS week,
    DAYOFWEEK(d.dt)                              AS day_of_week,
    TO_CHAR(d.dt, 'DY')                          AS day_name,
    DAYOFWEEK(d.dt) IN (1, 7)                    AS is_weekend,
    CASE WHEN MONTH(d.dt) >= 10
         THEN YEAR(d.dt) + 1 ELSE YEAR(d.dt) END AS fiscal_year,
    CASE
        WHEN MONTH(d.dt) IN (10,11,12) THEN 1
        WHEN MONTH(d.dt) IN (1,2,3)    THEN 2
        WHEN MONTH(d.dt) IN (4,5,6)    THEN 3
        ELSE 4
    END                                          AS fiscal_quarter
FROM (
    SELECT DATEADD(DAY, SEQ4(), '2018-01-01') AS dt
    FROM TABLE(GENERATOR(ROWCOUNT => 3000))
) d
WHERE d.dt <= '2026-12-31';

-- ── FACT TABLE ────────────────────────────────────────────────

CREATE OR REPLACE TABLE ANALYTICS.fact_encounters (
    encounter_key       INT AUTOINCREMENT PRIMARY KEY,
    hospital_key        INT REFERENCES ANALYTICS.dim_hospital(hospital_key),
    diagnosis_key       INT REFERENCES ANALYTICS.dim_diagnosis(diagnosis_key),
    date_key            INT REFERENCES ANALYTICS.dim_date(date_key),

    -- Measures
    score               FLOAT,          -- raw CMS score
    sample_size         INT,            -- number of cases
    readmission_rate    FLOAT,          -- derived %
    avg_los_days        FLOAT,          -- average length of stay
    cauti_index         FLOAT,          -- catheter UTI rate per 1,000 days
    encounter_volume    INT,            -- encounter count for period

    -- Metadata
    period_start        DATE,
    period_end          DATE,
    loaded_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);

-- ── KPI VIEWS ─────────────────────────────────────────────────

CREATE OR REPLACE VIEW ANALYTICS.vw_readmission_rate AS
SELECT
    h.hospital_name,
    h.state,
    h.region,
    d.year,
    d.month_name,
    d.quarter,
    AVG(f.readmission_rate)                     AS avg_readmission_rate,
    SUM(f.sample_size)                          AS total_cases,
    COUNT(DISTINCT f.hospital_key)              AS hospital_count
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital  h ON f.hospital_key  = h.hospital_key
JOIN ANALYTICS.dim_date      d ON f.date_key       = d.date_key
JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
WHERE dx.category = 'Readmission'
GROUP BY 1,2,3,4,5,6;

CREATE OR REPLACE VIEW ANALYTICS.vw_avg_los AS
SELECT
    h.hospital_name,
    h.state,
    h.hospital_type,
    dx.measure_name,
    d.year,
    d.quarter,
    AVG(f.avg_los_days)     AS avg_length_of_stay,
    SUM(f.sample_size)      AS total_cases
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital  h  ON f.hospital_key  = h.hospital_key
JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
JOIN ANALYTICS.dim_date      d  ON f.date_key       = d.date_key
GROUP BY 1,2,3,4,5,6;

CREATE OR REPLACE VIEW ANALYTICS.vw_cauti_index AS
SELECT
    h.hospital_name,
    h.state,
    h.region,
    d.year,
    d.month_name,
    AVG(f.cauti_index)      AS avg_cauti_index,
    SUM(f.sample_size)      AS total_patient_days
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital  h  ON f.hospital_key  = h.hospital_key
JOIN ANALYTICS.dim_date      d  ON f.date_key       = d.date_key
JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
WHERE dx.category = 'Infection'
GROUP BY 1,2,3,4,5;

CREATE OR REPLACE VIEW ANALYTICS.vw_encounter_volume AS
SELECT
    h.hospital_name,
    h.state,
    h.region,
    h.hospital_type,
    d.year,
    d.month,
    d.month_name,
    d.quarter,
    SUM(f.encounter_volume) AS total_encounters,
    SUM(f.sample_size)      AS total_cases,
    AVG(f.score)            AS avg_quality_score
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital h ON f.hospital_key = h.hospital_key
JOIN ANALYTICS.dim_date     d ON f.date_key      = d.date_key
GROUP BY 1,2,3,4,5,6,7,8;

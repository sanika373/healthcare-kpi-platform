-- ============================================================
--  Healthcare KPI Intelligence Platform
--  KPI Analytical Queries
-- ============================================================

-- ── 1. 30-Day Readmission Rate by State (YoY) ────────────────
SELECT
    h.state,
    d.year,
    ROUND(AVG(f.readmission_rate), 2)       AS avg_readmission_rate,
    SUM(f.sample_size)                       AS total_cases,
    LAG(ROUND(AVG(f.readmission_rate), 2))
        OVER (PARTITION BY h.state ORDER BY d.year) AS prev_year_rate,
    ROUND(
        (AVG(f.readmission_rate) -
         LAG(AVG(f.readmission_rate)) OVER (PARTITION BY h.state ORDER BY d.year))
        / NULLIF(LAG(AVG(f.readmission_rate)) OVER (PARTITION BY h.state ORDER BY d.year), 0) * 100
    , 2)                                     AS yoy_change_pct
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital  h  ON f.hospital_key  = h.hospital_key
JOIN ANALYTICS.dim_date      d  ON f.date_key       = d.date_key
JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
WHERE dx.category = 'Readmission'
GROUP BY h.state, d.year
ORDER BY h.state, d.year;


-- ── 2. Average LOS by Hospital Type & Diagnosis ──────────────
WITH ranked AS (
    SELECT
        h.hospital_type,
        dx.measure_name,
        ROUND(AVG(f.avg_los_days), 1)       AS avg_los,
        SUM(f.sample_size)                  AS total_cases,
        ROW_NUMBER() OVER (
            PARTITION BY h.hospital_type
            ORDER BY AVG(f.avg_los_days) DESC
        )                                   AS los_rank
    FROM ANALYTICS.fact_encounters f
    JOIN ANALYTICS.dim_hospital  h  ON f.hospital_key  = h.hospital_key
    JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
    GROUP BY h.hospital_type, dx.measure_name
)
SELECT * FROM ranked WHERE los_rank <= 10
ORDER BY hospital_type, los_rank;


-- ── 3. CAUTI Index Trend — Monthly Rolling Average ────────────
SELECT
    h.state,
    d.year,
    d.month,
    d.month_name,
    ROUND(AVG(f.cauti_index), 3)            AS monthly_cauti,
    ROUND(AVG(AVG(f.cauti_index)) OVER (
        PARTITION BY h.state
        ORDER BY d.year, d.month
        ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
    ), 3)                                   AS rolling_3m_avg
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital  h  ON f.hospital_key  = h.hospital_key
JOIN ANALYTICS.dim_date      d  ON f.date_key       = d.date_key
JOIN ANALYTICS.dim_diagnosis dx ON f.diagnosis_key = dx.diagnosis_key
WHERE dx.category = 'Infection'
GROUP BY h.state, d.year, d.month, d.month_name
ORDER BY h.state, d.year, d.month;


-- ── 4. Hospital Performance Scorecard (Top / Bottom 10) ───────
WITH scores AS (
    SELECT
        h.provider_id,
        h.hospital_name,
        h.state,
        h.region,
        ROUND(AVG(f.score), 2)              AS composite_score,
        SUM(f.encounter_volume)             AS total_encounters,
        ROUND(AVG(f.readmission_rate), 2)   AS avg_readmission,
        ROUND(AVG(f.avg_los_days), 1)       AS avg_los,
        ROUND(AVG(f.cauti_index), 3)        AS avg_cauti
    FROM ANALYTICS.fact_encounters f
    JOIN ANALYTICS.dim_hospital h ON f.hospital_key = h.hospital_key
    GROUP BY h.provider_id, h.hospital_name, h.state, h.region
),
percentiled AS (
    SELECT *,
        PERCENT_RANK() OVER (ORDER BY composite_score DESC) AS score_percentile
    FROM scores
)
SELECT * FROM percentiled
WHERE score_percentile <= 0.10 OR score_percentile >= 0.90
ORDER BY composite_score DESC;


-- ── 5. Encounter Volume MoM Growth by Region ─────────────────
SELECT
    h.region,
    d.year,
    d.month,
    d.month_name,
    SUM(f.encounter_volume)                 AS total_encounters,
    LAG(SUM(f.encounter_volume)) OVER (
        PARTITION BY h.region
        ORDER BY d.year, d.month
    )                                       AS prev_month_encounters,
    ROUND(
        (SUM(f.encounter_volume) -
         LAG(SUM(f.encounter_volume)) OVER (PARTITION BY h.region ORDER BY d.year, d.month))
        / NULLIF(LAG(SUM(f.encounter_volume)) OVER (PARTITION BY h.region ORDER BY d.year, d.month), 0) * 100
    , 1)                                    AS mom_growth_pct
FROM ANALYTICS.fact_encounters f
JOIN ANALYTICS.dim_hospital h ON f.hospital_key = h.hospital_key
JOIN ANALYTICS.dim_date     d ON f.date_key      = d.date_key
GROUP BY h.region, d.year, d.month, d.month_name
ORDER BY h.region, d.year, d.month;

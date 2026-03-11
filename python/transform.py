"""
transform.py
============
Transforms RAW Snowflake tables into ANALYTICS star schema:
  dim_hospital, dim_diagnosis, fact_encounters

Usage:
    python python/transform.py
"""

import os
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

TRANSFORMS = {

    # ── dim_hospital ─────────────────────────────────────────
    "dim_hospital": """
        MERGE INTO ANALYTICS.dim_hospital tgt
        USING (
            SELECT DISTINCT
                provider_id,
                hospital_name,
                address,
                city,
                state,
                zip_code,
                county_name,
                CASE
                    WHEN state IN ('CT','ME','MA','NH','RI','VT','NY','NJ','PA') THEN 'Northeast'
                    WHEN state IN ('IL','IN','MI','OH','WI','IA','KS','MN','MO','NE','ND','SD') THEN 'Midwest'
                    WHEN state IN ('DE','FL','GA','MD','NC','SC','VA','WV','AL','KY','MS','TN',
                                   'AR','LA','OK','TX','DC') THEN 'South'
                    ELSE 'West'
                END AS region,
                hospital_type,
                hospital_ownership
            FROM RAW.HOSPITAL_GENERAL
            WHERE provider_id IS NOT NULL
        ) src
        ON tgt.provider_id = src.provider_id
        WHEN MATCHED THEN UPDATE SET
            tgt.hospital_name      = src.hospital_name,
            tgt.state              = src.state,
            tgt.region             = src.region,
            tgt.hospital_type      = src.hospital_type,
            tgt.hospital_ownership = src.hospital_ownership,
            tgt.updated_at         = CURRENT_TIMESTAMP()
        WHEN NOT MATCHED THEN INSERT (
            provider_id, hospital_name, address, city, state, zip_code,
            county_name, region, hospital_type, hospital_ownership
        ) VALUES (
            src.provider_id, src.hospital_name, src.address, src.city,
            src.state, src.zip_code, src.county_name, src.region,
            src.hospital_type, src.hospital_ownership
        );
    """,

    # ── dim_diagnosis ────────────────────────────────────────
    "dim_diagnosis": """
        MERGE INTO ANALYTICS.dim_diagnosis tgt
        USING (
            SELECT DISTINCT
                measure_id,
                measure_name,
                CASE
                    WHEN LOWER(measure_name) LIKE '%readmission%' THEN 'Readmission'
                    WHEN LOWER(measure_name) LIKE '%infection%'
                      OR LOWER(measure_name) LIKE '%cauti%'
                      OR LOWER(measure_name) LIKE '%clabsi%'  THEN 'Infection'
                    WHEN LOWER(measure_name) LIKE '%mortality%'
                      OR LOWER(measure_name) LIKE '%death%'   THEN 'Mortality'
                    WHEN LOWER(measure_name) LIKE '%complication%' THEN 'Complication'
                    ELSE 'Other'
                END AS category,
                NULL AS sub_category
            FROM RAW.COMPLICATIONS_DEATHS
            WHERE measure_id IS NOT NULL
        ) src
        ON tgt.measure_id = src.measure_id
        WHEN NOT MATCHED THEN INSERT (measure_id, measure_name, category, sub_category)
        VALUES (src.measure_id, src.measure_name, src.category, src.sub_category);
    """,

    # ── fact_encounters ──────────────────────────────────────
    "fact_encounters": """
        INSERT INTO ANALYTICS.fact_encounters (
            hospital_key, diagnosis_key, date_key,
            score, sample_size,
            readmission_rate, avg_los_days, cauti_index, encounter_volume,
            period_start, period_end
        )
        SELECT
            h.hospital_key,
            dx.diagnosis_key,
            TO_NUMBER(TO_CHAR(COALESCE(TRY_TO_DATE(r.start_date, 'MM/DD/YYYY'), CURRENT_DATE()), 'YYYYMMDD')) AS date_key,

            TRY_TO_DOUBLE(r.score)                              AS score,
            TRY_TO_NUMBER(r.sample)                             AS sample_size,

            -- Readmission rate: score is per 100 for readmission measures
            CASE WHEN dx.category = 'Readmission'
                 THEN TRY_TO_DOUBLE(r.score) / 100.0 END        AS readmission_rate,

            -- LOS proxy: not directly in CMS; set to NULL, enrichable later
            NULL                                                AS avg_los_days,

            -- CAUTI index: score represents rate per 1,000 catheter days
            CASE WHEN LOWER(dx.measure_name) LIKE '%cauti%'
                 THEN TRY_TO_DOUBLE(r.score) END                AS cauti_index,

            TRY_TO_NUMBER(r.sample)                             AS encounter_volume,

            TRY_TO_DATE(r.start_date, 'MM/DD/YYYY')            AS period_start,
            TRY_TO_DATE(r.end_date,   'MM/DD/YYYY')            AS period_end

        FROM RAW.COMPLICATIONS_DEATHS r
        JOIN ANALYTICS.dim_hospital  h  ON r.provider_id = h.provider_id
        JOIN ANALYTICS.dim_diagnosis dx ON r.measure_id  = dx.measure_id
        WHERE r.score IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM ANALYTICS.fact_encounters f2
            WHERE f2.hospital_key  = h.hospital_key
              AND f2.diagnosis_key = dx.diagnosis_key
              AND f2.period_start  = TRY_TO_DATE(r.start_date, 'MM/DD/YYYY')
          );
    """,
}

def get_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database  = os.environ.get("SNOWFLAKE_DATABASE",  "HEALTHCARE_KPI"),
        schema    = "ANALYTICS",
        role      = os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )

def main():
    conn = get_conn()
    cur  = conn.cursor()
    try:
        for step, sql in TRANSFORMS.items():
            print(f"Running transform: {step}...")
            cur.execute(sql)
            print(f"  ✓ {step} complete — {cur.rowcount} rows affected")
        print("\n✅ All transforms complete.")
    except Exception as e:
        print(f"\n❌ Transform failed: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()

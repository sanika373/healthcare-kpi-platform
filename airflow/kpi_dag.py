"""
kpi_dag.py
==========
Apache Airflow DAG — orchestrates the Healthcare KPI pipeline daily.

Pipeline:
  1. fetch_cms_data      → Download latest CMS datasets
  2. load_raw_snowflake  → Ingest into RAW schema
  3. transform_dims      → Build dim_hospital + dim_diagnosis
  4. transform_facts     → Populate fact_encounters
  5. refresh_kpi_views   → Recreate KPI views (no-op if unchanged)
  6. data_quality_check  → Row count + null assertions

Copy to $AIRFLOW_HOME/dags/ to deploy.
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.dates import days_ago
import subprocess, sys, os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

default_args = {
    "owner"           : "sanika.pawar",
    "depends_on_past" : False,
    "email_on_failure": True,
    "email"           : ["sanika.dilip.pawar@gmail.com"],
    "retries"         : 2,
    "retry_delay"     : timedelta(minutes=5),
}

def run_ingest():
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "python", "ingest.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)

def run_transform():
    result = subprocess.run(
        [sys.executable, os.path.join(PROJECT_ROOT, "python", "transform.py")],
        capture_output=True, text=True
    )
    print(result.stdout)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)

def data_quality_check():
    import snowflake.connector, os
    conn = snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database  = os.environ.get("SNOWFLAKE_DATABASE",  "HEALTHCARE_KPI"),
    )
    checks = [
        ("dim_hospital row count",   "SELECT COUNT(*) FROM ANALYTICS.dim_hospital",   100),
        ("dim_diagnosis row count",  "SELECT COUNT(*) FROM ANALYTICS.dim_diagnosis",   10),
        ("fact_encounters row count","SELECT COUNT(*) FROM ANALYTICS.fact_encounters", 500),
        ("Null hospital_key check",  "SELECT COUNT(*) FROM ANALYTICS.fact_encounters WHERE hospital_key IS NULL", 0, "=="),
    ]
    cur = conn.cursor()
    for check in checks:
        label, sql = check[0], check[1]
        threshold  = check[2]
        op         = check[3] if len(check) > 3 else ">="
        cur.execute(sql)
        count = cur.fetchone()[0]
        passed = (count >= threshold) if op == ">=" else (count == threshold)
        status = "✓" if passed else "✗"
        print(f"  {status} {label}: {count} (expected {op} {threshold})")
        if not passed:
            raise AssertionError(f"DQ check failed: {label} — got {count}")
    cur.close()
    conn.close()
    print("✅ All data quality checks passed.")

with DAG(
    dag_id          = "healthcare_kpi_pipeline",
    default_args    = default_args,
    description     = "Daily CMS data ingestion, star schema build, and KPI refresh",
    schedule_interval = "0 6 * * *",   # 6 AM UTC daily
    start_date      = days_ago(1),
    catchup         = False,
    tags            = ["healthcare", "bi", "snowflake", "kpi"],
) as dag:

    t1 = PythonOperator(
        task_id         = "ingest_cms_data",
        python_callable = run_ingest,
        doc_md          = "Download CMS hospital quality CSV and load into Snowflake RAW schema."
    )

    t2 = PythonOperator(
        task_id         = "transform_to_star_schema",
        python_callable = run_transform,
        doc_md          = "Build dim_hospital, dim_diagnosis, and fact_encounters from RAW layer."
    )

    t3 = BashOperator(
        task_id      = "refresh_kpi_views",
        bash_command = f"snowsql -a $SNOWFLAKE_ACCOUNT -u $SNOWFLAKE_USER -p $SNOWFLAKE_PASSWORD "
                       f"-f {PROJECT_ROOT}/sql/schema.sql --query 'SELECT 1' -o exit_on_error=true",
        doc_md       = "Re-execute schema.sql to ensure KPI views are up to date."
    )

    t4 = PythonOperator(
        task_id         = "data_quality_check",
        python_callable = data_quality_check,
        doc_md          = "Assert row counts and null checks across all ANALYTICS tables."
    )

    t1 >> t2 >> t3 >> t4

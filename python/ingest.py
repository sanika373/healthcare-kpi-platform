"""
ingest.py
=========
Downloads CMS Hospital Quality data and loads it into Snowflake RAW schema.

Usage:
    python python/ingest.py
"""

import os
import requests
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

# ── CMS Open Data endpoints ───────────────────────────────────
CMS_DATASETS = {
    "hospital_general":
        "https://data.cms.gov/provider-data/api/1/datastore/query/xubh-q36u/0?limit=5000&offset=0&count=true&results=true&schema=true&keys=true&format=json&rowIds=false",
    "complications_deaths":
        "https://data.cms.gov/provider-data/api/1/datastore/query/ynj2-r877/0?limit=5000&offset=0&count=true&results=true&schema=true&keys=true&format=json&rowIds=false",
}

# ── Snowflake connection ──────────────────────────────────────
def get_snowflake_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        warehouse = os.environ.get("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database  = os.environ.get("SNOWFLAKE_DATABASE",  "HEALTHCARE_KPI"),
        schema    = "RAW",
        role      = os.environ.get("SNOWFLAKE_ROLE", "SYSADMIN"),
    )

# ── Fetch CMS data ────────────────────────────────────────────
def fetch_cms_data(url: str, dataset_name: str) -> pd.DataFrame:
    print(f"Fetching {dataset_name}...")
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    data = response.json()
    df = pd.DataFrame(data.get("results", []))
    print(f"  → {len(df)} rows fetched")
    return df

# ── Clean columns for Snowflake ───────────────────────────────
def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    # Uppercase column names (Snowflake default)
    df.columns = [c.upper().replace(" ", "_").replace("-", "_") for c in df.columns]
    # Replace 'Not Available' with None
    df = df.replace({"Not Available": None, "N/A": None, "": None})
    # Coerce numeric fields
    for col in ["SCORE", "SAMPLE"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

# ── Load to Snowflake ─────────────────────────────────────────
def load_to_snowflake(df: pd.DataFrame, table: str, conn):
    print(f"  → Loading {len(df)} rows into RAW.{table}...")
    success, nchunks, nrows, _ = write_pandas(
        conn, df, table_name=table, schema="RAW",
        auto_create_table=True, overwrite=True
    )
    if success:
        print(f"  ✓ {nrows} rows loaded in {nchunks} chunk(s)")
    else:
        raise RuntimeError(f"Failed to load {table}")

# ── Main ──────────────────────────────────────────────────────
def main():
    conn = get_snowflake_conn()
    try:
        for name, url in CMS_DATASETS.items():
            df = fetch_cms_data(url, name)
            df = clean_df(df)
            load_to_snowflake(df, name.upper(), conn)
        print("\n✅ Ingestion complete.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()

# 🏥 Healthcare KPI Intelligence Platform

A full-stack Business Intelligence pipeline that ingests public CMS hospital quality data, models it into a Snowflake star schema, and surfaces real-time clinical KPIs via an interactive Power BI dashboard.

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python) ![Snowflake](https://img.shields.io/badge/Snowflake-Data_Warehouse-29B5E8?logo=snowflake) ![Power BI](https://img.shields.io/badge/Power_BI-Dashboard-F2C811?logo=powerbi) ![Airflow](https://img.shields.io/badge/Apache_Airflow-Orchestration-017CEE?logo=apacheairflow) ![SQL](https://img.shields.io/badge/SQL-Star_Schema-orange)

---

## 📌 Project Overview

This project demonstrates end-to-end BI engineering skills including:
- **Data ingestion** from CMS Open Data (public hospital quality datasets)
- **Data modeling** using a star schema in Snowflake
- **KPI calculation** for readmission rates, average length of stay (LOS), and CAUTI index
- **Dashboard delivery** via Power BI with row-level security and scheduled refresh
- **Pipeline orchestration** using Apache Airflow DAGs

---

## 🏗️ Architecture

```
CMS Open Data (CSV)
        │
        ▼
  Python Ingest Layer
  (pandas + snowflake-connector)
        │
        ▼
  Snowflake Raw Schema
  (RAW.hospital_quality)
        │
        ▼
  Star Schema (ANALYTICS schema)
  ┌─────────────────────────────────────┐
  │  fact_encounters                    │
  │  dim_hospital                       │
  │  dim_date                           │
  │  dim_diagnosis                      │
  └─────────────────────────────────────┘
        │
        ▼
  KPI Views (readmission_rate, avg_los, cauti_index)
        │
        ▼
  Power BI Dashboard
  (self-service, row-level security by region)
        │
        ▼
  Apache Airflow DAG
  (scheduled daily refresh)
```

---

## 📊 KPIs Tracked

| KPI | Description | Business Impact |
|-----|-------------|-----------------|
| **Readmission Rate** | % of patients readmitted within 30 days | CMS penalty risk, care quality |
| **Average LOS** | Average length of stay per diagnosis | Bed utilization, cost efficiency |
| **CAUTI Index** | Catheter-associated UTI rate per 1,000 days | Infection control compliance |
| **Encounter Volume** | Monthly encounter count by hospital & specialty | Capacity planning |

---

## 🗂️ Project Structure

```
healthcare-kpi-platform/
├── README.md
├── requirements.txt
├── sql/
│   ├── schema.sql          # Star schema DDL
│   └── kpi_queries.sql     # KPI view definitions
├── python/
│   ├── ingest.py           # CMS data → Snowflake raw layer
│   └── transform.py        # Raw → star schema transformation
├── airflow/
│   └── kpi_dag.py          # Airflow DAG for daily pipeline
└── dashboard/
    └── README.md           # Power BI setup instructions
```

---

## ⚙️ Setup & Usage

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Snowflake credentials
```bash
cp .env.example .env
# Fill in your Snowflake account, user, password, warehouse, database
```

### 3. Initialize the schema
```bash
snowsql -f sql/schema.sql
```

### 4. Run ingestion
```bash
python python/ingest.py
```

### 5. Run transformation
```bash
python python/transform.py
```

### 6. (Optional) Deploy Airflow DAG
```bash
cp airflow/kpi_dag.py $AIRFLOW_HOME/dags/
airflow dags trigger healthcare_kpi_pipeline
```

---

## 📁 Data Source

Public dataset from the **CMS Hospital Quality Initiative**:
- Source: [data.cms.gov](https://data.cms.gov/provider-data/topics/hospitals)
- Dataset: Hospital General Information + Complications and Deaths
- License: Public Domain (U.S. Government Open Data)

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Ingestion | Python, Pandas, Snowflake Connector |
| Storage | Snowflake (Data Warehouse) |
| Modeling | SQL, Star Schema |
| Orchestration | Apache Airflow |
| Visualization | Power BI (DAX, Power Query, RLS) |

---

## 👩‍💻 Author

**Sanika Pawar** — Senior BI Engineer  
[LinkedIn](https://www.linkedin.com/in/sanika-pawar7481/) · [GitHub](https://github.com/sanika373?tab=repositories)

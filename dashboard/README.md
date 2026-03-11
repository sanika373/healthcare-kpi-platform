# Power BI Dashboard Setup

## Connection Setup

1. Open Power BI Desktop
2. **Get Data** → **Snowflake**
3. Enter your Snowflake server: `<account>.snowflakecomputing.com`
4. Database: `HEALTHCARE_KPI` | Warehouse: `COMPUTE_WH`
5. Import these views:
   - `ANALYTICS.vw_readmission_rate`
   - `ANALYTICS.vw_avg_los`
   - `ANALYTICS.vw_cauti_index`
   - `ANALYTICS.vw_encounter_volume`
   - `ANALYTICS.dim_hospital`
   - `ANALYTICS.dim_date`

## Recommended Report Pages

| Page | Visuals |
|------|---------|
| **Executive Summary** | KPI cards (readmission %, avg LOS, CAUTI index, total encounters), map by state |
| **Readmission Analysis** | Line chart YoY, bar by state, matrix by hospital |
| **Infection Control** | CAUTI trend line, rolling 3-month avg, top/bottom 10 hospitals |
| **Encounter Volume** | MoM growth bar, regional decomposition tree, drill-through to hospital |
| **Hospital Scorecard** | Scatter plot (LOS vs readmission), top/bottom 10 table |

## Row-Level Security (RLS)

Create a `Region` role in Power BI:
```dax
[region] = USERPRINCIPALNAME()
```
Map users to their region in the **Manage Roles** panel before publishing to Power BI Service.

## Scheduled Refresh

After publishing to Power BI Service:
1. Dataset Settings → **Scheduled refresh**
2. Set to **Daily** at 7:00 AM UTC (1 hour after Airflow pipeline completes)
3. Configure Snowflake gateway credentials

## Key DAX Measures

```dax
Avg Readmission Rate =
AVERAGEX(
    SUMMARIZE(fact_encounters, dim_hospital[hospital_name]),
    CALCULATE(AVERAGE(fact_encounters[readmission_rate]))
)

Readmission YoY Change % =
VAR CurrentYear = CALCULATE([Avg Readmission Rate], DATESYTD(dim_date[full_date]))
VAR PriorYear   = CALCULATE([Avg Readmission Rate], SAMEPERIODLASTYEAR(dim_date[full_date]))
RETURN DIVIDE(CurrentYear - PriorYear, PriorYear)

CAUTI Index (Rolling 3M) =
CALCULATE(
    AVERAGE(fact_encounters[cauti_index]),
    DATESINPERIOD(dim_date[full_date], LASTDATE(dim_date[full_date]), -3, MONTH)
)
```

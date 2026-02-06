"""
DAG for Gold Layer - Taxi Data Transformation
Handles: --taxi-type, --year (start), --month (start), --end-year, --end-month
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Get container name from environment (set in docker-compose.yml)
ETL_CONTAINER = os.getenv("PROJECT_ID_BASE", "nyc-taxi-etl") + "-etl"

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="taxi_gold_dag",
    default_args=default_args,
    description="Transform taxi data from Bronze to Gold layer (dimensional model)",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["gold", "transformation", "taxi"],
    params={
        "taxi_type": "yellow",
        "start_year": "2025",
        "start_month": "1",
        "end_year": "2025",
        "end_month": "11",
    },
) as dag:
    transform_to_gold = BashOperator(
        task_id="transform_to_gold",
        bash_command=(
            f"docker exec {ETL_CONTAINER} python -m environments.dev.etl.jobs.gold.taxi_gold_job "
            "--taxi-type {{ params.taxi_type }} "
            "--year {{ params.start_year }} "
            "--month {{ params.start_month }} "
            "--end-year {{ params.end_year }} "
            "--end-month {{ params.end_month }}"
        ),
    )

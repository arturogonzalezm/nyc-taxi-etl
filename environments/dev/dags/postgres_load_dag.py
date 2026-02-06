"""
DAG for Load Layer - PostgreSQL Load
Handles: --taxi-type
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
    dag_id="postgres_load_dag",
    default_args=default_args,
    description="Load taxi data from Gold layer to PostgreSQL",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["load", "postgres", "taxi"],
    params={
        "taxi_type": "yellow",
    },
) as dag:
    load_to_postgres = BashOperator(
        task_id="load_to_postgres",
        bash_command=(
            f"docker exec {ETL_CONTAINER} python -m environments.dev.etl.jobs.load.postgres_load_job "
            "--taxi-type {{ params.taxi_type }}"
        ),
    )

"""
DAG for Misc Layer - Zone Lookup Ingestion
No date range parameters required.
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
    dag_id="zone_lookup_ingestion_dag",
    default_args=default_args,
    description="Ingest taxi zone lookup reference data to Misc layer",
    schedule=None,
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["misc", "ingestion", "zone_lookup"],
) as dag:

    ingest_zone_lookup = BashOperator(
        task_id="ingest_zone_lookup",
        bash_command=(
            f"docker exec {ETL_CONTAINER} "
            "python -m etl.jobs.misc.zone_lookup_ingestion_job"
        ),
    )

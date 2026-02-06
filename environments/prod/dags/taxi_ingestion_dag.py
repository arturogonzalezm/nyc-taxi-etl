"""
DAG for Bronze Layer - Taxi Trip Data Ingestion (Production)

This DAG orchestrates the ingestion of NYC taxi trip data from the TLC website
into the Bronze layer (GCS) using Cloud Run for ETL job execution.

Architecture:
    - Cloud Composer triggers Cloud Run service
    - Cloud Run executes taxi_ingestion_job.py
    - Data flows: NYC TLC Website -> GCS (Bronze)

Handles: --taxi-type, --start-year, --start-month, --end-year, --end-month
"""

import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator

# Environment configuration from Cloud Composer environment variables
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
GCP_REGION = os.getenv("GCP_REGION", "us-central1")
CLOUD_RUN_URL = os.getenv("CLOUD_RUN_URL")

default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "execution_timeout": timedelta(hours=4),
}

with DAG(
    dag_id="taxi_ingestion_dag",
    default_args=default_args,
    description="Ingest taxi trip data from NYC TLC to Bronze layer (GCS) via Cloud Run",
    schedule=None,  # Triggered manually or by scheduler
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["bronze", "ingestion", "taxi", "prod"],
    params={
        "taxi_type": "yellow",
        "start_year": "2025",
        "start_month": "1",
        "end_year": "2025",
        "end_month": "11",
    },
    doc_md="""
    ## Taxi Ingestion DAG (Production)
    
    Ingests NYC taxi trip data from TLC website into GCS Bronze layer.
    
    ### Parameters
    - `taxi_type`: Type of taxi data (yellow or green)
    - `start_year`: Start year for data range
    - `start_month`: Start month for data range
    - `end_year`: End year for data range
    - `end_month`: End month for data range
    
    ### Execution
    This DAG triggers a Cloud Run job that executes the taxi ingestion ETL.
    
    ### IAM Requirements
    - Cloud Composer SA needs `roles/run.invoker` on Cloud Run service
    - Cloud Run SA needs `roles/storage.objectAdmin` on GCS bucket
    """,
) as dag:

    def trigger_cloud_run_job(**context):
        """
        Trigger Cloud Run service to execute taxi ingestion job.

        Uses authenticated HTTP request to Cloud Run service endpoint.
        """
        import google.auth.transport.requests
        import google.oauth2.id_token
        import requests

        params = context["params"]

        # Build job payload
        payload = {
            "job": "taxi_ingestion",
            "taxi_type": params.get("taxi_type", "yellow"),
            "start_year": int(params.get("start_year", 2025)),
            "start_month": int(params.get("start_month", 1)),
            "end_year": int(params.get("end_year", 2025)),
            "end_month": int(params.get("end_month", 11)),
        }

        # Get ID token for Cloud Run authentication
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, CLOUD_RUN_URL)

        # Make authenticated request to Cloud Run
        headers = {
            "Authorization": f"Bearer {id_token}",
            "Content-Type": "application/json",
        }

        response = requests.post(
            f"{CLOUD_RUN_URL}/run",
            headers=headers,
            json=payload,
            timeout=14400,  # 4 hour timeout for large data ingestion
        )

        response.raise_for_status()

        result = response.json()
        context["ti"].xcom_push(key="job_result", value=result)

        return result

    # Task to trigger Cloud Run ETL job
    ingest_taxi_data = PythonOperator(
        task_id="ingest_taxi_data",
        python_callable=trigger_cloud_run_job,
        provide_context=True,
    )

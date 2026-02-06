"""
DAG for Gold Layer - Taxi Data Transformation (Production)

This DAG orchestrates the transformation of taxi data from Bronze layer
to Gold layer (dimensional model) using Cloud Run for ETL job execution.

Architecture:
    - Cloud Composer triggers Cloud Run service
    - Cloud Run executes taxi_gold_job.py
    - Data flows: GCS (Bronze) -> GCS (Gold)

Handles: --taxi-type, --year, --month, --end-year, --end-month
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
    "execution_timeout": timedelta(hours=3),
}

with DAG(
    dag_id="taxi_gold_dag",
    default_args=default_args,
    description="Transform taxi data from Bronze to Gold layer (dimensional model) via Cloud Run",
    schedule=None,  # Triggered manually or by upstream DAG
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["gold", "transformation", "taxi", "prod"],
    params={
        "taxi_type": "yellow",
        "start_year": "2025",
        "start_month": "1",
        "end_year": "2025",
        "end_month": "11",
    },
    doc_md="""
    ## Taxi Gold DAG (Production)
    
    Transforms taxi data from Bronze layer into Gold layer dimensional model.
    
    ### Parameters
    - `taxi_type`: Type of taxi data (yellow or green)
    - `start_year`: Start year for data range
    - `start_month`: Start month for data range
    - `end_year`: End year for data range
    - `end_month`: End month for data range
    
    ### Execution
    This DAG triggers a Cloud Run job that executes the gold transformation ETL.
    
    ### IAM Requirements
    - Cloud Composer SA needs `roles/run.invoker` on Cloud Run service
    - Cloud Run SA needs `roles/storage.objectAdmin` on GCS bucket
    """,
) as dag:

    def trigger_cloud_run_job(**context):
        """
        Trigger Cloud Run service to execute gold transformation job.

        Uses authenticated HTTP request to Cloud Run service endpoint.
        """
        import google.auth.transport.requests
        import google.oauth2.id_token
        import requests

        params = context["params"]

        # Build job payload
        payload = {
            "job": "taxi_gold",
            "taxi_type": params.get("taxi_type", "yellow"),
            "year": int(params.get("start_year", 2025)),
            "month": int(params.get("start_month", 1)),
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
            timeout=10800,  # 3 hour timeout for transformation jobs
        )

        response.raise_for_status()

        result = response.json()
        context["ti"].xcom_push(key="job_result", value=result)

        return result

    # Task to trigger Cloud Run ETL job
    transform_to_gold = PythonOperator(
        task_id="transform_to_gold",
        python_callable=trigger_cloud_run_job,
        provide_context=True,
    )

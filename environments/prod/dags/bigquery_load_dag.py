"""
DAG for Load Layer - BigQuery Load (Production)

This DAG orchestrates the loading of dimensional model data from GCS Gold layer
into BigQuery using Cloud Run for ETL job execution.

Architecture:
    - Cloud Composer triggers Cloud Run service
    - Cloud Run executes bigquery_load_job.py
    - Data flows: GCS (Gold) -> BigQuery

Handles: --taxi-type, --year (optional), --month (optional)
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
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="bigquery_load_dag",
    default_args=default_args,
    description="Load taxi data from Gold layer (GCS) to BigQuery via Cloud Run",
    schedule=None,  # Triggered manually or by upstream DAG
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["load", "bigquery", "taxi", "prod"],
    params={
        "taxi_type": "yellow",
        "year": None,  # Optional: specific year
        "month": None,  # Optional: specific month
    },
    doc_md="""
    ## BigQuery Load DAG (Production)
    
    Loads dimensional model data from GCS Gold layer into BigQuery.
    
    ### Parameters
    - `taxi_type`: Type of taxi data (yellow or green)
    - `year`: Optional year filter for incremental loads
    - `month`: Optional month filter for incremental loads
    
    ### Execution
    This DAG triggers a Cloud Run job that executes the BigQuery load ETL.
    
    ### IAM Requirements
    - Cloud Composer SA needs `roles/run.invoker` on Cloud Run service
    - Cloud Run SA needs `roles/bigquery.dataEditor` and `roles/bigquery.jobUser`
    - Cloud Run SA needs `roles/storage.objectViewer` on GCS bucket
    """,
) as dag:

    def trigger_cloud_run_job(**context):
        """
        Trigger Cloud Run service to execute BigQuery load job.

        Uses authenticated HTTP request to Cloud Run service endpoint.
        """
        import google.auth.transport.requests
        import google.oauth2.id_token
        import requests

        params = context["params"]

        # Build job payload
        payload = {
            "job": "bigquery_load",
            "taxi_type": params.get("taxi_type", "yellow"),
        }

        if params.get("year"):
            payload["year"] = params["year"]
        if params.get("month"):
            payload["month"] = params["month"]

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
            timeout=7200,  # 2 hour timeout for long-running jobs
        )

        response.raise_for_status()

        result = response.json()
        context["ti"].xcom_push(key="job_result", value=result)

        return result

    # Task to trigger Cloud Run ETL job
    load_to_bigquery = PythonOperator(
        task_id="load_to_bigquery",
        python_callable=trigger_cloud_run_job,
        provide_context=True,
    )

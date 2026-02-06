"""
DAG for Misc Layer - Zone Lookup Ingestion (Production)

This DAG orchestrates the ingestion of NYC taxi zone lookup reference data
into the Misc layer (GCS) using Cloud Run for ETL job execution.

Architecture:
    - Cloud Composer triggers Cloud Run service
    - Cloud Run executes zone_lookup_ingestion_job.py
    - Data flows: NYC TLC Website -> GCS (Misc)

No date range parameters required - this is reference data.
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
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(minutes=30),
}

with DAG(
    dag_id="zone_lookup_ingestion_dag",
    default_args=default_args,
    description="Ingest taxi zone lookup reference data to Misc layer (GCS) via Cloud Run",
    schedule=None,  # Triggered manually - reference data rarely changes
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["misc", "ingestion", "zone_lookup", "prod"],
    doc_md="""
    ## Zone Lookup Ingestion DAG (Production)
    
    Ingests NYC taxi zone lookup reference data into GCS Misc layer.
    
    ### Parameters
    No parameters required - this ingests the complete zone lookup dataset.
    
    ### Execution
    This DAG triggers a Cloud Run job that executes the zone lookup ingestion ETL.
    
    ### IAM Requirements
    - Cloud Composer SA needs `roles/run.invoker` on Cloud Run service
    - Cloud Run SA needs `roles/storage.objectAdmin` on GCS bucket
    """,
) as dag:

    def trigger_cloud_run_job(**context):
        """
        Trigger Cloud Run service to execute zone lookup ingestion job.

        Uses authenticated HTTP request to Cloud Run service endpoint.
        """
        import google.auth.transport.requests
        import google.oauth2.id_token
        import requests

        # Build job payload
        payload = {
            "job": "zone_lookup_ingestion",
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
            timeout=1800,  # 30 minute timeout for reference data
        )

        response.raise_for_status()

        result = response.json()
        context["ti"].xcom_push(key="job_result", value=result)

        return result

    # Task to trigger Cloud Run ETL job
    ingest_zone_lookup = PythonOperator(
        task_id="ingest_zone_lookup",
        python_callable=trigger_cloud_run_job,
        provide_context=True,
    )

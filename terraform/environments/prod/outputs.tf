# =============================================================================
# OUTPUTS
# =============================================================================

output "composer_airflow_uri" {
  description = "Cloud Composer Airflow Web UI URL"
  value       = google_composer_environment.prod.config[0].airflow_uri
}

output "composer_dag_gcs_prefix" {
  description = "GCS path for uploading DAGs to Cloud Composer"
  value       = google_composer_environment.prod.config[0].dag_gcs_prefix
}

output "cloud_run_url" {
  description = "Cloud Run service URL for ETL job execution"
  value       = google_cloud_run_v2_service.etl_runner.uri
}

output "bigquery_dataset" {
  description = "BigQuery dataset ID"
  value       = google_bigquery_dataset.taxi.dataset_id
}

output "gcs_bucket" {
  description = "GCS bucket for production data"
  value       = google_storage_bucket.prod_data.name
}

output "artifact_registry_url" {
  description = "Artifact Registry URL for container images"
  value       = "${var.region}-docker.pkg.dev/${google_project.prod_project.project_id}/${google_artifact_registry_repository.etl_images.repository_id}"
}

output "composer_service_account" {
  description = "Cloud Composer service account email"
  value       = google_service_account.composer_sa.email
}

output "cloud_run_service_account" {
  description = "Cloud Run service account email"
  value       = google_service_account.cloud_run_sa.email
}

output "etl_service_account" {
  description = "ETL service account email"
  value       = google_service_account.etl_sa.email
}

output "vpc_network" {
  description = "VPC network for ETL workloads"
  value       = google_compute_network.etl_vpc.name
}

output "vpc_connector" {
  description = "VPC connector for Cloud Run egress"
  value       = google_vpc_access_connector.etl_connector.name
}

output "cloud_nat" {
  description = "Cloud NAT for outbound internet access"
  value       = google_compute_router_nat.etl_nat.name
}

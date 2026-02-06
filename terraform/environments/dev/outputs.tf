output "project_id" {
  description = "The GCP project ID"
  value       = google_project.nyc_taxi_project.project_id
}

output "project_number" {
  description = "The GCP project number"
  value       = google_project.nyc_taxi_project.number
}

output "service_account_email" {
  description = "Email of the NYC Taxi pipeline service account (CI/CD)"
  value       = google_service_account.nyc_taxi_sa.email
}

output "airflow_service_account_email" {
  description = "Email of the Airflow service account (GCS read/write only)"
  value       = google_service_account.airflow_sa.email
}

output "gcs_bucket_name" {
  description = "Name of the GCS bucket for pipeline data"
  value       = google_storage_bucket.nyc_taxi_etl.name
}

output "gcs_bucket_url" {
  description = "URL of the GCS bucket"
  value       = google_storage_bucket.nyc_taxi_etl.url
}

output "terraform_state_bucket" {
  description = "Name of the Terraform state bucket"
  value       = google_storage_bucket.terraform_state.name
}

output "iam_roles_assigned" {
  description = "IAM roles assigned to the pipeline service account (CI/CD)"
  value = [
    "roles/editor",
    "roles/storage.admin",
    "roles/serviceusage.serviceUsageAdmin",
    "roles/iam.serviceAccountAdmin",
    "roles/iam.workloadIdentityPoolAdmin",
    "roles/resourcemanager.projectIamAdmin"
  ]
}

output "airflow_iam_roles_assigned" {
  description = "IAM roles assigned to the Airflow service account (GCS only)"
  value = [
    "roles/storage.objectAdmin (bucket-level)",
    "roles/storage.legacyBucketReader (bucket-level)"
  ]
}

# Workload Identity Federation outputs for GitHub Actions
output "workload_identity_provider" {
  description = "Workload Identity Provider resource name (use this for GCP_WORKLOAD_IDENTITY_PROVIDER secret)"
  value       = google_iam_workload_identity_pool_provider.github_provider.name
}

output "workload_identity_pool" {
  description = "Workload Identity Pool resource name"
  value       = google_iam_workload_identity_pool.github_pool.name
}

# GitHub Actions secrets output (for easy copy-paste)
output "github_secrets" {
  description = "Values to add as GitHub Actions secrets"
  value = {
    GCP_WORKLOAD_IDENTITY_PROVIDER = google_iam_workload_identity_pool_provider.github_provider.name
    GCP_SERVICE_ACCOUNT            = google_service_account.nyc_taxi_sa.email
  }
}

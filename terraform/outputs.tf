output "project_id" {
  description = "The GCP project ID"
  value       = module.etl_infrastructure.project_id
}

output "project_number" {
  description = "The GCP project number"
  value       = module.etl_infrastructure.project_number
}

output "service_account_email" {
  description = "Email of the NYC Taxi ETL service account"
  value       = module.etl_infrastructure.service_account_email
}

output "gcs_bucket_name" {
  description = "Name of the GCS bucket"
  value       = module.etl_infrastructure.gcs_bucket_name
}

output "gcs_bucket_url" {
  description = "URL of the GCS bucket"
  value       = module.etl_infrastructure.gcs_bucket_url
}

output "iam_roles_assigned" {
  description = "IAM roles assigned to the service account"
  value       = module.etl_infrastructure.iam_roles_assigned
}

# Workload Identity Federation outputs for GitHub Actions
output "workload_identity_provider" {
  description = "Workload Identity Provider resource name (use this for GCP_WORKLOAD_IDENTITY_PROVIDER secret)"
  value       = module.etl_infrastructure.workload_identity_provider
}

output "workload_identity_pool" {
  description = "Workload Identity Pool resource name"
  value       = module.etl_infrastructure.workload_identity_pool
}

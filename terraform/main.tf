# =============================================================================
# GCP PROJECT (use existing - service accounts cannot create projects without org)
# =============================================================================

# Reference existing GCP Project
data "google_project" "nyc_taxi_project" {
  project_id = local.full_project_id
}

# Enable Cloud Resource Manager API (required for project operations)
resource "google_project_service" "cloudresourcemanager" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "cloudresourcemanager.googleapis.com"

  disable_on_destroy = false

  depends_on = [data.google_project.nyc_taxi_project]
}

# Enable Cloud Billing API
resource "google_project_service" "cloudbilling" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "cloudbilling.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# Enable IAM API
resource "google_project_service" "iam" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "iam.googleapis.com"

  disable_on_destroy = false

  depends_on = [data.google_project.nyc_taxi_project]
}

# Enable IAM Service Account Credentials API (required for Workload Identity Federation)
resource "google_project_service" "iamcredentials" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "iamcredentials.googleapis.com"

  disable_on_destroy = false

  depends_on = [data.google_project.nyc_taxi_project]
}

# Enable Service Usage API (required for listing/managing project services)
resource "google_project_service" "serviceusage" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "serviceusage.googleapis.com"

  disable_on_destroy = false

  depends_on = [data.google_project.nyc_taxi_project]
}

# Enable Cloud Storage API
resource "google_project_service" "storage" {
  project = data.google_project.nyc_taxi_project.project_id
  service = "storage.googleapis.com"

  disable_on_destroy = false

  depends_on = [data.google_project.nyc_taxi_project]
}

# =============================================================================
# SERVICE ACCOUNT
# =============================================================================

# Service Account for the pipeline
resource "google_service_account" "nyc_taxi_sa" {
  account_id   = "${var.project_id_base}-${var.environment}-sa-${var.instance_number}"
  display_name = "NYC Taxi Pipeline Service Account (${var.environment})"
  project      = data.google_project.nyc_taxi_project.project_id

  depends_on = [google_project_service.iam]
}

# =============================================================================
# WORKLOAD IDENTITY FEDERATION (for GitHub Actions)
# =============================================================================

# Workload Identity Pool for GitHub Actions
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = data.google_project.nyc_taxi_project.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"

  depends_on = [google_project_service.iam]
}

# Workload Identity Provider for GitHub OIDC
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = data.google_project.nyc_taxi_project.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_pool.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-provider"
  display_name                       = "GitHub Provider"

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }

  attribute_condition = "assertion.repository == '${var.github_repository}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

# Allow GitHub Actions to impersonate the service account
resource "google_service_account_iam_member" "github_actions_impersonation" {
  service_account_id = google_service_account.nyc_taxi_sa.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_pool.name}/attribute.repository/${var.github_repository}"
}

# =============================================================================
# IAM ROLES
# =============================================================================

# IAM: Storage Admin for GCS bucket management
resource "google_project_iam_member" "storage_admin" {
  project = data.google_project.nyc_taxi_project.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# IAM: BigQuery Data Editor for data operations
resource "google_project_iam_member" "bigquery_data_editor" {
  project = data.google_project.nyc_taxi_project.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# IAM: BigQuery Job User for running queries
resource "google_project_iam_member" "bigquery_job_user" {
  project = data.google_project.nyc_taxi_project.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# =============================================================================
# GOOGLE CLOUD STORAGE (GCS) BUCKETS
# =============================================================================

# Single GCS Bucket for NYC Taxi Pipeline
resource "google_storage_bucket" "nyc_taxi_etl" {
  name          = local.full_bucket_id
  location      = var.region
  project       = data.google_project.nyc_taxi_project.project_id
  force_destroy = true

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    environment = var.environment
    project     = var.project_id_base
  }

  depends_on = [google_project_service.storage]
}

# IAM binding for service account to access bucket
resource "google_storage_bucket_iam_member" "pipeline_bucket_access" {
  bucket = google_storage_bucket.nyc_taxi_etl.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

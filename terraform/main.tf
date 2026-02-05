# =============================================================================
# GCP PROJECT (created within Organization - fully automated)
# =============================================================================

# Create GCP Project within Organization
resource "google_project" "nyc_taxi_project" {
  name            = "${var.project_name} (${var.environment})"
  project_id      = local.full_project_id
  org_id          = var.organisation_id
  billing_account = var.billing_account_id

  auto_create_network = false

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    project     = var.project_id_base
  }
}

# =============================================================================
# ENABLE REQUIRED APIS
# =============================================================================

# Enable Cloud Resource Manager API (required for project operations)
resource "google_project_service" "cloudresourcemanager" {
  project = google_project.nyc_taxi_project.project_id
  service = "cloudresourcemanager.googleapis.com"

  disable_on_destroy = false
}

# Enable Cloud Billing API
resource "google_project_service" "cloudbilling" {
  project = google_project.nyc_taxi_project.project_id
  service = "cloudbilling.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# Enable IAM API
resource "google_project_service" "iam" {
  project = google_project.nyc_taxi_project.project_id
  service = "iam.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# Enable IAM Service Account Credentials API (required for Workload Identity Federation)
resource "google_project_service" "iamcredentials" {
  project = google_project.nyc_taxi_project.project_id
  service = "iamcredentials.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.iam]
}

# Enable Service Usage API (required for listing/managing project services)
resource "google_project_service" "serviceusage" {
  project = google_project.nyc_taxi_project.project_id
  service = "serviceusage.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# Enable Cloud Storage API
resource "google_project_service" "storage" {
  project = google_project.nyc_taxi_project.project_id
  service = "storage.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# Enable Security Token Service API (required for Workload Identity Federation)
resource "google_project_service" "sts" {
  project = google_project.nyc_taxi_project.project_id
  service = "sts.googleapis.com"

  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# =============================================================================
# SERVICE ACCOUNT
# =============================================================================

# Service Account for the pipeline
resource "google_service_account" "nyc_taxi_sa" {
  account_id   = "${var.project_id_base}-${var.environment}-sa-${var.instance_number}"
  display_name = "NYC Taxi Pipeline Service Account (${var.environment})"
  project      = google_project.nyc_taxi_project.project_id

  depends_on = [google_project_service.iam]
}

# =============================================================================
# WORKLOAD IDENTITY FEDERATION (for GitHub Actions)
# =============================================================================

# Workload Identity Pool for GitHub Actions
resource "google_iam_workload_identity_pool" "github_pool" {
  project                   = google_project.nyc_taxi_project.project_id
  workload_identity_pool_id = "github-actions-pool"
  display_name              = "GitHub Actions Pool"
  description               = "Identity pool for GitHub Actions CI/CD"

  depends_on = [google_project_service.iam, google_project_service.sts]
}

# Workload Identity Provider for GitHub OIDC
resource "google_iam_workload_identity_pool_provider" "github_provider" {
  project                            = google_project.nyc_taxi_project.project_id
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
# IAM ROLES FOR SERVICE ACCOUNT (Project-Level Permissions)
# =============================================================================
# With Organization, we can grant project-level IAM roles directly via Terraform

# Storage Admin - manage GCS buckets and objects
resource "google_project_iam_member" "storage_admin" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# Service Usage Admin - manage API enablement
resource "google_project_iam_member" "service_usage_admin" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/serviceusage.serviceUsageAdmin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# IAM Service Account Admin - manage service accounts
resource "google_project_iam_member" "iam_sa_admin" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/iam.serviceAccountAdmin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# Workload Identity Pool Admin - manage WIF pools and providers
resource "google_project_iam_member" "wif_admin" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/iam.workloadIdentityPoolAdmin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# Project IAM Admin - manage project IAM policies (needed for self-management)
resource "google_project_iam_member" "project_iam_admin" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/resourcemanager.projectIamAdmin"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# Editor - general project editing permissions
resource "google_project_iam_member" "editor" {
  project = google_project.nyc_taxi_project.project_id
  role    = "roles/editor"
  member  = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"

  depends_on = [google_service_account.nyc_taxi_sa]
}

# =============================================================================
# GOOGLE CLOUD STORAGE (GCS) BUCKETS
# =============================================================================

# GCS Bucket for NYC Taxi Pipeline data
resource "google_storage_bucket" "nyc_taxi_etl" {
  name          = local.full_bucket_id
  location      = var.region
  project       = google_project.nyc_taxi_project.project_id
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

# =============================================================================
# TERRAFORM STATE BUCKET (created in the project for state management)
# =============================================================================

# GCS Bucket for Terraform state
resource "google_storage_bucket" "terraform_state" {
  name          = "${var.project_id_base}-tfstate-${var.environment}"
  location      = var.region
  project       = google_project.nyc_taxi_project.project_id
  force_destroy = false

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  labels = {
    purpose     = "terraform-state"
    environment = var.environment
    project     = var.project_id_base
  }

  depends_on = [google_project_service.storage]
}

# =============================================================================
# BUCKET-LEVEL IAM BINDINGS
# =============================================================================
# Additional granular bucket-level permissions

# Storage Object Admin - full control over objects in the data bucket
resource "google_storage_bucket_iam_member" "pipeline_bucket_object_admin" {
  bucket = google_storage_bucket.nyc_taxi_etl.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# Storage Legacy Bucket Reader - allows listing bucket contents
resource "google_storage_bucket_iam_member" "pipeline_bucket_reader" {
  bucket = google_storage_bucket.nyc_taxi_etl.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# Storage Legacy Bucket Writer - allows creating/deleting objects
resource "google_storage_bucket_iam_member" "pipeline_bucket_writer" {
  bucket = google_storage_bucket.nyc_taxi_etl.name
  role   = "roles/storage.legacyBucketWriter"
  member = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

# Terraform state bucket - admin access for state management
resource "google_storage_bucket_iam_member" "tfstate_bucket_admin" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.nyc_taxi_sa.email}"
}

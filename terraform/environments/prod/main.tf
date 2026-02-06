# =============================================================================
# PRODUCTION ENVIRONMENT - TERRAFORM CONFIGURATION
# =============================================================================
# This module creates production infrastructure for NYC Taxi ETL pipeline:
# - GCP Project (created within Organization)
# - Cloud Composer (managed Airflow) for DAG orchestration
# - Cloud Run for ETL job execution
# - BigQuery dataset and tables for data warehouse
# - IAM roles and service accounts with proper permissions
# =============================================================================

# =============================================================================
# GCP PROJECT (created within Organization - fully automated)
# =============================================================================

resource "google_project" "prod_project" {
  name            = "${var.project_name} - ${var.environment}"
  project_id      = var.project_id
  org_id          = var.organisation_id
  billing_account = var.billing_account_id

  auto_create_network = false

  labels = local.common_labels
}

# =============================================================================
# ENABLE FOUNDATIONAL APIS (required before any other resources)
# =============================================================================

resource "google_project_service" "cloudresourcemanager" {
  project            = google_project.prod_project.project_id
  service            = "cloudresourcemanager.googleapis.com"
  disable_on_destroy = false
}

resource "google_project_service" "iam" {
  project            = google_project.prod_project.project_id
  service            = "iam.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "serviceusage" {
  project            = google_project.prod_project.project_id
  service            = "serviceusage.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "storage" {
  project            = google_project.prod_project.project_id
  service            = "storage.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# =============================================================================
# ENABLE REQUIRED APIS
# =============================================================================

resource "google_project_service" "composer" {
  project            = google_project.prod_project.project_id
  service            = "composer.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "cloudrun" {
  project            = google_project.prod_project.project_id
  service            = "run.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "bigquery" {
  project            = google_project.prod_project.project_id
  service            = "bigquery.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "artifactregistry" {
  project            = google_project.prod_project.project_id
  service            = "artifactregistry.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "cloudbuild" {
  project            = google_project.prod_project.project_id
  service            = "cloudbuild.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "vpcaccess" {
  project            = google_project.prod_project.project_id
  service            = "vpcaccess.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

resource "google_project_service" "compute" {
  project            = google_project.prod_project.project_id
  service            = "compute.googleapis.com"
  disable_on_destroy = false

  depends_on = [google_project_service.cloudresourcemanager]
}

# =============================================================================
# VPC NETWORK FOR CLOUD RUN EGRESS
# =============================================================================
# Cloud Run needs VPC access to make outbound HTTPS calls to external URLs
# like https://d37ci6vzurychx.cloudfront.net for NYC TLC data ingestion

# VPC Network
resource "google_compute_network" "etl_vpc" {
  name                    = "${var.project_id_base}-${var.environment}-etl-vpc"
  project                 = google_project.prod_project.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.compute]
}

# Subnet for Cloud Run VPC Connector
resource "google_compute_subnetwork" "etl_subnet" {
  name          = "${var.project_id_base}-${var.environment}-etl-subnet"
  project       = google_project.prod_project.project_id
  region        = var.region
  network       = google_compute_network.etl_vpc.id
  ip_cidr_range = "10.8.0.0/28" # /28 is minimum for VPC connector

  private_ip_google_access = true
}

# Cloud Router for NAT
resource "google_compute_router" "etl_router" {
  name    = "${var.project_id_base}-${var.environment}-etl-router"
  project = google_project.prod_project.project_id
  region  = var.region
  network = google_compute_network.etl_vpc.id
}

# Cloud NAT for outbound internet access
# Required for Cloud Run to reach external URLs (NYC TLC CloudFront)
resource "google_compute_router_nat" "etl_nat" {
  name                               = "${var.project_id_base}-${var.environment}-etl-nat"
  project                            = google_project.prod_project.project_id
  router                             = google_compute_router.etl_router.name
  region                             = var.region
  nat_ip_allocate_option             = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat = "ALL_SUBNETWORKS_ALL_IP_RANGES"

  log_config {
    enable = true
    filter = "ERRORS_ONLY"
  }
}

# VPC Connector for Cloud Run
resource "google_vpc_access_connector" "etl_connector" {
  name          = "${var.project_id_base}-${var.environment}-vpc-conn"
  project       = google_project.prod_project.project_id
  region        = var.region
  network       = google_compute_network.etl_vpc.id
  ip_cidr_range = "10.8.0.16/28" # Different range from subnet

  min_instances = 2
  max_instances = 10

  depends_on = [
    google_project_service.vpcaccess,
    google_compute_network.etl_vpc
  ]
}

# Firewall rule: Allow outbound HTTPS traffic to external URLs
resource "google_compute_firewall" "allow_egress_https" {
  name    = "${var.project_id_base}-${var.environment}-allow-egress-https"
  project = google_project.prod_project.project_id
  network = google_compute_network.etl_vpc.name

  direction = "EGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["443"]
  }

  # Allow HTTPS to any destination (NYC TLC CloudFront CDN)
  destination_ranges = ["0.0.0.0/0"]

  description = "Allow outbound HTTPS traffic for ETL data ingestion from NYC TLC"
}

# Firewall rule: Allow internal communication within VPC
resource "google_compute_firewall" "allow_internal" {
  name    = "${var.project_id_base}-${var.environment}-allow-internal"
  project = google_project.prod_project.project_id
  network = google_compute_network.etl_vpc.name

  direction = "INGRESS"
  priority  = 1000

  allow {
    protocol = "tcp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "udp"
    ports    = ["0-65535"]
  }

  allow {
    protocol = "icmp"
  }

  source_ranges = ["10.8.0.0/24"]

  description = "Allow internal communication within ETL VPC"
}

# =============================================================================
# SERVICE ACCOUNTS
# =============================================================================

# Service Account for Cloud Composer
resource "google_service_account" "composer_sa" {
  account_id   = local.composer_sa_name
  display_name = "Cloud Composer Service Account (${var.environment})"
  description  = "Service account for Cloud Composer to orchestrate ETL pipelines"
  project      = google_project.prod_project.project_id

  depends_on = [google_project_service.composer]
}

# Service Account for Cloud Run (ETL job execution)
resource "google_service_account" "cloud_run_sa" {
  account_id   = local.cloud_run_sa_name
  display_name = "Cloud Run Service Account (${var.environment})"
  description  = "Service account for Cloud Run to execute ETL jobs"
  project      = google_project.prod_project.project_id

  depends_on = [google_project_service.cloudrun]
}

# Service Account for ETL operations (BigQuery, GCS access)
resource "google_service_account" "etl_sa" {
  account_id   = local.etl_sa_name
  display_name = "ETL Service Account (${var.environment})"
  description  = "Service account for ETL operations - BigQuery and GCS access"
  project      = google_project.prod_project.project_id
}

# =============================================================================
# GCS BUCKET FOR PRODUCTION DATA
# =============================================================================

resource "google_storage_bucket" "prod_data" {
  name          = local.gcs_bucket_name
  location      = var.region
  project       = google_project.prod_project.project_id
  force_destroy = false # Protect production data

  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      age = 90
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  lifecycle_rule {
    condition {
      age = 365
    }
    action {
      type          = "SetStorageClass"
      storage_class = "COLDLINE"
    }
  }

  labels = local.common_labels
}

# =============================================================================
# BIGQUERY DATASET
# =============================================================================

resource "google_bigquery_dataset" "taxi" {
  dataset_id    = local.bigquery_dataset
  friendly_name = "NYC Taxi Data Warehouse"
  description   = "Production data warehouse for NYC Taxi ETL pipeline - dimensional model"
  location      = var.region
  project       = google_project.prod_project.project_id

  labels = local.common_labels

  access {
    role          = "OWNER"
    user_by_email = google_service_account.etl_sa.email
  }

  access {
    role          = "WRITER"
    user_by_email = google_service_account.cloud_run_sa.email
  }

  access {
    role          = "READER"
    user_by_email = google_service_account.composer_sa.email
  }

  depends_on = [google_project_service.bigquery]
}

# =============================================================================
# CLOUD COMPOSER (MANAGED AIRFLOW)
# =============================================================================

resource "google_composer_environment" "prod" {
  name    = local.composer_name
  region  = var.region
  project = google_project.prod_project.project_id

  config {
    software_config {
      image_version = var.composer_image_version

      airflow_config_overrides = {
        core-dags_are_paused_at_creation = "false"
        core-load_examples               = "false"
        webserver-expose_config          = "true"
      }

      env_variables = {
        ENVIRONMENT      = var.environment
        GCS_BUCKET       = local.gcs_bucket_name
        GCP_PROJECT_ID   = google_project.prod_project.project_id
        BIGQUERY_DATASET = local.bigquery_dataset
        CLOUD_RUN_URL    = google_cloud_run_v2_service.etl_runner.uri
      }

      pypi_packages = {
        "apache-airflow-providers-google" = ">=10.0.0"
        "google-cloud-bigquery"           = ">=3.0.0"
        "google-cloud-storage"            = ">=2.0.0"
      }
    }

    workloads_config {
      scheduler {
        cpu        = 1
        memory_gb  = 2
        storage_gb = 1
        count      = 1
      }
      web_server {
        cpu        = 1
        memory_gb  = 2
        storage_gb = 1
      }
      worker {
        cpu        = 2
        memory_gb  = 4
        storage_gb = 2
        min_count  = 1
        max_count  = 3
      }
    }

    environment_size = "ENVIRONMENT_SIZE_SMALL"

    node_config {
      service_account = google_service_account.composer_sa.email
    }
  }

  labels = local.common_labels

  depends_on = [
    google_project_service.composer,
    google_service_account.composer_sa,
    google_project_iam_member.composer_worker,
    google_cloud_run_v2_service.etl_runner
  ]
}

# =============================================================================
# CLOUD RUN SERVICE (ETL JOB RUNNER)
# =============================================================================

resource "google_cloud_run_v2_service" "etl_runner" {
  name     = local.cloud_run_name
  location = var.region
  project  = google_project.prod_project.project_id

  template {
    service_account = google_service_account.cloud_run_sa.email

    # VPC Access for outbound HTTPS calls to NYC TLC CloudFront
    vpc_access {
      connector = google_vpc_access_connector.etl_connector.id
      egress    = "ALL_TRAFFIC" # Route all traffic through VPC for NAT
    }

    containers {
      image = var.etl_container_image != "" ? var.etl_container_image : "gcr.io/cloudrun/hello"

      resources {
        limits = {
          cpu    = "4"
          memory = "8Gi"
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCS_BUCKET"
        value = local.gcs_bucket_name
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = google_project.prod_project.project_id
      }
      env {
        name  = "BIGQUERY_DATASET"
        value = local.bigquery_dataset
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "3600s" # 1 hour timeout for long-running ETL jobs
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  labels = local.common_labels

  depends_on = [
    google_project_service.cloudrun,
    google_vpc_access_connector.etl_connector
  ]
}

# =============================================================================
# ARTIFACT REGISTRY (FOR CONTAINER IMAGES)
# =============================================================================

resource "google_artifact_registry_repository" "etl_images" {
  location      = var.region
  repository_id = "${var.project_id_base}-${var.environment}-etl-images"
  description   = "Container images for ETL jobs"
  format        = "DOCKER"
  project       = google_project.prod_project.project_id

  labels = local.common_labels

  depends_on = [google_project_service.artifactregistry]
}

# =============================================================================
# IAM ROLES - CLOUD COMPOSER SERVICE ACCOUNT
# =============================================================================

# Composer Worker role (required for Composer)
resource "google_project_iam_member" "composer_worker" {
  project = google_project.prod_project.project_id
  role    = "roles/composer.worker"
  member  = "serviceAccount:${google_service_account.composer_sa.email}"
}

# GCS access for Composer (read/write to prod bucket)
resource "google_storage_bucket_iam_member" "composer_gcs_object_admin" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.composer_sa.email}"
}

resource "google_storage_bucket_iam_member" "composer_gcs_bucket_reader" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.composer_sa.email}"
}

# Cloud Run invoker (to trigger ETL jobs)
resource "google_cloud_run_v2_service_iam_member" "composer_invoke_cloudrun" {
  project  = google_project.prod_project.project_id
  location = var.region
  name     = google_cloud_run_v2_service.etl_runner.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.composer_sa.email}"
}

# BigQuery read access (for monitoring/validation)
resource "google_project_iam_member" "composer_bigquery_viewer" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.composer_sa.email}"
}

# =============================================================================
# IAM ROLES - CLOUD RUN SERVICE ACCOUNT
# =============================================================================

# GCS access for Cloud Run (read/write to prod bucket)
resource "google_storage_bucket_iam_member" "cloudrun_gcs_object_admin" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_storage_bucket_iam_member" "cloudrun_gcs_bucket_reader" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# BigQuery write access for Cloud Run (ETL jobs write to BigQuery)
resource "google_project_iam_member" "cloudrun_bigquery_data_editor" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

resource "google_project_iam_member" "cloudrun_bigquery_job_user" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# =============================================================================
# IAM ROLES - ETL SERVICE ACCOUNT
# =============================================================================

# GCS full access for ETL operations
resource "google_storage_bucket_iam_member" "etl_gcs_object_admin" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.etl_sa.email}"
}

resource "google_storage_bucket_iam_member" "etl_gcs_bucket_reader" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.legacyBucketReader"
  member = "serviceAccount:${google_service_account.etl_sa.email}"
}

resource "google_storage_bucket_iam_member" "etl_gcs_bucket_writer" {
  bucket = google_storage_bucket.prod_data.name
  role   = "roles/storage.legacyBucketWriter"
  member = "serviceAccount:${google_service_account.etl_sa.email}"
}

# BigQuery full access for ETL operations
resource "google_project_iam_member" "etl_bigquery_data_editor" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.etl_sa.email}"
}

resource "google_project_iam_member" "etl_bigquery_job_user" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.etl_sa.email}"
}

resource "google_project_iam_member" "etl_bigquery_data_owner" {
  project = google_project.prod_project.project_id
  role    = "roles/bigquery.dataOwner"
  member  = "serviceAccount:${google_service_account.etl_sa.email}"
}

# =============================================================================
# CROSS-SERVICE IAM BINDINGS
# =============================================================================

# Allow Cloud Run to act as ETL SA (for BigQuery operations)
resource "google_service_account_iam_member" "cloudrun_act_as_etl" {
  service_account_id = google_service_account.etl_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.cloud_run_sa.email}"
}

# Allow Composer to act as Cloud Run SA (for invoking Cloud Run)
resource "google_service_account_iam_member" "composer_act_as_cloudrun" {
  service_account_id = google_service_account.cloud_run_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.composer_sa.email}"
}

# =============================================================================
# IAM ROLES - CI/CD SERVICE ACCOUNT (from dev environment)
# =============================================================================
# Grant the CI/CD service account permissions to deploy to production

# Artifact Registry Admin - push container images (includes uploadArtifacts permission)
resource "google_artifact_registry_repository_iam_member" "cicd_artifact_registry_admin" {
  project    = google_project.prod_project.project_id
  location   = var.region
  repository = google_artifact_registry_repository.etl_images.name
  role       = "roles/artifactregistry.repoAdmin"
  member     = "serviceAccount:${var.cicd_service_account}"
}

# Cloud Run Admin - deploy and update Cloud Run services
resource "google_project_iam_member" "cicd_cloudrun_admin" {
  project = google_project.prod_project.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${var.cicd_service_account}"
}

# Service Account User - allow CI/CD to act as Cloud Run SA
resource "google_service_account_iam_member" "cicd_act_as_cloudrun" {
  service_account_id = google_service_account.cloud_run_sa.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${var.cicd_service_account}"
}

# Storage Admin - upload DAGs to Composer bucket
resource "google_project_iam_member" "cicd_storage_admin" {
  project = google_project.prod_project.project_id
  role    = "roles/storage.admin"
  member  = "serviceAccount:${var.cicd_service_account}"
}

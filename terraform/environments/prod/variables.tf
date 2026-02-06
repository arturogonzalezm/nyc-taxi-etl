# =============================================================================
# VARIABLES
# =============================================================================

variable "project_id" {
  description = "GCP Project ID for production environment"
  type        = string
}

variable "region" {
  description = "GCP Region for resources"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone for resources"
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prod"
}

variable "project_id_base" {
  description = "Base name for project resources"
  type        = string
  default     = "nyc-taxi-etl"
}

variable "composer_image_version" {
  description = "Cloud Composer image version"
  type        = string
  default     = "composer-2.9.7-airflow-2.9.3"
}

variable "etl_container_image" {
  description = "Container image for ETL jobs (Cloud Run)"
  type        = string
  default     = ""
}

variable "cicd_service_account" {
  description = "Service account email used by CI/CD pipeline (from dev environment)"
  type        = string
}

# =============================================================================
# LOCAL VALUES
# =============================================================================

locals {
  # Resource naming convention: {project_id_base}-{environment}-{resource_type}-{region}-{instance}
  composer_name    = "${var.project_id_base}-${var.environment}-composer"
  cloud_run_name   = "${var.project_id_base}-${var.environment}-etl-runner"
  bigquery_dataset = "taxi"
  gcs_bucket_name  = "${var.project_id_base}-${var.environment}-gcs-${var.region}-001"

  # Service account names
  composer_sa_name  = "${var.project_id_base}-${var.environment}-composer-sa"
  cloud_run_sa_name = "${var.project_id_base}-${var.environment}-cloudrun-sa"
  etl_sa_name       = "${var.project_id_base}-${var.environment}-etl-sa"

  # Common labels
  common_labels = {
    environment = var.environment
    project     = var.project_id_base
    managed_by  = "terraform"
  }
}

# =============================================================================
# PROJECT CONFIGURATION
# =============================================================================

variable "project_id_base" {
  description = "GCP Project ID base name"
  type        = string
  default     = "nyc-taxi-etl"
}

variable "project_name" {
  description = "GCP Project display name"
  type        = string
  default     = "NYC Taxi Pipeline"
}

variable "billing_account_id" {
  description = "GCP Billing Account ID"
  type        = string
  sensitive   = true
}

# =============================================================================
# LOCATION CONFIGURATION
# =============================================================================

variable "region" {
  description = "GCP Region"
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "GCP Zone"
  type        = string
  default     = "us-central1-a"
}

# =============================================================================
# ENVIRONMENT CONFIGURATION
# =============================================================================

variable "environment" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be one of: dev, prod."
  }
}

variable "instance_number" {
  description = "Instance number for resource naming (e.g., 001, 002)"
  type        = string
  default     = "001"
}

variable "bucket_suffix" {
  description = "Bucket suffix number (e.g., 001, 002)"
  type        = string
  default     = "001"
}

variable "resource_type" {
  description = "GCP Resource (e.g., gcs, sa, iam, bigquery, cr, cc, network, etc)"
  type        = string
  default     = "gcs"

  validation {
    condition     = contains(["gcs", "sa", "iam", "bigquery", "cr", "cc", "network"], var.resource_type)
    error_message = "Resource type must be one of: gcs, sa, iam, bigquery."
  }
}


# =============================================================================
# GITHUB CONFIGURATION
# =============================================================================

variable "github_repository" {
  description = "GitHub repository in format 'owner/repo' for Workload Identity Federation"
  type        = string
}

# =============================================================================
# LOCAL VALUES
# =============================================================================

locals {
  # Construct the full project ID: nyc-taxi-etl-dev-001 (max 30 chars)
  full_project_id = "${var.project_id_base}-${var.environment}-${var.instance_number}"
  full_bucket_id  = "${var.project_id_base}-${var.environment}-${var.resource_type}-${var.region}-${var.bucket_suffix}"
}

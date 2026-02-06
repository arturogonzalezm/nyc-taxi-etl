# =============================================================================
# NYC Taxi ETL - Prod Environment Configuration
# =============================================================================
# This file contains NON-SENSITIVE configuration values for the prod environment.
# Sensitive values are stored in GitHub Secrets.
#
# This is the SINGLE SOURCE OF TRUTH for prod environment configuration.
# =============================================================================

# Project naming
project_id_base = "nyc-taxi-etl"

# Instance numbering
instance_number = "003"

# Resource type for bucket naming
resource_type = "gcs"

# GCP Region
region = "us-central1"
zone   = "us-central1-a"

# Environment
environment = "prod"

# Cloud Composer configuration
composer_image_version = "composer-2.9.7-airflow-2.9.3"

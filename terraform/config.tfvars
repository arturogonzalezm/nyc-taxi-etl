# =============================================================================
# NYC Taxi ETL - Shared Configuration
# =============================================================================
# This file contains NON-SENSITIVE configuration values that are shared across
# all environments. Sensitive values (billing_account_id, organisation_id) are
# stored in GitHub Secrets.
#
# This is the SINGLE SOURCE OF TRUTH for project configuration.
# =============================================================================

# Project naming
project_id_base = "nyc-taxi-etl"
project_name    = "NYC Taxi Pipeline"

# Instance numbering
instance_number = "002"
bucket_suffix   = "002"

# Resource type for bucket naming
resource_type = "gcs"

# GCP Region
region = "us-central1"
zone   = "us-central1-a"

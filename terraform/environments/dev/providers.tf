terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # =============================================================================
  # REMOTE BACKEND FOR TERRAFORM STATE
  # =============================================================================
  # FIRST RUN: Comment out the backend block, run locally with your credentials
  # AFTER FIRST RUN: Uncomment and run: terraform init -migrate-state
  #
  # backend "gcs" {
  #   bucket = "nyc-taxi-etl-tfstate-dev"  # Change to -prod for production
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  # Authentication (in order of precedence):
  # 1. CI/CD: Workload Identity Federation (automatic)
  # 2. Local: gcloud auth application-default login
}

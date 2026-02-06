terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = ">= 5.0.0"
    }
  }

  # =============================================================================
  # REMOTE BACKEND FOR TERRAFORM STATE
  # =============================================================================
  # FIRST RUN: Comment out the backend block, run locally with your credentials
  # AFTER FIRST RUN: Uncomment and run: terraform init -migrate-state
  #
  # backend "gcs" {
  #   bucket = "nyc-taxi-etl-tfstate-prod"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  # Authentication (in order of precedence):
  # 1. CI/CD: Workload Identity Federation (automatic)
  # 2. Local: gcloud auth application-default login
}

provider "google-beta" {
  # Authentication (in order of precedence):
  # 1. CI/CD: Workload Identity Federation (automatic)
  # 2. Local: gcloud auth application-default login
}

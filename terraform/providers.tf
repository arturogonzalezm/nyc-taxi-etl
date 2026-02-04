terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Remote backend for shared state (uncomment after creating the bucket)
  # For organizations: This enables fully automatic deployments
  # For individuals without org: Create the state bucket manually first, then uncomment
  #
  # backend "gcs" {
  #   bucket = "nyc-taxi-etl-tfstate"
  #   prefix = "terraform/state"
  # }
}

provider "google" {
  # Uses ADC from:
  # - Local: gcloud auth application-default login
  # - CI/CD: Workload Identity Federation
}

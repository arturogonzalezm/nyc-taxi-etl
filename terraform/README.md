# Terraform Infrastructure for NYC Taxi ETL

This directory contains Terraform configuration for provisioning Google Cloud Platform (GCP) infrastructure for the NYC Taxi ETL project.

---

## Quick Start

### For Organizations (Fully Automatic)

If you have a GCP organization, everything can be deployed automatically via CI/CD:

1. Create a service account with `roles/owner` at the organization level
2. Set up Workload Identity Federation for GitHub Actions
3. Add GitHub secrets and push - CI/CD handles the rest

### For Individuals (No Organization)

Run the bootstrap script once to set up the initial infrastructure:

```bash
cd terraform

# Set required environment variables
export BILLING_ACCOUNT_ID="XXXXXX-XXXXXX-XXXXXX"
export GITHUB_REPOSITORY="owner/repo"

# Run bootstrap (creates project, service account, state bucket, etc.)
./bootstrap.sh dev   # For development environment
./bootstrap.sh prod  # For production environment

# The script outputs the GitHub secrets you need to add
```

After bootstrap:
1. Add the secrets to GitHub (Settings > Secrets > Actions)
2. Uncomment the backend configuration in `providers.tf`
3. Run `terraform init -migrate-state` to move state to GCS
4. Push to GitHub - CI/CD handles everything from now on!

---

## Terraform Structure

### File Organization

| File | Purpose | Contents |
|------|---------|----------|
| `main.tf` | Module invocation | Calls the `modules/etl_infrastructure` module with environment variables |
| `variables.tf` | Input variable declarations | All configurable parameters with types, defaults, and descriptions |
| `outputs.tf` | Output value definitions | Values exported from the module for CI/CD and documentation |
| `providers.tf` | Provider configuration | Google Cloud provider version constraints and authentication settings |
| `terraform.tfvars` | Variable values | Environment-specific configuration (not committed to version control) |
| `modules/etl_infrastructure/*` | Reusable module | GCP project, service account, GCS bucket, Workload Identity Federation, IAM bindings |

### Resource Grouping in main.tf

The `main.tf` file is organized into logical sections:

```hcl
# =============================================================================
# GCP PROJECT
# =============================================================================
# - google_project.nyc_taxi_project
# - google_project_service.* (API enablement)
# - google_service_account.nyc_taxi_sa

# =============================================================================
# WORKLOAD IDENTITY FEDERATION (for GitHub Actions)
# =============================================================================
# - google_iam_workload_identity_pool.github_pool
# - google_iam_workload_identity_pool_provider.github_provider
# - google_service_account_iam_member.github_actions_impersonation

# =============================================================================
# IAM ROLES
# =============================================================================
# - google_project_iam_member.storage_admin
# - google_project_iam_member.bigquery_data_editor
# - google_project_iam_member.bigquery_job_user

# =============================================================================
# GOOGLE CLOUD STORAGE (GCS) BUCKETS
# =============================================================================
# - google_storage_bucket.nyc_taxi_bucket
# - google_storage_bucket_iam_member.pipeline_bucket_access
```

---

## Architecture and Design

### Design Principles

1. **Infrastructure as Code (IaC)**: All resources are defined declaratively in Terraform, enabling version control, code review, and reproducible deployments.

2. **Least Privilege Access**: Service accounts are granted only the minimum permissions required for pipeline operations.

3. **Environment Isolation**: The naming convention supports multiple environments (dev, prod) with isolated resources.

4. **Secure CI/CD Integration**: Workload Identity Federation eliminates the need for long-lived service account keys in GitHub Actions.

### Resource Dependencies

```
┌─────────────────────────────────────────────────────────────────┐
│                        GCP Project                              │
│         (${project_id_base}-${environment}-${region}-${instance_number})    │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│ Service Account │  │   GCS Bucket    │  │ Workload Identity│
│ (nyc-taxi-acct) │  │ (data storage)  │  │   Federation     │
└─────────────────┘  └─────────────────┘  └─────────────────┘
          │                   │                   │
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                         IAM Bindings                            │
│  - Storage Admin          - BigQuery Data Editor                │
│  - BigQuery Job User      - Workload Identity User              │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **GitHub Actions** authenticates via Workload Identity Federation
2. **Terraform** provisions and manages infrastructure
3. **ETL Pipeline** uses the service account to read/write data to GCS
4. **BigQuery** (future) will consume data from GCS for analytics

---

## State Management

Terraform state is currently stored locally. For production environments, consider:

- **Remote State**: Store state in a GCS bucket with versioning enabled
- **State Locking**: Use Cloud Storage object locking to prevent concurrent modifications
- **State Encryption**: Enable default encryption on the state bucket

---

## Resources Created

| Resource Type | Name/Identifier | Description |
|---------------|-----------------|-------------|
| GCP Project | `${project_id_base}-${environment}-${region}-${instance_number}` | Primary project for all resources |
| Service Account (Pipeline) | `${project_id_base}-${environment}-sa-${instance_number}@<project_id>.iam.gserviceaccount.com` | Service account for CI/CD and infrastructure management |
| Service Account (Airflow) | `${project_id_base}-${environment}-airflow-${instance_number}@<project_id>.iam.gserviceaccount.com` | Service account for Airflow (GCS read/write only) |
| GCS Bucket | `${project_id_base}-${environment}-gcs-${region}-${instance_number}` | Data lake storage bucket |
| Workload Identity Pool | `github-actions-pool` | Identity pool for GitHub Actions |
| Workload Identity Provider | `github-provider` | OIDC provider for GitHub authentication |

### IAM Roles Assigned

#### Pipeline Service Account (CI/CD)

The pipeline service account is granted the following project-level roles:

- `roles/editor` - General project editing permissions
- `roles/storage.admin` - Full control of GCS resources
- `roles/serviceusage.serviceUsageAdmin` - Manage API enablement
- `roles/iam.serviceAccountAdmin` - Manage service accounts
- `roles/iam.workloadIdentityPoolAdmin` - Manage WIF pools and providers
- `roles/resourcemanager.projectIamAdmin` - Manage project IAM policies

#### Airflow Service Account (Local Docker-Compose)

The Airflow service account follows the **principle of least privilege** and is granted **only** bucket-level permissions:

- `roles/storage.objectAdmin` - Read/write/delete objects in the GCS bucket
- `roles/storage.legacyBucketReader` - List bucket contents

This service account is designed for Apache Airflow running locally via docker-compose. It can **only** read and write to the GCS bucket - no other GCP permissions are granted.

---

## Configuration Variables

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `project_id_base` | string | `nyc-taxi-etl` | Base for GCP Project ID |
| `project_name` | string | `NYC Taxi ETL` | GCP Project display name |
| `billing_account_id` | string | - | GCP Billing Account ID (required) |
| `region` | string | `us-central1` | GCP Region |
| `zone` | string | `us-central1-a` | GCP Zone |
| `environment` | string | `dev` | Environment name (dev, prod) |
| `instance_number` | string | `001` | Instance number for uniqueness |
| `instance_number` | string | `001` | Instance number for resource naming |
| `resource_type` | string | `gcs` | Resource discriminator used in bucket naming |
| `github_repository` | string | - | GitHub repository for Workload Identity Federation (required) |

---

## Outputs

| Output | Description |
|--------|-------------|
| `project_id` | The GCP project ID |
| `project_number` | The GCP project number |
| `service_account_email` | Email of the pipeline service account (CI/CD) |
| `airflow_service_account_email` | Email of the Airflow service account (GCS read/write only) |
| `gcs_bucket_name` | Name of the GCS bucket |
| `gcs_bucket_url` | URL of the GCS bucket |
| `workload_identity_provider` | Workload Identity Provider resource name |
| `workload_identity_pool` | Workload Identity Pool resource name |
| `airflow_iam_roles_assigned` | IAM roles assigned to the Airflow service account |

---

## Prerequisites

1. [Terraform](https://www.terraform.io/downloads) version 1.5.0 or higher
2. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (gcloud CLI)
3. GCP Billing Account with appropriate permissions
4. GitHub repository for CI/CD integration

---

## Deployment

### Automated Deployment (GitHub Actions)

Infrastructure is automatically deployed via GitHub Actions when changes are merged to the `main` branch.

Authentication uses Workload Identity Federation (no JSON keys). Configure these GitHub Secrets:

| Secret Name | Description |
|-------------|-------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Resource name of the Workload Identity Provider (output `workload_identity_provider`) |
| `GCP_SERVICE_ACCOUNT` | Email of the service account to impersonate (output `service_account_email`) |
| `GCP_BILLING_ACCOUNT_ID` | Billing account identifier |

#### Setting Up GitHub Secrets

The GitHub secrets aren't set up yet. You need to add them to your repository.

**Step 1:** Go to GitHub → Settings → Secrets and variables → Actions → New repository secret

**Step 2:** Add these secrets:

| Secret Name | How to get the value |
|-------------|----------------------|
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | Run: `terraform output workload_identity_provider` |
| `GCP_SERVICE_ACCOUNT` | Run: `terraform output service_account_email` |
| `GCP_BILLING_ACCOUNT_ID` | Your GCP billing account ID |

**Step 3:** Get the values locally:

```bash
cd terraform
terraform output workload_identity_provider
terraform output service_account_email
```

### Manual Deployment

```bash
# Authenticate with GCP
gcloud auth application-default login
gcloud config set project <YOUR_PROJECT_ID>

# Initialize Terraform
cd terraform
terraform init

# Review the execution plan
terraform plan

# Apply the configuration
terraform apply
```

---

## Clean Up

### Via GitHub Actions

Trigger the `destroy.yml` workflow manually from the Actions tab.

### Via Command Line

```bash
cd terraform
terraform destroy
```

**Warning**: This will permanently delete all resources including the GCS bucket and its contents.

# GCP Authentication Guide

This document describes the recommended authentication methods for accessing Google Cloud Platform (GCP) resources in the NYC Taxi ETL pipeline.

## Quick Start (Recommended)

After running `terraform apply`, set up authentication with a single command:

```bash
make setup
```

This generates Application Default Credentials (ADC) and grants your user the Token Creator role on the Airflow service account. The Spark GCS connector then impersonates the SA natively at runtime, giving you least-privilege GCS-only access without key files. See [How It Works](#how-it-works) for details.

---

## How It Works

The authentication uses **GCS connector native impersonation**:

1. You authenticate as yourself via `gcloud auth application-default login` (produces an `authorized_user` ADC file)
2. The `GCS_IMPERSONATE_SA` environment variable tells the Spark GCS connector which service account to impersonate
3. At runtime, the GCS connector exchanges your ADC token for short-lived SA credentials via the IAM API
4. All GCS requests use the SA's permissions (least-privilege, GCS bucket only)

This avoids the `impersonated_service_account type not recognized` error that older GCS connectors throw when reading ADC files generated with `--impersonate-service-account`.

> **Note:** The examples below use the default naming convention from `terraform/config.tfvars` (`instance_number = "003"`, `environment = "dev"`). If you changed these values, substitute accordingly. Run `terraform output airflow_service_account_email` to see your actual SA email.

### Prerequisites

- Google Cloud SDK installed and configured
- Terraform infrastructure deployed (`terraform apply`)
- `roles/iam.serviceAccountTokenCreator` on the Airflow SA (granted by `make setup`)

### Manual Setup (if not using `make setup`)

**Step 1: Grant Token Creator role**

```bash
gcloud iam service-accounts add-iam-policy-binding \
  nyc-taxi-etl-dev-airflow-003@nyc-taxi-etl-dev-003.iam.gserviceaccount.com \
  --member="user:$(gcloud config get account)" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=nyc-taxi-etl-dev-003
```

**Step 2: Generate ADC**

```bash
gcloud auth application-default login
```

This creates `authorized_user` credentials at `~/.config/gcloud/application_default_credentials.json`, which Docker mounts into the containers. The `GCS_IMPERSONATE_SA` env var (set in `.env`) tells the GCS connector to impersonate the Airflow SA at runtime.

---

## Comparison of Methods

| Method | Security | Use Case | Key Management |
|--------|----------|----------|----------------|
| **Service Account Impersonation** | High | Local development (recommended) | No keys required |
| **Workload Identity Federation** | High | Production, CI/CD | No keys required |
| **ADC (User Credentials)** | Medium | Quick local testing | No keys required |
| **Service Account Key File** | Lower | Legacy systems | Manual key rotation |

---

## Troubleshooting

### Common Issues

**1. Permission Denied**

If you receive a permission denied error:

```bash
# Verify your current authentication
gcloud auth list

# Check which credentials are being used
gcloud auth application-default print-access-token
```

**2. `impersonated_service_account type not recognized`**

This means the ADC file was generated with `--impersonate-service-account`. The GCS connector (hadoop3-2.2.x) cannot parse this credential type. Fix by regenerating plain ADC:

```bash
gcloud auth application-default login   # no --impersonate-service-account flag
```

The `GCS_IMPERSONATE_SA` env var handles impersonation at the connector level instead.

**3. Service Account Impersonation Fails**

Ensure you have the `roles/iam.serviceAccountTokenCreator` role:

```bash
gcloud projects get-iam-policy nyc-taxi-etl-dev-003 \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:$(gcloud config get account)"
```

**4. Bucket Access Denied**

Verify the Airflow SA has bucket access (Terraform should have granted this):

```bash
gcloud storage buckets get-iam-policy gs://nyc-taxi-etl-dev-gcs-us-central1-003
```

**5. Slow GCS Reads or Timeouts**

If you experience slow reads or `SocketTimeoutException` during Spark jobs, check that `GCS_IMPERSONATE_SA` is set in your `.env` — without it, requests use your user ADC directly which has lower API quotas.

---

## Security Best Practices

1. **Use GCS connector native impersonation** for local development (`make setup`)
2. **Use Workload Identity Federation** for CI/CD (configured automatically via Terraform)
3. **Never commit credentials** to version control
4. **Avoid service account key files** - use impersonation instead
5. **Use least-privilege IAM roles** - the Airflow SA only has GCS bucket access
6. **Enable audit logging** to track credential usage

---

## Related Documentation

- [Google Cloud Authentication Overview](https://cloud.google.com/docs/authentication)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Service Account Impersonation](https://cloud.google.com/iam/docs/impersonating-service-accounts)

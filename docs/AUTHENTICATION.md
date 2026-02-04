# GCP Authentication Guide

This document describes the recommended authentication methods for accessing Google Cloud Platform (GCP) resources in the NYC Taxi ETL pipeline.

## Authentication Methods

### 1. Workload Identity Federation with Service Account Impersonation (Recommended)

Workload Identity Federation allows you to use your Google account to impersonate a service account, eliminating the need for service account key files. This is the most secure approach for local development.

#### Prerequisites

- Google Cloud SDK installed and configured
- Access to the GCP project
- Permission to impersonate the service account

#### Setup Steps

**Step 1: Grant Service Account Token Creator Role**

First, grant yourself permission to impersonate the service account:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  nyc-taxi-etl-dev-sa-001@nyc-taxi-etl-dev-001.iam.gserviceaccount.com \
  --member="user:you@gmail.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=nyc-taxi-etl-dev-001
```

> **Note:** Replace `you@gmail.com` with your actual Google account email.

**Step 2: Authenticate with Impersonation**

```bash
gcloud auth application-default login \
  --impersonate-service-account=nyc-taxi-etl-dev-sa-001@nyc-taxi-etl-dev-001.iam.gserviceaccount.com
```

This creates Application Default Credentials (ADC) that automatically impersonate the service account.

---

### 2. Application Default Credentials (ADC)

For simpler setups or when service account impersonation is not required, you can use your own Google account credentials directly.

#### Setup Steps

**Step 1: Authenticate**

```bash
gcloud auth application-default login
```

This creates authorized_user credentials stored at:
- **Linux/macOS:** `~/.config/gcloud/application_default_credentials.json`
- **Windows:** `%APPDATA%\gcloud\application_default_credentials.json`

**Step 2: Grant Bucket Access**

Grant your user account direct access to the GCS bucket:

```bash
gcloud storage buckets add-iam-policy-binding \
  gs://nyc-taxi-etl-dev-gcs-us-central1-001 \
  --member="user:you@gmail.com" \
  --role="roles/storage.objectAdmin"
```

> **Note:** Replace `you@gmail.com` with your actual Google account email.

---

## Comparison of Methods

| Method | Security | Use Case | Key Management |
|--------|----------|----------|----------------|
| **Workload Identity Federation** | High | Production, CI/CD | No keys required |
| **Service Account Impersonation** | High | Local development | No keys required |
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

**2. Service Account Impersonation Fails**

Ensure you have the `roles/iam.serviceAccountTokenCreator` role:

```bash
gcloud projects get-iam-policy nyc-taxi-etl-dev-001 \
  --flatten="bindings[].members" \
  --filter="bindings.members:user:you@gmail.com"
```

**3. Bucket Access Denied**

Verify bucket permissions:

```bash
gcloud storage buckets get-iam-policy gs://nyc-taxi-etl-dev-gcs-us-central1-001
```

---

## Security Best Practices

1. **Prefer Workload Identity Federation** over service account keys
2. **Use service account impersonation** for local development
3. **Never commit credentials** to version control
4. **Rotate service account keys** regularly if you must use them
5. **Use least-privilege IAM roles** - grant only necessary permissions
6. **Enable audit logging** to track credential usage

---

## Related Documentation

- [Google Cloud Authentication Overview](https://cloud.google.com/docs/authentication)
- [Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation)
- [Application Default Credentials](https://cloud.google.com/docs/authentication/application-default-credentials)
- [Service Account Impersonation](https://cloud.google.com/iam/docs/impersonating-service-accounts)

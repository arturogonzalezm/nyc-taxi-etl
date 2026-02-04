# Terraform Infrastructure Setup

This document describes how to build and deploy the GCP infrastructure for the NYC Taxi ETL pipeline using Terraform.

## Prerequisites

- [Terraform](https://www.terraform.io/downloads) 1.5.0 or later
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and configured
- GCP project with billing enabled
- Appropriate IAM permissions to create resources

## Building the Environment

### Step 1: Navigate to the Terraform Directory

```bash
cd terraform
```

### Step 2: Initialize Terraform

Initialize the Terraform working directory. This downloads the required providers and sets up the backend.

```bash
terraform init
```

### Step 3: Review the Execution Plan

Preview the changes Terraform will make to your infrastructure:

```bash
terraform plan
```

Review the output carefully to ensure the planned changes match your expectations.

### Step 4: Apply the Configuration

Deploy the infrastructure:

```bash
terraform apply
```

When prompted, type `yes` to confirm and apply the changes.

---

## Quick Reference

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

---

## Additional Commands

### Destroy Infrastructure

To tear down all resources created by Terraform:

```bash
terraform destroy
```

### Format Configuration Files

To format Terraform files to canonical style:

```bash
terraform fmt
```

### Validate Configuration

To validate the Terraform configuration:

```bash
terraform validate
```

---

## Related Documentation

- [Terraform README](../terraform/README.md) - Detailed infrastructure documentation
- [Authentication Guide](AUTHENTICATION.md) - GCP authentication methods
- [Local Setup Guide](LOCAL_SETUP.md) - Local development environment setup

#!/usr/bin/env bash
# =============================================================================
# Generate .env and terraform.tfvars from terraform/config.tfvars
# =============================================================================
# This script reads the terraform config and generates:
# 1. .env - for docker-compose and local development
# 2. terraform/terraform.tfvars - for local terraform runs
#
# Sensitive values (billing_account_id, organisation_id, github_repository)
# must be provided via environment variables or prompted.
#
# Usage: ./scripts/generate-env.sh
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$PROJECT_ROOT/terraform/config.tfvars"
ENV_FILE="$PROJECT_ROOT/.env"
TFVARS_FILE="$PROJECT_ROOT/terraform/terraform.tfvars"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: $CONFIG_FILE not found"
    exit 1
fi

# =============================================================================
# Generate .env file
# =============================================================================
echo "# Auto-generated from terraform/config.tfvars" > "$ENV_FILE"
echo "# Run ./scripts/generate-env.sh to regenerate" >> "$ENV_FILE"
echo "" >> "$ENV_FILE"

# Parse config.tfvars and write to .env
while IFS='=' read -r key value; do
    # Skip empty lines and comments
    [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]] && continue

    # Clean up key and value
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs | sed 's/^"//;s/"$//')

    # Convert to uppercase (compatible with older bash)
    upper_key=$(echo "$key" | tr '[:lower:]' '[:upper:]')

    # Export to .env (quote values with spaces)
    echo "${upper_key}=\"$value\"" >> "$ENV_FILE"
done < "$CONFIG_FILE"

# Source the env file to get values
source "$ENV_FILE"

# Generate computed GCP values
ENVIRONMENT="${ENVIRONMENT:-dev}"
GCP_PROJECT_ID="${PROJECT_ID_BASE}-${ENVIRONMENT}-${INSTANCE_NUMBER}"
GCS_BUCKET="${PROJECT_ID_BASE}-${ENVIRONMENT}-${RESOURCE_TYPE}-${REGION}-${BUCKET_SUFFIX}"

echo "" >> "$ENV_FILE"
echo "# Computed values" >> "$ENV_FILE"
echo "ENVIRONMENT=$ENVIRONMENT" >> "$ENV_FILE"
echo "GCP_PROJECT_ID=$GCP_PROJECT_ID" >> "$ENV_FILE"
echo "GCS_BUCKET=$GCS_BUCKET" >> "$ENV_FILE"

# Default Postgres values
echo "" >> "$ENV_FILE"
echo "# Database defaults" >> "$ENV_FILE"
echo "POSTGRES_USER=postgres" >> "$ENV_FILE"
echo "POSTGRES_PASSWORD=postgres" >> "$ENV_FILE"
echo "POSTGRES_DB=nyc_taxi" >> "$ENV_FILE"

echo "✓ Generated $ENV_FILE"

# =============================================================================
# Generate terraform/terraform.tfvars
# =============================================================================

# Check for sensitive values in environment or prompt
if [ -z "$BILLING_ACCOUNT_ID" ]; then
    echo ""
    echo "Enter GCP Billing Account ID (format: XXXXXX-XXXXXX-XXXXXX):"
    read -r BILLING_ACCOUNT_ID
fi

if [ -z "$ORGANISATION_ID" ]; then
    echo ""
    echo "Enter GCP Organisation ID (run 'gcloud organizations list' to find it):"
    read -r ORGANISATION_ID
fi

if [ -z "$GITHUB_REPOSITORY" ]; then
    # Try to detect from git remote
    GITHUB_REPOSITORY=$(git -C "$PROJECT_ROOT" remote get-url origin 2>/dev/null | sed 's/.*github.com[:/]\(.*\)\.git/\1/' || echo "")
    if [ -z "$GITHUB_REPOSITORY" ]; then
        echo ""
        echo "Enter GitHub repository (format: owner/repo):"
        read -r GITHUB_REPOSITORY
    fi
fi

# Copy config.tfvars and append sensitive values
cat "$CONFIG_FILE" > "$TFVARS_FILE"

echo "" >> "$TFVARS_FILE"
echo "# ==============================================================================" >> "$TFVARS_FILE"
echo "# Sensitive values (DO NOT COMMIT - this file is gitignored)" >> "$TFVARS_FILE"
echo "# ==============================================================================" >> "$TFVARS_FILE"
echo "billing_account_id = \"$BILLING_ACCOUNT_ID\"" >> "$TFVARS_FILE"
echo "organisation_id    = \"$ORGANISATION_ID\"" >> "$TFVARS_FILE"
echo "github_repository  = \"$GITHUB_REPOSITORY\"" >> "$TFVARS_FILE"

echo "✓ Generated $TFVARS_FILE"

# =============================================================================
# Summary
# =============================================================================
echo ""
echo "============================================="
echo "Configuration Summary"
echo "============================================="
echo "  PROJECT_ID_BASE:    $PROJECT_ID_BASE"
echo "  ENVIRONMENT:        $ENVIRONMENT"
echo "  INSTANCE_NUMBER:    $INSTANCE_NUMBER"
echo "  REGION:             $REGION"
echo ""
echo "  GCP_PROJECT_ID:     $GCP_PROJECT_ID"
echo "  GCS_BUCKET:         $GCS_BUCKET"
echo ""
echo "  BILLING_ACCOUNT_ID: ${BILLING_ACCOUNT_ID:0:6}..."
echo "  ORGANISATION_ID:    $ORGANISATION_ID"
echo "  GITHUB_REPOSITORY:  $GITHUB_REPOSITORY"
echo "============================================="

#!/bin/bash
# =============================================================================
# BOOTSTRAP SCRIPT FOR NYC TAXI ETL TERRAFORM
# =============================================================================
# This script sets up the initial infrastructure required before Terraform
# can run automatically via CI/CD.
#
# For Organizations: Run this once, then CI/CD handles everything automatically
# For Individuals (no org): Run this once to create the project and state bucket
# =============================================================================

set -e

# Configuration
PROJECT_ID_BASE="nyc-taxi-etl"
ENVIRONMENT="${1:-dev}"
INSTANCE_NUMBER="001"
REGION="us-central1"
BILLING_ACCOUNT_ID="${BILLING_ACCOUNT_ID:-}"
GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-}"

# Derived values
PROJECT_ID="${PROJECT_ID_BASE}-${ENVIRONMENT}-${INSTANCE_NUMBER}"
STATE_BUCKET="${PROJECT_ID_BASE}-tfstate"
SERVICE_ACCOUNT="${PROJECT_ID_BASE}-${ENVIRONMENT}-sa-${INSTANCE_NUMBER}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "============================================="
echo "NYC Taxi ETL - Terraform Bootstrap"
echo "============================================="
echo "Environment: ${ENVIRONMENT}"
echo "Project ID: ${PROJECT_ID}"
echo "State Bucket: ${STATE_BUCKET}"
echo "============================================="

# Check required variables
if [ -z "$BILLING_ACCOUNT_ID" ]; then
    echo "Error: BILLING_ACCOUNT_ID environment variable is required"
    echo "Usage: BILLING_ACCOUNT_ID=XXXXXX-XXXXXX-XXXXXX ./bootstrap.sh [dev|prod]"
    exit 1
fi

if [ -z "$GITHUB_REPOSITORY" ]; then
    echo "Error: GITHUB_REPOSITORY environment variable is required"
    echo "Usage: GITHUB_REPOSITORY=owner/repo ./bootstrap.sh [dev|prod]"
    exit 1
fi

# Step 1: Create the GCP project (if it doesn't exist)
echo ""
echo "Step 1: Creating GCP project..."
if gcloud projects describe "$PROJECT_ID" &>/dev/null; then
    echo "  Project $PROJECT_ID already exists"
else
    echo "  Creating project $PROJECT_ID..."
    gcloud projects create "$PROJECT_ID" --name="NYC Taxi Pipeline ${ENVIRONMENT}"
fi

# Step 2: Link billing account
echo ""
echo "Step 2: Linking billing account..."
gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT_ID" || true

# Step 3: Enable required APIs
echo ""
echo "Step 3: Enabling APIs..."
gcloud services enable \
    cloudresourcemanager.googleapis.com \
    iam.googleapis.com \
    iamcredentials.googleapis.com \
    storage.googleapis.com \
    serviceusage.googleapis.com \
    cloudbilling.googleapis.com \
    --project="$PROJECT_ID"

# Step 4: Create Terraform state bucket (global, not per-environment)
echo ""
echo "Step 4: Creating Terraform state bucket..."
if gsutil ls -b "gs://${STATE_BUCKET}" &>/dev/null; then
    echo "  State bucket gs://${STATE_BUCKET} already exists"
else
    echo "  Creating state bucket gs://${STATE_BUCKET}..."
    gsutil mb -p "$PROJECT_ID" -l "$REGION" "gs://${STATE_BUCKET}"
    gsutil versioning set on "gs://${STATE_BUCKET}"
fi

# Step 5: Create service account (if it doesn't exist)
echo ""
echo "Step 5: Creating service account..."
SA_EMAIL="${PROJECT_ID_BASE}-${ENVIRONMENT}-sa-${INSTANCE_NUMBER}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SA_EMAIL" --project="$PROJECT_ID" &>/dev/null; then
    echo "  Service account already exists"
else
    echo "  Creating service account..."
    gcloud iam service-accounts create "${PROJECT_ID_BASE}-${ENVIRONMENT}-sa-${INSTANCE_NUMBER}" \
        --display-name="NYC Taxi Pipeline Service Account (${ENVIRONMENT})" \
        --project="$PROJECT_ID"
fi

# Step 6: Grant service account permissions
echo ""
echo "Step 6: Granting service account permissions..."
ROLES=(
    "roles/editor"
    "roles/storage.admin"
    "roles/iam.serviceAccountAdmin"
    "roles/iam.workloadIdentityPoolAdmin"
    "roles/serviceusage.serviceUsageAdmin"
)

for ROLE in "${ROLES[@]}"; do
    echo "  Granting $ROLE..."
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:$SA_EMAIL" \
        --role="$ROLE" \
        --quiet
done

# Step 7: Grant billing permissions
echo ""
echo "Step 7: Granting billing permissions..."
gcloud billing accounts add-iam-policy-binding "$BILLING_ACCOUNT_ID" \
    --member="serviceAccount:$SA_EMAIL" \
    --role="roles/billing.user" \
    --quiet || true

# Step 8: Create Workload Identity Pool (if it doesn't exist)
echo ""
echo "Step 8: Setting up Workload Identity Federation..."
POOL_ID="github-actions-pool"
PROVIDER_ID="github-provider"

if gcloud iam workload-identity-pools describe "$POOL_ID" --location="global" --project="$PROJECT_ID" &>/dev/null; then
    echo "  Workload Identity Pool already exists"
else
    echo "  Creating Workload Identity Pool..."
    gcloud iam workload-identity-pools create "$POOL_ID" \
        --location="global" \
        --display-name="GitHub Actions Pool" \
        --description="Identity pool for GitHub Actions CI/CD" \
        --project="$PROJECT_ID"
fi

if gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" \
    --workload-identity-pool="$POOL_ID" \
    --location="global" \
    --project="$PROJECT_ID" &>/dev/null; then
    echo "  Workload Identity Provider already exists"
else
    echo "  Creating Workload Identity Provider..."
    gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
        --location="global" \
        --workload-identity-pool="$POOL_ID" \
        --display-name="GitHub Provider" \
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
        --attribute-condition="assertion.repository == '${GITHUB_REPOSITORY}'" \
        --issuer-uri="https://token.actions.githubusercontent.com" \
        --project="$PROJECT_ID"
fi

# Step 9: Allow GitHub Actions to impersonate service account
echo ""
echo "Step 9: Allowing GitHub Actions to impersonate service account..."
PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format="value(projectNumber)")
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/attribute.repository/${GITHUB_REPOSITORY}" \
    --project="$PROJECT_ID" \
    --quiet

# Output values for GitHub Secrets
echo ""
echo "============================================="
echo "BOOTSTRAP COMPLETE!"
echo "============================================="
echo ""
echo "Add these secrets to GitHub (Settings > Secrets > Actions):"
echo ""
echo "GCP_WORKLOAD_IDENTITY_PROVIDER:"
echo "  projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}/providers/${PROVIDER_ID}"
echo ""
echo "GCP_SERVICE_ACCOUNT:"
echo "  ${SA_EMAIL}"
echo ""
echo "GCP_BILLING_ACCOUNT_ID:"
echo "  ${BILLING_ACCOUNT_ID}"
echo ""
echo "============================================="
echo ""
echo "Next steps:"
echo "1. Add the secrets above to GitHub"
echo "2. Uncomment the backend configuration in providers.tf"
echo "3. Run: terraform init -migrate-state"
echo "4. Push to GitHub - CI/CD will handle the rest!"
echo "============================================="

"""
Root conftest.py for all tests.

Sets up mock GCP environment variables to allow tests to run without
actual GCP configuration.
"""

import os
import pytest


@pytest.fixture(autouse=True)
def mock_gcp_env_vars(monkeypatch):
    """
    Automatically set mock GCP environment variables for all tests.

    This allows tests to run without requiring actual GCP configuration
    (terraform.tfvars or environment variables).
    """
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("GCP_PROJECT_ID", "test-project-id")

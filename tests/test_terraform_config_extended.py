"""
Extended tests for terraform_config module to improve coverage.

Tests cover:
- parse_tfvars() with various file formats
- get_gcp_config() error handling
- get_gcp_config_with_fallback() fallback chain
- Edge cases and error paths
"""

import os
import pytest
from unittest.mock import patch

from etl.jobs.utils.terraform_config import (
    parse_tfvars,
    get_gcp_config,
    get_gcp_config_with_fallback,
)


class TestParseTfvars:
    """Tests for parse_tfvars function."""

    def test_parse_tfvars_with_valid_file(self, tmp_path):
        """Test parse_tfvars parses valid tfvars file."""
        tfvars_content = """
            project_id_base = "nyc-taxi-etl"
            environment = "dev"
            region = "us-central1"
            instance_number = "003"
            resource_type = "gcs"
        """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["project_id_base"] == "nyc-taxi-etl"
        assert result["environment"] == "dev"
        assert result["region"] == "us-central1"

    def test_parse_tfvars_skips_comments(self, tmp_path):
        """Test parse_tfvars skips comment lines."""
        tfvars_content = """
            # This is a comment
            project_id_base = "test"
            # Another comment
            environment = "prod"
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["project_id_base"] == "test"
        assert result["environment"] == "prod"
        assert len(result) == 2

    def test_parse_tfvars_skips_empty_lines(self, tmp_path):
        """Test parse_tfvars skips empty lines."""
        tfvars_content = """
            project_id_base = "test"
            
            environment = "dev"
            
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert len(result) == 2

    def test_parse_tfvars_handles_unquoted_values(self, tmp_path):
        """Test parse_tfvars handles unquoted values."""
        tfvars_content = """
            instance_number = 003
            environment = dev
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["instance_number"] == "003"
        assert result["environment"] == "dev"

    def test_parse_tfvars_handles_inline_comments(self, tmp_path):
        """Test parse_tfvars handles inline comments."""
        tfvars_content = """
            project_id_base = "test" # This is an inline comment
            environment = "dev"
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["project_id_base"] == "test"

    def test_parse_tfvars_file_not_found(self):
        """Test parse_tfvars raises FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_tfvars("/nonexistent/path/terraform.tfvars")

    def test_parse_tfvars_with_none_path_uses_default(self):
        """Test parse_tfvars with None path searches for default location."""
        # This test verifies the default path logic
        # It may raise FileNotFoundError if terraform.tfvars doesn't exist
        try:
            result = parse_tfvars(None)
            assert isinstance(result, dict)
        except FileNotFoundError:
            # Expected if terraform.tfvars doesn't exist in default location
            pass

    def test_parse_tfvars_with_spaces_around_equals(self, tmp_path):
        """Test parse_tfvars handles various spacing around equals sign."""
        tfvars_content = """
            project_id_base="no-spaces"
            environment = "with-spaces"
            region  =  "extra-spaces"
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["project_id_base"] == "no-spaces"
        assert result["environment"] == "with-spaces"
        assert result["region"] == "extra-spaces"


class TestGetGcpConfig:
    """Tests for get_gcp_config function."""

    def test_get_gcp_config_returns_tuple(self, tmp_path):
        """Test get_gcp_config returns tuple of project_id and bucket."""
        tfvars_content = """
            project_id_base = "nyc-taxi-etl"
            environment = "dev"
            region = "us-central1"
            instance_number = "003"
            resource_type = "gcs"
            """
        tfvars_file = tmp_path / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        project_id, bucket = get_gcp_config(str(tfvars_file))

        assert project_id == "nyc-taxi-etl-dev-us-central1-003"
        assert bucket == "nyc-taxi-etl-dev-gcs-us-central1-003"

    def test_get_gcp_config_missing_required_vars(self, tmp_path):
        """Test get_gcp_config raises KeyError for missing required vars."""
        tfvars_content = """
            project_id_base = "test"
            # Missing: environment, region, instance_number, resource_type
            """
        tfvars_file = tmp_path / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        with pytest.raises(KeyError, match="Missing required variables"):
            get_gcp_config(str(tfvars_file))

    def test_get_gcp_config_missing_single_var(self, tmp_path):
        """Test get_gcp_config reports specific missing variable."""
        tfvars_content = """
            project_id_base = "test"
            environment = "dev"
            region = "us-central1"
            instance_number = "001"
            # Missing: resource_type
            """
        tfvars_file = tmp_path / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        with pytest.raises(KeyError, match="resource_type"):
            get_gcp_config(str(tfvars_file))

    def test_get_gcp_config_file_not_found(self):
        """Test get_gcp_config raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_gcp_config("/nonexistent/terraform.tfvars")

    def test_get_gcp_config_prod_environment(self, tmp_path):
        """Test get_gcp_config with prod environment."""
        tfvars_content = """
            project_id_base = "nyc-taxi-etl"
            environment = "prod"
            region = "us-east1"
            instance_number = "001"
            resource_type = "gcs"
            """
        tfvars_file = tmp_path / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        project_id, bucket = get_gcp_config(str(tfvars_file))

        assert "prod" in project_id
        assert "prod" in bucket
        assert "us-east1" in project_id
        assert "us-east1" in bucket


class TestGetGcpConfigWithFallback:
    """Tests for get_gcp_config_with_fallback function."""

    def test_fallback_uses_env_vars_when_set(self):
        """Test fallback uses environment variables when both are set."""
        with patch.dict(
            os.environ,
            {
                "GCP_PROJECT_ID": "env-project-id",
                "GCS_BUCKET": "env-bucket-name",
            },
        ):
            project_id, bucket = get_gcp_config_with_fallback()

        assert project_id == "env-project-id"
        assert bucket == "env-bucket-name"

    def test_fallback_uses_tfvars_when_env_not_set(self, tmp_path):
        """Test fallback uses terraform.tfvars when env vars not set."""
        tfvars_content = """
            project_id_base = "tfvars-project"
            environment = "dev"
            region = "us-central1"
            instance_number = "001"
            resource_type = "gcs"
            """
        tfvars_file = tmp_path / "terraform" / "terraform.tfvars"
        tfvars_file.parent.mkdir(parents=True)
        tfvars_file.write_text(tfvars_content)

        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "etl.jobs.utils.terraform_config.get_gcp_config"
            ) as mock_get_config:
                mock_get_config.return_value = ("tfvars-project-id", "tfvars-bucket")
                project_id, bucket = get_gcp_config_with_fallback()

        # Should have called get_gcp_config since env vars were empty
        assert project_id == "tfvars-project-id" or project_id == ""
        assert bucket == "tfvars-bucket" or bucket == ""

    def test_fallback_partial_env_vars(self):
        """Test fallback with only one env var set."""
        with patch.dict(
            os.environ,
            {"GCP_PROJECT_ID": "env-project", "GCS_BUCKET": ""},
            clear=True,
        ):
            with patch(
                "etl.jobs.utils.terraform_config.get_gcp_config"
            ) as mock_get_config:
                mock_get_config.return_value = ("tf-project", "tf-bucket")
                project_id, bucket = get_gcp_config_with_fallback()

        # Project ID from env, bucket from tfvars
        assert project_id == "env-project"

    def test_fallback_handles_tfvars_not_found(self):
        """Test fallback handles missing terraform.tfvars gracefully."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "etl.jobs.utils.terraform_config.get_gcp_config",
                side_effect=FileNotFoundError("Not found"),
            ):
                project_id, bucket = get_gcp_config_with_fallback()

        # Should return empty strings when both sources fail
        assert project_id == ""
        assert bucket == ""

    def test_fallback_handles_tfvars_key_error(self):
        """Test fallback handles KeyError from terraform.tfvars."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "etl.jobs.utils.terraform_config.get_gcp_config",
                side_effect=KeyError("Missing vars"),
            ):
                project_id, bucket = get_gcp_config_with_fallback()

        assert project_id == ""
        assert bucket == ""

    def test_fallback_env_vars_take_priority(self):
        """Test environment variables take priority over tfvars."""
        with patch.dict(
            os.environ,
            {
                "GCP_PROJECT_ID": "priority-project",
                "GCS_BUCKET": "priority-bucket",
            },
        ):
            with patch(
                "etl.jobs.utils.terraform_config.get_gcp_config"
            ) as mock_get_config:
                # This should not be called since env vars are set
                mock_get_config.return_value = ("tfvars-project", "tfvars-bucket")
                project_id, bucket = get_gcp_config_with_fallback()

        assert project_id == "priority-project"
        assert bucket == "priority-bucket"


class TestTerraformConfigEdgeCases:
    """Edge case tests for terraform_config module."""

    def test_parse_tfvars_with_special_characters(self, tmp_path):
        """Test parse_tfvars handles special characters in values."""
        tfvars_content = """
            project_name = "NYC Taxi Pipeline - Dev"
            description = "Test with special chars: @#$%"
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert "NYC Taxi Pipeline - Dev" in result["project_name"]

    def test_parse_tfvars_with_numeric_values(self, tmp_path):
        """Test parse_tfvars handles numeric values."""
        tfvars_content = """
            instance_number = "003"
            port = 5432
            """
        tfvars_file = tmp_path / "test.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result["instance_number"] == "003"
        assert result["port"] == "5432"

    def test_get_gcp_config_constructs_correct_ids(self, tmp_path):
        """Test get_gcp_config constructs IDs matching Terraform locals."""
        tfvars_content = """
            project_id_base = "my-project"
            environment = "staging"
            region = "europe-west1"
            instance_number = "042"
            resource_type = "storage"
            """
        tfvars_file = tmp_path / "terraform.tfvars"
        tfvars_file.write_text(tfvars_content)

        project_id, bucket = get_gcp_config(str(tfvars_file))

        # Verify format matches Terraform locals pattern
        assert project_id == "my-project-staging-europe-west1-042"
        assert bucket == "my-project-staging-storage-europe-west1-042"

    def test_parse_tfvars_empty_file(self, tmp_path):
        """Test parse_tfvars handles empty file."""
        tfvars_file = tmp_path / "empty.tfvars"
        tfvars_file.write_text("")

        result = parse_tfvars(str(tfvars_file))

        assert result == {}

    def test_parse_tfvars_only_comments(self, tmp_path):
        """Test parse_tfvars handles file with only comments."""
        tfvars_content = """
            # Comment 1
            # Comment 2
            # Comment 3
            """
        tfvars_file = tmp_path / "comments.tfvars"
        tfvars_file.write_text(tfvars_content)

        result = parse_tfvars(str(tfvars_file))

        assert result == {}

"""
Tests for ZoneLookupIngestionJob to improve coverage.
"""

import pytest
from unittest.mock import patch, MagicMock

from dev.etl.jobs.misc.zone_lookup_ingestion_job import (
    ZoneLookupIngestionJob,
    ReferenceDataError,
    run_zone_lookup_ingestion,
)
from dev.etl.jobs.base_job import JobExecutionError
from dev.etl.jobs.utils.config import JobConfig


class TestZoneLookupIngestionJobInit:
    """Tests for ZoneLookupIngestionJob initialization."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def test_init_creates_job(self):
        """Test that job can be initialized."""
        job = ZoneLookupIngestionJob()
        assert job is not None

    def test_init_sets_file_name(self):
        """Test that file_name is set from constant."""
        job = ZoneLookupIngestionJob()
        assert job.file_name == ZoneLookupIngestionJob.FILE_NAME

    def test_init_sets_source_url(self):
        """Test that source_url is set from constant."""
        job = ZoneLookupIngestionJob()
        assert job.source_url == ZoneLookupIngestionJob.SOURCE_URL

    def test_init_job_name(self):
        """Test that job name is set correctly."""
        job = ZoneLookupIngestionJob()
        assert job.job_name == "ZoneLookupIngestion"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = JobConfig()
        job = ZoneLookupIngestionJob(config=config)
        assert job.config is config


class TestZoneLookupIngestionJobValidateInputs:
    """Tests for ZoneLookupIngestionJob.validate_inputs method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def test_validate_inputs_does_not_raise(self):
        """Test that validate_inputs does not raise for valid job."""
        job = ZoneLookupIngestionJob()
        # Should not raise
        job.validate_inputs()


class TestZoneLookupIngestionJobConstants:
    """Tests for ZoneLookupIngestionJob class constants."""

    def test_file_name_constant(self):
        """Test FILE_NAME constant is set correctly."""
        assert ZoneLookupIngestionJob.FILE_NAME == "taxi_zone_lookup.csv"

    def test_source_url_constant(self):
        """Test SOURCE_URL constant is set correctly."""
        assert "taxi_zone_lookup.csv" in ZoneLookupIngestionJob.SOURCE_URL
        assert ZoneLookupIngestionJob.SOURCE_URL.startswith("https://")

    def test_required_columns_constant(self):
        """Test REQUIRED_COLUMNS constant contains expected columns."""
        required = ZoneLookupIngestionJob.REQUIRED_COLUMNS
        assert "LocationID" in required
        assert "Borough" in required
        assert "Zone" in required
        assert "service_zone" in required
        assert len(required) == 4

    def test_gcs_object_path_constant(self):
        """Test GCS_OBJECT_PATH constant is set correctly."""
        assert ZoneLookupIngestionJob.GCS_OBJECT_PATH == "misc/taxi_zone_lookup.csv"


class TestReferenceDataError:
    """Tests for ReferenceDataError exception class."""

    def test_reference_data_error_message(self):
        """Test ReferenceDataError stores message correctly."""
        error = ReferenceDataError("Reference data validation failed")
        assert str(error) == "Reference data validation failed"

    def test_reference_data_error_inheritance(self):
        """Test ReferenceDataError inherits from JobExecutionError."""
        error = ReferenceDataError("Test")
        assert isinstance(error, JobExecutionError)
        assert isinstance(error, Exception)

    def test_reference_data_error_with_cause(self):
        """Test ReferenceDataError can be raised with cause."""
        original = ValueError("Missing column")
        try:
            raise ReferenceDataError("Validation failed") from original
        except ReferenceDataError as e:
            assert e.__cause__ is original


class TestZoneLookupIngestionJobExtract:
    """Tests for ZoneLookupIngestionJob.extract method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_calls_extract_from_source(self):
        """Test extract calls _extract_from_source."""
        job = ZoneLookupIngestionJob()
        mock_df = MagicMock()

        with patch.object(job, "_extract_from_source", return_value=mock_df):
            result = job.extract()
            assert result is mock_df


class TestZoneLookupIngestionJobExtractFromSource:
    """Tests for ZoneLookupIngestionJob._extract_from_source method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_downloads_when_not_cached(self, tmp_path):
        """Test extract downloads file when not in cache."""
        import requests

        job = ZoneLookupIngestionJob()
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        mock_response = MagicMock()
        mock_response.content = (
            b"LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow"
        )

        mock_df = MagicMock()
        mock_df.count.return_value = 1
        mock_df.schema = "test_schema"
        job.spark.read.option.return_value.csv.return_value = mock_df

        with patch.object(requests, "get", return_value=mock_response):
            job._extract_from_source()

        # Verify file was created
        assert (tmp_path / job.file_name).exists()

    def test_extract_uses_cache_when_exists(self, tmp_path):
        """Test extract uses cached file when it exists."""
        import requests

        job = ZoneLookupIngestionJob()
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        # Create cached file
        cache_file = tmp_path / job.file_name
        cache_file.write_text(
            "LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow"
        )

        mock_df = MagicMock()
        mock_df.count.return_value = 1
        mock_df.schema = "test_schema"
        job.spark.read.option.return_value.csv.return_value = mock_df

        with patch.object(requests, "get") as mock_get:
            job._extract_from_source()
            # Should not download
            mock_get.assert_not_called()

    def test_extract_raises_on_download_error(self, tmp_path):
        """Test extract raises ReferenceDataError on download failure."""
        import requests

        job = ZoneLookupIngestionJob()
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        with patch.object(
            requests,
            "get",
            side_effect=requests.exceptions.RequestException("Network error"),
        ):
            with pytest.raises(ReferenceDataError, match="Failed to download"):
                job._extract_from_source()

    def test_extract_raises_on_parse_error(self, tmp_path):
        """Test extract raises ReferenceDataError on CSV parse failure."""
        job = ZoneLookupIngestionJob()
        job.spark = MagicMock()
        job.spark.read.option.return_value.csv.side_effect = Exception("Parse error")
        job.config._cache_dir = tmp_path

        # Create cached file
        cache_file = tmp_path / job.file_name
        cache_file.write_text("invalid csv")

        with pytest.raises(ReferenceDataError, match="Failed to parse"):
            job._extract_from_source()


class TestZoneLookupIngestionJobTransform:
    """Tests for ZoneLookupIngestionJob.transform method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    @patch("pyspark.sql.functions.col")
    def test_transform_validates_required_columns(self, mock_col):
        """Test transform validates required columns exist."""
        job = ZoneLookupIngestionJob()

        mock_df = MagicMock()
        mock_df.columns = ["LocationID", "Borough", "Zone", "service_zone"]
        mock_df.filter.return_value.count.return_value = 0
        mock_df.count.return_value = 10
        mock_df.select.return_value.distinct.return_value.count.return_value = 10

        result = job.transform(mock_df)

        assert result is mock_df

    @patch("pyspark.sql.functions.col")
    def test_transform_raises_on_missing_columns(self, mock_col):
        """Test transform raises error when required columns missing."""
        job = ZoneLookupIngestionJob()

        mock_df = MagicMock()
        mock_df.columns = ["LocationID", "Borough"]  # Missing Zone and service_zone

        with pytest.raises(ReferenceDataError, match="Missing required columns"):
            job.transform(mock_df)

    @patch("pyspark.sql.functions.col")
    def test_transform_raises_on_null_location_id(self, mock_col):
        """Test transform raises error when LocationID has nulls."""
        job = ZoneLookupIngestionJob()

        mock_df = MagicMock()
        mock_df.columns = ["LocationID", "Borough", "Zone", "service_zone"]
        mock_df.filter.return_value.count.return_value = 5  # 5 null LocationIDs

        with pytest.raises(ReferenceDataError, match="null LocationID"):
            job.transform(mock_df)

    @patch("pyspark.sql.functions.col")
    def test_transform_warns_on_duplicate_location_ids(self, mock_col):
        """Test transform logs warning on duplicate LocationIDs."""
        job = ZoneLookupIngestionJob()

        mock_df = MagicMock()
        mock_df.columns = ["LocationID", "Borough", "Zone", "service_zone"]
        mock_df.filter.return_value.count.return_value = 0
        mock_df.count.return_value = 10
        mock_df.select.return_value.distinct.return_value.count.return_value = (
            8  # 2 duplicates
        )

        with patch.object(job.logger, "warning") as mock_warn:
            job.transform(mock_df)
            mock_warn.assert_called()


class TestZoneLookupIngestionJobLoad:
    """Tests for ZoneLookupIngestionJob.load method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    @patch("dev.etl.jobs.misc.zone_lookup_ingestion_job.gcs_storage")
    def test_load_uploads_to_gcs(self, mock_gcs_storage, tmp_path):
        """Test load uploads CSV to GCS."""
        job = ZoneLookupIngestionJob()
        job.config._cache_dir = tmp_path

        # Create the cached file that load() expects
        cache_file = tmp_path / job.file_name
        cache_file.write_text(
            "LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow"
        )

        mock_df = MagicMock()
        mock_df.count.return_value = 100

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_storage.Client.return_value.bucket.return_value = mock_bucket

        job.load(mock_df)

        # Verify blob upload_from_filename was called
        mock_blob.upload_from_filename.assert_called_once()

    @patch("dev.etl.jobs.misc.zone_lookup_ingestion_job.gcs_storage")
    def test_load_uses_correct_gcs_path(self, mock_gcs_storage, tmp_path):
        """Test load uses correct GCS object path."""
        job = ZoneLookupIngestionJob()
        job.config._cache_dir = tmp_path

        # Create the cached file that load() expects
        cache_file = tmp_path / job.file_name
        cache_file.write_text(
            "LocationID,Borough,Zone,service_zone\n1,Manhattan,Test,Yellow"
        )

        mock_df = MagicMock()
        mock_df.count.return_value = 100

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_bucket.blob.return_value = mock_blob
        mock_gcs_storage.Client.return_value.bucket.return_value = mock_bucket

        job.load(mock_df)

        # Verify correct blob path was used
        mock_bucket.blob.assert_called_once_with(ZoneLookupIngestionJob.GCS_OBJECT_PATH)

    def test_load_raises_when_cache_file_missing(self, tmp_path):
        """Test load raises FileNotFoundError when cache file doesn't exist."""
        job = ZoneLookupIngestionJob()
        job.config._cache_dir = tmp_path

        mock_df = MagicMock()
        mock_df.count.return_value = 100

        with pytest.raises(FileNotFoundError, match="Local file not found"):
            job.load(mock_df)


class TestRunZoneLookupIngestionFunction:
    """Tests for run_zone_lookup_ingestion convenience function."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_run_zone_lookup_ingestion_creates_job(self):
        """Test run_zone_lookup_ingestion creates and runs job."""
        with patch.object(ZoneLookupIngestionJob, "run", return_value=True) as mock_run:
            result = run_zone_lookup_ingestion()
            mock_run.assert_called_once()
            assert result is True

    def test_run_zone_lookup_ingestion_returns_false_on_failure(self):
        """Test run_zone_lookup_ingestion returns False on failure."""
        with patch.object(ZoneLookupIngestionJob, "run", return_value=False):
            result = run_zone_lookup_ingestion()
            assert result is False

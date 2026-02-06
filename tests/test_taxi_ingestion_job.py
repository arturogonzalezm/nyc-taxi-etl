"""
Unit tests for TaxiIngestionJob.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from dev.etl.jobs.bronze.taxi_ingestion_job import (
    TaxiIngestionJob,
    DataValidationError,
    DownloadError,
    run_ingestion,
)
from dev.etl.jobs.base_job import JobExecutionError
from dev.etl.jobs.utils.config import JobConfig


class TestDataValidationError:
    """Tests for DataValidationError exception class."""

    def test_error_message(self):
        """Test DataValidationError stores message correctly."""
        error = DataValidationError("Validation failed")
        assert str(error) == "Validation failed"

    def test_error_inheritance(self):
        """Test DataValidationError inherits from JobExecutionError."""
        error = DataValidationError("Test")
        assert isinstance(error, JobExecutionError)
        assert isinstance(error, Exception)


class TestDownloadError:
    """Tests for DownloadError exception class."""

    def test_error_message(self):
        """Test DownloadError stores message correctly."""
        error = DownloadError("Download failed")
        assert str(error) == "Download failed"

    def test_error_inheritance(self):
        """Test DownloadError inherits from JobExecutionError."""
        error = DownloadError("Test")
        assert isinstance(error, JobExecutionError)
        assert isinstance(error, Exception)

    def test_error_with_cause(self):
        """Test DownloadError can be raised with cause."""
        original = IOError("Network error")
        try:
            raise DownloadError("Download failed") from original
        except DownloadError as e:
            assert e.__cause__ is original


class TestTaxiIngestionJobInit:
    """Tests for TaxiIngestionJob initialization."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_init_yellow_taxi(self):
        """Test initialization with yellow taxi type."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        assert job.taxi_type == "yellow"
        assert job.year == 2024
        assert job.month == 1

    def test_init_green_taxi(self):
        """Test initialization with green taxi type."""
        job = TaxiIngestionJob("green", 2024, 6)
        assert job.taxi_type == "green"
        assert job.year == 2024
        assert job.month == 6

    def test_init_file_name_format(self):
        """Test file name is generated correctly."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        assert job.file_name == "yellow_tripdata_2024-01.parquet"

    def test_init_file_name_format_double_digit_month(self):
        """Test file name with double digit month."""
        job = TaxiIngestionJob("green", 2023, 12)
        assert job.file_name == "green_tripdata_2023-12.parquet"

    def test_init_job_name_format(self):
        """Test job name is generated correctly."""
        job = TaxiIngestionJob("yellow", 2024, 3)
        assert job.job_name == "TaxiIngestion_yellow_2024_03"

    def test_init_invalid_taxi_type(self):
        """Test initialization with invalid taxi type raises error."""
        with pytest.raises(ValueError, match="Invalid taxi_type"):
            TaxiIngestionJob("blue", 2024, 1)

    def test_init_invalid_year_too_low(self):
        """Test initialization with year before 2009 raises error."""
        with pytest.raises(ValueError, match="Invalid year"):
            TaxiIngestionJob("yellow", 2008, 1)

    def test_init_invalid_month_zero(self):
        """Test initialization with month 0 raises error."""
        with pytest.raises(ValueError, match="Invalid month"):
            TaxiIngestionJob("yellow", 2024, 0)

    def test_init_invalid_month_thirteen(self):
        """Test initialization with month 13 raises error."""
        with pytest.raises(ValueError, match="Invalid month"):
            TaxiIngestionJob("yellow", 2024, 13)

    def test_init_invalid_month_negative(self):
        """Test initialization with negative month raises error."""
        with pytest.raises(ValueError, match="Invalid month"):
            TaxiIngestionJob("yellow", 2024, -1)

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = JobConfig()
        job = TaxiIngestionJob("yellow", 2024, 1, config=config)
        assert job.config is config


class TestTaxiIngestionJobValidateParameters:
    """Tests for TaxiIngestionJob._validate_parameters static method."""

    def test_validate_valid_parameters(self):
        """Test validation passes for valid parameters."""
        # Should not raise
        TaxiIngestionJob._validate_parameters("yellow", 2024, 1)
        TaxiIngestionJob._validate_parameters("green", 2009, 12)

    def test_validate_invalid_taxi_type(self):
        """Test validation fails for invalid taxi type."""
        with pytest.raises(ValueError, match="Invalid taxi_type"):
            TaxiIngestionJob._validate_parameters("red", 2024, 1)

    def test_validate_invalid_year_string(self):
        """Test validation fails for string year."""
        with pytest.raises(ValueError, match="Invalid year"):
            TaxiIngestionJob._validate_parameters("yellow", "2024", 1)

    def test_validate_invalid_month_string(self):
        """Test validation fails for string month."""
        with pytest.raises(ValueError, match="Invalid month"):
            TaxiIngestionJob._validate_parameters("yellow", 2024, "1")


class TestTaxiIngestionJobValidateInputs:
    """Tests for TaxiIngestionJob.validate_inputs method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_validate_inputs_valid(self):
        """Test validate_inputs passes for valid job."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        # Should not raise
        job.validate_inputs()

    def test_validate_inputs_logs_info(self):
        """Test validate_inputs logs validation info."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        with patch.object(job.logger, "info") as mock_log:
            job.validate_inputs()
            mock_log.assert_called()


class TestTaxiIngestionJobConstants:
    """Tests for TaxiIngestionJob class constants."""

    def test_nyc_tlc_base_url(self):
        """Test NYC TLC base URL constant."""
        assert "d37ci6vzurychx.cloudfront.net" in TaxiIngestionJob.NYC_TLC_BASE_URL
        assert TaxiIngestionJob.NYC_TLC_BASE_URL.startswith("https://")

    def test_valid_taxi_types(self):
        """Test valid taxi types constant."""
        assert "yellow" in TaxiIngestionJob.VALID_TAXI_TYPES
        assert "green" in TaxiIngestionJob.VALID_TAXI_TYPES
        assert len(TaxiIngestionJob.VALID_TAXI_TYPES) == 2

    def test_min_year(self):
        """Test minimum year constant."""
        assert TaxiIngestionJob.MIN_YEAR == 2009


class TestTaxiIngestionJobExtract:
    """Tests for TaxiIngestionJob.extract method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_builds_correct_url(self):
        """Test extract builds correct URL."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        expected_url = (
            f"{TaxiIngestionJob.NYC_TLC_BASE_URL}/yellow_tripdata_2024-01.parquet"
        )

        with patch.object(job, "_extract_with_local_cache") as mock_extract:
            mock_extract.return_value = Mock()
            job.extract()
            mock_extract.assert_called_once_with(expected_url)


class TestRunIngestionFunction:
    """Tests for run_ingestion convenience function."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_run_ingestion_creates_job(self):
        """Test run_ingestion creates TaxiIngestionJob."""
        with patch.object(TaxiIngestionJob, "run", return_value=True) as mock_run:
            result = run_ingestion("yellow", 2024, 1)
            mock_run.assert_called_once()
            assert result is True

    def test_run_ingestion_returns_false_on_failure(self):
        """Test run_ingestion returns False on job failure."""
        with patch.object(TaxiIngestionJob, "run", return_value=False):
            result = run_ingestion("yellow", 2024, 1)
            assert result is False


class TestTaxiIngestionJobExtractWithLocalCache:
    """Tests for TaxiIngestionJob._extract_with_local_cache method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_cache_miss_downloads_file(self, tmp_path):
        """Test extract downloads file when not in cache."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        with patch.object(job, "_download_file") as mock_download:
            job._extract_with_local_cache("http://example.com/file.parquet")
            mock_download.assert_called_once()

    def test_extract_cache_hit_skips_download(self, tmp_path):
        """Test extract skips download when file exists in cache."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        # Create cached file
        cache_file = tmp_path / job.file_name
        cache_file.write_text("cached data")

        with patch.object(job, "_download_file") as mock_download:
            job._extract_with_local_cache("http://example.com/file.parquet")
            mock_download.assert_not_called()

    def test_extract_download_failure_raises_download_error(self, tmp_path):
        """Test extract raises DownloadError when download fails."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        job.spark = MagicMock()
        job.config._cache_dir = tmp_path

        with patch.object(
            job, "_download_file", side_effect=Exception("Network error")
        ):
            with pytest.raises(DownloadError, match="Failed to download"):
                job._extract_with_local_cache("http://example.com/file.parquet")

    def test_extract_read_failure_raises_job_execution_error(self, tmp_path):
        """Test extract raises JobExecutionError when parquet read fails."""
        job = TaxiIngestionJob("yellow", 2024, 1)
        job.spark = MagicMock()
        job.spark.read.parquet.side_effect = Exception("Read error")
        job.config._cache_dir = tmp_path

        # Create cached file
        cache_file = tmp_path / job.file_name
        cache_file.write_text("invalid parquet")

        with pytest.raises(JobExecutionError, match="Failed to read parquet"):
            job._extract_with_local_cache("http://example.com/file.parquet")


class TestTaxiIngestionJobDownloadFile:
    """Tests for TaxiIngestionJob._download_file method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_download_file_success(self, tmp_path):
        """Test successful file download."""
        import requests

        job = TaxiIngestionJob("yellow", 2024, 1)
        destination = tmp_path / "test_file.parquet"

        mock_response = MagicMock()
        mock_response.headers = {"content-length": "100"}
        mock_response.iter_content.return_value = [b"test data"]

        with patch.object(requests, "get", return_value=mock_response):
            job._download_file("http://example.com/file.parquet", destination)
            assert destination.exists()
            assert destination.read_bytes() == b"test data"

    def test_download_file_timeout_raises_error(self, tmp_path):
        """Test download timeout raises DownloadError."""
        import requests

        job = TaxiIngestionJob("yellow", 2024, 1)
        destination = tmp_path / "test_file.parquet"

        with patch.object(
            requests, "get", side_effect=requests.exceptions.Timeout("Timeout")
        ):
            with pytest.raises(DownloadError, match="Download timeout"):
                job._download_file("http://example.com/file.parquet", destination)

    def test_download_file_http_error_raises_error(self, tmp_path):
        """Test HTTP error raises DownloadError."""
        import requests

        job = TaxiIngestionJob("yellow", 2024, 1)
        destination = tmp_path / "test_file.parquet"

        mock_response = MagicMock()
        mock_response.status_code = 404
        http_error = requests.exceptions.HTTPError(response=mock_response)

        with patch.object(requests, "get", side_effect=http_error):
            with pytest.raises(DownloadError, match="HTTP error"):
                job._download_file("http://example.com/file.parquet", destination)

    def test_download_file_request_exception_raises_error(self, tmp_path):
        """Test request exception raises DownloadError."""
        import requests

        job = TaxiIngestionJob("yellow", 2024, 1)
        destination = tmp_path / "test_file.parquet"

        with patch.object(
            requests,
            "get",
            side_effect=requests.exceptions.RequestException("Connection error"),
        ):
            with pytest.raises(DownloadError, match="Download failed"):
                job._download_file("http://example.com/file.parquet", destination)


class TestTaxiIngestionJobTransform:
    """Tests for TaxiIngestionJob.transform method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    @patch("pyspark.sql.functions.sha2")
    @patch("pyspark.sql.functions.concat_ws")
    @patch("pyspark.sql.functions.coalesce")
    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.lit")
    @patch("pyspark.sql.functions.current_timestamp")
    @patch("pyspark.sql.functions.current_date")
    def test_transform_calls_count(
        self,
        mock_date,
        mock_ts,
        mock_lit,
        mock_col,
        mock_coalesce,
        mock_concat,
        mock_sha2,
    ):
        """Test transform calls count on DataFrame."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        # Create mock DataFrame with proper return values
        mock_df = MagicMock()
        mock_df.columns = ["col1", "col2"]
        mock_df.count.return_value = 100
        mock_df.schema = "test_schema"

        # Chain mock for withColumn calls - each returns a new mock
        mock_result = MagicMock()
        mock_df.withColumn.return_value = mock_result
        mock_result.withColumn.return_value = mock_result
        mock_result.select.return_value.distinct.return_value.count.return_value = 100

        job.transform(mock_df)

        # Verify count was called
        mock_df.count.assert_called_once()

    @patch("pyspark.sql.functions.sha2")
    @patch("pyspark.sql.functions.concat_ws")
    @patch("pyspark.sql.functions.coalesce")
    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.lit")
    @patch("pyspark.sql.functions.current_timestamp")
    @patch("pyspark.sql.functions.current_date")
    def test_transform_logs_record_count(
        self,
        mock_date,
        mock_ts,
        mock_lit,
        mock_col,
        mock_coalesce,
        mock_concat,
        mock_sha2,
    ):
        """Test transform logs record count."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        mock_df = MagicMock()
        mock_df.columns = ["col1"]
        mock_df.count.return_value = 500
        mock_df.schema = "schema"

        mock_result = MagicMock()
        mock_df.withColumn.return_value = mock_result
        mock_result.withColumn.return_value = mock_result
        mock_result.select.return_value.distinct.return_value.count.return_value = 500

        with patch.object(job.logger, "info") as mock_log:
            job.transform(mock_df)
            # Check that record count was logged
            calls = [str(call) for call in mock_log.call_args_list]
            assert any("500" in call for call in calls)

    @patch("pyspark.sql.functions.sha2")
    @patch("pyspark.sql.functions.concat_ws")
    @patch("pyspark.sql.functions.coalesce")
    @patch("pyspark.sql.functions.col")
    @patch("pyspark.sql.functions.lit")
    @patch("pyspark.sql.functions.current_timestamp")
    @patch("pyspark.sql.functions.current_date")
    def test_transform_returns_dataframe(
        self,
        mock_date,
        mock_ts,
        mock_lit,
        mock_col,
        mock_coalesce,
        mock_concat,
        mock_sha2,
    ):
        """Test transform returns a DataFrame."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        mock_df = MagicMock()
        mock_df.columns = ["col1"]
        mock_df.count.return_value = 10
        mock_df.schema = "schema"

        mock_result = MagicMock()
        mock_df.withColumn.return_value = mock_result
        mock_result.withColumn.return_value = mock_result
        mock_result.select.return_value.distinct.return_value.count.return_value = 10

        result = job.transform(mock_df)

        assert result is not None


class TestTaxiIngestionJobLoad:
    """Tests for TaxiIngestionJob.load method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_load_writes_to_gcs_path(self):
        """Test load writes DataFrame to correct GCS path."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        mock_df = MagicMock()
        mock_cached_df = MagicMock()
        mock_df.cache.return_value = mock_cached_df
        mock_cached_df.count.return_value = 100

        mock_writer = MagicMock()
        mock_cached_df.write = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.partitionBy.return_value = mock_writer
        mock_writer.option.return_value = mock_writer

        job.load(mock_df)

        # Verify write chain was called with append mode
        mock_writer.mode.assert_called_once_with("append")
        mock_writer.partitionBy.assert_called_once()

    def test_load_partitions_by_year_and_month(self):
        """Test load partitions data by year and month."""
        job = TaxiIngestionJob("yellow", 2024, 6)

        mock_df = MagicMock()
        mock_cached_df = MagicMock()
        mock_df.cache.return_value = mock_cached_df
        mock_cached_df.count.return_value = 100

        mock_writer = MagicMock()
        mock_cached_df.write = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.partitionBy.return_value = mock_writer
        mock_writer.option.return_value = mock_writer

        job.load(mock_df)

        mock_writer.partitionBy.assert_called_once_with("year", "month")

    def test_load_caches_dataframe(self):
        """Test load caches DataFrame before writing."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        mock_df = MagicMock()
        mock_cached_df = MagicMock()
        mock_df.cache.return_value = mock_cached_df
        mock_cached_df.count.return_value = 50

        mock_writer = MagicMock()
        mock_cached_df.write = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.partitionBy.return_value = mock_writer
        mock_writer.option.return_value = mock_writer

        job.load(mock_df)

        mock_df.cache.assert_called_once()

    def test_load_unpersists_dataframe(self):
        """Test load unpersists DataFrame after writing."""
        job = TaxiIngestionJob("yellow", 2024, 1)

        mock_df = MagicMock()
        mock_cached_df = MagicMock()
        mock_df.cache.return_value = mock_cached_df
        mock_cached_df.count.return_value = 50

        mock_writer = MagicMock()
        mock_cached_df.write = mock_writer
        mock_writer.mode.return_value = mock_writer
        mock_writer.partitionBy.return_value = mock_writer
        mock_writer.option.return_value = mock_writer

        job.load(mock_df)

        mock_cached_df.unpersist.assert_called_once()

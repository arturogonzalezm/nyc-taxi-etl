"""
Unit tests for BaseSparkJob and JobExecutionError.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import logging

from etl.jobs.base_job import BaseSparkJob, JobExecutionError
from etl.jobs.utils.config import JobConfig
from etl.jobs.utils.spark_manager import SparkSessionManager


class TestJobExecutionError:
    """Tests for JobExecutionError exception class."""

    def test_error_message(self):
        """Test JobExecutionError stores message correctly."""
        error = JobExecutionError("Job failed")
        assert str(error) == "Job failed"

    def test_error_inheritance(self):
        """Test JobExecutionError inherits from Exception."""
        error = JobExecutionError("Test")
        assert isinstance(error, Exception)

    def test_error_with_cause(self):
        """Test JobExecutionError can be raised with cause."""
        original = ValueError("Original error")
        try:
            raise JobExecutionError("Wrapper") from original
        except JobExecutionError as e:
            assert e.__cause__ is original


class ConcreteTestJob(BaseSparkJob):
    """Concrete implementation for testing BaseSparkJob."""

    def __init__(self, job_name: str, config=None):
        super().__init__(job_name, config)
        self.validate_called = False
        self.extract_called = False
        self.transform_called = False
        self.load_called = False
        self.cleanup_called = False

    def validate_inputs(self):
        self.validate_called = True

    def extract(self):
        self.extract_called = True
        return Mock()

    def transform(self, df):
        self.transform_called = True
        return df

    def load(self, df):
        self.load_called = True


class TestBaseSparkJobInit:
    """Tests for BaseSparkJob initialization."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_init_with_valid_name(self):
        """Test initialization with valid job name."""
        job = ConcreteTestJob("test_job")
        assert job.job_name == "test_job"

    def test_init_strips_whitespace(self):
        """Test initialization strips whitespace from job name."""
        job = ConcreteTestJob("  test_job  ")
        assert job.job_name == "test_job"

    def test_init_empty_name_raises_error(self):
        """Test initialization with empty name raises ValueError."""
        with pytest.raises(ValueError, match="job_name cannot be empty"):
            ConcreteTestJob("")

    def test_init_whitespace_only_name_raises_error(self):
        """Test initialization with whitespace-only name raises ValueError."""
        with pytest.raises(ValueError, match="job_name cannot be empty"):
            ConcreteTestJob("   ")

    def test_init_none_name_raises_error(self):
        """Test initialization with None name raises error."""
        with pytest.raises((ValueError, TypeError)):
            ConcreteTestJob(None)

    def test_init_creates_logger(self):
        """Test initialization creates logger."""
        job = ConcreteTestJob("test_job")
        assert job.logger is not None
        assert isinstance(job.logger, logging.Logger)

    def test_init_logger_name_matches_job_name(self):
        """Test logger name matches job name."""
        job = ConcreteTestJob("my_unique_job")
        assert job.logger.name == "my_unique_job"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = JobConfig()
        job = ConcreteTestJob("test_job", config=config)
        assert job.config is config

    def test_init_uses_default_config(self):
        """Test initialization uses default config when not provided."""
        job = ConcreteTestJob("test_job")
        assert job.config is not None
        assert isinstance(job.config, JobConfig)

    def test_init_spark_is_none(self):
        """Test spark session is None after init."""
        job = ConcreteTestJob("test_job")
        assert job.spark is None

    def test_init_metrics_empty(self):
        """Test metrics dict is empty after init."""
        job = ConcreteTestJob("test_job")
        assert job._metrics == {}


class TestBaseSparkJobSetupLogger:
    """Tests for BaseSparkJob._setup_logger method."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_logger_level_is_info(self):
        """Test logger level is set to INFO."""
        job = ConcreteTestJob("test_logger")
        assert job.logger.level == logging.INFO

    def test_logger_has_handler(self):
        """Test logger has at least one handler."""
        job = ConcreteTestJob("test_handler")
        assert len(job.logger.handlers) >= 1

    def test_logger_handler_is_stream_handler(self):
        """Test logger handler is StreamHandler."""
        job = ConcreteTestJob("test_stream")
        # Find the StreamHandler we added
        stream_handlers = [
            h for h in job.logger.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert len(stream_handlers) >= 1


class TestBaseSparkJobGetMetrics:
    """Tests for BaseSparkJob.get_metrics method."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_get_metrics_returns_dict(self):
        """Test get_metrics returns a dictionary."""
        job = ConcreteTestJob("test_metrics")
        metrics = job.get_metrics()
        assert isinstance(metrics, dict)

    def test_get_metrics_returns_copy(self):
        """Test get_metrics returns a copy of metrics."""
        job = ConcreteTestJob("test_metrics_copy")
        job._metrics["test_key"] = "test_value"
        metrics = job.get_metrics()
        metrics["new_key"] = "new_value"
        assert "new_key" not in job._metrics


class TestBaseSparkJobCleanup:
    """Tests for BaseSparkJob.cleanup method."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_cleanup_does_not_raise(self):
        """Test cleanup method does not raise by default."""
        job = ConcreteTestJob("test_cleanup")
        # Should not raise
        job.cleanup()


class TestBaseSparkJobValidateInputs:
    """Tests for BaseSparkJob.validate_inputs method."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_validate_inputs_called(self):
        """Test validate_inputs can be called."""
        job = ConcreteTestJob("test_validate")
        job.validate_inputs()
        assert job.validate_called is True


class TestBaseSparkJobAbstractMethods:
    """Tests for abstract method requirements."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_cannot_instantiate_base_class(self):
        """Test BaseSparkJob cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSparkJob("test")

    def test_subclass_must_implement_extract(self):
        """Test subclass must implement extract method."""

        class IncompleteJob(BaseSparkJob):
            def validate_inputs(self):
                pass

            def transform(self, df):
                return df

            def load(self, df):
                pass

        with pytest.raises(TypeError):
            IncompleteJob("test")

    def test_subclass_must_implement_transform(self):
        """Test subclass must implement transform method."""

        class IncompleteJob(BaseSparkJob):
            def validate_inputs(self):
                pass

            def extract(self):
                return Mock()

            def load(self, df):
                pass

        with pytest.raises(TypeError):
            IncompleteJob("test")

    def test_subclass_must_implement_load(self):
        """Test subclass must implement load method."""

        class IncompleteJob(BaseSparkJob):
            def validate_inputs(self):
                pass

            def extract(self):
                return Mock()

            def transform(self, df):
                return df

        with pytest.raises(TypeError):
            IncompleteJob("test")


class TestBaseSparkJobRun:
    """Tests for BaseSparkJob.run method."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_run_success_returns_true(self):
        """Test run() returns True on successful execution."""
        job = ConcreteTestJob("test_run_success")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            result = job.run()
            assert result is True

    def test_run_calls_all_etl_steps(self):
        """Test run() calls validate, extract, transform, load in order."""
        job = ConcreteTestJob("test_run_steps")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            job.run()
            assert job.validate_called is True
            assert job.extract_called is True
            assert job.transform_called is True
            assert job.load_called is True

    def test_run_sets_success_metrics(self):
        """Test run() sets SUCCESS status in metrics on success."""
        job = ConcreteTestJob("test_run_metrics")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            job.run()
            metrics = job.get_metrics()
            assert metrics["status"] == "SUCCESS"
            assert "total_duration_seconds" in metrics
            assert metrics["job_name"] == "test_run_metrics"

    def test_run_sets_start_time_in_metrics(self):
        """Test run() sets start_time in metrics."""
        job = ConcreteTestJob("test_start_time")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            job.run()
            metrics = job.get_metrics()
            assert "start_time" in metrics

    def test_run_extract_returns_none_raises_error(self):
        """Test run() raises JobExecutionError when extract returns None."""

        class NoneExtractJob(BaseSparkJob):
            def validate_inputs(self):
                pass

            def extract(self):
                return None

            def transform(self, df):
                return df

            def load(self, df):
                pass

        job = NoneExtractJob("test_none_extract")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError, match="Extract step returned None"):
                job.run()

    def test_run_transform_returns_none_raises_error(self):
        """Test run() raises JobExecutionError when transform returns None."""

        class NoneTransformJob(BaseSparkJob):
            def validate_inputs(self):
                pass

            def extract(self):
                return Mock()

            def transform(self, df):
                return None

            def load(self, df):
                pass

        job = NoneTransformJob("test_none_transform")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError, match="Transform step returned None"):
                job.run()

    def test_run_sets_error_metrics_on_failure(self):
        """Test run() sets error metrics when job fails."""

        class FailingJob(BaseSparkJob):
            def validate_inputs(self):
                raise ValueError("Validation failed")

            def extract(self):
                return Mock()

            def transform(self, df):
                return df

            def load(self, df):
                pass

        job = FailingJob("test_error_metrics")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError):
                job.run()
            metrics = job.get_metrics()
            assert metrics["status"] == "FAILED"
            assert "error_message" in metrics
            assert "error_type" in metrics

    def test_run_calls_cleanup_on_success(self):
        """Test run() calls cleanup on successful execution."""
        job = ConcreteTestJob("test_cleanup_success")
        job.cleanup_called = False

        def mark_cleanup():
            job.cleanup_called = True

        job.cleanup = mark_cleanup
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            job.run()
            assert job.cleanup_called is True

    def test_run_calls_cleanup_on_failure(self):
        """Test run() calls cleanup even when job fails."""

        class FailingJob(BaseSparkJob):
            cleanup_called = False

            def validate_inputs(self):
                raise ValueError("Fail")

            def extract(self):
                return Mock()

            def transform(self, df):
                return df

            def load(self, df):
                pass

            def cleanup(self):
                self.cleanup_called = True

        job = FailingJob("test_cleanup_failure")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError):
                job.run()
            assert job.cleanup_called is True

    def test_run_wraps_non_job_execution_error(self):
        """Test run() wraps non-JobExecutionError in JobExecutionError."""

        class TypeErrorJob(BaseSparkJob):
            def validate_inputs(self):
                raise TypeError("Type error")

            def extract(self):
                return Mock()

            def transform(self, df):
                return df

            def load(self, df):
                pass

        job = TypeErrorJob("test_wrap_error")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError) as exc_info:
                job.run()
            assert "Type error" in str(exc_info.value)
            assert exc_info.value.__cause__ is not None

    def test_run_reraises_job_execution_error(self):
        """Test run() re-raises JobExecutionError without wrapping."""

        class JobErrorJob(BaseSparkJob):
            def validate_inputs(self):
                raise JobExecutionError("Direct job error")

            def extract(self):
                return Mock()

            def transform(self, df):
                return df

            def load(self, df):
                pass

        job = JobErrorJob("test_reraise")
        with patch.object(SparkSessionManager, "get_session", return_value=MagicMock()):
            with pytest.raises(JobExecutionError, match="Direct job error"):
                job.run()


class TestBaseSparkJobTrackMetrics:
    """Tests for BaseSparkJob._track_metrics context manager."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_track_metrics_records_duration(self):
        """Test _track_metrics records step duration."""
        job = ConcreteTestJob("test_track_duration")
        with job._track_metrics("test_step"):
            pass
        assert "test_step_duration_seconds" in job._metrics
        assert isinstance(job._metrics["test_step_duration_seconds"], float)

    def test_track_metrics_records_duration_on_exception(self):
        """Test _track_metrics records duration even when exception occurs."""
        job = ConcreteTestJob("test_track_exception")
        try:
            with job._track_metrics("failing_step"):
                raise ValueError("Test error")
        except ValueError:
            pass
        assert "failing_step_duration_seconds" in job._metrics


class TestBaseSparkJobCleanupWithSpark:
    """Tests for BaseSparkJob.cleanup with Spark session."""

    def setup_method(self):
        JobConfig.reset()

    def teardown_method(self):
        JobConfig.reset()

    def test_cleanup_logs_message(self):
        """Test cleanup logs cleanup message."""
        job = ConcreteTestJob("test_cleanup_spark")
        # Should not raise and should log
        job.cleanup()

    def test_cleanup_handles_no_spark_session(self):
        """Test cleanup handles case when spark is None."""
        job = ConcreteTestJob("test_cleanup_no_spark")
        job.spark = None
        # Should not raise
        job.cleanup()

    def test_cleanup_handles_exception_gracefully(self):
        """Test cleanup handles exceptions without raising."""
        job = ConcreteTestJob("test_cleanup_exception")
        # Mock logger to raise exception
        job.logger = MagicMock()
        job.logger.info.side_effect = Exception("Logger error")
        job.logger.warning = MagicMock()
        # Should not raise, should log warning
        job.cleanup()
        job.logger.warning.assert_called_once()

"""
Extended tests for PostgresLoadJob to improve coverage.

Tests cover:
- extract() method with mocked Spark operations
- transform() method with metadata enrichment
- _load_dimension() method with mocked psycopg2
- _load_fact_table() method
- _upsert_via_temp_table() method
- Error handling paths
"""

import pytest
from unittest.mock import patch, MagicMock

from environments.dev.etl.jobs.load.postgres_load_job import (
    PostgresLoadJob,
    run_postgres_load,
)
from environments.dev.etl.jobs.base_job import JobExecutionError
from environments.dev import JobConfig


class TestPostgresLoadJobExtract:
    """Tests for PostgresLoadJob.extract() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_reads_dimension_tables(self):
        """Test extract reads all dimension tables from gold layer."""
        job = PostgresLoadJob("yellow")

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 100
        mock_df.filter.return_value = mock_df
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark
        result = job.extract()

        assert "dim_date" in result
        assert "dim_location" in result
        assert "dim_payment" in result
        assert "fact_trip" in result

    def test_extract_reads_fact_table(self):
        """Test extract reads fact_trip table."""
        job = PostgresLoadJob("yellow")

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 1000
        mock_df.filter.return_value = mock_df
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark
        result = job.extract()

        assert "fact_trip" in result

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_extract_applies_year_filter(self, mock_F):
        """Test extract applies year filter to fact table."""
        job = PostgresLoadJob("yellow", year=2024)

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 500
        mock_df.filter.return_value = mock_df
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark
        job.extract()

        # Verify filter was called (for year)
        mock_df.filter.assert_called()

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_extract_applies_year_and_month_filter(self, mock_F):
        """Test extract applies both year and month filters."""
        job = PostgresLoadJob("yellow", year=2024, month=6)

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 100
        mock_df.filter.return_value = mock_df
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark
        job.extract()

        # Filter should be called twice (year and month)
        assert mock_df.filter.call_count >= 2

    def test_extract_raises_on_dimension_read_failure(self):
        """Test extract raises JobExecutionError on dimension read failure."""
        job = PostgresLoadJob("yellow")

        mock_spark = MagicMock()
        mock_spark.read.parquet.side_effect = Exception("Read failed")

        job.spark = mock_spark
        with pytest.raises(JobExecutionError, match="Failed to read dim_date"):
            job.extract()

    def test_extract_raises_on_fact_read_failure(self):
        """Test extract raises JobExecutionError on fact table read failure."""
        job = PostgresLoadJob("yellow")

        mock_spark = MagicMock()
        mock_dim_df = MagicMock()
        mock_dim_df.count.return_value = 100

        call_count = [0]

        def parquet_side_effect(path):
            call_count[0] += 1
            if "fact_trip" in path:
                raise Exception("Fact read failed")
            return mock_dim_df

        mock_spark.read.parquet.side_effect = parquet_side_effect

        job.spark = mock_spark
        with pytest.raises(JobExecutionError, match="Failed to read fact_trip"):
            job.extract()


class TestPostgresLoadJobTransform:
    """Tests for PostgresLoadJob.transform() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_transform_adds_metadata_columns(self, mock_F):
        """Test transform adds load metadata columns."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.withColumn.return_value = mock_df
        mock_df.count.return_value = 100

        dimensional_model = {
            "dim_date": mock_df,
            "dim_location": mock_df,
            "dim_payment": mock_df,
            "fact_trip": mock_df,
        }

        result = job.transform(dimensional_model)

        # Verify all tables are in result
        assert "dim_date" in result
        assert "dim_location" in result
        assert "dim_payment" in result
        assert "fact_trip" in result

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_transform_calls_withColumn_for_metadata(self, mock_F):
        """Test transform calls withColumn for each metadata field."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.withColumn.return_value = mock_df
        mock_df.count.return_value = 50

        dimensional_model = {"dim_date": mock_df}

        job.transform(dimensional_model)

        # Should call withColumn for postgres_load_timestamp,
        # postgres_load_date, load_job_name
        assert mock_df.withColumn.call_count >= 3

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_transform_preserves_all_tables(self, mock_F):
        """Test transform returns all input tables."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.withColumn.return_value = mock_df
        mock_df.count.return_value = 10

        input_tables = {
            "dim_date": mock_df,
            "dim_location": mock_df,
            "dim_payment": mock_df,
            "fact_trip": mock_df,
        }

        result = job.transform(input_tables)

        assert len(result) == len(input_tables)


class TestPostgresLoadJobLoadDimension:
    """Tests for PostgresLoadJob._load_dimension() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_load_dimension_truncates_table(self):
        """Test _load_dimension truncates table before insert."""
        import sys

        mock_psycopg2 = MagicMock()
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.count.return_value = 100

            job._load_dimension(mock_df, "taxi.dim_date", "dim_date")

            # Verify TRUNCATE was executed
            mock_cursor.execute.assert_called()
            truncate_call = mock_cursor.execute.call_args[0][0]
            assert "TRUNCATE" in truncate_call
        finally:
            del sys.modules["psycopg2"]

    def test_load_dimension_writes_via_jdbc(self):
        """Test _load_dimension writes data via Spark JDBC."""
        import sys

        mock_psycopg2 = MagicMock()
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.count.return_value = 100

            job._load_dimension(mock_df, "taxi.dim_date", "dim_date")

            # Verify JDBC write was called
            mock_df.write.jdbc.assert_called_once()
        finally:
            del sys.modules["psycopg2"]

    def test_load_dimension_handles_psycopg2_error(self):
        """Test _load_dimension handles psycopg2 errors."""
        import sys

        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception
        mock_psycopg2.connect.side_effect = Exception("Connection failed")
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_df = MagicMock()
            mock_df.count.return_value = 100

            with pytest.raises(JobExecutionError, match="Failed to load dim_date"):
                job._load_dimension(mock_df, "taxi.dim_date", "dim_date")
        finally:
            del sys.modules["psycopg2"]

    def test_load_dimension_parses_jdbc_url(self):
        """Test _load_dimension correctly parses JDBC URL."""
        import sys

        mock_psycopg2 = MagicMock()
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob(
                "yellow", postgres_url="jdbc:postgresql://myhost:5433/mydb"
            )

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.count.return_value = 50

            job._load_dimension(mock_df, "taxi.dim_location", "dim_location")

            # Verify connect was called with parsed parameters
            connect_call = mock_psycopg2.connect.call_args
            assert connect_call[1]["host"] == "myhost"
            assert connect_call[1]["port"] == 5433
            assert connect_call[1]["database"] == "mydb"
        finally:
            del sys.modules["psycopg2"]


class TestPostgresLoadJobLoadFactTable:
    """Tests for PostgresLoadJob._load_fact_table() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_load_fact_table_requires_fact_hash(self):
        """Test _load_fact_table raises error if fact_hash column missing."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.columns = ["col1", "col2"]  # No fact_hash
        mock_df.count.return_value = 100

        with pytest.raises(JobExecutionError, match="fact_hash column not found"):
            job._load_fact_table(mock_df)

    def test_load_fact_table_calls_upsert(self):
        """Test _load_fact_table calls _upsert_via_temp_table."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.columns = ["fact_hash", "col1", "col2"]
        mock_df.count.return_value = 1000

        with patch.object(job, "_upsert_via_temp_table") as mock_upsert:
            job._load_fact_table(mock_df)
            mock_upsert.assert_called_once_with(mock_df, "taxi.fact_trip")

    def test_load_fact_table_handles_upsert_error(self):
        """Test _load_fact_table handles upsert errors."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.columns = ["fact_hash", "col1"]
        mock_df.count.return_value = 100

        with patch.object(
            job, "_upsert_via_temp_table", side_effect=Exception("Upsert failed")
        ):
            with pytest.raises(JobExecutionError, match="Failed to upsert fact_trip"):
                job._load_fact_table(mock_df)


class TestPostgresLoadJobUpsert:
    """Tests for PostgresLoadJob._upsert_via_temp_table() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_upsert_creates_temp_table(self):
        """Test _upsert_via_temp_table creates temporary table."""
        import sys

        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception  # Make Error a proper exception class
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,)  # For row count queries
            mock_cursor.fetchall.return_value = []  # For index queries
            mock_cursor.rowcount = 10  # For rows affected formatting
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.columns = ["fact_hash", "col1", "col2"]
            mock_df.count.return_value = 100  # For record count formatting

            job._upsert_via_temp_table(mock_df, "taxi.fact_trip")

            # Verify temp table operations
            assert mock_cursor.execute.called
        finally:
            del sys.modules["psycopg2"]

    def test_upsert_writes_to_temp_table(self):
        """Test _upsert_via_temp_table writes data to temp table."""
        import sys

        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception  # Make Error a proper exception class
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,)  # For row count queries
            mock_cursor.fetchall.return_value = []  # For index queries
            mock_cursor.rowcount = 10  # For rows affected formatting
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.columns = ["fact_hash", "amount"]
            mock_df.count.return_value = 100  # For record count formatting

            job._upsert_via_temp_table(mock_df, "taxi.fact_trip")

            # Verify JDBC write was called
            mock_df.write.jdbc.assert_called()
        finally:
            del sys.modules["psycopg2"]

    def test_upsert_executes_merge_sql(self):
        """Test _upsert_via_temp_table executes INSERT ON CONFLICT."""
        import sys

        mock_psycopg2 = MagicMock()
        mock_psycopg2.Error = Exception  # Make Error a proper exception class
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob("yellow")

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = (0,)  # For row count queries
            mock_cursor.fetchall.return_value = []  # For index queries
            mock_cursor.rowcount = 10  # For rows affected formatting
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.columns = ["fact_hash", "trip_id"]
            mock_df.count.return_value = 100  # For record count formatting

            job._upsert_via_temp_table(mock_df, "taxi.fact_trip")

            # Verify SQL execution
            assert mock_cursor.execute.called
        finally:
            del sys.modules["psycopg2"]


class TestPostgresLoadJobLoad:
    """Tests for PostgresLoadJob.load() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_load_calls_dimension_loaders(self):
        """Test load() calls _load_dimension for each dimension."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()

        dimensional_model = {
            "dim_date": mock_df,
            "dim_location": mock_df,
            "dim_payment": mock_df,
            "fact_trip": mock_df,
        }

        with patch.object(job, "_load_dimension") as mock_load_dim:
            with patch.object(job, "_load_fact_table"):
                job.load(dimensional_model)

        # Should be called 3 times (one for each dimension)
        assert mock_load_dim.call_count == 3

    def test_load_calls_fact_loader_last(self):
        """Test load() calls _load_fact_table after dimensions."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        call_order = []

        dimensional_model = {
            "dim_date": mock_df,
            "dim_location": mock_df,
            "dim_payment": mock_df,
            "fact_trip": mock_df,
        }

        def track_dim_call(*args):
            call_order.append("dimension")

        def track_fact_call(*args):
            call_order.append("fact")

        with patch.object(job, "_load_dimension", side_effect=track_dim_call):
            with patch.object(job, "_load_fact_table", side_effect=track_fact_call):
                job.load(dimensional_model)

        # Fact should be loaded last
        assert call_order[-1] == "fact"
        assert call_order.count("dimension") == 3


class TestPostgresLoadJobIntegration:
    """Integration-style tests for PostgresLoadJob."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_full_job_flow_with_mocks(self, mock_F):
        """Test complete job flow with all methods mocked."""
        job = PostgresLoadJob("yellow", year=2024, month=6)

        mock_df = MagicMock()
        mock_df.count.return_value = 100
        mock_df.filter.return_value = mock_df
        mock_df.withColumn.return_value = mock_df
        mock_df.columns = ["fact_hash", "col1"]

        mock_spark = MagicMock()
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark

        with patch.object(job, "_load_dimension"):
            with patch.object(job, "_load_fact_table"):
                # Run the full ETL flow
                extracted = job.extract()
                transformed = job.transform(extracted)
                job.load(transformed)

    def test_run_postgres_load_with_all_params(self):
        """Test run_postgres_load function with all parameters."""
        with patch(
            "environments.dev.etl.jobs.load.postgres_load_job.PostgresLoadJob"
        ) as MockJob:
            mock_instance = MagicMock()
            mock_instance.run.return_value = True
            MockJob.return_value = mock_instance

            result = run_postgres_load(
                taxi_type="green",
                year=2024,
                month=3,
                postgres_url="jdbc:postgresql://test:5432/db",
                postgres_user="user",
                postgres_password="pass",
            )

            assert result is True
            MockJob.assert_called_once()


class TestPostgresLoadJobEdgeCases:
    """Edge case tests for PostgresLoadJob."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_extract_with_empty_dataframe(self):
        """Test extract handles empty DataFrames."""
        job = PostgresLoadJob("yellow")

        mock_spark = MagicMock()
        mock_df = MagicMock()
        mock_df.count.return_value = 0
        mock_df.filter.return_value = mock_df
        mock_spark.read.parquet.return_value = mock_df

        job.spark = mock_spark
        result = job.extract()

        assert "fact_trip" in result

    @patch("environments.dev.etl.jobs.load.postgres_load_job.F")
    def test_transform_with_single_table(self, mock_F):
        """Test transform works with single table."""
        job = PostgresLoadJob("yellow")

        mock_df = MagicMock()
        mock_df.withColumn.return_value = mock_df
        mock_df.count.return_value = 1

        result = job.transform({"dim_date": mock_df})

        assert "dim_date" in result

    def test_load_dimension_with_default_port(self):
        """Test _load_dimension uses default port when not specified."""
        import sys

        mock_psycopg2 = MagicMock()
        sys.modules["psycopg2"] = mock_psycopg2

        try:
            job = PostgresLoadJob(
                "yellow", postgres_url="jdbc:postgresql://myhost/mydb"
            )

            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.cursor.return_value = mock_cursor
            mock_psycopg2.connect.return_value = mock_conn

            mock_df = MagicMock()
            mock_df.count.return_value = 10

            job._load_dimension(mock_df, "taxi.dim_date", "dim_date")

            # Verify default port 5432 was used
            connect_call = mock_psycopg2.connect.call_args
            assert connect_call[1]["port"] == 5432
        finally:
            del sys.modules["psycopg2"]


class TestPostgresLoadJobValidateInputs:
    """Tests for PostgresLoadJob.validate_inputs() method."""

    def setup_method(self):
        """Reset JobConfig singleton before each test."""
        JobConfig.reset()

    def teardown_method(self):
        """Reset JobConfig singleton after each test."""
        JobConfig.reset()

    def test_validate_inputs_logs_connection_info(self):
        """Test validate_inputs logs connection information."""
        job = PostgresLoadJob("yellow")
        # Should not raise
        job.validate_inputs()

    def test_validate_inputs_with_year_month_filter(self):
        """Test validate_inputs with year and month filter."""
        job = PostgresLoadJob("yellow", year=2024, month=6)
        # Should not raise
        job.validate_inputs()

    def test_validate_inputs_with_year_only_filter(self):
        """Test validate_inputs with year only filter."""
        job = PostgresLoadJob("yellow", year=2024)
        # Should not raise
        job.validate_inputs()

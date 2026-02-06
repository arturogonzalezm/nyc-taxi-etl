"""
BigQuery Load Job - Load Dimensional Model to BigQuery

This module implements the load layer pipeline that reads the gold layer
dimensional model and loads it into BigQuery for analytics and BI tools.

Architecture:
    - Reads from Gold layer (Parquet files in GCS)
    - Loads into BigQuery using Spark BigQuery connector
    - Supports both full refresh and incremental loads
    - Handles yellow and green taxi data

Features:
    - Native BigQuery integration via Spark connector
    - Partitioned table support for cost optimization
    - MERGE operations for idempotent loads
    - Progress tracking and logging
    - Error handling with proper cleanup

Design Patterns:
    - Template Method: Inherits from BaseSparkJob
    - Batch Processing: Efficient bulk loads via BigQuery connector
"""

import sys
import os

from pathlib import Path

# Add project root to path for imports when running as script
if __name__ == "__main__":
    project_root = Path(__file__).resolve().parents[4]
    sys.path.insert(0, str(project_root))

import logging
from typing import Literal, Optional
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from environments.prod.etl.jobs.base_job import BaseSparkJob, JobExecutionError
from environments.prod.etl.jobs.utils.config import JobConfig

logger = logging.getLogger(__name__)


class BigQueryLoadJob(BaseSparkJob):
    """
    Production-ready BigQuery load job for dimensional model.

    This job reads the gold layer dimensional model and loads it into
    BigQuery for analytics, reporting, and BI tool consumption.

    Features:
        - Loads fact and dimension tables
        - Native BigQuery connector (optimized for performance)
        - Configurable load modes (overwrite, append, merge)
        - Partitioned table support
        - Progress tracking

    Load Strategy:
        - Dimensions: Truncate and reload (SCD Type 1)
        - Facts: MERGE for idempotent loads using fact_hash

    Example:
        >>> # Load all tables for yellow taxi
        >>> job = BigQueryLoadJob("yellow")
        >>> success = job.run()
        >>>
        >>> # Load specific month
        >>> job = BigQueryLoadJob("yellow", year=2024, month=1)
        >>> success = job.run()

    Attributes:
        taxi_type: Type of taxi data (yellow or green)
        year: Optional year filter for fact table
        month: Optional month filter for fact table
        project_id: GCP project ID
        dataset: BigQuery dataset name
    """

    def __init__(
        self,
        taxi_type: Literal["yellow", "green"],
        year: Optional[int] = None,
        month: Optional[int] = None,
        project_id: Optional[str] = None,
        dataset: Optional[str] = None,
        config: Optional[JobConfig] = None,
    ):
        """
        Initialise the BigQuery load job.

        :params taxi_type: Type of taxi data (yellow or green)
        :params year: Optional year filter (loads all if not specified)
        :params month: Optional month filter (loads all if not specified)
        :params project_id: GCP project ID (defaults to env var or config)
        :params dataset: BigQuery dataset name (defaults to 'taxi')
        :params config: Optional job configuration
        :raises ValueError: If parameters are invalid
        """
        if taxi_type not in ["yellow", "green"]:
            raise ValueError(f"Invalid taxi_type: {taxi_type}")

        super().__init__(
            job_name=f"BigQueryLoad_{taxi_type}_{year or 'all'}_{month or 'all'}",
            config=config,
        )

        self.taxi_type = taxi_type
        self.year = year
        self.month = month

        # BigQuery connection parameters
        self.project_id = project_id or os.getenv(
            "GCP_PROJECT_ID", self.config.gcs.project_id
        )
        self.dataset = dataset or os.getenv("BIGQUERY_DATASET", "taxi")

        # Temporary GCS bucket for BigQuery connector staging
        self.temp_gcs_bucket = os.getenv("GCS_BUCKET", self.config.gcs.bucket)

    def validate_inputs(self):
        """
        Validate job inputs and BigQuery connectivity.

        :raises JobExecutionError: If validation fails
        """
        self.logger.info(
            f"Validating BigQuery connection: {self.project_id}.{self.dataset}"
        )
        self.logger.info(f"Loading data for: {self.taxi_type} taxi")
        if self.year and self.month:
            self.logger.info(f"Filtered to: {self.year}-{self.month:02d}")
        elif self.year:
            self.logger.info(f"Filtered to year: {self.year}")
        else:
            self.logger.info("Loading all available data")

        # Validate required configuration
        if not self.project_id:
            raise JobExecutionError("GCP_PROJECT_ID not configured")
        if not self.dataset:
            raise JobExecutionError("BIGQUERY_DATASET not configured")

    def extract(self) -> dict:
        """
        Extract dimensional model from gold layer.

        :returns: Dictionary with DataFrames:
            {
                'fact_trip': DataFrame,
                'dim_date': DataFrame,
                'dim_location': DataFrame,
                'dim_payment': DataFrame
            }

        :raises JobExecutionError: If extraction fails
        """
        gold_base_path = self.config.get_storage_path("gold", taxi_type=self.taxi_type)
        self.logger.info(f"Reading dimensional model from: {gold_base_path}")

        dimensional_model = {}

        # Read dimension tables (always load all dimensions)
        for dim_name in ["dim_date", "dim_location", "dim_payment"]:
            dim_path = f"{gold_base_path}/{dim_name}"
            self.logger.info(f"Reading {dim_name} from {dim_path}")

            try:
                dim_df = self.spark.read.parquet(dim_path)
                dim_count = dim_df.count()
                self.logger.info(f"Loaded {dim_name}: {dim_count:,} records")
                dimensional_model[dim_name] = dim_df
            except Exception as e:
                raise JobExecutionError(f"Failed to read {dim_name}: {e}") from e

        # Read fact table (with optional year/month filter)
        fact_path = f"{gold_base_path}/fact_trip"
        self.logger.info(f"Reading fact_trip from {fact_path}")

        try:
            fact_df = self.spark.read.parquet(fact_path)

            # Apply filters if specified
            if self.year:
                fact_df = fact_df.filter(F.col("partition_year") == self.year)
                if self.month:
                    fact_df = fact_df.filter(F.col("partition_month") == self.month)

            fact_count = fact_df.count()
            self.logger.info(f"Loaded fact_trip: {fact_count:,} records")
            dimensional_model["fact_trip"] = fact_df

        except Exception as e:
            raise JobExecutionError(f"Failed to read fact_trip: {e}") from e

        return dimensional_model

    def transform(self, dimensional_model: dict) -> dict:
        """
        Transform data for BigQuery (minimal transformations).

        Adds load layer metadata timestamps to track when data was loaded to BigQuery.

        :params dimensional_model: Dictionary with dimensional model DataFrames
        :returns: Dictionary with metadata-enriched DataFrames
        """

        self.logger.info("=== Preparing data for BigQuery ===")

        # Add load layer metadata to all tables
        enriched_model = {}
        for table_name, df in dimensional_model.items():
            # Add load timestamp metadata
            df_with_metadata = (
                df.withColumn("bigquery_load_timestamp", F.current_timestamp())
                .withColumn("bigquery_load_date", F.current_date())
                .withColumn("load_job_name", F.lit(self.job_name))
            )

            count = df_with_metadata.count()
            self.logger.info(f"{table_name}: {count:,} records ready for load")
            enriched_model[table_name] = df_with_metadata

        return enriched_model

    def load(self, dimensional_model: dict):
        """
        Load dimensional model into BigQuery.

        Loads data in this order (ALWAYS):
        1. Dimensions first (overwrite - maintains referential integrity)
        2. Fact table last (merge - references dimensions via FK)

        This order ensures:
        - Dimensions exist before facts reference them
        - Idempotent loads (can re-run safely)

        :params dimensional_model: Dictionary with dimensional model DataFrames
        :raises JobExecutionError: If load fails
        """
        self.logger.info("=== Loading data to BigQuery ===")

        # ALWAYS load dimensions first
        # Dimensions must exist before fact table
        dimension_tables = {
            "dim_date": f"{self.dataset}.dim_date",
            "dim_location": f"{self.dataset}.dim_location",
            "dim_payment": f"{self.dataset}.dim_payment",
        }

        self.logger.info("Step 1/2: Loading dimension tables...")
        for dim_name, table_name in dimension_tables.items():
            self._load_dimension(dimensional_model[dim_name], table_name, dim_name)

        # Load fact table AFTER dimensions (always, regardless of full/incremental)
        self.logger.info("Step 2/2: Loading fact table...")
        self._load_fact_table(dimensional_model["fact_trip"])

        self.logger.info("=== BigQuery load complete ===")

    def _load_dimension(self, df: DataFrame, table_name: str, dim_name: str):
        """
        Load a dimension table to BigQuery using overwrite mode.

        Strategy: OVERWRITE (SCD Type 1 - full refresh)

        :params df: Dimension DataFrame
        :params table_name: BigQuery table name (dataset.table)
        :params dim_name: Dimension name for logging
        """

        self.logger.info(f"Loading {dim_name} to {table_name}...")
        record_count = df.count()

        try:
            # Write to BigQuery using Spark BigQuery connector
            df.write.format("bigquery").option(
                "table", f"{self.project_id}.{table_name}"
            ).option("temporaryGcsBucket", self.temp_gcs_bucket).option(
                "writeMethod", "direct"
            ).mode(
                "overwrite"
            ).save()

            self.logger.info(f"✓ Loaded {dim_name}: {record_count:,} records")

        except Exception as e:
            self.logger.error(f"Error loading {dim_name}: {e}")
            raise JobExecutionError(f"Failed to load {dim_name}: {e}") from e

    def _load_fact_table(self, df: DataFrame):
        """
        Load fact table to BigQuery using MERGE for idempotency.

        Strategy (Idempotent using fact_hash):
        - Uses BigQuery MERGE statement via temporary table
        - Only inserts records if fact_hash doesn't exist
        - Safe to re-run without creating duplicates
        - Tracks load timestamps for audit trail

        This makes the pipeline idempotent - safe to re-run any time!

        :params df: Fact DataFrame with fact_hash column
        """
        table_name = f"{self.dataset}.fact_trip"
        full_table_name = f"{self.project_id}.{table_name}"
        record_count = df.count()

        # Verify fact_hash column exists
        if "fact_hash" not in df.columns:
            raise JobExecutionError(
                "fact_hash column not found - cannot perform idempotent load"
            )

        self.logger.info("Loading fact_trip using MERGE (idempotent)...")
        self.logger.info(f"Records to merge: {record_count:,}")

        try:
            # For initial load or small datasets, use direct write
            # For incremental loads, we use a staging table approach

            # First, check if table exists and has data
            try:
                existing_count = (
                    self.spark.read.format("bigquery")
                    .option("table", full_table_name)
                    .load()
                    .count()
                )
                is_initial_load = existing_count == 0
            except Exception:
                # Table doesn't exist yet
                is_initial_load = True

            if is_initial_load:
                self.logger.info("Target table is empty/new - using direct INSERT")

                # Direct write for initial load (faster)
                df.write.format("bigquery").option("table", full_table_name).option(
                    "temporaryGcsBucket", self.temp_gcs_bucket
                ).option("writeMethod", "direct").option(
                    "partitionField", "pickup_datetime"
                ).option(
                    "partitionType", "DAY"
                ).option(
                    "clusteredFields",
                    "pickup_location_key,dropoff_location_key,date_key",
                ).mode(
                    "overwrite"
                ).save()

                self.logger.info(
                    f"✓ Initial load complete: {record_count:,} rows inserted"
                )
            else:
                self.logger.info(
                    f"Target table has {existing_count:,} rows - using MERGE"
                )

                # Write to staging table first
                staging_table = f"{full_table_name}_staging"
                self.logger.info(f"Writing to staging table: {staging_table}")

                df.write.format("bigquery").option("table", staging_table).option(
                    "temporaryGcsBucket", self.temp_gcs_bucket
                ).option("writeMethod", "direct").mode("overwrite").save()

                # Execute MERGE using BigQuery SQL
                merge_sql = f"""
                MERGE `{full_table_name}` AS target
                USING `{staging_table}` AS source
                ON target.fact_hash = source.fact_hash
                WHEN NOT MATCHED THEN
                    INSERT ROW
                """

                self.logger.info("Executing MERGE statement...")

                # Execute MERGE via BigQuery client
                from google.cloud import bigquery

                client = bigquery.Client(project=self.project_id)

                query_job = client.query(merge_sql)
                result = query_job.result()  # Wait for completion

                # Get rows affected
                rows_inserted = query_job.num_dml_affected_rows or 0
                self.logger.info(
                    f"✓ MERGE complete: {rows_inserted:,} new rows inserted"
                )

                # Clean up staging table
                self.logger.info("Cleaning up staging table...")
                client.delete_table(staging_table, not_found_ok=True)
                self.logger.info(f"✓ Deleted staging table: {staging_table}")

        except Exception as e:
            self.logger.error(f"Error loading fact_trip: {e}")
            raise JobExecutionError(f"Failed to load fact_trip: {e}") from e


def run_bigquery_load(
    taxi_type: Literal["yellow", "green"],
    year: Optional[int] = None,
    month: Optional[int] = None,
    project_id: Optional[str] = None,
    dataset: Optional[str] = None,
) -> bool:
    """
    Convenience function to run the BigQuery load job.

    :params taxi_type: Type of taxi (yellow or green)
    :params year: Optional year filter
    :params month: Optional month filter
    :params project_id: Optional GCP project ID
    :params dataset: Optional BigQuery dataset name
    :returns: True if successful, False otherwise
    """
    job = BigQueryLoadJob(taxi_type, year, month, project_id, dataset)
    return job.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="BigQuery Load Job")
    parser.add_argument(
        "--taxi-type", type=str, choices=["yellow", "green"], required=True
    )
    parser.add_argument("--year", type=int, help="Year filter (optional)")
    parser.add_argument("--month", type=int, help="Month filter (optional)")
    parser.add_argument("--project-id", type=str, help="GCP Project ID")
    parser.add_argument("--dataset", type=str, help="BigQuery dataset name")

    args = parser.parse_args()

    success = run_bigquery_load(
        args.taxi_type,
        args.year,
        args.month,
        args.project_id,
        args.dataset,
    )
    exit(0 if success else 1)

-- BigQuery Dimensional Model Schema for NYC Taxi ETL
-- This script creates the taxi dataset and all dimensional model tables
-- Run via BigQuery console or bq command-line tool

-- ============================================================================
-- CREATE DATASET (equivalent to PostgreSQL schema)
-- ============================================================================
-- Note: Run this command separately or via Terraform:
-- CREATE SCHEMA IF NOT EXISTS `project_id.taxi`;

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- dim_date: Date dimension with calendar attributes
CREATE TABLE IF NOT EXISTS taxi.dim_date (
    date_key INT64 NOT NULL,
    date DATE NOT NULL,
    year INT64 NOT NULL,
    quarter INT64 NOT NULL,
    month INT64 NOT NULL,
    month_name STRING NOT NULL,
    day INT64 NOT NULL,
    day_of_week INT64 NOT NULL,
    day_of_week_name STRING NOT NULL,
    is_weekend BOOL NOT NULL,
    week_of_year INT64 NOT NULL,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    data_layer STRING DEFAULT 'gold',
    -- Load metadata (added by bigquery_load_job)
    bigquery_load_timestamp TIMESTAMP,
    bigquery_load_date DATE,
    load_job_name STRING
)
OPTIONS (
    description = 'Date dimension with calendar attributes for time-based analysis'
);

-- dim_location: Location dimension based on NYC taxi zones
CREATE TABLE IF NOT EXISTS taxi.dim_location (
    location_key INT64 NOT NULL,
    borough STRING,
    zone STRING,
    service_zone STRING,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    data_layer STRING DEFAULT 'gold',
    -- Load metadata (added by bigquery_load_job)
    bigquery_load_timestamp TIMESTAMP,
    bigquery_load_date DATE,
    load_job_name STRING
)
OPTIONS (
    description = 'Location dimension based on NYC taxi zones'
);

-- dim_payment: Payment type and rate code dimension
CREATE TABLE IF NOT EXISTS taxi.dim_payment (
    payment_key INT64 NOT NULL,
    payment_type_id INT64,
    payment_type_desc STRING,
    rate_code_id INT64,
    rate_code_desc STRING,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    data_layer STRING DEFAULT 'gold',
    -- Load metadata (added by bigquery_load_job)
    bigquery_load_timestamp TIMESTAMP,
    bigquery_load_date DATE,
    load_job_name STRING
)
OPTIONS (
    description = 'Payment type and rate code dimension'
);

-- ============================================================================
-- FACT TABLE
-- ============================================================================

-- fact_trip: Central fact table containing trip metrics
-- Partitioned by pickup_datetime for query performance and cost optimization
-- Clustered by pickup_location_key and dropoff_location_key for common query patterns
CREATE TABLE IF NOT EXISTS taxi.fact_trip (
    trip_key INT64 NOT NULL,
    date_key INT64 NOT NULL,
    pickup_location_key INT64,
    dropoff_location_key INT64,
    payment_key INT64,
    pickup_datetime TIMESTAMP NOT NULL,
    dropoff_datetime TIMESTAMP NOT NULL,
    passenger_count INT64,
    trip_distance FLOAT64,
    trip_duration_seconds INT64,
    trip_duration_minutes FLOAT64,
    fare_amount FLOAT64,
    extra FLOAT64,
    mta_tax FLOAT64,
    tip_amount FLOAT64,
    tolls_amount FLOAT64,
    total_amount FLOAT64,
    tip_percentage FLOAT64,
    avg_speed_mph FLOAT64,
    partition_year INT64,
    partition_month INT64,
    gold_transformation_timestamp TIMESTAMP,
    gold_transformation_date DATE,
    gold_job_name STRING,
    data_layer STRING DEFAULT 'gold',
    fact_hash STRING NOT NULL,
    -- Load metadata (added by bigquery_load_job)
    bigquery_load_timestamp TIMESTAMP,
    bigquery_load_date DATE,
    load_job_name STRING
)
PARTITION BY DATE(pickup_datetime)
CLUSTER BY pickup_location_key, dropoff_location_key, date_key
OPTIONS (
    description = 'Central fact table containing trip metrics',
    require_partition_filter = false
);

-- ============================================================================
-- NOTES ON BIGQUERY CONSTRAINTS AND INDEXES
-- ============================================================================
-- 
-- BigQuery handles constraints and performance optimization differently than PostgreSQL:
--
-- 1. PRIMARY KEYS: BigQuery supports PRIMARY KEY constraints (not enforced, for documentation)
--    but they are optional. The fact_hash column serves as a logical unique identifier.
--
-- 2. FOREIGN KEYS: BigQuery supports FOREIGN KEY constraints (not enforced, for documentation)
--    but they are optional. Referential integrity should be maintained by the ETL process.
--
-- 3. INDEXES: BigQuery does not use traditional indexes. Instead:
--    - PARTITIONING: Divides table into segments for faster queries and lower costs
--    - CLUSTERING: Sorts data within partitions for efficient filtering
--
-- 4. UNIQUE CONSTRAINTS: Not enforced in BigQuery. Use MERGE statements or 
--    deduplication queries to maintain uniqueness.
--
-- ============================================================================

-- ============================================================================
-- OPTIONAL: Add primary key constraints (not enforced, for documentation only)
-- ============================================================================
-- These can be added if using BigQuery's constraint feature for documentation:
--
-- ALTER TABLE taxi.dim_date ADD PRIMARY KEY (date_key) NOT ENFORCED;
-- ALTER TABLE taxi.dim_location ADD PRIMARY KEY (location_key) NOT ENFORCED;
-- ALTER TABLE taxi.dim_payment ADD PRIMARY KEY (payment_key) NOT ENFORCED;
-- ALTER TABLE taxi.fact_trip ADD PRIMARY KEY (trip_key) NOT ENFORCED;

-- ============================================================================
-- OPTIONAL: Add foreign key constraints (not enforced, for documentation only)
-- ============================================================================
-- These can be added if using BigQuery's constraint feature for documentation:
--
-- ALTER TABLE taxi.fact_trip
--     ADD CONSTRAINT fk_fact_trip_date
--     FOREIGN KEY (date_key) REFERENCES taxi.dim_date(date_key) NOT ENFORCED;
--
-- ALTER TABLE taxi.fact_trip
--     ADD CONSTRAINT fk_fact_trip_pickup_location
--     FOREIGN KEY (pickup_location_key) REFERENCES taxi.dim_location(location_key) NOT ENFORCED;
--
-- ALTER TABLE taxi.fact_trip
--     ADD CONSTRAINT fk_fact_trip_dropoff_location
--     FOREIGN KEY (dropoff_location_key) REFERENCES taxi.dim_location(location_key) NOT ENFORCED;
--
-- ALTER TABLE taxi.fact_trip
--     ADD CONSTRAINT fk_fact_trip_payment
--     FOREIGN KEY (payment_key) REFERENCES taxi.dim_payment(payment_key) NOT ENFORCED;

-- ============================================================================
-- SAMPLE QUERIES (BigQuery SQL syntax)
-- ============================================================================

-- Trips by Borough
-- SELECT 
--     l.borough,
--     COUNT(*) as trip_count,
--     AVG(f.total_amount) as avg_fare
-- FROM taxi.fact_trip f
-- JOIN taxi.dim_location l ON f.pickup_location_key = l.location_key
-- GROUP BY l.borough
-- ORDER BY trip_count DESC;

-- Daily Revenue
-- SELECT 
--     d.date,
--     d.day_of_week_name,
--     SUM(f.total_amount) as daily_revenue,
--     COUNT(*) as trip_count
-- FROM taxi.fact_trip f
-- JOIN taxi.dim_date d ON f.date_key = d.date_key
-- GROUP BY d.date, d.day_of_week_name
-- ORDER BY d.date;

-- Payment Method Analysis
-- SELECT 
--     p.payment_type_desc as payment_method,
--     COUNT(*) as trip_count,
--     SUM(f.total_amount) as total_revenue,
--     AVG(f.tip_amount) as avg_tip
-- FROM taxi.fact_trip f
-- JOIN taxi.dim_payment p ON f.payment_key = p.payment_key
-- GROUP BY p.payment_type_desc
-- ORDER BY trip_count DESC;

-- ============================================================================
-- IAM PERMISSIONS (managed via Terraform or GCP Console)
-- ============================================================================
-- BigQuery uses IAM for access control instead of GRANT statements.
-- Common roles:
--   - roles/bigquery.dataViewer: Read access to tables
--   - roles/bigquery.dataEditor: Read/write access to tables
--   - roles/bigquery.dataOwner: Full control over tables
--   - roles/bigquery.user: Run queries and jobs
--
-- Example (via gcloud CLI):
-- gcloud projects add-iam-policy-binding PROJECT_ID \
--     --member="serviceAccount:etl-sa@PROJECT_ID.iam.gserviceaccount.com" \
--     --role="roles/bigquery.dataEditor"

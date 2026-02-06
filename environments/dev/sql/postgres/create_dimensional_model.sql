-- PostgreSQL Dimensional Model Schema for NYC Taxi ETL
-- This script creates the taxi schema and all dimensional model tables
-- Run automatically on PostgreSQL container startup via docker-entrypoint-initdb.d

-- Create schema
CREATE SCHEMA IF NOT EXISTS taxi;

-- ============================================================================
-- DIMENSION TABLES
-- ============================================================================

-- dim_date: Date dimension with calendar attributes
CREATE TABLE IF NOT EXISTS taxi.dim_date (
    date_key INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    month INTEGER NOT NULL,
    month_name VARCHAR(20) NOT NULL,
    day INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    day_of_week_name VARCHAR(20) NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    week_of_year INTEGER NOT NULL,
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_layer VARCHAR(10) DEFAULT 'gold',
    -- Load metadata (added by postgres_load_job)
    postgres_load_timestamp TIMESTAMP,
    postgres_load_date DATE,
    load_job_name VARCHAR(100)
);

-- dim_location: Location dimension based on NYC taxi zones
CREATE TABLE IF NOT EXISTS taxi.dim_location (
    location_key INTEGER PRIMARY KEY,
    borough VARCHAR(100),
    zone VARCHAR(200),
    service_zone VARCHAR(100),
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_layer VARCHAR(10) DEFAULT 'gold',
    -- Load metadata (added by postgres_load_job)
    postgres_load_timestamp TIMESTAMP,
    postgres_load_date DATE,
    load_job_name VARCHAR(100)
);

-- dim_payment: Payment type and rate code dimension
CREATE TABLE IF NOT EXISTS taxi.dim_payment (
    payment_key BIGINT PRIMARY KEY,
    payment_type_id INTEGER,
    payment_type_desc VARCHAR(50),
    rate_code_id INTEGER,
    rate_code_desc VARCHAR(50),
    created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_layer VARCHAR(10) DEFAULT 'gold',
    -- Load metadata (added by postgres_load_job)
    postgres_load_timestamp TIMESTAMP,
    postgres_load_date DATE,
    load_job_name VARCHAR(100)
);

-- ============================================================================
-- FACT TABLE
-- ============================================================================

-- fact_trip: Central fact table containing trip metrics
CREATE TABLE IF NOT EXISTS taxi.fact_trip (
    trip_key BIGINT PRIMARY KEY,
    date_key INTEGER NOT NULL,
    pickup_location_key INTEGER,
    dropoff_location_key INTEGER,
    payment_key BIGINT,
    pickup_datetime TIMESTAMP NOT NULL,
    dropoff_datetime TIMESTAMP NOT NULL,
    passenger_count INTEGER,
    trip_distance DOUBLE PRECISION,
    trip_duration_seconds INTEGER,
    trip_duration_minutes DOUBLE PRECISION,
    fare_amount DOUBLE PRECISION,
    extra DOUBLE PRECISION,
    mta_tax DOUBLE PRECISION,
    tip_amount DOUBLE PRECISION,
    tolls_amount DOUBLE PRECISION,
    total_amount DOUBLE PRECISION,
    tip_percentage DOUBLE PRECISION,
    avg_speed_mph DOUBLE PRECISION,
    partition_year INTEGER,
    partition_month INTEGER,
    gold_transformation_timestamp TIMESTAMP,
    gold_transformation_date DATE,
    gold_job_name VARCHAR(100),
    data_layer VARCHAR(10) DEFAULT 'gold',
    fact_hash VARCHAR(64) NOT NULL,
    -- Load metadata (added by postgres_load_job)
    postgres_load_timestamp TIMESTAMP,
    postgres_load_date DATE,
    load_job_name VARCHAR(100),
    CONSTRAINT uq_fact_trip_hash UNIQUE (fact_hash)
);

-- ============================================================================
-- FOREIGN KEY CONSTRAINTS
-- ============================================================================

ALTER TABLE taxi.fact_trip
    ADD CONSTRAINT fk_fact_trip_date
    FOREIGN KEY (date_key) REFERENCES taxi.dim_date(date_key);

ALTER TABLE taxi.fact_trip
    ADD CONSTRAINT fk_fact_trip_pickup_location
    FOREIGN KEY (pickup_location_key) REFERENCES taxi.dim_location(location_key);

ALTER TABLE taxi.fact_trip
    ADD CONSTRAINT fk_fact_trip_dropoff_location
    FOREIGN KEY (dropoff_location_key) REFERENCES taxi.dim_location(location_key);

ALTER TABLE taxi.fact_trip
    ADD CONSTRAINT fk_fact_trip_payment
    FOREIGN KEY (payment_key) REFERENCES taxi.dim_payment(payment_key);

-- ============================================================================
-- INDEXES FOR QUERY PERFORMANCE
-- ============================================================================

-- Indexes on fact table foreign keys
CREATE INDEX IF NOT EXISTS idx_fact_trip_date_key ON taxi.fact_trip(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_trip_pickup_location ON taxi.fact_trip(pickup_location_key);
CREATE INDEX IF NOT EXISTS idx_fact_trip_dropoff_location ON taxi.fact_trip(dropoff_location_key);
CREATE INDEX IF NOT EXISTS idx_fact_trip_payment ON taxi.fact_trip(payment_key);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_fact_trip_pickup_datetime ON taxi.fact_trip(pickup_datetime);
CREATE INDEX IF NOT EXISTS idx_fact_trip_partition ON taxi.fact_trip(partition_year, partition_month);

-- Indexes on dimension tables for joins
CREATE INDEX IF NOT EXISTS idx_dim_date_date ON taxi.dim_date(date);
CREATE INDEX IF NOT EXISTS idx_dim_location_borough ON taxi.dim_location(borough);
CREATE INDEX IF NOT EXISTS idx_dim_payment_type ON taxi.dim_payment(payment_type_id);

-- ============================================================================
-- GRANT PERMISSIONS (for application user if needed)
-- ============================================================================

-- Grant usage on schema
GRANT USAGE ON SCHEMA taxi TO PUBLIC;

-- Grant select on all tables
GRANT SELECT ON ALL TABLES IN SCHEMA taxi TO PUBLIC;

-- Grant insert, update, delete for ETL operations
GRANT INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA taxi TO PUBLIC;

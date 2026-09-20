-- Define the project schema structure for the data warehouse.

-- Store raw incoming data before any transformations or modeling.
CREATE SCHEMA IF NOT EXISTS staging;

-- Model the curated analytical data using a star schema.
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS warehouse;



CREATE TABLE IF NOT EXISTS warehouse.dim_region (
    region_key   SERIAL PRIMARY KEY,
    region_code  VARCHAR(2) NOT NULL UNIQUE,
    region_name  TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_id        INT PRIMARY KEY,
    full_date      DATE NOT NULL UNIQUE,
    day_name       VARCHAR(10) NOT NULL,
    day_of_month   INT NOT NULL,
    week_of_year   INT NOT NULL,
    month_of_year  INT NOT NULL,
    month_name     VARCHAR(10) NOT NULL,
    quarter   INT NOT NULL,
    year           INT NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.dim_category(
    category_id INT PRIMARY KEY, 
    category_name VARCHAR(50)
)
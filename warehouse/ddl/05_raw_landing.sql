CREATE TABLE IF NOT EXISTS staging.raw_landing(
    data          jsonb NOT NULL,
    ingest_date   date,
    source_file   text 
);


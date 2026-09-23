-- Static dimensions: values are known in advance and do not come from the daily file.
-- Runs with the DDL, not with the daily load.

INSERT INTO warehouse.dim_region (region_code, region_name) VALUES
    ('SA', 'Saudi Arabia'),
    ('AE', 'United Arab Emirates'),
    ('KW', 'Kuwait'),
    ('QA', 'Qatar'),
    ('BH', 'Bahrain'),
    ('OM', 'Oman')
ON CONFLICT (region_code) DO NOTHING;


INSERT INTO warehouse.dim_date (
    date_key, full_date, year, quarter, month, month_name,
    day_of_month, day_of_week, day_name
)
SELECT
    CAST(to_char(d, 'YYYYMMDD') AS integer),
    d::date,
    EXTRACT(YEAR FROM d),
    EXTRACT(QUARTER FROM d),
    EXTRACT(MONTH FROM d),
    trim(to_char(d, 'Month')),
    EXTRACT(DAY FROM d),
    EXTRACT(DOW FROM d),
    trim(to_char(d, 'Day'))
FROM generate_series('2026-01-01'::date, '2030-12-31'::date, interval '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;
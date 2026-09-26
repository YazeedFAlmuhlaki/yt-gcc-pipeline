-- Loads the fact table for one day.
-- Delete then insert, scoped to the ingest date, so the file is safe to re-run.
-- Type 2 dimensions are joined on the version valid at the ingest date,
-- Type 1 dimensions on the natural key alone.

DELETE FROM warehouse.fact_video_daily
WHERE ingest_date = '{{ ds }}';


INSERT INTO warehouse.fact_video_daily (
    video_key,
    channel_key,
    category_key,
    region_key,
    date_key,
    video_id,
    region_code,
    ingest_date,
    view_count,
    like_count,
    comment_count,
    regional_rank,
    pulled_at
)
SELECT
    dv.video_key,
    dc.channel_key,
    dcat.category_key,
    dr.region_key,
    dd.date_key,
    s.video_id,
    s.region_code,
    s.ingest_date,
    s.view_count,
    s.like_count,
    s.comment_count,
    s.regional_rank,
    s.pulled_at::timestamptz
FROM staging.stg_video_daily AS s

JOIN warehouse.dim_video AS dv
  ON dv.video_id = s.video_id
 AND dv.valid_from <= s.ingest_date
 AND (dv.valid_to > s.ingest_date OR dv.valid_to IS NULL)

JOIN warehouse.dim_channel AS dc
  ON dc.channel_id = s.channel_id
 AND dc.valid_from <= s.ingest_date
 AND (dc.valid_to > s.ingest_date OR dc.valid_to IS NULL)

JOIN warehouse.dim_category AS dcat
  ON dcat.category_id = s.category_id

JOIN warehouse.dim_region AS dr
  ON dr.region_code = s.region_code

JOIN warehouse.dim_date AS dd
  ON dd.full_date = s.ingest_date;
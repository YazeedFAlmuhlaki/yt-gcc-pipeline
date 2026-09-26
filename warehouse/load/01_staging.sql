-- Loads one day from the raw landing table into the staging table.
-- Delete before insert makes the file safe to re-run for the same day.

DELETE FROM staging.stg_video_daily
WHERE ingest_date = '{{ ds }}';


INSERT INTO staging.stg_video_daily (
    video_id,
    video_title,
    published_at,
    channel_id,
    channel_title,
    category_id,
    category_name,
    video_tags,
    view_count,
    like_count,
    comment_count,
    regional_rank,
    pulled_at,
    region_code,
    ingest_date,
    source_file
)
SELECT
    data ->> 'video_id',
    data ->> 'video_title',
    data ->> 'published_at',
    data ->> 'channel_id',
    data ->> 'channel_title',
    data ->> 'category_id',
    data ->> 'category_name',
    ARRAY(SELECT jsonb_array_elements_text(data -> 'video_tags')),
    (data ->> 'view_count')::bigint,
    (data ->> 'like_count')::bigint,
    (data ->> 'comment_count')::bigint,
    (data ->> 'regional_rank')::integer,
    data ->> 'pulled_at',
    data ->> 'region_code',
    ingest_date,
    source_file
FROM staging.raw_landing
WHERE ingest_date = '{{ ds }}';
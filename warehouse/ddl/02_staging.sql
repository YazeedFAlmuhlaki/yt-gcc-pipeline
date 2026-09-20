


-- Raw daily video metrics ingested from the source system before any transformations.
CREATE TABLE IF NOT EXISTS staging.stg_video_daily (
    video_id         text,
    video_title      text,
    published_at     text,
    channel_id       text,
    channel_title    text,
    category_id      text,
    category_name    text,
    video_tags       text[],
    view_count       bigint,
    like_count       bigint,
    comment_count    bigint,
    regional_rank    integer,
    pulled_at        text,
    region_code      text,
    ingest_date      date,
    loaded_at        timestamptz default current_timestamp,
    source_file      text
);
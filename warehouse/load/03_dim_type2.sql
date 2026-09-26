-- Type 2 dimensions: close the changed rows, then open new ones.
-- Order matters inside each dimension: close first, then insert.
-- After the close, a changed entity has no current row, so the same insert
-- covers both new entities and changed ones.

BEGIN;

-- dim_channel

UPDATE warehouse.dim_channel AS ct
SET valid_to   = '{{ ds }}',
    is_current = false
FROM (
    SELECT DISTINCT channel_id, channel_title
    FROM staging.stg_video_daily
) AS st
WHERE ct.channel_id = st.channel_id
  AND ct.is_current
  AND ct.channel_title IS DISTINCT FROM st.channel_title;

INSERT INTO warehouse.dim_channel (channel_id, channel_title, valid_from, valid_to, is_current)
SELECT DISTINCT
    s.channel_id,
    s.channel_title,
    '{{ ds }}',
    NULL,
    true
FROM staging.stg_video_daily AS s
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.dim_channel AS d
    WHERE d.channel_id = s.channel_id
      AND d.is_current
);


-- dim_video

UPDATE warehouse.dim_video AS vt
SET valid_to   = '{{ ds }}',
    is_current = false
FROM (
    SELECT DISTINCT video_id, video_title, published_at
    FROM staging.stg_video_daily
) AS st
WHERE vt.video_id = st.video_id
  AND vt.is_current
  AND (
        vt.video_title  IS DISTINCT FROM st.video_title
     OR vt.published_at IS DISTINCT FROM st.published_at::timestamptz
  );

INSERT INTO warehouse.dim_video (video_id, video_title, published_at, valid_from, valid_to, is_current)
SELECT DISTINCT
    s.video_id,
    s.video_title,
    s.published_at::timestamptz,
    '{{ ds }}',
    NULL,
    true
FROM staging.stg_video_daily AS s
WHERE NOT EXISTS (
    SELECT 1
    FROM warehouse.dim_video AS d
    WHERE d.video_id = s.video_id
      AND d.is_current
);

COMMIT;
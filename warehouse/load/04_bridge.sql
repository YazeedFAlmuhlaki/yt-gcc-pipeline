-- Links videos to their tags. Latest state only, no history.
-- Delete then insert, scoped to the videos seen today, so removed tags disappear
-- while links of videos not in today's file stay untouched.

DELETE FROM warehouse.bridge_video_tag AS b
USING warehouse.dim_video AS dv
WHERE b.video_key = dv.video_key
  AND dv.video_id IN (
      SELECT DISTINCT video_id
      FROM staging.stg_video_daily
  );


INSERT INTO warehouse.bridge_video_tag (video_key, tag_key)
SELECT DISTINCT
    dv.video_key,
    dt.tag_key
FROM staging.stg_video_daily AS s
CROSS JOIN LATERAL unnest(s.video_tags) AS t(tag_name)
JOIN warehouse.dim_video AS dv
  ON dv.video_id = s.video_id
 AND dv.is_current
JOIN warehouse.dim_tag AS dt
  ON dt.tag_name = t.tag_name
ON CONFLICT (video_key, tag_key) DO NOTHING;
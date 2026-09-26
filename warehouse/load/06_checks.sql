-- Data quality checks. Each one raises an exception, so the task fails loudly
-- instead of letting a wrong load pass as successful.

-- 1. Every staging row reached the fact table.
--    Catches rows silently dropped by a join that found no matching dimension row.
DO $$
DECLARE
    stg_count bigint;
    fact_count bigint;
BEGIN
    SELECT count(*) INTO stg_count
    FROM staging.stg_video_daily;

    SELECT count(*) INTO fact_count
    FROM warehouse.fact_video_daily
    WHERE ingest_date = '{{ ds }}';

    IF stg_count <> fact_count THEN
        RAISE EXCEPTION 'row count mismatch: staging %, fact %', stg_count, fact_count;
    END IF;
END $$;


-- 2. One current row per entity in the versioned dimensions.
--    Catches a broken close step that left two open versions.
DO $$
DECLARE
    bad_channels bigint;
    bad_videos bigint;
BEGIN
    SELECT count(*) INTO bad_channels
    FROM (
        SELECT channel_id
        FROM warehouse.dim_channel
        WHERE is_current
        GROUP BY channel_id
        HAVING count(*) > 1
    ) AS x;

    SELECT count(*) INTO bad_videos
    FROM (
        SELECT video_id
        FROM warehouse.dim_video
        WHERE is_current
        GROUP BY video_id
        HAVING count(*) > 1
    ) AS y;

    IF bad_channels > 0 OR bad_videos > 0 THEN
        RAISE EXCEPTION 'multiple current rows: % channels, % videos', bad_channels, bad_videos;
    END IF;
END $$;
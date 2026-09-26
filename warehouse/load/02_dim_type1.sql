INSERT INTO warehouse.dim_category(category_id, category_name)
SELECT DISTINCT
    category_id, 
    category_name 
FROM staging.stg_video_daily 
ON CONFLICT (category_id)
DO UPDATE SET
    category_name = EXCLUDED.category_name
WHERE dim_category.category_name IS DISTINCT FROM EXCLUDED.category_name;


INSERT INTO warehouse.dim_tag(tag_name)
SELECT DISTINCT 
    unnest(video_tags)
FROM staging.stg_video_daily  
ON CONFLICT (tag_name) DO NOTHING; 
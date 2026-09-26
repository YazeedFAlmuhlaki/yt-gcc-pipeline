CREATE TABLE IF NOT EXISTS warehouse.dim_category (
    category_key    integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY, 
    category_id     text NOT NULL UNIQUE, 
    category_name   text NOT NULL 
);


CREATE TABLE IF NOT EXISTS warehouse.dim_region(
    region_key  integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY, 
    region_code text NOT NULL UNIQUE, 
    region_name text NOT NULL 
); 


CREATE TABLE IF NOT EXISTS warehouse.dim_tag(
    tag_key     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag_name    text NOT NULL UNIQUE 
);

CREATE TABLE IF NOT EXISTS warehouse.dim_date (
    date_key        integer PRIMARY KEY,
    full_date       date NOT NULL UNIQUE,
    year            smallint NOT NULL,
    quarter         smallint NOT NULL,
    month           smallint NOT NULL,
    month_name      text NOT NULL,
    day_of_month    smallint NOT NULL,
    day_of_week     smallint NOT NULL,
    day_name        text NOT NULL
);

CREATE TABLE IF NOT EXISTS warehouse.dim_channel(
    channel_key     integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY, 
    channel_id      text NOT NULL, 
    channel_title   text NOT NULL, 
    valid_from      date NOT NULL, -- it is ingest date
    valid_to        date, 
    is_current      boolean NOT NULL 
);

-- unique index for dim_channel as it is SCD TYPE 2 
CREATE UNIQUE INDEX IF NOT EXISTS dim_channel_unique_index_t2 
ON warehouse.dim_channel(channel_id)
WHERE is_current; 


CREATE TABLE IF NOT EXISTS warehouse.dim_video(
    video_key       integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY, 
    video_id        text NOT NULL, 
    video_title     text NOT NULL, 
    published_at    timestamptz NOT NULL, 
    valid_from      date NOT NULL,
    valid_to        date,
    is_current      boolean NOT NULL
); 

-- unique index for dim_video as it is SCD TYPE 2 
CREATE UNIQUE INDEX IF NOT EXISTS dim_video_unique_index_t2 
ON warehouse.dim_video(video_id)
WHERE is_current; 


CREATE TABLE IF NOT EXISTS warehouse.bridge_video_tag (
    video_key int NOT NULL,
    tag_key   int NOT NULL,

    PRIMARY KEY (video_key, tag_key),

    CONSTRAINT video_fk
        FOREIGN KEY (video_key)
        REFERENCES warehouse.dim_video (video_key)
        ON DELETE CASCADE,

    CONSTRAINT tag_fk
        FOREIGN KEY (tag_key)
        REFERENCES warehouse.dim_tag (tag_key)
        ON DELETE CASCADE
);


CREATE TABLE IF NOT EXISTS warehouse.fact_video_daily(
    fact_key        integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    video_key       integer NOT NULL references warehouse.dim_video(video_key)       ON DELETE RESTRICT, 
    channel_key     integer NOT NULL references warehouse.dim_channel(channel_key)   ON DELETE RESTRICT,
    category_key    integer NOT NULL references warehouse.dim_category(category_key) ON DELETE RESTRICT, 
    region_key      integer NOT NULL references warehouse.dim_region(region_key)     ON DELETE RESTRICT, 
    date_key        integer NOT NULL references warehouse.dim_date(date_key)         ON DELETE RESTRICT, 

    video_id    text NOT NULL, 
    region_code text NOT NULL,
    ingest_date date NOT NULL,

    view_count    bigint, 
    like_count    bigint, 
    comment_count bigint,
    regional_rank int NOT NULL, 
    pulled_at     timestamptz NOT NULL , 

    CONSTRAINT uq_video_constraint
        UNIQUE (video_id, region_code, ingest_date)
);
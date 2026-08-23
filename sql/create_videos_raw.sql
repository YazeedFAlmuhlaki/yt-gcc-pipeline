CREATE EXTERNAL TABLE `yt_gcc_raw.videos`(
  `id` string COMMENT 'from deserializer', 
  `snippet` struct<publishedat:string,channelid:string,title:string,channeltitle:string,tags:array<string>,categoryid:string,defaultaudiolanguage:string> COMMENT 'from deserializer', 
  `statistics` struct<viewcount:string,likecount:string,favoritecount:string,commentcount:string> COMMENT 'from deserializer', 
  `rank` bigint COMMENT 'from deserializer', 
  `pulled_at` string COMMENT 'from deserializer')
PARTITIONED BY ( 
  `region` string, 
  `ingest_date` string)
ROW FORMAT SERDE 
  'org.apache.hive.hcatalog.data.JsonSerDe' 
STORED AS INPUTFORMAT 
  'org.apache.hadoop.mapred.TextInputFormat' 
OUTPUTFORMAT 
  'org.apache.hadoop.hive.ql.io.HiveIgnoreKeyTextOutputFormat'
LOCATION
  's3://yt-gcc-183749090090/raw/youtube/most_popular'
TBLPROPERTIES (
  'transient_lastDdlTime'='1787254638')
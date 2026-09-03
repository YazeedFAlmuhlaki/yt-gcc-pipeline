from urllib.parse import unquote_plus
import json

from yt_gcc.storage import read_s3_object, build_processed_key, ingest_yt_data, claim_run
from yt_gcc.config import CATEGORIES_S3_KEY, RUNS_TABLE


def to_int(value):
    """convert api count strings to int, keeping missing values as None"""
    if value is None:
        return None
    return int(value)


def lambda_handler(event, context):
    key = unquote_plus(event["Records"][0]["s3"]["object"]["key"])
    bucket = event["Records"][0]["s3"]["bucket"]["name"]

    success_str = read_s3_object(bucket=bucket, key=key)
    success_data = json.loads(success_str)


    ingest_date = success_data["date"]


    if not claim_run(RUNS_TABLE, ingest_date):
        print(f"{ingest_date} already processed, skipping")
        return {"ingest_date": ingest_date, "skipped": True}



    regions_list = success_data["regions"]

    categories_str = read_s3_object(bucket, CATEGORIES_S3_KEY)
    categories_list = [json.loads(line) for line in categories_str.splitlines()]
    categories_dict = {category["id"]: category["title"] for category in categories_list}

    all_records = []
    missing_categories = set()

    for region_key in regions_list:
        region_code = region_key.split("/")[3].split("=")[1]
        region_str = read_s3_object(bucket, region_key)
        region_videos = [json.loads(line) for line in region_str.splitlines()]

        for record in region_videos:
            snippet = record.get("snippet", {})
            statistics = record.get("statistics", {})

            category_id = snippet.get("categoryId")
            category_name = categories_dict.get(category_id)

            if category_name is None:
                category_name = "UNKNOWN"
                missing_categories.add(category_id)

            cleaned_record = {
                "video_id": record.get("id"),
                "video_title": snippet.get("title"),
                "published_at": snippet.get("publishedAt"),
                "channel_id": snippet.get("channelId"),
                "channel_title": snippet.get("channelTitle"),
                "category_id": category_id,
                "category_name": category_name,
                "video_tags": snippet.get("tags", []),
                "view_count": to_int(statistics.get("viewCount")),
                "like_count": to_int(statistics.get("likeCount")),
                "comment_count": to_int(statistics.get("commentCount")),
                "regional_rank": record.get("rank"),
                "pulled_at": record.get("pulled_at"),
                "region_code": region_code,
            }

            all_records.append(cleaned_record)

    if missing_categories:
        print("WARNING: category ids not found in lookup:", sorted(missing_categories))

    processed_key = build_processed_key(ingest_date)
    status_code = ingest_yt_data(all_records, bucket, processed_key)

    print("ingest_date=", ingest_date)
    print("records=", len(all_records))
    print("processed_key=", processed_key)
    print("status_code=", status_code)

    return {
        "ingest_date": ingest_date,
        "records": len(all_records),
        "processed_key": processed_key,
        "status_code": status_code,
    }
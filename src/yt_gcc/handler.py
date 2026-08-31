import os
from datetime import datetime, timezone

from yt_gcc.config import REGIONS_LIST
from yt_gcc.youtube import fetch_yt_data, enrich_yt_data
from yt_gcc.storage import build_yt_data_key, ingest_yt_data


def compute_time():
    """return tuple of (today: partition value, stamp: file name, iso: pulled_at enrichment)"""
    now = datetime.now(timezone.utc)
    return (
        now.strftime("%Y-%m-%d"),
        now.strftime("%Y%m%dT%H%M%SZ"),
        now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    )


def lambda_handler(event, context):
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    bkt_name = os.environ.get("BUCKET_NAME")

    today, stamp, iso_pulled_at = compute_time()

    succeeded = []
    failed = []

    for region in REGIONS_LIST:
        try:
            region_data = fetch_yt_data(region, yt_key)
            region_data_enriched = enrich_yt_data(region_data, iso_pulled_at)
            region_key = build_yt_data_key(region, today, stamp)
            status_code = ingest_yt_data(region_data_enriched, bkt_name, region_key)

            print(f"Region = {region}, Ingestion Status Code = {status_code}")
            succeeded.append(region)

        except Exception as e:
            print(f"An Error Occurred With Region = {region}")
            print("ERROR:", e)
            failed.append(region)

    if len(failed) == len(REGIONS_LIST):
        raise RuntimeError(f"all {len(REGIONS_LIST)} regions failed")

    return {
        "ingest_date": today,
        "pulled_at": iso_pulled_at,
        "succeeded": succeeded,
        "failed": failed,
    }
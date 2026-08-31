from yt_gcc.config import REGIONS_LIST
from yt_gcc.youtube import fetch_yt_data, enrich_yt_data 
from yt_gcc.storage import build_yt_data_key, ingest_yt_data
import os 
from dotenv import load_dotenv 
from datetime import datetime, timezone


load_dotenv() 

def compute_time():
    """return tuple of (today:used as partition, stamp:as file key, iso: as pulling enrichment)"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%d"), now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pipeline(): 

    yt_key = os.getenv("YOUTUBE_API_KEY")
    bkt_name = os.getenv("BUCKET_NAME")

    today, stamp, iso_pulled_at = compute_time()

    for region in REGIONS_LIST:

        try:

            region_data = fetch_yt_data(region, yt_key) 

            region_data_enriched = enrich_yt_data(region_data, iso_pulled_at)

            region_key = build_yt_data_key(region, today, stamp)

            region_ingestion_status_code = ingest_yt_data(region_data_enriched, bkt_name, region_key)

            print(f"Region = {region}, Ingestion Status Code = {region_ingestion_status_code}")

        
        except Exception as e: 
            print("An Error Occurred With Region = ", region)
            print("ERROR:", e)


if __name__ == "__main__":
    run_pipeline()

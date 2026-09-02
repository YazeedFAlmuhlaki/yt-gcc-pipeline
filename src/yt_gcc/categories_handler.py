import os 
import json

from yt_gcc.config import REGIONS_LIST
from yt_gcc.youtube import merge_categories 
from yt_gcc.storage import build_categories_key, ingest_yt_data
from yt_gcc.ingest_handler import compute_time 



def lambda_handler(event, context):

    
    yt_key = os.environ.get("YOUTUBE_API_KEY")
    bkt_name = os.environ.get("BUCKET_NAME")

    today, stamp, iso_pulled_at = compute_time()

    merged_categories = merge_categories(REGIONS_LIST, yt_key).values()

    categories_key = build_categories_key(today)

    status_code = ingest_yt_data(merged_categories, bkt_name, categories_key)

    return {
        "status_code"      : status_code,
        "fetched_date"     : today, 
        "total_categories" : len(merged_categories)
    }






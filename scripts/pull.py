# import os 
# from dotenv import load_dotenv 
# import json 
# from datetime import datetime, timezone

# import httpx 

# import boto3

# load_dotenv()

# # get the current time as UTC
# now = datetime.now(timezone.utc)


# today = now.strftime("%Y-%m-%d")
# stamp = now.strftime("%Y%m%dT%H%M%SZ")
# iso   = now.strftime("%Y-%m-%dT%H:%M:%SZ")



# API_URL = "https://www.googleapis.com/youtube/v3/videos"
# YT_API_KEY = os.getenv("YOUTUBE_API_KEY")


# def fetch_yt_data(region:str) -> list[dict]: 
#     """call the youtube api to return the most popular videos in the given region"""

#     query_params = {

#         "part"         : "snippet,statistics",
#         "chart"        : "mostPopular", 
#         "regionCode"   : region, 
#         "maxResults"   : 50, 
#         "key"          : YT_API_KEY, 
        
#     }

#     all_results = []

#     while True: 
#         response = httpx.get(url=API_URL, params=query_params)
#         data = response.json()["items"]

#         all_results.extend(data)

#         next_token = response.json().get("nextPageToken")

#         if not next_token: 
#             break 

#         query_params["pageToken"] = next_token

#     return all_results



    

# def enrich_yt_data(data:list[dict], pulled_at:str) -> list[dict]: 
#     """enrich the passed youtube data by adding the rank of each video and the pull date of the data"""

#     enriched_data = data

#     for rank, record in enumerate(enriched_data, start=1):
#         record["rank"]      = rank
#         record["pulled_at"] = pulled_at

#     return enriched_data


# def build_yt_data_key(region:str, ingest_date:str, stamp:str) -> str: 
#     """build the structure key that our data we will be stored at"""

#     return f"raw/youtube/most_popular/region={region}/ingest_date={ingest_date}/{stamp}.ndjson"

# def ingest_yt_data(items:list[dict], bucket:str, key:str):
#     """ingest data to our s3 bucket"""

#     s3 = boto3.client('s3')
    
#     prepared_items = "\n".join([json.dumps(record) for record in items]) + "\n"

#     response = s3.put_object(Bucket = bucket, Key = key, Body = prepared_items)

#     status_code = response['ResponseMetadata']['HTTPStatusCode']

#     return status_code




# if __name__ == "__main__": 

#     region_list = ["SA", "AE", "KW", "QA", "BH", "OM"]

#     for region in region_list: 

#         try:


#             region_data = fetch_yt_data(region)
        

#             region_data_enriched = enrich_yt_data(region_data, iso)


#             region_key = build_yt_data_key(region, today, stamp)

#             region_ingestion_status_code = ingest_yt_data(region_data_enriched, "yt-gcc-183749090090", region_key)

#             print(f"Region = {region}, Ingestion Status Code = {region_ingestion_status_code}")



#         except:
#             print("An Error Occurred With Region = ", region)




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



import boto3
import json


s3 = boto3.client('s3')


def build_yt_data_key(region:str, ingest_date:str, stamp:str) -> str: 
    """build the structure key that our data we will be stored at"""

    return f"raw/youtube/most_popular/region={region}/ingest_date={ingest_date}/{stamp}.ndjson"


def ingest_yt_data(items:list[dict], bucket:str, key:str):
    """ingest data to our s3 bucket"""
    
    prepared_items = "\n".join([json.dumps(record) for record in items]) + "\n"

    response = s3.put_object(Bucket = bucket, Key = key, Body = prepared_items)

    status_code = response['ResponseMetadata']['HTTPStatusCode']

    return status_code

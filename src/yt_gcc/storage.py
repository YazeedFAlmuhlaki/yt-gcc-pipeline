import boto3
import json


s3 = boto3.client('s3')
dynamodb = boto3.client("dynamodb")


def build_yt_data_key(region:str, ingest_date:str, stamp:str) -> str: 
    """build the structure key that our data we will be stored at"""

    return f"raw/youtube/most_popular/region={region}/ingest_date={ingest_date}/{stamp}.ndjson"


def build_categories_key(today:str): 
    return f"raw/youtube/categories/fetched_date={today}/categories.ndjson"

def build_processed_key(today:str): 
    return f"processed/youtube/most_popular/ingest_date={today}/most_popular.ndjson"


def ingest_yt_data(items, bucket:str, key:str):
    """ingest data to our s3 bucket"""
    
    prepared_items = "\n".join([json.dumps(record) for record in items]) + "\n"

    response = s3.put_object(Bucket = bucket, Key = key, Body = prepared_items)

    status_code = response['ResponseMetadata']['HTTPStatusCode']

    return status_code


def read_s3_object(bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read().decode("utf-8")


def claim_run(table: str, ingest_date: str) -> bool:
    """try to reserve this ingest_date; False means another invocation already has it"""
    try:
        dynamodb.put_item(
            TableName=table,
            Item={"ingest_date": {"S": ingest_date}},
            ConditionExpression="attribute_not_exists(ingest_date)",
        )
        return True
    except dynamodb.exceptions.ConditionalCheckFailedException:
        return False
import httpx
from .config import API_URL

def fetch_yt_data(region:str, YT_API_KEY:str) -> list[dict]: 
    """call the youtube api to return the most popular videos in the given region"""

    query_params = {

        "part"         : "snippet,statistics",
        "chart"        : "mostPopular", 
        "regionCode"   : region, 
        "maxResults"   : 50, 
        "key"          : YT_API_KEY, 
        
    }

    all_results = []

    while True: 
        response = httpx.get(url=API_URL, params=query_params)
        data = response.json()["items"]

        all_results.extend(data)

        next_token = response.json().get("nextPageToken")

        if not next_token: 
            break 

        query_params["pageToken"] = next_token

    return all_results


def enrich_yt_data(data:list[dict], pulled_at:str) -> list[dict]: 
    """enrich the passed youtube data by adding the rank of each video and the pull date of the data"""

    enriched_data = data

    for rank, record in enumerate(enriched_data, start=1):
        record["rank"]      = rank
        record["pulled_at"] = pulled_at

    return enriched_data

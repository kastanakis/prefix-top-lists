import os
import time
import boto3
import botocore
import datetime
import psutil  # To check available RAM
import pandas as pd
from pprint import pprint
from concurrent.futures import ThreadPoolExecutor, as_completed
from boto3.s3.transfer import TransferConfig
import pyarrow.parquet as pq
import gzip

def get_parquet_columns(file_path):
    """Extract specific columns from a Parquet file into a Pandas DataFrame and remove invalid rows."""
    columns_to_keep = ['query_name', 'query_type', 'response_type', 'ip4_address', 'ip6_address', 'country', 'as', 'as_full', 'ip_prefix']
    df = pq.read_table(file_path, columns=columns_to_keep).to_pandas()
    # Replace empty strings with NaN so they are considered missing
    df.replace("", pd.NA, inplace=True)
    # Drop rows where all values except 'query_name', 'query_type', "response_type" are missing
    df = df.dropna(subset=['ip4_address', 'ip6_address', 'country', 'as', 'as_full', 'ip_prefix'], how='all')
    
    # Print DataFrame head for debugging
    print("DataFrame Head:")
    print(df.head())
    return df

# **Step 1: Determine Optimal Chunksize Based on File Size & RAM**
def get_optimal_chunksize(file_size):
    """Determine the best multipart_chunksize based on file size and available RAM."""
    available_ram = psutil.virtual_memory().available
    max_ram_usage = available_ram * 0.25  # Use only 25% of available RAM for downloads
    chunk_size = min(512 * 1024 * 1024, max(16 * 1024 * 1024, max_ram_usage))
    return chunk_size

# **Step 2: Initialize OpenINTEL S3**
OI_ENDPOINT = "https://object.openintel.nl"
OI_BUCKET_NAME = "openintel-public"
OI_FDNS_LISTBASED = "fdns/basis=toplist"
DO_SOURCES = ["tranco", "umbrella", "crux", "radar", "majestic"]
GLOBAL_SCOPE = 'global'

# Create local directories to save files
SAVE_DIR = "openintel_data"
TEMP_DIR = "temp_downloads"
os.makedirs(SAVE_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Initialize OpenIntel S3 Resource (More Stable than Client)
s3_resource = boto3.resource(
    "s3",
    region_name="nl-utwente",
    endpoint_url=OI_ENDPOINT,
    config=botocore.config.Config(signature_version=botocore.UNSIGNED),
)

s3_bucket = s3_resource.Bucket(OI_BUCKET_NAME)

def check_file_exists(bucket, key):
    """Check if the given file exists in S3 before attempting to download."""
    try:
        s3_resource.Object(bucket, key).load()
        return True
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "404":
            print(f"⚠️ File not found: {key}")
        return False

# **Step 3: Get Latest Available Dataset for Each Source**
def get_all_available_dates(source):
    """List all available datasets for a source and return the most recent date."""
    if source == 'crux':
        prefix = f"{OI_FDNS_LISTBASED}/source={source}/country-code={GLOBAL_SCOPE}"
    else:
        prefix = f"{OI_FDNS_LISTBASED}/source={source}/"
    available_dates = []
    continuation_token = None

    while True:
        if continuation_token:
            response = s3_bucket.meta.client.list_objects_v2(
                Bucket=OI_BUCKET_NAME, Prefix=prefix, ContinuationToken=continuation_token
            )
        else:
            response = s3_bucket.meta.client.list_objects_v2(
                Bucket=OI_BUCKET_NAME, Prefix=prefix
            )

        if "Contents" in response:
            for obj in response["Contents"]:
                parts = obj["Key"].split("/")
                try:
                    year = int(parts[-4].split("=")[1])
                    month = int(parts[-3].split("=")[1])
                    day = int(parts[-2].split("=")[1])
                    available_dates.append(datetime.date(year, month, day))
                except (IndexError, ValueError):
                    continue

        if response.get("IsTruncated"):
            continuation_token = response["NextContinuationToken"]
        else:
            break

    return sorted(available_dates, reverse=True)

# **Step 4: Download Files and Extract Specific Columns**
def download_and_extract_columns(bucket, key, file_size, source, latest_date, max_retries=5):
    """Download an S3 file, extract specific columns into a DataFrame, and display it."""
    if not check_file_exists(bucket, key):
        return False
    
    retries = 0
    wait_time = 0
    optimal_chunk_size = get_optimal_chunksize(file_size)
    transfer_config = TransferConfig(multipart_chunksize=optimal_chunk_size)
    temp_file_path = os.path.join(TEMP_DIR, os.path.basename(key))

    while retries < max_retries:
        try:
            with open(temp_file_path, "wb") as tempFile:
                print(f"Downloading {key} -> {temp_file_path} (temporary)")
                s3_bucket.download_fileobj(Key=key, Fileobj=tempFile, Config=transfer_config)
            
            df = get_parquet_columns(temp_file_path)
            final_path = f"openintel_data/{source}_{latest_date}.csv"
            compressed_path = f"openintel_data/{source}_{latest_date}.csv.gz"
            
            df.to_csv(final_path, index=False)
            print(f"Successfully saved CSV: {final_path}")
            
            # Save as compressed CSV (gzip)
            with gzip.open(compressed_path, 'wt', encoding='utf-8') as gzfile:
                df.to_csv(gzfile, index=True)
            print(f"Successfully saved compressed CSV: {compressed_path}")
            os.remove(temp_file_path)  # Clean up temporary file
            return True
        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "503":
                wait_time += 10 
                print(f"503 Service Unavailable. Retrying in {wait_time:.2f} seconds...")
                time.sleep(wait_time)
                retries += 1
            else:
                print(f"Failed to download {key}: {e}")
                return False
    
    print(f"Max retries reached for {key}. Skipping...")
    return False

# **Step 5: Find and Process the Latest Datasets**
if __name__ == "__main__":
    # DATES_TO_PROCESS = pd.date_range(start="2025-03-24", end="2025-04-20").to_pydatetime()
    DATES_TO_PROCESS = pd.date_range(start="2026-01-01", end="2026-01-07").to_pydatetime()
    all_datasets = {source: get_all_available_dates(source) for source in DO_SOURCES}

    print("Available date ranges for each source:")
    for source, dates in all_datasets.items():
        if dates:
            print(f"{source}: {dates[-1]} to {dates[0]}")
        else:
            print(f"{source}: No available dates found.")

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_to_file = {}

        for source in DO_SOURCES:
            available_dates = all_datasets.get(source, [])
            for target_date in DATES_TO_PROCESS:
                specific_date = target_date.date()
                if specific_date not in available_dates:
                    print(f"❌ {specific_date} not available for {source}. Skipping...")
                    continue

                if source == 'crux':
                    prefix = f"{OI_FDNS_LISTBASED}/source={source}/country-code={GLOBAL_SCOPE}/year={specific_date.year}/month={specific_date.month:02d}/day={specific_date.day:02d}/"
                else:
                    prefix = f"{OI_FDNS_LISTBASED}/source={source}/year={specific_date.year}/month={specific_date.month:02d}/day={specific_date.day:02d}/"

                print(f"🔍 Searching files for {source} on {specific_date}: {prefix}")
                response = s3_bucket.meta.client.list_objects_v2(Bucket=OI_BUCKET_NAME, Prefix=prefix)

                if "Contents" not in response:
                    print(f"⚠️ No files found for {source} on {specific_date}. Skipping...")
                    continue

                for obj in response["Contents"]:
                    file_key = obj["Key"]
                    file_size = obj.get("Size", 512 * 1024 * 1024)

                    print(f"📥 Queuing download: {file_key}")
                    future = executor.submit(
                        download_and_extract_columns,
                        OI_BUCKET_NAME,
                        file_key,
                        file_size,
                        source,
                        specific_date
                    )
                    future_to_file[future] = file_key

        # **Wait for all downloads to complete**
        for future in as_completed(future_to_file):
            file_key = future_to_file[future]
            try:
                result = future.result()
                if not result:
                    print(f"Skipping {file_key} due to repeated failures.")
            except Exception as e:
                print(f"Unexpected error saving {file_key}: {e}")
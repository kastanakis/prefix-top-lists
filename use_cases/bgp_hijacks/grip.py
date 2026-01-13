import requests
import pandas as pd
import time
import json
import zipfile
from datetime import datetime
import urllib.parse


batch_size = 10
delay_between_batches = 3  # seconds
start_time = "2024-01-01T00:00:00"
end_time = "2024-12-31T00:00:00"
suspicious_time_prefix = {}

def get_prefixes(zip_file_path):
    # Open the ZIP file
    with zipfile.ZipFile(zip_file_path) as z:
        # List all files inside the ZIP
        file_list = z.namelist()

        # Assume the first CSV file in the ZIP (adjust if needed)
        csv_file = [f for f in file_list if f.endswith('.csv')][0]

        # Read the CSV file into a DataFrame
        with z.open(csv_file) as f:
            df = pd.read_csv(f, low_memory=False) 

    prefixes = df["prefix"]
    
    # Create a default dict with all the prefixes as keys and total_suspicious_times = 0.
    # Beause GRIP api returns only prefixs with suspicious events.
    for prefix in prefixes:
        suspicious_time_prefix[prefix] = [{'total_number_of_events': 0}]
        
    # Batch loop
    for i in range(0, len(prefixes), batch_size):
        batch = prefixes[i:i + batch_size]
#         print(f"Processing batch {i // batch_size + 1} ({len(batch)} prefixes)...")

        for prefix in batch:
            process_prefix(prefix)

        print("Sleeping before next batch...")
        time.sleep(delay_between_batches)

    # Save final result
    with open("popular_prefix_grip.json", "w") as outfile:
        json.dump(suspicious_time_prefix, outfile, indent=2)

def process_prefix(prefix):
    api_url = (
        f"https://api.grip.inetintel.cc.gatech.edu/json/events?"
        f"length=100&start=0&ts_start={start_time}&ts_end={end_time}"
        f"&min_susp=80&max_susp=100&event_type=moas&pfxs={prefix}"
    )

    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            print(f"[{prefix}] Request failed with code {response.status_code}")
            return

        json_string = response.json()
        events = json_string.get("data", [])

        if not events:
            return

        suspicious_event_details = [] 
        for event in events:
            attackers = event['summary']['attackers']
            victims = event['summary']['victims']
            event_time_unix = int(event['view_ts']) 
            event_time = datetime.utcfromtimestamp(event_time_unix).strftime('%Y-%m-%d %H:%M:%S')

            if event['finished_ts'] is None:
                finished_time = "Ongoing"
            else:
                finished_time_unix = int(event['finished_ts'])
                finished_time = datetime.utcfromtimestamp(finished_time_unix).strftime('%Y-%m-%d %H:%M:%S')

            start_duration = {
                "start": event_time,
                "end": finished_time,
                "attacker": attackers,
                "victim": victims
            }

            suspicious_event_details.append(start_duration)

        merge_all = []
        merge_all.append({"total_number_of_events": len(events)})
        merge_all.append(suspicious_event_details)
        suspicious_time_prefix[prefix] = merge_all

    except requests.exceptions.RequestException as e:
        print(f"[{prefix}] Exception during request: {e}")

prefixes = get_prefixes(zip_file_path = "../../output/prefix-top-lists/20250401_to_20250407/prefix_top_list_ranked.zip")

# Save result into a json file
with open("popular_prefix_grip_2024.json", "w") as outfile:
    json.dump(suspicious_time_prefix, outfile)
print(f"Completed with %s number of records." %len(suspicious_time_prefix))

import json
import matplotlib.pyplot as plt
from collections import Counter

# Load JSON data
with open("popular_prefix_grip_2024.json", "r") as f:
    data = json.load(f)

# Extract event counts and calculate max
event_counts = [entry[0]["total_number_of_events"] for entry in data.values()]
max_events = max(event_counts)
count_distribution = Counter(event_counts)

# Prepare x and y values
x = list(range(0, max_events + 1))
y = [count_distribution.get(i, 0) for i in x]

# Plot
plt.figure(figsize=(16, 6))
plt.rcParams.update({'font.size': 15})

plt.bar(x, y, color='orangered')
plt.yscale("log")
plt.xlabel("Number of Suspicious Events")
plt.ylabel("Number of Prefixes (log scale)")
# plt.title("Distribution of Prefixes by Event Count (Log Y-Axis) from 01 Jan to 31 Dec 2024")
plt.xticks(x, rotation=90)  # Show all ticks, rotated for readability
plt.grid(axis='y', which='both', linestyle='--', alpha=0.4)
plt.tight_layout()
plt.savefig("suspicious_events.png")
plt.show()

import matplotlib.pyplot as plt
import pandas as pd
# merged_df can now is data from popular_prefixes_hijacks.csv
# Sort by weight descending
merged_df = pd.read_csv("popular_prefixes_hijacks.csv")
plt.rcParams.update({'font.size': 15})
plt.figure(figsize=(10, 6))
plt.scatter(merged_df['weight'], merged_df['total_number_of_events'], alpha=0.3, s=10, color='black')
plt.xlabel('Weight')
plt.xscale("log")
plt.ylabel('Total Number of Suspicious Events')
plt.yscale("log")
# plt.title('Weight vs. Number of Suspicious Events')
plt.grid(True)
plt.tight_layout()
plt.savefig("weight_vs_suspicious_events.png")
plt.show()

from matplotlib.colors import LogNorm

# Load and clean data
df = pd.read_csv("popular_prefixes_hijacks.csv")
df = df[(df['weight'] > 0) & (df['total_number_of_events'] > 0)]

# Plot
plt.figure(figsize=(10, 6))
plt.hist2d(
    df['weight'],
    df['total_number_of_events'],
    bins=100,
    norm=LogNorm(),
    cmap='viridis'
)
plt.colorbar(label='Number of Prefixes')
plt.xscale('log')
plt.yscale('log')
plt.xlabel("Weight (log scale)")
plt.ylabel("Total Suspicious Events (log scale)")
# plt.title("Density of Suspicious Events by Prefix Weight")
plt.grid(True, which='both', linestyle='--', alpha=0.5)
plt.tight_layout()
plt.savefig("heatmap_weight_vs_suspicious_events.png")
plt.show()
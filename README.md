
# **Prefix Top Lists Reloaded (PTL) - Aggregating Domain Rankings into Network Prefixes**

**A Python-based pipeline that transforms domain-level popularity rankings into stable, prefix-based top lists.**  
This project maps **Domains → IPs → BGP Prefixes → ASes**, enabling **prefix-level and AS-level ranking** based on Zipf-weighted domain popularity.

---

## **Table of Contents**
- [Introduction](#📌-introduction)
- [How It Works](#⚙️-how-it-works)
- [Installation](#🚀-installation)
- [Usage](#📌-usage)
- [Methodology](#📊-methodology)
- [Example Output](#📈-example-output)
- [Temporal Analysis](#⏳-temporal-analysis)
- [Use Cases](#🔍-use-cases)
- [Contributing](#🤝-contributing)
- [License](#📜-license)

---

## **Introduction**
Domain popularity lists (e.g., Tranco, Umbrella, Majestic) provide valuable signals. However, these lists suffer from several limitations, such as a) frequent rank fluctuations over time, b) lack of aggregation across related domains (e.g., google.com vs google.co.uk), c) no inherent weighting to reflect relative importance.

**Prefix Top Lists (PTLs)** solve this by:  
✅ Applying **Zipf-based ranking**  
✅ Resolving **domains → IPs → prefixes → ASes**  
✅ Aggregating **domain weights by network prefix**  
✅ Supporting reproducible **network measurement studies**

---

## **How It Works**
1. Download & unify domain popularity lists   
2. Apply Zipf-based weighting  
3. Resolve domains using OpenINTEL 
4. Map IPs to BGP prefixes & ASes 
5. Aggregate weights to Prefixes (PTLs) and ASes (ATLs) 
6. Analyze PTL stability, BGP hijacks, DNS and PQC compliance 

---

## **Installation**
```bash
# Clone the repo
git clone <this_repo>
cd prefix-top-lists

# Install requirements
pip install pandas numpy requests matplotlib seaborn boto3 botocore pyarrow psutil beautifulsoup4
```

---

## **Usage**

### **1️⃣ Collect Historical Domain Lists**
Before running `__public_historical_rankings_collector.py`, **you must edit the script** and provide your own credentials:

Open the script and replace the placeholder strings:
```python3
TRANCO_EMAIL = "your-email@example.com"
TRANCO_API_TOKEN = "your-tranco-api-token"
CLOUDFLARE_API_TOKEN = "your-cloudflare-api-token"
```

Then run:
```bash
cd domain-top-lists/
python3 __public_historical_rankings_collector.py
```

The downloaded CSV files will be saved to the `domain-top-lists/historical_data/` folder, organized by data source:

- `domain-top-lists/historical_data/tranco/`
- `domain-top-lists/historical_data/umbrella/`
- `domain-top-lists/historical_data/majestic/`
- `domain-top-lists/historical_data/crux/`
- `domain-top-lists/historical_data/cloudflare/`

### **2️⃣ Download OpenINTEL DNS Resolution Data**
```bash
cd dns-resolution/
python3 dataset_collection.py
```

The downloaded and processed DNS resolution files are saved under the `dns-resolution/openintel_data/` folder, organized by week. Each subfolder is named by the date range and contains one `.csv.gz` per data source:

Example:

- `dns-resolution/openintel_data/20250414_to_20250420/tranco_2025-04-14.csv.gz`
- `dns-resolution/openintel_data/20250414_to_20250420/umbrella_2025-04-14.csv.gz`
- `dns-resolution/openintel_data/20250414_to_20250420/majestic_2025-04-14.csv.gz`

### **3️⃣ Generate Domain Top Lists (DTLs)**
```bash
cd domain-top-lists/
python3 domain_top_list_generator.py
```

The generated domain top list files will be saved to the `output/domain-top-lists/{WEEK_RANGE}/` folder, where `{WEEK_RANGE}` corresponds to the processed date range (e.g., `20250414_to_20250420`). Each dataset source (Tranco, Umbrella, Majestic) is processed individually to preserve source-specific rankings. A merged file is then created by combining these lists using **Zipf-weighted averaging**, which reflects domain popularity across all sources.


Example output files:

- `output/domain-top-lists/20250414_to_20250420/domain_top_list_tranco.csv`
- `output/domain-top-lists/20250414_to_20250420/domain_top_list_umbrella.csv`
- `output/domain-top-lists/20250414_to_20250420/domain_top_list_majestic.csv`
- `output/domain-top-lists/20250414_to_20250420/domain_top_list_merged_ranked.csv`


### **4️⃣ Generate PTL & ATL Files**
```bash
cd prefix-top-lists/
python3 prefix_top_list_generator.py
```

The resulting files will be saved to the `output/prefix-top-lists/{WEEK_RANGE}/` and `output/as-top-lists/{WEEK_RANGE}/` folders, where `{WEEK_RANGE}` corresponds to the processed date range (e.g., `20250414_to_20250420`).

This step takes the previously generated Domain Top Lists and DNS resolution data to:

- Map `domains → IPs → prefixes → ASNs`
- Aggregate Zipf-based weights or domain frequency counts
- Output both **ranked (weighted)** and **presence-based (unweighted)** lists

### Ranked (Zipf-weighted) Outputs
Based on the weighted domain top list (`domain_top_list_merged_ranked.csv`), reflects **relative popularity**:

- `output/prefix-top-lists/20250414_to_20250420/prefix_top_list_ranked.csv`
- `output/as-top-lists/20250414_to_20250420/as_top_list_ranked.csv`

### Presence-Based Outputs (Optional)
Unweighted alternative using domain occurrence frequency across sources:

- `output/prefix-top-lists/20250414_to_20250420/prefix_top_list_presence.csv`
- `output/as-top-lists/20250414_to_20250420/as_top_list_presence.csv`

*To generate these, uncomment and run the corresponding block in* `prefix_top_list_generator.py`.

---

## **Example Output**

### 🔹 Prefix Top List
| Prefix             | Weight | Domains                     | IPs                      |
|--------------------|--------|------------------------------|--------------------------|
| 2a00:1450:400e::/48 | 0.0705 | google.com, youtube.com     | 2a00:1450:400e:809::200e |
| 2606:4700::/44     | 0.0141 | cloudflare.com, cdnjs.com   | 2606:4700::6810:ffff     |

### 🔹 AS Top List
| ASN    | Weight | Prefixes | Domains              |
|--------|--------|----------|----------------------|
| 15169  | 0.1576 | 390      | google.com, gmail.com |
| 13335  | 0.1550 | 442      | cloudflare.com       |

---

## **Temporal Analysis**

The `temporal_analysis/temporal_analysis.py` script shows **prefix discovery dynamics** across weeks:

- Tracks newly discovered prefixes weekly  
- Computes their **Zipf weight contribution**  
- Plots a **CDF of prefix coverage** alongside **new weight bars**

### 🔹 Output Example:
- `prefix_cdf_vs_zipf_combined.png` — shows diminishing value of newly added prefixes over time (long-tail behavior)

---

## **Use Cases**

### **1. BGP Hijack Exposure**
- Analyzes suspicious routing events using **GRIP API**
- Extracts suspicious event counts for each PTL prefix
- Produces:
  - `popular_prefix_grip.json`
  - Histogram: `suspicious_events.png`
  - Scatter plot: `weight_vs_suspicious_events.png`

### **2. DNS Compliance (RFC 2182)**
> *(Planned in the `dns_compliance` folder)*

Will analyze whether a domain's name servers are spread across prefixes, helping evaluate **resilience to DNS infrastructure failure**.

### **3. Post-Quantum Cryptography (PQC) Readiness**
- Scans HTTPS domains for PQC TLS support using `oqsprovider`
- Maps PQC results back to prefixes via domain-PFX mapping
- Visualizes:
  - **PQC Compliance per Prefix**
  - **Violin plots by popularity tier** (`pqc_violin_combined_stacked.png`)
  - Outputs: `pqc_status_per_prefix.json`, `pqc.final.summary.csv`

```bash
# Run parallel domain scanning
bash use_cases/pqc_readiness/pqc_scan.sh
```

---

## **Contributing**
Contributions welcome!

- Add support for new top lists or BGP sources
- Automate week-to-week pipeline runs
- Expand use cases (e.g., CDN analysis, IPv6 focus)

---

## **License**
Licensed under the **MIT License**.  
See the [`LICENSE`](LICENSE) file for details.

---


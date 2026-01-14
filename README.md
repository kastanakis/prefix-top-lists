
# **Prefix Top Lists Reloaded: A Temporal Prefix Ranking Dataset**
**Published at PAM 2026, this work replicates and extends the Prefix Top Lists (PTL) methodology, originally introduced at IMC 2019, which maps popular domain names to BGP prefixes and Autonomous Systems (ASes).**

## 🔗 Quick Links
- **📦 Public output datasets (OpenINTEL):** https://openintel.nl/data/prefix-top-lists
- **📁 PAM 2026 output datasets (GitHub):** https://github.com/kastanakis/prefix-top-lists/tree/main/output

---

## **Introduction**
Internet measurement studies commonly rely on **domain-based top lists** (e.g., Tranco, Cisco Umbrella, Majestic, CrUX) to select popular targets. While widely used, prior research has shown that these lists are often **unstable over time**, treat **related domains as independent entities**, and provide limited visibility into the **network infrastructure** that actually hosts and routes traffic.

**Prefix Top Lists (PTLs)** address these limitations by shifting the unit of analysis from **domain names** to **BGP prefixes and Autonomous Systems (ASes)**. By aggregating domain popularity at the network level and applying a **Zipf-based weighting model**, PTLs emphasize highly popular services while reducing long-tail noise, resulting in rankings that are **more stable, interpretable, and infrastructure-aware**.

This repository provides a **reproducible implementation of the PTL methodology**, reviving and extending prior work using **modern domain top lists** and **public DNS and BGP data from OpenINTEL**. The resulting **Prefix Top Lists (PTLs)** and **AS Top Lists (ATLs)** are designed to support **network-aware measurement studies**, including routing security analysis, DNS resilience, and protocol adoption.


---

## **How It Works**
1. **Gathers domain-based top lists (DTLs)** from multiple sources, including Tranco, Umbrella, Majestic, CrUX, and Cloudflare Radar  

2. **Applies Zipf-based weighting** to each DTL and aggregates rankings over a **seven-day sliding window** to improve temporal stability  

3. **Maps domain names to IP addresses** using public DNS resolution data from **OpenINTEL**  

4. **Associates resolved IP addresses with BGP prefixes and origin Autonomous Systems (ASes)** using routing metadata  

5. **Aggregates domain weights at the network level**, producing **Prefix Top Lists (PTLs)** and **AS Top Lists (ATLs)**  

6. **Applies PTLs to practical measurement use cases**, including temporal stability analysis, routing security events, DNS resilience, and **Post-Quantum Cryptography (PQC)** deployment  
---

## **Requirements**

- **pandas**, **numpy**, **pyarrow** — data processing  
- **requests** — HTTP downloads  
- **boto3**, **botocore** — AWS S3 access (OpenINTEL data)  
- **psutil** — system resource monitoring  
- **matplotlib**, **seaborn** — visualization  
- **beautifulsoup4** — auxiliary parsing  

(Standard library modules such as `os`, `json`, `gzip`, and `zipfile` are used but require no installation.)

```bash
# Clone the repository
git clone https://github.com/kastanakis/prefix-top-lists/
cd prefix-top-lists

# Install Python dependencies
pip3 install pandas numpy pyarrow matplotlib requests boto3 botocore psutil seaborn beautifulsoup4

```

---

## **Usage**

### **1️⃣ Collect Domain-Based Top Lists (DTLs)**

The **collection and automation of domain-based top lists (DTLs)** is intentionally left to the user, as most DTLs are subject to **access restrictions, licensing terms, or usage policies** defined by their respective providers (e.g., Tranco, Umbrella, Majestic, CrUX, Cloudflare Radar).

This repository assumes that DTLs are **collected locally** and stored in a common, source-separated format. In our setup, we retrieve historical DTL snapshots and store them under: 

`domain-top-lists/historical_data/`

with one subdirectory per data source, for example:

- `domain-top-lists/historical_data/tranco/`
- `domain-top-lists/historical_data/umbrella/`
- `domain-top-lists/historical_data/majestic/`
- `domain-top-lists/historical_data/crux/`
- `domain-top-lists/historical_data/cloudflare/`

Once the DTLs are available locally in this directory structure, the remaining steps of the pipeline can be executed unchanged.

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

### **3️⃣ Process Domain Top Lists (DTLs)**
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
  
---

## **Use Cases**

### **1. BGP Hijack Exposure**
- Analyzes suspicious routing events using **GRIP API**
- Extracts suspicious event counts for each PTL prefix
- Produces:
  - `popular_prefix_grip_2024.json`
  - Histogram: `suspicious_events.png`
  - Scatter plot: `weight_vs_suspicious_events.png`
  - Heatmap: `heatmap_weight_vs_suspicious_events.png`

### **2. DNS Compliance (RFC 2182)**
> *(Planned in the `dns_compliance` folder)*

Analyzes whether a domain's name servers are spread across prefixes, helping evaluate **resilience to DNS infrastructure failure**.

### **3. Post-Quantum Cryptography (PQC) Readiness**
- Scans HTTPS domains for PQC TLS support using `oqsprovider`
- Maps PQC results back to prefixes via domain-PFX mapping
- Visualizes:
  - **Violin plots by popularity tier** (`pqc_violin_combined_stacked.png`)
  - Outputs: `pqc_status_per_prefix.json`, `final.pqc.summary.formatted.ranking.csv`

---

## **License**
Licensed under the **MIT License**.  
See the [`LICENSE`](LICENSE) file for details.

---


import csv
import json
import sys
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

# Set max field size to the maximum supported by the OS/Python
csv.field_size_limit(sys.maxsize)

# Input file paths
domain_file_path = './final.pqc.summary.formatted.ranking.csv'
prefix_file_path = '../../output/prefix-top-lists/20250401_to_20250407/prefix_top_list_ranked.csv'
output_json_path = 'pqc_status_per_prefix.json'

# Step 1: Load the prefix data
prefix_data = []
with open(prefix_file_path, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        domains = [d.strip() for d in row['domains'].split(',') if d.strip()]
        prefix_data.append({
            'prefix': row['prefix'],
            'weight': float(row['weight']),
            'domains': domains
        })

# Step 2: Build mappings
domain_to_prefix = {}
prefix_weights = {}

for entry in prefix_data:
    prefix = entry['prefix']
    prefix_weights[prefix] = entry['weight']
    for domain in entry['domains']:
        domain_to_prefix[domain] = prefix

# Step 3: Read the domain PQC data and organize by prefix
result = {}
unmatched_domains = []

with open(domain_file_path, newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        domain = row['domain'].strip()
        pqc_data = {
            'x25519_kyber768': int(row['x25519_kyber768']),
            'X25519MLKEM768': int(row['X25519MLKEM768']),
            'SecP256r1MLKEM768': int(row['SecP256r1MLKEM768']),
            'mlkem768': int(row['mlkem768'])
        }

        prefix = domain_to_prefix.get(domain)
        if prefix:
            if prefix not in result:
                result[prefix] = {'weight': prefix_weights[prefix]}
            result[prefix][domain] = pqc_data
        else:
            unmatched_domains.append(domain)

# Step 4: Write JSON output
with open(output_json_path, 'w') as f:
    json.dump(result, f, indent=2)

# Step 5: Determine PQC compliance per prefix (Strategy 1)
compliance_data = []

for prefix, pdata in result.items():
    weight = pdata['weight']
    compliant = 0
    for domain, pqc in pdata.items():
        if domain == 'weight':
            continue
        if any(pqc[group] == 1 for group in ['x25519_kyber768', 'X25519MLKEM768', 'SecP256r1MLKEM768', 'mlkem768']):
            compliant = 1
            break
    compliance_data.append((weight, compliant))


# Step 6: Generate heatmaps
pqc_groups = ['x25519_kyber768', 'X25519MLKEM768', 'SecP256r1MLKEM768', 'mlkem768']
group_matrix = []

# Sort by descending weight
sorted_prefixes = sorted(result.items(), key=lambda x: -x[1]['weight'])
# Define tiers with labels
tier_cutoffs = [100, 1000, 10000]
tier_labels = [f'Top {k:,}' for k in tier_cutoffs] + ['All']

# Calculate average PQC compliance per prefix
prefix_avg_compliance = []

for prefix, pdata in sorted_prefixes:
    compliant_count = 0
    domain_count = 0
    for domain, pqc in pdata.items():
        if domain == 'weight':
            continue
        domain_count += 1
        if any(pqc[group] == 1 for group in pqc_groups):
            compliant_count += 1
    avg_compliance = compliant_count / domain_count if domain_count > 0 else 0
    prefix_avg_compliance.append(avg_compliance)
    
# --- Helper for tier label ---
def get_tier_label(rank):
    for cutoff, label in zip(tier_cutoffs + [float('inf')], tier_labels):
        if rank <= cutoff:
            return label

# --- Tiered PQC Compliance Summary ---
print("\n===== PQC COMPLIANCE BY TIER =====")

tier_stats = []

for cutoff, label in zip(tier_cutoffs + [float('inf')], tier_labels):
    subset = sorted_prefixes[:cutoff] if cutoff != float('inf') else sorted_prefixes

    domain_total = 0
    domain_pqc = 0
    prefix_total = len(subset)
    prefix_pqc = 0

    for prefix, pdata in subset:
        has_pqc = False
        for domain, pqc in pdata.items():
            if domain == 'weight':
                continue
            domain_total += 1
            if any(pqc[group] == 1 for group in pqc_groups):
                domain_pqc += 1
                has_pqc = True
        if has_pqc:
            prefix_pqc += 1

    d_ratio = domain_pqc / domain_total if domain_total > 0 else 0
    p_ratio = prefix_pqc / prefix_total if prefix_total > 0 else 0

    tier_stats.append((label, domain_pqc, domain_total, d_ratio, prefix_pqc, prefix_total, p_ratio))

    print(f"[{label}]")
    print(f" - Domains: {domain_pqc}/{domain_total} ({d_ratio:.2%})")
    print(f" - Prefixes: {prefix_pqc}/{prefix_total} ({p_ratio:.2%})")
    print("")
    
import pandas as pd
import seaborn as sns

# --- Violin plot for prefixes ---
prefix_violin_data = []

for rank, (prefix, pdata) in enumerate(sorted_prefixes, start=1):
    is_compliant = any(
        any(pqc[group] == 1 for group in ['x25519_kyber768', 'X25519MLKEM768', 'SecP256r1MLKEM768', 'mlkem768'])
        for domain, pqc in pdata.items() if domain != 'weight'
    )
    for cutoff, label in zip(tier_cutoffs + [float('inf')], tier_labels):
        if rank <= cutoff:
            tier = label
            break
    prefix_violin_data.append({'tier': tier, 'pqc': int(is_compliant)})

# Combine prefix and domain violin data
combined_violin_data = []

# Prefix-level
for item in prefix_violin_data:
    combined_violin_data.append({**item, 'level': 'Prefix'})

df_combined = pd.DataFrame(combined_violin_data)

# Plot stacked violin plots
plt.figure(figsize=(10, 6))
sns.violinplot(
    data=df_combined,
    x='tier', y='pqc',
    inner='point', cut=0,
    color='steelblue',
    order=tier_labels
)

# --- Add ratio annotations on top of violins ---
for i, (label, d_pqc, d_total, d_ratio, p_pqc, p_total, p_ratio) in enumerate(tier_stats):
    x = i  # violin position on x-axis
    plt.text(x, 1.05, f"{p_ratio:.1%}", color='steelblue', ha='center', fontsize=11)
plt.ylabel('PQC Compliance', fontsize=14)
plt.xlabel('Prefix Rank Tier', fontsize=14)
plt.ylim(-0.1, 1.1)
plt.grid(axis='y', linestyle='--', alpha=0.4)
plt.tight_layout()
plt.savefig("pqc_violin_combined_stacked.png", dpi=300)
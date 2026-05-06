import csv
import json
import pandas as pd
from pprint import pprint
import os
from urllib.parse import urlparse
import glob
import argparse
from datetime import date, datetime, timedelta

def parse_end_date(end_date_str: str | None) -> date:
    """
    Parse end date in YYYY-MM-DD. If None, return yesterday's date (local).
    """
    if end_date_str is None:
        return date.today() - timedelta(days=1)
    try:
        return datetime.strptime(end_date_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid --end-date '{end_date_str}'. Use YYYY-MM-DD.") from e

def compute_dates_to_process(end_date: date):
    """
    Return a list of python datetimes (like your current code expects),
    covering 7 days ending on end_date (inclusive).
    """
    start_date = end_date - timedelta(days=6)
    # Keep your existing type: pandas DatetimeIndex -> python datetime objects
    return pd.date_range(start=start_date.isoformat(), end=end_date.isoformat()).to_pydatetime()

# ---------- Helpers ----------
def write_json(filename, content):
    with open(filename, 'w') as fp:
        json.dump(content, fp, indent=4)

def read_json(filename):
    with open(filename, 'r') as fp:
        return json.load(fp)

def canonicalize_domain(domain):
    if pd.isna(domain):
        return None
    # domain is now canon_domain — already cleaned
    if domain.endswith('.'):
        domain = domain[:-1]
    return domain.replace("www.", "", 1)

# ---------- DNS Processing ----------
def process_dns_files(dns_filepaths):
    raw2canon = {}
    domain2ip, domain2pfx, ip2pfx, pfx2as = {}, {}, {}, {}

    print("\n🔍 Processing DNS resolution files...")
    for filepath in dns_filepaths:
        print(f"  → Reading: {filepath}")
        with open(filepath, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                raw_domain = row['query_name'].rstrip('.')
                canon_domain = canonicalize_domain(raw_domain)
                raw2canon[raw_domain] = canon_domain
                ip = row['ip4_address'] or row['ip6_address']
                pfx = row['ip_prefix']
                asn = row['as']

                if not ip or not pfx or not canon_domain or (not pfx.count('.') and not ':' in pfx):
                    continue

                # domain = domain.strip().lower()  # Removed because canon_domain is now used throughout
                domain2ip.setdefault(canon_domain, []).append(ip) if ip not in domain2ip.get(canon_domain, []) else None
                domain2pfx.setdefault(canon_domain, []).append(pfx) if pfx not in domain2pfx.get(canon_domain, []) else None
                ip2pfx.setdefault(ip, []).append(pfx) if pfx not in ip2pfx.get(ip, []) else None
                pfx2as.setdefault(pfx, set()).add(asn) if asn else None

    print(f"\n✅ Parsed: {len(domain2ip)} domains, {len(ip2pfx)} IPs, {len(pfx2as)} prefixes with AS info")

    # Build alias mapping to canonical domains
    domain2pfx_canon = {}
    for domain, pfxes in domain2pfx.items():
        canon = canonicalize_domain(domain)
        domain2pfx_canon.setdefault(canon, []).extend(pfxes)

    ip2pfx = {ip: list(set(pfxes)) for ip, pfxes in ip2pfx.items()}
    return domain2ip, domain2pfx_canon, ip2pfx, pfx2as

# ---------- Weight Distribution ----------
def distribute_weights(domain2pfx, ip2pfx, pfx2as, weight_csv_path, output_pfx_path, output_as_path, is_frequency=False, domain2ip=None):
    print(f"\n📊 Distributing weights from: {weight_csv_path}")
    df = pd.read_csv(weight_csv_path)
    if not is_frequency: print(f"🧮 Total weight before filtering: {df['final_weight'].sum():.6f}")
    weight_col = "final_weight" if not is_frequency else "frequency"
    if weight_col not in df.columns:
        raise ValueError(f"Missing expected column '{weight_col}' in {weight_csv_path}")

    df = df.rename(columns={weight_col: "weight"})
    df_orig = pd.read_csv(weight_csv_path)
    df_orig = df_orig.rename(columns={weight_col: "weight"})
    df_orig['raw_domain'] = df_orig['domain']
    df_orig['domain'] = df_orig['domain'].apply(canonicalize_domain)  # Save original for unmatched comparison
    df['raw_domain'] = df['domain']
    df['domain'] = df['domain'].apply(canonicalize_domain)

    # Match and filter
    original_count = len(df)
    print("🔎 Domains in weight file (before filtering):", len(df))
    print("🔎 Unique domains in DNS mapping:", len(domain2pfx))
    df = df[df['domain'].isin(domain2pfx)]
    print("🔎 Domains remaining after filtering:", len(df))
    matched_count = len(df)
    print(f"ℹ️ Matched {matched_count} of {original_count} domains from weight file to DNS")
    unmatched = df_orig[~df_orig['domain'].isin(domain2pfx)]
    print(f"❌ Unmatched domains: {len(unmatched)}")
    if not unmatched.empty:
        print("🔍 Top unmatched domains by weight:")
        print(unmatched.sort_values(by='weight', ascending=False)[['raw_domain', 'domain', 'weight']].head(10))

    # Show top unmatched domains for debugging
    unmatched = df[~df['domain'].isin(domain2pfx)]
    if not unmatched.empty:
        print("🔍 Top unmatched domains:")
        print(unmatched.sort_values(by="weight", ascending=False)[['raw_domain', 'domain', 'weight']].head(10))

    # Normalize if needed
    if is_frequency or abs(df['weight'].sum() - 1.0) > 0.05:
        print("ℹ️ Normalizing weights...")
        print(abs(df['weight'].sum() - 1.0))
        df['weight'] = df['weight'] / df['weight'].sum()

    pfx_weights, pfx_domains, pfx_ips = {}, {}, {}
    ip_weights = {}
    ip2domain = {}
    for _, row in df.iterrows():
        domain, weight = row["domain"], row["weight"]
        ips = domain2ip.get(domain, [])
        if not ips:
            continue
        split_weight = weight / len(ips)
        for ip in ips:
            ip_weights[ip] = ip_weights.get(ip, 0) + split_weight
            ip2domain.setdefault(ip, set()).add(domain)

    for ip, weight in ip_weights.items():
        prefixes = ip2pfx.get(ip, [])
        
        for pfx in prefixes:
            pfx_weights[pfx] = pfx_weights.get(pfx, 0) + weight
            pfx_ips.setdefault(pfx, set()).add(ip)
            pfx_domains.setdefault(pfx, set()).update(ip2domain.get(ip, []))

    for ip, pfxs in ip2pfx.items():
        for pfx in pfxs:
            pfx_ips.setdefault(pfx, set()).add(ip)

    df_pfx = pd.DataFrame([
        {
            "prefix": pfx,
            "weight": pfx_weights[pfx],
            "domains": ", ".join(sorted(pfx_domains[pfx])),
            "ips": ", ".join(sorted(pfx_ips.get(pfx, set()))),
            "ases": ", ".join(sorted(pfx2as.get(pfx, set()))) if pfx in pfx2as else ""
        }
        for pfx in pfx_weights
    ]).sort_values(by="weight", ascending=False)

    df_pfx.to_csv(output_pfx_path, index=False)
    print(f"✅ Saved Prefix Top List: {output_pfx_path}")
    pprint(df_pfx.head(5))

    # Aggregate to AS-level
    as_weights, as_prefixes, as_domains, as_ips = {}, {}, {}, {}
    for pfx, weight in pfx_weights.items():
        for asn in pfx2as.get(pfx, []):
            # Handle MOAS prefixes by splitting weights
            asns = list(pfx2as.get(pfx, []))
            if asns:
                split_weight = weight / len(asns)
                weight = split_weight
            as_weights[asn] = as_weights.get(asn, 0) + weight
            as_prefixes.setdefault(asn, set()).add(pfx)
            as_domains.setdefault(asn, set()).update(pfx_domains[pfx])
            as_ips.setdefault(asn, set()).update(pfx_ips.get(pfx, set()))

    df_as = pd.DataFrame([
        {
            "asn": asn,
            "weight": as_weights[asn],
            "prefixes": ", ".join(sorted(as_prefixes[asn])),
            "domains": ", ".join(sorted(as_domains[asn])),
            "ips": ", ".join(sorted(as_ips[asn]))
        }
        for asn in as_weights
    ]).sort_values(by="weight", ascending=False)

    df_as.to_csv(output_as_path, index=False)
    print(f"✅ Saved AS Top List: {output_as_path}")
    pprint(df_as.head(5))

    print(f"🎯 Total prefix weight sum: {df_pfx['weight'].sum():.6f} (should be 1.0)")
    print(f"🎯 Total AS weight sum: {df_as['weight'].sum():.6f} (should be 1.0)")

# ---------- Master Pipeline ----------
def run_pipeline(name, dns_files, weight_file, pfx_out, as_out, is_frequency=False):
    print(f" Running PTL/ATL Pipeline: {name}")
    domain2ip, domain2pfx, ip2pfx, pfx2as = process_dns_files(dns_files)
    
    distribute_weights(domain2pfx, ip2pfx, pfx2as, weight_file, pfx_out, as_out, is_frequency=is_frequency, domain2ip=domain2ip)

# ---------- Main ----------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PTL/ATL pipeline for a weekly window.")
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (inclusive) in YYYY-MM-DD. Default: today. Start date is 6 days earlier."
    )
    args = parser.parse_args()

    end_date = parse_end_date(args.end_date)
    dates = compute_dates_to_process(end_date)

    date = f"{dates[0].strftime('%Y%m%d')}_to_{dates[-1].strftime('%Y%m%d')}"
    os.makedirs(f"../output/prefix-top-lists/{date}", exist_ok=True)
    os.makedirs(f"../output/as-top-lists/{date}", exist_ok=True)
    print(f"Processing week: {date}")

    dns_data_dir = "../dns-resolution/openintel_data"

    all_dns_files = sorted(glob.glob(os.path.join(dns_data_dir, "*.csv")))

    # Only keep files whose date falls inside this week
    week_dates = {d.date().isoformat() for d in dates}

    filtered_dns_files = [
        f for f in all_dns_files
        if any(date_str in f for date_str in week_dates)
    ]

    # Use source names for curated/full separation if needed
    curated_sources = ["tranco", "umbrella", "majestic"]
    full_sources = curated_sources + ["radar", "crux"]

    curated_dns_files = [f for f in filtered_dns_files if any(src in f for src in curated_sources)]
    full_dns_files = [f for f in filtered_dns_files if any(src in f for src in full_sources)]

    run_pipeline(
        name="Ranked (Zipf-based)",
        dns_files=curated_dns_files,
        weight_file="../output/domain-top-lists/" + date + "/domain_top_list_merged_ranked.csv",
        pfx_out="../output/prefix-top-lists/" + date + "/prefix_top_list_ranked.csv",
        as_out="../output/as-top-lists/" + date + "/as_top_list_ranked.csv",
        is_frequency=False
    )

    run_pipeline(
        name="Presence-based (All Sources)",
        dns_files=full_dns_files,
        weight_file="../output/domain-top-lists/" + date + "/domain_top_list_merged_presence.csv",
        pfx_out="../output/prefix-top-lists/" + date + "/prefix_top_list_presence.csv",
        as_out="../output/as-top-lists/" + date + "/as_top_list_presence.csv",
        is_frequency=True
    )

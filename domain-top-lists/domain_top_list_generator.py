import pandas as pd
import numpy as np
from urllib.parse import urlparse
import os
from collections import Counter
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

def clean_domain(domain):
    if pd.isna(domain):
        return None
    domain = domain.strip().lower()
    parsed_url = urlparse(domain)
    clean_domain = parsed_url.netloc if parsed_url.netloc else domain
    return clean_domain.replace("www.", "")

def load_domain_top_list(filepath, has_header=True):
    print(f"Loading file: {filepath}")
    df = pd.read_csv(filepath, header=0 if has_header else None, dtype=str)

    if has_header and "origin" in df.columns and "rank" in df.columns:
        df = df.rename(columns={"origin": "domain", "rank": "rank"})
    elif not has_header and df.shape[1] == 2 and df.iloc[0, 0].isdigit():
        df.columns = ["rank", "domain"]
    elif has_header and df.shape[1] == 2 and df.columns[0] == 'domain':
        df.columns = ["domain", "rank"]
    elif has_header and "GlobalRank" in df.columns and "Domain" in df.columns:
        df = df.rename(columns={"GlobalRank": "rank", "Domain": "domain"})
    elif has_header and df.shape[1] == 1 and df.columns[0] == "domain":
        df["rank"] = 0  # Placeholder
    else:
        raise ValueError(f"Unknown format in file: {filepath}")

    df["domain"] = df["domain"].apply(clean_domain)
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce").fillna(0).astype(int)
    df = df[["domain", "rank"]].dropna()
    print(f"→ Loaded {len(df)} entries.")
    return df

def precompute_harmonic_sum(total_elements, s=1.0):
    return np.sum(1 / (np.arange(1, total_elements + 1) ** s))

def apply_zipf_weighting(df, s=1.0):
    total_entries = len(df)
    print(f"Applying Zipf weights to {total_entries} domains...")
    harmonic_sum = precompute_harmonic_sum(total_entries, s)
    df = df.copy()
    df["weight"] = (1 / (df["rank"] ** s)) / harmonic_sum
    print(f"→ Zipf weighting complete (weight sum = {df['weight'].sum():.4f})")
    return df

def process_dataset(name, filepaths, has_header=True, is_rolling=False, use_weight=True, suffix=""):
    print(f"\n=== Processing {name} Dataset ===")
    df_list = []
    rank_tracker = {}

    for path in filepaths:
        df = load_domain_top_list(path, has_header=has_header)

        if use_weight:
            if df["rank"].nunique() > 1:
                df = apply_zipf_weighting(df)
            else:
                df["weight"] = 1 / len(df)
        else:
            df["weight"] = 1.0  # Assign dummy weight

        df_list.append(df)
        for _, row in df.iterrows():
            rank_tracker.setdefault(row["domain"], []).append(row.get("rank", None))

    # Merge weights or just deduplicate domains
    if use_weight:
        if len(df_list) > 1:
            df = pd.concat(df_list)
            df = df.groupby("domain", as_index=False)["weight"].mean()
        else:
            df = df_list[0]

        df["final_weight"] = df["weight"] / df["weight"].sum()
        df = df[["domain", "final_weight"]]
        df = df.sort_values("final_weight", ascending=False).reset_index(drop=True)
    else:
        df = pd.concat(df_list).drop_duplicates(subset="domain")
        df = df[["domain"]].reset_index(drop=True)
        df["final_weight"] = np.nan  # Placeholder, not used

    # Output
    global out_dir
    os.makedirs(out_dir, exist_ok=True)
    safe_name = name.lower().replace(" ", "_")
    suffix_str = f"_{suffix}" if suffix else ""
    out_path = f"{out_dir}/domain_top_list_{safe_name}{suffix_str}.csv"

    df.to_csv(out_path, index=False)
    print(f"→ Saved to: {out_path}\n")
    
    # Top 10 domains
    df_top10 = df.head(10).copy()
    df_top10["rank"] = range(1, 11)
    df_top10["top_rank"] = df_top10["domain"].apply(lambda d: min(rank_tracker.get(d, [None])))
    df_top10["bottom_rank"] = df_top10["domain"].apply(lambda d: max(rank_tracker.get(d, [None])))
    df_top10 = df_top10[["rank", "domain", "final_weight", "top_rank", "bottom_rank"]]
    print(df_top10.to_string(index=False))
    return df

def merge_and_average_zipf_weights(df_list):
    """
    Merges multiple domain ranking lists, ensures unique domains before merging,
    then computes the average Zipf weight and normalizes.

    - Renames each weight column (weight_0, weight_1, etc.) before merging.
    - Uses an outer join to include all domains from all sources.
    - Fills missing weights with 0.
    - Computes average across available weights.
    - Normalizes so final_weight sums to 1.
    """

    # Step 1: Deduplicate within each DataFrame and rename weight column
    for i, df in enumerate(df_list):
        df = df.copy()
        df = df.groupby("domain", as_index=False)["weight"].mean()
        df.columns = ["domain", f"weight_{i}"]
        df_list[i] = df

    # Step 2: Merge all DataFrames on "domain" using outer joins
    merged_df = df_list[0]
    for df in df_list[1:]:
        merged_df = merged_df.merge(df, on="domain", how="outer")

    # Step 3: Fill missing weights with 0
    merged_df.fillna(0, inplace=True)

    # Step 4: Compute the average of all renamed weight columns
    weight_columns = [col for col in merged_df.columns if col.startswith("weight_")]
    merged_df["final_weight"] = merged_df[weight_columns].mean(axis=1)

    # Step 5: Normalize so the total weight sums to 1
    merged_df["final_weight"] /= merged_df["final_weight"].sum()

    # Step 6: Keep only the relevant columns
    merged_df = merged_df[["domain", "final_weight"]]

    # Step 7: Sort by descending final weight
    merged_df = merged_df.sort_values("final_weight", ascending=False).reset_index(drop=True)

    return merged_df

def flatten_to_unweighted(df):
    return df[["domain"]].drop_duplicates().reset_index(drop=True)

def build_frequency_rank(df_list):
    all_domains = []
    for df in df_list:
        flat_df = flatten_to_unweighted(df)
        all_domains.extend(flat_df["domain"].tolist())

    freq_counts = Counter(all_domains)
    result_df = pd.DataFrame(freq_counts.items(), columns=["domain", "frequency"])
    result_df = result_df.sort_values("frequency", ascending=False).reset_index(drop=True)
    result_df["normalized_frequency"] = result_df["frequency"] / len(df_list)
    return result_df

def prepare_weighted_merge(*dfs):
    return [df.rename(columns={"final_weight": "weight"}) for df in dfs]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build weekly domain top lists.")
    parser.add_argument(
        "--end-date",
        type=str,
        default=None,
        help="End date (inclusive) in YYYY-MM-DD. Default: today. Start date is 6 days earlier."
    )
    args = parser.parse_args()

    end_date = parse_end_date(args.end_date)
    dates = compute_dates_to_process(end_date)
    print(dates)
    week_id = f"{dates[0].strftime('%Y%m%d')}_to_{dates[-1].strftime('%Y%m%d')}"
    out_dir = f"../output/domain-top-lists/{week_id}"
    os.makedirs(out_dir, exist_ok=True)
    start_str = dates[0].strftime("%Y-%m-%d")
    end_str = dates[-1].strftime("%Y-%m-%d")
    print(f"Processing domain top list datasets from {start_str} to {end_str}...")

    # 7-day datasets
    tranco_files = [f"historical_data/tranco/{d.strftime('%Y%m%d')}_tranco.csv" for d in dates]
    umbrella_files = [f"historical_data/umbrella/{d.strftime('%Y%m%d')}_umbrella.csv" for d in dates]
    majestic_files = [f"historical_data/majestic/{d.strftime('%Y%m%d')}_majestic.csv" for d in dates]

    # 1-day datasets
    crux_file     = [f"historical_data/crux/{dates[-1].strftime('%Y%m%d')}_crux.csv"]
    radar_file    = [f"historical_data/radar/{dates[-1].strftime('%Y%m%d')}_radar.csv"]

    # Run all
    tranco_rank = process_dataset("Tranco", tranco_files, has_header=False, is_rolling=True, use_weight=True, suffix="rank")
    umbrella_rank = process_dataset("Umbrella", umbrella_files, has_header=False, is_rolling=True, use_weight=True, suffix="rank")
    majestic_rank = process_dataset("Majestic", majestic_files, has_header=True, is_rolling=True, use_weight=True, suffix="rank")
    tranco_presence = process_dataset("Tranco", tranco_files, has_header=False, is_rolling=True, use_weight=False, suffix="presence")
    umbrella_presence = process_dataset("Umbrella", umbrella_files, has_header=False, is_rolling=True, use_weight=False, suffix="presence")
    majestic_presence = process_dataset("Majestic", majestic_files, has_header=True, is_rolling=True, use_weight=False, suffix="presence")
    crux_presence = process_dataset("Crux", crux_file, has_header=True, use_weight=False, suffix="presence")   # <== no weighting
    radar_presence = process_dataset("Radar", radar_file, has_header=True, use_weight=False, suffix="presence") # <== no weighting

    df_list_rank = prepare_weighted_merge(tranco_rank, umbrella_rank, majestic_rank)
    # df_list = load_processed_domain_lists(["tranco", "umbrella", "majestic"])
    merged_df_rank = merge_and_average_zipf_weights(df_list_rank)
    # Save the result
    merged_output_path = f"{out_dir}/domain_top_list_merged_ranked.csv"
    merged_df_rank.to_csv(merged_output_path, index=False)

    # Show Top 10
    print("\n=== Merged Top 10 Domains Across Tranco, Umbrella, Majestic ===")
    print(merged_df_rank.head(10).to_string(index=False))
    print(f"→ Merged file saved to: {merged_output_path}")
    
    # Combine all five datasets as unweighted sets for frequency merge
    all_df_list = [tranco_presence, umbrella_presence, majestic_presence, crux_presence, radar_presence]
    freq_merged_df = build_frequency_rank(all_df_list)

    # Save the frequency-based merged list
    freq_output_path = f"{out_dir}/domain_top_list_merged_presence.csv"
    freq_merged_df.to_csv(freq_output_path, index=False)

    # Print top 10 frequency-ranked domains
    print("\n=== Top Domains by Frequency Across All 5 Sources ===")
    print(freq_merged_df.head(10).to_string(index=False))
    print(f"→ Frequency-based file saved to: {freq_output_path}")
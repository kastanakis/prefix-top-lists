import pandas as pd
import matplotlib.pyplot as plt

# File paths and corresponding week labels
file_paths = [
    ("../output/prefix-top-lists/20250324_to_20250330/prefix_top_list_ranked.csv", "2025-03-30"),
    ("../output/prefix-top-lists/20250401_to_20250407/prefix_top_list_ranked.csv", "2025-04-06"),
    ("../output/prefix-top-lists/20250407_to_20250413/prefix_top_list_ranked.csv", "2025-04-13"),
    ("../output/prefix-top-lists/20250414_to_20250420/prefix_top_list_ranked.csv", "2025-04-20")
]

# Load data
dfs = []
for path, date in file_paths:
    df = pd.read_csv(path, dtype={"prefix": str})
    df["date"] = date
    dfs.append(df)

combined_df = pd.concat(dfs, ignore_index=True)

# Track newly seen prefixes and Zipf weight they contribute
seen_prefixes = set()
cumulative_prefixes = []
new_zipf_weights = []
dates = []

total_new_prefixes = 0

for date in sorted(combined_df["date"].unique()):
    week_df = combined_df[combined_df["date"] == date]
    current_prefixes = set(week_df["prefix"])
    new_prefixes = current_prefixes - seen_prefixes

    # CDF update
    total_new_prefixes += len(new_prefixes)
    cumulative_prefixes.append(total_new_prefixes)
    dates.append(date)

    # Zipf weight of new prefixes
    new_weight = week_df[week_df["prefix"].isin(new_prefixes)]["weight"].sum()
    new_zipf_weights.append(new_weight)

    seen_prefixes.update(new_prefixes)

# Prepend 0 for CDF
cdf_values = [0] + [x / cumulative_prefixes[-1] for x in cumulative_prefixes]
step_dates = [dates[0]] + dates  # Extend dates for proper step

# ---- Plotting ----
fig, ax1 = plt.subplots(figsize=(10, 5))

# Plot CDF on left y-axis
ax1.step(step_dates, cdf_values, where='pre', color='black', linewidth=2, label="Prefix Discovery (CDF)")
ax1.set_ylabel("Fraction of Prefixes Seen (CDF)", color='black')
ax1.set_ylim(0, 1.05)
ax1.set_yticks([i / 10 for i in range(11)])
ax1.tick_params(axis='y', labelcolor='black')

# Grid and ticks
ax1.grid(True, linestyle="--", alpha=0.5)
ax1.set_xticks(dates)
ax1.set_xticklabels(dates)
ax1.set_xlabel("Week")

# Plot Zipf weight bars on right y-axis
ax2 = ax1.twinx()
for i, (d, w) in enumerate(zip(dates, new_zipf_weights)):
    color = 'white' if i == 0 else 'red'
    alpha = 0 if i == 0 else 0.8
    ax2.bar(d, w, color=color, alpha=alpha, width=0.2)
ax2.set_ylabel("Zipf Weight of Newly Added Prefixes", color='red')
ax2.set_yscale("log")
ax2.tick_params(axis='y', labelcolor='red')

# Optional: Annotate bars with their values
for i, v in enumerate(new_zipf_weights):
    if i == 0: continue
    if v > 0:
        ax2.text(dates[i], v * 1.1, f"{v:.3f}", ha='center', va='bottom', fontsize=9, color='red')

plt.title("Prefix Discovery vs. New Prefix Zipf Weight")
plt.tight_layout()
plt.savefig("prefix_cdf_vs_zipf_combined.png")
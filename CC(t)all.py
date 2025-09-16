import os
import numpy as np
import pandas as pd
import shutil

# --- Configuration ---
SOURCE_XLSX = "Fire 2 Data.xlsx"
OUTPUT_XLSX = "Fire 2 Proceed.xlsx"
SPEED_DIR = "speed"
ID_COL = 0      # index column in excel (0-based)
BEST_LAG_COL = 19   # own best lag
CC_T_COL = 20       # own CC at best lag
CC_GLOBAL_COL = 21  # CC at global best lag

def load_speed_data(txt_path):
    """Load player & robot speed arrays from a .txt, skipping header, empty lines, and -1s."""
    player, robot = [], []
    try:
        with open(txt_path, "r") as f:
            lines = f.readlines()[1:]  # skip header
    except Exception as e:
        print(f"❌ Error reading {txt_path}: {e}")
        return np.array([]), np.array([])
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            continue
        try:
            p, r = float(parts[0]), float(parts[1])
            if p == -1 or r == -1:
                continue
            player.append(p)
            robot.append(r)
        except ValueError:
            continue
    return np.array(player), np.array(robot)

def pearson_corr(x, y):
    if len(x) == 0 or len(y) == 0:
        return 0.0
    if np.std(x) == 0 or np.std(y) == 0:
        return 0.0
    return np.corrcoef(x, y)[0, 1]

def cc_at_lag(x, y, lag):
    n = len(x)
    if lag > 0:
        xs, ys = x[:n-lag], y[lag:]
    elif lag < 0:
        xs, ys = x[-lag:], y[:n+lag]
    else:
        xs, ys = x, y
    return 0.0 if len(xs) == 0 else pearson_corr(xs, ys)

# --- Prepare Excel ---
shutil.copyfile(SOURCE_XLSX, OUTPUT_XLSX)
df = pd.read_excel(OUTPUT_XLSX, engine="openpyxl")

# Ensure enough columns and initialize
while df.shape[1] <= CC_GLOBAL_COL:
    df[f"Extra_{df.shape[1]+1}"] = np.nan
df.iloc[:, BEST_LAG_COL] = np.nan
df.iloc[:, CC_T_COL] = np.nan
df.iloc[:, CC_GLOBAL_COL] = np.nan
df.columns.values[BEST_LAG_COL] = "Best Lag (t)"
df.columns.values[CC_T_COL] = "CC(t)"
df.columns.values[CC_GLOBAL_COL] = "CC(global)"

indices = df.iloc[:, ID_COL].apply(
    lambda v: str(int(v)).zfill(5) if (isinstance(v, float) and v.is_integer()) else str(v).zfill(5)
)

# Load all data first for global lag
all_data = []
valid_rows = []

for row_idx, idx in enumerate(indices):
    path = os.path.join(SPEED_DIR, f"{idx}.txt")
    if not os.path.isfile(path):
        print(f"⚠️ No speed file for index {idx}")
        continue

    p, r = load_speed_data(path)
    if len(p) < 2:
        print(f"❌ Invalid or insufficient speed data for index {idx}: {len(p)} valid rows")
        continue

    all_data.append((idx, p, r, row_idx))
    valid_rows.append(row_idx)

if not all_data:
    print("No valid data for any index. Exiting.")
    exit()

# Find lag range
lengths = [len(p) for (_, p, _, _) in all_data]
global_L = min(lengths) // 4
lags = list(range(-global_L, global_L + 1))

# Calculate each file's best lag and CC, and gather for global best lag
per_index_results = []
all_ccs_by_lag = {lag: [] for lag in lags}

for idx, p, r, row_idx in all_data:
    # Per-index: Find best lag and its CC
    best_lag, best_cc = 0, -2.0
    for lag in lags:
        cc = cc_at_lag(p, r, lag)
        all_ccs_by_lag[lag].append(cc)
        if cc > best_cc:
            best_cc, best_lag = cc, lag
    per_index_results.append((row_idx, idx, best_lag, best_cc, p, r))

# Find global best lag (max sum of abs(CC) across all indices)
sum_abs_ccs = {lag: np.sum(np.abs(ccs)) for lag, ccs in all_ccs_by_lag.items()}
global_best_lag = max(sum_abs_ccs, key=lambda lag: sum_abs_ccs[lag])

print(f"\nAggregate global best lag (samples): {global_best_lag}")

# Now fill in Excel columns
for row_idx, idx, best_lag, best_cc, p, r in per_index_results:
    # Column 19: best lag for its own file
    df.iat[row_idx, BEST_LAG_COL] = best_lag
    # Column 20: CC(t) at its own best lag
    df.iat[row_idx, CC_T_COL] = best_cc
    # Column 21: CC(t) at global best lag
    cc_global = cc_at_lag(p, r, global_best_lag)
    df.iat[row_idx, CC_GLOBAL_COL] = cc_global
    print(f"✅ Index {idx}: best lag={best_lag}, CC(t)={best_cc:.4f}, CC(global)={cc_global:.4f}")

df.to_excel(OUTPUT_XLSX, index=False, engine="openpyxl")
print(f"\nAll done — results written to '{OUTPUT_XLSX}'.")
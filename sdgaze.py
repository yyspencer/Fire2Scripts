#!/usr/bin/env python3
import os
import csv
import shutil
import numpy as np
import pandas as pd

# ---------- Configuration ----------
source_excel = "Fire 2 Data.xlsx"
output_excel = "Fire 2 Proceed.xlsx"
folders = [
    os.path.join("shook"),
    os.path.join("shook", "baseline"),
    os.path.join("noshook"),
    os.path.join("noshook", "baseline"),
]
id_col_excel = 0

# Sheet/column targets (Excel 1-based → 0-based)
S1_COL = 14  # Sheet 1 (overall) → column 15
S2_COL = 9   # Sheet 2 (pre)     → column 10
S3_COL = 9   # Sheet 3 (post)    → column 10

OFFSET = 0.229  # seconds added after "0.2 seconds" tag for crisis estimate

# ---------- Helpers ----------
def idx5_direct(v) -> str:
    """Direct index (numeric-like -> zero-pad to 5; else str(...).zfill(5))."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v)).zfill(5)
    return str(v).zfill(5)

def ensure_cols(df: pd.DataFrame, upto_col_inclusive: int):
    while df.shape[1] <= upto_col_inclusive:
        df[f"Extra_{df.shape[1]+1}"] = np.nan

def find_matching_csv(index_5):
    """Return (csv_path, folder) whose filename starts with index_5; search in configured order."""
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if filename.lower().endswith(".csv") and filename[:5] == index_5:
                return os.path.join(folder, filename), folder
    return None, None

def find_col_caseins(header_row, target_name):
    """Case-insensitive, trimmed equality on header names. Return col index or -1."""
    t = target_name.strip().lower()
    for i, col in enumerate(header_row):
        if isinstance(col, str) and col.strip().lower() == t:
            return i
    return -1

def find_crisis_split_index(header, rows):
    """
    Crisis split row index:
      1) 'shook' in robotEvent (preferred) -> Event (case-insensitive substring).
      2) if not found: first '0.2 seconds' → let t0 = Time at that row; split at first row with Time >= t0 + OFFSET.
      3) else -1.
    """
    time_col = find_col_caseins(header, "Time")
    ev_col   = find_col_caseins(header, "robotEvent")
    if ev_col == -1:
        ev_col = find_col_caseins(header, "Event")
        if ev_col == -1:
            return -1

    # 1) shook split
    for i, r in enumerate(rows):
        if len(r) <= ev_col: 
            continue
        ev = r[ev_col]
        if isinstance(ev, str) and ("shook" in ev.strip().lower()):
            return i

    # 2) 0.2 seconds fallback (needs Time)
    if time_col == -1:
        return -1

    i0, t0 = -1, None
    for i, r in enumerate(rows):
        if len(r) <= max(ev_col, time_col):
            continue
        ev = r[ev_col]
        if isinstance(ev, str) and ("0.2 seconds" in ev.strip().lower()):
            try:
                t0 = float(r[time_col])
            except Exception:
                t0 = None
            i0 = i
            break

    if i0 == -1 or t0 is None:
        return -1

    target = t0 + OFFSET
    for m in range(i0, len(rows)):
        if len(rows[m]) <= time_col:
            continue
        try:
            tm = float(rows[m][time_col])
        except Exception:
            continue
        if tm >= target:
            return m
    return -1

def safe_float(s):
    try: 
        return float(s)
    except Exception:
        return np.nan

def segment_sd_gaze(rows, x_col, y_col, z_col):
    """
    Build SDs for X, Y, Z using sample SD (ddof=1).
    Skip rows with missing/invalid values in that axis.
    Require >= 2 values per axis; else return NaN.
    """
    gx, gy, gz = [], [], []
    for r in rows:
        if len(r) <= max(x_col, y_col, z_col):
            continue
        sx, sy, sz = r[x_col], r[y_col], r[z_col]
        if sx == "" or sy == "" or sz == "":
            continue
        try:
            gx.append(float(sx))
            gy.append(float(sy))
            gz.append(float(sz))
        except Exception:
            continue

    if len(gx) < 2 or len(gy) < 2 or len(gz) < 2:
        return np.nan

    sd_x = float(np.std(gx, ddof=1))
    sd_y = float(np.std(gy, ddof=1))
    sd_z = float(np.std(gz, ddof=1))
    return f"[{sd_x:.6f}, {sd_y:.6f}, {sd_z:.6f}]"

# ---------- Main ----------
def main():
    # Duplicate workbook
    try:
        shutil.copyfile(source_excel, output_excel)
    except Exception as e:
        print(f"❌ Failed to copy '{source_excel}' → '{output_excel}': {e}")
        return

    # Load three sheets (keep names/order)
    try:
        xls = pd.ExcelFile(output_excel, engine="openpyxl")
        sheet_names = xls.sheet_names
        if len(sheet_names) < 3:
            print("❌ Expected at least 3 sheets (overall, pre, post).")
            return
        df_s1 = xls.parse(sheet_names[0])   # overall
        df_s2 = xls.parse(sheet_names[1])   # pre
        df_s3 = xls.parse(sheet_names[2])   # post
    except Exception as e:
        print(f"❌ Failed to read '{output_excel}': {e}")
        return

    # Ensure target columns exist and set headers
    ensure_cols(df_s1, S1_COL)
    ensure_cols(df_s2, S2_COL)
    ensure_cols(df_s3, S3_COL)
    try: df_s1.columns.values[S1_COL] = "SD Gaze [x,y,z] (Overall)"
    except Exception: pass
    try: df_s2.columns.values[S2_COL] = "SD Gaze [x,y,z] (Pre)"
    except Exception: pass
    try: df_s3.columns.values[S3_COL] = "SD Gaze [x,y,z] (Post)"
    except Exception: pass

    print("Index | overall_sd             | pre_sd                 | post_sd                | Note")
    print("-------------------------------------------------------------------------------------------")

    for i in range(len(df_s1)):
        raw_id = df_s1.iat[i, id_col_excel]
        index_str = idx5_direct(raw_id)

        csv_path, folder = find_matching_csv(index_str)
        if not csv_path:
            df_s1.iat[i, S1_COL] = np.nan
            df_s2.iat[i, S2_COL] = np.nan
            df_s3.iat[i, S3_COL] = np.nan
            print(f"{index_str}: -  -  - (no csv)")
            continue

        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    df_s1.iat[i, S1_COL] = np.nan
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: -  -  - (empty csv)")
                    continue

                header = [h.strip() if isinstance(h, str) else h for h in header]
                rows = list(reader)

                # Required gaze columns (exact names)
                x_col = find_col_caseins(header, "Gaze Visualizer.x")
                y_col = find_col_caseins(header, "Gaze Visualizer.y")
                z_col = find_col_caseins(header, "Gaze Visualizer.z")
                if min(x_col, y_col, z_col) < 0:
                    df_s1.iat[i, S1_COL] = np.nan
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: -  -  - (gaze columns missing)")
                    continue

                # Overall SD
                sd_over = segment_sd_gaze(rows, x_col, y_col, z_col)
                df_s1.iat[i, S1_COL] = sd_over

                # Crisis split index
                time_col = find_col_caseins(header, "Time")
                split_idx = find_crisis_split_index(header, rows)

                if split_idx == -1 or time_col == -1:
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: {sd_over if not isinstance(sd_over, float) or not np.isnan(sd_over) else '-'}  -  - (no shook/0.2s)")
                    continue

                pre_rows  = rows[:split_idx]
                post_rows = rows[split_idx+1:]

                sd_pre  = segment_sd_gaze(pre_rows,  x_col, y_col, z_col)
                sd_post = segment_sd_gaze(post_rows, x_col, y_col, z_col)

                df_s2.iat[i, S2_COL] = sd_pre
                df_s3.iat[i, S3_COL] = sd_post

                print(f"{index_str}: "
                      f"{sd_over if not (isinstance(sd_over, float) and np.isnan(sd_over)) else '-':<22}  "
                      f"{sd_pre  if not (isinstance(sd_pre,  float) and np.isnan(sd_pre))  else '-':<22}  "
                      f"{sd_post if not (isinstance(sd_post, float) and np.isnan(sd_post)) else '-':<22}")

        except Exception as e:
            df_s1.iat[i, S1_COL] = np.nan
            df_s2.iat[i, S2_COL] = np.nan
            df_s3.iat[i, S3_COL] = np.nan
            print(f"{index_str}: -  -  - (error: {e})")

    # Save all three sheets
    try:
        with pd.ExcelWriter(output_excel, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{output_excel}': {e}")
        return

    print("\nDone! Gaze SD [x,y,z] written to Sheet1 col 15 (overall), Sheet2/3 col 10 (pre/post).")

if __name__ == "__main__":
    main()
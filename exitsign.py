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
S1_COL = 9  # Sheet 1 (overall) → column 10
S2_COL = 4  # Sheet 2 (pre)     → column 5
S3_COL = 4  # Sheet 3 (post)    → column 5

OFFSET = 0.229  # seconds added after "0.2 seconds" fallback

# ---------- Helpers ----------
def idx5_direct(v) -> str:
    """Direct index rule for Fire 2: zero-pad numerics to width 5; else str(...).zfill(5)."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v)).zfill(5)
    return str(v).zfill(5)

def find_matching_csv(index_5):
    """Return (csv_path, folder) whose filename starts with index_5; search in configured order."""
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if filename.lower().endswith(".csv") and filename[:5] == index_5:
                return os.path.join(folder, filename), folder
    return None, None

def find_header_col_caseins(header_row, target_name):
    """Return first column index whose header equals target_name (case-insensitive, trimmed); else -1."""
    tgt = target_name.strip().lower()
    for i, col in enumerate(header_row):
        if isinstance(col, str) and col.strip().lower() == tgt:
            return i
    return -1

def count_signage_looks(rows, look_col):
    """
    Count contiguous runs where LookingAt starts with 'Signage' (exact case).
    Same 'in_look' state machine as your original code.
    """
    count = 0
    in_look = False
    for r in rows:
        if len(r) <= look_col:
            in_look = False
            continue
        val = r[look_col]
        if val is None or val == "":
            in_look = False
            continue
        if isinstance(val, str) and val.startswith("Signage"):
            if not in_look:
                count += 1
                in_look = True
        else:
            in_look = False
    return count

def find_crisis_split_index(header, rows, offset=OFFSET):
    """
    1) Try 'shook' (robotEvent → Event). If found, return its row index.
    2) Else find '0.2 seconds' (robotEvent → Event): let t0 = Time at that row;
       return first row m with Time >= t0 + offset.
    If neither found (or Time missing/invalid), return -1.
    """
    time_col = find_header_col_caseins(header, "Time")
    ev_col   = find_header_col_caseins(header, "robotEvent")
    if ev_col == -1:
        ev_col = find_header_col_caseins(header, "Event")
        if ev_col == -1:
            return -1

    # 1) shook split
    for i, r in enumerate(rows):
        if len(r) <= ev_col: 
            continue
        ev = r[ev_col]
        if isinstance(ev, str) and ("shook" in ev.strip().lower()):
            return i

    # 2) 0.2 seconds fallback
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

    target = t0 + offset
    # first row with Time >= target
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

def ensure_cols(df: pd.DataFrame, upto_col_inclusive: int):
    while df.shape[1] <= upto_col_inclusive:
        df[f"Extra_{df.shape[1]+1}"] = np.nan

# ---------- Main ----------
def main():
    # Duplicate workbook
    try:
        shutil.copyfile(source_excel, output_excel)
    except Exception as e:
        print(f"❌ Failed to copy '{source_excel}' → '{output_excel}': {e}")
        return

    # Load three sheets (by current order)
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
    try: df_s1.columns.values[S1_COL] = "Signage Look Count (Overall)"
    except Exception: pass
    try: df_s2.columns.values[S2_COL] = "Signage Look Count (Pre)"
    except Exception: pass
    try: df_s3.columns.values[S3_COL] = "Signage Look Count (Post)"
    except Exception: pass

    print("Index | overall  pre  post  Note")
    print("---------------------------------")

    # Iterate indices from Sheet 1
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

                look_col = find_header_col_caseins(header, "LookingAt")
                if look_col == -1:
                    df_s1.iat[i, S1_COL] = np.nan
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: -  -  - (LookingAt col missing)")
                    continue

                # Overall
                overall_looks = count_signage_looks(rows, look_col)
                df_s1.iat[i, S1_COL] = overall_looks

                # Split index: shook → else '0.2 seconds' + 0.229
                split_idx = find_crisis_split_index(header, rows, offset=OFFSET)
                if split_idx == -1:
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: {overall_looks if not np.isnan(overall_looks) else '-'}  -  - (no shook/0.2s)")
                    continue

                pre_rows  = rows[:split_idx]
                post_rows = rows[split_idx+1:]

                pre_looks  = count_signage_looks(pre_rows,  look_col)
                post_looks = count_signage_looks(post_rows, look_col)

                df_s2.iat[i, S2_COL] = pre_looks
                df_s3.iat[i, S3_COL] = post_looks

                print(f"{index_str}: {overall_looks if not np.isnan(overall_looks) else '-'}  "
                      f"{pre_looks if not np.isnan(pre_looks) else '-'}  "
                      f"{post_looks if not np.isnan(post_looks) else '-'}")

        except Exception as e:
            df_s1.iat[i, S1_COL] = np.nan
            df_s2.iat[i, S2_COL] = np.nan
            df_s3.iat[i, S3_COL] = np.nan
            print(f"{index_str}: -  -  - (error: {e})")

    # Save all three sheets back
    try:
        with pd.ExcelWriter(output_excel, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{output_excel}': {e}")
        return

    print("\nDone! Signage Look Count written to: Sheet1 col 10 (overall), Sheet2/3 col 5 (pre/post).")

if __name__ == "__main__":
    main()
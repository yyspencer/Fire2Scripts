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
    os.path.join("noshookmodified"),
    os.path.join("noshookmodified", "baseline"),
]
id_col_excel = 0

# Sheet/column targets (Excel 1-based → 0-based)
S1_COL = 7  # Sheet 1 (overall) → column 8
S2_COL = 2  # Sheet 2 (pre)     → column 3
S3_COL = 2  # Sheet 3 (post)    → column 3

OFFSET = 0.229  # seconds to add after "0.2 seconds" tag (fallback crisis estimate)

# ---------- Helpers ----------
def idx5_direct(v) -> str:
    """
    Fire 2 rule: direct index.
    - If numeric-like, zero-pad to 5 (e.g., 123 -> '00123')
    - Else str(...).zfill(5) (no trimming).
    """
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
    t = target_name.strip().lower()
    for i, col in enumerate(header_row):
        if isinstance(col, str) and col.strip().lower() == t:
            return i
    return -1

def count_robot_looks(rows, look_col):
    """
    Count contiguous runs where LookingAt == 'Robot' (exact match).
    Empty cells or short rows reset in_look but do not increment the count.
    """
    robot_looks = 0
    in_look = False
    for r in rows:
        if len(r) <= look_col:
            in_look = False
            continue
        val = r[look_col]
        if val is None or val == "":
            in_look = False
            continue
        if val == "Robot":
            if not in_look:
                robot_looks += 1
                in_look = True
        else:
            in_look = False
    return robot_looks

def find_crisis_split_index(header, rows, offset=OFFSET):
    """
    1) Try to find 'shook' (robotEvent → Event). If found, return its row index.
    2) Else look for '0.2 seconds' (robotEvent → Event). Let t0 = Time at that row,
       then return first row m with Time >= t0 + offset.
    If neither found (or Time missing/invalid), return -1.
    """
    # Columns
    time_col = find_header_col_caseins(header, "Time")
    ev_col   = find_header_col_caseins(header, "robotEvent")
    if ev_col == -1:
        ev_col = find_header_col_caseins(header, "Event")

    # Need an event column for searching both 'shook' and '0.2 seconds'
    if ev_col == -1:
        return -1

    # 1) shook split
    for i, r in enumerate(rows):
        if len(r) <= ev_col:
            continue
        ev = r[ev_col]
        if isinstance(ev, str) and ("shook" in ev.strip().lower()):
            return i

    # 2) '0.2 seconds' fallback → needs Time column
    if time_col == -1:
        return -1

    idx_02 = -1
    t0 = None
    for i, r in enumerate(rows):
        if len(r) <= max(ev_col, time_col):
            continue
        ev = r[ev_col]
        if isinstance(ev, str) and ("0.2 seconds" in ev.strip().lower()):
            try:
                t0 = float(r[time_col])
            except Exception:
                t0 = None
            idx_02 = i
            break

    if idx_02 == -1 or t0 is None:
        return -1

    crisis_time_est = t0 + offset
    # find first row with Time >= crisis_time_est
    for m in range(idx_02, len(rows)):
        r = rows[m]
        if len(r) <= time_col:
            continue
        try:
            tm = float(r[time_col])
        except Exception:
            continue
        if tm >= crisis_time_est:
            return m

    return -1

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
    while df_s1.shape[1] <= S1_COL:
        df_s1[f"Extra_{df_s1.shape[1]+1}"] = np.nan
    while df_s2.shape[1] <= S2_COL:
        df_s2[f"Extra_{df_s2.shape[1]+1}"] = np.nan
    while df_s3.shape[1] <= S3_COL:
        df_s3[f"Extra_{df_s3.shape[1]+1}"] = np.nan

    try: df_s1.columns.values[S1_COL] = "Robot Look Count (Overall)"
    except Exception: pass
    try: df_s2.columns.values[S2_COL] = "Robot Look Count (Pre)"
    except Exception: pass
    try: df_s3.columns.values[S3_COL] = "Robot Look Count (Post)"
    except Exception: pass

    # Process indices
    print("Index | overall  pre  post  Note")
    print("---------------------------------")

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
            with open(csv_path, newline="", encoding="utf-8") as f:
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

                # Overall look count
                overall_looks = count_robot_looks(rows, look_col)
                df_s1.iat[i, S1_COL] = overall_looks

                # Split index: shook → else '0.2 seconds' + 0.229
                split_idx = find_crisis_split_index(header, rows)
                if split_idx == -1:
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: {overall_looks if not np.isnan(overall_looks) else '-'}  -  - (no shook/0.2s)")
                    continue

                pre_rows  = rows[:split_idx]
                post_rows = rows[split_idx+1:]

                pre_looks  = count_robot_looks(pre_rows,  look_col)
                post_looks = count_robot_looks(post_rows, look_col)

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

    # Save all three sheets back into Proceed workbook
    try:
        with pd.ExcelWriter(output_excel, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{output_excel}': {e}")
        return

    print("\nDone! Robot Look Count written to: Sheet1 col 8 (overall), Sheet2/3 col 3 (pre/post).")

if __name__ == "__main__":
    main()
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
S1_COL = 6  # Sheet 1 (overall) → column 7
S2_COL = 1  # Sheet 2 (pre)     → column 2
S3_COL = 1  # Sheet 3 (post)    → column 2

OFFSET = 0.229  # seconds to add after "0.2 seconds" tag

# ---------- Helpers ----------
def idx5_direct(v) -> str:
    """Fire 2 rule: direct index (numeric -> zfill(5); else str(...).zfill(5))."""
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

def percent_looking_robot_include_blanks(rows, look_col):
    """
    ORIGINAL DENOMINATOR LOGIC:
    - Denominator counts EVERY row that reaches the LookingAt column (even if blank).
    - Numerator counts rows with LookingAt == 'Robot' (exact match).
    """
    robot_cnt = 0
    denom = 0
    for r in rows:
        if len(r) <= look_col:
            continue
        denom += 1  # include blanks
        if r[look_col] == "Robot":
            robot_cnt += 1
    return (robot_cnt / denom * 100.0) if denom > 0 else np.nan, robot_cnt, denom

def find_shook_row(header, rows):
    """
    Find first row index (into 'rows') where robotEvent (preferred) or Event
    contains 'shook' (case-insensitive substring). Returns row_index or -1.
    """
    ev_col = find_header_col_caseins(header, "robotEvent")
    if ev_col == -1:
        ev_col = find_header_col_caseins(header, "Event")
        if ev_col == -1:
            return -1
    for i, r in enumerate(rows):
        if len(r) <= ev_col:
            continue
        txt = r[ev_col]
        if isinstance(txt, str) and ("shook" in txt.strip().lower()):
            return i
    return -1

def find_crisis_split_index(header, rows):
    """
    1) Try 'shook' split (robotEvent -> Event). If found, return its row index.
    2) Else find first '0.2 seconds' in robotEvent/Event; let t0 = Time at that row,
       then find first row m with Time >= t0 + 0.229 and return m.
    If neither found (or Time missing), return -1.
    """
    # 1) shook
    shook_idx = find_shook_row(header, rows)
    if shook_idx != -1:
        return shook_idx

    # 2) 0.2 seconds fallback
    time_col = find_header_col_caseins(header, "Time")
    if time_col == -1:
        return -1

    evt_col = find_header_col_caseins(header, "robotEvent")
    if evt_col == -1:
        evt_col = find_header_col_caseins(header, "Event")
        if evt_col == -1:
            return -1

    # find first row with "0.2 seconds" (substring, case-insensitive)
    idx_02 = -1
    t0 = None
    for i, r in enumerate(rows):
        if len(r) <= max(evt_col, time_col):
            continue
        ev = r[evt_col]
        if isinstance(ev, str) and ("0.2 seconds" in ev.strip().lower()):
            try:
                t0 = float(r[time_col])
            except Exception:
                t0 = None
            idx_02 = i
            break

    if idx_02 == -1 or t0 is None:
        return -1

    crisis_time_est = t0 + OFFSET
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

    try: df_s1.columns.values[S1_COL] = "% Looking At Robot (Overall)"
    except Exception: pass
    try: df_s2.columns.values[S2_COL] = "% Looking At Robot (Pre)"
    except Exception: pass
    try: df_s3.columns.values[S3_COL] = "% Looking At Robot (Post)"
    except Exception: pass

    print("Index | overall%   pre%   post%   Note")
    print("-------------------------------------------")

    # Iterate per index from Sheet 1
    for i in range(len(df_s1)):
        raw_id = df_s1.iat[i, id_col_excel]
        index_str = idx5_direct(raw_id)

        csv_path, folder = find_matching_csv(index_str)
        if not csv_path:
            df_s1.iat[i, S1_COL] = np.nan
            df_s2.iat[i, S2_COL] = np.nan
            df_s3.iat[i, S3_COL] = np.nan
            print(f"{index_str}: -        -      -      (no csv)")
            continue

        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    df_s1.iat[i, S1_COL] = np.nan
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: -        -      -      (empty csv)")
                    continue

                header = [h.strip() if isinstance(h, str) else h for h in header]
                rows = list(reader)

                # Locate LookingAt
                look_col = find_header_col_caseins(header, "LookingAt")
                if look_col == -1:
                    df_s1.iat[i, S1_COL] = np.nan
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: -        -      -      (LookingAt col missing)")
                    continue

                # Overall %
                overall_pct, rc_all, tot_all = percent_looking_robot_include_blanks(rows, look_col)
                df_s1.iat[i, S1_COL] = overall_pct

                # Crisis split: shook → else 0.2 seconds + 0.229
                split_idx = find_crisis_split_index(header, rows)
                if split_idx == -1:
                    df_s2.iat[i, S2_COL] = np.nan
                    df_s3.iat[i, S3_COL] = np.nan
                    print(f"{index_str}: {overall_pct if not np.isnan(overall_pct) else '-':>7}    -      -      (no shook/0.2s)")
                    continue

                pre_rows  = rows[:split_idx]
                post_rows = rows[split_idx+1:]

                pre_pct,  rc_pre,  tot_pre  = percent_looking_robot_include_blanks(pre_rows,  look_col)
                post_pct, rc_post, tot_post = percent_looking_robot_include_blanks(post_rows, look_col)

                df_s2.iat[i, S2_COL] = pre_pct
                df_s3.iat[i, S3_COL] = post_pct

                print(f"{index_str}: "
                      f"{overall_pct if not np.isnan(overall_pct) else '-':>7}  "
                      f"{pre_pct if not np.isnan(pre_pct) else '-':>7}  "
                      f"{post_pct if not np.isnan(post_pct) else '-':>7}  "
                      f"(rows all={tot_all}, pre={tot_pre}, post={tot_post})")

        except Exception as e:
            df_s1.iat[i, S1_COL] = np.nan
            df_s2.iat[i, S2_COL] = np.nan
            df_s3.iat[i, S3_COL] = np.nan
            print(f"{index_str}: -        -      -      (error: {e})")

    # Save all three sheets back into Proceed workbook
    try:
        with pd.ExcelWriter(output_excel, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{output_excel}': {e}")
        return

    print("\nDone! % Looking At Robot written to: Sheet1 col 7 (overall), Sheet2/3 col 2 (pre/post).")

if __name__ == "__main__":
    main()
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
    os.path.join("noshook", "baseline")
]
id_col_excel = 0

# Sheet/column targets (Excel 1-based → 0-based)
# Sheet 1 (overall): mean, sd, max, min → cols 16..19 → 15..18
S1_MEAN, S1_SD, S1_MAX, S1_MIN = 15, 16, 17, 18
# Sheet 2 (pre): mean, sd, max, min → cols 11..14 → 10..13
S2_MEAN, S2_SD, S2_MAX, S2_MIN = 10, 11, 12, 13
# Sheet 3 (post): mean, sd, max, min → cols 11..14 → 10..13
S3_MEAN, S3_SD, S3_MAX, S3_MIN = 10, 11, 12, 13

OFFSET = 0.229  # seconds added after "0.2 seconds" tag for crisis estimate

# ---------- Helpers ----------
def idx5_direct(v) -> str:
    """Direct index: if numeric-like, zero-pad to 5; else str(...).zfill(5)."""
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
        for fn in os.listdir(folder):
            if fn.endswith(".csv") and fn[:5] == index_5:
                return os.path.join(folder, fn), folder
    return None, None

def find_col_caseins(header_row, target_name):
    """Case-insensitive, trimmed equality on header names. Return col index or -1."""
    t = target_name.strip().lower()
    for i, col in enumerate(header_row):
        if isinstance(col, str) and col.strip().lower() == t:
            return i
    return -1

def split_index_shook_or_02(header, rows, time_idx):
    """
    Find crisis split row index:
      1) first row containing 'shook' in robotEvent (preferred) → Event (case-insensitive substring).
      2) else first '0.2 seconds' → let t0 = Time at that row; return first row with Time >= t0 + OFFSET.
      3) else return -1.
    """
    ev_idx = find_col_caseins(header, "robotEvent")
    if ev_idx == -1:
        ev_idx = find_col_caseins(header, "Event")
        if ev_idx == -1:
            return -1

    # 1) shook
    for i, r in enumerate(rows):
        if len(r) <= ev_idx:
            continue
        ev = r[ev_idx]
        if isinstance(ev, str) and ("shook" in ev.strip().lower()):
            return i

    # 2) 0.2 seconds fallback (needs Time)
    if time_idx == -1:
        return -1

    start_i, t0 = -1, None
    for i, r in enumerate(rows):
        if len(r) <= max(ev_idx, time_idx):
            continue
        ev = r[ev_idx]
        if isinstance(ev, str) and ("0.2 seconds" in ev.strip().lower()):
            try:
                t0 = float(r[time_idx])
            except Exception:
                t0 = None
            start_i = i
            break

    if start_i == -1 or t0 is None:
        return -1

    tgt = t0 + OFFSET
    for m in range(start_i, len(rows)):
        if len(rows[m]) <= time_idx:
            continue
        try:
            tm = float(rows[m][time_idx])
        except Exception:
            continue
        if tm >= tgt:
            return m
    return -1

def safe_float(s):
    try:
        return float(s)
    except Exception:
        return np.nan

def compute_distances(rows, px_idx, py_idx, pz_idx, rx_idx, ry_idx, rz_idx):
    """Per-row distance ‖player - robot‖; skip rows with invalid/missing coordinates."""
    dists = []
    for r in rows:
        if len(r) <= max(px_idx, py_idx, pz_idx, rx_idx, ry_idx, rz_idx):
            continue
        try:
            p = np.array([float(r[px_idx]), float(r[py_idx]), float(r[pz_idx])], dtype=float)
            q = np.array([float(r[rx_idx]), float(r[ry_idx]), float(r[rz_idx])], dtype=float)
        except Exception:
            continue
        if not (np.isfinite(p).all() and np.isfinite(q).all()):
            continue
        dists.append(float(np.linalg.norm(p - q)))
    return dists

def stats_from_list(vals):
    """Return (mean, sd(ddof=1), max, min) or (nan, nan, nan, nan) if <2 values (match your pattern)."""
    if len(vals) < 2:
        return (np.nan, np.nan, np.nan, np.nan)
    arr = np.array(vals, dtype=float)
    mean = float(np.mean(arr))
    sd   = float(np.std(arr, ddof=1))
    mx   = float(np.max(arr))
    mn   = float(np.min(arr))
    return (mean, sd, mx, mn)

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
    ensure_cols(df_s1, S1_MIN)
    ensure_cols(df_s2, S2_MIN)
    ensure_cols(df_s3, S3_MIN)
    try:
        df_s1.columns.values[S1_MEAN] = "Mean Player-Robot Dist (Overall)"
        df_s1.columns.values[S1_SD]   = "SD Player-Robot Dist (Overall)"
        df_s1.columns.values[S1_MAX]  = "Max Player-Robot Dist (Overall)"
        df_s1.columns.values[S1_MIN]  = "Min Player-Robot Dist (Overall)"
        df_s2.columns.values[S2_MEAN] = "Mean Player-Robot Dist (Pre)"
        df_s2.columns.values[S2_SD]   = "SD Player-Robot Dist (Pre)"
        df_s2.columns.values[S2_MAX]  = "Max Player-Robot Dist (Pre)"
        df_s2.columns.values[S2_MIN]  = "Min Player-Robot Dist (Pre)"
        df_s3.columns.values[S3_MEAN] = "Mean Player-Robot Dist (Post)"
        df_s3.columns.values[S3_SD]   = "SD Player-Robot Dist (Post)"
        df_s3.columns.values[S3_MAX]  = "Max Player-Robot Dist (Post)"
        df_s3.columns.values[S3_MIN]  = "Min Player-Robot Dist (Post)"
    except Exception:
        pass

    print("Index | overall(mean/sd/max/min) | pre(mean/sd/max/min) | post(mean/sd/max/min) | Note")
    print("-"*120)

    # Iterate indices from sheet 1
    for i in range(len(df_s1)):
        raw_id = df_s1.iat[i, id_col_excel]
        index_str = idx5_direct(raw_id)

        csv_path, folder = find_matching_csv(index_str)
        if not csv_path:
            # write NaNs everywhere for this row
            for df_t, cols in [(df_s1,(S1_MEAN,S1_SD,S1_MAX,S1_MIN)),
                               (df_s2,(S2_MEAN,S2_SD,S2_MAX,S2_MIN)),
                               (df_s3,(S3_MEAN,S3_SD,S3_MAX,S3_MIN))]:
                for c in cols: df_t.iat[i, c] = np.nan
            print(f"{index_str}: (no csv)")
            continue

        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    for df_t, cols in [(df_s1,(S1_MEAN,S1_SD,S1_MAX,S1_MIN)),
                                       (df_s2,(S2_MEAN,S2_SD,S2_MAX,S2_MIN)),
                                       (df_s3,(S3_MEAN,S3_SD,S3_MAX,S3_MIN))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (empty csv)")
                    continue

                # column indices (exact header names as in your original scripts)
                t_col  = find_col_caseins(header, "Time")
                px_col = find_col_caseins(header, "PlayerVR.x")
                py_col = find_col_caseins(header, "PlayerVR.y")
                pz_col = find_col_caseins(header, "PlayerVR.z")
                rx_col = find_col_caseins(header, "Robot.x")
                ry_col = find_col_caseins(header, "Robot.y")
                rz_col = find_col_caseins(header, "Robot.z")
                if min(t_col, px_col, py_col, pz_col, rx_col, ry_col, rz_col) < 0:
                    for df_t, cols in [(df_s1,(S1_MEAN,S1_SD,S1_MAX,S1_MIN)),
                                       (df_s2,(S2_MEAN,S2_SD,S2_MAX,S2_MIN)),
                                       (df_s3,(S3_MEAN,S3_SD,S3_MAX,S3_MIN))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (missing core columns)")
                    continue

                rows = list(reader)
                if not rows:
                    for df_t, cols in [(df_s1,(S1_MEAN,S1_SD,S1_MAX,S1_MIN)),
                                       (df_s2,(S2_MEAN,S2_SD,S2_MAX,S2_MIN)),
                                       (df_s3,(S3_MEAN,S3_SD,S3_MAX,S3_MIN))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (no data rows)")
                    continue

                # overall distances
                dists_all = compute_distances(rows, px_col, py_col, pz_col, rx_col, ry_col, rz_col)
                m_all, s_all, mx_all, mn_all = stats_from_list(dists_all)
                df_s1.iat[i, S1_MEAN] = m_all
                df_s1.iat[i, S1_SD]   = s_all
                df_s1.iat[i, S1_MAX]  = mx_all
                df_s1.iat[i, S1_MIN]  = mn_all

                # crisis split index: shook → else 0.2+0.229
                split_idx = split_index_shook_or_02(header, rows, t_col)
                if split_idx == -1:
                    # no split -> leave pre/post NaN
                    for c in (S2_MEAN,S2_SD,S2_MAX,S2_MIN,S3_MEAN,S3_SD,S3_MAX,S3_MIN):
                        (df_s2 if c in (S2_MEAN,S2_SD,S2_MAX,S2_MIN) else df_s3).iat[i, c if c in (S2_MEAN,S2_SD,S2_MAX,S2_MIN) else c] = np.nan
                    print(f"{index_str}: overall=({m_all:.6g}/{s_all:.6g}/{mx_all:.6g}/{mn_all:.6g}) | pre=NA | post=NA (no crisis)")
                    continue

                pre_rows  = rows[:split_idx]
                post_rows = rows[split_idx+1:]

                d_pre  = compute_distances(pre_rows,  px_col, py_col, pz_col, rx_col, ry_col, rz_col)
                d_post = compute_distances(post_rows, px_col, py_col, pz_col, rx_col, ry_col, rz_col)

                m_pre, s_pre, mx_pre, mn_pre   = stats_from_list(d_pre)
                m_post, s_post, mx_post, mn_post = stats_from_list(d_post)

                df_s2.iat[i, S2_MEAN] = m_pre
                df_s2.iat[i, S2_SD]   = s_pre
                df_s2.iat[i, S2_MAX]  = mx_pre
                df_s2.iat[i, S2_MIN]  = mn_pre

                df_s3.iat[i, S3_MEAN] = m_post
                df_s3.iat[i, S3_SD]   = s_post
                df_s3.iat[i, S3_MAX]  = mx_post
                df_s3.iat[i, S3_MIN]  = mn_post

                print(f"{index_str}: overall=({m_all:.6g}/{s_all:.6g}/{mx_all:.6g}/{mn_all:.6g}) | "
                      f"pre=({m_pre:.6g}/{s_pre:.6g}/{mx_pre:.6g}/{mn_pre:.6g}) | "
                      f"post=({m_post:.6g}/{s_post:.6g}/{mx_post:.6g}/{mn_post:.6g})")

        except Exception as e:
            for df_t, cols in [(df_s1,(S1_MEAN,S1_SD,S1_MAX,S1_MIN)),
                               (df_s2,(S2_MEAN,S2_SD,S2_MAX,S2_MIN)),
                               (df_s3,(S3_MEAN,S3_SD,S3_MAX,S3_MIN))]:
                for c in cols: df_t.iat[i, c] = np.nan
            print(f"{index_str}: error ({e})")
            continue

    # Save all three sheets
    try:
        with pd.ExcelWriter(output_excel, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{output_excel}': {e}")
        return

    print("\nDone! Player-Robot distance stats written to Sheet1 cols 16–19, Sheet2/3 cols 11–14.")

if __name__ == "__main__":
    main()
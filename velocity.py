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
# Sheet 1 (overall): mean, sd, min, max → cols 11..14 → 10..13
S1_MEAN, S1_SD, S1_MIN, S1_MAX = 10, 11, 12, 13
# Sheet 2 (pre): mean, sd, min, max → cols 6..9 → 5..8
S2_MEAN, S2_SD, S2_MIN, S2_MAX = 5, 6, 7, 8
# Sheet 3 (post): mean, sd, min, max → cols 6..9 → 5..8
S3_MEAN, S3_SD, S3_MIN, S3_MAX = 5, 6, 7, 8

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

def find_header_col_exact(header, name):
    """Case-sensitive exact match for core columns (Time, PlayerVR.*, Robot.*, roomEvent, Event, robotEvent)."""
    try:
        return header.index(name)
    except ValueError:
        return -1

def split_index_shook_or_02(header, rows, time_idx):
    """
    Find crisis split row index:
      1) first 'shook' in robotEvent (preferred) → Event (case-insensitive substring).
      2) else first '0.2 seconds' -> let t0 = Time at that row; return first row with Time >= t0 + OFFSET.
      3) else return -1.
    """
    # robotEvent preferred; else Event
    ev_idx = find_header_col_exact(header, "robotEvent")
    if ev_idx == -1:
        ev_idx = find_header_col_exact(header, "Event")
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
    t0 = None
    start_i = -1
    for i, r in enumerate(rows):
        if len(r) <= max(time_idx, ev_idx):
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

def compute_speeds_for_mask(times, pxyz, valid_mask):
    """
    Your original speed calc:
      iterate rows in order; between consecutive valid rows (valid_mask==True),
      speed = ||Δpos|| / Δt  (skip non-positive dt).
    Return list of speeds.
    """
    speeds = []
    prev_idx = None
    n = len(times)
    for i in range(n):
        if not valid_mask[i]:
            continue
        if prev_idx is None:
            prev_idx = i
            continue
        if i - prev_idx != 1:
            prev_idx = i
            continue
        t0, t1 = times[prev_idx], times[i]
        if not (np.isfinite(t0) and np.isfinite(t1)) or (t1 <= t0):
            prev_idx = i
            continue
        p0, p1 = pxyz[prev_idx], pxyz[i]
        if not (np.isfinite(p0).all() and np.isfinite(p1).all()):
            prev_idx = i
            continue
        speeds.append(np.linalg.norm(p1 - p0) / (t1 - t0))
        prev_idx = i
    return speeds

def stats_from_speeds(speeds):
    """Return (mean, sd(ddof=1), min, max) or (nan, nan, nan, nan) if <2 speeds."""
    if len(speeds) < 2:
        return (np.nan, np.nan, np.nan, np.nan)
    arr = np.array(speeds, dtype=float)
    mean = float(np.mean(arr))
    sd   = float(np.std(arr, ddof=1))
    mn   = float(np.min(arr))
    mx   = float(np.max(arr))
    return (mean, sd, mn, mx)

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

    # Ensure target cols
    ensure_cols(df_s1, S1_MAX)
    ensure_cols(df_s2, S2_MAX)
    ensure_cols(df_s3, S3_MAX)
    try:
        df_s1.columns.values[S1_MEAN] = "Mean Player Velocity (Overall)"
        df_s1.columns.values[S1_SD]   = "SD Player Velocity (Overall)"
        df_s1.columns.values[S1_MIN]  = "Min Player Velocity (Overall)"
        df_s1.columns.values[S1_MAX]  = "Max Player Velocity (Overall)"
        df_s2.columns.values[S2_MEAN] = "Mean Player Velocity (Pre)"
        df_s2.columns.values[S2_SD]   = "SD Player Velocity (Pre)"
        df_s2.columns.values[S2_MIN]  = "Min Player Velocity (Pre)"
        df_s2.columns.values[S2_MAX]  = "Max Player Velocity (Pre)"
        df_s3.columns.values[S3_MEAN] = "Mean Player Velocity (Post)"
        df_s3.columns.values[S3_SD]   = "SD Player Velocity (Post)"
        df_s3.columns.values[S3_MIN]  = "Min Player Velocity (Post)"
        df_s3.columns.values[S3_MAX]  = "Max Player Velocity (Post)"
    except Exception:
        pass

    print("Index | overall(mean/sd/min/max) | pre(mean/sd/min/max) | post(mean/sd/min/max) | Note")
    print("-"*110)

    # Iterate indices from sheet 1
    for i in range(len(df_s1)):
        raw_id = df_s1.iat[i, id_col_excel]
        index_str = idx5_direct(raw_id)

        csv_path, folder = find_matching_csv(index_str)
        if not csv_path:
            # write NaNs everywhere for this row
            for (df_t, cols) in [(df_s1,(S1_MEAN,S1_SD,S1_MIN,S1_MAX)),
                                 (df_s2,(S2_MEAN,S2_SD,S2_MIN,S2_MAX)),
                                 (df_s3,(S3_MEAN,S3_SD,S3_MIN,S3_MAX))]:
                for c in cols: df_t.iat[i, c] = np.nan
            print(f"{index_str}: (no csv)")
            continue

        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    # write NaNs
                    for (df_t, cols) in [(df_s1,(S1_MEAN,S1_SD,S1_MIN,S1_MAX)),
                                         (df_s2,(S2_MEAN,S2_SD,S2_MIN,S2_MAX)),
                                         (df_s3,(S3_MEAN,S3_SD,S3_MIN,S3_MAX))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (empty csv)")
                    continue

                # exact column names (like your original)
                t_col  = find_header_col_exact(header, "Time")
                px_col = find_header_col_exact(header, "PlayerVR.x")
                py_col = find_header_col_exact(header, "PlayerVR.y")
                pz_col = find_header_col_exact(header, "PlayerVR.z")
                rv_col = find_header_col_exact(header, "roomEvent")
                ev_col = find_header_col_exact(header, "robotEvent")
                if ev_col == -1:
                    ev_col = find_header_col_exact(header, "Event")  # crisis fallback

                if min(t_col, px_col, py_col, pz_col) < 0:
                    # write NaNs
                    for (df_t, cols) in [(df_s1,(S1_MEAN,S1_SD,S1_MIN,S1_MAX)),
                                         (df_s2,(S2_MEAN,S2_SD,S2_MIN,S2_MAX)),
                                         (df_s3,(S3_MEAN,S3_SD,S3_MIN,S3_MAX))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (missing core columns)")
                    continue

                rows = list(reader)
                if not rows:
                    for (df_t, cols) in [(df_s1,(S1_MEAN,S1_SD,S1_MIN,S1_MAX)),
                                         (df_s2,(S2_MEAN,S2_SD,S2_MIN,S2_MAX)),
                                         (df_s3,(S3_MEAN,S3_SD,S3_MIN,S3_MAX))]:
                        for c in cols: df_t.iat[i, c] = np.nan
                    print(f"{index_str}: (no data rows)")
                    continue

                # Extract arrays
                def sf(s): 
                    try: return float(s)
                    except Exception: return np.nan

                n = len(rows)
                times = np.array([sf(r[t_col]) if len(r) > t_col else np.nan for r in rows], dtype=float)
                pxyz  = np.array([[sf(r[px_col]), sf(r[py_col]), sf(r[pz_col])] 
                                  if len(r) > max(px_col,py_col,pz_col) else [np.nan]*3 for r in rows], dtype=float)

                # Survey Room exclusion: roomEvent (exact) preferred; else Event fallback (case-insensitive substr)
                in_survey = np.zeros(n, dtype=bool)
                if rv_col != -1:
                    state = False
                    for k in range(n):
                        rv = rows[k][rv_col] if len(rows[k]) > rv_col else ""
                        if rv == "Entered Survey Room":
                            state = True
                        elif rv == "Exited Survey Room":
                            state = False
                        in_survey[k] = state
                else:
                    ev_evt = find_header_col_exact(header, "Event")
                    if ev_evt != -1:
                        state = False
                        for k in range(n):
                            s = (rows[k][ev_evt] if len(rows[k]) > ev_evt else "")
                            s = str(s).strip().lower()
                            if "entered survey room" in s:
                                state = True
                            elif "exited survey room" in s:
                                state = False
                            in_survey[k] = state

                # Crisis split index
                split_idx = split_index_shook_or_02(header, rows, t_col)

                # Valid mask = finite time & positions & not in survey
                valid = np.isfinite(times) & np.isfinite(pxyz).all(axis=1) & (~in_survey)

                # Overall stats
                speeds_all = compute_speeds_for_mask(times, pxyz, valid)
                m_all, s_all, mn_all, mx_all = stats_from_speeds(speeds_all)
                df_s1.iat[i, S1_MEAN] = m_all
                df_s1.iat[i, S1_SD]   = s_all
                df_s1.iat[i, S1_MIN]  = mn_all
                df_s1.iat[i, S1_MAX]  = mx_all

                if split_idx == -1 or not np.isfinite(times[split_idx]):
                    # No crisis: pre/post NaN
                    for c in (S2_MEAN,S2_SD,S2_MIN,S2_MAX,S3_MEAN,S3_SD,S3_MIN,S3_MAX):
                        (df_s2 if c in (S2_MEAN,S2_SD,S2_MIN,S2_MAX) else df_s3).iat[i, c if c in (S2_MEAN,S2_SD,S2_MIN,S2_MAX) else c] = np.nan
                    print(f"{index_str}: overall=({m_all:.6g}/{s_all:.6g}/{mn_all:.6g}/{mx_all:.6g}) | pre=NA | post=NA (no crisis)")
                    continue

                # Time threshold for split
                crisis_t = times[split_idx]

                # Pre mask: strictly before crisis; Post mask: crisis and after
                pre_mask  = valid & (times < crisis_t)
                post_mask = valid & (times >= crisis_t)

                speeds_pre  = compute_speeds_for_mask(times, pxyz, pre_mask)
                speeds_post = compute_speeds_for_mask(times, pxyz, post_mask)

                m_pre, s_pre, mn_pre, mx_pre   = stats_from_speeds(speeds_pre)
                m_post, s_post, mn_post, mx_post = stats_from_speeds(speeds_post)

                df_s2.iat[i, S2_MEAN] = m_pre
                df_s2.iat[i, S2_SD]   = s_pre
                df_s2.iat[i, S2_MIN]  = mn_pre
                df_s2.iat[i, S2_MAX]  = mx_pre

                df_s3.iat[i, S3_MEAN] = m_post
                df_s3.iat[i, S3_SD]   = s_post
                df_s3.iat[i, S3_MIN]  = mn_post
                df_s3.iat[i, S3_MAX]  = mx_post

                print(f"{index_str}: overall=({m_all:.6g}/{s_all:.6g}/{mn_all:.6g}/{mx_all:.6g}) | "
                      f"pre=({m_pre:.6g}/{s_pre:.6g}/{mn_pre:.6g}/{mx_pre:.6g}) | "
                      f"post=({m_post:.6g}/{s_post:.6g}/{mn_post:.6g}/{mx_post:.6g})")

        except Exception as e:
            # Write NaNs on failure
            for (df_t, cols) in [(df_s1,(S1_MEAN,S1_SD,S1_MIN,S1_MAX)),
                                 (df_s2,(S2_MEAN,S2_SD,S2_MIN,S2_MAX)),
                                 (df_s3,(S3_MEAN,S3_SD,S3_MIN,S3_MAX))]:
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

    print("\nDone! Player velocity stats written to Sheet1 cols 11–14, Sheet2/3 cols 6–9.")

if __name__ == "__main__":
    main()
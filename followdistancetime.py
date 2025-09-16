#!/usr/bin/env python3
import os
import csv
import math
import shutil
import numpy as np
import pandas as pd

# --- Configuration ---
PROXIMITY_THRESHOLD = 2.0    # meters
FOLLOW_WINDOW       = 10.0   # seconds
OFFSET              = 0.229  # seconds for noshook estimate

SOURCE_XLSX = "Fire 2 Data.xlsx"
OUTPUT_XLSX = "Fire 2 Proceed.xlsx"
FOLDERS     = [
    "shook",
    os.path.join("shook", "baseline"),
    "noshook",
    os.path.join("noshookmodified", "baseline"),
]

# Excel: index column (0-based)
ID_COL = 0

# Sheet/column targets (Excel 1-based → 0-based)
# Sheet 1 (overall): Dist, Time → cols 23–24 → 22..23
S1_COL_DIST, S1_COL_TIME = 22, 23
# Sheet 2 (pre): Dist, Time → cols 18–19 → 17..18
S2_COL_DIST, S2_COL_TIME = 17, 18
# Sheet 3 (post): Dist, Time → cols 18–19 → 17..18
S3_COL_DIST, S3_COL_TIME = 17, 18

# --- Helpers ---

def idx5(v) -> str:
    """Use the first 5 characters of the cell (no zero-padding)."""
    return str(v).strip()[:5]

def euclidean_distance(p1, p2):
    return math.sqrt(
        (p1[0]-p2[0])**2 +
        (p1[1]-p2[1])**2 +
        (p1[2]-p2[2])**2
    )

def find_matching_csv(index_5):
    """Return (full_path, folder_name) for the CSV whose name starts with index_5."""
    for folder in FOLDERS:
        if not os.path.isdir(folder):
            continue
        for fn in os.listdir(folder):
            if fn.lower().endswith(".csv") and fn.startswith(index_5):
                return os.path.join(folder, fn), folder
    return None, None

def ensure_cols(df: pd.DataFrame, upto_col_inclusive: int):
    while df.shape[1] <= upto_col_inclusive:
        df[f"Extra_{df.shape[1]+1}"] = np.nan

def find_col_caseins(header, name):
    """Case-insensitive, trimmed equality on header names. Return col index or -1."""
    t = name.strip().lower()
    for i, h in enumerate(header):
        if isinstance(h, str) and h.strip().lower() == t:
            return i
    return -1

def detect_crisis_index(header, rows):
    """
    Return split row index:
      1) first 'shook' in robotEvent -> Event (case-insensitive substring)
      2) else first '0.2 seconds' -> t0; then first row with Time >= t0 + OFFSET
      else -1
    """
    time_idx = find_col_caseins(header, "Time")
    evt_idx  = find_col_caseins(header, "robotEvent")
    if evt_idx == -1:
        evt_idx = find_col_caseins(header, "Event")

    if evt_idx == -1:
        return -1

    # 1) shook
    for i, r in enumerate(rows):
        if len(r) <= evt_idx: continue
        ev = r[evt_idx]
        if isinstance(ev, str) and ("shook" in ev.strip().lower()):
            return i

    # 2) 0.2 seconds fallback
    if time_idx == -1:
        return -1
    t0 = None
    i0 = -1
    for i, r in enumerate(rows):
        if len(r) <= max(time_idx, evt_idx): continue
        ev = r[evt_idx]
        if isinstance(ev, str) and ("0.2 seconds" in ev.strip().lower()):
            try:
                t0 = float(r[time_idx])
            except Exception:
                t0 = None
            i0 = i
            break
    if i0 == -1 or t0 is None:
        return -1

    target = t0 + OFFSET
    for m in range(i0, len(rows)):
        if len(rows[m]) <= time_idx: continue
        try:
            tm = float(rows[m][time_idx])
        except Exception:
            continue
        if tm >= target:
            return m
    return -1

# --- Side-constrained follow (future-allowed but no cross-boundary matches) ---
def compute_follow_stats_side_locked(rows, crisis_time: float, mode: str):
    """
    Same matching as your original (scan from end; future allowed; FOLLOW_WINDOW),
    BUT constrain both the robot row i and the matched player row j to the same side:
      - mode='pre' : t_i  < crisis_time AND t_j  < crisis_time
      - mode='post': t_i >= crisis_time AND t_j >= crisis_time
    Also excludes Survey Room rows and resets at boundaries (same as before).
    rows[i] = (t, player_p, robot_p, room_evt_lc, shake_evt_lc_or_None, raw_row)
    """
    assert mode in ("pre", "post")
    followed_distance = 0.0
    followed_time     = 0.0
    prev_pos  = None
    prev_time = None
    inside_survey = False

    def on_side(tval: float) -> bool:
        return (tval < crisis_time) if mode == "pre" else (tval >= crisis_time)

    for i, (t, player_p, robot_p, room_evt, _, _) in enumerate(rows):
        # Select robot window
        if not np.isfinite(t) or not on_side(t):
            continue

        # Survey Room exclusion with reset at boundaries
        if room_evt == "entered survey room":
            inside_survey = True
            prev_pos = prev_time = None
            continue
        elif room_evt == "exited survey room":
            inside_survey = False
            prev_pos = prev_time = None
            continue
        if inside_survey:
            continue

        # Matching: scan from end (future allowed), but j must be on the same side
        matched = None
        for j in range(len(rows) - 1, -1, -1):
            tj, player_j, _, _, _, _ = rows[j]
            if not np.isfinite(tj) or not on_side(tj):
                continue
            dt = t - tj
            if dt > FOLLOW_WINDOW:
                break  # too far in past relative to t
            # future (dt < 0) allowed
            if euclidean_distance(player_j, robot_p) <= PROXIMITY_THRESHOLD:
                matched = (tj, player_j)
                break

        if matched:
            tj, player_j = matched
            if prev_pos is not None:
                followed_distance += euclidean_distance(prev_pos, player_j)
                followed_time     += (t - prev_time)
            prev_pos  = player_j
            prev_time = t

    return followed_distance, followed_time

# --- Main ---
def main():
    # Duplicate workbook
    try:
        shutil.copyfile(SOURCE_XLSX, OUTPUT_XLSX)
    except Exception as e:
        print(f"❌ Failed to copy '{SOURCE_XLSX}' → '{OUTPUT_XLSX}': {e}")
        return

    # Load three sheets (preserve order)
    try:
        xls = pd.ExcelFile(OUTPUT_XLSX, engine="openpyxl")
        sheet_names = xls.sheet_names
        if len(sheet_names) < 3:
            print("❌ Expected at least 3 sheets (overall, pre, post).")
            return
        df_s1 = xls.parse(sheet_names[0])   # overall
        df_s2 = xls.parse(sheet_names[1])   # pre
        df_s3 = xls.parse(sheet_names[2])   # post
    except Exception as e:
        print(f"❌ Failed to read '{OUTPUT_XLSX}': {e}")
        return

    # Ensure target columns exist & headers
    ensure_cols(df_s1, max(S1_COL_DIST, S1_COL_TIME))
    ensure_cols(df_s2, max(S2_COL_DIST, S2_COL_TIME))
    ensure_cols(df_s3, max(S3_COL_DIST, S3_COL_TIME))
    try:
        df_s1.columns.values[S1_COL_DIST] = "Followed Distance (m) — Overall"
        df_s1.columns.values[S1_COL_TIME] = "Followed Time (s) — Overall"
        df_s2.columns.values[S2_COL_DIST] = "Followed Distance (m) — Pre"
        df_s2.columns.values[S2_COL_TIME] = "Followed Time (s) — Pre"
        df_s3.columns.values[S3_COL_DIST] = "Followed Distance (m) — Post"
        df_s3.columns.values[S3_COL_TIME] = "Followed Time (s) — Post"
    except Exception:
        pass

    print("Index | overall(D,T) = pre+post(D,T) | pre(D,T) | post(D,T)")
    print("-"*100)

    # Iterate rows by Sheet 1 order
    for i in range(len(df_s1)):
        raw = df_s1.iat[i, ID_COL]
        idx = idx5(raw)

        csv_path, folder = find_matching_csv(idx)
        if not csv_path:
            df_s1.iat[i, S1_COL_DIST] = np.nan
            df_s1.iat[i, S1_COL_TIME] = np.nan
            df_s2.iat[i, S2_COL_DIST] = np.nan
            df_s2.iat[i, S2_COL_TIME] = np.nan
            df_s3.iat[i, S3_COL_DIST] = np.nan
            df_s3.iat[i, S3_COL_TIME] = np.nan
            print(f"{idx}: (no csv)")
            continue

        # Read CSV
        try:
            with open(csv_path, newline="", encoding="utf-8") as f:
                reader = csv.reader(f)
                header_raw = next(reader, [])
                if not header_raw:
                    raise ValueError("empty header")
                header = [h.strip() if isinstance(h, str) else h for h in header_raw]
                header_lc = [h.lower() if isinstance(h, str) else h for h in header]

                # Required column indices
                time_idx     = find_col_caseins(header, "Time")
                px_idx       = find_col_caseins(header, "PlayerVR.x")
                py_idx       = find_col_caseins(header, "PlayerVR.y")
                pz_idx       = find_col_caseins(header, "PlayerVR.z")
                rx_idx       = find_col_caseins(header, "Robot.x")
                ry_idx       = find_col_caseins(header, "Robot.y")
                rz_idx       = find_col_caseins(header, "Robot.z")
                room_evt_idx = find_col_caseins(header, "roomEvent")
                if min(time_idx, px_idx, py_idx, pz_idx, rx_idx, ry_idx, rz_idx, room_evt_idx) < 0:
                    raise ValueError("missing required columns")

                # Load all rows
                rows_raw = list(reader)
                if not rows_raw:
                    raise ValueError("no data rows")

                # Pack rows with parsed values
                rows = []
                for r in rows_raw:
                    if len(r) <= max(time_idx, px_idx, py_idx, pz_idx, rx_idx, ry_idx, rz_idx, room_evt_idx):
                        continue
                    try:
                        t        = float(r[time_idx])
                        player_p = [float(r[px_idx]), float(r[py_idx]), float(r[pz_idx])]
                        robot_p  = [float(r[rx_idx]), float(r[ry_idx]), float(r[rz_idx])]
                    except ValueError:
                        continue
                    room_evt  = r[room_evt_idx].strip().lower()
                    rows.append((t, player_p, robot_p, room_evt, None, r))
        except Exception as e:
            df_s1.iat[i, S1_COL_DIST] = np.nan
            df_s1.iat[i, S1_COL_TIME] = np.nan
            df_s2.iat[i, S2_COL_DIST] = np.nan
            df_s2.iat[i, S2_COL_TIME] = np.nan
            df_s3.iat[i, S3_COL_DIST] = np.nan
            df_s3.iat[i, S3_COL_TIME] = np.nan
            print(f"{idx}: SKIP (CSV read/parsing error: {e})")
            continue

        if not rows:
            df_s1.iat[i, S1_COL_DIST] = np.nan
            df_s1.iat[i, S1_COL_TIME] = np.nan
            df_s2.iat[i, S2_COL_DIST] = np.nan
            df_s2.iat[i, S2_COL_TIME] = np.nan
            df_s3.iat[i, S3_COL_DIST] = np.nan
            df_s3.iat[i, S3_COL_TIME] = np.nan
            print(f"{idx}: SKIP (no data rows)")
            continue

        # 1) Determine crisis_time
        crisis_time = None
        # shook in robotEvent (if present)
        shake_evt_idx = find_col_caseins(header, "robotEvent")
        if shake_evt_idx != -1:
            for tr, _, _, _, _, rr in rows:
                txt = rr[shake_evt_idx] if len(rr) > shake_evt_idx else ""
                if isinstance(txt, str) and ("shook" in txt.strip().lower()):
                    crisis_time = tr
                    break
        # fallback: any cell with "0.2" -> crisis = t + OFFSET
        if crisis_time is None:
            for tr, _, _, _, _, rr in rows:
                if any(isinstance(cell, str) and ("0.2" in cell.lower()) for cell in rr):
                    crisis_time = tr + OFFSET
                    break

        # 2) Compute stats with side-locked matching
        if crisis_time is None or not np.isfinite(crisis_time):
            # No crisis: define overall as whole-file computation (original method),
            # pre/post left NaN.
            dist_o, time_o = compute_follow_stats_side_locked(rows, float('inf'), mode="pre")  # harmless placeholder
            df_s1.iat[i, S1_COL_DIST] = dist_o
            df_s1.iat[i, S1_COL_TIME] = time_o
            df_s2.iat[i, S2_COL_DIST] = np.nan
            df_s2.iat[i, S2_COL_TIME] = np.nan
            df_s3.iat[i, S3_COL_DIST] = np.nan
            df_s3.iat[i, S3_COL_TIME] = np.nan
            print(f"{idx}: overall=(D={dist_o:.4f}, T={time_o:.4f}) | pre=NA | post=NA (no crisis)")
            continue

        dist_pre,  time_pre  = compute_follow_stats_side_locked(rows, crisis_time, mode="pre")
        dist_post, time_post = compute_follow_stats_side_locked(rows, crisis_time, mode="post")

        # Overall = pre + post (guaranteed equality)
        dist_overall = dist_pre + dist_post
        time_overall = time_pre + time_post

        df_s2.iat[i, S2_COL_DIST] = dist_pre
        df_s2.iat[i, S2_COL_TIME] = time_pre
        df_s3.iat[i, S3_COL_DIST] = dist_post
        df_s3.iat[i, S3_COL_TIME] = time_post
        df_s1.iat[i, S1_COL_DIST] = dist_overall
        df_s1.iat[i, S1_COL_TIME] = time_overall

        print(f"{idx}: overall=(D={dist_overall:.4f}, T={time_overall:.4f}) "
              f"| pre=(D={dist_pre:.4f}, T={time_pre:.4f}) "
              f"| post=(D={dist_post:.4f}, T={time_post:.4f})")

    # Save all three sheets
    try:
        with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl", mode="w") as writer:
            df_s1.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_s2.to_excel(writer, sheet_name=sheet_names[1], index=False)
            df_s3.to_excel(writer, sheet_name=sheet_names[2], index=False)
    except Exception as e:
        print(f"❌ Failed to save '{OUTPUT_XLSX}': {e}")
        return

    print("\nAll done — Followed Distance/Time written to: "
          "Sheet1 cols 23–24 (overall = pre+post), Sheet2 cols 18–19 (pre), Sheet3 cols 18–19 (post).")

if __name__ == "__main__":
    main()
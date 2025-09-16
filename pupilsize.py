#!/usr/bin/env python3
import os
import re
import shutil
import unicodedata
import numpy as np
import pandas as pd

# ========= Config =========
SOURCE_XLSX = "Fire 2 Data.xlsx"
OUTPUT_XLSX = "Fire 2 Data Proceed.xlsx"

# Search only these folders (in order)
SEARCH_FOLDERS = [
    "shook",
    "noshookmodified",
    os.path.join("noshookmodified", "baseline"),
    os.path.join("noshookmodified", "baseline"),  # intentional duplicate per request
]

# Sheet positions: 0=overview (contains indices & crisis times), 1=pre, 2=post
SHEET_IDX_PRE  = 1
SHEET_IDX_POST = 2

# Crisis time is in the 4th Excel column (1-based) -> 0-based index 3
CRISIS_COL_0BASED = 3

# Column targets (1-based → we convert to 0-based when writing)
# Sheet 2 (pre):
PRE_5S_L_COLS   = [20, 21, 22, 23]  # mean, SD, max, min
PRE_5S_R_COLS   = [24, 25, 26, 27]
PRE_FULL_L_COLS = [28, 29, 30, 31]
PRE_FULL_R_COLS = [32, 33, 34, 35]
# Sheet 3 (post):
POST_5S_L_COLS   = [20, 21, 22, 23]
POST_5S_R_COLS   = [24, 25, 26, 27]
POST_FULL_L_COLS = [28, 29, 30, 31]
POST_FULL_R_COLS = [32, 33, 34, 35]

# ========= Helpers =========
def ensure_width(df: pd.DataFrame, upto_1based: int) -> pd.DataFrame:
    """Ensure DataFrame has at least `upto_1based` columns (Excel-style index)."""
    upto_0 = upto_1based - 1
    while df.shape[1] <= upto_0:
        df[f"Extra_{df.shape[1]+1}"] = np.nan
    return df

def normalize_header_token(s: str) -> str:
    """Lowercase + remove spaces/underscores/dots/hyphens for robust header matching."""
    return re.sub(r"[ _.\-]+", "", str(s).strip().lower())

def find_pupil_cols(header) -> tuple[int,int]:
    """
    Find columns for left/right pupil by relaxed matching containing 'leftpupil'/'rightpupil'.
    Returns (left_idx, right_idx) or (-1, -1) if not found.
    """
    tokens = [normalize_header_token(h) for h in header]
    left = right = -1
    for i, tok in enumerate(tokens):
        if "leftpupil" in tok and left == -1:
            left = i
        if "rightpupil" in tok and right == -1:
            right = i
    return left, right

def first5(val) -> str:
    """Take the first 5 characters of the index cell."""
    return str(val).strip()[:5]

def find_csv_for_index(idx5: str):
    for folder in SEARCH_FOLDERS:
        if not os.path.isdir(folder):
            continue
        for name in os.listdir(folder):
            if name.lower().endswith(".csv") and name.startswith(idx5):
                return os.path.join(folder, name), folder
    return None, None

def compute_stats_and_n(values: list[float]) -> tuple[tuple[float,float,float,float], int, dict]:
    """
    Return ((mean, SD, max, min), n_used, diag).
    - Drop all -1 values.
    - SD is sample SD (ddof=1); requires ≥2 values else NaN.
    - min is computed over values >= 0 (if none, NaN).
    diag includes diagnostic counts & reason flags.
    """
    total_in_window = len(values)
    dropped_neg1 = sum(1 for v in values if v == -1)
    vals = [v for v in values if v != -1]
    n_used = len(vals)

    diag = {
        "total_in_window": total_in_window,
        "dropped_-1": dropped_neg1,
        "used_after_drop": n_used,
        "sd_nan": False,
        "min_nan": False,
    }

    if n_used == 0:
        return (np.nan, np.nan, np.nan, np.nan), 0, diag

    mean_v = float(np.mean(vals))
    sd_v   = float(np.std(vals, ddof=1)) if n_used > 1 else float('nan')
    if not np.isfinite(sd_v):
        diag["sd_nan"] = True

    max_v  = float(np.max(vals))
    nonneg = [v for v in vals if v >= 0]
    min_v  = float(np.min(nonneg)) if nonneg else float('nan')
    if not np.isfinite(min_v):
        diag["min_nan"] = True

    return (mean_v, sd_v, max_v, min_v), n_used, diag

def extract_window_stats(times: np.ndarray,
                         left: list[str], right: list[str],
                         t_start: float, t_end: float,
                         include_start: bool, include_end: bool):
    """
    Collect left/right pupil values where time is in the window (t_start, t_end)
    with boundary inclusivity configured. Returns:
      (L_stats, L_n, L_diag), (R_stats, R_n, R_diag)
      where stats = (mean, SD, max, min).
    """
    if not (np.isfinite(times).any()):
        empty = ( (np.nan, np.nan, np.nan, np.nan), 0, {"total_in_window":0,"dropped_-1":0,"used_after_drop":0,"sd_nan":False,"min_nan":False} )
        return empty, empty

    lvals, rvals = [], []
    n = len(times)
    for i in range(n):
        ti = times[i]
        if not np.isfinite(ti):
            continue
        if (ti > t_start or (include_start and ti == t_start)) and \
           (ti < t_end   or (include_end   and ti == t_end)):
            # parse floats; keep -1 (we drop later)
            try:
                lv = float(left[i]) if left[i] != "" else np.nan
            except Exception:
                lv = np.nan
            try:
                rv = float(right[i]) if right[i] != "" else np.nan
            except Exception:
                rv = np.nan
            if np.isfinite(lv): lvals.append(lv)
            if np.isfinite(rv): rvals.append(rv)

    L_stats, L_n, L_diag = compute_stats_and_n(lvals)
    R_stats, R_n, R_diag = compute_stats_and_n(rvals)
    return (L_stats, L_n, L_diag), (R_stats, R_n, R_diag)

# ========= Main =========
def main():
    # Duplicate workbook
    try:
        shutil.copyfile(SOURCE_XLSX, OUTPUT_XLSX)
    except Exception as e:
        print(f"❌ Failed to copy '{SOURCE_XLSX}' → '{OUTPUT_XLSX}': {e}")
        return

    # Load all sheets
    try:
        xls = pd.ExcelFile(OUTPUT_XLSX, engine="openpyxl")
        sheet_names = xls.sheet_names
        if len(sheet_names) < 3:
            print(f"❌ Expected at least 3 sheets; found {len(sheet_names)}.")
            return
        df_over = xls.parse(sheet_names[0])  # indices + crisis times
        df_pre  = xls.parse(sheet_names[SHEET_IDX_PRE])
        df_post = xls.parse(sheet_names[SHEET_IDX_POST])
    except Exception as e:
        print(f"❌ Failed to read '{OUTPUT_XLSX}': {e}")
        return

    # Ensure destination widths (up to col 35 on both pre/post)
    for cols in [PRE_5S_R_COLS, PRE_FULL_R_COLS, POST_5S_R_COLS, POST_FULL_R_COLS]:
        far = max(cols)
        df_pre  = ensure_width(df_pre,  far)
        df_post = ensure_width(df_post, far)

    # Summary counters
    summary = {
        "processed": 0,
        "skip_csv_or_crisis": 0,
        "csv_read_error": 0,
        "empty_csv": 0,
        "no_time_col": 0,
        "no_pupil_cols": 0,
        "window_empty": {
            "pre5_L": 0, "pre5_R": 0, "preFull_L": 0, "preFull_R": 0,
            "post5_L": 0, "post5_R": 0, "postFull_L": 0, "postFull_R": 0,
        }
    }

    # Iterate row-by-row
    rows = len(df_over)
    for i in range(rows):
        idx5 = first5(df_over.iat[i, 0])  # first 5 chars of index cell
        # Crisis time from the 4th column of sheet 1
        try:
            crisis_time = float(df_over.iat[i, CRISIS_COL_0BASED])
        except Exception:
            crisis_time = np.nan

        csv_path, folder = find_csv_for_index(idx5)
        if not csv_path or not np.isfinite(crisis_time):
            summary["skip_csv_or_crisis"] += 1
            # write NaNs for all 8 blocks on both sheets
            for cols in [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS]:
                for c in cols: df_pre.iat[i, c-1] = np.nan
            for cols in [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS]:
                for c in cols: df_post.iat[i, c-1] = np.nan
            print(f"{idx5}: SKIP — {'no CSV' if not csv_path else 'crisis_time NaN'}")
            continue

        # Load CSV (lenient)
        try:
            dfr = pd.read_csv(csv_path, engine="python", on_bad_lines="skip", dtype=str)
        except Exception as e:
            summary["csv_read_error"] += 1
            for cols in [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS]:
                for c in cols: df_pre.iat[i, c-1] = np.nan
            for cols in [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS]:
                for c in cols: df_post.iat[i, c-1] = np.nan
            print(f"{idx5}: SKIP — CSV read error: {e}")
            continue

        if dfr.shape[0] == 0:
            summary["empty_csv"] += 1
            for cols in [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS]:
                for c in cols: df_pre.iat[i, c-1] = np.nan
            for cols in [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS]:
                for c in cols: df_post.iat[i, c-1] = np.nan
            print(f"{idx5}: SKIP — empty CSV")
            continue

        # Find time + pupil columns
        header = list(dfr.columns)
        time_col = None
        if "Time" in header:
            time_col = "Time"
        else:
            for h in header:
                if normalize_header_token(h) == "time":
                    time_col = h; break
        if time_col is None:
            summary["no_time_col"] += 1
            for cols in [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS]:
                for c in cols: df_pre.iat[i, c-1] = np.nan
            for cols in [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS]:
                for c in cols: df_post.iat[i, c-1] = np.nan
            print(f"{idx5}: SKIP — Time column not found")
            continue

        left_idx, right_idx = find_pupil_cols(header)
        if left_idx == -1 or right_idx == -1:
            summary["no_pupil_cols"] += 1
            for cols in [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS]:
                for c in cols: df_pre.iat[i, c-1] = np.nan
            for cols in [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS]:
                for c in cols: df_post.iat[i, c-1] = np.nan
            print(f"{idx5}: SKIP — pupil columns not found")
            continue

        times = pd.to_numeric(dfr[time_col], errors="coerce").to_numpy()
        left_vals  = dfr.iloc[:, left_idx].astype(str).tolist()
        right_vals = dfr.iloc[:, right_idx].astype(str).tolist()

        # ---- Windows (pre excludes crisis point; post includes) ----
        # Pre 5s: [crisis_time - 5, crisis_time)
        (pre5_L_stats, pre5_L_n, pre5_L_diag), (pre5_R_stats, pre5_R_n, pre5_R_diag) = extract_window_stats(
            times, left_vals, right_vals,
            t_start=crisis_time-5.0, t_end=crisis_time, include_start=True, include_end=False
        )
        # Full pre: (-inf, crisis_time)
        (preFull_L_stats, preFull_L_n, preFull_L_diag), (preFull_R_stats, preFull_R_n, preFull_R_diag) = extract_window_stats(
            times, left_vals, right_vals,
            t_start=-np.inf, t_end=crisis_time, include_start=False, include_end=False
        )
        # Post 5s: [crisis_time, crisis_time+5]
        (post5_L_stats, post5_L_n, post5_L_diag), (post5_R_stats, post5_R_n, post5_R_diag) = extract_window_stats(
            times, left_vals, right_vals,
            t_start=crisis_time, t_end=crisis_time+5.0, include_start=True, include_end=True
        )
        # Full post: [crisis_time, +inf)
        (postFull_L_stats, postFull_L_n, postFull_L_diag), (postFull_R_stats, postFull_R_n, postFull_R_diag) = extract_window_stats(
            times, left_vals, right_vals,
            t_start=crisis_time, t_end=np.inf, include_start=True, include_end=False
        )

        # ---- Per-index diagnostics for empty windows ----
        empty_flags = []
        def note_empty(tag, n): 
            if n == 0:
                summary["window_empty"][tag] += 1
                empty_flags.append(tag)

        note_empty("pre5_L",     pre5_L_n)
        note_empty("pre5_R",     pre5_R_n)
        note_empty("preFull_L",  preFull_L_n)
        note_empty("preFull_R",  preFull_R_n)
        note_empty("post5_L",    post5_L_n)
        note_empty("post5_R",    post5_R_n)
        note_empty("postFull_L", postFull_L_n)
        note_empty("postFull_R", postFull_R_n)

        if empty_flags:
            print(f"{idx5}: WARNING — empty windows: {', '.join(empty_flags)}")

        # ---- Extra per-window NaN reasons (only when any NaN appears) ----
        def explain_nan(label, stats, diag):
            mean_v, sd_v, max_v, min_v = stats
            if all(np.isfinite(x) for x in stats):
                return
            reasons = []
            if diag["used_after_drop"] == 0:
                reasons.append("no usable values in window (empty after -1 drop)")
            else:
                if not np.isfinite(sd_v) and diag["sd_nan"]:
                    reasons.append("SD NaN (only one usable value)")
                if not np.isfinite(min_v) and diag["min_nan"]:
                    reasons.append("min NaN (no values >= 0)")
            print(f"  · {label}: total={diag['total_in_window']}, -1_dropped={diag['dropped_-1']}, used={diag['used_after_drop']} -> {'; '.join(reasons) or 'NaN present'}")

        print(f"{idx5}: diagnostics:")
        explain_nan("pre5  L", pre5_L_stats,     pre5_L_diag)
        explain_nan("pre5  R", pre5_R_stats,     pre5_R_diag)
        explain_nan("preFull L", preFull_L_stats, preFull_L_diag)
        explain_nan("preFull R", preFull_R_stats, preFull_R_diag)
        explain_nan("post5 L", post5_L_stats,    post5_L_diag)
        explain_nan("post5 R", post5_R_stats,    post5_R_diag)
        explain_nan("postFull L", postFull_L_stats, postFull_L_diag)
        explain_nan("postFull R", postFull_R_stats, postFull_R_diag)

        # ---- Write to sheets ----
        # Pre (sheet 2)
        for cols, stats in zip(
            [PRE_5S_L_COLS, PRE_5S_R_COLS, PRE_FULL_L_COLS, PRE_FULL_R_COLS],
            [pre5_L_stats,   pre5_R_stats,   preFull_L_stats,  preFull_R_stats]
        ):
            for c, val in zip(cols, stats):
                df_pre.iat[i, c-1] = val

        # Post (sheet 3)
        for cols, stats in zip(
            [POST_5S_L_COLS, POST_5S_R_COLS, POST_FULL_L_COLS, POST_FULL_R_COLS],
            [post5_L_stats,   post5_R_stats,   postFull_L_stats,  postFull_R_stats]
        ):
            for c, val in zip(cols, stats):
                df_post.iat[i, c-1] = val

        summary["processed"] += 1
        print(f"{idx5}: OK — pre5(nL={pre5_L_n}, nR={pre5_R_n}), preFull(nL={preFull_L_n}, nR={preFull_R_n}), "
              f"post5(nL={post5_L_n}, nR={post5_R_n}), postFull(nL={postFull_L_n}, nR={postFull_R_n})")

    # Save back all sheets
    try:
        with pd.ExcelWriter(OUTPUT_XLSX, engine="openpyxl", mode="w") as writer:
            df_over.to_excel(writer, sheet_name=sheet_names[0], index=False)
            df_pre.to_excel(writer,  sheet_name=sheet_names[SHEET_IDX_PRE],  index=False)
            df_post.to_excel(writer, sheet_name=sheet_names[SHEET_IDX_POST], index=False)
        print(f"\n✅ Saved results to '{OUTPUT_XLSX}'.")
    except Exception as e:
        print(f"❌ Failed to write '{OUTPUT_XLSX}': {e}")
        return

    # ---- Summary ----
    print("\n===== SUMMARY =====")
    print(f"Processed OK            : {summary['processed']}")
    print(f"Skipped (no CSV/crisis) : {summary['skip_csv_or_crisis']}")
    print(f"CSV read errors         : {summary['csv_read_error']}")
    print(f"Empty CSV               : {summary['empty_csv']}")
    print(f"Missing Time column     : {summary['no_time_col']}")
    print(f"Missing pupil columns   : {summary['no_pupil_cols']}")
    print("\nWindows with no usable samples (after -1 drop):")
    for k, v in summary["window_empty"].items():
        print(f"  {k:12s}: {v}")

if __name__ == "__main__":
    main()
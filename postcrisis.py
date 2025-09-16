import os
import pandas as pd
import shutil
import csv
import numpy as np

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
pre_crisis_col = 4  # 5th column
post_crisis_col = 5 # 6th column

shutil.copyfile(source_excel, output_excel)
df = pd.read_excel(output_excel, engine='openpyxl')

# --- Ensure at least 6 columns, and set Pre- and Post-crisis Interval headers ---
while df.shape[1] < 6:
    df[f"Extra_{df.shape[1]+1}"] = np.nan
df.iloc[:, pre_crisis_col] = np.nan
df.iloc[:, post_crisis_col] = np.nan
df.columns.values[pre_crisis_col] = "Pre-crisis Interval"
df.columns.values[post_crisis_col] = "Post-crisis Interval"

not_found_csv = []
not_found_column = []
not_found_keyword = []
other_errors = []

def find_matching_csv(index):
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for filename in os.listdir(folder):
            if filename.endswith(".csv") and filename[:5] == index:
                return os.path.join(folder, filename), folder
    return None, None

def find_robot_event_col(header_row):
    for idx, col in enumerate(header_row):
        if "robotevent" in col.strip().lower():
            return idx
    return -1

def get_crisis_and_row_times(filepath, folder_type):
    try:
        with open(filepath, newline='', encoding='utf-8') as csvfile:
            reader = list(csv.reader(csvfile))
            if not reader:
                return None, None, None, "no_header"
            header = reader[0]
            event_col = find_robot_event_col([col.strip() for col in header])
            if event_col == -1:
                return None, None, None, "no_column"
            data_rows = reader[1:]
            crisis_time = None
            first_data_time = None
            last_data_time = None
            for i, row in enumerate(data_rows):
                if len(row) <= event_col or not row or row[0].strip() == "":
                    continue
                try:
                    time_val = float(row[0])
                except Exception:
                    continue
                if first_data_time is None and i == 0:
                    first_data_time = time_val
                last_data_time = time_val  # will be overwritten until last valid row
                event_val = row[event_col]
                if crisis_time is None:
                    if folder_type.startswith("shook") and "shook" in event_val:
                        crisis_time = time_val
                    elif folder_type.startswith("noshook") and "0.2 seconds" in event_val:
                        crisis_time = round(time_val + 0.229, 6)
            if crisis_time is None:
                return None, first_data_time, last_data_time, "no_keyword"
            return crisis_time, first_data_time, last_data_time, None
    except Exception as e:
        return None, None, None, "other"

for idx, row in df.iterrows():
    raw_id = row.iloc[id_col_excel]
    if isinstance(raw_id, float) and raw_id.is_integer():
        index_str = str(int(raw_id)).zfill(5)
    else:
        index_str = str(raw_id).zfill(5)
    csv_path, found_folder = find_matching_csv(index_str)
    folder_report = found_folder if found_folder is not None else "not found"
    if not csv_path or not found_folder:
        df.iat[idx, pre_crisis_col] = np.nan
        df.iat[idx, post_crisis_col] = np.nan
        print(f"{index_str}: crisis_time=None, first_data_time=None, last_data_time=None")
        not_found_csv.append((index_str, folder_report))
        continue

    crisis_time, first_data_time, last_data_time, error_type = get_crisis_and_row_times(csv_path, found_folder)
    print(f"{index_str}: crisis_time={crisis_time}, first_data_time={first_data_time}, last_data_time={last_data_time}")
    if crisis_time is not None and first_data_time is not None and last_data_time is not None:
        df.iat[idx, pre_crisis_col] = crisis_time - first_data_time
        df.iat[idx, post_crisis_col] = last_data_time - crisis_time
    else:
        df.iat[idx, pre_crisis_col] = np.nan
        df.iat[idx, post_crisis_col] = np.nan
        if error_type == "no_column":
            not_found_column.append((index_str, folder_report))
        elif error_type == "no_keyword":
            not_found_keyword.append((index_str, folder_report))
        else:
            other_errors.append((index_str, folder_report))

def print_issue_list(issue_list, description):
    if issue_list:
        print(f"\n{description} ({len(issue_list)}):")
        for index, folder in issue_list:
            print(f"{index}  {folder}")

df.to_excel(output_excel, index=False, engine='openpyxl')
print_issue_list(not_found_csv, "IDs with NO matching CSV file in any folder")
print_issue_list(not_found_column, "IDs where 'robotEvent' column NOT FOUND in CSV")
print_issue_list(not_found_keyword, "IDs where keyword was NOT FOUND in 'robotEvent' column")
print_issue_list(other_errors, "IDs with OTHER errors (possibly corrupted CSV)")

if not (not_found_csv or not_found_column or not_found_keyword or other_errors):
    print("All indices processed successfully!")
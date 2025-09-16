import os
import csv
import numpy as np

survey_dir = "survey"
target_event = "robot entered survey room"

robot_x, robot_y, robot_z = [], [], []
positions_by_index = {}  # index -> (x, y, z)

for filename in os.listdir(survey_dir):
    if not filename.lower().endswith(".csv"):
        continue

    file_path = os.path.join(survey_dir, filename)
    index = filename[:5]  # first 5 characters of filename

    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.reader(file)
        raw_header = next(reader)
        header = [h.strip().lower() for h in raw_header]

        try:
            ix = header.index("robot.x")
            iy = header.index("robot.y")
            iz = header.index("robot.z")
            ie = header.index("roomevent")
        except ValueError:
            print(f"Skipping {filename}: missing required column.")
            continue

        for row in reader:
            if len(row) <= max(ix, iy, iz, ie):
                continue
            if row[ie].strip().lower() == target_event:
                try:
                    x = float(row[ix])
                    y = float(row[iy])
                    z = float(row[iz])
                    robot_x.append(x)
                    robot_y.append(y)
                    robot_z.append(z)
                    positions_by_index[index] = (x, y, z)
                except ValueError:
                    print(f"Invalid value in {filename}")
                break

# Output per-file positions
print("\n=== Robot Positions per File ===")
for idx, (x, y, z) in positions_by_index.items():
    print(f"Index {idx} → x = {x:.4f}, y = {y:.4f}, z = {z:.4f}")

# Final stats
x_arr = np.array(robot_x)
y_arr = np.array(robot_y)
z_arr = np.array(robot_z)

print("\n=== Summary Statistics ===")
if len(x_arr) > 0:
    print("Robot.x → Mean: {:.4f}, Variance: {:.6f}".format(np.mean(x_arr), np.var(x_arr)))
    print("Robot.y → Mean: {:.4f}, Variance: {:.6f}".format(np.mean(y_arr), np.var(y_arr)))
    print("Robot.z → Mean: {:.4f}, Variance: {:.6f}".format(np.mean(z_arr), np.var(z_arr)))
else:
    print("No valid data found.")
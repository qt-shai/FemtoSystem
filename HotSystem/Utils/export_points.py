import csv
import os

def export_points(csv_file=None):
    """
    Reads X,Y points from a CSV, scales by 1e-6, writes them as:
    index,x,y  (3 decimal places)
    """
    # Default file
    if csv_file is None:
        csv_file = r"Q:/QT-Quantum_Optic_Lab/expData/scan/SystemType.FEMTO/ELSC_SIL/2025_7_8_18_9_53_SCAN_pulses.csv"

    points = []

    # === Read CSV ===
    with open(csv_file, newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                try:
                    x = round(float(row[0]) * 1e-6, 2)
                    y = round(float(row[1]) * 1e-6, 2)
                    z = round(float(row[2]) * 1e-6, 3)
                    points.append((x, y, z))
                except ValueError:
                    continue  # Skip bad rows

    # === Write TXT ===
    folder = os.path.dirname(csv_file)
    base_name = os.path.splitext(os.path.basename(csv_file))[0]
    txt_file = os.path.join(folder, f"{base_name}_points.txt")

    with open(txt_file, "w") as f:
        for idx, (x, y, z) in enumerate(points, 1):
            f.write(f"{idx},{x:.2f},{y:.2f},{z:.2f}\n")

    print(f"✅ Saved {len(points)} scaled points to: {txt_file}")
    return txt_file

if __name__ == "__main__":
    export_points()

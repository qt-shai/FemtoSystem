import os

from Utils import open_file_dialog
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

def main():
    # Prompt user to select a folder containing CSV files
    folder_path = open_file_dialog(
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        select_folder=True
    )
    if not folder_path or not os.path.isdir(folder_path):
        print("No folder selected or folder does not exist. Exiting.")
        return

    # Gather all CSV files in the selected folder
    csv_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith('.csv')]
    if not csv_files:
        print(f"No CSV files found in folder: {folder_path}")
        return

    plt.figure(figsize=(10, 6))

    for fp in csv_files:
        base = os.path.basename(fp)
        name, _ = os.path.splitext(base)
        # Use the part after the last space or underscore for legend label
        if '_' in name:
            label = name.split('_')[-1]
        elif ' ' in name:
            label = name.split(' ')[-1]
        else:
            label = name

        # Load data: assume two columns, try skipping header
        try:
            data = np.genfromtxt(fp, delimiter=',', skip_header=1)
        except Exception:
            data = np.genfromtxt(fp, delimiter=',')

        if data is None or data.size == 0:
            print(f"No data in file: {fp}")
            continue

        data = np.atleast_2d(data)
        data = data[data[:, 0].argsort()]

        x = data[:, 0]
        y = data[:, 1]
        plt.plot(x, y, label=label)

    fig = plt.gcf()  # grab current figure
    plt.xlabel('Wavelength [nm]')
    plt.ylabel('Intensity')
    plt.title('Spectra Comparison')
    plt.legend(title='File Labels')
    plt.grid(True)
    plt.tight_layout()
    plt.show()

    # ─── auto-save the figure as PNG ───

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.dirname(folder_path)  # save alongside your data
    out_name = f"spectra_{timestamp}.png"
    out_path = os.path.join(out_dir, out_name)
    fig.savefig(out_path, dpi=300, bbox_inches='tight')
    print(f"Saved combined spectra figure to: {out_path}")

if __name__ == '__main__':
    main()

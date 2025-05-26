import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from Utils.Common import open_file_dialog  # Assumed to exist in your codebase

def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False):
    # === File selection ===
    if not filepath:
        filepath = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if not filepath or not os.path.isfile(filepath):
            print("❌ File not selected or not found.")
            return

    df = pd.read_csv(filepath, skiprows=1)
    x = df.iloc[:, 4].to_numpy()
    y = df.iloc[:, 5].to_numpy()
    z = df.iloc[:, 6].to_numpy()
    I = df.iloc[:, 3].to_numpy()

    # === Step estimation for Nx, Ny ===
    dx = np.unique(np.diff(x))
    dy = np.unique(np.diff(y))
    dz = np.unique(np.diff(z))

    dx = dx[dx > 0]
    dy = dy[dy > 0]
    dz = dz[dz > 0]

    step_x = dx[0] if len(dx) else 1
    step_y = dy[0] if len(dy) else 1
    step_z = dz[0] if len(dz) else 1

    Nx = int(round((x.max() - x.min()) / step_x)) + 1
    Ny = int(round((y.max() - y.min()) / step_y)) + 1
    Nz = len(I) // (Nx * Ny)
    total_points = Nx * Ny * Nz
    I = I[:total_points]

    print(f"Nx={Nx}, Ny={Ny}, Nz={Nz}, Trimmed total points={len(I)}")

    # === Reshape and rescale ===
    I_ = I.reshape((Nz, Ny, Nx))
    X_ = np.linspace(x.min(), x.max(), Nx) * 1e-6
    Y_ = np.linspace(y.min(), y.max(), Ny) * 1e-6
    Z_ = np.linspace(z.min(), z.max(), Nz) * 1e-6

    if log_scale:
        I_ = np.log10(I_ + np.finfo(float).eps)

    if minI is None:
        minI = np.min(I_)
    if maxI is None:
        maxI = np.max(I_)

    # === Plot all XY slices ===
    # === Optionally ask user to enter maxI ===
    # if maxI is None:
    #     try:
    #         maxI_input = input(f"Enter maxI (or press Enter for auto: {np.max(I_):.2f}): ")
    #         if maxI_input.strip():
    #             maxI = float(maxI_input)
    #         else:
    #             maxI = np.max(I_)
    #     except Exception as e:
    #         print(f"⚠️ Failed to parse maxI. Using auto value. ({e})")
    #         maxI = np.max(I_)

    if Nz <= 3:
        rows, cols = 3, 1
    else:
        rows = int(np.ceil(np.sqrt(Nz)))
        cols = int(np.ceil(Nz / rows))

    fig, axes = plt.subplots(rows, cols, figsize=(16, 9), constrained_layout=True)

    axes = axes.flatten()

    for k in range(Nz):
        ax = axes[k]
        im = ax.imshow(I_[k, :, :], extent=[X_[0], X_[-1], Y_[0], Y_[-1]],
                       origin='lower', aspect='equal', vmin=minI, vmax=maxI, cmap='rainbow')
        ax.set_title(f"XY @ Z = {Z_[k]:.2f} µm (slice {k+1})")
        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")

    # Turn off unused subplots
    for i in range(Nz, len(axes)):
        axes[i].axis("off")

    filename = os.path.basename(filepath)
    fig.suptitle(f"All XY Sections of {filename}", fontsize=16)

    fig.colorbar(im, ax=axes.tolist(), label="kCounts/s", shrink=0.8)
    plt.show()

    folder = os.path.dirname(filepath)
    fig.savefig(os.path.join(folder, os.path.splitext(filename)[0] + ".png"), dpi=300)

# === Example usage ===
if __name__ == "__main__":
    display_all_z_slices()

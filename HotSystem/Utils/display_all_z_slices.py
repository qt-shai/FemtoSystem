import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from Utils.Common import open_file_dialog  # Assumed to exist in your codebase

def display_selected_z_slices(filepath=None, minI=None, maxI=None, log_scale=False, slices=None, pixel_limit = True):
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

    # === Step estimation for Nx, Ny, Nz ===
    dx = np.unique(np.diff(x)); dx = dx[dx>0]
    dy = np.unique(np.diff(y)); dy = dy[dy>0]
    dz = np.unique(np.diff(z)); dz = dz[dz>0]
    step_x = dx[0] if dx.size else 1
    step_y = dy[0] if dy.size else 1
    step_z = dz[0] if dz.size else 1

    Nx = int(round((x.max() - x.min()) / step_x)) + 1
    Ny = int(round((y.max() - y.min()) / step_y)) + 1
    if step_z == 1:
        Nz = 1
    else:
        Nz = len(I) // (Nx * Ny)
    I = I[:Nx * Ny * Nz]

    print(f"Nx={Nx}, Ny={Ny}, Nz={Nz}, Trimmed total points={len(I)}")

    # === Reshape and axes ===
    expected_pts = Nx * Ny * Nz
    if Nz == 1 and I.size != expected_pts:
        # One Z-slice but len(I) != Nx*Ny → pivot into a 2D grid with NaNs
        pivot = (
            pd.DataFrame({'x': x, 'y': y, 'I': I})
            .pivot(index='y', columns='x', values='I')
        )
        # enforce sorted coords
        pivot = pivot.reindex(index=sorted(pivot.index), columns=sorted(pivot.columns))
        grid2d = pivot.to_numpy()
        # pad/truncate rows or cols if needed
        grid2d = grid2d[:Ny, :Nx]
        # convert to a 3D array of shape (1, Ny, Nx)
        I_ = grid2d[np.newaxis, :, :]
    else:
        # trim any excess so reshape is exact
        I = I[:expected_pts]
        I_ = I.reshape((Nz, Ny, Nx))
    X_ = np.linspace(x.min(), x.max(), Nx) * 1e-6
    Y_ = np.linspace(y.min(), y.max(), Ny) * 1e-6
    Z_ = np.linspace(z.min(), z.max(), Nz) * 1e-6

    if log_scale:
        I_ = np.log10(I_ + np.finfo(float).eps)

    if minI is None:
        minI = I_.min()
    if maxI is None:
        maxI = I_.max()

    # === Ask which slices to plot ===
    # if slices is None:
    #     raw = input(f"Enter slice numbers between 1 and {Nz}, separated by commas: ")
    #     try:
    #         # convert to 0-based indices
    #         slices = [int(tok.strip()) - 1 for tok in raw.split(",")]
    #     except ValueError:
    #         print("⚠️  Invalid input. Showing all slices.")
    #         slices = list(range(Nz))
    # else:
    #     # assume user passed 1-based slice numbers
    #     slices = [s - 1 for s in slices]

    # filter out-of-bounds
    #slices = list(range(17,27))
    slices = list(range(Nz))
    slices = [s for s in slices if 0 <= s < Nz]
    if not slices:
        print("⚠️  No valid slices selected. Aborting.")
        return

    # === Create subplots ===
    n = len(slices)
    cols = min(n, 4)
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(4*cols, 4*rows), constrained_layout=True)
    axes = np.atleast_1d(axes).ravel()

    for ax, idx in zip(axes, slices):
        if pixel_limit:
            # max_pixel_number = 80
            max_pixel_number = int(Ny * 0.8)
            data = I_[idx, :max_pixel_number, :]
            extent = [X_[0], X_[-1], Y_[0], Y_[max_pixel_number-1]]
        else:
            data = I_[idx]
            extent = [X_[0], X_[-1], Y_[0], Y_[-1]]
        im = ax.imshow(
            data,
            extent=extent,
            origin='lower',
            aspect='equal',
            vmin=minI,
            vmax=maxI
        )
        im.set_clim(0, 80)
        ax.set_title(f"XY @ Z={Z_[idx]:.2f} µm (slice {idx+1})")
        ax.set_xlabel("X (µm)")
        ax.set_ylabel("Y (µm)")

    # turn off any extra axes
    for ax in axes[n:]:
        ax.axis("off")

    # global title + colorbar
    filename = os.path.basename(filepath)
    fig.suptitle(f"Selected XY Sections of {filename}", fontsize=16)
    fig.colorbar(im, ax=axes[:n].tolist(), label="kCounts/s", shrink=0.8)

    plt.show()

    # save to PNG next to CSV
    folder = os.path.dirname(filepath)
    stem = os.path.splitext(filename)[0]
    outpath = os.path.join(folder, f"{stem}_slices.png")
    # fig.savefig(outpath, dpi=300)
    # print(f"Saved figure to {outpath}")

# === Example usage ===
if __name__ == "__main__":
    # To be prompted:
    display_selected_z_slices()

    # Or pass slices=[1,3,5] to plot slices 1, 3 and 5 directly:
    # display_selected_z_slices(slices=[1,3,5])

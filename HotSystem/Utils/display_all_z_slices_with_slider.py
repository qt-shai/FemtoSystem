import matplotlib
matplotlib.use('TkAgg')  # Ensure GUI interactivity in PyCharm

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import os

try:
    from Utils.Common import open_file_dialog
except ImportError:
    from tkinter import Tk, filedialog
    def open_file_dialog(filetypes):
        root = Tk()
        root.withdraw()
        return filedialog.askopenfilename(filetypes=filetypes)

def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False):
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

    dx = np.unique(np.diff(x))
    dy = np.unique(np.diff(y))
    dz = np.unique(np.diff(z))
    dx = dx[dx > 0]
    dy = dy[dy > 0]
    dz = dz[dz > 0]

    step_x = dx[0] if len(dx) else 1
    step_y = dy[0] if len(dy) else 1

    Nx = int(round((x.max() - x.min()) / step_x)) + 1
    Ny = int(round((y.max() - y.min()) / step_y)) + 1
    required = Nx * Ny
    Nz = int(np.ceil(len(I) / required))
    expected_size = Nx * Ny * Nz

    # Pad I with zeros if needed
    if len(I) < expected_size:
        print(f"⚠️ Padding data: expected {expected_size}, got {len(I)} — filling with zeros.")
        I = np.pad(I, (0, expected_size - len(I)), mode='constant')

    # Reshape into (Nz, Ny, Nx)
    I_ = I[:expected_size].reshape((Nz, Ny, Nx))

    print(f"len(I) = {len(I)}, expected = {Nx} x {Ny} x {Nz} = {expected_size}")

    X_ = np.linspace(x.min(), x.max(), Nx) * 1e-6
    Y_ = np.linspace(y.min(), y.max(), Ny) * 1e-6
    Z_ = np.linspace(z.min(), z.max(), Nz) * 1e-6

    if log_scale:
        I_ = np.log10(I_ + np.finfo(float).eps)

    if minI is None:
        minI = np.min(I_)
    if maxI is None:
        maxI = np.max(I_)

    plt.ion()
    fig, ax = plt.subplots(figsize=(8, 6))
    plt.subplots_adjust(bottom=0.25)

    slice_idx = 0
    im = ax.imshow(I_[slice_idx], extent=[X_[0], X_[-1], Y_[0], Y_[-1]],
                   origin='lower', aspect='equal', vmin=minI, vmax=maxI)
    ax.set_title(f"XY @ Z = {Z_[slice_idx]:.2f} µm (slice {slice_idx+1})")
    ax.set_xlabel("X (µm)")
    ax.set_ylabel("Y (µm)")
    cbar = fig.colorbar(im, ax=ax, label="kCounts/s")

    # Max I slider (always present)
    ax_max = plt.axes([0.2, 0.10, 0.65, 0.03])
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)

    if Nz > 1:
        # Slice slider only if multiple slices
        ax_slice = plt.axes([0.2, 0.15, 0.65, 0.03])
        slider_slice = Slider(ax_slice, 'Slice', 1, Nz, valinit=1, valstep=1)

        def update(_):
            idx = int(slider_slice.val) - 1
            vmax = slider_max.val
            im.set_data(I_[idx])
            im.set_clim(vmin=minI, vmax=vmax)
            ax.set_title(f"XY @ Z = {Z_[idx]:.2f} µm (slice {idx + 1})")
            fig.canvas.draw_idle()

        slider_slice.on_changed(update)
        slider_max.on_changed(update)

    else:
        # Only update max I
        def update(_):
            vmax = slider_max.val
            im.set_clim(vmin=minI, vmax=vmax)
            ax.set_title(f"XY @ Z = {Z_[0]:.2f} µm (single slice)")
            fig.canvas.draw_idle()

        slider_max.on_changed(update)

    plt.show(block=False)
    try:
        while plt.fignum_exists(fig.number):
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass

# Example usage
if __name__ == "__main__":
    display_all_z_slices()

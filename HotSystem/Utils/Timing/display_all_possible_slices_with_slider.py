import matplotlib
matplotlib.use('TkAgg')  # Ensure interactive GUI in PyCharm

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

def display_orthogonal_slices(filepath=None, minI=None, maxI=None, log_scale=False):
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
    Nz = len(I) // (Nx * Ny)
    I = I[:Nx * Ny * Nz]

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

    # Initial indices
    idx_z = Nz // 2
    idx_y = Ny // 2
    idx_x = Nx // 2

    plt.ion()
    fig, axs = plt.subplots(1, 3, figsize=(16, 5))
    plt.subplots_adjust(bottom=0.25)

    im_xy = axs[0].imshow(I_[idx_z], extent=[X_[0], X_[-1], Y_[0], Y_[-1]],
                          origin='lower', aspect='equal', vmin=minI, vmax=maxI, cmap='rainbow')
    axs[0].set_title(f"XY @ Z = {Z_[idx_z]:.2f} µm")
    axs[0].set_xlabel("X (µm)")
    axs[0].set_ylabel("Y (µm)")

    im_xz = axs[1].imshow(I_[:, idx_y, :], extent=[X_[0], X_[-1], Z_[0], Z_[-1]],
                          origin='lower', aspect='equal', vmin=minI, vmax=maxI, cmap='rainbow')
    axs[1].set_title(f"XZ @ Y = {Y_[idx_y]:.2f} µm")
    axs[1].set_xlabel("X (µm)")
    axs[1].set_ylabel("Z (µm)")

    im_yz = axs[2].imshow(I_[:, :, idx_x], extent=[Y_[0], Y_[-1], Z_[0], Z_[-1]],
                          origin='lower', aspect='equal', vmin=minI, vmax=maxI, cmap='rainbow')
    axs[2].set_title(f"YZ @ X = {X_[idx_x]:.2f} µm")
    axs[2].set_xlabel("Y (µm)")
    axs[2].set_ylabel("Z (µm)")

    fig.colorbar(im_xy, ax=axs.ravel().tolist(), shrink=0.8, label="kCounts/s")

    # Sliders
    ax_z = plt.axes([0.15, 0.15, 0.7, 0.03])
    ax_y = plt.axes([0.15, 0.10, 0.7, 0.03])
    ax_x = plt.axes([0.15, 0.05, 0.7, 0.03])
    ax_max = plt.axes([0.15, 0.00, 0.7, 0.03])

    slider_z = Slider(ax_z, 'Z (XY)', 0, Nz - 1, valinit=idx_z, valstep=1)
    slider_y = Slider(ax_y, 'Y (XZ)', 0, Ny - 1, valinit=idx_y, valstep=1)
    slider_x = Slider(ax_x, 'X (YZ)', 0, Nx - 1, valinit=idx_x, valstep=1)
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)

    def update(val=None):
        idx_z = int(slider_z.val)
        idx_y = int(slider_y.val)
        idx_x = int(slider_x.val)
        vmax = slider_max.val

        im_xy.set_data(I_[idx_z])
        im_xy.set_clim(vmin=minI, vmax=vmax)
        axs[0].set_title(f"XY @ Z = {Z_[idx_z]:.2f} µm")

        im_xz.set_data(I_[:, idx_y, :])
        im_xz.set_clim(vmin=minI, vmax=vmax)
        axs[1].set_title(f"XZ @ Y = {Y_[idx_y]:.2f} µm")

        im_yz.set_data(I_[:, :, idx_x])
        im_yz.set_clim(vmin=minI, vmax=vmax)
        axs[2].set_title(f"YZ @ X = {X_[idx_x]:.2f} µm")

        fig.canvas.draw_idle()

    slider_z.on_changed(update)
    slider_y.on_changed(update)
    slider_x.on_changed(update)
    slider_max.on_changed(update)

    plt.show(block=False)

    try:
        while plt.fignum_exists(fig.number):
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass

# === Run as script ===
if __name__ == "__main__":
    display_orthogonal_slices()

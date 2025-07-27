import json

import matplotlib
matplotlib.use('TkAgg')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import os
import sys

try:
    from Utils.Common import open_file_dialog
except ImportError:
    from tkinter import Tk, filedialog
    def open_file_dialog(filetypes):
        root = Tk(); root.withdraw()
        return filedialog.askopenfilename(filetypes=filetypes)

def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False, data=None):

    if data is not None:
        if isinstance(data, str):
            data = json.loads(data)
        x = np.array(data["x"])
        y = np.array(data["y"])
        z = np.array(data["z"])
        I = np.array(data["I"], dtype=np.float64).flatten()
    else:
        if not filepath:
            from tkinter.filedialog import askopenfilename as open_file_dialog
            filepath = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
            if not filepath or not os.path.isfile(filepath):
                print("❌ File not selected or not found.")
                return

        df = pd.read_csv(filepath, skiprows=1)
        x = df.iloc[:, 4].to_numpy()
        y = df.iloc[:, 5].to_numpy()
        z = df.iloc[:, 6].to_numpy()
        I = df.iloc[:, 3].to_numpy()

    # Grid dimensions
    x_unique = np.unique(x)
    y_unique = np.unique(y)
    z_unique = np.unique(z)
    Nx, Ny, Nz = len(x_unique), len(y_unique), len(z_unique)
    expected = Nx * Ny * Nz

    if len(I) != expected:
        print(f"⚠️ Intensity data length mismatch: {len(I)} vs expected {expected}.")
        if len(I) < expected:
            I = np.pad(I, (0, expected - len(I)), 'constant')
        else:
            I = I[:expected]

    I_ = I.reshape((Nz, Ny, Nx))
    X_ = np.linspace(x.min(), x.max(), Nx) * 1e-6
    Y_ = np.linspace(y.min(), y.max(), Ny) * 1e-6
    Z_ = np.linspace(z.min(), z.max(), Nz) * 1e-6

    if log_scale:
        I_ = np.log10(I_ + np.finfo(float).eps)

    if minI is None: minI = I_.min()
    if maxI is None: maxI = I_.max()

    def safe_extent(v):
        if v[0] == v[-1]:
            delta = 1e-6
            return [v[0] - delta, v[-1] + delta]
        return [v[0], v[-1]]

    extent_xy = safe_extent(X_) + safe_extent(Y_)

    plt.ion()
    if Nz > 1:
        fig, (ax_xy, ax_xz) = plt.subplots(1, 2, figsize=(12, 6))
    else:
        fig, ax_xy = plt.subplots(1, 1, figsize=(6, 6))
        ax_xz = None
    plt.subplots_adjust(bottom=0.30)

    z_idx = 0
    y_idx = Ny // 2

    im_xy = ax_xy.imshow(
        I_[z_idx], extent=extent_xy,
        origin='lower', aspect='equal', vmin=minI, vmax=maxI
    )
    ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
    ax_xy.set_xlabel("X (µm)"); ax_xy.set_ylabel("Y (µm)")

    if Nz > 1:
        extent_xz = safe_extent(X_) + safe_extent(Z_)
        im_xz = ax_xz.imshow(
            I_[:, y_idx, :], extent=extent_xz,
            origin='lower', aspect='auto', vmin=minI, vmax=maxI
        )
        ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
        ax_xz.set_xlabel("X (µm)"); ax_xz.set_ylabel("Z (µm)")
        cbar = fig.colorbar(im_xy, ax=[ax_xy, ax_xz], label="kCounts/s")
    else:
        cbar = fig.colorbar(im_xy, ax=ax_xy, label="kCounts/s")

    # Max I slider
    ax_max = plt.axes([0.15, 0.15, 0.7, 0.03])
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)

    def update_max(val):
        vmin = minI; vmax = slider_max.val
        im_xy.set_clim(vmin, vmax)
        if Nz > 1:
            im_xz.set_clim(vmin, vmax)
        fig.canvas.draw_idle()
    slider_max.on_changed(update_max)

    # Z slider (only if Nz > 1)
    if Nz > 1:
        ax_z = plt.axes([0.15, 0.10, 0.7, 0.03])
        slider_z = Slider(ax_z, 'Z slice', 1, Nz, valinit=1, valstep=1)

        def update_z(val):
            nonlocal z_idx
            z_idx = int(slider_z.val) - 1
            im_xy.set_data(I_[z_idx])
            ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
            fig.canvas.draw_idle()

        slider_z.on_changed(update_z)

    # Y slider only if XZ is shown
    if Nz > 1:
        ax_y = plt.axes([0.15, 0.05, 0.7, 0.03])
        slider_y = Slider(ax_y, 'Y slice', 1, Ny, valinit=y_idx + 1, valstep=1)
        def update_y(val):
            nonlocal y_idx
            y_idx = int(slider_y.val) - 1
            im_xz.set_data(I_[:, y_idx, :])
            ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_y.on_changed(update_y)

    plt.show(block=False)
    try:
        while plt.fignum_exists(fig.number):
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass

if __name__=="__main__":
    path = sys.argv[1] if len(sys.argv)>1 else None
    display_all_z_slices(filepath=path)

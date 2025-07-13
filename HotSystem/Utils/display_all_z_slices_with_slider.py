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

def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False):
    # — load file —
    if not filepath:
        filepath = open_file_dialog([("CSV Files","*.csv"),("All Files","*.*")])
        if not filepath or not os.path.isfile(filepath):
            print("❌ File not selected or not found."); return

    df = pd.read_csv(filepath, skiprows=1)
    x = df.iloc[:,4].to_numpy(); y = df.iloc[:,5].to_numpy()
    z = df.iloc[:,6].to_numpy(); I = df.iloc[:,3].to_numpy()

    # — grid dims —
    dx = np.unique(np.diff(x)); dy = np.unique(np.diff(y))
    dx = dx[dx>0]; dy = dy[dy>0]
    step_x = dx[0] if len(dx) else 1
    step_y = dy[0] if len(dy) else 1

    Nx = int(round((x.max()-x.min())/step_x))+1
    Ny = int(round((y.max()-y.min())/step_y))+1
    required = Nx*Ny
    Nz = int(np.ceil(len(I)/required))
    expected = Nx*Ny*Nz
    if len(I)<expected:
        I = np.pad(I,(0,expected-len(I)),'constant')
    I_ = I[:expected].reshape((Nz,Ny,Nx))

    # — axes in µm —
    X_ = np.linspace(x.min(), x.max(), Nx)*1e-6
    Y_ = np.linspace(y.min(), y.max(), Ny)*1e-6
    Z_ = np.linspace(z.min(), z.max(), Nz)*1e-6

    if log_scale:
        I_ = np.log10(I_+np.finfo(float).eps)

    if minI is None: minI = I_.min()
    if maxI is None: maxI = I_.max()

    # — figure & axes —
    plt.ion()
    fig, (ax_xy, ax_xz) = plt.subplots(1,2, figsize=(12,6))
    plt.subplots_adjust(bottom=0.30)  # leave room for two sliders

    # initial indices
    z_idx = 0
    y_idx = Ny//2

    im_xy = ax_xy.imshow(
        I_[z_idx], extent=[X_[0],X_[-1],Y_[0],Y_[-1]],
        origin='lower', aspect='equal', vmin=minI, vmax=maxI
    )
    ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
    ax_xy.set_xlabel("X (µm)"); ax_xy.set_ylabel("Y (µm)")

    im_xz = ax_xz.imshow(
        I_[:, y_idx, :], extent=[X_[0],X_[-1],Z_[0],Z_[-1]],
        origin='lower', aspect='auto', vmin=minI, vmax=maxI
    )
    ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
    ax_xz.set_xlabel("X (µm)"); ax_xz.set_ylabel("Z (µm)")

    cbar = fig.colorbar(im_xy, ax=[ax_xy,ax_xz], label="kCounts/s")

    # — Max I slider —
    ax_max = plt.axes([0.15, 0.15, 0.7, 0.03])
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)

    def update_max(val):
        vmin = minI; vmax = slider_max.val
        im_xy.set_clim(vmin, vmax)
        im_xz.set_clim(vmin, vmax)
        fig.canvas.draw_idle()
    slider_max.on_changed(update_max)

    # — Z‐slice slider (for XY) —
    ax_z = plt.axes([0.15, 0.10, 0.7, 0.03])
    slider_z = Slider(ax_z, 'Z slice', 1, Nz, valinit=1, valstep=1)
    def update_z(val):
        nonlocal z_idx
        z_idx = int(slider_z.val) - 1
        im_xy.set_data(I_[z_idx])
        ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
        fig.canvas.draw_idle()
    slider_z.on_changed(update_z)

    # — Y‐slice slider (for XZ) —
    ax_y = plt.axes([0.15, 0.05, 0.7, 0.03])
    slider_y = Slider(ax_y, 'Y slice', 1, Ny, valinit=y_idx+1, valstep=1)
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

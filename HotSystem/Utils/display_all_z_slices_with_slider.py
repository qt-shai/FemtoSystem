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
                print("File not selected or not found.")
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
        # print(f"Intensity data length mismatch: {len(I)} vs expected {expected}.")
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
    extent_xz = safe_extent(X_) + safe_extent(Z_)
    extent_yz = safe_extent(Y_) + safe_extent(Z_)

    plt.ion()
    if Nz > 1:
        fig, (ax_xy, ax_xz, ax_yz) = plt.subplots(1, 3, figsize=(18, 6))
    else:
        fig, ax_xy = plt.subplots(1, 1, figsize=(6, 6))
        ax_xz = ax_yz = None

    plt.subplots_adjust(bottom=0.30)

    z_idx = 0
    y_idx = Ny // 2
    x_idx = Nx // 2

    im_xy = ax_xy.imshow(
        I_[z_idx], extent=extent_xy,
        origin='lower', aspect='equal', vmin=minI, vmax=maxI
    )
    ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
    ax_xy.set_xlabel("X (µm)"); ax_xy.set_ylabel("Y (µm)")

    if Nz > 1:
        im_xz = ax_xz.imshow(
            I_[:, y_idx, :], extent=extent_xz,
            origin='lower', aspect='auto', vmin=minI, vmax=maxI
        )
        ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
        ax_xz.set_xlabel("X (µm)"); ax_xz.set_ylabel("Z (µm)")

        im_yz = ax_yz.imshow(I_[:, :, x_idx], extent=extent_yz, origin='lower',
                             aspect='auto', vmin=minI, vmax=maxI)
        ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
        ax_yz.set_xlabel("Y (µm)");
        ax_yz.set_ylabel("Z (µm)")

        cbar = fig.colorbar(im_xy, ax=[ax_xy, ax_xz, ax_yz], label="kCounts/s")
    else:
        cbar = fig.colorbar(im_xy, ax=ax_xy, label="kCounts/s")

    # Max I slider
    ax_max = plt.axes([0.01, 0.06, 0.1, 0.03])
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)
    # put label above, centered
    slider_max.label.set_transform(slider_max.ax.transAxes)
    slider_max.label.set_position((0.5, 1.1))  # (x,y) in axes coords; y>1 is above
    slider_max.label.set_ha('center')
    slider_max.label.set_va('bottom')

    def update_max(val):
        vmin = minI; vmax = slider_max.val
        im_xy.set_clim(vmin, vmax)
        if Nz > 1:
            im_xz.set_clim(vmin, vmax)
            im_yz.set_clim(minI, vmax)
        fig.canvas.draw_idle()

    slider_max.on_changed(update_max)

    # Z slider (only if Nz > 1)
    if Nz > 1:
        ax_z = plt.axes([0.15, 0.15, 0.7, 0.03])
        slider_z = Slider(ax_z, 'Z slice', 1, Nz, valinit=1, valstep=1)

        def update_z(val):
            nonlocal z_idx
            z_idx = int(slider_z.val) - 1
            im_xy.set_data(I_[z_idx])
            ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
            fig.canvas.draw_idle()

        slider_z.on_changed(update_z)

    # X, Y sliders only if XZ is shown
    if Nz > 1:
        ax_y = plt.axes([0.15, 0.1, 0.7, 0.03])
        slider_y = Slider(ax_y, 'Y slice', 1, Ny, valinit=y_idx + 1, valstep=1)
        def update_y(val):
            nonlocal y_idx
            y_idx = int(slider_y.val) - 1
            im_xz.set_data(I_[:, y_idx, :])
            ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
            fig.canvas.draw_idle()

        slider_y.on_changed(update_y)

        # X slice slider
        ax_x = plt.axes([0.15, 0.06, 0.7, 0.03])
        slider_x = Slider(ax_x, 'X slice', 1, Nx, valinit=x_idx + 1, valstep=1)

        def update_x(val):
            nonlocal x_idx
            x_idx = int(slider_x.val) - 1
            im_yz.set_data(I_[:, :, x_idx])
            ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
            fig.canvas.draw_idle()

        slider_x.on_changed(update_x)

    from matplotlib.widgets import RadioButtons

    # 1. Available colormaps
    colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                 'gray', 'hot', 'jet', 'bone', 'cool', 'spring', 'summer', 'autumn', 'winter']

    # 2. Add axes for RadioButtons
    radio_ax = plt.axes([0.01, 0.6, 0.03, 0.4], facecolor='lightgray')  # x, y, width, height
    radio = RadioButtons(radio_ax, colormaps, active=0)

    # 3. Apply default colormap initially
    im_xy.set_cmap('jet')
    if Nz > 1:
        im_xz.set_cmap('jet')
        im_yz.set_cmap('jet')

    # 4. Callback to update colormap
    def change_colormap(label):
        im_xy.set_cmap(label)
        if Nz > 1:
            im_xz.set_cmap(label)
            im_yz.set_cmap(label)
        fig.canvas.draw_idle()

    radio.on_clicked(change_colormap)

    def copy_main_axes_to_clipboard():
        import io
        from PIL import Image
        import win32clipboard

        # Determine how many subplots we need
        show_xz = Nz > 1
        show_yz = Nz > 1 and ax_yz is not None
        num_plots = 1 + int(show_xz) + int(show_yz)

        # Create new figure
        fig_copy, axs = plt.subplots(1, num_plots, figsize=(4 * num_plots, 4), dpi=150,
                                     gridspec_kw={"width_ratios": [1] * num_plots, "wspace": 0.4})
        axs = np.atleast_1d(axs)

        cmap = im_xy.get_cmap()
        vmin, vmax = im_xy.get_clim()

        # --- Re-plot XY ---
        im_list = []
        im1 = axs[0].imshow(I_[z_idx], extent=extent_xy, origin='lower', aspect='equal', cmap=cmap, vmin=vmin,
                            vmax=vmax)
        axs[0].set_title(ax_xy.get_title())
        axs[0].set_xlabel(ax_xy.get_xlabel())
        axs[0].set_ylabel(ax_xy.get_ylabel())
        im_list.append(im1)

        idx = 1

        # --- Re-plot XZ if present ---
        if show_xz:
            im2 = axs[idx].imshow(I_[:, y_idx, :], extent=extent_xz, origin='lower', aspect='auto', cmap=cmap,
                                  vmin=vmin, vmax=vmax)
            axs[idx].set_title(ax_xz.get_title())
            axs[idx].set_xlabel(ax_xz.get_xlabel())
            axs[idx].set_ylabel(ax_xz.get_ylabel())
            im_list.append(im2)
            idx += 1

        # --- Re-plot YZ if present ---
        if show_yz:
            im3 = axs[idx].imshow(I_[:, :, x_idx], extent=extent_yz, origin='lower', aspect='auto', cmap=cmap,
                                  vmin=vmin, vmax=vmax)
            axs[idx].set_title(ax_yz.get_title())
            axs[idx].set_xlabel(ax_yz.get_xlabel())
            axs[idx].set_ylabel(ax_yz.get_ylabel())
            im_list.append(im3)

        # --- Add colorbar (shared) ---
        cbar_ax = fig_copy.add_axes([0.92, 0.15, 0.015, 0.7])
        fig_copy.colorbar(im_list[0], cax=cbar_ax, label="kCounts/s")

        # --- Copy to clipboard ---
        buf = io.BytesIO()
        fig_copy.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image = Image.open(buf)

        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

        plt.close(fig_copy)
        print("Copied graph with colorbar to clipboard.")

    # Add "Copy" button in figure window
    from matplotlib.widgets import Button
    btn_ax = plt.axes([0.02, 0.45, 0.04, 0.04])  # x, y, width, height
    btn = Button(btn_ax, 'Copy')
    btn.on_clicked(lambda event: copy_main_axes_to_clipboard())

    from matplotlib.widgets import Button

    # Add2PPT Button
    ax_addppt = plt.axes([0.02, 0.4, 0.04, 0.04])
    btn_addppt = Button(ax_addppt, 'add2ppt')

    def handle_add2ppt(event):
        try:
            import win32com.client
            import pythoncom
            from PIL import ImageGrab, Image

            # Copy the scan axes to clipboard first
            copy_main_axes_to_clipboard()

            # Metadata (only file name)
            meta = {
                "filename": os.path.abspath(filepath) if filepath else "N/A"
            }

            # Insert into PPT
            pythoncom.CoInitialize()
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                print("No PowerPoint presentations are open.")
                return
            pres = ppt.ActivePresentation
            new_slide = pres.Slides.Add(pres.Slides.Count + 1, 12)
            ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)

            img = ImageGrab.grabclipboard()
            if not isinstance(img, Image.Image):
                print("Clipboard does not contain an image.")
                return

            shapes = new_slide.Shapes.Paste()
            if shapes.Count > 0:
                shape = shapes[0]
                shape.AlternativeText = json.dumps(meta, separators=(",", ":"))

            print(f"Added slide #{new_slide.SlideIndex} with filename metadata.")

        except Exception as e:
            print(f"Failed to add to PowerPoint: {e}")

    btn_addppt.on_clicked(handle_add2ppt)

    # --- Plot area resizing  -----------------
    ax_ph = plt.axes([0.01, 0.005, 0.1, 0.03])  # Plot height
    s_plot_h = Slider(ax_ph, 'Plot Height (%)', 40, 500, valinit=85, valstep=1)
    # put label above, centered
    s_plot_h.label.set_transform(s_plot_h.ax.transAxes)
    s_plot_h.label.set_position((0.5, 1.1))  # (x,y) in axes coords; y>1 is above
    s_plot_h.label.set_ha('center')
    s_plot_h.label.set_va('bottom')

    try:
        fig.set_constrained_layout(False)
    except Exception:
        pass

    # plt.subplots_adjust(bottom=0.3)  # make room for the extra slider

    ctrl_bottom = fig.subplotpars.bottom
    top_limit = 0.98
    max_h = max(0.0, top_limit - ctrl_bottom)

    # Fixed width fraction (centered); tweak if you want wider/narrower plots
    FIXED_W_FRAC = 0.90

    def _apply_plot_layout_h(h_frac_pct: float):
        h_frac = h_frac_pct / 100.0
        w_frac = FIXED_W_FRAC

        left = 0.25 - 0.5 * w_frac
        width = w_frac
        height = max_h * h_frac
        bottom = ctrl_bottom + 0.5 * (max_h - height)

        if ax_xz is not None and ax_yz is not None:
            gap = 0.03
            col_w = (width - 2 * gap) / 3.0
            ax_xy.set_position([left, bottom, col_w, height])
            ax_xz.set_position([left + col_w + gap, bottom, col_w, height])
            ax_yz.set_position([left + 2 * (col_w + gap), bottom, col_w, height])
        else:
            ax_xy.set_position([left, bottom, width, height])

        # keep colorbar aligned to the right of the last panel
        try:
            last_ax = ax_yz if ax_yz is not None else ax_xy
            lb = last_ax.get_position()
            cb_gap = 0.012
            cb_w = 0.018
            cbar.ax.set_position([lb.x1 + cb_gap, lb.y0, cb_w, lb.height])
        except Exception:
            pass

        fig.canvas.draw_idle()

    s_plot_h.on_changed(_apply_plot_layout_h)
    _apply_plot_layout_h(s_plot_h.val)

    # --- Arrow buttons to move the plot area (keep window maximized) ---

    NUDGE_STEP = 0.02  # move by 2% of figure per click

    # Place the arrows at the bottom-left control strip
    ax_up = plt.axes([0.055, 0.295, 0.02, 0.04])
    ax_left = plt.axes([0.035, 0.255, 0.02, 0.04])
    ax_down = plt.axes([0.055, 0.215, 0.02, 0.04])
    ax_right = plt.axes([0.075, 0.255, 0.02, 0.04])

    btn_up = Button(ax_up, '↑')
    btn_left = Button(ax_left, '←')
    btn_down = Button(ax_down, '↓')
    btn_right = Button(ax_right, '→')

    def _nudge(dx, dy):
        axes_list = [ax for ax in (ax_xy, ax_xz, ax_yz) if ax is not None]

        # Move all axes by the same delta (no limits)
        for ax in axes_list:
            p = ax.get_position()
            ax.set_position([p.x0 + dx, p.y0 + dy, p.width, p.height])

        # Keep the colorbar aligned to the right of the last panel
        try:
            last_ax = ax_yz if ax_yz is not None else ax_xy
            lb = last_ax.get_position()
            cb_gap, cb_w = 0.012, 0.018
            cbar.ax.set_position([lb.x1 + cb_gap, lb.y0, cb_w, lb.height])
        except Exception:
            pass

        fig.canvas.draw_idle()

    btn_left.on_clicked(lambda _e: _nudge(-NUDGE_STEP, 0.0))
    btn_right.on_clicked(lambda _e: _nudge(NUDGE_STEP, 0.0))
    btn_up.on_clicked(lambda _e: _nudge(0.0, NUDGE_STEP))
    btn_down.on_clicked(lambda _e: _nudge(0.0, -NUDGE_STEP))

    plt.show(block=False)
    try:
        while plt.fignum_exists(fig.number):
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass

if __name__=="__main__":
    path = sys.argv[1] if len(sys.argv)>1 else None
    display_all_z_slices(filepath=path)

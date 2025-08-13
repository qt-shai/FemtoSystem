import json

import matplotlib
matplotlib.use('TkAgg')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
import os, re
import sys
import win32com.client
import pythoncom
from PIL import ImageGrab, Image
from matplotlib.widgets import RadioButtons
import io
from PIL import Image
import win32clipboard
from matplotlib.widgets import Button

# --- NEW: prefer tifffile for scientific TIFFs, fallback to imageio ---
try:
    import tifffile as tiff
    _HAS_TIFFFILE = True
except Exception:
    _HAS_TIFFFILE = False
    try:
        import imageio.v3 as iio
    except Exception:
        iio = None

try:
    from Utils.Common import open_file_dialog
except ImportError:
    from tkinter import Tk, filedialog
    def open_file_dialog(filetypes):
        root = Tk(); root.withdraw()
        return filedialog.askopenfilename(filetypes=filetypes)

def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False, data=None):
    """
        If 'filepath' ends with .tif/.tiff, read it as (Z,Y,X) stack and view as Z-slices.
        Otherwise, keep the original CSV behavior.
        """

    # --- Helpers for TIFF reading ---
    def _read_tif_stack(path: str):
        # prefer tifffile, fallback to imageio.v3
        try:
            import tifffile as tiff
            arr = tiff.imread(path)  # returns (Z,Y,X) for multipage, (Y,X) for single
        except Exception:
            try:
                import imageio.v3 as iio
            except Exception as e:
                raise RuntimeError("Need tifffile or imageio.v3 to read TIFFs") from e
            arr = iio.imread(path, index=None)  # index=None -> stack if multipage
        return np.asarray(arr)

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
            filepath = open_file_dialog(filetypes=[
                ("CSV or TIFF", "*.csv *.tif *.tiff"),
                ("CSV Files", "*.csv"),
                ("TIFF Files", "*.tif *.tiff"),
                ("All Files", "*.*"),
            ])
            if not filepath or not os.path.isfile(filepath):
                print("File not selected or not found.")
                return
        ext = os.path.splitext(filepath)[1].lower()

        if ext in (".tif", ".tiff"):
            # --- TIFF path: read and average all frames into one 2D image ---
            stack = _read_tif_stack(filepath)
            stack = np.asarray(stack, dtype=np.float64)

            # Remove singleton/sample dims
            stack = np.squeeze(stack)

            # Handle color TIFFs: convert RGB(A) to grayscale first
            if stack.ndim == 3 and stack.shape[-1] in (3, 4):
                stack = stack[..., :3].mean(axis=-1)  # simple mean over RGB

            # If it's multi-frame (Z, Y, X), average over frames
            if stack.ndim == 3:
                stack = stack.mean(axis=0)  # collapse Z → average image

            # Ensure final shape is 2D
            if stack.ndim != 2:
                raise ValueError(f"Unexpected TIFF shape after averaging: {stack.shape}")

            # Wrap as single "slice"
            stack = stack[np.newaxis, ...]  # shape: (1, Y, X)
            Nz, Ny, Nx = stack.shape

            def _parse_site_center_from_name(name: str):
                # Match Site (<x> <y> <z>) where decimals use commas
                m = re.search(r"Site\s*\(\s*([^\s\)]+)\s+([^\s\)]+)\s+([^\s\)]+)\s*\)", name)
                if not m:
                    return None
                try:
                    # replace comma decimal with dot and convert to float (µm)
                    cx = float(m.group(1).replace(',', '.'))
                    cy = float(m.group(2).replace(',', '.'))
                    cz = float(m.group(3).replace(',', '.'))
                    return (cx, cy, cz)
                except Exception:
                    return None

            fname = os.path.basename(filepath)
            center_um = _parse_site_center_from_name(fname)  # (cx, cy, cz) in µm or None

            # Coordinate construction:
            # Keep your existing internal "µm * 1e6" convention, since you later multiply by 1e-6.
            PIXEL_SIZE_UM = 0.1  # µm per pixel

            if center_um is not None:
                cx_um, cy_um, cz_um = center_um

                # Build pixel-centered axes around the image center, then add the parsed center
                x_um = (np.arange(Nx, dtype=float) - (Nx - 1) / 2.0) * PIXEL_SIZE_UM + cx_um
                y_um = (np.arange(Ny, dtype=float) - (Ny - 1) / 2.0) * PIXEL_SIZE_UM + cy_um
                z_um = cz_um  # single averaged Z position

                # Store in your internal units (µm * 1e6). Later multiplied by 1e-6 → µm again.
                x = x_um * 1e6
                y = y_um * 1e6
                z = np.array([z_um * 1e6])
            else:
                # Fallback: original pixel-based axes (center at 0, no offset)
                x = np.arange(Nx, dtype=float) * 1e6 * PIXEL_SIZE_UM  # 0.1 µm/px
                y = np.arange(Ny, dtype=float) * 1e6 * PIXEL_SIZE_UM
                z = np.array([0.0])

            I = stack.reshape(-1)
        else:
            # --- CSV path: original behavior ---
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

    # --- Smoothing (minimal; does not modify I_) ---
    try:
        import scipy.ndimage as ndi
        _HAS_SCIPY_ND = True
    except Exception:
        _HAS_SCIPY_ND = False

    _smooth = {"on": False, "sigma": 1.0}

    def _gauss1d(sigma: float):
        if sigma <= 0:
            return np.array([1.0], dtype=np.float64)
        r = max(1, int(3 * sigma))
        x = np.arange(-r, r + 1, dtype=np.float64)
        k = np.exp(-(x * x) / (2.0 * sigma * sigma))
        k /= k.sum()
        return k

    def _smooth2d(img2d: np.ndarray) -> np.ndarray:
        """Return smoothed copy for display only (XY plane)."""
        if not _smooth["on"] or _smooth["sigma"] <= 0:
            return img2d
        s = float(_smooth["sigma"])
        if _HAS_SCIPY_ND:
            return ndi.gaussian_filter(img2d, sigma=s, mode="reflect")
        # NumPy fallback: separable conv with reflect padding
        k = _gauss1d(s)
        pad = len(k) // 2
        # rows
        rpad = np.pad(img2d, ((0, 0), (pad, pad)), mode='reflect')
        row_conv = np.apply_along_axis(lambda v: np.convolve(v, k, mode='valid'), 1, rpad)
        # cols
        cpad = np.pad(row_conv, ((pad, pad), (0, 0)), mode='reflect')
        out = np.apply_along_axis(lambda v: np.convolve(v, k, mode='valid'), 0, cpad)
        return out

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
        fig, ax_xy = plt.subplots(1, 1, figsize=(17, 12))
        ax_xz = ax_yz = None

    file_name_only = os.path.basename(filepath)
    # Add a big white title at the top
    fig.suptitle(
        file_name_only,
        fontsize=24,
        fontweight="bold",        # color="white",
        y=0.98
    )

    fig.canvas.manager.set_window_title(file_name_only)

    # Move the window to (X=200px, Y=100px) from top-left of screen
    mgr = plt.get_current_fig_manager()
    try:
        # TkAgg backend
        mgr.window.wm_geometry("+290+890")  # position only
        # mgr.window.wm_geometry("1200x900+200+100")  # size + position
    except Exception:
        try:
            # Qt5Agg backend
            mgr.window.move(200, 800)  # X, Y in pixels
            # mgr.window.resize(1200, 900)  # optional size
        except Exception:
            print("Could not set initial window position for this backend.")

    plt.subplots_adjust(bottom=0.30)
    # dbg = fig.text(0.5, 0.1, "Msg", ha="left", va="top", fontsize=9)

    z_idx = 0
    y_idx = Ny // 2
    x_idx = Nx // 2
    im_xy = ax_xy.imshow(
        _smooth2d(I_[z_idx]), extent=extent_xy,
        origin='lower', aspect='equal', vmin=minI, vmax=maxI
    )
    ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
    ax_xy.set_xlabel("X (µm)"); ax_xy.set_ylabel("Y (µm)")

    if Nz > 1:
        im_xz = ax_xz.imshow(
            _smooth2d(I_[:, y_idx, :]), extent=extent_xz,
            origin='lower', aspect='auto', vmin=minI, vmax=maxI
        )
        ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
        ax_xz.set_xlabel("X (µm)"); ax_xz.set_ylabel("Z (µm)")

        im_yz = ax_yz.imshow(_smooth2d(I_[:, :, x_idx]), extent=extent_yz, origin='lower',
                             aspect='auto', vmin=minI, vmax=maxI)
        ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
        ax_yz.set_xlabel("Y (µm)");
        ax_yz.set_ylabel("Z (µm)")

        cbar = fig.colorbar(im_xy, ax=[ax_xy, ax_xz, ax_yz], label="kCounts/s")
    else:
        cbar = fig.colorbar(im_xy, ax=ax_xy, label="kCounts/s")

    # ----------------  Smoothing controls (minimal UI)  ----------------
    ax_sigma = plt.axes([0.1, 0.10, 0.1, 0.03])  # x, y, w, h
    slider_sigma = Slider(ax_sigma, 'σ (px)', 0.0, 6.0, valinit=_smooth["sigma"], valstep=0.1)
    ax_smooth = plt.axes([0.20, 0.15, 0.06, 0.04])
    btn_smooth = Button(ax_smooth, 'smooth off')
    def _on_sigma_change(_val):
        _smooth["sigma"] = float(slider_sigma.val)
        if _smooth["on"]:
            # just refresh currently shown data
            im_xy.set_data(_smooth2d(I_[z_idx]))
            if Nz > 1:
                im_xz.set_data(_smooth2d(I_[:, y_idx, :]))
                im_yz.set_data(_smooth2d(I_[:, :, x_idx]))
            fig.canvas.draw_idle()
    slider_sigma.on_changed(_on_sigma_change)
    def _toggle_smoothing(_event):
        _smooth["on"] = not _smooth["on"]
        btn_smooth.label.set_text('smooth on' if _smooth["on"] else 'smooth off')
        # refresh display from original I_ through smoother (or not)
        im_xy.set_data(_smooth2d(I_[z_idx]))
        if Nz > 1:
            im_xz.set_data(_smooth2d(I_[:, y_idx, :]))
            im_yz.set_data(_smooth2d(I_[:, :, x_idx]))
        fig.canvas.draw_idle()
    btn_smooth.on_clicked(_toggle_smoothing)

    # ----------------   Max I slider    ----------------
    ax_max = plt.axes([0.1, 0.05, 0.1, 0.03])
    slider_max = Slider(ax_max, 'Max I', np.min(I_), np.max(I_), valinit=maxI)
    def update_max(val):
        vmin = minI; vmax = slider_max.val
        im_xy.set_clim(vmin, vmax)
        if Nz > 1:
            im_xz.set_clim(vmin, vmax)
            im_yz.set_clim(minI, vmax)
        fig.canvas.draw_idle()
    slider_max.on_changed(update_max)

    # ----------------     Plot area resizing     ----------------
    ax_ph = plt.axes([0.1, 0.005, 0.1, 0.03])
    s_plot_h = Slider(ax_ph, 'Size (%)', 40, 500, valinit=155 if Nz == 1 else 85, valstep=1)
    # plt.subplots_adjust(bottom=0.3)  # make room for the extra slider
    ctrl_bottom = fig.subplotpars.bottom
    top_limit = 0.98
    max_h = max(0.0, top_limit - ctrl_bottom)
    FIXED_W_FRAC = 0.90  # Fixed width fraction (centered); tweak if you want wider/narrower plots
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
        try: # keep colorbar aligned to the right of the last panel
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

    # ----------------    Z slider (only if Nz > 1)    ----------------
    if Nz > 1:
        ax_z = plt.axes([0.3, 0.1, 0.5, 0.03])
        slider_z = Slider(ax_z, 'Z slice', 1, Nz, valinit=1, valstep=1)
        def update_z(val):
            nonlocal z_idx
            z_idx = int(slider_z.val) - 1
            im_xy.set_data(_smooth2d(I_[z_idx]))
            ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_z.on_changed(update_z)
    # X, Y sliders only if XZ is shown
    if Nz > 1:
        ax_y = plt.axes([0.3, 0.05, 0.5, 0.03])
        slider_y = Slider(ax_y, 'Y slice', 1, Ny, valinit=y_idx + 1, valstep=1)
        def update_y(val):
            nonlocal y_idx
            y_idx = int(slider_y.val) - 1
            im_xz.set_data(_smooth2d(I_[:, y_idx, :]))
            ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_y.on_changed(update_y)
        # ----------------    X slice slider    ----------------
        ax_x = plt.axes([0.3, 0.005, 0.5, 0.03])
        slider_x = Slider(ax_x, 'X slice', 1, Nx, valinit=x_idx + 1, valstep=1)
        def update_x(val):
            nonlocal x_idx
            x_idx = int(slider_x.val) - 1
            im_yz.set_data(_smooth2d(I_[:, :, x_idx]))
            ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_x.on_changed(update_x)

    # ----------------    Radio Buttons   ----------------
    colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                 'gray', 'hot', 'jet', 'bone', 'cool', 'spring', 'summer', 'autumn', 'winter']
    radio_ax = plt.axes([0.005, 0.005, 0.03, 0.2], facecolor='lightgray')  # x, y, width, height
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

    # ----------------    "Copy"    ----------------
    def copy_main_axes_to_clipboard():
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
    btn_ax = plt.axes([0.05, 0.15, 0.04, 0.04])  # x, y, width, height
    btn = Button(btn_ax, 'Copy')
    btn.on_clicked(lambda event: copy_main_axes_to_clipboard())

    # ----------------    Add2PPT Button    ----------------
    ax_addppt = plt.axes([0.1, 0.15, 0.04, 0.04])
    btn_addppt = Button(ax_addppt, 'add2ppt')
    def handle_add2ppt(event):
        try:
            # Copy the scan axes to clipboard first
            copy_main_axes_to_clipboard()

            # Metadata (only file name)
            meta = {
                "filename": os.path.abspath(filepath) if filepath else "N/A"
            }
            file_name_only = os.path.basename(filepath) if filepath else "Untitled"

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

                # --- Add a big white title at the top with the file name ---
                slide_w = pres.PageSetup.SlideWidth
                # msoTextOrientationHorizontal = 1
                title_shape = new_slide.Shapes.AddTextbox(1, 20, 10, slide_w - 40, 50)
                tr = title_shape.TextFrame.TextRange
                tr.Text = file_name_only
                tr.ParagraphFormat.Alignment = 2  # ppAlignCenter = 2
                tr.Font.Bold = True
                tr.Font.Size = 28
                # tr.Font.Color.RGB = 0xFFFFFF  # white

                # Make the title box visually clean
                try:
                    title_shape.Fill.Visible = 0  # msoFalse
                    title_shape.Line.Visible = 0
                except Exception as e:
                    pass

            print(f"Added slide #{new_slide.SlideIndex} with filename metadata.")
            plt.close(fig)

        except Exception as e:
            print(f"Failed to add to PowerPoint: {e}")
    btn_addppt.on_clicked(handle_add2ppt)

    # ----------------     Grid toggle button     ----------------
    grid_state = {"on": False}
    ax_grid = plt.axes([0.15, 0.15, 0.04, 0.04])
    btn_grid = Button(ax_grid, 'grid off')
    def _apply_grid(ax, on: bool):
        if ax is None:
            return
        if on:
            ax.grid(True, which='major', linewidth=0.5, alpha=0.5)
            ax.grid(True, which='minor', linewidth=0.5, alpha=0.3)
            ax.minorticks_on()
        else:
            ax.grid(False, which='major')
            ax.grid(False, which='minor')
            ax.minorticks_off()
    def handle_toggle_grid(_event):
        grid_state["on"] = not grid_state["on"]
        on = grid_state["on"]
        _apply_grid(ax_xy, on)
        _apply_grid(ax_xz, on)
        _apply_grid(ax_yz, on)
        btn_grid.label.set_text('grid on' if on else 'grid off')
        fig.canvas.draw_idle()
    btn_grid.on_clicked(handle_toggle_grid)
    try:
        fig.set_constrained_layout(False)
    except Exception:
        pass

    # ----------------    Arrow buttons    ----------------

    NUDGE_STEP = 0.02  # move by 2% of figure per click

    # Place the arrows at the bottom-left control strip
    ax_up = plt.axes([0.87, 0.1, 0.02, 0.04])
    ax_left = plt.axes([0.85, 0.06, 0.02, 0.04])
    ax_down = plt.axes([0.87, 0.02, 0.02, 0.04])
    ax_right = plt.axes([0.89, 0.06, 0.02, 0.04])

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
            # dbg.set_text(f"x0={p.x0 + dx:.3f}, y0={p.y0 + dy:.3f}, w={p.width:.3f}, h={p.height:.3f}")

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

    if Nz==1:
        ax_xy.set_position([0.156, 0.053, 0.744, 1.054])
        # Keep the colorbar aligned to the right of the last panel
        lb = ax_xy.get_position()
        cb_gap, cb_w = 0.012, 0.018
        cbar.ax.set_position([lb.x1 + cb_gap, lb.y0, cb_w, lb.height])
    else:
        _nudge(0.25,-0.05)

    try:
        while plt.fignum_exists(fig.number):
            plt.pause(0.1)
    except KeyboardInterrupt:
        pass





# =========================
# CLI routing (fixed)
# =========================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Display CSV Z-slices or ProEM TIFF (averaged) with sliders."
    )
    parser.add_argument("path", nargs="?", default=None, help="Path to .csv or .tif/.tiff")
    parser.add_argument("--vmin", type=float, default=None, help="Lower display limit")
    parser.add_argument("--vmax", type=float, default=None, help="Upper display limit")
    parser.add_argument("--log", action="store_true", help="Use log-scale display")

    args = parser.parse_args()

    # TIFF logic is handled inside display_all_z_slices
    display_all_z_slices(
        filepath=args.path,
        minI=args.vmin,
        maxI=args.vmax,
        log_scale=args.log,
    )


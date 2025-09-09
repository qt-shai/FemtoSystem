import json

import matplotlib
# matplotlib.use('QtAgg')
matplotlib.use('TkAgg')
import json, os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider
from matplotlib.widgets import TextBox
from matplotlib.widgets import Button
from matplotlib.widgets import RadioButtons
import os, re
import sys
import win32com.client
import pythoncom
from PIL import ImageGrab, Image, ImageDraw
import tempfile
import io
from PIL import Image
import win32clipboard

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


# ------- Map overlay config -------
MAP_IMAGE_PATH = "map.jpg"     # path to your site map image
MAP_MODE = "corner"  # "center" or "corner"
MAP_CALIB_PATH = "map_calibration.json"

# If MAP_MODE == "center": we assume 0,0 is the center of the JPEG.
# If MAP_MODE == "corner": define world coords for the top-left pixel (Xmin_um, Ymax_um)
# and pixels-per-micron. +X to the right, +Y down (image convention).
MAP_PX_PER_UM = 1.0            # pixels per micron (tune to your map scale)
MAP_XMIN_UM = -1000.0          # used only when MAP_MODE == "corner"
MAP_YMAX_UM =  1000.0          # used only when MAP_MODE == "corner"

# Cross drawing params
CROSS_SIZE_PX = 100             # half-size of cross arm in pixels
CROSS_THICK_PX = 20             # line thickness
CROSS_COLOR = (255, 0, 0)      # red
RING_RADIUS_PX = 180          # NEW: circle radius in pixels
RING_THICK_PX = 20           # NEW: circle outline thickness

# ------- Preset parameters -------
PRESET1_SIGMA = 0.1
PRESET1_SIGMA_BG = 10.0
PRESET1_VMAX = 13000.0
PRESET1_PLOT_HEIGHT = 200
PRESET1_NUDGE = (0.15, -0.3)
PRESET1_FLIP_UD = False
PRESET1_FLIP_LR = True

OUTSIDE_MARGIN_PX = 50  # padding when cross falls outside map image


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

    # --- ADD: flip state + helper ---
    flip_state = {"ud": False, "lr": False}

    def _maybe_flip(a2d: np.ndarray) -> np.ndarray:
        """Flip up/down and/or left/right for display if toggles are on."""
        out = a2d
        if flip_state.get("ud", False):
            out = np.flipud(out)
        if flip_state.get("lr", False):
            out = np.fliplr(out)
        return out

    # Keep a pristine copy (no log / no flatten)
    EPS = np.finfo(float).eps
    I_raw_cube = I_.copy()  # shape: (Nz, Ny, Nx)

    # This is the array all imshows read from (can be flattened/logged)
    I_view = np.log10(I_raw_cube + EPS) if log_scale else I_raw_cube

    if minI is None: minI = I_view.min()
    if maxI is None: maxI = I_view.max()

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
    print(f"Shape of I_: {I_view.shape}, min={I_view.min()}, max={I_view.max()}")


    z_idx = 0
    y_idx = Ny // 2
    x_idx = Nx // 2
    im_xy = ax_xy.imshow(
        _maybe_flip(_smooth2d(I_view[z_idx])), extent=extent_xy,
        origin='lower', aspect='equal', vmin=minI, vmax=maxI
    )
    ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
    ax_xy.set_xlabel("X (µm)"); ax_xy.set_ylabel("Y (µm)")

    if Nz > 1:
        im_xz = ax_xz.imshow(
            _smooth2d(I_view[:, y_idx, :]), extent=extent_xz,
            origin='lower', aspect='auto', vmin=minI, vmax=maxI
        )
        ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
        ax_xz.set_xlabel("X (µm)"); ax_xz.set_ylabel("Z (µm)")

        im_yz = ax_yz.imshow(_smooth2d(I_view[:, :, x_idx]), extent=extent_yz, origin='lower',
                             aspect='auto', vmin=minI, vmax=maxI)
        ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
        ax_yz.set_xlabel("Y (µm)");
        ax_yz.set_ylabel("Z (µm)")

        cbar = fig.colorbar(im_xy, ax=[ax_xy, ax_xz, ax_yz], label="kCounts/s")
    else:
        cbar = fig.colorbar(im_xy, ax=ax_xy, label="kCounts/s")

    btn_x = 0.005
    btn_y = 0.97
    btn_w = 0.05
    btn_h = 0.025
    btn_rect = (btn_x, btn_y, btn_w, btn_h)  # tuple
    btn_x_slider =  btn_x + 0.03
    # ----------------   Max I slider    ----------------
    ax_max = plt.axes((btn_x_slider, 0.05, 0.1, 0.03))
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
    ax_ph = plt.axes((btn_x_slider, 0.005, 0.1, 0.03))
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

    # ----------------     Aggressiveness slider     ----------------

    ax_sigma_bg = plt.axes((btn_x_slider, 0.12, 0.1, 0.03))
    slider_sigma_bg = Slider(ax_sigma_bg, 'σ_bg', 5, 120, valinit=20, valstep=1)

    def _on_sigma_bg_change(val):
        # invalidate cache
        aggr_state["cube"] = None
        aggr_state["computed_sigma"] = None

        # if flatten++ is currently ON, recompute and refresh the view now
        if aggr_state.get("on", False):
            sigma_bg = float(val)
            aggr_state["cube"] = _compute_flat_cube_aggressive(sigma_bg=sigma_bg)
            aggr_state["computed_sigma"] = sigma_bg

            # ⬇️ make this assignment update the shared buffer
            nonlocal I_view
            C = aggr_state["cube"]
            I_view = np.log10(C + EPS) if log_scale else C

            # push updated data to plots (do NOT touch clim)
            im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
            if Nz > 1:
                im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
                im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
            try:
                btn_flat_aggr.label.set_text(f"flatten++ on (σ={sigma_bg:.0f})")
            except Exception:
                pass
            fig.canvas.draw_idle()

    slider_sigma_bg.on_changed(_on_sigma_bg_change)

    # ----------------    Z slider (only if Nz > 1)    ----------------
    if Nz > 1:
        ax_z = plt.axes([0.3, 0.1, 0.5, 0.03])
        slider_z = Slider(ax_z, 'Z slice', 1, Nz, valinit=1, valstep=1)
        def update_z(val):
            nonlocal z_idx
            z_idx = int(slider_z.val) - 1
            im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
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
            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
            ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_y.on_changed(update_y)
        # ----------------    X slice slider    ----------------
        ax_x = plt.axes([0.3, 0.005, 0.5, 0.03])
        slider_x = Slider(ax_x, 'X slice', 1, Nx, valinit=x_idx + 1, valstep=1)
        def update_x(val):
            nonlocal x_idx
            x_idx = int(slider_x.val) - 1
            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
            ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")
            fig.canvas.draw_idle()
        slider_x.on_changed(update_x)

    def shift_rect(rect, dx=0.0, dy=-0.03):
        x1, y1, w1, h1 = rect
        return x1 + dx, y1 + dy, w1, h1

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
        im1 = axs[0].imshow(_maybe_flip(I_view[z_idx]), extent=extent_xy, origin='lower', aspect='equal', cmap=cmap, vmin=vmin,
                            vmax=vmax)
        axs[0].set_title(ax_xy.get_title())
        axs[0].set_xlabel(ax_xy.get_xlabel())
        axs[0].set_ylabel(ax_xy.get_ylabel())
        im_list.append(im1)

        idx = 1

        # --- Re-plot XZ if present ---
        if show_xz:
            im2 = axs[idx].imshow(I_view[:, y_idx, :], extent=extent_xz, origin='lower', aspect='auto', cmap=cmap,
                                  vmin=vmin, vmax=vmax)
            axs[idx].set_title(ax_xz.get_title())
            axs[idx].set_xlabel(ax_xz.get_xlabel())
            axs[idx].set_ylabel(ax_xz.get_ylabel())
            im_list.append(im2)
            idx += 1

        # --- Re-plot YZ if present ---
        if show_yz:
            im3 = axs[idx].imshow(I_view[:, :, x_idx], extent=extent_yz, origin='lower', aspect='auto', cmap=cmap,
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
    btn_ax = plt.axes(btn_rect)  # x, y, width, height
    btn = Button(btn_ax, 'Copy')
    btn.on_clicked(lambda event: copy_main_axes_to_clipboard())
    btn_rect = shift_rect(btn_rect)

    # ----------------    Add2PPT Button    ----------------
    ax_addppt = plt.axes(btn_rect)
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
    btn_rect = shift_rect(btn_rect)

    # ----------------    Cal map Button (console + robust click capture)    ----------------
    ax_calmap = plt.axes(btn_rect)
    btn_calmap = Button(ax_calmap, 'Cal map')
    btn_rect = shift_rect(btn_rect)

    def _calibrate_map(_evt=None):
        try:
            base = Image.open(MAP_IMAGE_PATH).convert("RGB")
        except Exception as e:
            print(f"⚠️ map image not found/unreadable: {MAP_IMAGE_PATH} ({e})")
            return

        figC, axC = plt.subplots(1, 1, figsize=(7, 7))
        # Keep image coordinates: origin at top-left, +X right, +Y down
        H, W = base.size[1], base.size[0]
        axC.imshow(base, origin='upper')
        axC.set_xlim(0, W)
        axC.set_ylim(H, 0)
        axC.set_title("Calibration: LEFT-click TWO known points (P1 then P2).\n"
                      "Tip: turn off pan/zoom in the toolbar. Press Esc to cancel.")
        figC.canvas.draw_idle()

        # Make sure toolbar isn't in pan/zoom mode
        try:
            mgr = plt.get_current_fig_manager()
            tb = getattr(mgr, "toolbar", None)
            if tb and getattr(tb, "mode", ""):
                # clear any active mode
                # if it's 'pan/zoom' toggle pan; if it's 'zoom rect' toggle zoom; otherwise try both
                if "pan" in tb.mode:
                    tb.pan()  # toggles off
                elif "zoom" in tb.mode:
                    tb.zoom()  # toggles off
                else:
                    try:
                        tb.pan()
                    except Exception:
                        pass
                    try:
                        tb.zoom()
                    except Exception:
                        pass
        except Exception:
            pass

        clicks = []

        def _on_click(ev):
            if ev.inaxes is not axC: return
            if ev.button != 1:       return  # left-click only
            if ev.xdata is None or ev.ydata is None: return
            clicks.append((ev.xdata, ev.ydata))
            axC.plot(ev.xdata, ev.ydata, 'rx', markersize=10, mew=2)
            figC.canvas.draw_idle()

        cid = figC.canvas.mpl_connect('button_press_event', _on_click)

        # Show non-blocking and wait until 2 clicks or window closed
        plt.show(block=False)
        try:
            while plt.fignum_exists(figC.number) and len(clicks) < 2:
                plt.pause(0.05)
        except KeyboardInterrupt:
            pass

        figC.canvas.mpl_disconnect(cid)
        plt.close(figC)

        if len(clicks) < 2:
            print("❌ Calibration aborted (need two clicks).")
            return

        (x1, y1), (x2, y2) = clicks[:2]
        print(f"Clicked pixel coords: P1=({x1:.1f}, {y1:.1f}), P2=({x2:.1f}, {y2:.1f})")

        # Ask for world coords in console
        try:
            X1 = _parse_float(input("Enter X1 (µm): "))
            Y1 = _parse_float(input("Enter Y1 (µm): "))
            X2 = _parse_float(input("Enter X2 (µm): "))
            Y2 = _parse_float(input("Enter Y2 (µm): "))
        except Exception as e:
            print(f"❌ Invalid numeric input: {e}")
            return

        # compute per-axis scale (pixels per µm)
        if (X2 - X1) == 0 or (Y1 - Y2) == 0:
            print("❌ Degenerate inputs; need points with different X and Y.")
            return

        px_per_um_x = (x2 - x1) / (X2 - X1)
        px_per_um_y = (y2 - y1) / (Y1 - Y2)  # Y increases downward in pixels

        # compute world origin (top-left) from P1
        xmin_um = X1 - (x1 / px_per_um_x)
        ymax_um = Y1 + (y1 / px_per_um_y)

        _save_map_calib("corner", px_per_um_x, px_per_um_y, xmin_um, ymax_um)

        print(f"✅ Calibration solved:")
        print(f"   px/µm_x = {px_per_um_x:.6f}, px/µm_y = {px_per_um_y:.6f}")
        print(f"   xmin_um = {xmin_um:.3f}, ymax_um = {ymax_um:.3f}")

    btn_calmap.on_clicked(_calibrate_map)

    def _preview_map_cross(_evt=None):
        """Open map.jpg and overlay a cross at the filename's Site(x,y) using current calibration.
           If the cross would fall outside the image, expand the view so it's still visible.
        """
        try:
            base = Image.open(MAP_IMAGE_PATH).convert("RGB")
        except Exception as e:
            print(f"⚠️ map image not found/unreadable: {MAP_IMAGE_PATH} ({e})")
            return

        # Parse coords from current filename
        fname = os.path.basename(filepath) if filepath else ""
        ctr = _parse_site_center_from_name(fname)
        if not ctr:
            print("❌ No Site(...) coordinates found in current filename.")
            return
        cx_um, cy_um, _cz_um = ctr

        W, H = base.size
        cal = _load_map_calib()

        # Compute pixel position
        mode = "corner"
        if cal.get("mode", "").lower() == "corner":
            px_per_um_x = cal["px_per_um_x"]
            px_per_um_y = cal["px_per_um_y"]
            xmin_um = cal["xmin_um"]
            ymax_um = cal["ymax_um"]
            px = (cx_um - xmin_um) * px_per_um_x
            py = (ymax_um - cy_um) * px_per_um_y
            mode = "corner(calibrated)"
        else:
            # fallback to configured params
            if MAP_MODE.lower() == "center":
                px = W / 2.0 + cx_um * MAP_PX_PER_UM
                py = H / 2.0 - cy_um * MAP_PX_PER_UM
                mode = "center(config)"
            else:
                px = (cx_um - MAP_XMIN_UM) * MAP_PX_PER_UM
                py = (MAP_YMAX_UM - cy_um) * MAP_PX_PER_UM
                mode = "corner(config)"

        # Show the preview
        figP, axP = plt.subplots(1, 1, figsize=(7, 7))
        axP.imshow(base)
        axP.set_title(
            f"Preview: {mode}\nFile: {fname}\n"
            f"Site X={cx_um:.2f} µm, Y={cy_um:.2f} µm → px=({px:.1f}, {py:.1f})"
        )

        # draw cross (BIGGER)
        L = CROSS_SIZE_PX
        axP.plot([px - L, px + L], [py, py], '-', lw=CROSS_THICK_PX, color='r', zorder=3)
        axP.plot([px, px], [py - L, py + L], '-', lw=CROSS_THICK_PX, color='r', zorder=3)

        # circle around cross
        import matplotlib.patches as mpatches
        circ = mpatches.Circle((px, py), radius=RING_RADIUS_PX, fill=False,
                               edgecolor='r', linewidth=RING_THICK_PX, zorder=3)
        axP.add_patch(circ)

        # Expand view so cross is visible even if outside original bounds
        try:
            margin = OUTSIDE_MARGIN_PX
        except NameError:
            margin = 50
        x_min = min(0, px - RING_RADIUS_PX - margin)
        x_max = max(W, px + RING_RADIUS_PX + margin)
        y_min = min(0, py - RING_RADIUS_PX - margin)
        y_max = max(H, py + RING_RADIUS_PX + margin)

        axP.set_xlim(x_min, x_max)
        axP.set_ylim(y_max, y_min)  # keep image coordinates (origin at top-left)

        # warn if outside bounds
        if not (0 <= px <= W and 0 <= py <= H):
            axP.text(0.02, 0.98, "⚠️ Cross outside image bounds (view expanded)",
                     transform=axP.transAxes, va='top', ha='left',
                     bbox=dict(facecolor='yellow', alpha=0.6, edgecolor='none'))

        plt.show(block=False)

    # ----------------    Preview map Button    ----------------
    ax_prevmap = plt.axes(btn_rect)
    btn_prevmap = Button(ax_prevmap, 'Preview map')
    btn_prevmap.on_clicked(_preview_map_cross)
    btn_rect = shift_rect(btn_rect)

    # ----------------    Add+Map Button    ----------------
    ax_addppt_map = plt.axes(btn_rect)
    btn_addppt_map = Button(ax_addppt_map, 'add+map')

    def handle_add2ppt_with_map(event):
        try:
            # 1) Copy the scan axes to clipboard (same as add2ppt)
            copy_main_axes_to_clipboard()

            # Metadata (only file name)
            meta = {"filename": os.path.abspath(filepath) if filepath else "N/A"}
            file_name_only = os.path.basename(filepath) if filepath else "Untitled"

            # 2) Insert slide and paste the scan snapshot
            pythoncom.CoInitialize()
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                print("No PowerPoint presentations are open.")
                return
            pres = ppt.ActivePresentation
            new_slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # ppLayoutBlank = 12
            ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)

            img = ImageGrab.grabclipboard()
            if not isinstance(img, Image.Image):
                print("Clipboard does not contain an image.")
                return

            shapes = new_slide.Shapes.Paste()
            if shapes.Count > 0:
                shape = shapes[0]
                shape.AlternativeText = json.dumps(meta, separators=(",", ":"))

                # Title with filename at the top (same as add2ppt)
                slide_w = pres.PageSetup.SlideWidth
                title_shape = new_slide.Shapes.AddTextbox(1, 20, 10, slide_w - 40, 50)  # msoTextOrientationHorizontal=1
                tr = title_shape.TextFrame.TextRange
                tr.Text = file_name_only
                tr.ParagraphFormat.Alignment = 2  # ppAlignCenter
                tr.Font.Bold = True
                tr.Font.Size = 28
                try:
                    title_shape.Fill.Visible = 0
                    title_shape.Line.Visible = 0
                except Exception:
                    pass

            # 3) Parse coordinates from filename (you already have a parser)
            fname = os.path.basename(filepath) if filepath else ""
            center_um = None
            try:
                center_um = _parse_site_center_from_name(fname)  # (cx, cy, cz) in µm
            except Exception:
                center_um = None

            if center_um is None:
                print("⚠️ Could not parse Site(...) coordinates from filename; skipping map overlay.")
                plt.close(fig)
                return

            cx_um, cy_um, _cz_um = center_um

            # 4) Draw cross on map and insert image
            tmp_map_path = _make_map_with_cross(cx_um, cy_um, MAP_IMAGE_PATH)
            if tmp_map_path is None:
                print("⚠️ Map image not available; added slide without map.")
                plt.close(fig)
                return

            # Insert the small map on the same slide
            # Position: bottom-right corner, keeping margins; size proportional to slide width
            slide_h = pres.PageSetup.SlideHeight
            map_w = slide_w * 0.25
            map_h = slide_h * 0.25
            margin = 20
            left = slide_w - map_w - margin
            top = margin

            pic = new_slide.Shapes.AddPicture(
                FileName=tmp_map_path, LinkToFile=False, SaveWithDocument=True,
                Left=left, Top=top, Width=map_w, Height=map_h
            )
            pic.AlternativeText = json.dumps(
                {"type": "site-map", "x_um": cx_um, "y_um": cy_um, "source": MAP_IMAGE_PATH},
                separators=(",", ":")
            )

            print(f"Added slide #{new_slide.SlideIndex} with scan and site-map cross at ({cx_um:.1f}, {cy_um:.1f}) µm.")
            plt.close(fig)

        except Exception as e:
            print(f"Failed to add to PowerPoint with map: {e}")

    btn_addppt_map.on_clicked(handle_add2ppt_with_map)
    btn_rect = shift_rect(btn_rect)

    # ----------------     Grid toggle button     ----------------
    grid_state = {"on": False}
    ax_grid = plt.axes(btn_rect)
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
    btn_rect = shift_rect(btn_rect)

    # ----------------    Flip Up/Down toggle button    ----------------
    ax_flipud = plt.axes(btn_rect)
    btn_flipud = Button(ax_flipud, 'flip UD off')

    def _toggle_flipud(_event):
        flip_state["ud"] = not flip_state["ud"]
        btn_flipud.label.set_text('flip UD on' if flip_state["ud"] else 'flip UD off')

        # refresh displays (no clim change)
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_maybe_flip(_smooth2d(I_view[:, y_idx, :])))
            im_yz.set_data(_maybe_flip(_smooth2d(I_view[:, :, x_idx])))
        fig.canvas.draw_idle()

    btn_flipud.on_clicked(_toggle_flipud)
    btn_rect = shift_rect(btn_rect)

    # ---------------- NEW: Flip Left/Right toggle button ----------------
    ax_fliplr = plt.axes(btn_rect)
    btn_fliplr = Button(ax_fliplr, 'flip LR off')

    def _toggle_fliplr(_event):
        flip_state["lr"] = not flip_state["lr"]

    btn_fliplr.label.set_text('flip LR on' if flip_state["lr"] else 'flip LR off')

    # refresh displays (no clim change)
    im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
    if Nz > 1:
        im_xz.set_data(_maybe_flip(_smooth2d(I_view[:, y_idx, :])))
        im_yz.set_data(_maybe_flip(_smooth2d(I_view[:, :, x_idx])))
    fig.canvas.draw_idle()

    btn_fliplr.on_clicked(_toggle_fliplr)
    btn_rect = shift_rect(btn_rect)

    # ----------------  Smoothing controls (minimal UI)  ----------------
    ax_sigma = plt.axes((btn_x_slider, 0.10, 0.1, 0.03))  # x, y, w, h
    slider_sigma = Slider(ax_sigma, 'σ (px)', 0.0, 6.0, valinit=_smooth["sigma"], valstep=0.1)
    ax_smooth = plt.axes(btn_rect)
    btn_smooth = Button(ax_smooth, 'smooth off')
    def _on_sigma_change(_val):
        _smooth["sigma"] = float(slider_sigma.val)
        if _smooth["on"]:
            # just refresh currently shown data
            im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
            if Nz > 1:
                im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
                im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
            fig.canvas.draw_idle()
    slider_sigma.on_changed(_on_sigma_change)

    def _toggle_smoothing(_event):
        _smooth["on"] = not _smooth["on"]
        btn_smooth.label.set_text('smooth on' if _smooth["on"] else 'smooth off')
        # ⬇️ refresh from I_view so current processing (flatten/log/etc.) is preserved
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
        fig.canvas.draw_idle()

    btn_smooth.on_clicked(_toggle_smoothing)
    btn_rect = shift_rect(btn_rect)

    # ----------------     Flatten (beam-profile removal + DC invariance)     ----------------
    # Uses Q:\QT-Quantum_Optic_Lab\expData\Spectrometer\beam.tif
    flatten_state = {"on": False, "beam": None, "cube": None}
    def _resize_to(img: np.ndarray, shape_xy: tuple[int, int]) -> np.ndarray:
        """Resize 2D img to (Ny, Nx) using scipy if present, otherwise numpy-only bilinear."""
        ny, nx = shape_xy
        if img.shape == (ny, nx):
            return img
        if _HAS_SCIPY_ND:
            try:
                fy = ny / img.shape[0]
                fx = nx / img.shape[1]
                return ndi.zoom(img, (fy, fx), order=1)
            except Exception:
                pass
        # numpy-only bilinear
        y_old, x_old = img.shape
        x_old_coords = np.linspace(0, 1, x_old)
        x_new_coords = np.linspace(0, 1, nx)
        tmp = np.apply_along_axis(lambda row: np.interp(x_new_coords, x_old_coords, row), 1, img)
        y_old_coords = np.linspace(0, 1, y_old)
        y_new_coords = np.linspace(0, 1, ny)
        return np.apply_along_axis(lambda col: np.interp(y_new_coords, y_old_coords, col), 0, tmp)
    def _load_beam_norm() -> np.ndarray:
        """Load beam.tif → 2D normalized (median=1) beam profile, resized to data (Ny,Nx)."""
        if flatten_state["beam"] is not None:
            return flatten_state["beam"]
        beam_path = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer\beam.tif"
        try:
            B = _read_tif_stack(beam_path)
            B = np.asarray(B, dtype=np.float64)
            B = np.squeeze(B)
            if B.ndim == 3 and B.shape[-1] in (3, 4):   # RGB(A) → gray
                B = B[..., :3].mean(axis=-1)
            if B.ndim == 3:                             # multi-frame → average
                B = B.mean(axis=0)
            B = _resize_to(B, (Ny, Nx))
            # Smooth a bit to remove sensor/shot noise in the reference
            try:
                B = ndi.gaussian_filter(B, sigma=3.0)
            except Exception:
                pass
            med = np.median(B[B > 0]) if np.any(B > 0) else 1.0
            B_norm = B / max(med, EPS)
            B_norm = np.clip(B_norm, 1e-3, None)       # avoid divide-by-zero
        except Exception as e:
            print(f"⚠️ beam.tif not loaded ({e}); using unity flat-field.")
            B_norm = np.ones((Ny, Nx), dtype=np.float64)
        flatten_state["beam"] = B_norm
        return B_norm
    def _compute_flat_cube() -> np.ndarray:
        """Return cube with spatial profile removed, DC-invariant, then rescaled to raw kCounts/s."""
        Bn = _load_beam_norm()

        # global reference in kCounts/s (robust)
        raw_pos = I_raw_cube[I_raw_cube > 0]
        ref = float(np.median(raw_pos)) if raw_pos.size else float(np.mean(I_raw_cube))
        if ref <= 0 or not np.isfinite(ref):
            ref = 1.0

        C = np.empty_like(I_raw_cube, dtype=np.float64)
        for k in range(Nz):
            S = I_raw_cube[k].astype(np.float64)
            med = np.median(S[S > 0]) if np.any(S > 0) else S.mean()
            med = med if med > 0 else 1.0
            # DC-invariant per slice, remove beam profile
            C[k] = (S / med) / Bn

        # restore to kCounts/s scale so your old clim remains meaningful
        C *= ref
        return C
    def _apply_flatten(tgt_on: bool | None = None):
        nonlocal I_view
        if tgt_on is None:
            tgt_on = not flatten_state["on"]
        flatten_state["on"] = tgt_on

        if tgt_on:
            if flatten_state["cube"] is None:
                flatten_state["cube"] = _compute_flat_cube()
            C = flatten_state["cube"]
            I_view = np.log10(C + EPS) if log_scale else C
            cbar.set_label("kCounts/s")  # unchanged scale label
            btn_flat.label.set_text("flatten on")
        else:
            I_view = np.log10(I_raw_cube + EPS) if log_scale else I_raw_cube
            cbar.set_label("kCounts/s")
            btn_flat.label.set_text("flatten off")

        # refresh images (no clim changes)
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
        fig.canvas.draw_idle()

    # UI button
    ax_flat = plt.axes(btn_rect)   # x, y, w, h
    btn_flat = Button(ax_flat, 'flatten off')
    btn_flat.on_clicked(lambda _e: _apply_flatten())
    btn_rect = shift_rect(btn_rect)

    # -------   Aggressive flatten: per-slice background (big blur) removal   -------
    aggr_state = {"on": False, "cube": None, "computed_sigma": None}

    def _compute_flat_cube_aggressive(sigma_bg: float = 20.0) -> np.ndarray:
        """
        Strong shading correction per slice:
          C[k] = ( S / median(S) ) / ( G(S, sigma_bg) / median(G(S, sigma_bg)) )
        then rescale to global raw median so clim stays meaningful.
        """
        # reference scale (kCounts/s) — same as normal flatten so ranges match
        raw_pos = I_raw_cube[I_raw_cube > 0]
        ref = float(np.median(raw_pos)) if raw_pos.size else float(np.mean(I_raw_cube))
        if ref <= 0 or not np.isfinite(ref):
            ref = 1.0

        C = np.empty_like(I_raw_cube, dtype=np.float64)
        for k in range(Nz):
            S = I_raw_cube[k].astype(np.float64)

            # per-slice DC normalize
            medS = np.median(S[S > 0]) if np.any(S > 0) else S.mean()
            medS = medS if medS > 0 else 1.0
            Sn = S / medS

            # very smooth background of this slice (fallback if scipy missing)
            if _HAS_SCIPY_ND:
                B = ndi.gaussian_filter(Sn, sigma=sigma_bg, mode="reflect")
            else:
                # simple separable blur using our small Gaussian builder many times
                # approximate a big blur by applying smaller sigma repeatedly
                B = Sn.copy()
                for _ in range(5):
                    B = _smooth2d(B)
            # normalize background to median=1, clamp to avoid /0
            medB = np.median(B[B > 0]) if np.any(B > 0) else 1.0
            Bn = np.clip(B / max(medB, EPS), 1e-3, None)

            C[k] = Sn / Bn

        C *= ref  # back to kCounts/s scale (so your slider/clim remain valid)
        return C

    def _apply_flatten_aggressive(tgt_on: bool | None = None):
        nonlocal I_view
        if tgt_on is None:
            tgt_on = not aggr_state["on"]
        aggr_state["on"] = tgt_on

        if tgt_on:
            # turn normal flatten OFF
            flatten_state["on"] = False
            try:
                btn_flat.label.set_text("flatten off")
            except Exception:
                pass

            sigma_bg = float(getattr(slider_sigma_bg, "val", 20.0))  # ← read slider
            if aggr_state["cube"] is None or aggr_state.get("computed_sigma") != sigma_bg:
                aggr_state["cube"] = _compute_flat_cube_aggressive(sigma_bg=sigma_bg)
                aggr_state["computed_sigma"] = sigma_bg

            C = aggr_state["cube"]
            I_view = np.log10(C + EPS) if log_scale else C
            try:
                btn_flat_aggr.label.set_text(f"flatten++ on (σ={sigma_bg:.0f})")
            except Exception:
                pass
        else:
            I_view = np.log10(I_raw_cube + EPS) if log_scale else I_raw_cube
            try:
                btn_flat_aggr.label.set_text("flatten++ off")
            except Exception:
                pass

        # refresh images (do NOT touch clim)
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
        fig.canvas.draw_idle()

    # Aggressive flatten button
    ax_flat_aggr = plt.axes(btn_rect)
    btn_flat_aggr = Button(ax_flat_aggr, 'flatten++ off')
    btn_flat_aggr.on_clicked(lambda _e: _apply_flatten_aggressive(None))
    btn_rect = shift_rect(btn_rect)

    # ---------   Preset button: sigma=1.7, smooth on, flatten on, Max I=650   ---------

    # --- Preset 1 ---
    ax_preset1 = plt.axes(btn_rect)  # re-use your btn_rect placement
    btn_preset1 = Button(ax_preset1, 'Preset 1')

    def _apply_preset1(_evt=None):
        slider_sigma.set_val(PRESET1_SIGMA)
        _smooth["on"] = True
        try:
            btn_smooth.label.set_text('smooth on')
        except Exception:
            pass

        # AGGRESSIVE flatten ON with preset sigma_bg
        _apply_flatten_aggressive(True)
        _on_sigma_bg_change(PRESET1_SIGMA_BG)

        # vmax
        target_vmax = PRESET1_VMAX
        if hasattr(slider_max, "valmax") and target_vmax > slider_max.valmax:
            slider_max.valmax = target_vmax
        if hasattr(slider_max, "valmin") and target_vmax < slider_max.valmin:
            slider_max.valmin = target_vmax
        slider_max.set_val(target_vmax)

        try:
            txt_max.set_val(f"{target_vmax:.0f}")
        except Exception:
            pass

        # plot height + nudge
        s_plot_h.set_val(PRESET1_PLOT_HEIGHT)
        _nudge(*PRESET1_NUDGE)

        # apply flips based on constants
        try:
            flip_state["ud"] = PRESET1_FLIP_UD
            if 'btn_flipud' in globals() and btn_flipud is not None:
                btn_flipud.label.set_text('flip UD on' if flip_state["ud"] else 'flip UD off')

            flip_state["lr"] = PRESET1_FLIP_LR
            if 'btn_fliplr' in globals() and btn_fliplr is not None:
                btn_fliplr.label.set_text('flip LR on' if flip_state["lr"] else 'flip LR off')
        except Exception:
            pass

        # refresh displays
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_maybe_flip(_smooth2d(I_view[:, y_idx, :])))
            im_yz.set_data(_maybe_flip(_smooth2d(I_view[:, :, x_idx])))

        fig.canvas.draw_idle()

    btn_preset1.on_clicked(_apply_preset1)
    btn_rect = shift_rect(btn_rect)  # move rectangle for stacking

    # --- Preset 2 ---
    ax_preset2 = plt.axes(btn_rect)
    btn_preset2 = Button(ax_preset2, 'Preset 2')

    def _apply_preset2(_evt=None):
        # sigma → 1.7 and smooth ON
        slider_sigma.set_val(1.7)
        _smooth["on"] = True
        try:
            btn_smooth.label.set_text('smooth on')
        except Exception:
            pass

        # AGGRESSIVE flatten ON with sigma_bg=50 (override slider)
        sigma_bg = 5.0
        _apply_flatten_aggressive(True)
        _on_sigma_bg_change(sigma_bg)

        target_vmax = 4000.0
        if hasattr(slider_max, "valmax") and target_vmax > slider_max.valmax:
            slider_max.valmax = target_vmax
        if hasattr(slider_max, "valmin") and target_vmax < slider_max.valmin:
            slider_max.valmin = target_vmax
        slider_max.set_val(target_vmax)

        try:
            txt_max.set_val(f"{target_vmax:.0f}")
        except Exception:
            pass

        fig.canvas.draw_idle()

    btn_preset2.on_clicked(_apply_preset2)
    btn_rect = shift_rect(btn_rect)

    # ----------------    Radio Buttons   ----------------
    colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                 'gray', 'hot', 'jet', 'bone', 'cool', 'spring', 'summer', 'autumn', 'winter']
    radio_ax = plt.axes((btn_rect[0], btn_rect[1]-0.2, btn_rect[2], 0.2), facecolor='lightgray')  # x, y, width, height
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
    btn_rect = shift_rect(btn_rect,dy=-0.25)

    # ----------------    Arrow buttons    ----------------

    NUDGE_STEP = 0.02  # move by 2% of figure per click
    # Place the arrows at the bottom-left control strip
    ax_up = plt.axes((btn_rect[0]+0.015, btn_rect[1],0.015, 0.03))
    ax_left = plt.axes((btn_rect[0], btn_rect[1]-0.03,0.015, 0.03))
    ax_down = plt.axes((btn_rect[0]+0.015, btn_rect[1]-0.06,0.015, 0.03))
    ax_right = plt.axes((btn_rect[0]+0.03, btn_rect[1]-0.03, 0.015, 0.03))

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

    def _make_map_with_cross(x_um: float, y_um: float, map_path: str = MAP_IMAGE_PATH) -> str | None:
        """
        Open map.jpg, draw a cross at (x_um, y_um) in world microns, save to a temp PNG.
        Returns the temp file path, or None if anything fails.
        """
        try:
            base = Image.open(map_path).convert("RGB")
        except Exception as e:
            print(f"⚠️ map image not found or unreadable: {map_path} ({e})")
            return None

        W, H = base.size
        draw = ImageDraw.Draw(base)

        # world→pixel mapping
        mode = MAP_MODE.lower()
        if mode == "center":
            # center at (W/2, H/2), +X right, +Y up (so subtract y offset)
            px = W / 2.0 + x_um * MAP_PX_PER_UM
            py = H / 2.0 - y_um * MAP_PX_PER_UM
        elif mode == "corner":
            cal = _load_map_calib()
            if cal.get("mode", "").lower() == "corner":
                px_per_um_x = cal["px_per_um_x"]
                px_per_um_y = cal["px_per_um_y"]
                xmin_um = cal["xmin_um"]
                ymax_um = cal["ymax_um"]
            else:
                # fallback to hardcoded if no calibration file exists yet
                px_per_um_x = MAP_PX_PER_UM
                px_per_um_y = MAP_PX_PER_UM
                xmin_um = MAP_XMIN_UM
                ymax_um = MAP_YMAX_UM
            # Corner mapping: world (xmin_um, ymax_um) → pixel (0,0); +X→right, +Y→down
            px = (x_um - xmin_um) * px_per_um_x
            py = (ymax_um - y_um) * px_per_um_y
        else:
            print(f"⚠️ Unknown MAP_MODE '{MAP_MODE}', expected 'center' or 'corner'.")
            return None

        # --- If cross would be outside, pad canvas so it remains visible ---
        try:
            margin = OUTSIDE_MARGIN_PX
        except NameError:
            margin = 50  # safe default if constant not defined

        dx_left = int(max(0, margin - px))
        dx_right = int(max(0, px + margin - (W - 1)))
        dy_top = int(max(0, margin - py))
        dy_bottom = int(max(0, py + margin - (H - 1)))

        if dx_left or dx_right or dy_top or dy_bottom:
            newW = W + dx_left + dx_right
            newH = H + dy_top + dy_bottom
            padded = Image.new("RGB", (newW, newH), (255, 255, 255))  # white background
            padded.paste(base, (dx_left, dy_top))
            base = padded
            W, H = newW, newH
            px += dx_left
            py += dy_top
            draw = ImageDraw.Draw(base)  # re-init draw for new image

        # draw cross (BIGGER)
        x0 = px - CROSS_SIZE_PX;
        x1 = px + CROSS_SIZE_PX
        y0 = py - CROSS_SIZE_PX;
        y1 = py + CROSS_SIZE_PX
        draw.line((x0, py, x1, py), fill=CROSS_COLOR, width=CROSS_THICK_PX)
        draw.line((px, y0, px, y1), fill=CROSS_COLOR, width=CROSS_THICK_PX)

        # circle around cross
        r = RING_RADIUS_PX
        bbox = (px - r, py - r, px + r, py + r)
        try:
            draw.ellipse(bbox, outline=CROSS_COLOR, width=RING_THICK_PX)
        except TypeError:
            # Pillow without 'width' support: simulate thicker edge
            for off in range(-(RING_THICK_PX // 2), (RING_THICK_PX // 2) + 1):
                draw.ellipse((bbox[0] - off, bbox[1] - off, bbox[2] + off, bbox[3] + off),
                             outline=CROSS_COLOR)

        # save to temp file
        tmp = tempfile.NamedTemporaryFile(prefix="map_cross_", suffix=".png", delete=False)
        tmp_path = tmp.name
        tmp.close()
        base.save(tmp_path, "PNG")
        return tmp_path

    def _load_map_calib():
        """Return dict with keys mode, px_per_um_x, px_per_um_y, xmin_um, ymax_um if present."""
        if os.path.isfile(MAP_CALIB_PATH):
            try:
                with open(MAP_CALIB_PATH, "r", encoding="utf-8") as f:
                    d = json.load(f)
                return d
            except Exception as e:
                print(f"⚠️ Could not read {MAP_CALIB_PATH}: {e}")
        return {}

    def _save_map_calib(mode, px_per_um_x, px_per_um_y, xmin_um, ymax_um):
        d = {
            "mode": mode,
            "px_per_um_x": float(px_per_um_x),
            "px_per_um_y": float(px_per_um_y),
            "xmin_um": float(xmin_um),
            "ymax_um": float(ymax_um),
        }
        with open(MAP_CALIB_PATH, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2)
        print(f"✅ Saved calibration → {MAP_CALIB_PATH}: {d}")

    def _parse_float(s):
        # accept decimal comma
        return float(str(s).replace(",", "."))

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


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

PIXEL_SIZE_UM = 0.0735  # µm per pixel
CONNECT_SHIFT_UM = 5  # hard-coded stage step (µm)
CIRCLE_RADIUS_UM = 25.0       # current stitching radius
FEATHER_WIDTH_UM = 3.0        # soft edge width; 0 = hard edge
# Crop box in pixels: (y0, y1, x0, x1)  — inclusive/exclusive like NumPy slicing
CROP_PIXELS = (260, 800, 300, 800)   # <- tweak these to your needs

# For connect +X 2,3,6,1,7,8
# For connect +Y 2,3,4,6,1,5

# stash last connect inputs so we can rebuild without re-picking files
CONNECT_STATE = {
    "imgs": None, "offsets": None,
    "Hc": None, "Wc": None, "min_top": None, "min_left": None,
    "um_per_px_x": None, "um_per_px_y": None,
    "center_xy_um": None,  # (cx0_um, cy0_um)
}

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

    _is_switched_2d = False  # True when current dataset was created by _switch_to_2d_dataset

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
                import re
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

    # --- Helpers ---
    import re

    _SHOT_RE = re.compile(r'_#(\d{2})(?!\d)')  # captures 2-digit shot number

    # mapping from shot → (dx_um, dy_um) relative to *center* (origin)
    # NOTE: dy is +s for +Y (up in world), filenames already encode sign.
    SHOT_TO_OFFSET = {
        1: (0, 0),  # O
        2: (-1, -1),  # DL
        3: (0, -1),  # D
        4: (1, -1),  # DR
        5: (1, 0),  # R
        6: (-1, 0),  # L
        7: (-1, 1),  # UL
        8: (0, 1),  # U
        9: (1, 1),  # UR
    }

    def _shot_num_from_name(name: str) -> int | None:
        m = _SHOT_RE.search(name)
        if not m: return None
        try:
            return int(m.group(1))
        except Exception:
            return None

    def place_figure_top(fig=None, x_px=None, y_px=0, relx=0.5, topmost=False):
        import matplotlib.pyplot as plt, time
        fig = fig or plt.gcf()
        mgr = plt.get_current_fig_manager()

        # Force a layout so sizes are known
        try:
            fig.canvas.draw()
            plt.pause(0.01)
        except Exception:
            pass

        # --- TkAgg ---
        try:
            win = mgr.window  # Tk root for this figure
            # compute x if not given: center horizontally
            sw = win.winfo_screenwidth()
            sh = win.winfo_screenheight()
            if x_px is None:
                win.update_idletasks()
                w = win.winfo_width()
                if not w: w = int(fig.get_figwidth() * fig.dpi)
                x_px = max(0, (sw - w) // 2)

            if topmost:
                try:
                    win.wm_attributes('-topmost', 1)
                except Exception:
                    pass

            # Apply now and once again after idle (some WMs nudge it)
            geom = f"+{int(x_px)}+{int(y_px)}"
            win.wm_geometry(geom)
            win.update_idletasks()
            win.after(10, lambda: win.wm_geometry(geom))
            return
        except Exception:
            pass

        # --- Qt5/Qt6 ---
        try:
            win = mgr.window
            # figure width in pixels
            w = int(fig.get_figwidth() * fig.dpi)
            # center horizontally if not provided
            scr = win.screen().availableGeometry()
            if x_px is None:
                x_px = max(0, scr.x() + (scr.width() - w) // 2)
            win.move(int(x_px), int(y_px))
            # Some Qt styles move after show; nudge again shortly after
            fig.canvas.draw()
            plt.pause(0.01)
            win.move(int(x_px), int(y_px))
            if topmost:
                try:
                    win.setWindowFlag(win.window().windowFlags() | 0x00040000)  # Qt.WindowStaysOnTopHint
                    win.show()
                except Exception:
                    pass
            return
        except Exception:
            pass

    def open_files_dialog(filetypes):
        try:
            # Tkinter multi-select
            from tkinter import Tk, filedialog
            root = Tk(); root.withdraw()
            paths = filedialog.askopenfilenames(filetypes=filetypes)
            try: root.destroy()
            except Exception: pass
            return list(paths)
        except Exception:
            return []

    def _tif_to_2d(path: str) -> np.ndarray:
        """Read a TIFF, convert to 2D gray, average frames if multi-page."""
        arr = _read_tif_stack(path)
        arr = np.asarray(arr, dtype=np.float64)
        arr = np.squeeze(arr)
        if arr.ndim == 3 and arr.shape[-1] in (3, 4):      # RGB(A) → gray
            arr = arr[..., :3].mean(axis=-1)
        if arr.ndim == 3:                                   # (Z,Y,X) → mean over Z
            arr = arr.mean(axis=0)
        if arr.ndim != 2:
            raise ValueError(f"Unexpected TIFF shape for {os.path.basename(path)}: {arr.shape}")
        return arr

    def _resize_like(img: np.ndarray, shape_xy: tuple[int, int]) -> np.ndarray:
        """Resize 2D img to (Ny, Nx) — uses your scipy path if available, else numpy bilinear."""
        ny, nx = shape_xy
        if img.shape == (ny, nx):
            return img
        try:
            # leverage your existing helper if present
            return _resize_to(img, (ny, nx))  # defined elsewhere in your file
        except Exception:
            pass
        # numpy-only bilinear
        y0, x0 = img.shape
        x_old = np.linspace(0, 1, x0); x_new = np.linspace(0, 1, nx)
        tmp = np.apply_along_axis(lambda r: np.interp(x_new, x_old, r), 1, img)
        y_old = np.linspace(0, 1, y0); y_new = np.linspace(0, 1, ny)
        return np.apply_along_axis(lambda c: np.interp(y_new, y_old, c), 0, tmp)

    def _load_and_average_tifs(paths: list[str]) -> np.ndarray:
        """Read many TIFFs, resize to first image shape if needed, return 2D average."""
        imgs = []
        ref = None
        for pth in paths:
            im = _tif_to_2d(pth)
            if ref is None:
                ref = im.shape
            else:
                im = _resize_like(im, ref)
            imgs.append(im)
        if not imgs:
            raise RuntimeError("No valid TIFFs were loaded.")
        stack = np.stack(imgs, axis=0)
        return stack.mean(axis=0)

    def _switch_to_2d_dataset(avg2d: np.ndarray, px_um: float | None = None):
        """Replace current data with a single-slice 2D dataset created from avg2d."""
        nonlocal I_raw_cube, I_view, Nx, Ny, Nz, X_, Y_, Z_, extent_xy, extent_xz, extent_yz, _is_switched_2d

        Ny, Nx = avg2d.shape
        Nz = 1

        # use provided px_um if given, else global PIXEL_SIZE_UM (fallback 0.1)
        if px_um is None:
            try:
                px_um = float(PIXEL_SIZE_UM)
            except Exception:
                px_um = 0.1

        # Centered axes in µm
        x_um = (np.arange(Nx) - (Nx - 1) / 2.0) * px_um
        y_um = (np.arange(Ny) - (Ny - 1) / 2.0) * px_um
        X_ = x_um
        Y_ = y_um
        Z_ = np.array([0.0])

        I_raw_cube = avg2d[np.newaxis, ...].astype(np.float64)

        # invalidate caches
        try:
            flatten_state["cube"] = None
        except Exception:
            pass
        try:
            aggr_state["cube"] = None
            aggr_state["computed_sigma"] = None
        except Exception:
            pass

        # refresh pipeline
        _rebuild_I_view_and_refresh()

        extent_xy = [X_[0], X_[-1], Y_[0], Y_[-1]]
        try:
            im_xy.set_extent(extent_xy)
        except Exception:
            pass

        if ax_xz is not None: ax_xz.set_visible(False)
        if ax_yz is not None: ax_yz.set_visible(False)

        try:
            lb = ax_xy.get_position()
            cbar.ax.set_position([lb.x1 + 0.012, lb.y0, 0.018, lb.height])
        except Exception:
            pass

        try:
            ax_xy.set_title(f"XY @ Z={Z_[0]:.2f} µm")
        except Exception:
            pass

        # mark that current dataset is a centered 2D image controlled by PIXEL_SIZE_UM
        _is_switched_2d = True

        # keep slider ranges sane
        try:
            vmin_now = float(I_view.min());
            vmax_now = float(I_view.max())
            if hasattr(slider_max, "valmin"): slider_max.valmin = vmin_now
            if hasattr(slider_max, "valmax"): slider_max.valmax = vmax_now
            slider_max.set_val(min(maxI, vmax_now))
        except Exception:
            pass

        fig.canvas.draw_idle()

    def _current_processed_cube_no_log() -> np.ndarray:
        """
        Start from base (raw or flatten/flatten++), apply calibration if ON,
        then low-pass if ON. (Smoothing & flips are display-only.)
        """
        base = _current_base_cube()                  # your existing helper
        base = _apply_calibration_to_cube(base)      # <-- calibration here
        if hf_state.get("on", False):
            base = _apply_lowpass_cube(base, hf_state.get("cutoff", 0.08))
        return base

    def _apply_display_postproc_for_save(img2d: np.ndarray) -> np.ndarray:
        """
        Apply display-only effects (smoothing, flips) so saved looks like what you see.
        """
        a = img2d
        if _smooth.get("on", False):
            a = _smooth2d(a)  # same smoothing used for display
        a = _maybe_flip(a)
        return a

    def _to_uint16_for_save(a: np.ndarray, vmin=None, vmax=None) -> np.ndarray:
        """
        Map float/integer image to uint16 using current color limits if provided.
        Default: use min/max of the data.
        """
        a = np.asarray(a, dtype=np.float64)
        if vmin is None or vmax is None:
            vmin = float(np.nanmin(a))
            vmax = float(np.nanmax(a))
        if not np.isfinite(vmin): vmin = 0.0
        if not np.isfinite(vmax) or vmax <= vmin:
            vmax = vmin + 1.0
        a = (a - vmin) / (vmax - vmin)
        a = np.clip(a, 0.0, 1.0)
        return (a * 65535.0 + 0.5).astype(np.uint16)

    def _next_save_path(base_path: str, z_idx: int | None = None) -> str:
        """
        Build an incremental path like <stem>_edited[_zNN].tif next to the source.
        """
        folder, name = os.path.split(base_path)
        stem, _ = os.path.splitext(name)
        ztag = f"_z{z_idx+1:02d}" if z_idx is not None else ""
        candidate = os.path.join(folder, f"{stem}_edited{ztag}.tif")
        if not os.path.exists(candidate):
            return candidate
        i = 2
        while True:
            cand = os.path.join(folder, f"{stem}_edited{ztag}({i}).tif")
            if not os.path.exists(cand):
                return cand
            i += 1

    def _save_tif2d(img2d: np.ndarray, path: str):
        """
        Save a single 2D image to TIFF using tifffile if available, else imageio.
        """
        try:
            if _HAS_TIFFFILE:
                tiff.imwrite(path, img2d)
            elif iio is not None:
                iio.imwrite(path, img2d, plugin="TIFF")
            else:
                raise RuntimeError("No TIFF writer available (tifffile/imageio missing).")
        except Exception as e:
            raise RuntimeError(f"Could not save TIFF to '{path}': {e}")

    # -------- Outlier removal (hairs, small spots) --------
    # Tunables (you can tweak later or add sliders)
    OUTLIER_K = 3.0        # strength (threshold = K * sigma of residual via MAD)
    OUTLIER_RADIUS = 4     # grow mask a little (pixels) before fill
    OUTLIER_MIN_AREA = 6   # drop tiny blobs (pixels)

    outlier_state = {"last_raw": None}  # for optional undo later

    def _mad_sigma(a: np.ndarray) -> float:
        med = np.median(a)
        mad = np.median(np.abs(a - med)) + EPS
        return 1.4826 * mad  # Gaussian-equiv

    def _make_outlier_mask2d(img2d: np.ndarray, cutoff: float, k: float) -> tuple[np.ndarray, np.ndarray]:
        """Return (mask, background) where mask marks outliers in |img - lowpass(img)|."""
        bg = _lowpass_fft2d(img2d, cutoff)
        resid = img2d - bg
        s = _mad_sigma(resid)
        thr = max(EPS, k * s)
        mask = np.abs(resid) > thr

        # Clean up mask: open + area filter
        if _HAS_SCIPY_ND:
            se = np.ones((3, 3), dtype=bool)
            mask = ndi.binary_opening(mask, structure=se)
            lbl, n = ndi.label(mask)
            if n > 0:
                sizes = ndi.sum(mask, lbl, index=np.arange(1, n + 1))
                keep = np.isin(lbl, np.where(sizes >= OUTLIER_MIN_AREA)[0] + 1)
                mask = keep
        else:
            # Light-weight cleanup without scipy: 3x3 majority filter & size floor
            from numpy.lib.stride_tricks import sliding_window_view as _swv
            try:
                w = _swv(mask.astype(np.uint8), (3, 3)).sum(axis=(2, 3))
                core = (w[... ] >= 5).astype(bool)
                # pad back to original size
                m = np.zeros_like(mask, bool)
                m[1:-1, 1:-1] = core
                mask = m
            except Exception:
                pass
        return mask, bg

    def _apply_outlier_fill2d(img2d: np.ndarray, mask: np.ndarray, bg: np.ndarray) -> np.ndarray:
        """Replace masked pixels with background; optionally dilate a bit first."""
        if _HAS_SCIPY_ND and OUTLIER_RADIUS > 0:
            mask = ndi.binary_dilation(mask, iterations=int(OUTLIER_RADIUS))
        elif OUTLIER_RADIUS > 0:
            # simple box dilation fallback
            m = mask.astype(np.uint8)
            k = 2 * OUTLIER_RADIUS + 1
            pad = OUTLIER_RADIUS
            p = np.pad(m, pad, mode='edge')
            # sum over kxk window
            win = np.ones((k, k), dtype=np.uint8)
            from numpy.lib.stride_tricks import sliding_window_view as _swv
            s = (_swv(p, (k, k)) * win).sum(axis=(2, 3))
            m2 = np.zeros_like(m, bool)
            m2[...] = (s > 0)
            mask = m2

        out = img2d.copy()
        out[mask] = bg[mask]   # ← “delete to average value in that area”
        return out

    def _remove_outliers_cube(cube: np.ndarray, cutoff: float, k: float) -> tuple[np.ndarray, int]:
        """Process per-slice; return (cleaned_cube, num_pixels_changed)."""
        changed = 0
        if cube.ndim == 2:
            mask, bg = _make_outlier_mask2d(cube, cutoff, k)
            out = _apply_outlier_fill2d(cube, mask, bg)
            changed = int(mask.sum())
            return out, changed
        Nz, Ny, Nx = cube.shape
        out = np.empty_like(cube, dtype=np.float64)
        for i in range(Nz):
            m, bg = _make_outlier_mask2d(cube[i], cutoff, k)
            out[i] = _apply_outlier_fill2d(cube[i], m, bg)
            changed += int(m.sum())
        return out, changed

    def _build_connect_plus_x_mosaic(img0: np.ndarray, imgx: np.ndarray):
        """Rebuild origin + +X mosaic using the *current* PIXEL_SIZE_UM and show it."""
        # resize +X to origin if needed
        if imgx.shape != img0.shape:
            imgx = _resize_like(imgx, img0.shape)

        H, W = img0.shape
        try:
            px_per_um = 1.0 / float(PIXEL_SIZE_UM)
        except Exception:
            px_per_um = 10.0  # fallback (0.1 µm/px)

        # +X shift in pixels — uses your hard-coded stage step CONNECT_SHIFT_UM
        dx_um = float(CONNECT_SHIFT_UM)
        dy_um = 0.0
        dx_px = int(round(dx_um * px_per_um))
        dy_px = int(round(dy_um * px_per_um))

        # canvas that fits both
        min_top = min(0, dy_px)
        max_top = max(0, dy_px)
        min_left = min(0, dx_px)
        max_left = max(0, dx_px)
        Hc = (max_top - min_top) + H
        Wc = (max_left - min_left) + W

        canvas = np.zeros((Hc, Wc), dtype=np.float64)
        counts = np.zeros((Hc, Wc), dtype=np.float64)

        # place origin and +X
        _place_on_canvas(canvas, counts, img0, -min_top, -min_left)
        _place_on_canvas(canvas, counts, imgx, dy_px - min_top, dx_px - min_left)

        mosaic = canvas
        m = counts > 0
        mosaic[m] = canvas[m] / counts[m]

        # push to viewer; let _switch_to_2d_dataset pick up the *current* PIXEL_SIZE_UM
        _switch_to_2d_dataset(mosaic)

    def _build_connect_plus_x_mosaic_from_paths(origin_path: str, plus_x_path: str):
        """Freshly reload origin/+X from disk, rebuild mosaic using current PIXEL_SIZE_UM, and display."""
        # load raw images (no reuse of prior resized arrays)
        img0 = _tif_to_2d(origin_path).astype(np.float64)
        imgx = _tif_to_2d(plus_x_path).astype(np.float64)

        # resize +X to origin shape (fresh)
        if imgx.shape != img0.shape:
            imgx = _resize_like(imgx, img0.shape)

        H, W = img0.shape
        try:
            px_per_um = 1.0 / float(PIXEL_SIZE_UM)  # e.g., 0.2 µm/px → 5 px/µm
        except Exception:
            px_per_um = 10.0  # fallback

        dx_um, dy_um = float(CONNECT_SHIFT_UM), 0.0
        dx_px = int(round(dx_um * px_per_um))
        dy_px = int(round(dy_um * px_per_um))

        # build a brand-new canvas every time
        min_top = min(0, dy_px)
        max_top = max(0, dy_px)
        min_left = min(0, dx_px)
        max_left = max(0, dx_px)
        Hc = (max_top - min_top) + H
        Wc = (max_left - min_left) + W

        canvas = np.zeros((Hc, Wc), dtype=np.float64)
        counts = np.zeros((Hc, Wc), dtype=np.float64)

        # local placer (fresh writes only)
        def _place_on_canvas(canvas, counts, img, top, left):
            Hc, Wc = canvas.shape
            Hi, Wi = img.shape
            top = int(top);
            left = int(left)
            r0 = max(0, top);
            c0 = max(0, left)
            r1 = min(Hc, top + Hi);
            c1 = min(Wc, left + Wi)
            if r1 <= r0 or c1 <= c0: return
            rs = r0 - top;
            cs = c0 - left
            canvas[r0:r1, c0:c1] += img[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]
            counts[r0:r1, c0:c1] += 1

        _place_on_canvas(canvas, counts, img0, -min_top, -min_left)
        _place_on_canvas(canvas, counts, imgx, dy_px - min_top, dx_px - min_left)

        mosaic = canvas
        m = counts > 0
        mosaic[m] = canvas[m] / counts[m]

        # push fresh dataset (this resets processing caches & updates view)
        _switch_to_2d_dataset(mosaic)  # uses current PIXEL_SIZE_UM

    def _build_connect_plus_y_mosaic_from_paths(origin_path: str, plus_y_path: str):
        # load
        img0 = _tif_to_2d(origin_path).astype(np.float64)
        imgy = _tif_to_2d(plus_y_path).astype(np.float64)
        if imgy.shape != img0.shape:
            imgy = _resize_like(imgy, img0.shape)

        H, W = img0.shape

        # coords from names
        def _nf(s):
            return float(str(s).replace(",", "."))

        c0 = _parse_site_center_from_name(os.path.basename(origin_path))
        cy = _parse_site_center_from_name(os.path.basename(plus_y_path))
        if not c0 or not cy:
            raise RuntimeError("Missing Site(...) in filenames for +Y stitch.")
        cx0_um, cy0_um = _nf(c0[0]), _nf(c0[1])
        cxy_um = (_nf(cy[0]), _nf(cy[1]))

        # pixel scale (allow per-axis if you use PIXEL_STATE; fallback to PIXEL_SIZE_UM)
        try:
            px_um_x = float(PIXEL_STATE.get("um_per_px_x", PIXEL_SIZE_UM))
            px_um_y = float(PIXEL_STATE.get("um_per_px_y", PIXEL_SIZE_UM))
        except Exception:
            px_um_x = px_um_y = float(PIXEL_SIZE_UM)

        px_per_um_x = 1.0 / px_um_x
        px_per_um_y = 1.0 / px_um_y

        # offsets from filename coords (world → pixels)
        dx_um = cxy_um[0] - cx0_um
        dy_um = cxy_um[1] - cy0_um
        dx_px = int(round(dx_um * px_per_um_x))
        dy_px = int(round(dy_um * px_per_um_y))  # +µm Y → +rows (down)

        # canvas
        min_top = min(0, dy_px)
        max_top = max(0, dy_px)
        min_left = min(0, dx_px)
        max_left = max(0, dx_px)
        Hc = (max_top - min_top) + H
        Wc = (max_left - min_left) + W
        canvas = np.zeros((Hc, Wc), dtype=np.float64)
        counts = np.zeros((Hc, Wc), dtype=np.float64)

        # place & average
        _place_on_canvas(canvas, counts, img0, -min_top, -min_left)
        _place_on_canvas(canvas, counts, imgy, dy_px - min_top, dx_px - min_left)
        mosaic = canvas
        m = counts > 0
        mosaic[m] = canvas[m] / counts[m]

        # show as 2D dataset and set world extents centered on origin coords
        _switch_to_2d_dataset(mosaic)
        xmin = cx0_um - (Wc * px_um_x) / 2.0
        xmax = cx0_um + (Wc * px_um_x) / 2.0
        ymin = cy0_um - (Hc * px_um_y) / 2.0
        ymax = cy0_um + (Hc * px_um_y) / 2.0
        im_xy.set_extent([xmin, xmax, ymin, ymax])
        ax_xy.set_xlabel("X (µm)");
        ax_xy.set_ylabel("Y (µm)")
        ax_xy.set_title(f"XY @ Site({cx0_um:.2f}, {cy0_um:.2f}) µm  (origin + +Y)")
        fig.canvas.draw_idle()

    # ===== Calibration (flat-field) — hard-coded path =====
    CALIB_TIF_PATH = r"C:\WC\SLM_bmp\Calib\Averaged_calibration.tif"

    calib_state = {
        "on": False,             # toggle for applying calibration
        "gain": None,            # 2D gain map (Ny, Nx)
        "sigma": 15.0,           # blur (px) on the calibration image to avoid imprinting noise
        "clip": (0.25, 4.0),     # clamp gain to avoid extremes (min, max)
    }

    def _ensure_size(img2d: np.ndarray, shape_xy: tuple[int,int]) -> np.ndarray:
        ny, nx = shape_xy
        if img2d.shape == (ny, nx):
            return img2d
        try:
            return _resize_to(img2d, (ny, nx))  # you already have this helper
        except Exception:
            # small bilinear fallback
            y0, x0 = img2d.shape
            x_old = np.linspace(0, 1, x0); x_new = np.linspace(0, 1, nx)
            tmp = np.apply_along_axis(lambda r: np.interp(x_new, x_old, r), 1, img2d)
            y_old = np.linspace(0, 1, y0); y_new = np.linspace(0, 1, ny)
            return np.apply_along_axis(lambda c: np.interp(y_new, y_old, c), 0, tmp)

    def _tif_to_2d(path: str) -> np.ndarray:
        """Read TIFF, convert to gray, average frames if multipage, return 2D float64."""
        arr = _read_tif_stack(path)          # you already have this helper above
        arr = np.asarray(arr, dtype=np.float64)
        arr = np.squeeze(arr)
        if arr.ndim == 3 and arr.shape[-1] in (3, 4):
            arr = arr[..., :3].mean(axis=-1) # RGB(A) → gray
        if arr.ndim == 3:                     # (Z,Y,X) → YX by mean
            arr = arr.mean(axis=0)
        if arr.ndim != 2:
            raise ValueError(f"Unexpected calibration TIFF shape: {arr.shape}")
        return arr

    def _build_gain_from_calibration(cal2d: np.ndarray, sigma: float, clip_range=(0.25, 4.0)) -> np.ndarray:
        """Bright calib ⇒ low gain, dark calib ⇒ high gain."""
        A = np.asarray(cal2d, dtype=np.float64)
        if sigma > 0:
            try:
                import scipy.ndimage as ndi
                A = ndi.gaussian_filter(A, sigma=sigma, mode="reflect")
            except Exception:
                # fallback: a few passes of your numpy smoothing
                for _ in range(3):
                    A = _smooth2d(A)
        pos = A[A > 0]
        ref = float(np.median(pos)) if pos.size else float(np.mean(A))
        if not np.isfinite(ref) or ref <= 0:
            ref = 1.0
        gain = ref / np.clip(A, ref * 1e-6, None)  # inverse shading
        gmin, gmax = clip_range
        gain = np.clip(gain, gmin, gmax)
        return gain

    def _load_calibration_gain_for_current_shape() -> np.ndarray:
        """Load hard-coded calibration TIFF and return gain resized to (Ny,Nx) of current data."""
        if not os.path.isfile(CALIB_TIF_PATH):
            raise FileNotFoundError(f"Calibration TIFF not found:\n{CALIB_TIF_PATH}")
        cal = _tif_to_2d(CALIB_TIF_PATH)
        cal = _ensure_size(cal, (Ny, Nx))
        gain = _build_gain_from_calibration(cal, sigma=calib_state["sigma"], clip_range=calib_state["clip"])
        return gain

    def _apply_calibration_to_cube(base_cube: np.ndarray) -> np.ndarray:
        """Multiply base cube by gain (per-pixel) if calibration is ON."""
        if not calib_state.get("on") or calib_state.get("gain") is None:
            return base_cube
        G = calib_state["gain"]
        if base_cube.ndim == 2:
            return base_cube * G
        return base_cube * G[np.newaxis, :, :]

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

    # --- High-frequency removal (FFT low-pass) ---
    hf_state = {"on": False, "cutoff": 0.03}  # cutoff as fraction of Nyquist (smaller = stronger)

    def _lowpass_fft2d(img2d: np.ndarray, cutoff: float) -> np.ndarray:
        """Apply a circular low-pass in the FFT domain to a 2D image."""
        a = np.asarray(img2d, dtype=np.float64)
        F = np.fft.fftshift(np.fft.fft2(a))
        H, W = a.shape
        cy, cx = H // 2, W // 2
        yy, xx = np.ogrid[:H, :W]
        r = np.sqrt((yy - cy) ** 2 + (xx - cx) ** 2)
        rmax = np.sqrt(cy ** 2 + cx ** 2)
        mask = (r <= cutoff * rmax)
        Ff = F * mask
        out = np.fft.ifft2(np.fft.ifftshift(Ff)).real
        return out

    def _apply_lowpass_cube(cube: np.ndarray, cutoff: float) -> np.ndarray:
        """Apply low-pass per Z-slice. If Nz==1, handles the single slice."""
        if cube.ndim == 2:
            return _lowpass_fft2d(cube, cutoff)
        Nz, Ny, Nx = cube.shape
        out = np.empty_like(cube, dtype=np.float64)
        for k in range(Nz):
            out[k] = _lowpass_fft2d(cube[k], cutoff)
        return out

    def _current_base_cube() -> np.ndarray:
        """Pick the base cube considering flatten/flatten++ states."""
        if aggr_state.get("on") and aggr_state.get("cube") is not None:
            return aggr_state["cube"]
        if flatten_state.get("on") and flatten_state.get("cube") is not None:
            return flatten_state["cube"]
        return I_raw_cube

    def _rebuild_I_view_and_refresh():
        """Rebuild I_view from the current processed cube and refresh all images."""
        nonlocal I_view
        C = _current_processed_cube_no_log()
        I_view = np.log10(C + EPS) if log_scale else C

        # refresh images WITHOUT touching clim/cmap
        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
        if Nz > 1:
            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
        fig.canvas.draw_idle()

    # --- ADD: flip state + helper ---
    flip_state = {"ud": True, "lr": False}

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
        fig, (ax_xy, ax_xz, ax_yz) = plt.subplots(1, 3, figsize=(24, 6))
    else:
        fig, ax_xy = plt.subplots(1, 1, figsize=(24, 12))
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

    # --- Column layout for small buttons ---
    COL_GAP = 0.02  # horizontal gap between columns

    # Column 1 (existing) starts at btn_rect
    btn_rect_col1 = btn_rect  # alias for clarity

    # Column 2 starts to the right of column 1
    col2_x = btn_x + btn_w + COL_GAP
    btn_rect_col2 = (col2_x, btn_y, btn_w, btn_h)

    def shift_rect2(rect, dx=0.0, dy=-0.03):
        x1, y1, w1, h1 = rect
        return x1 + dx, y1 + dy, w1, h1

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

    # ----------------  Pixel size slider (µm/px)  ----------------
    # remembers the most recent connect +X selection
    # remembers the most recent connect +X / +Y selections
    _last_connect_px = {"active": False, "origin_path": None, "plus_x_path": None}
    _last_connect_py = {"active": False, "origin_path": None, "plus_y_path": None}
    _last_connect_view = {"mode": None}  # "plus_x" or "plus_y"

    ax_pix = plt.axes((btn_x_slider, 0.16, 0.1, 0.03))  # x,y,w,h — adjust if it overlaps
    # clamp initial to [0.20, 1.00]
    try:
        _pix_init = float(PIXEL_SIZE_UM)
    except Exception:
        _pix_init = 0.074

    slider_pix = Slider(ax_pix, 'px (µm)', 0.06, 0.08, valinit=_pix_init, valstep=0.0001, valfmt='%.4f')

    def _on_pixel_size_change(val):
        """Update global PIXEL_SIZE_UM and rescale axes/extents for 2D-switched datasets."""
        nonlocal X_, Y_, extent_xy, extent_xz, extent_yz, _is_switched_2d
        global PIXEL_SIZE_UM

        try:
            PIXEL_SIZE_UM = float(val)
        except Exception:
            return

        # If a connect view is active, rebuild it FRESH (no accumulation)
        try:
            if _last_connect_view.get("mode") == "plus_y" and _last_connect_py.get("active"):
                _build_connect_plus_y_mosaic_from_paths(
                    _last_connect_py["origin_path"], _last_connect_py["plus_y_path"]
                )
                print(f"Rebuilt connect +Y (fresh) with px={PIXEL_SIZE_UM:.4f} µm/px.")
                return
            if _last_connect_view.get("mode") == "plus_x" and _last_connect_px.get("active"):
                _build_connect_plus_x_mosaic_from_paths(
                    _last_connect_px["origin_path"], _last_connect_px["plus_x_path"]
                )
                print(f"Rebuilt connect +X (fresh) with px={PIXEL_SIZE_UM:.4f} µm/px.")
                return
        except Exception:
            # fall through to generic rescale if rebuild fails
            pass

        # Only live-rescale displays that were created with _switch_to_2d_dataset (mosaics/averages).
        if not _is_switched_2d:
            # Still update future stitching math via the global; inform quietly:
            print(f"px size set to {PIXEL_SIZE_UM:.2f} µm/px (will affect stitching / future 2D loads).")
            return

        # Recompute centered axes in µm based on new pixel size
        try:
            Ny, Nx = I_view[z_idx].shape
        except Exception:
            Ny, Nx = I_raw_cube.shape[-2], I_raw_cube.shape[-1]

        x_um = (np.arange(Nx) - (Nx - 1) / 2.0) * PIXEL_SIZE_UM
        y_um = (np.arange(Ny) - (Ny - 1) / 2.0) * PIXEL_SIZE_UM
        X_ = x_um
        Y_ = y_um

        # Update extents
        extent_xy = [X_[0], X_[-1], Y_[0], Y_[-1]]
        try:
            im_xy.set_extent(extent_xy)
            ax_xy.set_xlabel("X (µm)");
            ax_xy.set_ylabel("Y (µm)")
            # keep title format; Z stays 0 for switched 2D
            ax_xy.set_title(f"XY @ Z={Z_[0]:.2f} µm")
        except Exception:
            pass

        # If XZ/YZ were visible (unlikely in switched 2D), keep them consistent
        if Nz > 1 and ax_xz is not None and ax_yz is not None:
            extent_xz = [X_[0], X_[-1], Z_[0], Z_[-1]]
            extent_yz = [Y_[0], Y_[-1], Z_[0], Z_[-1]]
            try:
                im_xz.set_extent(extent_xz)
                im_yz.set_extent(extent_yz)
            except Exception:
                pass

        fig.canvas.draw_idle()
        print(f"px size set to {PIXEL_SIZE_UM:.2f} µm/px — display rescaled.")

    slider_pix.on_changed(_on_pixel_size_change)

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

    # -------------  Calibration: load from hard-coded path  -------------
    ax_capply = plt.axes(btn_rect)
    btn_capply = Button(ax_capply, 'calib apply')

    def _handle_calib_apply(_evt=None):
        try:
            G = _load_calibration_gain_for_current_shape()
            calib_state["gain"] = G
            calib_state["on"] = True
            try:
                btn_ctoggle.label.set_text('calib on')
            except Exception:
                pass
            _rebuild_I_view_and_refresh()
            print(f"✅ Calibration loaded from:\n{CALIB_TIF_PATH}")
        except Exception as e:
            print(f"❌ Calibration load failed: {e}")

    btn_capply.on_clicked(_handle_calib_apply)
    btn_rect = shift_rect(btn_rect)

    # -------------  Calibration toggle  -------------
    ax_ctoggle = plt.axes(btn_rect)
    btn_ctoggle = Button(ax_ctoggle, 'calib off')

    def _handle_calib_toggle(_evt=None):
        # Only toggle if a gain exists
        if calib_state.get("gain") is None:
            print("⚠️ No calibration loaded yet. Click 'calib apply' first.")
            return
        calib_state["on"] = not calib_state["on"]
        btn_ctoggle.label.set_text('calib on' if calib_state["on"] else 'calib off')
        _rebuild_I_view_and_refresh()

    btn_ctoggle.on_clicked(_handle_calib_toggle)
    btn_rect = shift_rect(btn_rect)

    # ----------------  Apply calibration to multiple TIFFs (batch)  ----------------
    ax_capply_multi = plt.axes(btn_rect)
    btn_capply_multi = Button(ax_capply_multi, 'apply multiple calib')
    btn_rect = shift_rect(btn_rect)

    def _load_calib_gain_for_shape(shape_xy: tuple[int, int]) -> np.ndarray:
        """
        Load the hard-coded calibration TIFF and build a gain map resized to 'shape_xy'.
        Same logic as _load_calibration_gain_for_current_shape() but independent of current dataset.
        """
        if not os.path.isfile(CALIB_TIF_PATH):
            raise FileNotFoundError(f"Calibration TIFF not found:\n{CALIB_TIF_PATH}")
        cal = _tif_to_2d(CALIB_TIF_PATH)  # 2D float64
        cal = _ensure_size(cal, shape_xy)  # resize to (Ny, Nx)
        gain = _build_gain_from_calibration(
            cal,
            sigma=calib_state.get("sigma", 15.0),
            clip_range=calib_state.get("clip", (0.25, 4.0)),
        )
        return gain

    def _apply_calib_to_array(img2d: np.ndarray, gain2d: np.ndarray) -> np.ndarray:
        """Multiply by per-pixel gain (float64), return float64 image."""
        if img2d.shape != gain2d.shape:
            gain2d = _ensure_size(gain2d, img2d.shape)
        return (np.asarray(img2d, dtype=np.float64) * gain2d)

    def _handle_apply_multiple_calib(_evt=None):
        try:
            # choose multiple TIFF files
            paths = open_files_dialog([("TIFF Files", "*.tif *.tiff")])
            if not paths:
                print("No files selected.")
                return

            # pre-check calibration file existence early
            if not os.path.isfile(CALIB_TIF_PATH):
                print(f"❌ Calibration TIFF not found:\n{CALIB_TIF_PATH}")
                return

            ok, fail = 0, 0
            for path in paths:
                try:
                    img2d = _tif_to_2d(path).astype(np.float64)  # read & flatten to 2D
                    Ny, Nx = img2d.shape
                    G = _load_calib_gain_for_shape((Ny, Nx))  # per-image sized gain
                    corrected = _apply_calib_to_array(img2d, G)

                    # map to uint16 using image min/max so full dynamic range is kept
                    out_u16 = _to_uint16_for_save(corrected)  # vmin/vmax auto from data

                    # build save path like "<stem>_edited.tif", avoiding collisions
                    save_path = _next_save_path(path, None)
                    _save_tif2d(out_u16, save_path)
                    print(f"✅ Calibrated & saved → {save_path}")
                    ok += 1
                except Exception as e:
                    print(f"❌ Failed on {os.path.basename(path)}: {e}")
                    fail += 1

            print(f"Batch complete: {ok} file(s) saved, {fail} failed.")

        except Exception as e:
            print(f"❌ apply multiple calib failed: {e}")

    btn_capply_multi.on_clicked(_handle_apply_multiple_calib)

    # ----------------  Remove outliers (hairs/spots)  ----------------
    ax_rmout = plt.axes(btn_rect)
    btn_rmout = Button(ax_rmout, 'remove outliers')

    def _handle_remove_outliers(_event=None):
        try:
            # Use the current cutoff slider/value if present; else default from hf_state
            cutoff = hf_state.get("cutoff", 0.08)
            k = OUTLIER_K

            # Backup for optional undo
            outlier_state["last_raw"] = I_raw_cube.copy()

            # Operate on RAW cube so downstream (flatten/++) all benefit
            cleaned, nchg = _remove_outliers_cube(I_raw_cube.astype(np.float64), cutoff, k)
            # Write back into raw
            I_raw_cube[:] = cleaned

            # Invalidate processed caches
            try:
                flatten_state["cube"] = None
            except Exception:
                pass
            try:
                aggr_state["cube"] = None
                aggr_state["computed_sigma"] = None
            except Exception:
                pass

            _rebuild_I_view_and_refresh()
            print(f"✅ Outlier removal done: {nchg} pixel(s) replaced (cutoff={cutoff:.3f}, k={k:.1f}).")

        except Exception as e:
            print(f"❌ Outlier removal failed: {e}")

    btn_rmout.on_clicked(_handle_remove_outliers)
    btn_rect = shift_rect(btn_rect)


    # ----------------  Save edited image to new TIFF  ----------------
    ax_save = plt.axes(btn_rect)
    btn_save = Button(ax_save, 'save tif')

    def _handle_save_tif(_event=None):
        try:
            # 1) Build processed (no log), pick current Z
            C = _current_processed_cube_no_log()
            slice2d = C[z_idx] if C.ndim == 3 else C

            # 2) Apply display-only postproc so it matches what you see
            slice2d_view = _apply_display_postproc_for_save(slice2d)

            # 3) Convert to uint16 using current color limits
            #    (use im_xy clim so saved dynamic range matches the view)
            vmin, vmax = im_xy.get_clim()
            out_u16 = _to_uint16_for_save(slice2d_view, vmin=vmin, vmax=vmax)

            # 4) Decide path next to the source file
            base_for_name = filepath if filepath else os.path.join(os.getcwd(), "image.tif")
            save_path = _next_save_path(base_for_name, z_idx if (Nz > 1) else None)

            # 5) Write
            _save_tif2d(out_u16, save_path)
            print(f"✅ Saved edited image → {save_path}")

            # Optional: put path on clipboard (Windows)
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(save_path)
                win32clipboard.CloseClipboard()
            except Exception:
                pass

        except Exception as e:
            print(f"❌ Save failed: {e}")

    btn_save.on_clicked(_handle_save_tif)
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

    # ----------------  Average multiple TIFFs  ----------------
    ax_avg = plt.axes(btn_rect)
    btn_avg = Button(ax_avg, 'avg TIFs')

    def _handle_avg_tifs(_event=None):
        try:
            paths = open_files_dialog([("TIFF Files", "*.tif *.tiff")])
            if not paths:
                print("No files selected.")
                return
            avg2d = _load_and_average_tifs(paths)
            _switch_to_2d_dataset(avg2d)  # adjust pixel size if needed
            print(f"✅ Averaged {len(paths)} TIFF(s).")
        except Exception as e:
            print(f"❌ Averaging failed: {e}")

    btn_avg.on_clicked(_handle_avg_tifs)
    btn_rect = shift_rect(btn_rect)

    # ----------------  Connect only +X to origin  ----------------
    ax_connect_px = plt.axes(btn_rect)
    btn_connect_px = Button(ax_connect_px, 'connect +X')
    btn_rect = shift_rect(btn_rect)

    def _norm_float(x):
        return float(str(x).replace(",", "."))

    def _coord_from_name(path):
        c = _parse_site_center_from_name(os.path.basename(path))
        if not c: return None
        return (_norm_float(c[0]), _norm_float(c[1]))  # (x_um, y_um)

    def _place_on_canvas(canvas, counts, img, top, left):
        Hc, Wc = canvas.shape
        Hi, Wi = img.shape
        top = int(top);
        left = int(left)
        r0 = max(0, top);
        c0 = max(0, left)
        r1 = min(Hc, top + Hi);
        c1 = min(Wc, left + Wi)
        if r1 <= r0 or c1 <= c0:
            return
        rs = r0 - top;
        cs = c0 - left
        canvas[r0:r1, c0:c1] += img[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]
        counts[r0:r1, c0:c1] += 1

    def _connect_plus_x_handler(_evt=None):
        try:
            # 1) Pick ONLY the origin frame
            origin_path = _pick_origin_tif()
            if not origin_path:
                print("Canceled.");
                return
            origin_path = os.path.abspath(origin_path)

            # --- NEW: infer true origin (center) from the selected shot number ---
            name_sel = os.path.basename(origin_path)
            shot = _shot_num_from_name(name_sel)
            if shot in SHOT_TO_OFFSET and shot != 1:
                try:
                    # coords of the selected file
                    c_sel = _parse_site_center_from_name(name_sel)
                    if c_sel:
                        xs, ys, _zs = float(str(c_sel[0]).replace(',', '.')), float(str(c_sel[1]).replace(',', '.')), \
                        c_sel[2]
                        dxs, dys = SHOT_TO_OFFSET[shot]
                        s = float(CONNECT_SHIFT_UM)

                        # center coords = selected - offset (because shot coords are offset from center)
                        cx0_um = xs - dxs * s
                        cy0_um = ys - dys * s

                        print(
                            f"Using inferred center from shot #{shot}: ({cx0_um:.2f}, {cy0_um:.2f}) instead of the selected file.")

                        # Try to swap to a matching _#01 file with those coords (if it exists)
                        folder = os.path.dirname(origin_path)
                        candidates = [f for f in os.listdir(folder) if f.lower().endswith(('.tif', '.tiff'))]

                        # decimal-comma tolerant match
                        def _nf(s):
                            return float(str(s).replace(',', '.'))

                        found_center = None
                        for f in candidates:
                            c = _parse_site_center_from_name(f)
                            sh = _shot_num_from_name(f)
                            if not c or sh != 1:
                                continue
                            if abs(_nf(c[0]) - cx0_um) < 1e-6 and abs(_nf(c[1]) - cy0_um) < 1e-6:
                                found_center = os.path.join(folder, f)
                                break

                        if found_center:
                            origin_path = os.path.abspath(found_center)
                            print(f"Center file found: {os.path.basename(origin_path)}")
                        else:
                            # Keep the computed center for expectations later; handlers below may re-parse from origin_path,
                            # so stash these to override (if you already compute cx0_um/cy0_um later, just reuse these values).
                            # A simple way: set a local override variable via closure or reassign after parsing.
                            pass

                        # You likely parse ctr0 again below; consider overriding it:
                        ctr0 = (cx0_um, cy0_um, c_sel[2] if c_sel and len(c_sel) > 2 else 0.0)

                    else:
                        print(f"⚠️ Could not parse Site(...) in selected filename; skipping shot-based centering.")
                except Exception as _e:
                    print(f"⚠️ Shot-based centering failed: {_e}")

            # 2) Parse origin coords
            ctr0 = _parse_site_center_from_name(os.path.basename(origin_path))
            if not ctr0:
                print("❌ Origin filename missing 'Site(x y z)'.");
                return
            cx0_um, cy0_um = _norm_float(ctr0[0]), _norm_float(ctr0[1])

            # 3) Exact-match +X neighbor in same folder
            folder = os.path.dirname(origin_path)
            all_tifs = [os.path.join(folder, f) for f in os.listdir(folder)
                        if f.lower().endswith((".tif", ".tiff"))]
            coord_map = {}
            for p in all_tifs:
                xy = _coord_from_name(p)
                if xy:
                    coord_map[xy] = os.path.abspath(p)

            s = CONNECT_SHIFT_UM  # hard-coded step (µm)

            target_plus_x = (cx0_um + s, cy0_um)
            plus_x_path = coord_map.get(target_plus_x, None)

            if not plus_x_path:
                print(f"❌ +X neighbor not found at ({target_plus_x[0]:.6f}, {target_plus_x[1]:.6f}) µm.")
                return

            # 4) Load both; resize +X to origin shape if needed
            img0 = _tif_to_2d(origin_path).astype(np.float64)
            imgx = _tif_to_2d(plus_x_path).astype(np.float64)
            if imgx.shape != img0.shape:
                imgx = _resize_like(imgx, img0.shape)

            H, W = img0.shape
            try:
                px_per_um = 1.0 / float(PIXEL_SIZE_UM)  # e.g., 0.1 µm/px → 10 px/µm
            except Exception:
                px_per_um = 10.0

            # 5) Pixel offsets from filename coords (relative to origin)
            dx_um = s
            dy_um = 0.0
            dx_px = int(round(dx_um * px_per_um))
            dy_px = int(round(dy_um * px_per_um))

            # 6) Canvas to fit both images (handles unusual sign just in case)
            min_top = min(0, 0, dy_px)
            max_top = max(0, 0, dy_px)
            min_left = min(0, 0, dx_px)
            max_left = max(0, 0, dx_px)
            Hc = (max_top - min_top) + H
            Wc = (max_left - min_left) + W

            canvas = np.zeros((Hc, Wc), dtype=np.float64)
            counts = np.zeros((Hc, Wc), dtype=np.float64)

            # 7) Place origin and +X (average overlap if any)
            _place_on_canvas(canvas, counts, img0, -min_top, -min_left)
            _place_on_canvas(canvas, counts, imgx, dy_px - min_top, dx_px - min_left)

            mosaic = canvas
            m = counts > 0
            mosaic[m] = canvas[m] / counts[m]

            _last_connect_px["active"] = True
            _last_connect_px["origin_path"] = origin_path
            _last_connect_px["plus_x_path"] = plus_x_path
            _last_connect_view["mode"] = "plus_x"

            _build_connect_plus_x_mosaic_from_paths(origin_path, plus_x_path)
            print(f"✅ Connected origin + +X ({CONNECT_SHIFT_UM:.1f} µm); slider will rebuild fresh.")

        except Exception as e:
            print(f"❌ connect +X failed: {e}")

    btn_connect_px.on_clicked(_connect_plus_x_handler)

    # ----------------  Connect only +Y to origin  ----------------
    ax_connect_py = plt.axes(btn_rect)
    btn_connect_py = Button(ax_connect_py, 'connect +Y')
    btn_rect = shift_rect(btn_rect)  # place it right below "load tif"

    def _connect_plus_y_handler(_evt=None):
        try:
            # 1) Pick ONLY the origin frame
            origin_path = _pick_origin_tif()
            if not origin_path:
                print("Canceled.")
                return
            origin_path = os.path.abspath(origin_path)

            # --- NEW: infer true origin (center) from the selected shot number ---
            name_sel = os.path.basename(origin_path)
            shot = _shot_num_from_name(name_sel)
            if shot in SHOT_TO_OFFSET and shot != 1:
                try:
                    # coords of the selected file
                    c_sel = _parse_site_center_from_name(name_sel)
                    if c_sel:
                        xs, ys, _zs = float(str(c_sel[0]).replace(',', '.')), float(str(c_sel[1]).replace(',', '.')), \
                        c_sel[2]
                        dxs, dys = SHOT_TO_OFFSET[shot]
                        s = float(CONNECT_SHIFT_UM)

                        # center coords = selected - offset (because shot coords are offset from center)
                        cx0_um = xs - dxs * s
                        cy0_um = ys - dys * s

                        print(
                            f"Using inferred center from shot #{shot}: ({cx0_um:.2f}, {cy0_um:.2f}) instead of the selected file.")

                        # Try to swap to a matching _#01 file with those coords (if it exists)
                        folder = os.path.dirname(origin_path)
                        candidates = [f for f in os.listdir(folder) if f.lower().endswith(('.tif', '.tiff'))]

                        # decimal-comma tolerant match
                        def _nf(s):
                            return float(str(s).replace(',', '.'))

                        found_center = None
                        for f in candidates:
                            c = _parse_site_center_from_name(f)
                            sh = _shot_num_from_name(f)
                            if not c or sh != 1:
                                continue
                            if abs(_nf(c[0]) - cx0_um) < 1e-6 and abs(_nf(c[1]) - cy0_um) < 1e-6:
                                found_center = os.path.join(folder, f)
                                break

                        if found_center:
                            origin_path = os.path.abspath(found_center)
                            print(f"Center file found: {os.path.basename(origin_path)}")
                        else:
                            # Keep the computed center for expectations later; handlers below may re-parse from origin_path,
                            # so stash these to override (if you already compute cx0_um/cy0_um later, just reuse these values).
                            # A simple way: set a local override variable via closure or reassign after parsing.
                            pass

                        # You likely parse ctr0 again below; consider overriding it:
                        ctr0 = (cx0_um, cy0_um, c_sel[2] if c_sel and len(c_sel) > 2 else 0.0)

                    else:
                        print(f"⚠️ Could not parse Site(...) in selected filename; skipping shot-based centering.")
                except Exception as _e:
                    print(f"⚠️ Shot-based centering failed: {_e}")

            # 2) Parse origin coords
            ctr0 = _parse_site_center_from_name(os.path.basename(origin_path))
            if not ctr0:
                print("❌ Origin filename missing 'Site(x y z)'.")
                return
            cx0_um = float(str(ctr0[0]).replace(",", "."))
            cy0_um = float(str(ctr0[1]).replace(",", "."))

            # 3) Locate the +Y neighbor in the same folder (exact filename coords)
            folder = os.path.dirname(origin_path)
            all_tifs = [os.path.join(folder, f)
                        for f in os.listdir(folder)
                        if f.lower().endswith((".tif", ".tiff"))]

            def _coord_from_name_local(p):
                c = _parse_site_center_from_name(os.path.basename(p))
                return None if not c else (float(str(c[0]).replace(",", ".")),
                                           float(str(c[1]).replace(",", ".")))

            coord_map = {}
            for p in all_tifs:
                xy = _coord_from_name_local(p)
                if xy:
                    coord_map[xy] = os.path.abspath(p)

            s = CONNECT_SHIFT_UM  # µm

            target_plus_y = (cx0_um, cy0_um + s)
            plus_y_path = coord_map.get(target_plus_y, None)
            if not plus_y_path:
                print(f"❌ +Y neighbor not found at ({target_plus_y[0]:.6f}, {target_plus_y[1]:.6f}) µm.")
                return

            # 4) Load both; resize +Y to origin shape if needed
            img0 = _tif_to_2d(origin_path).astype(np.float64)
            imgy = _tif_to_2d(plus_y_path).astype(np.float64)
            if imgy.shape != img0.shape:
                imgy = _resize_like(imgy, img0.shape)

            H, W = img0.shape
            try:
                px_per_um_x = 1.0 / float(PIXEL_STATE.get("um_per_px_x", PIXEL_SIZE_UM))
                px_per_um_y = 1.0 / float(PIXEL_STATE.get("um_per_px_y", PIXEL_SIZE_UM))
            except Exception:
                px_per_um_x = px_per_um_y = 10.0  # fallback: 0.1 µm/px

            # 5) Pixel offsets (+Y in µm → positive rows/down in pixels)
            dx_um = 0.0
            dy_um = s
            dx_px = int(round(dx_um * px_per_um_x))
            dy_px = int(round(dy_um * px_per_um_y))  # +µm Y → +pixels down

            # 6) Canvas that fits both
            min_top = min(0, dy_px)
            max_top = max(0, dy_px)
            min_left = min(0, dx_px)
            max_left = max(0, dx_px)
            Hc = (max_top - min_top) + H
            Wc = (max_left - min_left) + W

            canvas = np.zeros((Hc, Wc), dtype=np.float64)
            counts = np.zeros((Hc, Wc), dtype=np.float64)

            # 7) Place origin and +Y (average overlaps)
            _place_on_canvas(canvas, counts, img0, -min_top, -min_left)
            _place_on_canvas(canvas, counts, imgy, dy_px - min_top, dx_px - min_left)

            mosaic = canvas
            m = counts > 0
            mosaic[m] = canvas[m] / counts[m]

            # Show mosaic using your existing helper
            _switch_to_2d_dataset(mosaic)

            # World-coordinate extent centered on origin coords
            try:
                px_um_x = float(PIXEL_STATE.get("um_per_px_x", PIXEL_SIZE_UM))
                px_um_y = float(PIXEL_STATE.get("um_per_px_y", PIXEL_SIZE_UM))
            except Exception:
                px_um_x = px_um_y = float(PIXEL_SIZE_UM)

            xmin = cx0_um - (Wc * px_um_x) / 2.0
            xmax = cx0_um + (Wc * px_um_x) / 2.0
            ymin = cy0_um - (Hc * px_um_y) / 2.0
            ymax = cy0_um + (Hc * px_um_y) / 2.0

            try:
                im_xy.set_extent([xmin, xmax, ymin, ymax])
                ax_xy.set_xlabel("X (µm)")
                ax_xy.set_ylabel("Y (µm)")
                ax_xy.set_title(f"XY @ Site({cx0_um:.2f}, {cy0_um:.2f}) µm  (origin + +Y)")
                fig.canvas.draw_idle()
            except Exception:
                pass

            _last_connect_py["active"] = True
            _last_connect_py["origin_path"] = origin_path
            _last_connect_py["plus_y_path"] = plus_y_path
            _last_connect_view["mode"] = "plus_y"

            print(f"✅ Connected origin + +Y ({CONNECT_SHIFT_UM:.1f} µm).")

        except Exception as e:
            print(f"❌ connect +Y failed: {e}")

    btn_connect_py.on_clicked(_connect_plus_y_handler)

    # ----------------    Connect shifts (stitch 5 frames)    ----------------

    def _place_on_canvas_circ(canvas, counts, img, top, left, um_per_px_x, um_per_px_y, radius_um):
        """
        Place only a circular ROI (radius in µm) from 'img' onto 'canvas' at (top,left).
        The circle is centered at the image center. Outside pixels are ignored.
        """
        Hc, Wc = canvas.shape
        Hi, Wi = img.shape
        top = int(top);
        left = int(left)

        # Compute intersection region in canvas coords
        r0 = max(0, top);
        c0 = max(0, left)
        r1 = min(Hc, top + Hi);
        c1 = min(Wc, left + Wi)
        if r1 <= r0 or c1 <= c0:
            return

        # Slice of the image that actually lands on canvas
        rs = r0 - top;
        cs = c0 - left
        sub = img[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]

        # Build circular mask in this subregion (ellipse if px size differs per axis)
        # Circle center = image center in full image coords
        cy = (Hi - 1) / 2.0
        cx = (Wi - 1) / 2.0

        # Pixel radii from µm radius
        ry_px = radius_um / float(um_per_px_y)  # rows ↔ Y
        rx_px = radius_um / float(um_per_px_x)  # cols ↔ X

        # Coordinates for the subregion in full-image index space
        yy, xx = np.ogrid[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]
        # Elliptical metric = 1 at boundary
        mask = ((yy - cy) / ry_px) ** 2 + ((xx - cx) / rx_px) ** 2 <= 1.0
        if not np.any(mask):
            return

        # Accumulate only masked pixels
        sub_masked = np.where(mask, sub, 0.0)
        canvas[r0:r1, c0:c1] += sub_masked
        counts[r0:r1, c0:c1] += mask.astype(np.float64)

    def _place_on_canvas_circ_feather(canvas, wsum, img, top, left,
                                      um_per_px_x, um_per_px_y,
                                      radius_um, feather_um):
        Hc, Wc = canvas.shape
        Hi, Wi = img.shape
        top = int(top);
        left = int(left)

        r0 = max(0, top);
        c0 = max(0, left)
        r1 = min(Hc, top + Hi);
        c1 = min(Wc, left + Wi)
        if r1 <= r0 or c1 <= c0:
            return

        rs = r0 - top;
        cs = c0 - left
        sub = img[rs:rs + (r1 - r0), cs:cs + (c1 - c0)].astype(np.float64)

        cy = (Hi - 1) / 2.0
        cx = (Wi - 1) / 2.0
        ry_core = radius_um / float(um_per_px_y)
        rx_core = radius_um / float(um_per_px_x)
        ry_out = (radius_um + feather_um) / float(um_per_px_y)
        rx_out = (radius_um + feather_um) / float(um_per_px_x)

        yy, xx = np.ogrid[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]
        # normalized radii with respect to outer ellipse
        r_out = np.sqrt(((yy - cy) / ry_out) ** 2 + ((xx - cx) / rx_out) ** 2)
        r_core = np.sqrt(((yy - cy) / ry_core) ** 2 + ((xx - cx) / rx_core) ** 2)

        w = np.zeros_like(sub, dtype=np.float64)
        inside = r_core <= 1.0
        w[inside] = 1.0

        if feather_um > 0:
            band = (r_core > 1.0) & (r_out <= 1.0)
            # cosine ramp over the band using r_out in [r_core..1] mapped to t in [0..1]
            # use normalized parameter s = (r_out - 1*(ry_core/ry_out approx)) / (1 - 1*(ry_core/ry_out))
            # approximation: use linear map from r_core_norm to r_out_norm via r_core/r_out
            # practical simpler ramp: use r_out directly: r_out ∈ [r_core_ratio..1] → t ∈ [0..1]
            r_core_ratio = min(ry_core / ry_out, rx_core / rx_out)  # conservative
            t = (r_out[band] - r_core_ratio) / max(1e-9, (1.0 - r_core_ratio))
            t = np.clip(t, 0.0, 1.0)
            w[band] = 0.5 * (1.0 + np.cos(np.pi * t))  # 1→0 smooth

        canvas[r0:r1, c0:c1] += sub * w
        wsum[r0:r1, c0:c1] += w

    ax_connect = plt.axes(btn_rect)
    btn_connect = Button(ax_connect, 'connect shifts')
    btn_rect = shift_rect(btn_rect)

    def _place_on_canvas(canvas, counts, img, top, left):
        Hc, Wc = canvas.shape
        Hi, Wi = img.shape
        top = int(top);
        left = int(left)
        r0 = max(0, top);
        c0 = max(0, left)
        r1 = min(Hc, top + Hi);
        c1 = min(Wc, left + Wi)
        if r1 <= r0 or c1 <= c0:
            return
        rs = r0 - top;
        cs = c0 - left
        sub = img[rs:rs + (r1 - r0), cs:cs + (c1 - c0)]
        canvas[r0:r1, c0:c1] += sub
        counts[r0:r1, c0:c1] += 1

    def _norm_float(x):
        # normalize strings like "12,3" → 12.3, keep float as-is
        return float(str(x).replace(",", "."))

    def _coord_from_name(path):
        try:
            c = _parse_site_center_from_name(os.path.basename(path))
            if not c: return None
            return (_norm_float(c[0]), _norm_float(c[1]))  # (x_um, y_um)
        except Exception:
            return None

    def _pick_origin_tif() -> str | None:
        """
        Open a file dialog for a single TIFF. Be compatible with both:
          - Utils.Common.open_file_dialog()  # no-arg
          - our fallback open_file_dialog(filetypes=...)
        """
        try:
            # 1) Try the Utils.Common no-arg variant
            path = open_file_dialog()  # may raise TypeError if signature differs
            return path
        except TypeError:
            pass
        except Exception:
            pass

        try:
            # 2) Try our one-arg variant with filetypes kw
            return open_file_dialog(filetypes=[("TIFF Files", "*.tif *.tiff")])
        except TypeError:
            pass
        except Exception:
            pass

        # 3) Final fallback: call Tk directly with filter
        try:
            from tkinter import Tk, filedialog
            root = Tk();
            root.withdraw()
            path = filedialog.askopenfilename(filetypes=[("TIFF Files", "*.tif *.tiff")])
            try:
                root.destroy()
            except Exception:
                pass
            return path
        except Exception:
            return None

    def _find_nearby(coord_map, x_um, y_um, tol_um=0.02):
        """Return path whose (x,y) is within tol_um of (x_um,y_um); else None."""
        for (xx, yy), p in coord_map.items():
            if abs(xx - x_um) <= tol_um and abs(yy - y_um) <= tol_um:
                return p
        return None

    def _connect_shifts_handler(_evt=None):
        try:
            # 0) Start clean (avoid stale center/path from previous runs)
            CONNECT_STATE.update({
                "imgs": None, "offsets": None,
                "Hc": None, "Wc": None,
                "min_top": None, "min_left": None,
                "um_per_px_x": None, "um_per_px_y": None,
                "center_xy_um": None,
            })

            # 1) Pick ONLY the origin frame (#1)
            origin_path = _pick_origin_tif()
            if not origin_path:
                print("Canceled.")
                return
            origin_path = os.path.abspath(origin_path)

            # --- NEW: infer true origin (center) from the selected shot number ---
            name_sel = os.path.basename(origin_path)
            shot = _shot_num_from_name(name_sel)
            if shot in SHOT_TO_OFFSET and shot != 1:
                try:
                    # coords of the selected file
                    c_sel = _parse_site_center_from_name(name_sel)
                    if c_sel:
                        xs, ys, _zs = float(str(c_sel[0]).replace(',', '.')), float(str(c_sel[1]).replace(',', '.')), \
                        c_sel[2]
                        dxs, dys = SHOT_TO_OFFSET[shot]
                        s = float(CONNECT_SHIFT_UM)

                        # center coords = selected - offset (because shot coords are offset from center)
                        cx0_um = xs - dxs * s
                        cy0_um = ys - dys * s

                        print(
                            f"Using inferred center from shot #{shot}: ({cx0_um:.2f}, {cy0_um:.2f}) instead of the selected file.")

                        # Try to swap to a matching _#01 file with those coords (if it exists)
                        folder = os.path.dirname(origin_path)
                        candidates = [f for f in os.listdir(folder) if f.lower().endswith(('.tif', '.tiff'))]

                        # decimal-comma tolerant match
                        def _nf(s):
                            return float(str(s).replace(',', '.'))

                        found_center = None
                        for f in candidates:
                            c = _parse_site_center_from_name(f)
                            sh = _shot_num_from_name(f)
                            if not c or sh != 1:
                                continue
                            if abs(_nf(c[0]) - cx0_um) < 1e-6 and abs(_nf(c[1]) - cy0_um) < 1e-6:
                                found_center = os.path.join(folder, f)
                                break

                        if found_center:
                            origin_path = os.path.abspath(found_center)
                            print(f"Center file found: {os.path.basename(origin_path)}")
                        else:
                            # Keep the computed center for expectations later; handlers below may re-parse from origin_path,
                            # so stash these to override (if you already compute cx0_um/cy0_um later, just reuse these values).
                            # A simple way: set a local override variable via closure or reassign after parsing.
                            pass

                        # You likely parse ctr0 again below; consider overriding it:
                        ctr0 = (cx0_um, cy0_um, c_sel[2] if c_sel and len(c_sel) > 2 else 0.0)

                    else:
                        print(f"⚠️ Could not parse Site(...) in selected filename; skipping shot-based centering.")
                except Exception as _e:
                    print(f"⚠️ Shot-based centering failed: {_e}")

            # 2) Parse origin coords from filename
            ctr0 = _parse_site_center_from_name(os.path.basename(origin_path))
            if not ctr0:
                print("❌ Origin filename missing 'Site(x y z)'.")
                return
            cx0_um, cy0_um = _norm_float(ctr0[0]), _norm_float(ctr0[1])

            # 3) Build a map {(x_um,y_um) -> path} for all TIFFs in the folder
            folder = os.path.dirname(origin_path)
            all_tifs = [os.path.join(folder, f)
                        for f in os.listdir(folder)
                        if f.lower().endswith((".tif", ".tiff"))]

            coord_map = {}
            for p in all_tifs:
                xy = _coord_from_name(p)
                if xy:
                    coord_map[xy] = os.path.abspath(p)

            # 4) Expected coordinates for a 3×3 grid centered at origin (exact match)
            s = CONNECT_SHIFT_UM
            expected = {
                "O(0,0)": (cx0_um + 0 * s, cy0_um + 0 * s),
                "L(-s,0)": (cx0_um - s, cy0_um + 0 * s),
                "R(+s,0)": (cx0_um + s, cy0_um + 0 * s),
                "D(0,-s)": (cx0_um + 0 * s, cy0_um - s),
                "U(0,+s)": (cx0_um + 0 * s, cy0_um + s),
                "DL(-s,-s)": (cx0_um - s, cy0_um - s),
                "DR(+s,-s)": (cx0_um + s, cy0_um - s),
                "UL(-s,+s)": (cx0_um - s, cy0_um + s),
                "UR(+s,+s)": (cx0_um + s, cy0_um + s),
            }

            chosen = {}
            missing = []
            for label, xy in expected.items():
                p = coord_map.get(xy)
                if p:
                    chosen[label] = p
                else:
                    missing.append(label)

            if missing:
                print("❌ Missing neighbors with exact coordinates:", ", ".join(missing))
                print("   Expected files with coordinates:",
                      {k: f"({x:.6f}, {y:.6f}) µm" for k, (x, y) in expected.items()})
                return

            # 5) Load images; resize to origin's shape if needed
            # order here is row-major (bottom → top) so a consistent placement/debug order
            order = ["DL(-s,-s)", "D(0,-s)", "DR(+s,-s)",
                     "L(-s,0)", "O(0,0)", "R(+s,0)",
                     "UL(-s,+s)", "U(0,+s)", "UR(+s,+s)"]
            paths = [chosen[k] for k in order]

            imgs = []
            ref_shape = None
            for pth in paths:
                im = _tif_to_2d(pth).astype(np.float64)
                if ref_shape is None:
                    ref_shape = im.shape
                else:
                    im = _resize_like(im, ref_shape)
                imgs.append(im)

            H, W = imgs[0].shape

            # 6) Compute pixel offsets from exact filename coords (relative to origin)
            try:
                px_per_um = 1.0 / float(PIXEL_SIZE_UM)  # e.g., 0.1 µm/px → 10 px/µm
            except Exception:
                px_per_um = 10.0

            # Different pixel scale for X and Y, and optional Y inversion for origin='lower'
            PIXEL_STATE = PIXEL_STATE if 'PIXEL_STATE' in globals() else {}
            um_per_px_x = PIXEL_SIZE_UM
            um_per_px_y = PIXEL_SIZE_UM
            INVERT_Y = bool(PIXEL_STATE.get("invert_y", False))

            px_per_um_x = 1.0 / um_per_px_x
            px_per_um_y = 1.0 / um_per_px_y

            # small tolerance to swallow filename rounding when deciding “is this the origin?”
            TOL_UM = 1e-3

            offsets = []
            for label, pth in zip(order, paths):
                x_um, y_um = _coord_from_name(pth)
                dx_um = x_um - cx0_um
                dy_um = y_um - cy0_um

                # zero-out tiny numeric noise
                if abs(dx_um) < TOL_UM: dx_um = 0.0
                if abs(dy_um) < TOL_UM: dy_um = 0.0

                dx_px = int(round(dx_um * px_per_um_x))
                dy_px_raw = dy_um * px_per_um_y
                dy_px = -int(round(dy_px_raw)) if INVERT_Y else int(round(dy_px_raw))

                offsets.append((dy_px, dx_px))

                print(f"{label}: dx_um={dx_um:.3f} dy_um={dy_um:.3f}  → dx={dx_px} px, "
                      f"dy={dy_px} px  ← {os.path.basename(pth)}")

            # 7) Expand canvas to fit all frames
            min_top = min(0, min(dy for dy, dx in offsets))
            max_top = max(0, max(dy for dy, dx in offsets))
            min_left = min(0, min(dx for dy, dx in offsets))
            max_left = max(0, max(dx for dy, dx in offsets))

            Hc = (max_top - min_top) + H
            Wc = (max_left - min_left) + W
            canvas = np.zeros((Hc, Wc), dtype=np.float64)
            counts = np.zeros((Hc, Wc), dtype=np.float64)

            # 8) Place and average overlaps — circular ROI only
            for im, (dy, dx) in zip(imgs, offsets):
                _place_on_canvas_circ(
                    canvas, counts, im,
                    dy - min_top, dx - min_left,
                    um_per_px_x, um_per_px_y, CIRCLE_RADIUS_UM
                )

            mosaic = canvas
            m = counts > 0
            mosaic[m] = canvas[m] / counts[m]

            # 9) Display as a single-slice dataset (so all your existing UI works)
            # We already have: cx0_um, cy0_um  # parsed from origin filename
            # and Hc, Wc (canvas height/width in pixels), plus current pixel size
            try:
                px_um = float(PIXEL_SIZE_UM)
            except Exception:
                px_um = 0.1

            # Build extent so that the **figure center** equals (cx0_um, cy0_um)
            xmin = cx0_um - (Wc * px_um) / 2.0
            xmax = cx0_um + (Wc * px_um) / 2.0
            ymin = cy0_um - (Hc * px_um) / 2.0
            ymax = cy0_um + (Hc * px_um) / 2.0

            # Show mosaic and set world-coordinate extent
            _switch_to_2d_dataset(mosaic)  # uses current PIXEL_SIZE_UM for scaling
            extent_xy = [xmin, xmax, ymin, ymax]
            try:
                im_xy.set_extent(extent_xy)
                ax_xy.set_xlabel("X (µm)")
                ax_xy.set_ylabel("Y (µm)")
                ax_xy.set_title(f"XY @ Site({cx0_um:.2f}, {cy0_um:.2f}) µm")
                fig.canvas.draw_idle()
            except Exception:
                pass

            CONNECT_STATE.update({
                "imgs": imgs,
                "offsets": offsets,
                "Hc": Hc, "Wc": Wc,
                "min_top": min_top, "min_left": min_left,
                "um_per_px_x": um_per_px_x,
                "um_per_px_y": um_per_px_y,
                "center_xy_um": (cx0_um, cy0_um),
            })

            # --- Update Max I slider + display clim after stitching ---
            try:
                # Use the currently displayed (processed) data
                vmin_new = float(np.nanmin(I_view))
                vmax_new = float(np.nanmax(I_view))
            except Exception:
                # Fallback to raw mosaic if needed
                vmin_new = float(np.nanmin(mosaic))
                vmax_new = float(np.nanmax(mosaic))

            # Update slider range and set to the new max
            try:
                if 'slider_max' in globals() and slider_max is not None:
                    if hasattr(slider_max, "valmin"): slider_max.valmin = vmin_new
                    if hasattr(slider_max, "valmax"): slider_max.valmax = vmax_new
                    slider_max.set_val(vmax_new)
            except Exception:
                pass

            # Apply clim to all images that exist
            try:
                im_xy.set_clim(vmin_new, vmax_new)
                if Nz > 1:
                    im_xz.set_clim(vmin_new, vmax_new)
                    im_yz.set_clim(vmin_new, vmax_new)
            except Exception:
                pass

            fig.canvas.draw_idle()

            print(f"✅ Connected frames using exact filename coordinates; canvas {Hc}×{Wc} px.")
        except Exception as e:
            print(f"❌ connect shifts failed: {e}")

    btn_connect.on_clicked(_connect_shifts_handler)

    # --- Remove stitching circles ---
    ax_rm_circles = plt.axes(btn_rect)
    btn_rm_circles = Button(ax_rm_circles, 'remove stitching circles')
    btn_rect = shift_rect(btn_rect)

    def _remove_stitching_circles(_evt=None):
        st = CONNECT_STATE
        if not st["imgs"] or not st["offsets"]:
            print("⚠️ No stitched mosaic in memory. Run 'connect shifts' first.")
            return

        Hc, Wc = st["Hc"], st["Wc"]
        canvas = np.zeros((Hc, Wc), dtype=np.float64)
        wsum = np.zeros((Hc, Wc), dtype=np.float64)

        um_per_px_x = float(st["um_per_px_x"])
        um_per_px_y = float(st["um_per_px_y"])

        for im, (dy, dx) in zip(st["imgs"], st["offsets"]):
            _place_on_canvas_circ_feather(
                canvas, wsum, im,
                dy - st["min_top"], dx - st["min_left"],
                um_per_px_x, um_per_px_y,
                CIRCLE_RADIUS_UM, FEATHER_WIDTH_UM
            )

        # finalize: weighted average; leave 0 where no data
        mosaic = np.zeros_like(canvas)
        m = wsum > 0
        mosaic[m] = canvas[m] / wsum[m]

        # show with the same world extents you already compute
        (cx0_um, cy0_um) = st["center_xy_um"]
        px_um_x = um_per_px_x
        px_um_y = um_per_px_y
        xmin = cx0_um - (Wc * px_um_x) / 2.0
        xmax = cx0_um + (Wc * px_um_x) / 2.0
        ymin = cy0_um - (Hc * px_um_y) / 2.0
        ymax = cy0_um + (Hc * px_um_y) / 2.0

        _switch_to_2d_dataset(mosaic)
        try:
            im_xy.set_extent([xmin, xmax, ymin, ymax])
            ax_xy.set_xlabel("X (µm)")
            ax_xy.set_ylabel("Y (µm)")
            ax_xy.set_title(f"XY (seamless) @ Site({cx0_um:.2f}, {cy0_um:.2f}) µm")
            fig.canvas.draw_idle()
        except Exception:
            pass

        print(f"✅ Rebuilt mosaic with feathered seams (feather={FEATHER_WIDTH_UM:.2f} µm).")

    btn_rm_circles.on_clicked(_remove_stitching_circles)

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

    # ----------------  Low-pass (remove high-frequency) toggle  ----------------
    ax_lowpass = plt.axes(btn_rect)
    btn_lowpass = Button(ax_lowpass, 'lowpass off')

    def _toggle_lowpass(_event):
        hf_state["on"] = not hf_state["on"]
        try:
            btn_lowpass.label.set_text('lowpass on' if hf_state["on"] else 'lowpass off')
        except Exception:
            pass
        _rebuild_I_view_and_refresh()

    btn_lowpass.on_clicked(_toggle_lowpass)
    btn_rect = shift_rect(btn_rect)

    # ----------------  Low-pass cutoff slider  ----------------
    # Range: 0.01 (strong smoothing) .. 0.30 (very gentle)
    ax_cutoff = plt.axes((btn_x_slider, 0.08, 0.1, 0.03))  # x,y,w,h — adjust if it overlaps
    slider_cutoff = Slider(ax_cutoff, 'cutoff', 0.01, 0.30, valinit=hf_state["cutoff"], valstep=0.001)

    def _on_cutoff_change(val):
        hf_state["cutoff"] = float(val)
        # If low-pass is ON, immediately re-run the pipeline
        if hf_state.get("on", False):
            _rebuild_I_view_and_refresh()
        # Optional: show the value on the button label when ON
        try:
            if hf_state.get("on", False):
                btn_lowpass.label.set_text(f'lowpass on  c={val:.3f}')
            else:
                btn_lowpass.label.set_text('lowpass off')
        except Exception:
            pass

    slider_cutoff.on_changed(_on_cutoff_change)


    # ----------------    Flip Up/Down toggle button    ----------------
    ax_flipud = plt.axes(btn_rect)
    btn_flipud = Button(ax_flipud, 'flip UD on')

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
        _rebuild_I_view_and_refresh()

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
        _rebuild_I_view_and_refresh()

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

    # ----------------    Radio Buttons (Column 2)   ----------------
    colormaps = ['viridis', 'plasma', 'inferno', 'magma', 'cividis',
                 'gray', 'hot', 'jet', 'bone', 'cool', 'spring', 'summer', 'autumn', 'winter']

    # Put radio panel in column 2, sized a bit taller (0.22) to fit items
    radio_ax = plt.axes((btn_rect_col2[0], btn_rect_col2[1] - 0.2, btn_rect_col2[2], 0.22),
                        facecolor='lightgray')
    radio = RadioButtons(radio_ax, colormaps, active=0)

    # Apply default cmap initially
    im_xy.set_cmap('jet')
    if Nz > 1:
        im_xz.set_cmap('jet')
        im_yz.set_cmap('jet')

    def change_colormap(label):
        im_xy.set_cmap(label)
        if Nz > 1:
            im_xz.set_cmap(label)
            im_yz.set_cmap(label)
        fig.canvas.draw_idle()

    radio.on_clicked(change_colormap)

    # advance column-2 cursor below the radio panel
    btn_rect_col2 = shift_rect2(btn_rect_col2, dy=-0.25)

    # ----------------    Arrow buttons    ----------------

    NUDGE_STEP = 0.02  # move by 2% of figure per click
    # Place the arrows at the bottom-left control strip
    ax_up = plt.axes((btn_rect_col2[0]+0.015, btn_rect_col2[1],0.015, 0.03))
    ax_left = plt.axes((btn_rect_col2[0], btn_rect_col2[1]-0.03,0.015, 0.03))
    ax_down = plt.axes((btn_rect_col2[0]+0.015, btn_rect_col2[1]-0.06,0.015, 0.03))
    ax_right = plt.axes((btn_rect_col2[0]+0.03, btn_rect_col2[1]-0.03, 0.015, 0.03))

    btn_rect_col2 = shift_rect2(btn_rect_col2,dy=-0.11)

    btn_up = Button(ax_up, '↑')
    btn_left = Button(ax_left, '←')
    btn_down = Button(ax_down, '↓')
    btn_right = Button(ax_right, '→')

    _arrow_axes = [ax_up, ax_left, ax_down, ax_right]

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

    # ----------------  Hide/Show colormap + arrows (Column 2)  ----------------
    ax_toggle_ui = plt.axes(btn_rect_col2)
    btn_toggle_ui = Button(ax_toggle_ui, 'hide UI')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    _ui_state = {"shown": True}

    def _set_colormap_and_arrows_visible(flag: bool):
        try:
            radio_ax.set_visible(flag)
        except Exception:
            pass
        try:
            for _ax in _arrow_axes:
                if _ax is not None:
                    _ax.set_visible(flag)
        except Exception:
            pass
        try:
            fig.canvas.draw_idle()
        except Exception:
            pass

    def _toggle_ui(_evt=None):
        _ui_state["shown"] = not _ui_state["shown"]
        _set_colormap_and_arrows_visible(_ui_state["shown"])
        try:
            btn_toggle_ui.label.set_text('hide UI' if _ui_state["shown"] else 'show UI')
        except Exception:
            pass

    btn_toggle_ui.on_clicked(_toggle_ui)

    # ----------------  Load TIFF (Column 2, below 'hide UI')  ----------------
    ax_load_tif = plt.axes(btn_rect_col2)
    btn_load_tif = Button(ax_load_tif, 'load tif')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _handle_load_tif(_evt=None):
        try:
            path = _pick_origin_tif()  # compatible picker (Utils.Common or Tk)
            if not path:
                print("Canceled.")
                return
            path = os.path.abspath(path)

            # Read as 2D (RGB→gray, multipage→mean)
            img2d = _tif_to_2d(path).astype(np.float64)

            # Show as a single-slice dataset, using current PIXEL_SIZE_UM
            _switch_to_2d_dataset(img2d)

            # Make the title/file name obvious
            try:
                ax_xy.set_title(os.path.basename(path))
            except Exception:
                pass

            # If you track last connect +X, disable it so px slider won't rebuild that
            try:
                _last_connect_px["active"] = False
                _last_connect_px["origin_path"] = None
                _last_connect_px["plus_x_path"] = None
            except Exception:
                pass

            fig.canvas.draw_idle()
            print(f"✅ Loaded TIFF → {path}")

        except Exception as e:
            print(f"❌ load tif failed: {e}")

    btn_load_tif.on_clicked(_handle_load_tif)

    # ----------------  Crop (Column 2, below 'load tif')  ----------------
    ax_crop = plt.axes(btn_rect_col2)
    btn_crop = Button(ax_crop, 'crop')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _handle_crop(_evt=None):
        nonlocal I_raw_cube, I_view, Nx, Ny, Nz, X_, Y_, Z_, extent_xy, extent_xz, extent_yz, z_idx, x_idx, y_idx, _is_switched_2d
        try:
            y0, y1, x0, x1 = CROP_PIXELS
            # clamp & validate
            H, W = I_raw_cube.shape[-2], I_raw_cube.shape[-1]
            y0 = max(0, min(H - 1, int(y0)));
            y1 = max(y0 + 1, min(H, int(y1)))
            x0 = max(0, min(W - 1, int(x0)));
            x1 = max(x0 + 1, min(W, int(x1)))

            # slice every Z the same way
            if I_raw_cube.ndim == 3:
                I_raw_cube = I_raw_cube[:, y0:y1, x0:x1]
            else:  # safety (should always be Nz×Ny×Nx)
                I_raw_cube = I_raw_cube

            # recompute sizes
            Nz, Ny, Nx = I_raw_cube.shape

            # invalidate processing caches
            try:
                flatten_state["cube"] = None
            except Exception:
                pass
            try:
                aggr_state["cube"] = None
                aggr_state["computed_sigma"] = None
            except Exception:
                pass

            # rebuild axes centered using current pixel size
            px = float(PIXEL_SIZE_UM)
            X_ = (np.arange(Nx) - (Nx - 1) / 2.0) * px
            Y_ = (np.arange(Ny) - (Ny - 1) / 2.0) * px
            # keep same Z_ as before if available, else zeros
            try:
                Z_ = Z_ if Z_.size == Nz else np.linspace(0, 0, Nz)
            except Exception:
                Z_ = np.linspace(0, 0, Nz)

            # refresh view buffer and images (no clim change)
            I_view = np.log10(I_raw_cube + EPS) if log_scale else I_raw_cube

            # --- Update Max I slider + display clim after crop ---
            vmin_new = float(np.nanmin(I_view))
            vmax_new = float(np.nanmax(I_view))

            # Update the slider range and value
            try:
                if hasattr(slider_max, "valmin"): slider_max.valmin = vmin_new
                if hasattr(slider_max, "valmax"): slider_max.valmax = vmax_new
                # Set slider to the new max so its UI reflects current image
                slider_max.set_val(vmax_new)
            except Exception:
                pass

            # Apply new clim to all displayed images
            try:
                im_xy.set_clim(vmin_new, vmax_new)
                if Nz > 1:
                    im_xz.set_clim(vmin_new, vmax_new)
                    im_yz.set_clim(vmin_new, vmax_new)
            except Exception:
                pass

            # update extents
            extent_xy = [X_[0], X_[-1], Y_[0], Y_[-1]]
            extent_xz = [X_[0], X_[-1], Z_[0], Z_[-1]] if Nz > 1 else extent_xy
            extent_yz = [Y_[0], Y_[-1], Z_[0], Z_[-1]] if Nz > 1 else extent_xy

            im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
            im_xy.set_extent(extent_xy)
            ax_xy.set_title(f"XY @ Z={Z_[z_idx]:.2f} µm")
            ax_xy.set_xlabel("X (µm)");
            ax_xy.set_ylabel("Y (µm)")

            if Nz > 1:
                im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
                im_xz.set_extent(extent_xz)
                ax_xz.set_title(f"XZ @ Y={Y_[y_idx]:.2f} µm")

                im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
                im_yz.set_extent(extent_yz)
                ax_yz.set_title(f"YZ @ X={X_[x_idx]:.2f} µm")

            fig.canvas.draw_idle()
            print(f"✅ Cropped to (y:{y0}:{y1}, x:{x0}:{x1}) → shape {I_raw_cube.shape[-2]}×{I_raw_cube.shape[-1]} px.")

            # mark as switched 2D dataset layout if Nz==1 for consistent rescaling
            _is_switched_2d = (Nz == 1)

        except Exception as e:
            print(f"❌ crop failed: {e}")

    btn_crop.on_clicked(_handle_crop)

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

    place_figure_top(fig)  # appear higher on the monitor

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


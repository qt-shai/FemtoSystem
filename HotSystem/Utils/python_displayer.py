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
from matplotlib.patches import Polygon
import imageio.v3 as iio  # needs imageio-ffmpeg installed

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
SCALE_MIN = 0.0
# SCALE_MAX = 9000.0
SCALE_MAX = 3000.0
PIXEL_SIZE_UM = 0.0735  # µm per pixel
CONNECT_SHIFT_UM = 5  # hard-coded stage step (µm)
CIRCLE_RADIUS_UM = 25.0       # current stitching radius
FEATHER_WIDTH_UM = 3.0        # soft edge width; 0 = hard edge
# Crop box in pixels: (y0, y1, x0, x1)  — inclusive/exclusive like NumPy slicing
CROP_PIXELS = (260, 800, 300, 800)   # <- tweak these to your needs
PROFILE_STATE = {"points_um": None}
PROFILE_TEMPLATE = {"d0_um": None, "d1_um": None}  # tuples (dx, dy)

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
MAP_IMAGE_PATH = r"c:\WC\HotSystem\map.jpg"     # path to your site map image
MAP_MODE = "corner"  # "center" or "corner"
MAP_CALIB_PATH = r"c:\WC\HotSystem\Utils\map_calibration.json"

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

# --- top-level helpers for CLI "multicalib" mode (no viewer needed) ---

def _resize_to_shape_numpy(img: np.ndarray, ny: int, nx: int) -> np.ndarray:
    """Bilinear resize (numpy-only) to (ny, nx)."""
    if img.shape == (ny, nx):
        return img
    y_old, x_old = img.shape
    x_old_coords = np.linspace(0, 1, x_old)
    x_new_coords = np.linspace(0, 1, nx)
    tmp = np.apply_along_axis(lambda row: np.interp(x_new_coords, x_old_coords, row), 1, img)
    y_old_coords = np.linspace(0, 1, y_old)
    y_new_coords = np.linspace(0, 1, ny)
    return np.apply_along_axis(lambda col: np.interp(y_new_coords, y_old_coords, col), 0, tmp)

def _read_tif_2d(path: str) -> np.ndarray:
    """Read TIFF and return a 2D float64 image (RGB→gray, multipage→mean)."""
    try:
        import tifffile as tiff
        arr = tiff.imread(path)
    except Exception:
        try:
            import imageio.v3 as iio
            arr = iio.imread(path, index=None)
        except Exception as e:
            raise RuntimeError("Need tifffile or imageio.v3 to read TIFFs") from e
    a = np.asarray(arr, dtype=np.float64)
    a = np.squeeze(a)
    if a.ndim == 3 and a.shape[-1] in (3, 4):
        a = a[..., :3].mean(axis=-1)
    if a.ndim == 3:
        a = a.mean(axis=0)
    if a.ndim != 2:
        raise ValueError(f"Unexpected TIFF shape for {os.path.basename(path)}: {a.shape}")
    return a

def _save_tif_u16(path: str, img2d_u16: np.ndarray) -> None:
    try:
        import tifffile as tiff
        tiff.imwrite(path, img2d_u16)
    except Exception:
        import imageio.v3 as iio
        iio.imwrite(path, img2d_u16, plugin="TIFF")

def _to_u16(a: np.ndarray, vmin=None, vmax=None) -> np.ndarray:
    a = np.asarray(a, dtype=np.float64)
    if vmin is None or vmax is None:
        vmin = float(np.nanmin(a))
        vmax = float(np.nanmax(a))
    if not np.isfinite(vmin): vmin = 0.0
    if not np.isfinite(vmax) or vmax <= vmin: vmax = vmin + 1.0
    a = (a - vmin) / (vmax - vmin)
    a = np.clip(a, 0.0, 1.0)
    return (a * 65535.0 + 0.5).astype(np.uint16)

def _next_save_path(base_path: str) -> str:
    folder, name = os.path.split(base_path)
    stem, _ = os.path.splitext(name)
    candidate = os.path.join(folder, f"{stem}_edited.tif")
    if not os.path.exists(candidate):
        return candidate
    i = 2
    while True:
        cand = os.path.join(folder, f"{stem}_edited({i}).tif")
        if not os.path.exists(cand):
            return cand
        i += 1

def run_multicalib_cli(calib_path: str | None = None):
    """
    Batch-apply calibration to multiple TIFFs and exit. Mirrors the 'apply multiple calib' button.
    """
    # 1) calibration path (use the same default you hard-coded in the viewer)
    if calib_path is None:
        calib_path = r"C:\WC\SLM_bmp\Calib\Averaged_calibration.tif"
    if not os.path.isfile(calib_path):
        print(f"❌ Calibration TIFF not found:\n{calib_path}")
        return

    # 2) choose files
    try:
        from tkinter import Tk, filedialog
        root = Tk(); root.withdraw()
        paths = filedialog.askopenfilenames(title="Select TIFFs to calibrate", filetypes=[("TIFF Files", "*.tif *.tiff")])
        try: root.destroy()
        except Exception: pass
    except Exception:
        print("❌ Could not open file dialog.")
        return

    if not paths:
        print("No files selected.")
        return

    # 3) load calibration as 2D and normalize to median=1
    Cal = _read_tif_2d(calib_path)
    pos = Cal[Cal > 0]
    ref = float(np.median(pos)) if pos.size else float(np.mean(Cal))
    if not np.isfinite(ref) or ref <= 0: ref = 1.0
    Cal = Cal / ref
    Cal = np.clip(Cal, 1e-3, None)  # avoid divide-by-zero

    ok = fail = 0
    for p in paths:
        try:
            img = _read_tif_2d(p)
            Ny, Nx = img.shape
            cal = _resize_to_shape_numpy(Cal, Ny, Nx)
            corrected = img / cal
            out = _to_u16(corrected)  # scale to full dynamic range of each image
            save_path = _next_save_path(p)
            _save_tif_u16(save_path, out)
            print(f"✅ {os.path.basename(p)} → {os.path.basename(save_path)}")
            ok += 1
        except Exception as e:
            print(f"❌ Failed on {os.path.basename(p)}: {e}")
            fail += 1

    print(f"Batch complete: {ok} saved, {fail} failed.")


def display_all_z_slices(filepath=None, minI=None, maxI=None, log_scale=False, data=None):
    """
        If 'filepath' ends with .tif/.tiff, read it as (Z,Y,X) stack and view as Z-slices.
        Otherwise, keep the original CSV behavior.
        """

    _is_switched_2d = False  # True when current dataset was created by _switch_to_2d_dataset

    # --- Helpers for TIFF reading ---
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

    # ===== Gain Calibration (flat-field) — hard-coded path =====
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
        fig, ax_xy = plt.subplots(1, 1, figsize=(30, 14)) # FIGURE SIZE
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

    # Column 3 starts to the right of column 2
    col3_x = col2_x + btn_w + COL_GAP
    btn_rect_col3 = (col3_x, btn_y, btn_w, btn_h)

    def shift_rect3(rect, dx=0.0, dy=-0.03):
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
        # Grab the current images (must exist on-screen)
        im_xy_obj = globals().get("im_xy", None)
        if im_xy_obj is None:
            print("⚠️ No im_xy found; nothing to copy.")
            return

        # Pull visual state directly from the artists
        data_xy = np.array(im_xy_obj.get_array())
        extent_xy = list(im_xy_obj.get_extent())
        origin_xy = getattr(im_xy_obj, "origin", "upper")
        cmap = im_xy_obj.get_cmap()
        vmin, vmax = im_xy_obj.get_clim()

        im_xz_obj = globals().get("im_xz", None)
        im_yz_obj = globals().get("im_yz", None)

        show_xz = (Nz > 1) and (im_xz_obj is not None)
        show_yz = (Nz > 1) and (im_yz_obj is not None)

        num_plots = 1 + int(show_xz) + int(show_yz)

        fig_copy, axs = plt.subplots(
            1, num_plots, figsize=(4 * num_plots, 4), dpi=150,
            gridspec_kw={"width_ratios": [1] * num_plots, "wspace": 0.4}
        )
        axs = np.atleast_1d(axs)

        im_list = []

        # --- XY replot (exactly as on screen) ---
        im1 = axs[0].imshow(data_xy, extent=extent_xy, origin=origin_xy,
                            aspect='equal', cmap=cmap, vmin=vmin, vmax=vmax)
        axs[0].set_title(ax_xy.get_title())
        axs[0].set_xlabel(ax_xy.get_xlabel())
        axs[0].set_ylabel(ax_xy.get_ylabel())
        im_list.append(im1)

        idx = 1

        # --- XZ (if present) ---
        if show_xz:
            data_xz = np.array(im_xz_obj.get_array())
            extent_xz = list(im_xz_obj.get_extent())
            origin_xz = getattr(im_xz_obj, "origin", "upper")
            im2 = axs[idx].imshow(data_xz, extent=extent_xz, origin=origin_xz,
                                  aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
            axs[idx].set_title(ax_xz.get_title())
            axs[idx].set_xlabel(ax_xz.get_xlabel())
            axs[idx].set_ylabel(ax_xz.get_ylabel())
            im_list.append(im2)
            idx += 1

        # --- YZ (if present) ---
        if show_yz:
            data_yz = np.array(im_yz_obj.get_array())
            extent_yz = list(im_yz_obj.get_extent())
            origin_yz = getattr(im_yz_obj, "origin", "upper")
            im3 = axs[idx].imshow(data_yz, extent=extent_yz, origin=origin_yz,
                                  aspect='auto', cmap=cmap, vmin=vmin, vmax=vmax)
            axs[idx].set_title(ax_yz.get_title())
            axs[idx].set_xlabel(ax_yz.get_xlabel())
            axs[idx].set_ylabel(ax_yz.get_ylabel())
            im_list.append(im3)

        # --- Shared colorbar ---
        cbar_ax = fig_copy.add_axes([0.92, 0.15, 0.015, 0.7])
        fig_copy.colorbar(im_list[0], cax=cbar_ax, label="kCounts/s")

        # --- Copy PNG → DIB to clipboard (Windows) ---
        buf = io.BytesIO()
        fig_copy.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        image = Image.open(buf)

        output = io.BytesIO()
        image.convert("RGB").save(output, "BMP")
        data = output.getvalue()[14:]  # skip BMP header, keep DIB
        output.close()

        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
        win32clipboard.CloseClipboard()

        plt.close(fig_copy)
        print("Copied graph with colorbar to clipboard (world coords preserved).")

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

    # ----------------    Cal map 2 files (pick two files → world coords; click two pixels)    ----------------
    ax_calmap2 = plt.axes(btn_rect)
    btn_calmap2 = Button(ax_calmap2, 'Cal map 2 files')
    btn_rect = shift_rect(btn_rect)

    def _calibrate_map_from_files(_evt=None):
        # 1) Load base image
        try:
            base = Image.open(MAP_IMAGE_PATH).convert("RGB")
        except Exception as e:
            print(f"⚠️ map image not found/unreadable: {MAP_IMAGE_PATH} ({e})")
            return

        # 2) Choose two files; parse Site(x,y,...) from file names
        try:
            paths = open_files_dialog([("TIFF Files", "*.tif *.tiff"), ("All Files", "*.*")])
        except Exception as e:
            print(f"❌ File chooser error: {e}")
            return

        if not paths or len(paths) < 2:
            print("❌ Calibration aborted: please select at least TWO files.")
            return

        f1, f2 = os.path.abspath(paths[0]), os.path.abspath(paths[1])
        fname1, fname2 = os.path.basename(f1), os.path.basename(f2)
        ctr1 = _parse_site_center_from_name(fname1)
        ctr2 = _parse_site_center_from_name(fname2)

        if not ctr1 or not ctr2:
            print("❌ Could not parse Site(x,y) from one or both filenames.")
            print(f"   f1: {fname1} -> {ctr1}")
            print(f"   f2: {fname2} -> {ctr2}")
            return

        X1, Y1, _Z1 = ctr1
        X2, Y2, _Z2 = ctr2
        print(f"[Cal] From files: P1 Site=({X1:.3f}, {Y1:.3f}) ← {fname1}")
        print(f"[Cal] From files: P2 Site=({X2:.3f}, {Y2:.3f}) ← {fname2}")

        # 3) Let the user LEFT-click the two corresponding pixels (P1 then P2)
        figC, axC = plt.subplots(1, 1, figsize=(9, 9))  # bigger map
        H, W = base.size[1], base.size[0]
        axC.imshow(base, origin='upper')
        axC.set_xlim(0, W);
        axC.set_ylim(H, 0)
        axC.set_title(
            "Calibration (2 files): LEFT-click TWO pixels (P1 then P2).\n"
            "Tip: turn off pan/zoom in the toolbar. Press Esc to cancel.",
            fontsize=11
        )

        # Show chosen filenames on the figure
        try:
            axC.text(0.01, 0.99, f"P1: {fname1}\nP2: {fname2}",
                     transform=axC.transAxes, va='top', ha='left',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'), fontsize=9, zorder=5)
        except Exception:
            pass

        figC.canvas.draw_idle()

        # Ensure toolbar not in pan/zoom
        try:
            mgr = plt.get_current_fig_manager()
            tb = getattr(mgr, "toolbar", None)
            if tb and getattr(tb, "mode", ""):
                if "pan" in tb.mode:
                    tb.pan()
                elif "zoom" in tb.mode:
                    tb.zoom()
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
            if ev.button != 1: return
            if ev.xdata is None or ev.ydata is None: return
            clicks.append((ev.xdata, ev.ydata))
            axC.plot(ev.xdata, ev.ydata, 'rx', markersize=12, mew=2)
            figC.canvas.draw_idle()

        cid = figC.canvas.mpl_connect('button_press_event', _on_click)

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

        # 4) Compute calibration (corner mode)
        if (X2 - X1) == 0 or (Y1 - Y2) == 0:
            print("❌ Degenerate inputs; need points with different X and Y.")
            return

        px_per_um_x = (x2 - x1) / (X2 - X1)
        px_per_um_y = (y2 - y1) / (Y1 - Y2)  # Y increases downward in pixels

        xmin_um = X1 - (x1 / px_per_um_x)
        ymax_um = Y1 + (y1 / px_per_um_y)

        _save_map_calib(
            "corner",
            px_per_um_x, px_per_um_y, xmin_um, ymax_um,
            p1_px=(x1, y1), p2_px=(x2, y2),
            p1_um=(X1, Y1), p2_um=(X2, Y2),
        )

        print(f"✅ Calibration (2 files) solved:")
        print(f"   px/µm_x = {px_per_um_x:.6f}, px/µm_y = {px_per_um_y:.6f}")
        print(f"   xmin_um = {xmin_um:.3f}, ymax_um = {ymax_um:.3f}")

    btn_calmap2.on_clicked(_calibrate_map_from_files)

    # ----------------  Check map calib on folder (Column 3)  ----------------
    ax_check_map_folder = plt.axes(btn_rect_col3)
    btn_check_map_folder = Button(ax_check_map_folder, 'check map folder')
    btn_rect_col3 = shift_rect3(btn_rect_col3)

    def _check_map_calibration_folder(_evt=None):
        """
        Debug helper: pick a folder of TIFFs, parse all Site(x,y) centers, and overlay
        small red dots for each unique site on the map image using the current
        map calibration.
        """
        try:
            folder = _select_folder()
        except Exception as e:
            print(f"❌ Folder chooser error: {e}")
            return

        if not folder:
            print("Canceled.")
            return

        try:
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith((".tif", ".tiff"))]
        except Exception as e:
            print(f"❌ Could not list folder: {e}")
            return

        if not files:
            print("No TIFF files found in selected folder.")
            return

        # Load base map image
        try:
            base = Image.open(MAP_IMAGE_PATH).convert("RGB")
        except Exception as e:
            print(f"⚠️ map image not found/unreadable: {MAP_IMAGE_PATH} ({e})")
            return

        W, H = base.size

        # Load current calibration (if any)
        cal = _load_map_calib()
        use_corner = cal.get("mode", "").lower() == "corner"
        if not use_corner:
            print("ℹ️ No saved 'corner' calibration; using MAP_* config parameters.")

        # Collect unique centers (in µm)
        centers = {}
        s_um = float(CONNECT_SHIFT_UM)
        for p in files:
            center = None
            # Prefer true site center inferred from #01-#09 set
            try:
                center = _infer_center_from_file(p, s_um)
            except Exception:
                center = None

            # Fallback: raw Site(x,y,...) from the filename
            if center is None:
                try:
                    ctr = _parse_site_center_from_name(os.path.basename(p))
                except Exception:
                    ctr = None
                if ctr:
                    try:
                        x_um = float(str(ctr[0]).replace(",", "."))
                        y_um = float(str(ctr[1]).replace(",", "."))
                        center = (x_um, y_um)
                    except Exception:
                        center = None

            if center is None:
                continue

            x_um, y_um = center
            key = (round(x_um, 4), round(y_um, 4))  # de-dupe sites
            if key not in centers:
                centers[key] = (x_um, y_um)

        if not centers:
            print("❌ No usable Site(...) coordinates were found in that folder.")
            return

        # Convert each center (µm) -> pixel coords on map
        pts_px = []
        xs = []
        ys = []
        any_oob = False
        for (cx_um, cy_um) in centers.values():
            if use_corner:
                px_per_um_x = cal["px_per_um_x"]
                px_per_um_y = cal["px_per_um_y"]
                xmin_um = cal["xmin_um"]
                ymax_um = cal["ymax_um"]
                px = (cx_um - xmin_um) * px_per_um_x
                py = (ymax_um - cy_um) * px_per_um_y
            else:
                # Fallback to config parameters (pre-calibration)
                if MAP_MODE.lower() == "center":
                    px = W / 2.0 + cx_um * MAP_PX_PER_UM
                    py = H / 2.0 - cy_um * MAP_PX_PER_UM
                else:
                    px = (cx_um - MAP_XMIN_UM) * MAP_PX_PER_UM
                    py = (MAP_YMAX_UM - cy_um) * MAP_PX_PER_UM

            pts_px.append((px, py))
            xs.append(px)
            ys.append(py)
            if not (0 <= px <= W and 0 <= py <= H):
                any_oob = True

        # Show overlay
        # --- Show overlay ---
        figM, axM = plt.subplots(1, 1, figsize=(7, 7))
        axM.imshow(base)
        try:
            folder_name = os.path.basename(folder.rstrip(os.sep))
        except Exception:
            folder_name = folder
        axM.set_title(
            f"Map calibration check: {len(centers)} site(s)\nFolder: {folder_name}"
        )

        # plot P1/P2 green X markers
        clicked_px = cal.get("clicked_px") or {}
        for lbl in ("P1", "P2"):
            pt = clicked_px.get(lbl)
            if not pt or len(pt) != 2:
                continue
            cx, cy = float(pt[0]), float(pt[1])
            axM.plot(cx, cy, 'gx', markersize=14, mew=2.5, zorder=7)
            axM.text(cx + 10, cy - 10, lbl,
                     color='lime', fontsize=10, weight='bold', zorder=8,
                     bbox=dict(facecolor='black', alpha=0.4, edgecolor='none'))

        # draw all red dots (initially no DX/DY)
        scat = axM.plot([p[0] for p in pts_px], [p[1] for p in pts_px],
                        'r.', markersize=3, zorder=5)[0]

        # initial limits
        margin = 20
        x_min = min(0, min(xs) - margin)
        x_max = max(W, max(xs) + margin)
        y_min = min(0, min(ys) - margin)
        y_max = max(H, max(ys) + margin)
        axM.set_xlim(x_min, x_max)
        axM.set_ylim(y_max, y_min)

        if any_oob:
            axM.text(
                0.02, 0.98,
                "⚠️ Some dots fall outside the map bounds (check calibration)",
                transform=axM.transAxes, va='top', ha='left',
                bbox=dict(facecolor='yellow', alpha=0.6, edgecolor='none'),
            )

        # --- Interactive DX/DY tuning controls ---
        from matplotlib.widgets import Button, Slider

        dx_val = 0.0
        dy_val = 0.0

        # function to re-draw points when DX/DY changes
        def _update_dots():
            newx = [px + dx_val for (px, py) in pts_px]
            newy = [py + dy_val for (px, py) in pts_px]
            scat.set_data(newx, newy)
            figM.canvas.draw_idle()

        def _nudge(dx=0, dy=0):
            nonlocal dx_val, dy_val
            dx_val += dx
            dy_val += dy
            _update_dots()
            print(f"DX={dx_val:.1f}px, DY={dy_val:.1f}px")

        # small inset axes for buttons
        ax_up = plt.axes([0.85, 0.15, 0.05, 0.05])
        ax_down = plt.axes([0.85, 0.05, 0.05, 0.05])
        ax_left = plt.axes([0.79, 0.10, 0.05, 0.05])
        ax_right = plt.axes([0.91, 0.10, 0.05, 0.05])
        ax_save = plt.axes([0.79, 0.20, 0.17, 0.05])

        btn_up = Button(ax_up, '↑')
        btn_down = Button(ax_down, '↓')
        btn_left = Button(ax_left, '←')
        btn_right = Button(ax_right, '→')
        btn_save = Button(ax_save, '💾 Save offset')

        # link buttons to movement
        btn_up.on_clicked(lambda _e: _nudge(dy=-10))
        btn_down.on_clicked(lambda _e: _nudge(dy=+10))
        btn_left.on_clicked(lambda _e: _nudge(dx=-10))
        btn_right.on_clicked(lambda _e: _nudge(dx=+10))

        # save new calibration with adjusted origin
        def _save_offset(_e=None):
            dx_um = dx_val / cal["px_per_um_x"]
            dy_um = dy_val / cal["px_per_um_y"]
            new_xmin_um = cal["xmin_um"] - dx_um
            new_ymax_um = cal["ymax_um"] + dy_um
            cal["xmin_um"] = new_xmin_um
            cal["ymax_um"] = new_ymax_um
            with open(MAP_CALIB_PATH, "w", encoding="utf-8") as f:
                json.dump(cal, f, indent=2)
            print(f"💾 Saved updated offsets: DX={dx_val:.1f}px, DY={dy_val:.1f}px → "
                  f"xmin_um={new_xmin_um:.3f}, ymax_um={new_ymax_um:.3f}")
            axM.text(0.5, 0.02, "Saved!", transform=axM.transAxes,
                     ha='center', va='bottom', color='green',
                     bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))
            figM.canvas.draw_idle()

        btn_save.on_clicked(_save_offset)

        plt.show(block=False)


    btn_check_map_folder.on_clicked(_check_map_calibration_folder)

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
            # --- NEW: add cross-section plot if a line was chosen earlier ---
            try:
                pts = PROFILE_STATE.get("points_um", None)
                if pts and len(pts) == 2:
                    prof_png = _make_profile_png_for_current(pts)
                    if prof_png:
                        # place the profile under the map thumbnail (same right margin)
                        prof_w = map_w
                        prof_h = map_h * 0.9  # a bit shorter than the map box
                        prof_left = left
                        prof_top = top + map_h + 10  # small gap under the map
                        new_slide.Shapes.AddPicture(
                            FileName=prof_png, LinkToFile=False, SaveWithDocument=True,
                            Left=prof_left, Top=prof_top, Width=prof_w, Height=prof_h
                        )
                        # (Optional) tag it
                        try:
                            new_slide.Shapes[new_slide.Shapes.Count].AlternativeText = json.dumps(
                                {"type": "cross-section",
                                 "p0_um": {"x": float(pts[0][0]), "y": float(pts[0][1])},
                                 "p1_um": {"x": float(pts[1][0]), "y": float(pts[1][1])}},
                                separators=(",", ":")
                            )
                        except Exception:
                            pass
                    else:
                        print("⚠️ Cross-section not added (render failed).")
                else:
                    print("ℹ️ No saved cross-section; skipping profile for this slide.")
            except Exception as e:
                print(f"⚠️ Could not add cross-section image: {e}")

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

    # --- Button: Max I → 65000 ---
    ax_max65k = plt.axes(btn_rect_col2)
    btn_max65k = Button(ax_max65k, 'MaxI 65k')

    def _set_maxI_65k(_evt=None):
        target = 65000.0

        # Keep the slider's bounds compatible and move the knob
        try:
            if hasattr(slider_max, "valmax") and target > slider_max.valmax:
                slider_max.valmax = target
            if hasattr(slider_max, "valmin") and minI < slider_max.valmin:
                slider_max.valmin = minI
            slider_max.set_val(target)
        except Exception:
            pass

        # Apply clim immediately so the image updates even if slider callbacks are delayed
        try:
            im_xy.set_clim(minI, target)
            if Nz > 1:
                im_xz.set_clim(minI, target)
                im_yz.set_clim(minI, target)
        except Exception:
            pass

        # If you have a text box for Max (txt_max), sync it too
        try:
            txt_max.set_val(f"{target:.0f}")
        except Exception:
            pass

        fig.canvas.draw_idle()
        print("Max I set to 65000.")

    btn_max65k.on_clicked(_set_maxI_65k)
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    # ----------------  Connect multiple (batch whole folder)  ----------------
    ax_connect_multi = plt.axes(btn_rect_col2)
    btn_connect_multi = Button(ax_connect_multi, 'connect multiple')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _select_folder() -> str | None:
        try:
            from tkinter import Tk, filedialog
            root = Tk();
            root.withdraw()
            path = filedialog.askdirectory(title="Select folder with #01-#09 TIFFs")
            try:
                root.destroy()
            except Exception:
                pass
            return path or None
        except Exception:
            return None

    def _round_key(x: float, digits: int = 6) -> float:
        # avoid tiny FP drift when grouping centers
        return round(float(x), digits)

    def _infer_center_from_file(path: str, s_um: float) -> tuple[float, float] | None:
        """
        From filename like ...Site(x y z)_#NN.tif, infer the true center coords by
        subtracting the known shot offset (±s in µm) from the file's Site(x,y).
        For #01, offset is (0,0) so we get the same coords.
        """
        name = os.path.basename(path)
        ctr = _parse_site_center_from_name(name)
        shot = _shot_num_from_name(name)
        if not ctr or not shot or shot not in SHOT_TO_OFFSET:
            return None
        x_um = float(str(ctr[0]).replace(",", "."))
        y_um = float(str(ctr[1]).replace(",", "."))
        dxs, dys = SHOT_TO_OFFSET[shot]  # -1..+1 steps
        cx = x_um - dxs * s_um
        cy = y_um - dys * s_um
        return (cx, cy)

    def _shots_complete(d: dict[int, str]) -> bool:
        return all(k in d for k in range(1, 10))

    def _save_connected_name(origin_path: str) -> str:
        """
        Save next to the origin (#01) file. Prefer replacing '_#01' → '_connected';
        otherwise append '_connected' before extension. Avoid collisions.
        """
        folder, name = os.path.split(origin_path)
        stem, ext = os.path.splitext(name)
        import re
        out_stem = re.sub(r"_#\d{2}$", "_connected", stem)
        if out_stem == stem:
            out_stem = f"{stem}_connected"
        candidate = os.path.join(folder, out_stem + ".tif")
        if not os.path.exists(candidate):
            return candidate
        i = 2
        while True:
            cand = os.path.join(folder, f"{out_stem}({i}).tif")
            if not os.path.exists(cand):
                return cand
            i += 1

    def _connect_set_and_save(shots: dict[int, str], center_xy_um: tuple[float, float]):
        """
        Build a feathered circular mosaic for a complete 3×3 set (shots 1..9),
        then save a 16-bit TIFF using current pixel size and display mapping.
        """
        # Load all 9 images, resize to #01 shape
        p_origin = shots[1]
        img0 = _tif_to_2d(p_origin).astype(np.float64)
        H, W = img0.shape

        imgs = {1: img0}
        for n in range(2, 10):
            im = _tif_to_2d(shots[n]).astype(np.float64)
            if im.shape != (H, W):
                im = _resize_like(im, (H, W))
            imgs[n] = im

        # Pixel scale
        try:
            um_per_px_x = float(PIXEL_SIZE_UM)
            um_per_px_y = float(PIXEL_SIZE_UM)
        except Exception:
            um_per_px_x = um_per_px_y = 0.1  # safe fallback

        px_per_um_x = 1.0 / um_per_px_x
        px_per_um_y = 1.0 / um_per_px_y

        # Compute offsets from filenames (exact world coords)
        cx0_um, cy0_um = center_xy_um
        offsets = []  # [(dy_px, dx_px, img)]
        TOL_UM = 1e-3

        def _coord_from_name_local(p):
            c = _parse_site_center_from_name(os.path.basename(p))
            if not c: return None
            return float(str(c[0]).replace(",", ".")), float(str(c[1]).replace(",", "."))

        for n in range(1, 10):
            p = shots[n]
            x_um, y_um = _coord_from_name_local(p)
            dx_um = x_um - cx0_um
            dy_um = y_um - cy0_um
            if abs(dx_um) < TOL_UM: dx_um = 0.0
            if abs(dy_um) < TOL_UM: dy_um = 0.0
            dx_px = int(round(dx_um * px_per_um_x))
            dy_px = int(round(dy_um * px_per_um_y))  # +µm Y → +rows down
            offsets.append((dy_px, dx_px, imgs[n], p))

        # Canvas extents
        min_top = min(0, *(dy for dy, dx, im, p in offsets))
        max_top = max(0, *(dy for dy, dx, im, p in offsets))
        min_left = min(0, *(dx for dy, dx, im, p in offsets))
        max_left = max(0, *(dx for dy, dx, im, p in offsets))
        Hc = (max_top - min_top) + H
        Wc = (max_left - min_left) + W

        # Feathered circular placement (your “remove stitching circles” logic)
        canvas = np.zeros((Hc, Wc), dtype=np.float64)
        wsum = np.zeros((Hc, Wc), dtype=np.float64)
        for dy, dx, im, p in offsets:
            _place_on_canvas_circ_feather(
                canvas, wsum, im,
                dy - min_top, dx - min_left,
                um_per_px_x, um_per_px_y,
                CIRCLE_RADIUS_UM, FEATHER_WIDTH_UM
            )
        mosaic = np.zeros_like(canvas)
        m = wsum > 0
        mosaic[m] = canvas[m] / wsum[m]

        # Save next to origin with “_connected”
        out_u16 = _to_uint16_for_save(mosaic)  # use data min/max for full range
        save_path = _save_connected_name(p_origin)
        _save_tif2d(out_u16, save_path)
        print(f"   → saved '{os.path.basename(save_path)}'  ({Wc}×{Hc}px)")

    def _connect_multiple_handler(_evt=None):
        try:
            folder = _select_folder()
            if not folder:
                print("Canceled.")
                return
            print(f"Scanning: {folder}")

            # Gather TIFFs
            files = [os.path.join(folder, f) for f in os.listdir(folder)
                     if f.lower().endswith((".tif", ".tiff"))]
            if not files:
                print("No TIFF files found.")
                return

            s_um = float(CONNECT_SHIFT_UM)

            # Group by inferred center, collect per-shot files
            groups: dict[tuple[float, float], dict[int, str]] = {}
            for p in files:
                ctr = _infer_center_from_file(p, s_um)  # None if no Site(...) or shot tag
                if ctr is None:
                    continue
                cx, cy = (_round_key(ctr[0]), _round_key(ctr[1]))
                shot = _shot_num_from_name(os.path.basename(p))
                if not shot:
                    continue
                shots = groups.setdefault((cx, cy), {})
                shots[shot] = p

            # Process complete sets
            total = len(groups)
            done = fail = 0
            for (cx, cy), shots in sorted(groups.items()):
                label = f"Site({cx:.6f} {cy:.6f})"
                if not _shots_complete(shots):
                    missing = sorted(set(range(1, 10)) - set(shots.keys()))
                    print(f"Skipping {label}: missing shots {missing}")
                    continue
                print(f"Connecting {label} ...")
                try:
                    _connect_set_and_save(shots, (cx, cy))
                    done += 1
                except Exception as e:
                    print(f"   ❌ failed: {e}")
                    fail += 1

            print(f"Batch complete: {done} saved, {fail} failed, {total} site(s) scanned.")

        except Exception as e:
            print(f"❌ connect multiple failed: {e}")

    btn_connect_multi.on_clicked(_connect_multiple_handler)

    # ----------------  Multiple add+map  ----------------
    ax_addppt_map_multi = plt.axes(btn_rect_col2)
    btn_addppt_map_multi = Button(ax_addppt_map_multi, 'multiple add+map')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _set_xy_extent(ax_xy, img2d, x0, x1, y0, y1):
        """Set and remember world-coordinate extent on the main XY image."""
        extent = [x0, x1, y0, y1]
        globals()["xy_world_extent"] = extent  # remember for later reapply

        # Prefer existing image artist
        im = globals().get("im_xy", None)
        if im is not None and hasattr(im, "set_extent"):
            im.set_extent(extent)
            return

        # Try first AxesImage on that axes
        ims = ax_xy.get_images()
        if ims:
            ims[0].set_extent(extent)
            globals()["im_xy"] = ims[0]
            return

        # As a last resort, create one
        new_im = ax_xy.imshow(img2d, extent=extent, origin="upper")
        globals()["im_xy"] = new_im

    # global store for relative template
    PROFILE_TEMPLATE = globals().get("PROFILE_TEMPLATE", {})

    def set_profile_template_from_points(p0_um, p1_um, center_um):
        """
        Save a relative line template (d0_um, d1_um) in µm offsets from center_um.
        p0_um, p1_um, center_um are all absolute world coords (µm).
        """
        global PROFILE_TEMPLATE
        try:
            print(f"[TEMPLATE:SET] center_um={center_um}, p0_um={p0_um}, p1_um={p1_um}")
            cx, cy = float(center_um[0]), float(center_um[1])
            d0 = (float(p0_um[0] - cx), float(p0_um[1] - cy))
            d1 = (float(p1_um[0] - cx), float(p1_um[1] - cy))
            PROFILE_TEMPLATE["d0_um"] = d0
            PROFILE_TEMPLATE["d1_um"] = d1
            print(f"[TEMPLATE:SET] Saved relative template: d0_um={d0}, d1_um={d1}")
            return True
        except Exception as e:
            print(f"[TEMPLATE:SET] Failed: {e}")
            return False

    # --- DEBUG TOOLS ---
    DEBUG_ADD_MAP = True

    def _dbg(msg):
        if DEBUG_ADD_MAP:
            print(msg)

    def _log_axes_state(ax, label="ax_xy"):
        try:
            xlim = ax.get_xlim();
            ylim = ax.get_ylim()
            _dbg(f"[{label}] xlim={xlim}, ylim={ylim}, images={len(ax.images)}, patches={len(ax.patches)}")
        except Exception as e:
            print(f"[{label}] state log failed: {e}")

    # --- Coerce a "point-like" value to (float, float), with strong logs ---
    def _coerce_pt(val, name="point"):
        import math, numpy as np
        _dbg(f"[COERCE] {name} raw={repr(val)} (type={type(val)})")
        if val is None:
            raise ValueError(f"{name} is None")

        # Accept tuple / list / numpy array-like with length >=2
        if hasattr(val, "__len__") and len(val) >= 2:
            x, y = val[0], val[1]
        else:
            raise ValueError(f"{name} is not a 2-sequence")

        # Convert str → float if needed
        try:
            x = float(x)
            y = float(y)
        except Exception as e:
            raise ValueError(f"{name} cannot be cast to floats: {e}")

        # Check finiteness
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError(f"{name} has non-finite coords: ({x}, {y})")

        _dbg(f"[COERCE] {name} -> ({x}, {y})")
        return (x, y)

    from matplotlib.transforms import Bbox
    from mpl_toolkits.axes_grid1 import make_axes_locatable

    def export_main_axes_snapshot(ax, *, mappable=None, cbar_ax_or_cb=None, dpi=220, fname=None,
                                  font_scale=4.0):
        fig = ax.figure
        fig.canvas.draw()
        renderer = fig.canvas.get_renderer()

        # --- remember things we’ll change ---
        # Ax title + (optional) suptitle
        old_title_text = ax.get_title()
        old_suptitle_obj = getattr(fig, "_suptitle", None)

        # current font sizes (we’ll multiply by font_scale)
        old_xlab_fs = ax.xaxis.label.get_size()
        old_ylab_fs = ax.yaxis.label.get_size()
        old_xtick_fs = [t.get_size() for t in ax.get_xticklabels()]
        old_ytick_fs = [t.get_size() for t in ax.get_yticklabels()]

        hidden_profile_axes = []
        tmp_cbar = None
        tmp_cax = None
        cax = None
        hidden_other_cb_axes = []

        try:
            # 0) Hide inset profile axes (we only want the main image)
            for a in fig.axes:
                if getattr(a, "_is_profile_axes", False) and a.get_visible():
                    hidden_profile_axes.append(a)
                    a.set_visible(False)

            # 1) Remove any titles from the main image
            ax.set_title("")  # axes title off
            if old_suptitle_obj is not None:  # fig-level title off
                old_suptitle_obj.set_visible(False)

                # --- NEW: detect and hide pre-existing (small) colorbars near ax ---
                try:
                    ax_box = ax.get_position(fig)
                    for a in list(fig.axes):
                        if a is ax:
                            continue
                        # treat as "colorbar-like" if skinny and adjacent on the right of ax
                        pb = a.get_position(fig)
                        skinny = (pb.width < ax_box.width * 0.25)  # narrow vs main axes
                        right_of_ax = pb.x0 >= ax_box.x1 - 0.02

                        if skinny and right_of_ax and a.get_visible():
                            hidden_other_cb_axes.append(a)
                            a.set_visible(False)
                except Exception:
                    pass

            # 2) Ensure we have a colorbar
            if cbar_ax_or_cb is not None:
                if hasattr(cbar_ax_or_cb, "ax"):
                    cax = cbar_ax_or_cb.ax
                elif hasattr(cbar_ax_or_cb, "get_tightbbox"):
                    cax = cbar_ax_or_cb
                if getattr(cax, "figure", None) is not fig:
                    cax = None
            if cax is None and mappable is not None:
                from mpl_toolkits.axes_grid1 import make_axes_locatable
                div = make_axes_locatable(ax)
                tmp_cax = div.append_axes("right", size="3%", pad=0.06)
                tmp_cbar = fig.colorbar(mappable, cax=tmp_cax)
                cax = tmp_cax

            # 3) Enlarge fonts (~4×)
            ax.xaxis.label.set_size(old_xlab_fs * font_scale)
            ax.yaxis.label.set_size(old_ylab_fs * font_scale)
            for i, t in enumerate(ax.get_xticklabels()):
                t.set_size((old_xtick_fs[i] if i < len(old_xtick_fs) else t.get_size()) * font_scale)
            for i, t in enumerate(ax.get_yticklabels()):
                t.set_size((old_ytick_fs[i] if i < len(old_ytick_fs) else t.get_size()) * font_scale)

            # Colorbar tick/label sizes
            if cax is not None:
                # tick labels
                for t in cax.get_yticklabels():
                    t.set_size(t.get_size() * font_scale)
                # label (if present)
                try:
                    cb = tmp_cbar if tmp_cbar is not None else cax.colorbar
                    if cb is not None and cb.ax is cax and cb.label is not None:
                        cb.ax.set_ylabel(cb.label.get_text(), fontsize=cb.ax.yaxis.label.get_size() * font_scale)
                except Exception:
                    pass

            # 4) Save tight bbox around axes (+ colorbar), small padding
            from matplotlib.transforms import Bbox
            boxes = [ax.get_tightbbox(renderer).transformed(fig.dpi_scale_trans.inverted())]
            if cax is not None:
                boxes.append(cax.get_tightbbox(renderer).transformed(fig.dpi_scale_trans.inverted()))
            bbox = Bbox.union(boxes)
            pad = 6.0 / float(dpi)
            from matplotlib.transforms import Bbox as _B
            bbox = _B.from_extents(bbox.x0 - pad, bbox.y0 - pad, bbox.x1 + pad, bbox.y1 + pad)

            import os, tempfile
            if not fname:
                fname = os.path.join(tempfile.gettempdir(), "ppt_snapshot.png")
            fig.savefig(fname, dpi=dpi, bbox_inches=bbox, facecolor=fig.get_facecolor())
            print(f"[SNAPSHOT] wrote {fname} (dpi={dpi}, font_scale={font_scale})")
            return fname

        except Exception as e:
            print(f"[SNAPSHOT] failed: {e}")
            return None

        finally:
            # restore titles
            try:
                ax.set_title(old_title_text)
            except Exception:
                pass
            if old_suptitle_obj is not None:
                try:
                    old_suptitle_obj.set_visible(True)
                except Exception:
                    pass

            # restore inset axes
            for a in hidden_profile_axes:
                try:
                    a.set_visible(True)
                except Exception:
                    pass

            # restore fonts
            try:
                ax.xaxis.label.set_size(old_xlab_fs)
                ax.yaxis.label.set_size(old_ylab_fs)
                for i, t in enumerate(ax.get_xticklabels()):
                    if i < len(old_xtick_fs): t.set_size(old_xtick_fs[i])
                for i, t in enumerate(ax.get_yticklabels()):
                    if i < len(old_ytick_fs): t.set_size(old_ytick_fs[i])
            except Exception:
                pass

            for a in hidden_other_cb_axes:
                try:
                    a.set_visible(True)
                except Exception:
                    pass

            # remove temp colorbar/axes
            try:
                if tmp_cbar is not None: tmp_cbar.remove()
                if tmp_cax is not None: tmp_cax.remove()
            except Exception:
                pass

    def _run_multiple_add2ppt_map(paths):
        """Core logic for multi add+map, given an explicit list of paths."""
        try:
            if not paths:
                print("No files to process.")
                return

            pythoncom.CoInitialize()
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                print("No PowerPoint presentations are open.")
                return
            pres = ppt.ActivePresentation
            slide_w = pres.PageSetup.SlideWidth
            slide_h = pres.PageSetup.SlideHeight

            map_w = slide_w * 0.25
            map_h = slide_h * 0.25
            margin = 20

            # --- ADD this helper once (e.g., near your other PPT helpers) ---
            def _fit_shape_keep_aspect(shape, *, left, top, max_w, max_h):
                """
                Resize and place a PowerPoint shape to fit inside (max_w x max_h) box,
                preserving aspect ratio (no distortion).
                """
                try:
                    shape.LockAspectRatio = -1  # msoTrue
                except Exception:
                    pass

                try:
                    w, h = float(shape.Width), float(shape.Height)
                    if w <= 0 or h <= 0:
                        print("[FIT] invalid shape size; skipping resize")
                        return

                    scale = min(max_w / w, max_h / h)
                    shape.Width = w * scale
                    shape.Height = h * scale
                    shape.Left = left
                    shape.Top = top
                    print(f"[FIT] placed W={shape.Width:.1f} H={shape.Height:.1f} "
                          f"at L={shape.Left:.1f}, T={shape.Top:.1f}")
                except Exception as e:
                    print(f"[FIT] resize failed: {e}")

            # (keep your existing _draw_end_triangles and _clear_profile_markers
            #  exactly as they are here – omitted for brevity)

            _dbg(f"[INIT] slides={pres.Slides.Count}, slide_w={slide_w}, slide_h={slide_h}")

            for pth in paths:
                try:
                    pth = os.path.abspath(pth)
                    fname = os.path.basename(pth)
                    _dbg(f"\n=== Processing: {fname} ===")

                    # ---------- Load TIFF into viewer ----------
                    try:
                        img2d = _tif_to_2d(pth).astype(np.float64)
                        _dbg(f"[LOAD] img2d shape={getattr(img2d, 'shape', None)} dtype={img2d.dtype}")
                        _switch_to_2d_dataset(img2d)
                        try:
                            ax_xy.set_title(fname)
                        except Exception:
                            pass
                        fig.canvas.draw_idle()
                    except Exception as e:
                        print(f"⚠️ Skipping (load failed) {fname}: {e}")
                        continue

                    # ---------- World coords ----------
                    center_um = None
                    try:
                        center_um = _parse_site_center_from_name(fname)
                        globals()["LAST_CENTER_UM"] = center_um
                        print(f"[CENTER] LAST_CENTER_UM set to {center_um}")
                        _dbg(f"[CENTER] parsed center_um={center_um}")

                        if center_um is not None:
                            cx_um, cy_um, _ = center_um
                            um_per_px_x = globals().get("um_per_px_x", PIXEL_SIZE_UM) or 1.0
                            um_per_px_y = globals().get("um_per_px_y", PIXEL_SIZE_UM) or 1.0
                            H, W = img2d.shape[:2]
                            half_w_um = (W * um_per_px_x) * 0.5
                            half_h_um = (H * um_per_px_y) * 0.5
                            x0, x1 = cx_um - half_w_um, cx_um + half_w_um
                            y0, y1 = cy_um - half_h_um, cy_um + half_h_um
                            _dbg(f"[EXTENT] x=({x0:.2f},{x1:.2f}) y=({y0:.2f},{y1:.2f})")
                            _set_xy_extent(ax_xy, img2d, x0, x1, y0, y1)
                            try:
                                ax_xy.set_xlabel("x (µm)")
                                ax_xy.set_ylabel("y (µm)")
                            except Exception:
                                pass
                            ax_xy.set_xlim(x0, x1)
                            ax_xy.set_ylim(y0, y1)
                            ax_xy.autoscale(False)
                            _log_axes_state(ax_xy, "ax_after_extent")
                        else:
                            _dbg("[CENTER] center_um is None; skipping extent/template mapping")
                    except Exception as e:
                        print(f"⚠️ Could not set world coords for {fname}: {e}")

                    # ---------- flatten++ (optional) ----------
                    try:
                        sigma_bg = float(slider_sigma_bg.val) if 'slider_sigma_bg' in globals() else 20.0
                        nonlocal I_view
                        aggr_state["on"] = True
                        aggr_state["cube"] = _compute_flat_cube_aggressive(sigma_bg=sigma_bg)
                        aggr_state["computed_sigma"] = sigma_bg
                        C = aggr_state["cube"]
                        I_view = np.log10(C + EPS) if log_scale else C
                        im_xy.set_data(_maybe_flip(_smooth2d(I_view[z_idx])))
                        if Nz > 1:
                            im_xz.set_data(_smooth2d(I_view[:, y_idx, :]))
                            im_yz.set_data(_smooth2d(I_view[:, :, x_idx]))
                        try:
                            btn_flat_aggr.label.set_text(f"flatten++ on (σ={sigma_bg:.0f})")
                        except Exception:
                            pass
                        fig.canvas.draw_idle()
                        _dbg(f"[FLATTEN++] sigma_bg={sigma_bg}")
                    except Exception as e:
                        print(f"⚠️ flatten++ failed for {fname}: {e} (continuing without)")

                    # ---------- triangles from template (relative to center) ----------
                    pts_abs = None
                    try:
                        t = globals().get("PROFILE_TEMPLATE", None)
                        _dbg(f"[TEMPLATE] PROFILE_TEMPLATE present={bool(t)}; keys={list(t.keys()) if t else None}")
                        if not center_um:
                            _dbg("[TEMPLATE] center_um is None → cannot map relative offsets; skipping triangles")
                        elif not t:
                            _dbg("[TEMPLATE] PROFILE_TEMPLATE missing; skipping triangles")
                        else:
                            d0 = _coerce_pt(t.get("d0_um", None), "d0_um")
                            d1 = _coerce_pt(t.get("d1_um", None), "d1_um")
                            cx_um, cy_um, _ = center_um
                            p0 = (float(cx_um + d0[0]), float(cy_um + d0[1]))
                            p1 = (float(cx_um + d1[0]), float(cy_um + d1[1]))
                            pts_abs = (p0, p1)
                            _dbg(f"[PTS_ABS] p0={p0}, p1={p1}")
                            _clear_profile_markers(ax_xy)
                            before = len(ax_xy.patches)
                            tri0, tri1 = _draw_end_triangles(ax_xy, p0, p1, face='y', edge='k', lw=1.0)

                            tri0.set_zorder(100)
                            tri1.set_zorder(100)
                            tri0.set_visible(True)
                            tri1.set_visible(True)
                            _dbg(f"[TRIANGLES] patches before={before} after={len(ax_xy.patches)}")
                    except Exception as e:
                        print(f"⚠️ Could not apply cross-section template: {e}")

                    # Ensure triangles are drawn
                    try:
                        fig.canvas.draw()
                        fig.canvas.flush_events()
                        _log_axes_state(ax_xy, "ax_before_clipboard")
                    except Exception:
                        pass

                    # ---------- Create the slide FIRST ----------
                    new_slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # ppLayoutBlank
                    ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)

                    # ----- MAIN IMAGE INSERT: PNG snapshot (robust; includes scatter triangles) -----
                    main_shape = None

                    # im_xy.set_clim(SCALE_MIN, SCALE_MAX)

                    png_path = export_main_axes_snapshot(
                        ax_xy,
                        mappable=im_xy,  # provide the image artist
                        cbar_ax_or_cb=None,  # force a single, big colorbar
                        dpi=220,
                        font_scale=4.0
                    )

                    if png_path and os.path.exists(png_path):
                        try:
                            # Left column ~0.68 slide width, keep aspect
                            target_w = slide_w * 0.68
                            left, top = 40, 90
                            shp = new_slide.Shapes.AddPicture(
                                FileName=png_path, LinkToFile=False, SaveWithDocument=True,
                                Left=left, Top=top, Width=target_w, Height=-1
                            )
                            shp.LockAspectRatio = -1
                            main_shape = shp
                            print(
                                f"[PASTE] PNG inserted W={shp.Width:.1f} H={shp.Height:.1f} L={shp.Left:.1f} T={shp.Top:.1f}")
                        except Exception as e:
                            print(f"[PASTE] PNG AddPicture failed: {e}")

                    # After obtaining `main_shape` (either from clipboard or AddPicture)
                    if main_shape is not None:
                        # Left column box (example numbers—use your existing margins)
                        box_left = 40
                        box_top = 90
                        box_w = slide_w * 0.68  # ~2/3 slide width
                        box_h = slide_h * 0.80  # leave room for title
                        _fit_shape_keep_aspect(main_shape, left=box_left, top=box_top, max_w=box_w, max_h=box_h)

                    # Final sanity; if snapshot failed, fall back once to clipboard (best effort)
                    if main_shape is None:
                        try:
                            print("[PASTE] snapshot missing; trying clipboard fallback")
                            fig.canvas.draw()
                            copy_main_axes_to_clipboard()
                            shapes = new_slide.Shapes.Paste()
                            main_shape = shapes[0] if getattr(shapes, "Count", 0) else None
                            print(f"[PASTE] clipboard fallback, shape={'ok' if main_shape else 'none'}")
                        except Exception as e:
                            print(f"[PASTE] clipboard fallback failed: {e}")

                    if main_shape is None:
                        print("⚠️ No main image inserted (both PNG and clipboard failed).")
                    else:
                        try:
                            main_shape.AlternativeText = json.dumps({"filename": pth}, separators=(",", ":"))
                        except Exception as e:
                            print(f"[ALT] set AlternativeText failed: {e}")

                    # ---------- Title ----------
                    try:
                        title_shape = new_slide.Shapes.AddTextbox(1, 20, 10, slide_w - 40, 50)
                        tr = title_shape.TextFrame.TextRange
                        tr.Text = fname
                        tr.ParagraphFormat.Alignment = 2
                        tr.Font.Bold = True
                        tr.Font.Size = 28
                        try:
                            title_shape.Fill.Visible = 0
                            title_shape.Line.Visible = 0
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"[TITLE] failed: {e}")

                    # ---------- Small map ----------
                    try:
                        cx_um, cy_um, _cz_um = center_um if center_um else (0.0, 0.0, 0.0)
                        tmp_map_path = _make_map_with_cross(cx_um, cy_um, MAP_IMAGE_PATH)
                        _dbg(f"[MAP] tmp_map_path={tmp_map_path}")
                        if tmp_map_path:
                            left = slide_w - map_w - margin
                            top = margin
                            pic = new_slide.Shapes.AddPicture(
                                FileName=tmp_map_path, LinkToFile=False, SaveWithDocument=True,
                                Left=left, Top=top, Width=map_w, Height=map_h
                            )
                            try:
                                pic.AlternativeText = json.dumps(
                                    {"type": "site-map", "x_um": float(cx_um), "y_um": float(cy_um),
                                     "source": MAP_IMAGE_PATH},
                                    separators=(",", ":")
                                )
                            except Exception:
                                pass
                        else:
                            print("⚠️ Map not available; continuing without map.")
                    except Exception as e:
                        print(f"[MAP] failed: {e}")

                    # ---------- Cross-section plot (if we had pts_abs) ----------
                    try:
                        if pts_abs:
                            _dbg(f"[PROFILE] calling _make_profile_png_for_current with pts_abs={pts_abs}")
                            prof_png = _make_profile_png_for_current(pts_abs)
                            _dbg(f"[PROFILE] returned prof_png={prof_png}")
                            if prof_png:
                                prof_w = map_w
                                prof_h = map_h * 0.9
                                prof_left = slide_w - map_w - margin
                                prof_top = margin + map_h + 10
                                shp = new_slide.Shapes.AddPicture(
                                    FileName=prof_png, LinkToFile=False, SaveWithDocument=True,
                                    Left=prof_left, Top=prof_top, Width=prof_w, Height=prof_h
                                )
                                try:
                                    shp.AlternativeText = json.dumps(
                                        {"type": "cross-section",
                                         "p0_um": {"x": float(pts_abs[0][0]), "y": float(pts_abs[0][1])},
                                         "p1_um": {"x": float(pts_abs[1][0]), "y": float(pts_abs[1][1])}},
                                        separators=(",", ":")
                                    )
                                except Exception:
                                    pass
                            else:
                                print("⚠️ Cross-section not added (render failed or None path).")
                        else:
                            print("ℹ️ No cross-section template; skipping profile for this slide.")
                    except Exception as e:
                        print(f"⚠️ Could not add cross-section image: {e}")

                    print(
                        f"Added slide #{new_slide.SlideIndex} for {fname} with map cross at ({cx_um:.1f}, {cy_um:.1f}) µm.")

                except Exception as e:
                    print(f"❌ Failed on {os.path.basename(pth)}: {e}")

        except Exception as e:
            print(f"❌ multiple add+map failed: {e}")

        # ---------- Close the app after finishing ----------
        try:
            _dbg("[CLOSE] closing figures and root…")
            try:
                import matplotlib.pyplot as _plt
                _plt.close('all')
            except Exception:
                pass
            if 'root' in globals() and root:
                try:
                    root.after(100, root.destroy)
                except Exception:
                    pass
            import sys
            try:
                sys.exit(0)
            except SystemExit:
                pass
        except Exception as e:
            print(f"⚠️ Could not close app cleanly: {e}")

    def _handle_multiple_add2ppt_map(_evt=None):
        """Existing button: pick multiple files via dialog."""
        try:
            paths = open_files_dialog([("TIFF Files", "*.tif *.tiff"), ("All Files", "*.*")])
            if not paths:
                print("No files selected.")
                return
            _run_multiple_add2ppt_map(paths)
        except Exception as e:
            print(f"❌ multiple add+map failed: {e}")

    btn_addppt_map_multi.on_clicked(_handle_multiple_add2ppt_map)

    # ------------- Button: multiple add+map (dir) -------------
    ax_addppt_map_multi_dir = plt.axes(btn_rect_col2)
    btn_addppt_map_multi_dir = Button(ax_addppt_map_multi_dir, 'multi add+map dir')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _handle_multiple_add2ppt_map_dir(_evt=None):
        """New button: choose a directory, process all TIFFs inside."""
        import os
        from tkinter import filedialog

        # Ask for directory
        dir_path = filedialog.askdirectory(title="Select directory with TIFF files")
        if not dir_path:
            print("No directory selected.")
            return

        # Collect all .tif / .tiff (case-insensitive)
        exts = {'.tif', '.tiff'}
        paths = [
            os.path.join(dir_path, f)
            for f in sorted(os.listdir(dir_path))
            if os.path.isfile(os.path.join(dir_path, f))
               and os.path.splitext(f)[1].lower() in exts
        ]

        if not paths:
            print(f"No TIFF files found in directory: {dir_path}")
            return

        print(f"Found {len(paths)} TIFF files in {dir_path}")
        _run_multiple_add2ppt_map(paths)

    btn_addppt_map_multi_dir.on_clicked(_handle_multiple_add2ppt_map_dir)

    # ---------------- Button: multiple crop (batch) ----------------
    ax_multicrop = plt.axes(btn_rect_col2)
    btn_multicrop = Button(ax_multicrop, 'multiple crop')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _handle_multiple_crop(_evt=None):
        try:
            paths = open_files_dialog([("TIFF Files", "*.tif *.tiff")])
            if not paths:
                print("No files selected.")
                return

            # read desired crop box from global
            y0, y1, x0, x1 = CROP_PIXELS
            ok, fail = 0, 0

            for path in paths:
                try:
                    # load as 2D float64 (RGB→gray, multipage→mean)
                    img2d = _tif_to_2d(path).astype(np.float64)

                    H, W = img2d.shape
                    yy0 = max(0, min(H - 1, int(y0)))
                    yy1 = max(yy0 + 1, min(H, int(y1)))
                    xx0 = max(0, min(W - 1, int(x0)))
                    xx1 = max(xx0 + 1, min(W, int(x1)))

                    crop2d = img2d[yy0:yy1, xx0:xx1]

                    # save as uint16 using per-image min/max to keep dynamic range
                    out_u16 = _to_uint16_for_save(crop2d)

                    folder, name = os.path.split(path)
                    stem, _ = os.path.splitext(name)
                    save_path = os.path.join(folder, f"{stem}_crop.tif")

                    # avoid overwrite by auto-increment
                    i = 2
                    while os.path.exists(save_path):
                        save_path = os.path.join(folder, f"{stem}_crop({i}).tif")
                        i += 1

                    _save_tif2d(out_u16, save_path)
                    print(f"✅ Cropped → {os.path.basename(save_path)}")
                    ok += 1
                except Exception as e:
                    print(f"❌ Failed on {os.path.basename(path)}: {e}")
                    fail += 1

            print(f"Batch crop complete: {ok} saved, {fail} failed.")

        except Exception as e:
            print(f"❌ multiple crop failed: {e}")

    btn_multicrop.on_clicked(_handle_multiple_crop)

    # --- Button: line plot (choose two points → profile) ---
    ax_lineplot = plt.axes(btn_rect_col2)
    btn_lineplot = Button(ax_lineplot, 'line plot')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    # --- Line-plot state (enclosing function scope) ---
    _line_artists = []  # drawn artists on ax_xy
    _line_clicks_data = []  # [(xµm, yµm), (xµm, yµm)]
    _linepick_cid = None

    def _clear_line_artists():
        for a in list(_line_artists):
            try:
                a.remove()
            except Exception:
                pass
        _line_artists.clear()
        plt.gcf().canvas.draw_idle()

    def _enable_line_pick(_evt=None):
        nonlocal _linepick_cid, _line_clicks_data
        _clear_line_artists()
        _line_clicks_data = []
        if _linepick_cid is not None:
            fig.canvas.mpl_disconnect(_linepick_cid)
        _linepick_cid = fig.canvas.mpl_connect('button_press_event', _on_linepick_click)
        print("Line selection: left-click two points inside the XY image (right-click to cancel).")

    def _disable_line_pick():
        nonlocal _linepick_cid
        if _linepick_cid is not None:
            try:
                fig.canvas.mpl_disconnect(_linepick_cid)
            except Exception:
                pass
            _linepick_cid = None

    def _data_to_pixel(x_um, y_um):
        """Map data coords (µm) → array indices (xpix, ypix)."""
        xmin, xmax, ymin, ymax = im_xy.get_extent()
        arr = np.asarray(im_xy.get_array())
        Ny, Nx = arr.shape[-2], arr.shape[-1]
        xpix = (x_um - xmin) * (Nx - 1) / max(1e-12, (xmax - xmin))
        ypix = (y_um - ymin) * (Ny - 1) / max(1e-12, (ymax - ymin))
        return xpix, ypix, arr

    def _on_lineplot_button(event=None):
        _enable_line_pick()

    def _on_linepick_click(event):
        # cancel on right-click or click outside the image
        if event.button != 1 or event.inaxes is not ax_xy:
            if event.button != 1:  # right-click cancels
                _disable_line_pick()
                print("Line selection cancelled.")
            return
        if event.xdata is None or event.ydata is None:
            return

        # draw a point marker in data coords (µm)
        pt = ax_xy.plot(event.xdata, event.ydata, 'o', ms=8, mfc='none', mew=2)[0]
        _line_artists.append(pt)
        _line_clicks_data.append((float(event.xdata), float(event.ydata)))

        # once we have 2 points, draw line and build profile
        if len(_line_clicks_data) == 2:
            (x0, y0), (x1, y1) = _line_clicks_data
            ln = ax_xy.plot([x0, x1], [y0, y1], '-', lw=2)[0]
            _line_artists.append(ln)
            fig.canvas.draw_idle()
            _disable_line_pick()
            _finish_line_profile((x0, y0), (x1, y1))

    def _finish_line_profile(p0_um, p1_um):
        """Compute intensity profile between two data points (µm) and plot."""
        # convert to pixel space and sample
        x0p, y0p, arr = _data_to_pixel(*p0_um)
        x1p, y1p, _ = _data_to_pixel(*p1_um)
        L = int(max(2, np.hypot(x1p - x0p, y1p - y0p)))  # ~1 sample per pixel
        xs = np.linspace(x0p, x1p, L)
        ys = np.linspace(y0p, y1p, L)
        prof = _bilinear_profile_array(arr, xs, ys)  # uses current displayed data

        # reuse (or create) a profile axes
        ax_profile = None
        for ax in fig.axes:
            if getattr(ax, "_is_profile_axes", False):
                ax_profile = ax
                break
        _profile_rect = [0.23, 0.78, 0.18, 0.16]
        if ax_profile is None:
            ax_profile = fig.add_axes(_profile_rect)
            ax_profile._is_profile_axes = True
        else:
            ax_profile.set_position(_profile_rect)
        ax_profile.set_anchor('NW')
        ax_profile.clear()
        ax_profile.plot(np.arange(L), prof)
        ax_profile.set_title("Line Profile")
        ax_profile.set_xlabel("Distance (px)")
        ax_profile.set_ylabel("Intensity (a.u.)")
        fig.canvas.draw_idle()

        # save the two picked points (in µm) next to the image file if known
        try:
            import time, json, os
            folder, stem = ".", "line_points"
            if 'filepath' in locals() and filepath:
                folder, name = os.path.split(filepath)
                stem, _ = os.path.splitext(name)
            record = {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "image_path": filepath if 'filepath' in locals() else None,
                "points_um": [{"x": p0_um[0], "y": p0_um[1]}, {"x": p1_um[0], "y": p1_um[1]}]
            }
            json_path = os.path.join(folder, "line.json")
            if os.path.exists(json_path):
                try:
                    with open(json_path, "r") as f:
                        old = json.load(f)
                except Exception:
                    old = []
                if isinstance(old, list):
                    old.append(record)
                else:
                    old = [old, record]
                data_to_write = old
            else:
                data_to_write = [record]
            with open(json_path, "w") as f:
                json.dump(data_to_write, f, indent=2)
            print(f"Saved line points → {os.path.basename(json_path)}")
            # Remember the chosen line (in µm) for later use by multiple add+map
            try:
                # Prefer the parsed center from filename to ensure the same frame-of-reference
                center_um_for_template = globals().get("LAST_CENTER_UM", None)

                if center_um_for_template is None:
                    # Fallback: compute center from current axes
                    x0, x1 = ax_xy.get_xlim()
                    y0, y1 = ax_xy.get_ylim()
                    center_um_for_template = (0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.0)
                    print(f"[TEMPLATE:FALLBACK] Using axes center {center_um_for_template} for template")

                ok = set_profile_template_from_points(p0_um, p1_um, center_um_for_template)
                if not ok:
                    print("[TEMPLATE] set_profile_template_from_points failed; template not saved.")
                else:
                    print("[TEMPLATE] set_profile_template_from_points OK; template ready for add+map.")

                PROFILE_STATE["points_um"] = [tuple(p0_um), tuple(p1_um)]
                print(f"Saved cross-section for add+map multiple: "
                      f"({p0_um[0]:.3f},{p0_um[1]:.3f}) → ({p1_um[0]:.3f},{p1_um[1]:.3f}) µm")

            except Exception as _e:
                print(f"Warning: could not store cross-section: {_e}")


        except Exception as e:
            print(f"Warning: failed to save line JSON: {e}")

    def _make_profile_png_for_current(points_um, out_w_px=900, out_h_px=350, dpi=150):
        """
        Build a cross-section plot for the CURRENT image (using current processing,
        flips & smoothing) along the given two points in µm, and save to a temp PNG.
        Returns the PNG path or None on failure.
        """
        try:
            (x0_um, y0_um), (x1_um, y1_um) = points_um
        except Exception:
            return None

        try:
            # 1) Pull the exact image that matches what's being exported to PPT
            img2d = _get_img2d_for_profile()  # uses current processing pipeline
            img2d = np.asarray(img2d, dtype=float)

            # 2) Map µm → pixel using the current XY image extent
            extent = im_xy.get_extent()  # [xmin, xmax, ymin, ymax]
            H, W = img2d.shape[:2]
            xs_pix = lambda x: (x - extent[0]) * (W - 1) / max(1e-12, (extent[1] - extent[0]))
            ys_pix = lambda y: (y - extent[2]) * (H - 1) / max(1e-12, (extent[3] - extent[2]))

            x0p, y0p = xs_pix(x0_um), ys_pix(y0_um)
            x1p, y1p = xs_pix(x1_um), ys_pix(y1_um)

            # 3) Sample ~1 point per pixel along the line
            L = int(max(2, np.hypot(x1p - x0p, y1p - y0p)))
            t = np.linspace(0.0, 1.0, L)
            xs = x0p + (x1p - x0p) * t
            ys = y0p + (y1p - y0p) * t
            prof = _bilinear_profile_array(img2d, xs, ys)

            # 4) Build a clean, wide figure with distance scale in µm
            #    distance per step in µm (euclid in world coords)
            step_um = np.hypot((x1_um - x0_um), (y1_um - y0_um)) / max(1, L - 1)
            dist_um = np.arange(L) * step_um

            import tempfile, os
            from matplotlib import pyplot as _plt

            figP = _plt.figure(figsize=(out_w_px / dpi, out_h_px / dpi), dpi=dpi)
            axP = figP.add_subplot(111)
            axP.plot(dist_um, prof, lw=1.5)
            axP.set_xlabel("Distance (µm)")
            axP.set_ylabel("Intensity (a.u.)")
            axP.set_title("Cross-section")
            axP.grid(True, alpha=0.3)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            tmp_path = tmp.name
            tmp.close()
            figP.savefig(tmp_path, bbox_inches="tight", dpi=dpi)
            _plt.close(figP)
            return tmp_path
        except Exception as e:
            print(f"⚠️ Profile image render failed: {e}")
            return None

    def _bilinear_profile_array(img2d, xs_pix, ys_pix):
        """Bilinear sample of 2D array at fractional (x,y) pixel coords."""
        H, W = img2d.shape[:2]
        xs = np.asarray(xs_pix);
        ys = np.asarray(ys_pix)
        x0 = np.clip(np.floor(xs).astype(int), 0, W - 1);
        x1 = np.clip(x0 + 1, 0, W - 1)
        y0 = np.clip(np.floor(ys).astype(int), 0, H - 1);
        y1 = np.clip(y0 + 1, 0, H - 1)
        dx = xs - x0;
        dy = ys - y0
        Ia = img2d[y0, x0];
        Ib = img2d[y0, x1];
        Ic = img2d[y1, x0];
        Id = img2d[y1, x1]
        top = Ia * (1 - dx) + Ib * dx
        bot = Ic * (1 - dx) + Id * dx
        return top * (1 - dy) + bot * dy

    btn_lineplot.on_clicked(_on_lineplot_button)

    # --- Button: 8 line plots ---
    ax_lp8 = plt.axes(btn_rect_col2)
    btn_lp8 = Button(ax_lp8, '8 line plots')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    # --- 8 line plots state ---
    _lp8_clicks = []  # will hold 4 points: top(p0,p1), bottom(p2,p3)
    _lp8_cid = None
    _lp8_axes = []  # small profile axes (8 of them)
    _lp8_artists = []  # temporary markers/lines drawn on ax_img

    def _lp8_get_image_and_converters():
        """Return (im, d2p) where:
           im  = the AxesImage shown on ax_img
           d2p = function (x_data, y_data) -> (x_pix, y_pix) for sampling
        """
        im = None
        for _im in ax_xy.get_images():
            im = _im
            break
        if im is None:
            return None, None

        x0, x1, y0, y1 = im.get_extent()
        arr = np.asarray(im.get_array())
        H, W = arr.shape[:2]
        # origin is 'upper' by default in imshow; flip_y if so
        try:
            origin = im.origin
        except Exception:
            origin = im.get_origin()
        flip_y = (origin != 'lower')

        sx = (W - 1) / (x1 - x0)
        sy = (H - 1) / (y1 - y0)

        def d2p(x, y):
            ix = (x - x0) * sx
            iy = (y - y0) * sy
            if flip_y:
                iy = (H - 1) - iy
            return ix, iy

        return im, d2p

    def _get_img2d_for_profile():
        """Return the current 2D image slice used for profiles (same as line plot)."""
        try:
            C = _current_processed_cube_no_log()
            img = C[z_idx] if C.ndim == 3 else C
        except Exception:
            img = I_view[z_idx] if I_view.ndim == 3 else I_view
        return np.asarray(_maybe_flip(_smooth2d(img)), dtype=float)

    def _um_to_px(xs_um, ys_um, extent, img_shape):
        """Map data coords (µm) from ax_xy to pixel indices of img2d."""
        xmin, xmax, ymin, ymax = extent
        H, W = img_shape
        xs = (np.asarray(xs_um) - xmin) / max(1e-12, (xmax - xmin)) * (W - 1)
        ys = (np.asarray(ys_um) - ymin) / max(1e-12, (ymax - ymin)) * (H - 1)
        return xs, ys

    if '_bilinear_profile' not in globals():
        def _bilinear_profile(img, xs, ys):
            H, W = img.shape[:2]
            xs = np.asarray(xs);
            ys = np.asarray(ys)
            x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
            x1 = np.clip(x0 + 1, 0, W - 1)
            y0 = np.clip(np.floor(ys).astype(int), 0, H - 1)
            y1 = np.clip(y0 + 1, 0, H - 1)
            dx = xs - x0;
            dy = ys - y0
            Ia = img[y0, x0];
            Ib = img[y0, x1];
            Ic = img[y1, x0];
            Id = img[y1, x1]
            top = Ia * (1 - dx) + Ib * dx
            bot = Ic * (1 - dx) + Id * dx
            return top * (1 - dy) + bot * dy

    def _lp8_current_img2d():
        """Return the 2D image currently shown in ax_xy, matching your display pipeline."""
        try:
            C = _current_processed_cube_no_log()  # already defined in this file
        except Exception:
            # Fallback to the view buffer
            a = I_view[z_idx] if I_view.ndim == 3 else I_view
            try:
                return _maybe_flip(_smooth2d(a))
            except Exception:
                return a

        img = C[z_idx] if C.ndim == 3 else C
        try:
            return _maybe_flip(_smooth2d(img))
        except Exception:
            return img

    def _get_bilinear_profile_func():
        fn = globals().get("_bilinear_profile", None)
        if callable(fn):
            return fn

        # fallback local implementation
        def _bilinear_profile_local(img, xs, ys):
            H, W = img.shape[:2]
            xs = np.asarray(xs)
            ys = np.asarray(ys)
            x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
            x1 = np.clip(x0 + 1, 0, W - 1)
            y0 = np.clip(np.floor(ys).astype(int), 0, H - 1)
            y1 = np.clip(y0 + 1, 0, H - 1)
            dx = xs - x0
            dy = ys - y0
            Ia = img[y0, x0]
            Ib = img[y0, x1]
            Ic = img[y1, x0]
            Id = img[y1, x1]
            top = Ia * (1 - dx) + Ib * dx
            bot = Ic * (1 - dx) + Id * dx
            return top * (1 - dy) + bot * dy

        return _bilinear_profile_local

    def _get_img_axes():
        """
        Return the axes that shows the main image.
        Tries common globals, then scans the figure for an axes with an image.
        """
        # common global names you may already use in this file
        for name in ("ax_img", "ax_xy", "ax_main", "ax"):
            ax = globals().get(name, None)
            if ax is not None and hasattr(ax, "images") and len(ax.images) > 0:
                return ax
        # scan figure for an axes that actually contains an image
        fig = plt.gcf()
        for ax in fig.axes:
            if getattr(ax, "_is_main_image_axes", False):
                return ax
            if hasattr(ax, "images") and len(ax.images) > 0:
                return ax
        return None

    def _lp8_ensure_state():
        global _lp8_clicks, _lp8_cid, _lp8_axes, _lp8_artists
        if '_lp8_clicks' not in globals(): _lp8_clicks = []
        if '_lp8_cid' not in globals(): _lp8_cid = None
        if '_lp8_axes' not in globals(): _lp8_axes = []
        if '_lp8_artists' not in globals(): _lp8_artists = []

    def _on_lp8_button(event=None):
        _lp8_ensure_state()
        _lp8_enable_pick()

    def _lp8_enable_pick():
        _lp8_ensure_state()
        global _lp8_cid, _lp8_clicks, _lp8_artists
        _lp8_clicks = []
        # clear any previous temp artists
        for a in list(_lp8_artists):
            try:
                a.remove()
            except Exception:
                pass
        _lp8_artists.clear()

        # (re)connect click handler
        fig = plt.gcf()
        if _lp8_cid is not None:
            try:
                fig.canvas.mpl_disconnect(_lp8_cid)
            except Exception:
                pass
            _lp8_cid = None
        _lp8_cid = fig.canvas.mpl_connect('button_press_event', _lp8_on_click)
        print("8 line plots: click two points on TOP waveguide, then two on BOTTOM.")

    def _lp8_disable_pick():
        global _lp8_cid
        if _lp8_cid is not None:
            try:
                plt.gcf().canvas.mpl_disconnect(_lp8_cid)
            except Exception:
                pass
            _lp8_cid = None

    def _lp8_on_click(event):
        global _lp8_clicks, _lp8_artists
        if event.inaxes != ax_xy or event.button != 1:
            return
        x, y = float(event.xdata), float(event.ydata)
        _lp8_clicks.append((x, y))
        _lp8_artists.append(ax_xy.plot(x, y, 'o', ms=7, mfc='none', mew=2)[0])
        # visual feedback
        ax_xy.plot(x, y, 'o', ms=6, mfc='none', mew=1)
        plt.gcf().canvas.draw_idle()

        if len(_lp8_clicks) == 2:
            _lp8_artists.append(ax_xy.plot(
                [_lp8_clicks[0][0], _lp8_clicks[1][0]],
                [_lp8_clicks[0][1], _lp8_clicks[1][1]], '-', lw=2
            )[0])
            plt.gcf().canvas.draw_idle()
            print("Now pick two points on the BOTTOM waveguide.")

        if len(_lp8_clicks) == 4:
            _lp8_disable_pick()
            _lp8_run_profiles(_lp8_clicks)

    def _lp8_run_profiles(pts):
        """Create 8 interpolated line profiles between the two chosen lines."""
        fig = plt.gcf()
        global _lp8_axes
        # —— NEW: get the displayed 2D image like the line-plot does
        try:
            img2d = np.asarray(im_xy.get_array())
        except Exception:
            img2d = None
        if img2d is None:
            try:
                img2d = _maybe_flip(_smooth2d(I_view[z_idx]))
            except Exception:
                print("8 line plots: image array (img2d) not found.")
                return

        (x0t, y0t), (x1t, y1t), (x0b, y0b), (x1b, y1b) = pts
        # 8 lines: t ∈ {0,1/7,...,1}; 1=top, 8=bottom
        ts = [i / 7 for i in range(8)]
        pairs = [((x0t + (x0b - x0t) * t, y0t + (y0b - y0t) * t),
                  (x1t + (x1b - x1t) * t, y1t + (y1b - y1t) * t)) for t in ts]

        # Draw the 8 lines on the image (thin overlays)
        for (p0, p1) in pairs:
            ax_xy.plot([p0[0], p1[0]], [p0[1], p1[1]], '-', lw=1)

        _make_lp8_axes()  # axes already arranged in one column earlier
        if len(_lp8_axes) != 8:
            print(f"8 line plots: expected 8 axes, found {len(_lp8_axes)}; aborting.")
            return

        # 3) Provide the same bilinear sampler if not already present
        if '_bilinear_profile' not in globals():
            def _bilinear_profile(img, xs, ys):
                H, W = img.shape[:2]
                xs = np.asarray(xs)
                ys = np.asarray(ys)
                x0 = np.clip(np.floor(xs).astype(int), 0, W - 1)
                x1 = np.clip(x0 + 1, 0, W - 1)
                y0 = np.clip(np.floor(ys).astype(int), 0, H - 1)
                y1 = np.clip(y0 + 1, 0, H - 1)
                dx = xs - x0
                dy = ys - y0
                Ia = img[y0, x0]
                Ib = img[y0, x1]
                Ic = img[y1, x0]
                Id = img[y1, x1]
                top = Ia * (1 - dx) + Ib * dx
                bot = Ic * (1 - dx) + Id * dx
                return top * (1 - dy) + bot * dy

        # Get image + converters and array for sampling
        im, d2p = _lp8_get_image_and_converters()
        if im is None or d2p is None:
            print("8 line plots: image array (img2d) not found.")
            return
        img2d = np.asarray(im.get_array())

        for i, ((xa, ya), (xb, yb)) in enumerate(pairs):
            # convert data->pixel for sampling
            ix0, iy0 = d2p(xa, ya)
            ix1, iy1 = d2p(xb, yb)

            L = int(np.hypot(ix1 - ix0, iy1 - iy0)) + 1
            xs_pix = np.linspace(ix0, ix1, L)
            ys_pix = np.linspace(iy0, iy1, L)
            prof = _bilinear_profile(img2d, xs_pix, ys_pix)

            axp = _lp8_axes[i]
            axp.clear()
            axp.plot(np.arange(L), prof)
            axp.set_title(f"Line {i + 1}, y-{ya:.2f}", fontsize=8)
            axp.set_xlabel("px", fontsize=8)
            axp.set_ylabel("I", fontsize=8)
            axp.tick_params(labelsize=8)

        fig.canvas.draw_idle()
        _lp8_save_points(pts)

    def _lp8_layout_rects():
        """Positions for 8 small axes in a single column at left-top."""
        left, top = 0.17, 0.92  # figure coords
        w, h = 0.18, 0.08
        gap = 0.03
        rects = []
        for i in range(8):
            bottom = top - (i + 1) * h - i * gap
            rects.append([left, bottom, w, h])
        return rects

    def _make_lp8_axes():
        """Always recreate 8 profile axes laid out by _lp8_layout_rects()."""
        global _lp8_axes
        fig = plt.gcf()
        # remove any existing lp8 axes
        for ax in list(fig.axes):
            if getattr(ax, "_is_lp8", False):
                try:
                    ax.remove()
                except Exception:
                    pass

        rects = _lp8_layout_rects()
        _lp8_axes = []
        for i, rect in enumerate(rects):
            ax = fig.add_axes(rect)
            ax._is_lp8 = True
            ax._lp8_index = i
            ax.set_title(f"Line {i + 1}", fontsize=8)
            ax.tick_params(labelsize=8)
            _lp8_axes.append(ax)

    def _lp8_save_points(pts):
        """Save the 4 chosen points (top two, bottom two) to JSON next to the image."""
        import json, time
        (x0t, y0t), (x1t, y1t), (x0b, y0b), (x1b, y1b) = pts

        # decide target path
        folder, stem = ".", "lp8_points"
        try:
            folder, name = os.path.split(CURRENT_IMAGE_PATH)  # if tracked elsewhere in your script
            stem, _ = os.path.splitext(name)
        except Exception:
            pass
        json_path = os.path.join(folder, f"{stem}_lp8.json")

        record = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "image_path": (CURRENT_IMAGE_PATH if 'CURRENT_IMAGE_PATH' in globals() else None),
            "top_points": [{"x": x0t, "y": y0t}, {"x": x1t, "y": y1t}],
            "bottom_points": [{"x": x0b, "y": y0b}, {"x": x1b, "y": y1b}],
        }

        # append to file (keep a list history)
        try:
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    old = json.load(f)
                if isinstance(old, list):
                    old.append(record)
                    data_to_write = old
                else:
                    data_to_write = [old, record]
            else:
                data_to_write = [record]

            with open(json_path, "w") as f:
                json.dump(data_to_write, f, indent=2)
            print(f"Saved 4 points → {os.path.basename(json_path)}")
        except Exception as e:
            print(f"Warning: failed to save lp8 JSON: {e}")

    # wire the button
    btn_lp8.on_clicked(_on_lp8_button)

    # --- Button: apply 8 profiles (from JSON) ---
    ax_lp8_apply = plt.axes(btn_rect_col2)
    btn_lp8_apply = Button(ax_lp8_apply, 'apply 8 profiles')
    btn_rect_col2 = shift_rect2(btn_rect_col2)

    def _lp8_ensure_state():
        global _lp8_clicks, _lp8_cid, _lp8_axes, _lp8_artists
        if '_lp8_clicks' not in globals(): _lp8_clicks = []
        if '_lp8_cid' not in globals(): _lp8_cid = None
        if '_lp8_axes' not in globals(): _lp8_axes = []
        if '_lp8_artists' not in globals(): _lp8_artists = []

    def _on_lp8_apply_button(event=None):
        _lp8_apply_from_json()

    def _lp8_apply_from_json():
        _lp8_ensure_state()
        global _lp8_artists
        import os, json

        # derive the same JSON path used in _lp8_save_points(...)
        try:
            folder, name = os.path.split(CURRENT_IMAGE_PATH)
            stem, _ = os.path.splitext(name)
        except Exception:
            folder, stem = ".", "lp8_points"
        json_path = os.path.join(folder, f"{stem}_lp8.json")

        if not os.path.exists(json_path):
            print(f"apply 8 profiles: JSON not found: {json_path}")
            return

        try:
            with open(json_path, "r") as f:
                data = json.load(f)
            rec = data[-1] if isinstance(data, list) else data
            if "top_points" in rec and "bottom_points" in rec:
                tp, bp = rec["top_points"], rec["bottom_points"]
                pts = [(tp[0]["x"], tp[0]["y"]),
                       (tp[1]["x"], tp[1]["y"]),
                       (bp[0]["x"], bp[0]["y"]),
                       (bp[1]["x"], bp[1]["y"])]
            elif "points" in rec and len(rec["points"]) >= 4:  # backward compat
                p = rec["points"]
                pts = [(p[0]["x"], p[0]["y"]), (p[1]["x"], p[1]["y"]),
                       (p[2]["x"], p[2]["y"]), (p[3]["x"], p[3]["y"])]
            else:
                print("apply 8 profiles: JSON missing 4 points.")
                return
        except Exception as e:
            print(f"apply 8 profiles: failed to read JSON: {e}")
            return

        # clear overlays and draw using saved points
        for a in list(_lp8_artists):
            try:
                a.remove()
            except Exception:
                pass
        _lp8_artists.clear()

        print("apply 8 profiles: using saved points.")
        _lp8_run_profiles(pts)

    # wire the button
    btn_lp8_apply.on_clicked(_on_lp8_apply_button)

    # --- Button: view frames (multi-page TIFF) ---
    ax_view_frames = plt.axes(btn_rect_col2)
    btn_view_frames = Button(ax_view_frames, 'view frames')
    btn_rect_col2 = shift_rect2(btn_rect_col2)
    _movie_fps = 15  # default FPS for saved movie

    def _handle_view_frames(_evt=None):
        # pick a .tif/.tiff
        try:
            from tkinter import Tk, filedialog
            root = Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Select multi-frame TIFF",
                filetypes=[("TIFF Files", "*.tif *.tiff")])
            try:
                root.destroy()
            except Exception:
                pass
        except Exception:
            print("Could not open file dialog.");
            return
        if not path:
            print("Canceled.");
            return

        # read stack (Z,Y,X)
        try:
            try:
                import tifffile as tiff
                stack = tiff.imread(path)
            except Exception:
                import imageio.v3 as iio
                stack = iio.imread(path, index=None)
            arr = np.asarray(stack, dtype=np.float64)
        except Exception as e:
            print(f"Failed to read TIFF: {e}");
            return

        arr = np.squeeze(arr)
        # RGB(A) → gray
        if arr.ndim == 4 and arr.shape[-1] in (3, 4):
            arr = arr[..., :3].mean(axis=-1)
        # If single frame, just show and exit
        if arr.ndim == 2:
            figV, axV = plt.subplots(1, 1, figsize=(12, 10))
            imV = axV.imshow(arr, origin='lower', aspect='equal')
            axV.set_title(f"{os.path.basename(path)} (single frame)")
            figV.colorbar(imV, ax=axV, label="a.u.")
            plt.show(block=False)
            return
        if arr.ndim != 3:
            print(f"Unexpected TIFF shape: {arr.shape}");
            return

        Z, H, W = arr.shape
        figV, axV = plt.subplots(1, 1, figsize=(10, 7))
        plt.subplots_adjust(bottom=0.12)
        imV = axV.imshow(arr[0], origin='lower', aspect='equal')
        cbarV = figV.colorbar(imV, ax=axV, label="a.u.")
        axV.set_title(f"{os.path.basename(path)} — frame 1 / {Z}")

        # slider
        from matplotlib.widgets import Slider
        axVz = plt.axes([0.15, 0.04, 0.7, 0.03])
        sVz = Slider(axVz, 'frame', 1, Z, valinit=1, valstep=1)
        vmin, vmax = float(np.nanmin(arr)), float(np.nanmax(arr))
        imV.set_clim(vmin, vmax)

        def _upd(_):
            k = int(sVz.val) - 1
            imV.set_data(arr[k])
            axV.set_title(f"{os.path.basename(path)} — frame {k + 1} / {Z}")
            figV.canvas.draw_idle()

        sVz_cid = sVz.on_changed(_upd)

        # keyboard ←/→
        def _on_key(ev):
            if ev.key == 'right':
                sVz.set_val(min(Z, sVz.val + 1))
            elif ev.key == 'left':
                sVz.set_val(max(1, sVz.val - 1))

        figV.canvas.mpl_connect('key_press_event', _on_key)

        # --- Normalize frames by reference point (small circle) ---
        from matplotlib.widgets import Button
        # Bigger button at top-left of the viewer figure (figure coords)
        axBtnRef = figV.add_axes([0.02, 0.94, 0.16, 0.05])  # left, bottom, w, h
        btnPickRef = Button(axBtnRef, 'Pick Ref (R)')

        # keep originals & working copy
        arr0 = arr.copy()  # original stack
        arrN = arr.copy()  # normalized stack (displayed)
        sVz_cid = None  # holds the slider on_changed connection id

        ref_artist = None
        pick_cid = None
        ref_radius = 5  # pixels (circle radius)

        def _apply_norm_at(xc, yc):
            """Normalize each frame so mean in a small circle around (xc,yc) matches frame 1."""
            nonlocal arrN
            H, W = arr0.shape[1], arr0.shape[2]
            yy, xx = np.ogrid[:H, :W]
            mask = (xx - xc) ** 2 + (yy - yc) ** 2 <= (ref_radius ** 2)

            # target = mean of frame 0 within mask
            with np.errstate(invalid='ignore'):
                target = float(np.nanmean(arr0[0][mask]))
            if not np.isfinite(target) or target == 0:
                print("Normalization skipped: invalid target intensity.")
                return

            arrN = np.empty_like(arr0, dtype=float)
            for k in range(arr0.shape[0]):
                with np.errstate(invalid='ignore'):
                    m = float(np.nanmean(arr0[k][mask]))
                scale = (target / m) if (np.isfinite(m) and m != 0) else 1.0
                arrN[k] = arr0[k] * scale

            # refresh current frame view and color scale using normalized stack
            kcur = int(sVz.val) - 1
            imV.set_data(arrN[kcur])
            vminN, vmaxN = float(np.nanmin(arrN)), float(np.nanmax(arrN))
            imV.set_clim(vminN, vmaxN)
            cbarV.update_normal(imV)
            figV.canvas.draw_idle()
            print(f"Applied normalization at ({xc:.1f}, {yc:.1f}) with r={ref_radius}px.")

        def _on_pick_click(ev):
            nonlocal ref_artist, pick_cid
            nonlocal sVz_cid

            if ev.inaxes != axV or ev.button != 1:
                return
            xc, yc = float(ev.xdata), float(ev.ydata)

            # draw/replace a small circle marker
            try:
                if ref_artist is not None:
                    ref_artist.remove()
            except Exception:
                pass
            th = np.linspace(0, 2 * np.pi, 100)
            xs = xc + ref_radius * np.cos(th)
            ys = yc + ref_radius * np.sin(th)
            ref_artist, = axV.plot(xs, ys, '-', lw=1.5)
            figV.canvas.draw_idle()

            # disconnect pick mode and apply normalization
            if pick_cid is not None:
                figV.canvas.mpl_disconnect(pick_cid)
                pick_cid = None
            _apply_norm_at(xc, yc)

            # make slider show normalized frames from now on
            def _upd_norm(_):
                k = int(sVz.val) - 1
                imV.set_data(arrN[k])
                axV.set_title(f"{os.path.basename(path)} — frame {k + 1} / {Z}")
                figV.canvas.draw_idle()

            try:
                if sVz_cid is not None:
                    sVz.disconnect(sVz_cid)
            except Exception:
                pass
            sVz.on_changed(_upd_norm)

        def _start_pick_ref(_evt=None):
            nonlocal pick_cid
            # connect one-shot click picker
            if pick_cid is not None:
                try:
                    figV.canvas.mpl_disconnect(pick_cid)
                except Exception:
                    pass
                pick_cid = None
            pick_cid = figV.canvas.mpl_connect('button_press_event', _on_pick_click)
            print("Click a point to define the normalization reference (small circle).")

        btnPickRef.on_clicked(_start_pick_ref)

        # --- add: top-left small button to save movie ---
        ax_save_movie = plt.axes([0.01, 0.92, 0.10, 0.05])  # top-left
        btn_save_movie = Button(ax_save_movie, 'Save Movie (M)')

        def _save_normalized_movie():
            try:
                # choose which stack to save
                stack = None
                if 'norm_stack' in globals() and norm_stack is not None:
                    stack = norm_stack
                elif 'img_stack' in globals() and img_stack is not None:
                    stack = img_stack
                else:
                    print("Save Movie: no stack available.")
                    return

                # get display scaling from current image
                if 'im_obj' in globals() and im_obj is not None:
                    vmin, vmax = im_obj.get_clim()
                else:
                    vmin, vmax = float(np.nanmin(stack)), float(np.nanmax(stack))
                if vmax <= vmin:
                    vmax = vmin + 1.0

                # uint8 frames using current display range
                def to_u8(frame):
                    f = (frame - vmin) / (vmax - vmin)
                    f = np.clip(f, 0, 1)
                    return (f * 255).astype(np.uint8)

                frames_u8 = [to_u8(f) for f in stack]

                # output path
                folder, stem = ".", "movie"
                try:
                    folder, name = os.path.split(CURRENT_IMAGE_PATH)
                    stem, _ = os.path.splitext(name)
                except Exception:
                    pass
                out_path = os.path.join(folder, f"{stem}_normalized.mp4")

                # write mp4
                iio.imwrite(out_path, frames_u8, fps=_movie_fps, codec="h264", quality=8)
                print(f"Saved movie → {out_path}  (fps={_movie_fps})")
            except Exception as e:
                print(f"Save Movie: failed → {e}")

        btn_save_movie.on_clicked(lambda evt: _save_normalized_movie())

        # extend existing handler:
        def _on_key(event):
            k = (event.key or "").lower()
            if k == 'r':
                _begin_pick_reference()  # your existing function
            elif k == 'm':
                _save_normalized_movie()

        figV.canvas.mpl_connect('key_press_event', _on_key)

        plt.show(block=False)

    btn_view_frames.on_clicked(_handle_view_frames)

    # ----------------    Quit Button    ----------------
    ax_quit = plt.axes(btn_rect_col2)
    btn_quit = Button(ax_quit, 'Quit')
    btn_rect = shift_rect2(btn_rect_col2)

    def _quit_app(_evt=None):
        try:
            import matplotlib.pyplot as _plt
            _plt.close('all')  # close all MPL windows
        except Exception:
            pass
        # If you have a Tk root, close it too (safe no-op if not present)
        try:
            if 'root' in globals() and root:
                root.after(50, root.destroy)
        except Exception:
            pass
        # Optional: end the process (uncomment if you want a hard exit)
        # import sys
        # try:
        #     sys.exit(0)
        # except SystemExit:
        #     pass
        print("[UI] Quit requested — windows closed.")

    btn_quit.on_clicked(_quit_app)

    ######

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

    def _save_map_calib(mode,
                        px_per_um_x, px_per_um_y, xmin_um, ymax_um,
                        p1_px=None, p2_px=None,
                        p1_um=None, p2_um=None):
        d = {
            "mode": mode,
            "px_per_um_x": float(px_per_um_x),
            "px_per_um_y": float(px_per_um_y),
            "xmin_um": float(xmin_um),
            "ymax_um": float(ymax_um),
        }

        # store where we actually clicked (for debug overlays)
        if p1_px is not None and p2_px is not None:
            d["clicked_px"] = {
                "P1": [float(p1_px[0]), float(p1_px[1])],
                "P2": [float(p2_px[0]), float(p2_px[1])],
            }
        if p1_um is not None and p2_um is not None:
            d["clicked_um"] = {
                "P1": [float(p1_um[0]), float(p1_um[1])],
                "P2": [float(p2_um[0]), float(p2_um[1])],
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

def open_check_map_calibration(folder=None):
    """
    Open an interactive calibration-check window:
    - Shows current calibration dots over map
    - Lets user tune DX,DY (shift) and ScaleX,ScaleY
    - Saves updated calibration back to MAP_CALIB_PATH
    """
    import os, json, re
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider
    from PIL import Image

    # --- local helper: extract Site(x,y) center from filename ---
    def _parse_site_center_from_name(name: str):
        """
        Parse patterns like 'Site (-8642,1 1494,3 -785,6)' and return (x_um, y_um, z_um)
        """
        if not name:
            return None
        m = re.search(r"Site\s*\(([-\d,\.]+)\s+([-\d,\.]+)(?:\s+([-\d,\.]+))?", name)
        if not m:
            return None
        try:
            x = float(m.group(1).replace(",", "."))
            y = float(m.group(2).replace(",", "."))
            z = float(m.group(3).replace(",", ".")) if m.group(3) else 0.0
            return (x, y, z)
        except Exception:
            return None

    # ---------- Load map + calibration ----------
    try:
        base = Image.open(MAP_IMAGE_PATH).convert("RGB")
    except Exception as e:
        print(f"⚠️ Map image error: {e}")
        return

    W, H = base.size

    if not os.path.isfile(MAP_CALIB_PATH):
        print(f"❌ No calibration file found: {MAP_CALIB_PATH}")
        return
    with open(MAP_CALIB_PATH, "r", encoding="utf-8") as f:
        cal = json.load(f)

    # original calibration (we'll modify a scaled version of these)
    px_per_um_x0 = float(cal["px_per_um_x"])
    px_per_um_y0 = float(cal["px_per_um_y"])
    xmin_um0 = float(cal["xmin_um"])
    ymax_um0 = float(cal["ymax_um"])

    # ---------- Load site centers from folder ----------
    if folder is None:
        from tkinter.filedialog import askdirectory
        folder = askdirectory(title="Select folder with TIFFs")

    if not folder:
        print("Canceled.")
        return

    tifs = [os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".tif", ".tiff"))]
    if not tifs:
        print("No TIFF files found in folder.")
        return

    centers_um = []
    for p in tifs:
        c = _parse_site_center_from_name(os.path.basename(p))
        if not c:
            continue
        try:
            x_um = float(str(c[0]).replace(",", "."))
            y_um = float(str(c[1]).replace(",", "."))
            centers_um.append((x_um, y_um))
        except Exception:
            pass

    if not centers_um:
        print("No usable Site(x,y) in filenames.")
        return

    # helper: world (µm) -> pixel using current calib params
    def world_to_pixel(cx_um, cy_um, px_per_um_x, px_per_um_y, xmin_um, ymax_um):
        px = (cx_um - xmin_um) * px_per_um_x
        py = (ymax_um - cy_um) * px_per_um_y
        return px, py

    # ---------- Build figure ----------
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.imshow(base)
    ax.set_title(f"Map calibration check: {len(centers_um)} sites\nFolder: {os.path.basename(folder)}")

    # initial positions (no shift/scale yet)
    xs0, ys0 = [], []
    for (cx, cy) in centers_um:
        px, py = world_to_pixel(cx, cy, px_per_um_x0, px_per_um_y0, xmin_um0, ymax_um0)
        xs0.append(px)
        ys0.append(py)

    scat, = ax.plot(xs0, ys0, 'r.', markersize=3)

    # Green X markers for P1/P2 (if present in JSON)
    clicked_px = cal.get("clicked_px") or {}
    for lbl in ("P1", "P2"):
        pt = clicked_px.get(lbl)
        if pt and len(pt) == 2:
            cx, cy = pt
            ax.plot(cx, cy, 'gx', markersize=14, mew=2.5, zorder=6)
            ax.text(cx + 10, cy - 10, lbl,
                    color='lime', fontsize=10, weight='bold',
                    bbox=dict(facecolor='black', alpha=0.4, edgecolor='none'))

    ax.set_xlim(0, W)
    ax.set_ylim(H, 0)

    # ---------- Interactive state: shift + scale ----------
    dx_val = 0.0  # pixels
    dy_val = 0.0  # pixels
    sx_val = 1.0  # scale factor for px_per_um_x
    sy_val = 1.0  # scale factor for px_per_um_y

    def update_plot():
        px_per_um_x = px_per_um_x0 * sx_val
        px_per_um_y = px_per_um_y0 * sy_val
        xs, ys = [], []
        for (cx, cy) in centers_um:
            px, py = world_to_pixel(cx, cy, px_per_um_x, px_per_um_y, xmin_um0, ymax_um0)
            xs.append(px + dx_val)
            ys.append(py + dy_val)
        scat.set_data(xs, ys)
        fig.canvas.draw_idle()

    # call once to ensure consistent internal state
    update_plot()

    # ---------- Buttons & sliders ----------
    ax_up    = plt.axes([0.86, 0.15, 0.06, 0.05])
    ax_down  = plt.axes([0.86, 0.05, 0.06, 0.05])
    ax_left  = plt.axes([0.79, 0.10, 0.06, 0.05])
    ax_right = plt.axes([0.93, 0.10, 0.06, 0.05])
    ax_save  = plt.axes([0.79, 0.20, 0.20, 0.05])

    ax_step  = plt.axes([0.79, 0.27, 0.20, 0.03])
    ax_sx    = plt.axes([0.79, 0.32, 0.20, 0.03])
    ax_sy    = plt.axes([0.79, 0.37, 0.20, 0.03])

    btn_up    = Button(ax_up, '↑')
    btn_down  = Button(ax_down, '↓')
    btn_left  = Button(ax_left, '←')
    btn_right = Button(ax_right, '→')
    btn_save  = Button(ax_save, '💾 Save')

    s_step = Slider(ax_step, 'Step(px)', 1, 50, valinit=10, valstep=1)
    s_sx   = Slider(ax_sx, 'ScaleX', 0.8, 3, valinit=1.0, valstep=0.001)
    s_sy   = Slider(ax_sy, 'ScaleY', 0.8, 3, valinit=1.0, valstep=0.001)

    def nudge(dx=0, dy=0):
        nonlocal dx_val, dy_val
        step = float(s_step.val)
        dx_val += dx * step
        dy_val += dy * step
        update_plot()
        print(f"DX={dx_val:.2f}px, DY={dy_val:.2f}px")

    btn_up.on_clicked(lambda e: nudge(0, -1))
    btn_down.on_clicked(lambda e: nudge(0, +1))
    btn_left.on_clicked(lambda e: nudge(-1, 0))
    btn_right.on_clicked(lambda e: nudge(+1, 0))

    def on_sx(val):
        nonlocal sx_val
        sx_val = float(val)
        update_plot()
        print(f"ScaleX = {sx_val:.4f}")
    s_sx.on_changed(on_sx)

    def on_sy(val):
        nonlocal sy_val
        sy_val = float(val)
        update_plot()
        print(f"ScaleY = {sy_val:.4f}")
    s_sy.on_changed(on_sy)

    def save_offset(_):
        # new per-axis scales
        new_px_per_um_x = px_per_um_x0 * sx_val
        new_px_per_um_y = px_per_um_y0 * sy_val

        # convert pixel shifts to µm using NEW scales
        dx_um = dx_val / new_px_per_um_x
        dy_um = dy_val / new_px_per_um_y

        # adjust origin so that:
        # px_new = (cx - xmin_new)*new_px_per_um_x = px_orig*sx_val + dx_val
        cal["px_per_um_x"] = new_px_per_um_x
        cal["px_per_um_y"] = new_px_per_um_y
        cal["xmin_um"] = xmin_um0 - dx_um
        cal["ymax_um"] = ymax_um0 + dy_um

        with open(MAP_CALIB_PATH, "w", encoding="utf-8") as f:
            json.dump(cal, f, indent=2)

        print("💾 Saved updated calibration:")
        print(f"   px/µm_x = {cal['px_per_um_x']:.6f}, px/µm_y = {cal['px_per_um_y']:.6f}")
        print(f"   xmin_um = {cal['xmin_um']:.3f}, ymax_um = {cal['ymax_um']:.3f}")

    btn_save.on_clicked(save_offset)

    plt.show(block=True)

# from Utils.python_displayer import open_check_map_calibration
# open_check_map_calibration(r"C:\Users\Femto\Work Folders\Documents\LightField")
# import importlib, Utils.python_displayer as pd;importlib.reload(pd);pd.open_check_map_calibration(r"C:\Users\Femto\Work Folders\Documents\LightField")


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
    parser.add_argument("--multicalib", action="store_true",
                        help="Open a file picker and apply calibration to multiple TIFFs, then exit.")
    parser.add_argument("--calib", default=None,
                        help="Optional override for calibration TIFF path (used with --multicalib).")

    args = parser.parse_args()

    # NEW: headless batch-calibration mode
    if args.multicalib:
        run_multicalib_cli(calib_path=args.calib)
        sys.exit(0)

    # TIFF logic is handled inside display_all_z_slices
    display_all_z_slices(
        filepath=args.path,
        minI=args.vmin,
        maxI=args.vmax,
        log_scale=args.log,
    )


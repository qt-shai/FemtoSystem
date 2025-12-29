# Utils\plot_csv_spectrum.py
import os
import sys
import glob
import traceback

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import pythoncom
import win32com.client

from scipy.signal import savgol_filter



CSV_DIR = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"
def merge_spectra_union_average(spectra, ignore_start: int = 0):
    """
    Merge spectra into one on a union X grid.
    Each spectrum contributes only in its own wavelength range.
    Where multiple overlap, average them.
    """
    if not spectra:
        raise ValueError("No spectra to merge")

    # Global min/max
    x_lo = min(float(np.min(s["x"])) for s in spectra)
    x_hi = max(float(np.max(s["x"])) for s in spectra)

    # Use finest median dx
    dxs = []
    for s in spectra:
        x = s["x"]
        if len(x) >= 2:
            dxs.append(float(np.median(np.diff(x))))
    dx = min(dxs) if dxs else 1.0

    x_common = np.arange(x_lo, x_hi + 0.5 * dx, dx)

    # Accumulate sum and count only where the spectrum is defined
    y_sum = np.zeros_like(x_common, dtype=float)
    y_cnt = np.zeros_like(x_common, dtype=float)

    for s in spectra:
        x = s["x"]
        y = s["y"]

        # ignore first N samples of this spectrum
        if ignore_start > 0 and len(x) > ignore_start:
            x_use = x[ignore_start:]
            y_use = y[ignore_start:]
        else:
            x_use = x
            y_use = y

        if len(x_use) < 2:
            continue

        mask = (x_common >= x_use.min()) & (x_common <= x_use.max())
        if not np.any(mask):
            continue

        y_interp = np.interp(x_common[mask], x_use, y_use)
        y_sum[mask] += y_interp
        y_cnt[mask] += 1

    y_merged = np.full_like(x_common, np.nan, dtype=float)
    ok = y_cnt > 0
    y_merged[ok] = y_sum[ok] / y_cnt[ok]

    return x_common, y_merged

def load_calibration_csv(calib_csv: str):
    data = np.genfromtxt(calib_csv, delimiter=",", skip_header=1)
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"Bad calibration CSV (need 2 cols): {calib_csv}")
    x = data[:, 0]
    y = data[:, 1]
    order = np.argsort(x)
    return x[order], y[order]

def choose_csv_files_dialog(title: str = "Select CSV files",initial_dir: str | None = None):
    """
    Open a native file dialog to select multiple CSV files.
    Returns a list of paths (possibly empty).
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        paths = filedialog.askopenfilenames(
            title=title,
            initialdir=initial_dir,
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        root.destroy()
        return list(paths) if paths else []
    except Exception as e:
        print(f"[runcsv] file dialog failed: {e}")
        return []

def apply_calibration(x: np.ndarray, y: np.ndarray, calib_x: np.ndarray, calib_y: np.ndarray):
    """
    Divide y by calibration curve evaluated at x.
    """
    # interpolate calib onto spectrum grid
    c = np.interp(x, calib_x, calib_y)

    # avoid divide-by-zero / tiny numbers
    eps = 1e-12
    c = np.where(np.abs(c) < eps, np.nan, c)

    y_cal = y / c
    return y_cal

def smooth_moving_average(y: np.ndarray, window: int = 11) -> np.ndarray:
    window = int(window)
    if window <= 1:
        return y
    if window % 2 == 0:
        window += 1
    pad = window // 2
    ypad = np.pad(y, (pad, pad), mode="reflect")
    kernel = np.ones(window, dtype=float) / float(window)
    return np.convolve(ypad, kernel, mode="valid")
def smooth_aggressive(y: np.ndarray, window: int = 51, poly: int = 3):
    """
    Aggressive but shape-preserving smoothing.
    window must be odd.
    """
    window = int(window)
    if window % 2 == 0:
        window += 1
    window = min(window, len(y) - (len(y) + 1) % 2)
    return savgol_filter(y, window_length=window, polyorder=poly)

def run_runcsv(
    n: int = 1,
    folder: str | None = None,
    *,
    title_text: str | None = None,
    smooth_window: int | None = None,   # used for final SavGol window if provided
    merge: bool = False,
):
    # Special: folder="?" means "pick files via dialog"
    if isinstance(folder, str) and folder.strip() == "?":
        csv_paths = choose_csv_files_dialog(title="Select CSV files to calibrate",initial_dir=CSV_DIR)
        if not csv_paths:
            print("[runcsv cal] no files selected.")
            return None
        # Use the selection folder as output dir
        folder = os.path.dirname(csv_paths[0]) or CSV_DIR
    else:
        folder = folder or CSV_DIR
        csv_paths = newest_csvs_in_folder(folder, n)

    # Load spectra (no heavy smoothing here; we smooth after merge)
    spectra = []
    for fp in csv_paths:
        x, y = load_spectrum_csv(fp)
        spectra.append({"file": os.path.basename(fp), "x": x, "y": y})

    out_dir = os.path.dirname(csv_paths[0]) or folder
    out_png = os.path.join(out_dir, "~csv_spectrum_plot.png")

    # ----------------------------
    # Merge (for calibration mode)
    # ----------------------------
    merged_out = None
    spectra_to_plot = spectra

    if merge and len(spectra) >= 2:
        # ignore start samples to avoid fake dips at segment joins
        x_common, y_merged = merge_spectra_union_average(spectra, ignore_start=20)

        # Aggressive smoothing AFTER stitching (SavGol)
        finite = np.isfinite(y_merged)
        y_f = y_merged[finite]

        # choose aggressive window:
        # - if smooth_window provided: use it
        # - else: default aggressive 101
        win = int(smooth_window) if smooth_window is not None else 101
        if win % 2 == 0:
            win += 1
        # clamp to valid odd length <= len(y_f)
        if len(y_f) >= 7:
            win = min(win, len(y_f) if len(y_f) % 2 == 1 else len(y_f) - 1)
            win = max(win, 7)  # minimum for poly=3 stability
            y_f_s = savgol_filter(y_f, window_length=win, polyorder=3)
            y_merged[finite] = y_f_s

        merged_out = {"file": f"CALIB_{len(spectra)}", "x": x_common, "y": y_merged}
        spectra_to_plot = [merged_out]

    # ----------------------------
    # Plot (uses spectra_to_plot)
    # ----------------------------
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200)
    for s in reversed(spectra_to_plot):
        ax.plot(s["x"], s["y"], label=os.path.splitext(s["file"])[0])

    ax.set_title(title_text or os.path.splitext(os.path.basename(csv_paths[0]))[0])
    ax.set_xlabel("Wavelength [nm]")
    ax.set_ylabel("Intensity")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    # ----------------------------
    # Notes (put merged data!)
    # ----------------------------
    lines = [
        "% CSV Spectrum Export",
        "% Columns: wavelength_nm, intensity",
        "% Precision: 2 decimals",
        "",
    ]

    if merged_out is not None:
        lines.append(f"% MERGED (union avg) of {len(spectra)} newest files; ignore_start=20; SavGol window={win}, poly=3")
        for fp in csv_paths:
            lines.append(f"%   {os.path.basename(fp)}")
        lines.append("")
        for xv, yv in zip(merged_out["x"], merged_out["y"]):
            if np.isfinite(yv):
                lines.append(f"{xv:.2f}, {yv:.2f}")
        lines.append("")
    else:
        # fallback: list each file raw (as before)
        for fp in csv_paths:
            base = os.path.basename(fp)
            lines.append(f"% File: {base}")
            x, y = load_spectrum_csv(fp)
            for xv, yv in zip(x, y):
                lines.append(f"{xv:.2f}, {yv:.2f}")
            lines.append("")

    notes_text = "\n".join(lines)

    insert_slide_with_image(out_png, title_text or "Spectrum", notes_text)

    return merged_out, spectra, out_png

def run_runcsv_calibrated(
    n: int = 1,
    folder: str | None = None,
    *,
    title_text: str | None = None,
    smooth_window: int | None = None,
    calib_csv: str,
):
    # Special: folder="?" means "pick files via dialog"
    if isinstance(folder, str) and folder.strip() == "?":
        csv_paths = choose_csv_files_dialog(title="Select CSV files to calibrate",initial_dir=CSV_DIR)
        if not csv_paths:
            print("[runcsv cal] no files selected.")
            return None
        # Use the selection folder as output dir
        folder = os.path.dirname(csv_paths[0]) or CSV_DIR
        auto_title = f"Calibrated ({len(csv_paths)} files)"
    else:
        folder = folder or CSV_DIR
        csv_paths = newest_csvs_in_folder(folder, n)
        newest_base = os.path.splitext(os.path.basename(csv_paths[0]))[0]
        auto_title = f"{newest_base} (calibrated)"

    # load calibration
    calib_x, calib_y = load_calibration_csv(calib_csv)

    # load & calibrate spectra
    spectra = []
    for fp in csv_paths:
        x, y = load_spectrum_csv(fp)

        # apply calibration
        y = apply_calibration(x, y, calib_x, calib_y)

        # optional smoothing AFTER calibration
        if smooth_window is not None:
            finite = np.isfinite(y)
            if np.any(finite):
                y2 = y.copy()
                y2[finite] = smooth_aggressive(y2[finite], window=smooth_window, poly=3)
                y = y2

        spectra.append({"file": os.path.basename(fp), "x": x, "y": y})

    out_dir = os.path.dirname(csv_paths[0]) or folder
    out_png = os.path.join(out_dir, "~csv_spectrum_plot.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200)
    for s in reversed(spectra):
        ax.plot(s["x"], s["y"], label=os.path.splitext(s["file"])[0])

    ax.set_title(title_text or auto_title)
    ax.set_xlabel("Wavelength [nm]")
    ax.set_ylabel("Intensity / Calibration")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    # notes text (save the calibrated data)
    lines = [
        "% Calibrated CSV Spectrum Export",
        f"% Calibration file: {os.path.basename(calib_csv)}",
        "% Columns: wavelength_nm, calibrated_intensity",
        "% Precision: 6 decimals",
        "",
    ]
    for s in spectra:
        lines.append(f"% File: {s['file']}")
        for xv, yv in zip(s["x"], s["y"]):
            if np.isfinite(yv):
                lines.append(f"{xv:.6f}, {yv:.6f}")
        lines.append("")
    notes_text = "\n".join(lines)

    insert_slide_with_image(out_png, title_text or auto_title, notes_text)
    return out_png


def load_spectra(csv_paths, smooth_window: int | None = None):
    """
    Returns list of dicts:
      [{"file": <basename>, "x": ndarray, "y": ndarray}, ...]
    If smooth_window is provided -> y is smoothed.
    """
    spectra = []
    for fp in csv_paths:
        x, y = load_spectrum_csv(fp)
        if smooth_window is not None:
            y = smooth_uniform(y, window=smooth_window)
        spectra.append({"file": os.path.basename(fp), "x": x, "y": y})
    return spectra

def build_alt_text_from_spectra(spectra, precision: int = 2):
    """
    MATLAB-friendly text containing ALL numeric data (no trimming).
    """
    fmt = f"{{:.{precision}f}}"
    lines = []
    lines.append("% CSV Spectrum Export (possibly smoothed)")
    lines.append("% Columns: wavelength_nm, intensity")
    lines.append(f"% Precision: {precision} decimals")
    lines.append("")

    for s in spectra:
        lines.append(f"% File: {s['file']}")
        x = s["x"]
        y = s["y"]
        for xv, yv in zip(x, y):
            lines.append(f"{fmt.format(float(xv))}, {fmt.format(float(yv))}")
        lines.append("")

    return "\n".join(lines)

def newest_csvs_in_folder(folder: str, n: int):
    pattern = os.path.join(folder, "*.csv")
    candidates = glob.glob(pattern)
    if not candidates:
        raise FileNotFoundError(f"No CSV files found in: {folder}")

    # sort by mtime descending, take top n
    candidates.sort(key=os.path.getmtime, reverse=True)
    return candidates[:max(1, int(n))]

def load_spectrum_csv(file_path: str):
    data = np.genfromtxt(file_path, delimiter=",")
    if data.ndim != 2 or data.shape[1] < 2:
        raise ValueError(f"CSV does not have at least two columns: {file_path}")

    data = data[data[:, 0].argsort()]  # sort by wavelength
    x_vals = data[:, 0]
    y_vals = data[:, 1]
    return x_vals, y_vals

def save_plot_png(csv_paths, out_dir: str, *, title_override: str | None = None, smooth_window: int | None = None):
    newest = csv_paths[0]
    newest_base = os.path.splitext(os.path.basename(newest))[0]

    out_png = os.path.join(out_dir, "~csv_spectrum_plot.png")

    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=200)

    # load with optional smoothing
    spectra = load_spectra(csv_paths, smooth_window=smooth_window)

    # plot oldest -> newest so newest is on top (same behavior)
    for s in reversed(spectra):
        label = os.path.splitext(s["file"])[0]
        ax.plot(s["x"], s["y"], label=label)

    if title_override:
        ax.set_title(title_override)
    else:
        ax.set_title(newest_base if len(csv_paths) == 1 else f"Last {len(csv_paths)} spectra (newest: {newest_base})")

    ax.set_xlabel("Wavelength [nm]")
    ax.set_ylabel("Intensity")
    ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.5)

    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    return out_png, newest_base, spectra

def build_alt_text(csv_paths):
    """
    Build MATLAB-friendly text containing ALL numeric data (no trimming).
    Precision: 2 decimals.
    """
    lines = []
    lines.append("% CSV Spectrum Export")
    lines.append("% Columns: wavelength_nm, intensity")
    lines.append("% Precision: 2 decimals")
    lines.append("")

    for fp in csv_paths:
        base = os.path.basename(fp)
        lines.append(f"% File: {base}")

        x, y = load_spectrum_csv(fp)
        for xv, yv in zip(x, y):
            lines.append(f"{xv:.2f}, {yv:.2f}")

        lines.append("")  # blank line between files

    return "\n".join(lines)

def insert_slide_with_image(png_path: str, title_text: str, notes_text: str):

    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")

    if ppt.Presentations.Count == 0:
        raise RuntimeError("No PowerPoint presentation open!")

    pres = ppt.ActivePresentation
    slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # ppLayoutBlank

    slide_w = pres.PageSetup.SlideWidth
    slide_h = pres.PageSetup.SlideHeight

    # Title
    title = slide.Shapes.AddTextbox(1, 20, 10, slide_w - 40, 40)
    tr = title.TextFrame.TextRange
    tr.Text = title_text
    tr.Font.Size = 22
    tr.ParagraphFormat.Alignment = 1  # center

    # --- Bigger picture on slide: smaller margins ---
    margin = 25          # was 40
    top = 65             # was 70
    max_w = slide_w - 2 * margin
    max_h = slide_h - top - margin

    pic = slide.Shapes.AddPicture(
        FileName=png_path,
        LinkToFile=False,
        SaveWithDocument=True,
        Left=margin,
        Top=top
    )

    # -------------------------------
    # Speaker Notes: FULL DATA (copy/paste to MATLAB)
    # -------------------------------
    try:
        # Placeholder(2) is typically the body text of the Notes page
        notes_range = slide.NotesPage.Shapes.Placeholders(2).TextFrame.TextRange
        notes_range.Text = notes_text
    except Exception as e:
        print(f"[PPT] Failed to write speaker notes: {e}")

    try:
        pic.AlternativeText = "Spectrum plot (numeric data in Speaker Notes)."
        pic.Title = "I vs Wavelength"
    except Exception:
        pass

    pic.LockAspectRatio = True

    # Scale UP or DOWN to fill as much of the bounding box as possible
    scale = min(max_w / pic.Width, max_h / pic.Height)

    # # Make it a bit bigger (optional), but still safe
    # scale *= 1.05  # 5% boost; change to 1.10 if you want more

    # Don’t exceed the box after boost
    scale = min(scale, max_w / pic.Width*0.9, max_h / pic.Height*0.9)

    pic.Width = pic.Width * scale
    pic.Height = pic.Height * scale

    # Center horizontally
    pic.Left = (slide_w - pic.Width) / 2
    pic.Top = top

def main():
    try:
        # Usage:
        #   python plot_csv_spectrum.py            -> last 1 in CSV_DIR
        #   python plot_csv_spectrum.py 3          -> last 3 in CSV_DIR
        #   python plot_csv_spectrum.py 3 <folder> -> last 3 in folder
        #   python plot_csv_spectrum.py <file.csv> -> plot that file only
        args = sys.argv[1:]

        n = 1
        folder = CSV_DIR
        explicit_file = None

        if len(args) >= 1:
            # if first arg is a csv file
            if os.path.isfile(args[0]) and args[0].lower().endswith(".csv"):
                explicit_file = args[0]
            else:
                # else treat it as N
                try:
                    n = int(args[0])
                except Exception:
                    n = 1

        if len(args) >= 2 and os.path.isdir(args[1]):
            folder = args[1]

        if explicit_file:
            csv_paths = [explicit_file]
        else:
            csv_paths = newest_csvs_in_folder(folder, n)

        print(f"runcsv: using {len(csv_paths)} newest CSV(s):")
        for fp in csv_paths:
            print(f"  - {fp}")

        out_dir = os.path.dirname(csv_paths[0]) or folder
        png_path, newest_base, _ = save_plot_png(csv_paths, out_dir=out_dir)
        print(f"Saved plot PNG: {png_path}")

        # Slide title: newest file base (no folder, no extension)
        notes_text = build_alt_text(csv_paths)
        insert_slide_with_image(png_path, newest_base if len(csv_paths) == 1 else f"{newest_base} (+{len(csv_paths)-1})", notes_text)
        print("Slide added to the open PowerPoint.")
        return 0

    except Exception:
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

import os
import sys
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Configure your scan roots
# =========================
DEFAULT_SCAN_ROOTS = [
    r"Q:\QT-Quantum_Optic_Lab\expData\surveySystemType.FEMTO\scan",
    r"C:\WC\HotSystem\DATA",     # change/remove
    r"C:\WC",                    # change/remove
]

def save_xy_montage_per_slice(out_dir, xs_nm, ys_nm, zs_nm, I3, cmap, skip_first=False):
    X_um = xs_nm * 1e-6
    Y_um = ys_nm * 1e-6
    Z_um = zs_nm * 1e-6

    cx_um = float(np.mean([X_um.min(), X_um.max()]))
    cy_um = float(np.mean([Y_um.min(), Y_um.max()]))

    extent_rel = [
        X_um[0] - cx_um, X_um[-1] - cx_um,
        Y_um[0] - cy_um, Y_um[-1] - cy_um
    ]

    z0 = 1 if skip_first else 0
    Zp = Z_um[z0:]
    I3z = I3[z0:]
    Nz = len(Zp)
    if Nz == 0:
        return

    # ---- FIGURE ----
    fig = plt.figure(figsize=(Nz * 1.6, 4.8))

    # tight geometry
    left = 0.05
    right = 0.995
    bottom = 0.12
    top = 0.88
    usable_w = right - left
    ax_w = usable_w / Nz   # exact width per slice
    ax_h = top - bottom

    for i in range(Nz):
        ax = fig.add_axes([
            left + i * ax_w,
            bottom,
            ax_w * 0.98,   # tiny gap (almost touching)
            ax_h
        ])

        img = I3z[i]
        vmin = np.nanmin(img)
        vmax = np.nanmax(img)
        if not np.isfinite(vmin) or vmin == vmax:
            vmin, vmax = 0.0, 1.0

        ax.imshow(
            img,
            origin="lower",
            extent=extent_rel,
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
            aspect="equal"
        )

        ax.set_title(f"Z = {Zp[i]:.1f} µm", fontsize=8, pad=2)

        if i == 0:
            ax.set_ylabel("Y (µm)", fontsize=8)
            ax.set_xlabel("X (µm)", fontsize=8)
            ax.tick_params(labelsize=7)
        else:
            ax.set_xticks([])
            ax.set_yticks([])

    # ---- SINGLE-LINE TITLE ----
    fig.suptitle(
        f"XY slices (per-slice scaling)   |   "
        f"Center = ({cx_um:.1f}, {cy_um:.1f}) µm",
        fontsize=10,
        y=0.97
    )

    out = os.path.join(out_dir, "XY_all_per_slice_scale.png")
    plt.savefig(out, dpi=200)
    plt.close(fig)

    print(f"Saved XY montage: {out}")

def select_csv_file_dialog():
    """Open a file dialog to select a CSV file."""
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    file_path = filedialog.askopenfilename(
        title="Select CSV file",
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
    )

    root.destroy()
    return file_path

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _open_folder(path: str):
    """Open folder in the OS file explorer (Windows/macOS/Linux)."""
    try:
        path = os.path.abspath(path)
        if os.name == "nt":
            os.startfile(path)  # Windows
        elif sys.platform == "darwin":
            import subprocess
            subprocess.Popen(["open", path])
        else:
            import subprocess
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        print(f"[plot_all_slices] Failed to open folder: {e}")

def _snap(arr, step):
    # step in SAME units as arr (here: nm)
    if step is None or step <= 0:
        return arr
    return np.round(arr / step) * step

def _find_newest_csv_under(root: str) -> str | None:
    newest_path = None
    newest_mtime = -1.0

    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if not fn.lower().endswith(".csv"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                mt = os.path.getmtime(p)
            except Exception:
                continue
            if mt > newest_mtime:
                newest_mtime = mt
                newest_path = p

    return newest_path

def resolve_last_csv(scan_roots: list[str]) -> str | None:
    """Return newest CSV found under the newest-existing scan root."""
    roots = []
    for r in scan_roots:
        if isinstance(r, str) and r and os.path.isdir(r):
            roots.append(r)

    if not roots:
        return None

    # Search each root and pick global newest
    best_path = None
    best_mtime = -1.0
    for r in roots:
        p = _find_newest_csv_under(r)
        if not p:
            continue
        try:
            mt = os.path.getmtime(p)
        except Exception:
            continue
        if mt > best_mtime:
            best_mtime = mt
            best_path = p

    return best_path

def load_opx_csv_to_grid(csv_path: str, skiprows: int = 1):
    """
    Column assumptions (0-based):
      I      -> col 3
      x,y,z  -> cols 4,5,6
    """
    df = pd.read_csv(csv_path, skiprows=skiprows)

    I = df.iloc[:, 3].to_numpy(dtype=float)
    x = df.iloc[:, 4].to_numpy(dtype=float)
    y = df.iloc[:, 5].to_numpy(dtype=float)
    z = df.iloc[:, 6].to_numpy(dtype=float)

    # Snap to remove float noise (nm units)
    SNAP_NM = 1.0
    x = _snap(x, SNAP_NM)
    y = _snap(y, SNAP_NM)
    z = _snap(z, SNAP_NM)

    xs = np.unique(x); xs.sort()
    ys = np.unique(y); ys.sort()
    zs = np.unique(z); zs.sort()

    Nx, Ny, Nz = len(xs), len(ys), len(zs)
    I3 = np.full((Nz, Ny, Nx), np.nan, dtype=float)

    xi = np.searchsorted(xs, x)
    yi = np.searchsorted(ys, y)
    zi = np.searchsorted(zs, z)

    I3[zi, yi, xi] = I
    return xs, ys, zs, I3

def save_xy_slices(out_dir, xs_nm, ys_nm, zs_nm, I3, vmin, vmax, cmap):
    X_um = xs_nm * 1e-6
    Y_um = ys_nm * 1e-6
    Z_um = zs_nm * 1e-6

    cx_um = float(np.mean([X_um.min(), X_um.max()]))
    cy_um = float(np.mean([Y_um.min(), Y_um.max()]))

    extent_rel = [X_um[0] - cx_um, X_um[-1] - cx_um, Y_um[0] - cy_um, Y_um[-1] - cy_um]

    for k, z_um in enumerate(Z_um):
        fig = plt.figure(figsize=(6, 5))
        # [left, bottom, width, height] — centered
        ax = fig.add_axes([0.32, 0.15, 0.36, 0.72])

        im = ax.imshow(
            I3[k],
            origin="lower",
            extent=extent_rel,
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
            aspect="equal",
        )

        ax.set_title(
            f"XY slice\n"
            f"Center = ({cx_um:.1f}, {cy_um:.1f}) µm   |   Z = {z_um:.1f} µm",
            pad=10
        )
        ax.set_xlabel("X (µm) [relative]")
        ax.set_ylabel("Y (µm) [relative]")

        cbar = plt.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cbar.set_label("Intensity (kCounts/s)", fontsize=10)

        plt.tight_layout(rect=[0, 0, 1, 0.92])
        plt.savefig(os.path.join(out_dir, f"XY_z{k:04d}.png"), dpi=200)
        plt.close(fig)

def save_zx_slices(out_dir, xs_nm, ys_nm, zs_nm, I3, vmin, vmax, cmap, skip_first=False):
    X_um = xs_nm * 1e-6
    Y_um = ys_nm * 1e-6
    Z_um = zs_nm * 1e-6

    cx_um = float(np.mean([X_um.min(), X_um.max()]))
    cz_um = float(np.mean([Z_um.min(), Z_um.max()]))

    Ny = len(Y_um)

    # limit number of Y images to 50 (do NOT skip any Y)
    if Ny > 50:
        idxs = np.linspace(0, Ny - 1, 50, dtype=int)
    else:
        idxs = np.arange(0, Ny)

    # skip first Z slice only
    z0 = 1 if skip_first else 0
    if z0 >= len(Z_um):
        return

    Zp = Z_um[z0:]
    I3z = I3[z0:, :, :]

    extent_rel = [X_um[0] - cx_um, X_um[-1] - cx_um,
                  Zp[0] - cz_um, Zp[-1] - cz_um]

    for j in idxs:
        y_um = Y_um[j]

        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(
            I3z[:, j, :],
            origin="lower",
            extent=extent_rel,
            vmin=vmin,
            vmax=vmax,
            cmap=cmap,
            aspect="auto",
        )

        ax.set_title(
            f"ZX slice\n"
            f"Center = ({cx_um:.1f}, {cz_um:.1f}) µm   |   Y = {y_um:.1f} µm",
            pad=10
        )
        ax.set_xlabel("X (µm) [relative]")
        ax.set_ylabel("Z (µm) [relative]")

        plt.colorbar(im, ax=ax, label="I")
        plt.tight_layout(rect=[0, 0, 1, 0.92])
        plt.savefig(os.path.join(out_dir, f"ZX_y{j:04d}.png"), dpi=200)
        plt.close(fig)

def main():
    ap = argparse.ArgumentParser(
        description="Export XY and ZX slices from OPX CSV into a folder named after the CSV."
    )
    ap.add_argument("csv", nargs="?", help="CSV file path, or 'last'. If omitted, a file dialog will open.")
    ap.add_argument("--skiprows", type=int, default=1, help="Rows to skip at top of CSV (default: 1)")
    ap.add_argument("--vmin", type=float, default=None, help="Fixed min for color scale (optional)")
    ap.add_argument("--vmax", type=float, default=None, help="Fixed max for color scale (optional)")
    ap.add_argument("--cmap", type=str, default="jet", help='Colormap (default: "jet"). e.g. "rainbow"')
    ap.add_argument("--skip-first", action="store_true", help="Skip the first Z slice")

    args = ap.parse_args()

    # Support shorthand: script -1  (dialog + skip)
    if args.csv == "-1":
        args.csv = None
        args.skip_first = True

    csv_path = args.csv

    # Support: script last
    if isinstance(csv_path, str) and csv_path.lower() == "last":
        resolved = resolve_last_csv(DEFAULT_SCAN_ROOTS)
        if not resolved:
            print("plot_all_slices: could not resolve 'last' (no scan roots / no CSV found).")
            print("Edit DEFAULT_SCAN_ROOTS at top of plot_all_slices.py")
            return
        csv_path = resolved
        print(f"plot_all_slices last -> {csv_path}")

    # Dialog if still not set
    if not csv_path:
        csv_path = select_csv_file_dialog()
        if not csv_path:
            print("No file selected. Exiting.")
            return

    csv_path = os.path.abspath(csv_path)
    if not os.path.isfile(csv_path):
        raise FileNotFoundError(csv_path)

    out_dir = os.path.join(os.path.dirname(csv_path), os.path.splitext(os.path.basename(csv_path))[0])
    _ensure_dir(out_dir)
    _open_folder(out_dir)

    xs, ys, zs, I3 = load_opx_csv_to_grid(csv_path, skiprows=args.skiprows)

    vmin = args.vmin if args.vmin is not None else np.nanmin(I3)
    vmax = args.vmax if args.vmax is not None else np.nanmax(I3)

    Nx = len(xs)
    Ny = len(ys)
    Nz = len(zs)

    # XY only if both X and Y have >1 points
    if Nx <= 1 or Ny <= 1:
        print(f"XY skipped: Nx={Nx}, Ny={Ny} (need both >1).")
    else:
        save_xy_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap=args.cmap)
        save_xy_montage_per_slice(out_dir, xs, ys, zs, I3, cmap=args.cmap, skip_first=args.skip_first)

    # ZX only if Z has >1 slices
    if Nz <= 1:
        print("ZX skipped: only one Z slice (Nz<=1).")
    else:
        save_zx_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap=args.cmap, skip_first=args.skip_first)

    print(f"Saved all slices to: {out_dir}")
    print(
        f"  XY: {0 if (Nx <= 1 or Ny <= 1) else len(zs)} images, "
        f"ZX: {0 if Nz <= 1 else min(len(ys), 50)} images"
    )


if __name__ == "__main__":
    main()

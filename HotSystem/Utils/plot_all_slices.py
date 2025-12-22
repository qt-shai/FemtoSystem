import os
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


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


def _safe_name(v: float) -> str:
    return f"{v:.6g}".replace(".", "p").replace("-", "m")


def load_opx_csv_to_grid(csv_path: str, skiprows: int = 1):
    """
    Loads an OPX-like CSV and packs intensity onto a regular 3D grid.

    Column assumptions (0-based):
      I   -> col 3
      x,y,z -> cols 4,5,6

    Coordinate units:
      assumed to be in nm (so later we convert nm -> µm via *1e-3)
    """
    df = pd.read_csv(csv_path, skiprows=skiprows)

    I = df.iloc[:, 3].to_numpy(dtype=float)
    x = df.iloc[:, 4].to_numpy(dtype=float)
    y = df.iloc[:, 5].to_numpy(dtype=float)
    z = df.iloc[:, 6].to_numpy(dtype=float)

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


def save_xy_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap):
    # nm -> µm
    X_um, Y_um, Z_um = xs * 1e-3, ys * 1e-3, zs * 1e-3
    extent = [X_um[0], X_um[-1], Y_um[0], Y_um[-1]]

    for k, z in enumerate(Z_um):
        plt.figure(figsize=(6, 5))
        plt.imshow(I3[k], origin="lower", extent=extent, vmin=vmin, vmax=vmax, cmap=cmap)
        plt.title(f"XY @ Z={z:.3f} nm")
        plt.xlabel("X (nm)")
        plt.ylabel("Y (nm)")
        plt.colorbar(label="I")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"XY_z{k:04d}_Z{_safe_name(z)}um.png"), dpi=200)
        plt.close()


def save_zx_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap):
    # nm -> µm
    X_um, Y_um, Z_um = xs * 1e-3, ys * 1e-3, zs * 1e-3
    extent = [X_um[0], X_um[-1], Z_um[0], Z_um[-1]]

    for j, y in enumerate(Y_um):
        plt.figure(figsize=(6, 5))
        plt.imshow(I3[:, j, :], origin="lower", extent=extent, vmin=vmin, vmax=vmax, cmap=cmap, aspect="auto")
        plt.title(f"ZX @ Y={y:.3f} nm")
        plt.xlabel("X (nm)")
        plt.ylabel("Z (nm)")
        plt.colorbar(label="I")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"ZX_y{j:04d}_Y{_safe_name(y)}um.png"), dpi=200)
        plt.close()


def save_zy_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap):
    # nm -> µm
    X_um, Y_um, Z_um = xs * 1e-3, ys * 1e-3, zs * 1e-3
    extent = [Y_um[0], Y_um[-1], Z_um[0], Z_um[-1]]

    for i, x in enumerate(X_um):
        plt.figure(figsize=(6, 5))
        plt.imshow(I3[:, :, i], origin="lower", extent=extent, vmin=vmin, vmax=vmax, cmap=cmap, aspect="auto")
        plt.title(f"ZY @ X={x:.3f} nm")
        plt.xlabel("Y (nm)")
        plt.ylabel("Z (nm)")
        plt.colorbar(label="I")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, f"ZY_x{i:04d}_X{_safe_name(x)}um.png"), dpi=200)
        plt.close()


def main():
    ap = argparse.ArgumentParser(
        description="Export all XY / ZX / ZY slices from OPX CSV into a folder named after the CSV."
    )
    ap.add_argument("csv", nargs="?", help="CSV file path. If omitted, a file dialog will open.")
    ap.add_argument("--skiprows", type=int, default=1, help="Rows to skip at top of CSV (default: 1)")
    ap.add_argument("--vmin", type=float, default=None, help="Fixed min for color scale (optional)")
    ap.add_argument("--vmax", type=float, default=None, help="Fixed max for color scale (optional)")
    ap.add_argument("--cmap", type=str, default="jet", help='Colormap (default: "jet"). e.g. "rainbow"')
    args = ap.parse_args()

    csv_path = args.csv
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

    xs, ys, zs, I3 = load_opx_csv_to_grid(csv_path, skiprows=args.skiprows)

    vmin = args.vmin if args.vmin is not None else np.nanmin(I3)
    vmax = args.vmax if args.vmax is not None else np.nanmax(I3)

    save_xy_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap=args.cmap)
    save_zx_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap=args.cmap)
    save_zy_slices(out_dir, xs, ys, zs, I3, vmin, vmax, cmap=args.cmap)

    print(f"Saved all slices to: {out_dir}")
    print(f"  XY: {len(zs)} images, ZX: {len(ys)} images, ZY: {len(xs)} images")


if __name__ == "__main__":
    main()

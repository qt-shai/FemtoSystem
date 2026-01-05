#!/usr/bin/env python3
"""
scanxyz.py

Creates a PowerPoint slide with a ZX scan and an XY scan side-by-side.

Intended to be launched from CommandDispatcher via subprocess.

Example:
  python scanxyz.py --zx path/to/zx.csv --xy path/to/xy.csv --title "B6 QT17 dil5"

Notes:
- Tries to attach to the currently-running PowerPoint and use ActivePresentation.
- If PowerPoint is not running, it will create a new instance and a new presentation.
- CSV parsing is "best-effort": it tries to auto-detect columns for X/Y/Z and a value column.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


@dataclass
class Scan2D:
    x: np.ndarray  # axis-1 grid values (um)
    y: np.ndarray  # axis-2 grid values (um)
    z: np.ndarray  # 2D values, shape (len(y), len(x))


def _read_csv_guess(path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    meta: Dict[str, Any] = {}
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        first = f.readline().strip()

    has_alpha = any(c.isalpha() for c in first)
    if has_alpha and ("," in first or "\t" in first or ";" in first):
        delim = "," if "," in first else ("\t" if "\t" in first else ";")
        cols = [c.strip() for c in first.split(delim)]
        meta["colnames"] = cols
        data = np.genfromtxt(path, delimiter=delim, skip_header=1)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data.astype(float, copy=False), meta

    try:
        data = np.genfromtxt(path, delimiter=",")
        if data.ndim == 1:
            data = data.reshape(1, -1)
        if data.shape[1] <= 1:
            raise ValueError("looks like 1-col csv; retry whitespace")
        return data.astype(float, copy=False), meta
    except Exception:
        data = np.genfromtxt(path)
        if data.ndim == 1:
            data = data.reshape(1, -1)
        return data.astype(float, copy=False), meta


def _pick_columns(meta: Dict[str, Any], data: np.ndarray) -> Tuple[int, int, int, int]:
    colnames: Optional[List[str]] = meta.get("colnames")
    ncol = data.shape[1]

    if colnames and len(colnames) == ncol:
        lower = [c.strip().lower() for c in colnames]

        def find_any(keys):
            for k in keys:
                for i, name in enumerate(lower):
                    if k in name:
                        return i
            return None

        ix = find_any(["x_um", "x (um", "x[", "x ", "x"])
        iy = find_any(["y_um", "y (um", "y[", "y ", "y"])
        iz = find_any(["z_um", "z (um", "z[", "z ", "z"])
        iv = find_any(["counts", "count", "intensity", "value", "rate"])

        if ix is None: ix = 0
        if iy is None: iy = 1 if ncol > 1 else 0
        if iz is None: iz = 2 if ncol > 2 else (iy if ncol > 1 else 0)
        if iv is None: iv = ncol - 1
        return int(ix), int(iy), int(iz), int(iv)

    if ncol >= 4:
        return 0, 1, 2, ncol - 1
    if ncol == 3:
        return 0, 1, 1, 2
    raise ValueError(f"CSV has too few columns: {ncol}")


def _to_grid(x: np.ndarray, y: np.ndarray, v: np.ndarray) -> Scan2D:
    xu = np.unique(np.round(x.astype(float), 9))
    yu = np.unique(np.round(y.astype(float), 9))

    xi = {val: i for i, val in enumerate(xu)}
    yi = {val: i for i, val in enumerate(yu)}

    grid = np.full((len(yu), len(xu)), np.nan, dtype=float)
    for xx, yy, vv in zip(x, y, v):
        grid[yi[np.round(float(yy), 9)], xi[np.round(float(xx), 9)]] = float(vv)

    return Scan2D(x=xu, y=yu, z=grid)


def _load_scan_2d(path: str, plane_hint: str) -> Scan2D:
    data, meta = _read_csv_guess(path)
    ix, iy, iz, iv = _pick_columns(meta, data)

    X = data[:, ix]
    Y = data[:, iy]
    Z = data[:, iz]
    V = data[:, iv]

    if plane_hint.lower() == "zx":
        return _to_grid(X, Z, V)
    if plane_hint.lower() == "xy":
        return _to_grid(X, Y, V)

    return _to_grid(X, Y, V)


def _save_heatmap(scan: Scan2D, xlabel: str, ylabel: str, title: str, out_path: str) -> None:
    fig = plt.figure(figsize=(6, 5), dpi=200)
    ax = fig.add_subplot(111)

    extent = [float(scan.x[0]), float(scan.x[-1]), float(scan.y[0]), float(scan.y[-1])]
    im = ax.imshow(scan.z, origin="lower", aspect="auto", extent=extent)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.colorbar(im, ax=ax, label="Intensity")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _ppt_add_slide(title: str, img_left: str, img_right: str) -> None:
    try:
        import win32com.client  # type: ignore
    except Exception as e:
        raise RuntimeError("win32com is required to add to an *active* PowerPoint. Install pywin32.") from e

    ppt = win32com.client.Dispatch("PowerPoint.Application")
    ppt.Visible = True

    pres = None
    try:
        pres = ppt.ActivePresentation
    except Exception:
        pres = None

    if pres is None:
        pres = ppt.Presentations.Add()

    slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # 12 = blank
    w = pres.PageSetup.SlideWidth
    h = pres.PageSetup.SlideHeight

    margin = 24
    title_h = 48

    tb = slide.Shapes.AddTextbox(1, margin, 8, w - 2 * margin, title_h)
    tb.TextFrame.TextRange.Text = title
    tb.TextFrame.TextRange.Font.Size = 40
    tb.TextFrame.TextRange.ParagraphFormat.Alignment = 2  # center

    img_top = title_h + 20
    img_h = h - img_top - margin
    img_w = (w - 3 * margin) / 2

    slide.Shapes.AddPicture(FileName=os.path.abspath(img_left),
                            LinkToFile=False, SaveWithDocument=True,
                            Left=margin, Top=img_top, Width=img_w, Height=img_h)
    slide.Shapes.AddPicture(FileName=os.path.abspath(img_right),
                            LinkToFile=False, SaveWithDocument=True,
                            Left=2 * margin + img_w, Top=img_top, Width=img_w, Height=img_h)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--zx", required=True, help="Path to ZX scan CSV")
    ap.add_argument("--xy", required=True, help="Path to XY scan CSV")
    ap.add_argument("--title", default="", help="Slide title (e.g. from dispatcher self._spc_note)")
    ap.add_argument("--keep_pngs", action="store_true", help="Do not delete temporary PNGs")
    args = ap.parse_args()

    if not os.path.isfile(args.zx):
        print(f"[scanxyz] ZX csv not found: {args.zx}")
        return 2
    if not os.path.isfile(args.xy):
        print(f"[scanxyz] XY csv not found: {args.xy}")
        return 2

    title = args.title.strip() or "scanxyz"

    try:
        zx = _load_scan_2d(args.zx, "zx")
        xy = _load_scan_2d(args.xy, "xy")
    except Exception as e:
        print(f"[scanxyz] Failed to parse CSVs: {e}")
        return 3

    tmpdir = tempfile.mkdtemp(prefix="scanxyz_")
    zx_png = os.path.join(tmpdir, "zx.png")
    xy_png = os.path.join(tmpdir, "xy.png")

    try:
        _save_heatmap(zx, xlabel="X (µm)", ylabel="Z (µm)", title="ZX slice", out_path=zx_png)
        _save_heatmap(xy, xlabel="X (µm)", ylabel="Y (µm)", title="XY slice", out_path=xy_png)
        _ppt_add_slide(title=title, img_left=zx_png, img_right=xy_png)
        print(f"[scanxyz] Added slide '{title}' to active PowerPoint.")
    except Exception as e:
        print(f"[scanxyz] Failed: {e}")
        return 4
    finally:
        if not args.keep_pngs:
            try:
                for p in (zx_png, xy_png):
                    if os.path.isfile(p):
                        os.remove(p)
                os.rmdir(tmpdir)
            except Exception:
                pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

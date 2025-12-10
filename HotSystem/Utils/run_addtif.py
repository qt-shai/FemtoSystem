# run_addtif.py
import sys
import traceback
import os
import glob
import json

import pythoncom
import win32com.client

import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
import matplotlib.image as mpimg



# --------------------------------------------------------------------
#  CONFIG PATHS
# --------------------------------------------------------------------
TIF_DIR = r"C:\Users\Femto\Work Folders\Documents\LightField"
MAP_IMAGE = r"C:\WC\HotSystem\map.jpg"
MAP_JSON  = r"C:\WC\HotSystem\map_points.json"


# ================================================================
#   MAP CALIBRATION
# ================================================================
def load_map_calibration():
    with open(MAP_JSON, "r") as f:
        d = json.load(f)

    px1, py1 = d["pixel_points"][0]
    px2, py2 = d["pixel_points"][1]

    X1, Y1 = d["real_points"][0]
    X2, Y2 = d["real_points"][1]

    scale_x = (px2 - px1) / (X2 - X1)
    scale_y = (py2 - py1) / (Y2 - Y1)

    return px1, py1, X1, Y1, scale_x, scale_y


def real_to_pixel(real_x, real_y):
    with open(MAP_JSON, "r") as f:
        d = json.load(f)

    # pixel coordinates
    px1, py1 = d["pixel_points"][0]
    px2, py2 = d["pixel_points"][1]

    # real coordinates
    X1, Y1 = d["real_points"][0]
    X2, Y2 = d["real_points"][1]

    # vector in pixel space
    v_pix = np.array([px2 - px1, py2 - py1])
    v_pix_unit = v_pix / np.linalg.norm(v_pix)

    # perpendicular vector (90 degrees)
    v_perp = np.array([-v_pix_unit[1], v_pix_unit[0]])

    # distance conversion (pixel per µm)
    dist_pix  = np.linalg.norm(v_pix)
    dist_real = np.sqrt((X2-X1)**2 + (Y2-Y1)**2)
    px_per_um = dist_pix / dist_real

    # vector in real space
    dx = real_x - X1
    dy = real_y - Y1

    # projection onto pixel axes
    px = px1 + (dx * v_pix_unit[0] + dy * v_perp[0]) * px_per_um
    py = py1 + (dx * v_pix_unit[1] + dy * v_perp[1]) * px_per_um

    return int(px), int(py)



# ================================================================
#   DRAW CROSS ON MAP
# ================================================================
def create_map_with_cross(map_path, map_json, real_x, real_y, stage_x, stage_y, output_png):
    """
    Creates a PNG showing:
        - The map
        - A cross at the pixel corresponding to (real_x, real_y)
        - Stage position text
    """

    # Load calibration JSON
    with open(map_json, "r") as f:
        data = json.load(f)

    px1, py1 = data["pixel_points"][0]
    px2, py2 = data["pixel_points"][1]
    X1,  Y1   = data["real_points"][0]
    X2,  Y2   = data["real_points"][1]

    # --- Compute pixel location from real coordinates ---
    # Linear mapping separately for X and Y
    px = px1 + (real_x - X1) * (px2 - px1) / (X2 - X1)
    py = py1 + (real_y - Y1) * (py2 - py1) / (Y2 - Y1)

    # --- Load map ---
    img = mpimg.imread(map_path)

    # --- Draw map with cross ---
    fig, ax = plt.subplots(figsize=(6, 6), dpi=150)
    ax.imshow(img)
    ax.set_xticks([])
    ax.set_yticks([])

    # Cross size in pixels
    cross = 40
    ax.plot([px - cross, px + cross], [py, py], "r-", linewidth=2)
    ax.plot([px, px], [py - cross, py + cross], "r-", linewidth=2)

    # Stage position info
    ax.text(
        10, 20,
        f"Stage: X={stage_x:.1f} µm   Y={stage_y:.1f} µm",
        color="yellow",
        fontsize=12,
        bbox=dict(facecolor="black", alpha=0.4)
    )

    plt.tight_layout()
    fig.savefig(output_png, bbox_inches="tight")
    plt.close(fig)

    print(f"[MAP] Cross rendered at pixel ({px:.1f}, {py:.1f})")
    return output_png



# ================================================================
#   CREATE PNG FROM NEWEST TIF
# ================================================================
def create_tif_png():
    tifs = []
    for pat in ["*.tif", "*.tiff"]:
        tifs += glob.glob(os.path.join(TIF_DIR, pat))

    if not tifs:
        print("No TIF files found.")
        return None

    tif_fp = max(tifs, key=os.path.getmtime)
    print("Using newest TIF:", tif_fp)

    arr = np.array(Image.open(tif_fp))

    vmin, vmax = float(arr.min()), float(arr.max())
    out_png = os.path.join(TIF_DIR, "~tif_with_colorbar.png")

    fig, ax = plt.subplots(figsize=(6, 6), dpi=200)
    im = ax.imshow(arr, cmap="gray")
    im.set_clim(vmin, vmax)
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label("Intensity")
    ax.set_xticks([]); ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(out_png, bbox_inches="tight")
    plt.close(fig)

    return tif_fp, out_png


# ================================================================
#   INSERT INTO POWERPOINT
# ================================================================
def insert_slide(tif_png, tif_fp, map_png=None):
    pythoncom.CoInitialize()
    ppt = win32com.client.Dispatch("PowerPoint.Application")

    if ppt.Presentations.Count == 0:
        raise RuntimeError("No PowerPoint presentation open!")

    pres = ppt.ActivePresentation
    slide = pres.Slides.Add(pres.Slides.Count + 1, 12)  # blank layout

    slide_width = pres.PageSetup.SlideWidth

    # Title
    title = slide.Shapes.AddTextbox(1, 20, 10, slide_width - 40, 40)
    title.TextFrame.TextRange.Text = os.path.basename(tif_fp)
    title.TextFrame.TextRange.Font.Size = 22
    title.TextFrame.TextRange.ParagraphFormat.Alignment = 1

    # TIF image
    tif_shape = slide.Shapes.AddPicture(
        FileName=tif_png,
        LinkToFile=False,
        SaveWithDocument=True,
        Left=60,
        Top=70
    )

    map_shape = slide.Shapes.AddPicture(
        FileName=map_png,
        LinkToFile=False,
        SaveWithDocument=True,

        # RIGHT side placement
        Left=tif_shape.Left + tif_shape.Width + 40,  # put to the right
        Top=tif_shape.Top  # align top
    )


# ================================================================
#   MAIN ENTRY
#   addtif       → run without stage XY → only TIF
#   addtif map   → run with XY → TIF + map_with_cross
# ================================================================
def main():
    try:
        args = sys.argv[1:]

        # -------------------------------------
        # Case 1: ADDTIF → do NOT add map
        # -------------------------------------
        if len(args) == 0:
            tif_fp, tif_png = create_tif_png()
            insert_slide(tif_png, tif_fp)
            print("addtif: TIF slide added.")
            return 0

        # -------------------------------------
        # Case 2: ADDTIF MAP → add map + cross
        # Called as: run_addtif.py map X Y
        # -------------------------------------
        if args[0].lower() == "map" and len(args) == 3:
            stage_x = float(args[1])
            stage_y = float(args[2])

            tif_fp, tif_png = create_tif_png()

            # Convert real stage XY to map pixel XY inside create_map_with_cross
            map_png = os.path.join(TIF_DIR, "~map_cross.png")

            create_map_with_cross(
                map_path=MAP_IMAGE,
                map_json=MAP_JSON,
                real_x=stage_x,
                real_y=stage_y,
                stage_x=stage_x,
                stage_y=stage_y,
                output_png=map_png
            )

            insert_slide(tif_png, tif_fp, map_png)
            print(f"addtif map: slide added with real coords ({stage_x},{stage_y})")
            return 0

        print("Invalid usage.")
        print(" addtif → python run_addtif.py")
        print(" addtif map → python run_addtif.py map X Y")
        return 1

    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

import os
import json
import re

import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.widgets import Button

IMAGE_PATH   = r"C:\WC\HotSystem\map.jpg"
JSON_PATH    = r"C:\WC\HotSystem\map_points.json"
CALIB_DIR    = r"C:\WC\calibration files"
COUPON_IMAGE = r"C:\WC\HotSystem\coupon_map.jpg"


# ------------------------------------------------------------
#  Parse coordinates from filenames like:
#  Site (-10789,10 1237,80 -835,10) B6 ....tif
# ------------------------------------------------------------
def extract_xyz_from_name(name):
    """
    Parse coordinates inside parentheses.
    Returns (X, Y, Z) or None.
    Accepts formats like:
    (1234,56 -789,01 222,33)
    """
    m = re.search(r"\(\s*([-\d,\.]+)\s+([-\d,\.]+)\s+([-\d,\.]+)\s*\)", name)
    if not m:
        return None

    def parse_num(s):
        s = s.replace(",", ".")   # convert comma-decimals to dot
        return float(s)

    try:
        x = parse_num(m.group(1))
        y = parse_num(m.group(2))
        z = parse_num(m.group(3))
        return (x, y, z)
    except Exception:
        return None


def load_two_calibration_files():
    """Load the first 2 calibration .tif files with parsed coordinates."""
    if not os.path.isdir(CALIB_DIR):
        print(f"Calibration directory missing: {CALIB_DIR}")
        return [], []

    files = []
    for f in os.listdir(CALIB_DIR):
        if f.lower().endswith(".tif") and "site" in f.lower():
            coords = extract_xyz_from_name(f)
            if coords:
                files.append({"file": f, "coords": coords})

    if len(files) < 2:
        print("Not enough calibration files found.")
        return [], []

    # Sort by Y coordinate so order is stable (e.g. R1 vs B6)
    files.sort(key=lambda x: x["coords"][1])

    # Take the first two
    f1, f2 = files[0], files[1]

    print("Using calibration files:")
    print(" 1:", f1["file"], "→", f1["coords"])
    print(" 2:", f2["file"], "→", f2["coords"])

    return [f1["file"], f2["file"]], [f1["coords"], f2["coords"]]


# ------------------------------------------------------------
#                MAIN CALIBRATION GUI
# ------------------------------------------------------------
def edit_points_on_image(image_path, json_path):
    # Load calibration files
    calib_files, real_coords = load_two_calibration_files()
    # real_coords = [(X1, Y1, Z1), (X2, Y2, Z2)]
    real_points = [(c[0], c[1]) for c in real_coords] if real_coords else []

    # GUI figure
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_axes([0.22, 0.05, 0.76, 0.9])
    img = mpimg.imread(image_path)
    ax.imshow(img)
    ax.set_title("Calibration: point1 (X1,Y1), point2 (X2,Y2), point3 = coupon ref.")

    points = []             # pixel coordinates (on main map)
    active_index = None     # index of selected point
    is_select_mode = False
    point_artists = []
    step = 5                # normal step
    select_radius = 20

    coupon_calib = {}       # {"main_ref":[x,y], "coupon_ref":[x,y], ...}

    # Labels for what each point is
    if len(calib_files) == 2:
        fig.text(0.02, 0.90, f"Point 1 → {calib_files[0]}", fontsize=9)
        fig.text(0.02, 0.87, f"Point 2 → {calib_files[1]}", fontsize=9)
    else:
        fig.text(0.02, 0.90, "Calibration files not found!", fontsize=9, color="red")
    fig.text(0.02, 0.84, "Point 3 → coupon main ref", fontsize=9)

    # -----------------------------
    #  Redraw all points + square
    # -----------------------------
    def update_plot():
        for a in point_artists:
            a.remove()
        point_artists.clear()

        # Draw points as crosses (selected = yellow, others = red)
        for i, (x, y) in enumerate(points):
            size = 8  # half-length of cross arms
            if i == active_index:
                color = "yellow"
                lw = 2.5
            else:
                color = "red"
                lw = 2

            # horizontal bar
            h, = ax.plot([x - size, x + size], [y, y], color=color, linewidth=lw)
            # vertical bar
            v, = ax.plot([x, x], [y - size, y + size], color=color, linewidth=lw)
            point_artists.extend([h, v])

        # Square around point #1
        if len(points) >= 1:
            x, y = points[0]
            side = 40
            half = side / 2
            xs = [x - half, x + half, x + half, x - half, x - half]
            ys = [y - half, y - half, y + half, y + half, y - half]
            square, = ax.plot(xs, ys, "cyan", linewidth=2)
            point_artists.append(square)

        fig.canvas.draw_idle()

    # Load saved pixel points & coupon calibration if exist
    if os.path.exists(json_path):
        try:
            with open(json_path) as f:
                data = json.load(f)

            saved = data.get("pixel_points") or data.get("points", [])
            for p in saved:
                if len(p) == 2:
                    points.append((float(p[0]), float(p[1])))

            if "coupon_calibration" in data:
                coupon_calib.update(data["coupon_calibration"])
                print("Loaded existing coupon calibration:", coupon_calib)

            if points:
                active_index = 0
                print("Loaded pixel points:", points)
                update_plot()
        except Exception as e:
            print("Could not parse existing JSON:", e)

    # -----------------------------
    def onclick(event):
        nonlocal points, active_index, is_select_mode
        if event.inaxes != ax:
            return
        if event.xdata is None:
            return

        x = round(event.xdata, 2)
        y = round(event.ydata, 2)

        if is_select_mode and points:
            # select nearest existing point
            best_idx = None
            best_d2 = None
            for i, (px, py) in enumerate(points):
                d2 = (px - x)**2 + (py - y)**2
                if best_d2 is None or d2 < best_d2:
                    best_d2 = d2
                    best_idx = i
            if best_d2 is not None and best_d2 <= select_radius**2:
                active_index = best_idx
                print("Selected point", best_idx, points[best_idx])
                update_plot()
                return

        # adding mode
        if len(points) >= 3:
            print("Already have 3 points (2 calib + 1 coupon ref).")
            return

        points.append((x, y))
        active_index = len(points) - 1
        print(f"Added pixel point #{active_index}: {x, y}")
        update_plot()
    # -----------------------------

    def on_done(event):
        # Just close the main figure; execution continues after plt.show()
        print("Done pressed.")
        plt.close(fig)

    def on_select(event):
        nonlocal is_select_mode
        is_select_mode = not is_select_mode
        select_button.label.set_text("Select: ON" if is_select_mode else "Select: OFF")
        fig.canvas.draw_idle()

    def move(dx, dy):
        nonlocal points, active_index
        # Auto-select point 0 if nothing selected
        if active_index is None and len(points) > 0:
            active_index = 0

        if active_index is None or active_index >= len(points):
            print("No point selected.")
            return

        x, y = points[active_index]
        points[active_index] = (round(x + dx, 2), round(y + dy, 2))
        update_plot()
        fig.canvas.draw_idle()

    # keyboard support: Shift fine, normal, Ctrl fast
    def on_key(event):
        fine = 1
        normal = step
        fast = step * 5

        key = event.key.lower()
        if "ctrl" in key:
            s = fast
        elif "shift" in key:
            s = fine
        else:
            s = normal

        if "up" in key:
            move(0, -s)
        elif "down" in key:
            move(0, s)
        elif "left" in key:
            move(-s, 0)
        elif "right" in key:
            move(s, 0)
        elif key in ("enter", "return"):
            print("Enter pressed, closing.")
            plt.close(fig)
        elif key in ("s", "+"):
            on_select(None)

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("button_press_event", onclick)

    # -------------------------------------------------
    #  COUPON CALIBRATION: point 3 on main map is ref
    # -------------------------------------------------
    def on_coupon(event):
        nonlocal coupon_calib

        if len(points) < 3:
            print("Need 3 points on main map (2 calibration + 1 coupon ref).")
            return

        # Main ref is the 3rd point (index 2)
        main_idx = 2
        mx, my = points[main_idx]
        print(f"Coupon calibration: using main ref point #3 at ({mx}, {my})")

        if not os.path.exists(COUPON_IMAGE):
            print(f"Coupon image not found: {COUPON_IMAGE}")
            return

        # Open coupon window
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        img2 = mpimg.imread(COUPON_IMAGE)
        ax2.imshow(img2)
        ax2.set_title("Coupon map: click reference point (same physical location)")
        ax2.set_xticks([])
        ax2.set_yticks([])

        coupon_points = []

        def onclick_coupon(ev):
            if ev.inaxes != ax2 or ev.xdata is None:
                return
            cx = round(ev.xdata, 2)
            cy = round(ev.ydata, 2)
            coupon_points.append((cx, cy))
            ax2.plot(cx, cy, "rx")
            fig2.canvas.draw_idle()
            print(f"Coupon ref clicked at ({cx}, {cy})")
            # close after first click
            plt.close(fig2)

        fig2.canvas.mpl_connect("button_press_event", onclick_coupon)
        plt.show()   # blocks until coupon fig is closed

        if not coupon_points:
            print("No coupon reference chosen.")
            return

        cx, cy = coupon_points[0]

        coupon_calib = {
            "main_ref":   [mx, my],
            "coupon_ref": [cx, cy],
            "coupon_image": COUPON_IMAGE,
            "main_index": main_idx
        }

        print("Coupon calibration stored:", coupon_calib)

    # ------------- Buttons on the left -----------------
    ax_done = fig.add_axes([0.02, 0.80, 0.16, 0.08])
    ax_sel  = fig.add_axes([0.02, 0.68, 0.16, 0.08])
    done_button   = Button(ax_done, "Done")
    select_button = Button(ax_sel,  "Select: OFF")

    done_button.on_clicked(on_done)
    select_button.on_clicked(on_select)

    # arrow buttons
    ax_up    = fig.add_axes([0.07, 0.54, 0.06, 0.06])
    ax_left  = fig.add_axes([0.02, 0.46, 0.06, 0.06])
    ax_down  = fig.add_axes([0.07, 0.38, 0.06, 0.06])
    ax_right = fig.add_axes([0.12, 0.46, 0.06, 0.06])

    up_button    = Button(ax_up,    "↑")
    left_button  = Button(ax_left,  "←")
    down_button  = Button(ax_down,  "↓")
    right_button = Button(ax_right, "→")

    up_button.on_clicked(lambda e: move(0, -step))
    left_button.on_clicked(lambda e: move(-step, 0))
    down_button.on_clicked(lambda e: move(0, step))
    right_button.on_clicked(lambda e: move(step, 0))

    # Coupon map button
    ax_coupon = fig.add_axes([0.02, 0.26, 0.16, 0.08])
    coupon_button = Button(ax_coupon, "Coupon map")
    coupon_button.on_clicked(on_coupon)

    fig.canvas.draw()

    print("Calibration tool ready...")
    # This blocks until the main window is closed (Done button or X or Enter)
    plt.show()

    # After window closes, save calibration output
    result = {
        "pixel_points": points,        # [P1, P2, P3]
        "real_points": real_points,    # [(X1,Y1), (X2,Y2)]
        "files": calib_files,
        "coupon_calibration": coupon_calib
    }

    try:
        with open(json_path, "w") as f:
            json.dump(result, f, indent=2)
        print("Saved calibration to", json_path)
        print(result)
    except Exception as e:
        print("Error saving calibration:", e)

    return result


# Run standalone
if __name__ == "__main__":
    edit_points_on_image(IMAGE_PATH, JSON_PATH)

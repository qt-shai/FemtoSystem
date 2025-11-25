# from ECM import *
import win32clipboard

from ImGuiwrappedMethods import *
from Common import *
from HW_wrapper import HW_devices as hw_devices
from HW_wrapper.Wrapper_MFF_101 import FilterFlipperController
import os
import cv2
import numpy as np

import time, cv2, numpy as np

def phase_to_u8(phase_rad):
    ph = np.mod(phase_rad, 2 * np.pi)
    return np.uint8(np.round(ph * (255.0 / (2 * np.pi))))

def u8_to_phase(u8):
    return (u8.astype(np.float32) / 255.0) * 2 * np.pi

def detect_dc_center(g, guess=None, win_frac=0.30):
    """
    Return (dcx, dcy) in image coords.
    Assumes DC is a BRIGHT spot.
    Searches around 'guess' (defaults to image center),
    then refines with a 5×5 weighted centroid (sub-pixel).
    """
    import numpy as np, cv2

    H, W = g.shape[:2]
    if guess is None:
        guess = (W * 0.5, H * 0.5)
    cxg, cyg = map(float, guess)

    # --- search window around guess (clamped) ---
    rx = int(max(24, win_frac * W * 0.5))
    ry = int(max(24, win_frac * H * 0.5))
    x0, x1 = max(0, int(cxg - rx)), min(W, int(cxg + rx))
    y0, y1 = max(0, int(cyg - ry)), min(H, int(cyg + ry))
    if (x1 - x0) < 6 or (y1 - y0) < 6:
        return float(W * 0.5), float(H * 0.5)

    roi = g[y0:y1, x0:x1].astype(np.float32).copy()

    # --- smooth & normalize locally ---
    roi = cv2.GaussianBlur(roi, (0, 0), 1.2)
    m, M = float(roi.min()), float(roi.max())
    if M > m:
        roi_n = (roi - m) / (M - m + 1e-12)
    else:
        return float(W * 0.5), float(H * 0.5)

    # --- coarse BRIGHT peak (DC) ---
    _, _, _, max_loc = cv2.minMaxLoc(roi_n)  # (x, y) in ROI coords
    x_coarse, y_coarse = max_loc

    # --- sub-pixel refinement via weighted centroid in 5×5 patch ---
    x_c = int(np.clip(x_coarse, 2, roi_n.shape[1] - 3))
    y_c = int(np.clip(y_coarse, 2, roi_n.shape[0] - 3))
    patch = roi_n[y_c - 2:y_c + 3, x_c - 2:x_c + 3].copy()

    # weights: brighten the peak and square to sharpen
    patch_w = np.clip(patch - patch.min(), 0.0, None)
    patch_w **= 2.0
    s = float(patch_w.sum())

    if s > 1e-12:
        py, px = np.mgrid[-2:3, -2:3]
        dx = float((patch_w * px).sum() / s)
        dy = float((patch_w * py).sum() / s)
    else:
        dx = dy = 0.0

    x_sub = x_c + dx
    y_sub = y_c + dy

    # --- map back to full image and clamp ---
    dcx = float(np.clip(x0 + x_sub, 0, W - 1))
    dcy = float(np.clip(y0 + y_sub, 0, H - 1))

    dcx = W * 0.11
    dcy = H * 0.5
    return dcx, dcy

OUT_BMP = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"

class ZeluxGUI():
    def __init__(self):
        self.show_coords_grid = None
        self.window_tag = "Zelux Window"
        self.HW = hw_devices.HW_devices()
        self.cam = self.HW.camera
        self.flipper = None
        self.flipper_serial_number = ""
        self.show_center_cross = True
        self.background_image = None
        self.subtract_background = False
        self.HW = hw_devices.HW_devices()
        self.positioner = self.HW.positioner
        self.manual_cross_pos = None
        self.rotation_count = 0
        self.zel_shift_x = 0.0  # in microns
        self.zel_shift_y = 0.0  # in microns
        self.ax_alpha = 253.7 # degrees
        self.show_axis = False
        self.cross_x = 1552
        self.cross_y = 701
        self.autosym_mode = "coarse" # coarse / normal

        # --- Target generator defaults ---
        self.target_mode = "gaussian"  # or "soft_disk"
        self.tgt_sigma_px = 48  # Gaussian / soft_disk size (px std for gaussian; radius for disk)
        self.tgt_sep_px = 260  # center-to-center separation for multi-spot (px)
        self.tgt_angle_deg = 90.0  # line angle (deg); 0=horizontal, 90=vertical
        self.tgt_weights = "1,1,1"  # relative weights; for two_spots use "1,1"

        try:
            self.background_image = np.load("zelux_background.npy")
            print("Background image loaded.")
        except FileNotFoundError:
            self.background_image = None
            print("No background image found.")

        self.AddNewWindow()

    def CaptureBackground(self):
        self.background_image = np.copy(self.cam.lateset_image_buffer)
        print("Background image captured.")
        np.save("zelux_background.npy", self.background_image)
        print("Background image saved.")

    def StartLive(self):
        # If the Stop button is already in place, we’re already live—do nothing.
        if dpg.does_item_exist("btnStopLive"):
            print("Already live; Stop button exists.")
            return

        self.cam.constantGrabbing = True
        self.LiveTh = threading.Thread(target=self.cam.LiveTh)
        self.LiveTh.setDaemon(True)
        self.LiveTh.start()

        if dpg.does_item_exist("btnStartLive"):
            # Create new button before deleting the old one
            dpg.add_button(label="Stop", tag="btnStopLive", parent=self.window_tag,
                           before="btnStartLive", callback=self.StopLive)
            dpg.bind_item_theme("btnStopLive", "btnRedTheme")
            dpg.delete_item("btnStartLive")

    def StopLive(self):
        self.cam.constantGrabbing = False
        self.LiveTh.join()

        if dpg.does_item_exist("btnStopLive"):
            # Create new button before deleting the old one
            dpg.add_button(label="Start", tag="btnStartLive", parent=self.window_tag,
                           before="btnStopLive", callback=self.StartLive)
            dpg.bind_item_theme("btnStartLive", "btnGreenTheme")
            dpg.delete_item("btnStopLive")

    def UpdateImage(self):
        window_size = dpg.get_item_width(self.window_tag), dpg.get_item_height(self.window_tag)
        _width, _height = window_size
        _width = _width
        _height = _height

        # Update image dimensions to match the new window size
        dpg.set_item_width("image_id", _width)
        dpg.set_item_height("image_id", _height)

        # dpg.delete_item("image_drawlist")
        # dpg.add_drawlist(tag="image_drawlist", width=_width, height=_width * self.cam.ratio, parent=self.window_tag)
        # dpg.draw_image(texture_tag="image_id", pmin=(0, 0), pmax=(_width, _width * self.cam.ratio), uv_min=(0, 0),
        #                uv_max=(1, 1), parent="image_drawlist")

        # rebuild drawlist
        disp_h = _width * self.cam.ratio
        if dpg.does_item_exist("image_drawlist"):
            dpg.delete_item("image_drawlist")
        dpg.add_drawlist(tag="image_drawlist", width=_width, height=disp_h, parent=self.window_tag)
        # flip image in X and Y by swapping UV coordinates
        dpg.draw_image(
            texture_tag="image_id",
            pmin=(0, 0),
            pmax=(_width, disp_h),
            uv_min=(1, 1),  # bottom-right corner of texture
            uv_max=(0, 0),  # top-left corner of texture
            parent="image_drawlist"
        )

        # dpg.set_value("image_id", self.cam.lateset_image_buffer)
        height = self.cam.camera.image_height_pixels
        width = self.cam.camera.image_width_pixels

        if self.subtract_background and self.background_image is not None:
            # Reshape to (H, W, 4)
            img_rgba = self.cam.lateset_image_buffer.reshape((height, width, 4))
            bg_rgba = self.background_image.reshape((height, width, 4))

            # Convert both to grayscale using RGB channels only
            gray = np.mean(img_rgba[:, :, :3], axis=2)
            bg_gray = np.mean(bg_rgba[:, :, :3], axis=2)

            offset = 0.25  # try values from 0.02 to 0.1 depending on noise level
            subtracted = gray - bg_gray + offset
            subtracted = np.clip(subtracted, 0, None)

            gamma = 0.98
            norm = np.clip(subtracted / (subtracted.max() + 1e-6), 0, 1)  # avoid div by 0
            bright = np.power(norm, gamma)

            # Convert grayscale back to RGBA
            rgba_img = np.stack([bright] * 3 + [np.ones_like(bright)], axis=-1)  # add alpha = 1
            img = rgba_img.astype(np.float32).reshape(-1)

        else:
            # Just use the raw RGBA buffer as-is
            img = self.cam.lateset_image_buffer.astype(np.float32)

        if self.rotation_count:
            img = self.cam.lateset_image_buffer.reshape((height, width, 4))
            # np.rot90 rotates CCW, so k = (4 - steps)
            img = np.rot90(img, k=(4 - self.rotation_count) % 4)
            # print("ui texture expects :", dpg.get_item_width("tex_zlx"),
            #       dpg.get_item_height("tex_zlx"))
            # print("array shape handed :", img.shape[:2][::-1])  # (width, height)
            _width, _height = img.shape[:2]

        # dpg.set_value("image_id", img)
        dpg.set_value("image_id", img.astype(np.float32).reshape(-1))
        # print(f"Live image range after subtraction: min={img.min():.3f}, max={img.max():.3f}")

        ratio = self.cam.ratio
        if self.rotation_count % 2:
            disp_h = _width * (1.0 / ratio)
        else:
            disp_h = _width * ratio

        dpg.set_item_width("image_id", _width)
        dpg.set_item_height("image_id", disp_h)

        # rebuild drawlist
        if dpg.does_item_exist("image_drawlist"):
            dpg.delete_item("image_drawlist")
        dpg.add_drawlist(tag="image_drawlist", width=_width, height=disp_h, parent=self.window_tag)
        # dpg.draw_image("image_id", (0, 0), (_width, disp_h), parent="image_drawlist")
        dpg.draw_image(
            texture_tag="image_id",
            pmin=(0, 0),
            pmax=(_width, disp_h),
            uv_min=(1, 1),  # bottom-right corner of texture
            uv_max=(0, 0),  # top-left corner of texture
            parent="image_drawlist"
        )

        # Draw cross if enabled
        if self.show_center_cross or self.show_coords_grid:
            if self.manual_cross_pos is None:
                center_x = _width / 2
                center_y = (_width * self.cam.ratio) / 2
            else:
                center_x, center_y = self.manual_cross_pos
            dpg.draw_line((center_x - 100, center_y), (center_x + 100, center_y), color=(0, 255, 0, 255), thickness=1,
                          parent="image_drawlist")
            dpg.draw_line((center_x, center_y - 100), (center_x, center_y + 100), color=(0, 255, 0, 255), thickness=1,
                          parent="image_drawlist")

            # Get current absolute position (stage coordinates)
            try:
                self.positioner.GetPosition()  # updates AxesPositions
                abs_x = self.positioner.AxesPositions[0]*1e-6
                abs_y = self.positioner.AxesPositions[1]*1e-6
                abs_z = self.positioner.AxesPositions[2]*1e-6
                coord_text = f"X = {abs_x:.1f}, Y = {abs_y:.1f}, Z = {abs_z:.1f}"
            except Exception as e:
                coord_text = "Stage position not available"

            # Draw coordinate text at bottom-left
            dpg.draw_text((10, _width * self.cam.ratio - 20), coord_text,
                          size=16, color=(0, 255, 0, 255), parent="image_drawlist")

        # Draw angled axis if enabled
        if self.show_axis:
            # compute center
            cx = _width / 2
            cy = (_width * self.cam.ratio) / 2
            alpha = np.deg2rad(self.ax_alpha)  # hard‑coded angle of 30°
            L = max(_width, _width * self.cam.ratio)  # length to span the image
            x1, y1 = cx - L * np.cos(alpha), cy - L * np.sin(alpha)
            x2, y2 = cx + L * np.cos(alpha), cy + L * np.sin(alpha)
            dpg.draw_line((x1, y1), (x2, y2),
                          color=(255, 255, 0, 255),
                          thickness=1,
                          parent="image_drawlist")

        # Draw coordinate grid if enabled
        if self.show_coords_grid:
            step_px = 100
            font_size = 14
            pixel_to_um_x = 0.04  # um/pixel
            pixel_to_um_y = 0.04  # um/pixel

            # Apply shift (in microns)
            x_shift_px = 3.18 / pixel_to_um_x
            y_shift_px = 1.4 / pixel_to_um_y

            # Horizontal lines (Y coords - reversed + shifted down)
            y = 0
            while y < (_width * self.cam.ratio) - step_px:
                y_shifted = y + y_shift_px
                offset_px = y_shifted - center_y
                coord_y = abs_y + offset_px * pixel_to_um_y

                dpg.draw_line((0, y_shifted), (_width, y_shifted), color=(100, 255, 100, 80), thickness=1,
                              parent="image_drawlist")
                dpg.draw_text((5, y_shifted + 2), f"{coord_y:.1f}", size=font_size,
                              color=(0, 255, 0, 200), parent="image_drawlist")
                y += step_px

            # Vertical lines (X coords - reversed + shifted right)
            x = 2 * step_px
            while x < _width:
                x_shifted = x + x_shift_px
                offset_px = x_shifted - center_x
                coord_x = abs_x - offset_px * pixel_to_um_x

                dpg.draw_line((x_shifted, 0), (x_shifted, _width * self.cam.ratio), color=(100, 255, 100, 80),
                              thickness=1, parent="image_drawlist")
                dpg.draw_text((x_shifted + 2, _width * self.cam.ratio - 18), f"{coord_x:.1f}", size=font_size,
                              color=(0, 255, 0, 200), parent="image_drawlist")
                x += step_px

            # ✅ Draw all future data (angles & energies)
            if hasattr(self, "all_future_data") and self.all_future_data:
                base_y = _width * self.cam.ratio - 770
                N = len(self.all_future_data)
                step_y = 61
                block_height = N * step_y
                Y_center = (_width * self.cam.ratio) / 2  + 55
                base_y = Y_center - block_height / 2-30
                for idx, (angle, E) in enumerate(self.all_future_data):
                    text = f"HWP={angle:.1f}°, E={E:.1f} nJ"
                    dpg.draw_text(
                        (220, base_y + idx * step_y),
                        text,
                        size=16,
                        color=(255, 255, 255, 255),
                        parent="image_drawlist"
                    )
            # ✅ Draw saved query points if any
            if hasattr(self, "query_points") and self.query_points:
                shift_x = getattr(self, "zel_shift_x", 0.0)+3.2
                shift_y = getattr(self, "zel_shift_y", 0.0)-1.4

                for index, x_um, y_um, z in self.query_points:
                    offset_x = (x_um + shift_x - abs_x) / pixel_to_um_x
                    offset_y = (y_um + shift_y - abs_y) / pixel_to_um_y
                    x_px = center_x - offset_x + x_shift_px
                    y_px = center_y + offset_y + y_shift_px

                    dpg.draw_circle(center=(x_px, y_px), radius=6.0,
                                    color=(255, 0, 0, 255), fill=(0, 0, 0, 255),
                                    parent="image_drawlist")
                    dpg.draw_text(pos=(x_px + 6, y_px - 6), text=f"{int(index)}",
                                  size=14, color=(255, 255, 0, 255),
                                  parent="image_drawlist")

        # === AutoSym 1st-order ROI overlay (closure-safe) ===
        roi = getattr(self, "autosym_roi", None)
        if roi:
            # Image-space size the metric used
            W_img = float(roi.get("W", 1.0))
            H_img = float(roi.get("H", 1.0))

            # Current drawlist size
            disp_w = float(_width)
            disp_h_val = float(disp_h)  # don't shadow the name 'disp_h'

            # Map IMAGE -> SCREEN. Bind params as defaults to avoid capturing 'roi'.
            def im2scr(x, y, W=W_img, H=H_img, DW=disp_w, DH=disp_h_val):
                X = DW * (1.0 - float(x) / W)  # X flipped (your UVs flip X)
                Y = DH * (1.0 - float(y) / H)  # Y flipped (your UVs flip Y)
                return X, Y

            # Uniform scale (pixels are square after your resize)
            sx = disp_w / W_img
            sy = disp_h_val / H_img
            s = 0.5 * (sx + sy)

            # ---- centers ----
            # DC / image center: wedge & annulus are centered HERE (global image center)
            cx0_img = 0.5 * W_img
            cy0_img = 0.5 * H_img
            cx0, cy0 = im2scr(cx0_img, cy0_img)

            # 1st-order centroid: just for the small dot (image coords stored by worker)
            c1x_img = float(roi.get("cx", cx0_img))
            c1y_img = float(roi.get("cy", cy0_img))
            c1x, c1y = im2scr(c1x_img, c1y_img)

            # Radii (defined in image pixels, measured from the image center)
            rmin = s * float(roi.get("rmin", 40.0))
            rmax = s * float(roi.get("rmax", 120.0))

            # Annulus
            dpg.draw_circle(center=(cx0, cy0), radius=rmin,
                            color=(255, 40, 40, 255), thickness=2, parent="image_drawlist")
            dpg.draw_circle(center=(cx0, cy0), radius=rmax,
                            color=(255, 40, 40, 255), thickness=2, parent="image_drawlist")

            # Symmetric wedge about dir_deg (angles are in IMAGE coords, origin = image center)
            wedge_deg = float(roi.get("wedge_deg", 32.0))
            dir_deg = float(roi.get("dir_deg", 0.0))
            half = 0.5 * wedge_deg
            a0 = np.deg2rad(dir_deg - half)
            a1 = np.deg2rad(dir_deg + half)

            def ray_endpoint(angle_rad, radius_img,
                             CX=cx0_img, CY=cy0_img, map_fn=im2scr):
                x_img = CX + radius_img * np.cos(angle_rad)
                y_img = CY + radius_img * np.sin(angle_rad)
                return map_fn(x_img, y_img)

            p0 = ray_endpoint(a0, float(roi.get("rmax", 120.0)))
            p1 = ray_endpoint(a1, float(roi.get("rmax", 120.0)))
            q0 = ray_endpoint(a0, float(roi.get("rmin", 40.0)))
            q1 = ray_endpoint(a1, float(roi.get("rmin", 40.0)))

            # Outer rays + inner ticks
            dpg.draw_line((cx0, cy0), p0, color=(255, 40, 40, 255), thickness=2, parent="image_drawlist")
            dpg.draw_line((cx0, cy0), p1, color=(255, 40, 40, 255), thickness=2, parent="image_drawlist")
            dpg.draw_line(q0, p0, color=(255, 40, 40, 80), thickness=1, parent="image_drawlist")
            dpg.draw_line(q1, p1, color=(255, 40, 40, 80), thickness=1, parent="image_drawlist")

            # 1st-order centroid marker
            dpg.draw_circle(center=(c1x, c1y), radius=3.0,
                            color=(255, 40, 40, 255), fill=(255, 40, 40, 255),
                            parent="image_drawlist")

            # Candidate debug overlay with labels
            cands = getattr(self, "autosym_debug_candidates", None)
            if cands:
                for c in cands:
                    X, Y = im2scr(float(c["x"]), float(c["y"]))
                    rad = max(3.0, float(c.get("r", 6.0)) * s)
                    chosen = bool(c.get("chosen", False))
                    col = (0, 255, 0, 255) if chosen else (255, 180, 0, 230)
                    dpg.draw_circle(center=(X, Y), radius=rad, color=col, thickness=2, parent="image_drawlist")
                    # Text label: brightness (sum), area, score
                    lbl = f"I={c.get('sum', 0):.3f}  A={c.get('area', 0):.0f}  S={c.get('score', 0):.2f}"
                    dpg.draw_text((X + 6, Y - rad - 14), lbl,
                                  size=14, color=col, parent="image_drawlist")
        # === /AutoSym ROI overlay ===

        # === Draw DC (yellow cross), independent from ROI ===
        dc = getattr(self, "autosym_dc", None)
        if dc and all(k in dc for k in ("x", "y", "W", "H")):
            W_img = float(dc["W"]);
            H_img = float(dc["H"])
            disp_w = float(_width);
            disp_h_scr = float(disp_h)

            # map image → screen (both axes flipped in UVs)
            def im2scr(x, y):
                X = disp_w * (1.0 - float(x) / W_img)
                Y = disp_h_scr * (1.0 - float(y) / H_img)
                return X, Y

            dcx, dcy = im2scr(float(dc["x"]), float(dc["y"]))

            L = 40.0  # cross half-length in screen px
            # subtle black outline for visibility
            dpg.draw_line((dcx - L, dcy), (dcx + L, dcy), color=(0, 0, 0, 255), thickness=3, parent="image_drawlist")
            dpg.draw_line((dcx, dcy - L), (dcx, dcy + L), color=(0, 0, 0, 255), thickness=3, parent="image_drawlist")
            # yellow cross
            dpg.draw_line((dcx - L, dcy), (dcx + L, dcy), color=(255, 255, 0, 255), thickness=1,
                          parent="image_drawlist")
            dpg.draw_line((dcx, dcy - L), (dcx, dcy + L), color=(255, 255, 0, 255), thickness=1,
                          parent="image_drawlist")
        # === /DC cross ===

    def toggle_show_axis(self, sender=None, app_data=None, user_data=None):
        """
        Callback for the 'Ax' checkbox.
        Toggles whether the angled axis line is shown, then redraws the image.
        """
        self.show_axis = app_data  # True when checked, False when unchecked
        self.UpdateImage()

    def UpdateExposure(sender, app_data=None, user_data=None):
        # a = dpg.get_value(sender)
        sender.cam.SetExposureTime(int(user_data * 1e3))
        time.sleep(0.001)
        dpg.set_value(item="slideExposure", value=sender.cam.camera.exposure_time_us / 1e3)
        print("Actual exposure time: " + str(sender.cam.camera.exposure_time_us / 1e3) + "milisecond")
        pass

    def set_cross_from_inputs(self, sender, app_data, user_data=None):
        """Read X/Y text boxes (strings), convert to ints, then redraw cross."""
        x_str = dpg.get_value("inpCrossX")
        y_str = dpg.get_value("inpCrossY")

        try:
            x = int(x_str)
            y = int(y_str)
        except ValueError:
            # you could show an error message here instead
            print(f"Invalid integer input: X='{x_str}', Y='{y_str}'")
            return

        self.manual_cross_pos = (x, y)
        self.show_center_cross = True
        dpg.set_value("chkShowCross", True)
        self.UpdateImage()

    def UpdateGain(sender, app_data, user_data):
        # a = dpg.get_value(sender)
        sender.cam.SetGain(user_data)
        time.sleep(0.001)
        dpg.set_value(item="slideGain", value=sender.cam.camera.convert_gain_to_decibels(sender.cam.camera.gain))
        print("Actual gain time: " + str(sender.cam.camera.convert_gain_to_decibels(sender.cam.camera.gain)) + "db")
        pass

    def AddNewWindow(self, _width=800):
        # self.cam.ratio = self.cam.image_height_pixels / self.cam.image_width_pixels
        _width = 1000

        with dpg.window(label=self.window_tag, tag=self.window_tag, no_title_bar=False,
                        pos=[15, 15],
                        width=int(_width * 1.0),
                        height=int(_width * self.cam.ratio * 1.2)):
            pass

    def DeleteMainWindow(self):
        dpg.delete_item(item=self.window_tag)
        pass

    def GUI_controls(self, isConnected=False, _width=800):
        dpg.delete_item("groupZeluxControls", children_only=False)
        self.set_all_themes()
        if isConnected:
            with dpg.group(tag="groupZeluxControls", parent=self.window_tag, horizontal=True):  # vertical container
                with dpg.group(tag="controls_row1_and2", horizontal=False):
                    with dpg.group(tag="controls_row1", horizontal=True):
                        dpg.add_button(label="Live", callback=self.StartLive, tag="btnStartLive")
                        dpg.add_button(label="Save", callback=self.cam.saveImage, tag="btnSave")

                        dpg.bind_item_theme("btnStartLive", "btnGreenTheme")
                        dpg.bind_item_theme("btnSave", "btnBlueTheme")

                        minExp = min(self.cam.camera.exposure_time_range_us) / 1e3
                        maxExp = max(self.cam.camera.exposure_time_range_us) / 1e3
                        dpg.add_slider_int(label="Exp", tag="slideExposure",
                                           width=100, callback=self.UpdateExposure,
                                           default_value=self.cam.camera.exposure_time_us / 1e3,
                                           min_value=minExp if minExp > 0 else 1,
                                           max_value=maxExp if maxExp < 1000 else 1000)

                        minGain = self.cam.camera.convert_gain_to_decibels(min(self.cam.camera.gain_range))
                        maxGain = self.cam.camera.convert_gain_to_decibels(max(self.cam.camera.gain_range))
                        dpg.add_slider_int(label="G", tag="slideGain",
                                           width=100, callback=self.UpdateGain,
                                           default_value=self.cam.camera.convert_gain_to_decibels(self.cam.camera.gain),
                                           min_value=minGain, max_value=maxGain)

                        dpg.add_checkbox(label="+", tag="chkShowCross", callback=self.toggle_center_cross,default_value=self.show_center_cross)
                        dpg.add_button(label="CapBG", callback=self.CaptureBackground)
                        dpg.add_checkbox(label="SubBG", tag="chkSubtractBG",
                                         callback=lambda s, a, u: setattr(self, 'subtract_background', a))
                        dpg.add_checkbox(label="KpSt", tag="keepSt", default_value=False)
                        dpg.add_checkbox(label="Ax", tag="Axis", callback=self.toggle_show_axis, default_value=self.show_axis)
                        # dpg.add_button(label="Rotate 90°", tag="btnRotate", callback=self.rotate_image)
                        dpg.add_button(label="GS", tag="btnIterateGS", callback=self.StartSLMIterations)
                        dpg.add_button(label="StopGS", tag="btnStopIter", callback=self.StopSLMIterations)
                        # --- Target maker controls ---
                        dpg.add_combo(
                            label="Target",
                            items=["gaussian", "soft_disk", "two_spots", "three_spots"],
                            default_value=getattr(self, "target_mode", "gaussian"),
                            width=140,
                            callback=lambda s, a, u: setattr(self, "target_mode", a)
                        )

                    with dpg.group(tag="controls_row2", horizontal=True):
                        dpg.add_button(label="Sv", tag="btnSaveProcessedImage", callback=self.SaveProcessedImage)

                        dpg.add_input_int(label="#X", tag="StitchNumFrames_X", width=110, default_value=10, min_value=1)
                        dpg.add_input_int(label="#Y", tag="StitchNumFrames_Y", width=110, default_value=10, min_value=1)

                        dpg.add_input_int(label="X[µm]", tag="StitchStepSize_X", default_value=20, width=110,
                                          min_clamped=True, min_value=1)
                        dpg.add_input_int(label="Y[µm]", tag="StitchStepSize_Y", default_value=20, width=110,
                                          min_clamped=True, min_value=1)
                        dpg.add_button(label="St", tag="btnStitchFrames", callback=self.StitchFrames)

                        dpg.add_checkbox(label="Coords", tag="chkShowCoords", callback=self.toggle_coords_display)
                        dpg.add_input_text(label="X_+", tag="inpCrossX",
                                           width=50, default_value=str(self.cross_x),
                                           on_enter=True)
                        dpg.add_input_text(label="Y_+", tag="inpCrossY",
                                           width=50, default_value=str(self.cross_y),
                                           on_enter=True)
                        dpg.add_button(label="Set +", tag="btnSetCross",
                                       callback=self.set_cross_from_inputs)

                    with dpg.group(horizontal=True):
                        dpg.add_input_int(label="Sigma/Radius", width=120,
                                          default_value=self.tgt_sigma_px,
                                          callback=lambda s, a, u: setattr(self, "tgt_sigma_px", int(a)))
                        dpg.add_input_int(label="Separation", width=120,
                                          default_value=self.tgt_sep_px,
                                          callback=lambda s, a, u: setattr(self, "tgt_sep_px", int(a)))
                        dpg.add_input_float(label="Angle°", width=120,
                                            default_value=self.tgt_angle_deg,
                                            callback=lambda s, a, u: setattr(self, "tgt_angle_deg", float(a)))
                        dpg.add_input_text(label="Weights", width=120,
                                           default_value=self.tgt_weights,
                                           callback=lambda s, a, u: setattr(self, "tgt_weights", a))
                        dpg.add_button(label="Make Target", callback=self._save_current_target_bitmap)
                        dpg.add_button(label="AutoSym", tag="btnAutoSym", callback=self.StartAutoSym)
                        dpg.add_button(label="StopSym", tag="btnStopAutoSym", callback=self.StopAutoSym)

        else:
            dpg.add_group(tag="ZeluxControls", parent=self.window_tag, horizontal=False)
            dpg.add_text("camera is probably not connected")

    def Controls(self):
        dpg.add_group(tag="ZeluxControls", parent=self.window_tag, horizontal=True)

        if len(self.cam.available_cameras) < 1:
            self.GUI_controls(isConnected=False, _width=700)
            pass
        else:
            if dpg.does_item_exist("image_tag"):
                dpg.delete_item("image_tag")

            with dpg.texture_registry(tag="image_tag", show=False):
                dpg.add_dynamic_texture(width=self.cam.camera.image_width_pixels,
                                        height=self.cam.camera.image_height_pixels,
                                        default_value=self.cam.lateset_image_buffer,
                                        tag="image_id", parent="image_tag")

            self.GUI_controls(isConnected=True)
            pass

    def toggle_coords_display(self, sender, app_data, user_data=None):
        self.show_coords_grid = app_data  # True or False
        self.UpdateImage()

    def SaveProcessedImage(self):

        height = self.cam.camera.image_height_pixels
        width = self.cam.camera.image_width_pixels

        # Always reshape the latest frame
        img_rgba = self.cam.lateset_image_buffer.reshape((height, width, 4))

        # Utility: convert any image array to float in [0, 1] safely
        def to_float01(a):
            if a.dtype == np.uint8:
                return a.astype(np.float32) / 255.0
            if np.issubdtype(a.dtype, np.integer):
                maxv = float(np.iinfo(a.dtype).max)
                return a.astype(np.float32) / maxv
            # float input
            return np.clip(a.astype(np.float32), 0.0, 1.0)

        # ---------------- Image prep ----------------
        if self.subtract_background and getattr(self, "background_image", None) is not None:
            # Convert both current frame and background to float [0,1]
            bg_rgba = self.background_image.reshape((height, width, 4))
            img_rgb_f = to_float01(img_rgba[:, :, :3])
            bg_rgb_f = to_float01(bg_rgba[:, :, :3])

            # Grayscale, subtract, offset, clip
            gray = img_rgb_f.mean(axis=2)
            bggray = bg_rgb_f.mean(axis=2)

            offset = 0.25
            subtracted = np.clip(gray - bggray + offset, 0.0, None)

            # Normalize + gamma, then expand back to 3-channel 8-bit
            gamma = 0.98
            norm = subtracted / (subtracted.max() + 1e-6)
            bright = np.power(norm, gamma)
            img_rgb = (np.repeat(bright[..., None], 3, axis=2) * 255.0).astype(np.uint8)
        else:
            # No background subtraction: DO NOT rescale if buffer already uint8
            rgb = img_rgba[:, :, :3]
            if rgb.dtype == np.uint8:
                img_rgb = rgb.copy()
            else:
                img_rgb = (np.clip(rgb, 0.0, 1.0) * 255.0).astype(np.uint8)

        # ---------------- Overlays ----------------
        if getattr(self, "show_center_cross", False) or getattr(self, "show_coords_grid", False):
            center_x = width // 2
            center_y = height // 2

            # Crosshair
            cv2.line(img_rgb, (center_x - 100, center_y), (center_x + 100, center_y), (0, 255, 0), 1)
            cv2.line(img_rgb, (center_x, center_y - 100), (center_x, center_y + 100), (0, 255, 0), 1)

            # Stage coordinates (keep your original units behavior)
            abs_x = abs_y = abs_z = 0.0
            try:
                self.positioner.GetPosition()
                abs_x = self.positioner.AxesPositions[0] * 1e-6  # microns to meters? (kept as in your code)
                abs_y = self.positioner.AxesPositions[1] * 1e-6
                abs_z = self.positioner.AxesPositions[2] * 1e-6
                coord_text = f"X = {abs_x:.1f}, Y = {abs_y:.1f}, Z = {abs_z:.1f}"
            except Exception:
                coord_text = "Stage position not available"

            cv2.putText(img_rgb, coord_text, (10, height - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

        if getattr(self, "show_coords_grid", False):
            # Defaults if the position fetch failed above
            if "abs_x" not in locals():  # just in case
                abs_x = abs_y = 0.0

            step_px = 100
            pixel_to_um_x = 0.04  # um/pixel
            pixel_to_um_y = 0.04
            x_shift_px = 2.38 / pixel_to_um_x
            y_shift_px = 0.85 / pixel_to_um_y

            # Horizontal grid lines
            y = 0
            while y < height - step_px:
                y_shifted = int(y + y_shift_px)
                offset_px = y_shifted - (height // 2)
                coord_y = abs_y + offset_px * pixel_to_um_y
                cv2.line(img_rgb, (0, y_shifted), (width, y_shifted), (100, 255, 100), 1, cv2.LINE_AA)
                cv2.putText(img_rgb, f"{coord_y:.1f}", (5, y_shifted + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                y += step_px

            # Vertical grid lines
            x = 2 * step_px
            while x < width:
                x_shifted = int(x + x_shift_px)
                offset_px = x_shifted - (width // 2)
                coord_x = abs_x - offset_px * pixel_to_um_x
                cv2.line(img_rgb, (x_shifted, 0), (x_shifted, height), (100, 255, 100), 1, cv2.LINE_AA)
                cv2.putText(img_rgb, f"{coord_x:.1f}", (x_shifted + 2, height - 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                x += step_px

        # ---------------- Save ----------------
        folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/Images/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)

        timeStamp = getCurrentTimeStamp()
        filename = os.path.join(folder_path, f"Zelux_Image_{timeStamp}.png")

        # OpenCV expects BGR
        cv2.imwrite(filename, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
        print(f"Image saved with overlays to: {filename}")

        try:
            copy_image_to_clipboard(filename)
        except Exception:
            pass

        return filename

    def rotate_image(self, sender, app_data, user_data=None):
        """Rotate the live image by 90° clockwise."""
        self.rotation_count = (self.rotation_count + 1) % 4
        self.UpdateImage()

    def StitchFrames(self, sender, app_data, user_data=None):
        self.show_center_cross = True  # Show the cross
        dpg.set_value("chkShowCross", True)

        # Read values from new inputs
        step_um_x = dpg.get_value("StitchStepSize_X")
        step_um_y = dpg.get_value("StitchStepSize_Y")
        num_frames_x = dpg.get_value("StitchNumFrames_X")
        num_frames_y = dpg.get_value("StitchNumFrames_Y")

        # Convert to picometers
        step_pm_x = int(step_um_x * self.positioner.StepsIn1mm * 1e-3)
        step_pm_y = int(step_um_y * self.positioner.StepsIn1mm * 1e-3)

        folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/Images/Stitch/'
        os.makedirs(folder_path, exist_ok=True)

        # Clear folder before saving
        keep_all = dpg.get_value("keepSt")
        folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/Images/Stitch/'
        if not keep_all:
            for fname in os.listdir(folder_path):
                if fname.lower() == "bg.png":
                    continue  # ❌ Skip background image
                fpath = os.path.join(folder_path, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
            print("Stitch folder cleared (except bg.png).")
        else:
            print("Stitch folder cleanup skipped (keepSt is ON)")

        try:
            self.positioner.GetPosition()
            start_x = int(self.positioner.AxesPositions[0])
            start_y = int(self.positioner.AxesPositions[1])
            start_z = int(self.positioner.AxesPositions[2])
        except Exception as e:
            print(f"Cannot read stage position: {e}")
            return

        # Precompute target positions
        target_positions = []
        for j in range(num_frames_y):  # Y loop
            for i in range(num_frames_x):  # X loop
                x_pos = start_x + i * step_pm_x
                y_pos = start_y + j * step_pm_y
                target_positions.append((i, j, x_pos, y_pos))


        for i, j, x_target, y_target in target_positions:
            abs_x = x_target * 1e-6
            abs_y = y_target * 1e-6

            # Format coordinate string exactly as in filename (3 decimals)
            x_str = f"{round(abs_x, 2):.2f}"
            y_str = f"{round(abs_y, 2):.2f}"

            search_str = f"Zelux_X = {x_str}_Y = {y_str}_"
            already_saved = any(search_str in fname for fname in os.listdir(folder_path))
            if already_saved:
                print(f"Skipping ({x_str}, {y_str}) — already saved.")
                continue

            # Move to X
            if abs(self.positioner.AxesPositions[0] - x_target) > 1:
                self.positioner.MoveABSOLUTE(0, x_target)
                time.sleep(0.001)
                while not self.positioner.ReadIsInPosition(0):
                    time.sleep(0.001)

            # Move to Y
            if abs(self.positioner.AxesPositions[1] - y_target) > 1:
                self.positioner.MoveABSOLUTE(1, y_target)
                time.sleep(0.001)
                while not self.positioner.ReadIsInPosition(1):
                    time.sleep(0.001)

            # Optional Z correction
            if len(self.positioner.LoggedPoints) == 3:
                current_pos = np.array([x_target, y_target, start_z])
                ref_pos = list(self.initial_scan_Location) if hasattr(self, "initial_scan_Location") else [start_x,
                                                                                                           start_y,
                                                                                                           start_z]
                ref_pos[2] = start_z
                corrected_z = int(self.Z_correction(ref_pos, current_pos))
                self.positioner.MoveABSOLUTE(2, corrected_z)
                time.sleep(0.2)
                while not self.positioner.ReadIsInPosition(2):
                    time.sleep(0.001)

            # Capture image
            self.positioner.GetPosition()
            abs_x = x_target * 1e-6
            abs_y = y_target * 1e-6
            abs_z = round(self.positioner.AxesPositions[2] * 1e-6, 2)

            coord_text = f"X = {abs_x:.2f}_Y = {abs_y:.2f}_Z = {abs_z:.2f}"
            img_rgba = self.cam.lateset_image_buffer.reshape((self.cam.camera.image_height_pixels,
                                                              self.cam.camera.image_width_pixels, 4))
            img_rgb = img_rgba[:, :, :3]
            img_rgb = img_rgb / (img_rgb.max() + 1e-6)
            img_rgb = (img_rgb * 255).astype(np.uint8)

            filename = os.path.join(folder_path, f"Zelux_{coord_text}.png")
            cv2.imwrite(filename, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
            # print(f"Saved {filename}")
            print(f"Saved {len(os.listdir(folder_path))}/{len(target_positions)}: {os.path.basename(filename)}")

        # Return to start
        print("Returning to starting position...")
        for ch, pos in zip([0, 1, 2], [start_x, start_y, start_z]):
            try:
                self.positioner.MoveABSOLUTE(ch, pos)
                time.sleep(0.001)
                while not self.positioner.ReadIsInPosition(ch):
                    time.sleep(0.001)
            except Exception as e:
                print(f"Error returning axis {ch} to position: {e}")

    def toggle_center_cross(self, sender, app_data, user_data=None):
        self.show_center_cross = app_data  # True or False
        self.UpdateImage()  # Re-draw with or without the cross

    def Move_flipper(self, serial_number):
        try:
            self.flipper = FilterFlipperController(serial_number=serial_number)
            self.flipper.connect()
            self.flipper.toggle()
        except Exception as e:
            print(e)

    def set_all_themes(self):
        if dpg.does_item_exist("OnTheme"):
            dpg.delete_item("OnTheme")
        if dpg.does_item_exist("OffTheme"):
            dpg.delete_item("OffTheme")

        with dpg.theme(tag="OnTheme"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 200, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (0, 180, 0))  # handle when pressed
                # Optionally color the track:
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 70, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (60, 80, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 90, 70))

        # OFF Theme: keep the slider handle red in all states.
        with dpg.theme(tag="OffTheme"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (200, 0, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (180, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (70, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (80, 60, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (90, 70, 70))

    def Z_correction(self, _refp: list, _point: list):
        # Define the points (self.positioner.LoggedPoints equivalent)
        P = np.array(self.positioner.LoggedPoints)
        refP = np.array(_refp)
        point = np.array(_point)

        # Vector U and normalization
        U = P[1, :] - P[0, :]
        u = U / np.linalg.norm(U)

        # Vector V and normalization
        V = P[2, :] - P[0, :]
        v = V / np.linalg.norm(V)

        # Cross product to find the normal vector N
        N = np.cross(u, v)

        # Calculate D
        D = -np.dot(refP, N)

        # Calculate the new points Pnew
        # Pnew = -(point[:, :2] @ N[:2] + D) / N[2]
        Znew = -(point[:2] @ N[:2] + D) / N[2]

        # print(Znew)

        return Znew

    def StartSLMIterations(self, sender=None, app_data=None, user_data=None):
        """Launch GS iterations in a background thread and auto-save (Sv) every round."""
        if getattr(self, "_iter_th", None) and self._iter_th.is_alive():
            print("Iteration already running.")
            return
        self._iter_stop = False
        self._iter_th = threading.Thread(target=self._SLMIterationsWorker, daemon=True)
        self._iter_th.start()
        print("Started SLM iteration thread.")

    def StopSLMIterations(self, sender=None, app_data=None, user_data=None):
        """Signal the worker to stop after the current round."""
        self._iter_stop = True
        print("Stopping iterations...")

    def _save_current_target_bitmap(self):
        import cv2, os, numpy as np
        CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
        TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"

        corr = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr is None:
            print(f"❌ Cannot read correction map: {CORR_BMP}")
            return
        H, W = corr.shape
        mode = getattr(self, "target_mode", "gaussian")
        tgt = self._build_synth_target(W, H, mode)
        ok = cv2.imwrite(TARGET_BMP, (np.clip(tgt, 0, 1) * 255).astype(np.uint8))
        if ok:
            print(f"✅ Target ({mode}) written to {TARGET_BMP}  | size={W}x{H}")
        else:
            print("❌ Failed to write target bitmap")

    def _parse_weights(self, count):
        try:
            w = [float(x) for x in self.tgt_weights.replace(";", ",").split(",")]
        except Exception:
            w = []
        if len(w) < count:
            w = (w + [1.0] * count)[:count]
        w = np.clip(np.array(w, dtype=np.float32), 1e-6, None)
        return w / w.sum()

    def _build_synth_target(self, W, H, mode):
        import numpy as np, cv2
        yy, xx = np.mgrid[0:H, 0:W]
        cx, cy = W / 2.0, H / 2.0
        sig = max(2, int(self.tgt_sigma_px))
        img = np.zeros((H, W), np.float32)

        if mode == "gaussian":
            r2 = (xx - cx) ** 2 + (yy - cy) ** 2
            img = np.exp(-0.5 * r2 / (sig * sig)).astype(np.float32)

        elif mode == "soft_disk":
            # cosine-edged disk
            r = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
            core = (r <= sig).astype(np.float32)
            rim = (r > sig) & (r < 1.2 * sig)
            img = core.copy()
            img[rim] = 0.5 * (1 + np.cos(np.pi * (r[rim] - sig) / (0.2 * sig)))

        elif mode in ("two_spots", "three_spots"):
            n = 2 if mode == "two_spots" else 3
            w = self._parse_weights(n)
            sep = float(self.tgt_sep_px)
            ang = np.deg2rad(float(self.tgt_angle_deg))
            dx, dy = (sep / 2.0) * np.cos(ang), (sep / 2.0) * np.sin(ang)

            centers = []
            if n == 2:
                centers = [(cx - dx, cy - dy), (cx + dx, cy + dy)]
            else:
                # 3 spots: one at center, two symmetric
                centers = [(cx, cy), (cx - dx, cy - dy), (cx + dx, cy + dy)]

            for (ux, uy), ww in zip(centers, w):
                r2 = (xx - ux) ** 2 + (yy - uy) ** 2
                spot = np.exp(-0.5 * r2 / (sig * sig)).astype(np.float32)
                img += ww * spot
        else:
            # Fallback to single Gaussian
            r2 = (xx - cx) ** 2 + (yy - cy) ** 2
            img = np.exp(-0.5 * r2 / (sig * sig)).astype(np.float32)

        # normalize & very light apodization to suppress ringing
        if img.max() > 0: img /= img.max()
        ap_sig = 0.16
        x = (xx - cx) / (W / 2.0);
        y = (yy - cy) / (H / 2.0)
        apod = np.exp(-(x * x + y * y) / (2 * ap_sig * ap_sig)).astype(np.float32)
        img = (img * apod)
        img /= (img.max() + 1e-8)
        return img

    def _write_phase_with_corr(self, phase_core_rad: np.ndarray, corr_u8: np.ndarray,
                               out_path: str, carrier_cmd=(250.0, 0.0),
                               steer_cmd=(0.0, 0.0), settle_s: float = 0.35):
        """
        Compose final phase:
            phase_out = wrap( phase_core
                              + ramp(carrier_cmd + steer_cmd)
                              + corr_phase )
        Save as BMP at out_path so the Hamamatsu app can pick it up.
        """
        import numpy as np, cv2, time
        H, W = phase_core_rad.shape
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

        # convert correction to radians using your converter
        corr_phase = (corr_u8.astype(np.float32) * (2.0 * np.pi / 255.0)) if corr_u8 is not None else 0.0

        Cx, Cy = carrier_cmd;
        Sx, Sy = steer_cmd
        ramp = -2.0 * np.pi * ((Cx + Sx) * (xx / W) + (Cy + Sy) * (yy / H))

        phase_out = np.remainder(phase_core_rad.astype(np.float32) + ramp + corr_phase, 2.0 * np.pi)

        # use your existing phase_to_u8()
        u8 = phase_to_u8(phase_out)
        ok = cv2.imwrite(out_path, u8)
        if not ok:
            print(f"❌ Failed writing {out_path}")
        if settle_s and settle_s > 0:
            time.sleep(settle_s)
            st = os.stat(OUT_BMP)
            # print(f"[SLM] wrote {OUT_BMP} size={st.st_size} mtime={st.st_mtime:.3f}")

    def _spot_second_moments(self, img01: np.ndarray, roi_px=220):
        """Returns (sigma_x, sigma_y, cx, cy) on a bright blob; img01 in [0..1]."""
        import numpy as np, cv2
        H, W = img01.shape

        g = cv2.GaussianBlur(img01.astype(np.float32), (0, 0), 1.6)
        thr = np.quantile(g, 0.85)
        m = (g >= thr).astype(np.uint8)
        num, labels = cv2.connectedComponents(m)
        if num <= 1:
            cx, cy = W / 2.0, H / 2.0
        else:
            areas = [(labels == i).sum() for i in range(1, num)]
            i_max = 1 + int(np.argmax(areas))
            mask = (labels == i_max).astype(np.float32)
            s = mask.sum() + 1e-8
            yy, xx = np.mgrid[0:H, 0:W]
            cy = float((yy * mask).sum() / s);
            cx = float((xx * mask).sum() / s)

        # crop ROI and compute σx, σy
        x0 = int(max(0, cx - roi_px // 2));
        x1 = int(min(W, cx + roi_px // 2))
        y0 = int(max(0, cy - roi_px // 2));
        y1 = int(min(H, cy + roi_px // 2))
        patch = g[y0:y1, x0:x1]
        H2, W2 = patch.shape
        yy2, xx2 = np.mgrid[0:H2, 0:W2]
        m0 = float(patch.sum()) + 1e-8
        mx = float((xx2 * patch).sum() / m0);
        my = float((yy2 * patch).sum() / m0)
        sx = float(np.sqrt((((xx2 - mx) ** 2) * patch).sum() / m0))
        sy = float(np.sqrt((((yy2 - my) ** 2) * patch).sum() / m0))
        return sx, sy, cx, cy

    def _zernike_minimal(self, W, H, aperture='circle'):
        """
        Low-order modes on panel grid: defocus (Z20), astig x/y (Z2m2, Z22), coma x/y (Z3m1, Z31).
        RMS-normalized under mask so step sizes are comparable.
        """
        import numpy as np
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        x = (xx - W / 2) / (W / 2);
        y = (yy - H / 2) / (H / 2)
        r = np.sqrt(x * x + y * y);
        th = np.arctan2(y, x)
        mask = (r <= 1.0).astype(np.float32) if aperture == 'circle' else np.ones((H, W), np.float32)

        Z = {}
        Z['Z20'] = mask * (2 * r * r - 1)  # defocus
        Z['Z2m2'] = mask * (r * r * np.cos(2 * th))  # astig @ 0°
        Z['Z22'] = mask * (r * r * np.sin(2 * th))  # astig @ 45°
        Z['Z3m1'] = mask * (r ** 3 * np.cos(th))  # coma x
        Z['Z31'] = mask * (r ** 3 * np.sin(th))  # coma y
        for k in Z:
            a = Z[k];
            s = float(np.sqrt((a * a * mask).sum()) + 1e-12);
            Z[k] = a / s
        return Z

    def _SLMIterationsWorker(self):
        """
        Runs GS iterations that:
          • write an SLM BMP with the phase + correction
          • trigger a Zelux save (self.SaveProcessedImage)
          • compute ROI MSE (energy-normalized) + centroid
          • steer with a soft-limited proportional controller
          • do relaxed GS updates toward a centered target
        """
        # ---------------- CONFIG ----------------
        CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
        TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"
        OUT_BMP = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"
        CARRIER_CMD = (250.0, 0.0)  # spectral-px offset (try 150–300 each axis)

        OUTER_ITERS = 10  # outer rounds
        INNER_GS = 40  # GS steps per round (relaxed)
        BETA_GS = 0.65  # 0.5–0.7 is stable
        APOD_SIGMA = 0.16  # edge taper for target
        ROI = 200

        # Steering controller
        Kp = 0.35  # proportional gain
        SOFT_LIM = 60.0  # soft limit for commanded spectral px
        SETTLE_S = 0.45

        CALIB_PATH = r"C:\WC\HotSystem\Utils\slm_calibration.json"
        FORCE_RECAL = False  # set True if you want to re-measure

        import json
        from datetime import datetime

        import os, glob, time
        import numpy as np
        import cv2

        # --------------- Helpers ----------------
        def _count_peaks(img01, rel=0.35, min_sep=60, max_peaks=10, debug_path=None):
            """
            Count bright spots via non-maximum suppression.
            - rel: keep pixels > rel * max(img)
            - min_sep: suppress a disk of this radius around each found peak (px)
            """
            import cv2, numpy as np

            g = cv2.GaussianBlur(img01.astype(np.float32), (0, 0), 1.2)
            m = g.max()
            if m <= 1e-8:
                return 0

            work = g.copy()
            peaks = []
            thr = rel * m

            # simple NMS: repeatedly pick the max and suppress its neighborhood
            for _ in range(max_peaks):
                y, x = np.unravel_index(np.argmax(work), work.shape)
                v = work[y, x]
                if v < thr:
                    break
                peaks.append((x, y, float(v)))
                cv2.circle(work, (x, y), int(min_sep), 0, -1)

            # optional debug overlay
            if debug_path is not None and len(peaks):
                vis = (255 * (g / m)).astype(np.uint8)
                vis = cv2.cvtColor(vis, cv2.COLOR_GRAY2BGR)
                for x, y, _ in peaks:
                    cv2.circle(vis, (int(x), int(y)), int(min_sep // 2), (0, 255, 0), 2)
                cv2.imwrite(debug_path, vis)

            return len(peaks)

        def save_calib(path, panel_wh, sx, sy):
            W, H = panel_wh
            data = {
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "panel": {"W": int(W), "H": int(H)},
                "sx": float(sx),
                "sy": float(sy)
            }
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                print(f"[Calib] saved to {path}  (sx={sx:.4f}, sy={sy:.4f})")
            except Exception as e:
                print(f"[Calib] ⚠️ failed to save: {e}")

        def load_calib(path, panel_wh):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                W, H = panel_wh
                if int(data["panel"]["W"]) == int(W) and int(data["panel"]["H"]) == int(H):
                    sx = float(data["sx"]);
                    sy = float(data["sy"])
                    print(f"[Calib] loaded from {path}  (sx={sx:.4f}, sy={sy:.4f})")
                    return sx, sy
                else:
                    print("[Calib] file exists but panel size mismatch; recalibrating.")
                    return None
            except FileNotFoundError:
                return None
            except Exception as e:
                print(f"[Calib] ⚠️ could not read {path}: {e}")
                return None

        def phase_to_u8(phase_rad):
            ph = np.mod(phase_rad, 2 * np.pi)
            return np.uint8(np.round(ph * (255.0 / (2 * np.pi))))

        def u8_to_phase(u8):
            return (u8.astype(np.float32) / 255.0) * 2 * np.pi

        def preprocess_target_to_panel(target_path, panel_wh, x_shift=0, y_shift=0, rot_deg=0.0):
            """Load grayscale target, resize to panel, (optional) rotate+translate, apodize once."""
            W, H = panel_wh
            img = cv2.imread(target_path, cv2.IMREAD_GRAYSCALE)
            if img is None:
                raise FileNotFoundError(target_path)
            tgt = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
            if tgt.max() > 0: tgt /= tgt.max()
            # rotation then translation
            Mrot = cv2.getRotationMatrix2D((W / 2, H / 2), rot_deg, 1.0)
            tgt = cv2.warpAffine(tgt, Mrot, (W, H), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            Mtran = np.float32([[1, 0, x_shift], [0, 1, y_shift]])
            tgt = cv2.warpAffine(tgt, Mtran, (W, H), flags=cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            # apodize once to reduce ringing
            yy, xx = np.mgrid[0:H, 0:W]
            x = (xx - W / 2) / (W / 2);
            y = (yy - H / 2) / (H / 2)
            r2 = x * x + y * y
            apod = np.exp(-r2 / (2 * APOD_SIGMA * APOD_SIGMA)).astype(np.float32)
            tgt *= apod
            tgt /= (tgt.max() + 1e-8)
            return tgt

        def gs_update_relaxed(phase_slm, target_amp, steps=30, beta=0.6, phi_carrier=None):
            """Relaxed GS with optional carrier (added in SLM plane)."""
            if phi_carrier is None:
                phi_carrier = 0.0
            for _ in range(steps):
                field_s = np.exp(1j * (phase_slm + phi_carrier))  # <-- include carrier
                field_f = np.fft.fftshift(np.fft.fft2(field_s))
                amp_f = np.abs(field_f)
                phase_f = np.angle(field_f)

                amp_new = (1 - beta) * amp_f + beta * target_amp
                field_f_new = amp_new * np.exp(1j * phase_f)

                field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))
                # remove carrier again to keep phase_slm as the *residual* we optimize
                phase_slm = np.angle(field_s_back * np.exp(-1j * phi_carrier)).astype(np.float32)
            return np.mod(phase_slm, 2 * np.pi)

        def brightest_centroid(img01):
            # noise-robust: light median then gaussian
            g = cv2.medianBlur((img01 * 255).astype(np.uint8), 3).astype(np.float32) / 255.0
            g = cv2.GaussianBlur(g, (0, 0), 2.0)
            thr = np.quantile(g, 0.80)
            m = (g >= thr).astype(np.uint8)
            num, labels = cv2.connectedComponents(m)
            if num <= 1:
                H, W = g.shape;
                return W / 2.0, H / 2.0
            areas = [(labels == i).sum() for i in range(1, num)]
            i_max = 1 + int(np.argmax(areas))
            mask = (labels == i_max).astype(np.float32);
            s = mask.sum() + 1e-8
            yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]]
            cy = float((yy * mask).sum() / s);
            cx = float((xx * mask).sum() / s)
            return cx, cy

        def calibrate_steering(phase_slm, corr_u8, out_path, W, H,
                               dir_img=r"Q:\QT-Quantum_Optic_Lab\expData\Images",
                               probe_px=40.0, settle_s=0.3, timeout_s=6.0):
            """Measure (sx, sy): camera-px per commanded spectral-px (panel units)."""

            def latest_path():
                pats = [os.path.join(dir_img, "Zelux_*.png"),
                        os.path.join(dir_img, "Zelux_Image_*.png"),
                        os.path.join(dir_img, "*.png"),
                        os.path.join(dir_img, "*.bmp")]
                files = []
                for p in pats: files.extend(glob.glob(p))
                return max(files, key=os.path.getmtime) if files else None

            def write_phase(ph):
                ph_out = np.mod(ph + u8_to_phase(corr_u8), 2 * np.pi)
                cv2.imwrite(out_path, phase_to_u8(ph_out))

            def capture_new_after(old_path):
                try:
                    new_path = self.SaveProcessedImage()
                except Exception:
                    new_path = None
                t0 = time.time()
                while time.time() - t0 < timeout_s:
                    p = latest_path()
                    if p and p != old_path and (not new_path or p == new_path):
                        return p
                    time.sleep(0.1)
                return latest_path()

            def read_gray01(p):
                img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                if img is None: return None
                if img.ndim == 3:
                    if img.shape[2] == 4: img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = img.astype(np.float32)
                if img.shape[0] > 40: img = img[:-40, :]
                if img.max() > 0: img /= img.max()
                return cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA)

            def apply_and_measure(cmdx, cmdy):
                yy, xx = np.mgrid[0:H, 0:W]
                ramp = -2 * np.pi * (cmdx * (xx / W) + cmdy * (yy / H))
                ph = np.mod(phase_slm + ramp.astype(np.float32), 2 * np.pi)
                old = latest_path()
                write_phase(ph)
                time.sleep(settle_s)
                p = capture_new_after(old)
                img01 = read_gray01(p)
                if img01 is None:
                    return W / 2.0, H / 2.0
                return brightest_centroid(img01)

            # Baseline + symmetric probes per axis
            _ = apply_and_measure(0.0, 0.0)
            cxp, _ = apply_and_measure(+probe_px, 0.0)
            cxm, _ = apply_and_measure(-probe_px, 0.0)
            dx_meas = (cxp - cxm) / 2.0
            sx = dx_meas / probe_px

            _, cyp = apply_and_measure(0.0, +probe_px)
            _, cym = apply_and_measure(0.0, -probe_px)
            dy_meas = (cyp - cym) / 2.0
            sy = dy_meas / probe_px

            print(f"[Calib] steering gain: sx={sx:.3f}, sy={sy:.3f}")
            return sx, sy

        # --------------- Load maps & target ---------------
        corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr_u8 is None:
            print(f"❌ Cannot read correction BMP: {CORR_BMP}")
            return
        H, W = corr_u8.shape
        print(f"Panel (from correction): {W}x{H}")

        def save_phase_with_correction(
                phase_core_rad: np.ndarray,
                corr_map,  # uint8 correction map OR float32 phase (rad)
                out_path: str,
                carrier_cmd: tuple[float, float] = (0.0, 0.0),  # (Cx, Cy) spectral px
                steer_cmd: tuple[float, float] = (0.0, 0.0),  # (Sx, Sy) spectral px
                settle_s: float = 0.45
        ) -> None:
            """
            Compose final phase sent to the SLM:

                phase_out = wrap( phase_core_rad
                                  + ramp(carrier_cmd + steer_cmd)
                                  + corr_phase )

            - phase_core_rad: the GS-optimized residual phase (no carrier, no correction)
            - corr_map: uint8 correction BMP *or* float32 phase [rad] of same size
            - carrier_cmd / steer_cmd are in 'spectral pixels' (panel coords)
            """
            # ---- shapes & types ----
            if phase_core_rad.dtype != np.float32:
                phase_core = phase_core_rad.astype(np.float32, copy=False)
            else:
                phase_core = phase_core_rad

            H, W = phase_core.shape
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)

            # ---- correction phase (accept u8 or phase) ----
            if corr_map is None:
                corr_phase = 0.0
            elif corr_map.dtype == np.uint8:
                # u8 -> phase in radians
                corr_phase = (corr_map.astype(np.float32) * (2.0 * np.pi / 255.0))
            else:
                # assume already radians
                corr_phase = corr_map.astype(np.float32, copy=False)

            # ---- ramps (carrier + steering) ----
            Cx, Cy = carrier_cmd
            Sx, Sy = steer_cmd
            # same convention used in calibration and everywhere else:
            ramp = -2.0 * np.pi * ((Cx + Sx) * (xx / W) + (Cy + Sy) * (yy / H))

            # ---- compose & wrap to [0, 2π) ----
            phase_out = np.remainder(phase_core + ramp + corr_phase, 2.0 * np.pi)

            # ---- write as 8-bit LUT ----
            u8 = np.uint8(np.round(phase_out * (255.0 / (2.0 * np.pi))))
            ok = cv2.imwrite(out_path, u8)
            if not ok:
                print(f"❌ Failed writing {out_path}")

            if settle_s and settle_s > 0:
                time.sleep(settle_s)

        def centroid_first_order(img01, dead_radius=120):
            import numpy as np, cv2
            H, W = img01.shape
            cy0, cx0 = H / 2.0, W / 2.0
            g = cv2.GaussianBlur(img01.astype(np.float32), (0, 0), 2.0)
            # mask out the DC region so we track the diffracted order
            yy, xx = np.mgrid[0:H, 0:W]
            rr = np.hypot(xx - cx0, yy - cy0)
            g[rr < dead_radius] = 0.0
            y, x = np.unravel_index(np.argmax(g), g.shape)
            return float(x), float(y)

        def write_pure_carrier_and_measure(Cx=200.0, Cy=0.0):
            """Write ONLY a carrier (plus correction), then report first-order centroid."""
            import numpy as np, cv2, time
            # build carrier phase locally (no GS, no steering)
            yy, xx = np.mgrid[0:H, 0:W]
            base = np.zeros((H, W), np.float32)
            ph = np.mod(base - 2 * np.pi * (Cx * (xx / float(W)) + Cy * (yy / float(H))), 2 * np.pi)
            save_phase_with_correction(ph, corr_u8, OUT_BMP)
            time.sleep(0.3)  # give SLM app time to reload
            snap = self.SaveProcessedImage()
            img = cv2.imread(snap, cv2.IMREAD_GRAYSCALE)
            if img is None:
                print("[Carrier test] no image");
                return
            if img.shape[0] > 40:
                img = img[:-40, :]  # crop overlay
            img = cv2.resize(img.astype(np.float32) / max(1.0, float(img.max())), (W, H))
            c1x, c1y = centroid_first_order(img, dead_radius=120)
            print(f"[Carrier test] first-order centroid=({c1x:.1f},{c1y:.1f})")

        write_pure_carrier_and_measure(Cx=250.0, Cy=0.0)

        mode = getattr(self, "target_mode", "gaussian")
        if mode in ("gaussian", "soft_disk", "two_spots", "three_spots"):
            target_amp = self._build_synth_target(W, H, mode)
        else:
            if not os.path.exists(TARGET_BMP):
                print(f"❌ Desired image not found: {TARGET_BMP}")
                return
            target_amp = preprocess_target_to_panel(TARGET_BMP, (W, H), x_shift=0, y_shift=0, rot_deg=0.0)

        # (Optional) write a quick preview
        try:
            cv2.imwrite(r"C:\WC\HotSystem\Utils\Desired_target_preview.png",
                        (target_amp * 255).astype(np.uint8))
        except Exception:
            pass
        target = target_amp  # already apodized & centered per config

        pk = _count_peaks(target)
        print(f"[Target] peak count guess = {pk}")

        def make_two_spot_support(target_amp, frac=0.55):
            # keep the brightest ~45% inside each spot as the “forced” region
            # (works well for soft Gaussians)
            g = cv2.GaussianBlur(target_amp, (0, 0), 1.0)
            thr = frac * g.max()
            S = (g >= thr).astype(np.float32)
            return S

        S = make_two_spot_support(target_amp)  # same size as panel

        def mraf_update(phase_slm, target_amp, S, steps=30, alpha=0.8, phi_carrier=None):
            """
            Mixed-Region Amplitude Freedom:
              - inside S:  amplitude -> alpha*target + (1-alpha)*current
              - outside S: amplitude -> current  (free)
            """
            if phi_carrier is None:
                phi_carrier = 0.0
            for _ in range(steps):
                field_s = np.exp(1j * (phase_slm + phi_carrier))
                field_f = np.fft.fftshift(np.fft.fft2(field_s))
                amp = np.abs(field_f)
                phase = np.angle(field_f)

                amp_new = amp.copy()
                amp_new[S > 0] = (1 - alpha) * amp[S > 0] + alpha * target_amp[S > 0]

                field_f_new = amp_new * np.exp(1j * phase)
                field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))

                # remove carrier to keep 'phase_slm' as residual being optimized
                phase_slm = np.angle(field_s_back * np.exp(-1j * phi_carrier)).astype(np.float32)
            return np.mod(phase_slm, 2 * np.pi)

        # --------------- Initialize phase & calibrate ---------------
        rng = np.random.default_rng(1)
        phase_slm = rng.uniform(0, 2 * np.pi, size=(H, W)).astype(np.float32)

        # ---- calibration: reuse if available ----
        cal = load_calib(CALIB_PATH, (W, H)) if not FORCE_RECAL else None
        if cal is None:
            sx, sy = calibrate_steering(phase_slm, corr_u8, OUT_BMP, W, H,
                                        probe_px=40.0, settle_s=0.3, timeout_s=6.0)
            if abs(sx) < 1e-3 or abs(sy) < 1e-3:
                print("[Calib] WARNING: near-zero response; using gain floors to proceed.")
            save_calib(CALIB_PATH, (W, H), sx, sy)
        else:
            sx, sy = cal

        # One test frame with ONLY carrier, zero steer
        save_phase_with_correction(phase_slm, corr_u8, OUT_BMP, carrier_cmd=CARRIER_CMD, steer_cmd=(0.0, 0.0),
                                   settle_s=SETTLE_S)
        p_test = self.SaveProcessedImage()
        img = cv2.imread(p_test, 0)
        if img is not None and img.shape[0] > 40: img = img[:-40, :]
        img = cv2.resize(img.astype(np.float32) / max(1, img.max()), (W, H))
        cx_car, cy_car = brightest_centroid(img)
        print(f"[Carrier test] centroid=({cx_car:.1f},{cy_car:.1f})  (should be far from center if carrier works)")

        # after getting sx, sy
        def _sanity_probe(sign='x', mag=12.0):
            yy, xx = np.mgrid[0:H, 0:W]
            if sign == 'x':
                ramp = -2 * np.pi * ((mag) * (xx / W))
            else:
                ramp = -2 * np.pi * ((mag) * (yy / H))
            ph = np.mod(phase_slm + ramp.astype(np.float32), 2 * np.pi)
            save_phase_with_correction(ph, corr_u8, OUT_BMP)
            time.sleep(0.45)
            p = self.SaveProcessedImage()
            img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
            img = img[:-40, :] if img is not None and img.shape[0] > 40 else img
            img = cv2.resize(img.astype(np.float32) / max(img.max(), 1), (W, H))
            cx1, cy1 = brightest_centroid(img)
            return cx1, cy1

        # baseline centroid
        p0 = self.SaveProcessedImage()
        m0 = cv2.resize(cv2.imread(p0, 0)[:-40, :], (W, H)) if p0 else None
        cx0, cy0 = brightest_centroid((m0.astype(np.float32) / max(m0.max(), 1)))

        # X probe
        cx1, cy1 = _sanity_probe('x', +12.0)
        print(f"[Sanity] +X command moved centroid Δx={cx1 - cx0:+.2f} px (Δy={cy1 - cy0:+.2f})")

        # Y probe
        cx2, cy2 = _sanity_probe('y', +12.0)
        print(f"[Sanity] +Y command moved centroid Δy={cy2 - cy0:+.2f} px (Δx={cx2 - cx0:+.2f})")

        # MSE history
        self._mse_hist = []
        steer_cmd = (0.0, 0.0)
        Cx, Cy = CARRIER_CMD

        # build once (panel coords)
        yy, xx = np.mgrid[0:H, 0:W]
        phi_carrier = -2 * np.pi * (Cx * (xx / W) + Cy * (yy / H)).astype(np.float32)

        # --------------- Iteration loop ---------------
        for outer in range(1, OUTER_ITERS + 1):
            if getattr(self, "_iter_stop", False):
                print("Iterations stopped by user.")
                break

            # 1) Write SLM pattern with correction
            save_phase_with_correction(
                phase_core_rad=phase_slm,
                corr_map=corr_u8,
                out_path=OUT_BMP,
                carrier_cmd=CARRIER_CMD,
                steer_cmd=steer_cmd,
                settle_s=SETTLE_S
            )
            print(f"[{outer}/{OUTER_ITERS}] wrote SLM BMP → {OUT_BMP}")
            time.sleep(0.25)  # let optics/SLM settle

            # 2) Trigger Zelux save
            try:
                snap_path = self.SaveProcessedImage()
                print(f"   Zelux saved: {snap_path}")
            except Exception as e:
                print(f"   ❌ SaveProcessedImage failed: {e}")
                break

            # 3) Read, crop overlay, normalize, resize to panel
            meas8 = cv2.imread(snap_path, cv2.IMREAD_GRAYSCALE)
            if meas8 is None:
                print("   ⚠️ Could not read snapshot; skipping round")
                continue
            if meas8.shape[0] > 40:
                meas8 = meas8[:-40, :]  # crop bottom overlay before resizing
            meas = meas8.astype(np.float32)
            if meas.max() > 0: meas /= meas.max()
            # saturation check (normalized image)
            sat = float((meas >= 0.98).mean())
            if sat > 0.003:
                print("   ⚠️ Bright core clipped; reduce exposure/power")
            # resize ONCE to panel geometry
            meas_p = cv2.resize(meas, (W, H), interpolation=cv2.INTER_AREA)

            # 4) ROI MSE (energy-normalized, light blur)

            roi = cv2.dilate(S, np.ones((21, 21), np.uint8))
            mr = cv2.GaussianBlur(meas_p, (0, 0), 1.0) * roi
            tr = cv2.GaussianBlur(target, (0, 0), 1.0) * roi
            mr /= (mr.sum() + 1e-8);  tr /= (tr.sum() + 1e-8)
            mse = float(np.mean((mr - tr) ** 2))

            l1 = float(np.mean(np.abs(mr - tr)))
            # guard PSNR for zero error
            psnr = (float('inf') if mse <= 1e-20 else -10.0 * np.log10(mse))
            # NCC (cosine similarity of vectorized ROIs)
            num = float(np.sum(mr * tr))
            den = float(np.sqrt(np.sum(mr * mr) * np.sum(tr * tr)) + 1e-12)
            ncc = num / den

            # Keep your history (store MSE with high precision)
            self._mse_hist.append(mse)
            hist_str = ", ".join(f"{v:.3e}" for v in self._mse_hist)  # scientific notation
            print(f"   MSE history [{len(self._mse_hist)}]: {hist_str}")
            print(f"   metrics: MSE={mse:.3e}  L1={l1:.3e}  PSNR={psnr if np.isfinite(psnr) else 'inf'}  NCC={ncc:.6f}")

            # 5) Centroid (panel pixels) + steering
            meas_cx, meas_cy = brightest_centroid(meas_p)
            tx, ty = W / 2.0, H / 2.0
            ex, ey = (tx - meas_cx), (ty - meas_cy)

            # effective gains (clamped to avoid divide-by-zero)
            sx_eff = float(np.clip(sx, -0.45, -0.08) if sx < 0 else np.clip(sx, 0.08, 0.45))
            sy_eff = float(np.clip(sy, -0.45, -0.08) if sy < 0 else np.clip(sy, 0.08, 0.45))

            ux = Kp * (ex / sx_eff)  # ← sign handled by sx_eff
            uy = Kp * (ey / sy_eff)

            cmdx = SOFT_LIM * np.tanh(ux / SOFT_LIM)
            cmdy = SOFT_LIM * np.tanh(uy / SOFT_LIM)

            steer_cmd = (cmdx, cmdy)

            yy, xx = np.mgrid[0:H, 0:W]
            ramp = -2 * np.pi * (cmdx * (xx / W) + cmdy * (yy / H))  # same formula used during calibration
            phase_slm = np.mod(phase_slm + ramp.astype(np.float32), 2 * np.pi)

            print(f"   steer: err=({ex:+.2f},{ey:+.2f}) cmd=({cmdx:+.2f},{cmdy:+.2f}) (sx={sx:.3f}, sy={sy:.3f})")

            # 7) Inner GS update toward the desired amplitude
            # if INNER_GS > 0:
            #     phase_slm = gs_update_relaxed(phase_slm, target_amp=target, steps=INNER_GS, beta=BETA_GS, phi_carrier= phi_carrier)

            phase_slm = mraf_update(
                phase_slm, target_amp=target, S=S,
                steps=INNER_GS, alpha=0.85, phi_carrier=phi_carrier
            )

        # Final write
        save_phase_with_correction(
            phase_core_rad=phase_slm,
            corr_map=corr_u8,
            out_path=OUT_BMP,
            carrier_cmd=CARRIER_CMD,
            steer_cmd=steer_cmd,
            settle_s=SETTLE_S
        )
        print("Iteration loop finished.")

    def StartAutoSym(self, sender=None, app_data=None, user_data=None):
        if getattr(self, "_autosym_th", None) and self._autosym_th.is_alive():
            print("AutoSym already running.");  return
        self._autosym_stop = False
        import threading
        self._autosym_th = threading.Thread(target=self._AutoSymWorker, daemon=True)
        self._autosym_th.start()
        print("Started AutoSym thread.")

    def _principal_moments_roundness(self, g01, roi_px=220, dead_radius=120, prefer_center=None):
        """
        Compute |σ1/σ2 - 1| from principal moments (rotation-invariant).
        - Masks the DC (dead_radius around image center).
        - If prefer_center=(cx,cy) is given, prioritizes a blob near that location.
        Returns: E, (sx1, sx2), (cx, cy)
        """
        import numpy as np, cv2
        H, W = g01.shape
        g = cv2.GaussianBlur(g01.astype(np.float32), (0, 0), 1.6)

        # mask DC (zero-order) so we only consider diffracted orders
        yy, xx = np.mgrid[0:H, 0:W]
        cx0, cy0 = W / 2.0, H / 2.0
        if dead_radius > 0:
            dc_mask = ((xx - cx0) ** 2 + (yy - cy0) ** 2) < (dead_radius ** 2)
            g = g.copy()
            g[dc_mask] = 0.0

        # adaptive threshold & connected components
        thr = np.quantile(g, 0.85)
        m = (g >= thr).astype(np.uint8)
        num, labels = cv2.connectedComponents(m)
        if num <= 1:
            # fallback: use global centroid but still mask DC
            y, x = np.unravel_index(np.argmax(g), g.shape)
            cx, cy = float(x), float(y)
        else:
            # pick blob closest to prefer_center if given; otherwise largest area
            if prefer_center is not None:
                px, py = prefer_center
                best_i, best_d2 = None, 1e18
                for i in range(1, num):
                    ys, xs = np.where(labels == i)
                    if xs.size == 0: continue
                    cx_i = xs.mean();
                    cy_i = ys.mean()
                    d2 = (cx_i - px) ** 2 + (cy_i - py) ** 2
                    if d2 < best_d2:
                        best_d2, best_i = d2, i
                labels_keep = (labels == best_i).astype(np.float32)
            else:
                areas = [(labels == i).sum() for i in range(1, num)]
                best_i = 1 + int(np.argmax(areas))
                labels_keep = (labels == best_i).astype(np.float32)
            s = labels_keep.sum() + 1e-8
            cy = float((yy * labels_keep).sum() / s);
            cx = float((xx * labels_keep).sum() / s)

        # crop ROI around that centroid
        x0 = int(max(0, cx - roi_px // 2));
        x1 = int(min(W, cx + roi_px // 2))
        y0 = int(max(0, cy - roi_px // 2));
        y1 = int(min(H, cy + roi_px // 2))
        patch = g[y0:y1, x0:x1]
        H2, W2 = patch.shape
        if H2 < 5 or W2 < 5:
            return 1.0, (50.0, 50.0), (cx, cy)  # clearly bad

        yy2, xx2 = np.mgrid[0:H2, 0:W2]
        w = patch / (patch.sum() + 1e-8)
        mx = float((xx2 * w).sum());
        my = float((yy2 * w).sum())
        xz = (xx2 - mx);
        yz = (yy2 - my)
        cov_xx = float(((xz * xz) * w).sum())
        cov_yy = float(((yz * yz) * w).sum())
        cov_xy = float(((xz * yz) * w).sum())
        # eigenvalues of covariance => principal variances
        tr = cov_xx + cov_yy
        det = cov_xx * cov_yy - cov_xy * cov_xy
        lam1 = 0.5 * (tr + np.sqrt(max(tr * tr - 4.0 * det, 0.0)))
        lam2 = 0.5 * (tr - np.sqrt(max(tr * tr - 4.0 * det, 0.0)))
        s1 = float(np.sqrt(max(lam1, 1e-12)))
        s2 = float(np.sqrt(max(lam2, 1e-12)))
        E = abs(s1 / (s2 + 1e-9) - 1.0)
        return E, (s1, s2), (cx, cy)

    def _roundness_with_wedge(self, g01, center_hint, roi_px=240,
                              dead_radius=140, rmin=120, rmax=9999,
                              wedge_deg=30.0, wedge_dir_deg=0.0):
        """
        Rotation-invariant roundness in a sector annulus aimed at the first order.
        Returns: E, (s1,s2), (cx,cy)
        """
        import numpy as np, cv2
        H, W = g01.shape
        g = cv2.GaussianBlur(g01.astype(np.float32), (0, 0), 1.8)

        yy, xx = np.mgrid[0:H, 0:W]
        cx0, cy0 = W / 2.0, H / 2.0
        rr = np.hypot(xx - cx0, yy - cy0)
        ang = np.degrees(np.arctan2(yy - cy0, xx - cx0))  # 0° to the right, +CCW

        # annulus + dead zone
        mask = (rr >= max(dead_radius, rmin)) & (rr <= rmax)

        # wedge around wedge_dir_deg
        da = ((ang - wedge_dir_deg + 180.0) % 360.0) - 180.0
        mask &= (np.abs(da) <= (wedge_deg / 2.0))

        work = g * mask.astype(np.float32)

        # take centroid in that mask
        s = work.sum() + 1e-8
        cy = float((yy * work).sum() / s);
        cx = float((xx * work).sum() / s)

        # crop ROI around that centroid
        x0 = int(max(0, cx - roi_px // 2));
        x1 = int(min(W, cx + roi_px // 2))
        y0 = int(max(0, cy - roi_px // 2));
        y1 = int(min(H, cy + roi_px // 2))
        patch = work[y0:y1, x0:x1]
        H2, W2 = patch.shape
        if H2 < 8 or W2 < 8 or patch.max() <= 0:
            return None, (0.0, 0.0), (cx, cy)

        yy2, xx2 = np.mgrid[0:H2, 0:W2]
        w = patch / (patch.sum() + 1e-8)
        mx = float((xx2 * w).sum());
        my = float((yy2 * w).sum())
        xz = xx2 - mx;
        yz = yy2 - my
        cxx = float((xz * xz * w).sum());
        cyy = float((yz * yz * w).sum());
        cxy = float((xz * yz * w).sum())
        tr = cxx + cyy;
        det = cxx * cyy - cxy * cxy
        lam1 = 0.5 * (tr + np.sqrt(max(tr * tr - 4 * det, 0.0)));
        lam2 = max(1e-12, 0.5 * (tr - np.sqrt(max(tr * tr - 4 * det, 0.0))))
        s1 = float(np.sqrt(lam1));
        s2 = float(np.sqrt(lam2))
        E = abs(s1 / (s2 + 1e-9) - 1.0)
        return E, (s1, s2), (cx, cy)

    def _astig_mode(self, Z, theta_rad):
        """Unit-RMS astig at angle theta: cosθ*Z2m2 + sinθ*Z22 (already RMS-normalized Z’s)."""
        return np.cos(theta_rad) * Z['Z2m2'] + np.sin(theta_rad) * Z['Z22']

    def StopAutoSym(self, sender=None, app_data=None, user_data=None):
        self._request_stop_and_join()
        print("Stopping AutoSym...")

    # In ZeluxGUI (the owner of _AutoSymWorker / _FlatTopWorker)
    def _request_stop_and_join(self, join_timeout=2.0):
        # Set *both* flags so any worker respects it
        setattr(self, "_autosym_stop", True)
        setattr(self, "_flattop_stop", True)

        # If you store the thread on the parent (as shown earlier):
        t = getattr(self, "_autosym_thread", None)
        if t and t.is_alive():
            t.join(timeout=join_timeout)
            if t.is_alive():
                print("Stop requested; worker will exit after its current step…")
            else:
                print("Worker stopped.")
        else:
            print("Stop flag set.")

    def _AutoSymWorker(self):
        """
        Minimize ellipticity on the **true 1st diffraction order** (not the DC).
        Uses polar astigmatism (amplitude + angle) and optionally coma.
        Locks the metric to the detected 1st order via a wedge/annulus ROI so the
        DC in the center and other lobes don't confuse the optimizer.

        Side effects:
          • Writes residual phase BMP to OUT_BMP with a carrier to push orders off DC.
          • Updates self.autosym_roi with the exact ROI parameters used by the metric,
            for the UI overlay in UpdateImage().
        """
        import time, cv2, numpy as np

        # --- paths / geometry ---
        CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
        OUT_BMP = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"

        # carrier to push orders away from DC (x, y) in grating periods across aperture
        CARRIER = tuple(getattr(self, "_autosym_carrier", (250.0, 0.0)))

        self.autosym_iter = 0
        self.autosym_debug_candidates = None
        self.autosym_roi = None

        corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr_u8 is None:
            print(f"❌ Cannot read correction BMP: {CORR_BMP}")
            return
        H, W = corr_u8.shape
        # Basic DC default = image center (override if you compute a refined DC)
        self.autosym_dc = {"x": float(W) * 0.5, "y": float(H) * 0.5, "W": float(W), "H": float(H)}

        # Zernike set (your helper)
        Z = self._zernike_minimal(W, H, aperture='circle')

        # --- parameterization (polar astig + optional coma) ---
        pars = dict(DEF=0.0, AST_A=0.0, AST_TH=0.0, COMA_X=0.0, COMA_Y=0.0)

        mode = getattr(self, "autosym_mode", "normal").lower()
        is_coarse = (mode == "coarse")
        print(f"[AutoSym] start (mode={'COARSE' if is_coarse else 'NORMAL'})")

        # scaling knobs for coarse
        M_STEP = 2.8 if is_coarse else 1.0  # much larger moves
        M_CSTOP = 0.14 if is_coarse else 0.06  # early stop target E
        MAX_IT = 14 if is_coarse else 80  # cap iterations
        ANNEAL = 0.35 if is_coarse else 0.60  # more aggressive shrink
        WEDGE_W = 1.4 if is_coarse else 1.0  # a bit wider wedge at start

        # step sizes (+ anneal floors)
        STEP_DEF, STEP_MIN_DEF = 0.30 * np.pi * M_STEP, 0.02 * np.pi
        STEP_A, STEP_MIN_A = 0.25 * np.pi * M_STEP, 0.02 * np.pi
        STEP_TH, STEP_MIN_TH = np.deg2rad(12.0 * M_STEP), np.deg2rad(2.0)
        STEP_C, STEP_MIN_C = 0.15 * np.pi * M_STEP, 0.03 * np.pi

        def compose(p):
            ph = (p['DEF'] * Z['Z20']).astype(np.float32)
            ph += (p['AST_A'] * self._astig_mode(Z, p['AST_TH'])).astype(np.float32)
            ph += (p['COMA_X'] * Z['Z3m1'] + p['COMA_Y'] * Z['Z31']).astype(np.float32)
            return np.mod(ph, 2 * np.pi)

        # --- emit "zero residual + carrier" and take a robust probe frame ---
        self._write_phase_with_corr(np.zeros_like(corr_u8, np.float32), corr_u8, OUT_BMP,
                                    carrier_cmd=CARRIER, steer_cmd=(0.0, 0.0), settle_s=0.35)
        time.sleep(0.35)

        def _grab_gray():
            """Return normalized grayscale (W×H) for metric (cropping any bottom bar)."""
            h = self.cam.camera.image_height_pixels
            w = self.cam.camera.image_width_pixels
            rgba = self.cam.lateset_image_buffer.reshape((h, w, 4))
            rgb = rgba[:, :, :3].astype(np.float32)
            if rgb.max() > 0: rgb /= max(1e-6, rgb.max())
            if rgb.shape[0] > 40:  # crop a possible Zelux status bar
                rgb = rgb[:-40, :, :]
            g = cv2.resize(rgb.mean(axis=2), (W, H), interpolation=cv2.INTER_AREA)
            return g

        # ---------- robust +1 selection with multi-term score ----------
        g_probe = _grab_gray()
        g_blur = cv2.GaussianBlur(g_probe, (0, 0), 1.0)
        g_norm = g_blur / max(1e-6, g_blur.max())

        Hc, Wc = H, W
        cx, cy = detect_dc_center(g_probe)  # ← use this, not W/2, H/2
        self.autosym_dc = {"x": cx, "y": cy, "W": float(W), "H": float(H)}

        # Exclude a generous DC disk
        Rdc = 0.1 * min(W, H)
        yy, xx = np.mgrid[0:H, 0:W]
        mask_outside_dc = ((xx - cx) ** 2 + (yy - cy) ** 2) > (Rdc * Rdc)

        vals = g_norm[mask_outside_dc]
        if vals.size == 0:
            print("[AutoSym] DC mask swallowed the frame; shrinking Rdc.")
            Rdc = 0.12 * min(W, H)
            mask_outside_dc = ((xx - cx) ** 2 + (yy - cy) ** 2) > (Rdc * Rdc)
            vals = g_norm[mask_outside_dc]

        vmax = float(vals.max()) if vals.size else 0.0
        p99 = float(np.percentile(vals, 99.0)) if vals.size else 0.0
        print(f"[AutoSym] outside-DC stats: vmax={vmax:.3f}, p99={p99:.3f}")

        # Try progressively lower thresholds until we get some pixels
        scales = [0.60, 0.45, 0.35, 0.25, 0.15]
        mask = None
        for s in scales:
            t = max(0.02, p99 * s)  # allow very faint signals
            cand = (g_norm >= t) & mask_outside_dc
            npx = int(cand.sum())
            print(f"[AutoSym] thresh try: t={t:.3f} → {npx} px")
            if npx >= 20:  # require a small blob of pixels, not specks
                mask = cand
                break

        # If still nothing, very weak image — pick the absolute max outside DC
        if mask is None or mask.sum() == 0:
            print("[AutoSym] no blobs after relaxed thresholds; falling back to global max outside DC.")
            prod = g_norm * mask_outside_dc.astype(g_norm.dtype)
            idx = int(np.argmax(prod))
            y0, x0 = divmod(idx, Wc)
            # Create a tiny 3x3 blob around the max so CC sees one component
            mask = np.zeros_like(g_norm, dtype=np.uint8)
            y0a, y0b = max(0, y0 - 1), min(H, y0 + 2)
            x0a, x0b = max(0, x0 - 1), min(W, x0 + 2)
            mask[y0a:y0b, x0a:x0b] = 1

        num, lab, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
        print(f"[AutoSym] connected components (including background) = {num}")

        cands = []
        for i in range(1, num):
            area = stats[i, cv2.CC_STAT_AREA]
            if area < 10:
                continue
            x, y = float(cents[i][0]), float(cents[i][1])  # centroids
            r = float(np.hypot(x - cx, y - cy))
            ang = float(np.arctan2(y - cy, x - cx))  # radians
            s = float((g_norm * (lab == i)).sum())  # brightness proxy (sum)
            cands.append({"x": x, "y": y, "r": r, "ang": ang, "sum": s, "area": float(area)})

        if not cands:
            # fallback: brightest pixel outside DC
            idx = int(np.argmax(g_norm * mask_outside_dc))
            y0, x0 = divmod(idx, Wc)
            c1x, c1y = float(x0), float(y0)
            r_near = float(np.hypot(x0 - cx, y0 - cy))
            cands = [{"x": c1x, "y": c1y, "r": r_near, "ang": float(np.arctan2(c1y - cy, c1x - cx)),
                      "sum": float(g_norm[int(c1y), int(c1x)]), "area": 1.0}]
        else:
            # >>> EXPECTED SIDE <<<
            # If your +1 order is on the LEFT of DC (as you said), lock to π radians:
            # expected_angle = np.pi
            # If you want this auto from CARRIER, use:
            expected_angle = 0.0 if CARRIER[0] >= 0 else np.pi

            r_vals = np.array([c["r"] for c in cands])
            s_vals = np.array([c["sum"] for c in cands])
            med_r = float(np.median(r_vals[s_vals >= np.median(s_vals)])) if len(cands) > 2 else float(
                np.median(r_vals))

            # weights
            w_ang, w_rad, w_y, w_brt = 3.0, 2.0, 1.5, 1.0

            def score(c):
                # angle closeness: 1 at expected_angle, 0 opposite
                ang_diff = abs(((c["ang"] - expected_angle + np.pi) % (2 * np.pi)) - np.pi)
                s_ang = 1.0 - (ang_diff / np.pi)

                # radius closeness: Gaussian around med_r (30% band)
                s_rad = np.exp(-((c["r"] - med_r) / max(1.0, 0.30 * med_r)) ** 2)

                # same-row preference: Gaussian with 10% of height
                s_y = np.exp(-((c["y"] - cy) / (0.10 * H + 1e-6)) ** 2)

                # brightness normalized
                s_brt = c["sum"] / (s_vals.max() + 1e-6)
                return w_ang * s_ang + w_rad * s_rad + w_y * s_y + w_brt * s_brt

            best_idx = int(np.argmax([score(c) for c in cands]))
            best = cands[best_idx]
            c1x, c1y = float(best["x"]), float(best["y"])
            r_near = float(best["r"])

        first_order_hint = (float(c1x), float(c1y))

        # Save all candidates (image-space) for overlay
        vis_r = 0.025 * min(W, H)  # cosmetic circle radius for drawing
        scores = [0.0] * len(cands)
        try:
            scores = [score(c) for c in cands]
        except NameError:
            pass  # when we took the fallback path (no scoring function)

        # mark chosen index (if scoring existed)
        chosen_idx = int(np.argmax(scores)) if len(scores) == len(cands) else 0

        # Save ALL candidates for the overlay, with brightness/area/score and chosen flag
        vis_r = 0.025 * min(W, H)
        self.autosym_debug_candidates = []
        for i, c in enumerate(cands):
            self.autosym_debug_candidates.append({
                "x": float(c["x"]), "y": float(c["y"]),
                "r": float(vis_r),
                "sum": float(c["sum"]),
                "area": float(c["area"]),
                "score": float(scores[i]),
                "chosen": bool(i == best_idx),
            })

        # Lock wedge direction from DC→+1
        DIR_LOCK_DEG = float(np.degrees(np.arctan2(c1y - cy, c1x - cx)))

        # Radial gates (keep around the chosen ring)
        WEDGE_DEG = 36.0
        WEDGE_DEG = float(WEDGE_DEG) * WEDGE_W

        RMIN = int(max(20, 0.65 * r_near))
        RMAX = int(min(0.95 * (min(W, H) / 2), 1.35 * r_near))
        DEAD_RADIUS = int(max(18, 0.50 * r_near))
        ROI_PX = int(min(min(W, H), 1.50 * r_near))

        first_order_hint = (c1x, c1y)

        def measure_E(update_roi = True):
            g = _grab_gray()
            E, (s1, s2), (cx, cy) = self._roundness_with_wedge(
                g,
                center_hint=first_order_hint,
                roi_px=ROI_PX,
                dead_radius=DEAD_RADIUS,
                rmin=RMIN, rmax=RMAX,
                wedge_deg=WEDGE_DEG,
                wedge_dir_deg=DIR_LOCK_DEG,
            )
            if (E is None) or not np.isfinite(E) or (max(s1, s2) > 120.0):
                return None, s1, s2

            # for the UI overlay (in the same W×H space)
            if update_roi:
                self.autosym_roi = {
                    "cx": float(cx), "cy": float(cy),
                    "rmin": float(RMIN), "rmax": float(RMAX),
                    "wedge_deg": float(WEDGE_DEG),
                    "dir_deg": float(DIR_LOCK_DEG),
                    "roi_px": float(ROI_PX),
                    "dead_radius": float(DEAD_RADIUS),
                    "W": float(W), "H": float(H),
                }
            return E, s1, s2

        # --- initialize: write neutral residual (with carrier); get baseline E ---
        self._write_phase_with_corr(compose(pars), corr_u8, OUT_BMP,
                                    carrier_cmd=CARRIER, steer_cmd=(0.0, 0.0))
        time.sleep(0.40)

        bestE, s1, s2 = measure_E()
        if bestE is None:
            # widen once and retry using r_near
            WEDGE_DEG = min(40.0, WEDGE_DEG * 1.6)
            RMIN = max(20, int(0.35 * r_near))
            RMAX = min(int(0.98 * min(W, H)), int(1.6 * r_near))
            ROI_PX = min(int(1.8 * r_near), int(min(W, H)))
            DEAD_RADIUS = max(20, int(0.30 * r_near))
            bestE, s1, s2 = measure_E()

        if bestE is None:
            print("[AutoSym] init metric invalid even after widening; check camera image / wedge.")
            return

        best = pars.copy()
        print(f"[AutoSym] init: E={bestE:.4f}  σ1={s1:.2f}  σ2={s2:.2f}")

        stable = 0

        # in coarse mode, don’t enable coma unless things are really not round:
        use_coma = False
        if (not use_coma) and (STEP_A <= STEP_MIN_A * 1.1) and (STEP_TH <= STEP_MIN_TH * 1.1) and (
                bestE > (0.30 if is_coarse else 0.20)
        ):
            use_coma = True
            print("[AutoSym] enabling coma tuning...")

        # ---------------- main loop ----------------
        for it in range(1, MAX_IT + 1):
            self.autosym_iter = it  # keep UI in sync
            update_roi = True
            if it >= 2:
                # stop drawing the candidate circles after the 2nd iter
                self.autosym_debug_candidates = None
                self.autosym_roi = None
                update_roi = False

            if getattr(self, "_autosym_stop", False):
                break

            # candidate moves for this sweep
            moves = [
                ('DEF', +STEP_DEF), ('DEF', -STEP_DEF),
                ('AST_A', +STEP_A), ('AST_A', -STEP_A),
                ('AST_TH', +STEP_TH), ('AST_TH', -STEP_TH),
            ]
            if use_coma:
                moves += [
                    ('COMA_X', +STEP_C), ('COMA_X', -STEP_C),
                    ('COMA_Y', +STEP_C), ('COMA_Y', -STEP_C),
                ]

            improved = False
            for name, delta in moves:
                trial = best.copy()
                trial[name] += float(delta)
                if name == 'AST_TH':
                    # wrap angle to [-π, π] so it doesn't drift
                    trial['AST_TH'] = ((trial['AST_TH'] + np.pi) % (2 * np.pi)) - np.pi

                self._write_phase_with_corr(compose(trial), corr_u8, OUT_BMP,
                                            carrier_cmd=CARRIER, steer_cmd=(0.0, 0.0),
                                            settle_s=0.30)
                time.sleep(0.12)

                E, s1, s2 = measure_E(update_roi=update_roi)
                if E is None:
                    # bad measurement → shrink that step a bit and skip
                    if name == 'DEF':
                        STEP_DEF = max(STEP_DEF * 0.6, STEP_MIN_DEF)
                    elif name == 'AST_A':
                        STEP_A = max(STEP_A * 0.6, STEP_MIN_A)
                    elif name == 'AST_TH':
                        STEP_TH = max(STEP_TH * 0.6, STEP_MIN_TH)
                    elif name in ('COMA_X', 'COMA_Y'):
                        STEP_C = max(STEP_C * 0.6, STEP_MIN_C)
                    continue

                print(f"[AutoSym] it={it:02d} {name}{'+' if delta > 0 else '-'}: "
                      f"E={E:.4f} (sigma1={s1:.2f}, sigma2={s2:.2f})")

                if E < bestE:
                    bestE, best = E, trial
                    improved = True

            if not improved:
                STEP_DEF = max(STEP_DEF * ANNEAL, STEP_MIN_DEF)
                STEP_A = max(STEP_A * ANNEAL, STEP_MIN_A)
                STEP_TH = max(STEP_TH * ANNEAL, STEP_MIN_TH)
                if use_coma:
                    STEP_C = max(STEP_C * ANNEAL, STEP_MIN_C)

                msg = (f"[AutoSym] anneal → DEF={STEP_DEF / np.pi:.3f}π  "
                       f"A={STEP_A / np.pi:.3f}π  TH={np.degrees(STEP_TH):.1f}°")
                if use_coma:
                    msg += f"  C={STEP_C / np.pi:.3f}π"
                msg += f" ; best E={bestE:.4f}"
                print(msg)

                # unlock coma only after astig/angle steps are small AND E not good enough
                if (not use_coma) and (STEP_A <= STEP_MIN_A * 1.1) and (STEP_TH <= STEP_MIN_TH * 1.1) and (
                        bestE > 0.20):
                    use_coma = True
                    print("[AutoSym] enabling coma tuning...")

                # after printing anneal msg or after a successful improvement:
                stable += (bestE < M_CSTOP)
                if is_coarse and (bestE < M_CSTOP):
                    print(f"[AutoSym] coarse stop: E={bestE:.4f} < {M_CSTOP:.3f}")
                    break
                if not is_coarse and stable >= 3:
                    print(f"[AutoSym] stopping: stable and round (E={bestE:.4f}).")
                    break

            else:
                stable = 0

            # write current best so GUI shows progress
            self._write_phase_with_corr(compose(best), corr_u8, OUT_BMP,
                                        carrier_cmd=CARRIER, steer_cmd=(0.0, 0.0))

        # --- final write ---
        self._write_phase_with_corr(compose(best), corr_u8, OUT_BMP,
                                    carrier_cmd=CARRIER, steer_cmd=(0.0, 0.0))
        print(f"[AutoSym] done. best E={bestE:.4f}")

    def _FlatTopWorker(self):
        """
        Camera-in-the-loop flat-top generator.
        Iterates GS and updates the SLM until the measured +1 order spot is uniform
        (low CV in a circular ROI), then stops.

        Reads parameters from self._flattop_params set by handle_sym():
          - rfrac, edge, init, more, cv_thr, maxit, seed
        """
        import time, cv2, numpy as np

        # --- paths / geometry (same as AutoSym) ---
        CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
        OUT_BMP = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"
        # carrier to push orders away from DC (x, y) in grating periods across aperture
        CARRIER = tuple(getattr(self, "_autosym_carrier", (250.0, 0.0)))

        # ---- parameters from handle_sym() ----
        params = getattr(self, "_flattop_params", {})
        R_frac = float(params.get("rfrac", 0.22))
        roll_frac = float(params.get("edge", 0.06))
        profile = params.get("profile", "supergauss")
        order_m = int(params.get("m", 6))
        init_steps = int(params.get("init", 80))
        more_steps = int(params.get("more", 15))
        cv_thr = float(params.get("cv_thr", 0.10))
        maxit = int(params.get("maxit", 40))
        seed = params.get("seed", 1)
        open_loop = bool(params.get("open_loop", False))
        zero_carrier = bool(params.get("zero_carrier", False))

        EFFECTIVE_CARRIER = (0.0, 0.0) if zero_carrier else CARRIER

        # helpers
        def make_flattop_target(
                W, H,
                R_frac=0.32,
                roll_frac=0.10,
                profile="supergauss",  # "supergauss" | "raisedcos" | "gauss" | "hard"
                m=6,  # super-Gaussian order (4–8 typical)
                center=None,
                normalize=True
        ):
            """
            Return a W×H float32 target amplitude in [0,1] for a flat-top disk.

            R_frac   : disk radius as fraction of min(W,H)
            roll_frac: edge roll width as fraction of R (0 → hard edge)
            profile  : edge roll profile
                       - "supergauss": exp( -| (r-R)/w |^m )   (default)
                       - "raisedcos" : cosine ramp over width w (Tukey-like)
                       - "gauss"     : Gaussian roll about R with width w
                       - "hard"      : hard edge (Heaviside)
            m        : super-Gaussian order when profile="supergauss"
            normalize: if True, renormalize to [0,1]
            """
            import numpy as np

            yy, xx = np.mgrid[0:H, 0:W]
            if center is None:
                cx, cy = W / 2.0, H / 2.0
            else:
                cx, cy = map(float, center)

            r = np.hypot(xx - cx, yy - cy).astype(np.float32)

            R = float(R_frac) * float(min(W, H))
            R = max(1.0, R)  # guard
            w = float(roll_frac) * R
            w = max(1e-6, w)  # avoid div-by-zero in soft profiles

            # Start as a hard top-hat (1 inside R, 0 outside)
            tgt = (r <= R).astype(np.float32)

            prof = (profile or "supergauss").lower()

            if prof == "hard" or roll_frac <= 0:
                edge = (r <= R).astype(np.float32)

            elif prof in ("supergauss", "super-gauss", "sgauss", "sg"):
                # normalized distance through the rim
                d = (r - R) / w
                edge = np.exp(-(np.abs(d) ** float(m))).astype(np.float32)
                # clip so inside is ≈1, outside fades smoothly
                edge = np.clip(edge, 0.0, 1.0)

            elif prof in ("raisedcos", "cos", "tukey"):
                # cosine ramp: 1 for r<=R, then 0.5(1+cos(pi*(r-R)/w)) until R+w, then 0
                edge = np.zeros_like(r, dtype=np.float32)
                inside = (r <= R)
                ramp = (r > R) & (r < (R + w))
                edge[inside] = 1.0
                edge[ramp] = 0.5 * (1.0 + np.cos(np.pi * (r[ramp] - R) / w))

            elif prof in ("gauss", "gaussian"):
                # Gaussian roll centered at R with width ~ w
                d = (r - R) / (w / np.sqrt(2.0))
                edge = np.exp(-(d ** 2)).astype(np.float32)
                edge[r <= R] = 1.0
                edge[r >= (R + 3 * w)] = 0.0  # practical cutoff

            else:
                # fallback to super-Gaussian
                d = (r - R) / w
                edge = np.exp(-(np.abs(d) ** float(m))).astype(np.float32)
                edge = np.clip(edge, 0.0, 1.0)

            # Prefer the smooth edge outside and hard 1.0 inside
            tgt = np.maximum(tgt, edge).astype(np.float32)

            if normalize:
                mn, mx = float(tgt.min()), float(tgt.max())
                if mx > mn:
                    tgt = (tgt - mn) / (mx - mn + 1e-8)

            return tgt.astype(np.float32)

        def gs_farfield(target_amp, steps, phase_init=None, rng_seed=1):
            Ht, Wt = target_amp.shape
            if phase_init is None:
                rng = np.random.default_rng(rng_seed)
                phase = rng.uniform(0, 2 * np.pi, size=(Ht, Wt)).astype(np.float32)
            else:
                phase = phase_init.copy()
            for _ in range(steps):
                field_s = np.exp(1j * phase)  # unit amp @ SLM
                field_f = np.fft.fftshift(np.fft.fft2(field_s))
                phase_f = np.angle(field_f)
                field_f_new = target_amp * np.exp(1j * phase_f)
                field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))
                phase = np.angle(field_s_back).astype(np.float32)
            return np.mod(phase, 2 * np.pi)

        def grab_gray_to_panel(W, H):
            h = self.cam.camera.image_height_pixels
            w = self.cam.camera.image_width_pixels
            rgba = self.cam.lateset_image_buffer.reshape((h, w, 4))
            rgb = rgba[:, :, :3].astype(np.float32)
            if rgb.max() > 0: rgb /= max(1e-6, rgb.max())
            if rgb.shape[0] > 40:
                rgb = rgb[:-40, :, :]
            g = cv2.resize(rgb.mean(axis=2), (W, H), interpolation=cv2.INTER_AREA)
            return g

        def detect_plus_one(g):
            """
            Return centroid (x,y) of the nearest bright blob to the image center
            (DC is allowed). Also return its radius from the center.
            """
            import numpy as np, cv2

            Hc, Wc = g.shape
            cx, cy = Wc / 2.0, Hc / 2.0

            # (Optional) keep showing the detected DC for the UI cross, but don't exclude it
            try:
                dcx, dcy = detect_dc_center(g, guess=(cx, cy), win_frac=0.30)
            except Exception:
                dcx, dcy = cx, cy
            self.autosym_dc = {"x": float(dcx), "y": float(dcy), "W": float(Wc), "H": float(Hc)}

            # Smooth & normalize
            gb = cv2.GaussianBlur(g, (0, 0), 1.0)
            gn = gb / max(1e-6, gb.max())

            # Global stats (no DC mask)
            vals = gn.ravel()
            if vals.size == 0:
                return None
            p99 = float(np.percentile(vals, 99.0))

            # Build a thresholded mask (progressively relaxed) over the WHOLE frame
            for s in (0.60, 0.45, 0.30, 0.20):
                t = max(0.02, p99 * s)
                m = (gn >= t)
                if int(m.sum()) >= 20:
                    num, lab, stats, cents = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
                    if num > 1:
                        cands = []
                        for i in range(1, num):
                            area = stats[i, cv2.CC_STAT_AREA]
                            if area < 10:
                                continue
                            x, y = float(cents[i][0]), float(cents[i][1])
                            r = float(np.hypot(x - cx, y - cy))
                            cands.append((r, x, y))
                        if cands:
                            cands.sort(key=lambda t3: t3[0])  # nearest bright blob (could be DC)
                            r_near, x1, y1 = cands[0]
                            return (x1, y1, r_near)

            # Fallback: absolute global max (anywhere, including DC)
            idx = int(np.argmax(gn))
            y0, x0 = divmod(idx, Wc)
            r0 = float(np.hypot(x0 - cx, y0 - cy))
            return (float(x0), float(y0), r0)

        def roi_cv(g, cx, cy, radius):
            """Coefficient of variation inside a circle centered at (cx,cy) with radius."""
            Hc, Wc = g.shape
            yy, xx = np.mgrid[0:Hc, 0:Wc]
            rr = np.hypot(xx - cx, yy - cy)
            mask = rr <= radius
            vals = g[mask]
            if vals.size < 50:
                return None
            m = float(vals.mean())
            s = float(vals.std())
            return (s / (m + 1e-9), m, s, int(mask.sum()))

        # ---- init correction & target ----
        corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr_u8 is None:
            print(f"❌ FlatTop: cannot read correction BMP: {CORR_BMP}")
            return
        H, W = corr_u8.shape
        # Basic DC default = image center (override if you compute a refined DC)
        self.autosym_dc = {"x": float(W) * 0.5, "y": float(H) * 0.5, "W": float(W), "H": float(H)}

        target_amp = make_flattop_target(
            W, H,
            R_frac=R_frac,
            roll_frac=roll_frac,
            profile=profile,
            m=order_m,
            center=None,  # or (cx,cy) if you want to center on detected DC
            normalize=True
        )

        # ---- initial GS and display with carrier ----
        phase = gs_farfield(target_amp, steps=init_steps, phase_init=None, rng_seed=seed)

        if open_loop:
            # Do a single long GS run total = init + maxit*more (no camera in the loop)
            total_more = max(0, int(maxit)) * max(0, int(more_steps))
            if total_more > 0:
                phase = gs_farfield(target_amp, steps=total_more, phase_init=phase, rng_seed=None)

            self._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                        carrier_cmd=EFFECTIVE_CARRIER , steer_cmd=(0.0, 0.0), settle_s=0.0)
            print(f"[FlatTop OPEN-LOOP] wrote GS result (steps={init_steps}+{maxit}×{more_steps}).")

            if zero_carrier:
                import os, time, cv2, numpy as np
                ZERO_DIR = r"C:\WC\SLM_bmp\zero_carrier"
                os.makedirs(ZERO_DIR, exist_ok=True)
                ts = time.strftime("%Y%m%d_%H%M%S")
                Hh, Ww = phase.shape
                meta = f"r{R_frac:.3f}_e{roll_frac:.3f}_{profile}_m{order_m}_init{init_steps}_more{more_steps}"
                base = f"zero_{meta}_{ts}"
                npy_path = os.path.join(ZERO_DIR, base + ".npy")
                bmp_path = os.path.join(ZERO_DIR, base + ".bmp")

                # save raw phase (radians, pre-correction); this is what zcar will load
                np.save(npy_path, phase.astype(np.float32))

                # also drop a preview BMP written with ZERO carrier (so it looks like what you saved)
                try:
                    corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
                    if corr_u8 is not None:
                        # write to bmp_path without disturbing your OUT_BMP
                        self._write_phase_with_corr(phase.astype(np.float32), corr_u8, bmp_path,
                                                    carrier_cmd=(0.0, 0.0), steer_cmd=(0.0, 0.0), settle_s=0.0)
                except Exception:
                    pass
                print(f"[FlatTop] zero-carrier phase saved: {npy_path}")
            return

        # ---- normal closed-loop path below ----
        self._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                    carrier_cmd=EFFECTIVE_CARRIER , steer_cmd=(0.0, 0.0), settle_s=0.0)
        time.sleep(0.35)

        # ---- find +1 ROI once (radius ~ flat-top radius*panel_scale) ----
        g0 = grab_gray_to_panel(W, H)
        det = detect_plus_one(g0)
        if det is None:
            print("[FlatTop] Could not detect +1 order; aborting.")
            return
        x1, y1, r_near = det
        # choose a measurement radius slightly smaller than the bright ring thickness
        meas_r = max(6.0, min(0.40 * r_near, 0.35 * min(W, H)))  # conservative circle
        print(f"[FlatTop] ROI @ ({x1:.1f},{y1:.1f}) R={meas_r:.1f}")

        # ---- iterate until uniform (low CV) or stop ----
        best_cv = 1e9
        for it in range(1, maxit + 1):
            if getattr(self, "_flattop_stop", False):
                print("[FlatTop] stop requested.")
                break

            # measure CV on camera in ROI
            g = grab_gray_to_panel(W, H)
            cv_val, mean_val, std_val, npx = roi_cv(g, x1, y1, meas_r)
            if cv_val is None:
                print("[FlatTop] ROI too small to measure; increasing radius slightly.")
                meas_r *= 1.15
                continue

            best_cv = min(best_cv, cv_val)
            print(f"[FlatTop] it={it:02d}  CV={cv_val:.4f} (mean={mean_val:.3f}, std={std_val:.3f}, n={npx})")

            # stop condition
            if cv_val <= cv_thr:
                print(f"[FlatTop] uniform! CV={cv_val:.4f} ≤ {cv_thr:.3f}.")
                break

            # do more GS steps from *current* phase and show again
            phase = gs_farfield(target_amp, steps=more_steps, phase_init=phase, rng_seed=None)
            self._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                        carrier_cmd=EFFECTIVE_CARRIER , steer_cmd=(0.0, 0.0), settle_s=0.0)
            time.sleep(0.25)

        # final write (already current)
        self._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                    carrier_cmd=EFFECTIVE_CARRIER , steer_cmd=(0.0, 0.0), settle_s=0.0)
        print(f"[FlatTop] done. best CV={best_cv:.4f}")
        # after the final write (or right before return in open_loop path)
        if zero_carrier:
            import os, time, cv2, numpy as np
            ZERO_DIR = r"C:\WC\SLM_bmp\zero_carrier"
            os.makedirs(ZERO_DIR, exist_ok=True)
            ts = time.strftime("%Y%m%d_%H%M%S")
            Hh, Ww = phase.shape
            meta = f"r{R_frac:.3f}_e{roll_frac:.3f}_{profile}_m{order_m}_init{init_steps}_more{more_steps}"
            base = f"zero_{meta}_{ts}"
            npy_path = os.path.join(ZERO_DIR, base + ".npy")
            bmp_path = os.path.join(ZERO_DIR, base + ".bmp")

            # save raw phase (radians, pre-correction); this is what zcar will load
            np.save(npy_path, phase.astype(np.float32))

            # also drop a preview BMP written with ZERO carrier (so it looks like what you saved)
            try:
                corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
                if corr_u8 is not None:
                    # write to bmp_path without disturbing your OUT_BMP
                    self._write_phase_with_corr(phase.astype(np.float32), corr_u8, bmp_path,
                                                carrier_cmd=(0.0, 0.0), steer_cmd=(0.0, 0.0), settle_s=0.0)
            except Exception:
                pass

            print(f"[FlatTop] zero-carrier phase saved: {npy_path}")


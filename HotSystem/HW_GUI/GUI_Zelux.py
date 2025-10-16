# from ECM import *
import win32clipboard

from ImGuiwrappedMethods import *
from Common import *
from HW_wrapper import HW_devices as hw_devices
from HW_wrapper.Wrapper_MFF_101 import FilterFlipperController
import os
import cv2
import numpy as np

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

        # --- Target generator defaults ---
        self.target_mode = "gaussian"  # or "soft_disk"
        self.target_fwhm = 120  # px (for gaussian)
        self.target_R = 90  # px (for soft_disk radius)
        self.target_M = 8  # super-gaussian order (edge softness)
        self.target_out = r"C:\WC\HotSystem\Utils\Desired_image.bmp"
        self.target_preview = r"C:\WC\HotSystem\Utils\Desired_target_preview.png"

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
                        dpg.add_combo(label="Target", items=["gaussian", "soft_disk"],
                                      default_value=self.target_mode,
                                      width=110,
                                      callback=lambda s, a, u: setattr(self, "target_mode", a))

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
                        dpg.add_input_int(label="FWHM(px)", tag="inpFWHM", width=120, default_value=self.target_fwhm)
                        dpg.add_input_int(label="R(px)", tag="inpR", width=100, default_value=self.target_R)
                        dpg.add_input_int(label="m", tag="inpM", width=100, default_value=self.target_M)
                        dpg.add_button(label="Make Desired", tag="btnMakeDesired", callback=self.MakeDesiredImage)

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

    def _SLMIterationsWorker(self):
        # --- CONFIG (paths & params you gave) ---
        CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
        TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"
        OUT_BMP = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"  # Point SLMControl3 to this once

        # SLM UI transforms (pixels) — as requested
        X_SHIFT, Y_SHIFT, ROT_DEG = -17, 114, 0.0

        # Iteration knobs
        OUTER_ITERS = 10  # rounds (you can change on the fly)
        INNER_GS = 30  # GS steps per round
        APOD_SIGMA = 0.16  # edge taper to reduce ringing

        # ---- helpers ----
        def preprocess_target_to_panel(target_path, panel_wh, x_shift=-17, y_shift=114, rot_deg=0.0):
            import cv2, numpy as np
            W, H = panel_wh
            img = cv2.imread(target_path, cv2.IMREAD_GRAYSCALE)  # works for your RGB BMP too
            if img is None:
                raise FileNotFoundError(target_path)
            tgt = cv2.resize(img, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
            if tgt.max() > 0: tgt /= tgt.max()

            # rotation → translation (match your SLM UI)
            Mrot = cv2.getRotationMatrix2D((W / 2, H / 2), rot_deg, 1.0)
            tgt = cv2.warpAffine(tgt, Mrot, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=0)
            Mtran = np.float32([[1, 0, x_shift], [0, 1, y_shift]])
            tgt = cv2.warpAffine(tgt, Mtran, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                 borderValue=0)

            # mild apodization
            yy, xx = np.mgrid[0:H, 0:W]
            x = (xx - W / 2) / (W / 2);
            y = (yy - H / 2) / (H / 2)
            r2 = x * x + y * y
            apod = np.exp(-r2 / (2 * APOD_SIGMA * APOD_SIGMA)).astype(np.float32)
            tgt *= apod
            tgt /= (tgt.max() + 1e-8)
            return tgt

        def phase_to_u8(phase_rad):
            ph = np.mod(phase_rad, 2 * np.pi)
            return np.uint8(np.round(ph * (255.0 / (2 * np.pi))))

        def u8_to_phase(u8):
            return (u8.astype(np.float32) / 255.0) * 2 * np.pi

        def gs_update_relaxed(phase_slm, target_amp, steps=30, beta=0.6):
            """
            Relaxed Gerchberg–Saxton (amplitude relaxation beta in [0,1]).
            beta=1 -> standard GS. 0.5–0.7 typically converges smoother.
            """
            H, W = target_amp.shape
            amp_target = target_amp
            for _ in range(steps):
                field_s = np.exp(1j * phase_slm)  # unit amp at SLM
                field_f = np.fft.fftshift(np.fft.fft2(field_s))  # far-field
                amp_f = np.abs(field_f)
                phase_f = np.angle(field_f)

                # relaxed amplitude: move current amplitude toward target
                amp_new = (1 - beta) * amp_f + beta * amp_target

                field_f_new = amp_new * np.exp(1j * phase_f)
                field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))
                phase_slm = np.angle(field_s_back).astype(np.float32)
            return np.mod(phase_slm, 2 * np.pi)

        def save_phase_with_correction(phase_slm_rad, corr_u8, out_path):
            phase_out = np.mod(phase_slm_rad + u8_to_phase(corr_u8), 2 * np.pi)
            ok = cv2.imwrite(out_path, phase_to_u8(phase_out))
            if not ok:
                print(f"❌ Failed writing {out_path}")

        import glob, os, cv2, time

        # Folder where Zelux saves images
        ZELUX_IMG_DIR = r"Q:\QT-Quantum_Optic_Lab\expData\Images"

        def find_latest_zelux(dir_path=ZELUX_IMG_DIR):
            """Return full path of the newest Zelux image (PNG/BMP)."""
            patterns = [
                os.path.join(dir_path, "Zelux_*.png"),
                os.path.join(dir_path, "Zelux_Image_*.png"),
                os.path.join(dir_path, "*.png"),
                os.path.join(dir_path, "*.bmp"),
            ]
            files = []
            for pat in patterns:
                files.extend(glob.glob(pat))
            if not files:
                return None
            return max(files, key=os.path.getmtime)

        def read_meas_latest():
            """
            Load newest Zelux frame as grayscale float [0..1].
            Crops off a 40 px bottom strip to remove overlay text.
            """
            p = find_latest_zelux(ZELUX_IMG_DIR)
            if not p:
                return np.zeros((H, W), np.float32)  # H,W are panel size (defined earlier)
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            if img is None:
                return np.zeros((H, W), np.float32)
            if img.ndim == 3:
                if img.shape[2] == 4:
                    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            img = img.astype(np.float32)
            if img.max() > 0:
                img /= img.max()
            # remove bottom overlay text if present
            if img.shape[0] > 40:
                img = img[:-40, :]
            return img

        def calibrate_steering(phase_slm, corr_u8, out_path, W, H,
                               dir_img=r"Q:\QT-Quantum_Optic_Lab\expData\Images",
                               probe_px=10.0, settle_s=0.25, timeout_s=5.0):
            """
            Calibrate mapping from commanded far-field shift (in 'spectral pixels') to
            measured centroid shift (camera pixels). Returns (sx, sy).
            """
            import glob, os, time, cv2, numpy as np

            def latest_path():
                pats = [os.path.join(dir_img, "Zelux_*.png"),
                        os.path.join(dir_img, "Zelux_Image_*.png"),
                        os.path.join(dir_img, "*.png"),
                        os.path.join(dir_img, "*.bmp")]
                files = []
                for p in pats: files.extend(glob.glob(p))
                return max(files, key=os.path.getmtime) if files else None

            def write_phase(ph):
                ph_out = np.mod(ph + (corr_u8.astype(np.float32) / 255.0) * 2 * np.pi, 2 * np.pi)
                cv2.imwrite(out_path, np.uint8(np.round(ph_out * (255.0 / (2 * np.pi)))))

            def capture_new_after(old_path):
                # trigger a new save in Zelux and wait for a newer file
                try:
                    new_path = self.SaveProcessedImage()  # auto press "Sv"
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
                    if img.shape[2] == 4:
                        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                img = img.astype(np.float32)
                if img.max() > 0: img /= img.max()
                if img.shape[0] > 40:  # crop overlay text if present
                    img = img[:-40, :]
                return img

            def centroid_brightest(img01):
                g = cv2.GaussianBlur(img01, (0, 0), 2.0)
                thr = np.quantile(g, 0.70)
                m = (g >= thr).astype(np.uint8)
                num, labels = cv2.connectedComponents(m)
                if num <= 1:
                    hh, ww = img01.shape
                    return ww / 2.0, hh / 2.0
                areas = [(labels == i).sum() for i in range(1, num)]
                i_max = 1 + int(np.argmax(areas))
                mask = (labels == i_max).astype(np.float32)
                s = mask.sum() + 1e-8
                yy, xx = np.mgrid[0:img01.shape[0], 0:img01.shape[1]]
                cy = float((yy * mask).sum() / s);
                cx = float((xx * mask).sum() / s)
                return cx, cy

            def apply_and_measure(cmdx, cmdy):
                yy, xx = np.mgrid[0:H, 0:W]
                ramp = -2 * np.pi * (cmdx * (xx / W) + cmdy * (yy / H))
                ph = np.mod(phase_slm + ramp.astype(np.float32), 2 * np.pi)
                old = latest_path()
                write_phase(ph)
                time.sleep(settle_s)  # allow SLM app to reload
                p = capture_new_after(old)
                img01 = read_gray01(p)
                if img01 is None:
                    return W / 2.0, H / 2.0
                # map centroid into panel coords
                cx, cy = centroid_brightest(img01)
                cx *= (W / img01.shape[1]);
                cy *= (H / img01.shape[0])
                return cx, cy

            # baseline
            cx0, cy0 = apply_and_measure(0.0, 0.0)

            # X probe
            cxp, cyp = apply_and_measure(+probe_px, 0.0)
            cxm, cym = apply_and_measure(-probe_px, 0.0)
            dx_meas = (cxp - cxm) / 2.0
            sx = dx_meas / probe_px  # measured_px per commanded_px (can be negative)

            # Y probe
            cxp, cyp = apply_and_measure(0.0, +probe_px)
            cxm, cym = apply_and_measure(0.0, -probe_px)
            dy_meas = (cyp - cym) / 2.0
            sy = dy_meas / probe_px

            print(f"[Calib] steering gain: sx={sx:.3f}, sy={sy:.3f}")
            return sx, sy

        # --- centroid of brightest blob (robust) ---
        def brightest_centroid(img01):
            g = cv2.GaussianBlur(img01, (0, 0), 2.0)
            thr = np.quantile(g, 0.70)  # top ~30% intensities
            m = (g >= thr).astype(np.uint8)
            num, labels = cv2.connectedComponents(m)
            if num <= 1:
                H, W = g.shape;
                return W / 2.0, H / 2.0
            areas = [(labels == i).sum() for i in range(1, num)]
            i_max = 1 + int(np.argmax(areas))
            mask = (labels == i_max).astype(np.float32)
            s = mask.sum() + 1e-8
            yy, xx = np.mgrid[0:g.shape[0], 0:g.shape[1]]
            cy = float((yy * mask).sum() / s);
            cx = float((xx * mask).sum() / s)
            return cx, cy

        # --- PI steering parameters ---
        STEER_SIGN_X = +1.0  # flip to -1.0 if movement is inverted in X
        STEER_SIGN_Y = -1.0  # flip sign if Y is inverted (often -1)
        Kp = 0.28  # proportional gain (px → px/round)
        Ki = 0.01  # integral gain (px/frame accumulated)
        MAX_STEP = 10.0  # clamp per-round command (px)

        # keep integrators on the instance so they persist across rounds
        if not hasattr(self, "_int_ex"):
            self._int_ex, self._int_ey = 0.0, 0.0

        # ---- load correction, desired & build target amplitude ----
        corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr_u8 is None:
            print(f"❌ Cannot read correction BMP: {CORR_BMP}")
            return
        H, W = corr_u8.shape
        print(f"Panel (from correction): {W}x{H}")

        tgt_gray = cv2.imread(TARGET_BMP, cv2.IMREAD_GRAYSCALE)
        if tgt_gray is None:
            print(f"❌ Cannot read desired image: {TARGET_BMP}")
            return

        # panel from correction map
        target_amp = preprocess_target_to_panel(TARGET_BMP, (W, H), x_shift=0, y_shift=0, rot_deg=0.0)
        cv2.imwrite(r"C:\WC\HotSystem\Utils\Desired_target_preview.png", (target_amp * 255).astype(np.uint8))

        # rotation then translation (match SLM UI)
        Mrot = cv2.getRotationMatrix2D((W / 2, H / 2), ROT_DEG, 1.0)
        target = cv2.warpAffine(target_amp, Mrot, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                borderValue=0)
        Mtran = np.float32([[1, 0, X_SHIFT], [0, 1, Y_SHIFT]])
        target = cv2.warpAffine(target, Mtran, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                                borderValue=0)

        # apodization to reduce ringing
        yy, xx = np.mgrid[0:H, 0:W]
        x = (xx - W / 2) / (W / 2)
        y = (yy - H / 2) / (H / 2)
        r2 = x * x + y * y
        apod = np.exp(-r2 / (2 * APOD_SIGMA * APOD_SIGMA)).astype(np.float32)
        target *= apod
        target /= (target.max() + 1e-8)

        # ---- init phase & run ----
        rng = np.random.default_rng(1)
        phase_slm = rng.uniform(0, 2 * np.pi, size=(H, W)).astype(np.float32)

        sx, sy = calibrate_steering(
            phase_slm=phase_slm,
            corr_u8=corr_u8,
            out_path=OUT_BMP,
            W=W, H=H,
            dir_img=ZELUX_IMG_DIR,  # your Zelux folder
            probe_px=40.0,  # try 8–15 if response is tiny
            settle_s=0.3,  # allow SLM app to reload
            timeout_s=6.0
        )
        if abs(sx) < 1e-3 or abs(sy) < 1e-3:
            print("[Calib] WARNING: zero response; check SLM app external mode and paths.")

        # if too small (no response), fall back to 1.0 to avoid divide-by-zero
        sx = sx if abs(sx) > 1e-3 else 1.0
        sy = sy if abs(sy) > 1e-3 else 1.0
        print(f"[Calib] sx={sx:.3f}, sy={sy:.3f}")

        # MSE history
        self._mse_hist = []

        for outer in range(1, OUTER_ITERS + 1):
            if getattr(self, "_iter_stop", False):
                print("Iterations stopped by user.")
                break

            # 1) write SLM pattern (with correction)
            save_phase_with_correction(phase_slm, corr_u8, OUT_BMP)
            print(f"[{outer}/{OUTER_ITERS}] wrote SLM BMP → {OUT_BMP}")

            # small delay to let SLM update optics
            time.sleep(0.25)

            # 2) auto-press “Sv”: call your existing saver (returns file path)
            try:
                snap_path = self.SaveProcessedImage()
                print(f"   Zelux saved: {snap_path}")
            except Exception as e:
                print(f"   ❌ SaveProcessedImage failed: {e}")
                break

            # 3) quick metric (optional): compare current camera image to target
            meas = cv2.imread(snap_path, cv2.IMREAD_GRAYSCALE)
            # after: meas = cv2.imread(snap_path, cv2.IMREAD_GRAYSCALE)
            sat = (meas >= 250).mean()
            if sat > 0.003:  # >0.3% pixels near white → likely clipping
                print("Please decrease laser power to avoid saturation")
                print("Please decrease laser power to avoid saturation")


            if meas is not None:
                # ----- ROI MSE (reduces background influence) -----
                ROI = 128  # px; try 96–160
                cx, cy = int(W / 2), int(H / 2)
                x0, x1 = max(0, cx - ROI // 2), min(W, cx + ROI // 2)
                y0, y1 = max(0, cy - ROI // 2), min(H, cy + ROI // 2)

                meas_roi = cv2.resize(meas, (W, H), interpolation=cv2.INTER_AREA)[y0:y1, x0:x1]
                target_roi = target[y0:y1, x0:x1]

                # normalize each ROI to its own max to avoid exposure drift
                meas_roi = cv2.GaussianBlur(meas_roi, (0, 0), 1.0)
                target_roi = cv2.GaussianBlur(target_roi, (0, 0), 1.0)
                mr = meas_roi / (meas_roi.max() + 1e-8)
                tr = target_roi / (target_roi.max() + 1e-8)
                err = float(np.mean((mr - tr) ** 2))

                self._mse_hist.append(err)
                hist_str = ", ".join(f"{v:.6f}" for v in self._mse_hist)
                print(f"   MSE history [{len(self._mse_hist)}]: {hist_str}")


            # ----- measure centroid error (pixels) -----
            meas_cx, meas_cy = brightest_centroid(meas)

            # --- calibrated proportional steering with soft limit ---
            tx, ty = W / 2.0, H / 2.0
            ex, ey = (tx - meas_cx), (ty - meas_cy)

            Kp = 0.9  # 0.6–1.2
            SOFT_LIM = 120.0

            eps = 1e-6
            ux = Kp * (ex / (sx + np.sign(sx) * eps))
            uy = Kp * (ey / (sy + np.sign(sy) * eps))

            # soft-limit (smoothly approaches ±SOFT_LIM)
            cmdx = SOFT_LIM * np.tanh(ux / SOFT_LIM)
            cmdy = SOFT_LIM * np.tanh(uy / SOFT_LIM)

            yy, xx = np.mgrid[0:H, 0:W]
            ramp = -2 * np.pi * (cmdx * (xx / W) + cmdy * (yy / H))
            phase_slm = np.mod(phase_slm + ramp.astype(np.float32), 2 * np.pi)

            print(f"   steer: err=({ex:+.2f},{ey:+.2f}) cmd=({cmdx:+.2f},{cmdy:+.2f}) (sx={sx:.3f}, sy={sy:.3f})")

            # 4) inner GS update towards desired amplitude
            phase_slm = gs_update_relaxed(phase_slm, target_amp=target, steps=INNER_GS, beta=0.6)

        # final write
        save_phase_with_correction(phase_slm, corr_u8, OUT_BMP)
        print("Iteration loop finished.")

    def MakeDesiredImage(self, sender=None, app_data=None, user_data=None):
        import numpy as np, cv2, os

        # Panel size from camera/SLM correction; fall back if unknown
        try:
            H = int(self.cam.camera.image_height_pixels)
            W = int(self.cam.camera.image_width_pixels)
        except Exception:
            W, H = 1272, 1024  # your SLM panel

        mode = self.target_mode
        FWHM = int(dpg.get_value("inpFWHM")) if dpg.does_item_exist("inpFWHM") else self.target_fwhm
        R = int(dpg.get_value("inpR")) if dpg.does_item_exist("inpR") else self.target_R
        M = int(dpg.get_value("inpM")) if dpg.does_item_exist("inpM") else self.target_M

        yy, xx = np.mgrid[0:H, 0:W]
        cx, cy = W / 2.0, H / 2.0
        x = xx - cx;
        y = yy - cy
        r = np.sqrt(x * x + y * y)

        if mode == "gaussian":
            sigma = FWHM / (2 * np.sqrt(2 * np.log(2)))
            tgt = np.exp(-(r ** 2) / (2 * sigma ** 2)).astype(np.float32)
        else:  # soft_disk
            tgt = np.exp(- (r / float(max(R, 1))) ** max(M, 2)).astype(np.float32)

        # tiny blur to avoid pixelation; normalize
        tgt = cv2.GaussianBlur(tgt, (0, 0), 0.5)
        tgt /= (tgt.max() + 1e-8)

        # ensure folder exists, then save BMP + a preview PNG
        os.makedirs(os.path.dirname(self.target_out), exist_ok=True)
        cv2.imwrite(self.target_out, (tgt * 255).astype(np.uint8))
        cv2.imwrite(self.target_preview, (tgt * 255).astype(np.uint8))

        print(f"✅ Desired image written → {self.target_out} (mode={mode}, FWHM={FWHM}, R={R}, M={M})")

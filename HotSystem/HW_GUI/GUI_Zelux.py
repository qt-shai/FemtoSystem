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
                        # dpg.add_input_text(label="X_+", tag="inpCrossX",
                        #                    width=50, default_value=str(int(self.cam.camera.image_width_pixels / 2)),
                        #                    on_enter=True)
                        # dpg.add_input_text(label="Y_+", tag="inpCrossY",
                        #                    width=50, default_value=str(int(self.cam.camera.image_height_pixels / 2)),
                        #                    on_enter=True)
                        # dpg.add_button(label="Set +", tag="btnSetCross",
                        #                callback=self.set_cross_from_inputs)


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

        # Prepare RGB image (with or without background subtraction)
        if self.subtract_background and self.background_image is not None:
            img_rgba = self.cam.lateset_image_buffer.reshape((height, width, 4))
            bg_rgba = self.background_image.reshape((height, width, 4))

            gray = np.mean(img_rgba[:, :, :3], axis=2)
            bg_gray = np.mean(bg_rgba[:, :, :3], axis=2)

            offset = 0.25
            subtracted = gray - bg_gray + offset
            subtracted = np.clip(subtracted, 0, None)

            gamma = 0.98
            norm = np.clip(subtracted / (subtracted.max() + 1e-6), 0, 1)
            bright = np.power(norm, gamma)

            img_rgb = (np.stack([bright] * 3, axis=-1) * 255).astype(np.uint8)
        else:
            img_rgba = self.cam.lateset_image_buffer.reshape((height, width, 4))
            img_rgb = (img_rgba[:, :, :3] * 255).astype(np.uint8)

        # --- Overlay: draw cross and coordinates using OpenCV ---
        if self.show_center_cross or self.show_coords_grid:
            center_x = width // 2
            center_y = height // 2

            # Draw cross
            cv2.line(img_rgb, (center_x - 100, center_y), (center_x + 100, center_y), (0, 255, 0), 1)
            cv2.line(img_rgb, (center_x, center_y - 100), (center_x, center_y + 100), (0, 255, 0), 1)

            # Get current absolute position (stage coordinates)
            try:
                self.positioner.GetPosition()
                abs_x = self.positioner.AxesPositions[0] * 1e-6  # microns to mm
                abs_y = self.positioner.AxesPositions[1] * 1e-6
                abs_z = self.positioner.AxesPositions[2] * 1e-6
                coord_text = f"X = {abs_x:.1f}, Y = {abs_y:.1f}, Z = {abs_z:.1f}"
            except Exception:
                coord_text = "Stage position not available"

            # Draw coordinates in bottom-left
            cv2.putText(img_rgb, coord_text, (10, height - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1, cv2.LINE_AA)

        if self.show_coords_grid:
            step_px = 100
            pixel_to_um_x = 0.04  # um/pixel
            pixel_to_um_y = 0.04
            x_shift_px = 2.38 / pixel_to_um_x
            y_shift_px = 0.85 / pixel_to_um_y

            # Horizontal grid lines
            y = 0
            while y < height - step_px:
                y_shifted = int(y + y_shift_px)
                offset_px = y_shifted - center_y
                coord_y = abs_y + offset_px * pixel_to_um_y
                cv2.line(img_rgb, (0, y_shifted), (width, y_shifted), (100, 255, 100), 1, cv2.LINE_AA)
                cv2.putText(img_rgb, f"{coord_y:.1f}", (5, y_shifted + 15),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                y += step_px

            # Vertical grid lines
            x = 2 * step_px
            while x < width:
                x_shifted = int(x + x_shift_px)
                offset_px = x_shifted - center_x
                coord_x = abs_x - offset_px * pixel_to_um_x
                cv2.line(img_rgb, (x_shifted, 0), (x_shifted, height), (100, 255, 100), 1, cv2.LINE_AA)
                cv2.putText(img_rgb, f"{coord_x:.1f}", (x_shifted + 2, height - 18),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
                x += step_px

        # --- Save to disk ---
        folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/Images/'
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        timeStamp = getCurrentTimeStamp()
        filename = os.path.join(folder_path, f"Zelux_Image_{timeStamp}.png")

        # Save using OpenCV (convert RGB to BGR)
        cv2.imwrite(filename, cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))
        print(f"Image saved with overlays to: {filename}")
        copy_image_to_clipboard(filename)
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

    def on_off_slider_callback(self, sender=None, app_data=None):
        # app_data is the new slider value (0 or 1)
        flipper_1_serial_number = "37008855"
        flipper_2_serial_number = "37008948"
        if sender == "on_off_slider":
            self.flipper_serial_number = flipper_1_serial_number
        elif sender == "on_off_slider_2":
            self.flipper_serial_number = flipper_2_serial_number
        if app_data == 1:
            self.Move_flipper(self.flipper_serial_number)
            flipper_position = self.flipper.get_position()
            if flipper_position == 2:
                dpg.configure_item(sender, format="Up")
            else:
                dpg.configure_item(sender, format="Down")
            dpg.bind_item_theme(sender, "OnTheme")
        else:
            self.Move_flipper(self.flipper_serial_number)

            flipper_position = self.flipper.get_position()
            if flipper_position == 2:
                dpg.configure_item(sender, format="Up")
            else:
                dpg.configure_item(sender, format="Down")
            dpg.bind_item_theme(sender, "OffTheme")

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

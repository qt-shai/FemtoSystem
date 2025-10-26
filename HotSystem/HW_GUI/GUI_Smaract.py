from functools import partial
import dearpygui.dearpygui as dpg
import numpy as np
import pyperclip

from Common import DpgThemes
from HW_wrapper import HW_devices as hw_devices
import random  # for simulation
import math
import os
import shutil
import time
from datetime import datetime
import re

from SystemConfig import Instruments
from Common import load_window_positions


class GUI_smaract():
    def __init__(self, simulation: bool = False, serial_number:str = "") -> None:
        self.last_z_value = None
        self.HW = hw_devices.HW_devices()
        self.dev = self.HW.positioner
        self.selectedDevice = serial_number
        self.dev.error = None
        if simulation:
            self.simulation = simulation
        else:
            self.simulation = False
        self.dev.GetAvailableDevices()

        self.prefix = "mcs"
        self.window_tag:str = f"{self.prefix}_Win"
        self.ch_offset = 0

        if simulation:
            print("GUI Smaract in simulation mode")

    def create_gui(self):
        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        red_button_theme = themes.color_theme((255, 0, 0), (0, 0, 0))

        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()

        child_width = 100
        # lbl_list=["in","out","right","left","up","down"]
        lbl_list = ["out", "in", "left", "right", "down", "up"]
        with dpg.window(tag=self.window_tag, label=f"{self.prefix} stage, disconnected", no_title_bar=False, height=self.viewport_height/8, width=self.viewport_width*0.8, pos=[0, 0],
                        collapsed=False):
            with dpg.group(horizontal=True):
                with dpg.group(horizontal=False, tag="_column 1_"):
                    dpg.add_text("Position (um)")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_text("Ch" + str(ch), tag=f"{self.prefix}_Ch" + str(ch))
                    dpg.add_button(label="Stop all axes", callback=self.btn_stop_all_axes)
                    dpg.bind_item_theme(dpg.last_item(), red_button_theme)

                with dpg.group(horizontal=False, tag="_column 2_"):
                    dpg.add_text("                 Coarse (um)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_button(label=lbl_list[ch*2], width=50, callback=self.move_c_f, user_data=(ch, 'pos', 'c'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_button(label=lbl_list[ch*2+1], width=50, callback=self.move_c_f, user_data=(ch, 'neg', 'c'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_input_float(label="", default_value=1, tag=f"{self.prefix}_ch" + str(ch) + "_Cset",
                                                indent=-1, format='%.1f', width=150, step=1, step_fast=100,callback=self.ipt_large_step)
                            dpg.add_text("um  ", indent=-10)
                    with dpg.group(horizontal=True, tag="group_pos_1"):
                        dpg.add_button(label="load pos", callback=self.load_pos)
                        dpg.add_button(label="save pos",callback=self.save_pos)


                with dpg.group(horizontal=False, tag="_column 3_"):
                    dpg.add_text("          Fine (nm)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="-", width=25, callback=self.move_c_f, user_data=(ch, 'pos', 'f'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_button(label="+", width=25, callback=self.move_c_f, user_data=(ch, 'neg', 'f'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_input_float(label="", default_value=100, tag=f"{self.prefix}_ch" + str(ch) + "_Fset",
                                                indent=-1, format='%.1f', width=150, step=10, step_fast=100,callback=self.ipt_small_step)
                            dpg.add_text("nm  ", indent=-10)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="connect", callback=self.btn_connect, tag=f"{self.prefix}_Connect")
                        dpg.add_button(label="Log", callback=self.btnLogPoint, tag=f"{self.prefix}_Log")
                        dpg.add_button(label="Del", callback=self.btnDelPoint)
                        dpg.add_text(tag=f"{self.prefix}logged_points", label="")

                with dpg.group(horizontal=False, tag="_column 4_", width=child_width/3):
                    dpg.add_text(" UV")
                    for ch in range(2):
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="-", width=10, callback=self.move_uv, user_data=(ch, -1, True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                            dpg.add_button(label="+", width=10, callback=self.move_uv, user_data=(ch, 1, True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                with dpg.group(horizontal=False, width=child_width*2):
                    dpg.add_text("Move Abs. (um)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_input_float(label="", default_value=0, tag=f"{self.prefix}_ch" + str(ch) + "_ABS", indent=-1,
                                                format='%.4f', step=1, step_fast=10) #
                    dpg.add_button(label="Set XYZ", callback=self.fill_current_position_to_moveabs)
                with dpg.group(horizontal=False, width=child_width*.8):
                    dpg.add_text("   GO")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="GO", callback=self.move_absolute, user_data=ch)
                    dpg.add_button(label="Pst", callback=self.paste_clipboard_to_moveabs)
                with dpg.group(horizontal=False, width=child_width*0.8):
                    dpg.add_text(" Ref.")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Ref. " + str(ch))
                with dpg.group(horizontal=False, width=child_width*0.8):
                    dpg.add_text("  Zero   ")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Zero " + str(ch), callback=self.btn_zero, user_data=ch)
                with dpg.group(horizontal=False, width=child_width):
                    dpg.add_text("    Home")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Home " + str(ch), callback=self.btn_move_to_home, user_data=ch,indent=10)
                with dpg.group(horizontal=False, width=child_width):
                    dpg.add_text("Status")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_combo(items=["idle",""], tag="mcs_Status" + str(ch))
                with dpg.group(horizontal=False):
                    dpg.add_combo(label="Devices", items=self.dev.Available_Devices_List, tag=f"{self.prefix}_device_selector",
                                  callback=self.cmb_device_selector, width=300)
                    dpg.add_button(label="Refresh", callback=self.btn_get_av_device_list)
            with dpg.group(horizontal=False, tag="table_group"):
                with dpg.group(horizontal=True, tag="table_group2"):
                    dpg.add_button(label="Load logged from file", callback=self.load_logged_points_from_file)
                    dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                    dpg.add_button(label="update table", callback=self.update_logged_points_table)
                    dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                    dpg.add_button(label="Calc UV", tag=f"{self.prefix}_calc_uv", callback=self.btn_calc_uv)
                    dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                with dpg.table(header_row=True, tag=f"{self.prefix}logged_points_table", width=700):
                    dpg.add_table_column(label="Point")
                    dpg.add_table_column(label="X")
                    dpg.add_table_column(label="Y")
                    dpg.add_table_column(label="Z")
                    dpg.add_table_column(label="Delete")
                    dpg.add_table_column(label="Go Abs")

        self.load_logged_points_from_file()
        self.load_last_abs_position()  # ✅ load saved abs fields

        if self.simulation:
            self.dev.AxesKeyBoardLargeStep = []
            self.dev.AxesKeyBoardSmallStep = []
            self.dev.AxesPositions = []
            self.dev.AxesNewPositions = []
            self.dev.AxesTargetPositions = []
            self.dev.AxesRelativeStep = []
            self.dev.AxesPosUnits = []
            self.dev.AxesVelocities = []
            self.dev.AxesAcceleraitions = []
            self.dev.AxesState = []
            self.dev.AxesFault = []
        else:
            self.connect()
            self.dev.AxesKeyBoardLargeStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Cset") * self.dev.StepsIn1mm / 1e3) for ch in range(3)]
            self.dev.AxesKeyBoardSmallStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Fset") * self.dev.StepsIn1mm / 1e6) for ch in range(3)]

    def DeleteMainWindow(self):
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

    def fill_current_position_to_moveabs(self):
        try:
            # Get current position from device or simulation
            if self.dev.IsConnected:
                self.dev.GetPosition()  # Ensure it's updated
                pos = self.dev.AxesPositions  # [x, y, z] in pm
            elif self.simulation:
                import random
                pos = [random.uniform(-1e9, 1e9) for _ in range(3)]
            else:
                print("Device not connected.")
                return

            x_value = pos[0] * 1e-6  # convert pm to µm
            y_value = pos[1] * 1e-6
            z_value = pos[2] * 1e-6

            # Update MoveABS fields
            dpg.set_value(f"{self.prefix}_ch0_ABS", x_value)
            dpg.set_value(f"{self.prefix}_ch1_ABS", y_value)
            dpg.set_value(f"{self.prefix}_ch2_ABS", z_value)

            # ✅ Store Z value
            self.last_z_value = z_value

            # Format with comma as decimal separator and no thousands separator
            def fmt(v):
                return f"{v:.1f}".replace('.', ',')

            clipboard_str = f"Site ({fmt(x_value)} {fmt(y_value)} {fmt(z_value)})"
            import pyperclip
            pyperclip.copy(clipboard_str)

            print(f"{clipboard_str} Copied to clipboard")

            # ✅ Save to file
            with open("last_position.txt", "w") as f:
                f.write(f"{x_value:.6f},{y_value:.6f},{z_value:.6f}\n")
            print("Position saved to last_position.txt")
        except Exception as e:
            print(f"Failed to set MoveABS from position: {e}")

    def paste_clipboard_to_moveabs(self):
        try:
            clipboard_text = pyperclip.paste().strip()
            print(f"Clipboard text: {clipboard_text}")

            if clipboard_text.lower().startswith("site"):
                # Parse "Site (x y z)" with commas as decimal separators
                start = clipboard_text.find("(")
                end = clipboard_text.find(")", start)
                inside = clipboard_text[start + 1:end]

                # Replace decimal commas with dots
                inside = inside.replace(",", ".")
                # Split by whitespace (handles spaces or tabs)
                parts = [p for p in inside.strip().split() if p]

                if len(parts) < 3:
                    raise ValueError(f"Expected 3 coordinates in Site(...), got {parts}")

                x_value, y_value, z_value = map(float, parts[:3])

                dpg.set_value(f"{self.prefix}_ch0_ABS", x_value)
                dpg.set_value(f"{self.prefix}_ch1_ABS", y_value)
                dpg.set_value(f"{self.prefix}_ch2_ABS", z_value)

                print(f"Set MoveAbsX={x_value}, MoveAbsY={y_value}, MoveAbsZ={z_value}")

            else:
                # Legacy "X=..., Y=...[...]" format
                text = clipboard_text.replace(",", ".")  # allow decimal commas
                x_str = text.split('X=')[1].split(',')[0]
                y_str = text.split('Y=')[1].split(']')[0]
                x_value = float(x_str.strip())
                y_value = float(y_str.strip())

                dpg.set_value(f"{self.prefix}_ch0_ABS", x_value)
                dpg.set_value(f"{self.prefix}_ch1_ABS", y_value)

                print(f"Set MoveAbsX={x_value}, MoveAbsY={y_value} (Z unchanged)")

        except Exception as e:
            print(f"Failed to parse clipboard: {e}")

    def load_last_abs_position(self):
        try:
            if os.path.exists("last_position.txt"):
                with open("last_position.txt", "r") as f:
                    line = f.readline().strip()
                    x, y, z = [float(val) for val in line.split(",")]

                dpg.set_value(f"{self.prefix}_ch0_ABS", x)
                dpg.set_value(f"{self.prefix}_ch1_ABS", y)
                dpg.set_value(f"{self.prefix}_ch2_ABS", z)

                self.last_z_value = z
                print(f"Loaded last position: x={x}, y={y}, z={z}")
            else:
                print("last_position.txt not found.")
        except Exception as e:
            print(f"Error loading last_position.txt: {e}")

    def save_pos(self, profile_name="local"):
        # Core static windows
        window_names = [
            "pico_Win", "mcs_Win", "Zelux Window", "graph_window", "Main_Window",
            "OPX Window", "Map_window", "Scan_Window", "LaserWin", "CLD1011LP_Win",
            "experiments_window", "console_window", "hrs500_Win",
        ]
        file_name = f"win_pos_{profile_name}.txt"

        # Save viewport size
        vp_w = dpg.get_viewport_client_width()
        vp_h = dpg.get_viewport_client_height()

        # Gather all windows once
        all_items = dpg.get_all_items()
        # Any alias starting with one of these prefixes will be recorded
        dynamic_prefixes = [
            "KDC101_Win_",
            "Femto_Window_",
            "Keysight33500B_Win"
        ]

        for item in all_items:
            if dpg.get_item_type(item) == "mvAppItemType::mvWindowAppItem":
                tag = dpg.get_item_alias(item) or str(item)
                for prefix in dynamic_prefixes:
                    if tag.startswith(prefix):
                        window_names.append(tag)
                        break

        # Collect positions & sizes
        window_positions = {}
        for win in window_names:
            if dpg.does_item_exist(win):
                pos = dpg.get_item_pos(win)
                size = (dpg.get_item_width(win), dpg.get_item_height(win))
                window_positions[win] = (pos, size)
                print(f"{win}: pos={pos}, size={size}")

        # Also capture OPX graph size
        graph_tag = "plotImaga"
        if dpg.does_item_exist(graph_tag):
            gsize = (dpg.get_item_width(graph_tag), dpg.get_item_height(graph_tag))
            window_positions[graph_tag] = (None, gsize)
            print(f"{graph_tag} size={gsize}")

        # Write them out
        try:
            with open(file_name, "w") as f:
                f.write(f"Viewport_Size: {vp_w}, {vp_h}\n")
                for name, (pos, size) in window_positions.items():
                    if pos is not None:
                        f.write(f"{name}_Pos: {pos[0]}, {pos[1]}\n")
                    f.write(f"{name}_Size: {size[0]}, {size[1]}\n")
            print(f"Saved positions -> {file_name}")
        except Exception as e:
            print(f"Error saving window positions: {e}")

    def load_pos(self, profile_name="local", include_main=False, main_tag=None):
        if str(profile_name) == "530":
            profile_name = "local"
        file_name = f"win_pos_{profile_name}.txt"
        try:
            load_window_positions(file_name, include_main=include_main, main_tag=main_tag)
        except Exception as e:
            print(f"Error loading window positions and sizes: {e}")

    def _get_rot_deg_from_ch2(self) -> float:
        """Read ch2 ABS field (µm) and treat its numeric value as degrees of in-plane rotation."""
        try:
            return float(dpg.get_value(f"{self.prefix}_ch2_Cset"))
        except Exception:
            return float(self.last_z_value or 0.0)

    def _uv_rotated(self):
        """
        Return (U,V) rotated in the XY plane by +theta (deg), where theta comes from ch2.
        Keeps the Z components unchanged.
        Falls back to current U/V if base vectors aren't saved yet.
        """
        import math
        theta = math.radians(self._get_rot_deg_from_ch2())
        c, s = math.cos(theta), math.sin(theta)

        # Prefer base (unrotated) vectors if we have them; else use current
        U0 = getattr(self.dev, "U_base", getattr(self.dev, "U", [1, 0, 0]))
        V0 = getattr(self.dev, "V_base", getattr(self.dev, "V", [0, 1, 0]))

        Ux, Uy, Uz = float(U0[0]), float(U0[1]), float(U0[2])
        Vx, Vy, Vz = float(V0[0]), float(V0[1]), float(V0[2])

        # 2D rotation in XY plane
        Ux_r, Uy_r = (c * Ux - s * Uy), (s * Ux + c * Uy)
        Vx_r, Vy_r = (c * Vx - s * Vy), (s * Vx + c * Vy)

        U_rot = [Ux_r, Uy_r, Uz]
        V_rot = [Vx_r, Vy_r, Vz]
        return U_rot, V_rot

    def ipt_large_step(self,app_data,user_data):
        ch=int(app_data[6])        
        self.dev.AxesKeyBoardLargeStep[ch]=int(user_data*self.dev.StepsIn1mm/1e3)
        # print(self.dev.AxesKeyBoardLargeStep[ch])

    def ipt_small_step(self,app_data,user_data):
        ch=int(app_data[6])
        self.dev.AxesKeyBoardSmallStep[ch]=int(user_data*self.dev.StepsIn1mm/1e6)
        # print(self.dev.AxesKeyBoardSmallStep[ch])

    def btnLogPoint(self):

        current_height = dpg.get_item_height(self.window_tag)
        new_height = current_height + 30  # Increase height by 50 units
        dpg.configure_item(self.window_tag, height=new_height)

        if self.dev.IsConnected:
            self.log_point(self.dev.AxesPositions)
        elif self.simulation:
            simulated_position = [random.uniform(-1e9, 1e9) for _ in range(3)]
            self.log_point(simulated_position)
        else:
            print("Cannot log point while Smaract is disconnected.")

    def log_point(self, position):
        """Log a point, update the UI, and calculate vectors if applicable."""
        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        
        if len( self.dev.LoggedPoints)<3:
            self.dev.LoggedPoints.append(position.copy())  # [pm]
        print(self.dev.LoggedPoints)

        # Update the UI
        dpg.set_value(f"{self.prefix}logged_points", "* " * len(self.dev.LoggedPoints))
        self.update_logged_points_table()

        # Prepare the text to copy with only the last logged point and the increment line
        last_point = self.dev.LoggedPoints[-1]
        text_to_copy = f"self.dev.LoggedPoints.append({last_point})"
        
        print(text_to_copy)

        # Check the number of logged points and calculate vectors accordingly
        if len(self.dev.LoggedPoints) == 3:
            self.dev.calc_uv()
            dpg.bind_item_theme(f"{self.prefix}_calc_uv", yellow_theme)



    def load_logged_points_from_file(self):
        if os.path.exists('logged_points.txt'):
            with open('logged_points.txt', 'r') as f:
                self.dev.LoggedPoints = [list(map(int, line.strip().split(','))) for line in f]
        else:
            self.dev.LoggedPoints = []  # Set to an empty list if the file doesn't exist

    def update_logged_points_table(self):
        """Rebuild the table rows to show all logged points."""
        table_id = f"{self.prefix}logged_points_table"

        # Delete only the rows, keep the table headers intact
        for child in dpg.get_item_children(table_id, 1):
            dpg.delete_item(child)

        # Rebuild the table with the current logged points
        for i, point in enumerate(self.dev.LoggedPoints, start=1):
            with dpg.table_row(parent=table_id):
                dpg.add_text(f"Point {i}")
                dpg.add_text(f"{point[0]/1e6:.2f}")
                dpg.add_text(f"{point[1]/1e6:.2f}")
                dpg.add_text(f"{point[2]/1e6:.2f}")
                dpg.add_button(label="Delete", width=100, callback=partial(self.delete_table_row, i - 1))
                dpg.add_button(label="fill abs", width=100, callback=partial(self.go_abs_callback, point))

    def go_abs_callback(self,point):
        """Callback to set the input fields with the selected point."""
        for ch, value in enumerate(point):
            dpg.set_value(f"{self.prefix}_ch{ch}_ABS", value/1e6)

    def delete_table_row(self, index):
        """Delete a row from the table and update the points list."""
        if 0 <= index < len(self.dev.LoggedPoints):
            current_height = dpg.get_item_height(self.window_tag)
            new_height = current_height - 30  # Increase height by 50 units
            dpg.configure_item(self.window_tag, height=new_height)

            # Remove the selected point
            del self.dev.LoggedPoints[index]
            dpg.set_value(f"{self.prefix}logged_points", "* " * len(self.dev.LoggedPoints))
            # Rebuild the table to reflect the change
            self.update_logged_points_table()

    def btnDelPoint(self):
        current_height = dpg.get_item_height(self.window_tag)
        new_height = current_height - 30  # Increase height by 50 units
        dpg.configure_item(self.window_tag, height=new_height)

        if self.dev.IsConnected:
            self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
            dpg.set_value(f"{self.prefix}logged_points", "* " * len(self.dev.LoggedPoints))
            self.update_logged_points_table()
        else:
            print("Cannot log point while Smaract is disconnected.")
            if self.simulation:
                random_numbers = [random.randint(-1000, 1000) for _ in range(3)]
                self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
                dpg.set_value(f"{self.prefix}logged_points", "* " * len(self.dev.LoggedPoints))
                self.update_logged_points_table()

    def btn_calc_uv(self):
        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        dpg.bind_item_theme(f"{self.prefix}_calc_uv", yellow_theme)
        if len(self.dev.LoggedPoints)<3:
            print(f"Please log at least three points prior to calculating u & v")
            return
        self.dev.calc_uv()
        # Save pristine (unrotated) copies
        self.dev.U_base = list(self.dev.U)
        self.dev.V_base = list(self.dev.V)

    def cmb_device_selector(self, app_data, item):
        self.selectedDevice = item

    def btn_connect(self):
        if not self.dev.IsConnected:
            self.connect()
        else:
            self.dev.Disconnect()
            dpg.set_item_label(self.window_tag, "Smaract, disconnected")
            dpg.set_item_label(f"{self.prefix}_Connect", "Connect")

    def btn_get_av_device_list(self):
        self.dev.GetAvailableDevices()

    def btn_stop_all_axes(self):
        self.dev.StopAllAxes()

    def btn_move_to_home(self, sender, app_data, ch):
        self.dev.MoveToHome(ch)

    def move_absolute(self, sender, app_data, ch):
        value = dpg.get_value(f"{self.prefix}_ch" + str(ch) + "_ABS")
        self.dev.MoveABSOLUTE(ch, int(value * self.dev.StepsIn1mm / 1e3))

    def move_uv(self, sender, app_data, user_data):
        try:
            ch, direction, is_coarse = user_data
            direction = float(direction)

            value1 = float(dpg.get_value(f"{self.prefix}_ch{ch}_Cset"))
            if not is_coarse:
                value1 = value1 / 10.0

            steps = int(direction * value1 / 1e3 * self.dev.StepsIn1mm)

            # <<< NEW: use rotated U/V based on ch2 angle >>>
            U_rot, V_rot = self._uv_rotated()
            vec = U_rot if ch == 0 else V_rot

            amount = [vec[i] * steps for i in range(3)]
            print(f"UV move (ch={ch}) angle={self._get_rot_deg_from_ch2():.3f}° amount={amount}")

            for channel in range(3):
                if not self.simulation:
                    self.dev.MoveRelative(channel, int(amount[channel]))
        except Exception as e:
            print(f"An error occurred: {e}")

    def btn_zero(self, sender, app_data, ch):
        self.dev.SetPosition(channel = ch, newPosition = 0)

    def move_c_f(self, sender, app_data, user_data):
        try:
            ch, direction, move_type = user_data
            factor = 1 if direction == 'pos' else -1
            scale = 1e3 if move_type == 'c' else 1e6
            steps = int(factor * dpg.get_value(f"{self.prefix}_ch{ch}_{move_type.upper()}set") * self.dev.StepsIn1mm / scale)
            self.dev.MoveRelative(ch + self.ch_offset, steps)
        except Exception as e:
            print(f"An error occurred in move_c_f: {e}")

    def connect(self):
        if self.simulation:
            print("Loaded smaract simulation device")
            return

        if self.dev.IsConnected:
            print(f"{self.prefix} device already connected")
            dpg.set_item_label(self.window_tag, f"{self.prefix} stage, {self.selectedDevice}, connected")
            dpg.set_item_label(f"{self.prefix}_Connect", "Disconnect")
            return

        if self.selectedDevice != "":
            self.dev.connect(self.selectedDevice)
            if self.dev.IsConnected:
                print(f"Connected to {self.prefix}")
                dpg.set_item_label(self.window_tag, f"{self.prefix} stage, {self.selectedDevice}, connected")
                dpg.set_item_label(f"{self.prefix}_Connect", "Disconnect")
            else:
                print(f"Connection to {self.prefix} device failed")

        else:
            print(f'Connection to {self.prefix} device failed. No device found.')
        
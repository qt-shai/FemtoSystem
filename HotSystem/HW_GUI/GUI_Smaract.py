from functools import partial
import dearpygui.dearpygui as dpg
import numpy as np

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


class GUI_smaract():
    def __init__(self, simulation: bool = False, serial_number:str = "") -> None:
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
                                                indent=-1, format='%.1f', width=200, step=10, step_fast=100,callback=self.ipt_small_step)
                            dpg.add_text("nm  ", indent=-10)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="connect", callback=self.btn_connect, tag=f"{self.prefix}_Connect")
                        dpg.add_button(label="Log", callback=self.btnLogPoint, tag=f"{self.prefix}_Log")
                        dpg.add_button(label="Del", callback=self.btnDelPoint)
                        dpg.add_text(tag=f"{self.prefix}logged_points", label="")
                with dpg.group(horizontal=False, tag="_column 4_", width=child_width):
                    dpg.add_text(" Ref.")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Ref. " + str(ch))

                with dpg.group(horizontal=False, tag="_column 5_", width=child_width):
                    dpg.add_text("  Zero   ")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Zero " + str(ch), callback=self.btn_zero, user_data=ch)
                    # dpg.add_button(label="Calc V",tag=f"{self.prefix}_calc_v", callback=self.btn_calc_v)

                with dpg.group(horizontal=False, tag="_column 6_", width=child_width):
                    dpg.add_text(" Move UV")
                    for ch in range(2):
                        with dpg.group(horizontal=True):
                            if ch == 0:
                                dpg.add_text("  U")
                            else:
                                dpg.add_text("  V")
                            dpg.add_button(label="-", width=20, callback=self.move_uv, user_data=(ch, -1, True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                            dpg.add_button(label="+", width=20, callback=self.move_uv, user_data=(ch, 1, True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)

                with dpg.group(horizontal=False, tag="_column 7_", width=child_width+100):
                    dpg.add_text("Move Abs. (um)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_input_float(label="", default_value=0, tag=f"{self.prefix}_ch" + str(ch) + "_ABS", indent=-1,
                                                format='%.4f', width=250, step=1, step_fast=10) #
                            
                with dpg.group(horizontal=False, tag="_column 8_", width=child_width*.8):
                    dpg.add_text("   GO")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="GO", callback=self.move_absolute, user_data=ch)

                with dpg.group(horizontal=False, tag="_column 9_", width=child_width):
                    dpg.add_text("    Home")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Home " + str(ch), callback=self.btn_move_to_home, user_data=ch,indent=10)

                with dpg.group(horizontal=False, tag="_column 10_", width=child_width):
                    dpg.add_text("Status")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_combo(items=["idle",""], tag="mcs_Status" + str(ch))

            with dpg.group(horizontal=True):
                dpg.add_combo(label="Devices", items=self.dev.Available_Devices_List, tag=f"{self.prefix}_device_selector",
                              callback=self.cmb_device_selector, width=300)
                dpg.add_button(label="Refresh", callback=self.btn_get_av_device_list)
                dpg.add_text(" Disable keyboard")
                dpg.add_checkbox(tag="mcs_Disable_Keyboard", callback=self.cbx_disable_keyboard)
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

        if simulation:
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


    def save_pos(self):
        # Define the list of windows to check and save positions for
        window_names = [
            "pico_Win", "mcs_Win", "Zelux Window",'graph_window','Main_Window',
            "OPX Window", "Map_window", "Scan_Window", "LaserWin","CLD1011LP_Win",
            "experiments_window","graph_window", "console_window"
        ]

        # Dynamically find and add all KDC windows
        all_windows = dpg.get_all_items()
        for item in all_windows:
            if dpg.get_item_type(item) == "mvAppItemType::mvWindowAppItem":
                tag = dpg.get_item_alias(item) or str(item)
                if tag.startswith("KDC101_Win_"):
                    window_names.append(tag)

        # Dictionary to store window positions and dimensions
        window_positions = {}

        # Iterate through the list of window names and collect their positions and sizes if they exist
        for win_name in window_names:
            if dpg.does_item_exist(win_name):
                win_pos = dpg.get_item_pos(win_name)
                win_size = dpg.get_item_width(win_name), dpg.get_item_height(win_name)
                window_positions[win_name] = (win_pos, win_size)
                print(f"Position of {win_name}: {win_pos}, Size: {win_size}")

        try:
            # Remove any existing window position and size entries
            lines = []
            new_content = [line for line in lines if not any(win_name in line for win_name in window_positions.keys())]

            # Append the new window positions and dimensions to the content
            for win_name, (position, size) in window_positions.items():
                new_content.append(f"{win_name}_Pos: {position[0]}, {position[1]}\n")
                new_content.append(f"{win_name}_Size: {size[0]}, {size[1]}\n")

            # Write back the updated content to the file
            with open("win_pos.txt", "w") as file:
                file.writelines(new_content)

            print("Window positions and sizes saved successfully to win_pos.txt.")
        except Exception as e:
            print(f"Error saving window positions and sizes: {e}")

    def load_pos(self):
        try:
            # Check if win_pos.txt exists and read the contents
            if not os.path.exists("win_pos.txt"):
                print("win_pos.txt not found.")
                return

            # Dictionaries to store positions and sizes loaded from the file
            window_positions = {}
            window_sizes = {}

            with open("win_pos.txt", "r") as file:
                lines = file.readlines()
                for line in lines:
                    # Split the line to get key and value
                    parts = line.split(": ")
                    if len(parts) != 2:
                        continue  # Skip lines that don't have the expected format

                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Check if the key is a window position entry
                    if "_Pos" in key:
                        # Extract window name and coordinates
                        window_name = key.replace("_Pos", "")
                        x, y = value.split(", ")
                        window_positions[window_name] = (float(x), float(y))

                    # Check if the key is a window size entry
                    elif "_Size" in key:
                        # Extract window name and dimensions
                        window_name = key.replace("_Size", "")
                        width, height = value.split(", ")
                        window_sizes[window_name] = (int(width), int(height))

            # Update window positions and sizes in Dear PyGui if the windows exist
            for window_name, pos in window_positions.items():
                if dpg.does_item_exist(window_name):
                    dpg.set_item_pos(window_name, pos)
                    print(f"Loaded position for {window_name}: {pos}")
                else:
                    print(f"{window_name} does not exist in the current context.")

            for window_name, size in window_sizes.items():
                if dpg.does_item_exist(window_name):
                    dpg.set_item_width(window_name, size[0])
                    dpg.set_item_height(window_name, size[1])
                    print(f"Loaded size for {window_name}: {size}")
                else:
                    print(f"{window_name} does not exist in the current context.")

        except Exception as e:
            print(f"Error loading window positions and sizes: {e}")

    def cbx_disable_keyboard(self, app_data, user_data):
        if user_data:
            self.dev.KeyboardEnabled = False
        else:
            self.dev.KeyboardEnabled = True

    def ipt_large_step(self,app_data,user_data):
        ch=int(app_data[6])        
        self.dev.AxesKeyBoardLargeStep[ch]=int(user_data*self.dev.StepsIn1mm/1e3)
        print(self.dev.AxesKeyBoardLargeStep[ch])

    def ipt_small_step(self,app_data,user_data):
        ch=int(app_data[6])
        self.dev.AxesKeyBoardSmallStep[ch]=int(user_data*self.dev.StepsIn1mm/1e6)
        print(self.dev.AxesKeyBoardSmallStep[ch])

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

    # def load_points(self):
    #     try:
    #         themes = DpgThemes()
    #         yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))

    #         with open("map_config.txt", "r") as file:
    #             lines = file.readlines()

    #             # Clear the existing LoggedPoints
    #             self.dev.LoggedPoints = []
    #             loading_points = False

    #             for line in lines:
    #                 # Start loading points after finding "LoggedPoint"
    #                 if line.startswith(f"{self.prefix}LoggedPoint"):
    #                     loading_points = True
    #                     coords = line.split(": ")[1].split(", ")  # Process the logged point line

    #                     if len(coords) == 3:  # Ensure we have 3 coordinates
    #                         logged_point = (float(coords[0]), float(coords[1]), float(coords[2]))
    #                         self.dev.LoggedPoints.append(logged_point)

    #                         current_height = dpg.get_item_height(self.window_tag)
    #                         new_height = current_height + 30  # Increase height by 50 units
    #                         dpg.configure_item(self.window_tag, height=new_height)

    #                         # Check how many points have been logged and calculate u or v
    #                         if len(self.dev.LoggedPoints) == 3:
    #                             self.dev.calc_uv()
    #                             dpg.bind_item_theme(f"{self.prefix}_calc_uv", yellow_theme)

    #             # Update the logged points indicator and table
    #             dpg.set_value(f"{self.prefix}logged_points", "* " * len(self.dev.LoggedPoints))
    #             self.update_logged_points_table()
    #             print("Logged points loaded successfully.")

    #     except FileNotFoundError:
    #         print("map_config.txt not found.")
    #     except Exception as e:
    #         print(f"Error loading logged points: {e}")

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
                value1 = value1 / 10

            steps = int(direction * value1 / 1e3 * self.dev.StepsIn1mm)
            amount = [self.dev.U[i] * steps for i in range(3)] if ch == 0 else [self.dev.V[i] * steps for i in range(3)]
            print(amount)

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
        
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
        self.simulation = simulation
        self.dev.GetAvailableDevices()
        self.NumOfLoggedPoints = 0
        self.U = [1, 0, 0]
        self.V = [0, 1, 0]
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
                    dpg.add_button(label="load pos", callback=self.load_pos)

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
                with dpg.group(horizontal=False, tag="_column 4_", width=child_width*.8):
                    dpg.add_text(" Ref.")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Ref. " + str(ch))
                    dpg.add_button(label="Calc U",tag=f"{self.prefix}_calc_u",callback=self.btn_calc_u)

                with dpg.group(horizontal=False, tag="_column 5_", width=child_width*.8):
                    dpg.add_text("  Zero   ")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Zero " + str(ch), callback=self.btn_zero, user_data=ch)
                    dpg.add_button(label="Calc V",tag=f"{self.prefix}_calc_v", callback=self.btn_calc_v)

                with dpg.group(horizontal=False, tag="_column 6_", width=child_width *.8):
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
                    dpg.add_button(label="ToText", callback=self.generate_to_text)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="AutoFill", callback=self.AutoFill)
                        dpg.add_button(label="Load", callback=self.load_points)
                        dpg.bind_item_theme(dpg.last_item(), yellow_theme)

                with dpg.group(horizontal=False, tag="_column 7_", width=child_width):
                    dpg.add_text("Move Abs. (um)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_input_float(label="", default_value=0, tag=f"{self.prefix}_ch" + str(ch) + "_ABS", indent=-1,
                                                format='%.4f', width=150, step=1, step_fast=10) #
                    dpg.add_button(label="Save", callback=self.save_log_points)
                    dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                            
                with dpg.group(horizontal=False, tag="_column 8_", width=child_width*.8):
                    dpg.add_text("   GO")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="GO", callback=self.move_absolute, user_data=ch)
                    dpg.add_button(label = "Backup", callback = self.backup)

                with dpg.group(horizontal=False, tag="_column 9_", width=child_width):
                    dpg.add_text("    Home")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Home " + str(ch), callback=self.btn_move_to_home, user_data=ch,indent=10)
                    dpg.add_button(label="Copy latest", callback=self.copy_latest_timestamp_files)

                with dpg.group(horizontal=False, tag="_column 10_", width=child_width):
                    dpg.add_text("Status")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_combo(items=["idle",""], tag="mcs_Status" + str(ch))
                    dpg.add_button(label="save pos",callback=self.save_pos)

            with dpg.group(horizontal=True):
                dpg.add_combo(label="Devices", items=self.dev.Available_Devices_List, tag=f"{self.prefix}_device_selector",
                              callback=self.cmb_device_selector, width=300)
                dpg.add_button(label="Refresh", callback=self.btn_get_av_device_list)
                dpg.add_text(" Disable keyboard")
                dpg.add_checkbox(tag="mcs_Disable_Keyboard", callback=self.cbx_disable_keyboard)
            with dpg.group(horizontal=False, tag="table_group"):
                with dpg.table(header_row=True, tag=f"{self.prefix}logged_points_table", width=700):
                    dpg.add_table_column(label="Point")
                    dpg.add_table_column(label="X")
                    dpg.add_table_column(label="Y")
                    dpg.add_table_column(label="Z")
                    dpg.add_table_column(label="Delete")
                    dpg.add_table_column(label="Go Abs")

        self.load_points()
        # Set a callback to call load_pos after the first frame is rendered
        dpg.set_frame_callback(1, self.load_pos)

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
        # Dictionary to store window positions and dimensions
        window_positions = {}

        # Check if pico_Win exists and get its position and size
        if dpg.does_item_exist("pico_Win"):
            pico_win_pos = dpg.get_item_pos("pico_Win")
            pico_win_size = dpg.get_item_width("pico_Win"), dpg.get_item_height("pico_Win")
            window_positions["pico_Win"] = (pico_win_pos, pico_win_size)
            print(f"Position of pico_Win: {pico_win_pos}, Size: {pico_win_size}")

        # Check if mcs_Win exists and get its position and size
        if dpg.does_item_exist("mcs_Win"):
            mcs_win_pos = dpg.get_item_pos("mcs_Win")
            mcs_win_size = dpg.get_item_width("mcs_Win"), dpg.get_item_height("mcs_Win")
            window_positions["mcs_Win"] = (mcs_win_pos, mcs_win_size)
            print(f"Position of mcs_Win: {mcs_win_pos}, Size: {mcs_win_size}")

        # Check if Zelux Window exists and get its position and size
        if dpg.does_item_exist("Zelux Window"):
            zelux_win_pos = dpg.get_item_pos("Zelux Window")
            zelux_win_size = dpg.get_item_width("Zelux Window"), dpg.get_item_height("Zelux Window")
            window_positions["Zelux Window"] = (zelux_win_pos, zelux_win_size)
            print(f"Position of Zelux Window: {zelux_win_pos}, Size: {zelux_win_size}")

        # Check if OPX Window exists and get its position and size
        if dpg.does_item_exist("OPX Window"):
            opx_win_pos = dpg.get_item_pos("OPX Window")
            opx_win_size = dpg.get_item_width("OPX Window"), dpg.get_item_height("OPX Window")
            window_positions["OPX Window"] = (opx_win_pos, opx_win_size)
            print(f"Position of OPX Window: {opx_win_pos}, Size: {opx_win_size}")

        # Check if Map_window exists and get its position and size
        if dpg.does_item_exist("Map_window"):
            map_win_pos = dpg.get_item_pos("Map_window")
            map_win_size = dpg.get_item_width("Map_window"), dpg.get_item_height("Map_window")
            window_positions["Map_window"] = (map_win_pos, map_win_size)
            print(f"Position of Map_window: {map_win_pos}, Size: {map_win_size}")

        # Check if Scan_Window exists and get its position and size
        if dpg.does_item_exist("Scan_Window"):
            scan_win_pos = dpg.get_item_pos("Scan_Window")
            scan_win_size = dpg.get_item_width("Scan_Window"), dpg.get_item_height("Scan_Window")
            window_positions["Scan_Window"] = (scan_win_pos, scan_win_size)
            print(f"Position of Scan_Window: {scan_win_pos}, Size: {scan_win_size}")

        try:
            # Read existing map_config.txt content, if available
            try:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
            except FileNotFoundError:
                lines = []

            # Create a list to store the updated content
            new_content = []

            # Remove any existing window position and size entries
            for line in lines:
                if not any(win_name in line for win_name in window_positions.keys()):
                    new_content.append(line)

            # Append the new window positions and dimensions to the content
            for win_name, (position, size) in window_positions.items():
                new_content.append(f"{win_name}_Pos: {position[0]}, {position[1]}\n")
                new_content.append(f"{win_name}_Size: {size[0]}, {size[1]}\n")

            # Write back the updated content to the file
            with open("map_config.txt", "w") as file:
                file.writelines(new_content)

            print("Window positions and sizes saved successfully to map_config.txt.")
        except Exception as e:
            print(f"Error saving window positions and sizes: {e}")

    def load_pos(self):
        try:
            # Check if map_config.txt exists and read the contents
            if not os.path.exists("map_config.txt"):
                print("map_config.txt not found.")
                return

            # Dictionaries to store positions and sizes loaded from the file
            window_positions = {}
            window_sizes = {}

            with open("map_config.txt", "r") as file:
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

    def backup(self):
        """
            Back up files changed in the last 'days' from the source directory to the backup directory.
            """
        source_dir = r'C:\WC\HotSystem'
        backup_dirs = [r'C:\WC\HotSystem_Backups',  # First backup directory
            r'Q:\QT-Quantum_Optic_Lab\Shai-OpticsLab'  # Second backup directory
        ]
        days = 3  # Modify for how many days you want to look for recent changes

        # Get current time and calculate the threshold for recently modified files
        current_time = time.time()
        cutoff_time = current_time - (days * 86400)  # Convert days to seconds

        # Create a timestamp for the backup folder with only the date and hour
        timestamp = datetime.now().strftime('%Y-%m-%d_%H')

        # List of directories and file types to skip
        skip_dirs = ['__pycache__', '.svn', '.idea', 'Utils','.venv','venv','.vscode']
        skip_extensions = ['.dll']

        # Iterate over the list of backup directories
        for backup_dir_base in backup_dirs:
            backup_dir = os.path.join(backup_dir_base, f'Backup_{timestamp}')

            try:
                # Create backup directory if it doesn't exist
                if not os.path.exists(backup_dir):
                    os.makedirs(backup_dir)
            except OSError as e:
                print(f"An error occurred while creating the backup directory: {e}")
                return

            # Iterate over all files in the source directory
            for foldername, _, filenames in os.walk(source_dir):
                # Skip specified directories
                if any(skip_dir in foldername for skip_dir in skip_dirs):
                    continue

                for filename in filenames:
                    # Skip .dll files
                    if any(filename.endswith(ext) for ext in skip_extensions):
                        continue

                    # Get the full path of the file
                    file_path = os.path.join(foldername, filename)

                    # Get the file's last modified time
                    file_modified_time = os.path.getmtime(file_path)

                    # If the file was modified within the last 'n' days, back it up
                    if file_modified_time > cutoff_time:
                        # Create the corresponding path in the backup directory
                        relative_path = os.path.relpath(foldername, source_dir)
                        backup_subdir = os.path.join(backup_dir, relative_path)

                        if not os.path.exists(backup_subdir):
                            os.makedirs(backup_subdir)

                        # Copy the file and overwrite if it already exists
                        shutil.copy2(file_path, os.path.join(backup_subdir, filename))
                        print(f"Backed up: {file_path} -> {backup_subdir}")

        print("backup done.")

    def copy_latest_timestamp_files(self) -> None:
        """
        Copy all files with the latest timestamp from the source directory to the destination directory.
        The files will be copied to a folder named with the timestamp and file-specific information (e.g., 'DSM2').
        The destination folder format is <timestamp>_<file_info>, and the original filenames are retained.

        Source directory is always 'D:\\TempScanData' and the destination directory is always 'Q:\\QT-Quantum_Optic_Lab\\expData\\scan'.
        """
        # Define the fixed source and destination directories
        source_dir = r'D:\TempScanData'
        # source_dir = r'C:\Users\shai\Downloads\test'
        base_dest_dir = r'Q:\QT-Quantum_Optic_Lab\expData\scan'

        # Check if source directory exists
        if not os.path.exists(source_dir):
            print(f"Source directory '{source_dir}' does not exist. Aborting operation.")
            return

        # Pattern to extract timestamp and file-specific info (e.g., 'DSM2')
        file_pattern = re.compile(r'(\d{4}_\d{1,2}_\d{1,2}_\d{1,2}_\d{1,2}_\d{1,2})(scan_(\w+))')

        latest_timestamp = None
        latest_datetime = None  # Store the latest timestamp as a datetime object
        files_to_copy = []

        # Iterate over all files in the source directory
        for filename in os.listdir(source_dir):
            match = file_pattern.search(filename)
            if match:
                timestamp_str = match.group(1)  # Get the timestamp part
                file_info = match.group(3)  # Get the file-specific info part (e.g., 'DSM2')

                # Parse the timestamp string into a datetime object for proper comparison
                try:
                    timestamp_dt = datetime.strptime(timestamp_str, '%Y_%m_%d_%H_%M_%S')
                except ValueError:
                    print(f"Skipping file with invalid timestamp: {filename}")
                    continue

                # Determine if this is the latest timestamp we've found
                if latest_datetime is None or timestamp_dt > latest_datetime:
                    latest_timestamp = timestamp_str
                    latest_datetime = timestamp_dt
                    latest_file_info = file_info
                    files_to_copy = [filename]  # Start a new list of files for this timestamp
                elif timestamp_dt == latest_datetime:
                    files_to_copy.append(filename)  # Add to the list if the timestamp matches

        if not files_to_copy:
            print("No matching files found.")
            return

        # Create the destination folder with the latest timestamp and file info (e.g., 2024_9_12_19_1_1_DSM2)
        dest_dir = os.path.join(base_dest_dir, f'{latest_timestamp}_{latest_file_info}')
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)

        # Copy the files to the destination folder without renaming them
        for file in files_to_copy:
            source_path = os.path.join(source_dir, file)
            dest_path = os.path.join(dest_dir, file)
            shutil.copy2(source_path, dest_path)
            print(f"Copied: {source_path} -> {dest_path}")

        print("Done.")

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

    def generate_to_text(self):
        """Generate a formatted string for the logged points."""
        if self.dev.LoggedPoints:
            scaled_points = np.round(np.array(self.dev.LoggedPoints) * 1e6, decimals=0).astype(int)
            array_string = f"self.ZCalibrationData = np.array({scaled_points.tolist()})"
            print(array_string)

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

        self.dev.LoggedPoints.append(position.copy())  # [pm]
        self.NumOfLoggedPoints += 1
        print(self.dev.LoggedPoints)

        # Update the UI
        dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
        self.update_table()

        # Prepare the text to copy with only the last logged point and the increment line
        last_point = self.dev.LoggedPoints[-1]
        text_to_copy = f"self.dev.LoggedPoints.append({last_point})\nself.NumOfLoggedPoints += 1"
        
        print(text_to_copy)

        # Check the number of logged points and calculate vectors accordingly
        if len(self.dev.LoggedPoints) == 2:
            self.calc_vector('u')
            dpg.bind_item_theme(f"{self.prefix}_calc_u", yellow_theme)
        elif len(self.dev.LoggedPoints) == 3:
            self.calc_vector('v')
            dpg.bind_item_theme(f"{self.prefix}_calc_v", yellow_theme)

    def AutoFill(self):
        self.dev.LoggedPoints.append([0, 0, 700000])
        self.NumOfLoggedPoints += 1
        self.dev.LoggedPoints.append([940000327, 369, -5800002])
        self.NumOfLoggedPoints += 1
        self.calc_vector('u')
        self.dev.LoggedPoints.append([940000327, -766999940, -22899927])
        self.NumOfLoggedPoints += 1
        self.calc_vector('v')
        dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
        self.update_table()

    def load_points(self):
        try:
            themes = DpgThemes()
            yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))

            with open("map_config.txt", "r") as file:
                lines = file.readlines()

                # Clear the existing LoggedPoints
                self.dev.LoggedPoints = []
                self.NumOfLoggedPoints = 0  # Reset the count of logged points
                loading_points = False

                for line in lines:
                    # Start loading points after finding "LoggedPoint"
                    if line.startswith(f"{self.prefix}LoggedPoint"):
                        loading_points = True
                        coords = line.split(": ")[1].split(", ")  # Process the logged point line

                        if len(coords) == 3:  # Ensure we have 3 coordinates
                            logged_point = (float(coords[0]), float(coords[1]), float(coords[2]))
                            self.dev.LoggedPoints.append(logged_point)
                            self.NumOfLoggedPoints += 1

                            current_height = dpg.get_item_height(self.window_tag)
                            new_height = current_height + 30  # Increase height by 50 units
                            dpg.configure_item(self.window_tag, height=new_height)

                            # Check how many points have been logged and calculate u or v
                            if self.NumOfLoggedPoints == 2:
                                self.calc_vector('u')
                                dpg.bind_item_theme(f"{self.prefix}_calc_u", yellow_theme)
                            elif self.NumOfLoggedPoints == 3:
                                self.calc_vector('v')
                                dpg.bind_item_theme(f"{self.prefix}_calc_v", yellow_theme)

                # Update the logged points indicator and table
                dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
                self.update_table()
                print("Logged points loaded successfully.")

        except FileNotFoundError:
            print("map_config.txt not found.")
        except Exception as e:
            print(f"Error loading logged points: {e}")

    def save_log_points(self):
        # Read existing content from the file
        file_path = "map_config.txt"
        try:
            with open(file_path, "r") as file:
                lines = file.readlines()
        except FileNotFoundError:
            lines = []  # If the file doesn't exist, start with an empty list

        # Filter out old logged points
        filtered_lines = [line for line in lines if not line.startswith(f"{self.prefix}LoggedPoint:")]

        # Append new logged points
        with open(file_path, "w") as file:
            # Write back the filtered lines
            file.writelines(filtered_lines)

            # Add the new logged points from self.positioner
            for point in self.dev.LoggedPoints:
                file.write(f"{self.prefix}LoggedPoint: {point[0]}, {point[1]}, {point[2]}\n")

        print("Log points saved.")

    def update_table(self):
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
                # # Add a delete button in the last column
                # dpg.add_button(label="Delete", width=60, height=20, callback=lambda s=i - 1: self.delete_row(s))
                # Use partial to pass the correct index to the callback function
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
            self.NumOfLoggedPoints -= 1
            dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
            # Rebuild the table to reflect the change
            self.update_table()

    def btnDelPoint(self):
        current_height = dpg.get_item_height(self.window_tag)
        new_height = current_height - 30  # Increase height by 50 units
        dpg.configure_item(self.window_tag, height=new_height)

        if self.dev.IsConnected:
            self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
            self.NumOfLoggedPoints -= 1
            dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
            self.update_table()
        else:
            print("Cannot log point while Smaract is disconnected.")
            if self.simulation:
                random_numbers = [random.randint(-1000, 1000) for _ in range(3)]
                self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
                self.NumOfLoggedPoints -= 1
                dpg.set_value(f"{self.prefix}logged_points", "* " * self.NumOfLoggedPoints)
                self.update_table()

    def btn_calc_u(self):
        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        self.calc_vector('u')
        dpg.bind_item_theme(f"{self.prefix}_calc_u", yellow_theme)

    def btn_calc_v(self):
        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        self.calc_vector('v')
        dpg.bind_item_theme(f"{self.prefix}_calc_v", yellow_theme)

    def calc_vector(self, vector_name):
        if len(self.dev.LoggedPoints) < 2:
            print(f"Please log at least two points prior to calculating {vector_name.upper()}")
        else:
            print(f"Calculating {vector_name.upper()}")
            p1 = self.dev.LoggedPoints[-2]
            p2 = self.dev.LoggedPoints[-1]
            difference = [p2[i] - p1[i] for i in range(len(p1))]

            try:
                magnitude = math.sqrt(sum([component ** 2 for component in difference]))
                if magnitude == 0:
                    raise ValueError("The two points are identical, cannot compute vector.")

                normalized_vector = [component / magnitude for component in difference]

                if vector_name.lower() == 'u':
                    self.U = normalized_vector
                    print(self.U)
                elif vector_name.lower() == 'v':
                    self.V = normalized_vector
                    print(self.V)
                else:
                    print(f"Unknown vector name: {vector_name}")

            except ZeroDivisionError:
                print("Division by zero error encountered during vector normalization.")
            except ValueError as e:
                print(e)

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
            amount = [self.U[i] * steps for i in range(3)] if ch == 0 else [self.V[i] * steps for i in range(3)]
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
        
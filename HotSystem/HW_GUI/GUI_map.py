import math
import os
import pdb
import sys
import time
import traceback

import dearpygui.dearpygui as dpg
from functools import partial

import numpy as np

from Utils import calculate_z_series

class Map:
    def __init__(self,ZCalibrationData: np.ndarray | None = None, use_picomotor = False):
        # Initialize variables
        self.is_windows_shrunk = False
        self.win_size = [300, 900]
        self.disable_d_click = False
        self.click_coord = None
        self.clicked_position = None
        self.map_item_x = 0
        self.map_item_y = 0
        self.map_keyboard_enable = True
        self.move_mode = "marker"
        self.text_color = (0, 0, 0, 255)  # Set color to black
        self.active_marker_index = -1
        self.active_area_marker_index = -1

        self.area_markers = []
        self.Map_aspect_ratio = None
        self.markers = []

        self.maintain_aspect_ratio = True
        self.Map_aspect_ratio = 1.0
        self.use_picomotor = False
        self.b_Zcorrection = False
        self.text_color = "Black"
        self.map_click_callback_registered = False

        # Variables for image dimensions and data
        self.image_path = "Sample_map.png"
        self.width = 0
        self.height = 0
        self.channels = 0
        self.data = None

        self.ZCalibrationData = ZCalibrationData

        # Load map parameters
        self.use_picomotor, self.exp_notes = self.load_map_parameters()

    def delete_map_gui(self):
        self.delete_all_markers()
        dpg.delete_item("Sample_map_registry")
        dpg.delete_item("Map_window")
        # Unregister handlers
        if dpg.does_item_exist("handler_registry"):
            dpg.delete_item("handler_registry")

    def toggle_shrink_child_windows(self):
        """Toggle shrinking and expanding of child windows to make the map image more visible."""

        # Define child window tags
        child_windows_to_toggle = [
            "child_window_1",
            "child_window_2",  # Add all child window tags here
            "child_window_3",
            "child_window_4",
            "child_window_5"
        ]

        # Toggle between shrinking and expanding
        if self.is_windows_shrunk:
            child_width = int(self.win_size[0] * 0.45)
            child_height = int(self.win_size[1] * 0.5)
            # Expand child windows to original size
            for child_window in child_windows_to_toggle:
                if dpg.does_item_exist(child_window):
                    dpg.set_item_width(child_window,  child_width)  # Original width
                    dpg.set_item_height(child_window, child_height)  # Original height
            # Update button label
            dpg.set_item_label("toggle_shrink_button", "<<<")
            self.is_windows_shrunk = False
        else:
            # Shrink child windows
            child_width = int(self.win_size[0] * 0.15)
            child_height = int(self.win_size[1] * 0.5)
            for child_window in child_windows_to_toggle:
                if dpg.does_item_exist(child_window):
                    dpg.set_item_width(child_window, child_width)  # Shrunk width
                    dpg.set_item_height(child_window, child_height)  # Shrunk height
            # Update button label
            dpg.set_item_label("toggle_shrink_button", ">>>")
            self.is_windows_shrunk = True



    def create_map_gui(self, win_size, win_pos):
        self.win_size = win_size
        use_pico=False
        exp_notes=""

        # Check if the handler_registry already exists
        if not dpg.does_item_exist("handler_registry"):
            with dpg.handler_registry(tag="handler_registry"):
                dpg.add_mouse_click_handler(callback=self.map_click_callback)

        # Check if the file exists before loading the image
        if os.path.exists(self.image_path):
            with dpg.group(horizontal=False):
                with dpg.texture_registry(tag="Sample_map_registry"):
                    self.width, self.height, self.channels, self.data = dpg.load_image(self.image_path)
                    dpg.add_static_texture(self.width, self.height, self.data, tag="map_texture")
                    self.Map_aspect_ratio = self.width / self.height

                with dpg.window(label="Map Resizer", width=win_size[0], height=win_size[1]*3, tag="Map_window",
                                pos=[700, 5], horizontal_scrollbar=True, collapsed=True):
                    child_width = win_size[0]*0.45
                    child_height = win_size[1]*0.5
                    # Main horizontal group to separate controls and map
                    with dpg.group(horizontal=True):
                        # Left-hand side: Control panels
                        with dpg.group(horizontal=False):
                            # Group for map controls: Width, Height, and Aspect Ratio
                            with dpg.child_window(width=child_width, height=child_height,tag = "child_window_1",horizontal_scrollbar=True):
                                dpg.add_text("Map Size & Aspect Ratio Controls", bullet=True)
                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                                with dpg.group(horizontal=True):
                                    dpg.add_slider_int(label="Width", min_value=100, max_value=self.width * 3,
                                                       default_value=self.width, id="width_slider",
                                                       callback=self.resize_image, width=200)
                                    dpg.add_input_int(label="", default_value=self.width, id="width_input",
                                                      callback=self.resize_from_input, width=100)
                                    dpg.add_text("A.ratio")

                                with dpg.group(horizontal=True):
                                    dpg.add_slider_int(label="Height", min_value=100, max_value=self.height * 3,
                                                       default_value=self.height, id="height_slider",
                                                       callback=self.resize_image, width=200)
                                    dpg.add_input_int(label="", default_value=self.height, id="height_input",
                                                      callback=self.resize_from_input, width=100)
                                    dpg.add_button(label="ON", callback=self.toggle_aspect_ratio)

                                dpg.add_button(label="<<<", tag="toggle_shrink_button", callback=self.toggle_shrink_child_windows)

                            # Group for Offset Controls
                            with dpg.child_window(width=child_width, height=child_height*1.2, tag = "child_window_2",horizontal_scrollbar=True):
                                dpg.add_text("Offset Controls", bullet=True)
                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                with dpg.group(horizontal=True):
                                    dpg.add_input_float(label="OffsetX", tag="MapOffsetX", indent=-1,
                                                        width=150, default_value=0, step=0.01, step_fast=1)
                                    dpg.add_input_float(label="OffsetY", tag="MapOffsetY", indent=-1,
                                                        width=150, default_value=0, step=0.01, step_fast=1)
                                    dpg.add_button(label="Set 0", callback=self.set_marker_coord_to_zero)

                                with dpg.group(horizontal=True):
                                    dpg.add_input_float(label="FactorX", tag="MapFactorX", indent=-1,
                                                        width=150, default_value=1, step=0.01, step_fast=1)
                                    dpg.add_input_float(label="FactorY", tag="MapFactorY", indent=-1,
                                                        width=150, default_value=1, step=0.01, step_fast=1)

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="Set Gap", callback=self.map_set_gap)
                                    dpg.add_input_int(label="", tag="MapSetGap", indent=-1, width=130,
                                                      min_value=1, default_value=10, step=10, step_fast=100)
                                    dpg.add_button(label="x", callback=self.toggle_set_x_or_y,
                                                   tag="toggle_set_x_or_y")
                                    dpg.add_input_float(label="Move Step", tag="MapMoveStep", indent=-1,
                                                        width=150, default_value=1, step=1, step_fast=100)
                                dpg.add_text("Click map for coordinates", tag="coordinates_text")
                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                            # Group for marking points, areas, and update scan
                            with dpg.child_window(width=child_width, height=child_height, tag = "child_window_3",horizontal_scrollbar=True):
                                dpg.add_text("Marker & Scan Controls", bullet=True)
                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="Mark Point", callback=self.mark_point_on_map)
                                    dpg.add_button(label="Mark Area", callback=partial(self.start_rectangle_query, False))
                                    dpg.add_button(label="Area + Center", callback=partial(self.start_rectangle_query, True))
                                    dpg.add_button(label="Find Middle", callback=self.find_middle)
                                    dpg.add_button(label="Black", tag="toggle_text_color", callback=self.toggle_text_color)

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="Delete Last Mark", callback=self.delete_last_mark)
                                    dpg.add_button(label="Delete All Markers", callback=self.delete_all_markers)
                                    dpg.add_button(label="Delete All Except Active", callback=self.delete_all_except_active)

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="Break area to ", callback=self.break_area)
                                    dpg.add_input_int(label="", tag="BreakAreaSize", indent=-1,
                                                      width=150, min_value=50, default_value=60, step=1, step_fast=10)
                                    dpg.add_button(label="Scan All Area Markers", callback=self.scan_all_area_markers)
                                    dpg.bind_item_theme(dpg.last_item(), theme="btnYellowTheme")
                                    dpg.add_checkbox(label="Pico", tag="checkbox_map_use_picomotor", indent=-1,
                                                     callback=self.toggle_use_picomotor, default_value=self.use_picomotor)

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="Save", callback=self.save_map_parameters)
                                    dpg.add_button(label="Load", callback=self.load_map_parameters)
                                    dpg.add_input_int(label="# digits", tag="MapNumOfDigits", indent=-1,
                                                      width=150, min_value=0, default_value=1, step=1,
                                                      step_fast=100, callback=self.btn_num_of_digits_change)
                                    dpg.add_button(label="Fix area", callback=self.fix_area)
                                    dpg.add_checkbox(label="Disable d.click",tag="checkbox_disable_d_click", callback=self.toggle_disable_d_click, default_value=self.disable_d_click)

                            # Group for marker movement buttons
                            with dpg.child_window(width=child_width, height=child_height, tag = "child_window_4",horizontal_scrollbar=True):
                                dpg.add_text("Marker Movement Controls", bullet=True)
                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="move marker", callback=self.toggle_marker_area, tag="toggle_marker_area")
                                    dpg.add_button(label="Map Keys: Enabled", tag="toggle_map_keyboard",
                                                   callback=self.toggle_map_keyboard)

                                    with dpg.collapsing_header(label="Keyboard Shortcuts", default_open=False):
                                        dpg.add_text("The following keys can be used to interact with markers and area markers:")
                                        dpg.add_separator()
                                        dpg.add_text("Ctrl + M : Enable/disable map keyboard shortcuts")
                                        dpg.add_text("M(Coarse) / N(Fine) + arrow keys: Shift marker/area marker")
                                        dpg.add_text("M/N + PageDown: Stretch vertically (Y-axis) - Coarse mode is supported")
                                        dpg.add_text("M/N + PageUp: Squeeze vertically (Y-axis) - Coarse mode is supported")
                                        dpg.add_text("M/N + Home: Squeeze horizontally (X-axis) - Coarse mode is supported")
                                        dpg.add_text("M/N + End: Stretch horizontally (X-axis) - Coarse mode is supported")
                                        dpg.add_text("Del: Delete active marker or area marker")
                                        dpg.add_text("M + Insert: Insert a new marker or area marker near the active marker")
                                        dpg.add_text("N + Insert: insert an area marker.")
                                        dpg.add_text("M/N + Del : Delete active marker or area marker")
                                        dpg.add_text("M + K : move marker")
                                        dpg.add_text("M + A : move area")
                                        dpg.add_text("M + + : Activate marker/area marker above current active")
                                        dpg.add_text("M + - : Activate marker/area marker below current active")
                                        dpg.add_text("M/N + U : Update scan area from active area")
                                        dpg.add_text("M/N + P : Mark point on map")
                                        dpg.add_text("M + G : Go")
                                        dpg.add_text("N + G : Go & activate next")

                                width = 50
                                height = 40
                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="^", width=width, height=height,
                                                   callback=lambda: self.move_active_marker("up"))
                                    dpg.add_button(label="^^", width=width, height=height,
                                                   callback=lambda: self.move_active_marker("up up"))
                                    dpg.add_button(label="vv", width=width, height=height,
                                                   callback=lambda: self.move_active_marker("down down"))
                                    dpg.add_button(label="<<", width=width, height=height,
                                                   callback=lambda: self.move_active_marker("left left"))
                                    dpg.add_button(label="<---> X", width=120, height=height,
                                                   callback=lambda: self.stretch_squeeze_area_marker("stretch_x"))
                                    dpg.add_button(label="-> <- X", width=120, height=height,
                                                   callback=lambda: self.stretch_squeeze_area_marker("squeeze_x"))

                                with dpg.group(horizontal=True):
                                    dpg.add_button(label="<", width=width, height=round(height),
                                                   callback=lambda: self.move_active_marker("left"))
                                    dpg.add_button(label="v", width=width, height=round(height),
                                                   callback=lambda: self.move_active_marker("down"))
                                    dpg.add_button(label=">", width=width, height=round(height),
                                                   callback=lambda: self.move_active_marker("right"))
                                    dpg.add_button(label=">>", width=width, height=round(height),
                                                   callback=lambda: self.move_active_marker("right right"))
                                    dpg.add_button(label=" ^  Y\n v ", width=120, height=round(height),
                                                   callback=lambda: self.stretch_squeeze_area_marker("stretch_y"))
                                    dpg.add_button(label=" v  Y\n ^", width=120, height=round(height),
                                                   callback=lambda: self.stretch_squeeze_area_marker("squeeze_y"))

                            # Table for displaying markers
                            with dpg.child_window(width=child_width, height=900, tag = "child_window_5",horizontal_scrollbar=True):
                                with dpg.group(horizontal=True):
                                    dpg.add_text("Markers Table   ", bullet=True)
                                    dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                    dpg.add_button(label="Marker Up", callback=self.shift_marker_up)
                                    dpg.add_button(label="Marker Down", callback=self.shift_marker_down)
                                    dpg.add_button(label="Area Up", callback=self.shift_area_marker_up)
                                    dpg.add_button(label="Area Down", callback=self.shift_area_marker_down)

                                with dpg.table(header_row=True, tag="markers_table", width=child_width-20):
                                    dpg.add_table_column(label="ID")
                                    dpg.add_table_column(label="rel X")
                                    dpg.add_table_column(label="rel Y")
                                    dpg.add_table_column(label="rel Z")
                                    dpg.add_table_column(label="")
                                    dpg.add_table_column(label="")
                                    dpg.add_table_column(label="Action")
                                    dpg.add_table_column(label="")
                                    dpg.add_table_column(label="")

                        # Right-hand side: Map display
                        with dpg.group(horizontal=False):
                            # Display the map image
                            dpg.add_image("map_texture", width=self.width, height=self.height, tag="map_image")
                            dpg.add_draw_layer(tag="map_draw_layer", parent="Map_window")
        else:
            print(f"{self.image_path} does not exist")

        use_pico, exp_notes = self.load_map_parameters()  # load map parameters
        self.toggle_shrink_child_windows()
        return use_pico, exp_notes

    # Placeholder methods for the callbacks used in the GUI
    def fix_area(self):
        try:

            # Get the break_size from the input field
            break_size = dpg.get_value("BreakAreaSize")

            if break_size <= 0:
                print("Invalid break area size.")
                return

            if self.active_area_marker_index is None or self.active_area_marker_index >= len(self.area_markers):
                print("No active area marker to fix.")
                return

            # Get the active rectangle (relative coordinates and Z scan info)
            active_rectangle = self.area_markers[self.active_area_marker_index]
            min_x, min_y, max_x, max_y, z_scan_info = active_rectangle[:5]

            # Calculate the current width and height
            width = max_x - min_x
            height = max_y - min_y

            # Calculate the number of full squares needed to cover the rectangle
            num_hor_squares = math.ceil(width / break_size)
            num_ver_squares = math.ceil(height / break_size)

            # Calculate the new width and height
            new_width = num_hor_squares * break_size
            new_height = num_ver_squares * break_size

            # Adjust max_x and max_y to get the new dimensions
            max_x = min_x + new_width
            max_y = min_y + new_height

            # Update the rectangle in area_markers
            self.area_markers[self.active_area_marker_index] = (min_x, min_y, max_x, max_y, z_scan_info)

            # Remove the existing rectangle from the map
            tag = f"query_rectangle_{self.active_area_marker_index}"
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

            # Convert the relative coordinates to absolute for drawing on the map
            min_x_abs = min_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value("MapOffsetX")
            max_x_abs = max_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value("MapOffsetX")
            min_y_abs = min_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value("MapOffsetY")
            max_y_abs = max_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value("MapOffsetY")

            # Draw the new rectangle on the map
            dpg.draw_rectangle(pmin=(min_x_abs, min_y_abs), pmax=(max_x_abs, max_y_abs),
                               color=(0, 255, 0, 255),
                               thickness=2, parent="map_draw_layer", tag=tag)

            # Update markers table and highlight the active rectangle
            self.update_markers_table()
            self.highlight_active_rectangle()

            print(f"Active area marker adjusted to integer multiples of break size {break_size}.")

        except Exception as e:
            print(f"Error fixing area: {e}")

    def toggle_text_color(self, sender):
        """Toggle between cyan and black for marker text color."""
        current_label = dpg.get_item_label(sender)

        if current_label == "Cyan":
            dpg.configure_item(sender, label="Black")
            self.text_color = (0, 0, 0, 255)  # Set color to black
        else:
            dpg.configure_item(sender, label="Cyan")
            self.text_color = (0, 255, 255, 255)  # Set color to cyan

        self.update_marker_texts()

    def toggle_map_keyboard(self):
        """Toggle between enable and disable using tag instead of sender."""
        current_label = dpg.get_item_label("toggle_map_keyboard")

        if current_label == "Map Keys: Disabled":
            dpg.configure_item("toggle_map_keyboard", label="Map Keys: Enabled")
            self.map_keyboard_enable = True
        else:
            dpg.configure_item("toggle_map_keyboard", label="Map Keys: Disabled")
            self.map_keyboard_enable = False

    def start_rectangle_query(self, add_center_point_marker=False):
        if len(self.markers) < 2:
            print("Not enough markers to create a rectangle.")
            return

        # Determine which markers to use for the rectangle
        if self.active_marker_index is not None and 0 <= self.active_marker_index < len(self.markers):
            # Use the active marker and the one above it if it exists, otherwise the one below it
            active_marker_pos = self.markers[self.active_marker_index][3]  # Get clicked position of active marker
            if self.active_marker_index > 0:
                second_marker_pos = self.markers[self.active_marker_index - 1][3]  # Marker above the active one
            else:
                second_marker_pos = self.markers[self.active_marker_index + 1][3]  # Marker below the active one
        else:
            # No active marker, use the last two markers as before
            active_marker_pos = self.markers[-1][3]
            second_marker_pos = self.markers[-2][3]

        # Calculate the min and max positions for the rectangle
        min_x = min(active_marker_pos[0], second_marker_pos[0])
        min_y = min(active_marker_pos[1], second_marker_pos[1])
        max_x = max(active_marker_pos[0], second_marker_pos[0])
        max_y = max(active_marker_pos[1], second_marker_pos[1])

        # Use the relative coordinates directly from the markers
        relative_min_x = min(self.markers[self.active_marker_index][2][0], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][0])
        relative_min_y = min(self.markers[self.active_marker_index][2][1], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][1])
        relative_max_x = max(self.markers[self.active_marker_index][2][0], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][0])
        relative_max_y = max(self.markers[self.active_marker_index][2][1], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][1])

        # Store the rectangle in self.area_markers with Z scan disabled by default
        rectangle = (relative_min_x, relative_min_y, relative_max_x, relative_max_y, "Z scan disabled")

        # Check if the rectangle already exists
        for existing_rectangle in self.area_markers:
            if all(abs(existing_rectangle[i] - rectangle[i]) < 1e-6 for i in range(4)):
                print("Rectangle already exists.")
                return 1  # Prevent adding a duplicate rectangle

        # If not, append the new rectangle
        self.area_markers.append(rectangle)

        # Get the index of the last rectangle added (zero-based indexing)
        rect_index = len(self.area_markers) - 1

        # Remove any existing rectangle with the same tag
        tag = f"query_rectangle_{rect_index}"

        # If the tag exists, delete the previous rectangle
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
            print(f"Existing rectangle with tag {tag} deleted.")

        # Set the newly created rectangle as the active one
        self.active_area_marker_index = rect_index

        # Draw a rectangle based on the two marker positions
        dpg.draw_rectangle(pmin=(min_x, min_y), pmax=(max_x, max_y), color=(0, 255, 0, 255), thickness=2,
                           parent="map_draw_layer", tag=tag)

        # Highlight the active rectangle (change color to magenta)
        self.highlight_active_rectangle()

        # Update the table to reflect the new rectangle
        self.update_markers_table()

        self.move_mode = "area_marker"
        # Update the button label to indicate the current state
        dpg.set_item_label("toggle_marker_area", "move area")

        print(f"Rectangle {rect_index} drawn and added to area_markers.")

        # --- ADDING CENTER POINT MARKER ---
        if add_center_point_marker:
            # Calculate the center of the rectangle (absolute coordinates)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2

            # Convert the absolute coordinates to relative coordinates
            relative_center_x = (center_x - self.map_item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
            relative_center_y = (center_y - self.map_item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

            # Calculate Z value (if needed, otherwise set to 0)
            z_center = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_center_x * 1e6)),
                                                int(relative_center_y * 1e6))) / 1e6

            # Mark the center point on the map using absolute coordinates
            self.clicked_position = (center_x, center_y)  # Use absolute coordinates for clicked position
            self.click_coord = (relative_center_x, relative_center_y, z_center)  # Store relative coordinates
            self.mark_point_on_map()  # Call the existing function to mark the point

    def break_area(self):
        try:
            # Get the size of the smaller squares from the input field
            break_size = dpg.get_value("BreakAreaSize")

            if self.active_area_marker_index is None or self.active_area_marker_index >= len(self.area_markers):
                print("No active area marker to break.")
                return

            # Get the active rectangle (relative coordinates and Z scan info)
            active_rectangle = self.area_markers[self.active_area_marker_index]
            min_x, min_y, max_x, max_y, z_scan_info = active_rectangle[:5]

            # Calculate the width and height of the rectangle
            width = max_x - min_x
            height = max_y - min_y

            if break_size <= 0:
                print("Invalid break area size.")
                return

            # Calculate the number of full horizontal and vertical squares
            num_hor_squares = width // break_size
            num_ver_squares = height // break_size

            # Break the rectangle into smaller squares
            for i in range(int(num_hor_squares) + 1):  # +1 to handle edge cases
                for j in range(int(num_ver_squares) + 1):  # +1 to handle edge cases
                    # Calculate the small rectangle boundaries
                    small_min_x = min_x + i * break_size
                    small_max_x = min(small_min_x + break_size, max_x)  # Ensure it doesn't go past max_x
                    small_min_y = min_y + j * break_size
                    small_max_y = min(small_min_y + break_size, max_y)  # Ensure it doesn't go past max_y

                    # Create the smaller rectangle with the same Z scan value as the original area marker
                    small_rectangle = (small_min_x, small_min_y, small_max_x, small_max_y, z_scan_info)

                    # Check if the smaller rectangle already exists
                    if any(all(abs(existing_rectangle[k] - small_rectangle[k]) < 1e-6 for k in range(4)) for
                           existing_rectangle in self.area_markers):
                        print(f"Small rectangle ({i},{j}) already exists.")
                        continue

                    # Add the new smaller rectangle to area_markers
                    self.area_markers.append(small_rectangle)

                    # Convert the relative coordinates to absolute for drawing on the map
                    min_x_abs = small_min_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value(
                        "MapOffsetX")
                    max_x_abs = small_max_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value(
                        "MapOffsetX")
                    min_y_abs = small_min_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value(
                        "MapOffsetY")
                    max_y_abs = small_max_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value(
                        "MapOffsetY")

                    # Draw the smaller rectangle on the map
                    tag = f"query_rectangle_{len(self.area_markers) - 1}"
                    dpg.draw_rectangle(pmin=(min_x_abs, min_y_abs), pmax=(max_x_abs, max_y_abs),
                                       color=(0, 255, 0, 255),
                                       thickness=2, parent="map_draw_layer", tag=tag)

            # Update the markers table and active area marker state
            self.update_markers_table()
            print(
                f"Rectangle split into {int(num_hor_squares) + 1}x{int(num_ver_squares) + 1} smaller rectangles with Z scan: {z_scan_info}.")

        except Exception as e:
            print(f"Error breaking area: {e}")

    def update_scan_area_marker(self, index):
        """Update scan parameters based on the selected area marker."""
        if index < len(self.area_markers):
            # Get the selected rectangle from area_markers by index, including Z scan state
            selected_rectangle = self.area_markers[index]
            min_x, min_y, max_x, max_y, z_scan_state = selected_rectangle

            # Calculate the width and height of the rectangle
            Lx_scan = int(max_x - min_x) * 1e3  # Convert to micrometers
            Ly_scan = int(max_y - min_y) * 1e3  # Convert to micrometers
            X_pos = (max_x + min_x) / 2
            Y_pos = (max_y + min_y) / 2

            # Calculate the Z evaluation
            z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array([int(X_pos * 1e6)]),
                                                    int(Y_pos * 1e6))) / 1e6

            # Call Update_Lx_Scan and Update_Ly_Scan with the calculated values
            dpg.set_value(item="inInt_Lx_scan", value=Lx_scan)
            dpg.set_value(item="inInt_Ly_scan", value=Ly_scan)
            print(Lx_scan)
            print(Ly_scan)

            # Update MCS fields with the new absolute positions
            point = (X_pos * 1e6, Y_pos * 1e6, z_evaluation * 1e6)
            print(point)
            for ch, value in enumerate(point):
                if self.use_picomotor:
                    dpg.set_value(f"pico_ch{ch}_ABS", value / 1e6)
                else:
                    dpg.set_value(f"mcs_ch{ch}_ABS", value / 1e6)

            # Toggle Z scan state based on z_scan_state
            print(z_scan_state)

        else:
            print("Invalid area marker index or no area markers available.") # NE

    def toggle_aspect_ratio(self, sender, app_data, user_data):
        self.maintain_aspect_ratio = not self.maintain_aspect_ratio

        # Update the button label to indicate the current state
        if self.maintain_aspect_ratio:
            dpg.set_item_label(sender, "ON")
        else:
            dpg.set_item_label(sender, "OFF")

    def toggle_marker_area(self, sender):
        """Toggle between moving markers and area markers."""
        if not hasattr(self, 'move_mode'):
            self.move_mode = "marker"  # Initialize with marker mode
        self.move_mode = "area_marker" if self.move_mode == "marker" else "marker"
        print(f"Mode switched to {self.move_mode}")

        # Update the button label to indicate the current state
        if self.move_mode == "area_marker":
            dpg.set_item_label(sender, "move area")
        else:
            dpg.set_item_label(sender, "move marker")

    def move_active_marker(self, direction):
        """Move the active marker or area marker in a given direction."""
        try:
            move_step = dpg.get_value("MapMoveStep")  # Define the movement step size

            print(self.move_mode)

            # Check if there is a map image and get its position
            if dpg.does_item_exist("map_image"):
                item_x, item_y = dpg.get_item_pos("map_image")
            else:
                print("map_image does not exist")
                item_x = 0
                item_y = 0

            # Check which mode is active: marker or area_marker
            if self.move_mode == "marker":
                # Check if there is an active marker
                if not hasattr(self, 'active_marker_index') or self.active_marker_index < 0:
                    print("No active marker to move.")
                    return

                if len(self.markers) == 0:
                    print("No markers to move.")
                    return

                # Get the active marker and its associated text and coordinates
                marker_tag, text_tag, relative_coords, clicked_position = self.markers[self.active_marker_index]
                abs_x, abs_y = clicked_position

            elif self.move_mode == "area_marker":
                # Check if there is an active area marker
                if not hasattr(self, 'active_area_marker_index') or self.active_area_marker_index < 0:
                    print("No active area marker to move.")
                    return

                if len(self.area_markers) == 0:
                    print("No area markers to move.")
                    return

                # Get the active area marker's relative coordinates
                rel_min_x, rel_min_y, rel_max_x, rel_max_y, z_enable = self.area_markers[self.active_area_marker_index]

                # Calculate absolute coordinates based on relative coordinates, item position, and map factors
                abs_min_x = rel_min_x / dpg.get_value("MapFactorX") + dpg.get_value("MapOffsetX") + item_x
                abs_min_y = rel_min_y / dpg.get_value("MapFactorY") + dpg.get_value("MapOffsetY") + item_y
                abs_max_x = rel_max_x / dpg.get_value("MapFactorX") + dpg.get_value("MapOffsetX") + item_x
                abs_max_y = rel_max_y / dpg.get_value("MapFactorY") + dpg.get_value("MapOffsetY") + item_y

                abs_x, abs_y = abs_min_x, abs_min_y  # Use absolute coordinates for movement

            # Move the marker or area marker based on the direction
            if direction == "up":
                abs_y -= move_step
            elif direction == "up up":
                abs_y -= move_step * 10
            elif direction == "down":
                abs_y += move_step
            elif direction == "down down":
                abs_y += move_step * 10
            elif direction == "left":
                abs_x -= move_step
            elif direction == "left left":
                abs_x -= move_step * 10
            elif direction == "right":
                abs_x += move_step
            elif direction == "right right":
                abs_x += move_step * 10

            if self.move_mode == "marker":
                # Update the marker's position on the map
                dpg.configure_item(marker_tag, center=(abs_x, abs_y))

                if self.ZCalibrationData is None:
                    print("No Z calibration data.")
                    return 1

                # Calculate the relative position of the click on the map
                relative_x = (abs_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                relative_y = (abs_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
                z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x * 1e6)),
                                                        int(relative_y * 1e6))) / 1e6

                # Retrieve the number of digits from the input field
                num_of_digits = dpg.get_value("MapNumOfDigits")

                # Update the format string to use the retrieved number of digits
                coord_text = f"({relative_x:.{num_of_digits}f}, {relative_y:.{num_of_digits}f}, {z_evaluation:.{num_of_digits}f})"

                dpg.configure_item(text_tag, pos=(abs_x, abs_y), text=coord_text)

                # Update the stored relative coordinates for the marker
                self.markers[self.active_marker_index] = (
                    marker_tag, text_tag, (relative_x, relative_y, z_evaluation), (abs_x, abs_y))

            elif self.move_mode == "area_marker":
                # Update the area marker's absolute position
                new_abs_min_x = abs_x
                new_abs_min_y = abs_y
                new_abs_max_x = abs_max_x + (abs_x - abs_min_x)
                new_abs_max_y = abs_max_y + (abs_y - abs_min_y)

                # Recalculate relative coordinates for storage
                new_rel_min_x = (new_abs_min_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                new_rel_min_y = (new_abs_min_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
                new_rel_max_x = (new_abs_max_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                new_rel_max_y = (new_abs_max_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

                # Update the area marker in the area_markers list with relative coordinates
                self.area_markers[self.active_area_marker_index] = (
                    new_rel_min_x, new_rel_min_y, new_rel_max_x, new_rel_max_y, z_enable)

                # Update the drawn rectangle
                dpg.configure_item(f"query_rectangle_{self.active_area_marker_index}",
                                   pmin=(new_abs_min_x, new_abs_min_y), pmax=(new_abs_max_x, new_abs_max_y))

            # Update the table after moving
            self.update_markers_table()

        except Exception as ex:
            self.error = f"Unexpected error: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def stretch_squeeze_area_marker(self, direction, is_coarse=False):
        """Stretch or squeeze the active area marker in X or Y direction, with coarse option."""
        # Automatically switch to area_marker mode
        self.move_mode = "area_marker"

        # Update the button label to indicate the current state
        if dpg.does_item_exist("toggle_marker_area"):
            dpg.set_item_label("toggle_marker_area", "move area")

        if not hasattr(self, 'active_area_marker_index') or self.active_area_marker_index < 0:
            print("No active area marker to stretch or squeeze.")
            return

        if len(self.area_markers) == 0:
            print("No area markers to modify.")
            return

        # Get the active area marker's relative coordinates
        rel_min_x, rel_min_y, rel_max_x, rel_max_y, z_enable = self.area_markers[self.active_area_marker_index]

        move_step = dpg.get_value("MapMoveStep")  # Define the movement step size for stretching/squeezing
        if is_coarse:
            move_step *= 10  # Coarse movement is 10 times bigger

        # Stretch or squeeze the area marker based on the direction
        if direction == "stretch_x":
            rel_max_x += move_step  # Stretch horizontally by increasing max_x
        elif direction == "squeeze_x":
            rel_max_x -= move_step  # Squeeze horizontally by decreasing max_x
        elif direction == "stretch_y":
            rel_max_y += move_step  # Stretch vertically by increasing max_y
        elif direction == "squeeze_y":
            rel_max_y -= move_step  # Squeeze vertically by decreasing max_y

        # Update the area marker's relative coordinates
        self.area_markers[self.active_area_marker_index] = (rel_min_x, rel_min_y, rel_max_x, rel_max_y, z_enable)

        # Recalculate absolute coordinates for rendering
        if dpg.does_item_exist("map_image"):
            item_x, item_y = dpg.get_item_pos("map_image")
        else:
            item_x, item_y = 0, 0

        abs_min_x = rel_min_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
        abs_min_y = rel_min_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")
        abs_max_x = rel_max_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
        abs_max_y = rel_max_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")

        # Update the drawn rectangle on the map
        dpg.configure_item(f"query_rectangle_{self.active_area_marker_index}",
                           pmin=(abs_min_x, abs_min_y), pmax=(abs_max_x, abs_max_y))

        # Update the table after modifying the area marker
        self.update_markers_table()

        print(f"Active area marker {direction} in {'coarse' if is_coarse else 'fine'} mode.")

    def save_map_parameters(self):
        try:
            # Try to read the existing file content, if it doesn't exist, create an empty list
            try:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
            except FileNotFoundError:
                lines = []

            # Create a list to store the new content
            new_content = []
            device_section = False  # Flag to track the device states section

            # Iterate through the existing lines and skip the map-related parameters
            for line in lines:
                if any(param in line for param in
                       ["OffsetX", "OffsetY", "FactorX", "FactorY", "MoveStep", "NumOfDigits", "ImageWidth",
                        "ImageHeight", "Exp_notes", "Marker", "Rectangle", "use_picomotor", "disable_d_click", "is_windows_shrunk"]):
                    # Skip lines that will be replaced by the new map parameters, points, and markers
                    continue
                new_content.append(line)

            # Add new map parameters, point markers, and rectangles
            new_content.append(f"OffsetX: {dpg.get_value('MapOffsetX')}\n")
            new_content.append(f"OffsetY: {dpg.get_value('MapOffsetY')}\n")
            new_content.append(f"FactorX: {dpg.get_value('MapFactorX')}\n")
            new_content.append(f"FactorY: {dpg.get_value('MapFactorY')}\n")
            new_content.append(f"MoveStep: {dpg.get_value('MapMoveStep')}\n")
            new_content.append(f"NumOfDigits: {dpg.get_value('MapNumOfDigits')}\n")
            new_content.append(f"ImageWidth: {dpg.get_value('width_slider')}\n")
            new_content.append(f"ImageHeight: {dpg.get_value('height_slider')}\n")
            new_content.append(f"Exp_notes: {dpg.get_value('inTxtScan_expText')}\n")
            new_content.append(f"disable_d_click: {self.disable_d_click}\n")
            new_content.append(f"is_windows_shrunk: {self.is_windows_shrunk}\n")

            # Save the use_picomotor state
            new_content.append(f"use_picomotor: {self.use_picomotor}\n")

            # Save point markers data with both clicked position and relative coordinates
            for marker in self.markers:
                marker_tag, text_tag, relative_coords, clicked_position = marker
                new_content.append(
                    f"Marker: {relative_coords[0]}, {relative_coords[1]}, {relative_coords[2]}, {clicked_position[0]}, {clicked_position[1]}\n")

            # Save rectangles from self.area_markers
            for rect in self.area_markers:
                new_content.append(f"Rectangle: {rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}, {rect[4]}\n")

            # Write back the updated content to the file
            with open("map_config.txt", "w") as file:
                file.writelines(new_content)

            print("Map parameters, point markers, and rectangles saved without touching device states.")

        except Exception as e:
            print(f"Error saving map parameters: {e}")

    def load_map_parameters(self):
        try:
            exp_notes = ""
            # Dictionaries to store positions and sizes loaded from the file
            window_positions = {}
            window_sizes = {}

            # Check if the configuration file exists
            with open("map_config.txt", "r") as file:
                lines = file.readlines()
                for line in lines:
                    # Split the line and check if it has the correct format
                    parts = line.split(": ")
                    if len(parts) < 2:
                        continue  # Skip lines that don't have the expected format

                    key = parts[0]
                    value = parts[1].strip()  # Remove any extra whitespace

                    # Load experimental notes
                    if key == "Exp_notes":
                        exp_notes = value
                        if dpg.does_item_exist("inTxtScan_expText"):
                            dpg.set_value("inTxtScan_expText", value)  # Update the input text widget with the loaded notes

                    elif key == "use_picomotor":
                        self.use_picomotor = value.lower() == "true"  # Convert to boolean
                        if dpg.does_item_exist("checkbox_map_use_picomotor"):
                            dpg.set_value("checkbox_map_use_picomotor", self.use_picomotor)

                    elif key == "disable_d_click":
                        self.disable_d_click = value.lower() == "true"
                        if dpg.does_item_exist("checkbox_map_disable_d_click"):
                            dpg.set_value("checkbox_map_disable_d_click", self.disable_d_click)

                    elif key == "is_windows_shrunk":
                        self.is_windows_shrunk = value.lower() == "true"
                        if dpg.does_item_exist("checkbox_map_is_windows_shrunk"):
                            dpg.set_value("checkbox_map_is_windows_shrunk", self.is_windows_shrunk)

                    # Check if the key is a window position entry
                    elif "_Pos" in key:
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

            if not dpg.does_item_exist("map_image"):
                print("map image does not exist.")
            else:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
                    for line in lines:
                        # Split the line and check if it has the correct format
                        parts = line.split(": ")
                        if len(parts) < 2:
                            continue  # Skip lines that don't have the expected format

                        key = parts[0]
                        value = parts[1].strip()  # Remove any extra whitespace

                        if key == "OffsetX":
                            dpg.set_value("MapOffsetX", float(value))
                        elif key == "OffsetY":
                            dpg.set_value("MapOffsetY", float(value))
                        elif key == "FactorX":
                            dpg.set_value("MapFactorX", float(value))
                        elif key == "FactorY":
                            dpg.set_value("MapFactorY", float(value))
                        elif key == "MoveStep":
                            dpg.set_value("MapMoveStep", float(value))
                        elif key == "NumOfDigits":
                            dpg.set_value("MapNumOfDigits", int(value))
                        elif key == "ImageWidth":
                            dpg.set_value("width_slider", int(value))
                        elif key == "ImageHeight":
                            dpg.set_value("height_slider", int(value))
                            self.resize_image(sender=None, app_data=None, user_data=None)
                        elif key == "Marker":
                            # Ensure there are 5 coordinates for markers
                            coords = value.split(", ")
                            if len(coords) == 5:
                                relative_x, relative_y, z_evaluation = float(coords[0]), float(coords[1]), float(coords[2])
                                clicked_x, clicked_y = float(coords[3]), float(coords[4])
                                new_coords = (relative_x, relative_y, z_evaluation)
                                new_clicked_position = (clicked_x, clicked_y)

                                if not self.marker_exists(new_coords):
                                    self.click_coord = new_coords
                                    self.clicked_position = new_clicked_position
                                    self.mark_point_on_map()

                        elif key == "Rectangle":
                            # Ensure there are 5 values for rectangles (4 coordinates + Z scan state)
                            rect_coords = value.split(", ")
                            if len(rect_coords) == 5:
                                relative_min_x, relative_min_y, relative_max_x, relative_max_y = float(
                                    rect_coords[0]), float(rect_coords[1]), float(rect_coords[2]), float(rect_coords[3])
                                z_scan_state = rect_coords[4]

                                # Convert relative coordinates to absolute for drawing purposes
                                if dpg.does_item_exist("map_image"):
                                    item_x, item_y = dpg.get_item_pos("map_image")
                                    if item_x == 0:
                                        dpg.render_dearpygui_frame()  # Render a frame to ensure the map image position is ready
                                        item_x, item_y = dpg.get_item_pos("map_image")
                                else:
                                    print("map_image does not exist")
                                    item_x = 0
                                    item_y = 0

                                min_x = relative_min_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
                                min_y = relative_min_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")
                                max_x = relative_max_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
                                max_y = relative_max_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")

                                # Store the rectangle with relative coordinates and Z scan state
                                new_rectangle = (
                                    relative_min_x, relative_min_y, relative_max_x, relative_max_y, z_scan_state)
                                if new_rectangle not in self.area_markers:
                                    self.area_markers.append(new_rectangle)
                                    rect_index = len(self.area_markers) - 1  # Index of the new rectangle
                                    # Draw the rectangle on the map with absolute coordinates
                                    dpg.draw_rectangle(pmin=(min_x, min_y), pmax=(max_x, max_y),
                                                       color=(0, 255, 0, 255),
                                                       thickness=2, parent="map_draw_layer",
                                                       tag=f"query_rectangle_{rect_index}")
                                else:
                                    print("Rectangle already exists")
                            else:
                                print(len(rect_coords))
                                print("Rectangle should have 5 values (4 coordinates and Z scan state)")

                # Activate the last marker and area marker after loading
                if self.markers:
                    self.active_marker_index = len(self.markers) - 1
                    self.act_marker(self.active_marker_index)  # Activate the last marker

                if self.area_markers:
                    self.active_area_marker_index = len(self.area_markers) - 1
                    self.act_area_marker(self.active_area_marker_index)  # Activate the last area marker

                self.update_markers_table()

                print("Map parameters and markers loaded.")

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

            return self.use_picomotor, exp_notes
        except FileNotFoundError:
            print("map_config.txt not found.")
        except Exception as e:
            print(f"Error loading map parameters: {e}")

    def update_markers_table(self):
        """Rebuild the table rows to show both markers and area markers."""
        table_id = "markers_table"

        # Ensure the table exists before attempting to access its children
        if not dpg.does_item_exist(table_id):
            print(f"Table {table_id} does not exist.")
            return  # Exit the function if the table does not exist

        # Get the number of digits from the input field
        num_of_digits = dpg.get_value("MapNumOfDigits")

        # Create a dynamic format string based on the number of digits
        format_str = f"{{:.{num_of_digits}f}}"

        # Delete only the rows, keep the table headers intact
        for child in dpg.get_item_children(table_id, 1):
            if dpg.does_item_exist(child):  # Check if the item exists before deleting it
                dpg.delete_item(child)

        # Helper function to format numbers with a variable number of decimal places and strip trailing zeros
        def format_value(val):
            return format_str.format(val).rstrip('0').rstrip('.') if '.' in format_str.format(
                val) else format_str.format(val)

        # Add markers to the table
        for i, (marker_tag, text_tag, relative_coords, clicked_position) in enumerate(self.markers):
            with dpg.table_row(parent=table_id):
                # If this is the active marker, add an asterisk (*) next to the ID
                active_indicator = "*" if i == self.active_marker_index else ""

                dpg.add_text(f"{i}{active_indicator}")  # Add the marker ID with an asterisk if active
                dpg.add_text(format_value(relative_coords[0]))
                dpg.add_text(format_value(relative_coords[1]))
                dpg.add_text(format_value(relative_coords[2]))
                dpg.add_text("")
                dpg.add_text("")
                dpg.add_button(label="Del", width=-1,
                               callback=partial(self.delete_marker, i))  # Use zero-based index
                dpg.add_button(label="Go", width=-1, callback=partial(self.go_to_marker, i))
                dpg.add_button(label="*", width=-1,
                               callback=partial(self.act_marker, i))  # Use zero-based index

        # Only add the area markers section if there are any area markers
        if self.area_markers:
            with dpg.table_row(parent=table_id):
                dpg.add_text("ID ---")
                dpg.add_text("Min X")
                dpg.add_text("Max X")
                dpg.add_text("Min Y")
                dpg.add_text("Max Y")
                dpg.add_text("--------")
                dpg.add_text("Action")
                dpg.add_text("--------")
                dpg.add_text("--------")

        # Add area markers (rectangles) to the table with relative positions
        marker_count = len(self.markers)
        for i, (min_x, min_y, max_x, max_y, z_scan_state) in enumerate(self.area_markers):
            # If this is the active area marker, add an asterisk (*) next to the ID
            active_area_indicator = "*" if i == self.active_area_marker_index else ""

            # Add "Z" next to the ID if Z scan is enabled
            z_indicator = "z" if z_scan_state == "Z scan enabled" else ""

            # Add the area marker row to the table with relative positions
            with dpg.table_row(parent=table_id):
                dpg.add_text(f"A{z_indicator}{i}{active_area_indicator}")
                dpg.add_text(format_value(min_x))
                dpg.add_text(format_value(max_x))
                dpg.add_text(format_value(min_y))
                dpg.add_text(format_value(max_y))

                dpg.add_button(label="Del", width=-1, callback=partial(self.delete_area_marker, i))
                dpg.add_button(label="Updt", width=-1, callback=partial(self.update_scan_area_marker, i))
                dpg.add_button(label="z", width=-1, callback=partial(self.toggle_z_scan, i))
                dpg.add_button(label="*", width=-1, callback=partial(self.act_area_marker, i))

        print("Markers and area markers table updated.")

    def toggle_z_scan(self, index):
        """Toggle Z scan for the selected area marker."""
        if 0 <= index < len(self.area_markers):
            # Assuming area_markers have an additional field for Z scan state (True/False)
            area_marker = self.area_markers[index]

            # Check if Z scan is enabled and toggle the state
            if len(area_marker) == 5 and area_marker[4] == "Z scan enabled":
                # Disable Z scan
                self.area_markers[index] = (
                    area_marker[0], area_marker[1], area_marker[2], area_marker[3], "Z scan disabled")
                print(f"Z scan disabled for area marker {index}.")
            else:
                # Enable Z scan
                self.area_markers[index] = (
                    area_marker[0], area_marker[1], area_marker[2], area_marker[3], "Z scan enabled")
                print(f"Z scan enabled for area marker {index}.")
        else:
            print("Invalid area marker index.")

        self.update_markers_table()

    def delete_marker(self, index):
        """Delete a specific marker by index."""
        if 0 <= index < len(self.markers):
            # Get the marker details at the given index
            marker_tag, text_tag, _, _ = self.markers[index]

            # Delete the marker and text from the GUI if they exist
            if dpg.does_item_exist(marker_tag):
                dpg.delete_item(marker_tag)
            if dpg.does_item_exist(text_tag):
                dpg.delete_item(text_tag)

            # Remove the marker from the list
            self.markers.pop(index)

            # Update the table after deletion
            self.update_markers_table()

            # Activate the next marker or the previous one if no next marker exists
            if self.markers:
                if index >= len(self.markers):
                    # If the deleted marker was the last one, activate the new last marker
                    self.active_marker_index = len(self.markers) - 1
                else:
                    # Otherwise, activate the marker at the same index
                    self.active_marker_index = index
                self.act_marker(self.active_marker_index)
            else:
                print("No more markers to activate, switching to area markers.")
                self.move_mode = "area_marker"
                # Update the button label to indicate the current state
                dpg.set_item_label("toggle_marker_area", "move area")

            print(f"Marker {index + 1} deleted.")
        else:
            print(f"Invalid marker index: {index}")

    def delete_area_marker(self, index):
        """Delete a specific area marker (rectangle) by index."""
        if 0 <= index < len(self.area_markers):
            # Construct the tag for the rectangle based on its index
            rectangle_tag = f"query_rectangle_{index}"

            # Delete the rectangle from the GUI if it exists
            if dpg.does_item_exist(rectangle_tag):
                dpg.delete_item(rectangle_tag)

            # Remove the area marker from the list
            self.area_markers.pop(index)

            # Update the combined table after deletion
            self.update_markers_table()

            # Activate the next area marker or the previous one if no next area marker exists
            if self.area_markers:
                if index >= len(self.area_markers):
                    # If the deleted area marker was the last one, activate the new last area marker
                    self.active_area_marker_index = len(self.area_markers) - 1
                else:
                    # Otherwise, activate the area marker at the same index
                    self.active_area_marker_index = index
                self.act_area_marker(self.active_area_marker_index)
            else:
                print("No more area markers to activate, switching to point markers.")
                self.move_mode = "marker"
                # Update the button label to indicate the current state
                dpg.set_item_label("toggle_marker_area", "move marker")

            print(f"Area marker {index + 1} deleted.")
        else:
            print(f"Invalid area marker index: {index}")

    def resize_image(self, sender, app_data, user_data):
        # Get the values from the sliders or input fields
        new_width = dpg.get_value("width_slider")
        new_height = dpg.get_value("height_slider")

        # Check which slider (width or height) triggered the callback
        if sender == "width_slider":
            print("Width slider was changed.")
            # Adjust height to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_height = int(new_width / self.Map_aspect_ratio)
                dpg.set_value("height_slider", new_height)

        elif sender == "height_slider":
            print("Height slider was changed.")
            # Adjust width to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_width = int(new_height * self.Map_aspect_ratio)
                dpg.set_value("width_slider", new_width)

        # Update input fields when sliders change
        dpg.set_value("width_input", new_width)
        dpg.set_value("height_input", new_height)

        # Only update the image if the new width and height are reasonable
        if new_width >= 100 and new_height >= 100:
            dpg.configure_item("map_image", width=new_width, height=new_height)

    def resize_from_input(self, sender, app_data, user_data):
        # Get the values from the input fields
        new_width = dpg.get_value("width_input")
        new_height = dpg.get_value("height_input")

        # Check which slider (width or height) triggered the callback
        if sender == "width_input":
            print("Width input was changed.")
            # Adjust height to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_height = int(new_width / self.Map_aspect_ratio)
                dpg.set_value("height_input", new_height)

        elif sender == "height_input":
            print("Height input was changed.")
            # Adjust width to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_width = int(new_height * self.Map_aspect_ratio)
                dpg.set_value("width_input", new_width)

        # Update sliders when input fields change
        dpg.set_value("width_slider", new_width)
        dpg.set_value("height_slider", new_height)

        # Resize the image
        if new_width >= 100 and new_height >= 100:
            dpg.configure_item("map_image", width=new_width, height=new_height)

    def map_click_callback(self, app_data):
        # Get the mouse position relative to the map widget
        try:

            mouse_pos = dpg.get_mouse_pos(local=True)

            if mouse_pos is None:
                print("Mouse position not available.")
                return 1

            mouse_x, mouse_y = mouse_pos

            if dpg.does_item_exist("map_image"):
                self.map_item_x, self.map_item_y = dpg.get_item_pos("map_image")
            else:
                print("map_image does not exist")
                return 1

            if mouse_x < self.map_item_x or mouse_y < self.map_item_y:
                # print("click outside the map region")
                return 0  # click outside the map region

            if self.ZCalibrationData is None:
                print("No Z calibration data.")
                return 1

            # pdb.set_trace()  # Insert a manual breakpoint
            # Calculate the relative position of the click on the map
            relative_x = (mouse_x - self.map_item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
            relative_y = (mouse_y - self.map_item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

            # Make sure to pass both x and y as separate parameters, not in an array
            z_evaluation=0
            if hasattr(self, 'ZCalibrationData') and self.ZCalibrationData is not None and len(self.ZCalibrationData) > 0:
                print(self.ZCalibrationData)
                z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x * 1e6)), np.array(int(relative_y * 1e6)))) / 1e6

            # Update the text with the coordinates
            dpg.set_value("coordinates_text", f"x = {relative_x:.1f}, y = {relative_y:.1f}, z = {z_evaluation:.2f}")

            # Check if the current clicked_position is equal to the previous clicked position
            if self.marker_exists((relative_x, relative_y)):
                print("A marker with the same relative coordinates already exists.")
                return 1  # Prevent creating a new marker

            if self.click_coord == (relative_x, relative_y, z_evaluation) and not self.disable_d_click:
                # Do something when the positions are equal
                print("Current click position is the same as the previous click.")
                self.mark_point_on_map()
            else:
                # Store the coordinates for the mark
                self.clicked_position = (mouse_x, mouse_y)
                self.click_coord = (relative_x, relative_y, z_evaluation)

        except Exception as e:
            # Print the error message along with the detailed traceback
            print(f"Error in map_click_callback: {e}")
            traceback.print_exc()  # This will print the complete traceback, including the line number of the error

    def delete_all_markers(self):
        # Delete all point markers and their associated text
        for marker_tag, text_tag, relative_coords, clicked_position in self.markers:
            if dpg.does_item_exist(marker_tag):
                dpg.delete_item(marker_tag)
            if dpg.does_item_exist(text_tag):
                dpg.delete_item(text_tag)

        # Delete all area markers (rectangles)
        for i, rectangle in enumerate(self.area_markers):
            rectangle_tag = f"query_rectangle_{i}"
            if dpg.does_item_exist(rectangle_tag):
                dpg.delete_item(rectangle_tag)

        # Clear both markers and area_markers lists
        self.markers = []
        self.area_markers = []
        self.update_markers_table()  # Update the table after deletion
        print("All markers and rectangles have been deleted.")

    def delete_all_except_active(self):
        """Delete all markers and area markers except the active ones."""

        # Delete all non-active point markers and their associated text
        for i, (marker_tag, text_tag, relative_coords, clicked_position) in enumerate(self.markers):
            if i != self.active_marker_index:  # Skip the active marker
                if dpg.does_item_exist(marker_tag):
                    dpg.delete_item(marker_tag)
                if dpg.does_item_exist(text_tag):
                    dpg.delete_item(text_tag)

        # Remove non-active markers from the list
        self.markers = [self.markers[self.active_marker_index]] if self.active_marker_index is not None else []
        self.active_marker_index = 0

        # Delete all non-active area markers (rectangles)
        for i in range(len(self.area_markers)):
            if i != self.active_area_marker_index:  # Skip the active area marker
                rectangle_tag = f"query_rectangle_{i}"
                if dpg.does_item_exist(rectangle_tag):
                    dpg.delete_item(rectangle_tag)

        # Remove non-active area markers from the list
        self.area_markers = [
            self.area_markers[self.active_area_marker_index]] if self.active_area_marker_index is not None else []
        self.active_area_marker_index = 0

        # Update the table after deletion
        self.update_markers_table()
        print("All markers and rectangles except active ones have been deleted.")

    def mark_point_on_map(self):
        # Ensure that self.clicked_position exists and is not None
        if not hasattr(self, 'clicked_position') or self.clicked_position is None:
            print("Error: Clicked position is not defined.")
            return  # Exit the function if clicked position is not set

        x_pos, y_pos = self.clicked_position

        marker_tag = f"marker_{len(self.markers)}"
        text_tag = f"text_{len(self.markers)}"

        # Retrieve the number of digits from the input field
        num_of_digits = dpg.get_value("MapNumOfDigits")

        # Update the format string to use the retrieved number of digits
        coord_text = f"({self.click_coord[0]:.{num_of_digits}f}, {self.click_coord[1]:.{num_of_digits}f}, {self.click_coord[2]:.{num_of_digits}f})"

        # Add a circle at the clicked position
        dpg.draw_circle(center=(x_pos, y_pos), radius=2, color=(255, 0, 0, 255), fill=(255, 0, 0, 100), parent="map_draw_layer", tag=marker_tag)

        # Add text next to the marker showing the 3 coordinates, using the selected text color
        dpg.draw_text(pos=(x_pos, y_pos), text=coord_text, color=self.text_color, size=14 + num_of_digits * 2,
                      parent="map_draw_layer", tag=text_tag)

        print(coord_text)

        # Store the marker and text tags, along with the relative and clicked positions
        self.markers.append((marker_tag, text_tag, self.click_coord, self.clicked_position))

        # Activate the newly added marker by setting it as the active marker
        self.active_marker_index = len(self.markers) - 1

        self.update_markers_table()
        self.update_marker_texts()

    def update_marker_texts(self, full=1):
        # Retrieve the updated number of digits
        num_of_digits = dpg.get_value("MapNumOfDigits")
        if num_of_digits < 0:
            num_of_digits = 0
            dpg.set_value("MapNumOfDigits", num_of_digits)

        # Loop through all markers and update the text
        for i, (marker_tag, text_tag, click_coord, clicked_position) in enumerate(self.markers):
            x_pos, y_pos = clicked_position

            # If full == 1, recalculate the relative positions and Z values
            if full == 1:
                # clicked_position provides the absolute position of the click
                abs_x, abs_y = x_pos, y_pos

                # Calculate relative X and Y positions based on offsets and factors
                relative_x = (abs_x - self.map_item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                relative_y = (abs_y - self.map_item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

                # Recalculate Z based on the updated relative coordinates
                z_evaluation=0
                if hasattr(self, 'ZCalibrationData') and self.ZCalibrationData is not None and len(
                        self.ZCalibrationData) > 0:
                    z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x * 1e6)),
                                                            int(relative_y * 1e6))) / 1e6

                # Update click_coord with the new calculated relative X, Y, and Z values
                click_coord = [relative_x, relative_y, z_evaluation]

            # Update the format string for the current marker
            coord_text = f"({click_coord[0]:.{num_of_digits}f}, {click_coord[1]:.{num_of_digits}f}, {click_coord[2]:.{num_of_digits}f})"

            # Determine the color (magenta for active marker, self.text_color for others)
            text_color = (255, 0, 255) if i == self.active_marker_index else self.text_color

            # Delete the old text and redraw with updated coordinates
            dpg.delete_item(text_tag)
            dpg.draw_text(pos=(x_pos + 10, y_pos), text=coord_text, color=text_color, size=14 + num_of_digits * 2,
                          parent="map_draw_layer", tag=text_tag)

    def btn_num_of_digits_change(self, sender, app_data):
        self.update_marker_texts()
        self.update_markers_table()

    def marker_exists(self, coords):
        for _, _, existing_relative_coords, _ in self.markers:
            # Compare relative coordinates with a small tolerance for floating point values
            if all(abs(existing_relative_coords[i] - coords[i]) < 1e-6 for i in range(2)):
                print("Marker already exists")
                return True
        return False

    def delete_last_mark(self):
        if self.markers:
            # Unpack the four elements returned by pop: marker tag, text tag, relative coordinates, and clicked position
            last_marker, last_text, _, _ = self.markers.pop()

            # Delete both the marker and the associated text
            dpg.delete_item(last_marker)
            dpg.delete_item(last_text)

            self.update_markers_table()  # Update the table after deletion
            print("marker has been deleted.")

    def find_middle(self):
        try:
            # Try to get the current position from the positioner
            self.positioner.GetPosition()
            Center = list(self.positioner.AxesPositions)  # Ensure that Center is properly retrieved

            # Initialize P1 and P2 lists
            P1 = []
            P2 = []

            # Calculate the lower and upper bounds
            for ch in range(2):
                P1.append((Center[ch] - self.L_scan[ch] * 1e3 / 2) * 1e-6)
                P2.append((Center[ch] + self.L_scan[ch] * 1e3 / 2) * 1e-6)

            # Print the calculated values
            print(f"Center = {[c * 1e-6 for c in Center]}")
            print(f"P1 = {P1}, P2 = {P2}")
            print(f"L_scan = {self.L_scan}")

        except AttributeError as e:
            print(f"Attribute error: {e}")
        except IndexError as e:
            print(f"Index error: {e}")
        except TypeError as e:
            print(f"Type error: {e}")
        except Exception as e:
            # Catch all other exceptions
            print(f"An unexpected error occurred: {e}")

    def act_marker(self, index):
        """Activate a specific marker by its index."""
        if 0 <= index < len(self.markers):
            self.active_marker_index = index  # Store the active marker's index
            print(f"Marker {index + 1} activated.")
            self.update_markers_table()  # Update the table to visually highlight the active marker
            self.update_marker_texts()
        else:
            print("Invalid marker index.")

    def act_area_marker(self, index):
        """Activate a specific area marker by its index."""
        if 0 <= index < len(self.area_markers):
            self.active_area_marker_index = index  # Store the active area marker's index
            print(f"Area marker {index} activated.")  # Zero-based index
            self.highlight_active_rectangle()  # Change rectangle color to magenta
        else:
            print("Invalid area marker index.")

    def set_marker_coord_to_zero(self):
        """Set the map offsets such that the active marker's relative coordinates become (0,0)."""
        if self.active_marker_index is not None and self.active_marker_index >= 0:
            marker_tag, text_tag, relative_coords, clicked_position = self.markers[self.active_marker_index]

            # Get the absolute clicked position for the active marker
            abs_x, abs_y = clicked_position

            # Calculate the new offsets to make the active marker's relative position (0,0)
            # Keep the marker's visual position unchanged but reset its relative coordinates
            new_offset_x = abs_x - self.map_item_x
            new_offset_y = abs_y - self.map_item_y

            # Update the offsets in the UI
            dpg.set_value("MapOffsetX", new_offset_x)
            dpg.set_value("MapOffsetY", new_offset_y)

            # Recalculate relative coordinates of all markers based on the new offsets and factors
            self.update_marker_texts(full=1)

            print(f"Offsets updated: MapOffsetX={new_offset_x}, MapOffsetY={new_offset_y}")

    def toggle_set_x_or_y(self, sender):
        """Toggle between setting the gap for X or Y axis."""
        current_label = dpg.get_item_label(sender)

        if current_label == "x":
            dpg.configure_item(sender, label="y")
            print("Toggled to Y axis.")
        else:
            dpg.configure_item(sender, label="x")
            print("Toggled to X axis.")

    def map_set_gap(self, sender, app_data, user_data):
        """Set FactorX or FactorY such that the gap between the active marker and the previous marker equals the gap_value."""
        if not hasattr(self, 'active_marker_index') or self.active_marker_index < 0:
            print("No marker is activated. Please activate a marker first.")
            return

        if len(self.markers) < 2:
            print("Need at least two markers to calculate the gap.")
            return

        # Get the active marker's coordinates
        active_marker_tag, active_text_tag, active_relative_coords, active_clicked_position = self.markers[
            self.active_marker_index]

        # Get the previous marker's coordinates (the one before the active marker)
        if self.active_marker_index > 0:
            previous_marker_tag, previous_text_tag, previous_relative_coords, previous_clicked_position = self.markers[
                self.active_marker_index - 1]
        else:  # (the one after the active marker)
            previous_marker_tag, previous_text_tag, previous_relative_coords, previous_clicked_position = self.markers[
                self.active_marker_index + 1]

        # Get the gap value from the input field
        gap_value = dpg.get_value("MapSetGap")

        # Check whether we are adjusting "x" or "y" axis
        axis = dpg.get_item_label("toggle_set_x_or_y")  # Assuming 'X' or 'Y' is passed as label
        print(f"Axis selected: {axis}")

        if axis == "x":
            # Consider the current MapFactorX for delta_x calculation
            current_factor_x = dpg.get_value("MapFactorX")

            # Calculate delta_x between active and previous marker, considering the current MapFactorX
            delta_x = abs((active_relative_coords[0] - previous_relative_coords[0]) / current_factor_x)

            # Calculate FactorX so that the gap between the markers becomes equal to gap_value
            factor_x = gap_value / delta_x if delta_x != 0 else 1  # Prevent division by zero

            # Update the FactorX value in the UI
            dpg.set_value("MapFactorX", factor_x)
            print(f"FactorX updated based on gap value {gap_value}: FactorX = {factor_x}")

        elif axis == "y":
            # Consider the current MapFactorY for delta_y calculation
            current_factor_y = dpg.get_value("MapFactorY")

            # Calculate delta_y between active and previous marker, considering the current MapFactorY
            delta_y = abs((active_relative_coords[1] - previous_relative_coords[1]) / current_factor_y)

            # Calculate FactorY so that the gap between the markers becomes equal to gap_value
            factor_y = gap_value / delta_y if delta_y != 0 else 1  # Prevent division by zero

            # Update the FactorY value in the UI
            dpg.set_value("MapFactorY", factor_y)
            print(f"FactorY updated based on gap value {gap_value}: FactorY = {factor_y}")

        else:
            print("Invalid axis input. Use 'X' or 'Y'.")

        # Recalculate marker positions with updated factors
        self.update_marker_texts(full=1)

        # Ensure that the new gap is set properly by recalculating and updating the positions
        print(f"Markers updated. New gap set to {gap_value} on the {axis} axis.")

    def shift_marker_up(self):
        """Shift the active marker up in the list."""
        if hasattr(self, 'active_marker_index') and self.active_marker_index > 0:
            # Swap the active marker with the one above it
            self.markers[self.active_marker_index], self.markers[self.active_marker_index - 1] = \
                self.markers[self.active_marker_index - 1], self.markers[self.active_marker_index]
            self.active_marker_index -= 1  # Update active marker index
            print(f"Marker shifted up to position {self.active_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift up, already at the top.")

    def shift_marker_down(self):
        """Shift the active marker down in the list."""
        if hasattr(self, 'active_marker_index') and self.active_marker_index < len(self.markers) - 1:
            # Swap the active marker with the one below it
            self.markers[self.active_marker_index], self.markers[self.active_marker_index + 1] = \
                self.markers[self.active_marker_index + 1], self.markers[self.active_marker_index]
            self.active_marker_index += 1  # Update active marker index
            print(f"Marker shifted down to position {self.active_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift down, already at the bottom.")

    def shift_area_marker_up(self):
        """Shift the active area marker up in the list."""
        if hasattr(self, 'active_area_marker_index') and self.active_area_marker_index > 0:
            # Swap the active area marker with the one above it
            self.area_markers[self.active_area_marker_index], self.area_markers[self.active_area_marker_index - 1] = \
                self.area_markers[self.active_area_marker_index - 1], self.area_markers[self.active_area_marker_index]
            self.active_area_marker_index -= 1  # Update active area marker index
            print(f"Area marker shifted up to position {self.active_area_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift up, already at the top or no area markers active.")

    def shift_area_marker_down(self):
        """Shift the active area marker down in the list."""
        if hasattr(self, 'active_area_marker_index') and self.active_area_marker_index < len(self.area_markers) - 1:
            # Swap the active area marker with the one below it
            self.area_markers[self.active_area_marker_index], self.area_markers[self.active_area_marker_index + 1] = \
                self.area_markers[self.active_area_marker_index + 1], self.area_markers[self.active_area_marker_index]
            self.active_area_marker_index += 1  # Update active area marker index
            print(f"Area marker shifted down to position {self.active_area_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift down, already at the bottom or no area markers active.")

    def highlight_active_rectangle(self):
        """Change the color of the active rectangle to magenta and reset others to green.
           If Z scan is enabled, use cyan color."""
        for i, (min_x, min_y, max_x, max_y, z_scan_state) in enumerate(self.area_markers):
            # Determine the color: magenta for active, green for others, cyan if Z scan is enabled
            if i == self.active_area_marker_index:
                rect_color = (255, 0, 255, 255)  # Active rectangle color (magenta)
            elif z_scan_state == "Z scan enabled":
                rect_color = (0, 255, 255, 255)  # Z scan enabled (cyan)
            else:
                rect_color = (0, 255, 0, 255)  # Default color for other rectangles (green)

            # Check if the rectangle item exists before trying to update it
            rect_tag = f"query_rectangle_{i}"  # Use consistent tag indexing
            if dpg.does_item_exist(rect_tag):
                # Update the existing rectangle color
                dpg.configure_item(rect_tag, color=rect_color)
            else:
                print(f"Rectangle with tag {rect_tag} does not exist.")

        self.update_markers_table()

    def scan_all_area_markers(self):
        """Automatically scan all area markers sequentially without user interaction, handling errors and skipping problematic markers."""
        if len(self.area_markers) == 0:
            print("No area markers available for scanning.")
            return

        print(f"Starting scan for {len(self.area_markers)} area markers.")

        # Iterate over all area markers
        for index in range(len(self.area_markers)):
            try:
                print(f"Activating area marker {index + 1}/{len(self.area_markers)}.")

                # Activate the area marker before scanning
                self.act_area_marker(index)

                print(f"Updating scan parameters for area marker {index + 1}.")
                # Update the scan parameters for the selected area marker
                self.update_scan_area_marker(index)

                # After updating, the start scan position (point) is already calculated in the update function
                point = [
                    dpg.get_value("mcs_ch0_ABS") * 1e6,  # X position in micrometers
                    dpg.get_value("mcs_ch1_ABS") * 1e6,  # Y position in micrometers
                    dpg.get_value("mcs_ch2_ABS") * 1e6  # Z position in micrometers
                ]

                # Move to the calculated scan start position for each axis
                for ch in range(3):
                    if self.use_picomotor:
                        self.pico.MoveABSOLUTE(ch + 1, int(point[ch]))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm, by picomotor.")
                    else:
                        self.positioner.MoveABSOLUTE(ch, int(point[ch]))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm.")

                # Ensure the stage has reached its position
                time.sleep(0.005)  # Allow motion to start
                for ch in range(3):
                    res = self.readInpos(ch)  # Wait for motion to complete
                    if res:
                        print(f"Axis {ch} in position at {self.positioner.AxesPositions[ch]}.")
                    else:
                        print(f"Failed to move axis {ch} to position.")

                # Start the scan automatically
                print(f"Starting scan for area marker {index + 1}.")
                self.StartScan3D()

                # Halt if the scan is stopped manually
                if self.stopScan:
                    print(f"Scan stopped manually after scanning {index + 1} area markers.")
                    return

            except Exception as e:
                print(f"An error occurred while scanning area marker {index + 1}: {e}")
                # Skip to the next area marker if an error occurs
                continue

        print("Completed scanning all area markers.")

    def go_to_marker(self):
        """Move to the absolute coordinates of the active marker."""

        # Ensure that there is an active marker
        if self.active_marker_index is None or self.active_marker_index >= len(self.markers):
            print("No active marker selected.")
            return

        # Get the absolute coordinates of the active marker (stored in self.click_coord)
        marker = self.markers[self.active_marker_index]
        absolute_coords = marker[2]  # self.click_coord is stored here

        print(
            f"Moving to marker at (X: {absolute_coords[0]} µm, Y: {absolute_coords[1]} µm, Z: {absolute_coords[2]} µm)")

        # Move the positioner to the stored absolute positions for each axis
        for ch in range(3):
            try:
                self.positioner.MoveABSOLUTE(ch, int(absolute_coords[ch] * 1e6))  # Move absolute to marker position
                print(f"Moved to position for channel {ch} at {absolute_coords[ch]} µm.")
            except Exception as e:
                print(f"Failed to move channel {ch} to {absolute_coords[ch]} µm: {e}")
                return

        # Ensure the stage has reached its position
        time.sleep(0.005)  # Allow motion to start
        for ch in range(3):
            try:
                res = self.readInpos(ch)  # Wait for motion to complete
                if res:
                    print(f"Axis {ch} in position at {self.positioner.AxesPositions[ch]}.")
                else:
                    print(f"Failed to move axis {ch} to position.")
            except Exception as e:
                print(f"Error while waiting for channel {ch} to reach position: {e}")
                return

        print("Reached the active marker position.")

    def toggle_use_picomotor(sender, app_data, user_data):
        sender.use_picomotor = user_data
        time.sleep(0.001)
        dpg.set_value(item="checkbox_map_use_picomotor", value=sender.use_picomotor)
        print("Set use_picomotor to: " + str(sender.use_picomotor))

    def toggle_disable_d_click(self, app_data, user_data):
        self.disable_d_click = user_data
        dpg.set_value(item="checkbox_disable_d_click", value=self.disable_d_click)
        print("Set disable d click to: " + str(self.disable_d_click))


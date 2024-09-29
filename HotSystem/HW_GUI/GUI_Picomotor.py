# from ECM import *
# from ImGuiwrappedMethods import *
from functools import partial

import dearpygui.dearpygui as dpg
from Common import DpgThemes

from HW_wrapper import HW_devices as hw_devices
import math
import random  # for simulation

class GUI_picomotor():
    def __init__(self, simulation: bool = False) -> None:
        self.NumOfLoggedPoints = 0
        self.U = None
        self.V = None
        self.HW = hw_devices.HW_devices()
        self.dev = self.HW.picomotor
        self.simulation = simulation
        self.prefix = "pico"
        self.ch_offset = 1

        themes = DpgThemes()
        yellow_theme = themes.color_theme((155, 155, 0), (0, 0, 0))
        red_button_theme = themes.color_theme((255, 0, 0), (0, 0, 0))

        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()

        pos = [int(self.viewport_width * 0.0), int(self.viewport_height * 0.2)]

        Child_Width=80
        lbl_list = ["out", "in", "left", "right", "down", "up"]
        with dpg.window(tag=f"{self.prefix}_Win", label="Picomotor, disconnected", no_title_bar=False, height=200, width=1400,pos=pos,
                        collapsed=True):
            with dpg.group(horizontal=True):  
                with dpg.group(horizontal=False, tag="column 1_"):
                    dpg.add_text("Position (um)")                    
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_text("Ch"+str(ch),tag=f"{self.prefix}_Ch"+str(ch))
                    dpg.add_button(label="Stop all axes",callback=self.btnStopAllAxes)
                    dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                with dpg.group(horizontal=False, tag="column 2_"):
                    dpg.add_text("        Coarse (um)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_button(label=lbl_list[ch*2],width=80,callback=self.move_c_f, user_data=(ch, 'neg', 'c'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)                            
                            dpg.add_button(label=lbl_list[ch*2+1],width=80,callback=self.move_c_f,user_data=(ch, 'pos', 'c'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_input_float(label="",default_value=1,tag=f"{self.prefix}_ch"+str(ch)+"_Cset",indent=-1,format='%.1f',width=150,
                                                step=1,
                                                step_fast=100,callback=self.set_move_step, user_data=(ch,'c'))
                            dpg.add_text("um",indent=-10)
                    with dpg.group(horizontal=True):
                        dpg.add_text(" Disable keyboard")
                        dpg.add_checkbox(tag=f"{self.prefix}_Disable_Keyboard", callback=self.cbx_disable_keyboard)

                with dpg.group(horizontal=False, tag="column 3_"):
                    dpg.add_text("        Fine (nm)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="-",width=25,callback=self.move_c_f, user_data=(ch, 'neg', 'f'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_button(label="+",width=25,callback=self.move_c_f,user_data=(ch, 'pos', 'f'))
                            dpg.bind_item_theme(dpg.last_item(), red_button_theme)
                            dpg.add_input_float(label="",default_value=100,tag=f"{self.prefix}_ch"+str(ch)+"_Fset",indent=-1,format='%.1f',
                                                width=150,step=1,
                                                step_fast=100,callback=self.set_move_step, user_data=(ch,'f'))
                            dpg.add_text("nm",indent=-10)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Log", callback=self.btnLogPoint, tag=f"{self.prefix}_Log")
                        dpg.add_button(label="Del", callback=self.btnDelPoint)
                        dpg.add_text(tag="pico_logged_points", label="")
                with dpg.group(horizontal=False, tag="column 4_",width=Child_Width):
                    dpg.add_text("GoTo Ref.")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Ref. "+str(ch))

                    dpg.add_button(label="Save", callback=self.save_log_points)

                with dpg.group(horizontal=False, tag="column 5_",width=Child_Width):
                    dpg.add_text("     Zero")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Zero "+str(ch),callback=self.BtnZero,user_data=ch)
                    dpg.add_button(label="Load", callback=self.load_points)

                with dpg.group(horizontal=False, width=Child_Width):
                    dpg.add_text(" Move UV")
                    for ch in range(2):
                        with dpg.group(horizontal=True):
                            if ch == 0:
                                dpg.add_text("  U")
                            else:
                                dpg.add_text("  V")
                            dpg.add_button(label="-", width=20, callback=self.move_uv, user_data=(ch,-1,True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                            dpg.add_button(label="+", width=20, callback=self.move_uv, user_data=(ch,1,True))
                            dpg.bind_item_theme(dpg.last_item(), yellow_theme)
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Calc U",tag=f"{self.prefix}_calc_u", callback=self.btn_calc_u)
                        dpg.add_button(label="Calc V",tag=f"{self.prefix}_calc_v", callback=self.btn_calc_v)

                with dpg.group(horizontal=False, tag="column 6_",width=Child_Width*2):
                    dpg.add_text("Abs. (nm)")
                    for ch in range(self.dev.no_of_channels):
                        with dpg.group(horizontal=True):
                            dpg.add_input_float(label="",default_value=0,tag=f"{self.prefix}_ch"+str(ch)+"_ABS",indent=-1,format='%.3f',width=60,
                                                step=100,
                                                step_fast=1000)
                with dpg.group(horizontal=False):
                    dpg.add_text("Go")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="GO", callback=self.move_absolute, user_data=ch)
                with dpg.group(horizontal=False, tag="column 7_",width=Child_Width):
                    dpg.add_text("  Home")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_button(label="Home "+str(ch),callback=self.btnMoveToHome,user_data=ch)
                with dpg.group(horizontal=False, tag="column 8_",width=Child_Width):
                    dpg.add_text("Status")
                    for ch in range(self.dev.no_of_channels):
                        dpg.add_text("idle",tag=f"{self.prefix}_Status"+str(ch))
            # Independent group for the table below _column 1_
            with dpg.group(horizontal=False):
                with dpg.table(header_row=True, tag=f"{self.prefix}_logged_points_table", width=700):
                    dpg.add_table_column(label="Point")
                    dpg.add_table_column(label="X")
                    dpg.add_table_column(label="Y")
                    dpg.add_table_column(label="Z")
                    dpg.add_table_column(label="Delete")
                    dpg.add_table_column(label="Go Abs")

        self.load_points()

        if simulation:
            self.dev.StepsIn1mm = 1e6 * 40
            self.dev.AxesKeyBoardLargeStep = []
            self.dev.AxesKeyBoardSmallStep = []
            self.dev.AxesPositions = [0, 0, 0]
            for ch in range(self.dev.no_of_channels):
                self.dev.AxesKeyBoardLargeStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Cset") * self.dev.StepsIn1mm / 1e3) for ch in range(3)]
                self.dev.AxesKeyBoardSmallStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Fset") * self.dev.StepsIn1mm / 1e6) for ch in range(3)]
        else:
            self.Connect()

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
                        coords = line.split(": ")[1].split(", ")  # Process the logged point line

                        if len(coords) == 3:  # Ensure we have 3 coordinates
                            logged_point = (float(coords[0]), float(coords[1]), float(coords[2]))
                            self.dev.LoggedPoints.append(logged_point)
                            self.NumOfLoggedPoints += 1

                            current_height = dpg.get_item_height(f"{self.prefix}_Win")
                            new_height = current_height + 30  # Increase height by 50 units
                            dpg.configure_item(f"{self.prefix}_Win", height=new_height)

                            # Check how many points have been logged and calculate u or v
                            if self.NumOfLoggedPoints == 2:
                                self.calc_vector('u')
                                dpg.bind_item_theme(f"{self.prefix}_calc_u", yellow_theme)
                            elif self.NumOfLoggedPoints == 3:
                                self.calc_vector('v')
                                dpg.bind_item_theme(f"{self.prefix}_calc_v", yellow_theme)

                # Update the logged points indicator and table
                dpg.set_value(f"{self.prefix}_logged_points", "* " * self.NumOfLoggedPoints)
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

    def cbx_disable_keyboard(self, app_data, user_data):
        if user_data:
            self.dev.KeyboardEnabled = False
        else:
            self.dev.KeyboardEnabled = True

    def btnLogPoint(self):

        current_height = dpg.get_item_height(f"{self.prefix}_Win")
        new_height = current_height + 30  # Increase height by 50 units
        dpg.configure_item(f"{self.prefix}_Win", height=new_height)

        self.dev.GetPosition()

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

        for ch in range(3):
            position[ch] = position[ch] / self.dev.StepsIn1mm * 1e3

        self.dev.LoggedPoints.append(position.copy())  # [um]
        self.NumOfLoggedPoints += 1
        print(self.dev.LoggedPoints)

        # Update the UI
        dpg.set_value(f"{self.prefix}_logged_points", "* " * self.NumOfLoggedPoints)
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

    def btnDelPoint(self):

        current_height = dpg.get_item_height(f"{self.prefix}_Win")
        new_height = current_height - 30  # Increase height by 50 units
        dpg.configure_item(f"{self.prefix}_Win", height=new_height)

        if self.dev.IsConnected:
            self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
            self.NumOfLoggedPoints -= 1
            dpg.set_value(f"{self.prefix}_logged_points", "* " * self.NumOfLoggedPoints)
            self.update_table()
        else:
            print("Cannot log point while Smaract is disconnected.")
            if self.simulation:
                self.dev.LoggedPoints.pop()  # [pm]  Removes the last item
                self.NumOfLoggedPoints -= 1
                dpg.set_value(f"{self.prefix}_logged_points", "* " * self.NumOfLoggedPoints)
                self.update_table()

    def update_table(self):
        """Rebuild the table rows to show all logged points."""
        table_id = f"{self.prefix}_logged_points_table"

        # Delete only the rows, keep the table headers intact
        for child in dpg.get_item_children(table_id, 1):
            dpg.delete_item(child)

        # Rebuild the table with the current logged points
        for i, point in enumerate(self.dev.LoggedPoints, start=1):
            with dpg.table_row(parent=table_id):
                dpg.add_text(f"Point {i}")
                dpg.add_text(f"{point[0]:.3f}")
                dpg.add_text(f"{point[1]:.3f}")
                dpg.add_text(f"{point[2]:.3f}")
                # # Add a delete button in the last column
                # dpg.add_button(label="Delete", width=60, height=20, callback=lambda s=i - 1: self.delete_row(s))
                # Use partial to pass the correct index to the callback function
                dpg.add_button(label="Delete", width=100, callback=partial(self.delete_table_row, i - 1))
                dpg.add_button(label="fill abs", width=100, callback=partial(self.go_abs_callback, point))

    def delete_table_row(self, index):
        """Delete a row from the table and update the points list."""
        if 0 <= index < len(self.dev.LoggedPoints):
            # Remove the selected point
            del self.dev.LoggedPoints[index]
            self.NumOfLoggedPoints -= 1
            dpg.set_value(f"{self.prefix}_logged_points", "* " * self.NumOfLoggedPoints)
            # Rebuild the table to reflect the change
            self.update_table()

            current_height = dpg.get_item_height(f"{self.prefix}_Win")
            new_height = current_height - 30  # Increase height by 50 units
            dpg.configure_item(f"{self.prefix}_Win", height=new_height)


    def go_abs_callback(self,point):
        """Callback to set the input fields with the selected point."""
        for ch, value in enumerate(point):
            dpg.set_value(f"{self.prefix}_ch{ch}_ABS", value/1e6)

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
            magnitude = math.sqrt(sum([component ** 2 for component in difference]))
            normalized_vector = [component / magnitude for component in difference]

            if vector_name.lower() == 'u':
                self.U = normalized_vector
                print(self.U)
            elif vector_name.lower() == 'v':
                self.V = normalized_vector
                print(self.V)
            else:
                print(f"Unknown vector name: {vector_name}")

    def btnStopAllAxes(self):
        self.dev.StopAllAxes()
        
    def btnMoveToHome(self,sender,app_data,ch):
        self.dev.MoveToHome(ch+1)
        
    def move_absolute(self,sender,value,ch):
        value = dpg.get_value(f"{self.prefix}_ch" + str(ch) + "_ABS")
        self.dev.MoveABSOLUTE(ch+1,int(value*self.dev.StepsIn1mm/1e3))



    def set_move_step(self,sender,app_data,user_data):
        ch, move_type = user_data

        scale = 1e3 if move_type == 'c' else 1e6
        steps = int(dpg.get_value(f"{self.prefix}_ch{ch}_{move_type.upper()}set") * self.dev.StepsIn1mm / scale)
        if move_type == 'c':
            self.dev.AxesKeyBoardLargeStep[ch] = steps
        else:
            self.dev.AxesKeyBoardSmallStep[ch] = steps

    def move_uv(self, sender, app_data, user_data):
        try:
            ch, direction, is_coarse = user_data

            direction = float(direction)

            value1 = float(dpg.get_value(f"{self.prefix}_ch{ch}_Cset"))

            if not is_coarse:
                value1 = value1 / 10

            steps = int(direction * value1 / 1e3 * self.dev.StepsIn1mm)
            amount = [self.U[i] * steps for i in range(3)] if ch == 0 else [self.V[i] * steps for i in range(3)]
            print(f"{self.prefix}:")
            print(amount)

            for channel in range(3):
                if not self.simulation:
                    self.dev.MoveRelative(channel+1, int(amount[channel]))

        except Exception as e:
            print(f"An error occurred: {e}")

    def BtnZero(self, sender, app_data, ch):
        self.dev.SetZeroPosition(ch+1)

    def move_c_f(self, sender, app_data, user_data):
        try:
            ch, direction, move_type = user_data
            factor = 1 if direction == 'pos' else -1
            scale = 1e3 if move_type == 'c' else 1e6
            steps = int(factor * dpg.get_value(f"{self.prefix}_ch{ch}_{move_type.upper()}set") * self.dev.StepsIn1mm / scale)
            self.dev.MoveRelative(ch + self.ch_offset, steps)
        except Exception as e:
            print(f"An error occurred in move_c_f: {e}")

    
    def Connect(self):
        self.dev.connect()
        print("Connecting")  
        if self.dev.IsConnected:
            dpg.set_item_label(f"{self.prefix}_Win",f"{self.prefix} stage, connected")
            for ch in range(self.dev.no_of_channels):
                self.dev.AxesKeyBoardLargeStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Cset") * self.dev.StepsIn1mm / 1e3) for ch in range(3)]
                self.dev.AxesKeyBoardSmallStep = [int(dpg.get_value(f"{self.prefix}_ch{ch}_Fset") * self.dev.StepsIn1mm / 1e6) for ch in range(3)]


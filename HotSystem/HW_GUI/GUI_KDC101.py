from HW_wrapper.Wrapper_KDC101 import MotorStage
from HW_wrapper.abstract_motor import Motor
import dearpygui.dearpygui as dpg
from Common import DpgThemes
from HW_GUI.GUI_motors import GUIMotor
import time
import threading
import numpy as np
from SystemConfig import Instruments, load_instrument_images

class GUI_KDC101(GUIMotor):
    def __init__(self, serial_number, device, simulation: bool = False) -> None:
        self.dev = device #1200 0.23, 150 0.68, 1800 -0.2
        self.prefix = "KDC101"
        self.unique_id = str(serial_number)  # <-- always unique for KDC1 vs KDC2
        self.window_tag: str = f"{self.prefix}_Win_{self.unique_id}"
        self.enable_button_tag = f"{self.prefix}_EnableButton_{self.unique_id}"
        self.stop_button_tag = f"{self.prefix}_StopButton_{self.unique_id}"
        self.position_tag = f"{self.prefix}_Position_{self.unique_id}"
        self.jog_up_tag = f"{self.prefix}_Jog Up_{self.unique_id}"
        self.jog_down_tag = f"{self.prefix}_Jog Down_{self.unique_id}"
        self.position_display_tag = f"{self.prefix}_PositionDisplay_{self.unique_id}"
        self.position_input_tag = f"{self.prefix}_PositionInput{self.unique_id}"
        self.controls_tag = f"{self.prefix}_Controls_{self.unique_id}"
        self.step = 0.5
        self.is_kdc2 = (int(serial_number) == 27270698)

        themes = DpgThemes()
        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()
        #self.system_initialization()
        Child_Width = 100
        with dpg.window(label=f"{self.prefix} {str(serial_number)}", no_title_bar=False,
                        height=150, width=400, pos=[0, 0],
                        collapsed=False, tag=self.window_tag):
            with dpg.group(horizontal=False, tag=f"column 2_{self.unique_id}", width=2*Child_Width, height = 120):
                with dpg.group(tag=self.controls_tag, parent = f"column 2_{self.unique_id}"):
                    dpg.add_text("Input Position:", color=(0, 255, 0), indent = 10)
                    dpg.add_input_float(default_value=float(str(self.dev.get_current_position())),
                                        callback=self.update_position,
                                        tag=self.position_input_tag,
                                        format='%.2f',
                                        step = self.step,
                                        indent=10,
                                        on_enter=True,
                                        max_value = 360,
                                        min_value = 0,
                                        width=75,
                                        parent = self.controls_tag)
                    if int(serial_number) == 27270698:
                        self.combo_tag = f"{self.prefix}_GratingCombo_{self.unique_id}"  # NEW

                        dpg.add_combo(
                            items=[
                                "150 g/mm --> 0.68",
                                "1200 g/mm --> 0.23",
                                "1800 g/mm --> -0.2",
                            ],
                            default_value="150 g/mm --> 0.68",
                            callback=self.combo_select_callback,
                            width=200,
                            indent=10,
                            parent=self.controls_tag,
                            tag = self.combo_tag,  # NEW
                        )
                    else:
                        self.combo_tag = None

            with dpg.group(horizontal=False):#, pos = [10,120]):
                dpg.add_text(
                    "Current Position (mm):" if self.is_kdc2 else "Current Position (°):",
                    color=(0, 255, 0),
                    indent=10
                )
                dpg.add_text(default_value="---", tag=self.position_display_tag, indent=10)
                dpg.add_button(label="Read Current Angle", callback=self.read_current_angle)
            with dpg.group(horizontal=True, tag=f"group 1_{self.unique_id}", width=Child_Width):
                dpg.add_button(label="Home", callback=self.home_button)
                dpg.add_button(label="Disable", tag=self.enable_button_tag, callback=self.enable_button)
                dpg.add_button(label="Stop", tag=self.stop_button_tag, callback=self.stop_button)
                dpg.add_button(label="Jog up", tag=self.jog_up_tag, callback=self.jog_up_button)
                dpg.add_button(label="Jog Down", tag=self.jog_down_tag, callback=self.jog_down_button)
    def DeleteMainWindow(self):
        """
        Deletes the main Dear PyGui window and does any needed cleanup.
        """
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)
        print(f"Deleted KDC_101 GUI window: {self.window_tag}")
    def _combo_to_position(self, selection: str) -> float:
        # selection is like "150 g/mm --> 0.68"
        return float(selection.split("-->")[1].strip())
    def combo_select_callback(self, sender, app_data, user_data):
        """
        app_data is the selected combo string.
        Sets the input float to the mapped position and triggers motion update.
        """
        try:
            pos = self._combo_to_position(app_data)
            dpg.set_value(self.position_input_tag, pos)     # update GUI input box
            self.update_position(self.position_input_tag, pos, None)  # trigger move using your existing logic
        except Exception as e:
            print(f"Error in combo selection: {e}")
    def read_current_angle(self):
        try:
            pos = float(str(self.dev.get_current_position()))
            if getattr(self, "is_kdc2", False):
                dpg.set_value(self.position_display_tag, f"{pos:.3f} mm")
                print(f"Current position: {pos:.3f} mm")
            else:
                dpg.set_value(self.position_display_tag, f"{pos:.3f}°")
                print(f"Current angle: {pos:.3f}°")
        except Exception as e:
            print(f"Error reading current angle: {e}")
            dpg.set_value(self.position_display_tag, "Error")
    def system_initialization(self):
        self.dev.connect()
        self.dev.enable()
    def update_position(self, sender, app_data, user_data):
        try:
            new_value = float(app_data)
            print(f"Moving to {new_value}")

            # guard: don't issue move if already moving
            if self.dev.is_busy():
                print("Device busy, ignoring move request")
                return

            self.dev.MoveABSOLUTE(new_value)

        except Exception as e:
            print(f"Move failed: {e}")
    def home_button(self):
        """Callback for the Home button."""
        try:
            print("Homing the stage...")
            self.dev.move_to_home()
            print("Stage homed successfully.")
            time.sleep(0.1)
            new_value = float(str(self.dev.get_current_position()))
            dpg.set_value(self.position_input_tag, new_value)
            #self.update_position_showing()
        except Exception as e:
            print(f"Error during homing: {e}")
    def stop_button(self):
        """Callback for the Home button."""
        try:
            print("Stopping the stage...")
            self.dev.stop_all_axes()
            print("Stage stopped successfully.")
            time.sleep(0.15)
            new_value = float(str(self.dev.get_current_position()))
            dpg.set_value(self.position_input_tag, new_value)
            #self.update_position_showing()
        except Exception as e:
            print(f"Error during stopping: {e}")
    def show_position(self):
        while self.dev.is_busy():
            try:
                new_value = float(str(self.dev.get_current_position()))
                dpg.set_value(self.position_input_tag, new_value)
            except Exception as e:
                print(f"Error updating position: {e}")
                break
    def update_position_showing(self):
        while self.dev.is_busy():
            try:
                time.sleep(0.05)
                self.update_position_display()
            except Exception as e:
                print(f"Error updating position: {e}")
                break
    def jog_up_button(self):
        """Callback for the Jog Up button."""
        try:
            print("Jogging up successfully...")
            self.dev.jog_continuous("forward")

            # Start the thread for updating the position
            threading.Thread(target=self.show_position, daemon=True).start()
            #self.update_position_showing()
        except Exception as e:
            print(f"Error during stopping: {e}")
    def jog_down_button(self):
        """Callback for the Jog Down button."""
        try:
            print("Jogging down successfully...")
            self.dev.jog_continuous("backward")

            # Start the thread for updating the position
            threading.Thread(target=self.show_position, daemon=True).start()
            #self.update_position_showing()
        except Exception as e:
            print(f"Error during stopping: {e}")
    def enable_button(self):
        try:
            if self.dev.is_enabled():
                self.dev.disable()
                dpg.set_item_label(self.enable_button_tag, "Enable")
                dpg.set_value(self.window_tag, f"{self.prefix} stage, disabled")
            else:
                self.dev.enable()
                dpg.set_item_label(self.enable_button_tag, "Disable")
                dpg.set_value(self.window_tag, f"{self.prefix} stage, enabled")
        except Exception as e:
            dpg.set_value(self.window_tag, f"Error toggling motor: {e}")


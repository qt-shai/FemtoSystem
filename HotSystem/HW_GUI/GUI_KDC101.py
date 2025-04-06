from HW_wrapper.Wrapper_KDC101 import MotorStage
from HW_wrapper.abstract_motor import Motor
import dearpygui.dearpygui as dpg
from Common import DpgThemes
from HW_GUI.GUI_motors import GUIMotor
import time
import threading
from SystemConfig import Instruments, load_instrument_images

class GUI_KDC101(GUIMotor):

    def __init__(self, serial_number, device) -> None:
        self.dev = device
        self.prefix = "KDC101"
        self.window_tag: str = f"{self.prefix}_Win_{serial_number}"
        self.enable_button_tag = f"{self.prefix}_EnableButton_{serial_number}"
        self.stop_button_tag = f"{self.prefix}_StopButton_{serial_number}"
        self.position_tag = f"{self.prefix}_Position_{serial_number}"
        self.jog_up_tag = f"{self.prefix}_Jog Up_{serial_number}"
        self.jog_down_tag = f"{self.prefix}_Jog Down_{serial_number}"
        self.position_display_tag = f"{self.prefix}_PositionDisplay_{serial_number}"
        self.step = 0.5
        themes = DpgThemes()
        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()
        self.system_initialization()
        Child_Width = 100
        try:
            with dpg.window(label=f"{self.prefix} motor", no_title_bar=False,
                            height=150, width=400, pos=[0, 0],
                            collapsed=False, tag=self.window_tag):

                with dpg.group(horizontal=False, tag="group 1", width=Child_Width):
                    dpg.add_button(label="Home", callback=self.home_button, pos=[150,30])
                    dpg.add_button(label="Disable", tag=self.enable_button_tag, callback=self.enable_button, pos=[20,30])
                    dpg.add_button(label="Stop", tag=self.stop_button_tag, callback=self.stop_button, pos=[280, 30])
                    dpg.add_button(label="Jog up", tag=self.jog_up_tag, callback=self.jog_up_button, pos=[280, 80])
                    dpg.add_button(label="Jog Down", tag=self.jog_down_tag, callback=self.jog_down_button, pos=[280, 110])

                with dpg.group(horizontal=False, tag="column 2", width=2*Child_Width, pos = [10,60], height = 120):
                    #dpg.add_text(tag = "blabla_tag", default_value= self.dev.blabla.get(), color=(255, 255, 0))
                    with dpg.group(tag="controls"):
                        dpg.add_text("Input Position:", color=(0, 255, 0), indent = 10)
                        dpg.add_input_float(default_value=float(str(self.dev.get_current_position())),
                                            callback=self.update_position,
                                            tag="position_input",
                                            format='%.6f',
                                            step = self.step,
                                            indent=10,
                                            on_enter=True,
                                            max_value = 360,
                                            min_value = 0,
                                            width=250)
                with dpg.group(horizontal=True, pos = [10,120]):
                    # current_pos = self.dev.get_current_position()
                    # dpg.add_text(default_value=f"Current_position:{current_pos:.6f}", tag = self.position_display_tag,color=(0, 255, 0), indent=10,
                    #              pos=[80, 110])
                    dpg.add_text("Current Position:", color=(0, 255, 0), indent=10)

                #self.on_position_update(channel=0,position=float(str(self.dev.get_current_position())))
                #self.dev.blabla.add_observer(lambda val : dpg.set_value("blabla_tag",val))
                #print(self.current_position())
        except Exception as e:
            print(e)

    def update_position_display(self):
        """Updates the position display with the latest position."""
        try:
            current_pos = self.dev.get_current_position()
            dpg.set_value(self.position_tag, f"{current_pos:.6f}")
        except Exception as e:
            dpg.set_value(self.position_tag, f"Error: {e}")

    def system_initialization(self):
        self.dev.connect()
        self.dev.enable()

    def update_position(self, sender, app_data, user_data):
        new_value = app_data
        print(new_value)
        while not self.dev.is_busy():
            self.dev.MoveABSOLUTE(new_value)
        #self.update_position_display()

    # def update_position(self):
    #     """Retrieves and displays the current motor position."""
    #     try:
    #         position = self.dev.get_current_position()  # Assuming `get_position()` fetches the current position
    #         dpg.set_value(self.position_tag, f"Current Position: {position:}")
    #     except Exception as e:
    #         dpg.set_value(self.position_tag, f"Error: {e}")


    def home_button(self):
        """Callback for the Home button."""
        try:
            print("Homing the stage...")
            self.dev.move_to_home()
            print("Stage homed successfully.")
            time.sleep(0.1)
            new_value = float(str(self.dev.get_current_position()))
            dpg.set_value("position_input", new_value)
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
            dpg.set_value("position_input", new_value)
            #self.update_position_showing()
        except Exception as e:
            print(f"Error during stopping: {e}")

    def show_position(self):
        while self.dev.is_busy():
            try:
                new_value = float(str(self.dev.get_current_position()))
                dpg.set_value("position_input", new_value)
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


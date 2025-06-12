from HW_wrapper.Wrapper_KDC101 import MotorStage
from HW_wrapper.abstract_motor import Motor
import dearpygui.dearpygui as dpg
from Common import DpgThemes
from HW_GUI.GUI_motors import GUIMotor
import time
import threading
import numpy as np
from SystemConfig import Instruments, load_instrument_images
from HW_wrapper.Wrapper_Pharos import PharosLaserAPI

class GUI_KDC101(GUIMotor):

    def __init__(self, serial_number, device, simulation: bool = False) -> None:
        self.dev = device
        self.prefix = "KDC101"
        self.unique_id = self._get_unique_id_from_device()
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
        themes = DpgThemes()
        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()
        self.pharos = PharosLaserAPI(host="192.168.101.58")
        #self.system_initialization()
        Child_Width = 100
        with dpg.window(label=f"{self.prefix} motor", no_title_bar=False,
                        height=150, width=400, pos=[0, 0],
                        collapsed=False, tag=self.window_tag):
            with dpg.group(horizontal=False, tag=f"group 1_{self.unique_id}", width=Child_Width):
                dpg.add_button(label="Home", callback=self.home_button, pos=[150,30])
                dpg.add_button(label="Disable", tag=self.enable_button_tag, callback=self.enable_button, pos=[20,30])
                dpg.add_button(label="Stop", tag=self.stop_button_tag, callback=self.stop_button, pos=[280, 30])
                dpg.add_button(label="Jog up", tag=self.jog_up_tag, callback=self.jog_up_button, pos=[280, 80])
                dpg.add_button(label="Jog Down", tag=self.jog_down_tag, callback=self.jog_down_button, pos=[280, 110])
            with dpg.group(horizontal=False, tag=f"column 2_{self.unique_id}", width=2*Child_Width, pos = [10,60], height = 120):
                #dpg.add_text(tag = "blabla_tag", default_value= self.dev.blabla.get(), color=(255, 255, 0))
                with dpg.group(tag=self.controls_tag, parent = f"column 2_{self.unique_id}"):
                    dpg.add_text("Input Position:", color=(0, 255, 0), indent = 10)
                    dpg.add_input_float(default_value=float(str(self.dev.get_current_position())),
                                        callback=self.update_position,
                                        tag=self.position_input_tag,
                                        format='%.6f',
                                        step = self.step,
                                        indent=10,
                                        on_enter=True,
                                        max_value = 360,
                                        min_value = 0,
                                        width=75,
                                        parent = self.controls_tag)
            with dpg.group(horizontal=False, pos = [10,120]):
                dpg.add_text("Current Position:", color=(0, 255, 0), indent=10)
                dpg.add_text(default_value="---", tag=self.position_display_tag, indent=10)
                dpg.add_button(label="Read Current Angle", callback=self.read_current_angle)
                with dpg.group(horizontal=True):
                    dpg.add_text("P[µW]:", color=(0, 255, 0))
                    dpg.add_text("N/A", tag=f"{self.prefix}_LaserPower_{self.unique_id}")
                with dpg.group(horizontal=True):
                    dpg.add_text("E[nJ]:", color=(0, 255, 0))
                    dpg.add_text("N/A", tag=f"{self.prefix}_PulseEnergy_{self.unique_id}")


    def calculate_laser_pulse(self, HWP_deg: float, Att_percent: float, rep_rate: float = 50e3) -> tuple[float, float]:
        # --- Polynomial calculation ---
        P_att = 13.86 * Att_percent ** 2 + 16.70 * Att_percent + 2.42

        # --- HWP modulation factor ---
        theta0 = -7.2
        modulation = np.sin(np.radians(2 * (HWP_deg - theta0))) ** 2 / np.sin(np.radians(2 * (40 - theta0))) ** 2

        P_uW = P_att * modulation
        pulse_energy_nJ = P_uW * 1e-6 / rep_rate * 1e9
        return P_uW, pulse_energy_nJ

    def get_current_attenuation(self) -> float:
        try:
            return float(self.pharos.getBasicTargetAttenuatorPercentage())
        except Exception as e:
            print(f"Error reading attenuation: {e}")
            return 0.0

    def read_current_angle(self):
        try:
            angle = float(str(self.dev.get_current_position()))
            dpg.set_value(self.position_display_tag, f"{angle:.3f}°")
            print(f"Current angle: {angle:.3f}°")

            # === Update Laser Power & Energy ===
            # You must define or fetch the current attenuation value here:
            Att_percent = self.get_current_attenuation()  # Replace with actual function or value

            P_uW, pulse_energy_nJ = self.calculate_laser_pulse(angle, Att_percent)
            dpg.set_value(f"{self.prefix}_LaserPower_{self.unique_id}", f"{P_uW:.1f}")
            dpg.set_value(f"{self.prefix}_PulseEnergy_{self.unique_id}", f"{pulse_energy_nJ:.1f}")
        except Exception as e:
                print(f"Error reading current angle: {e}")
                dpg.set_value(self.position_display_tag, f"Error")

    def system_initialization(self):
        self.dev.connect()
        self.dev.enable()

    def update_position(self, sender, app_data, user_data):
        new_value = app_data
        print(new_value)
        while not self.dev.is_busy():
            self.dev.MoveABSOLUTE(new_value)

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


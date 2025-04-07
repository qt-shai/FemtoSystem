import dearpygui.dearpygui as dpg
from Wrapper_Pharos import PharosLaserAPI

class GUIPharosLaser:
    """
    A Dear PyGui-based GUI for controlling a PharosLaserAPI device.
    Inspired by the GUIMotor structure in the provided example.
    """

    def __init__(self, laser: PharosLaserAPI, simulation: bool = False) -> None:
        """
        :param laser: An instance of the PharosLaserAPI wrapper.
        :param simulation: Whether we're in simulation mode (disables real actions).
        """
        self.dev = laser
        self.simulation = simulation
        self.is_collapsed = False
        self.unique_id = self._get_unique_id_from_device()
        self.window_tag = f"PharosLaserWin_{self.unique_id}"
        self.window_label = (
            f"Pharos Laser (simulation)" if simulation 
            else f"Pharos Laser @ {laser.base_url}"
        )

        # You can tweak these to match your preferred layout
        self.child_width = 180
        self.window_width = 1200
        self.window_height = 400

        # Create the primary window
        with dpg.window(
            tag=self.window_tag, 
            label=self.window_label, 
            width=self.window_width, 
            height=self.window_height,
            collapsed=False
        ):
            with dpg.group(horizontal=True):
                # Each group can act like a column of controls
                self.create_connection_controls()
                self.create_basic_controls()
                self.create_attenuator_controls()
                self.create_output_controls()
                self.create_power_readbacks()
                self.create_preset_controls()
                self.create_chiller_controls()

        # Optionally, you can do a first-time read or connection test here
        if not simulation:
            self.connect_device()

    # --------------------------------------------------------------------------
    # Helper / Internal
    # --------------------------------------------------------------------------
    def _get_unique_id_from_device(self) -> str:
        """
        Returns a unique ID string for this device/GUI instance.
        Here, we just use the device's base URL or memory ID.
        """
        if hasattr(self.dev, "base_url"):
            return self.dev.base_url
        else:
            return str(id(self.dev))

    def connect_device(self):
        """
        A placeholder 'connect' action. 
        The PharosLaserAPI does not have a direct 'connect' call, 
        but you can do an initial test (e.g., getBasic()) to check availability.
        """
        print("Testing laser availability...")
        try:
            _ = self.dev.getBasic()  # Just a test call
            dpg.set_item_label(self.window_tag, f"{self.window_label} (online)")
            print("Laser is online.")
        except Exception as e:
            print(f"Error connecting to laser: {e}")
            dpg.set_item_label(self.window_tag, f"{self.window_label} (offline)")

    def toggle_gui_collapse(self):
        """
        Collapses/expands the entire set of controls for a more compact UI.
        """
        if self.is_collapsed:
            print("Expanding laser GUI window")
            for item in [
                "conn_controls",
                "basic_controls",
                "attenuator_controls",
                "output_controls",
                "power_readbacks",
                "preset_controls",
                "chiller_controls",
            ]:
                dpg.show_item(f"{item}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, self.window_width)
            dpg.set_item_height(self.window_tag, self.window_height)
        else:
            print("Collapsing laser GUI window")
            for item in [
                "conn_controls",
                "basic_controls",
                "attenuator_controls",
                "output_controls",
                "power_readbacks",
                "preset_controls",
                "chiller_controls",
            ]:
                dpg.hide_item(f"{item}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    # --------------------------------------------------------------------------
    # GUI Section Creators
    # --------------------------------------------------------------------------
    def create_connection_controls(self):
        with dpg.group(horizontal=False, tag=f"conn_controls_{self.unique_id}", width=self.child_width):
            dpg.add_text("Connection")
            dpg.add_button(label="Toggle Collapse", callback=lambda: self.toggle_gui_collapse())
            dpg.add_button(label="Connect/Test", callback=lambda: self.connect_device())

    def create_basic_controls(self):
        """
        A group of basic on/off/standby commands for the laser.
        """
        with dpg.group(horizontal=False, tag=f"basic_controls_{self.unique_id}", width=self.child_width):
            dpg.add_text("Basic Controls")
            dpg.add_button(label="Turn On", callback=self.btn_turn_on)
            dpg.add_button(label="Turn Off", callback=self.btn_turn_off)
            dpg.add_button(label="Standby", callback=self.btn_standby)

    def create_attenuator_controls(self):
        """
        A group for controlling the attenuator percentage and reading back its current value.
        """
        with dpg.group(horizontal=False, tag=f"attenuator_controls_{self.unique_id}", width=self.child_width * 1.2):
            dpg.add_text("Attenuator (%)")
            dpg.add_button(label="Get Atten.", callback=self.btn_get_attenuator)
            dpg.add_input_float(
                label="Set Atten.",
                tag=f"input_atten_{self.unique_id}",
                default_value=0.0,
                min_value=0.0,
                max_value=100.0,
                format="%.1f"
            )
            dpg.add_button(label="Set", callback=self.btn_set_attenuator)

    def create_output_controls(self):
        """
        A group for enabling/closing the laser output shutter, etc.
        """
        with dpg.group(horizontal=False, tag=f"output_controls_{self.unique_id}", width=self.child_width):
            dpg.add_text("Output Controls")
            dpg.add_button(label="Enable Output", callback=self.btn_enable_output)
            dpg.add_button(label="Close Output", callback=self.btn_close_output)
            dpg.add_button(label="Is Output Open?", callback=self.btn_is_output_open)

    def create_power_readbacks(self):
        """
        A group for reading back power/frequency info.
        """
        with dpg.group(horizontal=False, tag=f"power_readbacks_{self.unique_id}", width=self.child_width*1.3):
            dpg.add_text("Measurements")
            dpg.add_button(label="Refresh Power", callback=self.btn_refresh_power)
            dpg.add_text("", tag=f"power_text_{self.unique_id}")
            dpg.add_button(label="Refresh Freq.", callback=self.btn_refresh_frequency)
            dpg.add_text("", tag=f"freq_text_{self.unique_id}")

    def create_preset_controls(self):
        """
        A group for preset selection, applying, etc.
        """
        with dpg.group(horizontal=False, tag=f"preset_controls_{self.unique_id}", width=self.child_width):
            dpg.add_text("Preset")
            dpg.add_button(label="Get Selected", callback=self.btn_get_preset)
            dpg.add_input_int(label="Set Preset", tag=f"input_preset_{self.unique_id}", default_value=0)
            dpg.add_button(label="Apply Preset", callback=self.btn_apply_preset)

    def create_chiller_controls(self):
        """
        A group for turning the chiller on/off and controlling set temperature (if available).
        """
        with dpg.group(horizontal=False, tag=f"chiller_controls_{self.unique_id}", width=self.child_width*1.3):
            dpg.add_text("Chiller (if available)")
            dpg.add_button(label="Turn On", callback=self.btn_turn_on_chiller)
            dpg.add_button(label="Turn Off", callback=self.btn_turn_off_chiller)
            dpg.add_button(label="Read Actual Temp", callback=self.btn_get_chiller_temp)
            dpg.add_text("", tag=f"chiller_temp_text_{self.unique_id}")
            dpg.add_input_float(
                label="Set Temp",
                tag=f"chiller_temp_input_{self.unique_id}",
                default_value=20.0,
                format="%.1f"
            )
            dpg.add_button(label="Apply", callback=self.btn_set_chiller_temp)

    # --------------------------------------------------------------------------
    # Callbacks for Basic Controls
    # --------------------------------------------------------------------------
    def btn_turn_on(self):
        if self.simulation:
            print("[SIM] Laser Turn On")
        else:
            try:
                self.dev.turnOn()
                print("Laser turned on.")
            except Exception as e:
                print(f"Error turning on laser: {e}")

    def btn_turn_off(self):
        if self.simulation:
            print("[SIM] Laser Turn Off")
        else:
            try:
                self.dev.turnOff()
                print("Laser turned off.")
            except Exception as e:
                print(f"Error turning off laser: {e}")

    def btn_standby(self):
        if self.simulation:
            print("[SIM] Laser Standby")
        else:
            try:
                self.dev.goToStandby()
                print("Laser is now in Standby.")
            except Exception as e:
                print(f"Error setting laser to Standby: {e}")

    # --------------------------------------------------------------------------
    # Callbacks for Attenuator
    # --------------------------------------------------------------------------
    def btn_get_attenuator(self):
        if self.simulation:
            print("[SIM] Getting attenuator (fake 50%)")
            dpg.set_value(f"input_atten_{self.unique_id}", 50.0)
        else:
            try:
                val = self.dev.getBasicTargetAttenuatorPercentage()
                # The API might return a dict or a single value. Adjust as needed:
                # e.g., val might be {"TargetAttenuatorPercentage": 73.0}
                if isinstance(val, dict):
                    val = val.get("TargetAttenuatorPercentage", 0.0)
                dpg.set_value(f"input_atten_{self.unique_id}", float(val))
                print(f"Current Attenuator: {val}%")
            except Exception as e:
                print(f"Error getting attenuator: {e}")

    def btn_set_attenuator(self):
        if self.simulation:
            print("[SIM] Setting attenuator")
        else:
            try:
                new_val = dpg.get_value(f"input_atten_{self.unique_id}")
                self.dev.setBasicTargetAttenuatorPercentage(new_val)
                print(f"Attenuator set to {new_val}%")
            except Exception as e:
                print(f"Error setting attenuator: {e}")

    # --------------------------------------------------------------------------
    # Callbacks for Output
    # --------------------------------------------------------------------------
    def btn_enable_output(self):
        if self.simulation:
            print("[SIM] Enabling laser output")
        else:
            try:
                self.dev.enableOutput()
                print("Output enabled.")
            except Exception as e:
                print(f"Error enabling output: {e}")

    def btn_close_output(self):
        if self.simulation:
            print("[SIM] Closing laser output")
        else:
            try:
                self.dev.closeOutput()
                print("Output closed.")
            except Exception as e:
                print(f"Error closing output: {e}")

    def btn_is_output_open(self):
        if self.simulation:
            print("[SIM] Output is open? Let's pretend it's True.")
        else:
            try:
                is_open = self.dev.getBasicIsOutputOpen()
                # Might be { "IsOutputOpen": True } or just a boolean.
                if isinstance(is_open, dict):
                    is_open = is_open.get("IsOutputOpen", False)
                print(f"Output open? {is_open}")
            except Exception as e:
                print(f"Error reading output state: {e}")

    # --------------------------------------------------------------------------
    # Callbacks for Power & Frequency Readbacks
    # --------------------------------------------------------------------------
    def btn_refresh_power(self):
        if self.simulation:
            print("[SIM] Power ~2.50 W")
            dpg.set_value(f"power_text_{self.unique_id}", "Power: 2.50 W [SIM]")
        else:
            try:
                val = self.dev.getBasicActualOutputPower()
                # Possibly returns a dict or float
                if isinstance(val, dict):
                    val = val.get("ActualOutputPower", 0.0)
                text_val = f"Power: {val:.2f} W"
                dpg.set_value(f"power_text_{self.unique_id}", text_val)
                print(text_val)
            except Exception as e:
                print(f"Error reading power: {e}")

    def btn_refresh_frequency(self):
        if self.simulation:
            print("[SIM] Freq ~100 kHz")
            dpg.set_value(f"freq_text_{self.unique_id}", "Frequency: 100 kHz [SIM]")
        else:
            try:
                val = self.dev.getBasicActualOutputFrequency()
                if isinstance(val, dict):
                    val = val.get("ActualOutputFrequency", 0.0)
                text_val = f"Frequency: {val:.2f} Hz"
                dpg.set_value(f"freq_text_{self.unique_id}", text_val)
                print(text_val)
            except Exception as e:
                print(f"Error reading frequency: {e}")

    # --------------------------------------------------------------------------
    # Callbacks for Preset
    # --------------------------------------------------------------------------
    def btn_get_preset(self):
        if self.simulation:
            print("[SIM] Current preset = 1")
            dpg.set_value(f"input_preset_{self.unique_id}", 1)
        else:
            try:
                val = self.dev.getBasicSelectedPresetIndex()
                # Possibly a dict, e.g., { "SelectedPresetIndex": 2 }
                if isinstance(val, dict):
                    val = val.get("SelectedPresetIndex", 0)
                print(f"Current preset = {val}")
                dpg.set_value(f"input_preset_{self.unique_id}", val)
            except Exception as e:
                print(f"Error getting preset: {e}")

    def btn_apply_preset(self):
        if self.simulation:
            print("[SIM] Applying preset")
        else:
            try:
                new_preset = dpg.get_value(f"input_preset_{self.unique_id}")
                # set new preset
                self.dev.setBasicSelectedPresetIndex(new_preset)
                print(f"Selected preset: {new_preset}")
                # apply it
                self.dev.applySelectedPreset()
                print("Preset applied.")
            except Exception as e:
                print(f"Error applying preset: {e}")

    # --------------------------------------------------------------------------
    # Callbacks for Chiller
    # --------------------------------------------------------------------------
    def btn_turn_on_chiller(self):
        if self.simulation:
            print("[SIM] Turn on chiller")
        else:
            try:
                self.dev.turnOnChiller()
                print("Chiller turned on.")
            except Exception as e:
                print(f"Error turning on chiller: {e}")

    def btn_turn_off_chiller(self):
        if self.simulation:
            print("[SIM] Turn off chiller")
        else:
            try:
                self.dev.turnOffChiller()
                print("Chiller turned off.")
            except Exception as e:
                print(f"Error turning off chiller: {e}")

    def btn_get_chiller_temp(self):
        if self.simulation:
            print("[SIM] Chiller temp is 20.0")
            dpg.set_value(f"chiller_temp_text_{self.unique_id}", "20.0 °C [SIM]")
        else:
            try:
                val = self.dev.getChillerActualTemperature()
                # Possibly returns a dict or float
                if isinstance(val, dict):
                    val = val.get("ActualTemperature", 0.0)
                dpg.set_value(f"chiller_temp_text_{self.unique_id}", f"{val:.1f} °C")
                print(f"Chiller temperature: {val:.1f} °C")
            except Exception as e:
                print(f"Error reading chiller temperature: {e}")

    def btn_set_chiller_temp(self):
        if self.simulation:
            print("[SIM] Setting chiller setpoint to input value")
        else:
            try:
                new_temp = dpg.get_value(f"chiller_temp_input_{self.unique_id}")
                self.dev.setChillerTargetTemperature(new_temp)
                print(f"Chiller setpoint set to {new_temp} °C")
            except Exception as e:
                print(f"Error setting chiller temperature: {e}")


def main():
    # 1. Create context
    dpg.create_context()

    # 2. Create viewport
    dpg.create_viewport(title="Pharos Laser GUI", width=1200, height=600)


    laserIP = "192.168.101.58"
    port = "20022"
    laser_api = PharosLaserAPI(laserIP, port)

    # -- Instantiate your GUI class (which internally creates windows/groups)
    gui_pharos = GUIPharosLaser(laser_api, simulation=False)

    # 4. Setup dearpygui
    dpg.setup_dearpygui()

    # 5. Show viewport
    dpg.show_viewport()

    # 6. Start the GUI
    dpg.start_dearpygui()

    # 7. Destroy context
    dpg.destroy_context()

if __name__ == "__main__":
    main()

# ------------------------------------------------------------------------------
# HOW TO USE THIS GUI
# ------------------------------------------------------------------------------
# 1. Install dearpygui: pip install dearpygui
# 2. Create an instance of PharosLaserAPI:
#      laser_api = PharosLaserAPI("192.168.101.58", 20022)
# 3. Create the GUI object:
#      gui = GUIPharosLaser(laser_api, simulation=False)
# 4. Start Dear PyGui:
#      dpg.start_dearpygui()
#
# Note: Adjust the layout, widths, and controls as suits your application.
#       You can also add periodic updates or watchers using dearpygui's
#       callback system or a separate refresh thread.
#
# Example run:
#   if __name__ == "__main__":
#       laser_api = PharosLaserAPI("192.168.101.58", 20022)
#       gui = GUIPharosLaser(laser_api, simulation=False)
#       dpg.start_dearpygui()

import dearpygui.dearpygui as dpg
from Common import DpgThemes
from HW_wrapper import HighlandT130
from SystemConfig import Instruments, load_instrument_images


class GUIHighlandT130:
    def __init__(self, device: HighlandT130, instrument: Instruments = Instruments.HIGHLAND, simulation: bool = False) -> None:
        """
        GUI class for controlling the Highland T130 EOM driver.

        :param device: Instance of HighlandT130 device.
        :param instrument: The instrument enum value.
        :param simulation: Flag to indicate if simulation mode is enabled.
        """
        self.is_collapsed: bool = False
        load_instrument_images()
        self.dev:HighlandT130 = device
        self.simulation:bool = simulation
        self.unique_id:str = self._get_unique_id_from_device()
        self.instrument:Instruments = instrument
        self.range:int = 1  # Default range is 1
        self.width = 1000
        self.height = 170
        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        self.window_tag = "HighlandT130_Win"
        with dpg.window(tag=self.window_tag, label=f"{self.instrument.value}",
                        no_title_bar=False, height=self.height, width=self.width, pos=[0, 0], collapsed=True):
            with dpg.group(horizontal=True):
                self.create_instrument_image()
                self.create_main_controls()

        if not simulation:
            self.toggle_connect()

    def _get_unique_id_from_device(self) -> str:
        """
        Generate a unique identifier for the GUI instance based on the device properties.

        :return: A string that uniquely identifies this device.
        """
        if hasattr(self.dev, 'serial_number') and self.dev.serial_number is not None:
            return self.dev.serial_number
        elif hasattr(self.dev, 'name') and self.dev.name is not None:
            return self.dev.name
        else:
            return str(id(self.dev))

    def create_instrument_image(self):
        with dpg.group(horizontal=False, tag=f"column_instrument_image_{self.unique_id}"):
            dpg.add_image_button(
                f"{self.instrument.value}_texture", width=100, height=100,
                callback=self.toggle_gui_collapse,
                user_data=None
            )
            self.create_connect_button()

    def create_main_controls(self):
        self.create_range_controls()
        self.create_timing_controls()
        self.create_amplitude_controls()
        self.create_bias_controls()
        self.create_save_load_controls()

    def create_range_controls(self):
        """
        Create the range selection controls with description for each range.
        """
        with dpg.group(horizontal=False, tag=f"column_range_{self.unique_id}"):
            dpg.add_text("Timing range")
            dpg.add_radio_button(items=["1 (0-5ns)", "2 (0-50ns)", "3 (0-300ns)"],
                                 tag=f"range_radio_{self.unique_id}", callback=self.set_range)

    def create_timing_controls(self):
        """
        Create the delay controls with enforced limits based on the selected range.
        """
        with dpg.group(horizontal=False, tag=f"column_timing_{self.unique_id}"):
            dpg.add_text("Delay (ns)")
            dpg.add_input_float(default_value=0.0, tag=f"delay_input_{self.unique_id}",
                                format='%.3f', width=200, callback=self.enforce_delay)
            dpg.add_text("Width (ns)")
            dpg.add_input_float(default_value=1.0, tag=f"width_input_{self.unique_id}",
                                format='%.3f', width=200, callback=self.enforce_width)

    def create_amplitude_controls(self):
        """
        Create the amplitude controls with enforced limits.
        """
        with dpg.group(horizontal=False, tag=f"column_amplitude_{self.unique_id}"):
            dpg.add_text("Amplitude (V)")
            dpg.add_input_float(default_value=-0.5, tag=f"amplitude_input_{self.unique_id}",
                                format='%.3f', width=200, min_value=-7.0, max_value=-0.5, callback=self.enforce_amplitude)
            dpg.add_text("-0.5V to -7V")

    def create_bias_controls(self):
        """
        Create the bias voltage controls with enforced limits.
        """
        with dpg.group(horizontal=False, tag=f"column_bias_{self.unique_id}"):
            dpg.add_text("Bias Voltage (V):")
            dpg.add_input_float(default_value=0.0, tag=f"bias_input_{self.unique_id}",
                                format='%.3f', width=200, min_value=-6.0, max_value=6.0, callback=self.enforce_bias)
            dpg.add_text("-6V to +6V")
            dpg.add_radio_button(items=["Internal", "External"], tag=f"bias_source_{self.unique_id}", horizontal=False, callback=self.enforce_bias)

    def set_range(self):
        """
        Set the range for the device and store the selected range.
        """
        try:
            self.range = int(dpg.get_value(f"range_radio_{self.unique_id}")[0])  # Get selected range number
            self.dev.set_range(self.range)
            print(f"Range set to {self.range}")
        except Exception as e:
            print(f"Error setting range: {e}")

    def enforce_delay(self):
        """
        Enforce the delay value to be within the limits based on the selected range.
        """
        delay = dpg.get_value(f"delay_input_{self.unique_id}")
        if self.range == 1:
            delay = max(0.0, min(delay, 5.0))  # Range 1: 0-5ns
        elif self.range == 2:
            delay = max(0.0, min(delay, 50.0))  # Range 2: 0-50ns
        elif self.range == 3:
            delay = max(0.0, min(delay, 300.0))  # Range 3: 0-300ns
        dpg.set_value(f"delay_input_{self.unique_id}", delay)
        self.dev.set_delay(delay)

    def enforce_width(self):
        """
        Enforce the width value to be within the limits based on the selected range.
        """
        width = dpg.get_value(f"width_input_{self.unique_id}")
        if self.range == 1:
            width = max(0.25, min(width, 5.0))  # Range 1: 250ps-5ns
        elif self.range == 2:
            width = max(0.5, min(width, 50.0))  # Range 2: 500ps-50ns
        elif self.range == 3:
            width = max(1.0, min(width, 300.0))  # Range 3: 1ns-300ns
        dpg.set_value(f"width_input_{self.unique_id}", width)
        self.dev.set_width(width)

    def enforce_amplitude(self):
        """
        Enforce the amplitude value to be within the allowed limits (-0.5V to -7V).
        """
        amplitude = dpg.get_value(f"amplitude_input_{self.unique_id}")
        amplitude = max(-7.0, min(amplitude, -0.5))  # Amplitude range: -0.5V to -7V
        dpg.set_value(f"amplitude_input_{self.unique_id}", amplitude)
        # The function accepts positive values. The output is negative.
        self.dev.set_amplitude(-amplitude)

    def enforce_bias(self):
        """
        Enforce the bias value to be within the allowed limits (-6V to +6V).
        """
        bias = dpg.get_value(f"bias_input_{self.unique_id}")
        bias = max(-6.0, min(bias, 6.0))  # Bias range: -6V to +6V
        source:bool = dpg.get_value(f"bias_source_{self.unique_id}") == "internal"
        dpg.set_value(f"bias_input_{self.unique_id}", bias)
        self.dev.set_bias(bias, internal= source)

    def create_save_load_controls(self):
        with dpg.group(horizontal=False, tag=f"column_save_load_{self.unique_id}"):
            dpg.add_text("Configurations")
            dpg.add_input_text(tag=f"config_name_{self.unique_id}", width=150)
            dpg.add_button(label="Save Config", callback=self.save_configuration)
            dpg.add_button(label="Recall Config", callback=self.recall_configuration)
            dpg.add_button(label="List Configs", callback=self.list_configurations)

    def create_connect_button(self):
        """
        Create a button that toggles between "Connect" and "Disconnect" depending on the connection status.
        """
        with dpg.group(horizontal=False, tag=f"column_connect_{self.unique_id}"):
            dpg.add_button(label="Connect", tag=f"connect_button_{self.unique_id}", callback=self.toggle_connect)

    def toggle_connect(self):
        """
        Toggle the connection status of the device. If the device is connected, it will disconnect and vice versa.
        """
        if self.dev.is_connected:
            self.disconnect()
            dpg.set_item_label(f"connect_button_{self.unique_id}", "Connect")
        else:
            self.connect()
            dpg.set_item_label(f"connect_button_{self.unique_id}", "Disconnect")
        self.get_status()

    def connect(self):
        """
        Connect the device and update the connect button label.
        """
        try:
            self.dev.connect()
            dpg.set_value(f"connect_button_{self.unique_id}", "Disconnect")
            print("Device connected.")
        except Exception as e:
            print(f"Error connecting: {e}")

    def disconnect(self):
        """
        Disconnect the device and update the connect button label.
        """
        try:
            self.dev.disconnect()
            dpg.set_value(f"connect_button_{self.unique_id}", "Connect")
            print("Device disconnected.")
        except Exception as e:
            print(f"Error disconnecting: {e}")

    def toggle_gui_collapse(self):
        columns = ['range', 'timing', 'amplitude', 'bias', 'save_load', 'connect']
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for col in columns:
                dpg.show_item(f"column_{col}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, self.width)
            dpg.set_item_height(self.window_tag, self.height)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for col in columns:
                dpg.hide_item(f"column_{col}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, 150)
            dpg.set_item_height(self.window_tag, 150)
        self.is_collapsed = not self.is_collapsed

    def get_status(self):
        try:
            status = self.dev.get_device_status() or self.instrument.value
            dpg.set_item_label(self.window_tag, f'{status} ({"connected" if self.dev.is_connected else "disconnected"})')
            print(f"Status: {status}")
        except Exception as e:
            print(f"Error getting status: {e}")

    def save_configuration(self):
        try:
            name = dpg.get_value(f"config_name_{self.unique_id}")
            self.dev.save_configuration(name)
            print(f"Configuration '{name}' saved.")
        except Exception as e:
            print(f"Error saving configuration: {e}")

    def recall_configuration(self):
        try:
            name = dpg.get_value(f"config_name_{self.unique_id}")
            self.dev.recall_configuration(name)
            print(f"Configuration '{name}' recalled.")
        except Exception as e:
            print(f"Error recalling configuration: {e}")

    def list_configurations(self):
        try:
            configs = self.dev.list_configurations()
            print(f"Available Configurations:\n{configs}")
        except Exception as e:
            print(f"Error listing configurations: {e}")

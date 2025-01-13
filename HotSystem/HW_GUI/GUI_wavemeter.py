import logging

import dearpygui.dearpygui as dpg
import numpy as np
from Common import DpgThemes
from HW_wrapper.wrapper_wavemeter import HighFinesseWLM  # or wherever your WLM wrapper is located
from SystemConfig import Instruments, load_instrument_images

import asyncio
import threading
import time

def run_asyncio_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


class GUIWavemeter:
    def __init__(self, device: HighFinesseWLM, instrument: Instruments = Instruments.WAVEMETER, simulation: bool = False) -> None:
        """
        GUI class for HighFinesse Wavemeter control.

        :param device: The HighFinesse WLM wrapper object.
        :param instrument: The Instruments enum identifier (e.g., Instruments.WAVEMETER).
        :param simulation: Flag to indicate if simulation mode is enabled.
        """
        self.is_collapsed = False
        load_instrument_images()  # If you have an instrument image for the WLM
        self.dev = device
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()
        self.instrument = instrument

        # --- Create an asyncio loop + thread for background tasks ---
        self.background_loop = asyncio.new_event_loop()
        t = threading.Thread(target=run_asyncio_loop,args=(self.background_loop,),daemon=True)
        t.start()

        # Data lists for real-time plotting
        self.start_time = time.time()
        self.time_data = []
        self.measurement_data = []

        # Flag to indicate if continuous measuring is active
        self.continuous_measure_active = False

        # Example: create a button theme (red) just like in GUI_matisse.py
        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        self.window_tag = f"WavemeterWin_{self.unique_id}"
        with dpg.window(
            tag=self.window_tag,
            label=f"{self.instrument.value}",
            no_title_bar=False,
            height=300,
            width=700,
            pos=[0, 0],
            collapsed=False
        ):
            with dpg.group(horizontal=True):
                self.create_instrument_image()
                self.create_wavemeter_controls(red_button_theme)

        # Store references to your main “column” groups, if you wish to hide/show them on collapse
        self.column_tags = [
            f"column_wavemeter_{self.unique_id}",
        ]

        # Attempt to connect immediately if not in simulation
        if not simulation:
            self.connect()

    def _get_unique_id_from_device(self) -> str:
        """Generate a unique identifier for the GUI instance based on the device properties."""
        # If your device has an "index" or an "addr", you can incorporate it into a unique string
        if hasattr(self.dev, "index") and self.dev.index is not None:
            return str(self.dev.index)
        # If your device uses an address
        if hasattr(self.dev, "addr") and self.dev.addr is not None:
            return str(self.dev.addr)
        return str(id(self.dev))

    def create_instrument_image(self):
        """
        Create an image button that toggles collapsing/expanding the GUI.
        If you have a .png or .jpg for your WLM, ensure `load_instrument_images()`
        has created a texture with the correct name. Otherwise, remove/replace this method.
        """
        with dpg.group(horizontal=False, tag=f"column_instrument_image_{self.unique_id}"):
            # Use your actual texture tag or remove the image if not available
            dpg.add_image_button(
                f"{self.instrument.value}_texture",  # e.g. "WAVEMETER_texture"
                width=80, height=80,
                callback=self.toggle_gui_collapse
            )

    def create_wavemeter_controls(self, theme):
        """
        Builds the main wavemeter controls (connect, channel, measure, display).
        """
        with dpg.group(horizontal=False, tag=f"column_wavemeter_{self.unique_id}", width=400):
            dpg.add_text("HighFinesse WLM Controls")

            # Connect/Disconnect Buttons
            dpg.add_button(label="Connect", callback=self.btn_connect)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Disconnect", callback=self.btn_disconnect)
            dpg.bind_item_theme(dpg.last_item(), theme)

            # Channel selection (if multi-channel device; optional)
            dpg.add_text("Channel:")
            dpg.add_input_int(default_value=0, tag=f"WLMChannel_{self.unique_id}", width=80)

            # Unit Selector
            dpg.add_text("Frequency Units:")
            dpg.add_combo(
                ["THz", "GHz", "MHz"],
                default_value="GHz",
                tag=f"UnitSelector_{self.unique_id}",
                width=100
            )

            # Wavelength display
            dpg.add_text("Wavelength (nm):", tag=f"WLM_Wavelength_Label_{self.unique_id}")

            dpg.add_button(label="Measure Once", callback=self.btn_measure)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Continuous Read", callback=self.toggle_continuous_measure)
            dpg.bind_item_theme(dpg.last_item(), theme)

            with dpg.plot(label="WLM Plot", height=300, width=700):
                # X-axis
                x_axis_tag = f"x_axis_{self.unique_id}"
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=x_axis_tag)
                # Y-axis
                y_axis_tag = f"y_axis_{self.unique_id}"
                with dpg.plot_axis(dpg.mvYAxis, label="Frequency", tag=y_axis_tag):
                    # A line series for wave data
                    dpg.add_line_series(
                        [], [], label="WLM Measurements", tag=f"wlm_measurement_series_{self.unique_id}"
                    )
            # Enable auto-fit for x and y axes
            dpg.fit_axis_data(x_axis_tag)
            dpg.fit_axis_data(y_axis_tag)

    def toggle_continuous_measure(self):
        """
        Starts or stops the continuous measure loop.
        Schedules the coroutine in the background event loop.
        """
        if not self.background_loop:
            print("Error: No background loop.")
            return

        if self.continuous_measure_active:
            # Stop the loop
            self.continuous_measure_active = False
            print("Continuous read stopped.")
        else:
            # Start the loop
            self.continuous_measure_active = True
            print("Continuous read started.")
            future = asyncio.run_coroutine_threadsafe(self.continuous_measure_loop(), self.background_loop)
            

    
    async def continuous_measure_loop(self):
        """
        Continuously reads WLM data (frequency) and updates the graph in selected units until stopped.
        """
        start_freq = 0
        try:
            # Get initial frequency
            start_freq = self.dev.get_frequency() * 1e-9  # Default in GHz
            print(f"Starting frequency: {start_freq:.6f} GHz")
        except Exception as exc:
            logging.error(f"Exception starting WLM measurement: {exc}")
            self.continuous_measure_active = False
            return

        concatenated_measurements = []
        concatenated_times = []
        x_axis_tag = f"x_axis_{self.unique_id}"
        y_axis_tag = f"y_axis_{self.unique_id}"

        while self.continuous_measure_active:
            try:
                # Get the current frequency
                freq_ghz = self.dev.get_frequency() * 1e-9 - start_freq  # Default in GHz

                # Convert frequency based on selected units
                unit = dpg.get_value(f"UnitSelector_{self.unique_id}")
                if unit == "THz":
                    freq_converted = freq_ghz * 1e-3  # GHz to THz
                    y_label = "Frequency (THz)"
                elif unit == "MHz":
                    freq_converted = freq_ghz * 1e3  # GHz to MHz
                    y_label = "Frequency (MHz)"
                else:  # Default is GHz
                    freq_converted = freq_ghz
                    y_label = "Frequency (GHz)"

                concatenated_measurements.append(freq_converted)
                elapsed_time_s = time.time() - self.start_time
                concatenated_times.append(elapsed_time_s)

                # Update the plot
                dpg.set_value(
                    f"wlm_measurement_series_{self.unique_id}",
                    [concatenated_times, concatenated_measurements]
                )
                # Update the Y-axis label
                dpg.configure_item(y_axis_tag, label=y_label)

                # Enable auto-fit for x and y axes
                
                dpg.fit_axis_data(x_axis_tag)
                dpg.fit_axis_data(y_axis_tag)

            except Exception as exc:
                logging.error(f"Exception in continuous_measure_loop: {exc}")
                break

            await asyncio.sleep(0.5)  # Update frequency every 0.5 seconds

    def save_graph_data(self):
        """
        Retrieves the current (time, wavelength) values from the WLM plot
        and writes them to a CSV file.
        """
        try:
            # Retrieve the 2D list [time_values, wavelength_values] from the plot
            time_values, wavelength_values = dpg.get_value(f"wlm_measurement_series_{self.unique_id}")

            if not time_values or not wavelength_values:
                dpg.set_value(f"WLM_Readout_Value_{self.unique_id}", "No data to save.")
                return

            # Write to CSV
            filename = "wavemeter_measurement_data.csv"
            with open(filename, "w", encoding="utf-8") as f:
                # Optional: write a header (adjust units/labels as needed)
                f.write("Time(s),Wavelength(nm)\n")
                for t, w in zip(time_values, wavelength_values):
                    f.write(f"{t},{w}\n")

            dpg.set_value(f"WLM_Readout_Value_{self.unique_id}", f"Data saved to {filename}")
        except Exception as exc:
            dpg.set_value(f"WLM_Readout_Value_{self.unique_id}", f"Error saving data: {exc}")

    def toggle_gui_collapse(self):
        """
        Collapse/expand the GUI, just like in GUIMatisse.
        """
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.show_item(column_tag)
            dpg.set_item_width(self.window_tag, 700)
            dpg.set_item_height(self.window_tag, 300)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.hide_item(column_tag)
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    def btn_connect(self):
        """Manual connect button callback."""
        self.connect()

    def btn_disconnect(self):
        """Manual disconnect button callback."""
        self.dev.close()
        dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} [DISCONNECTED]")

    def btn_measure(self):
        """Measure the wavelength from the WLM and update GUI labels, with exception handling."""
        try:
            if self.dev.is_connected:
                channel = dpg.get_value(f"WLMChannel_{self.unique_id}")
                # If your device’s get_wavelength() returns meters, multiply by 1e9 to convert to nm
                wavel_m = self.dev.get_wavelength(channel=channel)  # returns float or None
                if isinstance(wavel_m, float):
                    wavel_nm = wavel_m * 1e9
                    dpg.set_value(f"WLM_Wavelength_Label_{self.unique_id}", f"Wavelength (nm): {wavel_nm:.4f}")
                    print(f"Wavelength (nm): {wavel_nm:.4f}")
                else:
                    # wavel_m could be None or a string error code like "over", "under", etc.
                    dpg.set_value(f"WLM_Wavelength_Label_{self.unique_id}", "Wavelength (nm): (No Data)")
            else:
                dpg.set_value(f"WLM_Wavelength_Label_{self.unique_id}", "Wavelength (nm): (Not Connected)")
        except Exception as e:
            print(f"Error measuring wavelength: {e}")
            dpg.set_value(f"WLM_Wavelength_Label_{self.unique_id}", f"Wavelength (nm): Error -> {str(e)}")

    def connect(self):
        """Attempt to connect to the WLM and update the window label accordingly."""
        try:
            self.dev.connect()
            if self.dev.is_connected:
                dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} [CONNECTED]")
                print("Wavemeter connected.")
            else:
                dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} [NOT CONNECTED]")
        except Exception as e:
            print(f"Failed to connect to Wavemeter: {e}")
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} [NOT CONNECTED]")

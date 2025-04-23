import datetime
import logging

import dearpygui.dearpygui as dpg
import numpy as np
from Common import DpgThemes
from HW_wrapper.Wrapper_moku import Moku
from SystemConfig import Instruments, load_instrument_images

import asyncio
import threading
import time

def run_asyncio_loop(loop: asyncio.AbstractEventLoop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

class GUIMoku:
    def __init__(self, device:Moku, instrument: Instruments = Instruments.MOKU, simulation: bool = False) -> None:
        """
        GUI class for Moku Interferometer Stabilizer.

        :param moku_ip: IP address of the Moku device.
        """
        self.dev = device
        self.is_collapsed = False
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()
        self.instrument = instrument
        load_instrument_images()  # If you have an instrument image for the WLM

        # Data lists for real-time plotting
        self.start_time = time.time()
        self.time_data = []
        self.measurement_data = []

        # Flag to indicate if continuous measuring is active
        self.continuous_stream_active = False

        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        # --- Create an asyncio loop + thread for background tasks ---
        self.background_loop = asyncio.new_event_loop()
        t = threading.Thread(target=run_asyncio_loop, args=(self.background_loop,), daemon=True)
        t.start()

        self.window_tag = "Moku_Win"
        with dpg.window(tag=self.window_tag, label="Moku Interferometer Stabilizer", width=700, height=350, pos=[50, 50], collapsed=False):
            with dpg.group(horizontal=True):
                self.create_instrument_image()
                self.create_control_panel()

        # Store references to your main “column” groups, if you wish to hide/show them on collapse
        self.column_tags = [f"column_moku_{self.unique_id}"]

        # Attempt to connect immediately if not in simulation
        # if not simulation:
        #     self.connect()

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

    def toggle_gui_collapse(self):
        """
        Collapse/expand the GUI, just like in GUIMatisse.
        """
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.show_item(column_tag)
            dpg.set_item_width(self.window_tag, 700)
            dpg.set_item_height(self.window_tag, 350)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.hide_item(column_tag)
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    def create_control_panel(self):
        """
        Creates the control panel with buttons and input fields.
        """
        with dpg.group(horizontal=False,tag=f"column_moku_{self.unique_id}"):
            dpg.add_text("Device Information:")

            dpg.add_button(label="Show Info", callback=self.show_device_info)

            dpg.add_text("Control Panel:")

            # PID Reset Button
            dpg.add_button(label="Reset PID Windup", callback=self.reset_pid_windup)

            # Streaming Output
            dpg.add_button(label="Start Output Stream", callback=self.start_pid_output)

            # Threshold inputs
            dpg.add_text("Unwind Thresholds:")
            dpg.add_input_float(label="Lower Threshold", default_value=0.05,width=120, tag=f"lower_threshold_{self.unique_id}",callback=self.update_lower_threshold,)
            dpg.add_input_float(label="Upper Threshold", default_value=4.95,width=120, tag=f"upper_threshold_{self.unique_id}",callback=self.update_upper_threshold,)

            dpg.add_text("", tag=f"results_display_{self.unique_id}")


        with dpg.plot(label="MOKU Plot", height=300, width=400):
            # X-axis
            x_axis_tag = f"x_axis_{self.unique_id}"
            dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=x_axis_tag)
            # Y-axis
            y_axis_tag = f"y_axis_{self.unique_id}"
            with dpg.plot_axis(dpg.mvYAxis, label="Output (V)", tag=y_axis_tag):
                # A line series for wave data
                dpg.add_line_series(
                    [], [], label="MOKU Measurements", tag=f"moku_measurement_series_{self.unique_id}"
                )
        # Enable auto-fit for x and y axes
        dpg.fit_axis_data(x_axis_tag)
        dpg.fit_axis_data(y_axis_tag)

    def update_lower_threshold(self, sender, app_data):
        """
        Callback to update the lower threshold.

        :param sender: The DPG sender ID.
        :param app_data: The new value of the input field.
        """
        print(f"Lower threshold updated to: {app_data}")
        self.dev.lower_threshold = round(app_data,3)  # Directly update the device threshold

    def update_upper_threshold(self, sender, app_data):
        """
        Callback to update the upper threshold.

        :param sender: The DPG sender ID.
        :param app_data: The new value of the input field.
        """
        print(f"Upper threshold updated to: {app_data}")
        self.dev.upper_threshold = round(app_data,3)  # Directly update the device threshold

    def show_device_info(self):
        """
        Display the Moku device information in the console.
        """
        self.dev.print_device_info()

    def reset_pid_windup(self):
        """
        Reset the PID windup.
        """
        self.dev.reset_pid_windup()
        print("PID windup reset.")

    def start_pid_output(self):
        """
        Start streaming PID output data.
        """
        if not self.background_loop:
            print("Error: No background loop.")
            return

        if self.continuous_stream_active:
            # Stop the loop
            self.continuous_stream_active = False
            print("Continuous read stopped.")
        else:
            # Start the loop
            self.continuous_stream_active = True
            print("Continuous stream started.")
            future = asyncio.run_coroutine_threadsafe(self.continuous_measure_loop(), self.background_loop)


    async def continuous_measure_loop(self):
        concatenated_pid_data = []  # Store the collected PID data
        time_values: list[float] = []  # Store time values for the graph

        # Tags for the plot series and axes
        series_tag = f"moku_measurement_series_{self.unique_id}"
        x_axis_tag = f"x_axis_{self.unique_id}"
        y_axis_tag = f"y_axis_{self.unique_id}"
        start_time = time.time()

        while self.continuous_stream_active:
            try:
                if self.dev.concatenated_pid_data:
                    # Update the graph with new data
                    dpg.set_value(series_tag, [self.dev.time_values, self.dev.concatenated_pid_data])
                    dpg.set_value(f"results_display_{self.unique_id}", f"Graph updated with {len(concatenated_pid_data)} points.")
                    dpg.fit_axis_data(x_axis_tag)
                    dpg.fit_axis_data(y_axis_tag)
                else:
                    dpg.set_value(f"results_display_{self.unique_id}", "No valid PID data received.")
            except Exception as exc:
                dpg.set_value(f"results_display_{self.unique_id}", f"Error: {exc}")
                break

            await asyncio.sleep(0.5)

    def _get_unique_id_from_device(self) -> str:
        """Generate a unique identifier for the GUI instance based on the device properties."""
        return str(id(self.dev))


import asyncio
import logging
import threading
from typing import Optional, List
from HW_wrapper.Arduino.arduino_wrapper import ArduinoController

import dearpygui.dearpygui as dpg

def run_asyncio_loop(loop):
    """Runs an asyncio event loop in a dedicated thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()

class GUIArduino:
    """
    GUI interface for Arduino communication using DearPyGui.
    """

    def __init__(self, arduino: ArduinoController):
        """
        Initializes the GUI for Arduino control.

        :param arduino: The ArduinoController instance.
        """
        self.unique_id = "arduino_gui"
        self.continuous_read_active = False
        self.arduino = arduino
        self.measurement_data: Optional[List[float]] = None
        self.window_tag = "ArduinoWin"
        if arduino is None:
            arduino = ArduinoController(address="COM7")
            self.arduino = arduino

        # Subscribe GUI elements to observable fields
        self.arduino.communication_result.add_observer(self.update_results_display)
        self.arduino.num_points.add_observer(self.update_num_points)
        self.arduino.time_interval_us.add_observer(self.update_time_interval)

        # 1. Create the background loop

        self.background_loop = asyncio.new_event_loop()

        # 2. Start the loop in a separate thread
        t = threading.Thread(target=run_asyncio_loop, args=(self.background_loop,), daemon=True)
        t.start()

        # Create GUI window
        with dpg.window(tag=self.window_tag, label="Arduino Communication", width=650, height=800):
            dpg.add_text("Arduino Communication Panel", color=(0, 255, 0))

            # Input Fields
            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Points", tag="num_points", default_value=self.arduino.num_points.get(),
                                  callback=self.set_num_points,width=150)
                dpg.add_input_int(label="Time", tag="time_interval", default_value=self.arduino.time_interval_us.get(),
                                  callback=self.set_time_interval,width=150)

            with dpg.group(horizontal=True):
                dpg.add_button(label="Start", callback=self.arduino.start_measurement)
                dpg.add_button(label="Read", callback=self.read_measurement_and_update_graph)
                dpg.add_button(label="Cont Read", callback=self.toggle_continuous_read)
                dpg.add_button(label="Save Data", callback=self.save_graph_data)

            # --- Pulse Generation Controls ---
            with dpg.group(horizontal=True):
                dpg.add_input_float(label="Width", default_value=100.0, tag="pulse_width", format="%.1f",width=100)
                dpg.add_input_float(label="Spacing", default_value=1000.0, tag="pulse_spacing", format="%.1f",width=100)
                dpg.add_button(label="Set",callback=self.set_pulse,width=50)
                dpg.add_button(label="Stop",callback=self.stop_pulse,width=50)
                # Response Display
                dpg.add_text("Results:", tag="results_label")
                dpg.add_text("", tag="results_display", wrap=450)

            with dpg.plot(label="Measurement Plot", height=300, width=400):
                x_axis_tag = f"x_axis_{self.unique_id}"
                y_axis_tag = f"y_axis_{self.unique_id}"
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)",tag=x_axis_tag)
                with dpg.plot_axis(dpg.mvYAxis, label="Measurement",tag=y_axis_tag):
                    dpg.add_line_series([], [], label="My Measurements", tag="measurement_series")


    def update_results_display(self, result: str):
        """
        Updates the GUI text element when new data is received.
        """
        dpg.set_value("results_display", result)

    def update_num_points(self, value: int):
        """
        Updates the number of points field in the GUI.
        """
        dpg.set_value("num_points", value)

    def update_time_interval(self, value: int):
        """
        Updates the time interval field in the GUI.
        """
        dpg.set_value("time_interval", value)

    def set_num_points(self, sender, app_data):
        """
        Callback to update the observable num_points field when changed in GUI.
        """
        self.arduino.num_points.set(app_data)

    def set_time_interval(self, sender, app_data):
        """
        Callback to update the observable time_interval_us field when changed in GUI.
        """
        self.arduino.time_interval_us.set(app_data)

    def read_measurement_and_update_graph(self):
        """
        Reads measurement data from an Arduino via communication_result.get(),
        parses the data, and updates the corresponding graph in Dear PyGui.
        """
        try:
            # 1. Attempt to retrieve measurement data from the Arduino.
            measurement_data_raw = self.arduino.communication_result.get()

            # 2. Check if any data was returned.
            if not measurement_data_raw:
                dpg.set_value("results_display", "No data received.")
                return

            # 3. Ensure the data follows the expected "MEASURE:" prefix format.
            if not measurement_data_raw.startswith("MEASURE:"):
                dpg.set_value("results_display", f"Unexpected format: {measurement_data_raw}")
                return

            # 4. Parse measurement data. Example string: "MEASURE:123,456,789"
            try:
                data_str = measurement_data_raw.split(":", maxsplit=1)[1]  # e.g., "123,456,789"
                self.measurement_data = list(map(int, data_str.split(",")))
                with self.arduino.lock:
                    self.arduino.last_measured_value = self.measurement_data[-1]
            except (ValueError, IndexError) as parse_exc:
                dpg.set_value("results_display", f"Data parse error: {parse_exc}")
                return

            # 5. Prepare data for the graph:
            #    - time_values: x-axis based on the time interval
            #    - measurement_values: y-axis with the parsed measurements
            time_interval = self.arduino.time_interval_us.get()
            time_values = [i * time_interval*1e-3 for i in range(len(self.measurement_data))]

            # 6. Update the plot series in Dear PyGui, if it exists.
            if dpg.does_item_exist("measurement_series"):
                dpg.set_value("measurement_series", [time_values, self.measurement_data])
                # dpg.set_axis_limits("y_axis", 0, 1024)
                dpg.set_axis_limits_auto("x_axis")
                dpg.set_axis_limits_auto("y_axis")
                dpg.set_value("results_display", "Graph updated successfully.")
            else:
                dpg.set_value("results_display", "Graph update failed: series not found.")
                print("Error: Plot series 'measurement_series' does not exist.")

        except Exception as exc:
            # Catch any unforeseen errors and display/log them.
            dpg.set_value("results_display", f"Error updating graph: {exc}")
            print(f"Exception occurred: {exc}")

    async def continuous_read_loop(self):
        """
        Continuously reads measurement data and updates the graph until stopped.
        """
        try:
            self.arduino.start_measurement()
        except Exception as exc:
            logging.error(f"!!!! Exception occurred: {exc}. Please correct this AKUM solution !!!!")
            self.arduino.reconnect()
            self.arduino.start_measurement()
            # TODO: make this not AKUM

        concatenated_measurements = []

        while self.continuous_read_active:
            try:
                # Wait for data from Arduino
                measurement_data_raw = self.arduino.communication_result.get()

                if measurement_data_raw and measurement_data_raw.startswith("MEASURE:"):
                    # Parse and concatenate measurement data
                    new_data = list(map(int, measurement_data_raw.split(":")[1].split(",")))
                    concatenated_measurements.extend(new_data)
                    with self.arduino.lock:
                        self.arduino.last_measured_value = new_data[-1]

                    # Update the graph
                    time_interval = self.arduino.time_interval_us.get()
                    time_values = [i * time_interval*1e-3/17 for i in range(len(concatenated_measurements))]
                    dpg.set_value("measurement_series", [time_values, concatenated_measurements])
                    dpg.set_value("results_display", f"Graph updated with {len(concatenated_measurements)} points.")
                    x_axis_tag = f"x_axis_{self.unique_id}"
                    y_axis_tag = f"y_axis_{self.unique_id}"
                    dpg.fit_axis_data(x_axis_tag)
                    dpg.fit_axis_data(y_axis_tag)       
                else:
                    dpg.set_value("results_display", "No valid data received.")
            except Exception as exc:
                dpg.set_value("results_display", f"Error: {exc}")
                break

            # Wait briefly before sending the next measure command
            await asyncio.sleep(0.5)  # Adjust the delay as needed
            try:
                self.arduino.start_measurement()
            except Exception as exc:
                logging.error(f"!!!! Exception occurred: {exc}. Please correct this AKUM solution !!!!")
                self.arduino.reconnect()

    def toggle_continuous_read(self):
        """Schedules continuous_read_loop() on the background loop."""

        if not self.background_loop:
            dpg.set_value("results_display", "Error: No background loop.")
            return

        if self.continuous_read_active:
            # Stop the loop
            self.continuous_read_active = False
            dpg.set_value("results_display", "Continuous read stopped.")
        else:
            # Start the loop
            self.continuous_read_active = True
            dpg.set_value("results_display", "Continuous read started.")

            # Schedule the coroutine in the background loop
            future = asyncio.run_coroutine_threadsafe(self.continuous_read_loop(), self.background_loop)

    def save_graph_data(self):
        """
        Retrieves the current time and measurement values from the plot
        and writes them to a CSV file.
        """
        try:
            # Get the [time_values, measurement_values] from the plot
            time_values, measurement_values = dpg.get_value("measurement_series")

            if not time_values or not measurement_values:
                dpg.set_value("results_display", "No data to save.")
                return

            # Write to CSV
            filename = "measurement_data.csv"
            with open(filename, "w", encoding="utf-8") as f:
                # Optional: write a header
                f.write("Time(ms),Measurement\n")
                for t, m in zip(time_values, measurement_values):
                    f.write(f"{t},{m}\n")

            dpg.set_value("results_display", f"Data saved to {filename}")
        except Exception as exc:
            dpg.set_value("results_display", f"Error saving data: {exc}")

    def set_pulse(self, sender, app_data):
        """
        Callback for the "Set Pulse" button.
        Reads pulse_width_us and pulse_spacing_us from the input fields,
        and calls self.arduino.set_pulse(...) on the device wrapper.
        """
        try:
            # Read pulse width and spacing from the input fields
            pulse_width = dpg.get_value("pulse_width")
            pulse_spacing = dpg.get_value("pulse_spacing")

            # Check for valid values
            if pulse_width <= 0 or pulse_spacing <= 0:
                dpg.set_value("results_display", "Pulse width and spacing must be greater than 0.")
                return

            # The `set_pulse` method expects integers, so convert them
            self.arduino.set_pulse(int(pulse_width), int(pulse_spacing))

            # Feedback to the user
            dpg.set_value("results_display", f"Pulse set: Width = {pulse_width} μs, Spacing = {pulse_spacing} μs.")
        except ValueError as e:
            dpg.set_value("results_display", f"Invalid input: {e}")
        except Exception as e:
            dpg.set_value("results_display", f"Error setting pulse: {e}")

    def stop_pulse(self, sender, app_data):
        """
        Callback for the "Stop Pulse" button.
        Calls self.arduino.stop_pulse() on the device wrapper.
        """
        try:
            # Call the stop_pulse method
            self.arduino.stop_pulse()

            # Provide feedback to the user
            dpg.set_value("results_display", "Pulse generation stopped.")
        except Exception as e:
            dpg.set_value("results_display", f"Error stopping pulse: {e}")

    def window_moved_callback(sender, app_data):
        """
        Called whenever the user moves a window that has this callback attached.

        :param sender: The tag (string) of the window being moved.
        :param app_data: Typically the new position [x, y] of the window (provided by Dear PyGui).
        """
        # You can get the updated position from app_data or by using dpg.get_item_pos(sender)
        new_pos = dpg.get_item_pos(sender)
        # print(f"Window '{sender}' moved. New position: {new_pos}")

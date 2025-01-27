from datetime import datetime, timedelta
import time
import threading
import asyncio

import dearpygui.dearpygui as dpg
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from SystemConfig import Instruments, load_instrument_images

from HW_wrapper.SRS_PID.wrapper_sim960_pid import SRSsim960, AutoTuneMethod

def run_asyncio_loop(loop):
    """Helper function to run an asyncio loop in a separate thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()

class GUISIM960:
    """
    A Dear PyGui-based GUI for controlling an SRS SIM960 PID controller.

    Usage:
        gui = GUISIM960(sim960_instance)
        gui.show()
        # Then somewhere:
        dpg.start_dearpygui()

    This follows a style similar to the example provided in the prompt.
    """

    def __init__(self, sim960: SRSsim960, instrument: Instruments = Instruments.SIM960, simulation: bool = False) -> None:
        """
        Create the GUI for an SRSsim960 device.

        :param sim960: An instance of SRSsim960 wrapper (the device to control).
        :param simulation: Whether we are in simulation mode (disables hardware actions).
        """
        self.continuous_read_active = False
        self.stabilize_iterations = 1
        self.stabilize_measure_delay = 0.5
        self.stabilize_measure_count = 1
        self.stabilize_span = 2
        self.stabilize_step = 0.2
        self.stabilize_running = False
        self.new_setpoint = None
        self.dev = sim960
        self.simulation = simulation
        self.is_collapsed = False
        self.instrument = instrument
        self.unique_id = self._get_unique_id_from_device()
        self.win_tag = "SIM960_Win"
        self.win_label = f"SRS SIM960, slot {self.dev.slot} ({self.unique_id})"
        self.background_loop = asyncio.new_event_loop()
        self.lock = threading.Lock()
        t = threading.Thread(
            target=run_asyncio_loop,
            args=(self.background_loop,),
            daemon=True
        )
        t.start()

        if self.simulation:
            self.win_label += " [SIMULATION]"


        # Create a main window for the device
        with dpg.window(tag=self.win_tag, label=self.win_label,
                        no_title_bar=False, height=400, width=1200, pos=[100, 100], collapsed=True):
            with dpg.group(horizontal=True):
                self.create_device_image()
                self.create_pid_controls()
                self.create_manual_controls()
                self.create_monitor_controls()
                self.create_stabilize_controls()

                # We can start an update loop if needed
        # For example, we might poll the device periodically to update displays:
        # In the real code, you'd start a thread or use a dearpygui timer. For brevity, omitted here.

    def _get_unique_id_from_device(self) -> str:
        """
        Generate a unique identifier (string) for this GUI instance based on
        the device's properties.
        """
        # If device has a 'serial_number', use it
        if hasattr(self.dev, 'serial_number') and self.dev.serial_number:
            return str(self.dev.serial_number)
        # If the device has a 'port' or 'name', that might work
        if hasattr(self.dev, 'port') and self.dev.port:
            return str(self.dev.port)
        # Fallback: use Python's id() to ensure it's unique
        return str(id(self.dev))

    def create_device_image(self):
        """
        Create a clickable image or button that toggles the GUI's collapsed state.
        In a real application, you'd load a texture or an icon. We'll just make a dummy button.
        """
        with dpg.group(horizontal=False, tag=f"column_img_{self.unique_id}"):
            # dpg.add_button(
            #     label="SIM960",
            #     width=80, height=80,
            #     callback=self.toggle_gui_collapse
            # )
            # Use your actual texture tag or remove the image if not available
            dpg.add_image_button(
                f"{self.instrument.value}_texture",  # e.g. "WAVEMETER_texture"
                width=80, height=80,
                callback=self.toggle_gui_collapse
            )

    def create_pid_controls(self):
        """
        Create controls for setting and reading P, I, D values, enabling/disabling them, etc.
        """
        with dpg.group(horizontal=False, tag=f"pid_controls_{self.unique_id}"):
            try:
                gain = self.dev.get_proportional_gain()
            except Exception as e:
                print("Session invalid. Reinitializing the connection...")
                self.dev.mf.disconnect()
                self.dev.mf.connect()
                gain = self.dev.get_proportional_gain()


            dpg.add_text("PID Gains")
            # Proportional
            with dpg.group(horizontal=True):
                dpg.add_input_float(label="P Gain", default_value=gain, # callback=self.cb_set_proportional_gain,
                    tag=f"p_gain_{self.unique_id}", format="%.4f", step=0.1, step_fast=1.0,width=100)
                dpg.add_checkbox(label="", default_value=True, callback=self.cb_enable_p, tag=f"enable_p_{self.unique_id}")
            # Integral
            with dpg.group(horizontal=True):
                dpg.add_input_float(label="I Gain", default_value=self.dev.get_integral_gain(), # callback=self.cb_set_integral_gain,
                    tag=f"i_gain_{self.unique_id}", format="%.6f", step=0.1, step_fast=1.0,width=100)
                dpg.add_checkbox(label="", default_value=False, callback=self.cb_enable_i, tag=f"enable_i_{self.unique_id}")
            # Derivative
            with dpg.group(horizontal=True):
                dpg.add_input_float(label="D Gain", default_value=self.dev.get_derivative_gain(), # callback=self.cb_set_derivative_gain,
                    tag=f"d_gain_{self.unique_id}", format="%.6f", step=0.1, step_fast=1.0,width=100)
                dpg.add_checkbox(label="", default_value=False, callback=self.cb_enable_d, tag=f"enable_d_{self.unique_id}")

            self.dev.enable_proportional(True)
            self.dev.enable_integral(True)            

            dpg.add_button(label="Get PID Gains", callback=self.cb_get_pid_gains, tag=f"get_pid_gains_{self.unique_id}")

            dpg.add_button(label="Set PID Gains", callback=self.cb_set_pid_gains, tag=f"set_pid_gains_{self.unique_id}")

            # Read the current setpoint from the device
            try:
                current_setpoint = self.dev.read_setpoint()
            except Exception as e:
                print(f"Error reading setpoint during initialization: {e}")
                current_setpoint = 0.0  # Fallback to a default value

        # # --- The new combo to select an auto-tune method ---
            with dpg.group(horizontal=False):
                dpg.add_text("Auto-Tune Method:")
                dpg.add_combo(label="Method", items=["ZIEGLER_NICHOLS", "COHEN_COON", "TYREUS_LUYBEN", "OTHER"],  # or any you want
                    default_value="ZIEGLER_NICHOLS", tag=f"auto_tune_method_{self.unique_id}", width=100)
                # --- Button to run auto-tuning ---
                dpg.add_button(label="Auto-Tune PID", callback=self.cb_run_auto_tune, user_data=None  # We can pass self here if needed
                )
                # Button to halt auto-tune
                dpg.add_button(label="Halt Auto-Tune", callback=self.cb_halt_auto_tune)

                # New setpoint control
                dpg.add_input_float(label="Setpoint [V]", default_value=current_setpoint, callback=self.cb_set_new_setpoint, tag=f"setpoint_{self.unique_id}", format="%.3f", width=100)
                dpg.add_button(label="Set New Setpoint", callback=self.cb_apply_new_setpoint)

            # A button to reset the device
            dpg.add_button(label="Reset Device", callback=self.cb_reset_device)

    def cb_get_pid_gains(self):
        """
        Callback to fetch the current PID gains from the device,
        update the GUI fields, and print the values to the console.
        """
        try:
            # Fetch PID gains from the device
            with self.lock:
                p_gain = self.dev.get_proportional_gain()
                i_gain = self.dev.get_integral_gain()
                d_gain = self.dev.get_derivative_gain()

            # Update the GUI fields
            dpg.set_value(f"p_gain_{self.unique_id}", p_gain)
            dpg.set_value(f"i_gain_{self.unique_id}", i_gain)
            dpg.set_value(f"d_gain_{self.unique_id}", d_gain)

            # Print to console
            print(f"Current PID Gains: P = {p_gain:.4f}, I = {i_gain:.6f}, D = {d_gain:.6f}")
        except Exception as e:
            print(f"Error fetching PID gains: {e}")

    def cb_set_pid_gains(self):
        """
        Callback to set the PID gains on the device based on the GUI fields.
        """
        try:
            # Retrieve PID gains from the GUI fields
            # Retrieve PID gains from the GUI fields with 3 decimal places of precision
            p_gain = round(dpg.get_value(f"p_gain_{self.unique_id}"), 3)
            i_gain = round(dpg.get_value(f"i_gain_{self.unique_id}"), 3)
            d_gain = round(dpg.get_value(f"d_gain_{self.unique_id}"), 3)

            # Set PID gains on the device
            self.dev.set_proportional_gain(p_gain)
            self.dev.set_integral_gain(i_gain)
            self.dev.set_derivative_gain(d_gain)

            # Print to console
            print(f"Set PID Gains: P = {p_gain:.4f}, I = {i_gain:.6f}, D = {d_gain:.6f}")
        except Exception as e:
            print(f"Error setting PID gains: {e}")

    def cb_set_new_setpoint(self, sender, app_data):
        """Callback to set the new setpoint value."""
        self.new_setpoint = float(dpg.get_value(sender))

    def cb_apply_new_setpoint(self):
        """Apply the new setpoint to the device."""
        try:
            if self.new_setpoint is None:
                self.new_setpoint = 0.0
            if not self.simulation:
                self.dev.set_setpoint(self.new_setpoint)
                print(f"New setpoint applied: {self.new_setpoint:.3f} V")
            else:
                print(f"Simulation mode: Setpoint would be {self.new_setpoint:.3f} V")
        except Exception as e:
            print(f"Error setting setpoint: {e}")

    def cb_halt_auto_tune(self):
        """
        Stop the auto-tune process by setting the flag to False.
        """
        if self.auto_tune_running:
            self.dev.auto_tune_running = False
            self.stabilize_running = False
            print("Halt auto-tune signal sent.")
        else:
            print("Auto-tune is not currently running.")

    def create_manual_controls(self):
        """
        Create controls for setting the device to manual mode or PID mode,
        and controlling manual output voltage, offset, etc.
        """
        with dpg.group(horizontal=False, tag=f"manual_controls_{self.unique_id}"):
            dpg.add_text("Output Mode")
            # Mode radio: manual or PID
            dpg.add_radio_button(
                items=["Manual", "PID"], default_value="PID",
                callback=self.cb_set_output_mode,
                tag=f"output_mode_{self.unique_id}"
            )

            # Manual output input
            dpg.add_text("Manual Output")
            dpg.add_input_float(label="Voltage", default_value=0.0, callback=self.cb_set_manual_output, tag=f"manual_out_{self.unique_id}", format="%.3f",width=100)

            # Output Offset
            dpg.add_text("Output Offset")
            dpg.add_input_float(label="Offset [V]", default_value=self.dev.get_output_offset(), callback=self.cb_set_output_offset, tag=f"output_offset_{self.unique_id}", format="%.3f",width=100)

            dpg.add_text("Step for Max Extinction")
            dpg.add_input_float(label="Step [V]", default_value=1.5,  # or whatever you prefer
                tag=f"goto_step_{self.unique_id}", format="%.3f",width=100)

            dpg.add_button(label="Stabilize",callback=self.cb_stabilize)
            dpg.add_button(label="Goto max extinction", callback=self.goto_max_ext)
            dpg.add_button(label="Jump to Zero", callback=self.cb_jump_to_zero)

    def create_stabilize_controls(self):
        """
        Create compact controls for the stabilize parameters in the GUI.
        """
        with dpg.group(horizontal=False, tag=f"stabilize_controls_{self.unique_id}", width=250):
            dpg.add_text("Stabilize Parameters")

            with dpg.group(horizontal=False):
                dpg.add_input_float(
                    label="Step", default_value=self.stabilize_step,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_step_{self.unique_id}",
                    format="%.2f", width=80
                )
                dpg.add_input_float(
                    label="Span", default_value=self.stabilize_span,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_span_{self.unique_id}",
                    format="%.2f", width=80
                )
                dpg.add_input_int(
                    label="Measure Count", default_value=self.stabilize_measure_count,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_measure_count_{self.unique_id}",
                    width=80
                )
                dpg.add_input_float(
                    label="Measure Delay", default_value=self.stabilize_measure_delay,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_measure_delay_{self.unique_id}",
                    format="%.2f", width=80
                )
                dpg.add_input_float(
                    label="# of Iterations", default_value=self.stabilize_iterations,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_iterations_{self.unique_id}",
                    format="%.2f", width=80
                )

            with dpg.group(horizontal=True):
                # Measurement Input Plot
                with dpg.plot(label="Measurement Input", height=200, width=400):
                    x_axis_tag = f"input_x_axis_{self.unique_id}"
                    y_axis_tag = f"input_y_axis_{self.unique_id}"
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=x_axis_tag)
                    with dpg.plot_axis(dpg.mvYAxis, label="Input Voltage (V)", tag=y_axis_tag):
                        dpg.add_line_series([], [], label="Measurement Input", tag=f"measurement_series_input_{self.unique_id}")

                # Output Voltage Plot
                with dpg.plot(label="Output Voltage", height=200, width=400):
                    x_axis_tag = f"output_x_axis_{self.unique_id}"
                    y_axis_tag = f"output_y_axis_{self.unique_id}"
                    dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=x_axis_tag)
                    with dpg.plot_axis(dpg.mvYAxis, label="Output Voltage (V)", tag=y_axis_tag):
                        dpg.add_line_series([], [], label="Output Voltage", tag=f"measurement_series_output_{self.unique_id}")



    def cb_update_stabilize_param(self, sender, app_data):
        """
        Callback to update the stabilize parameters when changed in the GUI.
        """
        if sender == f"stabilize_step_{self.unique_id}":
            self.stabilize_step = app_data
            print(f"Updated step to {self.stabilize_step:.2f}")
        elif sender == f"stabilize_span_{self.unique_id}":
            self.stabilize_span = app_data
            print(f"Updated span to {self.stabilize_span:.2f}")
        elif sender == f"stabilize_measure_count_{self.unique_id}":
            self.stabilize_measure_count = app_data
            print(f"Updated measure count to {self.stabilize_measure_count}")
        elif sender == f"stabilize_measure_delay_{self.unique_id}":
            self.stabilize_measure_delay = app_data
            print(f"Updated measure delay to {self.stabilize_measure_delay:.2f}")
        elif sender == f"stabilize_iterations_{self.unique_id}":
            self.stabilize_iterations = int(app_data)
            print(f"Updated measure delay to {self.stabilize_iterations:.2f}")

    def cb_stabilize(self) -> None:
        """
        Stabilize the output, measure readings, perform a parabolic fit for every iteration
        (only for values below 0.1), and set the output offset to the best estimate.
        After each iteration, measure around +1.7 ± 0.2 from the chosen voltage, record the
        maximal value, and include it in the results. Save data to a single CSV and plot.
        """
        try:
            # Parameters
            middle = self.dev.read_output_voltage()
            print(f"Middle (Current Output Voltage) = {middle:.3f} V")

            # Fetch parameters from GUI
            iterations = self.stabilize_iterations
            step = self.stabilize_step
            span = self.stabilize_span
            measure_count = self.stabilize_measure_count
            measure_delay = self.stabilize_measure_delay

            # Generate linear voltage range
            voltage_offsets = np.arange(-span / 2, span / 2 + step, step)

            for offset in voltage_offsets:
                if not -10.000 <= middle + offset <= 10.000:
                    raise ValueError(f"Voltage {middle + offset:.3f} V is out of range.")

            # Initialize data storage
            all_data = []
            chosen_voltages = []
            recorded_readings = []
            maximal_readings = []
            maximal_voltages = []
            iteration_times = []

            # Stabilization loop
            self.stabilize_running = True
            self.dev.set_output_mode(manual=True)
            colors = plt.cm.viridis(np.linspace(0, 1, iterations))

            # Get current timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for i in range(iterations):
                start_time = time.time()
                iteration_data = {"Iteration": [], "Set Voltage (V)": [], "Measured Reading": []}

                print(f"Iteration {i + 1}/{iterations}")
                for offset in voltage_offsets:
                    set_voltage = middle + offset
                    self.dev._write(f"MOUT {set_voltage:.3f}")
                    time.sleep(measure_delay)

                    measured_values = [
                        self.dev.read_measure_input() for _ in range(measure_count)
                    ]
                    avg_reading = sum(measured_values) / len(measured_values)
                    print(f"Measured values at Voltage {set_voltage:.3f} V: {avg_reading}")
                    iteration_data["Iteration"].append(i + 1)
                    iteration_data["Set Voltage (V)"].append(set_voltage)
                    iteration_data["Measured Reading"].append(avg_reading)

                # Append to all data
                all_data.extend(pd.DataFrame(iteration_data).to_dict('records'))

                # Record iteration time
                iteration_times.append(time.time() - start_time)

                # Perform parabolic fit
                readings = iteration_data["Measured Reading"]
                set_voltages = iteration_data["Set Voltage (V)"]

                filtered_indices = [idx for idx, val in enumerate(readings) if abs(val) < 0.1]
                filtered_voltages = [set_voltages[idx] for idx in filtered_indices]
                filtered_readings = [readings[idx] for idx in filtered_indices]

                if len(filtered_voltages) >= 3:
                    coefficients = np.polyfit(filtered_voltages, filtered_readings, 2)
                    if coefficients[0] > 0:
                        estimated_min_voltage = -coefficients[1] / (2 * coefficients[0])
                        if min(filtered_voltages) <= estimated_min_voltage <= max(filtered_voltages):
                            chosen_voltage = estimated_min_voltage
                        else:
                            chosen_voltage = set_voltages[np.argmin(readings)]
                    else:
                        chosen_voltage = set_voltages[np.argmin(readings)]
                else:
                    chosen_voltage = set_voltages[np.argmin(readings)]

                chosen_voltages.append(chosen_voltage)
                print(f"* * * * Chose voltage {chosen_voltage} * * * *")
                middle = chosen_voltage

                # Measure around chosen_voltage + 1.6 ± 0.3
                span_voltage_offsets = (
                    np.linspace(chosen_voltage - 1.3, chosen_voltage - 1.9, 10)
                    if chosen_voltage > 0
                    else np.linspace(chosen_voltage + 1.3, chosen_voltage + 1.9, 10)
                )
                span_readings = []
                for voltage in span_voltage_offsets:
                    self.dev._write(f"MOUT {voltage:.3f}")
                    time.sleep(measure_delay)
                    span_measured_values = [
                        self.dev.read_measure_input() for _ in range(measure_count)
                    ]
                    span_avg_reading = sum(span_measured_values) / len(span_measured_values)
                    span_readings.append(span_avg_reading)

                print(f"Readings around Chosen Voltage + 1.6 ± 0.3:")
                for voltage, reading in zip(span_voltage_offsets, span_readings):
                    print(f"  Voltage: {voltage:.3f} V, Reading: {reading:.3f}")

                # Find maximal reading and corresponding voltage
                max_reading = max(span_readings)
                max_voltage = span_voltage_offsets[np.argmax(span_readings)]
                maximal_readings.append(max_reading)
                maximal_voltages.append(max_voltage)

                print(f"Maximal Reading: {max_reading:.3f} at Voltage: {max_voltage:.3f} V")

                final_voltage_offsets = np.linspace(chosen_voltage - 0.3, chosen_voltage + 0.3, 10)
                final_readings = []
                for voltage in final_voltage_offsets:
                    self.dev._write(f"MOUT {voltage:.3f}")
                    time.sleep(measure_delay)
                    final_measured_values = [
                        self.dev.read_measure_input() for _ in range(measure_count)
                    ]
                    avg_final_reading = (sum(final_measured_values) / len(final_measured_values))*1000
                    final_readings.append(avg_final_reading)
                    # Print each final reading
                    print(f"Voltage: {voltage:.3f} V, Final Reading: {avg_final_reading:.3f}")

                # Take the minimum reading from the measurements
                min_final_reading = min(final_readings)
                recorded_readings.append(min_final_reading)
                print(f"Minimum recorded reading within ±0.3 V around {chosen_voltage:.3f} V: {min_final_reading:.3f}")

            # Finalize
            final_voltage = chosen_voltages[-1]
            # self.dev.set_output_offset(final_voltage)

            # Save results to a single CSV
            df = pd.DataFrame(all_data)
            df["Chosen Voltage (V)"] = [v for v in chosen_voltages for _ in range(len(voltage_offsets))]
            df["Recorded Reading"] = [r for r in recorded_readings for _ in range(len(voltage_offsets))]
            df["Maximal Voltage (V)"] = [v for v in maximal_voltages for _ in range(len(voltage_offsets))]
            df["Maximal Reading"] = [r for r in maximal_readings for _ in range(len(voltage_offsets))]
            csv_filename = f"stabilization_results_{timestamp}.csv"
            df.to_csv(csv_filename, index=False)
            print(f"Results saved to {csv_filename}")

            # Plot results
            fig, axs = plt.subplots(1, 2, figsize=(12, 6))
            for i in range(iterations):
                axs[0].plot(
                    df[df["Iteration"] == i + 1]["Set Voltage (V)"],
                    df[df["Iteration"] == i + 1]["Measured Reading"],
                    'o-', color=colors[i],
                    label=f"Iteration {i + 1}"
                )
                axs[0].axvline(
                    chosen_voltages[i], color='red', linestyle='--',
                    label=f"Chosen Voltage: {chosen_voltages[i]:.3f}"
                )
            axs[0].set_title("Readings vs Set Voltage (All Iterations)")
            axs[0].set_xlabel("Set Voltage (V)")
            axs[0].set_ylabel("Measured Reading")
            axs[0].grid(True)
            axs[0].legend()

            axs[1].plot(np.cumsum(iteration_times), chosen_voltages, 'o-', color='blue', label="Chosen Voltages")
            axs[1].plot(np.cumsum(iteration_times), recorded_readings, 'o-', color='green', label="Minimal Readings x1000")
            axs[1].plot(np.cumsum(iteration_times), maximal_readings, 'o-', color='purple', label="Maximal Readings")
            axs[1].set_title("Convergence of Chosen Voltages and Readings Over Time")
            axs[1].set_xlabel("Time (s)")
            axs[1].set_ylabel("Value")
            axs[1].grid(True)
            axs[1].legend()

            plt.tight_layout()

            # Save figure
            figure_filename = f"stabilization_plot_{timestamp}.png"
            plt.savefig(figure_filename)
            print(f"Figure saved to {figure_filename}")
            plt.show()

        except Exception as e:
            print(f"Failed to stabilize output: {e}")
            raise

    def create_monitor_controls(self):
        """
        Create controls for reading the measured input or output.
        """
        with dpg.group(horizontal=False, tag=f"monitor_controls_{self.unique_id}"):
            dpg.add_text("Monitoring")
            # We'll show measure input or output
            dpg.add_button(label="Update Readings", callback=self.cb_update_measurement)
            dpg.add_text("Measure Input:", tag=f"measure_input_{self.unique_id}")
            dpg.add_text("Output Voltage:", tag=f"output_voltage_{self.unique_id}")
            dpg.add_button(label="Start/Stop Continuous Read", callback=self.cb_toggle_continuous_read)

            dpg.add_text("Output Limits")
            dpg.add_input_float(label="Upper Lim", default_value=self.dev.get_upper_limit(),  # Fetch initial value from device
                callback=self.cb_set_upper_limit, tag=f"upper_limit_{self.unique_id}", format="%.3f",width=100)
            dpg.add_button(label="Set Upper", callback=self.cb_apply_upper_limit)
            dpg.add_input_float(label="Lower Lim", default_value=self.dev.get_lower_limit(),  # Fetch initial value from device
                callback=self.cb_set_lower_limit, tag=f"lower_limit_{self.unique_id}", format="%.3f",width=100)
            dpg.add_button(label="Set Lower", callback=self.cb_apply_lower_limit)
            dpg.add_button(label="Get Limits", callback=self.cb_get_limits)

    def cb_set_upper_limit(self, sender, app_data):
        """Callback to set the new upper limit."""
        self.upper_limit = float(dpg.get_value(sender))

    def cb_apply_upper_limit(self):
        """Apply the new upper limit to the device."""
        try:
            if not self.simulation:
                self.dev.set_upper_limit(self.upper_limit)
                print(f"New upper limit applied: {self.upper_limit:.3f} V")
            else:
                print(f"Simulation mode: Upper limit would be {self.upper_limit:.3f} V")
        except Exception as e:
            print(f"Error setting upper limit: {e}")

    def cb_set_lower_limit(self, sender, app_data):
        """Callback to set the new lower limit."""
        self.lower_limit = float(dpg.get_value(sender))

    def cb_apply_lower_limit(self):
        """Apply the new lower limit to the device."""
        try:
            if not self.simulation:
                self.dev.set_lower_limit(self.lower_limit)
                print(f"New lower limit applied: {self.lower_limit:.3f} V")
            else:
                print(f"Simulation mode: Lower limit would be {self.lower_limit:.3f} V")
        except Exception as e:
            print(f"Error setting lower limit: {e}")

    def cb_get_limits(self):
        """Fetch the current limits and update the GUI fields."""
        try:
            upper = self.dev.get_upper_limit()
            lower = self.dev.get_lower_limit()

            dpg.set_value(f"upper_limit_{self.unique_id}", upper)
            dpg.set_value(f"lower_limit_{self.unique_id}", lower)

            print(f"Current Limits: Upper = {upper:.3f} V, Lower = {lower:.3f} V")
        except Exception as e:
            print(f"Error fetching limits: {e}")

    def cb_toggle_continuous_read(self):
        """
        Toggle continuous reading of measurement for the SRS device.
        Similar logic to the Arduino version: check loop, toggle active flag,
        and schedule or cancel the background task.
        """

        # 1) Check if the background loop exists
        if not self.background_loop:
            print("Error: No background loop. Cannot schedule continuous read.")
            return

        # 2) If continuous reading is already active, stop it
        if self.continuous_read_active:
            self.continuous_read_active = False
            print("Stopping continuous read...")

        # 3) Otherwise, start continuous reading
        else:
            self.continuous_read_active = True
            print("Starting continuous read...")

            # 4) Schedule the _continuous_read_task on the background loop
            # Option A: If your background_loop is an asyncio loop in another thread
            # you can do run_coroutine_threadsafe():
            asyncio.run_coroutine_threadsafe(self._continuous_read_task(), self.background_loop)

            # OR Option B: If you're *inside* the same thread running an asyncio loop:
            # self.background_loop.create_task(self._continuous_read_task())

    async def _continuous_read_task(self):
        """
        Continuously reads the device measurement once per second and prints the result.
        """
        time_values = []
        measurement_inputs = []
        output_voltages = []
        start_time = time.time()
        v_pi = 2.5

        while self.continuous_read_active:
            try:

                # Update the graph
                if dpg.does_item_exist(f"measurement_series_input_{self.unique_id}"):
                    dpg.set_value(f"measurement_series_input_{self.unique_id}", [self.dev.time_values, self.dev.measurement_inputs])
                    x_axis_tag = f"input_x_axis_{self.unique_id}"
                    y_axis_tag = f"input_y_axis_{self.unique_id}"
                    dpg.fit_axis_data(x_axis_tag)
                    dpg.fit_axis_data(y_axis_tag)
                    dpg.set_value(f"measurement_series_output_{self.unique_id}", [self.dev.time_values, self.dev.output_voltages])
                    x_axis_tag = f"output_x_axis_{self.unique_id}"
                    y_axis_tag = f"output_y_axis_{self.unique_id}"
                    dpg.fit_axis_data(x_axis_tag)
                    dpg.fit_axis_data(y_axis_tag)

                # Update GUI display with current measurement values
                dpg.set_value(f"measure_input_{self.unique_id}", f"Measure Input: {self.dev.measurement_inputs[-1]:.5f} V")
                dpg.set_value(f"output_voltage_{self.unique_id}", f"Output Voltage: {self.dev.output_voltages[-1]:.5f} V")

            except Exception as e:
                # Handle errors gracefully
                dpg.set_value(f"measure_input_{self.unique_id}", f"Error reading input: {e}")
                break

            # Sleep for 1 second in the asyncio world
            await asyncio.sleep(1.0)

    def cb_jump_to_zero(self):
        """
        Moves the SRS output voltage to a stable state near zero (synchronously).
        """
        try:
            print(f"jumping to 0")

            # Apply the offset multiple times for stabilization
            self.dev.set_manual_output(0)
            time.sleep(0.5)
            self.dev.set_output_mode(True)

            print(f"val = {self.dev.read_output_voltage()}")
            time.sleep(0.5)
            self.dev.set_manual_output(0)
            print(f"val = {self.dev.read_output_voltage()}")
            time.sleep(0.5)

            # Turn off manual output
            self.dev.set_output_mode(False)

            # Flush the output and mark the device as unstable
            #self.dev.mf.flush_output()
            self.dev.is_stable = False
            self.dev.last_stable_timestamp = datetime.now()

            print("Jump to zero completed.")
        except Exception as e:
            print(f"Error during Jump to Zero: {e}")

    def cb_set_proportional_gain(self, sender, app_data):
        """Callback to set the P gain on the device."""
        new_val = dpg.get_value(sender)
        if not self.simulation:
            self.dev.set_proportional_gain(new_val)

    def cb_set_integral_gain(self, sender, app_data):
        """Callback to set the I gain on the device."""
        new_val = dpg.get_value(sender)
        if not self.simulation:
            self.dev.set_integral_gain(new_val)

    def cb_set_derivative_gain(self, sender, app_data):
        """Callback to set the D gain on the device."""
        new_val = dpg.get_value(sender)
        if not self.simulation:
            self.dev.set_derivative_gain(new_val)

    def cb_enable_p(self, sender, app_data):
        """Enable or disable proportional action."""
        enable = dpg.get_value(sender)
        if not self.simulation:
            self.dev.enable_proportional(enable)

    def cb_enable_i(self, sender, app_data):
        """Enable or disable integral action."""
        enable = dpg.get_value(sender)
        if not self.simulation:
            self.dev.enable_integral(enable)

    def cb_enable_d(self, sender, app_data):
        """Enable or disable derivative action."""
        enable = dpg.get_value(sender)
        if not self.simulation:
            self.dev.enable_derivative(enable)

    def cb_reset_device(self):
        """Reset the device."""
        if not self.simulation:
            self.dev.reset()

    def goto_max_ext(self):
        """
        Moves the output by the amount specified in the 'Step for Max Extinction' float input.
        """
        # Read the current output voltage
        with self.lock:
            meas_output = self.dev.read_output_voltage()

        # Retrieve the user-entered step size
        step_value = dpg.get_value(f"goto_step_{self.unique_id}")

        # Now move output by step_value
        with self.lock:
            self.dev.set_manual_output(meas_output + step_value)

            self.dev.set_output_mode(True)
        dpg.set_value(f"output_mode_{self.unique_id}", True)

    def cb_set_output_mode(self, sender, app_data):
        """
        Callback to set manual or PID mode.
        """
        mode_str = dpg.get_value(sender)
        manual = (mode_str == "Manual")

        if manual: # set manual output to the PID value
            with self.lock:
                meas_output = self.dev.read_output_voltage()
                self.dev.set_manual_output(meas_output)

        if not self.simulation:
            with self.lock:
                self.dev.set_output_mode(manual)


    def cb_set_manual_output(self, sender, app_data):
        """
        Callback to set the manual output (MOUT).
        """
        new_val = dpg.get_value(sender)
        if not self.simulation:
            with self.lock:
                self.dev.set_manual_output(new_val)

    def cb_set_output_offset(self, sender, app_data):
        """
        Callback to set output offset.
        """
        new_val = round(dpg.get_value(sender),3)
        if not self.simulation:
            with self.lock:
                self.dev.set_output_offset(new_val)

    def cb_update_measurement(self):
        """
        Read the measure input and output from the device and update the labels.
        """
        try:
            with self.lock:  # Ensure thread-safe access
                if not self.simulation:
                    meas_input = self.dev.read_measure_input()
                    meas_output = self.dev.read_output_voltage()
                    middle = self.dev.get_output_offset()
                    print(f"Offset = {middle}")

                    dpg.set_value(f"measure_input_{self.unique_id}", f"Measure Input: {meas_input:.5f} V")
                    dpg.set_value(f"output_voltage_{self.unique_id}", f"Output Voltage: {meas_output:.5f} V")
                else:
                    # In simulation, just display dummy values
                    dpg.set_value(f"measure_input_{self.unique_id}", "Measure Input: 123.456 (sim)")
                    dpg.set_value(f"output_voltage_{self.unique_id}", "Output Voltage: 3.333 (sim)")
        except Exception as e:
            print(f"Error during measurement update: {e}")

    def toggle_gui_collapse(self):
        """
        Toggles whether the entire window is collapsed to show minimal info or expanded.
        """
        if self.is_collapsed:
            # Expand
            for section in ("pid_controls", "manual_controls", "monitor_controls"):
                dpg.show_item(f"{section}_{self.unique_id}")
            dpg.set_item_width(self.win_tag, 1300)
            dpg.set_item_height(self.win_tag, 400)
        else:
            # Collapse
            for section in ("pid_controls", "manual_controls", "monitor_controls"):
                dpg.hide_item(f"{section}_{self.unique_id}")
            dpg.set_item_width(self.win_tag, 150)
            dpg.set_item_height(self.win_tag, 150)
        self.is_collapsed = not self.is_collapsed

    def cb_run_auto_tune(self, sender, app_data, user_data):
        """
        Callback to run auto-tuning of the PID gains.
        """
        # Set the auto-tune running flag
        self.auto_tune_running = True
        
        # 1) Get which method the user selected in the combo.
        method_str = dpg.get_value(f"auto_tune_method_{self.unique_id}")

        # 2) Map the string to your AutoTuneMethod enum.
        #    Adjust as needed depending on your actual enum / code.
        #    If your enum is something like:
        #       class AutoTuneMethod(Enum):
        #           ZIEGLER_NICHOLS = 1
        #           COHEN_COON = 2
        #           TYREUS_LUYBEN = 3
        #           OTHER = 4
        #    then you can do:

        method_map = {
            "ZIEGLER_NICHOLS": AutoTuneMethod.ZIEGLER_NICHOLS,
            "COHEN_COON": AutoTuneMethod.COHEN_COON,
            "TYREUS_LUYBEN": AutoTuneMethod.TYREUS_LUYBEN,
            "OTHER": AutoTuneMethod.OTHER
        }
        selected_method = method_map.get(method_str, AutoTuneMethod.ZIEGLER_NICHOLS)

        try:
            # 3) Call auto_tune_pid with your desired parameters.
            #    For example:
            p_new, i_new, d_new = self.dev.auto_tune_pid(method=selected_method,
                                                         tune_time=3000.0,
                                                         max_gain=1000.0,
                                                         gain_step=1,
                                                         stable_cycles_required=3,
                                                         amplitude_threshold=0.02,
                                                         measure_count=15,
                                                         measure_delay=1)

            # 4) Update the device’s gains internally (optional).
            self.dev.set_proportional_gain(p_new)
            self.dev.set_integral_gain(i_new)
            self.dev.set_derivative_gain(d_new)

            # 5) Update the GUI so the user sees the new P, I, D.
            dpg.set_value(f"p_gain_{self.unique_id}", p_new)
            dpg.set_value(f"i_gain_{self.unique_id}", i_new)
            dpg.set_value(f"d_gain_{self.unique_id}", d_new)

            # Optionally, display a success message or popup
            print(f"Auto-tune complete: P={p_new}, I={i_new}, D={d_new}")

        except Exception as e:
            # If auto-tune fails (e.g., no stable oscillations found),
            # you might show an error popup or log the exception.
            print(f"Auto-tune failed: {e}")

    def show(self):
        """
        Make the GUI visible. Typically you'd call dpg.start_dearpygui() after this.
        """
        dpg.show_item(self.win_tag)



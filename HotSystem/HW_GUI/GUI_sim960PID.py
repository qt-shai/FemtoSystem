import time

import dearpygui.dearpygui as dpg
import numpy as np
from matplotlib import pyplot as plt

from HW_wrapper.SRS_PID.wrapper_sim960_pid import SRSsim960, AutoTuneMethod


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

    def __init__(self, sim960: SRSsim960, simulation: bool = False) -> None:
        """
        Create the GUI for an SRSsim960 device.

        :param sim960: An instance of SRSsim960 wrapper (the device to control).
        :param simulation: Whether we are in simulation mode (disables hardware actions).
        """
        self.stabilize_measure_delay = 0.2
        self.stabilize_measure_count = 5
        self.stabilize_span = 1
        self.stabilize_step = 0.1
        self.stabilize_running = False
        self.new_setpoint = None
        self.dev = sim960
        self.simulation = simulation
        self.is_collapsed = False
        self.unique_id = self._get_unique_id_from_device()
        self.win_tag = f"SIM960Win_{self.unique_id}"
        self.win_label = f"SRS SIM960, slot {self.dev.slot} ({self.unique_id})"
        if self.simulation:
            self.win_label += " [SIMULATION]"

        # Create a main window for the device
        with dpg.window(tag=self.win_tag, label=self.win_label,
                        no_title_bar=False, height=400, width=1300, pos=[100, 100], collapsed=False):
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
            dpg.add_button(
                label="SIM960",
                width=80, height=80,
                callback=self.toggle_gui_collapse
            )

    def create_pid_controls(self):
        """
        Create controls for setting and reading P, I, D values, enabling/disabling them, etc.
        """
        with dpg.group(horizontal=False, tag=f"pid_controls_{self.unique_id}", width=250):
            dpg.add_text("PID Gains")
            # Proportional
            with dpg.group(horizontal=True):
                dpg.add_input_float(
                    label="P Gain", default_value=self.dev.get_proportional_gain(),
                    callback=self.cb_set_proportional_gain,
                    tag=f"p_gain_{self.unique_id}",
                    format="%.4f", step=0.1, step_fast=1.0
                )
                dpg.add_checkbox(
                    label="", default_value=True,
                    callback=self.cb_enable_p, tag=f"enable_p_{self.unique_id}"
                )
            # Integral
            with dpg.group(horizontal=True):
                dpg.add_input_float(
                    label="I Gain", default_value=self.dev.get_integral_gain(),
                    callback=self.cb_set_integral_gain,
                    tag=f"i_gain_{self.unique_id}",
                    format="%.6f", step=0.1, step_fast=1.0
                )
                dpg.add_checkbox(
                    label="", default_value=False,
                    callback=self.cb_enable_i, tag=f"enable_i_{self.unique_id}"
                )
            # Derivative
            with dpg.group(horizontal=True):
                dpg.add_input_float(
                    label="D Gain", default_value=self.dev.get_derivative_gain(),
                    callback=self.cb_set_derivative_gain,
                    tag=f"d_gain_{self.unique_id}",
                    format="%.6f", step=0.1, step_fast=1.0
                )
                dpg.add_checkbox(
                    label="", default_value=False,
                    callback=self.cb_enable_d, tag=f"enable_d_{self.unique_id}"
                )

            # Read the current setpoint from the device
            try:
                current_setpoint = self.dev.read_setpoint()
            except Exception as e:
                print(f"Error reading setpoint during initialization: {e}")
                current_setpoint = 0.0  # Fallback to a default value

        # # --- The new combo to select an auto-tune method ---
            with dpg.group(horizontal=False):
                dpg.add_text("Auto-Tune Method:")
                dpg.add_combo(
                    label="Method",
                    items=["ZIEGLER_NICHOLS", "COHEN_COON", "TYREUS_LUYBEN", "OTHER"],  # or any you want
                    default_value="ZIEGLER_NICHOLS",
                    tag=f"auto_tune_method_{self.unique_id}",
                    width=150
                )
                # --- Button to run auto-tuning ---
                dpg.add_button(
                    label="Auto-Tune PID",
                    callback=self.cb_run_auto_tune,
                    user_data=None  # We can pass self here if needed
                )
                # Button to halt auto-tune
                dpg.add_button(
                    label="Halt Auto-Tune",
                    callback=self.cb_halt_auto_tune
                )

                # New setpoint control
                dpg.add_input_float(
                    label="Setpoint [V]",
                    default_value=current_setpoint,
                    callback=self.cb_set_new_setpoint,
                    tag=f"setpoint_{self.unique_id}",
                    format="%.3f"
                )
                dpg.add_button(
                    label="Set New Setpoint",
                    callback=self.cb_apply_new_setpoint
                )

            # A button to reset the device
            dpg.add_button(label="Reset Device", callback=self.cb_reset_device)

    def cb_set_new_setpoint(self, sender, app_data):
        """Callback to set the new setpoint value."""
        self.new_setpoint = dpg.get_value(sender)

    def cb_apply_new_setpoint(self):
        """Apply the new setpoint to the device."""
        if not self.simulation:
            self.dev.set_setpoint(self.new_setpoint)
            print(f"New setpoint applied: {self.new_setpoint:.3f} V")
        else:
            print(f"Simulation mode: Setpoint would be {self.new_setpoint:.3f} V")

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
        with dpg.group(horizontal=False, tag=f"manual_controls_{self.unique_id}", width=250):
            dpg.add_text("Output Mode")
            # Mode radio: manual or PID
            dpg.add_radio_button(
                items=["Manual", "PID"], default_value="PID",
                callback=self.cb_set_output_mode,
                tag=f"output_mode_{self.unique_id}"
            )

            # Manual output input
            dpg.add_text("Manual Output")
            dpg.add_input_float(
                label="Voltage [V]", default_value=0.0,
                callback=self.cb_set_manual_output,
                tag=f"manual_out_{self.unique_id}",
                format="%.3f"
                )

            # Output Offset
            dpg.add_text("Output Offset")
            dpg.add_input_float(
                label="Offset [V]", default_value=self.dev.get_output_offset(),
                callback=self.cb_set_output_offset,
                tag=f"output_offset_{self.unique_id}",
                format="%.3f"
                )

            # Button to halt auto-tune
            dpg.add_button(
                label="Stabilize",
                callback=self.cb_stabilize,
            )

    def create_stabilize_controls(self):
        """
        Create compact controls for the stabilize parameters in the GUI.
        """
        with dpg.group(horizontal=False, tag=f"stabilize_controls_{self.unique_id}", width=250):
            dpg.add_text("Stabilize Parameters")

            with dpg.group(horizontal=False):
                dpg.add_input_float(
                    label="Step", default_value=0.2,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_step_{self.unique_id}",
                    format="%.2f", width=80
                )
                dpg.add_input_float(
                    label="Span", default_value=1.0,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_span_{self.unique_id}",
                    format="%.2f", width=80
                )
                dpg.add_input_int(
                    label="Measure Count", default_value=5,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_measure_count_{self.unique_id}",
                    width=80
                )
                dpg.add_input_float(
                    label="Measure Delay", default_value=0.2,
                    callback=self.cb_update_stabilize_param,
                    tag=f"stabilize_measure_delay_{self.unique_id}",
                    format="%.2f", width=80
                )

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

    def cb_stabilize(self) -> None:
        """
        Stabilize the output, measure readings, and set the output offset
        and manual output voltage to the closest measured value to zero,
        updating both the device and the GUI.
        """
        try:
            # Parameters
            middle = self.dev.get_output_offset()
            print(f"Middle = {middle:.3f} V")
            iterations = 1

            # Fetch parameters from GUI
            step = self.stabilize_step
            span = self.stabilize_span
            measure_count = self.stabilize_measure_count
            measure_delay = self.stabilize_measure_delay

            # Generate voltage range from -span/2 to +span/2 with the specified step
            voltage_offsets = np.arange(-span / 2, span / 2 + step, step)

            # Validate the generated voltages
            for offset in voltage_offsets:
                if not -10.000 <= middle + offset <= 10.000:
                    raise ValueError(f"Voltage {middle + offset:.3f} V is out of range.")

            # Set the stabilize running flag
            self.stabilize_running = True
            self.dev.set_output_mode(manual=True)

            # Data collection
            set_voltages = []
            readings = []

            # Finite loop for stabilization
            for i in range(iterations):
                if not self.stabilize_running:
                    print("Stabilization halted by user.")
                    break

                print(f"Iteration {i + 1}/{iterations}")
                for offset in voltage_offsets:
                    if not self.stabilize_running:
                        print("Stabilization halted by user.")
                        break

                    set_voltage = middle + offset
                    self.dev._write(f"MOUT {set_voltage:.3f}")
                    print(f"Set output voltage to {set_voltage:.3f} V")
                    time.sleep(0.5)  # Add a small delay between commands

                    # Measure the output multiple times to calculate the average reading
                    measured_values = []
                    for _ in range(measure_count):
                        if not self.stabilize_running:
                            print("Stabilization halted during measurement collection.")
                            break
                        measured_values.append(self.dev.read_measure_input())
                        time.sleep(measure_delay)

                    if not self.stabilize_running:
                        break

                    avg_reading = sum(measured_values) / len(measured_values)
                    set_voltages.append(set_voltage)
                    readings.append(avg_reading)

            # Find the voltage with the closest reading to zero
            if set_voltages and readings:
                closest_index = min(range(len(readings)), key=lambda i: abs(readings[i]))
                closest_voltage = set_voltages[closest_index]
                closest_reading = readings[closest_index]

                print(f"Closest Voltage: {closest_voltage:.3f} V, Closest Reading: {closest_reading:.3f}")

                # Update the output offset and manual output voltage in the device
                if not self.simulation:
                    self.dev.set_output_offset(closest_voltage)
                    self.dev._write(f"MOUT {closest_voltage:.3f}")
                    print(f"Output offset set to the closest voltage: {closest_voltage:.3f} V")
                    print(f"Manual output set to the closest voltage: {closest_voltage:.3f} V")

                # Update the GUI to reflect the new offset and manual output values
                dpg.set_value(f"output_offset_{self.unique_id}", closest_voltage)
                dpg.set_value(f"manual_out_{self.unique_id}", closest_voltage)

                # Plot the data
                plt.figure(figsize=(8, 6))
                plt.plot(set_voltages, readings, 'bo', label="Measured Data")
                plt.scatter([closest_voltage], [closest_reading], color='g', label="Closest to Zero", zorder=5)
                plt.axhline(y=0, color='k', linestyle='--', label="Zero Line")
                plt.title("Readings vs Set Voltage")
                plt.xlabel("Set Voltage (V)")
                plt.ylabel("Measured Reading")
                plt.axvline(x=closest_voltage, color='g', linestyle='--', label=f"Closest Voltage: {closest_voltage:.3f} V")
                plt.legend()
                plt.grid(True)
                plt.show()

        except Exception as e:
            print(f"Failed to stabilize output: {e}")
            raise

    def create_monitor_controls(self):
        """
        Create controls for reading the measured input or output.
        """
        with dpg.group(horizontal=False, tag=f"monitor_controls_{self.unique_id}", width=250):
            dpg.add_text("Monitoring")
            # We'll show measure input or output
            dpg.add_button(label="Update Readings", callback=self.cb_update_measurement)
            dpg.add_text("Measure Input:", tag=f"measure_input_{self.unique_id}")
            dpg.add_text("Output Voltage:", tag=f"output_voltage_{self.unique_id}")

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

    def cb_set_output_mode(self, sender, app_data):
        """
        Callback to set manual or PID mode.
        """
        mode_str = dpg.get_value(sender)
        manual = (mode_str == "Manual")
        if not self.simulation:
            self.dev.set_output_mode(manual)

    def cb_set_manual_output(self, sender, app_data):
        """
        Callback to set the manual output (MOUT).
        """
        new_val = dpg.get_value(sender)
        if not self.simulation:
            self.dev.set_manual_output(new_val)

    def cb_set_output_offset(self, sender, app_data):
        """
        Callback to set output offset.
        """
        new_val = dpg.get_value(sender)
        if not self.simulation:
            self.dev.set_output_offset(new_val)

    def cb_update_measurement(self):
        """
        Read the measure input and output from the device and update the labels.
        """
        if not self.simulation:
            meas_input = self.dev.read_measure_input()
            meas_output = self.dev.read_output_voltage()
            dpg.set_value(f"measure_input_{self.unique_id}", f"Measure Input: {meas_input:.5f} V")
            dpg.set_value(f"output_voltage_{self.unique_id}", f"Output Voltage: {meas_output:.5f} V")
        else:
            # In simulation, just display dummy values
            dpg.set_value(f"measure_input_{self.unique_id}", "Measure Input: 123.456 (sim)")
            dpg.set_value(f"output_voltage_{self.unique_id}", "Output Voltage: 3.333 (sim)")

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

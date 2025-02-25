import math
from datetime import datetime, timedelta
from typing import Dict

import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib import pyplot as plt

from SystemConfig import Instruments, InstrumentsAddress
from Utils import ObservableField
from .wrapper_sim900_mainframe import SRSsim900
import time
from enum import Enum
import random

import asyncio
import threading
import time

class AutoTuneMethod(Enum):
    ZIEGLER_NICHOLS = 1
    COHEN_COON = 2
    TYREUS_LUYBEN = 3
    OTHER = 99

class SRSsim960:
    """
    A wrapper for the SRS SIM960 PID controller inserted into the SIM900 mainframe.
    We communicate by sending 'CONN <slot>, ...' commands through the SRSsim900.
    """

    def __init__(self, mainframe: SRSsim900, slot: int = 3, simulation: bool=False):
        """
        :param mainframe: An instance of SRSsim900.
        :param slot: The slot number in the SIM900 mainframe where SIM960 is inserted.
        """
        self.v_pi = 2.5
        self.stability_recovery_time_seconds = 10
        self.auto_tune_running = None
        self.mf = mainframe
        self.slot = slot
        self.simulation = simulation
        self.is_stable:bool = False
        self.last_stable_timestamp:datetime = datetime.now() - timedelta(seconds=self.stability_recovery_time_seconds*1e3)
        self.stability_tolerance:float = 0.01

        self.unwind_th=9.9
        self.start_time = time.time()
        self.time_values = []
        self.measurement_inputs = []
        self.output_voltages = []
        self.measurement_observable = ObservableField([[],[],[]])  # lists of time, input, output
        self.lock = threading.Lock()
        self.update_thread = threading.Thread(target=self.continuous_measure_loop, daemon=True)
        # Start the loop
        self.continuous_stream_active = True

    def continuous_measure_loop(self):
        while self.continuous_stream_active:
            try:
                current_time = time.time() - self.start_time
                output_voltage = self.read_output_voltage()
                measurement_input = self.read_measure_input()

                self.time_values.append(current_time)
                self.measurement_inputs.append(measurement_input)
                self.output_voltages.append(output_voltage)

                # Limit the data to avoid memory overflow (e.g., keep the last 1000 points)
                if len(self.time_values) > 1000:
                    self.time_values.pop(0)
                    self.measurement_inputs.pop(0)
                    self.output_voltages.pop(0)
                with self.lock:
                    self.measurement_observable.set([self.time_values, self.measurement_inputs, self.output_voltages])

                if abs(output_voltage) > self.unwind_th:

                    print('SRS is not stable.')
                    sign = 1 if output_voltage > 0 else -1
                    offset = self.v_pi * 4 * sign
                    print(f"jumping to {output_voltage + offset:.3f}")
                    self.set_manual_output(output_voltage + offset)
                    self.set_output_mode(True)

                    print(f"val = {self.read_output_voltage()}")
                    self.set_manual_output(output_voltage + offset)
                    time.sleep(0.5)
                    self.set_manual_output(output_voltage + offset)
                    print(f"val = {self.read_output_voltage()}")
                    time.sleep(1.0)
                    self.set_output_mode(False)
                    # self.dev.mf.flush_output()
                    self.is_stable = False
                    self.last_stable_timestamp = datetime.now()
                else:
                    if not self.is_stable and datetime.now() > self.last_stable_timestamp + timedelta(seconds=self.stability_recovery_time_seconds):
                        # print('SRS is not stable. Trying to recover...')
                        if np.isclose(self.read_setpoint(), self.read_setpoint(), self.stability_tolerance):
                            print('SRS is stable.')
                            self.is_stable = True

            except Exception as exc:
                    print(f"Error in SIM 960 continuous loop: {exc}")
                    break

            time.sleep(0.5)

    def _write(self, command: str) -> None:
        """
        Internal helper to write a command to SIM960 via the mainframe slot.
        """
        with self.lock:
            self.mf.write(f"CONN {self.slot},'quit'")
            self.mf.write(command)
            self.mf.write("quit")

    def _query(self, command: str, timeout = 1, is_float = False) -> str|float:
        """
        Internal helper to query from SIM960 via the mainframe slot.

        :param command: The command to send.
        :param timeout: The timeout in seconds.
        """
        with self.lock:
            start = time.time()
            while not self.mf.is_connected and time.time() - start < timeout:
                time.sleep(0.1)

            if self.mf.is_connected:
                # self.mf._connection.flush(pyvisa.constants.VI_IO_IN_BUF_DISCARD | pyvisa.constants.VI_IO_OUT_BUF_DISCARD)  # Flush both buffers
                self.mf.write(f"CONN {self.slot},'quit'")
                resp = self.mf.query(command)

                if is_float:
                    max_retries = 5
                    for attempt in range(1, max_retries + 1):
                        try:
                            float_value = float(resp)
                            break
                        except ValueError:
                            print(f"Attempt {attempt}: Invalid response '{resp}' for query {command}, retrying...")
                            time.sleep(0.1)  # Wait 100ms before retrying
                            resp = self.mf.query(command) # Remove any extra whitespace
                self.mf.write("quit")
                return resp
            else:
                print(f"Could not process command {command}. SRS mainframe is not connected.")
                return ""

    def reset(self) -> None:
        """
        Perform a device reset (*RST).
        """
        self._write("*RST")

    @staticmethod
    def get_available_devices() -> list:
        """
        Scan all available slots in the mainframe to detect connected SIM960 devices.

        :return: A list of SRSsim960 instances representing available SIM960 devices.
        """
        available_devices = []

        # Iterate through all potential slots (typically 1 to 8 for SIM900 mainframes)
        for slot in range(1, 9):
            try:
                # Create a temporary mainframe instance and check the slot
                # Assuming `SRSsim900` is already initialized elsewhere in your system
                temp_mainframe = SRSsim900(InstrumentsAddress.SRS_MAINFRAME)
                temp_mainframe.write(f"CONN {slot},'quit'")  # Connect to the slot
                response = temp_mainframe.query("*IDN?")  # Query the ID string

                if "SIM960" in response:
                    # Detected SIM960, create an instance and append it to the list
                    sim960_device = SRSsim960(temp_mainframe, slot)
                    available_devices.append(sim960_device)

                temp_mainframe.write("quit")  # Disconnect from the slot

            except Exception as e:
                # Handle errors (e.g., no device in the slot) gracefully
                continue

        return available_devices

    # -----------------------------------------------------------------------
    # Basic PID parameter access
    # -----------------------------------------------------------------------

    def enable_proportional(self, enable: bool) -> None:
        """
        Enable or disable proportional action (PCTL).

        :param enable: True to enable, False to disable.
        """
        if self.simulation:
            return

        val = 1 if enable else 0
        self._write(f"PCTL {val}")

    def set_setpoint(self, setpoint: float):
        """
        Set a new setpoint on the SIM960 controller.

        :param port: Serial port to connect to the SIM960.
        :param baud_rate: Baud rate for serial communication.
        :param setpoint: Desired setpoint value in volts (-10.000 to +10.000).
        """
        try:
            if self.simulation:
                return
            # Ensure the setpoint is within the valid range
            if not -10.000 <= setpoint <= 10.000:
                raise ValueError("Setpoint must be within the range -10.000 to +10.000 volts.")

            self._write(f"SETP {setpoint:.3f}")

        except Exception as e:
            print(f"Error in sim960 wrapper: {e}")

    def set_proportional_gain(self, gain: float) -> None:
        """
        Set proportional gain (GAIN).
        0.1 <= |gain| <= 1000

        :param gain: Gain in V/V.
        """
        if self.simulation:
            return

        if not (0.1 <= abs(gain) <= 1000):
            print("Gain out of range.")
        else:
            self._write(f"GAIN {gain}")

    def get_proportional_gain(self) -> float:
        """
        Get the proportional gain.

        :return: Gain in V/V.
        """

        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query("GAIN?",is_float=True))

    def enable_integral(self, enable: bool) -> None:
        """
        Enable or disable integral action (ICTL).

        :param enable: True to enable, False to disable.
        """
        if self.simulation:
            return

        val = 1 if enable else 0
        self._write(f"ICTL {val}")

    def set_integral_gain(self, gain: float) -> None:
        """
        Set the integral gain (INTG).
        1e-2 <= gain <= 5e5

        :param gain: Gain in V/(V·s).
        """
        if self.simulation:
            return

        if not (1e-2 <= gain <= 5e5):
            print("Integral gain out of range.")
        else:
            self._write(f"INTG {gain}")

    def get_integral_gain(self) -> float:
        """
        Get the integral gain.

        :return: Gain in V/(V·s).
        """
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "INTG?"))

    def enable_derivative(self, enable: bool) -> None:
        """
        Enable or disable derivative action (DCTL).

        :param enable: True to enable, False to disable.
        """
        if self.simulation:
            return

        val = 1 if enable else 0
        self._write(f"DCTL {val}")

    def set_derivative_gain(self, gain: float) -> None:
        """
        Set the derivative gain (DERV).
        1e-6 <= gain <= 10

        :param gain: Gain in V/(V/s).
        """
        if self.simulation:
            return

        if not (1e-6 <= gain <= 10):
            print("Derivative gain out of range.")
        else:
            self._write(f"DERV {gain}")

    def get_derivative_gain(self) -> float:
        """
        Get the derivative gain.

        :return: Gain in V/(V/s).
        """
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "DERV?"))

    def enable_offset(self, enable: bool) -> None:
        """
        Enable or disable output offset (OCTL).

        :param enable: True to enable offset, False to disable.
        """
        if self.simulation:
            return

        val = 1 if enable else 0
        self._write(f"OCTL {val}")

    def set_output_offset(self, offset: float) -> None:
        """
        Set the output offset (OFST).
        -10 <= offset <= 10

        :param offset: Offset in volts.
        """
        if self.simulation:
            return

        if not (-10.0 <= offset <= 10.0):
            raise ValueError("Offset out of range.")
        self._write(f"OFST {offset}")

    def get_output_offset(self) -> float:
        """
        Get the current output offset.

        :return: Offset in volts.
        """
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "OFST?"))

    # -----------------------------------------------------------------------
    # Control modes: manual or PID
    # -----------------------------------------------------------------------

    def set_output_mode(self, manual: bool) -> None:
        """
        Set output mode to manual or PID (AMAN).
        True => manual (0), False => PID (1).

        :param manual: True for manual, False for PID.
        """
        if self.simulation:
            return

        val = 0 if manual else 1
        self._write(f"AMAN {val}")

    def get_output_mode(self) -> bool:
        """
        Return True if in manual mode, False if in PID mode.

        :return: Boolean indicating the output mode (True => manual).
        """
        if self.simulation:  # Check if simulation is enabled
            return random.randint(0, 1)==0 # Return a random float between 1 and 10
        else:
            return self._query("AMAN?").strip() == "0"

    def set_manual_output(self, output: float) -> None:
        """
        Set manual output (MOUT), valid only when AMAN=0 (manual).
        -10 <= output <= 10

        :param output: Voltage in volts.
        """
        if self.simulation:
            return

        if not (-10.0 <= output <= 10.0):
            print("Manual output out of range.")
        else:
            self._write(f"MOUT {output:.5f}")


    def read_setpoint(self) -> float:
        """
        Reads the current setpoint value from the SIM960 device.

        :return: The current setpoint in volts.
        """
        try:
            # Send the query command to read the setpoint
            if self.simulation:  # Check if simulation is enabled
                return random.uniform(1, 10)  # Return a random float between 1 and 10
            else:
                response = self._query("SETP?")

            # Convert the response to a float
            setpoint = float(response.strip())
            print(f"Current setpoint: {setpoint:.3f} V")
            return setpoint
        except ValueError as e:
            print(f"Error parsing setpoint value: {e}")
            raise
        except Exception as e:
            print(f"Failed to read setpoint: {e}")
            raise

    def get_manual_output(self) -> float:
        """
        Get the current manual output (MOUT).

        :return: Manual output in volts.
        """
        if self.simulation:  # Check if simulation is enabled
            return random.randint(0, 1)==0 # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "MOUT?"))

    # -----------------------------------------------------------------------
    # Measurements
    # -----------------------------------------------------------------------

    def read_measure_input(self) -> float:
        """
        Read the measure input (MMON?).

        :return: The measured voltage in volts.
        """
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "MMON?"))

    def read_output_voltage(self) -> float:
        """
        Read the actual front-panel output (OMON?).

        :return: The output voltage in volts.
        """
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "OMON?"))

    def manual_scan_and_find_peak(
        self,
        start: float,
        stop: float,
        step: float,
        find_peak: bool = True,
        settle_time: float = 0.2
        ) -> float:
        """
        Manually scan MOUT between start and stop, reading MMON?.
        Finds the max (if find_peak=True) or min (otherwise).
        Sets MOUT to the best found value.

        :param start: Starting output voltage.
        :param stop: Ending output voltage.
        :param step: Increment step (positive for start<stop, negative if start>stop).
        :param find_peak: True => find maximum, False => find minimum.
        :param settle_time: Wait time after each step (s).
        :return: The best MOUT value found.
        """
        self.set_output_mode(manual=True)

        best_val = None
        best_mout = start
        current = start

        increasing = (stop >= start)
        while (current <= stop) if increasing else (current >= stop):
            self.set_manual_output(current)
            time.sleep(settle_time)
            measured = self.read_measure_input()

            if best_val is None:
                best_val = measured
            else:
                if find_peak and (measured > best_val):
                    best_val = measured
                    best_mout = current
                elif (not find_peak) and (measured < best_val):
                    best_val = measured
                    best_mout = current

            current += step if increasing else step

        self.set_manual_output(best_mout)
        return best_mout


    def enable_pid_and_fix_after_wait(self, wait_time: float = 1.0) -> None:
        """
        Enable PID mode, wait, read the front-panel output (OMON),
        then switch to manual mode and fix MOUT to that value.
        """
        self.set_output_mode(manual=False)
        time.sleep(wait_time)
        pid_output = self.read_output_voltage()
        self.set_output_mode(manual=True)
        self.set_manual_output(pid_output)

    def auto_tune_pid(
            self,
            method: AutoTuneMethod = AutoTuneMethod.ZIEGLER_NICHOLS,
            tune_time: float = 30.0,
            max_gain: float = 200.0,
            gain_step: float = 1.0,
            amplitude_threshold: float = 0.001,
            measure_count: int = 5,
            measure_delay: float = 0.1,
            stable_cycles_required: int = 3
        ) -> tuple[float, float, float]:
        """
        Auto-tune the PID loop by increasing P until oscillations are detected
        and remain stable for a given number of cycles.

        :param method: AutoTuneMethod for final P, I, D formula.
        :param tune_time: Maximum time to spend searching for oscillations.
        :param max_gain: Maximum proportional gain to try.
        :param gain_step: Increment step for P gain.
        :param amplitude_threshold: Minimum amplitude to confirm oscillations.
        :param measure_count: Number of measurements to average at each step.
        :param measure_delay: Delay between measurements.
        :param stable_cycles_required: Number of stable oscillation cycles required.
        :return: Tuple (P, I, D).
        """
        # Initialize PID mode
        self.set_output_mode(manual=False)
        self.enable_proportional(True)
        self.enable_integral(False)
        self.enable_derivative(False)

        # Start with minimal P gain
        current_p = 3
        self.set_proportional_gain(current_p)
        self.set_integral_gain(0.01)
        self.set_derivative_gain(0.000001)

        start_time = time.time()

        found_ku = False
        ku = None
        tu = None

        # Ensure auto-tune is running
        self.auto_tune_running = True
        cycle_count = 0
        last_amplitude = 0
        last_time = time.time()

        while self.auto_tune_running and (time.time() - start_time) < tune_time:
            if current_p > max_gain:
                break

            # Set proportional gain
            self.set_proportional_gain(current_p)

            # Measure the output multiple times to calculate the amplitude
            readings = []
            for _ in range(measure_count):
                if not self.auto_tune_running:
                    print("Auto-tune halted during measurement collection.")
                    return None, None, None
                readings.append(self.read_measure_input())
                time.sleep(measure_delay)

            # Calculate average amplitude
            avg_reading = sum(readings) / len(readings)
            amplitude = max(readings) - min(readings)

            print(f"P: {current_p}, Amplitude: {amplitude}")

            # Check for oscillations
            if amplitude > amplitude_threshold:
                current_time = time.time()
                if last_amplitude > 0 and (current_time - last_time) > (measure_count * measure_delay):
                    cycle_count += 1
                    print(f"Oscillation cycle detected: Cycle {cycle_count}")
                    last_time = current_time

                # Reset cycle count if amplitude decreases
                if amplitude < last_amplitude*0.7:
                    print(f"Amp = {amplitude}, 0.7*last_amp = {last_amplitude*0.7}, resetting...")
                    cycle_count = 0
                    current_p += gain_step

                # Check if stable cycles have been achieved
                if cycle_count >= stable_cycles_required:
                    found_ku = True
                    ku = current_p
                    # Estimate Tu as the period between last two cycle detections
                    tu = measure_count * measure_delay
                    print(f"Stable oscillations detected. Ku: {ku}, Tu: {tu}")
                    break

                last_amplitude = amplitude
            else:
                cycle_count = 0  # Reset if no oscillations are detected
                last_amplitude = 0
                current_p += gain_step


        # If the process was halted
        if not self.auto_tune_running:
            print("Auto-tune halted.")
            return None, None, None

        if not found_ku:
            raise RuntimeError("Failed to detect stable oscillations within the tune_time or max_gain limit.")

        # Calculate final PID gains based on the selected method
        if method == AutoTuneMethod.ZIEGLER_NICHOLS:
            p_final = 0.6 * ku
            ti = 0.5 * tu
            td = 0.125 * tu
        elif method == AutoTuneMethod.COHEN_COON:
            p_final = 0.9 * ku
            ti = 0.75 * tu
            td = 0.15 * tu
        elif method == AutoTuneMethod.TYREUS_LUYBEN:
            p_final = 0.45 * ku
            ti = 2.2 * tu
            td = 0.16 * tu
        else:
            p_final = 0.5 * ku
            ti = 1.0 * tu
            td = 0.1 * tu

        i_final = p_final / ti if ti else 0.0
        d_final = p_final * td

        print(f"Final PID values: P={p_final}, I={i_final}, D={d_final}")
        self.auto_tune_running = False
        return p_final, i_final, d_final

    def auto_tune_pid_original(
            self,
            method: AutoTuneMethod = AutoTuneMethod.ZIEGLER_NICHOLS,
            tune_time: float = 30.0,
            max_gain: float = 200.0,
            gain_step: float = 1,
            stable_cycles_required: int = 3,
            amplitude_threshold: float = 0.001,
            measure_count: int = 5,
            measure_delay: float = 0.1
        ) -> tuple[float, float, float]:
        """
        Auto-tune the PID loop for slow processes with low-frequency noise (e.g. <1 Hz).

        This function:
          1) Forces the system into PID mode but disables I and D, leaving only P active.
          2) Slowly ramps P upward from near-zero to max_gain in steps of gain_step.
          3) At each step, it waits enough time (measure_delay * measure_count) to accommodate
             slow dynamics, then takes multiple measurements, averaging them to reduce noise.
          4) Monitors the averaged output for zero-crossings (sign changes) and tracks amplitude.
          5) Once stable oscillations with amplitude > amplitude_threshold are detected for
             stable_cycles_required full cycles, it captures:
             Ku => the current P (ultimate gain)
             Tu => the oscillation period
          6) Applies standard formulas (Ziegler-Nichols, Cohen-Coon, Tyreus-Luyben, or OTHER).

        Adjustments for slow systems:
          - Default tune_time is large (300 s).
          - Default gain_step is small (0.2).
          - We take several measurements (measure_count) with measure_delay between them,
            then compute an average to limit random noise.
          - stable_cycles_required is 3 by default, expecting big, slow oscillations.
          - amplitude_threshold is small (0.001) to allow detection of low-level oscillations.
          - If no stable oscillation is found before tune_time or max_gain, raises RuntimeError.

        :param method: AutoTuneMethod for final P, I, D formula.
        :param tune_time: Maximum total time to spend searching for oscillations (seconds).
        :param max_gain: Upper limit on the proportional gain we are willing to try.
        :param gain_step: Increment step for P each iteration.
        :param stable_cycles_required: Number of full cycles needed to declare stable oscillations.
        :param amplitude_threshold: Minimum amplitude (peak-to-peak/2) to confirm real oscillations.
        :param measure_count: Number of times we read the input at each P step (to average).
        :param measure_delay: Delay (seconds) between each measurement in a batch.
        :return: Tuple (P, I, D).
        """

        # -------- Basic validations --------
        if tune_time <= 0:
            raise ValueError("tune_time must be positive.")
        if max_gain <= 0:
            raise ValueError("max_gain must be positive.")
        if gain_step <= 0:
            raise ValueError("gain_step must be positive.")
        if stable_cycles_required < 1:
            raise ValueError("stable_cycles_required must be >= 1.")
        if amplitude_threshold < 0:
            raise ValueError("amplitude_threshold must be >= 0.")
        if measure_count < 1:
            raise ValueError("measure_count must be >= 1.")
        if measure_delay < 0:
            raise ValueError("measure_delay must be >= 0.")

        # ------------------ Prepare hardware for auto-tune ------------------
        # 1) Start in PID mode so we can manipulate the gains,
        #    but disable integral and derivative.
        self.set_output_mode(manual=False)  # AMAN=1 => PID mode
        self.enable_proportional(True)
        self.enable_integral(False)
        self.enable_derivative(False)

        # 2) Ensure P, I, D are zero so we begin from a "no-control" baseline.
        #    Actually set small P to avoid dividing by zero if internal logic does so.
        self.set_proportional_gain(0.1)
        self.set_integral_gain(0.01)
        self.set_derivative_gain(0.000001)

        # ------------------ Search for ultimate gain Ku and period Tu ------------------
        # We'll ramp P upward, monitoring the output. We'll detect oscillations by:
        #   - collecting data over short intervals
        #   - checking if sign changes and amplitude are stable for stable_cycles_required cycles

        start_time = time.time()
        found_ku = False
        ku = None
        tu = None

        # Helper storage for detecting cycles
        cycle_sign = 0
        cycle_count = 0
        time_of_last_zero_cross = None
        min_val, max_val = None, None

        current_p = 0.1

        # Ensure auto-tune is running
        self.auto_tune_running = True

        while self.auto_tune_running and (time.time() - start_time) < tune_time:
            # Ramping logic
            if current_p > max_gain:
                break  # we've exceeded what we're willing to try; stop

            # 1) Set P
            print(f"setting gain to {current_p}")
            self.set_proportional_gain(current_p)

            # 2) Wait & gather multiple measurements to reduce noise
            #    For slow dynamics, we do a brief "soak" time:
            total_wait = measure_count * measure_delay
            time.sleep(total_wait / 2.0)  # partial soak
            readings = []
            for _ in range(measure_count):
                measured_value = self.read_measure_input()
                print(f"measured value: {measured_value}")
                readings.append(measured_value)
                time.sleep(measure_delay)

            # 3) Compute average reading
            avg_reading = sum(readings) / len(readings)

            # 4) Update min/max for amplitude detection
            if min_val is None or avg_reading < min_val:
                min_val = avg_reading
            if max_val is None or avg_reading > max_val:
                max_val = avg_reading

            # 5) Check for zero-crossing => half-cycle
            new_sign = 1 if avg_reading > 0 else -1 if avg_reading < 0 else 0
            if cycle_sign != 0 and new_sign != cycle_sign and new_sign != 0:
                now = time.time()
                amplitude = (max_val - min_val) / 2.0 if (max_val is not None and min_val is not None) else 0.0

                # Reset min/max for next half-cycle
                min_val, max_val = avg_reading, avg_reading

                # Only track a cycle if amplitude above threshold
                if amplitude >= amplitude_threshold:
                    print(f"Oscillations detected amplitude is {amplitude}")
                    if time_of_last_zero_cross is not None:
                        half_period = now - time_of_last_zero_cross
                        cycle_count += 0.5  # each sign flip => half-cycle

                        # Once we see stable_cycles_required full cycles => done
                        if cycle_count >= stable_cycles_required:
                            # We'll define Ku as current P
                            ku = current_p
                            # Approx period = average half_period * 2 => but let's assume last half_period * 2
                            tu = half_period * 2
                            found_ku = True
                            print(f"Found ku : {ku}, Found Tu: {tu}")
                            break
                    time_of_last_zero_cross = now
                else:
                    print(f"Oscillations amplitude is {amplitude}")

            cycle_sign = new_sign
            current_p += gain_step

        # Did we find Ku, Tu or not?
        if not found_ku:
            raise RuntimeError(
                "Could not achieve stable oscillations within tune_time or max_gain limit."
            )

        # -------- Compute final (P, I, D) from Ku, Tu --------
        # For references:
        #  Ziegler–Nichols (classic) => P = 0.6*Ku, I = 2*P/Tu, D = 0.125*Tu * P
        #  Cohen–Coon, Tyreus–Luyben => approximate standard formula sets
        #  OTHER => a fallback guess
        if method == AutoTuneMethod.ZIEGLER_NICHOLS:
            p_final = 0.6 * ku
            ti = 0.5 * tu  # integral time
            td = 0.125 * tu
            i_final = p_final / ti if ti != 0 else 0.0
            d_final = p_final * td
        elif method == AutoTuneMethod.COHEN_COON:
            # Approx typical formula:
            #   P ~ 0.9*Ku, Ti ~ 0.75*Tu, Td ~ 0.15*Tu
            p_final = 0.9 * ku
            ti = 0.75 * tu
            td = 0.15 * tu
            i_final = p_final / ti if ti != 0 else 0.0
            d_final = p_final * td
        elif method == AutoTuneMethod.TYREUS_LUYBEN:
            # Approximations:
            #   P ~ 0.45*Ku, Ti ~ 2.2*Tu, Td ~ 0.16*Tu
            p_final = 0.45 * ku
            ti = 2.2 * tu
            td = 0.16 * tu
            i_final = p_final / ti if ti != 0 else 0.0
            d_final = p_final * td
        else:
            # A fallback guess
            p_final = 0.5 * ku
            ti = 1.0 * tu
            td = 0.1 * tu
            i_final = p_final / ti if ti != 0 else 0.0
            d_final = p_final * td

        print(f"Final values: {p_final}, {ti}, {td}, {i_final}, {d_final}")

        return (p_final, i_final, d_final)

    def test_pid_performance(
            self,
            p: float,
            i: float,
            d: float,
            test_time: float = 10.0,
            sample_interval: float = 0.1,
            setpoint: float = 0.0,
            pdf_filename: str = "PID_Performance_Report.pdf",
            tolerance: float = 0.02,
            steady_time: float = 1.0
        ) -> Dict[str, float]:
        """
        Test and document the system's PID performance over a specified period.

        :param p: Proportional gain.
        :param i: Integral gain.
        :param d: Derivative gain.
        :param test_time: Total test duration in seconds.
        :param sample_interval: Interval (seconds) between measurements.
        :param setpoint: Desired setpoint for measuring performance (user-defined reference).
        :param pdf_filename: Name of the PDF to save the performance report.
        :param tolerance: Range around setpoint for detecting settling.
        :param steady_time: How long (seconds) output must stay within tolerance to consider it settled.
        :return: Dictionary of key performance metrics:
            {
                "max_error": ...,
                "overshoot_percent": ...,
                "settling_time": ...,
                "final_error": ...,
                "IAE": ... (integral of absolute error),
                "RMSE": ... (root mean square error)
            }
        """

        if test_time <= 0:
            raise ValueError("test_time must be positive.")
        if sample_interval <= 0:
            raise ValueError("sample_interval must be positive.")
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative.")
        if steady_time < 0:
            raise ValueError("steady_time must be non-negative.")

        # 1) Configure PID gains
        self.set_proportional_gain(p)
        self.set_integral_gain(i)
        self.set_derivative_gain(d)
        self.enable_proportional(True)
        self.enable_integral(True)
        self.enable_derivative(True)

        # 2) Enable closed-loop PID mode
        self.set_output_mode(manual=False)

        # Data storage
        times = []
        measurements = []
        errors = []
        start_time = time.time()
        last_within_tolerance = None

        # For integral and RMS calculations
        sum_abs_error = 0.0
        sum_sq_error = 0.0

        # Variables for performance metrics
        max_error = 0.0
        settled_time = None

        # 3) Collect data
        while (time.time() - start_time) < test_time:
            now = time.time() - start_time
            meas = self.read_measure_input()
            err = meas - setpoint

            times.append(now)
            measurements.append(meas)
            errors.append(err)

            # Track error stats
            abs_err = abs(err)
            sum_abs_error += abs_err * sample_interval
            sum_sq_error += (err ** 2) * sample_interval

            # Track max absolute error
            if abs_err > max_error:
                max_error = abs_err

            # Check settling
            if abs_err <= tolerance:
                # Mark time if just entered tolerance region
                if last_within_tolerance is None:
                    last_within_tolerance = now
                else:
                    # See if it's been within tolerance for the full 'steady_time'
                    if (now - last_within_tolerance) >= steady_time and settled_time is None:
                        settled_time = now
            else:
                # Reset if it left the tolerance window
                last_within_tolerance = None

            time.sleep(sample_interval)

        # 4) Final metrics
        final_value = measurements[-1] if measurements else 0.0
        final_error = final_value - setpoint
        overshoot = 0.0
        if setpoint != 0:
            # overshoot = (peak - setpoint) / setpoint * 100%
            # We define peak as max measurement after crossing setpoint
            peak = max(measurements) if measurements else setpoint
            overshoot = ((peak - setpoint) / abs(setpoint)) * 100.0

        # Integral of absolute error
        iae = sum_abs_error
        # RMSE
        rmse = math.sqrt(sum_sq_error / test_time) if test_time > 0 else 0.0
        # If we never declared a settled_time, define it as test_time
        if settled_time is None:
            settled_time = test_time

        # 5) Create PDF report with plots and metrics
        with PdfPages(pdf_filename) as pdf:
            fig, ax = plt.subplots(figsize=(8, 5))
            ax.plot(times, measurements, label="Process Variable (PV)")
            ax.axhline(setpoint, color="r", linestyle="--", label="Setpoint")

            ax.set_title("PID Performance Over Time")
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Measured Value (V)")  # or other units

            ax.grid(True)
            ax.legend(loc="best")
            pdf.savefig(fig)
            plt.close(fig)

            # Include textual metrics on second page
            fig2, ax2 = plt.subplots(figsize=(8, 5))
            ax2.axis("off")
            lines = [
                "PID Performance Report",
                f"Test Time: {test_time:.2f} s",
                f"Sample Interval: {sample_interval:.2f} s",
                f"Setpoint: {setpoint:.3f}",
                f"P Gain: {p:.3f}, I Gain: {i:.3f}, D Gain: {d:.3f}",
                f"Max Abs Error: {max_error:.3f}",
                f"Overshoot: {overshoot:.2f} %",
                f"Settling Time: {settled_time:.3f} s",
                f"Final Value: {final_value:.3f}",
                f"Final Error: {final_error:.3f}",
                f"IAE (Integral Abs Error): {iae:.3f}",
                f"RMSE (Root Mean Sq Error): {rmse:.3f}",
            ]
            text = "\n".join(lines)
            ax2.text(0.1, 0.9, text, va="top", fontsize=10)
            pdf.savefig(fig2)
            plt.close(fig2)

        # 6) Return key metrics as dictionary
        return {
            "max_error": max_error,
            "overshoot_percent": overshoot,
            "settling_time": settled_time,
            "final_error": final_error,
            "IAE": iae,
            "RMSE": rmse
        }

    def set_upper_limit(self, limit: float) -> None:
        """Set the upper limit for output."""
        if self.simulation:
            return

        if not (-10.0 <= limit <= 10.0):
            print("Upper limit out of range.")
        else:
            self._write(f"ULIM {limit:.3f}")

    def set_lower_limit(self, limit: float) -> None:
        """Set the lower limit for output."""
        if self.simulation:
            return

        if not (-10.0 <= limit <= 10.0):
            print("Lower limit out of range.")
        else:
            self._write(f"LLIM {limit:.3f}")

    def get_upper_limit(self) -> float:
        """Get the current upper limit."""
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "ULIM?"))

    def get_lower_limit(self) -> float:
        """Get the current lower limit."""
        if self.simulation:  # Check if simulation is enabled
            return random.uniform(1, 10)  # Return a random float between 1 and 10
        else:
            return float(self._query(is_float=True, command= "LLIM?"))


def adjust_pid_for_low_frequency(
    p: float,
    i: float,
    d: float,
    target_bandwidth_hz: float = 0.1
    ) -> tuple[float, float, float]:
    """
    Adjust the PID gains to ensure the control loop bandwidth is around or below
    a target low-frequency range (default 0.1 Hz).

    This function:
      1) Interprets the user-provided P, I, D in "parallel" form (not time-constant form).
         - P = proportional gain
         - I = integral gain  (units of 1/s, typically P / Ti)
         - D = derivative gain (units of s * P)
      2) Estimates the integral time Ti = P / I, derivative time Td = D / P.
      3) Computes an approximate loop bandwidth from Ti, Td, and P.
         For slower, drift-correcting control, we want the bandwidth ~ target_bandwidth_hz or below.
      4) If the loop bandwidth is above target_bandwidth_hz, it scales P, I, and D down so that
         the new bandwidth is at or below the target. If the bandwidth is already suitable, it
         leaves them unchanged.

    Note:
      - This is a simplified approach that treats the integral time Ti as a main driver for
        low-frequency response. Precisely computing bandwidth requires knowledge of the plant
        transfer function, which is beyond the scope here.
      - For very slow drift correction, a larger Ti => smaller integral gain => narrower bandwidth.
      - The derivative action is generally minimal or zero in slow-drift corrections, but we
        still handle it gracefully here.
      - If I = 0.0 or P=0.0 is encountered, we skip bandwidth logic to avoid division by zero.
        In that case, we simply return the original gains.

    :param p: Original proportional gain.
    :param i: Original integral gain (1/s).
    :param d: Original derivative gain (s * P).
    :param target_bandwidth_hz: The maximum desired loop bandwidth in Hz.
    :return: (p_adj, i_adj, d_adj) => adjusted gains that yield a lower frequency range.
    """

    # Protect against degenerate cases
    if p == 0.0 or i == 0.0:
        # Can't compute times, return original
        return (p, i, d)

    # Compute integral time and derivative time from parallel form
    #   Ti = P / I,   Td = D / P
    ti = p / i
    td = d / p if p != 0.0 else 0.0

    if ti <= 0.0:
        # Negative or zero integral time makes no sense for slow control; keep original
        return (p, i, d)

    # Approximate a "natural" or cross-over frequency:
    #   For a standard PID controlling a system with unknown plant, we do a rough guess:
    #   w_c ~ 1 / Ti    (very rough estimate, ignoring derivative for slow control)
    #   Then f_c = w_c / (2*pi)
    current_bw_hz = 1.0 / (2.0 * math.pi * ti)

    if current_bw_hz <= target_bandwidth_hz:
        # Already below desired bandwidth => no change
        return (p, i, d)
    else:
        # We want f_c_new <= target_bandwidth_hz
        # => w_c_new <= 2*pi*target_bandwidth_hz
        # => 1/Ti_new <= 2*pi*target_bandwidth_hz
        # => Ti_new >= 1/(2*pi*target_bandwidth_hz)
        ti_new = 1.0 / (2.0 * math.pi * target_bandwidth_hz)

        # Scale factor to apply to Ti
        scale_factor = ti_new / ti

        # Typically, P and I are tied by Ti => ti = p/i => ti_new = p_new / i_new
        # If we want to keep the same ratio p : i, we can scale both by the same factor
        # but we must do it so that p_new / i_new = ti_new. A direct approach:
        #
        #   Let's keep P_new = alpha * P, I_new = alpha * I
        #   Then Ti_new = (alpha * P)/(alpha * I) = P / I = Ti (unchanged by alpha).
        #
        # That won't fix ti. We actually want Ti_new > Ti => we must change ratio p : i.
        #
        # Another approach: Keep P the same, only scale i so that p/i = ti_new:
        #   => i_new = p / ti_new
        #
        # Similarly for d: if we keep P the same, d = Td * P => d_new = Td * p_new
        # but p_new = p => d_new = (td)* p => no change. However, that would keep same derivative time => same old bandwidth?
        #
        # For slow drift correction, it's common to reduce P as well if we want to reduce bandwidth
        # But let's do the simplest approach: keep P the same, only adjust i and d accordingly.
        #
        # p => stays the same
        # i_new => p / ti_new
        # d_new => td * p  (unchanged, if we want the same derivative time in real seconds)
        # BUT if we keep the same td, that might push bandwidth. Usually for slow drift, we reduce derivative if it's not needed.
        #
        # We'll adopt a simple approach for slow drift: keep D minimal. If td is small, no problem. If td is large,
        # that might not matter as much if i is small enough. We'll proceed with the direct method:
        #
        #   p_new = p
        #   i_new = p / ti_new
        #   d_new = p_new * td   (unchanged ratio)
        #
        # => new T_i = ti_new => new T_d = td
        #
        # This solution ensures we widen integral time to the desired new value.

        p_new = p
        i_new = p / ti_new
        d_new = p_new * td

        return (p_new, i_new, d_new)


import logging
import threading
from typing import Any, Dict, Optional, List

import nidaqmx
import numpy as np
from nidaqmx.constants import TerminalConfiguration, VoltageUnits, Edge, AcquisitionType

from Utils import ObservableField


class NI_DAQ_Controller:
    """
    Controller class for NI-DAQ devices using the nidaqmx library.
    All configuration, data acquisition, and continuous measurement are handled here.
    """
    def __init__(self, configuration: Dict[str, Any]) -> None:
        self.type: str = "NI-DAQ"
        self.daq_apd_input: str = configuration.get("apd_input", "Dev3/ai0")
        self.daq_sample_clk: str = configuration.get("sample_clk", "PFI1")
        self.daq_start_trig: str = configuration.get("start_trig", "PFI0")
        self.daq_max_sampling_rate: float = configuration.get("max_samp_rate", 625e3)
        self.min_voltage: float = configuration.get("min_voltage", -1.0)
        self.max_voltage: float = configuration.get("max_voltage", 1.0)
        self.daq_timeout: int = configuration.get("timeout", 3600)
        self.observable_num_samples: ObservableField[int] = ObservableField(configuration.get("number_measurements", 10))
        self.time_interval_us: ObservableField[int] = ObservableField(configuration.get("time_interval_us", 1000))
        self.pulse_width_us: ObservableField[int] = ObservableField(configuration.get("pulse_width_us", 1000))
        self.pulse_spacing_us: ObservableField[int] = ObservableField(configuration.get("pulse_spacing_us", 5000))
        self.initial_configuration = configuration

        self.task: Optional[nidaqmx.Task] = None
        self.pulse_task: Optional[nidaqmx.Task] = None

        # Observable for messages (status, errors, etc.)
        self.communication_result: ObservableField[str] = ObservableField("")
        # Observable for measurement data updates; GUI will subscribe to this field.
        self.measurement_data: ObservableField[List[float]] = ObservableField([])

        self._measurement_thread: Optional[threading.Thread] = None
        self._measurement_stop_event = threading.Event()

    def __repr__(self) -> str:
        return f"NI_DAQ_Controller(configuration: {self.initial_configuration})"

    def open(self) -> None:
        """
        Configures the NI-DAQ for analog input measurement.
        """
        try:
            self.task = nidaqmx.Task()
            self._configure_analog_input_channel()
            self._configure_sample_clock()
            self._configure_trigger()
            logging.info("NI-DAQ task opened and configured.")
        except Exception as e:
            logging.exception("Failed to open NI-DAQ task.")
            self.close()
            raise Exception("Error opening NI-DAQ task. Check connections and configuration.") from e

    def _configure_analog_input_channel(self) -> None:
        if self.task is None:
            raise RuntimeError("Task not initialized.")
        self.task.ai_channels.add_ai_voltage_chan(
            self.daq_apd_input,
            "",
            TerminalConfiguration.RSE,
            self.min_voltage,
            self.max_voltage,
            VoltageUnits.VOLTS,
        )

    def _configure_sample_clock(self) -> None:
        if self.task is None:
            raise RuntimeError("Task not initialized.")
        self.task.timing.cfg_samp_clk_timing(
            rate=self.daq_max_sampling_rate,
            source=self.daq_sample_clk,
            active_edge=Edge.RISING,
            sample_mode=AcquisitionType.FINITE,
            samps_per_chan=self.observable_num_samples.get(),
        )

    def _configure_trigger(self) -> None:
        if self.task is None:
            raise RuntimeError("Task not initialized.")
        self.task.timing.ai_conv_src = self.daq_sample_clk
        self.task.timing.ai_conv_active_edge = Edge.RISING
        trig = self.task.triggers.start_trigger
        trig.cfg_dig_edge_start_trig(self.daq_start_trig, Edge.RISING)

    def acquire_data(self) -> np.ndarray:
        """
        Reads samples from the NI-DAQ device.

        :return: A NumPy array containing the acquired samples.
        """
        if self.task is None:
            raise RuntimeError("Task not opened.")
        try:
            samples = self.task.read(number_of_samples_per_channel=self.observable_num_samples.get(),
                                     timeout=self.daq_timeout)
            data = np.asarray(samples)
            if data.ndim == 1:
                data = data.reshape((len(data), 1))
            self.communication_result.set(f"Acquired {data.shape[0]} samples.")
            return data
        except Exception as e:
            logging.exception("Error during data acquisition.")
            self.communication_result.set(f"Acquisition error: {e}")
            raise

    def close(self) -> None:
        """
        Closes the NI-DAQ task and pulse generation task if active.
        """
        if self.task is not None:
            self.task.close()
            self.task = None
            logging.info("NI-DAQ task closed.")
        if self.pulse_task is not None:
            self.pulse_task.close()
            self.pulse_task = None
            logging.info("Pulse generation task closed.")

    def set_pulse(self, pulse_width_us: int, pulse_spacing_us: int) -> None:
        """
        Configures and starts pulse generation.

        :param pulse_width_us: Pulse duration in microseconds.
        :param pulse_spacing_us: Spacing between pulses in microseconds.
        """
        if pulse_width_us <= 0 or pulse_spacing_us <= 0:
            logging.error("Invalid pulse parameters: must be > 0.")
            self.communication_result.set("Invalid pulse parameters.")
            return
        try:
            period_us = pulse_width_us + pulse_spacing_us
            frequency = 1e6 / period_us
            duty_cycle = pulse_width_us / period_us * 100.0
            if self.pulse_task is not None:
                self.pulse_task.close()
            self.pulse_task = nidaqmx.Task()
            # Assumes the device counter channel is "Dev3/ctr0"
            self.pulse_task.co_channels.add_co_pulse_chan_freq(
                counter="Dev3/ctr0",
                name_to_assign_to_channel="",
                freq=frequency,
                duty_cycle=duty_cycle,
                initial_delay=0.0,
            )
            self.pulse_task.start()
            self.pulse_width_us.set(pulse_width_us)
            self.pulse_spacing_us.set(pulse_spacing_us)
            self.communication_result.set(f"Pulse started: {pulse_width_us}μs width, {pulse_spacing_us}μs spacing.")
            logging.info("Pulse generation started.")
        except Exception as e:
            logging.exception("Error starting pulse generation.")
            self.communication_result.set(f"Pulse error: {e}")

    def stop_pulse(self) -> None:
        """
        Stops pulse generation.
        """
        try:
            if self.pulse_task is not None:
                self.pulse_task.stop()
                self.pulse_task.close()
                self.pulse_task = None
                self.communication_result.set("Pulse generation stopped.")
                logging.info("Pulse generation stopped.")
        except Exception as e:
            logging.exception("Error stopping pulse generation.")
            self.communication_result.set(f"Stop pulse error: {e}")

    def start_measure(self) -> None:
        """
        Starts continuous measurement acquisition in a separate thread.
        """
        if self._measurement_thread and self._measurement_thread.is_alive():
            logging.info("Measurement loop already running.")
            return
        self._measurement_stop_event.clear()
        self._measurement_thread = threading.Thread(target=self._measurement_loop, daemon=True)
        self._measurement_thread.start()
        self.communication_result.set("Measurement started.")

    def stop_measure(self) -> None:
        """
        Stops continuous measurement acquisition.
        """
        self._measurement_stop_event.set()
        if self._measurement_thread:
            self._measurement_thread.join()
            self._measurement_thread = None
        self.communication_result.set("Measurement stopped.")

    def _measurement_loop(self) -> None:
        """
        Continuously acquires data and updates the measurement_data observable field.
        """
        concatenated_data: List[float] = []
        while not self._measurement_stop_event.is_set():
            try:
                data = self.acquire_data()
                flattened = data.flatten().tolist()
                concatenated_data.extend(flattened)
                # Update observable field (using a copy for thread safety)
                self.measurement_data.set(concatenated_data.copy())
            except Exception as e:
                logging.exception("Error in measurement loop.")
                self.communication_result.set(f"Measurement error: {e}")
            self._measurement_stop_event.wait(0.5)
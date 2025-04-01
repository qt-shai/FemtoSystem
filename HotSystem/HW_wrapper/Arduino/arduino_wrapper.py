import logging
import threading
from typing import List, Optional

from Utils import SerialDevice, ObservableField

logging.basicConfig(level=logging.INFO)


class ArduinoController(SerialDevice):
    """
    Specialized class for communicating with an Arduino via Serial.
    Inherits from SerialDevice and adds an observable field for monitoring responses.
    """

    def __init__(self, address: str, baudrate: int = 9600, timeout: int = 1000, simulation: bool = False):
        """
        Initializes the ArduinoController.

        :param address: Serial address (e.g., 'ASRL3::INSTR').
        :param baudrate: Baud rate for serial communication.
        :param timeout: Read timeout in milliseconds.
        :param simulation: If True, operates in simulation mode.
        """
        super().__init__(address=address, baudrate=baudrate, timeout=timeout, simulation=simulation)

        # Observable fields for GUI interaction
        self.communication_result: ObservableField[str] = ObservableField("")
        self.num_points: ObservableField[int] = ObservableField(10)  # Default value
        self.time_interval_us: ObservableField[int] = ObservableField(1000)  # Default in microseconds
        self.pulse_width_us = ObservableField(1000)
        self.pulse_spacing_us = ObservableField(5000)
        self.last_measured_value: Optional[float] = None
        self.lock = threading.Lock()

    def start_measurement(self) -> None:
        """
        Sends a command to start a measurement sequence on the Arduino.
        Uses the observable fields for parameters.
        """
        num_points = self.num_points.get()
        time_us = self.time_interval_us.get()

        if num_points <= 0 or time_us <= 0:
            logging.error("Invalid measurement parameters: num_points and time_interval_us must be > 0.")
            return

        command = f"start measure:{num_points},{time_us}"
        # logging.info(f"Sending command: {command}")

        try:
            response = self._send_command(command, get_response=True, verbose=False)
            if response:
                self.communication_result.set(response)
        except Exception as e:
            logging.error(f"error {e}. this is akum. Reconnecting")
            self.reconnect()

    def read_measurement(self) -> None:
        """
        Reads the latest measurement data from the Arduino.
        """
        self.communication_result.get()

    def set_pulse(self, pulse_width: int, spacing: int) -> None:
        """
        Sends a command to start continuous pulse generation.

        :param pulse_width: Pulse duration in microseconds.
        :param spacing: Time between pulses in microseconds.
        """
        if pulse_width <= 0 or spacing <= 0:
            logging.error("Invalid pulse parameters: pulse_width and spacing must be > 0.")
            return

        self.pulse_width_us.set(pulse_width)
        self.pulse_spacing_us.set(spacing)

        command = f"set pulse:{pulse_width},{spacing}"
        logging.info(f"Sending command: {command}")

        response = self._send_command(command, get_response=True, verbose=True)
        if response:
            self.communication_result.set(response)

    def stop_pulse(self) -> None:
        """
        Sends a command to stop continuous pulse generation.
        """
        command = "stop pulse"
        logging.info("Stopping pulse generation.")

        response = self._send_command(command, get_response=True, verbose=True)
        if response:
            self.communication_result.set(response)

    def set_pulse(self, pulse_width: int, spacing: int) -> None:
        """
        Sends a command to start continuous pulse generation.

        :param pulse_width: Pulse duration in microseconds.
        :param spacing: Time between pulses in microseconds.
        """
        if pulse_width <= 0 or spacing <= 0:
            logging.error("Invalid pulse parameters: pulse_width and spacing must be > 0.")
            return

        self.pulse_width_us.set(pulse_width)
        self.pulse_spacing_us.set(spacing)

        command = f"set pulse:{pulse_width},{spacing}"
        logging.info(f"Sending command: {command}")

        response = self._send_command(command, get_response=True, verbose=True)
        if response:
            self.communication_result.set(response)

    def stop_pulse(self) -> None:
        """
        Sends a command to stop continuous pulse generation.
        """
        command = "stop pulse"
        logging.info("Stopping pulse generation.")

        response = self._send_command(command, get_response=True, verbose=True)
        if response:
            self.communication_result.set(response)


    @staticmethod
    def parse_measurement_data(raw_data: str) -> List[int]:
        """
        Parse the measurement data string of the form "MEASURE:val1,val2,val3..."
        and return it as a list of integers.

        :param raw_data: The raw string received from Arduino, e.g. "MEASURE:100,200,150".
        :return: List of integer measurements.
        """
        if not raw_data.startswith("MEASURE:"):
            raise ValueError("Data does not start with 'MEASURE:'")
        data_str = raw_data[len("MEASURE:"):]
        data_str = data_str.strip()
        if not data_str:
            raise ValueError("No measurement data found.")

        values = data_str.split(',')
        measurements = []
        for val in values:
            val = val.strip()
            if not val.isdigit():
                raise ValueError(f"Invalid numeric value in data: '{val}'")
            measurements.append(int(val))
        return measurements
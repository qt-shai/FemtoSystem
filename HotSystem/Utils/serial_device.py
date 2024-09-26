from typing import Optional

import pyvisa


class SerialDevice:
    """
    Base class to manage serial communication for any serial device using pyvisa, with support for simulation.
    """

    def __init__(self, address: str, baudrate: int = 9600, timeout: int = 1000, simulation: bool = False) -> None:
        """
        Initialize the serial device.

        :param address: The COM port or USB address (e.g., 'ASRL3::INSTR') of the device.
        :param baudrate: The baud rate for the serial communication.
        :param timeout: Timeout for serial communication in ms.
        :param simulation: If True, operate in simulation mode.
        """
        self.address: str = address
        self.baudrate: int = baudrate
        self.timeout: int = timeout
        self.simulation: bool = simulation
        self.rm: Optional[pyvisa.ResourceManager] = None
        self.device: Optional[pyvisa.resources.SerialInstrument] = None

        if not self.simulation:
            self.rm = pyvisa.ResourceManager()
            self._initialize_serial_connection()
        else:
            print(f"Simulated device initialized on {self.address}.")

    def _initialize_serial_connection(self) -> None:
        """
        Initialize the serial connection to the device.
        """
        try:
            self.device = self.rm.open_resource(self.address, open_timeout=self.timeout)
            self.device.baud_rate = self.baudrate
            self.device.timeout = self.timeout
            self.device.read_termination = '\r\n'  # Default terminator, can be changed by child class
            print(f"Serial connection established on {self.address}.")
        except pyvisa.VisaIOError as e:
            print(f"Failed to establish serial connection on {self.address}: {e}")
            self.device = None

    def _simulate_response(self, command: str) -> str:
        """
        Generate a simulated response for a given command.

        :param command: The command for which a simulated response is needed.
        :return: A simulated response string.
        """
        # Customize simulated responses based on the command
        simulated_responses = {
            "IDENT": "Simulated HighlandT130 EOM Driver",
            "STATUS": "Simulated Status: All systems nominal",
            "TEMP": "Simulated Temperature: 25.0 C"
        }
        return simulated_responses.get(command.split()[0], "Simulated Response: OK")

    def _send_command(self, command: str, verbose: bool = False) -> str:
        """
        Send a command to the serial device and receive the response.

        :param command: The command to send.
        :param verbose: If True, print detailed output.
        :return: The response from the device.
        """
        if self.simulation:
            response = self._simulate_response(command)
            if verbose:
                print(f"Simulated sending: {command}")
                print(f"Simulated received: {response}")
            return response

        if self.device:
            try:
                self.device.write(command)
                if verbose:
                    print(f"Sent: {command}")
                response: str = self.device.read().strip()
                if verbose:
                    print(f"Received: {response}")
                return response
            except pyvisa.VisaIOError as e:
                print(f"Error sending command '{command}': {e}")
                return ""
        else:
            print("Device not connected.")
            return ""

    def close_connection(self) -> None:
        """
        Close the serial connection to the device.
        """
        if self.device:
            self.device.close()
            print("Serial connection closed.")

    def __del__(self) -> None:
        """
        Destructor to ensure resources are released when the object is destroyed.
        """
        self.close_connection()

    def __enter__(self) -> 'SerialDevice':
        """
        Enter method for context management.
        """
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]) -> None:
        """
        Exit method for context management.

        :param exc_type: The type of exception.
        :param exc_val: The exception instance.
        :param exc_tb: The traceback object.
        """
        self.close_connection()
        if exc_type:
            print(f"Exception occurred: {exc_type}, {exc_val}")

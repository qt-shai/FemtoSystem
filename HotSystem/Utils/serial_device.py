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
        self.write_terminator:str = "\r\n"
        self.read_terminator:str = "\r\n"
        self.address: str = address
        self.baudrate: int = baudrate
        self.timeout: int = timeout
        self.simulation: bool = simulation
        self.rm: Optional[pyvisa.ResourceManager] = None
        self._serial_connection: Optional[pyvisa.resources.SerialInstrument] = None

    @property
    def is_connected(self) -> bool:
        """
        Check if the device is connected.

        This property performs an actual check to see if the resource manager and
        the serial connection are initialized and active.

        :return: True if the device is connected, False otherwise.
        """
        if self.simulation:
            return True

        if self._serial_connection is not None:
            try:
                # Perform a simple query to check if the connection is alive (e.g., a no-op command or status check)
                self._serial_connection.query('*IDN?')  # Assumes the device supports this command
                return True
            except pyvisa.VisaIOError:
                return False
        return False

    def connect(self) -> None:
        """
        Establish a connection to the Highland T130 EOM driver.

        If not in simulation mode, this method initializes the pyvisa ResourceManager
        and opens a serial connection to the device. It checks if the resource manager
        or the serial connection is already initialized to avoid reinitialization.

        :raises Exception: If the connection to the device fails.
        :return: None
        """
        if self.simulation:
            print(f"Simulated device initialized on {self.address}.")
            return

        if self.is_connected:
            print("Device is already connected.")
            return

        try:
            if self.rm is None:
                self.rm = pyvisa.ResourceManager()
                print("Resource Manager initialized.")
            else:
                print("Resource Manager already initialized.")

            if self._serial_connection is None:
                self._initialize_serial_connection()
                print("Serial connection initialized.")
            else:
                print("Serial connection already initialized.")

            print(f"Connected to device at {self.address}.")
        except Exception as e:
            print(f"Failed to connect to device: {e}")
            raise

    def _initialize_serial_connection(self) -> None:
        """
        Initialize the serial connection to the device.

        :raises Exception: If the serial connection cannot be established.
        :return: None
        """
        try:
            self._serial_connection = self.rm.open_resource(
                self.address,
                baud_rate=self.baudrate,
                timeout=self.timeout,
                read_termination=self.read_terminator,
                write_termination=self.write_terminator
            )
            print(f"Serial connection opened on {self.address}.")
        except Exception as e:
            print(f"Error initializing serial connection: {e}")
            self._serial_connection = None
            raise

    def disconnect(self) -> None:
        """
        Close the serial connection to the device and release resources.

        :return: None
        """
        if self._serial_connection is not None:
            try:
                self._serial_connection.close()
                print("Serial connection closed.")
            except Exception as e:
                print(f"Error closing serial connection: {e}")
        else:
            print("Serial connection was not open.")

        if self.rm is not None:
            try:
                self.rm.close()
                print("Resource Manager closed.")
            except Exception as e:
                print(f"Error closing Resource Manager: {e}")
        else:
            print("Resource Manager was not initialized.")

        self._serial_connection = None
        self.rm = None

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
        return simulated_responses.get(command.split()[0], f"Simulated Response for {self.address}: OK")

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

        if self._serial_connection:
            try:
                self._serial_connection.write(command)
                if verbose:
                    print(f"Sent: {command}")
                response: str = self._serial_connection.read().strip()
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
        if self._serial_connection:
            self._serial_connection.close()
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

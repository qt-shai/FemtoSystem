from typing import Optional
import pyvisa


class SerialDevice:
    """
    Base class to manage communication with devices over serial or TCP/IP using pyvisa, with support for simulation.
    """

    def __init__(self, address: str, baudrate: int = 9600, timeout: int = 1000, simulation: bool = False) -> None:
        """
        Initialize the device.

        :param address: The address (e.g., 'ASRL3::INSTR' for serial or 'TCPIP::K-33522B-03690.local::5025::SOCKET' for TCP/IP).
        :param baudrate: The baud rate for serial communication (ignored for TCP/IP).
        :param timeout: Timeout for communication in ms.
        :param simulation: If True, operate in simulation mode.
        """
        self.write_terminator: str = "\r\n"
        self.read_terminator: str = "\r\n"
        self.address: str = address
        self.baudrate: int = baudrate
        self.timeout: int = timeout
        self.simulation: bool = simulation
        self.rm: Optional[pyvisa.ResourceManager] = None
        self._connection: Optional[pyvisa.resources.MessageBasedResource] = None

    @property
    def is_connected(self) -> bool:
        """
        Check if the device is connected.

        :return: True if the device is connected, False otherwise.
        """
        if self.simulation:
            return True

        if self._connection is not None:
            try:
                self._connection.query('*IDN?')
                return True
            except pyvisa.VisaIOError:
                return False
        return False

    def connect(self) -> None:
        """
        Establish a connection to the device.

        :raises Exception: If the connection fails.
        """
        if self.simulation:
            print(f"Simulated device initialized on {self.address}.")
            return

        if self.is_connected:
            print("Device is already connected.")
            return

        try:
            if self.rm is None:
                print("Initializing resource manager")
                self.rm = pyvisa.ResourceManager()
                print("Resource Manager initialized.")

            if self._connection is None:
                self._initialize_connection()
                print("Connection initialized.")
            else:
                print("Connection already initialized.")

            print(f"Connected to device at {self.address}.")
        except Exception as e:
            print(f"Failed to connect to device: {e}")
            raise

    def _initialize_connection(self) -> None:
        """
        Initialize the connection to the device (serial or TCP/IP).

        :raises Exception: If the connection cannot be established.
        """
        try:
            if 'TCPIP' in self.address:
                # Handle TCP/IP connections
                self._connection = self.rm.open_resource(
                    self.address,
                    timeout=self.timeout,
                    **({"read_termination": self.read_terminator, "write_termination": self.write_terminator}
                       if "SOCKET" not in self.address else {})
                )
                print(f"TCP/IP connection opened on {self.address}.")
            else:
                # Handle Serial connections
                serial_address = (f"ASRL{self.address[3:]}::INSTR"
                                  if self.address.upper().startswith("COM")
                                  else self.address)
                self._connection = self.rm.open_resource(
                    serial_address,
                    baud_rate=self.baudrate,
                    timeout=self.timeout,
                    read_termination=self.read_terminator,
                    write_termination=self.write_terminator,
                )
                print(f"Serial connection opened on {serial_address}.")
        except Exception as e:
            print(f"Error initializing connection: {e}")
            self._connection = None
            raise

    def disconnect(self) -> None:
        """
        Close the connection to the device and release resources.
        """
        if self._connection:
            try:
                self._connection.close()
                print("Connection closed.")
            except Exception as e:
                print(f"Error closing connection: {e}")
        else:
            print("Connection was not open.")

        if self.rm:
            try:
                self.rm.close()
                print("Resource Manager closed.")
            except Exception as e:
                print(f"Error closing Resource Manager: {e}")

        self._connection = None
        self.rm = None

    def _send_command(self, command: str, get_response: bool = False, verbose: bool = False) -> Optional[str]:
        """
        Send a command to the device. Optionally, retrieve the response.

        :param command: The command to send.
        :param get_response: If True, retrieve the response after sending the command.
        :param verbose: If True, print detailed output.
        :return: The response from the device if `get_response` is True; otherwise, None.
        """
        if self.simulation:
            simulated_response = f"Simulated Response for {self.address}: OK"
            if verbose:
                print(f"Simulated sending: {command}")
                if get_response:
                    print(f"Simulated received: {simulated_response}")
            return simulated_response if get_response else None

        if self._connection:
            try:
                self._connection.write(command)
                if verbose:
                    print(f"Sent: {command}")
                # Call _get_response if get_response is True
                return self._get_response(verbose) if get_response else None
            except pyvisa.VisaIOError as e:
                print(f"Error sending command '{command}': {e}")
                return None
        else:
            print("Device not connected.")
            return None

    def _get_response(self, verbose: bool = False) -> str:
        """
        Retrieve a response from the device.

        :param verbose: If True, print detailed output.
        :return: The response from the device.
        """
        try:
            response: str = self._connection.read().strip()
            # Check for termination character
            if not response.endswith(self.read_terminator.strip()):
                response = response.rstrip()  # Strip trailing characters if termination character is missing
                print("Warning: Response does not end with termination character.")
            if verbose:
                print(f"Received: {response}")
            return response
        except pyvisa.VisaIOError as e:
            print(f"Error reading response: {e}")
            return ""

    def __enter__(self) -> 'SerialDevice':
        """ Enter method for context management. """
        return self

    def __exit__(self, exc_type: Optional[type], exc_val: Optional[BaseException], exc_tb: Optional[object]) -> None:
        """ Exit method for context management. """
        self.disconnect()
        if exc_type:
            print(f"Exception occurred: {exc_type}, {exc_val}")

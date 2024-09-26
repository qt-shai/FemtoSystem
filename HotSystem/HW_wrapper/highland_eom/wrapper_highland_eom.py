from enum import Enum
from Utils import SerialDevice

class T130USBCommands(Enum):
    """
    Enum to encapsulate all available USB commands for the Highland T130 EOM driver.
    """
    IDENT = "ID"
    MODE = "MODE"
    RANGE = "RANGE"
    DELAY = "DELAY"
    WIDTH = "WIDTH"
    AMPLITUDE = "AMPL"
    BIAS = "BIAS"
    POTS = "POTS"
    DIPSW = "DIPSW"
    DACS = "DACS"
    TEMPERATURE = "TEMP"
    STATUS = "STATUS"
    SUPPLIES = "SUPPLIES"
    NAME = "NAME"
    SAVE = "SAVE"
    LIST = "LIST"
    RECALL = "RECALL"
    HELP = "HELP"
    ERRORS = "ERRORS"


class HighlandT130(SerialDevice):
    """
    Class to manage communication with the Highland T130 EOM driver via USB.
    """

    def __init__(self, address: str, baudrate: int = 115200, timeout: int = 1000, simulation: bool = False):
        """
        Initialize the Highland T130 EOM driver.

        :param address: The COM port or USB address (e.g., 'COM3' or 'ASRL5::INSTR') of the device.
        :param baudrate: The baud rate for the serial communication.
        :param timeout: Timeout for serial communication in ms.
        :param simulation: If True, operate in simulation mode.
        """
        self.simulation: bool = simulation
        super().__init__(address, baudrate, timeout, simulation)  # Initialize the base class
        self.terminator: str = '' #'\r\n'

    def _simulate_action(self, action: str, verbose: bool) -> None:
        """
        Simulate an action if in simulation mode.

        :param action: The action description to print.
        :param verbose: If True, print detailed output.
        """
        if self.simulation and verbose:
            print(f"Simulating {action}.")

    def _perform_request(self, command: T130USBCommands, argument: str = "", verbose: bool = False) -> any:
        """
        Perform a request to the device and handle errors.

        :param command: The command to send.
        :param argument: The argument for the command (if any).
        :param verbose: If True, print detailed output.
        :return: The response from the device.
        """
        if self.simulation:
            self._simulate_action(f"command {command.value} with argument {argument}", verbose)
            return "OK"

        # Use the base class method to send the command and receive the response
        full_command = f"{command.value} {argument}{self.terminator}"
        return self._send_command(full_command, verbose)

    def get_device_identity(self, verbose: bool = False) -> str:
        """
        Retrieve the identity string of the device.

        :param verbose: If True, print detailed output.
        :return: The identity string.
        """
        return self._perform_request(T130USBCommands.IDENT, verbose=verbose)

    def get_device_status(self, verbose: bool = False) -> str:
        """
        Retrieve the current status of the device.

        :param verbose: If True, print detailed output.
        :return: The status string.
        """
        return self._perform_request(T130USBCommands.STATUS, verbose=verbose)

    def set_range(self, range_value: int, verbose: bool = False) -> None:
        """
        Set the timing range of the device.

        :param range_value: The range to set (1, 2, or 3).
        :param verbose: If True, print detailed output.
        """
        if range_value not in [1, 2, 3]:
            print("Range must be 1, 2, or 3.")
            raise ValueError("Range must be 1, 2, or 3.")
        self._perform_request(T130USBCommands.RANGE, str(range_value), verbose)

    def set_delay(self, delay_value: float, verbose: bool = False) -> None:
        """
        Set the delay of the output pulse.

        :param delay_value: The delay to set (in nanoseconds).
        :param verbose: If True, print detailed output.
        """
        if not 0.0 <= delay_value <= 1000.0:  # Example range; adjust according to the manual.
            print("Delay must be between 0.0 and 1000.0 nanoseconds.")
            raise ValueError("Delay must be between 0.0 and 1000.0 nanoseconds.")
        self._perform_request(T130USBCommands.DELAY, f"{delay_value}ns", verbose)

    def set_width(self, width_value: float, verbose: bool = False) -> None:
        """
        Set the width of the output pulse.

        :param width_value: The width to set (in nanoseconds).
        :param verbose: If True, print detailed output.
        """
        if not 1.0 <= width_value <= 1000.0:  # Example range; adjust according to the manual.
            print("Width must be between 1.0 and 1000.0 nanoseconds.")
            raise ValueError("Width must be between 1.0 and 100.0 nanoseconds.")
        self._perform_request(T130USBCommands.WIDTH, f"{width_value}ns", verbose)

    def set_amplitude(self, amplitude_value: float, verbose: bool = False) -> None:
        """
        Set the output pulse amplitude.

        :param amplitude_value: The amplitude to set (in volts).
        :param verbose: If True, print detailed output.
        """
        if not 0.25 <= amplitude_value <= 7.2:
            print("Amplitude must be between 0.25 and 7.2.")
            raise ValueError("Amplitude must be between 0.25 and 7.2.")
        else:
            self._perform_request(T130USBCommands.AMPLITUDE, str(amplitude_value), verbose)

    def set_bias(self, bias_value: float, internal: bool = True, verbose: bool = False) -> None:
        """
        Set the bias voltage and source.

        :param bias_value: The bias voltage to set (in volts).
        :param internal: True for internal bias, False for external.
        :param verbose: If True, print detailed output.
        """
        if not -6.0 <= bias_value <= 6.0:  # Example range; adjust according to the manual.
            print("Bias must be between -6.0 and 6.0 volts.")
            raise ValueError("Bias must be between -10.0 and 10.0 volts.")
        bias_source = "INT" if internal else "EXT"
        self._perform_request(T130USBCommands.BIAS, f"{bias_source} {bias_value}", verbose)

    def get_error_status(self, verbose: bool = False) -> str:
        """
        Retrieve the error status of the device.

        :param verbose: If True, print detailed output.
        :return: The error status string.
        """
        return self._perform_request(T130USBCommands.ERRORS, verbose=verbose)

    def save_configuration(self, name: str, verbose: bool = False) -> None:
        """
        Save the current device configuration with a name.

        :param name: The name of the configuration.
        :param verbose: If True, print detailed output.
        """
        self._perform_request(T130USBCommands.SAVE, f'"{name}"', verbose)

    def recall_configuration(self, name: str = "", verbose: bool = False) -> None:
        """
        Recall a saved device configuration.

        :param name: The name of the configuration to recall. If empty, recalls the last saved configuration.
        :param verbose: If True, print detailed output.
        """
        self._perform_request(T130USBCommands.RECALL, f'"{name}"' if name else "", verbose)

    def list_configurations(self, verbose: bool = False) -> str:
        """
        List all saved configurations on the device.

        :param verbose: If True, print detailed output.
        :return: A list of saved configurations.
        """
        return self._perform_request(T130USBCommands.LIST, verbose=verbose)

    # Additional methods can be added to support more commands as needed.

import time

from ..Attocube import AttocubeDevice, AttoJSONMethods
from HW_wrapper.abstract_motor import Motor


class AttoDry800(Motor):
    def __init__(self, address: str, serial_number: str = None, name: str = "AttoDry800", simulation: bool = False):
        """
        Initialize the AttoDry800 cryostat.

        :param address: The IP address of the cryostat.
        :param serial_number: The serial number of the cryostat.
        :param name: The name of the cryostat device.
        :param simulation: Boolean flag to indicate if in simulation mode.
        """
        super().__init__(serial_number, name)
        self.simulation = simulation
        self.address = address
        self.no_of_channels = 3  # Assuming 3 axes for movement
        self.channels = [0, 1, 2]
        self.device = AttocubeDevice(address, simulation=simulation)

    def _simulate_action(self, action: str, verbose: bool = False) -> None:
        """
        Simulate an action if in simulation mode.

        :param action: The action description to print.
        :param verbose: If True, print detailed output.
        """
        if self.simulation and verbose:
            print(f"Simulating {action}.")

    def _perform_request(self, method: str, params: list, verbose: bool = False) -> any:
        """
        Perform a request to the device and handle errors.

        :param method: The method name to request.
        :param params: The parameters for the request.
        :param verbose: If True, print detailed output.
        :return: The response from the device.
        """
        if self.simulation:
            self._simulate_action(f"{method} with params {params}", verbose)
            return

        try:
            response = self.device.request(method, params)
            self.device.handle_error(response, self.simulation)
            if verbose:
                print(f"Request {method} with params {params} successful.")
            return response
        except Exception as e:
            print(f"Error performing request {method} with params {params}: {e}")
            raise e

    # noinspection DuplicatedCode
    def _check_and_enable_output(self, channel: int, verbose: bool = False) -> None:
        """
        Check if the output and control move for a given channel are enabled; if not, enable them.

        :param channel: The channel number to check.
        :param verbose: If True, print detailed output.
        """
        if verbose:
            print(f"Checking if output and control move are enabled for channel {channel}.")

        # Check if the control output is enabled
        response_output = self._perform_request(AttoJSONMethods.GET_CONTROL_OUTPUT.value, [channel], verbose)
        if response_output is None or response_output[1]:
            if verbose:
                print(f"Output for channel {channel} is already enabled.")
        else:
            if verbose:
                print(f"Output for channel {channel} is not enabled. Enabling it.")
            self._perform_request(AttoJSONMethods.SET_CONTROL_OUTPUT.value, [channel, True], verbose)

        # Check if the control move is enabled
        response_move = self._perform_request(AttoJSONMethods.GET_CONTROL_MOVE.value, [channel], verbose)
        if response_move is None or response_move[1]:
            if verbose:
                print(f"Control move for channel {channel} is already enabled.")
        else:
            if verbose:
                print(f"Control move for channel {channel} is not enabled. Enabling it.")
            self._perform_request(AttoJSONMethods.SET_CONTROL_MOVE.value, [channel, True], verbose)

    def connect(self, verbose: bool = False) -> None:
        """
        Connect to the cryostat.

        :param verbose: If True, print detailed output.
        """
        if verbose:
            print("Attempting to connect to the cryostat.")
        if self.simulation:
            self._simulate_action("connect to the cryostat", verbose)

        try:
            self.device.connect()
            if verbose:
                print("Successfully connected to the cryostat.")
        except Exception as e:
            print(f"Error connecting to the device: {e}")

    def disconnect(self, verbose: bool = False) -> None:
        """
        Disconnect from the cryostat.

        :param verbose: If True, print detailed output.
        """
        if verbose:
            print("Attempting to disconnect from the cryostat.")

        try:
            self.device.close()
            if verbose:
                print("Successfully disconnected from the cryostat.")
        except Exception as e:
            print(f"Error disconnecting from the device: {e}")

    def is_connected(self, verbose: bool = False) -> bool:
        """
        Check if the cryostat is connected.

        :param verbose: If True, print detailed output.
        :return: True if connected, False otherwise.
        """
        connected = self.device.is_open
        if verbose:
            print(f"Connection status: {'Connected' if connected else 'Not Connected'}.")
        return connected

    def stop_all_axes(self, verbose: bool = False) -> None:
        """
        Stop all movement on all axes.

        :param verbose: If True, print detailed output.
        """
        for axis in range(self.no_of_channels):
            if verbose:
                print(f"Stopping movement for axis {axis}.")
            self._perform_request(AttoJSONMethods.STOP_MOVEMENT.value, [axis], verbose)

    def move_to_home(self, channel: int, verbose: bool = False) -> None:
        """
        Move a specific channel to its home position.

        :param channel: The channel number to move.
        :param verbose: If True, print detailed output.
        """
        self._check_and_enable_output(channel, verbose)
        self._perform_request(AttoJSONMethods.MOVE_TO_REFERENCE.value, [channel], verbose)

    def move_absolute(self, channel: int, position: int, verbose: bool = False) -> None:
        """
        Move a specific channel to an absolute position.

        :param channel: The channel number to move.
        :param position: The target position in steps.
        :param verbose: If True, print detailed output.
        """
        self._check_and_enable_output(channel, verbose)
        self._perform_request(AttoJSONMethods.MOVE_ABSOLUTE.value, [channel, position], verbose)

    def move_relative(self, channel: int, steps: int, verbose: bool = False) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The channel number to move.
        :param steps: The number of steps to move.
        :param verbose: If True, print detailed output.
        """
        self._check_and_enable_output(channel, verbose)
        current_position = self.get_position(channel, verbose=verbose)
        target_position = current_position + steps
        self.move_absolute(channel, int(target_position), verbose=verbose)

    def set_zero_position(self, channel: int, verbose: bool = False) -> None:
        """
        Set the current position of a specific channel to zero.

        :param channel: The channel number to zero.
        :param verbose: If True, print detailed output.
        """
        self._check_and_enable_output(channel, verbose)
        self._perform_request(AttoJSONMethods.MOVE_ABSOLUTE.value, [channel, 0], verbose)

    def get_position(self, axis: int, verbose: bool = False) -> float:
        """
        Get the current position of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :param verbose: If True, print detailed output.
        :return: The current position (in nm or µ°).
        """
        response = self._perform_request(AttoJSONMethods.GET_POSITION.value, [axis], verbose)
        return response[1] if response else -1.0

    def get_status(self, channel: int, verbose: bool = False) -> str:
        """
        Get the status of a specific channel.

        :param channel: The channel number to check.
        :param verbose: If True, print detailed output.
        :return: Status as a string.
        """
        response = self._perform_request(AttoJSONMethods.GET_STATUS_MOVING_ALL_AXES.value, [channel], verbose)
        return response[1] if response else "Error"

    def set_temperature(self, temperature: float, verbose: bool = False) -> None:
        """
        Set the temperature of the cryostat.

        :param temperature: The temperature to set (in Kelvin).
        :param verbose: If True, print detailed output.
        """
        self._perform_request(AttoJSONMethods.SET_TEMPERATURE.value, [temperature], verbose)

    def get_temperature(self, verbose: bool = False) -> float:
        """
        Get the current temperature of the cryostat.

        :param verbose: If True, print detailed output.
        :return: The current temperature (in Kelvin).
        """
        response = self._perform_request(AttoJSONMethods.GET_TEMPERATURE.value, [], verbose)
        return response[1] if response else -1.0

    def stabilize_temperature(self, stabilize: bool, verbose: bool = False) -> None:
        """
        Stabilize the temperature of the cryostat.

        :param stabilize: Whether to stabilize the temperature (True/False).
        :param verbose: If True, print detailed output.
        """
        self._perform_request(AttoJSONMethods.STABILIZE_TEMPERATURE.value, [stabilize], verbose)

    def get_firmware_version(self, verbose: bool = False) -> str:
        """
        Get the firmware version of the cryostat.

        :param verbose: If True, print detailed output.
        :return: The firmware version.
        """
        response = self._perform_request(AttoJSONMethods.GET_FIRMWARE_VERSION.value, [], verbose)
        return response[1] if response else "Error"

    def get_moving_status(self, verbose: bool = False) -> dict:
        """
        Read the moving status of all axes.

        :param verbose: If True, print detailed output.
        :return: A dictionary with axis numbers as keys and their moving status (True/False) as values.
        """
        response = self._perform_request(AttoJSONMethods.GET_STATUS_MOVING_ALL_AXES.value, [], verbose)
        if verbose:
            print(f"Axis {self.channels} status: {response.resultDict['result'][1:]}")

        return response.resultDict['result'][1:] if response else {}

    def wait_for_axes_to_stop(self, axes: list | int, max_wait_time: float = 10, verbose: bool = False) -> None:
        """
        Wait for a specified list of axes to stop moving.

        :param axes: List of axes (channels) or a single axis to wait for.
        :param max_wait_time: Maximum time in seconds to wait for the axes to stop moving.
        :param verbose: If True, print detailed output.
        """
        # Ensure axes is a list even if a single integer is provided
        if isinstance(axes, int):
            axes = [axes]
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            moving_status = self.get_moving_status(verbose=verbose)
            if all(not moving_status[axis] for axis in axes):
                if verbose:
                    print(f"All specified axes {axes} have stopped moving.")
                return
            if verbose:
                print(f"Waiting for axes {axes} to stop moving...")
            time.sleep(0.5)  # Wait for 500 ms before checking again

        raise TimeoutError(f"Axes {axes} did not stop moving within {max_wait_time} seconds.")

import time
from typing import List, Optional, Dict
from HW_wrapper.abstract_motor import Motor
from ..Attocube import AttocubeDevice, AttoJSONMethods


class AttoDry800(Motor):
    """
    Wrapper class for controlling the AttoDry800 cryostat.
    Implements the Motor interface for compatibility with GUIMotor.
    """

    def __init__(self, address: str, serial_number: Optional[str] = None, name: str = "AttoDry800",
                 simulation: bool = False, polling_rate: float = 2.0):
        """
        Initialize the AttoDry800 cryostat.

        :param address: The IP address of the cryostat.
        :param serial_number: The serial number of the cryostat.
        :param name: The name of the cryostat device.
        :param simulation: Boolean flag to indicate if in simulation mode.
        :param polling_rate: The rate at which the motor's position is polled (in Hz).
        """
        super().__init__(serial_number=serial_number, name=name, polling_rate=polling_rate, simulation=simulation)
        self.address = address
        self.no_of_channels: int = 3  # Assuming 3 axes for movement
        self.channels: List[int] = [0, 1, 2]  # Logical channels for X, Y, Z axes
        self.StepsIn1mm: int = 1000000  # Steps in 1mm (assuming 1 step = 1 nm)
        self._axes_positions: Dict[int, float] = {ch: 0.0 for ch in self.channels}  # Positions in nanometers
        self._axes_pos_units: Dict[int, str] = {ch: "nm" for ch in self.channels}
        self._connected: bool = False
        self.device = AttocubeDevice(address, simulation=simulation)
        self.fix_output_voltage_min = 0
        self.fix_output_voltage_max = 60000

    def connect(self) -> None:
        if self.simulation:
            self._simulate_action("connect to the atto positioner")
            self._connected = True
        else:
            try:
                self.device.connect()
                self._connected = True
                print("Successfully connected to the cryostat.")
            except Exception as e:
                print(f"Error connecting to the device: {e}")
                self._connected = False
                raise e
        self.start_position_updates()

    def disconnect(self) -> None:
        """Disconnect from the cryostat."""
        self.stop_position_updates()
        if self.simulation:
            self._simulate_action("disconnect from the cryostat")
            self._connected = False
        else:
            try:
                self.device.close()
                self._connected = False
                print("Successfully disconnected from the cryostat.")
            except Exception as e:
                print(f"Error disconnecting from the device: {e}")
                raise e

    def is_connected(self) -> bool:
        """Check if the cryostat is connected."""
        return self._connected

    def stop_all_axes(self) -> None:
        """Stop all movement on all axes."""
        for axis in self.channels:
            self._perform_request(AttoJSONMethods.STOP_MOVEMENT.value, [axis])

    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position.

        :param channel: The channel number to move.
        """
        self._check_and_enable_output(channel)
        self._perform_request(AttoJSONMethods.MOVE_TO_REFERENCE.value, [channel])
        self.wait_for_axes_to_stop([channel])

    def MoveABSOLUTE(self, channel: int, position: int) -> None:
        """
        Move a specific channel to an absolute position.

        :param channel: The channel number to move.
        :param position: The target position in steps.
        """
        self._check_and_enable_output(channel)
        self._perform_request(AttoJSONMethods.MOVE_ABSOLUTE.value, [channel, position])
        self.wait_for_axes_to_stop([channel])

    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The channel number to move.
        :param steps: The number of steps to move.
        """
        self._check_and_enable_output(channel)
        current_position = self.get_position(channel)
        target_position = current_position + steps
        self.MoveABSOLUTE(channel, int(target_position))

    def set_zero_position(self, channel: int) -> None:
        """
        Set the current position of a specific channel to zero.

        :param channel: The channel number to zero.
        """
        self._axes_positions[channel] = 0.0
        print(f"Channel {channel} position set to zero.")

    def set_control_fix_output_voltage(self, axis: int, amplitude_mv: float) -> None:
        """
        Set a fixed DC voltage for a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :param amplitude_mv: The DC voltage to set in millivolts. (up to 60000 mV).
        """
        amplitude_mv = int(amplitude_mv)
        if axis not in self.channels:
            raise ValueError(f"Invalid axis {axis}. Valid axes are {self.channels}.")
        if not (0<=amplitude_mv<=60000):
            raise ValueError(f"Invalid amplitude. Must be between 0 and 60000. Received {amplitude_mv}")
        self._perform_request(AttoJSONMethods.SET_CONTROL_FIX_OUTPUT_VOLTAGE.value, [axis, amplitude_mv])
        print(f"Set axis {axis} to a fixed voltage of {amplitude_mv} mV.")

    def get_control_fix_output_voltage(self, axis: int) -> float:
        """
        Get the fixed DC voltage of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :return: The fixed DC voltage in mV.
        """
        response = self._perform_request(AttoJSONMethods.GET_CONTROL_FIX_OUTPUT_VOLTAGE.value, [axis])
        if response:
            return response[1]  # Assuming the position is the second item in the response
        else:
            return -1.0

    def get_control_output_voltage(self, axis: int) -> float:
        """
        Get the DC voltage of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :return: The DC voltage in mV.
        """
        response = self._perform_request(AttoJSONMethods.GET_CONTROL_OUTPUT.value, [axis])
        if response:
            return response[1]  # Assuming the position is the second item in the response
        else:
            return -1.0

    def move_one_step(self, axis: int, backward: bool = False) -> None:
        """
        Move one step on a specific axis in the specified direction.

        :param axis: The axis number (0, 1, or 2).
        :param backward: True to move backward, False to move forward.
        """
        if axis not in self.channels:
            raise ValueError(f"Invalid axis {axis}. Valid axes are {self.channels}.")
        self._check_and_enable_output(axis)
        self._perform_request(AttoJSONMethods.MOVE_SINGLE_STEP.value, [axis, backward])
        print(f"Moved one step {'backward' if backward else 'forward'} on axis {axis}.")

    def set_actuator_voltage(self, axis: int, voltage_mv: int) -> None:
        """
        Set the actuator voltage for a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :param voltage_mv: The actuator voltage to set in millivolts (up to 60000 mV).
        """
        if axis not in self.channels:
            raise ValueError(f"Invalid axis {axis}. Valid axes are {self.channels}.")
        if not (0 <= voltage_mv <= 60000):
            raise ValueError(f"Voltage must be between 0 and 60000 mV. Received: {voltage_mv}.")
        self._perform_request(AttoJSONMethods.SET_CONTROL_AMPLITUDE.value, [axis, voltage_mv])
        print(f"Set actuator voltage for axis {axis} to {voltage_mv} mV.")

    def get_actuator_voltage(self, axis: int) -> float:
        """
        Get the actuator voltage of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :return: The actuator voltage in mV.
        """
        response = self._perform_request(AttoJSONMethods.GET_CONTROL_AMPLITUDE.value, [axis])
        if response:
            return response[1]  # Assuming the position is the second item in the response
        else:
            return -1.0

    def set_control_frequency(self, axis: int, frequency_mhz: int) -> None:
        """
        Set the actuator frequency for a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :param frequency_mhz: The actuator frequency to set in millHertz (up to 5000000 mHz).
        """
        if axis not in self.channels:
            raise ValueError(f"Invalid axis {axis}. Valid axes are {self.channels}.")
        if not (0 <= frequency_mhz <= 5000000):
            raise ValueError(f"Voltage must be between 0 and 5000000 mHz. Received: {frequency_mhz}.")
        self._perform_request(AttoJSONMethods.SET_CONTROL_FREQUENCY.value, [axis, frequency_mhz])
        print(f"Set actuator voltage for axis {axis} to {frequency_mhz} mV.")

    def get_status(self, channel: int) -> str:
        """
        Get the status of a specific channel.

        :param channel: The channel number to check.
        :return: Status as a string ("Moving" or "Idle").
        """
        moving_status = self.get_moving_status()
        if moving_status and channel in moving_status:
            return "Moving" if moving_status[channel] else "Idle"
        else:
            return "Unknown"

    def get_position_unit(self, channel: int) -> str:
        """
        Get the position unit of the specified channel.

        :param channel: The channel number.
        :return: Position unit as a string.
        """
        return self._axes_pos_units[channel]

    def readInpos(self, channel: int) -> bool:
        """
        Check if the axis is in position (not moving).

        :param channel: The channel number.
        :return: True if in position, False otherwise.
        """
        moving_status = self.get_moving_status()
        if moving_status and channel in moving_status:
            return not moving_status[channel]
        else:
            return True  # Assume in position if status not available

    def generatePulse(self, channel: int) -> None:
        """
        No operation for AttoDry800.

        :param channel: The channel number.
        """
        pass

    # Private helper methods
    def _simulate_action(self, action: str) -> None:
        """
        Simulate an action if in simulation mode.

        :param action: The action description to print.
        """
        if self.simulation:
            print(f"Simulating {action}.")

    def _perform_request(self, method: str, params: List, verbose: bool = False) -> any:
        """
        Perform a request to the device and handle errors.

        :param method: The method name to request.
        :param params: The parameters for the request.
        :param verbose: If True, print detailed output.
        :return: The response from the device.
        """
        if self.simulation:
            self._simulate_action(f"{method} with params {params}")
            return 0
        try:
            response = self.device.request(method, params)
            self.device.handle_error(response, self.simulation)
            if verbose:
                print(f"Request {method} with params {params} successful.")
            return response
        except Exception as e:
            print(f"Error performing request {method} with params {params}: {e}")
            self.disconnect()
            time.sleep(0.1)
            self.connect()
            self._perform_request(method, params, verbose)

    def _check_and_enable_output(self, channel: int) -> None:
        """
        Check if the output and control move for a given channel are enabled; if not, enable them.

        :param channel: The channel number to check.
        """
        # Check if the control output is enabled
        response_output = self._perform_request(AttoJSONMethods.GET_CONTROL_OUTPUT.value, [channel])
        if response_output and not response_output[1]:
            self._perform_request(AttoJSONMethods.SET_CONTROL_OUTPUT.value, [channel, True])

        # Check if the control move is enabled
        response_move = self._perform_request(AttoJSONMethods.GET_CONTROL_MOVE.value, [channel])
        if response_move and not response_move[1]:
            self._perform_request(AttoJSONMethods.SET_CONTROL_MOVE.value, [channel, True])

    def get_position(self, axis: int) -> Optional[float]:
        """
        Get the current position of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :return: The current position in nanometers.
        """
        response = self._perform_request(AttoJSONMethods.GET_POSITION.value, [axis])
        if response:
            return response[1]  # Assuming the position is the second item in the response
        else:
            return None

    def get_moving_status(self) -> Dict[int, bool]:
        """
        Read the moving status of all axes.

        :return: A dictionary with axis numbers as keys and their moving status (True/False) as values.
        """
        response = self._perform_request(AttoJSONMethods.GET_STATUS_MOVING_ALL_AXES.value, [])
        if response:
            return {axis: response[axis] for axis in self.channels}
        else:
            return {}

    def get_control_frequency(self, axis: int) -> float:
        """
        Get the control frequency of a specific axis.

        :param axis: The axis number (0, 1, or 2).
        :return: The control frequency in mHz.
        """
        response = self._perform_request(AttoJSONMethods.GET_CONTROL_FREQUENCY.value, [axis])
        if response:
            return response[1]  # Assuming the position is the second item in the response
        else:
            return -1.0

    def wait_for_axes_to_stop(self, axes: List[int], max_wait_time: float = 10.0) -> None:
        """
        Wait for a specified list of axes to stop moving.

        :param axes: List of axes (channels) to wait for.
        :param max_wait_time: Maximum time in seconds to wait for the axes to stop moving.
        """
        start_time = time.time()
        while time.time() - start_time < max_wait_time:
            moving_status = self.get_moving_status()
            if all(not moving_status.get(axis, False) for axis in axes):
                return
            time.sleep(0.5)  # Wait for 500 ms before checking again
        raise TimeoutError(f"Axes {axes} did not stop moving within {max_wait_time} seconds.")

    # Additional methods for temperature control (if needed)
    def set_temperature(self, temperature: float) -> None:
        """
        Set the temperature of the cryostat.

        :param temperature: The temperature to set (in Kelvin).
        """
        self._perform_request(AttoJSONMethods.SET_TEMPERATURE.value, [temperature])

    def get_temperature(self) -> float:
        """
        Get the current temperature of the cryostat.

        :return: The current temperature (in Kelvin).
        """
        response = self._perform_request(AttoJSONMethods.GET_TEMPERATURE.value, [])
        if response:
            return response[1]
        else:
            return -1.0

    def stabilize_temperature(self, stabilize: bool) -> None:
        """
        Stabilize the temperature of the cryostat.

        :param stabilize: Whether to stabilize the temperature (True/False).
        """
        self._perform_request(AttoJSONMethods.STABILIZE_TEMPERATURE.value, [stabilize])

    def get_firmware_version(self) -> str:
        """
        Get the firmware version of the cryostat.

        :return: The firmware version.
        """
        response = self._perform_request(AttoJSONMethods.GET_FIRMWARE_VERSION.value, [])
        if response:
            return response[1]
        else:
            return "Error"

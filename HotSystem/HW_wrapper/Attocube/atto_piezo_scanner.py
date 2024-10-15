from typing import List, Optional
from HW_wrapper import Keysight33500B, Motor  # Assuming the Keysight33500B wrapper exists
import numpy as np


class AttoScannerWrapper(Motor):
    def __init__(self, awg: Keysight33500B, max_travel_x: float = 40, max_travel_y: float = 40,
                 serial_number: str = None, name: str = None):
        """
        Initializes the Atto Scanner Wrapper with the Keysight 33500B AWG and implements the Motor interface.

        :param awg: The Keysight 33500B AWG device object.
        :param max_travel_x: Maximum travel range in microns for the X-axis.
        :param max_travel_y: Maximum travel range in microns for the Y-axis.
        :param serial_number: Optional serial number of the AWG device.
        :param name: Optional name of the AWG device.
        """
        super().__init__(serial_number, name)
        self.awg = awg
        self.max_travel_x = max_travel_x  # Max travel range in microns for X
        self.max_travel_y = max_travel_y  # Max travel range in microns for Y
        self.voltage_limit = 10  # The AWG cannot exceed ±10V
        self.no_of_channels = 2  # Two channels for X and Y
        self.channels = [1, 2]  # Channels for X and Y
        self.velocity: Optional[List[float]] = [0.0, 0.0]  # Default velocities for both channels

    def connect(self) -> None:
        """
        Establish a connection to the Keysight 33500B AWG.
        """
        self.awg.connect()

    def disconnect(self) -> None:
        """
        Disconnect the Keysight 33500B AWG.
        """
        self.awg.disconnect()

    def is_connected(self) -> bool:
        """
        Check if the Keysight 33500B AWG is connected.
        :return: True if connected, False otherwise.
        """
        return self.awg.is_connected

    def stop_all_axes(self) -> None:
        """
        Stop all movement by resetting the AWG output to zero for both channels.
        """
        self.awg.set_offset(0.0, channel=1)
        self.awg.set_offset(0.0, channel=2)
        print("All axes stopped.")

    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position (0 volts).

        :param channel: The channel number (1 for X-axis, 2 for Y-axis).
        """
        if channel in self.channels:
            self.awg.set_offset(0.0, channel=channel)
            print(f"Channel {channel} moved to home position (0V).")
        else:
            raise ValueError(f"Invalid channel: {channel}. Only channels 1 and 2 are supported.")

    def move_absolute(self, channel: int, position: int|float) -> None:
        """
        Move a specific channel to an absolute position by converting the position to a voltage.

        :param channel: The channel number (1 for X, 2 for Y).
        :param position: The target position in microns.
        """
        if channel == 1:
            voltage = self._position_to_voltage(position, self.max_travel_x)
        elif channel == 2:
            voltage = self._position_to_voltage(position, self.max_travel_y)
        else:
            raise ValueError("Invalid channel. Only channel 1 (X-axis) or channel 2 (Y-axis) are supported.")

        self.awg.set_offset(voltage, channel=channel)
        print(f"Moved channel {channel} to absolute position {position} microns (voltage: {voltage}V).")

    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps (microns).

        :param channel: The channel number to move.
        :param steps: The number of steps to move relative to the current position.
        """
        current_voltage = self.awg.get_current_voltage(channel)
        current_position = self._voltage_to_position(current_voltage, channel)
        new_position = current_position + steps
        self.move_absolute(channel, new_position)
        print(f"Moved channel {channel} by {steps} microns (relative movement).")

    def set_zero_position(self, channel: int) -> None:
        """
        Set the current position of a specific channel to zero (resets the position to home).

        :param channel: The channel number to zero.
        """
        self.move_to_home(channel)
        print(f"Set channel {channel} to zero position.")

    def get_status(self, channel: int) -> str:
        """
        Get the status of a specific channel. For the AWG, this can be simplified to show whether
        the channel is outputting or stopped.

        :param channel: The channel number to check.
        :return: Status as a string.
        """
        voltage = self.awg.get_current_voltage(channel)
        if voltage == 0:
            return f"Channel {channel} is at home position (0V)."
        else:
            return f"Channel {channel} is outputting {voltage}V."

    def _enforce_voltage_limit(self, voltage: float) -> float:
        """
        Ensure the voltage stays within the range of ±10V.

        :param voltage: The desired voltage.
        :return: The voltage, limited to the range of ±10V.
        """
        return np.clip(voltage, -self.voltage_limit, self.voltage_limit)

    def _position_to_voltage(self, position: float, max_travel: float) -> float:
        """
        Convert a position in microns to the corresponding voltage, respecting the max travel range.

        :param position: The position in microns.
        :param max_travel: The maximum travel range for the axis in microns.
        :return: The corresponding voltage, limited to ±10V.
        """
        voltage = position / (max_travel / self.voltage_limit)  # Scale to voltage range
        return self._enforce_voltage_limit(voltage)

    def _voltage_to_position(self, voltage: float, channel: int) -> float:
        """
        Convert a voltage to a position in microns based on the travel range for the channel.

        :param voltage: The voltage to convert.
        :param channel: The channel to calculate for (1 for X-axis, 2 for Y-axis).
        :return: The corresponding position in microns.
        """
        if channel == 1:
            return voltage * (self.max_travel_x / self.voltage_limit)
        elif channel == 2:
            return voltage * (self.max_travel_y / self.voltage_limit)
        else:
            raise ValueError(f"Invalid channel: {channel}. Only channels 1 and 2 are supported.")

    def MoveABSOLUTE(self, channel: int, position: float) -> None:
        """
        Move to an absolute position by setting a DC value on the specified channel.

        :param channel: The AWG channel (1 for X, 2 for Y).
        :param position: Desired position in microns.
        """
        if channel == 1:
            voltage = self._position_to_voltage(position, self.max_travel_x)
        elif channel == 2:
            voltage = self._position_to_voltage(position, self.max_travel_y)
        else:
            raise ValueError("Invalid channel. Only channel 1 (X-axis) or channel 2 (Y-axis) are supported.")

        self._move_with_velocity(channel, self.awg.get_current_voltage(channel), voltage)
        print(f"Moved channel {channel} to {position} microns (voltage: {voltage}V).")

    def _move_with_velocity(self, channel: int, start_position: float, end_position: float) -> None:
        """
        Move from start to end position by ramping the voltage, simulating a velocity-based movement.

        :param channel: The AWG channel (1 for X, 2 for Y).
        :param start_position: Starting position in microns.
        :param end_position: Ending position in microns.
        """
        if channel == 1:
            start_voltage = self._position_to_voltage(start_position, self.max_travel_x)
            end_voltage = self._position_to_voltage(end_position, self.max_travel_x)
        elif channel == 2:
            start_voltage = self._position_to_voltage(start_position, self.max_travel_y)
            end_voltage = self._position_to_voltage(end_position, self.max_travel_y)
        else:
            raise ValueError("Invalid channel. Only channel 1 (X-axis) or channel 2 (Y-axis) are supported.")

        duration = abs(end_position - start_position) / self.velocity[channel]  # Time for the movement
        num_points = int(duration * 1000)  # 1 ms step for smooth ramp
        voltage_ramp = [start_voltage + (end_voltage - start_voltage) * i / num_points for i in range(num_points)]

        self.awg.write_arbitrary_waveform(voltage_ramp, channel=channel)
        print(f"Ramping channel {channel} from {start_position} to {end_position} microns.")

    def MoveToPoints(self, channel: int, points: List[float]) -> None:
        """
        Move to a series of points using an arbitrary waveform and external triggers.

        :param channel: The AWG channel (1 for X, 2 for Y).
        :param points: List of points in microns to move through.
        """
        if channel == 1:
            voltage_points = [self._position_to_voltage(p, self.max_travel_x) for p in points]
        elif channel == 2:
            voltage_points = [self._position_to_voltage(p, self.max_travel_y) for p in points]
        else:
            raise ValueError("Invalid channel. Only channel 1 (X-axis) or channel 2 (Y-axis) are supported.")

        self.awg.write_arbitrary_waveform(voltage_points, channel=channel)
        self.awg.set_external_trigger_advance()
        print(f"Set up movement on channel {channel} for points: {points} microns.")

    def SetVelocity(self, channel: int, velocity: float) -> None:
        """
        Set the velocity for continuous movement.

        :param channel: The AWG channel (1 for X, 2 for Y).
        :param velocity: The velocity in microns/second.
        """
        print(f"Velocity set to {velocity} microns/second on channel {channel}.")
        # This could be tied into the ramping function for gradual movement.
        self.velocity[channel] = velocity

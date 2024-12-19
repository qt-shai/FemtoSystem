from typing import List, Optional, Dict
import numpy as np
from HW_wrapper.abstract_motor import Motor
from HW_wrapper import Keysight33500B
import threading
import time


class AttoScannerWrapper(Motor):
    """
    Wrapper class for controlling the AttoScanner using the Keysight 33500B AWG.
    Implements the Motor interface for compatibility with GUIMotor.
    """

    def __init__(self, awg: Keysight33500B, max_travel_x: float = 40e6, max_travel_y: float = 40e6,
                 serial_number: Optional[str] = None, name: Optional[str] = "AttoScanner",
                 simulation: bool = False, polling_rate: float = 10.0):
        """
        Initializes the AttoScannerWrapper with the Keysight 33500B AWG and implements the Motor interface.

        :param awg: The Keysight 33500B AWG device object.
        :param max_travel_x: Maximum travel range for the X-axis in picometers.
        :param max_travel_y: Maximum travel range for the Y-axis in picometers.
        :param serial_number: Optional serial number of the AWG device.
        :param name: Optional name of the AWG device.
        :param simulation: Boolean flag to indicate if in simulation mode.
        :param polling_rate: The rate at which the motor's position is polled (in Hz).
        """
        super().__init__(serial_number=serial_number, name=name, polling_rate=polling_rate)
        self.awg = awg
        self.max_travel_x = max_travel_x  # Max travel range in pm for X
        self.max_travel_y = max_travel_y  # Max travel range in pm for Y
        self.voltage_limit = 10.0  # The AWG cannot exceed ±10V
        self.no_of_channels = 2  # Two channels for X and Y
        self.channels = [0, 1]  # Logical channels: 0 for X, 1 for Y
        self.StepsIn1mm = 1e9  # Steps per mm; adjust as needed
        self._axes_positions: Dict[int, float] = {ch: 0.0 for ch in self.channels}  # Positions in microns
        self._axes_pos_units: Dict[int, str] = {ch: "µm" for ch in self.channels}
        self.velocity: List[float] = [1.0, 1.0]  # Default velocities for both axes in microns/second
        self._connected: bool = False
        self.simulation = simulation  # Store the simulation flag if needed

    def connect(self) -> None:
        """Establish a connection to the Keysight 33500B AWG."""
        if self.simulation:
            self._connected = True
            self.start_position_updates()
        else:
            try:
                self.awg.connect()
                self._connected = True
                self.start_position_updates()
                print("AttoScanner connected.")
            except Exception as e:
                print(f"Error connecting to the device: {e}")
                self._connected = False
                raise e
        self.start_position_updates()

    def disconnect(self) -> None:
        """Disconnect the Keysight 33500B AWG."""
        self.stop_position_updates()
        self.awg.disconnect()
        self._connected = False
        print("AttoScanner disconnected.")

    def is_connected(self) -> bool:
        """Check if the Keysight 33500B AWG is connected."""
        return self._connected

    def stop_all_axes(self) -> None:
        """Stop all movement by resetting the AWG output to zero for both channels."""
        for ch in [1, 2]:
            self.awg.set_offset(0.0, channel=ch)
        print("All axes stopped.")

    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position (0 volts).

        :param channel: The logical channel number (0 for X-axis, 1 for Y-axis).
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            self.awg.set_offset(0.0, channel=awg_channel)
            self._set_position(channel, 0.0)
            print(f"Channel {channel} moved to home position (0V).")
        else:
            raise ValueError(f"Invalid channel: {channel}. Only channels 0 and 1 are supported.")

    def MoveABSOLUTE(self, channel: int, position: int) -> None:
        """
        Move a specific channel to an absolute position by converting the position to a voltage.

        :param channel: The logical channel number (0 for X, 1 for Y).
        :param position: The target position in steps.
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            position_microns = position * 1000 / self.StepsIn1mm  # Convert steps to microns
            voltage = self._position_to_voltage(position_microns, channel)
            self.awg.set_offset(voltage, channel=awg_channel)
            self._set_position(channel, position_microns)
            print(f"Moved channel {channel} to position {position_microns:.2f} µm (voltage: {voltage:.2f} V).")
        else:
            raise ValueError(f"Invalid channel: {channel}.")

    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The logical channel number to move.
        :param steps: The number of steps to move.
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            delta_microns = steps * 1000 / self.StepsIn1mm  # Convert steps to microns
            current_position = self.get_position(channel)
            new_position = current_position + delta_microns
            voltage = self._position_to_voltage(new_position, channel)
            self.awg.set_offset(voltage, channel=awg_channel)
            self._set_position(channel, new_position)
            print(f"Moved channel {channel} by {delta_microns:.2f} µm to position {new_position:.2f} µm (voltage: {voltage:.2f} V).")
        else:
            raise ValueError(f"Invalid channel: {channel}.")

    def get_position(self, channel: int) -> Optional[float]:
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            voltage = self.awg.get_current_voltage(awg_channel)
            position = self._voltage_to_position(voltage, channel)
            return position
        else:
            raise ValueError(f"Invalid channel: {channel}.")

    def set_zero_position(self, channel: int) -> None:
        """
        Set the current position of a specific channel to zero (resets the position to home).

        :param channel: The logical channel number to zero.
        """
        self.move_to_home(channel)
        print(f"Set channel {channel} to zero position.")

    def get_status(self, channel: int) -> str:
        """
        Get the status of a specific channel.

        :param channel: The logical channel number to check.
        :return: Status as a string.
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            voltage = self.awg.get_current_voltage(awg_channel)
            if voltage == 0.0:
                return "Idle"
            else:
                return "Moving"
        else:
            return "Unknown"

    def init_before_scan(self) -> None:
        """
        Initialize the AWG settings before starting a scan.
        """
        # Set up the AWG for scanning, e.g., set trigger modes, waveforms, etc.
        for axis in self.channels:
            awg_channel = self._map_channel_to_awg_channel(axis)
            self.awg.set_waveform_type("TRIANGLE", awg_channel)
            # Additional configuration can be done here
        print("AttoScanner initialized before scan.")

    def update_positions(self) -> None:
        """
        Update the motor's positions and notify observers.
        """
        for channel in self.channels:
            new_position = self.get_current_position(channel)
            self._set_position(channel, new_position)

    def get_position_unit(self, channel: int) -> str:
        """
        Get the position unit of the specified axis.

        :param channel: Logical channel (0 for X-axis, 1 for Y-axis).
        :return: Position unit as a string.
        """
        return self._axes_pos_units[channel]

    # Private helper methods
    def _map_channel_to_awg_channel(self, channel: int) -> Optional[int]:
        """
        Map logical channel (0, 1) to AWG channel (1, 2).

        :param channel: The logical channel number (0 for X-axis, 1 for Y-axis).
        :return: The corresponding AWG channel number (1 or 2), or None if invalid channel.
        """
        channel_mapping = {0: 1, 1: 2}
        return channel_mapping.get(channel)

    def _position_to_voltage(self, position: float, channel: int) -> float:
        """
        Convert a position in microns to the corresponding voltage.

        :param position: The position in microns.
        :param channel: Logical channel (0 for X-axis, 1 for Y-axis).
        :return: The corresponding voltage, limited to ±10V.
        """
        max_travel = self.max_travel_x if channel == 0 else self.max_travel_y
        voltage = position * (self.voltage_limit / max_travel)
        return self._enforce_voltage_limit(voltage)

    def _voltage_to_position(self, voltage: float, channel: int) -> float:
        """
        Convert a voltage to a position in microns based on the travel range for the channel.

        :param voltage: The voltage to convert.
        :param channel: The logical channel to calculate for (0 for X-axis, 1 for Y-axis).
        :return: The corresponding position in microns.
        """
        max_travel = self.max_travel_x if channel == 0 else self.max_travel_y
        position = voltage * (max_travel / self.voltage_limit)
        return position

    def _enforce_voltage_limit(self, voltage: float) -> float:
        """
        Ensure the voltage stays within the range of ±10V.

        :param voltage: The desired voltage.
        :return: The voltage, limited to the range of ±10V.
        """
        return float(np.clip(voltage, -self.voltage_limit, self.voltage_limit))

    def readInpos(self, channel: int) -> bool:
        """
        For the AttoScanner, assume it is always in position.

        :param channel: The logical channel number.
        :return: True, as the AttoScanner is assumed to reach the position instantaneously.
        """
        return True

    def generatePulse(self, channel: int) -> None:
        """
        No operation for AttoScannerWrapper.

        :param channel: The channel number.
        """
        pass

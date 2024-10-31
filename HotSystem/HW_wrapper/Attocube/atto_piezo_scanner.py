from typing import List, Optional
import numpy as np
from HW_wrapper import Motor, Keysight33500B


class AttoScannerWrapper(Motor):
    def __init__(self, awg: Keysight33500B, max_travel_x: float = 40e6, max_travel_y: float = 40e6,
                 serial_number: Optional[str] = None, name: Optional[str] = None):
        """
        Initializes the Atto Scanner Wrapper with the Keysight 33500B AWG and implements the Motor interface.

        :param awg: The Keysight 33500B AWG device object.
        :param max_travel_x: Maximum travel range in microns for the X-axis (in pm)
        :param max_travel_y: Maximum travel range in microns for the Y-axis (in pm)
        :param serial_number: Optional serial number of the AWG device.
        :param name: Optional name of the AWG device.
        """
        super().__init__(serial_number, name)
        self.awg = awg
        self.max_travel_x = max_travel_x  # Max travel range in pm for X
        self.max_travel_y = max_travel_y  # Max travel range in pm for Y
        self.voltage_limit = 10.0  # The AWG cannot exceed ±10V
        self.no_of_channels = 2  # Two channels for X and Y
        self.channels = [0, 1]  # Logical channels: 0 for X, 1 for Y
        self.StepsIn1mm = 1e9  # Steps per mm; adjust as needed
        self._axes_positions: List[float] = [0.0, 0.0]  # Initial positions for both axes in pm
        self._axes_pos_units: List[str] = ["pm", "pm"]  # Units for each axis
        self.velocity: List[float] = [1.0, 1.0]  # Default velocities for both axes in microns/second

        # Internal state
        self._axes_positions: List[float] = [0.0, 0.0]  # Positions in microns
        self._axes_pos_units: List[str] = ["pm", "pm"]
        self._connected: bool = False


    def connect(self) -> None:
        """Establish a connection to the Keysight 33500B AWG."""
        self.awg.connect()
        print("AttoScanner connected.")

    def disconnect(self) -> None:
        """Disconnect the Keysight 33500B AWG."""
        self.awg.disconnect()
        print("AttoScanner disconnected.")

    def is_connected(self) -> bool:
        """Check if the Keysight 33500B AWG is connected."""
        return self.awg.is_connected

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
            self._axes_positions[channel] = 0.0
            print(f"Channel {channel} moved to home position (0V).")
        else:
            raise ValueError(f"Invalid channel: {channel}. Only channels 0 and 1 are supported.")

    def MoveABSOLUTE(self, channel: int, position: float) -> None:
        """
        Move a specific channel to an absolute position by converting the position to a voltage.

        :param channel: The logical channel number (0 for X, 1 for Y).
        :param position: The target position in pm
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            position_microns = position * 1000 / self.StepsIn1mm  # Convert steps to microns
            voltage = self._position_to_voltage(position_microns, channel)
            self.awg.set_offset(voltage, channel=awg_channel)
            self._axes_positions[channel] = position_microns
            print(f"Moved channel {channel} to position {position_microns:.2f} µm (voltage: {voltage:.2f} V).")
        else:
            raise ValueError(f"Invalid channel: {channel}.")

    def move_relative(self, channel: int, steps: float) -> None:
        """
        Move a specific channel by a relative number of steps (pm converted to steps).

        :param channel: The logical channel number to move.
        :param steps: The number of steps to move.
        """
        awg_channel = self._map_channel_to_awg_channel(channel)
        if awg_channel is not None:
            delta_microns = steps * 1000 / self.StepsIn1mm  # Convert steps to microns
            new_position = self._axes_positions[channel] + delta_microns
            voltage = self._position_to_voltage(new_position, channel)
            self.awg.set_offset(voltage, channel=awg_channel)
            self._axes_positions[channel] = new_position
            print(f"Moved channel {channel} by {delta_microns:.2f} µm (voltage: {voltage:.2f} V).")
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
                return f"Channel {channel} is at home position (0V)."
            else:
                return f"Channel {channel} is outputting {voltage}V."
        else:
            return f"Channel {channel} is invalid."

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

    def _map_channel_to_awg_channel(self, channel: int) -> Optional[int]:
        """
        Map logical channel (0, 1) to AWG channel (1, 2).

        :param channel: The logical channel number (0 for X, 1 for Y).
        :return: The corresponding AWG channel number (1 or 2), or None if invalid channel.
        """
        channel_mapping = {0: 1, 1: 2}
        return channel_mapping.get(channel)

    def _position_to_voltage(self, position: float, max_travel: float) -> float:
        """
        Convert a position in microns to the corresponding voltage.

        :param position: The position in microns.
        :param max_travel: The maximum travel range for the axis in microns.
        :return: The corresponding voltage, limited to ±10V.
        """
        voltage = position * (self.voltage_limit / max_travel)
        return self._enforce_voltage_limit(voltage)

    def _enforce_voltage_limit(self, voltage: float) -> float:
        """
        Ensure the voltage stays within the range of ±10V.

        :param voltage: The desired voltage.
        :return: The voltage, limited to the range of ±10V.
        """
        return float(np.clip(voltage, -self.voltage_limit, self.voltage_limit))

    def ReadIsInPosition(self, channel: int) -> bool:
        """
        For the AttoScanner, assume it is always in position.

        :param channel: The logical channel number.
        :return: True, as the AttoScanner is assumed to reach the position instantaneously.
        """
        return channel in self.channels

    def generatePulse(self, channel: int) -> None:
        """
        No operation for AttoScannerWrapper.

        :param channel: The channel number.
        """
        pass

    def get_current_position(self, channel: int) -> float:
        """
        Get the current position of the specified axis in microns.

        :param channel: Logical channel (0 for X-axis, 1 for Y-axis).
        :return: Current position in microns.
        """
        return self._axes_positions[channel]

    def GetPosition(self) -> None:
        """
        Update internal position data by reading current voltage and converting to position.
        """
        for channel in self.channels:
            awg_channel = self._map_channel_to_awg_channel(channel)
            voltage = self.awg.get_current_voltage(awg_channel)
            position = self._voltage_to_position(voltage, channel)
            self._axes_positions[channel] = position

    def _voltage_to_position(self, voltage: float, channel: int) -> float:
        """
        Convert a voltage to a position in microns based on the travel range for the channel.

        :param voltage: The voltage to convert.
        :param channel: The logical channel to calculate for (0 for X-axis, 1 for Y-axis).
        :return: The corresponding position in microns.
        """
        if channel == 0:
            return voltage * (self.max_travel_x / self.voltage_limit)
        elif channel == 1:
            return voltage * (self.max_travel_y / self.voltage_limit)
        else:
            raise ValueError(f"Invalid channel: {channel}. Only channels 0 and 1 are supported.")

    def get_position_unit(self, channel: int) -> str:
        """
        Get the position unit of the specified axis.

        :param channel: Logical channel (0 for X-axis, 1 for Y-axis).
        :return: Position unit as a string.
        """
        return self._axes_pos_units[channel]

    @property
    def AxesPositions(self) -> List[float]:
        """List of current axis positions in microns."""
        return self._axes_positions

    @property
    def AxesPosUnits(self) -> List[str]:
        """List of position units for each axis."""
        return self._axes_pos_units
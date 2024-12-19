from enum import Enum
from typing import List, Optional, Tuple

import numpy as np

from HW_wrapper.abstract_motor import Motor
from pylablib.devices import Attocube
import time


class ANC300Modes(Enum):
    GND = "gnd"  # Ground
    STP = "stp"  # Step
    CAP = "cap"  # Measure capacitance, then ground
    OFFS = "offs"  # Offset only, no stepping
    STP_PLUS = "stp+"  # Offset with added stepping waveform
    STP_MINUS = "stp-"  # Offset with subtracted stepping

class Anc300Wrapper(Motor):
    """
    Wrapper class for controlling the Attocube ANC300 positioner via the pylablib Attocube module.
    Implements the Motor interface for compatibility with GUIMotor.
    """

    def __init__(self, conn: str, serial_number: Optional[str] = None, name: str = "ANC300", simulation: bool = False):
        """
        Initialize the ANC300 controller.

        :param conn: Connection parameters for the ANC300 (e.g., IP address or serial port).
        :param serial_number: Serial number of the ANC300 device.
        :param name: Name of the ANC300 device.
        :param simulation: Boolean flag to indicate if in simulation mode.
        """
        super().__init__(serial_number=serial_number, name=name)
        self.max_travel = 50e-6 #meters
        self.simulation = simulation
        self.conn = conn
        self.no_of_channels: int = 2  # Adjust based on actual device configuration
        self.channels: List[int] = [1, 2]  # Logical channels: 1, 2 for X, Y axes
        self.StepsIn1mm: int = int(1e12)  # Steps in 1 mm (assuming 1 step = 1 pm)
        self._axes_positions: List[float] = [0.0] * self.no_of_channels  # Positions in picometers
        self._axes_pos_units: List[str] = ["pm"] * self.no_of_channels
        self._connected: bool = False
        self.device:Optional[Attocube.ANC300] = None  # Will be initialized in connect()
        self.offset_voltage_min = 0 # Volts
        self.offset_voltage_max = 150 # Volts

    def connect(self) -> None:
        """Connect to the ANC300 device."""
        if self.simulation:
            self._simulate_action("connect to the ANC300")
            self._connected = True
        else:
            try:
                self.device = Attocube.ANC300(self.conn)
                # Try to get device info to confirm connection
                device_info = self.device.get_device_info()
                print(f"Connected to ANC300: Serial={device_info.serial}, Version={device_info.version}")
                self._connected = True
            except Exception as e:
                print(f"Error connecting to the device: {e}")
                self._connected = False
                raise e

    def disconnect(self) -> None:
        """Disconnect from the ANC300 device."""
        if self.simulation:
            self._simulate_action("disconnect from the ANC300")
            self._connected = False
        else:
            try:
                if self.device is not None:
                    self.device.close()
                self._connected = False
                print("Successfully disconnected from the ANC300.")
            except Exception as e:
                print(f"Error disconnecting from the device: {e}")
                raise e

    @property
    def is_connected(self) -> bool:
        """Check if the ANC300 is connected."""
        if self.simulation:
            return self._connected
        else:
            try:
                # Try to get device info to confirm connection
                device_info = self.device.get_device_info()
                return True
            except Exception:
                return False

    def stop_all_axes(self) -> None:
        """Stop all movement on all axes."""
        if self.simulation:
            self._simulate_action("stop all axes")
        else:
            for channel in self.channels:
                self.device.stop(channel)  # channel indices start from 1 in pylablib
            print("All axes stopped.")

    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position.

        :param channel: The logical channel number (0 for X-channel, 1 for Y-channel, etc.).
        """
        if self.simulation:
            self._simulate_action(f"move channel {channel} to home")
        else:
            # ANC300 does not have a built-in home command; we can define home as zero position
            self.MoveABSOLUTE(channel, 0)
            print(f"Channel {channel} moved to home position (0 pm).")

    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of microns.

        :param channel: The logical channel number.
        :param steps: The number of microns to move.
        """
        self.verify_channel(channel)
        if self.simulation:
            self._simulate_action(f"move channel {channel} by {steps} steps")
            self._axes_positions[channel] += steps
            return

        steps_voltages = self._convert_units_to_meters(steps)
        current_position = self.get_position(channel)
        self.MoveABSOLUTE(channel, np.clip(current_position+steps_voltages,0,59))
        print(f"Moved channel {channel} by {steps} pm.")

    def set_zero_position(self, channel: int) -> None:
        """
        Set the current position of a specific channel to zero.

        :param channel: The logical channel number.
        """
        if self.simulation:
            self._simulate_action(f"set zero position for channel {channel}")
            self._axes_positions[channel] = 0.0
        else:
            # There is no direct method to set the position to zero in hardware, so we adjust our internal tracking
            self._axes_positions[channel] = 0.0
            print(f"Channel {channel} position set to zero.")

    def get_status(self, channel: int) -> str:
        """
        Get the status of a specific channel.

        :param channel: The logical channel number.
        :return: Status as a string ("Moving" or "Idle").
        """
        self.verify_channel(channel)
        if self.simulation:
            return "Idle"

        is_moving = self.device.is_moving(channel)
        return "Moving" if is_moving else "Idle"

    def readInpos(self, channel: int) -> bool:
        """
        Check if the channel is in position (not moving).

        :param channel: The logical channel number.
        :return: True if in position, False otherwise.
        """
        self.verify_channel(channel)
        if self.simulation:
            return True
        return not self.device.is_moving(channel)

    def generatePulse(self, channel: int) -> None:
        """
        No operation for Anc300Wrapper.

        :param channel: The logical channel number.
        """
        pass

    def GetPosition(self) -> None:
        """Update internal positions for all axes."""
        for channel in self.channels:
            self.get_position(channel)

    def set_offset_voltage(self, channel: int, voltage: float) -> None:
        """
        Set the offset voltage for a specific channel.

        :param channel: The logical channel number.
        :param voltage: The offset voltage (in volts).
        """
        self.verify_channel(channel)
        if self.simulation:
            self._simulate_action(f"set offset voltage for channel {channel} to {voltage} V")
        else:
            if voltage > 59:
                raise ValueError(f"Voltage {voltage} exceeds the maximum allowed limit of 59V.")
            if channel not in self.channels:
                raise ValueError(f"Channel {channel} does not exist.")
            self.device.set_offset(channel, voltage)

    def get_offset_voltage(self, channel: int) -> float:
        """
        Get the offset voltage for a specific channel.

        :param channel: The logical channel number.
        :return: The offset voltage (in volts).
        """
        self.verify_channel(channel)
        if self.simulation:
            return 0.0

        return self.device.get_offset(channel)

    def get_position(self, channel: int) -> float:
        """
        Get the current position of a specific channel.

        :param channel: The channel number (0, 1, or 2).
        :return: The current position in nanometers.
        """
        self.verify_channel(channel)
        voltage = self.device.get_output(channel)
        position = self._convert_units_to_meters(voltage)
        return position

    @property
    def AxesPositions(self) -> List[float]:
        """List of current channel positions in picometers."""
        return self._axes_positions

    @property
    def AxesPosUnits(self) -> List[str]:
        """List of position units for each channel."""
        return self._axes_pos_units

    # Private helper methods
    def _simulate_action(self, action: str) -> None:
        """
        Simulate an action in simulation mode.

        :param action: The action description to print.
        """
        if self.simulation:
            print(f"Simulating {action}.")

    def _convert_units_to_meters(self, position: float) -> float:
        """
        Convert position from voltage to meters.

        :param position: Position in picometers.
        :return: Position in meters.
        """
        return position * self.max_travel/self.offset_voltage_max

    def _convert_units_to_offset_voltage(self,position: float) -> float:
        """
         Convert position from picometers to offset voltage.

        :param position: Position in picometers.
        :return: Position in offset voltage (in volts).
        """
        return position * self.offset_voltage_max/self.max_travel

    def MoveABSOLUTE(self, channel: int, position: float) -> None:
        self.verify_channel(channel)
        voltage = self._convert_units_to_offset_voltage(position)
        self.set_offset_voltage(channel, voltage)

    def set_external_input_modes(self, channel: int, dcin: bool = False, acin:bool = False) -> None:
        """
        Enable/Disable external input modes.

        :param channel: The channel number. (1,2)
        :param dcin: Enable/Disable DC input.
        :param acin: Enable/Disable AC input.
        """
        self.verify_channel(channel)
        if self.simulation:
            return
        self.device.set_external_input_modes(channel, dcin, acin)


    def get_external_input_modes(self, channel: int) -> Tuple[bool,bool]:
        """
        Get external input modes.

        :param channel: The channel number. (1,2)
        """
        self.verify_channel(channel)
        if self.simulation:
            return True,True
        if channel in self.channels:
            return self.device.get_external_input_modes(channel)


    def set_mode(self, channel: int, mode: ANC300Modes) -> None:
        """
        Set channel mode.

        `channel` is either a channel index (starting from 1), or "all" (all axes).
        `mode` can be one of the modes defined in `ANC300_MODES`.
        Note that not all modes are supported by all modules:
        - ANM150 doesn't support offset voltage ("offs", "stp+", "stp-" modes).
        - ANM200 doesn't support stepping ("stp", "stp+", "stp-" modes).

        :param channel: Channel index (1-based) or "all" for all axes.
        :param mode: Mode to set, as defined in `ANC300_MODES`.
        """
        self.verify_channel(channel)
        if self.simulation:
            print(f"Simulating setting mode for channel {channel} to {mode.value}")
            return
        self.device.set_mode(channel, mode.value)


    def get_mode(self, channel: int) -> ANC300Modes:
        """
        Get the mode of a specific channel.

        `channel` is the channel index (starting from 1).

        :param channel: Channel index (1-based).
        :return: The current mode of the channel as an `ANC300_MODES` enum.
        """
        self.verify_channel(channel)
        if self.simulation:
            print(f"Simulating getting mode for channel {channel}")
            return ANC300Modes.GND  # Default simulated mode
        mode_value = self.device.get_mode(channel)
        try:
            return ANC300Modes(mode_value)
        except ValueError:
            print(f"Unsupported mode value '{mode_value}' returned for channel {channel}")
            raise ValueError(f"Unsupported mode value '{mode_value}' for channel {channel}")



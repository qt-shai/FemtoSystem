from typing import List, Optional
from HW_wrapper.abstract_motor import Motor
from pylablib.devices import Attocube
import time

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
        self.simulation = simulation
        self.conn = conn
        self.no_of_channels: int = 3  # Adjust based on actual device configuration
        self.channels: List[int] = [0, 1, 2]  # Logical channels: 0, 1, 2 for X, Y, Z axes
        self.StepsIn1mm: int = int(1e12)  # Steps in 1 mm (assuming 1 step = 1 pm)
        self._axes_positions: List[float] = [0.0, 0.0, 0.0]  # Positions in picometers
        self._axes_pos_units: List[str] = ["pm", "pm", "pm"]
        self._connected: bool = False
        self.device = None  # Will be initialized in connect()

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
            for axis in self.channels:
                self.device.stop(axis + 1)  # Axis indices start from 1 in pylablib
            print("All axes stopped.")

    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position.

        :param channel: The logical channel number (0 for X-axis, 1 for Y-axis, etc.).
        """
        if self.simulation:
            self._simulate_action(f"move channel {channel} to home")
        else:
            # ANC300 does not have a built-in home command; we can define home as zero position
            self.move_absolute(channel, 0)
            print(f"Channel {channel} moved to home position (0 pm).")

    def move_absolute(self, channel: int, position: int) -> None:
        """
        Move a specific channel to an absolute position.

        :param channel: The logical channel number.
        :param position: The target position in steps (picometers converted to steps).
        """
        if self.simulation:
            self._simulate_action(f"move channel {channel} to absolute position {position} steps")
            self._axes_positions[channel] = position
        else:
            position_meters = self._convert_units_to_meters(position)
            self.device.move_to(channel + 1, position_meters)
            self.device.wait_move(channel + 1)
            self._axes_positions[channel] = position
            print(f"Moved channel {channel} to position {position} pm.")

    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The logical channel number.
        :param steps: The number of steps to move.
        """
        if self.simulation:
            self._simulate_action(f"move channel {channel} by {steps} steps")
            self._axes_positions[channel] += steps
        else:
            steps_meters = self._convert_units_to_meters(steps)
            self.device.move_by(channel + 1, steps_meters)
            self.device.wait_move(channel + 1)
            self._axes_positions[channel] += steps
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
        if self.simulation:
            return "Idle"
        else:
            is_moving = self.device.is_moving(channel + 1)
            return "Moving" if is_moving else "Idle"

    def get_current_position(self, channel: int) -> float:
        """
        Get the current position of a specific channel in picometers.

        :param channel: The logical channel number.
        :return: Current position in picometers.
        """
        if self.simulation:
            return self._axes_positions[channel]
        else:
            position_meters = self.device.get_position(channel + 1)
            position_pm = self._convert_meters_to_units(position_meters)
            self._axes_positions[channel] = position_pm
            return position_pm

    def get_position_unit(self, channel: int) -> str:
        """
        Get the position unit of the specified channel.

        :param channel: The logical channel number.
        :return: Position unit as a string ("pm").
        """
        return self._axes_pos_units[channel]

    def readInpos(self, channel: int) -> bool:
        """
        Check if the axis is in position (not moving).

        :param channel: The logical channel number.
        :return: True if in position, False otherwise.
        """
        if self.simulation:
            return True
        else:
            return not self.device.is_moving(channel + 1)

    def generatePulse(self, channel: int) -> None:
        """
        No operation for Anc300Wrapper.

        :param channel: The logical channel number.
        """
        pass

    def GetPosition(self) -> None:
        """Update internal positions for all axes."""
        for channel in self.channels:
            self.get_current_position(channel)

    @property
    def AxesPositions(self) -> List[float]:
        """List of current axis positions in picometers."""
        return self._axes_positions

    @property
    def AxesPosUnits(self) -> List[str]:
        """List of position units for each axis."""
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
        Convert position from picometers to meters.

        :param position: Position in picometers.
        :return: Position in meters.
        """
        return position * self.StepsIn1mm*1e3  # 1 picometer = 1e-12 meters

    def _convert_meters_to_units(self, position_meters: float) -> float:
        """
        Convert position from meters to picometers.

        :param position_meters: Position in meters.
        :return: Position in picometers.
        """
        return position_meters * self.StepsIn1mm*1e3  # 1 meter = 1e12 picometers

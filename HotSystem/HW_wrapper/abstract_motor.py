from abc import ABC, abstractmethod
from typing import List


class Motor(ABC):
    """
    Abstract base class for motor control.
    This class defines the interface that all motor types must implement to be compatible with the GUI.
    """

    def __init__(self, serial_number: str = None, name: str = None):
        """
        Initialize the motor with optional unique identifiers.

        :param serial_number: The serial number of the motor device.
        :param name: The name of the motor device.
        """
        self.no_of_channels: int = 0
        self.channels: List[int] = []
        self.StepsIn1mm: int = 1000000  # Default steps in 1mm for positioning; can be overridden
        self.serial_number: str = serial_number  # Optional serial number
        self.name: str = name  # Optional device name

    @abstractmethod
    def connect(self) -> None:
        """Establish a connection to the motor device."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the motor device."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the motor device is connected."""
        pass

    @abstractmethod
    def stop_all_axes(self) -> None:
        """Stop all movement on all axes."""
        pass

    @abstractmethod
    def move_to_home(self, channel: int) -> None:
        """
        Move a specific channel to its home position.

        :param channel: The channel number to move.
        """
        pass

    @abstractmethod
    def move_absolute(self, channel: int, position: int) -> None:
        """
        Move a specific channel to an absolute position.

        :param channel: The channel number to move.
        :param position: The target position in steps.
        """
        pass

    @abstractmethod
    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The channel number to move.
        :param steps: The number of steps to move.
        """
        pass

    @abstractmethod
    def set_zero_position(self, channel: int) -> None:
        """
        Set the current position of a specific channel to zero.

        :param channel: The channel number to zero.
        """
        pass

    @abstractmethod
    def get_status(self, channel: int) -> str:
        """
        Get the status of a specific channel.

        :param channel: The channel number to check.
        :return: Status as a string.
        """
        pass

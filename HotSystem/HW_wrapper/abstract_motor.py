from abc import ABC, abstractmethod
from typing import List, Optional, Callable, Dict
import threading
import time

import numpy as np


class Motor(ABC):
    """
    Abstract base class for motor control.
    This class defines the interface that all motor types must implement to be compatible with the GUI.
    """

    def __init__(self, serial_number: Optional[str] = None, name: Optional[str] = None,
                 polling_rate: float = 10.0, simulation:bool = False):
        """
        Initialize the motor with optional unique identifiers.

        :param serial_number: The serial number of the motor device.
        :param name: The name of the motor device.
        :param polling_rate: The rate at which the motor's position is polled (in Hz).
        """
        self.simulation:bool = simulation
        self.no_of_channels: int = 0
        self.channels: List[int] = []
        self.StepsIn1mm: int = 1000000  # Default steps in 1mm for positioning; can be overridden
        self.serial_number: Optional[str] = serial_number  # Optional serial number
        self.name: Optional[str] = name  # Optional device name
        self._polling_rate: float = polling_rate
        self._observers: List[Callable[[int, float], None]] = []  # Observers to notify on position change
        self._axes_positions: Dict[int, float] = {}  # Positions per channel
        self._axes_pos_units: Dict[int, str] = {}
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def set_polling_rate(self, rate: float) -> None:
        """
        Set the polling rate for position updates.

        :param rate: New polling rate in Hz.
        """
        self._polling_rate = rate

    def add_position_observer(self, observer: Callable[[int, float], None]) -> None:
        """
        Add an observer that will be notified when the position changes.

        :param observer: A callable that accepts the channel number and new position.
        """
        self._observers.append(observer)

    def remove_position_observer(self, observer: Callable[[int, float], None]) -> None:
        """
        Remove an observer.

        :param observer: The observer to remove.
        """
        self._observers.remove(observer)

    def get_position(self, channel: int) -> Optional[float]:
        """
        Get the current position of a specific channel.

        :param channel: The channel number.
        :return: The current position.
        """
        return self._axes_positions.get(channel, 0.0)

    def get_position_unit(self, channel: int) -> float:
        """
        Get the position units of a specific channel.

        :param channel: The channel number.
        :return: The current position units.
        """
        return self._axes_pos_units.get(channel, 0.0)

    def _set_position(self, channel: int, value: float) -> None:
        """
        Set the position of a specific channel and notify observers.

        :param channel: The channel number.
        :param value: The new position value.
        """
        self._axes_positions[channel] = value
        # Notify observers
        for observer in self._observers:
            observer(channel, value)

    def start_position_updates(self) -> None:
        """
        Start the thread that updates the motor positions.
        """
        if self._update_thread is None or not self._update_thread.is_alive():
            self._stop_event.clear()
            self._update_thread = threading.Thread(target=self._position_update_loop)
            self._update_thread.daemon = True
            self._update_thread.start()

    def stop_position_updates(self) -> None:
        """
        Stop the position update thread.
        """
        self._stop_event.set()
        if self._update_thread is not None:
            self._update_thread.join()
            self._update_thread = None

    def _position_update_loop(self) -> None:
        """
        The loop that runs in a separate thread to update the positions.
        """
        while not self._stop_event.is_set():
            try:
                self.update_positions()
                time.sleep(1 / self._polling_rate)
            except TimeoutError:
                print(f"Timeout error in {self} position update loop.")

    def update_positions(self) -> None:
        """
        Update the motor's positions and notify observers.
        """
        for channel in self.channels:
            if not self.simulation:
                new_position = self.get_position(channel)
            else:
                new_position = int(np.random.rand(1)*self.StepsIn1mm)
            self._axes_positions[channel] = new_position

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
    def MoveABSOLUTE(self, channel: int, position: int) -> None:
        """
        Move a specific channel to an absolute position.

        :param channel: The target channel number.
        :param position: The target position in steps.
        """
        pass

    @abstractmethod
    def move_relative(self, channel: int, steps: int) -> None:
        """
        Move a specific channel by a relative number of steps.

        :param channel: The target channel number.
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

    def init_before_scan(self) -> None:
        """
        Optional method to initialize the motor before starting a scan.
        This can be overridden by subclasses if needed.
        """
        pass

    def GetPosition(self) -> None:
        """Update internal positions for all axes."""
        for channel in self.channels:
            position = self.get_position(channel)
            self._axes_positions[channel] = position

    @property
    def AxesPositions(self) -> Dict[int, float]:
        """List of current axis positions in nanometers."""
        return self._axes_positions

    @property
    def AxesPosUnits(self) -> Dict[int, str]:
        """List of position units for each axis."""
        return self._axes_pos_units

    def verify_channel(self, channel: int, verbose:bool = False) -> None:
        if channel not in self.channels:
            if verbose:
                print(f"channel {channel} is not supported. Expected values are {self.channels}")
        raise ValueError(f"channel {channel} is not supported. Expected values are {self.channels}")




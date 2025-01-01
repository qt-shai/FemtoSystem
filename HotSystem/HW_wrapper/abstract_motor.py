import threading
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict
import numpy as np

from Utils import ObserverInterface, ObservableField


class Motor(ObserverInterface, ABC):

    """
    Abstract base class for motor control.
    This class defines the interface that all motor types must implement to be compatible with the GUI.
    """

    class MotorEvents(Enum):
        POSITION_CHANGED = "position_changed"
        # Add more as needed by this specific motor class

    def __init__(self, serial_number: Optional[str] = None, name: Optional[str] = None,
                 polling_rate: float = 10.0, simulation:bool = False):
        """
        Initialize the motor with optional unique identifiers.

        :param serial_number: The serial number of the motor device.
        :param name: The name of the motor device.
        :param polling_rate: The rate at which the motor's position is polled (in Hz).
        """
        super().__init__()
        self._lock = threading.Lock()
        self.simulation:bool = simulation
        self.no_of_channels: int = 0
        self.channels: List[int] = []
        self.StepsIn1mm: int = 1000000  # Default steps in 1mm for positioning; can be overridden
        self.serial_number: Optional[str] = serial_number  # Optional serial number
        self.name: Optional[str] = name  # Optional device name
        self._polling_rate: float = polling_rate
        self.axes_positions: Dict[int, ObservableField[float]] = {
            ch: ObservableField(0.0) for ch in self.channels}
        self._axes_pos_units: Dict[int, str] = {}
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._position_bounds: Dict[int, tuple[float,float]] = {ch: (1e9,-1e9) for ch in self.channels}

    def set_polling_rate(self, rate: float) -> None:
        """
        Set the polling rate for position updates.

        :param rate: New polling rate in Hz.
        """
        self._polling_rate = rate

    def set_position(self, channel: int, value: float) -> None:
        """
        Set the position of a specific channel, then notify observers.

        :param channel: The channel number.
        :param value: The new position value.
        """
        self.verify_channel(channel)
        lower_bound, upper_bound = self._position_bounds[channel]

        if not (lower_bound <= value <= upper_bound):
            raise ValueError(
                f"Position {value} is out of bounds for channel {channel}. Bounds: ({lower_bound}, {upper_bound}).")

        with self._lock:
            self.axes_positions[channel].set(value)

    def get_position(self, channel: int) -> float:
        """
        Get the position of a specific channel, optionally notifying observers.

        :param channel: The channel number.
        :return: The current position value.
        """
        self.verify_channel(channel)
        if self.simulation:
            value = np.random.rand()
            self.axes_positions[channel].set(value)
        with self._lock:
            value = self.axes_positions[channel].get()
        return value

    def get_position_unit(self, channel: int) -> float:
        """
        Get the position units of a specific channel.

        :param channel: The channel number.
        :return: The current position units.
        """
        return self._axes_pos_units.get(channel, 0.0)

    def start_position_updates(self) -> None:
        """
        Start the thread that updates the motor positions.
        """
        if self._update_thread is None or not self._update_thread.is_alive():
            self._stop_event.clear()
            self._update_thread = threading.Thread(target=self._position_update_loop, daemon=True)
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
        thread_wait_time = 1 / self._polling_rate
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    self.update_positions()
                threading.Event().wait(thread_wait_time)
            except Exception as ex:
                print(f"Unexpected error in position update loop: {ex}")

    def update_positions(self) -> None:
        """
        Update the motor's positions and notify observers.
        """
        for channel in self.channels:
            with self._lock:
                new_position = self.get_position(channel)
                self.axes_positions[channel].set(new_position)

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
    def move_relative(self, channel: int, steps: float) -> None:
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
            self.axes_positions[channel].set(channel, position)

    @property
    def AxesPositions(self) -> Dict[int, float]:
        """List of current axis positions in nanometers."""
        return {ch: self.axes_positions[ch].get() for ch in self.channels}

    @property
    def AxesPosUnits(self) -> Dict[int, str]:
        """List of position units for each axis."""
        return self._axes_pos_units

    def verify_channel(self, channel: int, verbose:bool = False) -> None:
        if channel not in self.channels:
            if verbose:
                print(f"channel {channel} is not supported. Expected values are {self.channels}")
            raise ValueError(f"channel {channel} is not supported. Expected values are {self.channels}")
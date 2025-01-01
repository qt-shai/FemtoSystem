import re
from enum import Enum
from typing import Dict, Callable, List

from Utils import SerialDevice

# ---------------------------------------------------------------------------
# Numeric constants for device constraints (not Enums)
# ---------------------------------------------------------------------------
MIN_FREQ = 0.0
MAX_FREQ = 403.0
MIN_PHASE = 0
MAX_PHASE = 16383
MIN_ATTENUATION = 0
MAX_ATTENUATION = 1023
MIN_REF_FREQ = 1.0
MAX_REF_FREQ = 25.0
MIN_DIRECT_FREQ = 250.0
MAX_DIRECT_FREQ = 1000.0

# ---------------------------------------------------------------------------
# Enums for device settings
# ---------------------------------------------------------------------------
class Channel(Enum):
    """Channel enumeration for data validation."""
    CH0 = 0
    CH1 = 1


class UpdateMode(Enum):
    """Enum for the 'I x' (update mode) command."""
    AUTOMATIC = "A"  # Immediate update
    MANUAL    = "M"  # Deferred updates
    PERFORM   = "P"  # Perform pending updates now


class ClockMode(Enum):
    """Enum for the clock source mode."""
    INTERNAL = "D"  # Internal 40MHz TCXO
    EXTERNAL = "E"  # External reference
    DIRECT   = "P"  # External direct

# ---------------------------------------------------------------------------
# NovatechDDS426A Wrapper with Observer Pattern
# ---------------------------------------------------------------------------
class NovatechDDS426A(SerialDevice):
    """
    A wrapper class for the Novatech 426A DDS device.
    Implements the observer pattern to notify external listeners on status changes.
    """

    def __init__(self,
                 address: str,
                 baudrate: int = 19200,
                 timeout: int = 1000,
                 simulation: bool = False):
        """
        Initialize the Novatech 426A DDS.

        :param address: The serial address, e.g., 'ASRL3::INSTR'.
        :param baudrate: Baud rate (default 19200).
        :param timeout: Communication timeout (ms). Default 1000 ms.
        :param simulation: Whether to operate in simulation mode.
        """
        super().__init__(address, baudrate=baudrate, timeout=timeout, simulation=simulation)
        self._status_observers: List[Callable[[Dict[str, str]], None]] = []

    # -----------------------------
    # Observer-related methods
    # -----------------------------
    def add_status_observer(self, observer: Callable[[Dict[str, str]], None]) -> None:
        """
        Add an observer that will be notified of status changes.

        :param observer: A callback taking a status dictionary.
        """
        self._status_observers.append(observer)

    def remove_status_observer(self, observer: Callable[[Dict[str, str]], None]) -> None:
        """
        Remove a status observer.

        :param observer: The callback to remove.
        """
        self._status_observers.remove(observer)

    def _notify_status_observers(self) -> None:
        """Query the device status and notify all observers."""
        status = self.query_status()
        for obs in self._status_observers:
            obs(status)

    # -----------------------------
    # Device commands
    # -----------------------------
    def set_frequency(self, channel: Channel, frequency_mhz: float) -> str:
        """
        Set the frequency of a given channel.

        :param channel: Channel.CH0 or Channel.CH1.
        :param frequency_mhz: Frequency in MHz, in [0..403].
        :return: Device response.
        """
        if not isinstance(channel, Channel):
            raise ValueError("Channel must be a Channel enum (CH0 or CH1).")
        if not (MIN_FREQ <= frequency_mhz <= MAX_FREQ):
            raise ValueError(f"Frequency must be in [{MIN_FREQ}, {MAX_FREQ}] MHz.")

        cmd = f"F{channel.value} {frequency_mhz:.9f}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_phase(self, channel: Channel, phase_value: int) -> str:
        """
        Set the phase of a given channel in [0..16383].

        :param channel: Channel.CH0 or Channel.CH1.
        :param phase_value: Phase in [0..16383].
        :return: Device response.
        """
        if not isinstance(channel, Channel):
            raise ValueError("Channel must be a Channel enum (CH0 or CH1).")
        if not (MIN_PHASE <= phase_value <= MAX_PHASE):
            raise ValueError(f"Phase must be in [{MIN_PHASE}, {MAX_PHASE}].")

        cmd = f"P{channel.value} {phase_value}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def synchronize_phase(self) -> str:
        """Synchronize the phase of both channels."""
        resp = self._send_command("PS", get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_update_mode(self, mode: UpdateMode) -> str:
        """
        Set the update mode:
         - AUTOMATIC (A)
         - MANUAL (M)
         - PERFORM (P)

        :param mode: An UpdateMode enum value.
        :return: Device response.
        """
        cmd = f"I {mode.value}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_amplitude(self, channel: Channel, attenuation_value: int) -> str:
        """
        Set amplitude attenuation for a channel in [0..1023].
        1023 = full scale, 0 = ~14 dBm attenuation.

        :param channel: Channel.CH0 or Channel.CH1.
        :param attenuation_value: 0..1023
        :return: Device response.
        """
        if not isinstance(channel, Channel):
            raise ValueError("Channel must be a Channel enum (CH0 or CH1).")
        if not (MIN_ATTENUATION <= attenuation_value <= MAX_ATTENUATION):
            raise ValueError(f"Attenuation must be in [{MIN_ATTENUATION}, {MAX_ATTENUATION}].")

        cmd = f"V{channel.value} {attenuation_value}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_reference_frequency(self, ref_freq_mhz: float) -> str:
        """
        Set the external reference frequency in [1..25] MHz (FR command).

        :param ref_freq_mhz: Reference frequency in MHz.
        :return: Device response.
        """
        if not (MIN_REF_FREQ <= ref_freq_mhz <= MAX_REF_FREQ):
            raise ValueError(f"Reference freq must be in [{MIN_REF_FREQ}, {MAX_REF_FREQ}] MHz.")
        cmd = f"FR {ref_freq_mhz:.3f}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_direct_frequency(self, direct_freq_mhz: float) -> str:
        """
        Set the external direct frequency in [250..1000] MHz (FD command).

        :param direct_freq_mhz: Frequency in MHz.
        :return: Device response.
        """
        if not (MIN_DIRECT_FREQ <= direct_freq_mhz <= MAX_DIRECT_FREQ):
            raise ValueError(f"Direct frequency must be in [{MIN_DIRECT_FREQ}, {MAX_DIRECT_FREQ}] MHz.")
        cmd = f"FD {direct_freq_mhz:.3f}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_clock_mode(self, mode: ClockMode) -> str:
        """
        Set the clock source mode:
         - INTERNAL = 'D'
         - EXTERNAL = 'E'
         - DIRECT   = 'P'

        :param mode: A ClockMode enum value.
        :return: Device response.
        """
        cmd = f"C {mode.value}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def set_echo(self, enable: bool) -> str:
        """Enable ('E') or disable ('D') serial echo."""
        cmd = f"E {'E' if enable else 'D'}"
        resp = self._send_command(cmd, get_response=True) or ""
        self._notify_status_observers()
        return resp

    def save_settings(self) -> str:
        """Save settings to non-volatile memory (S command)."""
        resp = self._send_command("S", get_response=True) or ""
        self._notify_status_observers()
        return resp

    def reset_device(self) -> str:
        """Reset the device (R command). Non-volatile data is preserved."""
        resp = self._send_command("R", get_response=True) or ""
        self._notify_status_observers()
        return resp

    def factory_reset(self) -> str:
        """Perform a factory reset (CLR command)."""
        resp = self._send_command("CLR", get_response=True) or ""
        self._notify_status_observers()
        return resp

    def query_status(self) -> Dict[str, str]:
        """
        Query the device status (Q command) and parse it into a dictionary.

        Example lines:
            F0 = 10.00000000000
            P0 = 0.00
            V0 = 1023
            ...
            FR: 10.000
            FD: 1000.000
            Clock mode: D
            Update mode: A
            PLL: Locked
            Firmware version: x.x
            OK
        """
        raw_resp = self._send_command("Q", get_response=True) or ""
        status_dict: Dict[str, str] = {}
        for line in raw_resp.splitlines():
            line = line.strip()
            if not line or line.lower() in ("q", "ok"):
                continue
            eq_match = re.match(r"^(\S+)\s*=\s*(.*)$", line)
            colon_match = re.match(r"^([^:]+):\s*(.*)$", line)
            if eq_match:
                key, val = eq_match.groups()
                status_dict[key.strip()] = val.strip()
            elif colon_match:
                key, val = colon_match.groups()
                status_dict[key.strip()] = val.strip()
        return status_dict
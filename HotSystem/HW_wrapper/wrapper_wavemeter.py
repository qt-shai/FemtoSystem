"""
Thread-safe HighFinesse Wavemeter wrapper with automatic background polling.

Key features
------------
* Inherits: class:`Utils.periodic_updater.PeriodicUpdateMixin`
  for robust, reusable update handling.
* Exposes: attr:`frequency` as an:class:`ObservableField` so that GUIs
  (or any other component) can subscribe without polling.
* Works in simulation mode if no hardware is present.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Final, Optional, Deque

import numpy as np
from pylablib.devices.HighFinesse import wlm

from Utils import ObservableField, PeriodicUpdateMixin

_logger: Final = logging.getLogger(__name__)


class HighFinesseWLM(PeriodicUpdateMixin):  # pylint: disable=too-many-public-methods
    """
    High-level wrapper for a HighFinesse wavemeter.

    Parameters
    ----------
    index:
        Device index (driver-specific, usually 0).
    simulation:
        If True, no hardware calls are made; random data are generated.
    polling_rate:
        Hz; how often:pyattr:`frequency` updates are pushed.

    Notes
    -----
    * On: meth:`connect`, background updates start automatically;
      they stop on: meth:`close`.
    * All hardware accesses are guarded by: pyattr:`lock`.
    """

    _SIM_FREQ_CENTER_HZ: Final[float] = 4.77e14
    _SIM_FREQ_SPAN_HZ: Final[float] = 1.0e9

    def __init__(
        self,
        index: int = 0,
        *,
        simulation: bool = False,
        polling_rate: float | None = None,
        max_points: int = 10_000) -> None:
        if index < 0:
            raise ValueError("index must be non-negative")
        super().__init__(polling_rate=polling_rate)
        self.index: int = index
        self.simulation: bool = simulation

        self.lock: threading.Lock = threading.Lock()
        self._device: Optional[wlm.WLM] = None

        # Observable output
        self.frequency: ObservableField[float] = ObservableField(0.0)

        # Raw logs for optional later export
        self.freq_history: Deque[float] = deque(maxlen=max_points)
        self.time_history: Deque[float] = deque(maxlen=max_points)

    # ------------------------------------------------------------------
    # Context-manager sugar
    # ------------------------------------------------------------------
    def __enter__(self) -> "HighFinesseWLM":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:  # noqa: D401
        self.close()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def connect(self, *, simulation_fallback: bool = True) -> None:
        """Open the driver and start periodic updates."""
        if self.simulation:
            _logger.info("[SIM] Wavemeter index %d connected", self.index)
            # self.start_updates()
            return

        if self._device and self._device.is_opened():
            _logger.debug("Already connected")
            return

        for attempt in (1, 2):  # 1 try + 1 retry
            try:
                # DLL call – may raise HighFinesseError
                self._device = wlm.WLM()
                # self.start_updates()
                return
            except Exception as exc:  # pylint: disable=broad-except
                if attempt == 2 or not simulation_fallback:
                    _logger.exception("Failed to open wavemeter: %s", exc)
                    raise
                # first attempt failed → wait and retry
                time.sleep(2.0)

            # If still here we fell through two failures
        if simulation_fallback:
            self.simulation = True
            # self.start_updates()

        _logger.info("Connected to HighFinesse WLM (index=%d)", self.index)
        # self.start_updates()

    def close(self) -> None:
        """Stop updates and release the driver."""
        self.stop_updates()
        if self.simulation:
            _logger.info("[SIM] Wavemeter disconnected")
            return

        if self._device:
            try:
                self._device.close()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                _logger.warning("Error while closing WLM: %s", exc)

        self._device = None
        _logger.info("HighFinesse WLM closed")

    # ------------------------------------------------------------------
    # Low-level getters/setters (wrapped for thread-safety)
    # ------------------------------------------------------------------
    def get_wavelength(self, channel: int = 0) -> float | None:
        """Return wavelength [m]; ``None`` if unavailable."""
        if self.simulation:
            return self._simulated_wavelength()
        if not self._device:
            return None
        with self.lock:
            return self._device.get_wavelength()

    def get_frequency(self, channel: int = 0) -> float | None:
        """Return frequency [Hz]; ``None`` if unavailable."""
        if self.simulation:
            return self._simulated_frequency()
        if not self._device:
            return None
        with self.lock:
            return self._device.get_frequency()

    def set_exposure(self, exposure_ms: int, channel: int = 0) -> None:
        """
        Set CCD/diode exposure.

        Raises
        ------
        ValueError
            If *exposure_ms* is out of the 1–60000 ms safe range.
        """
        if not 1 <= exposure_ms <= 60_000:
            raise ValueError("exposure_ms must be 1–60000 ms")

        if self.simulation or not self._device:
            _logger.debug("[SIM] set_exposure=%d", exposure_ms)
            return

        with self.lock:
            self._device.set_exposure(exp_time=exposure_ms)

    # ------------------------------------------------------------------
    # PeriodicUpdateMixin hook
    # ------------------------------------------------------------------
    def _poll(self) -> None:
        """Sample frequency and notify observers (called by background thread)."""
        freq = self.get_frequency()
        if freq is None:
            raise RuntimeError("Frequency read returned None")

        timestamp = time.time()
        with self.lock:
            self.frequency.set(freq)
            self.freq_history.append(freq)
            self.time_history.append(timestamp)

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _simulated_frequency(self) -> float:
        """Return a pseudo-random frequency for simulation."""
        return self._SIM_FREQ_CENTER_HZ + np.random.uniform(
            -self._SIM_FREQ_SPAN_HZ, self._SIM_FREQ_SPAN_HZ
        )

    def _simulated_wavelength(self) -> float:
        """Convert the simulated frequency to wavelength [m]."""
        c = 299_792_458.0  # m / s
        return c / self._simulated_frequency()

    # ------------------------------------------------------------------
    # Properties for quick checks
    # ------------------------------------------------------------------
    @property
    def is_connected(self) -> bool:
        """``True`` if the hardware link is active (always ``True`` in simulation)."""
        if self.simulation:
            return True
        return bool(self._device and self._device.is_opened())

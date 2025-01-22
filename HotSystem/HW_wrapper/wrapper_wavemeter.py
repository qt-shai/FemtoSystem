from typing import Optional

import numpy as np
from pylablib.devices.HighFinesse import wlm


class HighFinesseWLM:
    """
    Wrapper class for HighFinesse WLM (wavemeter) control, using pylablib's WLM class.
    """

    def __init__(self, index: int = 0, simulation: bool = False):
        """
        Initialize the HighFinesse WLM device.

        :param index: The device index of the WLM (defaults to 0).
        :param simulation: If True, no real hardware access is performed.
        """
        self.index = index
        self.simulation = simulation
        self.dev: Optional[wlm.WLM] = None

    def __del__(self):
        """
        Ensure that the device is closed when the object is deleted.
        """
        self.close()

    @property
    def is_connected(self) -> bool:
        """
        Check if the WLM device is connected.

        :return: True if the device is connected, False otherwise.
        """
        if self.simulation:
            return True
        return self.dev is not None

    def connect(self):
        """
        Connect to the HighFinesse WLM device.
        """
        if self.simulation:
            print(f"[Simulation] Pretending to connect to HighFinesse WLM (index={self.index})")
            return
        try:
            self.dev = wlm.WLM()
            print(f"Connected to HighFinesse WLM with index {self.index}")
        except Exception as e:
            print(f"Failed to connect to HighFinesse WLM: {e}")
            self.dev = None

    def close(self):
        """
        Close the connection to the WLM device.
        """
        if self.simulation:
            print("[Simulation] Pretending to close HighFinesse WLM connection.")
            return
        if self.dev is not None:
            self.dev.close()
            print("Connection to HighFinesse WLM closed.")
            self.dev = None

    def get_id(self) -> Optional[str]:
        """
        Get the WLM device ID/string information.

        :return: The device info string or None if simulation/not connected.
        """
        if self.simulation or self.dev is None:
            return None
        return self.dev.get_info_str()

    def get_wavelength(self, channel: int = 0) -> Optional[float]:
        """
        Read the current wavelength from the WLM.

        :param channel: The channel index (if the WLM has multiple channels).
        :return: The current wavelength in nm, or None if simulation/not connected.
        """
        if self.simulation or self.dev is None:
            return None
        return self.dev.get_wavelength()

    def get_frequency(self, channel: int = 0) -> Optional[float]:
        """
        Read the current wavelength from the WLM.

        :param channel: The channel index (if the WLM has multiple channels).
        :return: The current wavelength in nm, or None if simulation/not connected.
        """
        if self.simulation or self.dev is None:
            return np.random.uniform(10,1000)
        return self.dev.get_frequency()

    def set_exposure(self, exposure_time: int, channel: int = 0):
        """
        Set the exposure time for a given channel on the WLM.

        :param exposure_time: The desired exposure time (in some device-specific units, e.g. ms).
        :param channel: The channel index.
        """
        if self.simulation or self.dev is None:
            return
        self.dev.set_exposure( exp_time=exposure_time)

    def get_exposure(self, channel: int = 0) -> Optional[int]:
        """
        Get the current exposure time for a given channel on the WLM.

        :param channel: The channel index.
        :return: The current exposure time, or None if simulation/not connected.
        """
        if self.simulation or self.dev is None:
            return None
        return self.dev.get_exposure()

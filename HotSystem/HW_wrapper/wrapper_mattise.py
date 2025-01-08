from typing import Optional

from pylablib.devices import Sirah


class SirahMatisse:
    """
    Wrapper class for Sirah Matisse laser control, using pylablib's SirahMatisse class.
    """
    def __init__(self, addr, use_mc_server="auto", simulation:bool = False):
        """
        Initialize the Sirah Matisse laser.

        :param addr: The address of the device (e.g., VISA address).
        :param use_mc_server: Whether to use the Matisse Commander server for communication.
        """
        self.addr = addr
        self.use_mc_server = use_mc_server
        self.dev: Optional[Sirah.Matisse.SirahMatisse] = None
        self.simulation = simulation

    def __del__(self):
        self.close()

    @property
    def is_connected(self) -> bool:
        """
        Check if the device is connected.

        This property performs an actual check to see if the resource manager and
        the serial connection are initialized and active.

        :return: True if the device is connected, False otherwise.
        """
        if self.simulation:
            return True

        return self.get_id() is not None

    def connect(self):
        """
        Connect to the Sirah Matisse laser.
        """
        if self.simulation:
            return
        try:
            self.dev = Sirah.Matisse.SirahMatisse(self.addr, use_mc_server=self.use_mc_server)
            self.get_id()
            print(f"Connected to Sirah Matisse at {self.addr}")
        except Exception as e:
            print(f"Failed to connect to Sirah Matisse: {e}")

    def get_id(self):
        """
        Get the device ID.
        """
        if self.simulation:
            return
        return self.dev.get_id()

    def set_diode_power_lowlevel(self, cutoff):
        """
        Set the low-level cutoff current laser resonator power.
        """
        if self.simulation:
            return
        self.dev.set_diode_power_lowlevel(cutoff)
        return self.dev.get_diode_power_lowlevel()

    def get_diode_power_lowlevel(self):
        """
        Get the low-level cutoff current laser resonator power.
        """
        if self.simulation:
            return
        return self.dev.get_diode_power_lowlevel()

    def get_diode_power(self):
        """
        Get the current laser resonator power.
        """
        if self.simulation:
            return
        return self.dev.get_diode_power()

    def thin_etalon_move_to(self, position, wait=True, wait_timeout=30.):
        """
        Move the thin etalon to the specified position.
        """
        if self.simulation:
            return
        self.dev.thinet_move_to(position, wait, wait_timeout)

    def thin_etalon_stop(self):
        """
        Stop the thin etalon motor.
        """
        if self.simulation:
            return
        self.dev.thinet_stop()

    def thin_etalon_home(self, wait=True, wait_timeout=30.):
        """
        Home the thin etalon motor.
        """
        if self.simulation:
            return
        self.dev.thinet_home(wait, wait_timeout)

    def get_thin_ehalon_position(self):
        """
        Get the current position of the thin etalon motor.
        """
        if self.simulation:
            return
        return self.dev.thinet_get_position()

    def set_thin_etalon_ctl_status(self, status="run"):
        """
        Set thin etalon lock status ("run" or "stop").
        """
        if self.simulation:
            return
        self.dev.set_thinet_ctl_status(status)
        return self.dev.get_thinet_ctl_status()

    def get_thin_ehalon_ctl_status(self):
        """
        Get thin etalon lock status ("run" or "stop").
        """
        if self.simulation:
            return
        return self.dev.get_thinet_ctl_status()

    def bifi_move_to(self, position, wait=True, wait_timeout=30.):
        """
        Move the birefringent filter to the specified position.
        """
        if self.simulation:
            return
        self.dev.bifi_move_to(position, wait, wait_timeout)

    def bifi_stop(self):
        """
        Stop the birefringent filter motor.
        """
        if self.simulation:
            return
        self.dev.bifi_stop()

    def bifi_home(self, wait=True, wait_timeout=30.):
        """
        Home the birefringent filter motor.
        """
        if self.simulation:
            return
        self.dev.bifi_home(wait, wait_timeout)

    def get_bifi_position(self):
        """
        Get the current position of the birefringent filter motor.
        """
        if self.simulation:
            return
        return self.dev.bifi_get_position()

    def set_slowpiezo_position(self, value):
        """
        Set slow piezo DC position.
        """
        if self.simulation:
            return
        self.dev.set_slowpiezo_position(value)
        return self.dev.get_slowpiezo_position()

    def get_slowpiezo_position(self):
        """
        Get slow piezo DC position.
        """
        if self.simulation:
            return
        return self.dev.get_slowpiezo_position()

    def set_fastpiezo_position(self, value):
        """
        Set fast piezo DC position between 0 and 1.
        """
        if self.simulation:
            return
        self.dev.set_fastpiezo_position(value)
        return self.dev.get_fastpiezo_position()

    def get_fastpiezo_position(self):
        """
        Get fast piezo DC position between 0 and 1.
        """
        if self.simulation:
            return
        return self.dev.get_fastpiezo_position()

    def set_fastpiezo_ctl_status(self, status="run"):
        """
        Set fast piezo lock status ("run" or "stop").
        """
        if self.simulation:
            return
        self.dev.set_fastpiezo_ctl_status(status)
        return self.dev.get_fastpiezo_ctl_status()

    def get_fastpiezo_ctl_status(self):
        """
        Get fast piezo lock status ("run" or "stop").
        """
        if self.simulation:
            return
        return self.dev.get_fastpiezo_ctl_status()

    def set_scan_status(self, status="run"):
        """
        Set scan status ("run" or "stop").
        """
        if self.simulation:
            return
        self.dev.set_scan_status(status)
        return self.dev.get_scan_status()

    def get_scan_status(self):
        """
        Get scan status ("run" or "stop").
        """
        if self.simulation:
            return
        return self.dev.get_scan_status()

    def wait_scan(self, timeout=None):
        """
        Wait until scan is stopped.
        """
        if self.simulation:
            return
        self.dev.wait_scan(timeout)

    def set_scan_position(self, value):
        """
        Set scan position.
        """
        if self.simulation:
            return
        self.dev.set_scan_position(value)
        return self.dev.get_scan_position()

    def get_scan_position(self):
        """
        Get scan position.
        """
        if self.simulation:
            return
        return self.dev.get_scan_position()

    def get_refcell_position(self) -> float:
        """
        Get reference cell DC position between 0 and 1.
        """
        return self.dev.get_refcell_position()

    def set_refcell_position(self, value: float) -> float:
        """
        Set reference cell DC position between 0 and 1.

        :param value: The value to set the reference cell position to (between 0 and 1).
        :return: The updated reference cell position.
        """
        return self.dev.set_refcell_position(value)

    def set_slowpiezo_ctl_status(self, status="run"):
        """
        Set slow piezo lock status ("run" or "stop").
        """
        if self.simulation:
            return
        self.dev.set_slowpiezo_ctl_status(status)
        return self.dev.get_slowpiezo_ctl_status()

    def get_slowpiezo_ctl_status(self):
        """
        Get slow piezo lock status ("run" or "stop").
        """
        if self.simulation:
            return
        return self.dev.get_slowpiezo_ctl_status()

    def close(self):
        """
        Close the connection to the device.
        """
        if self.simulation:
            return
        self.dev.close()
        print("Connection to Sirah Matisse closed.")

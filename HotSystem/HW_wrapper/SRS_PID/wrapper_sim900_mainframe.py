from Utils import SerialDevice

class SRSsim900(SerialDevice):
    """
    A wrapper class for the SRS SIM900 mainframe.
    Includes multiplexer/preamp/voltmeter controls as shown in the example code.
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: int = 1000):
        """
        Initialize the SIM900 mainframe connection.

        :param port: The COM port or device path.
        :param baudrate: Baud rate for serial communication.
        :param timeout: Read/write timeout in milliseconds.
        """
        super().__init__(port, baudrate=baudrate, timeout=timeout)

    def initialize(self) -> None:
        """
        Initialize the device by flushing buffers.
        """
        self.flush_output()  # FLSH

    def ping(self, restart: bool = False) -> str:
        """
        Check whether device responds. Optionally attempt a restart on failure.

        :param restart: If True, send SRST upon failure and retry once.
        :return: Success string or raises IOError if all attempts fail.
        """
        if restart:
            self._connection.write("quit")
            self._connection.write("SRST")
        try:
            data = self._connection.query("ECHO? 'HELLO'")
            if data.strip() == "HELLO":
                return "Ping successful."
            else:
                if not restart:
                    return self.ping(restart=True)
                raise IOError("Confusing device communication.")
        except:
            if not restart:
                return self.ping(restart=True)
            raise IOError("Echo test failed.")

    def flush_output(self) -> None:
        """
        Flush the output buffers (FLSH).
        """
        self._connection.write("FLSH")

    def reset(self) -> None:
        """
        Reset the device with *RST.
        """
        self._connection.write("*RST")

    # -----------------------------
    # Multiplexer Controls (Port 8)
    # -----------------------------

    def set_channel(self, channel: int) -> None:
        """
        Select channel on multiplexer (1-8), 0 = not connected.

        :param channel: The channel number (1..8), or 0 to disconnect.
        """
        self._connection.write(f"SNDT 8,'CHAN {channel}'")

    def get_channel(self) -> int:
        """
        Get the currently selected multiplexer channel.

        :return: The integer channel number (0..8).
        """
        self._connection.write("CONN 8,'quit'")
        val = self._connection.query("CHAN?")
        self._connection.write("quit")
        return int(val)

    def write(self, command: str) -> None:
        """
        Expose writing capabilities to other SIM900 series wrappers

        :param command: The command to write.
        """
        self._connection.write(command)

    def query(self, command: str) -> str:
        """
        Expose query capabilities to other SIM900 series wrappers

        :param command: The command to query.
        """
        return self._connection.query(command)

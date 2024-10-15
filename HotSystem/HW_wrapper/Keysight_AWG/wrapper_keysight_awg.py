from Utils import SerialDevice
import time


class Keysight33500B(SerialDevice):
    """
    Wrapper class for Keysight 33500B waveform generator.

    Inherits from SerialDevice to handle serial communication.
    """

    def __init__(self, address: str, baudrate: int = 9600, timeout: int = 1000, simulation: bool = False):
        """
        Initialize the Keysight 33500B device.

        :param address: The address of the device (e.g., 'ASRL3::INSTR' or USB address).
        :param baudrate: Baud rate for serial communication (default is 9600).
        :param timeout: Timeout for communication in milliseconds (default is 1000 ms).
        :param simulation: If True, operate in simulation mode (default is False).
        """
        super().__init__(address, baudrate, timeout, simulation)

    def connect(self):
        """
        Connect to the Keysight 33500B device.
        Sends *IDN? command to check device identity and ensure the connection is valid.
        """
        super().connect()
        # Verify connection with *IDN? query
        identity = self.query("*IDN?")
        if "33500B" not in identity:
            raise Exception("Failed to connect to Keysight 33500B. Device ID not recognized.")
        print("Connected to Keysight 33500B")

    def set_waveform_type(self, waveform_type: str, channel: int = 1):
        """
        Set the waveform type for a specific channel.

        :param waveform_type: The desired waveform type.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        valid_waveforms = ["SINE", "SQUARE", "TRIANGLE", "RAMP", "NOISE"]
        if waveform_type not in valid_waveforms:
            raise ValueError(f"Invalid waveform type: {waveform_type}. Must be one of {valid_waveforms}")
        command = f"FUNC{channel} {waveform_type}"
        self._send_command(command)
        time.sleep(0.1)

    def set_frequency(self, frequency: float, channel: int = 1):
        """
        Set the frequency for a specific channel.

        :param frequency: The desired frequency in Hz.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        if not 20 <= frequency <= 20e6:
            raise ValueError("Frequency must be between 20 Hz and 20 MHz.")
        command = f"FREQ{channel} {frequency}"
        self._send_command(command)
        time.sleep(0.1)

    def set_amplitude(self, amplitude: float, channel: int = 1):
        """
        Set the amplitude for a specific channel.

        :param amplitude: The desired amplitude in Vpp.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        if not 0.01 <= amplitude <= 10:
            raise ValueError("Amplitude must be between 0.01 Vpp and 10 Vpp.")
        command = f"VOLT{channel} {amplitude}"
        self._send_command(command)
        time.sleep(0.1)

    def set_offset(self, offset: float, channel: int = 1):
        """
        Set the DC offset for a specific channel.

        :param offset: The desired offset in volts.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        if not -5 <= offset <= 5:
            raise ValueError("Offset must be between -5V and 5V.")
        command = f"VOLT{channel}:OFFS {offset}"
        self._send_command(command)
        time.sleep(0.1)

    def set_duty_cycle(self, duty_cycle: float, channel: int = 1):
        """
        Set the duty cycle for a specific channel using square wave.

        :param duty_cycle: The desired duty cycle in percentage.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        if not 0 <= duty_cycle <= 100:
            raise ValueError("Duty cycle must be between 0% and 100%.")
        command = f"FUNC{channel}:SQUARE:DCYC {duty_cycle}"
        self._send_command(command)
        time.sleep(0.1)

    def set_phase(self, phase: float, channel: int = 1):
        """
        Set the phase for a specific channel.

        :param phase: The desired phase in degrees.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        if not 0 <= phase <= 360:
            raise ValueError("Phase must be between 0 and 360 degrees.")
        command = f"PHAS{channel} {phase}"
        self._send_command(command)
        time.sleep(0.1)

    def set_output_state(self, state: bool, channel: int = 1):
        """
        Set the output state (ON or OFF) for a specific channel.

        :param state: True to turn ON the output, False to turn it OFF.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")
        command = f"OUTP{channel} ON" if state else f"OUTP{channel} OFF"
        self._send_command(command)
        time.sleep(0.1)

    def set_external_trigger(self):
        """
        Set the AWG to wait for an external trigger.
        """
        self._send_command("TRIG:SOUR EXT")  # Set the trigger source to external
        self._send_command("TRIG:DEL MIN")  # Minimize the trigger delay

    def write_arbitrary_waveform(self, points: list, channel: int = 1):
        """
        Write arbitrary waveform to AWG for the specified channel using a list of points.

        :param points: List of voltage points defining the waveform.
        :param channel: The channel to configure (1 or 2).
        """
        if channel not in [1, 2]:
            raise ValueError("Channel must be 1 or 2.")

        waveform_name = f"ARBITRARY_WAVE_{channel}"
        self._send_command(f"DATA:VOL:CLEAR")  # Clear the previous waveform
        self._send_command(f"DATA:ARB{channel} {waveform_name}, " + ",".join(map(str, points)))
        self._send_command(f"FUNC{channel}:ARB {waveform_name}")  # Use the arbitrary waveform for the specified channel
        self._send_command(f"FUNC{channel} ARB")

    def set_external_trigger_advance(self, rep_rate: float):
        """
        Set the mode where an external trigger starts the entire sequence with the given repetition rate.

        :param rep_rate: Repetition rate for the sequence in Hz.
        """
        self.set_external_trigger()
        self._send_command(f"TRIG:SEQ:PER {1 / rep_rate}")
        self._send_command("TRIG:SEQ ON")

    def set_triggered_point_mode(self):
        """
        Set mode where each external trigger moves to the next point in the waveform vector.
        """
        self.set_external_trigger()
        self._send_command("TRIG:SEQ ADVANCE")  # Set to advance one step per trigger

    def set_triggered_waveform_mode(self, waveform: str):
        """
        Set mode where an external trigger outputs one waveform from a dictionary of waveforms.

        :param waveform: The waveform name (e.g., 'TRIANGLE') to output on trigger.
        """
        self.set_external_trigger()
        self._send_command(f"FUNC {waveform}")  # Set the waveform to output
        self._send_command("TRIG:MODE SINGLE")  # Single output per trigger

    def set_internal_trigger(self):
        """
        Set the AWG to use the internal trigger source.
        """
        self._send_command("TRIG:SOUR INT")  # Set trigger source to internal

    def set_external_trigger_once(self, rep_rate: float):
        """
        Set the AWG to wait for an external trigger and output the waveform once at a given repetition rate.

        :param rep_rate: Repetition rate for the external trigger.
        """
        self._send_command("TRIG:SOUR EXT")  # Set trigger source to external
        self._send_command(f"TRIG:PER {1 / rep_rate}")  # Set repetition rate
        self._send_command("TRIG:MODE NORM")  # Normal (once) trigger mode

    def query(self, command: str) -> str:
        """
        Sends a query command to the device and returns the response.

        :param command: The SCPI command to send (e.g., '*IDN?').
        :return: The response from the device as a string.
        """
        return self._send_command(command)

    def disconnect(self):
        """
        Disconnect from the device and release the serial connection.
        """
        super().disconnect()

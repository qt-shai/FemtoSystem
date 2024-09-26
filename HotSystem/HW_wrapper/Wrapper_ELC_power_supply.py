# from ECM import *
import pyvisa
import sys


class ALR3206T:
    def __init__(self, dev_address: str = "ASRL3::INSTR", simulation: bool = False):
        """
        Initialize the ALR3206T power supply.

        :param dev_address: The VISA address of the device.
        """
        self.instrument_address = dev_address
        self.rm = pyvisa.ResourceManager()
        self.scaling = 1000  # We want to use Volts, instrument use mV
        #  Read current values into self fields
        self.number_channels = 3
        self.current_setpoint: list[float]
        self.voltage_setpoint: list[float]
        self.OVP_setpoint: list[float]
        self.OCP_setpoint: list[float]
        self.output_state: list[bool]
        self.simulation = simulation
        self.number_channels = 3
        self.device = None

        try:
            if not self.simulation:
                self.device = self.rm.open_resource(self.instrument_address, open_timeout=1000)
                self.device.read_termination = '\r'
                #  Read current values into self fields

                self.current_setpoint: list[float] = [self.get_current(q) for q in range(1, self.number_channels+1)]
                self.voltage_setpoint: list[float] = [self.get_voltage(q) for q in range(1, self.number_channels+1)]
                self.OVP_setpoint: list[float] = [self.get_ovp(q) for q in range(1, self.number_channels+1)]
                self.OCP_setpoint: list[float] = [self.get_ocp(q) for q in range(1, self.number_channels+1)]
                self.output_state: list[bool] = [self.get_output_state(q) for q in range(1, self.number_channels+1)]

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            self.device = None

    def _send_command(self, parameter: str, command: str, value: str = "") -> str:
        """
        Send a command to the power supply.

        :param parameter: The parameter to set or get (e.g., "VOLT1", "CURR1").
        :param command: The command type ("WR" for write, "RD" for read).
        :param value: The value to set (only for write commands).
        :return: The response from the power supply.
        """
        address = "0"  # USB port address
        space = " "  # ASCII space character
        # carriage_return = chr(0x0D)  # ASCII carriage return
        if value:
            command_string = f"{address}{space}{parameter}{space}{command}{space}{value}"
        else:
            command_string = f"{address}{space}{parameter}{space}{command}"
        if self.device:

            self.device.write(command_string)
            response = self.device.read()
            return response
        else:
            return self.error

    def set_current(self, channel: int, current: float) -> str:
        """
        Set the current for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :param current: The current value to set (in amperes).
        :return: The response from the power supply.
        """
        parameter = f"CURR{channel}"
        command = "WR"
        value = current*self.scaling
        self.current_setpoint[channel] = value
        return self._send_command(parameter, command, str(value))

    def get_current(self, channel: int) -> float:
        """
        Get the current for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The current value (in amperes).
        """
        parameter = f"CURR{channel}"
        command = "RD"
        response = self._send_command(parameter, command)
        return float(response.split(" ")[-1]) / self.scaling

    def set_voltage(self, channel: int, voltage: float) -> str:
        """
        Set the voltage for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :param voltage: The voltage value to set (in volts).
        :return: The response from the power supply.
        """
        parameter = f"VOLT{channel}"
        command = "WR"
        value = voltage*self.scaling
        self.voltage_setpoint[channel] = value
        return self._send_command(parameter, command, str(value))

    def get_voltage(self, channel: int) -> float:
        """
        Get the voltage for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The voltage value (in volts).
        """
        parameter = f"VOLT{channel}"
        command = "RD"
        response = self._send_command(parameter, command)
        return float(response.split(" ")[-1]) / self.scaling

    def get_output_state(self, channel: int) -> bool:
        """
        Turn on the output for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The response from the power supply.
        """
        parameter = f"OUT{channel}"
        command = "RD"
        value = ""
        response = self._send_command(parameter, command, value)
        self.output_state[channel] = bool(response.split(" ")[-1])
        return self.output_state[channel]

    def output_on(self, channel: int) -> str:
        """
        Turn on the output for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The response from the power supply.
        """
        parameter = f"OUT{channel}"
        command = "WR"
        value = "1"
        return self._send_command(parameter, command, value)

    def output_off(self, channel: int) -> str:
        """
        Turn off the output for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The response from the power supply.
        """
        parameter = f"OUT{channel}"
        command = "WR"
        value = "0"
        return self._send_command(parameter, command, value)

    def identify(self) -> str:
        """
        Identify the power supply.

        :return: The identification string of the power supply.
        """
        parameter = "IDN"
        command = "RD"
        return self._send_command(parameter, command)

    def get_serial(self) -> str:
        """
        Read the serial of the power supply.

        :return: The serial of the power supply.
        """
        parameter = "SERIAL"
        command = "RD"
        return self._send_command(parameter, command)

    def set_ocp(self, channel: int, current: float) -> str:
        """
        Set the overcurrent protection (OCP) for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :param current: The OCP current value to set (in amperes).
        :return: The response from the power supply.
        """
        parameter = f"OCP{channel}"
        command = "WR"
        value = str(current*self.scaling)
        return self._send_command(parameter, command, value)

    def get_ocp(self, channel: int) -> float:
        """
        Get the overcurrent protection (OCP) for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The OCP current value (in amperes).
        """
        parameter = f"OCP{channel}"
        command = "RD"
        response = self._send_command(parameter, command)
        value = float(response.split(" ")[-1]) / self.scaling
        self.OCP_setpoint[channel] = value
        return value

    def set_ovp(self, channel: int, voltage: float) -> str:
        """
        Set the overvoltage protection (OVP) for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :param voltage: The OVP voltage value to set (in volts).
        :return: The response from the power supply.
        """
        parameter = f"OVP{channel}"
        command = "WR"
        value = str(voltage*self.scaling)
        return self._send_command(parameter, command, value)

    def get_ovp(self, channel: int) -> float:
        """
        Get the overvoltage protection (OVP) for a specific channel.

        :param channel: The channel number (1, 2, or 3).
        :return: The OVP voltage value (in volts).
        """
        parameter = f"OVP{channel}"
        command = "RD"
        response = self._send_command(parameter, command)
        value = float(response.split(" ")[-1]) / self.scaling
        self.OVP_setpoint[channel] = value
        return value

    def close(self) -> None:
        """
        Close the connection to the power supply.

        :return: None
        """
        if self.device:
            self.device.close()

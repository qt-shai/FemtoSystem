import serial
from serial.tools import list_ports
from serial import SerialException
import time
import sys
import logging
import threading


from Utils import SerialDevice

logger = logging.getLogger(__name__)

class CoboltLaser:
    """Creates a laser object using either COM-port or serial number to connect to laser. \n Will automatically return proper subclass, if applicable"""

    def __init__(self, port=None, serialnumber=None, baudrate=115200, simulation : bool = False):
        self.lock = threading.Lock()
        self.simulation = simulation
        self.serialnumber = serialnumber
        self.port = port
        self.modelnumber = None
        self.baudrate = baudrate
        self.address = None
        self.isConnected=False
        if not self.simulation:
            self.connect()
            self.modulation_power_setpoint = 0.0

    def __del__(self):
        self.disconnect()

    def __str__(self):
        try:
            return f'Serial number: {self.serialnumber}, Model number: {self.modelnumber}, Wavelength: {"{:.0f}".format(float(self.modelnumber[0:4]))} nm, Type: {self.__class__.__name__}'
        except:
            return (
                f"Serial number: {self.serialnumber}, Model number: {self.modelnumber}"
            )

    def connect(self):
        """Connects the laser on using a specified COM-port (preferred) or serial number. Will throw exception if it cannot connect to specified port or find laser with given serial number.

        Raises:
            SerialException: serial port error
            RuntimeError: no laser found
        """

        if self.simulation:
            self.isConnected=False
            return

        if self.port != None:
            try:
                port = self.port if "COM" in self.port else f"COM{self.port}"
                self.address = serial.Serial(port, self.baudrate, timeout=100)
            except Exception as err:
                self.address = None
                raise SerialException(f"{self.port} not accesible.") from err

        elif self.serialnumber != None:
            ports = list_ports.comports()
            for port in ports:
                try:
                    self.address = serial.Serial(
                        port.device, baudrate=self.baudrate, timeout=1
                    )
                    sn = self.send_cmd("sn?")
                    self.address.close()
                    if sn == self.serialnumber:
                        self.port = port.device
                        self.address = serial.Serial(self.port, baudrate=self.baudrate)
                        break
                except:
                    pass
            if self.port == None:
                raise RuntimeError("No laser found")
        if self.address != None:
            self._identify_()
        if self.__class__ == CoboltLaser:
            self._classify_()
        self.isConnected=True

    def _identify_(self):
        """Fetch Serial number and model number of laser. Will raise exception and close connection if not connected to a cobolt laser.

        Raises:
            RuntimeError: error identifying the laser model
        """
        try:
            firmware = self.send_cmd("gfv?")
            if "ERROR" in firmware:
                self.disconnect()
                raise RuntimeError("Not a Cobolt laser")
            self.serialnumber = self.send_cmd("sn?")
            if not "." in firmware:
                if "0" in self.serialnumber:
                    self.modelnumber = (
                        f"0{self.serialnumber.partition(str(0))[0]}-04-XX-XXXX-XXX"
                    )
                    self.serialnumber = self.serialnumber.partition("0")[2]
                    while self.serialnumber[0] == "0":
                        self.serialnumber = self.serialnumber[1:]
            else:
                self.modelnumber = self.send_cmd("glm?")
        except:
            self.disconnect()
            raise RuntimeError("Not a Cobolt laser")

    def _classify_(self):
        """Classifies the laser into probler subclass depending on laser type"""
        try:
            if not "-71-" in self.modelnumber:
                if "-06-" in self.modelnumber:
                    if (
                        "-91-" in self.modelnumber[0:4]
                        or "-93-" in self.modelnumber[0:4]
                    ):
                        self.__class__ = Cobolt06DPL
                    elif "1100" in self.modelnumber:
                        self.__class__ = Cobolt06MLD12V
                        self.__init__()
                    else:
                        self.__class__ = Cobolt06MLD
                        self.__init__()
        except:
            pass

    def is_connected(self):
        """Ask if laser is connected"""
        try:
            if self.address.is_open:
                try:
                    test = self.send_cmd("?")
                    if test == "OK":
                        return True
                    else:
                        return False
                except:
                    return False
            else:
                return False
        except:
            return False

    def disconnect(self):
        """Disconnect the laser"""
        if self.address != None:
            self.address.close()
            self.serialnumber = None
            self.modelnumber = None

    def turn_on(self):
        """Turn on the laser with the autostart sequence.The laser will await the TEC setpoints and pass a warm-up state"""
        logger.info("Turning on laser")
        return self.send_cmd(f"@cob1")

    def turn_off(self):
        """Turn off the laser"""
        logger.info("Turning off laser")
        return self.send_cmd(f"l0")

    def is_on(self):
        """Ask if laser is turned on"""
        answer = self.send_cmd(f"l?")
        if answer == "1":
            return True
        else:
            return False

    def interlock(self):
        """Returns: 0 if closed, 1 if open"""
        return self.send_cmd(f"ilk?")

    def get_fault(self):
        """Get laser fault"""
        faults = {
            "0": "0 - No errors",
            "1": "1 - Temperature error",
            "3": "3 - Interlock error",
            "4": "4 - Constant power time out",
        }
        fault = self.send_cmd("f?")
        return faults.get(fault, fault)

    def clear_fault(self):
        """Clear laser fault"""
        return self.send_cmd("cf")

    def get_mode(self):
        """Get operating mode"""
        modes = {
            "0": "0 - Constant Current",
            "1": "1 - Constant Power",
            "2": "2 - Modulation Mode",
        }
        mode = self.send_cmd("gam?")
        return modes.get(mode, mode)

    def get_state(self):
        """Get autostart state"""
        states = {
            "0": "0 - Off",
            "1": "1 - Waiting for key",
            "2": "2 - Continuous",
            "3": "3 - On/Off Modulation",
            "4": "4 - Modulation",
            "5": "5 - Fault",
            "6": "6 - Aborted",
        }
        state = self.send_cmd("gom?")
        return states.get(state, state)
    
    def constant_current(self, current=None):
        """Enter constant current mode, current in mA"""
        if current != None:
            if not "-08-" in self.modelnumber or not "-06-" in self.modelnumber:
                self.send_cmd(f"slc {current/1000}")
            else:
                self.send_cmd(f"slc {current}")
            logger.info(f"Entering constant current mode with I = {current} mA")
        else:
            logger.info("Entering constant current mode")
        return self.send_cmd(f"ci")

    def set_current(self, current):
        """Set laser current in mA"""
        logger.info(f"Setting I = {current} mA")
        if not "-08-" in self.modelnumber or not "-06-" in self.modelnumber:
            current = current / 1000
        return self.send_cmd(f"slc {current}") 

    def get_current(self):
        """Get laser current in mA"""
        self.actual_current = float(self.send_cmd(f"i?"))
        return self.actual_current

    def get_current_setpoint(self):
        """Get laser current setpoint in mA"""
        return float(self.send_cmd(f"glc?"))

    def constant_power(self, power=None):
        """Enter constant power mode, power in mW"""
        if power != None:
            self.send_cmd(f"p {float(power)/1000}")
            logger.info(f"Entering constant power mode with P = {power} mW")
        else:
            logger.info("Entering constant power mode")
        return self.send_cmd(f"cp")

    def set_power(self, power):
        """Set laser power in mW"""
        logger.info(f"Setting P = {power} mW")
        return self.send_cmd(f"p {float(power)/1000}")

    def get_power(self):
        self.get_current()
        """Get laser power in mW"""
        self.actual_power = float(self.send_cmd(f"pa?")) * 1000
        return self.actual_power

    def get_power_setpoint(self):
        """Get laser power setpoint in mW"""
        self.constant_power_setpoint = float(self.send_cmd(f"p?")) * 1000
        return self.constant_power_setpoint

    def get_ophours(self):
        """Get laser operational hours"""
        return self.send_cmd(f"hrs?")

    def _timeDiff_(self, time_start):
        """time in ms"""
        time_diff = time.perf_counter() - time_start
        return time_diff
    
    def get_TEC_temperature(self):
        return self.send_cmd("rtect?")
    
    def get_Base_temperature(self):
        return self.send_cmd("rbpt?")

    def send_cmd(self, message, timeout=1):
        """Sends a message to the laset and awaits response until timeout (in s).

        Returns:
            The response recieved from the laser as string

        Raises:
            RuntimeError: sending the message failed
        """
        time_start = time.perf_counter()
        message += "\r"
        try:
            self.lock.acquire()
            utf8_msg = message.encode()
            self.address.write(utf8_msg)
            logger.debug(f"sent laser [{self}] message [{utf8_msg}]")
        except Exception as e:
            self.lock.release()
            raise RuntimeError("Error: write failed") from e

        time_stamp = 0
        while time_stamp < timeout:

            try:
                received_string = self.address.readline().decode()
                time_stamp = self._timeDiff_(time_start)
            except:
                self.lock.release()
                time_stamp = self._timeDiff_(time_start)
                continue

            if len(received_string) > 1:
                while (received_string[-1] == "\n") or (received_string[-1] == "\r"):
                    received_string = received_string[0:-1]
                    if len(received_string) < 1:
                        break

                logger.debug(
                    f"received from laser [{self}] message [{received_string}]"
                )
                self.lock.release()
                return received_string.splitlines()[0]

        self.lock.release()
        raise RuntimeError("Syntax Error: No response")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.turn_off()
        self.disconnect()

    def analog_power_modulation(self):
        pass

    def digital_power_modulation(self):
        pass

    def on_off_modulation(self, enable):
        pass

class Cobolt06MLD(CoboltLaser):
    """For lasers of type 06-MLD"""

    def __init__(self, simulation : bool = False, port=None,serialnumber=None):
        # super().__init__(simulation=simulation, port=port,serialnumber=serialnumber)
        self.max_current = 227  # mA
        self.max_power = 85  # mW
        self.simulation = simulation

    def constant_current(self, current=None):
        self.analog_modulation(0)
        self.digital_modulation(0)
        return super().constant_current(current)
    
    def constant_power(self, power=None):
        self.analog_modulation(0)
        self.digital_modulation(0)
        return super().constant_power(power)
    
    def digital_power_modulation(self):
        self.modulation_mode()
        self.analog_modulation(0)
        self.digital_modulation(1)
    
    def analog_power_modulation(self):
        self.modulation_mode()
        self.digital_modulation(0)
        self.analog_modulation(1)

    def modulation_mode(self, power=None):
        """Enter modulation mode.

        Args:
            power: modulation power (mW)
        """
        logger.info(f"Entering modulation mode")
        if power != None:
            self.send_cmd(f"slmp {power}")
        return self.send_cmd("em")

    def digital_modulation(self, enable):
        """Enable digital modulation mode by enable=1, turn off by enable=0"""
        return self.send_cmd(f"sdmes {enable}")

    def analog_modulation(self, enable):
        """Enable analog modulation mode by enable=1, turn off by enable=0"""
        return self.send_cmd(f"sames {enable}")

    def on_off_modulation(self, enable):
        """Enable On/Off modulation mode by enable=1, turn off by enable=0"""
        if enable == 1:
            return self.send_cmd("eoom")
        elif enable == 0:
            return self.send_cmd("xoom")

    def get_modulation_state(self):
        """Get the laser modulation settings as [analog, digital]"""
        dm = self.send_cmd("gdmes?")
        am = self.send_cmd("games?")
        return [am, dm]

    def set_modulation_power(self, power):
        """Set the modulation power in mW"""
        logger.info(f"Setting modulation power = {power} mW")
        return self.send_cmd(f"slmp {power}")

    def get_power(self):
        super().get_power()
        self.get_modulation_power()

    def get_modulation_power(self):
        """Get the modulation power setpoint in mW"""
        self.modulation_power_setpoint = float(self.send_cmd("glmp?"))
        return self.modulation_power_setpoint

    def set_analog_impedance(self, arg):
        """Set the impedance of the analog modulation.

        Args:
            arg: 0 for HighZ, 1 for 50 Ohm.
        """
        return self.send_cmd(f"salis {arg}")

    def get_analog_impedance(self):
        """Get the impedance of the analog modulation \n
        return: 0 for HighZ and 1 for 50 Ohm"""
        return self.send_cmd("galis?")    
    
class Cobolt06DPL(CoboltLaser):
    """For lasers of type 06-DPL"""

    def __init__(self, port=None, serialnumber=None):
        super().__init__(port, serialnumber)

    def modulation_mode(self, highI=None):
        """Enter Modulation mode, with possibiity to set the modulation high current level in mA (**kwarg)"""
        if highI != None:
            self.send_cmd(f"smc {highI}")
        return self.send_cmd("em")

    def digital_modulation(self, enable):
        """Enable digital modulation mode by enable=1, turn off by enable=0"""
        return self.send_cmd(f"sdmes {enable}")

    def analog_modulation(self, enable):
        """Enable analog modulation mode by enable=1, turn off by enable=0"""
        return self.send_cmd(f"sames {enable}")

    def get_modulation_state(self):
        """Get the laser modulation settings as [analog, digital]"""
        dm = self.send_cmd("gdmes?")
        am = self.send_cmd("games?")
        return [am, dm]

    def set_modulation_current_high(self, highI):
        """Set the modulation high current in mA"""
        return self.send_cmd(f"smc {highI}")

    def set_modulation_current_low(self, lowI):
        """Set the modulation low current in mA"""
        return self.send_cmd(f"slth {lowI}")

    def get_modulation_current(self):
        """Return the modulation currrent setpoints in mA as [highCurrent,lowCurrent]"""
        highI = float(self.send_cmd("gmc?"))
        lowI = float(self.send_cmd("glth?"))
        return [highI, lowI]

    def get_modulation_tec(self):
        """Read the temperature of the modulation TEC in °C"""
        return float(self.send_cmd("rtec4t?"))

    def set_modulation_tec(self, temperature):
        """Set the temperature of the modulation TEC in °C"""
        return self.send_cmd(f"stec4t {temperature}")

    def get_modualtion_tec_setpoint(self):
        """Get the setpoint of the modulation TEC in °C"""
        return float(self.send_cmd("gtec4t?"))

class Cobolt06MLD12V(CoboltLaser):
    def __init__(self, port=None, serialnumber=None, TEC_idx = [1]):
        # super().__init__(port, serialnumber)
        self.TEC_idx = TEC_idx
        self.TEC_enabled = []
        self.TEC_setPoint = []
        self.TEC_temperature = []
        self.get_laser_info()

    # compatible with MLD06
    def get_mode(self):
        return self.get_run_mode()

    def get_modulation_state(self):
        """Get the laser modulation settings as [analog, digital]"""
        dm = self.send_cmd("gdmes?")
        am = self.send_cmd("games?")
        return [am, dm]
    
    def set_modulation_power(self, power):
        self.digital_power_modulation()
        self.set_power(power)
        
    def get_modulation_power(self):
        self.get_power()
        return self.modulation_power_setpoint
    
    def set_analog_impedance(self, arg):
        pass
    def get_analog_impedance(self):
        pass

    # system commands:
    def get_laser_info(self):
        self.identifier = self.send_cmd('*IDN?')
        self.modelnumber = self.send_cmd('SYSTem:MODel:NUMber?')
        self.serialnumber = self.send_cmd('SYSTem:SERial:NUMber?')
        self.operation_hours = self.send_cmd('LASer:HOURs?')
        self.aytustart_state = self.send_cmd('AUTOstart:ENAbled?') # 0: disable, 1: enable
        self.key_state = self.send_cmd('KEYswitch:ENAbled?') # 0: disable, 1: enable
        self.key_position = self.send_cmd('KEYswitch?') # 0: off, 1: on
        self.remote_state = self.send_cmd('REMote:ENAbled?') # set/return 0: disable, 1: enable
        self.remove_voltage = self.send_cmd('REMote?') # 0: No input signal. 1: 5V is present
        self.interlock_state = self.send_cmd('INTerlock?') # 0: open, 1:closed
        for i in range(len(self.TEC_idx)):
            self.TEC_enabled.append(self.send_cmd(f'TEC{self.TEC_idx[i]}:ENAbled?')) # 0: disable, 1: enable
            self.TEC_setPoint.append(self.send_cmd(f'TEC{self.TEC_idx[i]}:TEMPerature:SETPoint?')) # float [C]
            self.TEC_temperature.append(self.send_cmd(f'TEC{self.TEC_idx[i]}:TEMPerature?')) # float [C]
        self.get_start_state()
        self.ANALOG_impedance = self.send_cmd('SYSTem:INPut:ANAlog:IMPedance?') # set/return system impedance for analog input high: 1k ohm, low: 50 ohm
        self.ANALOG_range = self.send_cmd('SYSTem:INPut:ANAlog:VOLTage:RANGe:MAX?') # set/return 0: 0 to 1V, 5: 0 to 5V
        self.ANALOG_applied_volatge = self.send_cmd('SYSTem:INPut:ANAlog:VOLTage:READing?')
        self.fault_string = self.send_cmd('FAULt?')
        self.fault_state = self.send_cmd('FAULt:STATe?') # 0: no fault, 1: fault present
    def get_start_state(self):
        self.start_sequence_state = self.send_cmd('STATe?')
    def set_clear_fault(self):
        self.send_cmd('FAULt:CLEar') # clear faults and restart laser
    def get_TEC_temperature(self):
        self.TEC_temperature = []
        for i in range(len(self.TEC_idx)):
            self.TEC_temperature.append(self.send_cmd(f'TEC{self.TEC_idx[i]}:TEMPerature?')) # float [C]

    # Emission control and laser status
    def restart(self):
        '''
        Restarts the autostart program, through waiting for TECs,
        warmup and to the completed state.
        '''
        self.send_cmd('AUTOstart:RESTart') # clear faults and restart laser
    def abort(self):
        '''
        Aborts the autostart sequence. Stops all function including
        laser drive current and temperature controls.
        '''
        self.send_cmd('AUTOstart:ABORt')
    def start(self):
        '''
        Starts the autostart sequence and results in laser emission
        once the ‘Laser ON’ state is reached, regardless of the
        autostart enabled state.
        '''
        self.send_cmd('STARt')
    def stop(self):
        '''
        Stops the laser emission and will set the laser in the ‘Standby’
        state
        '''
        self.send_cmd('STOP')
    def pause(self, val = 'none'):
        '''
        Pause and resume emission without changing the state or
        operating mode of the laser, no external signal required.
        0 : Resume emission
        1 : Pause emission
        '''
        if val == 'none':
            return self.send_cmd('LASer:PAUSed?')
        else:
            self.send_cmd(f'LASer:PAUSed {str(val)}')
    def pause_emission(self, val = 'none'):
        '''
        Pause and resume emission without changing the state or
        operating mode of the laser, no external signal required.
        0 : Resume emission
        1 : Pause emission
        '''
        self.pause(val=1)
    def resume_emission(self):
        '''
        Pause and resume emission without changing the state or
        operating mode of the laser, no external signal required.
        0 : Resume emission
        1 : Pause emission
        '''
        self.pause(val=0)
    def set_get_run_mode(self,val='none'):
        '''
        Sets / returns the run mode for the laser.
        options:
        'ConstantCurrent'
        'ConstantPower'
        'PowerModulation'
        'CurrentModulation'
        '''
        if val=='none':
            return self.send_cmd('LASer:RUNMode?')
        else:
            self.send_cmd(f'LASer:RUNMode {val}')
    def digital_power_modulation(self):
        self.set_get_run_mode(val='PowerModulation')
        self.set_digitalTrig_modulation(1)
        self.set_analogTrig_modulation(0)
    def analog_power_modulation(self):
        self.set_get_run_mode(val='PowerModulation')
        self.set_digitalTrig_modulation(0)
        self.set_analogTrig_modulation(1)

    def set_current_modulation_mode(self):
        self.set_get_run_mode(val='CurrentModulation')
    def constant_power(self):
        self.set_get_run_mode(val='ConstantPower')
    def constant_current(self):
        self.set_get_run_mode(val='ConstantCurrent')
    def get_run_mode(self):
        return self.set_get_run_mode()
    
    def get_max_current(self):
        '''
        Returns the factory set maximum current setpoint allowed for
        the laser.
        '''
        self.max_current = float(self.send_cmd('LASer:CURRent:SETPoint:MAX?'))
    
    def get_max_power(self):
        '''
        Returns the factory set maximum power setpoint allowed for
        the laser.
        '''        
        self.max_power = float(self.send_cmd('LASer:POWer:SETPoint:MAX?'))
    
    def get_power(self):
        '''
        Returns the actual laser power. For MLDs this value is
        calibrated to a look up table of corresponding current settings,
        and for DPLs it is calibrated to the measured photodiode
        voltage in constant power mode.
        '''
        self.actual_power = float(self.send_cmd('LASer:POWer?'))

        '''
        Returns the measured current delivered to the laser diode.
        '''
        self.actual_current = float(self.send_cmd('LASer:CURRent?'))

        self.get_max_current()
        self.get_max_power()

        '''
        Returns the factory set nominal laser power.
        '''
        self.power_nominal_setpoint = float(self.send_cmd('LASer:POWer:SETPoint:NOMInal?'))

        # reads power setpoints
        self.constant_power_setpoint = float(self.send_cmd(f'LASer:ConstantPower:POWer:SETPoint?'))
        self.modulation_power_setpoint = float(self.send_cmd(f'LASer:PowerModulation:POWer:SETPoint?'))
        self.constant_current_setpoint = float(self.send_cmd(f'LASer:ConstantCurrent:CURRent:SETPoint?'))
        self.modulation_current_setpoint = float(self.send_cmd(f'LASer:CurrentModulation:CURRent:HIGH:SETPoint?'))
    # Constant power mode
    def set_power(self, val):
        '''
        Sets / Returns the constant current mode set point. The input
        range is limited at the factory.
        '''
        self.send_cmd(f'LASer:ConstantPower:POWer:SETPoint {val}')
        self.send_cmd(f'LASer:PowerModulation:POWer:SETPoint {val}')
    # Constant current mode
    def set_current(self, val):
        '''
        Sets / Returns the desired constant current mode set point.
        The input range is limited at the factory to prevent damage to
        the laser and/or limit the power for laser safety reasons.
        '''
        self.send_cmd(f'LASer:ConstantCurrent:CURRent:SETPoint {val}')
        self.send_cmd(f'LASer:CurrentModulation:CURRent:HIGH:SETPoint {val}')
    def set_digitalTrig_modulation(self,val):
        '''
        Sets the digital power modulation enabled state. If
        enabled, the laser will require a high signal on the appropriate
        input to emit
        '''
        self.send_cmd(f'LASer:PowerModulation:DIGital:ENAbled {val}')
        '''
        Sets the digital power modulation enabled state. If
        enabled, the laser will require a high signal on the appropriate
        input to emit
        '''
        self.send_cmd(f'LASer:CurrentModulation:DIGital:ENAbled {val}')

    def set_analogTrig_modulation(self, val):
        '''
        Sets the analog power modulation enabled state. If
        enabled, the laser will require a high signal on the appropriate
        input to emit
        '''
        self.send_cmd(f'LASer:PowerModulation:ANAlog:ENAbled {val}')

        '''
        Sets the analog power modulation enabled state. If
        enabled, the laser will require a high signal on the appropriate
        input to emit
        '''
        self.send_cmd(f'LASer:CurrentModulation:ANAlog:ENAbled {val}')

def list_lasers():
    """Return a list of laser objects for all cobolt lasers connected to the computer"""
    lasers = []
    ports = list_ports.comports()
    for port in ports:
        try:
            laser = CoboltLaser(port=port.device)
            if laser.serialnumber == None or laser.serialnumber.startswith("Syntax"):
                del laser
            else:
                lasers.append(laser)
        except:
            pass
    return lasers


import pyvisa
import time
import threading

class ThorlabsCLD1011LP:
    def __init__(self,simulation=False):#, resource_name: str):
        """
        Initialize the Thorlabs CLD1011LP laser diode driver.
        
        Parameters:
        resource_name (str): VISA resource string (e.g., 'USB0::0x1313::0x80C8::M00352057::INSTR')
        """
        self.rm = pyvisa.ResourceManager()
        avDevices = self.rm.list_resources()
        self.device = self.rm.open_resource(avDevices[0])
        self.device.timeout = 5000  # Set timeout to 5 seconds
        self.endC = '\n'
        self.lock = threading.Lock()
        self.maxI = 250.0 #mA
        self.minI = 0.0 # mA
        self.disable_modulation()
        self.get_device_info()

    def write_cmd(self,cmd):
        self.lock.acquire()
        res = self.device.write(cmd)
        time.sleep(0.1)
        if isinstance(res, str):
            res = res.replace(self.endC, "")
        self.lock.release()
        return res

    def query_cmd(self,cmd):
        self.lock.acquire()
        res = self.device.query(cmd)
        time.sleep(0.1)
        if isinstance(res, str):
            res = res.replace(self.endC, "")
        self.lock.release()
        return res

    def enable_modulation(self):
        self.write_cmd('SOURce:AM 1')
        self.modulation_mod = 'enabled'
    
    def disable_modulation(self):
        self.write_cmd('SOURce:AM 0')
        self.modulation_mod = 'disabled'

    def get_device_info(self):
        """Retrieve the device information"""
        self.info = self.query_cmd('*IDN?')
        return self.info

    def get_mode(self):
        self.mode = self.query_cmd('SOURce1:FUNCtion:MODE?')

    def set_current_mode(self):
        self.disable_laser()
        self.write_cmd('SOURce1:FUNCtion:MODE CURRent')

    def set_power_mode(self):
        self.disable_laser()
        self.write_cmd('SOURce1:FUNCtion:MODE POWer')

    def set_current(self, current_ma: float):
        """
        Set the current to the laser diode.

        Parameters:
        current_ma (float): Current to set in milliamps (mA)
        """
        if self.minI < current_ma*1e-3 < self.maxI:
            self.write_cmd(f'SOURce1:CURRent:LEVel {current_ma*1e-3}')
        else:
            print(f"set_current: {current_ma*1e-3: .3f} is out of range")
    
    def get_key_state(self):
        res = self.query_cmd('OUTP:PROT:KEYL:TRIP?')
        if res == '1':
            self.key = 'Key lock'
        else:
            self.key = 'Key unlock'

    def get_lasing_state(self):
        res = self.query_cmd('OUTPut?')
        if res == '1':
            self.lasing_state = 'Laser is ON'
        else:
            self.lasing_state = 'Laser is OFF'
    
    def get_tec_state(self):
        res = self.query_cmd('OUTPut2?')
        if res == '1':
            self.tec_state = 'TEC is ON'
        else:
            self.tec_state = 'TEC is OFF'

    def get_current(self):
        """Get the current output from the driver"""
        self.current = self.query_cmd('SOURce1:CURRent:LEVel?')
    
    def set_power(self,pwr):
        self.write_cmd(f'SOURce1:POWer:LEVel {pwr*1e-3}')

    def get_power(self):
        self.power = self.query_cmd('SOURce1:POWer:LEVel?')
    
    def get_info(self):
        self.actual_temp = self.query_cmd('MEAS:TEMPerature?')
        self.actual_current = self.query_cmd('MEAS:CURRent?')
        self.actual_voltage = self.query_cmd('MEAS:VOLTage?')
        self.actual_power = self.query_cmd('MEAS:POWer?')
        self.get_key_state()
        self.get_lasing_state()
        self.get_tec_state()
        self.get_mode()

    def enable_tec(self):
        self.write_cmd('OUTPut2 1')

    def disable_tec(self):
        self.write_cmd('OUTPut2 0')

    def enable_laser(self):
        """Enable the laser diode output"""
        self.write_cmd('OUTPut 1')
        self.enable_tec()

    def disable_laser(self):
        """Disable the laser diode output"""
        self.write_cmd('OUTPut 0')

    def set_ext_modulation(self):
        pass

    def set_int_modulation(self):
        pass

    def close(self):
        """Close the connection to the laser driver"""
        self.device.close()

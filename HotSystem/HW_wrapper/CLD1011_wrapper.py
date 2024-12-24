import pyvisa
import time
import threading

class ThorlabsCLD1011LP:
    def __init__(self):#, resource_name: str):
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
        self.disable_modulation()

    def enable_modulation(self):
        self.device.write('SOURce:AM 1')
        self.modulation_mod = 'enabled'
    
    def disable_modulation(self):
        self.device.write('SOURce:AM 0')
        self.modulation_mod = 'disabled'

    def get_device_info(self):
        """Retrieve the device information"""
        return self.device.query('*IDN?')

    def get_mode(self):
        self.mode = self.device.query('SOURce1:FUNCtion:MODE?')

    def set_current_mode(self):
        self.disable_laser()
        self.device.write('SOURce1:FUNCtion:MODE CURRent')

    def set_power_mode(self):
        self.disable_laser()
        self.device.write('SOURce1:FUNCtion:MODE POWer')

    def set_current(self, current_ma: float):
        """
        Set the current to the laser diode.

        Parameters:
        current_ma (float): Current to set in milliamps (mA)
        """
        self.device.write(f'SOURce1:CURRent:LEVel {current_ma*1e-3}')
    
    def get_key_state(self):
        res = self.device.query('OUTP:PROT:KEYL:TRIP?')
        res = res.replace(self.endC, "")
        if res == '1':
            self.key = 'Key lock'
        else:
            self.key = 'Key unlock'

    def get_current(self):
        """Get the current output from the driver"""
        self.current = self.device.query('SOURce1:CURRent:LEVel?')
    
    def set_power(self,pwr):
        self.device.write(f'SOURce1:POWer:LEVel {pwr*1e-3}')

    def get_power(self):
        self.power = self.device.query('SOURce1:POWer:LEVel?')
    
    def get_info(self):
        self.actual_temp = self.device.query('MEAS:TEMPerature?')
        self.actual_current = self.device.query('MEAS:CURRent?')
        self.actual_voltage = self.device.query('MEAS:VOLTage?')
        self.actual_power = self.device.query('MEAS:POWer?')
        self.get_key_state()

    def enable_tec(self):
        self.device.write('OUTPut2 1')

    def disable_tec(self):
        self.device.write('OUTPut2 0')

    def enable_laser(self):
        """Enable the laser diode output"""
        self.device.write('OUTPut 1')
        self.enable_tec()

    def disable_laser(self):
        """Disable the laser diode output"""
        self.device.write('OUTPut 0')

    def close(self):
        """Close the connection to the laser driver"""
        self.device.close()

# Usage Example
if __name__ == '__main__':
    # Replace with your actual resource name (VISA string)
    # resource_name = 'USB0::0x1313::0x80C8::M00352057::INSTR'

    # Create an instance of the driver
    driver = ThorlabsCLD1011LP()#resource_name)
    
    # Get device info
    print("Device Info:", driver.get_device_info())

    driver.get_key_state()

    # Set current to 100 mA (0.1 A)
    driver.set_current(0.050)

    # Enable laser
    driver.enable_laser()
    time.sleep(5)  # Laser on for 5 seconds

    # Disable laser
    driver.disable_laser()

    # Close the connection
    driver.close()

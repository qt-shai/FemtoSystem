import inspect
import sys

import pyvisa


class RS_SGS100a():
    def __init__(self, dev_address = 'TCPIP0::192.168.0.0::inst0::INSTR', simulation: bool = False):  #todo replace with search for device IP and address
        self.instrument_address = dev_address
        self.rm = pyvisa.ResourceManager()
        self.simulation = simulation

        if not self.simulation:
            try:
                self.device = self.rm.open_resource(self.instrument_address, open_timeout=1000) #timeout in milliseconds
            except Exception as ex:
                self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
                self.device = None
                self.ID = "none"
                self.freq = 0 # GHz
                self.power = 0 # dBm
                self.RFstate = False
                self.PulseModulationState = False
                self.IQ_State = False
                self.PulseModulationSource = "none"

                # raise
                print(self.error)
            if not(self.device == None):
                self.Get_deviceID()
                self.Read_State()

    def __del__(self):
        self.Disconnect()

    def Get_deviceID(self):
        success, self.ID = self.Command_query('*IDN?') # RF on
        if not(success):
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get IDN")
        else:
            print("Connected to:", self.ID) # todo: write to log   
    def Resetting_Device(self):
        if not(self.Command_write('*RST')): # resetting the instrument
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get IDN")
    def Set_freq(self,freq = 2.87): # GHz
        if not(self.Command_write(':SOUR:FREQ:CW '+str(freq)+' GHz')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting frequency")
            pass
    def Read_freq(self): # GHz
        if not(self.device == None):
            success, freq = self.Command_query(':SOUR:FREQ:CW?') # RF on
            self.freq = float(freq.strip())/1e9
            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get frequency")
                pass
    def Set_power(self,power = -10): # dBm
        if not(self.Command_write(':SOUR:POW:POW '+str(power)+' dBm')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting power")
            pass
    def Read_power(self): # dBm
        if not(self.device == None):
            success, power = self.Command_query(':SOUR:POW:POW?') # RF on
            self.power = float(power.strip())
            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get power")
                pass
    def Turn_RF_ON(self): # 
        if not(self.Command_write(':OUTP:STAT 1')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting RF ON")
            pass
    def Turn_RF_OFF(self): # 
        if not(self.Command_write(':OUTP:STAT 0')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting RF OFF")
            pass
    def Get_RF_state(self): # 
        if not(self.device == None):
            success, RFstate = self.Command_query(':OUTP:STAT?') # RF on
            self.RFstate = bool(int(RFstate.strip()))

            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get RF state")
                pass                    

    def Set_PulseModulation_InternalSource(self): # digital trigger
        if not(self.Command_write('SOUR:PULM:SOUR INT')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting PulseModulation to Internal")
            pass    
    def Set_PulseModulation_ExternalSource(self): # digital trigger
        if not(self.device == None):
            if not(self.Command_write('SOUR:PULM:SOUR EXT')): # set frequency
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting PulseModulation to External")
                pass
    def Set_PulseModulation_ON(self): # digital trigger
        if not(self.Command_write('SOUR:PULM:STAT ON')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting PulseModulation ON")
            pass
    def Set_PulseModulation_OFF(self): # digital trigger 
        if not(self.Command_write('SOUR:PULM:STAT OFF')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting PulseModulation OFF")
            pass
    def Get_PulseModulation_state(self): # GHz
        if not(self.device == None):
            success, PulseModulationState = self.Command_query('SOUR:PULM:STAT?') # RF on
            self.PulseModulationState = bool(int(PulseModulationState.strip()))
            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get PulseModulation state")
                pass
    def Get_PulseModulation_Source(self): # GHz
        if not(self.device == None):
            success, PulseModulationSource = self.Command_query('SOUR:PULM:SOUR?') # RF on
            self.PulseModulationSource = PulseModulationSource.strip() 
            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get PulseModulation source")
                pass

    def Set_IQ_mode_ON(self): # digital trigger
        if not(self.Command_write('SOUR:IQ:STAT ON')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting IQ mode ON")
            pass
    def Set_IQ_mode_OFF(self): # digital trigger 
        if not(self.Command_write('SOUR:IQ:STAT OFF')): # set frequency
            # todo: add error handling
            print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error setting IQ mode OFF")
            pass
    def Get_IQ_mode_state(self): # GHz
        if not(self.device == None):
            success, IQ_State = self.Command_query('SOUR:IQ:STAT?') # RF on
            self.IQ_State = bool(int(IQ_State.strip()))
            if not(success):
                # todo: add error handling
                print(self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name + ":error get IQ mode state")
                pass
    
    def Read_State(self):
        if not(self.device == None):
            self.Get_RF_state()
            self.Get_PulseModulation_Source()
            self.Get_PulseModulation_state()
            self.Get_IQ_mode_state()

            self.Read_freq()
            self.Read_power()
            pass

    def Disconnect(self):
        self.device.close()
        self.rm.close()
        self.device = None
        self.rm = None

    def Command_query(self, command_str):
        res = self.device.query(command_str)
        return self.device.query('*OPC?'), res
    def Command_write(self, command_str): # from qudi
        res = self.device.write(command_str)
        # self.device.write('*WAI')
        # while int(float(self.device.query('*OPC?'))) != 1:
        #     time.sleep(0.2)
        return self.device.query('*OPC?')

    def SetFreq(self,freq = 2.87):
        self.freq = freq
        # add R&S command

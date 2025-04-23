#from ECM import *
from ImGuiwrappedMethods import *
from Common import *
from HW_wrapper import HW_devices as hw_devices

class GUI_RS_SGS100a(): #todo: support several devices
    def __init__(self, simulation:bool = False):
        self.window_tag:str = ""
        self.simulation = simulation
        if not simulation:
            self.HW = hw_devices.HW_devices()
            self.dev = self.HW.microwave
            self.dev_ip = self.dev.instrument_address
            self.dev.Set_PulseModulation_ExternalSource()
            self.devID = self.dev.ID
            self.freq = self.dev.freq # GHz
            self.power = self.dev.power # dBm
            self.RFstate = self.dev.RFstate
            self.DigitalState = self.dev.PulseModulationState
            self.IQstate = self.dev.IQ_State
            self.DigitalSource = self.dev.PulseModulationSource

    def controls(self):
        if self.simulation:
            return
        imgui.begin("Rohde Schwarz SGS100A",True,imgui.WINDOW_NO_TITLE_BAR or imgui.WINDOW_NO_COLLAPSE) # open new window

        guiID = Common_Counter_Singletone()
        guiString = self.__class__.__name__+ "_" +inspect.currentframe().f_code.co_name 

        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored(self.dev.ID,1,1,1,0.5)
        imgui.pop_id()

        imgui.begin_child("RF ON/OFF", 380, 40, True)
        # set Rf ON/OFF
        if self.RFstate:
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            imgui.text_colored("RF module is turned ON",1,1,0,1)
            imgui.pop_id()

            imgui.same_line()
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            if imgui.button("Turn OFF"):
                self.dev.Turn_RF_OFF()
            imgui.pop_id()
        else:
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            imgui.text_colored("RF module is turned OFF",1,1,1,1)
            imgui.pop_id()

            imgui.same_line()
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            if imgui.button("Turn ON"):
                self.dev.Turn_RF_ON()
            imgui.pop_id()
        
        self.dev.Get_RF_state()
        self.RFstate = self.dev.RFstate

        imgui.end_child()

        imgui.same_line()
        imgui.begin_child("Power and Freq", 420, 40, True)
        imgui.same_line()
        # set frequency
        changed, self.freq = inputDouble(self.freq, "freq", "GHz", guiString, 1, 0.7, 0.7, 1, 130, True,'%.12f')
        HelpHovered("Set Rohde Schwarz frequency in GHz")
        if(changed):
            self.dev.Set_freq(self.freq)
        else:
            self.dev.Read_freq()
            self.freq = self.dev.freq

        imgui.same_line()
        # set power
        changed, self.power = inputDouble(self.power, "power", "dBm", guiString, 1, 0.7, 0.7, 1, 70, False,'%.2f')
        HelpHovered("Set Rohde Schwarz power in dBm")
        if(changed):
            self.dev.Set_power(self.power)
        else:
            self.dev.Read_power()
            self.power = self.dev.power

        imgui.end_child()

        imgui.same_line()
        imgui.begin_child("I/Q and Digital", 350, 40, True)

        imgui.same_line()
        # set IQ mode
        clicked, state, self.IQstate = checkbox(self.IQstate,"IQ state",guiString, 1, 1, 1, 1)
        HelpHovered("Enable or Disable IQ modulation (Mod On/Off)")
        if clicked:
            if (self.IQstate):
                self.dev.Set_IQ_mode_ON()
            else:
                self.dev.Set_IQ_mode_OFF()

        self.dev.Get_IQ_mode_state()
        self.IQstate = self.dev.IQ_State

        imgui.same_line()
        # set Digital
        clicked, state, self.DigitalState = checkbox(self.DigitalState,"Digital state",guiString, 1, 1, 1, 1)
        HelpHovered("Enable or Disable digital trigger (Pulse modulation state)")
        if clicked:
            if (self.DigitalState):
                self.dev.Set_PulseModulation_ON()
            else:
                self.dev.Set_PulseModulation_OFF()
            
        self.dev.Get_PulseModulation_state()
        self.DigitalState = self.dev.PulseModulationState

        imgui.end_child()


        #  *************
        imgui.same_line()
        imgui.begin_child("Source", 350, 40, True)

        imgui.same_line()
        # read signal source (ext/int)
        self.dev.Get_PulseModulation_Source()
        self.DigitalSource = self.dev.PulseModulationSource
        guiID.Step_up()
        imgui.push_id(guiString + str(guiID.counter))
        imgui.text_colored("Trigger source: " + self.DigitalSource,1,1,0,1)
        imgui.pop_id()

        imgui.same_line()
        # set EXT/INT
        if self.DigitalSource == 'EXT':
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            if imgui.button("Set Internal"):
                self.dev.Set_PulseModulation_InternalSource()
            imgui.pop_id()
        else:
            guiID.Step_up()
            imgui.push_id(guiString + str(guiID.counter))
            if imgui.button("Set External"):
                self.dev.Set_PulseModulation_ExternalSource()
            imgui.pop_id()

        self.dev.Get_PulseModulation_state()
        self.DigitalState = self.dev.PulseModulationState
        imgui.end_child()
        # *****************************



        imgui.end()

        pass

    pass

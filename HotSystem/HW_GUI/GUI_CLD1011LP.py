import dearpygui.dearpygui as dpg
import HW_wrapper
import serial.tools.list_ports
from Common import DpgThemes
import HW_wrapper.Wrapper_Cobolt
import HW_wrapper.Wrapper_CLD1011
from HW_wrapper.HW_devices import HW_devices


class GUI_CLD1011LP():  # todo1: support several devices
    # init parameters
    def __init__(self, simulation: bool = False):
        self.HW = HW_devices(simulation=simulation)
        self.window_tag = "CLD1011LP_Win"
        self.laser = self.HW.CLD1011LP

        # Define GUI themes
        themes = DpgThemes()
        yellow_theme = themes.color_theme((55, 55, 0), (255, 255, 255))
        win_theme = themes.color_theme([0, 25, 25, 255], (255, 255, 255))
        green_theme = themes.color_theme([0, 55, 0, 255], (255, 255, 255))

        # Define the layout of the GUI
        Child_Width = 200

        dpg.add_window(tag=self.window_tag, label=""+ self.laser.info, no_title_bar=False, height=440, width=1600, collapsed=True)
        
        # groups
        dpg.add_group(tag="Laser_sections", horizontal=True, parent=self.window_tag)
        dpg.add_group(tag="control", horizontal=False, parent="Laser_sections")
        dpg.add_group(tag="info", horizontal=False, parent="Laser_sections")
        dpg.add_group(tag="parameters", horizontal=False, parent="Laser_sections")
        
        

        # btns
        dpg.add_button(parent="control",tag="btn_turn_on_off_laser",label="laser on",callback=self.turn_on_off_laser)
        dpg.add_button(parent="control",tag="btn_turn_on_off_tec",label="tec on",callback=self.turn_on_off_tec)
        dpg.add_button(parent="control",tag="btn_turn_on_off_modulation",label="Enable Modulation",callback=self.set_modulation_ena_dis)
        dpg.add_button(parent="control",tag="btn_switch_mode",label="set power mode",callback=self.switch_to_pwr_cur_mode)
        # btn turn on/off laser and tec
        
        dpg.add_text(parent="info",default_value="Laser Information", color=(255, 255, 0))
        dpg.add_text(parent="info",default_value="Current ---", tag="Laser Current")
        dpg.add_text(parent="info",default_value="Temperature ---", tag="Laser Temp")
        dpg.add_text(parent="info",default_value="Modulation ---", tag="Laser Modulation")
        dpg.add_text(parent="info",default_value="Mode ---", tag="Laser Mode")

        dpg.add_text(parent="parameters",default_value="Laser parameters", color=(255, 255, 0))
        dpg.add_input_float(parent="parameters", label="Set current(mA)", default_value=0, callback=self.set_current, tag="current_input", format='%.3f', width=200,min_value=0,max_value=250)

    def set_current(self, app_data, user_data):
        if 0<user_data <250:
            self.laser.set_current(user_data)
    
    def switch_to_pwr_cur_mode(self):
        self.laser.get_mode()
        if self.laser.mode in ['POW']:
            self.laser.set_current_mode()
        else:
            self.laser.set_power_mode()
    def set_modulation_ena_dis(self):
        if self.laser.modulation_mod in ['enabled']:
            self.laser.disable_modulation()
        else:
            self.laser.enable_modulation()
    def turn_on_off_laser(self):
        self.laser.get_lasing_state()
        if self.laser.lasing_state in ['Laser is ON']:
            self.laser.disable_laser()
        else:
            self.laser.enable_laser()
    def turn_on_off_tec(self):
        self.laser.get_tec_state()
        if self.laser.tec_state in ['TEC is ON']:
            self.laser.disable_tec()
        else:
            self.laser.enable_tec()

import inspect
import pdb

from typing import Optional
import dearpygui.demo as DPGdemo
import imgui
from OpenGL.GL import glGetString
from imgui.integrations.glfw import GlfwRenderer
from pyglet.gl import GL_VERSION, glClearColor, glClear, GL_COLOR_BUFFER_BIT
from PIL import Image
from Common import Common_Counter_Singletone, KeyboardKeys
from EventDispatcher import EventDispatcher
#from ExpSequenceGui import ExpSequenceGui
from HW_GUI import GUI_CLD1011LP as gui_CLD1011LP
from HW_GUI import GUI_Cobolt as gui_Cobolt
from HW_GUI import GUI_Picomotor as gui_Picomotor
from HW_GUI import GUI_RohdeSchwarz as gui_RohdeSchwarz
from HW_GUI import GUI_Smaract as gui_Smaract
from HW_GUI import GUI_Zelux as gui_Zelux
from HW_GUI.GUI_HRS_500 import GUI_HRS500
from HW_GUI.GUI_NI_DAQ import GUIDAQ
from HW_GUI.GUI_Picomotor import GUI_picomotor
from HW_GUI.GUI_arduino import GUIArduino
from HW_GUI.GUI_atto_scanner import GUIAttoScanner
from HW_GUI.GUI_highland_eom import GUIHighlandT130
from HW_GUI.GUI_keysight_AWG import GUIKeysight33500B
from HW_GUI.GUI_mattise import GUIMatisse
from HW_GUI.GUI_wavemeter import GUIWavemeter
from HW_GUI.GUI_motor_atto_positioner import GUIMotorAttoPositioner
from HW_GUI.GUI_motors import GUIMotor
from HW_GUI.GUI_KDC101 import GUI_KDC101
from HW_GUI.GUI_MFF_101 import GUI_MFF
from HW_GUI.GUI_sim960PID import GUISIM960
from HW_GUI.GUI_moku import GUIMoku
from HW_wrapper.Wrapper_moku import Moku
from HWrap_OPX import GUI_OPX, Experiment
from SystemConfig import SystemType, SystemConfig, load_system_config, run_system_config_gui, Instruments
from Utils.Common import calculate_z_series
from Common import WindowNames
from Window import Window_singleton
from Outout_to_gui import DualOutput
import threading
import glfw
import dearpygui.dearpygui as dpg
import os
import time
import HW_wrapper.HW_devices as hw_devices
import sys
from Utils.Common import calculate_z_series
import numpy as np

import Outout_to_gui as outout
from Common import wait_for_item_and_set

class Layer:
    def __init__(self, name="Layer"):
        self.m_DebugName = name
        self.KeepThreadRunning = True

    def on_attach(self):
        pass  # Do something when a layer is added to the layers stack

    def on_detach(self):
        pass  # Do something when a layer is removed from the layers stack

    def on_update(self):
        pass  # Initial update flow

    def obj_to_render(self, is_demo=False):
        pass  # Object to render can be GUI or vertex or other

    def on_render(self):
        pass  # Final update flow

    def on_event(self, event):
        pass  # Event handling function

    @property
    def name(self):
        return self.m_DebugName

class LayerStack:
    def __init__(self):
        self.m_Layers = [] # the list
        self.m_LayerInsert = 0 # index

    def __del__(self):
        for layer in self.m_Layers:
            del layer

    def push_layer(self, layer):
        self.m_LayerInsert = self.m_Layers.insert(self.m_LayerInsert, layer)

    def push_overlay(self, overlay):
        self.m_Layers.append(overlay)

    def pop_layer(self, layer):
        try:
            index = self.m_Layers.index(layer)
            del self.m_Layers[index]
            self.m_LayerInsert -= 1
        except ValueError:
            print("layer was not found in the list")
            pass

    def pop_overlay(self, overlay):
        try:
            index = self.m_Layers.index(overlay)
            del self.m_Layers[index]
        except ValueError:
            print("layer was not found in the list")
            pass

class ImGuiOverlay(Layer):
    def __init__(self):
        self.visible = False
        super().__init__()

        self.system_config: Optional[SystemConfig] = load_system_config()
        self.system_type: Optional[SystemType] = self.system_config.system_type

        # TODO : fix for all systems !!
        simulation = False
        if not self.system_type in [SystemType.HOT_SYSTEM, SystemType.ATTO]:
            simulation = True
        #self.exSeq = ExpSequenceGui()
        try:
            self.mwGUI = gui_RohdeSchwarz.GUI_RS_SGS100a(simulation)
        except:
            self.mwGUI = None
        # self.opxGUI = GUI_OPX(simulation)
    m_Time = 0.0


    def obj_to_render(self,IsDemo = False):
        io = imgui.get_io()
        io.font_global_scale = 1.4
        if (IsDemo):
            imgui.show_demo_window()
        else:
            self.guiID = Common_Counter_Singletone()
            self.guiID.Reset()
            #self.exSeq.controls()
            if self.mwGUI:
                self.mwGUI.controls()
            # self.smaractGUI.controls()
            # self.picomotorGUI.controls()

    def on_attach(self):
        imgui.create_context()
        self.renderer = GlfwRenderer(Application_singletone().GetWindow().m_Window_GL,False)
        
        imgui.style_colors_dark()
        # imgui.style_colors_light()
        # imgui.style_colors_classic()

        io = imgui.get_io()
        io.backend_flags |= 1 << 1 #imgui.IMGUI_BACKEND_FLAGS_HAS_MOUSE_CURSORS
        io.backend_flags |= 1 << 2#imgui.IMGUI_BACKEND_FLAGS_HAS_SET_MOUSE_POS
        # return super().on_attach()

    def on_update(self):
        self.io = imgui.get_io()
        io = self.io
        app = Application_singletone()
        # io.DisplaySize = ImVec2(app.GetWindow().GetWidth(), app.GetWindow().GetHeight())
        io.display_size = glfw.get_framebuffer_size(app.GetWindow().m_Window_GL)
        time = glfw.get_time()
        io.delta_time = (time - self.m_Time) if self.m_Time > 0.0 else (1.0 / 60.0)
        self.m_Time = time

        self.renderer.process_inputs()
        imgui.new_frame()
    def on_render(self):
        imgui.render()
        self.renderer.render(imgui.get_draw_data())
        # return super().on_render()

    # dispatch layer events
    def on_event(self, event):
        dispatcher = EventDispatcher(event)
        dispatcher.handled = False
        
        Event_handler = lambda event: self.keyboard_callback(event)
        Event_handler._event_type = "KeyboardEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        Event_handler = lambda event: self.char_callback(event)
        Event_handler._event_type = "CharEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True

        Event_handler = lambda event: self.mouse_callback(event)
        Event_handler._event_type = "MouseEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True

        Event_handler = lambda event: self.resize_callback(event)
        Event_handler._event_type = "WindowResizeEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        Event_handler = lambda event: self.scroll_callback(event)
        Event_handler._event_type = "ScrollEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        Event_handler = lambda event: self.OnWindowClose(event)
        Event_handler._event_type = "WindowCloseEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        return False

    # Layer callbacks (triggered by events set in window.py by glfw object)
    def keyboard_callback(self,event):
        if False: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        # perf: local for faster access
        io = self.io

        if event.action == glfw.PRESS:
            io.keys_down[event.key] = True
        elif event.action == glfw.RELEASE:
            io.keys_down[event.key] = False

        io.key_ctrl = (
            io.keys_down[glfw.KEY_LEFT_CONTROL] or
            io.keys_down[glfw.KEY_RIGHT_CONTROL]
        )

        io.key_alt = (
            io.keys_down[glfw.KEY_LEFT_ALT] or
            io.keys_down[glfw.KEY_RIGHT_ALT]
        )

        io.key_shift = (
            io.keys_down[glfw.KEY_LEFT_SHIFT] or
            io.keys_down[glfw.KEY_RIGHT_SHIFT]
        )

        io.key_super = (
            io.keys_down[glfw.KEY_LEFT_SUPER] or
            io.keys_down[glfw.KEY_RIGHT_SUPER]
        )

        if (io.key_ctrl and io.keys_down[glfw.KEY_SPACE]):
            self.SmaractLogPoint()

        if (io.key_ctrl and io.keys_down[glfw.KEY_LEFT]):
            self.SmaractKeyboardMovements(1)

        if (io.key_ctrl and io.keys_down[glfw.KEY_RIGHT]):
            self.SmaractKeyboardMovements(1,-1)

        if (io.key_ctrl and io.keys_down[glfw.KEY_UP]):
            self.SmaractKeyboardMovements(0)

        if (io.key_ctrl and io.keys_down[glfw.KEY_DOWN]):
            self.SmaractKeyboardMovements(0,-1)
        
        if (io.key_ctrl and io.keys_down[glfw.KEY_PAGE_UP]):
            self.SmaractKeyboardMovements(2,-1)

        if (io.key_ctrl and io.keys_down[glfw.KEY_PAGE_DOWN]):
            self.SmaractKeyboardMovements(2)

        if (io.key_alt and io.keys_down[glfw.KEY_LEFT]): # Picomotor steps
            self.PicoKeyboardMovements(1)

        if (io.key_alt and io.keys_down[glfw.KEY_RIGHT]): # Picomotor steps
            self.PicoKeyboardMovements(1,-1)

        if (io.key_alt and io.keys_down[glfw.KEY_UP]): # Picomotor steps
            self.PicoKeyboardMovements(0)

        if (io.key_alt and io.keys_down[glfw.KEY_DOWN]): # Picomotor steps
            self.PicoKeyboardMovements(0,-1)

        if (io.key_alt and io.keys_down[glfw.KEY_PAGE_UP]): # Picomotor steps
            self.PicoKeyboardMovements(2,-1)

        if (io.key_alt and io.keys_down[glfw.KEY_PAGE_DOWN]): # Picomotor steps
            self.PicoKeyboardMovements(2)

    def char_callback(self,event):
        if False: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        io = imgui.get_io()

        if 0 < event.char < 0x10000:
            io.add_input_character(event.char)
    def resize_callback(self,event):
        if True: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.io.display_size = event.width, event.height
    def mouse_callback(self,event):
        if False: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
    def scroll_callback(self,event):
        if False: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.io.mouse_wheel_horizontal = event.x_offset
        self.io.mouse_wheel = event.y_offset
    def OnWindowClose(self,event): # should get windowclos event
        if True: 
            print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.renderer.shutdown()
        return True

class Application_singletone:
    # create singleton
    _instance = None
    _lock = threading.Lock()

    def __new__(self, create_context: bool = True):
        with self._lock:
            if self._instance is None:
                self._instance = super(Application_singletone, self).__new__(self)
                self.glVer = glGetString(GL_VERSION)
                print("OpenGL version = ", self.glVer)
            else:
                # print("Application all ready exist!")
                pass
        return self._instance
    def __init__(self):
        self.m_Window.winData.event_callback = self.OnEvent
        pass

    m_running = True
    m_LayerStack = LayerStack()
    m_Window = Window_singleton()
    
    def Run(self):
        while self.m_running:
            glClearColor(0.1, 0.1, 0.1, 1)
            glClear(GL_COLOR_BUFFER_BIT)

            for layer in self.m_LayerStack.m_Layers:
                layer.on_update() #ImGuiLayerCore
                layer.obj_to_render()
                layer.on_render()
            
            self.m_Window.OnUpdate()
        
        self.Appclose()
    def OnEvent(self,event): 
        dispatcher = EventDispatcher(event)

        # dispatch application events
        Event_handler = lambda event: self.OnWindowResize(event)
        Event_handler._event_type = "WindowResizeEvent"
        res = dispatcher.dispatch(Event_handler)

        Event_handler = lambda event: self.OnWindowClose(event)
        Event_handler._event_type = "WindowCloseEvent"
        res = dispatcher.dispatch(Event_handler)

        # dispatch layer events
        it = len(self.m_LayerStack.m_Layers)  # Initialize iterator to the length of m_LayerStack

        # todo: think if handled window events send also to layers or not
        while it > 0:  # Loop until iterator reaches the beginning of the list
            it -= 1  # Decrement the iterator
            if self.m_LayerStack.m_Layers[it].on_event(event):  # Call OnEvent method of the current layer
                break
        pass
    def PushLayer(self, layer = Layer()): # should get layer
        self.m_LayerStack.push_layer(layer)
    def PushOverLay(self, layer = Layer()): # should get layer
        self.m_LayerStack.push_overlay(layer)
        layer.on_attach()
    def GetWindow(self):
        return self.m_Window
    def Appclose(self):
        # add close all HW (specifically OPX)
        # close wrong location threeads
        for layer in self.m_LayerStack.m_Layers:
            layer.KeepThreadRunning = False    
            pass
        glfw.terminate()
        pass
    
    # app callbacks (triggered by events set in window.py by glfw object)
    def OnWindowClose(self,event): # should get windowclos event
        print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.m_running = False
        return True
    def OnWindowResize(self,event): # should get window resize event
        print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )

class PyGuiOverlay(Layer):


    CURRENT_KEY: Optional[KeyboardKeys]

    m_Time = 0.0

    def __init__(self):
        """
               Initialize the application based on the detected system configuration.
        """
        super().__init__()
        self.modifier_key = None
        self.step_tuning_counter = None
        self.step_tuning_key = None
        self.viewport_h = None
        self.allow_bring_to_front = 1
        self.viewport_w = None
        self.selected_points = []
        self.moku_gui: Optional[Moku] = None
        self.DAQ_gui: Optional[GUIDAQ] = None
        self.picomotorGUI:Optional[GUI_picomotor] = None
        self.arduino_gui: Optional[GUIArduino] = None
        self.srs_pid_gui: list[GUISIM960] = []
        self.atto_scanner_gui: Optional[GUIMotor] = None
        self.keysight_gui: Optional[GUIKeysight33500B] = None
        self.mattise_gui: Optional[GUIMatisse] = None
        self.moku: Optional[GUIMoku] = None
        self.mwGUI = None
        self.system_type: Optional[SystemType] = None
        self.system_config: Optional[SystemConfig] = None
        self.mff_101_gui: Optional[list[GUI_MFF]] = []
        # Initialize instruments based on the system configuration

        self.smaract_thread = None
        self.smaractGUI = None
        self.atto_positioner_gui:Optional[GUIMotor] = None
        self.highland_gui: Optional[list[GUIHighlandT130]] = []
        self.lsr = None
        self.opx = None
        self.cam = None
        self.error = None
        self.picomotor_thread = None
        self.cobolt_thread = None
        self.CLD1011LP_thread = None
        self.GetScreenSize()
        self.CURRENT_KEY = None
        self.main_parent = "MainWindow"
        self.active_instrument_list = []
        self.window_positions = {}
        self.messages = []
        self.command_history = []
        self.MAX_HISTORY = 10  # Store last 5 commands

    def on_render(self):
        jobs = dpg.get_callback_queue() # retrieves and clears queue
        dpg.run_callbacks(jobs)
        dpg.render_dearpygui_frame()

        self.track_window_position()

        if getattr(self, 'cam', None) and getattr(self.cam, 'cam', None):
            cam_obj = self.cam.cam
            if isinstance(cam_obj.available_cameras, list) and cam_obj.available_cameras:
                if getattr(cam_obj, 'constantGrabbing', False):
                    self.cam.UpdateImage()
            else:
                self.cam = 'none'
        else:
            self.cam = 'none'

    def render_CLD1011LP(self):
        while self.KeepThreadRunning:
            time.sleep(0.5)
            try:
                self.CLD1011LP_gui.laser.get_info()
                if self.CLD1011LP_gui.laser.lasing_state in ['Laser is ON']:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_laser",label="Turn laser off")
                else:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_laser",label="Turn laser on")

                if self.CLD1011LP_gui.laser.tec_state in ['TEC is ON']:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_tec",label="Turn TEC off")
                else:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_tec",label="Turn TEC on")

                if self.CLD1011LP_gui.laser.modulation_mod in ['enabled']:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_modulation",label="disable modulation")
                else:
                    dpg.set_item_label(item="cld1011lp btn_turn_on_off_modulation",label="enable modulation")

                if self.CLD1011LP_gui.laser.mode in ['POW']:
                    dpg.set_item_label(item="btn_switch_mode",label="set current mode")
                else:
                    dpg.set_item_label(item="cld1011lp btn_switch_mode",label="set power mode")

                dpg.set_value(value=f"Current " + self.CLD1011LP_gui.laser.actual_current+ " A", item="cld1011lp Laser Current")
                dpg.set_value(value=f"Temperature " + self.CLD1011LP_gui.laser.actual_temp+ " degC", item="cld1011lp Laser Temp")
                dpg.set_value(value=f"Modulation " + self.CLD1011LP_gui.laser.modulation_mod, item="cld1011lp Laser Modulation")
                dpg.set_value(value=f"Mode " + self.CLD1011LP_gui.laser.mode, item="cld1011lp Laser Mode")

            except Exception as e:
                print(f"CLD1011LP render error: {e}")

    def render_cobolt(self):
        while self.KeepThreadRunning:
            time.sleep(0.15)
            try:
                if self.coboltGUI.laser.is_connected():
                    Laser_state=self.coboltGUI.laser.get_state()
                    dpg.set_value("Laser State","State:  "+Laser_state)
                    Laser_mode=self.coboltGUI.laser.get_mode()
                    dpg.set_value("Laser Mode","Mode: "+Laser_mode)

                    if self.coboltGUI.laser.is_on():
                        dpg.set_value("Laser ON OFF","The Laser is ON")
                        dpg.set_value("Turn_ON_OFF",True)
                    else:
                        dpg.set_value("Laser ON OFF","The Laser is OFF")
                        dpg.set_value("Turn_ON_OFF",False)

                    self.coboltGUI.laser.get_power()
                    Laser_power=str(round(self.coboltGUI.laser.actual_power*1000)/1000)
                    Laser_current=str(self.coboltGUI.laser.actual_current)
                    Laser_mod_power=str(round(self.coboltGUI.laser.modulation_power_setpoint*1000)/1000)

                    dpg.set_value("Laser Power","Actual power "+Laser_power+" mW")
                    dpg.set_value("Laser Current","Actual current "+Laser_current+" mA")
                    dpg.set_value("Laser Mod Power","Mod. Power setpoint "+Laser_mod_power+" mW")
                    am,dm = self.coboltGUI.laser.get_modulation_state()
                    dpg.set_value("Analog_Modulation_cbx",am=='1')
                    dpg.set_value("Digital_Modulation_cbx",dm=='1')

                    if Laser_mode in ["1 - Constant Power", "ConstantPower"]:
                        dpg.set_item_label("LaserWin",
                                           f"Cobolt (const pwr mode): {Laser_power} mW (setpoint: {Laser_mod_power} mW)")
                    elif Laser_mode in ["0 - Constant Current", "ConstantCurrent"]:
                        dpg.set_item_label("LaserWin", f"Cobolt (const current mode): {Laser_current} mA")
                    elif Laser_mode in ["2 - Modulation Mode", "PowerModulation"]:
                        dpg.set_item_label("LaserWin",
                                           f"Cobolt (mod. pwr mode): {Laser_power} mW (setpoint: {Laser_mod_power} mW)")

            except Exception as e:
                print(f"Cobolt render error: {e}")

    def render_picomotor(self):
        while self.KeepThreadRunning:
            time.sleep(1)
            try:
                if  self.picomotorGUI.dev.IsConnected:
                    self.picomotorGUI.dev.GetPosition()
                    for ch in range(self.picomotorGUI.dev.no_of_channels):
                        value=self.picomotorGUI.dev.AxesPositions[ch]/self.picomotorGUI.dev.StepsIn1mm*1e3
                        formatted_value = "{:.2f}".format(value) # Format with 2 significant digits
                        dpg.set_value("pico_Ch"+str(ch),"Ch"+str(ch)+" "+str(formatted_value))
                        if self.picomotorGUI.dev.GetMotionDone(ch+1):
                            dpg.set_value("pico_Status"+str(ch),"idle")
                        else:
                            dpg.set_value("pico_Status"+str(ch),"Moving")
            except Exception as e:
                print(f"Picomotor render error: {e}")

    def render_smaract(self):
        while self.KeepThreadRunning:
            time.sleep(0.2)
            if  self.smaractGUI.dev.IsConnected:
                self.smaractGUI.dev.GetPosition()
                for ch in range(self.smaractGUI.dev.no_of_channels):
                    value=self.smaractGUI.dev.AxesPositions[ch]/self.smaractGUI.dev.StepsIn1mm*1e3
                    formatted_value = "{:.4f}".format(value) # Format with 4 significant digits
                    dpg.set_value("mcs_Ch"+str(ch),"Ch"+str(ch)+" "+str(formatted_value))
                    self.smaractGUI.dev.ReadChannelsState(ch)
                    dpg.configure_item("mcs_Status" + str(ch), items=self.smaractGUI.dev.AxesState+self.smaractGUI.dev.AxesFault)         

    def obj_to_render(self, is_demo=False):
        pass

    def Callback_mouse_down(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_click(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            # print(f"app_data: {app_data}")
    def Callback_mouse_double_click(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_down(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_drag(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_move(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_release(self,sender,app_data):
        if self.allow_bring_to_front == 1:
            #dpg.focus_item("Main_Window")
            pass
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_mouse_wheel(self,sender,app_data):
        if False:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_key_down(self,sender,app_data):
        ignore = True
        if not ignore:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"app_data: {app_data}")
    def Callback_key_press(self,sender,app_data):
        # print(f"sender: {sender}")

        ignore=True
        if not ignore:
            print(f"Callback_key_press: {app_data}") ####KKK

        # if app_data == 17: # todo: map keys (17 == LCTRL):
            # print("hellow from Left CTRL!!")
        # if True:
        #     print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        #     print(f"app_data: {app_data}")
        self.keyboard_callback(sender,app_data)
    def Callback_key_release(self,sender,app_data):
        # Map the key data to the KeyboardKeys enum
        if app_data in KeyboardKeys._value2member_map_:
            key_data_enum = KeyboardKeys(app_data)
        else:
            return

        modifier_keys = {KeyboardKeys.CTRL_KEY, KeyboardKeys.SHIFT_KEY, KeyboardKeys.ALT_KEY,
                         KeyboardKeys.M_KEY, KeyboardKeys.N_KEY}

        if key_data_enum in modifier_keys:
            self.CURRENT_KEY = None # If CTRL/Shift/Alt/M/N is released, reset the flag

        ignore = True
        if not ignore:
            print("callback from "+self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
            print(f"Callback_key_release: {app_data}")

    def GetWindowSize(self):
        monitor = glfw.get_primary_monitor() # Get the primary monitor
        self.Window_width, self.Window_height = glfw.get_monitor_physical_size(monitor) # Get the physical size of the monitor

    def GetScreenSize(self):
        monitor = glfw.get_primary_monitor()        # Get the primary monitor
        mode = glfw.get_video_mode(monitor)         # Get the video mode of the monitor
        self.Monitor_width, self.Monitor_height = mode.size                   # Extract the width and height from the video mode

    def startDPG(self,IsDemo = False, _width = 600, _height = 1200):
        dpg.create_context()
        dpg.configure_app(manual_callback_management=True)
        # dpg.show_font_manager()

        self.LoadTheme()

        fontScale = self.Monitor_width/3840 #3840 from reference screen resolution
        pos = [int(0.0*self.Monitor_width),int(0.0*self.Monitor_height)]     # position relative to actual screen size
        size = [int(1.0*self.Monitor_width),int(0.97*self.Monitor_height)]   # new window width,height

        with dpg.font_registry():
            default_font = dpg.add_font("C:\\Windows\\Fonts\\Calibri.ttf", int(30*fontScale)+1)

        dpg.bind_font(default_font)

        self.AddAndBindFonts()

        dpg.handler_registry()

        with dpg.handler_registry():
            dpg.add_mouse_down_handler(callback=self.Callback_mouse_down)
            dpg.add_mouse_click_handler(callback=self.Callback_mouse_click)
            dpg.add_mouse_double_click_handler(callback=self.Callback_mouse_double_click)
            dpg.add_mouse_down_handler(callback=self.Callback_mouse_down)
            dpg.add_mouse_drag_handler(callback=self.Callback_mouse_drag)
            dpg.add_mouse_move_handler(callback=self.Callback_mouse_move)
            dpg.add_mouse_release_handler(callback=self.Callback_mouse_release)
            dpg.add_mouse_wheel_handler(callback=self.Callback_mouse_wheel)
            dpg.add_key_down_handler(callback=self.Callback_key_down)
            dpg.add_key_press_handler(callback=self.Callback_key_press)
            dpg.add_key_release_handler(callback=self.Callback_key_release)

        if IsDemo:
            DPGdemo.show_demo()

        dpg.create_viewport(title='QuTi SW', width=size[0], height=size[1],
                            x_pos = int(pos[0]), y_pos = int(pos[1]), always_on_top = False,
                            # min_width=100, max_width=1200,
                            # min_height=100, max_height=900,
                            resizable=True,
                            vsync=True, decorated=True, clear_color=True,
                            disable_close=False)
        self.viewport_w, self.viewport_h = dpg.get_viewport_client_width(), dpg.get_viewport_client_height()
        dpg.setup_dearpygui()
        dpg.show_viewport()
        pass

    def track_window_position(self):
        """
        Periodically checks the position of tracked windows and logs changes.
        """
        for window in WindowNames:
            win_name = window.value
            if dpg.does_item_exist(win_name):
                current_pos = dpg.get_item_pos(win_name)
                if win_name not in self.window_positions or self.window_positions[win_name] != current_pos:
                    # print(f"Window '{win_name}' moved. New position: {current_pos}")
                    self.window_positions[win_name] = current_pos

    def on_attach(self):

        self.startDPG(IsDemo=False,_width=2150,_height=1800)
        self.setup_main_exp_buttons()
        self.setup_instruments()
        dpg.focus_item("Main_Window")

        self.create_console_gui()
        # Redirect stdout and stderr to both the GUI console and the original outputs
        sys.stdout = DualOutput(sys.__stdout__)
        sys.stdout.parent = self
        sys.stderr = DualOutput(sys.__stderr__)

        dpg.set_frame_callback(100, lambda: dpg.focus_item("cmd_input"))

    def setup_instruments(self) -> None:
        """
        Set up instruments and dynamically arrange their GUIs based on the system configuration.
        Each new GUI is placed below the previously loaded one.
        """
        self.system_config = load_system_config()

        if not self.system_config:
            run_system_config_gui()
            load_system_config()

        if not self.system_config:
            raise Exception("No system config")

        # Initialize y_offset to start placing GUIs vertically
        y_offset = 30
        vertical_spacing = 20  # Spacing between GUIs

        self.highland_list = hw_devices.HW_devices().highland_eom_driver

        for device in self.system_config.devices:
            instrument = device.instrument
            print(f"loading instrument {instrument.value}")
            try:

                if instrument == Instruments.ROHDE_SCHWARZ:
                    pass
                    # self.mwGUI = gui_RohdeSchwarz.GUI_RS_SGS100a(self.simulation)
                    # dpg.set_item_pos(self.mwGUI.window_tag, [20, y_offset])
                    # y_offset += dpg.get_item_height(self.mwGUI.window_tag) + vertical_spacing

                elif instrument in [Instruments.SMARACT_SLIP, Instruments.SMARACT_SCANNER]:
                    self.smaractGUI = gui_Smaract.GUI_smaract(simulation=device.simulation,
                                                              serial_number=device.serial_number)
                    self.create_bring_window_button(self.smaractGUI.window_tag, button_label="Smaract",
                                                    tag="Smaract_button", parent="focus_group")
                    self.active_instrument_list.append(self.smaractGUI.window_tag)
                    dpg.set_item_pos(self.smaractGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.smaractGUI.window_tag) + vertical_spacing

                    if not device.simulation:
                        self.smaract_thread = threading.Thread(target=self.render_smaract)
                        self.smaract_thread.start()

                elif instrument == Instruments.CLD1011LP:
                    self.CLD1011LP_gui = gui_CLD1011LP.GUI_CLD1011LP(device.simulation)
                    self.create_bring_window_button(self.CLD1011LP_gui.window_tag, button_label="CLD1011LP",
                                                    tag="CLD1011LP_button", parent="focus_group")
                    self.active_instrument_list.append(self.CLD1011LP_gui.window_tag)
                    dpg.set_item_pos(self.CLD1011LP_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.CLD1011LP_gui.window_tag) + vertical_spacing
                    if not device.simulation:
                        self.CLD1011LP_thread = threading.Thread(target=self.render_CLD1011LP)
                        self.CLD1011LP_thread.start()

                elif instrument == Instruments.COBOLT:
                    self.coboltGUI = gui_Cobolt.GUI_Cobolt(device.simulation, com_port = device.com_port)
                    self.create_bring_window_button(self.coboltGUI.window_tag, button_label="Cobolt",
                                                    tag="Cobolt_button", parent="focus_group")
                    self.active_instrument_list.append(self.coboltGUI.window_tag)
                    dpg.set_item_pos(self.coboltGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.coboltGUI.window_tag) + vertical_spacing
                    if not device.simulation:
                        self.cobolt_thread = threading.Thread(target=self.render_cobolt)
                        self.cobolt_thread.start()

                elif instrument == Instruments.PICOMOTOR:
                    self.picomotorGUI = gui_Picomotor.GUI_picomotor(simulation=device.simulation)
                    self.create_bring_window_button(self.picomotorGUI.window_tag, button_label="picomotor",
                                                    tag="picomotor_button", parent="focus_group")
                    self.active_instrument_list.append(self.picomotorGUI.window_tag)
                    dpg.set_item_pos(self.picomotorGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.picomotorGUI.window_tag) + vertical_spacing

                    if not device.simulation:
                        self.picomotor_thread = threading.Thread(target=self.render_picomotor)
                        self.picomotor_thread.start()

                elif instrument == Instruments.ZELUX:
                    self.cam = gui_Zelux.ZeluxGUI()
                    self.create_bring_window_button(self.cam.window_tag, button_label="Zelux", tag="Zelux_button", parent="focus_group")
                    self.active_instrument_list.append(self.cam.window_tag)
                    if len(self.cam.cam.available_cameras) > 0:
                        self.cam.Controls()
                        dpg.set_item_pos(self.cam.window_tag, [self.Monitor_width-dpg.get_item_width(self.cam.window_tag)-vertical_spacing, vertical_spacing])

                elif instrument == Instruments.OPX:
                    self.opx = GUI_OPX(device.simulation)
                    self.opx.controls()
                    self.create_bring_window_button(self.opx.window_tag, button_label="OPX", tag="OPX_button",
                                                    parent="focus_group")
                    self.create_sequencer_button()
                    self.active_instrument_list.append(self.opx.window_tag)
                    dpg.set_item_pos(self.opx.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.opx.window_tag) + vertical_spacing

                elif instrument == Instruments.ATTO_POSITIONER:
                    self.atto_positioner_gui = GUIMotorAttoPositioner(
                        motor=hw_devices.HW_devices().atto_positioner,
                        instrument=Instruments.ATTO_POSITIONER,
                        simulation=device.simulation
                    )
                    self.create_bring_window_button(self.atto_positioner_gui.window_tag, button_label="ATTO_POSITIONER",
                                                    tag="ATTO_POSITIONER_button", parent="focus_group")
                    self.active_instrument_list.append(self.atto_positioner_gui.window_tag)
                    dpg.set_item_pos(self.atto_positioner_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.atto_positioner_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.HIGHLAND:
                    matching_device = next(
                        (highland for highland in self.highland_list if str(highland.serial_number) == device.serial_number),
                        None  # Default if no match is found
                    )
                    current_gui = GUIHighlandT130(matching_device)
                    self.highland_gui.append(current_gui)
                    # for highland_gui in self.highland_gui:
                    self.create_bring_window_button(current_gui.window_tag, button_label=f"Highland sn:{matching_device.serial_number}",
                                                    tag=f"Highland_button_{device.serial_number}", parent="focus_group")
                    self.active_instrument_list.append(current_gui.window_tag)
                    dpg.set_item_pos(current_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(current_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.MATTISE:
                    self.mattise_gui = GUIMatisse(
                        device=hw_devices.HW_devices().matisse_device,
                        simulation=device.simulation
                    )
                    self.create_bring_window_button(self.mattise_gui.window_tag, button_label="MATTISE",
                                                    tag="MATTISE_button", parent="focus_group")
                    self.active_instrument_list.append(self.mattise_gui.window_tag)
                    dpg.set_item_pos(self.mattise_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.mattise_gui.window_tag) + vertical_spacing
                elif instrument == Instruments.WAVEMETER:
                    self.wlm_gui = GUIWavemeter(device=hw_devices.HW_devices().wavemeter, instrument=instrument, simulation=device.simulation)
                    self.create_bring_window_button(self.wlm_gui.window_tag, button_label="WAVEMETER",
                                                    tag="WAVEMETER_button", parent="focus_group")
                    dpg.set_item_pos(self.mattise_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.mattise_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.KEYSIGHT_AWG:
                    self.keysight_gui = GUIKeysight33500B(
                        device= hw_devices.HW_devices().keysight_awg_device,
                        simulation=device.simulation
                    )
                    self.create_bring_window_button(self.keysight_gui.window_tag, button_label="KEYSIGHT_AWG",
                                                    tag="keysight_button", parent="focus_group")
                    self.active_instrument_list.append(self.keysight_gui.window_tag)
                    dpg.set_item_pos(self.keysight_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.keysight_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.ATTO_SCANNER:
                    hw_devices.HW_devices().atto_scanner.connect()
                    self.atto_scanner_gui = GUIAttoScanner(
                        motor= hw_devices.HW_devices().atto_scanner,
                        instrument=Instruments.ATTO_SCANNER,
                        simulation=device.simulation
                    )
                    self.create_bring_window_button(self.atto_scanner_gui.window_tag, button_label="ATTO_SCANNER",
                                                    tag="ATTO_SCANNER_button", parent="focus_group")
                    self.active_instrument_list.append(self.atto_scanner_gui.window_tag)
                    dpg.set_item_pos(self.atto_scanner_gui.window_tag, [20, 20])
                    y_offset += dpg.get_item_height(self.atto_scanner_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.KDC_101:
                    self.kdc_101_gui = GUI_KDC101(serial_number = device.serial_number, device = hw_devices.HW_devices().kdc_101)
                    dpg.set_item_pos(self.kdc_101_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.kdc_101_gui.window_tag) + vertical_spacing
                    self.create_bring_window_button(self.kdc_101_gui.window_tag, button_label="kdc_101",
                                                    tag="kdc_101_button", parent="focus_group")
                    self.active_instrument_list.append(self.kdc_101_gui.window_tag)

                elif instrument == Instruments.MFF_101:
                    # if self.mff_101_gui is None:
                    #     self.mff_101_gui = GUI_MFF(serial_number = device.serial_number, device = hw_devices.HW_devices().mff_101_list)
                    # else:
                    #     self.mff_101_gui.add_new_button(serial_number=device.serial_number)
                    # self.mff_101_gui = GUI_MFF(serial_number=device.serial_number,device=hw_devices.HW_devices().mff_101_list)
                    flipper_list = hw_devices.HW_devices().mff_101_list
                    matching_device = next(
                        (flipper for flipper in flipper_list if str(flipper.serial_no) == device.serial_number),
                        None  # Default if no match is found
                    )
                    self.mff_101_gui.append(GUI_MFF(serial_number=matching_device.serial_no, device = matching_device))
                    # last_gui = self.mff_101_gui[-1]
                    # last_gui.create_gui_into_zelux()
                    pass

                elif instrument == Instruments.HRS_500:
                    self.hrs_500_gui = GUI_HRS500(hw_devices.HW_devices().hrs_500)
                    self.create_bring_window_button(self.hrs_500_gui.window_tag, button_label="Spectrometer",
                                                    tag="HRS_500_button", parent="focus_group")
                    self.active_instrument_list.append(self.hrs_500_gui.window_tag)

                elif instrument == Instruments.ARDUINO:
                    self.create_bring_window_button(self.arduino_gui.window_tag, button_label="Arduino",
                                                    tag="Arduino_button", parent="focus_group")
                    self.active_instrument_list.append(self.arduino_gui.window_tag)
                    self.arduino_gui = GUIArduino(hw_devices.HW_devices().arduino)

                elif instrument == Instruments.SIM960:
                    print('Initializing PID HW list')
                    srs_pid_list=hw_devices.HW_devices().SRS_PID_list
                    print(f'SRS PID list: {srs_pid_list}')
                    if device.simulation:
                        device.ip_address=0
                        matching_device=srs_pid_list[0]
                    else:
                        matching_device = next(
                            (sim_device for sim_device in srs_pid_list if str(sim_device.slot) == device.ip_address),
                            None  # Default if no match is found
                        )
                    print('Initializing PID GUI')
                    self.srs_pid_gui.append(GUISIM960(
                        sim960=matching_device,
                        simulation=device.simulation
                    ))
                    self.create_bring_window_button(self.srs_pid_gui[0].win_tag, button_label="SIM960",
                                                    tag="SIM960_button", parent="focus_group")
                    self.active_instrument_list.append(self.srs_pid_gui[0].win_tag)

                elif instrument == Instruments.MOKU:
                    self.moku_gui = GUIMoku(hw_devices.HW_devices().moku)

                elif instrument == Instruments.NI_DAQ:
                    self.DAQ_gui = GUIDAQ(daq=hw_devices.HW_devices().ni_daq_controller)

                else:
                    print(f"Unknown instrument {instrument} ")

            except Exception as e:
                print(f"Failed loading device {device} of instrument type {instrument} with error {e}")

    def update_in_render_cycle(self):
        # add thing to update every rendering cycle
        pass
    def on_update(self):
        # todo: fix window termination
        if not(dpg.is_dearpygui_running()):
            dpg.destroy_context()
        pass

    # dispatch layer events
    def on_event(self, event):
        dispatcher = EventDispatcher(event)
        dispatcher.handled = False

        # Event_handler = lambda event: self.keyboard_callback(event) # SHAI 21-8-2024
        # Event_handler._event_type = "KeyboardEvent"
        # dispatcher.dispatch(Event_handler)
        # if dispatcher.handled:
        #     return True
        '''
        Event_handler = lambda event: self.char_callback(event)
        Event_handler._event_type = "CharEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True

        Event_handler = lambda event: self.mouse_callback(event)
        Event_handler._event_type = "MouseEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True

        Event_handler = lambda event: self.resize_callback(event)
        Event_handler._event_type = "WindowResizeEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        Event_handler = lambda event: self.scroll_callback(event)
        Event_handler._event_type = "ScrollEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        
        Event_handler = lambda event: self.OnWindowClose(event)
        Event_handler._event_type = "WindowCloseEvent"
        dispatcher.dispatch(Event_handler)
        if dispatcher.handled:
            return True
        '''

        return False

    def keyboard_callback(self, event, key_data):
        """Handles keyboard input and triggers movement for various devices."""
        try:

            # Determine if coarse movement is enabled (for OPX and other devices)
            is_coarse = self.CURRENT_KEY == KeyboardKeys.CTRL_KEY

            # Map the key data to the KeyboardKeys enum
            if key_data in KeyboardKeys._value2member_map_:
                key_data_enum = KeyboardKeys(key_data)
            else:
                return

            # Update modifier key if it's a modifier
            if key_data_enum in [KeyboardKeys.CTRL_KEY, KeyboardKeys.SHIFT_KEY]:
                self.modifier_key = key_data_enum

            # Initialize step tuning attributes if not present
            if not hasattr(self, "step_tuning_key"):
                self.step_tuning_key = None
                self.step_tuning_counter = 0

            # === Step size tuning for Smaract ===
            if hasattr(self, 'last_moved_axis'):
                axis = self.last_moved_axis
                coarse_tag = f"{self.smaractGUI.prefix}_ch{axis}_Cset"
                fine_tag = f"{self.smaractGUI.prefix}_ch{axis}_Fset"

                # Combo logic: only check when the key is a step key, not modifier
                if key_data_enum in [KeyboardKeys.OEM_PERIOD, KeyboardKeys.OEM_COMMA]:
                    combo = (self.modifier_key, key_data_enum)

                    # Track repeated presses of same combo
                    if combo == getattr(self, "step_tuning_key", None):
                        self.step_tuning_counter += 1
                    else:
                        self.step_tuning_counter = 0
                        self.step_tuning_key = combo

                    factor = 2 ** self.step_tuning_counter
                    print(f"{combo} → counter={self.step_tuning_counter} → factor={factor}")

                    # Ctrl + . → increase coarse step
                    if combo == (KeyboardKeys.CTRL_KEY, KeyboardKeys.OEM_PERIOD):
                        val = dpg.get_value(coarse_tag) + factor
                        dpg.set_value(coarse_tag, val)
                        self.smaractGUI.ipt_large_step(coarse_tag, val)
                        print(f"↑ Coarse step axis {axis} = {val:.1f} µm")

                    # Ctrl + , → decrease coarse step
                    elif combo == (KeyboardKeys.CTRL_KEY, KeyboardKeys.OEM_COMMA):
                        val = max(1, dpg.get_value(coarse_tag) - factor)
                        dpg.set_value(coarse_tag, val)
                        self.smaractGUI.ipt_large_step(coarse_tag, val)
                        print(f"↓ Coarse step axis {axis} = {val:.1f} µm")

                    # Shift + . → increase fine step
                    elif combo == (KeyboardKeys.SHIFT_KEY, KeyboardKeys.OEM_PERIOD):
                        val = dpg.get_value(fine_tag) + factor * 10
                        dpg.set_value(fine_tag, val)
                        self.smaractGUI.ipt_small_step(fine_tag, val)
                        print(f"↑ Fine step axis {axis} = {val:.1f} nm")

                    # Shift + , → decrease fine step
                    elif combo == (KeyboardKeys.SHIFT_KEY, KeyboardKeys.OEM_COMMA):
                        val = max(10, dpg.get_value(fine_tag) - factor * 10)
                        dpg.set_value(fine_tag, val)
                        self.smaractGUI.ipt_small_step(fine_tag, val)
                        print(f"↓ Fine step axis {axis} = {val:.1f} nm")

            # Handle Smaract controls
            if self.CURRENT_KEY in [KeyboardKeys.CTRL_KEY, KeyboardKeys.SHIFT_KEY]:
                # Focus on cmd_input if Ctrl+D is pressed
                if key_data_enum == KeyboardKeys.D_KEY:
                    dpg.focus_item("cmd_input")
                    return
                self.handle_smaract_controls(key_data_enum, is_coarse)

            # Update the current key pressed
            self.CURRENT_KEY = key_data_enum

        except Exception as ex:
            self.error = f"Unexpected error in keyboard_callback: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)



    def handle_smaract_controls(self, key_data_enum, is_coarse):
        """Handles keyboard input for Smaract device controls."""
        try:
            if key_data_enum == KeyboardKeys.S_KEY: # Save all even if keyboard disabled
                #pdb.set_trace()  # Insert a manual breakpoint
                if self.smaractGUI:
                    self.smaractGUI.save_log_points()
                    self.smaractGUI.save_pos()
                if self.picomotorGUI:
                    self.picomotorGUI.save_log_points()

                if hasattr(self.opx, 'map') and self.opx.map is not None:
                    self.opx.map.save_map_parameters()
                return

            if self.smaractGUI and self.smaractGUI.dev.KeyboardEnabled:
                if key_data_enum == KeyboardKeys.SPACE_KEY:
                    print('Logging point')
                    self.smaract_log_points()
                elif key_data_enum == KeyboardKeys.LEFT_KEY:
                    self.last_moved_axis = 0
                    self.smaract_keyboard_movement(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.RIGHT_KEY:
                    self.last_moved_axis = 0
                    self.smaract_keyboard_movement(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.UP_KEY:
                    self.last_moved_axis = 1
                    self.smaract_keyboard_movement(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.DOWN_KEY:
                    self.last_moved_axis = 1
                    self.smaract_keyboard_movement(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEUP_KEY:
                    self.last_moved_axis = 2
                    self.smaract_keyboard_movement(2, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEDOWN_KEY:
                    self.last_moved_axis = 2
                    self.smaract_keyboard_movement(2, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.INSERT_KEY:
                    self.last_moved_axis = 0
                    self.smaract_keyboard_move_uv(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.DEL_KEY:
                    self.last_moved_axis = 0
                    self.smaract_keyboard_move_uv(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.HOME_KEY:
                    self.last_moved_axis = 1
                    self.smaract_keyboard_move_uv(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.END_KEY:
                    self.last_moved_axis = 2
                    self.smaract_keyboard_move_uv(1, 1, is_coarse)

        except Exception as ex:
            self.error = f"Error in handle_smaract_controls: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def smaract_log_points(self):
        try:
            # if self.io.keys_down[glfw.KEY_SPACE]:
            self.smaractGUI.btnLogPoint()
            # self.smaractGUI.dev.GetPosition()
            # self.smaractGUI.dev.LoggedPoints.append(self.smaractGUI.dev.AxesPositions.copy()) # [pm]
            print(f"Last logged point: {self.smaractGUI.dev.LoggedPoints[-1]}")
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            # raise
    def smaract_del_points(self):
        try:
            self.smaractGUI.btnDelPoint()
            print(f"Last logged point: {self.smaractGUI.dev.LoggedPoints[-1]}")
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            # raise

    def smaract_keyboard_movement(self,ax,direction = 1,Coarse_or_Fine = 1):
        try:
            if Coarse_or_Fine==0:
                # print("Small step")
                self.smaractGUI.dev.MoveRelative(ax,direction*self.smaractGUI.dev.AxesKeyBoardSmallStep[ax])
            else:
                # print("Large step")
                # print(self.smaractGUI.dev.AxesKeyBoardLargeStep[ax])
                self.smaractGUI.dev.MoveRelative(ax,direction*self.smaractGUI.dev.AxesKeyBoardLargeStep[ax])
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            # raise

    def opx_keyboard_map_movement(self, ax, direction=1, is_coarse = 1):
        """
        Move the active marker in response to keyboard input, controlling movement along specified axis (ax) and direction.

        :param ax: Axis to move (0 for horizontal, 1 for vertical)
        :param direction: Direction of movement (-1 for left/up, 1 for right/down)
        :param is_coarse: 1 for fine movement, 10 for coarse movement
        """
        try:
            print("HEY")
            # Determine the movement direction and axis
            if ax == 0:  # Horizontal movement
                if direction == -1:
                    move_direction = "left" if is_coarse == 0 else "left left"
                elif direction == 1:
                    move_direction = "right" if is_coarse == 0 else "right right"
                else:
                    print("Illegal direction value for horizontal movement.")
                    return 1
            elif ax == 1:  # Vertical movement
                if direction == -1:
                    move_direction = "up" if is_coarse == 0 else "up up"
                elif direction == 1:
                    move_direction = "down" if is_coarse == 0 else "down down"
                else:
                    print("Illegal direction value for vertical movement.")
                    return 1
            else:
                print("Illegal axis value.")
                return 1

            # Move the active marker or area marker based on the calculated direction
            print(move_direction)
            self.opx.map.move_active_marker(move_direction)

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            # Handle the exception appropriately
            print(self.error)

    def smaract_keyboard_move_uv(self,ax,direction, is_coarse):
        try:
            self.smaractGUI.move_uv(sender=self, app_data=None, user_data=(ax,direction,is_coarse))
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))

    def pico_keyboard_move_uv(self,ax,direction, is_coarse):
        try:
            self.picomotorGUI.move_uv(sender=self, app_data=None, user_data=(ax,direction,is_coarse))
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))

    def pico_keyboard_movement(self,ax,dir = 1,Coarse_or_Fine = 1):
        try:
            print("pico movement")
            if Coarse_or_Fine==0:
                self.picomotorGUI.dev.MoveRelative(ax+1,dir*self.picomotorGUI.dev.AxesKeyBoardSmallStep[ax])
            else:
                print("Large step")
                self.picomotorGUI.dev.MoveRelative(ax+1,dir*self.picomotorGUI.dev.AxesKeyBoardLargeStep[ax])
        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            # raise

    def char_callback(self,event):
        print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        io = imgui.get_io()

        if 0 < event.char < 0x10000:
            io.add_input_character(event.char)
    def resize_callback(self,event):
        print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.io.display_size = event.width, event.height
    def mouse_callback(self,event):
        # print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        pass
    def scroll_callback(self,event):
        print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.io.mouse_wheel_horizontal = event.x_offset
        self.io.mouse_wheel = event.y_offset
    def OnWindowClose(self,event): # should get windowclos event
        print("callback from:" + self.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        self.smaractGUI.dev.Disconnect()
        self.picomotorGUI.dev.Disconnect()
        self.renderer.shutdown()
        dpg.destroy_context()
        return True

    def AddAndBindFonts(self): # add after create context
        # get availableFonts from windows folder

        # fontsPath = pathlib.Path(__file__).parent.resolve() # get path of current folder
        # path = fontsPath.__str__() + "\\fonts"

        path = "C:\\Windows\\Fonts"
        res = os.listdir(path)
        a = [e for e in res if (not(e.find(".otf")==-1) or not(e.find(".OTF")==-1) or not(e.find(".ttf")==-1) or not(e.find(".TTF")==-1))]
        self.gui_globalFontSize = 25
        self.fontList = []
        # add a font registry

        with dpg.font_registry():
            for e in a:
                # dpg.add_font(path + "\\" + e, 25)
                self.fontList.append(dpg.add_font(file = path + "\\" + e, size = self.gui_globalFontSize))
        # dpg.add_font_registry()
        # for e in res:
        #     print(e)
        #     self.fontList.append(dpg.add_font(file = path + "\\" + e, size = self.gui_globalFontSize))

        dpg.bind_font(self.fontList[10])

    def Btn_colorTheme(self, _tag,_color = (255,255,255)): # optional to make a list of all thems which later can be used in the SW to change color
        dpg.add_theme(tag=_tag)
        dpg.add_theme_component(item_type = dpg.mvAll,parent=_tag,tag=_tag+"Cmp")
        dpg.add_theme_color(target = dpg.mvThemeCol_Button, value = _color, category=dpg.mvThemeCat_Core,parent=_tag+"Cmp")
        dpg.add_theme_style(target = dpg.mvStyleVar_FrameRounding, x = 15, y = -20, category=dpg.mvThemeCat_Core,parent=_tag+"Cmp")

    def LoadTheme(self):
        dpg.add_theme(tag="LineYellowTheme")
        dpg.add_theme_component(item_type = dpg.mvLineSeries,parent="LineYellowTheme",tag="LineYellowThemeCmp")
        dpg.add_theme_color(target = dpg.mvPlotCol_Line, value = (255, 255, 0), category=dpg.mvThemeCat_Plots,parent="LineYellowThemeCmp")
        # dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Diamond, category=dpg.mvThemeCat_Plots)
        # dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 7, category=dpg.mvThemeCat_Plots)

        dpg.add_theme(tag="LineMagentaTheme")
        dpg.add_theme_component(item_type = dpg.mvLineSeries,parent="LineMagentaTheme",tag="LineMagentaThemeCmp")
        dpg.add_theme_color(target = dpg.mvPlotCol_Line, value = (255, 0, 255), category=dpg.mvThemeCat_Plots,parent="LineMagentaThemeCmp")
        # dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Diamond, category=dpg.mvThemeCat_Plots)
        # dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 7, category=dpg.mvThemeCat_Plots)

        dpg.add_theme(tag="LineCyanTheme")
        dpg.add_theme_component(item_type = dpg.mvLineSeries,parent="LineCyanTheme",tag="LineCyanThemeCmp")
        dpg.add_theme_color(target = dpg.mvPlotCol_Line, value = (0, 255, 255), category=dpg.mvThemeCat_Plots,parent="LineCyanThemeCmp")
        # dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Diamond, category=dpg.mvThemeCat_Plots)
        # dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 7, category=dpg.mvThemeCat_Plots)

        dpg.add_theme(tag="LineRedTheme")
        dpg.add_theme_component(item_type = dpg.mvLineSeries,parent="LineRedTheme",tag="LineRedThemeCmp")
        dpg.add_theme_color(target = dpg.mvPlotCol_Line, value = (255, 0, 0), category=dpg.mvThemeCat_Plots,parent="LineRedThemeCmp")
        # dpg.add_theme_style(dpg.mvPlotStyleVar_Marker, dpg.mvPlotMarker_Diamond, category=dpg.mvThemeCat_Plots)
        # dpg.add_theme_style(dpg.mvPlotStyleVar_MarkerSize, 7, category=dpg.mvThemeCat_Plots)

        dpg.add_theme(tag="NewTheme")
        # dpg.add_theme_component(item_type = dpg.mvAll,parent="NewTheme",tag="NewThemeCmp")
        dpg.add_theme_component(item_type = dpg.mvInputDouble,parent="NewTheme",tag="NewThemeCmp")
        dpg.add_theme_color(target = dpg.mvThemeCol_FrameBg, value = (110, 180, 100), category=dpg.mvThemeCat_Core,parent="NewThemeCmp")
        dpg.add_theme_style(target = dpg.mvStyleVar_FrameRounding, x = 5, category=dpg.mvThemeCat_Core,parent="NewThemeCmp")

        dpg.add_theme_component(item_type = dpg.mvInputInt,parent="NewTheme",tag="NewThemeCmp2")
        dpg.add_theme_color(target = dpg.mvThemeCol_FrameBg, value = (150, 150, 100), category=dpg.mvThemeCat_Core,parent="NewThemeCmp2")
        dpg.add_theme_style(target = dpg.mvStyleVar_FrameRounding, x = 5, y = 0, category=dpg.mvThemeCat_Core,parent="NewThemeCmp2")

        self.Btn_colorTheme(_tag = "btnYellowTheme",_color = (155,155,0))
        self.Btn_colorTheme(_tag = "btnRedTheme",_color = (150, 100, 100))
        self.Btn_colorTheme(_tag = "btnGreenTheme",_color = (100, 150, 100))
        self.Btn_colorTheme(_tag = "btnBlueTheme",_color = (100, 100, 150))
        self.Btn_colorTheme(_tag="btnPurpleTheme", _color=(195, 177, 255))

        # Create a theme to highlight the new container (group or child window)
        with dpg.theme(tag="highlighted_header_theme"):
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0), category=dpg.mvThemeCat_Core)  # Black text

    def bring_window_to_front(self, window_id: str):
        """
        Brings the specified window to the front by its Dear PyGui ID
        by setting the keyboard focus on it.
        """
        try:
            dpg.focus_item(window_id)
        except Exception as e:
            print(f"Error bringing window '{window_id}' to front: {e}")

    def create_bring_window_button(self, window_id: str, tag: str,parent: Optional[str] = None,
                                   button_label: str = "Instrument"):
        def bring_window_callback(sender, app_data, user_data):
            self.bring_window_to_front(window_id)

        kwargs = {"label": button_label, "callback": bring_window_callback, "tag": tag}
        if parent is not None:
            kwargs["parent"] = parent
        dpg.add_button(**kwargs)

    def create_sequencer_button(self, parent: Optional[str] = "sequencer_group"):
        dpg.add_text("Show current sequence:", parent = parent)
        dpg.add_button(label="Show Sequence", parent = parent, callback=self.png_sequencer)

    def clamp(self, n, min_n, max_n):
        return max(min(max_n, n), min_n)

    def create_instrument_window_section(self):
        for window in self.active_instrument_list:
            # If the window is hovered, check and clamp its position.
            if dpg.is_item_hovered(window):
                x, y = dpg.get_item_pos(window)
                w, h = dpg.get_item_rect_size(window)
                min_x, min_y, max_x, max_y = 0,0, self.viewport_w//1.1, self.viewport_h*1.3
                new_x = self.clamp(x, min_x, max_x - w)
                new_y = self.clamp(y, min_y, max_y - h)
                if (new_x, new_y) != (x, y):
                    dpg.set_item_pos(window, (new_x, new_y))
                    time.sleep(0.1)


    def check_sequence_type(self):
        """
        Functions that checks the sequence type and uploads a corresponding image.
        The image data is hardcoded.
        """
        exp_to_path = {
            #Todo: Add the rest of the experiments.
            Experiment.COUNTER: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Counter.png",
            Experiment.ODMR_CW: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\CW_ODMR.png",
            Experiment.PULSED_ODMR: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Pulsed_ODMR.png",
            Experiment.ODMR_Bfield: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\ODMR_Bfield.png",
            Experiment.NUCLEAR_MR: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_MR.png",
            Experiment.RABI: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Rabi.png",
            Experiment.NUCLEAR_POL_ESR: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_Pol_ESR.png",
            Experiment.Nuclear_spin_lifetimeS0: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_spin_lifetime_S0.png",
            Experiment.Nuclear_spin_lifetimeS1: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_spin_lifetime_S1.png",
            Experiment.Hahn: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Electron_Hahn.png", #Todo: Update Hahn to actual sequence
            Experiment.NUCLEAR_RABI: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_Rabi.png",
            Experiment.Nuclear_Ramsay: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Nuclear_Ramsay_S0.png", #Todo: Figure out which Ramsay
            Experiment.Electron_lifetime: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\T1_Electron_lifetime.png",
            Experiment.Nuclear_Fast_Rot: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\nuclear_fast_rot.png",
            Experiment.TIME_BIN_ENTANGLEMENT: "Q:\\QT-Quantum_Optic_Lab\\Tutorials\\Sequences_for_QuTi_in_png\\Time_bin.png"
        }
        if self.opx.exp not in exp_to_path:
            print(f"Warning: No known image for experiment type: {self.opx.exp}")
            return None
        path = exp_to_path[self.opx.exp]
        try:
            width, height, channels, data = dpg.load_image(path)
            return width, height, channels, data
        except Exception as e:
            print(f"Failed loading image file at '{path}': {e}")
            return None

    def png_sequencer(self):
        try:
            image_data = self.check_sequence_type()
            if image_data is None:
                print("No valid image data. Check image loading.")
                return
            width, height, channels, data = image_data
            with dpg.texture_registry():
                if not dpg.does_item_exist("texture_tag"):
                    dpg.add_static_texture(width, height, data, tag="texture_tag")
            if not dpg.does_item_exist("image_tag"):
                dpg.add_image("texture_tag", tag = "image_tag",parent="ShowSequence", width = int(540*1.3), height = int(234*1.3))
            dpg.show_item("ShowSequence")
            dpg.focus_item("ShowSequence")
        except Exception as e:
            print("Exception occurred:", e)


    def setup_main_exp_buttons(self):
        with dpg.window(label="Main Buttons Group", tag="Main_Window",
                          autosize=True, no_move=True, collapsed=True):
            with dpg.group(label="Main Buttons Group", horizontal=True):
                dpg.add_text("Bring Instrument to front:")
                with dpg.group(tag = "focus_group",horizontal=True):
                    pass
            with dpg.group(tag="sequencer_group", horizontal=True):
                pass

        with dpg.window(label="Sequence", tag="ShowSequence",
                        autosize=True, no_move=False, show = False):
            pass
        with dpg.item_handler_registry(tag="left_region_handler"):
            pass
        with dpg.item_handler_registry(tag="right_region_handler"):
            pass
    #Can be used after fixes later
        with dpg.window(label="Viewport Window", tag="Viewport_Window", no_resize=True, no_move=True,width = self.viewport_w, height = self.viewport_h):
            dpg.add_drawlist(tag="full_drawlist", width=800, height=600)
        dpg.set_primary_window("Viewport_Window", True)
        # dpg.draw_line([100, 100], [400, 400], color=[0, 255, 0, 255], thickness=4, parent="full_drawlist")


    def create_console_gui(self):
        """Creates a console GUI window for displaying logs and user inputs."""
        with dpg.window(tag="console_window", label="Console", pos=[20, 20], width=400, height=360):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Clear Console", callback=self.clear_console)
                dpg.add_combo(items=[], tag="command_history", width=120, callback=self.fill_input)
                dpg.add_button(label="Save Logs", callback=self.save_logs)

            # Console log display
            with dpg.child_window(tag="console_output", autosize_x=True, height=270):
                dpg.add_text("Console initialized.", tag="console_log", wrap=800)

            # Input field for sending commands or messages
            with dpg.group(horizontal=True):
                dpg.add_input_text(label="", tag="console_input", width=300)
                dpg.add_button(label="Send", callback=self.send_console_input)
                dpg.add_input_text(label="Cmd", tag="cmd_input", hint="Enter command (e.g. c, sv, mv, sub ELSC, clog e)",
                                   on_enter=True, callback=lambda s, a, u: self.handle_cmd_input())

    def clear_console(self):
        """Clears the console log."""
        if isinstance(sys.stdout, DualOutput):
            sys.stdout.messages.clear()
        dpg.set_value("console_log", "")

    def save_logs(self):
        """Saves the console log to a file."""
        logs = dpg.get_value("console_log")
        with open("console_logs.txt", "w") as file:
            file.write(logs)
        print("Logs saved to console_logs.txt")

    def handle_cmd_input(self):
        command = dpg.get_value("cmd_input").strip()
        outout.run(command)
        dpg.set_value("cmd_input", "")

    def send_console_input(self):
        """Sends the input text to the console."""
        input_text = dpg.get_value("console_input")
        if input_text:
            try:
                # Check if the command is an expression (like `2+2`)
                result = eval(input_text)
                print(f">>> {input_text}")  # Show the executed command
                print(result)  # Print the result to console (DualOutput will capture it)
            except SyntaxError:
                # If it's not an expression, try executing it as a statement
                try:
                    exec(input_text, globals(), locals())
                    print(f">>> {input_text}")  # Show the executed command
                except Exception as e:
                    print(f"Execution Error: {e}")
            except Exception as e:
                print(f"Evaluation Error: {e}")

            self.update_command_history(input_text)
            dpg.set_value("console_input", "")  # Clear the input field


    def update_command_history(self, command):
        """Updates the command history combo box."""
        if command in self.command_history:
            self.command_history.remove(command)  # Remove duplicate before re-adding

        self.command_history.insert(0, command)  # Insert at the top
        if len(self.command_history) > self.MAX_HISTORY:
            self.command_history.pop()  # Remove the oldest entry

        # Update the combo box
        dpg.configure_item("command_history", items=self.command_history)

    def fill_input(self, sender, app_data):
        """Fills the input field with the selected command."""
        dpg.set_value("console_input", app_data)

    def on_detach(self):
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        dpg.destroy_context()





import inspect
import os
import sys
import threading
import time
from typing import Optional

import dearpygui.dearpygui as dpg
import dearpygui.demo as DPGdemo
import glfw
import imgui
import numpy as np
from OpenGL.GL import glGetString
from imgui.integrations.glfw import GlfwRenderer
from pyglet.gl import GL_VERSION, glClearColor, glClear, GL_COLOR_BUFFER_BIT

import HW_wrapper.HW_devices as hw_devices
from Common import Common_Counter_Singletone, KeyboardKeys
from EventDispatcher import EventDispatcher
from ExpSequenceGui import ExpSequenceGui
from HW_GUI import GUI_CLD1011LP as gui_CLD1011LP
from HW_GUI import GUI_Cobolt as gui_Cobolt
from HW_GUI import GUI_Picomotor as gui_Picomotor
from HW_GUI import GUI_RohdeSchwarz as gui_RohdeSchwarz
from HW_GUI import GUI_Smaract as gui_Smaract
from HW_GUI import GUI_Zelux as gui_Zelux
from HW_GUI.GUI_atto_scanner import GUIAttoScanner
from HW_GUI.GUI_highland_eom import GUIHighlandT130
from HW_GUI.GUI_keysight_AWG import GUIKeysight33500B
from HW_GUI.GUI_mattise import GUIMatisse
from HW_GUI.GUI_wavemeter import GUIWavemeter
from HW_GUI.GUI_motor_atto_positioner import GUIMotorAttoPositioner
from HW_GUI.GUI_motors import GUIMotor
from HW_GUI.GUI_sim960PID import GUISIM960
from HWrap_OPX import GUI_OPX
from SystemConfig import SystemType, SystemConfig, load_system_config, run_system_config_gui, Instruments
from Utils.Common import calculate_z_series
from Window import Window_singleton


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
        super().__init__()
        self.system_config: Optional[SystemConfig] = load_system_config()
        self.system_type: Optional[SystemType] = self.system_config.system_type
        # TODO : fix for all systems !!
        simulation = False
        if not self.system_type in [SystemType.HOT_SYSTEM, SystemType.ATTO]:
            simulation = True
        self.exSeq = ExpSequenceGui()
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
            self.exSeq.controls()
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

    def __new__(self):
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
        self.arduino_gui: Optional[GUIArduino] = None
        self.srs_pid_gui: list[GUISIM960] = []
        self.atto_scanner_gui: Optional[GUIMotor] = None
        self.keysight_gui: Optional[GUIKeysight33500B] = None
        self.mattise_gui: Optional[GUIMatisse] = None
        self.mwGUI = None
        self.system_type: Optional[SystemType] = None
        self.system_config: Optional[SystemConfig] = None
        # Initialize instruments based on the system configuration

        self.smaract_thread = None
        self.smaractGUI = None
        self.atto_positioner_gui:Optional[GUIMotor] = None
        self.highland_gui: Optional[GUIHighlandT130] = None
        self.lsr = None
        self.opx = None
        self.cam = None
        self.error = None
        self.picomotor_thread = None
        self.cobolt_thread = None
        self.CLD1011LP_thread = None
        self.GetScreenSize()
        self.CURRENT_KEY = None

    def on_render(self):
        jobs = dpg.get_callback_queue() # retrieves and clears queue
        dpg.run_callbacks(jobs)
        dpg.render_dearpygui_frame()

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

                    if Laser_mode in ["1 - Constant Power","ConstantPower"]:
                        dpg.set_item_label("LaserWin","Cobolt (const pwr mode): actual power "+Laser_power+" mW")
                    elif Laser_mode in ["0 - Constant Current","ConstantCurrent"]:
                        dpg.set_item_label("LaserWin","Cobolt (const current mode): actual Current "+Laser_current+" mA")
                    elif Laser_mode in ["2 - Modulation Mode","PowerModulation"]:
                        dpg.set_item_label("LaserWin","Cobolt (mod. pwr mode): actual power "+Laser_power+" mW")
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
        dpg.setup_dearpygui()
        dpg.show_viewport()
        pass
    def on_attach(self):

        self.startDPG(IsDemo=False,_width=2150,_height=1800)
        self.setup_instruments()

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

        for device in self.system_config.devices:
            instrument = device.instrument
            print(f"loading instrument {instrument.value}")
            try:

                if instrument == Instruments.ROHDE_SCHWARZ:
                    pass
                    # self.mwGUI = gui_RohdeSchwarz.GUI_RS_SGS100a(device.simulation)
                    # dpg.set_item_pos(self.mwGUI.window_tag, [20, y_offset])
                    # y_offset += dpg.get_item_height(self.mwGUI.window_tag) + vertical_spacing

                elif instrument in [Instruments.SMARACT_SLIP, Instruments.SMARACT_SCANNER]:
                    self.smaractGUI = gui_Smaract.GUI_smaract(simulation=device.simulation,
                                                              serial_number=device.serial_number)
                    dpg.set_item_pos(self.smaractGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.smaractGUI.window_tag) + vertical_spacing

                    if not device.simulation:
                        self.smaract_thread = threading.Thread(target=self.render_smaract)
                        self.smaract_thread.start()

                elif instrument == Instruments.CLD1011LP:
                    self.CLD1011LP_gui = gui_CLD1011LP.GUI_CLD1011LP(self.simulation)
                    dpg.set_item_pos(self.CLD1011LP_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.CLD1011LP_gui.window_tag) + vertical_spacing
                    if not self.simulation:
                        self.CLD1011LP_thread = threading.Thread(target=self.render_CLD1011LP)
                        self.CLD1011LP_thread.start()

                elif instrument == Instruments.COBOLT:
                    self.coboltGUI = gui_Cobolt.GUI_Cobolt(device.simulation, com_port = device.com_port)
                    dpg.set_item_pos(self.coboltGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.coboltGUI.window_tag) + vertical_spacing
                    if not device.simulation:
                        self.cobolt_thread = threading.Thread(target=self.render_cobolt)
                        self.cobolt_thread.start()

                elif instrument == Instruments.PICOMOTOR:
                    self.picomotorGUI = gui_Picomotor.GUI_picomotor(simulation=device.simulation)
                    dpg.set_item_pos(self.picomotorGUI.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.picomotorGUI.window_tag) + vertical_spacing

                    if not device.simulation:
                        self.picomotor_thread = threading.Thread(target=self.render_picomotor)
                        self.picomotor_thread.start()

                elif instrument == Instruments.ZELUX:
                    self.cam = gui_Zelux.ZeluxGUI()
                    if len(self.cam.cam.available_cameras) > 0:
                        self.cam.Controls()
                        dpg.set_item_pos(self.cam.window_tag, [self.Monitor_width-dpg.get_item_width(self.cam.window_tag)-vertical_spacing, vertical_spacing])

                elif instrument == Instruments.OPX:
                    self.opx = GUI_OPX(device.simulation)
                    self.opx.controls()
                    dpg.set_item_pos(self.opx.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.opx.window_tag) + vertical_spacing

                elif instrument == Instruments.ATTO_POSITIONER:
                    self.atto_positioner_gui = GUIMotorAttoPositioner(
                        motor=hw_devices.HW_devices().atto_positioner,
                        instrument=Instruments.ATTO_POSITIONER,
                        simulation=device.simulation
                    )
                    dpg.set_item_pos(self.atto_positioner_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.atto_positioner_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.HIGHLAND:
                    self.highland_gui = GUIHighlandT130(
                        device=hw_devices.HW_devices().highland_eom_driver,
                        simulation=device.simulation
                    )
                    dpg.set_item_pos(self.highland_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.highland_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.MATTISE:
                    self.mattise_gui = GUIMatisse(
                        device=hw_devices.HW_devices().matisse_device,
                        simulation=device.simulation
                    )
                    dpg.set_item_pos(self.mattise_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.mattise_gui.window_tag) + vertical_spacing
                elif instrument == Instruments.WAVEMETER:
                    self.wlm_gui = GUIWavemeter(device=hw_devices.HW_devices().wavemeter, instrument=instrument, simulation=device.simulation)
                    dpg.set_item_pos(self.mattise_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.mattise_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.KEYSIGHT_AWG:
                    self.keysight_gui = GUIKeysight33500B(
                        device= hw_devices.HW_devices().keysight_awg_device,
                        simulation=device.simulation
                    )
                    dpg.set_item_pos(self.keysight_gui.window_tag, [20, y_offset])
                    y_offset += dpg.get_item_height(self.keysight_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.ATTO_SCANNER:
                    hw_devices.HW_devices().atto_scanner.connect()
                    self.atto_scanner_gui = GUIAttoScanner(
                        motor= hw_devices.HW_devices().atto_scanner,
                        instrument=Instruments.ATTO_SCANNER,
                        simulation=device.simulation
                    )
                    dpg.set_item_pos(self.atto_scanner_gui.window_tag, [20, 20])
                    y_offset += dpg.get_item_height(self.atto_scanner_gui.window_tag) + vertical_spacing

                elif instrument == Instruments.ARDUINO:
                    self.arduino_gui = GUIArduino(hw_devices.HW_devices().arduino)

                elif instrument == Instruments.SIM960:
                    srs_pid_list=hw_devices.HW_devices().SRS_PID_list
                    matching_device = next(
                        (sim_device for sim_device in srs_pid_list if str(sim_device.slot) == device.ip_address),
                        None  # Default if no match is found
                    )
                    self.srs_pid_gui.append(GUISIM960(
                        sim960=matching_device,
                        simulation=device.simulation
                    ))

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
            is_coarse_pico = self.CURRENT_KEY == KeyboardKeys.ALT_KEY

            # Map the key data to the KeyboardKeys enum
            if key_data in KeyboardKeys._value2member_map_:
                key_data_enum = KeyboardKeys(key_data)
            else:
                return


            # Handle OPX map logic if enabled
            if hasattr(self.opx, 'map') and self.opx.map is not None:
                if self.opx.map.map_keyboard_enable:
                    self.handle_opx_keyboard_movement(key_data_enum, is_coarse)

            # Handle Smaract controls
            if self.CURRENT_KEY in [KeyboardKeys.CTRL_KEY, KeyboardKeys.SHIFT_KEY]:
                self.handle_smaract_controls(key_data_enum, is_coarse)

            # Handle Picomotor controls
            elif self.CURRENT_KEY in [KeyboardKeys.ALT_KEY, KeyboardKeys.Z_KEY]:
                if self.picomotorGUI:
                    print("picomotor key")
                    self.handle_picomotor_controls(key_data_enum, is_coarse_pico)

            # Update the current key pressed
            self.CURRENT_KEY = key_data_enum

        except Exception as ex:
            self.error = f"Unexpected error in keyboard_callback: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def handle_opx_keyboard_movement(self, key_data_enum, is_coarse):
        """Handles keyboard movement for OPX map control."""
        try:
            if self.CURRENT_KEY in [KeyboardKeys.M_KEY, KeyboardKeys.N_KEY]:
                is_coarse = self.CURRENT_KEY == KeyboardKeys.M_KEY  # Determine if coarse mode is active

                if key_data_enum == KeyboardKeys.LEFT_KEY:
                    self.opx_keyboard_map_movement(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.RIGHT_KEY:
                    self.opx_keyboard_map_movement(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.UP_KEY:
                    self.opx_keyboard_map_movement(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.DOWN_KEY:
                    self.opx_keyboard_map_movement(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEDOWN_KEY:
                    self.opx.map.stretch_squeeze_area_marker("stretch_y", is_coarse)  # Stretch vertically (Y) with PageUp
                elif key_data_enum == KeyboardKeys.PAGEUP_KEY:
                    self.opx.map.stretch_squeeze_area_marker("squeeze_y", is_coarse)  # Squeeze vertically (Y) with PageDown
                elif key_data_enum == KeyboardKeys.HOME_KEY:
                    self.opx.map.stretch_squeeze_area_marker("squeeze_x", is_coarse)  # Squeeze horizontally (X) with Home
                elif key_data_enum == KeyboardKeys.END_KEY:
                    self.opx.map.stretch_squeeze_area_marker("stretch_x", is_coarse)  # Stretch horizontally (X) with End
                elif key_data_enum == KeyboardKeys.DEL_KEY:
                    self.delete_active_item()  # Delete active marker or area marker
                elif key_data_enum == KeyboardKeys.INSERT_KEY:
                    self.insert_marker_near_active(duplicate_or_add_area = is_coarse)  # Insert a new marker near the active one & Insert a new area marker based on the active marker
                elif key_data_enum == KeyboardKeys.K_KEY:
                    self.opx.map.move_mode = "marker"
                    # Update the button label to indicate the current state
                    if dpg.does_item_exist("toggle_marker_area"):
                        dpg.set_item_label("toggle_marker_area", "move marker")
                elif key_data_enum == KeyboardKeys.A_KEY:
                    self.opx.map.move_mode = "area_marker"
                    # Update the button label to indicate the current state
                    if dpg.does_item_exist("toggle_marker_area"):
                        dpg.set_item_label("toggle_marker_area", "move area")
                elif key_data_enum == KeyboardKeys.PLUS_KEY:
                    if self.opx.map.move_mode == "marker":
                        self.opx.map.act_marker(self.opx.map.active_marker_index + 1)
                    else:
                        self.opx.map.act_area_marker(self.opx.map.active_area_marker_index + 1)
                elif key_data_enum == KeyboardKeys.MINUS_KEY:
                    if self.opx.move_mode == "marker":
                        self.opx.map.act_marker(self.opx.active_marker_index - 1)
                    else:
                        self.opx.map.act_area_marker(self.opx.active_area_marker_index - 1)
                elif key_data_enum == KeyboardKeys.U_KEY:
                    self.opx.map.update_scan_area_marker(self.opx.active_area_marker_index)
                elif key_data_enum == KeyboardKeys.P_KEY:
                    self.opx.map.mark_point_on_map()
                elif key_data_enum == KeyboardKeys.G_KEY:
                    self.opx.map.go_to_marker()
                    if not is_coarse:
                        self.opx.map.active_marker_index += 1

                        # If the active_marker_index exceeds the number of markers, wrap around to the first marker
                        if self.opx.map.active_marker_index >= len(self.opx.map.markers):
                            self.opx.map.active_marker_index = 0


        except Exception as ex:
            self.error = f"Error in handle_opx_keyboard_movement: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def insert_marker_near_active(self, duplicate_or_add_area=False):
        """Insert a new marker or area marker just above the active one in the list and reactivate the original active one."""
        try:
            if self.opx.move_mode == "marker":
                # Insert a new area marker based on the active marker
                if hasattr(self.opx.map, 'active_marker_index') and 0 <= self.opx.map.active_marker_index < len(
                        self.opx.map.markers):
                    # Store the original active marker index
                    original_active_marker_index = self.opx.map.active_marker_index

                    # Get the active marker's current position
                    _, _, active_coords, active_position = self.opx.map.markers[original_active_marker_index]
                    active_x, active_y = active_position

                    if dpg.does_item_exist("map_image"):
                        item_x, item_y = dpg.get_item_pos("map_image")
                    else:
                        print("map_image does not exist")
                        return

                    if duplicate_or_add_area:
                        # Insert the new marker in the list just above the active marker
                        new_marker_index = original_active_marker_index  # Inserting above means inserting at the current index

                        # Define the offset for the new marker (based on active marker)
                        offset = 2  # Adjust this offset as needed
                        new_x = active_x + offset
                        new_y = active_y + offset

                        # Calculate the relative position of the new marker on the map
                        relative_x = (new_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                        relative_y = (new_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
                        z_evaluation = float(
                            calculate_z_series(self.opx.ZCalibrationData, np.array(int(relative_x * 1e6)),
                                               int(relative_y * 1e6))) / 1e6

                        # Ensure no marker with the same coordinates already exists
                        if self.opx.marker_exists((relative_x, relative_y)):
                            print("A marker with the same relative coordinates already exists.")
                            return

                        # Create the new marker data
                        new_marker_tag = f"marker_{len(self.opx.map.markers)}"
                        new_text_tag = f"text_{len(self.opx.map.markers)}"
                        new_marker_data = (
                            new_marker_tag, new_text_tag, (relative_x, relative_y, z_evaluation), (new_x, new_y))

                        # Insert the new marker just above the active marker in the markers list
                        self.opx.map.markers.insert(new_marker_index, new_marker_data)

                        # Add the new marker to the map
                        dpg.draw_circle(center=(new_x, new_y), radius=2, color=(255, 0, 0, 255), fill=(255, 0, 0, 100),
                                        parent="map_draw_layer", tag=new_marker_tag)
                        coord_text = f"({relative_x:.2f}, {relative_y:.2f}, {z_evaluation:.2f})"
                        dpg.draw_text(pos=(new_x, new_y), text=coord_text, color=self.opx.text_color, size=14,
                                      parent="map_draw_layer", tag=new_text_tag)

                        # Update the markers table to reflect the change
                        self.opx.map.update_markers_table()

                        # Reactivate the original active marker
                        self.opx.map.active_marker_index = original_active_marker_index + 1  # The original marker is now one index down
                        self.opx.map.act_marker(self.opx.map.active_marker_index)

                        print(f"New marker added in the list just above the active marker at index {new_marker_index}.")
                    else:
                        # Use start_rectangle_query to create an area marker between two markers
                        self.opx.map.start_rectangle_query()

                else:
                    print("No active marker to insert a new marker nearby.")

            elif self.opx.move_mode == "area_marker":
                # Insert a new area marker near the active area marker
                if hasattr(self.opx, 'active_area_marker_index') and 0 <= self.opx.active_area_marker_index < len(
                        self.opx.area_markers):
                    # Store the original active area marker index
                    original_active_area_marker_index = self.opx.active_area_marker_index

                    # Get the active area marker's current position
                    min_x, min_y, max_x, max_y = self.opx.area_markers[original_active_area_marker_index]

                    if dpg.does_item_exist("map_image"):
                        item_x, item_y = dpg.get_item_pos("map_image")
                    else:
                        print("map_image does not exist")
                        return

                    if duplicate_or_add_area:
                        # Insert the new area marker in the list just above the active one
                        new_area_marker_index = original_active_area_marker_index  # Inserting above means using the current index

                        # Define the offset for the new area marker
                        offset = 2  # Adjust this offset as needed
                        new_min_x = min_x + offset
                        new_min_y = min_y + offset
                        new_max_x = max_x + offset
                        new_max_y = max_y + offset

                        # Calculate the relative coordinates for the area marker
                        relative_min_x = (new_min_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value(
                            "MapFactorX")
                        relative_min_y = (new_min_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value(
                            "MapFactorY")
                        relative_max_x = (new_max_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value(
                            "MapFactorX")
                        relative_max_y = (new_max_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value(
                            "MapFactorY")

                        # Add the new area marker to the list
                        new_area_marker_data = (relative_min_x, relative_min_y, relative_max_x, relative_max_y)
                        self.opx.area_markers.insert(new_area_marker_index, new_area_marker_data)

                        # Draw the new area marker on the map
                        dpg.draw_rectangle(pmin=(new_min_x, new_min_y), pmax=(new_max_x, new_max_y),
                                           color=(0, 255, 0, 255), thickness=2, parent="map_draw_layer",
                                           tag=f"query_rectangle_{new_area_marker_index}")

                        # Update the markers table after adding the new area marker
                        self.opx.update_markers_table()

                        # Reactivate the original active area marker
                        self.opx.active_area_marker_index = original_active_area_marker_index + 1  # The original area marker is now one index down
                        self.opx.act_area_marker(self.opx.active_area_marker_index)

                        print(
                            f"New area marker added in the list just above the active area marker at index {new_area_marker_index}.")
                else:
                    print("No active area marker to insert a new area marker nearby.")

        except Exception as e:
            print(f"Error in insert_marker_near_active: {e}")

    def delete_active_item(self):
        """Delete the active marker or area marker based on the current move mode."""
        if self.opx.map.move_mode == "marker":
            if hasattr(self.opx.map, 'active_marker_index') and 0 <= self.opx.map.active_marker_index < len(self.opx.map.markers):
                self.opx.map.delete_marker(self.opx.active_marker_index)
            else:
                print("No active marker to delete.")
        elif self.opx.map.move_mode == "area_marker":
            if hasattr(self.opx.map, 'active_area_marker_index') and 0 <= self.opx.map.active_area_marker_index < len(
                    self.opx.map.area_markers):
                self.opx.map.delete_area_marker(self.opx.map.active_area_marker_index)
            else:
                print("No active area marker to delete.")

    def handle_smaract_controls(self, key_data_enum, is_coarse):
        """Handles keyboard input for Smaract device controls."""
        try:
            if key_data_enum == KeyboardKeys.S_KEY: # Save all even if keyboard disabled
                #pdb.set_trace()  # Insert a manual breakpoint
                self.smaractGUI.save_log_points()
                self.picomotorGUI.save_log_points()
                self.smaractGUI.save_pos()
                if hasattr(self.opx, 'map') and self.opx.map is not None:
                    self.opx.map.save_map_parameters()
                return

            if self.smaractGUI.dev.KeyboardEnabled:
                if key_data_enum == KeyboardKeys.SPACE_KEY:
                    print('Logging point')
                    self.smaract_log_points()
                elif key_data_enum == KeyboardKeys.X_KEY:
                    print('Deleting point')
                    self.smaract_del_points()
                elif key_data_enum == KeyboardKeys.LEFT_KEY:
                    self.smaract_keyboard_movement(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.RIGHT_KEY:
                    self.smaract_keyboard_movement(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.UP_KEY:
                    self.smaract_keyboard_movement(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.DOWN_KEY:
                    self.smaract_keyboard_movement(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEUP_KEY:
                    self.smaract_keyboard_movement(2, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEDOWN_KEY:
                    self.smaract_keyboard_movement(2, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.INSERT_KEY:
                    self.smaract_keyboard_move_uv(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.DEL_KEY:
                    self.smaract_keyboard_move_uv(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.HOME_KEY:
                    self.smaract_keyboard_move_uv(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.END_KEY:
                    self.smaract_keyboard_move_uv(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.M_KEY:
                    print("Enabling map keyboard shortcuts")
                    self.opx.map.toggle_map_keyboard()

        except Exception as ex:
            self.error = f"Error in handle_smaract_controls: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def handle_picomotor_controls(self, key_data_enum, is_coarse):
        """Handles keyboard input for Picomotor controls."""
        try:
            if self.picomotorGUI.dev.KeyboardEnabled:
                if key_data_enum == KeyboardKeys.LEFT_KEY:
                    self.pico_keyboard_movement(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.RIGHT_KEY:
                    self.pico_keyboard_movement(1, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.UP_KEY:
                    self.pico_keyboard_movement(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.DOWN_KEY:
                    self.pico_keyboard_movement(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEUP_KEY:
                    self.pico_keyboard_movement(2, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.PAGEDOWN_KEY:
                    self.pico_keyboard_movement(2, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.BACK_KEY:
                    current_state = dpg.get_item_configuration("LaserWin")["collapsed"]
                    dpg.configure_item("LaserWin", collapsed=not current_state)
                elif key_data_enum == KeyboardKeys.INSERT_KEY:
                    self.pico_keyboard_move_uv(0, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.DEL_KEY:
                    self.pico_keyboard_move_uv(0, -1, is_coarse)
                elif key_data_enum == KeyboardKeys.HOME_KEY:
                    self.pico_keyboard_move_uv(1, 1, is_coarse)
                elif key_data_enum == KeyboardKeys.END_KEY:
                    self.pico_keyboard_move_uv(1, -1, is_coarse)

        except Exception as ex:
            self.error = f"Error in handle_picomotor_controls: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
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
                print("Small step")
                self.smaractGUI.dev.MoveRelative(ax,direction*self.smaractGUI.dev.AxesKeyBoardSmallStep[ax])
            else:
                print("Large step")
                print(self.smaractGUI.dev.AxesKeyBoardLargeStep[ax])
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

        # Create a theme to highlight the new container (group or child window)
        with dpg.theme(tag="highlighted_header_theme"):
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (255, 255, 0), category=dpg.mvThemeCat_Core)  # Black text





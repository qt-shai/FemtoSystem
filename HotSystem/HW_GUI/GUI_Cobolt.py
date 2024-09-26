import dearpygui.dearpygui as dpg
import  HW_wrapper
import serial.tools.list_ports
from Common import DpgThemes
import HW_wrapper.Wrapper_Cobolt

class GUI_Cobolt(): #todo: support several devices
    # init parameters
    def __init__(self, simulation: bool = False):
        
        self.laser=[]
        self.available_ports = []
        self.Port = []
        self.isConnected=False
        self.items_list = [ # List of controllable items to enable/disable
                "Turn_ON_OFF",
                "ON_OFF_Modulation",
                "Laser Mode combo",
                "power_input",
                "current_input",
                "Modulation_power_input"
            ]
        
        # Maximum current and power parameters
        self.Max_current = 227 # mA
        self.Max_power = 85 # mW
        
        # Get the list of available serial ports
        self.ports = serial.tools.list_ports.comports()        
        self.selected_port = 0 # Default to the first port
        
        # Create a list of port descriptions for the combo box
        Ports_str=[]
        if len(self.ports) == 0:
            Ports_str = ["empty"]
        else:
            for idx in range(len(self.ports)):
                Ports_str.append(self.ports[idx].device + ", " + self.ports[idx].description)

        # Define GUI themes
        themes = DpgThemes()
        yellow_theme = themes.color_theme((55, 55, 0), (255, 255, 255))        
        win_theme = themes.color_theme([0, 25, 25, 255], (255, 255, 255))
        green_theme = themes.color_theme([0, 55, 0, 255], (255, 255, 255))

        # Define the layout of the GUI
        Child_Width=180
        with dpg.window(tag="LaserWin", label="Cobolt Laser, disconnected", no_title_bar=False, height=440, width=1600,collapsed=True):
            with dpg.group(tag="Indicators",horizontal=True):  
                # Column 1: Connection settings and mode selection
                with dpg.group(horizontal=False, tag="column 1",width=Child_Width):
                    dpg.add_text("Connection", color=(255, 255, 0))
                    with dpg.group(horizontal=True):
                        dpg.add_combo(items=Ports_str, tag = "Ports", callback=self.cmbPort,default_value = Ports_str[0],width=150)
                        dpg.add_button(label="Connect",tag="Laser Connect",callback = self.btnConnect,width=50)

                    dpg.add_text(default_value="Port ---",tag="Laser Port")
                    with dpg.group(horizontal=True):
                        dpg.add_text(default_value="Not connected",tag="Laser ON OFF",color=(255, 50, 50))
                        dpg.add_checkbox(tag="Turn_ON_OFF",callback=self.cbxTurn_ON_OFF)
                    dpg.add_text("Laser mode", color=(255, 255, 0))
                    dpg.add_combo(items=["Constant current", "Constant power","Digital Modulation","Analog Modulation"], tag="Laser Mode combo", callback=self.btnUpdateMode, width=150)
                dpg.bind_item_theme(dpg.last_item(), green_theme)
                # Column 2: Laser information display
                with dpg.group(horizontal=False, tag="column 2",width=Child_Width):
                    # with dpg.child_window(border = True):
                    dpg.add_text("Laser Information", color=(255, 255, 0))
                    dpg.add_text(default_value="Power ---",tag="Laser Power")
                    dpg.add_text(default_value="Mod. power ---",tag="Laser Mod Power")
                    dpg.add_text(default_value="Current ---",tag="Laser Current")
                    dpg.add_text(default_value="TEC temp. ---",tag="Laser TEC")
                    dpg.add_text(default_value="Base Plate temp. ---",tag="Laser Base")
                    dpg.add_text(default_value="Mode: ---",tag="Laser Mode")
                    dpg.add_text(default_value="State: ---",tag="Laser State")

                # Column 3: Laser settings controls
                with dpg.group(horizontal=False, tag="column 3",width=Child_Width+140):  
                    # with dpg.child_window(border = True):
                    dpg.add_text("Settings", color=(255, 255, 0))
                    with dpg.group(tag="controls"):
                        with dpg.group(horizontal=True):
                            dpg.add_text("Set Power",tag="txt")
                            dpg.add_input_float(label="",default_value=0, callback = self.inputPower,tag="power_input",indent=170,format='%.1f',width=30)
                            dpg.add_text("mW   ")
                        with dpg.group(horizontal=True):
                            dpg.add_text("Set Current")
                            dpg.add_input_float(label="",default_value=0, callback = self.inputCurrent,tag="current_input",indent=170,format ='%.1f',width=30)
                            dpg.add_text("mA   ")
                        with dpg.group(horizontal=True):
                            dpg.add_text("Set Mod. Power")
                            dpg.add_input_float(label="",default_value=0, callback = self.inputModulationPower,tag="Modulation_power_input",indent=170,format='%.1f',width=30)
                            dpg.add_text("mW   ")

                # Column 4: Modulation settings
                # with dpg.child_window(border = True):
                with dpg.group(horizontal=False, tag="column 4",width=Child_Width):
                    dpg.add_text("Modulation", color=(255, 255, 0))
                    with dpg.group(horizontal=True):
                        dpg.add_text("Analog Mod.")
                        dpg.add_checkbox(tag="Analog_Modulation_cbx",default_value=False,indent=180)
                    with dpg.group(horizontal=True):
                        dpg.add_text("Digital Mod.")
                        dpg.add_checkbox(tag="Digital_Modulation_cbx",default_value=False,indent=180)
                    with dpg.group(horizontal=True):
                        dpg.add_text("ON/OFF Mod.")
                        dpg.add_checkbox(tag="ON_OFF_Modulation",default_value=False,callback=self.cbxON_OFF_MOdulation,indent=180)

        # Bind themes to the main window and controls
        # dpg.bind_item_theme("LaserWin", win_theme)
        dpg.bind_item_theme(item="controls", theme=yellow_theme)       
        for item in self.items_list:
            dpg.disable_item(item) # Disable controls initially until connected
        
        # Handle simulation mode    
        self.simulation = simulation
        if not simulation:            
            self.btnConnect() # Attempt to connect automatically if not in simulation mode
            
    # Handles the ON/OFF modulation checkbox toggle
    def cbxOnOffModulation(self,app_data,user_data):
        try:
            self.laser.on_off_modulation(int(user_data))
        except AttributeError:
            print("Laser object does not support ON/OFF modulation")
        except Exception as e:
            print(f"Error in cbxOnOffModulation: {e}")    
    
    # Handles input power change
    def inputPower(self, app_data, user_data):
        try:
            if user_data>self.Max_power:
                user_data=self.Max_power 
            elif user_data<0:
                user_data=0   
            self.laser.set_power(user_data)
        except AttributeError:
            print("Laser object does not support setting power")
        except Exception as e:
            print(f"Error in inputPower: {e}")
    
    # Handles input current change        
    def inputCurrent(self, app_data, user_data):    
        try:
            if user_data>self.Max_current:
                user_data=self.Max_current 
            elif user_data<0:
                user_data=0     
            self.laser.set_current(user_data*1e3) # for cobolt 06 or 08 it expect Amps - we send mAmps
        except AttributeError:
            print("Laser object does not support setting current")
        except Exception as e:
            print(f"Error in inputCurrent: {e}")
        
    # Handles input modulation power change
    def inputModulationPower(self, app_data, user_data):
        try:
             # Ensure the modulation power is within the valid range
            if user_data>self.Max_power:
                user_data=self.Max_power 
            elif user_data<0:
                user_data=0
            # Set the modulation power on the laser
            self.laser.set_modulation_power(user_data)
        except AttributeError:
            print("Laser object does not support setting modulation power")
        except Exception as e:
            print(f"Error in inputModulationPower: {e}")
    
    # Handles the selection of the serial port from the combo box
    def cmbPort(self,app_data,user_data):
        try:
            # Extract the port from the selected string (first 4 characters)
            self.Port=user_data[0:4]
        except Exception as e:
            print(f"Error in cmbPort: {e}")
    
    # Handles the connection and disconnection of the laser
    def btnConnect(self):
        if self.isConnected:
            print("Disconnecting..")
            try:
                # Attempt to disconnect the laser
                self.laser.disconnect()
                self.isConnected=False
                dpg.set_value("Laser Port","Port ---")
                dpg.set_value("Laser ON OFF","Not connected")
                dpg.set_value("Laser Mode","Mode ---")     
                # Disable control items since the laser is disconnected       
                for item in self.items_list:
                    dpg.disable_item(item)
                dpg.set_item_label("Laser Connect","Connect")
            except Exception as e:
                print(f"Error during disconnection: {e}")
        else:            
            self.Port=dpg.get_value("Ports")[0:4]
            dpg.set_item_label("Laser Connect","Connecting to "+self.Port+"..")
            try: 
                # Attempt to connect to the laser
                self.laser= HW_wrapper.Wrapper_Cobolt.Cobolt06MLD(port=self.Port)
                dpg.set_value("Laser Port","Connected to " + str(self.laser.address.port))
                self.isConnected=self.laser.isConnected #True
                # Enable control items since the laser is connected
                for item in self.items_list:
                    dpg.enable_item(item)
                dpg.set_item_label("Laser Connect","Disconnect")
            except Exception as err:
                print(f"Error during connection: {err}")
                dpg.set_item_label("Laser Connect","Connection error")
    
    # Handles updating the laser mode based on the selected combo box option 
    def btnUpdateMode(self,app_data,user_data):
        try:
            if user_data=="Constant current":
                print("Switching to constant current")
                self.laser.analog_modulation(0)
                self.laser.digital_modulation(0)
                self.laser.constant_current()
            elif user_data=="Constant power":
                print("Switching to constant power")
                self.laser.analog_modulation(0)
                self.laser.digital_modulation(0)
                self.laser.constant_power()
            elif user_data == "Digital Modulation":
                print("Switching to constant power")
                self.laser.modulation_mode()
                self.laser.analog_modulation(0)
                self.laser.digital_modulation(1)
            elif user_data == "Analog Modulation":
                print("Switching to constant power")
                self.laser.modulation_mode()
                self.laser.digital_modulation(0)
                self.laser.analog_modulation(1)
        except AttributeError:
            print("Laser object does not support the selected mode")
        except Exception as e:
            print(f"Error in btnUpdateMode: {e}")
        
    # Handles the ON/OFF modulation checkbox toggle
    def cbxON_OFF_MOdulation(self,app_data,user_data):
        try:
            self.laser.on_off_modulation(int(user_data))
        except AttributeError:
            print("Laser object does not support ON/OFF modulation")
        except Exception as e:
            print(f"Error in cbxON_OFF_MOdulation: {e}")
    
    # Handles the laser ON/OFF checkbox toggle   
    def cbxTurn_ON_OFF(self,app_data,user_data):
        try:
            if user_data:
                self.laser.turn_on()
            else:
                self.laser.turn_off()
        except AttributeError:
            print("Laser object does not support turning on/off")
        except Exception as e:
            print(f"Error in cbxTurn_ON_OFF: {e}")
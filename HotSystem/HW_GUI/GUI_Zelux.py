#from ECM import *
from ImGuiwrappedMethods import *
from Common import *
from HW_wrapper import HW_devices as hw_devices
from Arduino_controlled_motor import FilterFlipperController

class ZeluxGUI():
    def __init__(self):
        self.window_tag = "Zelux Window"
        self.HW = hw_devices.HW_devices()
        self.cam = self.HW.camera
        self.flipper = None

        self.AddNewWindow()

    def StartLive(self):
        global stopBtn
        self.cam.constantGrabbing = True
        self.LiveTh = threading.Thread(target=self.cam.LiveTh)
        self.LiveTh.setDaemon(True)
        self.LiveTh.start()
        stopBtn = dpg.add_button(label="Stop Live", before="btnStartLive", parent=self.window_tag,tag="btnStopLive", callback=self.StopLive)
        dpg.delete_item("btnStartLive")
        # dpg.delete_item("btnSave")
        dpg.bind_item_theme(item = "btnStopLive", theme = "btnRedTheme")

    def StopLive(self):
        global startBtn
        self.cam.constantGrabbing = False
        self.LiveTh.join()
        startBtn = dpg.add_button(label="Start Live", before="btnStopLive",parent=self.window_tag,tag="btnStartLive", callback=self.StartLive)
        # dpg.add_button(label="Save Image", before="btnStopLive", callback=self.cam.saveImage,tag="btnSave", parent="groupZeluxControls")
        dpg.delete_item("btnStopLive")
        dpg.bind_item_theme(item = "btnStartLive", theme = "btnGreenTheme")

    def UpdateImage(self):
        window_size = dpg.get_item_width(self.window_tag), dpg.get_item_height(self.window_tag)
        _width, _height = window_size
        _width = _width * 0.9
        _height = _height*0.9

        
        # Update image dimensions to match the new window size
        dpg.set_item_width("image_id", _width)
        dpg.set_item_height("image_id", _height)

        dpg.delete_item("image_drawlist")
        dpg.add_drawlist(tag="image_drawlist", width=_width, height=_width*self.cam.ratio,parent=self.window_tag)
        dpg.draw_image(texture_tag="image_id", pmin=(0, 0), pmax=(_width, _width*self.cam.ratio), uv_min=(0, 0), uv_max=(1, 1),parent="image_drawlist")
        dpg.set_value("image_id", self.cam.lateset_image_buffer)
        
    def UpdateExposure(sender, app_data, user_data):
        # a = dpg.get_value(sender)
        sender.cam.SetExposureTime(int(user_data*1e3))
        time.sleep(0.001)
        dpg.set_value(item = "slideExposure", value=sender.cam.camera.exposure_time_us/1e3)
        print("Actual exposure time: " + str(sender.cam.camera.exposure_time_us/1e3 )+ "milisecond")
        pass

    def UpdateGain(sender, app_data, user_data):
        # a = dpg.get_value(sender)
        sender.cam.SetGain(user_data)
        time.sleep(0.001)
        dpg.set_value(item = "slideGain", value=sender.cam.camera.convert_gain_to_decibels(sender.cam.camera.gain))
        print("Actual gain time: " + str(sender.cam.camera.convert_gain_to_decibels(sender.cam.camera.gain))+ "db")
        pass
    
    def AddNewWindow(self, _width = 800):

        _width = 1000
        
        with dpg.window(label=self.window_tag, tag=self.window_tag, no_title_bar = False,
                        pos = [15,15],
                        width=int(_width*1.0), 
                        height=int(_width*self.cam.ratio*1.2)):
                        pass
            
               
    def DeleteMainWindow(self):
        dpg.delete_item(item=self.window_tag)
        pass
    
    def GUI_controls(self, isConnected = False, _width = 800):
        dpg.delete_item("groupZeluxControls")
        if isConnected:
            dpg.add_group(tag="groupZeluxControls", parent=self.window_tag,horizontal=True)
            dpg.add_button(label="Start Live", callback=self.StartLive,tag="btnStartLive", parent="groupZeluxControls")
            dpg.add_button(label="Save Image", callback=self.cam.saveImage,tag="btnSave", parent="groupZeluxControls")
            dpg.add_checkbox(label="Intensity Correction", tag="chkbox_intensity_correction", parent="chkbox_group",
                             callback=self.Move_flipper, indent=-1, default_value=self.flipper.position)

            dpg.bind_item_theme(item = "btnStartLive", theme = "btnGreenTheme")
            dpg.bind_item_theme(item = "btnSave", theme = "btnBlueTheme")


            minExp = min(self.cam.camera.exposure_time_range_us)/1e3
            maxExp = max(self.cam.camera.exposure_time_range_us)/1e3
            slider_exposure = dpg.add_slider_int(label="exposure", tag="slideExposure", parent="groupZeluxControls", 
                                                    width=100, callback=self.UpdateExposure,
                                                    default_value=self.cam.camera.exposure_time_us/1e3,
                                                    min_value= minExp if minExp >0 else 1,
                                                    max_value= maxExp if maxExp <1000 else 1000)
            
            minGain = self.cam.camera.convert_gain_to_decibels(min(self.cam.camera.gain_range))
            maxGain = self.cam.camera.convert_gain_to_decibels(max(self.cam.camera.gain_range))
            slider_gain = dpg.add_slider_int(label="gain", tag="slideGain", parent="groupZeluxControls",
                                                    width=100, callback=self.UpdateGain,
                                                    default_value=self.cam.camera.convert_gain_to_decibels(self.cam.camera.gain),
                                                    min_value= minGain,
                                                    max_value= maxGain)

            # dpg.add_drawlist(tag="image_drawlist", width=_width, height=_width*self.cam.ratio,parent=self.window_tag)
            # dpg.draw_image(texture_tag="image_id", pmin=(0, 0), pmax=(_width, _width*self.cam.ratio), uv_min=(0, 0), uv_max=(1, 1),parent="image_drawlist")

        else:
            dpg.add_group(tag="ZeluxControls", parent=self.window_tag,horizontal=False)
            dpg.add_text("camera is probably not connected")

    def Controls(self):
        dpg.add_group(tag="ZeluxControls", parent=self.window_tag,horizontal=True)

        if len(self.cam.available_cameras) < 1:
            self.GUI_controls(isConnected = False, _width = 700)
            pass
        else:
            with dpg.texture_registry(tag="image_tag", show=False):
                dpg.add_dynamic_texture(width=self.cam.camera.image_width_pixels, 
                                height=self.cam.camera.image_height_pixels, 
                                default_value=self.cam.lateset_image_buffer, 
                                tag="image_id", parent="image_tag")

            self.GUI_controls(isConnected = True)
            pass


    def Move_flipper(self):
        if self.flipper == None:
            self.flipper = FilterFlipperController(serial_no="37008855")
            self.flipper.connect()
        self.flipper.toggle()
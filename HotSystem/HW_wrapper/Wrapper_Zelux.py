import os
from typing import List

import numpy as np
from matplotlib import pyplot as plt
from Common import getCurrentTimeStamp, increase_brightness
import SystemConfig.system_config as config
from Zelux_dll_setup import configure_path
configure_path()
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK


class Zelux:

    @staticmethod
    def get_available_devices() -> List[config.Device]:
        """
        Static method to return available devices as instances of the Device class.
        This method uses ctl.FindDevices() to gather information about available devices.
        Missing information (IP, MAC, serial) is replaced with 'N/A'.

        :return: A list of Device instances.
        """
        available_devices = []
        try:
            sdk = TLCameraSDK()
            available_cameras = sdk.discover_available_cameras()
            if len(available_cameras) > 0:
                for device in available_cameras:
                    available_devices.append(config.Device(
                        instrument=config.Instruments.ZELUX,
                        ip_address='N/A',
                        mac_address='N/A',
                        serial_number=device
                    ))

        except Exception as e:
            print(f"Could not find Zelux camera. Error: {e}")
        return available_devices

    def __init__(self, simulation : bool = False):
        self.simulation = simulation
        if simulation:
            self.available_cameras = []
            self.imageNotes = ""
            return
        try:
            # if on Windows, use the provided setup script to add the DLLs folder to the PATH
            self.imageNotes = ""
        except ImportError:
            configure_path = None
        pass
        
        self.GetAvailableCamera()
        if len(self.available_cameras) < 1:
            pass
        else:
            self.GetInitialParams()
    
    def GetInitialParams(self):
        # self.exposureTime = self.camera.exposure_time_us #msec
        self.gain_db = self.camera.convert_gain_to_decibels(self.camera.gain)
        self.SingleShot()
        self.constantGrabbing = False
        self.ratio = self.camera.image_height_pixels/self.camera.image_width_pixels

    def LiveTh(self):
        self.PrepareForShot()
        while (self.constantGrabbing):
            self.GrabFrame()
        self.StopGrabbing()

    def GetAvailableCamera(self):
        self.sdk = TLCameraSDK()
        self.available_cameras = self.sdk.discover_available_cameras()
        if len(self.available_cameras) < 1:
            print("no cameras detected")
        else:
            self.camera = self.sdk.open_camera(self.available_cameras[0])

    def SingleShot(self):
        self.constantGrabbing = False
        self.PrepareForShot()
        self.GrabFrame()
        self.StopGrabbing()
    
    def PrepareForShot(self):
        self.camera.frames_per_trigger_zero_for_unlimited = 0  # start camera in continuous mode
        self.camera.image_poll_timeout_ms = 1000  # 1 second polling timeout
        self.camera.arm(2) # what does 2 means?
        self.camera.issue_software_trigger()
    
    def GrabFrame(self):
        frame = self.camera.get_pending_frame_or_null()
        if frame is not None:
            # print("frame #{} received!".format(frame.frame_count))

            frame.image_buffer  # .../ perform operations using the data from image_buffer

            #  NOTE: frame.image_buffer is a temporary memory buffer that may be overwritten during the next call
            #        to get_pending_frame_or_null. The following line makes a deep copy of the image data:
            buf = np.copy(frame.image_buffer)

            # buf = buf.astype(np.float16) 
            buf = (buf/255.0).reshape(-1)
            buf = np.array([buf,buf,buf,[1.0]*len(buf)])
            buf = buf.transpose()
            self.lateset_image_buffer = buf.reshape(-1)
        else:
            print("timeout reached during polling, program exiting...")

    def saveImage(self):
        width=self.camera.image_width_pixels 
        height=self.camera.image_height_pixels 
        image=self.lateset_image_buffer
        # Reshape the vector into a 2D array
        image =image.reshape(height, width,4)
        I = image[:,:,3]
        r = image[:,:,0]
        g = image[:,:,1]
        b = image[:,:,2]
        rgb_image = np.zeros((height, width, 3))
        rgb_image[:,:,0] = r * I * 1.0
        rgb_image[:,:,1] = g * I * 1.0
        rgb_image[:,:,2] = b * I * 1.0

        max_pixel = rgb_image.max()
        if (max_pixel>1.0):
            rgb_image = rgb_image/max_pixel

        # Display RGB image
        # plt.imshow(image, cmap='gray')  # You can choose the colormap as per your requirement
        # plt.imshow(rgb_image)
        # plt.axis('off')
        # plt.close() # close figure

        # todo: change file name based on timestamp
        folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/Images/'
        if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
            os.makedirs(folder_path)
        timeStamp = getCurrentTimeStamp()
        plt.imsave(folder_path + timeStamp + '_'+ self.imageNotes +'.png', rgb_image) # save image to png
        plt.imsave(folder_path + 'Last_Image.png', rgb_image) # save image to png
        increase_brightness(folder_path + "Last_Image.png",folder_path + "Zelux_Last_Image.png", 10)

    def StopGrabbing(self):
        self.camera.disarm()
        self.disposeRequired = False

    def SetGain(self, db_gain = 6.0): # in db
        if self.camera.gain_range.max > 0:
           gain_index = self.camera.convert_decibels_to_gain(db_gain)
           self.camera.gain = gain_index
        #    self.gain_db = db_gain
           print(f"Set camera gain to {self.camera.convert_gain_to_decibels(self.camera.gain)} db")

    def SetExposureTime(self, val = 53): #micro seconds
        self.camera.exposure_time_us = val
        # self.exposureTime = self.camera.exposure_time_us

    def SetROI(self, roi = (100, 100, 600, 600)):
        self.camera.roi = roi  # set roi to be at origin point (100, 100) with a width & height of 500



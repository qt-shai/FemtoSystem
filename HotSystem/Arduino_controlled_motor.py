import clr
import time

# Load the necessary .NET assemblies.
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.FilterFlipperCLI.dll")

from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.FilterFlipperCLI import *
from System import UInt32

class FilterFlipperController:
    """Class representing a Thorlabs Filter Flipper controller."""

    def __init__(self, serial_no: str = "37008855"):
        self.serial_no = serial_no
        self.settings_timeout = 10000
        self.op_timeout = 60000
        self.polling_rate = 250

        # Build the device list.
        DeviceManagerCLI.BuildDeviceList()

        # Create the device instance.
        self.device = FilterFlipper.CreateFilterFlipper(self.serial_no)

    def connect(self):
        try:
            self.device.Connect(self.serial_no)
            # Wait for the device settings to initialize.
            if not self.device.IsSettingsInitialized():
                self.device.WaitForSettingsInitialized(self.settings_timeout)
                if not self.device.IsSettingsInitialized():
                    raise Exception("Device settings failed to initialize.")

            # Start polling and enable the device.
            self.device.StartPolling(self.polling_rate)
            time.sleep(0.25)
            self.device.EnableDevice()
            time.sleep(0.25)
            print("Device connected and enabled.")
        except Exception as e:
            print("Error during device connection:", e)

    def get_device_info(self):
        try:
            info = self.device.GetDeviceInfo()
            print("Device Description:", info.Description)
            return info
        except Exception as e:
            print("Error retrieving device information:", e)

    def home(self):
        try:
            print("Homing Device...")
            self.device.Home(self.op_timeout)
            print("Homing completed.")
        except Exception as e:
            print("Error during homing:", e)

    def set_position(self, position: int):
        try:
            pos_val = UInt32(position)
            print(f"Moving to position: {pos_val}")
            self.device.SetPosition(pos_val, self.op_timeout)
            print("Position set.")
        except Exception as e:
            print("Error setting position:", e)

    def disconnect(self):
        try:
            self.device.DisableDevice()
            self.device.StopPolling()
            self.device.Disconnect()
            print("Device disconnected.")
        except Exception as e:
            print("Error during disconnect:", e)

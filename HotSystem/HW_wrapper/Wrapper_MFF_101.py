import clr
import time
import inspect

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

    def __init__(self, serial_number: str = "37009011"):
        self.serial_no = serial_number
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

    def is_busy(self) -> bool:
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Device is busy: {self.device.IsDeviceBusy}.")
        return self.device.IsDeviceBusy

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

    def toggle(self):
        try:
            # self.connect()
            self.get_device_info()
            print(f"Device serial Number: {self.serial_no}")

            # Retrieve the current position.
            current_position = self.device.Position  # Assumes device.Position returns an integer or comparable value.
            print(f"Current position: {current_position}")

            # Toggle: if current position is 2, then set to 0; otherwise, set to 2.
            new_position = 1 if current_position == 2 else 2
            print(f"Toggling position to: {new_position}")

            self.set_position(new_position)
            return new_position
        except Exception as e:
            print("Error during toggling:", e)
        # finally:
        #     self.disconnect()

    def get_position(self):
        return self.device.Position

#
# if __name__ == "__main__":
#     controller = FilterFlipperController()
#     controller.toggle()

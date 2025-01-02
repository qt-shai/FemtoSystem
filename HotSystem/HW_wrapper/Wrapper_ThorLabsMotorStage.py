"""An example that uses the .NET Kinesis Libraries to connect to a KDC."""
import time
import clr
import inspect

from HotSystem.HW_wrapper.abstract_motor import Motor

clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.DCServoCLI.dll")
from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.KCube.DCServoCLI import *
from System import Decimal


class MotorStage(Motor):
    """Class representing a Thorlabs PRM1Z8 motor stage."""

    def __init__(self, serial_number: int = 27266074):
        super().__init__()
        self.serial_number = str(serial_number)
        DeviceManagerCLI.BuildDeviceList()
        self.device = KCubeDCServo.CreateKCubeDCServo(self.serial_number)
        self.timeout = 20000

    def __del__(self):
        # self.disconnect()
        pass

    def connect(self) -> None:
        try:
            # Connect, begin polling, and enable
            self.device.Connect(self.serial_number)

            # Wait for Settings to Initialise
            if not self.device.IsSettingsInitialized():
                self.device.WaitForSettingsInitialized(self.timeout)
                if not self.device.IsSettingsInitialized():
                    raise Exception(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                                    f"Settings failed to initialize")

            # Configure the motor
            m_config = self.device.LoadMotorConfiguration(self.serial_number,
                                                          DeviceConfiguration.DeviceSettingsUseOptionType.UseFileSettings)
            m_config.DeviceSettingsName = "PRMTZ8" #Type of motor
            m_config.UpdateCurrentConfiguration()
            self.device.SetSettings(self.device.MotorDeviceSettings, True, False)
        except Exception as e:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Error during initialization:", e)

    def get_device_info(self) -> dict:
        """Get Device information"""
        device_info = self.device.GetDeviceInfo()
        print(device_info.Description)
        return device_info.Description

    def is_connected(self) -> bool:
        """Checks if the device is connected"""
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Is connected:", self.device.IsConnected)
        return self.device.IsConnected

    def is_enabled(self) -> bool:
        """Checks if the device is enabled"""
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Is enabled:",
            self.device.IsEnabled)
        return self.device.IsEnabled

    def move_to_home(self, channel:int=0) -> None:
        """Return device to angle 0"""
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Homing Actuator")
        self.device.Home(self.timeout)  #timeout, blocking call

    def MoveABSOLUTE(self, angle, channel:int=0)-> None:
        """Moves device to angle (in degrees)"""
        if self.validate_angle(angle):
            d = Decimal(abs(angle))
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Moving to position {angle}°")
            self.device.MoveTo(d, self.timeout)
        else:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Angle needs to be smaller than 360°")


    def move_relative(self, angle, channel:int=0):
        """Moves device by an angle (in degrees)"""
        if self.validate_angle(angle):
            current_angle = self.device.Position
            new_angle = current_angle + Decimal(angle)
            if new_angle > Decimal(360):
                new_angle = new_angle - Decimal(360)
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Moving by position {angle}°")
            self.device.MoveTo(new_angle,self.timeout)
        else:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Angle needs to be smaller than 360°")

    def get_current_position(self, channel: int=0) -> float:
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Position is: {self.device.Position}°")
        return self.device.Position

    def get_params(self) -> tuple:
        vel_params = self.device.GetVelocityParams()
        jog_params = self.device.GetJogParams()
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Velocity is: {vel_params.MaxVelocity}°",
            f'Acceleration is: {vel_params.Acceleration},',f'Jog step is: {jog_params.StepSize}.')
        return vel_params.MaxVelocity, jog_params.Acceleration

    def get_info(self):
        print(dir(self.device))

    def is_busy(self) -> bool:
        return self.device.IsDeviceBusy

    def get_device_info(self) -> None:
        #Return the serial number and type of the Device
        print("Device Methods and Properties:")
        print(self.device.GetJogParams())
        methods_and_properties = dir(self.device)
        print("Device Methods and Properties:")
        print("\n".join(methods_and_properties))  # Print each item in a new line
        #print(self.device.get_MotorPositionLimits().MaxValue)

    def jog(self, direction) -> None:
        """Makes a jog, not continuous. Can be called multiple times in a future held/unheld jog method"""
        try:
            if direction.lower() == "forward":
                self.device.MoveJog(MotorDirection.Forward, 0)
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Jogging forward...")
            elif direction.lower() == "backward":
                self.device.MoveJog(MotorDirection.Backward, 0)
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Jogging backwards...")
            else:
                raise ValueError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                                 f"Invalid direction. Use 'forward' or 'backward'.")
        except Exception as e:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Error during jog motion: {e}")

    def set_velocity_and_acceleration(self, max_velocity, acceleration) -> None:
        """
        Sets Velocity and Acceleration values. The defaults are 10 degrees/sec and 10 degrees/sec^2
        """
        try:
            # Retrieve current velocity parameters
            vel_params = self.device.GetVelocityParams()

            # Update velocity and acceleration
            vel_params.MaxVelocity = Decimal(max_velocity)
            vel_params.Acceleration = Decimal(acceleration)

            # Set the new velocity parameters
            self.device.SetVelocityParams(vel_params)
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Velocity set to {max_velocity} and acceleration set to {acceleration}")
        except Exception as e:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Error setting velocity in MotorStage.set_velocity_and_acceleration: {e}")

    def set_jog_step(self, step_size:int) -> None:
        """Sets the jog step in degrees"""
        if self.validate_angle(step_size):
            jog_step_decimal = Decimal(step_size)
            try:
                jog_params = self.device.GetJogParams()
                jog_params.StepSize = jog_step_decimal
                self.device.SetJogParams(jog_params)
                updated_jog_params = self.device.GetJogParams()
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                    f"Updated Jog Step: {updated_jog_params.StepSize}")
            except Exception as e:
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                    f"Error setting jog step: {e}")
        else:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Jog step needs to be smaller than 360°")

    def validate_angle(self,angle) -> bool:
        """
        Validates if the angle is within the valid range (0 to 360°).

        Parameters:
            angle (float): The angle to validate.

        Raises:
            ValueError: If the angle absolute value is above 360°.
        """
        if 0 <= angle <= 360:
            return True
        else:
            return False

    def jog_continuous(self, direction) -> None:
        """Makes a jog, not continuous. Can be called multiple times in a future held/unheld jog method"""
        try:
            if direction.lower() == "forward":
                self.device.MoveContinuous(MotorDirection.Forward)
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Jogging forward...")
            elif direction.lower() == "backward":
                self.device.MoveContinuous(MotorDirection.Backward)
                print(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Jogging backwards...")
            else:
                raise ValueError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                                 f"Invalid direction. Use 'forward' or 'backward'.")
        except Exception as e:
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
                f"Error during jog motion in MotorStage.jog_continuous: {e}")

    def stop_all_axes(self) -> None:
        """Stop the ongoing motion."""
        try:
            self.device.StopImmediate()
            print(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Motion stopped.")
            print("Motion stopped.")
        except Exception as e:
            print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] "
            f"Error during stop command in MotorStage.stop: {e}")

    def disable(self) -> None:
        """Disable the device."""
        self.device.DisableDevice()

    def enable(self) -> None:
        """Enable the device. It takes times for the device to enable, so no other processes can be run in that time.
        Without polling enabling fails."""
        self.device.StartPolling(250)
        time.sleep(0.25)
        self.device.EnableDevice()
        time.sleep(0.25)

    def disconnect(self) -> None:
        """Disconnect the device."""
        self.device.DisableDevice()
        self.device.StopPolling()
        self.device.Disconnect()

    def set_zero_position(self, channel: int = 0) -> None:
        pass

    def get_status(self, channel: int = 0) -> tuple:
        """Return if the device ius connected, enabled or busy"""
        return self.is_connected(), self.is_enabled(), self.is_busy()


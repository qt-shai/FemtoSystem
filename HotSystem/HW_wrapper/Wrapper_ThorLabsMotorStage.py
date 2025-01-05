"""An example that uses the .NET Kinesis Libraries to connect to a KDC."""
import time
import clr
import inspect
import threading

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

    def set_new_jog_step(self,relative_distance:float) -> None:
        jog_params = self.device.GetJogParams()
        jog_params.StepSize = relative_distance
        self.device.SetJogParams(jog_params)

    def move_to_position_non_blocking_absolute(self, position):
        """
        Moves the device to an absolute position non-blocking by using jogging commands.

        Parameters:
            position (Decimal): The absolute position to move to (using System.Decimal).

        Raises:
            RuntimeError: If there is an issue with the jog or device commands.

        Behavior:
            - Calculates the relative distance needed to reach the absolute position.
            - Sets the jog step size to the calculated distance (converted to float).
            - Executes a jog motion in the appropriate direction.
            - Resets the jog step size to a default value of 10.0 for safety.
        """
        try:
            # Get the current position as a Decimal
            current_position = self.device.Position

            # Calculate the relative distance as a Decimal
            if Decimal(position) > current_position:
                relative_distance = Decimal(position) - current_position
                self.set_new_jog_step(relative_distance)
                self.jog("forward")
            else:
                relative_distance = current_position - Decimal(position)
                self.set_new_jog_step(relative_distance)
                self.jog("backward")
            if not self.is_busy():
                self.set_jog_step(10)

        except Exception as e:
            raise RuntimeError(f"Error during non-blocking absolute motion: {e}")

    def move_to_position_non_blocking_relative(self, position) -> None:
        """
        Moves the device to a relative position non-blocking by using jogging commands.

        Parameters:
            position (float): The relative distance to move in the forward direction.

        Raises:
            RuntimeError: If there is an issue with the jog or device commands.

        Behavior:
            - Sets the jog step size to the desired position.
            - Executes a jog motion in the forward direction.
            - Resets the jog step size to a default value of 10 for safety.
        """
        try:
            # Set the jog step to the desired position
            self.set_jog_step(position)
            # Execute a jog forward motion
            self.jog("forward")
            # Reset jog step to a default value of 10
            time.sleep(0.25)
            self.set_jog_step(10)
        except Exception as e:
            raise RuntimeError(f"Error during non-blocking relative motion: {e}")

    def move_relative(self, angle, channel:int=0) -> None:
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
        return vel_params.MaxVelocity, vel_params.Acceleration, jog_params.StepSize

    def get_info(self) -> dir:
        print(dir(self.device))
        return dir(self.device)

    def is_busy(self) -> bool:
        print(
            f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Device is busy: {self.device.IsDeviceBusy}.")
        return self.device.IsDeviceBusy

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

    def set_jog_step(self, step_size:float) -> None:
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
        #self.device.StopPolling()
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

    def enable(self):
        """
        Enables the device for operation.

        Returns:
            str: Status message indicating success or failure.
        """
        try:
            # Check if the device is connected
            if not self.device.IsConnected:
                return "Device is not connected. Please connect the device and try again."

            # Enable the device
            self.device.StartPolling(250)
            time.sleep(0.25)
            self.device.EnableDevice()
            time.sleep(0.25)

            return "Device initialized and enabled successfully."

        except Exception as e:
            return f"Error initializing device: {str(e)}"

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


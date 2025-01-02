from HotSystem.HW_wrapper import Motor
import time
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.DeviceManagerCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\Thorlabs.MotionControl.GenericMotorCLI.dll")
clr.AddReference("C:\\Program Files\\Thorlabs\\Kinesis\\ThorLabs.MotionControl.KCube.DCServoCLI.dll")
from Thorlabs.MotionControl.DeviceManagerCLI import *
from Thorlabs.MotionControl.GenericMotorCLI import *
from Thorlabs.MotionControl.KCube.DCServoCLI import *
from System import Decimal


class MotorStage(Motor):
    def connect(self) -> None:
        pass

    def disconnect(self) -> None:
        pass

    def is_connected(self) -> bool:
        pass

    def stop_all_axes(self) -> None:
        pass

    def move_to_home(self, channel: int) -> None:
        pass

    def MoveABSOLUTE(self, channel: int, position: int) -> None:
        pass

    def move_relative(self, channel: int, steps: int) -> None:
        pass

    def set_zero_position(self, channel: int) -> None:
        pass

    def get_status(self, channel: int) -> str:
        pass

    def get_current_position(self, channel: int) -> float:
        pass
# Import the .NET Common Language Runtime (CLR) to allow interaction with .NET
# Install the 'pythonnet' package using 'pip install pythonnet'

# Solution: Unblock the Assembly
# Unblock the Assembly:
#
# Navigate to the file DeviceIOLib.dll in Windows Explorer.
# Right-click on the file and select Properties.
# In the General tab, if you see an Unblock button or checkbox at the bottom, click it and then click Apply and OK.
# This will unblock the assembly and should allow it to be loaded.

from typing import Optional, Tuple, List
import clr
from SystemConfig import Instruments, Device

# Add a reference to each .NET assembly required
clr.AddReference ("HW_wrapper\\DeviceIOLib")
clr.AddReference ("HW_wrapper\\CmdLib8742")

# Import classes from the namespaces
from Newport.DeviceIOLib import *
from NewFocus.PicomotorApp import CmdLib8742
from System.Text import StringBuilder

class newportPicomotor():

    @staticmethod
    def get_available_devices() -> List[Device]:
        """
        Static method to return available devices as instances of the Device class.
        This method uses ctl.FindDevices() to gather information about available devices.
        Missing information (IP, MAC, serial) is replaced with 'N/A'.

        :return: A list of Device instances.
        """
        available_devices = []
        try:
            # Call the class constructor to create an object
            device_io = DeviceIOLib(True)
            device_io.DiscoverDevices(5, 1000)
            # Get the list of discovered devices
            n_device_count = device_io.GetDeviceCount()
            print("Device Count = %d\n" % n_device_count)
            if n_device_count > 0:
                for device_key in device_io.GetDeviceKeys():
                    device_io.GetModelSerial(device_key)
                    available_devices.append(Device(
                                instrument=Instruments.PICOMOTOR,
                                ip_address=device_key,
                                mac_address=device_io.GetMACAddress(device_key),
                                serial_number=device_io.GetModelSerial(device_key)
                            ))

        except Exception as e:
            print(f"Could not find picomotor. Error: {e}" )
        del device_io
        return available_devices

    def __init__(self, simulation:bool = False):
        self.simulation = simulation
        self.error: Optional[str] = None
        self.IsConnected: bool = False
        self.ky: Optional[str] = None
        self.no_of_channels: int = 3
        self.channels:List[int] = [1,2,3]
        self.deviceIO: Optional[DeviceIOLib] = None
        self.Pico: Optional[CmdLib8742] = None
        self.Address: Optional[int] = None
        self.LoggedPoints = []
        self.KeyboardEnabled = True

    def __del__(self):
        self.Disconnect()
        
    def InitAfterConnect(self):
        """Initialize various settings after connecting to the device."""
        self.StepsIn1mm=1e3*40
        self.AxesKeyBoardLargeStep = []
        self.AxesKeyBoardSmallStep = []
        self.AxesPositions = [0,0,0]
        self.AxesPosUnits = []
        self.AxesNewPositions = []
        self.AxesTargetPositions = []
        self.AxesRelativeStep = []
        self.AxesPosUnits = []
        self.AxesVelocities = []
        self.AxesAcceleraitions = []
        self.AxesState = [0,0,0]
        self.AxesFault = [0,0,0]
        for i in range(self.no_of_channels):
                self.ReadChannelsState(i)
                self.AxesPositions.append(0)
                self.AxesNewPositions.append(0)
                self.AxesTargetPositions.append(0)
                self.AxesPosUnits.append("steps")
                self.AxesVelocities.append(0)
                self.AxesAcceleraitions.append(0)
                self.AxesRelativeStep.append(0)
                self.AxesKeyBoardLargeStep.append(1000000) # [in pm]  1um
                self.AxesKeyBoardSmallStep.append(100000) # [in pm] 100nm 

    def ReadChannelsState(self, channel: int = 1) -> None:
        """Read the state of the specified channel."""
        try:
            status, out = self.Pico.GetMotionDone(self.ky, channel, True)
            if status:
                self.AxesState[channel] = out
            else:
                print(f"Failed to get motion done status for channel {channel}")
            
            status, _ = self.Pico.GetScanDone(self.ky, True)
            if not status:
                print(f"Failed to get scan done status for channel {channel}")
        except Exception as e:
            self.error = f"Failed to read channel state: {e}"
            print(self.error)
        
    def connect(self):
        """Establish connection with the Picomotor device."""
        if self.simulation:
            print("Loaded picomotor simulation device")
            return
        print ("Waiting for device discovery...")
        try:
            # Call the class constructor to create an object
            self.deviceIO = DeviceIOLib(True)
            self.Pico = CmdLib8742(self.deviceIO)
            # Discover USB and Ethernet devices - delay 5 seconds
            self.deviceIO.DiscoverDevices (5, 5000)
            # Get the list of discovered devices        
            nDeviceCount = self.deviceIO.GetDeviceCount ()
            print ("Device Count = %d\n" % nDeviceCount)
            if (nDeviceCount > 0) :
                strBldr = StringBuilder (64)
                        
                self.ky = str (self.deviceIO.GetFirstDeviceKey())

                print ("Device Key[%d] = %s" % (1, self.ky))
                    # If the device was opened
                if (self.deviceIO.Open (self.ky)) :

                    self.IsConnected = True
                    strModel = ""
                    strSerialNum = ""
                    strFwVersion = ""
                    strFwDate = ""
                    
                    strModel, strSerialNum, strFwVersion, strFwDate = self.Pico.IdentifyInstrument (self.ky, strModel, strSerialNum, strFwVersion, strFwDate)
                    
                    print ("Model = %s" % strModel)
                    print ("Serial Num = %s" % strSerialNum)
                    print ("Fw Version = %s" % strFwVersion)
                    print ("Fw Date = %s\n" % strFwDate)

                    strCmd = "*IDN?"
                    strBldr.Remove (0, strBldr.Length)
                    nReturn = self.deviceIO.Query (self.ky, strCmd, strBldr)
                    print ("Return Status = %d" % nReturn)
                    print ("*IDN Response = %s\n\n" % strBldr.ToString ())   
                    self.GetDeviceAddress()  
                    self.InitAfterConnect()
                    self.GetPosition()
                    self.GetAcceleration()
                    self.GetVelocities()   
                else:
                    self.error = "Failed to open the device."
                    print(self.error)        
            else :
                self.error = "Cannot find picomotor device"
                print ("No devices discovered.\n")
        except Exception as e:
            self.error = f"Connection error: {e}"
            print(self.error)
        
    def Disconnect(self): 
        """Disconnect from the Picomotor device."""
        try:
            print("Closing connection with Picomotor")
            if self.deviceIO:
                self.deviceIO.Close(self.ky)
            if self.Pico:
                self.Pico.Shutdown()
            if self.deviceIO:
                self.deviceIO.Shutdown()
            self.IsConnected = False
        except Exception as e:
            self.error = f"Error while disconnecting: {e}"
            print(self.error)
        
    def AbortMotion(self):
        # This command is used to instantaneously stop any motion that is in progress. Motion is stopped abruptly. For stop with deceleration see ST command which uses programmable acceleration/deceleration setting.
        try:
            self.Pico.AbortMotion(self.ky)
        except Exception as e:
            self.error = f"Failed to abort motion: {e}"
            print(self.error)
        
    def SetZeroPosition(self, Motor: int) -> None:
        """Set the zero position for the specified motor."""
        try:
            self.Pico.SetZeroPosition(self.ky, Motor)
        except Exception as e:
            self.error = f"Failed to set zero position: {e}"
            print(self.error)
        
    def GetErrorNum(self) -> Optional[int]:
        """Get the error number from the error queue."""
        try:
            status, Num = self.Pico.GetErrorNum(self.ky, '')
            if status:
                return Num
            else:
                print("Failed to get error number")
                return None
        except Exception as e:
            self.error = f"Failed to get error number: {e}"
            print(self.error)
            return None
        
    def GetErrorMsg(self) -> Optional[str]:
        """Get the error message from the error queue."""
        try:
            status, Msg = self.Pico.GetErrorMsg(self.ky, '')
            if status:
                return Msg
            else:
                print("Failed to get error message")
                return None
        except Exception as e:
            self.error = f"Failed to get error message: {e}"
            print(self.error)
            return None
    
    def GetMotorType(self, Motor: int) -> Optional[str]:
        """Get the motor type from the specified device."""
        try:
            status, Motor_type = self.Pico.GetMotorType(self.ky, Motor, self.Pico.eMotorType.Standard)
            if status:
                return Motor_type
            else:
                print(f"Failed to get motor type for motor {Motor}")
                return None
        except Exception as e:
            self.error = f"Failed to get motor type: {e}"
            print(self.error)
            return None
    
    def GetPosition(self) -> None:
        """Get the current position for all channels."""
        try:
            for ch in range(self.no_of_channels):
                status, self.AxesPositions[ch] = self.Pico.GetPosition(self.ky, ch + 1, 0)
                if not status:
                    print(f"Failed to get position for channel {ch+1}")
        except Exception as e:
            self.error = f"Failed to get position: {e}"
            print(self.error)
            
    def ReadPosition(self, ch: int = 0) -> Tuple[Optional[int], str]:
        """Read the position of the specified channel."""
        try:
            status, out = self.Pico.GetPosition(self.ky, ch, 0)
            units = "steps"
            if status:
                return out, units
            else:
                print(f"Failed to read position for channel {ch}")
                return None, units
        except Exception as e:
            self.error = f"Failed to read position: {e}"
            print(self.error)
            return None, "steps"
        
    def GetRelativeSteps(self, Motor: int) -> Optional[int]:
        """Get the relative steps setting for the specified motor."""
        try:
            status, out = self.Pico.GetRelativeSteps(self.ky, Motor, 0)
            if status:
                return out
            else:
                print(f"Failed to get relative steps for motor {Motor}")
                return None
        except Exception as e:
            self.error = f"Failed to get relative steps: {e}"
            print(self.error)
            return None
        
    def MoveRelative(self, Motor: int, Steps: int) -> None:
        """Perform a relative move on the specified motor."""
        try:
            self.Pico.RelativeMove(self.ky, Motor, Steps)
        except Exception as e:
            self.error = f"Failed to move relative: {e}"
            print(self.error)
        
    def GetAbsTargetPos(self, Motor: int) -> Optional[int]:
        """Get the absolute target position for the specified motor."""
        try:
            status, pos = self.Pico.GetAbsTargetPos(self.ky, Motor, 0)
            if status:
                return pos
            else:
                print(f"Failed to get absolute target position for motor {Motor}")
                return None
        except Exception as e:
            self.error = f"Failed to get absolute target position: {e}"
            print(self.error)
            return None
        
    def MoveABSOLUTE(self, Motor: int, Pos: int) -> None:
        """Perform an absolute move on the specified motor."""
        try:
            self.Pico.AbsoluteMove(self.ky, Motor, Pos)
        except Exception as e:
            self.error = f"Failed to move absolute: {e}"
            print(self.error)
       
    def JogNegative(self, Motor: int):
        # This method performs a jog in the negative direction on the specified device.
        status = self.Pico.JogNegative(self.ky, Motor)
        if not status:
            print(f"Failed to jog negative on motor {Motor}.")
    
    def JogPositive(self, Motor: int):
        # This method performs a jog in the positive direction on the specified device.
        status = self.Pico.JogPositive(self.ky, Motor)
        if not status:
            print(f"Failed to jog positive on motor {Motor}.")

    def StopMotion(self, Motor: int):
        # This method performs a stop motion on the specified device.
        status = self.Pico.StopMotion(self.ky, Motor)
        if not status:
            print(f"Failed to stop motion on motor {Motor}.")

    def StopAllAxes(self):
        # This method stops motion on all axes.
        for ax in range(self.no_of_channels):
            self.StopMotion(ax + 1)

    def GetMotionDone(self, Motor: int) -> bool:
        # This method gets the motion done status from the specified device.
        status, out = self.Pico.GetMotionDone(self.ky, Motor, True)
        if status:
            return out
        else:
            # print(f"Failed to get motion done status for motor {Motor}.")
            return False
     
    def GetVelocities(self):
        # This method gets the velocity from the specified device for all channels.
        for ch in range(self.no_of_channels):
            status, velocity = self.Pico.GetVelocity(self.ky, ch + 1, 0)
            if status:
                self.AxesVelocities[ch] = velocity
            else:
                print(f"Failed to get velocity for channel {ch + 1}.")

    def SetVelocity(self, Motor: int, velocity: int):
        # This method sets the velocity for the specified device. The velocity is in steps per second.
        if velocity > 2000:
            print("Velocity cannot exceed 2000 steps/s")
            velocity = 2000

        status = self.Pico.SetVelocity(self.ky, Motor, velocity)
        if not status:
            print(f"Failed to set velocity for motor {Motor}.")

    def GetAcceleration(self):
        # This method gets the acceleration value for each axis.
        for ch in range(self.no_of_channels):
            status, acceleration = self.Pico.GetAcceleration(self.ky, ch + 1, 0)
            if status:
                self.AxesAcceleraitions[ch] = acceleration
            else:
                print(f"Failed to get acceleration for channel {ch + 1}.")

    def SetAcceleration(self, Motor: int, Val: int):
        # This method sets the acceleration value for the specified axis.
        if Val > 200000:
            print("Acceleration cannot exceed 200000 steps/sec^2")
            Val = 200000

        status = self.Pico.SetAccelaration(self.ky, Motor, Val)
        if not status:
            print(f"Failed to set acceleration for motor {Motor}.")

    def SaveToMemory(self):
        # This method saves settings in the device's volatile memory to its persistent memory.
        status = self.Pico.SaveToMemory(self.ky)
        if not status:
            print("Failed to save settings to memory.")

    def GetScanDone(self) -> bool:
        # This method gets the scan done status from the specified device.
        status, out = self.Pico.GetScanDone(self.ky, True)
        if status:
            return out
        else:
            print("Failed to get scan done status.")
            return False

    def Reset(self):
        # This method resets a master controller so that it can be rediscovered.
        status = self.Pico.Reset(self.ky)
        if not status:
            print("Failed to reset the device.")

    def GetDeviceAddress(self) -> str:
        # This method gets the device address from the specified device.
        status, out = self.Pico.GetDeviceAddress(self.ky, 1)
        if status:
            self.Address = out
            return out
        else:
            print("Failed to get device address.")
            return ""

    def MoveToTravelLimitPos(self, Motor: int):
        # This method performs a Move To Travel Limit in the positive direction on the specified device.
        status = self.Pico.MoveToTravelLimitPos(self.ky, self.Address, Motor)
        if not status:
            print(f"Failed to move motor {Motor} to travel limit in the positive direction.")

    def MoveToTravelLimitNeg(self, Motor: int):
        # This method performs a Move To Travel Limit in the negative direction on the specified device.
        status = self.Pico.MoveToTravelLimitNeg(self.ky, self.Address, Motor)
        if not status:
            print(f"Failed to move motor {Motor} to travel limit in the negative direction.")
    
    def MoveToHome(self, Motor: int):
        # This method performs a Move To Home on the specified device.
        status = self.Pico.MoveToHome(self.ky, self.Address, Motor)
        if not status:
            print(f"Failed to move motor {Motor} to home position.")
        

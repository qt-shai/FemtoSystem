import math
import sys
from enum import Enum
from typing import List, Tuple, Optional
import numpy as np
from HW_wrapper.SmarAct.smaract_movement import Movement
from HW_wrapper.SmarAct.smaract_stream_manager import StreamManager
import smaract.ctl as ctl
from SystemConfig import Device, Instruments


class smaractMCS2():
    class LogicLevel(Enum):
        LOW = 0
        HIGH = 1

    @staticmethod
    def get_available_devices() -> List[Device]:
        """
        Static method to return available devices as instances of the Device class.
        This method uses ctl.FindDevices() to gather information about available devices.
        Missing information (IP, MAC, serial) is replaced with 'N/A'.

        :return: A list of Device instances.
        """
        try:
            devices_raw = ctl.FindDevices().splitlines()  # e.g., ['network:sn:MCS2-00018624', 'network:sn:MCS2-00018625']

            # Initialize the list to hold device objects
            available_devices = []

            # Parse each device entry and create a Device object
            # If devices_raw is not a list, convert it to a list
            if not isinstance(devices_raw, list):
                devices_raw = [devices_raw]

            for device in devices_raw:
                # Example device string: 'network:sn:MCS2-00018624'
                device_parts = device.split(':')
                if len(device_parts) == 3 and device_parts[1] == 'sn':
                    serial_number = device_parts[2]  # Extract serial number

                    instrument = ip = "N/A"
                    if "MCS2-00017055" in serial_number:
                        instrument = Instruments.SMARACT_SLIP
                        ip = "192.168.101.60"
                    elif "MCS2-00018624" in serial_number:
                        instrument = Instruments.SMARACT_SCANNER
                        ip = "192.168.101.59"

                    available_devices.append(Device(
                        instrument=instrument,  # Assuming the instrument is 'Smaract'
                        ip_address=ip,  # Replace with actual IP if available
                        mac_address="N/A",  # Replace with actual MAC if available
                        serial_number=serial_number
                    ))

            return available_devices

        except ctl.Error as e:
            print(f"Error while finding devices: {e}")
            return []

    def __init__(self, simulation :bool = False):
        self.simulation = simulation
        self.amplifier_enabled = None
        self.streaming_active = None
        self.trigger_mode = None
        self.error = None
        self.dHandle = None
        self.IsConnected = False
        self.deviceLocator:Optional[str] = None
        self.GetAvailableDevices()
        self.LoggedPoints = []
        self.StepsIn1mm=1e9
        self.KeyboardEnabled = True
        self.no_of_channels = 3  # For support in simulation mode
        self.U = [1, 0, 0]
        self.V = [0, 1, 0]

    def __del__(self):
        self.Disconnect()

    def StopEMG_AllAxes(self):
        for ax in range(self.no_of_channels):
            self.Stop(ax)
            self.Stop(ax)

    #  enable IO 
    def setIOmoduleEnable(self,dev = 0):
        # Set output driver voltage level to 3.3V.
        ctl.SetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_VOLTAGE, ctl.IOModuleVoltage.VOLTAGE_3V3)
        # Enable the digital output driver circuit of the I/O module.
        ctl.SetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_OPTIONS, ctl.IOModuleOption.DIGITAL_OUTPUT_ENABLED)
    # generates single pulse
    def generatePulse(self,channel = 0):
        self.set_Channel_IO_state(channel=channel,level = self.LogicLevel.HIGH)
        self.set_Channel_IO_state(channel=channel,level = self.LogicLevel.LOW)
    # set IO to HIGH (LVTTL) or LOW (zero)
    def set_Channel_Constant_Mode_State(self, channel = 0):
        result = ctl.SetProperty_i32(self.dHandle, channel,ctl.Property.CH_OUTPUT_TRIG_MODE,ctl.ChannelOutputTriggerMode.CONSTANT)

    def set_Channel_IO_state(self, channel = 0, level = LogicLevel.HIGH):
        if level == self.LogicLevel.LOW:
            A = ctl.TriggerPolarity.ACTIVE_HIGH
            B = ctl.TriggerPolarity.ACTIVE_LOW
        else:
            A = ctl.TriggerPolarity.ACTIVE_LOW
            B = ctl.TriggerPolarity.ACTIVE_HIGH

        result = ctl.SetProperty_i32(self.dHandle, channel,ctl.Property.CH_OUTPUT_TRIG_POLARITY,A)
        result = ctl.SetProperty_i32(self.dHandle, channel,ctl.Property.CH_OUTPUT_TRIG_MODE,B)

    # Set move acceleration [in pm/s2].
    def SetAcceleration(self, channel, Acc):
        try:
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_ACCELERATION, int(Acc))


        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    # Get move acceleration [in pm/s2].
    def ReadAcceleration(self, channel):
        try:
            acc = ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_ACCELERATION)
            return acc

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    # Set move velocity [in pm/s].
    def SetVelocity(self, channel, Vel):
        try:
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_VELOCITY, int(Vel))

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    # Get Velocity [in pm/s]
    def ReadVelocity(self, channel):
        try:
            vel = ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_VELOCITY)
            return vel

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    
    def SetMoveMode(self, channel, move_mode):
        ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.MOVE_MODE, move_mode)
    
    # Specify absolute newPosition [in pm].
    # (For Piezo Scanner channels adjust to valid value within move range, e.g. +-10000000.)
    def MoveABSOLUTE(self,channel, newPosition):
        try:
            self.SetMoveMode(channel, ctl.MoveMode.CL_ABSOLUTE)
            # Start movement.
            ctl.Move(self.dHandle, channel, newPosition, 0)
            # Note that the function call returns immediately, without waiting for the movement to complete.
            # The "ChannelState.ACTIVELY_MOVING" (and "ChannelState.CLOSED_LOOP_ACTIVE") flag in the channel state
            # can be monitored to determine the end of the movement.
            
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    # Specify absolute RelStep [in pm].
    def MoveRelative(self,channel, RelStep):
        try:
            self.SetMoveMode(channel, ctl.MoveMode.CL_RELATIVE)
            # Start movement.
            ctl.Move(self.dHandle, channel, RelStep, 0)
            # Note that the function call returns immediately, without waiting for the movement to complete.
            # The "ChannelState.ACTIVELY_MOVING" (and "ChannelState.CLOSED_LOOP_ACTIVE") flag in the channel state
            # can be monitored to determine the end of the movement.

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    # stop also hold in position
    # if needed re-enable the axis
    def StopAllAxes(self):
        for ax in range(self.no_of_channels):
            self.Stop(ax)
    # STOP
    # This command stops any ongoing movement. It also stops the hold position feature of a closed loop command.
    # Note for closed loop movements with acceleration control enabled:
    # The first "stop" command sent while moving triggers the positioner to come to a halt by decelerating to zero.
    # A second "stop" command triggers a hard stop ("emergency stop").
    def Stop(self, channel):
        try:
            ctl.Stop(self.dHandle, channel)

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    # todo: read guide
    # do not use this function before reading the programmers guide
    def calibrate(self, channel):
        try:
            # Set calibration options (start direction: forward)
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CALIBRATION_OPTIONS, 0)
            
            # Start calibration sequence
            ctl.Calibrate(self.dHandle, channel)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    # todo: read programmers guide and verify referencing options
    # do not use this function before reading the guide
    def findReference(self, channel):
        try:
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.REFERENCING_OPTIONS, ctl.ReferencingOption.STOP_ON_REF_FOUND)
            # Set velocity to 1mm/s
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_VELOCITY, 1000000000)
            # Set acceleration to 10mm/s2.
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.MOVE_ACCELERATION, 10000000000)
            # Start referencing sequence
            ctl.Reference(self.dHandle, channel)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
            .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    # should be private
    def ReadPosition(self, channel = 0):
        if self.simulation:
            units = "pm"
            position = 0
            return position, units

        try:
            base_unit = self.GetPositionerType(channel)
            # Next we read the current position of channel 0. Position values have the data type int64,
            # thus we need to use "getProperty_i64".
            # Note that there is no distinction between linear and rotatory positioners regarding the functions which
            # need to be used (getPosition / getAngle) and there is no additional "revolutions" parameter for rotatory positioners
            # as it was in the previous controller systems.
            # Depending on the preceding read base unit, the position is in pico meter [pm] for linear positioners
            # or nano degree [ndeg] for rotatory positioners.
            # Note: it is also possible to read the base resolution of the unit using the property key "POS_BASE_RESOLUTION".
            # To keep things simple this is not shown in this example.
            position = ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.POSITION)
            # print("MCS2 position of channel {}: {}".format(channel, position), end='')
            # print("pm.") if base_unit == ctl.BaseUnit.METER else print("ndeg.")

            units = "pm" if base_unit == ctl.BaseUnit.METER else "ndeg."

            return position, units

        except ctl.Error as e:
            # Catching the "ctl.Error" exceptions may be used to handle errors of SmarActCTL function calls.
            # The "e.func" element holds the name of the function that caused the error and
            # the "e.code" element holds the error code.
            # Passing an error code to "GetResultInfo" returns a human readable string specifying the error.
            print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    
    def SetPosition(self,channel = 0, newPosition = 0):
        ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.POSITION, int(newPosition))

    def GetPositionerType(self, channel = 0): # linear or Rotational
        try:
            # First we want to know if the configured positioner type is a linear or a rotatory type.
            # For this purpose we can read the base unit property.
            return ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.POS_BASE_UNIT)

            

        except ctl.Error as e:
            # Catching the "ctl.Error" exceptions may be used to handle errors of SmarActCTL function calls.
            # The "e.func" element holds the name of the function that caused the error and
            # the "e.code" element holds the error code.
            # Passing an error code to "GetResultInfo" returns a human readable string specifying the error.
            print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise
    
    def ReadIsInPosition(self,channel):
        state = ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CHANNEL_STATE)
        if state & ctl.ChannelState.IN_POSITION:
            return True
        else:
            return False

    def ReadChannelsState(self,channel = 0):
        try:
            self.AxesState.clear()
            self.AxesFault.clear()
            
            state = ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CHANNEL_STATE)
            # The returned channel state holds a bit field of several state flags.
            # See the MCS2 Programmers Guide for the meaning of all state flags.
            # We pick the "sensorPresent" flag to check if there is a positioner connected
            # which has an integrated sensor.
            # Note that in contrast to previous controller systems the controller supports
            # hotplugging of the sensor module and the actuators.

            if state & ctl.ChannelState.ACTIVELY_MOVING:
                self.AxesState.append("ch"+ str(channel) + "actively moving")
            
            if state & ctl.ChannelState.CLOSED_LOOP_ACTIVE:
                self.AxesState.append("ch"+ str(channel) + " in closed loop")

            if state & ctl.ChannelState.CALIBRATING:
                self.AxesState.append("ch"+ str(channel) + " CALIBRATING")
            
            if state & ctl.ChannelState.REFERENCING:
                self.AxesState.append("ch"+ str(channel) + " REFERENCING")

            if state & ctl.ChannelState.MOVE_DELAYED:
                self.AxesState.append("ch"+ str(channel) + " MOVE_DELAYED")

            if state & ctl.ChannelState.SENSOR_PRESENT:
                self.AxesState.append("ch"+ str(channel) + " SENSOR_PRESENT")

            if state & ctl.ChannelState.IS_CALIBRATED:
                self.AxesState.append("ch"+ str(channel) + " IS_CALIBRATED")
            
            if state & ctl.ChannelState.IS_REFERENCED:
                self.AxesState.append("ch"+ str(channel) + " IS_REFERENCED")
            
            if state & ctl.ChannelState.END_STOP_REACHED:
                self.AxesState.append("ch"+ str(channel) + " END_STOP_REACHED")

            if state & ctl.ChannelState.RANGE_LIMIT_REACHED:
                self.AxesState.append("ch"+ str(channel) + " RANGE_LIMIT_REACHED")

            if state & ctl.ChannelState.FOLLOWING_LIMIT_REACHED:
                self.AxesState.append("ch"+ str(channel) + " FOLLOWING_LIMIT_REACHED")

            if state & ctl.ChannelState.MOVEMENT_FAILED:
                self.AxesFault.append("ch"+ str(channel) + " MOVEMENT_FAILED")

            if state & ctl.ChannelState.IS_STREAMING:
                self.AxesState.append("ch"+ str(channel) + " IS_STREAMING")
            
            if state & ctl.ChannelState.POSITIONER_OVERLOAD:
                self.AxesFault.append("ch"+ str(channel) + " POSITIONER_OVERLOAD")

            if state & ctl.ChannelState.OVER_TEMPERATURE:
                self.AxesFault.append("ch"+ str(channel) + " OVER_TEMPERATURE")
            
            if state & ctl.ChannelState.REFERENCE_MARK:
                self.AxesState.append("ch"+ str(channel) + " REFERENCE_MARK")

            if state & ctl.ChannelState.IS_PHASED:
                self.AxesState.append("ch"+ str(channel) + " IS_PHASED")

            if state & ctl.ChannelState.POSITIONER_FAULT:
                self.AxesFault.append("ch"+ str(channel) + " POSITIONER_FAULT")

            if state & ctl.ChannelState.AMPLIFIER_ENABLED:
                self.AxesState.append("ch"+ str(channel) + " AMPLIFIER_Enabled")
            else:
                self.AxesState.append("ch"+ str(channel) + " AMPLIFIER_Disabled")
            
            if state & ctl.ChannelState.IN_POSITION:
                self.AxesState.append("ch"+ str(channel) + " IN_POSITION")
            
            if state & ctl.ChannelState.BRAKE_ENABLED:
                self.AxesState.append("ch"+ str(channel) + " BRAKE_Enabled")
            else:
                self.AxesState.append("ch"+ str(channel) + " BRAKE_Disabled")

        except ctl.Error as e:
            # Catching the "ctl.Error" exceptions may be used to handle errors of SmarActCTL function calls.
            # The "e.func" element holds the name of the function that caused the error and
            # the "e.code" element holds the error code.
            # Passing an error code to "GetResultInfo" returns a human readable string specifying the error.
            print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    def ReadNumberOfChannels(self):
        try:
            # Reading the number of channels of the system using "GetProperty_i32".
            # Note that the "idx" parameter is unused for this property and thus must be set to zero.
            no_of_channels = ctl.GetProperty_i32(self.dHandle, 0, ctl.Property.NUMBER_OF_CHANNELS)
            print("MCS2 number of channels: {}.".format(no_of_channels))

            self.no_of_channels = no_of_channels
            return no_of_channels

        except ctl.Error as e:
            # Catching the "ctl.Error" exceptions may be used to handle errors of SmarActCTL function calls.
            # The "e.func" element holds the name of the function that caused the error and
            # the "e.code" element holds the error code.
            # Passing an error code to "GetResultInfo" returns a human readable string specifying the error.
            print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    def ReadDevSerial(self):
        try:
            # First we read the device serial number which is a string property using "GetProperty_s".
            # Note that for string properties the ioArraySize must be explicitly passed as argument
            # (ctl.STRING_MAX_LENGTH+1) to specify the buffer size for the returned value.
            device_sn = ctl.GetProperty_s(self.dHandle, 0, ctl.Property.DEVICE_SERIAL_NUMBER)
            print("MCS2 device serial number: {}".format(device_sn))
            self.devSerial = device_sn

        except ctl.Error as e:
            # Catching the "ctl.Error" exceptions may be used to handle errors of SmarActCTL function calls.
            # The "e.func" element holds the name of the function that caused the error and
            # the "e.code" element holds the error code.
            # Passing an error code to "GetResultInfo" returns a human readable string specifying the error.
            print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

        except Exception as ex:
            print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            raise

    def GetAvailableDevices(self):
        try:
            dev_list = ctl.FindDevices() # need network:sn:MCS2-00000412
        except ctl.FindDevices.Error as err:
            # todo: add error handling
            print(err)

        dev_list = dev_list.split("\n") # split string every \n to get list of devices todo: once another stage will arrive we need see if we get one string or list
        self.Available_Devices_List = list(dict.fromkeys(dev_list)) # remove duplicants by using dictionary
        # self.Available_Devices_List.insert(0,"") # add empty device at the beginning
    
    def InitAfterConnect(self):
        self.AxesKeyBoardLargeStep = []
        self.AxesKeyBoardSmallStep = []
        self.AxesPositions = []
        self.AxesNewPositions = []
        self.AxesTargetPositions = []
        self.AxesRelativeStep = []
        self.AxesPosUnits = []
        self.AxesVelocities = []
        self.AxesAcceleraitions = []
        self.AxesState = []
        self.AxesFault = []
        for i in range(self.no_of_channels):
                self.ReadChannelsState(i)
                self.AxesPositions.append(0)
                self.AxesNewPositions.append(0)
                self.AxesTargetPositions.append(0)
                self.AxesPosUnits.append("")
                self.AxesVelocities.append(0)
                self.AxesAcceleraitions.append(0)
                self.AxesRelativeStep.append(0)
                self.AxesKeyBoardLargeStep.append(1000000) # [in pm]  1um
                self.AxesKeyBoardSmallStep.append(100000) # [in pm] 100nm 

    def connect(self,dev):
        if self.simulation:
            self.IsConnected = False
            return
        try:
            if "MCS2-00017055" in dev:  # Positioner 1 (Hot System)
                self.dHandle = ctl.Open('network:192.168.101.60', "")
            elif "MCS2-00018624" in dev:  # Scanner (Femto)
                self.dHandle = ctl.Open('network:192.168.101.59', "")
            self.deviceLocator = dev
            self.ReadDevSerial()
            self.ReadNumberOfChannels()
            self.InitAfterConnect()
            self.GetPosition()
            self.GetAcceleration()
            self.GetVelocities()
            self.stream_manager = StreamManager(self.dHandle)
            self.IsConnected = True
            # TODO: check serial before enabling amplifier
            for ch in range(3):
                ctl.SetProperty_i32(self.dHandle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
            
        except Exception as e:
            self.deviceLocator = ""
            self.IsConnected = False
            self.error = "Could Not connect to:" + str(dev) + "\nVerify if device selection is not empty."
            print(f"Could not open connection to smaract. Error: {e}. \n Smaract Error : {self.error}")
     
    def Disconnect(self):
        if self.simulation:
            self.IsConnected = False
            return
        try:
            for ch in range(3):
                ctl.SetProperty_i32(self.dHandle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.FALSE)
            ctl.Close(self.dHandle)
            self.IsConnected = False
            self.deviceLocator = ""
        except:
            self.error = "Could Not disconnect.\nVerify if device is connected."

    def GetPosition(self):
        for ax in range(self.no_of_channels):
            self.AxesPositions[ax], self.AxesPosUnits[ax] = self.ReadPosition(ax)

    def calc_uv(self):
        if len(self.LoggedPoints)<3:
            print(f"Please log at least three points prior to calculating u & v")
            return
        p1, p2, p3 = self.LoggedPoints[-3:]
        self.U = self.calculate_vector(p1, p2)
        self.V = self.calculate_vector(p2, p3)

    def calculate_vector(self, p1, p2):
        difference = [p2[i] - p1[i] for i in range(len(p1))]
        try:
            magnitude = math.sqrt(sum([component ** 2 for component in difference]))
            if magnitude == 0 or magnitude == 0:
                print("The two points are identical, cannot compute vector.")
                return None
                # raise ValueError("The two points are identical, cannot compute vector.")

            return [component / magnitude for component in difference]

        except ZeroDivisionError:
            print("Division by zero error encountered during vector normalization.")
        except ValueError as e:
            print(e)

    def GetVelocities(self):
        for ax in range(self.no_of_channels):
            self.AxesVelocities[ax] = self.ReadVelocity(ax)
    
    def GetAcceleration(self):
        for ax in range(self.no_of_channels):
            self.AxesAcceleraitions[ax] = self.ReadAcceleration(ax)

    def SetPositionTrigger(self, channel: int, min_limit: int, max_limit: int, increment: int,
                           direction: int = 0, pulse_width: int = 1000, start_threshold: int = np.inf,
                           verbose : bool = False):
        """
        Set position trigger parameters for a specific channel.
        :param channel: The channel number.
        :param min_limit: The minimum position limit for comparison in pm.
        :param max_limit: The maximum position limit for comparison in pm.
        :param increment: The position increment for generating triggers in pm.
        :param direction: The direction for position comparison trigger (<0 for BACKWARD, 0 for EITHER, >0 for FORWARD).
        :param pulse_width: The pulse width of the trigger output in ns. Default = 1000 ns
        :param start_threshold: The starting threshold for position comparison in pm. Inf = don't use
        :param verbose: Toggle the verbose output.
        """
        try:
            if direction < 0:
                trigger_direction = ctl.BACKWARD_DIRECTION
            elif direction > 0:
                trigger_direction = ctl.FORWARD_DIRECTION
            else:
                trigger_direction = ctl.EITHER_DIRECTION

            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_POS_COMP_DIRECTION, trigger_direction)
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_LIMIT_MIN, int(min_limit))  # pm
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_LIMIT_MAX, int(max_limit))  # pm
            ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_INCREMENT, int(increment))  # pm
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_PULSE_WIDTH, int(pulse_width))  # ns
            if start_threshold != np.inf:
                ctl.SetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_START_THRESHOLD, int(start_threshold))  # pm
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_MODE, ctl.ChannelOutputTriggerMode.POSITION_COMPARE)

            self.set_trigger_properties(channel, pulse_width, verbose)

        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
        except Exception as ex:
            self.error = (
                "Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            raise

    def set_trigger_properties(self, channel: int, pulse_width: int = 1000, verbose: bool = False):
        """
         Set position trigger parameters for a specific channel.

         :param channel: The channel number.
         :param pulse_width: The pulse width of the trigger output in ns. Default = 1000 ns
         :param verbose: Toggle the verbose output.
         """

        ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_PULSE_WIDTH, pulse_width)  # ns
        ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_POLARITY,
                            ctl.TriggerPolarity.ACTIVE_HIGH)
        ctl.SetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_VOLTAGE, ctl.IOModuleVoltage.VOLTAGE_3V3)
        if verbose: print("Configure the I/O module: (3.3V output voltage, driver enabled)")
        ctl.SetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_OPTIONS,
                            ctl.IOModuleOption.DIGITAL_OUTPUT_ENABLED)

    def DisablePositionTrigger(self, channel: int):
        """
        Disable position trigger for a specific channel.

        :param channel: The channel number.
        """
        try:
            # Disable the output trigger mode
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_MODE,
                                ctl.ChannelOutputTriggerMode.CONSTANT)
            ctl.SetProperty_i32(self.dHandle, channel, ctl.Property.IO_MODULE_OPTIONS,
                                0)  # Disable digital output driver circuit
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
        except Exception as ex:
            self.error = (
                "Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno))
            raise
    
    def confingure_stream_params(self,points: List[Tuple[int, ...]],pulse_width: int = 1000, verbose: bool = False):
        movement = Movement(self.dHandle, self.stream_manager.stream_handle)
        movement.configure_stream()
        for channel in points[0][::2]:
                movement.set_properties(channel)
                self.set_trigger_properties(channel, pulse_width, verbose)

    def SetUpStream(self, points: List[Tuple[int, ...]], trigger_mode: ctl.StreamTriggerMode):
        """
        Set up a stream for the specified channels using a given list of points.

        :param points: List of tuples containing stream data. Each tuple should have the format (ch_A, pos_A, ch_B, pos_B).
        :param trigger_mode: The trigger mode for the stream.
        :param stream_rate: The rate of advancement between frames in the stream when the triggering mode is direct (in Hz).
        :param pulse_width: The pulse width of the trigger output in ns. Default = 1000 ns
        :param verbose: Toggle the verbose output.
        """
        try:
            self.stream_manager.start_stream(points, trigger_mode)
        except Exception as ex:
            self.error = "Unexpected error: {}, {} in line: {}".format(ex, type(ex), sys.exc_info()[-1].tb_lineno)
            raise

    def set_in_position_delay(self, channel: int, delay: int = 2):
        """
        A channel is 'in position' when the positioner has been within the configured In Position Threshold
        near the target for minimum or longer than the configured delay and no commanded movement
        is currently executed.
        :param channel: The channel number.
        :param delay: Time required for the positioner to be considered "in position". Valid range: 0-10,000 ms
        """
        if 0 <= delay <= 10000:
            ctl.SetProperty_i32(self.dHandle,channel, ctl.Property.IN_POSITION_DELAY, int(delay))
        else:
            self.error = f"In position delay should be between 0 and 10,000ms. Received: {delay}"
            raise

    def set_in_position_threshold(self, channel: int, threshold: int = 10000):
        """
        A channel is 'in position' when the positioner has been within the configured In Position Threshold
        near the target for minimum or longer than the configured delay and no commanded movement
        is currently executed.

        :param channel: The channel number.
        :param threshold: Distance require for the positioner to be considered "in position". Valid range: 0-10^9 pm
        """
        if 0 <= threshold <= 1e9:
            ctl.SetProperty_i32(self.dHandle,channel, ctl.Property.IN_POSITION_THRESHOLD, int(threshold))
        else:
            self.error = f"In position delay should be between 0 and 1e9pm. Received: {threshold}"
            raise

    def is_streaming_active(self, channel: int) -> bool:
        """
        Check if streaming is active for the specified channel.

        :param channel: The channel number.
        :return: True if streaming is active, False otherwise.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return bool(ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.DEVICE_STATE)
                        & ctl.DeviceState.IS_STREAMING)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def is_amplifier_enabled(self, channel: int) -> bool:
        """
        Check if the amplifier is enabled for the specified channel.

        :param channel: The channel number.
        :return: True if the amplifier is enabled, False otherwise.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return bool(ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.AMPLIFIER_ENABLED))
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_io_module_options(self) -> int:
        """
        Retrieve the state of IO_MODULE_OPTIONS.

        :return: The state of IO_MODULE_OPTIONS.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_OPTIONS)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_pos_comp_direction(self, channel: int) -> int:
        """
        Retrieve the position comparison direction for the specified channel.

        :param channel: The channel number.
        :return: The position comparison direction.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CH_POS_COMP_DIRECTION)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_pos_comp_limit_min(self, channel: int) -> int:
        """
        Retrieve the minimum position comparison limit for the specified channel.

        :param channel: The channel number.
        :return: The minimum position comparison limit in picometers.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_LIMIT_MIN)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_pos_comp_limit_max(self, channel: int) -> int:
        """
        Retrieve the maximum position comparison limit for the specified channel.

        :param channel: The channel number.
        :return: The maximum position comparison limit in picometers.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_LIMIT_MAX)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_pos_comp_increment(self, channel: int) -> int:
        """
        Retrieve the position comparison increment for the specified channel.

        :param channel: The channel number.
        :return: The position comparison increment in picometers.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i64(self.dHandle, channel, ctl.Property.CH_POS_COMP_INCREMENT)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_output_trig_pulse_width(self, channel: int) -> int:
        """
        Retrieve the output trigger pulse width for the specified channel.

        :param channel: The channel number.
        :return: The output trigger pulse width in nanoseconds.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_PULSE_WIDTH)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_output_trig_polarity(self, channel: int) -> int:
        """
        Retrieve the output trigger polarity for the specified channel.

        :param channel: The channel number.
        :return: The output trigger polarity.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_POLARITY)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_output_trig_mode(self, channel: int) -> int:
        """
        Retrieve the output trigger mode for the specified channel.

        :param channel: The channel number.
        :return: The output trigger mode.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.CH_OUTPUT_TRIG_MODE)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    def get_io_module_voltage(self) -> float:
        """
        Retrieve the IO module voltage.

        :return: The IO module voltage as 5.0 or 3.3.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            voltage = ctl.GetProperty_i32(self.dHandle, 0, ctl.Property.IO_MODULE_VOLTAGE)
            if voltage == ctl.IOModuleVoltage.VOLTAGE_5V:
                return 5.0
            elif voltage == ctl.IOModuleVoltage.VOLTAGE_3V3:
                return 3.3
            else:
                raise ValueError("Unexpected IO module voltage value.")
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise
        except ValueError as ve:
            self.error = str(ve)
            raise

    def is_digital_output_enabled(self, channel: int) -> bool:
        """
        Check if the digital output is enabled for the specified channel.

        :param channel: The channel number.
        :return: True if digital output is enabled, False otherwise.
        :raises: ctl.Error if there is an error retrieving the property.
        """
        try:
            return bool(ctl.GetProperty_i32(self.dHandle, channel, ctl.Property.IO_MODULE_OPTIONS) & ctl.IOModuleOption.DIGITAL_OUTPUT_ENABLED)
        except ctl.Error as e:
            self.error = ("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
                          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code,
                                  sys.exc_info()[-1].tb_lineno))
            raise

    @staticmethod
    def get_smaract_error_name(error_code:int = 0) -> Optional[str]:
        hex_code = hex(error_code)
        for error_enum in ctl.ErrorCode:
            if hex(error_enum.value) == hex_code:
                return error_enum.name
        return None
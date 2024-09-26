
#!/usr/bin/python3
import sys
import smaract.ctl as ctl

# SmarAct MCS2 programming example: Closed-Loop Tip-Tilt Mirror-Mounts
#
# This programming example shows how to work with piezo driven
# closed-loop tip-tilt mirror-mounts.
#
# Please refer to the MCS2-UG00004_Closed_Loop_Tip_Tilt_Mirror_Mounts document
# for detailed information about the calibrating and referencing procedure of
# closed-loop tip-tilt mirror-mounts.
#
# For a full command reference see the MCS2 Programmers Guide.

def assert_lib_compatibility():
    """
    Checks that the major version numbers of the Python API and the
    loaded shared library are the same to avoid errors due to 
    incompatibilities.
    Raises a RuntimeError if the major version numbers are different.
    """
    vapi = ctl.api_version
    vlib = [int(i) for i in ctl.GetFullVersionString().split('.')]
    if vapi[0] != vlib[0]:
        raise RuntimeError("Incompatible SmarActCTL python api and library version.")

def waitWhile(channel, mask):
    """Wait until the specified channel state flags become true"""
    while(1):
        state = ctl.GetProperty_i32(d_handle, channel, ctl.Property.CHANNEL_STATE)
        if (state & mask) == 0:
            break

def getPositions(channels):
    """Read the current position of both channels"""
    pos = []
    for i in range(2):
        pos.append(ctl.GetProperty_i64(d_handle, channels[i], ctl.Property.POSITION))

    print("MCS2 position ch {}: {:.2f} degree, ch {}: {:.2f} degree".format(channels[0], (pos[0] / 1000000000.0), channels[1], (pos[1] / 1000000000.0)))

print("***************************************************************************")
print("*  SmarAct MCS2 Programming Example (Closed-Loop Tip-Tilt Mirror-Mounts)  *")
print("***************************************************************************")

# Read the version of the library
# Note: this is the only function that does not require the library to be initialized.
version = ctl.GetFullVersionString()
print("SmarActCTL library version: '{}'.".format(version))
assert_lib_compatibility()

# Find available MCS2 devices
try:
    buffer = ctl.FindDevices()
    if len(buffer) == 0:
        print("MCS2 no devices found.")
        raise ConnectionError
    locators = buffer.split("\n")
    for locator in locators:
        print("MCS2 available devices: {}".format(locator))
except:
    print("MCS2 failed to find devices. Exit.")
    input()
    sys.exit(1)

d_handle = None
try:
    # Open the first MCS2 device from the list
    d_handle = ctl.Open(locators[0])
    print("MCS2 opened {}.".format(locators[0]))

    # Specify the indexes of the two channels the mirror-mount is connected to.
    channels = [0, 1]
    # Verify that there is a stick-slip piezo driver available.
    type = ctl.GetProperty_i32(d_handle, 0, ctl.Property.MODULE_TYPE) 
    if type != ctl.ChannelModuleType.STICK_SLIP_PIEZO_DRIVER:
        print("MCS2 this is not a stick-slip piezo driver, abort.")
        ctl.Close(d_handle)
        input()
        sys.exit(1)

    # Configure both channels.
    # Note: sensor power mode, positioner type and safe direction are persistent properties.
    # There is in general no need to configure these in every session. We do it here for completeness of the example.
    for i in range(2):
        channel = channels[i]
        # Note: the "power save" sensor mode is not available for mirror-mounts.
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.SENSOR_POWER_MODE, ctl.SensorPowerMode.ENABLED)
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.MAX_CL_FREQUENCY, 5000)
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.HOLD_TIME, ctl.HOLD_TIME_INFINITE)
        # The correct positioner type must be configured to both channels.
        # Currently, the following mirror-mount positioner types are supported by the MCS2:
        # CT018/AT001 / ST...S1I1E2 (607) for STT25.4I-type mirror-mounts
        # CT041/AT001 / ST...S1I2E2 (608) for STT50.8I-type mirror-mounts
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.POSITIONER_TYPE, 607)
        # The safe direction must be set to "backward direction" for mirror-mounts.
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.SAFE_DIRECTION, ctl.BACKWARD_DIRECTION)
        # The logical scale offset property is used to shift the zero position to the middle of the movement range of the mirror mount.
        # Note: the offset value must be adjusted according to the travel range of the mirror-mount.
        ctl.SetProperty_i64(d_handle, channel, ctl.Property.LOGICAL_SCALE_OFFSET, 2500000000)
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.LOGICAL_SCALE_INVERSION, ctl.NON_INVERTED)
        # The calibration and referencing options should always be specified to define the behavior
        # before starting the actual calibration / referencing sequence.
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.CALIBRATION_OPTIONS, 0)
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.REFERENCING_OPTIONS, 0)
        # The move velocity and acceleration properties define the movement parameters for the calibration and referencing sequences.
        # The base unit is "degree" for mirror-mounts. The parameters must be given in nano degree (per second / per second ^2).
        ctl.SetProperty_i64(d_handle, channel, ctl.Property.MOVE_VELOCITY, 1000000000)
        ctl.SetProperty_i64(d_handle, channel, ctl.Property.MOVE_ACCELERATION, 10000000000)
 
    # Due to geometric effects, moving one axis of a mirror-mount may influence the endstop
    # position of the other. This effect can be eliminated by the following calibration procedure:
    # - Calibrate Channel A
    # - Reference Channel A
    # - Calibrate Channel B
    # - Reference Channel B
    # - Calibrate Channel A finally
    # - Reference Channel A finally
    print("*******************************************************")
    print("-> Press return to start the calibration sequence.")
    input()
    print("MCS2 start calibrating sequence...")
    for i in range (6):
        channel = channels[(int(i / 2) % 2)]  # ch=0,0,1,1,0,0
        idx = (i % 2)  # idx=0,1,0,1,0,1
        if idx == 0:
            ctl.Calibrate(d_handle, channel)
        else:
            ctl.Reference(d_handle, channel)
        waitWhile(channel, ctl.ChannelState.ACTIVELY_MOVING)
        # Check if the sequence was successful.
        state = ctl.GetProperty_i32(d_handle, channel, ctl.Property.CHANNEL_STATE)
        # The ctl.ChannelState.MOVEMENT_FAILED indicates a failed calibration / referencing.
        if (state & ctl.ChannelState.MOVEMENT_FAILED) != 0:
            # The channel error property may then be read to determine the reason of the error.
            error = ctl.GetProperty_i32(d_handle, channel, ctl.Property.CHANNEL_ERROR)
            print("MCS2 sequence failed: {} (0x{:04X}), channel {}, abort.".format(ctl.GetResultInfo(error), error, channel))
            ctl.Close(d_handle)
            input()
            sys.exit(1)
        else:
            if (idx == 0):
                print("MCS2 calibrating of channel {} done.".format(channel))
            else:
                print("MCS2 referencing of channel {} done.".format(channel))      
    print("MCS2 calibration sequence finished.")

    # The recommended procedure for referencing both axes (A and B) is as follows:
    # - Reference Channel A
    # - Reference Channel B
    # - Reference Channel A finally
    print("*******************************************************")
    print("-> Press return to start the referencing sequence.")
    input()
    print("MCS2 start referencing sequence...")
    for i in range(3):
        channel = channels[(i % 2)] # ch=0,1,0
        ctl.Reference(d_handle, channel)
        waitWhile(channel, ctl.ChannelState.ACTIVELY_MOVING)
        # Check if the sequence was successful.
        state = ctl.GetProperty_i32(d_handle, channel, ctl.Property.CHANNEL_STATE)
        # The ctl.ChannelState.MOVEMENT_FAILED indicates a failed referencing.
        if (state & ctl.ChannelState.MOVEMENT_FAILED) != 0:
            # The channel error property may then be read to determine the reason of the error.
            error = ctl.GetProperty_i32(d_handle, channel, ctl.Property.CHANNEL_ERROR)
            print("MCS2 sequence failed: {} (0x{:04X}), channel {}, abort.".format(ctl.GetResultInfo(error), error, channel))
            ctl.Close(d_handle)
            input()
            sys.exit(1)
        else:
            print("MCS2 referencing of channel {} done.".format(channel))
    print("MCS2 referencing sequence finished.")
    # Read current positions of both axes.
    getPositions(channels)

    print("*******************************************************")
    print("-> Press return to start the movement.")
    input()
    # Move both axes to approx. the middle of the movement range.
    for i in range(2):
        channel = channels[i]
        ctl.SetProperty_i32(d_handle, channel, ctl.Property.MOVE_MODE, ctl.MoveMode.CL_ABSOLUTE)
        ctl.SetProperty_i64(d_handle, channel, ctl.Property.MOVE_VELOCITY, 1000000000)
        ctl.SetProperty_i64(d_handle, channel, ctl.Property.MOVE_ACCELERATION, 10000000000)
        ctl.Move(d_handle, channel, 0)
        waitWhile(channel, ctl.ChannelState.ACTIVELY_MOVING)
        getPositions(channels)

except ctl.Error as e:
    # Passing an error code to "GetResultInfo" returns a human readable string
    # specifying the error.
    print("MCS2 {}: {}, error: {} (0x{:04X}) in line: {}."
          .format(e.func, ctl.GetResultInfo(e.code), ctl.ErrorCode(e.code).name, e.code, (sys.exc_info()[-1].tb_lineno)))

except Exception as ex:
    print("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
    raise

finally:
    # Before closing the program the connection to the device must be closed by calling "Close".
    if d_handle != None:
        ctl.Close(d_handle)
    print("MCS2 close.")
    print("*******************************************************")
    print("Done. Press return to exit.")
    input()

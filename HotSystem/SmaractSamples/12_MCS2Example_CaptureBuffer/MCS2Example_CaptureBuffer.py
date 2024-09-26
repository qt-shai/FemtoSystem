#!/usr/bin/python3
import sys
import smaract.ctl as ctl
import numpy as np
import matplotlib.pyplot as plt

# SmarAct MCS2 programming example: Capture Buffer
#
# This programming example shows you how to use the
# capture buffer.

# Note that this feature requires a feature permission.
# If the feature is not unlocked on the controller a
# PERMISSION_DENIED error is returned when starting or
# reading the capture buffer.

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

def initialize_channel(ch):
    # Start by setting some general channel properties.
    type = ctl.GetProperty_i32(d_handle, ch, ctl.Property.CHANNEL_TYPE)
    if type == ctl.ChannelModuleType.STICK_SLIP_PIEZO_DRIVER:
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.MAX_CL_FREQUENCY, 6000)
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.HOLD_TIME, 1000)
    elif type == ctl.ChannelModuleType.PIEZO_SCANNER_DRIVER:
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.HOLD_TIME, 1000)
    elif type == ctl.ChannelModuleType.MAGNETIC_DRIVER:
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)

def show_capture_buffer_config(mod):
    dataset = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_DATASET_TYPE)
    pos_type = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_POSITION_TYPE, 2)
    pos_index = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_POSITION_INDEX, 2)
    aux_index = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_AUX_INPUT_INDEX, 4)
    pos = ["cur", "tar"]
    print("MCS2 capture buffer config:")
    if dataset == ctl.CaptureBufferDataset.TYPE_0:
        print("MCS2 Pos32[1] | Pos32[0]")
        print("MCS2 {}{}     | {}{}".format(pos[pos_type[1]], pos_index[1], pos[pos_type[0]], pos_index[0]))
    elif dataset == ctl.CaptureBufferDataset.TYPE_1:
        print("MCS2 Pos24[1] | Pos24[0] | Aux16[0]")
        print("MCS2 {}{}     | {}{}     | {}".format(pos[pos_type[1]], pos_index[1], pos[pos_type[0]], pos_index[0], aux_index[0]))
    elif dataset == ctl.CaptureBufferDataset.TYPE_2:
        print("MCS2 Pos48[0] | Aux16[0]")
        print("MCS2 {}{}     | {}".format(pos[pos_type[0]], pos_index[0], aux_index[0]))
    elif dataset == ctl.CaptureBufferDataset.TYPE_3:
        print("MCS2 Aux16[3] | Aux16[2] | Aux16[1] | Aux16[0]")
        print("MCS2 Aux{}     | Aux{}     | Aux{}     | Aux{}".format(aux_index[3],aux_index[2], aux_index[1], aux_index[0]))

def stop_capture(mod):
    ctl.SetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_ACTIVE, ctl.CaptureBuffer.INACTIVE)

def start_capture(mod, capture_rate, dataset=ctl.CaptureBufferDataset.TYPE_0):
    # Configure capture sources.
    pos_type = [0, 1]        # current position, target position
    pos_index = [0, 0]       # ch0, ch0
    aux_index = [0, 1, 2, 3] # aux input 0 - 3
    ctl.SetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_DATASET_TYPE, dataset)
    ctl.SetPropertyArray_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_POSITION_TYPE, pos_type)
    ctl.SetPropertyArray_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_POSITION_INDEX, pos_index)
    ctl.SetPropertyArray_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_AUX_INPUT_INDEX, aux_index)

    # Note: not all capture rates may actually be used. When setting a capture rate the
    # controller will pick the closest possible rate. Read back the property to determine
    # the real rate.
    ctl.SetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_RATE, capture_rate)
    capture_rate_real = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_RATE)
    print("MCS2 requested capture rate: {} Hz, set capture rate: {} Hz".format(capture_rate, capture_rate_real))
    buffer_size = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_SIZE)
    if (buffer_size == 0):
        print("MCS2 this controller does not support the capture buffer feature")
        return False
    max_capture_time = buffer_size / capture_rate_real
    print("MCS2 max capture time: {} s".format(max_capture_time))
    # Start capture instantly (no trigger condition).
    ctl.SetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_TRIGGER_MODE, ctl.CaptureBufferTriggerMode.DIRECT)
    ctl.SetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_ACTIVE, ctl.CaptureBuffer.ACTIVE)
    return True

def read_capture_buffer(mod, data_set):
    print("MCS2 reading capture buffer...")
    buffer_size = ctl.GetProperty_i32(d_handle, mod, ctl.Property.CAPTURE_BUFFER_SIZE)
    # To read large buffers from the controller the GetPropertyBuffer_i32/_64 function must be used.
    buffer = ctl.GetPropertyBuffer_i64(d_handle, mod, ctl.Property.CAPTURE_BUFFER_DATA, buffer_size)
    print("MCS2 max. buffer size: {}, captured samples: {}".format(buffer_size, len(buffer)))

    samples = []
    for value in buffer:
        from_bytes = lambda range, signed: int.from_bytes(bytes[range], byteorder="little", signed=signed)
        # Note: using bitwise operators does not really work in python since there are signed/unsigned issues.
        # Thus we are using int.to_bytes() and int.from_bytes() here instead.
        bytes = value.to_bytes(length=8, byteorder="little", signed=True)
        a = 0; b = 0; c = 0; d = 0
        if data_set == ctl.CaptureBufferDataset.TYPE_0:
            # Pos32[1] | Pos32[0]
            a = from_bytes(slice(0,4), True) / 1000  # val is in nm -> to um
            b = from_bytes(slice(4,8), True) / 1000
        elif data_set == ctl.CaptureBufferDataset.TYPE_1:
            # Pos24[1] | Pos24[0] | Aux16[0]
            a = from_bytes(slice(0,2), False) / (2 ** 16 - 1)  # in 16bit ADC increments
            b = from_bytes(slice(2,5), True) / 1000  # val is in nm -> to um
            c = from_bytes(slice(5,8), True) / 1000  # val is in nm -> to um
        elif data_set == ctl.CaptureBufferDataset.TYPE_2:
            # Pos48[0] | Aux16[0]
            a = from_bytes(slice(0,2), False) / (2 ** 16 - 1)  # in 16bit ADC increments
            b = from_bytes(slice(2,8), True) / 1000000  # val is in pm -> to um
        elif data_set == ctl.CaptureBufferDataset.TYPE_3:
            # Aux16[3] | Aux16[2] | Aux16[1] | Aux16[0]
            a = from_bytes(slice(0,2), False) / (2 ** 16 - 1)  # in 16bit ADC increments
            b = from_bytes(slice(2,4), False) / (2 ** 16 - 1)
            c = from_bytes(slice(4,6), False) / (2 ** 16 - 1)
            d = from_bytes(slice(6,8), False) / (2 ** 16 - 1)
        samples.append((a, b, c, d))
    return samples

def plot_data(data, dataset):
    figure, ax = plt.subplots()
    data = np.array(data)
    y1 = data[:, 0]
    y2 = data[:, 1]
    y3 = data[:, 2]
    y4 = data[:, 3]
    t = np.linspace(0, y1.size, y1.size)
    ax.plot(t, y1, color="red")
    ax.plot(t, y2, color="green")
    ax.plot(t, y3, color="blue")
    ax.plot(t, y4, color="yellow")
    plt.show()

def wait_while_moving(ch, mod):
    cb_active = False
    while(1):
        state = ctl.GetProperty_i32(d_handle, ch, ctl.Property.CHANNEL_STATE)
        # The ChannelState.MOVEMENT_FAILED channel state flag indicates a failed movement.
        if ((state & ctl.ChannelState.MOVEMENT_FAILED) != 0):
            # The channel error property may then be read to determine the reason of the error.
            error = ctl.GetProperty_i32(d_handle, ch, ctl.Property.CHANNEL_ERROR)
            print("MCS2 movement failed: {} (error: 0x{:04X}), abort.".format(ctl.GetResultInfo(error), error))
            return False
        if ((state & ctl.ChannelState.ACTIVELY_MOVING) == 0):
            return True  # The movement has finished.

        # The state of the capture buffer may be obtained via events or property polling.
        # For demonstration only this is shown here while waiting for a movement to finish:
        # A CAPTURE_BUFFER_STATE_CHANGED event informs about the current state of the capture.
        try:
            event = ctl.WaitForEvent(d_handle, 10)
            if (event.type == ctl.EventType.CAPTURE_BUFFER_STATE_CHANGED):
                print("MCS2 received event: {}".format(ctl.GetEventInfo(event)))
        except ctl.Error as e:
            # Ignore timeout here
            if e.code == ctl.ErrorCode.TIMEOUT:
                pass
        # Alternatively, the MODULE_STATE property may be polled to get the current state.
        state = ctl.GetProperty_i32(d_handle, mod, ctl.Property.MODULE_STATE)
        active = ((state & ctl.ModuleState.CAPTURE_BUFFER_ACTIVE) != 0)
        if cb_active != active:
            print("MCS2 capture buffer state changed ({}).".format(active))
            cb_active = active

print("*******************************************************")
print("*  SmarAct MCS2 Programming Example (Capture Buffer)  *")
print("*******************************************************")

# Read the version of the library
# Note: this is the only function that does not require the library to be initialized.
version = ctl.GetFullVersionString()
print("SmarActCTL library version: '{}'.".format(version))
assert_lib_compatibility()

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

    ch_idx = 0
    # Note that the capture buffer is a module function therefore the module index
    # must be passed to all capture buffer properties.
    mod_idx = 0

    initialize_channel(ch_idx)
    stop_capture(mod_idx)

    print("MCS2 move to start position...")
    ctl.SetProperty_i32(d_handle, ch_idx, ctl.Property.MOVE_MODE, ctl.MoveMode.CL_ABSOLUTE)
    ctl.SetProperty_i64(d_handle, ch_idx, ctl.Property.MOVE_VELOCITY, 1000000000)  # pm/s
    ctl.SetProperty_i64(d_handle, ch_idx, ctl.Property.MOVE_ACCELERATION, 10000000000)  # pm/s2
    ctl.Move(d_handle, ch_idx, 0)
    wait_while_moving(ch_idx, mod_idx)
    print("MCS2 movement finished.")

    # Start a closed loop movement and capture current position and target position.
    dataset = ctl.CaptureBufferDataset.TYPE_0
    capture_rate = 1000  # Hz

    if start_capture(mod_idx, capture_rate, dataset):
        show_capture_buffer_config(mod_idx)
        print("MCS2 start movement...")
        ctl.SetProperty_i64(d_handle, ch_idx, ctl.Property.MOVE_VELOCITY, 10000000)  # pm/s
        ctl.SetProperty_i64(d_handle, ch_idx, ctl.Property.MOVE_ACCELERATION, 100000000)  # pm/s2
        ctl.Move(d_handle, ch_idx, 10000000)
        wait_while_moving(ch_idx, mod_idx)
        print("MCS2 movement finished.")
        # The capture may be stopped manually or it is stopped automatically when the buffer is full.
        stop_capture(mod_idx)
        # The capture must be stopped before the data can be read.
        b = read_capture_buffer(mod_idx, dataset)
        plot_data(b, dataset)

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

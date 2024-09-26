#!/usr/bin/python3
import sys
import smaract.ctl as ctl

# SmarAct MCS2 programming example: Wave Form Generator
#
# This programming example shows you how to use the
# wave form generator to perform closed-loop movements.
# For a full command reference see the MCS2 Programmers Guide.

class WfgConfig():
    def __init__(self):
        self._wave_form = ctl.WaveForm.CONST
        self._symmetry = 0      # permille
        self._hold = 0          # permille
        self._no_of_steps = 1   # no
        self._period = 1000000  # us
    def __call__(self, wave_form = ctl.WaveForm.CONST, symmetry = 0, hold = 0, no_of_steps = 1, period = 1000000):
        self._wave_form = wave_form
        self._symmetry = symmetry
        self._hold = hold
        self._no_of_steps = no_of_steps
        self._period = period

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
        # Enable the amplifier.
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
        # Set max closed loop frequency (maxCLF) to 6 kHz. This properties sets a limit for the maximum actuator driving frequency.
        # The maxCLF is not persistent thus set to a default value at startup.
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.MAX_CL_FREQUENCY, 6000)
        # The hold time specifies how long the position is actively held after reaching the target.
        # This property is also not persistent and set to zero by default.
        # A value of 0 deactivates the hold time feature, the constant ctl.HOLD_TIME_INFINITE sets the time to infinite.
        # (Until manually stopped by "Stop") Here we set the hold time to 1000 ms.
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.HOLD_TIME, 1000)
    elif type == ctl.ChannelModuleType.PIEZO_SCANNER_DRIVER:
        # Enable the amplifier.
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)
        # The hold time specifies how long the position is actively held after reaching the target.
        # This property is also not persistent and set to zero by default.
        # A value of 0 deactivates the hold time feature, the constant ctl.HOLD_TIME_INFINITE sets the time to infinite.
        # (Until manually stopped by "Stop") Here we set the hold time to 1000 ms.
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.HOLD_TIME, 1000)
    elif type == ctl.ChannelModuleType.MAGNETIC_DRIVER:
        # Enable the amplifier (and start the phasing sequence).
        ctl.SetProperty_i32(d_handle, ch, ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)

    # Enable the "move-to-start" option and set velocity and accelleration for the initial movement.
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.POSITIONER_CONTROL_OPTIONS, ctl.PosControlOption.WFG_MOVE_TO_START)
    ctl.SetProperty_i64(d_handle, ch, ctl.Property.MOVE_VELOCITY, 100000000)  # pm/s
    ctl.SetProperty_i64(d_handle, ch, ctl.Property.MOVE_ACCELERATION, 1000000000)  # pm/s2

def wait_while_moving(ch):
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

def configure_wave_form(ch, signal, amp_mod, f_mod, delay, amplitude, offset):
    # Configure the wave form generator:
    # Note that the internal calculation of the signal buffers may take a decent amount of time
    # (up to 20 ms per channel). Therefore the wave form should be prepared in advance before starting
    # the movement, especially when using command groups to synchronize several moves for different
    # channels and when low delays are required.
    # Depending on the actual wave form not all properties have a meaning, however we set them all here
    # for completeness.

    # Scaling and timing
    ctl.SetProperty_i64(d_handle, ch, ctl.Property.WFG_SIGNAL_AMPLITUDE, amplitude)  # pm
    ctl.SetProperty_i64(d_handle, ch, ctl.Property.WFG_SIGNAL_OFFSET, offset)  # pm
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_DELAY, delay)  # us

    # Signal
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_SYMMETRY, signal._symmetry)  # permille
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_HOLD, signal._hold)  # permille
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_NUMBER_OF_STEPS, signal._no_of_steps)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_PERIOD, signal._period)  # us
    # Important note: the wave form property must be set after symmetry, hold and number of steps to
    # trigger the internal calculation of the signal buffers.
    # If this is ignored, then a WFG_BUFFER_NOT_READY error is generated when the movement is started.
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_SIGNAL_WAVE_FORM, signal._wave_form)
    # Amplitude modulation
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_AMP_MOD_SYMMETRY, amp_mod._symmetry)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_AMP_MOD_HOLD, amp_mod._hold)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_AMP_MOD_NUMBER_OF_STEPS, amp_mod._no_of_steps)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_AMP_MOD_PERIOD, amp_mod._period)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_AMP_MOD_WAVE_FORM, amp_mod._wave_form)
    # Frequency modulation
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_FREQ_MOD_SYMMETRY, f_mod._symmetry)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_FREQ_MOD_HOLD, f_mod._hold)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_FREQ_MOD_NUMBER_OF_STEPS, f_mod._no_of_steps)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_FREQ_MOD_PERIOD, f_mod._period)
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.WFG_FREQ_MOD_WAVE_FORM, f_mod._wave_form)

    # Read the starting position which results from the previous configuration.
    # When using the "move-to-start" positioner control option this position is autoamtically
    # targeted with a regular point-to-point movement before the actual wave form generation starts.
    start_pos = ctl.GetProperty_i64(d_handle, ch, ctl.Property.WFG_START_POSITION)
    print("MCS2 channel {} wave form starting position: {} pm.".format(ch, start_pos))

def start_wave_form_movement(ch, number_of_periods):
    ctl.SetProperty_i32(d_handle, ch, ctl.Property.MOVE_MODE, ctl.MoveMode.CL_WFG)
    print("MCS2 start the wfg movement with {} periods...".format(number_of_periods))
    # The parameter of the Move() function specifies the number of periods or repetitions of the wave form.
    ctl.Move(d_handle, ch, number_of_periods)
    # Wait for the movement to finish.
    if (wait_while_moving(ch)):
        print("MCS2 movement done.")

def start_xy_wave_form_movement(x_ch, y_ch, x_periods, y_periods):
    ctl.SetProperty_i32(d_handle, x_ch, ctl.Property.MOVE_MODE, ctl.MoveMode.CL_WFG)
    ctl.SetProperty_i32(d_handle, y_ch, ctl.Property.MOVE_MODE, ctl.MoveMode.CL_WFG)
    print("MCS2 MCS2 start synchronized wfg movement with {} x-periods, {} y-periods...".format(x_periods, y_periods))
    # To synchronize the wave form movements of different channels the Move commands
    # of all channels must be grouped to a command group. For this simply surround the commands
    # with calls to the OpenCommandGroup and CloseCommandGroup functions.
    # This way the wave form execution of all channels start at the exact same time.
    # Since the "move-to-start" positioner control option is set all grouped channels move to
    # their starting position and wait for all other channels to reach their starting position
    # before the actual wave form generation is started.
    t_handle = ctl.OpenCommandGroup(d_handle, ctl.CmdGroupTriggerMode.DIRECT)
    ctl.Move(d_handle, x_ch, x_periods, t_handle)
    ctl.Move(d_handle, y_ch, y_periods, t_handle)
    ctl.CloseCommandGroup(d_handle, t_handle)
    # Wait for the movement to finish.
    x_ok = wait_while_moving(x_ch)
    y_ok = wait_while_moving(y_ch)
    if (x_ok and y_ok):
        print("MCS2 x/y movement done.")

def start_line_scan(x_ch, y_ch, edge_length, duration, number_of_lines):
    signal = WfgConfig()
    amp_mod = WfgConfig()
    f_mod = WfgConfig()
    # The x-channel performs a staircase movement where each step represents the position of one line.
    # The hold parameter defines the 'move to the next line' phase.
    signal(ctl.WaveForm.STAIRCASE, symmetry=0, hold=-800, no_of_steps=number_of_lines, period=duration)
    configure_wave_form(x_ch, signal, amp_mod, f_mod, 0, edge_length, 0)
    # The y-channel performs a sawtooth movements where the rising edge represents the
    # 'scanning' phase and the falling edge represents the 'move back to line start' phase.
    signal(ctl.WaveForm.SAWTOOTH, symmetry=800, hold=0, period=int(duration/number_of_lines))
    configure_wave_form(y_ch, signal, amp_mod, f_mod, 0, edge_length, 0)
    print("MCS2 configure 'x/y line scan' with {} lines and {} pm edge-length.".format(number_of_lines, edge_length))
    start_xy_wave_form_movement(x_ch, y_ch, 1, number_of_lines)

def start_snake_scan(x_ch, y_ch, edge_length, duration, number_of_lines):
    signal = WfgConfig()
    amp_mod = WfgConfig()
    f_mod = WfgConfig()
    # The x-channel performs a staircase movement where each step represents the position of one line.
    # The hold parameter defines the 'move to the next line' phase.
    signal(ctl.WaveForm.STAIRCASE, symmetry=0, hold=-800, no_of_steps=number_of_lines, period=duration)
    configure_wave_form(x_ch, signal, amp_mod, f_mod, 0, edge_length, 0)
    # The y-channel performs a sawtooth movements where the rising edge represents the
    # 'scanning forward' phase and the falling edge represents the 'scanning backward' phase.
    # The hold parameter must be used to include a 'hold position' phase where the other channel
    # is moving to the next line.
    signal(ctl.WaveForm.SAWTOOTH, symmetry=500, hold=200, period=int(duration/(number_of_lines/2)))
    configure_wave_form(y_ch, signal, amp_mod, f_mod, 0, edge_length, 0)
    print("MCS2 configure 'x/y snake scan' with {} lines and {} pm edge-length.".format(number_of_lines, edge_length))
    start_xy_wave_form_movement(x_ch, y_ch, 1, int(number_of_lines/2))

def start_spiral_scan(x_ch, y_ch, diameter, dir=False, clv=False):
    signal = WfgConfig()
    amp_mod = WfgConfig()
    f_mod = WfgConfig()
    periods = 30     # Spiral pitch
    period = 100000  # Base signal period
    # Define starting position depending on the spiral move direction.
    offset = 0
    if dir:
        offset = int(-diameter / 2)
    if clv:
        # Constant linear velocity (CLV) spiral movement requires a special amplitude and frequency modulation
        # the CLV wave form specifies if the spiral starts from the center or from the extreme end.
        period = 1000
        if dir:
            amp_mod(ctl.WaveForm.CLV_INWARD, period=2000000)
            f_mod(ctl.WaveForm.CLV_INWARD, period=2000000)
        else:
            amp_mod(ctl.WaveForm.CLV_OUTWARD, period=2000000)
            f_mod(ctl.WaveForm.CLV_OUTWARD, period=2000000)
    else:
        # Constant angular velocity (CAV) spiral movement requires a sawtooth amplitude modulation
        # and no frequency modulation.
        period = 100000
        symmetry = 0
        if not dir:
            symmetry = 1000
        amp_mod(ctl.WaveForm.SAWTOOTH, symmetry=symmetry, hold=0, period=(periods * period))
    # x- and y-channel perform a sin/cosine wave form resulting in a circle/spiral movement.
    signal(ctl.WaveForm.SINE, period=period, hold=0)
    configure_wave_form(x_ch, signal, amp_mod, f_mod, 0, diameter, 0)
    signal(ctl.WaveForm.SINE, period=period, hold=250)
    configure_wave_form(y_ch, signal, amp_mod, f_mod, 0, diameter, 0)
    print("MCS2 configure 'x/y spiral scan' with {} pm diameter.".format(diameter))
    start_xy_wave_form_movement(x_ch, y_ch, periods, periods)

def printMenu():
    print("*******************************************************")
    print("WARNING: make sure the positioner can move freely\n \
            without damaging other equipment!")
    print("*******************************************************")
    print("Enter command and return:")
    print("[?] print this menu")
    print("[s] stop")
    print("[1-8] start one-channel wave form movement with different patterns")
    print("[a] start x/y line scan pattern")
    print("[b] start x/y snake scan pattern")
    print("[c] start x/y spiral scan, constant angular velocity (CAV) pattern")
    print("[d] start x/y spiral scan, constant linear velocity (CLV) pattern")
    print("[q] quit")

# STOP
# This command stops any ongoing movement. It also stops the hold position feature of a closed loop command.
# Note for closed loop movements with acceleration control enabled:
# The first "stop" command sent while moving triggers the positioner to come to a halt by decelerating to zero.
# A second "stop" command triggers a hard stop ("emergency stop").
def stop(ch):
    print("MCS2 stop channel: {}.".format(ch))
    ctl.Stop(d_handle, ch)  # soft stop
    ctl.Stop(d_handle, ch)  # hard stop

print("*******************************************************")
print("*  SmarAct MCS2 Programming Example (WFG)             *")
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

    # Prerequirements:
    # - one (or two) linear positioners with integrated sensor must be connected to channel 0 (and channel 1)
    # - the correct positioner types must be configured
    # - the channels must be calibrated
    # - the resonance frequencies must have been determined and configured (scanner piezo channels only)
    # - the channels must be positioned to the center of the movement range
    # -> The MCS2ServiceTool may be used to perform these tasks

    x_channel = 0
    y_channel = 1
    initialize_channel(x_channel)
    initialize_channel(y_channel)

    printMenu()
    while True:
        # Global wave form configuration
        number_of_periods = 10
        delay = 0
        amplitude = 20000000  # pm
        offset = 0  # pm
        signal = WfgConfig()
        amp_mod = WfgConfig()
        f_mod = WfgConfig()

        key = input()
        if key == '?':
            printMenu()
        elif key == 's':
            stop(x_channel)
        elif key == '1':
            signal(ctl.WaveForm.SAWTOOTH, symmetry=1000, hold=0, period=100000)
            amp_mod()  # Disable amplitude modulation
            f_mod()    # Disable frequency modulation
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'symmetric triangle' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '2':
            signal(ctl.WaveForm.SAWTOOTH, symmetry=750, hold=-250, period=100000)
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'sawtooth with hold' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '3':
            signal(ctl.WaveForm.STAIRCASE, no_of_steps=4, hold=-700, period=100000)  # start with 'hold' phase
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'staircase with neg. hold' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '4':
            signal(ctl.WaveForm.STAIRCASE, no_of_steps=4, hold=500, period=100000)  # start with 'signal' phase
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'staircase with pos. hold' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '5':
            signal(ctl.WaveForm.SINE, period=100000, hold=0)
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'sine' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '6':
            signal(ctl.WaveForm.SINE, period=100000, hold=0)
            # Note: the modulation period must be set to a multiple of the signal period (10 signal periods * 100ms = 1000ms)
            amp_mod(ctl.WaveForm.SAWTOOTH, symmetry=1000, hold=0, period=1000000)
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'sine with sawtooth amp. modulation' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '7':
            signal(ctl.WaveForm.SINE, period=100000, hold=250)
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'cosine' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == '8':
            signal(ctl.WaveForm.CONST, period=100000)
            amp_mod()
            f_mod()
            configure_wave_form(x_channel, signal, amp_mod, f_mod, delay, amplitude, offset)
            print("MCS2 set wave form 'constant' with {} us period and {} pm amplitude.".format(signal._period, amplitude))
            start_wave_form_movement(x_channel, number_of_periods)
        elif key == 'a':
            start_line_scan(x_channel, y_channel, amplitude, 1000000, 8)
        elif key == 'b':
            start_snake_scan(x_channel, y_channel, amplitude, 1000000, 8)
        elif key == 'c':
            start_spiral_scan(x_channel, y_channel, amplitude, dir=False, clv=False)
        elif key == 'd':
            start_spiral_scan(x_channel, y_channel, amplitude, dir=False, clv=True)
        elif key == 'q':
            break

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

import smaract.ctl as ctl
from typing import List, Tuple


class Movement:
    def __init__(self, device_handle, stream_handle):
        self.device_handle = device_handle
        self.stream_handle = stream_handle

    def set_properties(self, channel: int):
        # ctl.SetProperty_i64(self.device_handle, channel, ctl.Property.POSITION, 0)
        ctl.SetProperty_i32(self.device_handle, int(channel), ctl.Property.SENSOR_POWER_MODE, ctl.SensorPowerMode.ENABLED)
        ctl.SetProperty_i32(self.device_handle, int(channel), ctl.Property.AMPLIFIER_ENABLED, ctl.TRUE)

    def configure_stream(self, stream_rate: int = 1000):
        """
        Set up a parameters of the stream

        :param channel: The channel to be configured
        :param stream_rate: The rate of advancement between frames in the stream when the triggering mode is direct (in Hz).
        """
        ctl.SetProperty_i32(self.device_handle, 0, ctl.Property.DEV_INPUT_TRIG_MODE, ctl.DeviceInputTriggerMode.STREAM)
        ctl.SetProperty_i32(self.device_handle, 0, ctl.Property.DEV_INPUT_TRIG_CONDITION, ctl.TriggerCondition.RISING)
        # ctl.SetProperty_i32(self.device_handle, 0, ctl.Property.STREAM_EXT_SYNC_RATE, stream_rate)
        # ctl.SetProperty_i32(self.device_handle, 0, ctl.Property.STREAM_BASE_RATE, stream_rate)

        # Disable motion stream interpolation option - enable fast movements inside a motion stream
        ctl.SetProperty_i32(self.device_handle, 0, ctl.Property.STREAM_OPTIONS, ctl.StreamOption.INTERPOLATION_DIS)

    def open_stream(self, trigger_mode: ctl.StreamTriggerMode):
        self.stream_handle = ctl.OpenStream(self.device_handle, trigger_mode)

    def close_stream(self):
        ctl.CloseStream(self.device_handle, self.stream_handle)

    def move_to_position(self, x: int, y: int, z: int):
        # Assuming channels 0, 1, 2 correspond to X, Y, Z
        ctl.Move(self.device_handle, 0, x, 0)
        ctl.Move(self.device_handle, 1, y, 0)
        ctl.Move(self.device_handle, 2, z, 0)

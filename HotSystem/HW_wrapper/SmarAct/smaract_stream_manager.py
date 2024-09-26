from threading import Event
import smaract.ctl as ctl
from typing import List, Tuple, Union


class StreamManager:
    def __init__(self, d_handle):
        self.device_handle = d_handle
        self.stream_done = Event()
        self.stream_abort = Event()
        self.stream_handle = None

    def wait_for_stream_done(self):
        while True:
            try:
                event = ctl.WaitForEvent(self.device_handle, ctl.INFINITE)
                if event.type == ctl.EventType.STREAM_FINISHED:
                    if ctl.EventParameter(event.i32) == ctl.ErrorCode.NONE:
                        self.stream_done.set()
                    elif ctl.EventParameter(event.i32) == ctl.ErrorCode.ABORTED:
                        self.stream_done.set()
                        self.stream_abort.set()
                    else:
                        self.stream_done.set()
                        self.stream_abort.set()
            except ctl.Error as e:
                if e.code == ctl.ErrorCode.CANCELED:
                    print("Wait for event canceled.")
                else:
                    print("Error:", ctl.GetResultInfo(e.code))
                return

    def start_stream(self, points: List[Tuple[int, ...]], trigger_mode: ctl.StreamTriggerMode):
        if not type(points) is list or not len(points[0]) in [2,4,6]:
            raise ValueError("Point must be a tuple of 1, 2, or 3 pairs of integers.")
        self.stream_handle = ctl.OpenStream(self.device_handle, trigger_mode)
        for point in points:
            frame = list(point)
            ctl.StreamFrame(self.device_handle, self.stream_handle, frame)
        ctl.CloseStream(self.device_handle, self.stream_handle)

    def close_stream(self):
        if self.stream_handle:
            ctl.CloseStream(self.device_handle, self.stream_handle)    


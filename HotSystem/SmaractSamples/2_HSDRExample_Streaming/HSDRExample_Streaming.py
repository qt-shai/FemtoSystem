#!/usr/bin/python3

# SmarAct MCS2 High-Speed-Data-Reader (HSDR) programming example:
# streaming
#
# This programming example shows you how to connect to a
# SmarAct MCS2 HSDR device and and configure and start
# a data stream.
#
# See the MCS2 HSDR Programmers Guide for more information.

import sys
import optparse
import threading
import smaract.si as si
import smaract.hsdr as hsdr


handle = None

def parse_command_line_options():
    # Get locator used to connect to the device.
    # Default locator connects to the first USB device found.
    parser = optparse.OptionParser()
    parser.add_option( "-l", dest="locator", default="usb:ix:0")
    options, args = parser.parse_args()
    return options
    
class DataSourceDescription:
    def __init__(self, component_id, component_index, data_source_type):
        self.component_id = component_id
        self.component_index = component_index
        self.data_source_type = data_source_type

    def __eq__(self, other):
        if not isinstance(other, DataSourceDescription):
            return NotImplemented
        return (self.component_id, self.component_index, self.data_source_type) == (other.component_id, other.component_index, other.data_source_type)

class DataSourceAddress:
    def __init__(self, channel_index, data_source_index):
        self.channel_index = channel_index
        self.data_source_index = data_source_index

class DataSource:
    def __init__(self, address = None, data_type = 0, name = ""):
        self.address = address
        self.data_type = data_type
        self.name = name

class StreamConfig:
    def __init__(self, enabled_data_sources = None, interleaving_enabled = False, frame_aggregation = 0, stream_buffer_aggregation = 0, frame_rate = 0, precise_frame_rate = 0, number_of_stream_buffers = 0):
        self.enabled_data_sources = enabled_data_sources or []
        self.interleaving_enabled = interleaving_enabled
        self.frame_aggregation = frame_aggregation
        self.stream_buffer_aggregation = stream_buffer_aggregation
        self.frame_rate = frame_rate
        self.precise_frame_rate = precise_frame_rate
        self.number_of_stream_buffers = number_of_stream_buffers

class DataSourceData:
    def __init__(self, data = None):
        self.data = data or []

class StreamData:
    def __init__(self, data_source = None):
        self.data_source = data_source or {}

stream_data = StreamData()

def enable_data_sources(handle, stream_config, data_sources_to_enable):
    """
    Enables a data source for streaming and updates the frame size. The frame
    size is used for decoding the stream later.
    Each data source to enable is identified by a DataSourceDescription class.
    The function automatically determines the channel and data source indexes.
    """
    # iterate over all channels
    number_of_channels = si.GetProperty_i32(handle, si.EPK(si.Property.NUMBER_OF_CHANNELS,0,0))
    for ch in range(number_of_channels):
        # iterate over all data sources of the current channel
        number_of_data_sources = si.GetProperty_i32(handle, si.EPK(si.Property.NUMBER_OF_DATA_SOURCES,ch,0))
        for ds in range(number_of_data_sources):
            # retrieve component ID, component index and type of the data source
            component_id = si.GetProperty_i32(handle, si.EPK(si.Property.COMPONENT_ID,ch,ds))
            component_index = si.GetProperty_i32(handle, si.EPK(si.Property.COMPONENT_INDEX,ch,ds))
            data_source_type = si.GetProperty_i32(handle, si.EPK(si.Property.DATA_SOURCE_TYPE,ch,ds))

            # check if the data source matches this description
            description = DataSourceDescription(component_id, component_index, data_source_type)
            if description in data_sources_to_enable:
                # found described data source
                print("Enabling data source {} of channel {} for streaming.".format(ds, ch))
                si.SetProperty_i32(handle, si.EPK(si.Property.STREAMING_ENABLED,ch,ds), si.ENABLED)

                # retrieve data source information
                data_source = DataSource()
                data_source.address = DataSourceAddress(ch, ds)
                data_source.data_type = si.GetProperty_i32(handle, si.EPK(si.Property.DATA_TYPE,ch,ds))
                data_source.name = si.GetProperty_s(handle, si.EPK(si.Property.DATA_SOURCE_NAME,ch,ds))

                # add data source to the list of enabled data sources
                stream_config.enabled_data_sources.append(data_source)

def configure_stream(handle, stream_config):
    """
    Configures the data stream according to the global stream_config
    object. The data sources to be enabled is given as a list of
    data source descriptions.
    """
    si.SetProperty_i32(handle, si.EPK(si.Property.FRAME_AGGREGATION,0,0), stream_config.frame_aggregation)
    si.SetProperty_i32(handle, si.EPK(si.Property.FRAME_RATE,0,0), stream_config.frame_rate)
    si.SetProperty_i32(handle, si.EPK(si.Property.STREAMBUFFER_AGGREGATION,0,0), stream_config.stream_buffer_aggregation)
    si.SetProperty_i32(handle, si.EPK(si.Property.STREAMBUFFERS_INTERLEAVED,0,0), stream_config.interleaving_enabled)
    si.SetProperty_i32(handle, si.EPK(si.Property.NUMBER_OF_STREAMBUFFERS,0,0), stream_config.number_of_stream_buffers)

    # read back actual frame rate
    stream_config.precise_frame_rate = si.GetProperty_f64(handle, si.EPK(si.Property.PRECISE_FRAME_RATE,0,0))
    print("Frame rate is {} Hz".format(stream_config.precise_frame_rate))

def process_buffer(handle, buffer):
    """
    Processes the contents of a buffer received from the API.
    This function would typically e.g. store the data to disc.
    In this example the data is stored in a buffer for later
    processing.
    """
    for element_index in range(buffer.info.numberOfSources):
        if element_index not in stream_data.data_source:
            stream_data.data_source[element_index] = DataSourceData()

        values = si.CopyBuffer(handle, buffer.info.bufferId, element_index)
        stream_data.data_source[element_index].data += values

    # Note: The following code line is an example how it should *not* be
    # implemented. Printing to standard out is a relatively time consuming
    # operation and should be avoided at this place.
    print("Received {} frames.".format(buffer.info.numberOfFrames))

def receive_stream_buffer(handle, timeout):
    """
    Waits for stream data coming from the HSDR.
    """
    ev = si.WaitForEvent(handle, timeout)
    if ev.type == si.EventType.STREAMBUFFER_READY:
        # get buffer data
        buffer = si.AcquireBuffer(handle, ev.bufferId)
        process_buffer(handle, buffer)
        last_frame = bool(buffer.info.flags & si.Flag.STREAM_END)
        si.ReleaseBuffer(handle, ev.bufferId)
        return last_frame
    else:
        print("Received unexpected event type: {} (parameter: {})".format(ev.type, ev.devEventParameter))
    return True

def stream_data_thread():
    last_frame = False
    while not last_frame:
        last_frame = receive_stream_buffer(handle, 20000)
        
def print_data():
    """
    Prints all received stream data to standard out.
    """
    for frame in range(len(stream_data.data_source[0].data)):
        print("frame {}: {}".format(
            frame,
            " ".join(str(stream_data.data_source[ds].data[frame]) for ds in stream_data.data_source)
        ))

def plot_data(stream_config):
    """
    Plots received stream data.
    Note that this function requires the matplotlib library to be installed.
    This can be done with "python -m pip install -U matplotlib" in a shell.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        plt.xlabel("Time [s]")
        plt.title("Stream Data")

        samples = len(stream_data.data_source[0].data)
        t = np.linspace(0, samples / stream_config.precise_frame_rate, samples)
        for ds_index, ds in enumerate(stream_config.enabled_data_sources):
            plt.plot(t, stream_data.data_source[ds_index].data, label=ds.name)

        plt.legend()
        plt.show()

    except ImportError:
        print("matplotlib is not installed, cannot show plot")

try:

    opt = parse_command_line_options()

    # connect to HSDR
    print("Connecting to HSDR with locator \"{}\".".format(opt.locator))
    handle = si.Open(opt.locator)

    data_sources_to_enable = [
        DataSourceDescription(hsdr.ComponentID.CHANNEL0,0,si.DataSource.POSITION),  # base API data_source
        DataSourceDescription(hsdr.ComponentID.CHANNEL0,0,hsdr.DataSource.TARGET),  # device specific data_source
    ]

    stream_config = StreamConfig()
    stream_config.interleaving_enabled = False
    stream_config.frame_aggregation = 5
    stream_config.stream_buffer_aggregation = 0   # "same as frame aggregation"
    stream_config.frame_rate = 10
    stream_config.number_of_stream_buffers = 4

    # enable selected data sources
    enable_data_sources(handle, stream_config, data_sources_to_enable)
    # configure data stream
    configure_stream(handle, stream_config)

    # enable data stream
    print("Starting data stream.")
    si.SetProperty_i32(handle, si.EPK(si.Property.STREAMING_MODE,0,0), si.StreamingMode.DIRECT)
    si.SetProperty_i32(handle, si.EPK(si.Property.STREAMING_ACTIVE,0,0), si.ENABLED)

    # start thread to receive stream
    t = threading.Thread(target=stream_data_thread)
    t.start()
    input("Press Enter to stop stream...\n")

    # stop data stream
    print("Stopping data stream.")
    si.SetProperty_i32(handle, si.EPK(si.Property.STREAMING_ACTIVE,0,0), si.DISABLED)

    # receive remaining buffers
    t.join()
    print_data()
    plot_data(stream_config)

except si.Error as e:
    err_name = "(0x{:04X})".format(e.code)
    if e.code in set(err.value for err in si.ErrorCode):
        err_name = si.ErrorCode(e.code).name + " " + err_name
    print("SI {} error: {} in line: {}."
          .format(e.func, err_name, (sys.exc_info()[-1].tb_lineno)))

finally:
    # disconnect from device
    try:
        if handle is not None:
            print("Closing connection.")
            si.Close(handle)
    except:
        pass
#!/usr/bin/python3

# SmarAct MCS2 High-Speed-Data-Reader (HSDR) programming example:
# read device info
#
# This programming example shows you how to connect to a
# SmarAct MCS2 HSDR device and query various information
# about the device.
#
# See the MCS2 HSDR Programmers Guide for more information.

import sys
import optparse
import smaract.si as si

handle = None

def parse_command_line_options():
    # Get locator used to connect to the device.
    # Default locator connects to the first USB device found.
    parser = optparse.OptionParser()
    parser.add_option( "-l", dest="locator", default="usb:ix:0")
    options, args = parser.parse_args()
    return options

def read_data_source_info(handle, channel, data_source_index):
    name = si.GetProperty_s(handle, si.EPK(si.Property.DATA_SOURCE_NAME,channel,data_source_index))
    print("  Data Source {}: {}".format(data_source_index, name))

    # read data source type
    ds_type = si.GetProperty_i32(handle, si.EPK(si.Property.DATA_SOURCE_TYPE,channel,data_source_index))
    print("    Data source type : {}".format(ds_type))

    # read data type
    data_type = si.GetProperty_i32(handle, si.EPK(si.Property.DATA_TYPE,channel,data_source_index))
    print("    Data type        : {}".format(data_type))

    # read component ID
    component_id = si.GetProperty_i32(handle, si.EPK(si.Property.COMPONENT_ID,channel,data_source_index))
    print("    Component ID     : {}".format(component_id))

    # read component index
    component_index = si.GetProperty_i32(handle, si.EPK(si.Property.COMPONENT_INDEX,channel,data_source_index))
    print("    Component index  : {}".format(component_index))

    # read base unit
    base_unit = si.GetProperty_i32(handle, si.EPK(si.Property.BASE_UNIT,channel,data_source_index))
    print("    Base unit        : {}".format(base_unit))

    # read base resolution
    base_resolution = si.GetProperty_i32(handle, si.EPK(si.Property.BASE_RESOLUTION,channel,data_source_index))
    print("    Base resolution  : {}".format(base_resolution))

try:
    opt = parse_command_line_options()

    # connect to device
    print("Connecting to HSDR with locator \"{}\".".format(opt.locator))
    handle = si.Open(opt.locator)

    # read device ID
    device_id = si.GetProperty_s(handle, si.EPK(si.Property.DEVICE_ID,0,0))
    print("AttoDry800xs ID is: \"{}\".".format(device_id))

    # read number of channels
    number_of_channels = si.GetProperty_i32(handle, si.EPK(si.Property.NUMBER_OF_CHANNELS,0,0))
    print("AttoDry800xs has {} channels.".format(number_of_channels))

    # read channel structures
    for ch in range(number_of_channels):
        print("Channel {}:".format(ch))

        # read number of data sources
        number_of_data_sources = si.GetProperty_i32(handle, si.EPK(si.Property.NUMBER_OF_DATA_SOURCES,ch,0))
        for ds in range(number_of_data_sources):
            read_data_source_info(handle, ch, ds)

except si.Error as e:
    err_name = "(0x{:04X})".format(e.code)
    if e.code in set(err.value for err in si.ErrorCode):
        err_name = si.ErrorCode(e.code).name + " " + err_name
    print("SI {} error: {} in line: {}."
          .format(e.func, err_name, (sys.exc_info()[-1].tb_lineno)))

finally:
    # disconnect from HSDR
    try:
        if handle is not None:
            print("Closing connection.")
            si.Close(handle)
    except:
        pass
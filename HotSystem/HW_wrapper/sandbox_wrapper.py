import pyvisa
import sys

import serial

port_ = 'COM6'
device = serial.Serial(port_)


# dev_address="ASRL5::INSTR"
# rm = pyvisa.ResourceManager()
# device = rm.open_resource(dev_address)
address = "0"  # ASCII 0 for USB port
parameter = "IDN"
command = "RD"
# value = "1.3"
space = " "  # ASCII space character
carriage_return = "\r"  # ASCII carriage return

# command_string = f"{address}{space}{parameter}{space}{command}{space}{value}{carriage_return}"
command_string = f"{address}{space}{parameter}{space}{command}{carriage_return}"
print(command_string)

device.write(command_string.encode())
resposne = device.readall()
device.close()
Install:
pip install “…/atto_device-0.0.8-py3-none-any.whl”

Usage:
from atto_device.CRYO800 import Device
dev = Device('[IP Adress of device])
dev.connect()
print(dev.sample.getTemperature())

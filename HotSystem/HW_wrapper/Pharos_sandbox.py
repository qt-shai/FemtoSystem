# import requests
from Wrapper_Pharos import PharosLaserAPI


# Replace <PHAROS_IP> with the actual IP address of your PHAROS device.
# If your laser API is running on a non-standard port (other than 80),
# replace <PORT> with the correct port number.
laserIP = "192.168.101.58"
port = "20022"
# url = "http://"+ laserIP + ":" + port + "/Basic"
# url = "http://192.168.101.58:20022/v0/basic"

laser = PharosLaserAPI(host=laserIP,port=port)

try:
    res=laser.getBasic()
    res=laser.getBasicIsOutputOpen()
    print(laser.getBasicTargetPpDivider())
except Exception as e:
    print(e)



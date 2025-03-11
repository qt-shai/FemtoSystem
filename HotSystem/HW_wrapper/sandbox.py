import requests

# Replace <PHAROS_IP> with the actual IP address of your PHAROS device.
# If your laser API is running on a non-standard port (other than 80),
# replace <PORT> with the correct port number.
laserIP = "192.168.101.58"
port = "20022"
url = "http://"+ laserIP + ":" + port + "/basic"
url = "http://192.168.101.58:20022/basic/SelectedPresetIndex"
try:
    response = requests.get(url)
    if response.status_code == 200:
        # Parse response as JSON
        data = response.json()
        print("Response data:\n", data)
    else:
        print(f"Request failed with status code: {response.status_code}")
        print("Response content:\n", response.text)
except requests.RequestException as e:
    print("An error occurred while making the request:", e)

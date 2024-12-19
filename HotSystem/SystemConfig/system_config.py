import os
import platform
import subprocess
import xml.etree.ElementTree as ET
from enum import Enum
from typing import List, Optional
from Utils import remove_overlap_from_string

class SystemType(Enum):
    HOT_SYSTEM = "HotSystem"
    FEMTO = "Femto"
    ATTO = "Atto"
    ICE = "ICE"
    BOAZ = "Boaz"
    AMIR = "Amir"
    SHAI = "Shai"

class Instruments(Enum):
    HIGHLAND = "highland"
    MATTISE = "mattise"
    ATTO_SCANNER = "atto_scanner"
    ATTO_POSITIONER = "atto_positioner"
    SMARACT_SLIP = "smaract_slip"
    ROHDE_SCHWARZ = "rohde_schwarz"
    SMARACT_SCANNER = "smaract_scanner"
    COBOLT = "cobolt"
    PICOMOTOR = "picomotor"
    ZELUX = "zelux"
    OPX = "OPX"
    ELC_POWER_SUPPLY = "elc_power_supply"
    SIMULATION = "simulation"
    KEYSIGHT_AWG = "keysight_awg"

class InstrumentsAddress(Enum):
    MCS2_00018624 = "192.168.101.70"
    MCS2_00017055 = "192.168.101.59"
    MATTISE = "COM3"
    KEYSIGHT_AWG = "TCPIP::K-33522B-03690.local::5025::SOCKET"
    Rhode_Schwarz_hot_system = '192.168.101.57'  # todo replace with search for device IP and address and some CNFG files
    Rhode_Schwarz_atto = "192.168.101.50"
    atto_positioner = "192.168.101.53"  # todo replace with search for device IP and address and some CNFG files
    atto_scanner = "192.168.101.60"
    opx_ip = '192.168.101.56'
    opx_port = 80
    opx_cluster = 'Cluster_1'

class Device:
    """
    Represents a device with its instrument type and additional information.
    """
    def __init__(self, instrument: Instruments, ip_address: str = None, mac_address: str = None, serial_number: str = None, com_port: str = None):
        self.instrument = instrument
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.serial_number = serial_number
        self.com_port = com_port

    @property
    def device_key(self):
        return self.instrument.value, self.serial_number or self.mac_address or self.ip_address

    def __repr__(self):
        return f"Device(instrument={self.instrument.value}, ip={self.ip_address}, mac={self.mac_address}, sn={self.serial_number})"

class SystemConfig:

    microwave_ip: str = '192.168.101.57'  # todo replace with search for device IP and address and some CNFG files
    atto_positioner_ip: str = "192.168.101.53"  # todo replace with search for device IP and address and some CNFG files
    # atto_scanner_ip: str = "192.168.101.53"  # todo: get correct IP + replace with search for device IP and address and some CNFG files
    keysight_awg_ip: str = "192.168.101.53"  # todo: get correct IP + replace with search for device IP and address and some CNFG files
    opx_ip = '192.168.101.56'
    opx_port = 80
    opx_cluster = 'Cluster_1'

    def __init__(self, system_type: SystemType, devices: List[Device]):
        """
        Configuration for a specific system type.

        :param system_type: The type of the system.
        :param devices: A list of Device instances to load.
        """
        self.system_type = system_type
        self.devices = devices

def load_system_from_xml(file_path: str) -> Optional[SystemConfig]:
    """
    Load the system configuration from an XML file.

    :param file_path: Path to the XML file.
    :return: An instance of SystemConfig based on the XML data.
    """
    if not os.path.exists(file_path):
        return None
    try:
        # Parse the XML file
        tree = ET.parse(file_path)
        root = tree.getroot()

        # Extract the system type from the XML
        identifier_element = root.find(".//Identifier")
        if identifier_element is None or not identifier_element.text:
            raise ValueError("No system type identifier found in XML.")

        system_type_str = identifier_element.text.strip()
        system_type = SystemType(system_type_str)

        # Extract selected devices from the XML
        device_elements = root.findall(".//Device")
        devices: List[Device] = []
        for device_element in device_elements:
            # Extract instrument
            instrument_element = device_element.find("Instrument")
            if instrument_element is None or not instrument_element.text:
                print("Warning: Device without instrument found in XML. Skipping...")
                continue
            instrument_name = instrument_element.text.strip()
            try:
                instrument_enum = Instruments[instrument_name.upper()]
            except KeyError:
                print(f"Warning: Unknown instrument '{instrument_name}' found in XML. Skipping...")
                continue

            # Extract IP address, MAC address, and serial number
            ip_element = device_element.find("IPAddress")
            mac_element = device_element.find("MACAddress")
            sn_element = device_element.find("SerialNumber")
            com_port_element = device_element.find("COMPort")

            ip_address = ip_element.text.strip() if ip_element is not None and ip_element.text else None
            mac_address = mac_element.text.strip() if mac_element is not None and mac_element.text else None
            serial_number = sn_element.text.strip() if sn_element is not None and sn_element.text else None
            com_port = com_port_element.text.strip() if com_port_element is not None and com_port_element.text else None

            device = Device(
                instrument=instrument_enum,
                ip_address=ip_address,
                mac_address=mac_address,
                serial_number=serial_number,
                com_port=com_port,
            )
            devices.append(device)

        # Create and return a SystemConfig instance
        return SystemConfig(system_type=system_type, devices=devices)

    except ET.ParseError as e:
        raise ValueError(f"Error parsing XML file: {e}")
    except Exception as e:
        raise ValueError(f"An error occurred while reading the XML file: {e}")

def load_system_config() -> Optional[SystemConfig]:
    """
    Load the system configuration by checking if the file exists, opening a file dialog if needed,
    or creating a new configuration via the GUI.
    """

    expected_base_path = r"HotSystem\SystemConfig\xml_configs"
    # Get the current working directory
    current_working_directory = os.getcwd() + "\\"
    # Check if the current working directory is within the expected base path
    base_path = remove_overlap_from_string(current_working_directory, expected_base_path)
    config_file = "system_info.xml"
    full_path = os.path.join(base_path, config_file)
    selected_system_file = None
    # Check if the file exists
    if os.path.exists(full_path):
        print(f"Configuration file found: {full_path}")
        selected_system_file = full_path

    if selected_system_file:
        # Load the configuration
        system_config = load_system_from_xml(selected_system_file)
        if system_config:
            print(f"Loaded system configuration: {system_config.system_type}, Devices: {system_config.devices}")
            return system_config
        else:
            print("Error: Could not load system configuration from file.")
            return None
    else:
        print("Error: No valid system configuration file could be loaded.")
        return None

def ping_device(ip_address: str, timeout: float = 0.3) -> bool:
    """
    Pings the device with the given IP address to check if it's reachable, with a specified timeout.

    :param ip_address: The IP address of the device to ping.
    :param timeout: The maximum number of seconds to wait for a ping response. Default is 5 seconds.
    :return: True if the device responds to the ping within the timeout, False otherwise.
    """
    try:
        # Check the operating system
        param = "-n" if platform.system().lower() == "windows" else "-c"

        # Add timeout for Windows (-w for wait time in milliseconds) or Unix-like systems (-W for seconds)
        timeout_param = "-w" if platform.system().lower() == "windows" else "-W"

        # Ping the device with timeout
        command = ["ping", param, "1", timeout_param, str(timeout), ip_address]
        response = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)

        return response.returncode == 0  # Ping successful if return code is 0
    except subprocess.TimeoutExpired:
        print(f"Ping to {ip_address} timed out after {timeout} seconds.")
        return False
    except Exception as e:
        print(f"Error while pinging {ip_address}: {e}")
        return False

def get_mac_address(ip_address: str) -> Optional[str]:
    """
    Retrieves the MAC address of a device at the given IP address using ARP.

    :param ip_address: The IP address of the device to get the MAC address for.
    :return: The MAC address if found, None otherwise.
    """
    try:
        # Windows uses 'arp -a', while Unix-like systems (Linux, macOS) use 'arp -n'
        if platform.system().lower() == "windows":
            command = ["arp", "-a", ip_address]
        else:
            command = ["arp", ip_address]

        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        output = result.stdout

        # Parse the output to extract the MAC address
        if platform.system().lower() == "windows":
            lines = output.splitlines()
            for line in lines:
                if ip_address in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        return parts[1]  # MAC address
        else:
            # For Unix-like systems
            parts = output.split()
            if len(parts) >= 3:
                return parts[2]  # MAC address for Linux/macOS systems

    except Exception as e:
        print(f"Error while getting MAC address for {ip_address}: {e}")

    return None

def find_ethernet_device(ip_address: str, instrument: Instruments) -> Optional[Device]:
    """
    Pings an Ethernet device to check if it's available, and retrieves its MAC address if available.
    The result is returned as a Device object.

    :param ip_address: The IP address of the device to ping and retrieve the MAC address.
    :param instrument: The type of instrument (e.g., Instruments.SMARACT).
    :return: A Device object if the device is available and responds, None otherwise.
    """
    # Ping the device
    if ping_device(ip_address, timeout=2):
        print(f"Device at {ip_address} is available.")
        # Get the MAC address
        mac_address = get_mac_address(ip_address)
        if mac_address:
            print(f"MAC address of {ip_address}: {mac_address}")
        else:
            print(f"MAC address for {ip_address} could not be found.")
        # Return a Device object with the retrieved details
        return Device(instrument=instrument, ip_address=ip_address, mac_address=mac_address, serial_number="N/A")
    else:
        print(f"Device at {ip_address} is not available.")

    return None


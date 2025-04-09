import ast
import os
import pdb
import xml.etree.ElementTree as ET
from typing import List, Optional, Dict
# from numpy.array_api import trunc
# import sys
# # Add the project root (C:\WC\HotSystem) to sys.path
# project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
# if project_root not in sys.path:
#     sys.path.append(project_root)

from Utils import remove_overlap_from_string, get_square_matrix_size, scan_com_ports
import dearpygui.dearpygui as dpg
import HW_wrapper.Wrapper_Smaract as Smaract
import HW_wrapper.Wrapper_Picomotor as Picomotor
import HW_wrapper.Wrapper_Zelux as ZeluxCamera
import HW_wrapper.SRS_PID.wrapper_sim960_pid as wrapper_sim960_pid
import HW_wrapper.SRS_PID.wrapper_sim900_mainframe as wrapper_sim900_mainframe
from SystemConfig import (SystemConfig, find_ethernet_device, InstrumentsAddress, connect_thorlabs_motor_device_by_serial,get_thorlabs_motor_serial_nums)
from SystemConfig import SystemType, Instruments, Device, load_system_from_xml

# Initialize the devices list and selection dictionary
devices_list = []
selected_devices = {}

# Function to simulate available devices for each instrument type
def get_available_devices(instrument: Instruments, ports: Dict[str, str | OSError]) -> Optional[List[Device]]:
    """
    Simulate available devices for each instrument type.
    Returns a list of Device instances, or None if none found.
    """
    print(f"Looking for available devices of type {instrument}")
    devices = None
    if instrument == Instruments.SMARACT_SLIP:
        devices = [
            dev
            for dev in Smaract.smaractMCS2.get_available_devices()
            if "MCS2-00017055" in dev.serial_number
        ]
    elif instrument == Instruments.SMARACT_SCANNER:
        devices = [
            dev
            for dev in Smaract.smaractMCS2.get_available_devices()
            if "MCS2-00018624" in dev.serial_number
        ]
    elif instrument == Instruments.PICOMOTOR:
        devices = Picomotor.newportPicomotor.get_available_devices()
    elif instrument == Instruments.ZELUX:
        devices = ZeluxCamera.Zelux.get_available_devices()
    elif instrument == Instruments.ROHDE_SCHWARZ:
        devices = [
            find_ethernet_device(ip, instrument)
            for ip in [
                InstrumentsAddress.Rhode_Schwarz_hot_system.value,
                InstrumentsAddress.Rhode_Schwarz_atto.value,
            ]
        ]
        devices = [dev for dev in devices if dev]
        if len(devices) == 0:
            devices = None
    elif instrument == Instruments.ATTO_POSITIONER:
        devices = find_ethernet_device(SystemConfig.atto_positioner_ip, instrument)
        if not isinstance(devices, list) and devices:
            devices = [devices]
    elif instrument == Instruments.ATTO_SCANNER:
        devices = find_ethernet_device(InstrumentsAddress.atto_scanner.value, instrument)
        if not isinstance(devices, list) and devices:
            devices = [devices]
    elif instrument == Instruments.OPX:
        ip_list = [
            InstrumentsAddress.opx_hot_system_ip.value,
            InstrumentsAddress.opx_femto_system_ip.value,
            InstrumentsAddress.opx_atto_system_ip.value
        ]
        devices = find_device_list_from_ip(instrument, ip_list)

        if devices:
            for dev in devices:
                if dev.ip_address == InstrumentsAddress.opx_hot_system_ip.value:
                    dev.misc = InstrumentsAddress.opx_hot_system_cluster.value
                elif dev.ip_address == InstrumentsAddress.opx_femto_system_ip.value:
                    dev.misc = InstrumentsAddress.opx_femto_system_cluster.value
                elif dev.ip_address == InstrumentsAddress.opx_atto_system_ip.value:
                    dev.misc = InstrumentsAddress.opx_atto_system_cluster.value
    if (instrument == Instruments.KDC_101) or (instrument == Instruments.MFF_101):
        #get_thorlabs_motor_serial_nums()
        devices = connect_thorlabs_motor_device_by_serial(instrument)
    if not isinstance(devices, list) and devices:
        devices = [devices]

        if not isinstance(devices, list) and devices:
            devices = [devices]

    elif instrument == Instruments.SIM960:
        # NEW LOGIC FOR SIM960
        # Attempt to detect or retrieve a list of SIM960 devices
        # sim960_list = SRSsim960.get_available_devices()  # or custom detection logic
        # The 'Device' class in your system expects instrument, ip, mac, sn, com_port...
        # So you must map sim960 object => Device
        # Example:
        # ports = scan_com_ports()
        mainframe_port = next((port for port, description in ports.items() if "sim900" in description.lower()),None)
        sim960_list = []

        if mainframe_port:
            try:
                temp_mainframe = wrapper_sim900_mainframe.SRSsim900(mainframe_port)
                temp_mainframe.connect()
            except Exception as e:
                print(f"failed mainframe. Error: {e}")

            # Loop over channels 1 to 8 and check for connected modules
            try:
                sim960_list = [channel for channel in range(8) if int(temp_mainframe.query(f"CTCR? {channel}")) ]
                print(f"SRS SIM900 channels found : {sim960_list}")
                devices = [Device(instrument=Instruments.SIM960, ip_address=str(sim_dev), com_port=mainframe_port) for
                           sim_dev in sim960_list]
                if temp_mainframe:
                    temp_mainframe.disconnect()
            except Exception as e:
                print(f"failed to detect channels in SRS900 mainframe. Error: {e}")

    elif instrument == Instruments.KEYSIGHT_AWG:
        ip_list = [InstrumentsAddress.KEYSIGHT_AWG_33522B.value, InstrumentsAddress.KEYSIGHT_AWG_33600A.value]
        devices = find_device_list_from_ip(instrument, ip_list)
    elif instrument == Instruments.ARDUINO:
        arduino_port = next(
            (port for port, description in ports.items() if "arduino" in description.lower()), None
        )
        if arduino_port:
            return [
                Device(
                    instrument=Instruments.ARDUINO,
                    ip_address="N/A",
                    mac_address="N/A",
                    serial_number="N/A",
                    com_port=arduino_port,
                    simulation=False,
                )
            ]
        else:
            return [
                Device(
                    instrument=Instruments.ARDUINO,
                    ip_address="N/A",
                    mac_address="N/A",
                    serial_number="N/A",
                    com_port="N/A",
                    simulation=True,
                )
            ]
        pass
    elif instrument == Instruments.OPX:
        ip_list = [
            InstrumentsAddress.opx_hot_system_ip.value,
            InstrumentsAddress.opx_femto_system_ip.value,
            InstrumentsAddress.opx_atto_system_ip.value
        ]
        devices = find_device_list_from_ip(instrument, ip_list)

        if devices:
            for dev in devices:
                if dev.ip_address == "192.168.101.56":
                    dev.misc = "Cluster_1"
                elif dev.ip_address == "192.168.101.61":
                    dev.misc = "Cluster_2"
                elif dev.ip_address == "192.168.101.157":
                    dev.misc = "Cluster_3"

    # Return as a list or None
    if not isinstance(devices, list) and devices:
        devices = [devices]
    return devices


def find_device_list_from_ip(instrument: Instruments, ip_list: List[str]):
    devices = [find_ethernet_device(ip, instrument) for ip in ip_list]
    devices = [dev for dev in devices if dev]
    if len(devices) == 0:
        devices = None
    return devices


def generate_device_key(device):
    """
    Generate a unique key for a device based on its attributes.
    """
    key_parts = [device.instrument.value]
    if device.serial_number and device.serial_number != 'N/A':
        key_parts.append(f"SN:{device.serial_number}")
    if device.ip_address and device.ip_address != 'N/A':
        key_parts.append(f"IP:{device.ip_address}")
    if device.mac_address and device.mac_address != 'N/A':
        key_parts.append(f"MAC:{device.mac_address}")
    return '_'.join(key_parts)


def save_to_xml(system_type: SystemType, selected_devices_list: list):
    """
    Save the chosen system type and selected devices to an XML file.
    """
    # pdb.set_trace()
    root = ET.Element("SystemInfo")
    system_element = ET.SubElement(root, "System")

    # Add system identifier
    identifier = ET.SubElement(system_element, "Identifier")
    identifier.text = system_type.value

    # Add selected devices
    devices_element = ET.SubElement(system_element, "Devices")

    for device in selected_devices_list:
        print(device.instrument.value)
        print(device.com_port)
        if device is not None:
            device_element = ET.SubElement(devices_element, "Device")

            instrument_element = ET.SubElement(device_element, "Instrument")
            instrument_element.text = device.instrument.value

            ip_element = ET.SubElement(device_element, "IPAddress")
            ip_element.text = device.ip_address or 'N/A'

            mac_element = ET.SubElement(device_element, "MACAddress")
            mac_element.text = device.mac_address or 'N/A'

            sn_element = ET.SubElement(device_element, "SerialNumber")
            sn_element.text = device.serial_number or 'N/A'

            com_port_element = ET.SubElement(device_element, "COMPort")
            com_port_element.text = device.com_port or 'N/A'

            simulation_element = ET.SubElement(device_element, "Simulation")
            simulation_element.text = str(device.simulation) or str(False)

            misc_element = ET.SubElement(device_element, "Misc")
            misc_element.text = device.misc or "N/A"
        else:
            print("Warning: A None value found in selected_devices_list, skipping...")

    # Save to XML file
    tree = ET.ElementTree(root)
    try:
        expected_base_path = r"HotSystem\SystemConfig\xml_configs"
        # Get the current working directory
        current_working_directory = os.getcwd() + "\\"
        print(f"Current working directory: {current_working_directory}")
        # Check if the current working directory is within the expected base path
        base_path = remove_overlap_from_string(current_working_directory, expected_base_path)
        tree.write(f"{base_path}/system_info.xml")
        dpg.configure_item("SuccessPopup", show=True)
    except Exception as e:
        dpg.set_value("ErrorText", f"Failed to save to XML: {e}")
        dpg.configure_item("ErrorPopup", show=True)


def on_save(sender, app_data):
    """
    Handler for Save button click.
    """
    system_type = SystemType(dpg.get_value("system_combobox"))
    selected_devices_list = [
        device for device in devices_list
        if selected_devices.get(generate_device_key(device), False)
    ]

    if not selected_devices_list:
        dpg.configure_item("WarningPopup", show=True)
        return

    # Save the configuration to XML
    save_to_xml(system_type, selected_devices_list)


def toggle_device_selection(sender, app_data, user_data):
    """
    Toggle the selection state of a device by changing the background color of its associated child window.
    """
    device, window_id = user_data
    device_key = generate_device_key(device)
    selected_devices[device_key] = not selected_devices.get(device_key, False)  # Toggle selection

    # Update the background color of the child window based on the selection state
    if selected_devices[device_key]:
        dpg.bind_item_theme(window_id, "selected_theme")
    else:
        dpg.bind_item_theme(window_id, "default_theme")


def load_instrument_images():
    """
    Load images for instruments if available; otherwise, show a placeholder.
    """
    create_themes()
    expected_base_path = r"HotSystem\SystemConfig\Images"
    # Get the current working directory
    current_working_directory = os.getcwd() + "\\"
    # Check if the current working directory is within the expected base path
    base_path = remove_overlap_from_string(current_working_directory, expected_base_path)

    with dpg.texture_registry():
        for icon in ['config','keyboard']:
            image_path = os.path.join(base_path, f"{icon}.png")
            texture_tag = f"{icon}_texture"
            if not dpg.does_item_exist(texture_tag):
                if os.path.exists(image_path):
                    width, height, channels, data = dpg.load_image(image_path)
                    dpg.add_static_texture(width, height, data, tag=texture_tag)

        for instrument in Instruments:
            texture_tag = f"{instrument.value}_texture"
            if not dpg.does_item_exist(texture_tag):
                image_path = os.path.join(base_path, f"{instrument.value}.png")
                print(f"Image path: {image_path}")
                if os.path.exists(image_path):
                    width, height, channels, data = dpg.load_image(image_path)
                    dpg.add_static_texture(width, height, data, tag=texture_tag)
                else:
                    # Create a placeholder texture (a white square)
                    placeholder_data = [255, 255, 255, 255] * 50 * 50
                    dpg.add_static_texture(50, 50, placeholder_data, tag=texture_tag)


def create_themes():
    """
    Create the themes for selected, default, and main window states with pastel colors.
    Themes are only created if they don't already exist.
    """
    # Create the "selected_theme" if it doesn't already exist
    if not dpg.does_item_exist("selected_theme"):
        with dpg.theme(tag="selected_theme"):
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (109, 155, 109), category=dpg.mvThemeCat_Core)  # Pastel green
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (51, 51, 51), category=dpg.mvThemeCat_Core)  # Dark gray text
            with dpg.theme_component(dpg.mvInputText):  # Apply to input float widgets
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (109, 155, 109), category=dpg.mvThemeCat_Core)  # Pastel green background
                dpg.add_theme_color(dpg.mvThemeCol_Text, (51, 51, 51), category=dpg.mvThemeCat_Core)  # Dark gray text

    # Create the "default_theme" if it doesn't already exist
    if not dpg.does_item_exist("default_theme"):
        with dpg.theme(tag="default_theme"):
            with dpg.theme_component(dpg.mvChildWindow):
                dpg.add_theme_color(dpg.mvThemeCol_ChildBg, (240, 240, 240), category=dpg.mvThemeCat_Core)  # Light gray
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (51, 51, 51), category=dpg.mvThemeCat_Core)  # Dark gray text
            with dpg.theme_component(dpg.mvInputText):  # Apply to input float widgets
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (240, 240, 240), category=dpg.mvThemeCat_Core)  # Light gray background
                dpg.add_theme_color(dpg.mvThemeCol_Text, (51, 51, 51), category=dpg.mvThemeCat_Core)  # Dark gray text

    # Create the "main_window_theme" if it doesn't already exist
    if not dpg.does_item_exist("main_window_theme"):
        with dpg.theme(tag="main_window_theme"):
            with dpg.theme_component(dpg.mvWindowAppItem):
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, (167, 199, 231), category=dpg.mvThemeCat_Core)  # Pastel magenta
            with dpg.theme_component(dpg.mvText):
                dpg.add_theme_color(dpg.mvThemeCol_Text, (51, 51, 51), category=dpg.mvThemeCat_Core)  # Dark gray text

def run_system_config_gui():
    """
    Initialize the Dear PyGui interface.
    """

    # Create the necessary themes
    create_themes()

    # Load images for instruments
    load_instrument_images()

    # Load the existing system configuration
    # Define the primary and alternative paths
    primary_path = "xml_configs/system_info.xml"
    alternative_path = "C:/wc/HotSystem/SystemConfig/xml_configs/system_info.xml"

    # Check if the primary path exists
    if os.path.exists(primary_path):
        system_config_path = primary_path
    elif os.path.exists(alternative_path):
        system_config_path = alternative_path
    else:
        system_config_path = None
        print("Error: system_info.xml not found in either path")
        return

    system_config = load_system_from_xml(system_config_path)

    # Create a set of device keys from the existing configuration for comparison
    configured_device_keys = set()
    instruments_with_na_identifiers = set()
    configured_devices_dict = {}

    if system_config is None:
        print("Error: system_config is None")

    if system_config:
        for configured_device in system_config.devices:
            configured_device_key = generate_device_key(configured_device)
            configured_devices_dict[configured_device_key] = configured_device
            # Check if all identifiers are 'N/A' or None
            if (
                configured_device.serial_number in [None, 'N/A']
                and configured_device.mac_address in [None, 'N/A']
                and configured_device.ip_address in [None, 'N/A']
                and configured_device.com_port in [None, 'N/A']
                and configured_device.simulation == 'False'
            ):
                # Collect instrument types with devices with 'N/A' identifiers
                instruments_with_na_identifiers.add(configured_device.instrument)
            else:
                # Add device_key to configured_device_keys
                configured_device_keys.add(configured_device_key)

    ports = scan_com_ports()
    # Query available devices for each instrument type
    for instrument in Instruments:
        available_devices = get_available_devices(instrument, ports)
        if available_devices:
            for device in available_devices:
                if device:
                    devices_list.append(device)
                    selected_devices[generate_device_key(device)] = False  # Initialize selection state
                    # Mark the device as selected if it exists in the system configuration
                    device_key = generate_device_key(device)
                    if device_key in configured_device_keys:
                        # device.com_port = configured_devices_dict[device_key].com_port
                        # device.simulation = configured_devices_dict[device_key].simulation

                        selected_devices[device_key] = True
                        # Update device attributes from XML configuration
                        configured_device = configured_devices_dict[device_key]
                        device.com_port = configured_device.com_port or device.com_port
                        device.simulation = configured_device.simulation


                    elif device.instrument in instruments_with_na_identifiers:
                        selected_devices[device_key] = True
        else:
            # Add a placeholder device
            simulation_from_config = next(
                (dev.simulation for dev in system_config.devices if dev.instrument == instrument),
                False
            )

            com_port_from_config = next(
                (dev.com_port for dev in system_config.devices if dev.instrument == instrument),
                'N/A'
            )

            ip_from_config = next(
                (dev.ip_address for dev in system_config.devices if dev.instrument == instrument),
                'N/A'
            )

            placeholder_device = Device(
                instrument=instrument,
                ip_address=ip_from_config,
                mac_address='N/A',
                serial_number='N/A',
                com_port=com_port_from_config,
                simulation=simulation_from_config,
            )
            placeholder_device.is_placeholder = True
            devices_list.append(placeholder_device)
            selected_devices[generate_device_key(placeholder_device)] = False
            # Check if the instrument is in the set of instruments with 'N/A' identifiers
            if instrument in instruments_with_na_identifiers or any(dev.instrument == instrument for dev in system_config.devices):
                selected_devices[generate_device_key(placeholder_device)] = True

    num_devices = len(devices_list)

    # Calculate matrix size based on the number of devices
    matrix_size = get_square_matrix_size(num_devices)

    # Adjusted the window width to better fit the content
    total_cell_width = 300  # Adjusted cell width
    with dpg.window(label="System and Instrument Configuration", width=total_cell_width * matrix_size + 50,
                    height=170 * matrix_size +200, tag="main_window"):
        dpg.bind_item_theme("main_window", "main_window_theme")
        with dpg.group(horizontal=True):
            dpg.add_text("System:")
            default_system_type = system_config.system_type.value if system_config else SystemType.HOT_SYSTEM.value
            dpg.add_combo([s.value for s in SystemType], default_value=default_system_type, tag="system_combobox")
            dpg.add_button(label="Save", callback=on_save)

        # Create the main table
        with dpg.table(header_row=False, resizable=False, width=total_cell_width * matrix_size, height=170 * matrix_size + 20):
            for _ in range(matrix_size):
                dpg.add_table_column(width=total_cell_width)

            index = 0  # Device index for accessing each device

            for _ in range(matrix_size):
                with dpg.table_row(height=170):
                    for _ in range(matrix_size):
                        if index < num_devices:
                            device = devices_list[index]
                            instrument = device.instrument
                            # Create a unique window ID to apply highlighting to
                            window_id = dpg.generate_uuid()

                            # Use a child window to encapsulate the content for highlighting
                            with dpg.child_window(width=total_cell_width, height=170, tag=window_id):
                                with dpg.group(horizontal=True):
                                    # Image clickable to toggle selection
                                    dpg.add_image_button(
                                        f"{instrument.value}_texture", width=80, height=80,
                                        callback=toggle_device_selection,
                                        user_data=(device, window_id)
                                    )

                                    with dpg.group():
                                        dpg.add_text(f"{instrument.value}")
                                        dpg.add_text(f"IP: {device.ip_address or 'N/A'}")
                                        dpg.add_text(f"MAC: {device.mac_address or 'N/A'}")
                                        dpg.add_text(f"SN: {device.serial_number or 'N/A'}")

                                        with dpg.group(horizontal=True):
                                            dpg.add_text(f"COM Port:")
                                            dpg.add_input_text(default_value=device.com_port or '',
                                                               callback=update_device_com_port,
                                                               user_data=device)

                                            # Add a simulation checkbox
                                        with dpg.group(horizontal=True):
                                            dpg.add_text("Simulation:")
                                            dpg.add_checkbox(default_value=True if device.simulation is None else device.simulation,
                                                             callback=update_device_simulation,
                                                             user_data=device)

                                        with dpg.group(horizontal=True):
                                            dpg.add_text("Misc:")
                                            dpg.add_input_text(
                                                default_value=device.misc or 'N/A',
                                                callback=update_device_misc,
                                                user_data=device)

                            # Bind the theme based on selection
                            if selected_devices.get(generate_device_key(device), False):
                                dpg.bind_item_theme(window_id, "selected_theme")
                            else:
                                dpg.bind_item_theme(window_id, "default_theme")

                            index += 1  # Move to next device
                        else:
                            with dpg.child_window(width=total_cell_width, height=120):
                                pass



    # Popups for messages
    with dpg.window(label="Success", tag="SuccessPopup", modal=True, show=False):
        dpg.add_text("Configuration saved successfully!")

    with dpg.window(label="Warning", tag="WarningPopup", modal=True, show=False):
        dpg.add_text("No instruments selected!")

    with dpg.window(label="Error", tag="ErrorPopup", modal=True, show=False):
        dpg.add_text("", tag="ErrorText")

    dpg.create_viewport(title="System Configuration GUI", width=total_cell_width * matrix_size + 50, height=150 * matrix_size + 200)


def update_device_misc(sender, app_data, user_data):
    """
    Update the misc attribute of the device.
    sender: the ID of the calling widget
    app_data: the value from the widget (string)
    user_data: the device object passed as user_data
    """
    device = user_data
    device.misc = app_data  # Update the misc attribute of the device

def update_device_com_port(sender, app_data, user_data):
    """
    Update the com_port attribute of the device.
    sender: the ID of the calling widget
    app_data: the value from the widget
    user_data: the device object passed as user_data
    """
    device = user_data
    device.com_port = app_data  # Update the com_port attribute of the device

def update_device_simulation(sender, app_data, user_data):
    """
    Update the simulation attribute of the device.
    sender: the ID of the calling widget
    app_data: the value from the widget (True/False for checkbox)
    user_data: the device object passed as user_data
    """
    print("Simulation callback triggered!")

    device = user_data
    device.simulation = app_data  # Update the simulation attribute of the device



if __name__ == "__main__":
    dpg.create_context()
    run_system_config_gui()
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

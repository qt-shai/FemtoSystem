import threading
import time

import dearpygui.dearpygui as dpg
import numpy as np
from Common import DpgThemes
from HW_wrapper import SirahMatisse
from SystemConfig import Instruments, load_instrument_images

class GUIMatisse:
    def __init__(self, device: SirahMatisse, instrument: Instruments = Instruments.MATTISE, simulation: bool = False) -> None:
        """
        GUI class for Sirah Matisse laser control.

        :param device: The Sirah Matisse laser device object.
        :param instrument: The instrument identifier.
        :param simulation: Flag to indicate if simulation mode is enabled.
        """
        self.scan_thread = None
        self.scanning = False
        self.is_collapsed: bool = False
        load_instrument_images()
        self.dev = device
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()
        self.instrument = instrument
        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        self.window_tag = "Matisse_Win"
        with dpg.window(tag=self.window_tag, label=f"{self.instrument.value}",
                        no_title_bar=False, height=320, width=1800, pos=[20, 20], collapsed=False):
            with dpg.group(horizontal=True):
                self.create_instrument_image()
                self.create_diode_power_controls(red_button_theme)
                self.create_thin_etalon_controls(red_button_theme)
                self.create_bifi_controls(red_button_theme)
                self.create_piezo_controls(red_button_theme)
                self.create_scan_controls(red_button_theme)
                self.create_refcell_controls(red_button_theme)
                self.create_scanning_controls(red_button_theme)

        # Store column tags for easy access and interchangeability
        self.column_tags = [
            f"column_diode_power_{self.unique_id}",
            f"column_thin_etalon_{self.unique_id}",
            f"column_bifi_{self.unique_id}",
            f"column_piezo_{self.unique_id}",
            f"column_scan_{self.unique_id}",
            f"column_refcell_{self.unique_id}",
        ]

        if not simulation:
            self.connect()

    def _get_unique_id_from_device(self) -> str:
        """
        Generate a unique identifier for the GUI instance based on the device properties.

        :return: A string that uniquely identifies this device.
        """
        if hasattr(self.dev, 'addr') and self.dev.addr is not None:
            return self.dev.addr
        else:
            return str(id(self.dev))

    def create_instrument_image(self):
        with dpg.group(horizontal=False, tag=f"column_instrument_image_{self.unique_id}"):
            dpg.add_image_button(
                f"{self.instrument.value}_texture", width=80, height=80,
                callback=self.toggle_gui_collapse,
                user_data=None
            )

    def create_diode_power_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_diode_power_{self.unique_id}", width=150):
            dpg.add_text("Diode Power")
            dpg.add_text("Current Power:", tag=f"DiodePower_{self.unique_id}")
            dpg.add_text("Low-level Cutoff:")
            dpg.add_input_float(label="", default_value=0.0, tag=f"DiodePowerCutoff_{self.unique_id}",
                                format='%.2f', width=100)
            dpg.add_button(label="Set Cutoff", callback=self.btn_set_diode_power_cutoff)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_thin_etalon_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_thin_etalon_{self.unique_id}", width=200):
            dpg.add_text("Thin Etalon Motor")
            dpg.add_text("Position:", tag=f"ThinEtalonPosition_{self.unique_id}")
            dpg.add_input_int(default_value=0, tag=f"ThinEtalonMoveTo_{self.unique_id}", width=100)
            dpg.add_button(label="Move", callback=self.btn_move_thin_etalon)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Stop", callback=self.btn_stop_thin_etalon)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Home", callback=self.btn_home_thin_etalon)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_text("Control Status:")
            dpg.add_combo(["run", "stop"], default_value="stop", tag=f"ThinEtalonCtlStatus_{self.unique_id}",
                          callback=self.btn_set_thin_etalon_ctl_status, width=100)

    def create_bifi_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_bifi_{self.unique_id}", width=200):
            dpg.add_text("Birefringent Filter Motor")
            dpg.add_text("Position:", tag=f"BifiPosition_{self.unique_id}")
            dpg.add_input_int(default_value=0, tag=f"BifiMoveTo_{self.unique_id}", width=100)
            dpg.add_button(label="Move", callback=self.btn_move_bifi)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Stop", callback=self.btn_stop_bifi)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_button(label="Home", callback=self.btn_home_bifi)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_piezo_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_piezo_{self.unique_id}", width=200):
            dpg.add_text("Piezo Controls")
            dpg.add_text("Slow Piezo Position:", tag=f"SlowPiezoPosition_{self.unique_id}")
            dpg.add_input_float(default_value=0.0, tag=f"SlowPiezoSetPos_{self.unique_id}",
                                format='%.4f', width=100)
            dpg.add_button(label="Set", callback=self.btn_set_slowpiezo_position)
            dpg.bind_item_theme(dpg.last_item(), theme)

            dpg.add_text("Slow Piezo Lock:")
            dpg.add_combo(
                ["run", "stop"],
                default_value="stop",
                tag=f"SlowPiezoCtlStatus_{self.unique_id}",
                callback=self.btn_set_slowpiezo_ctl_status,
                width=100
            )


            dpg.add_text("Fast Piezo Position:", tag=f"FastPiezoPosition_{self.unique_id}")
            dpg.add_input_float(default_value=0.0, tag=f"FastPiezoSetPos_{self.unique_id}",
                                format='%.4f', width=100)
            dpg.add_button(label="Set", callback=self.btn_set_fastpiezo_position)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_text("Fast Piezo Lock:")
            dpg.add_combo(["run", "stop"], default_value="stop", tag=f"FastPiezoCtlStatus_{self.unique_id}",
                          callback=self.btn_set_fastpiezo_ctl_status, width=100)

    def create_scan_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_scan_{self.unique_id}", width=200):
            dpg.add_text("Scan Controls")
            dpg.add_text("Scan Status:")
            dpg.add_combo(["run", "stop"], default_value="stop", tag=f"ScanStatus_{self.unique_id}",
                          callback=self.btn_set_scan_status, width=100)
            dpg.add_button(label="Wait for Scan", callback=self.btn_wait_scan)
            dpg.bind_item_theme(dpg.last_item(), theme)
            dpg.add_text("Scan Position:", tag=f"ScanPosition_{self.unique_id}")
            dpg.add_input_float(default_value=0.0, tag=f"ScanSetPosition_{self.unique_id}",
                                format='%.4f', width=100)
            dpg.add_button(label="Set", callback=self.btn_set_scan_position)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_refcell_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_refcell_{self.unique_id}", width=200):
            dpg.add_text("Reference Cell Controls")
            dpg.add_text("Reference cell Position (0-1):", tag=f"RefcellPosition_{self.unique_id}")
            dpg.add_input_float(default_value=0.0, tag=f"RefcellSetPos_{self.unique_id}",
                                format='%.4f', width=100, callback=self.validate_refcell_position)
            dpg.add_button(label="Set", callback=self.btn_set_refcell_position)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def validate_refcell_position(self, sender, app_data, user_data):
        """
        Ensures that the input value for the reference cell position stays between 0 and 1.
        If the value goes outside the range, it's automatically adjusted.
        """
        value = dpg.get_value(f"RefcellSetPos_{self.unique_id}")
        value = np.clip(value, 0, 1)
        dpg.set_value(f"RefcellSetPos_{self.unique_id}", value)

    def btn_set_refcell_position(self):
        """
        Set the reference cell position using the value from the input field.
        """
        value = dpg.get_value(f"RefcellSetPos_{self.unique_id}")
        updated_position = self.dev.set_refcell_position(value)
        dpg.set_value(f"RefcellPosition_{self.unique_id}", f"{updated_position:.4f}")

    def toggle_gui_collapse(self):
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.show_item(column_tag)
            dpg.set_item_width(self.window_tag, 1800)
            dpg.set_item_height(self.window_tag, 320)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.hide_item(column_tag)
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    def btn_set_diode_power_cutoff(self):
        cutoff = dpg.get_value(f"DiodePowerCutoff_{self.unique_id}")
        self.dev.set_diode_power_lowlevel(cutoff)

    def btn_move_thin_etalon(self):
        position = dpg.get_value(f"ThinEtalonMoveTo_{self.unique_id}")
        self.dev.thin_etalon_move_to(position)

    def btn_stop_thin_etalon(self):
        self.dev.thin_etalon_stop()

    def btn_home_thin_etalon(self):
        self.dev.thin_etalon_home()

    def btn_set_thin_etalon_ctl_status(self):
        status = dpg.get_value(f"ThinEtalonCtlStatus_{self.unique_id}")
        self.dev.set_thin_etalon_ctl_status(status)

    def btn_set_slowpiezo_ctl_status(self):
        """
        Handle changes to the slow piezo lock combo.
        'run' typically means 'locked', and 'stop' means 'unlocked'.
        """
        status = dpg.get_value(f"SlowPiezoCtlStatus_{self.unique_id}")
        # This calls your wrapper method that actually enables or disables
        # the slow piezo control loop in the Sirah Matisse device.
        self.dev.set_slowpiezo_ctl_status(status)

    def btn_move_bifi(self):
        position = dpg.get_value(f"BifiMoveTo_{self.unique_id}")
        self.dev.bifi_move_to(position)

    def btn_stop_bifi(self):
        self.dev.bifi_stop()

    def btn_home_bifi(self):
        self.dev.bifi_home()

    def btn_set_slowpiezo_position(self):
        value = dpg.get_value(f"SlowPiezoSetPos_{self.unique_id}")
        self.dev.set_slowpiezo_position(value)

    def btn_set_fastpiezo_position(self):
        value = dpg.get_value(f"FastPiezoSetPos_{self.unique_id}")
        self.dev.set_fastpiezo_position(value)

    def btn_set_fastpiezo_ctl_status(self):
        status = dpg.get_value(f"FastPiezoCtlStatus_{self.unique_id}")
        self.dev.set_fastpiezo_ctl_status(status)

    def btn_set_scan_status(self):
        status = dpg.get_value(f"ScanStatus_{self.unique_id}")
        self.dev.set_scan_status(status)

    def btn_wait_scan(self):
        self.dev.wait_scan()

    def btn_set_scan_position(self):
        value = dpg.get_value(f"ScanSetPosition_{self.unique_id}")
        self.dev.set_scan_position(value)

    def connect(self):
        try:
            self.dev.connect()
            print("Connected to Sirah Matisse")
            if self.dev.is_connected:
                dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} connected")
            else:
                dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} not connected")
        except Exception as e:
            print(f"Failed to connect to Sirah Matisse: {e}")
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} not connected")

    def create_scanning_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_scanning_{self.unique_id}", width=200):
            dpg.add_text("Scanning Controls")

            # Scan Device Selector
            dpg.add_text("Select Scan Device:")
            dpg.add_combo(
                ["Slow Piezo", "Ref Cell"],  # List of devices
                default_value="Slow Piezo",
                label="Scan Device",
                tag=f"ScanDeviceSelector_{self.unique_id}",
                width=150
            )

            dpg.add_input_float(label="Scan Range (MHz)", default_value=200.0, tag=f"ScanRange_{self.unique_id}",
                                format="%.2f", width=150, callback=self.update_scanning_parameters)
            dpg.add_input_float(label="Scan Speed (MHz/s)", default_value=100.0, tag=f"ScanSpeed_{self.unique_id}",
                                format="%.2f", width=150, callback=self.update_scanning_parameters)
            dpg.add_input_int(label="Number of Points", default_value=10, tag=f"NumberOfScanPoints_{self.unique_id}",
                              min_value=10, max_value=1000, width=150, callback=self.update_scanning_parameters)

            # "To MHz" conversion fields for each device
            dpg.add_text("Conversion Factors (to MHz):")
            dpg.add_input_float(
                label="Slow Piezo to MHz",
                default_value=81500.0,
                tag=f"SlowPiezoToMHz_{self.unique_id}",
                format="%.6f",
                width=150,
                callback = self.update_scanning_parameters,
            )
            dpg.add_input_float(
                label="Ref Cell to MHz",
                default_value=81500.0,
                tag=f"RefCellToMHz_{self.unique_id}",
                format="%.6f",
                width=150,
                callback = self.update_scanning_parameters,
            )

            # Start/Stop Scan Button
            dpg.add_button(label="Start Scan", tag=f"StartStopScan_{self.unique_id}", callback=self.toggle_scan)
            dpg.bind_item_theme(dpg.last_item(), theme)

            # Initialize wrapper attributes
            self.dev.scan_device = "Slow Piezo"
            self.dev.scan_range = 200.0
            self.dev.scan_speed = 100.0
            self.dev.num_scan_points = 10
            self.dev.slow_piezo_to_mhz = 81500.0
            self.dev.ref_cell_to_mhz = 81500.0

    def update_scanning_parameters(self, sender, app_data, user_data):
        """
        Update scanning parameters in the SirahMatisse wrapper based on GUI input values.
        """
        self.dev.scan_device = dpg.get_value(f"ScanDeviceSelector_{self.unique_id}")
        self.dev.scan_range = dpg.get_value(f"ScanRange_{self.unique_id}")
        self.dev.scan_speed = dpg.get_value(f"ScanSpeed_{self.unique_id}")
        self.dev.num_scan_points = dpg.get_value(f"NumberOfScanPoints_{self.unique_id}")
        self.dev.slow_piezo_to_mhz = dpg.get_value(f"SlowPiezoToMHz_{self.unique_id}")
        self.dev.ref_cell_to_mhz = dpg.get_value(f"RefCellToMHz_{self.unique_id}")

        print(f"Updated scanning parameters: {self.dev.scan_device}, "
              f"Range: {self.dev.scan_range} MHz, Speed: {self.dev.scan_speed} MHz/s, "
              f"Points: {self.dev.num_scan_points}, S low Piezo Conversion: {self.dev.slow_piezo_to_mhz}, "
              f"Ref Cell Conversion: {self.dev.ref_cell_to_mhz}")

    def toggle_scan(self):
        """
        Toggles between starting and stopping the scan.
        """
        button_label = dpg.get_item_label(f"StartStopScan_{self.unique_id}")

        if button_label == "Start Scan":
            dpg.set_item_label(f"StartStopScan_{self.unique_id}", "Stop Scan")
            self.start_scan()
        else:
            dpg.set_item_label(f"StartStopScan_{self.unique_id}", "Start Scan")
            self.stop_scan()

    def btn_start_stop_scan(self):
        """
        Handles the Start/Stop Scan button press.
        """
        try:
            # Get current button label
            button_label = dpg.get_item_label(f"StartStopScan_{self.unique_id}")

            if button_label == "Start Scan":
                # Change button to "Stop Scan"
                dpg.set_item_label(f"StartStopScan_{self.unique_id}", "Stop Scan")

                # Get the selected scan device
                scan_device = dpg.get_value(f"ScanDeviceSelector_{self.unique_id}")

                self.dev.set_slowpiezo_ctl_status("stop")
                time.sleep(0.5)
                self.dev.set_fastpiezo_ctl_status("stop")
                time.sleep(0.5)

                # Start the scan process
                self.start_scan()
            else:
                # Change button back to "Start Scan"
                dpg.set_item_label(f"StartStopScan_{self.unique_id}", "Start Scan")

                # Stop the scan process
                self.stop_scan()
        except Exception as e:
            print(f"Error handling Start/Stop Scan button: {e}")

    def start_scan(self):
        """
        Start the scan process based on the selected device and parameters.
        """
        scan_device = dpg.get_value(f"ScanDeviceSelector_{self.unique_id}")
        scan_range = dpg.get_value(f"ScanRange_{self.unique_id}")
        scan_speed = dpg.get_value(f"ScanSpeed_{self.unique_id}")
        num_points = dpg.get_value(f"NumberOfScanPoints_{self.unique_id}")

        # Get the appropriate conversion factor
        if scan_device == "Slow Piezo":
            piezo_to_mhz = dpg.get_value(f"SlowPiezoToMHz_{self.unique_id}")
            control_func = self.dev.set_slowpiezo_position
            get_position_func = self.dev.get_slowpiezo_position
        elif scan_device == "Ref Cell":
            piezo_to_mhz = dpg.get_value(f"RefCellToMHz_{self.unique_id}")
            control_func = self.dev.set_refcell_position
            get_position_func = self.dev.get_refcell_position
        else:
            print(f"Unknown scan device: {scan_device}")
            return

        # Run the scan in a background thread
        self.scanning = True
        self.scan_thread = threading.Thread(
            target=self.scan_loop,
            args=(control_func, get_position_func, scan_range, scan_speed, num_points, piezo_to_mhz),
            daemon=True
        )
        self.scan_thread.start()

    def scan_loop(self, control_func, get_position_func, scan_range_mhz, scan_speed_mhz_per_s, num_scan_points,
                  piezo_to_mhz):
        """
        Perform the up-and-down scanning using the selected device in a loop until stopped.

        :param control_func: Function to set the position of the selected device.
        :param get_position_func: Function to get the current position of the selected device.
        :param scan_range_mhz: Total range of the scan in MHz.
        :param scan_speed_mhz_per_s: Speed of the scan in MHz per second.
        :param num_scan_points: Number of points in one scan direction.
        :param piezo_to_mhz: Conversion factor from piezo units to MHz.
        """
        try:
            # Convert scan parameters to piezo units
            scan_range_piezo = scan_range_mhz / piezo_to_mhz
            step_size_piezo = scan_range_piezo / num_scan_points
            start_position = get_position_func()

            # Generate positions for up and down scan
            positions_up = [start_position + i * step_size_piezo for i in range(num_scan_points + 1)]
            positions_down = positions_up[::-1]
            full_scan_positions = positions_up + positions_down

            # Calculate delay between steps based on speed
            delay_per_step = step_size_piezo / (scan_speed_mhz_per_s / piezo_to_mhz)

            print(f"Starting scan with {len(full_scan_positions)} points. Delay per step: {delay_per_step:.4f}s")

            # Perform the scan loop
            self.scanning = True
            while self.scanning:
                for pos in full_scan_positions:
                    if not self.scanning:
                        print("Scan stopped by user.")
                        return  # Exit the scan loop if stopped
                    control_func(pos)
                    time.sleep(delay_per_step)  # Simulate speed

            print("Scan completed successfully.")
        except Exception as e:
            print(f"Error during scan: {e}")
        finally:
            self.scanning = False

    def stop_scan(self):
        """
        Stop the scanning process.
        """
        try:
            if hasattr(self, 'scanning') and self.scanning:
                self.scanning = False  # Signal to terminate the scanning loop
                print("Stopping the scan...")

                # Wait for the thread to finish if it's running
                if hasattr(self, 'scan_thread') and self.scan_thread and self.scan_thread.is_alive():
                    self.scan_thread.join(timeout=5)  # Wait for a maximum of 5 seconds
                    if self.scan_thread.is_alive():
                        print("Scan thread did not terminate cleanly. It may need manual intervention.")
                    else:
                        print("Scan stopped successfully.")
                else:
                    print("No active scan thread.")
            else:
                print("No scan is currently running.")
        except Exception as e:
            print(f"An error occurred while stopping the scan: {e}")



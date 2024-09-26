from HW_wrapper import HW_devices as hwDevices
import dearpygui.dearpygui as dpg
from HW_wrapper.Wrapper_ELC_power_supply import ALR3206T


class ALR3206TGUI:
    def __init__(self, simulation: bool = False):
        """
        Initialize the GUI for ALR3206T power supply.

        """
        self.HW = hwDevices.HW_devices()
        self.psu: ALR3206T = self.HW.power_supply if not simulation else None
        self.simulation = simulation

    def set_current(self, sender, app_data, user_data):
        """
        Set the current for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        current = dpg.get_value(sender)
        self.psu.set_current(channel, current)
        dpg.set_value(user_data['response'], f"Current set to {current} A on channel {channel}")

    def get_current(self, sender, app_data, user_data):
        """
        Get the current for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        current = self.psu.get_current(channel)
        dpg.set_value(user_data['response'], f"Current on channel {channel}: {current} A")

    def set_voltage(self, sender, app_data, user_data):
        """
        Set the voltage for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        voltage = dpg.get_value(sender)
        self.psu.set_voltage(channel, voltage)
        dpg.set_value(user_data['response'], f"Voltage set to {voltage} V on channel {channel}")

    def get_voltage(self, sender, app_data, user_data):
        """
        Get the voltage for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        voltage = self.psu.get_voltage(channel)
        dpg.set_value(user_data['response'], f"Voltage on channel {channel}: {voltage} V")

    def output_on(self, sender, app_data, user_data):
        """
        Turn on the output for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        self.psu.output_on(channel)
        dpg.set_value(user_data['response'], f"Output on channel {channel} turned on")

    def output_off(self, sender, app_data, user_data):
        """
        Turn off the output for a specific channel.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        channel = user_data['channel']
        self.psu.output_off(channel)
        dpg.set_value(user_data['response'], f"Output on channel {channel} turned off")

    def identify(self, sender, app_data, user_data):
        """
        Identify the power supply.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        identity = self.psu.identify()
        dpg.set_value(user_data['response'], f"Identity: {identity}")

    def controls(self):
        """
        Create and run the GUI for controlling the ALR3206T power supply.
        """
        dpg.add_window(label="ALR3206T Control", width=600, height=400, tag="mainPWR_SUP_window", no_title_bar=False)
        if self.simulation:
            max_current = [6]*3
            max_voltage = [32] *3
        else:
            max_current = [self.psu.get_ocp(channel) for channel in range(1, 4)]
            max_voltage = [self.psu.get_ovp(channel) for channel in range(1, 4)]

        for channel in range(1, 4):
            dpg.add_group(label=f"Channel {channel} Controls", tag=f"Channel {channel} Controls", parent="mainPWR_SUP_window")
            dpg.add_text(label=f"Channel {channel}", parent=f"Channel {channel} Controls")
            dpg.add_slider_float(label="Set Current (A)",
                                 min_value=0.0,
                                 max_value=max_current[channel-1],
                                 callback=self.set_current if not self.simulation else None,
                                 user_data={'channel': channel, 'response': f'current_response_{channel}'},
                                 parent=f"Channel {channel} Controls")
            dpg.add_button(label="Get Current",
                           callback=self.get_current if not self.simulation else None,
                           user_data={'channel': channel, 'response': f'current_response_{channel}'},
                           parent=f"Channel {channel} Controls")
            dpg.add_slider_float(label="Set Voltage (V)",
                                 min_value=0.0,
                                 max_value=max_voltage[channel-1],
                                 callback=self.set_voltage if not self.simulation else None,
                                 user_data={'channel': channel, 'response': f'voltage_response_{channel}'},
                                 parent=f"Channel {channel} Controls")
            dpg.add_button(label="Get Voltage",
                           callback=self.get_voltage if not self.simulation else None,
                           user_data={'channel': channel, 'response': f'voltage_response_{channel}'},
                           parent=f"Channel {channel} Controls")
            dpg.add_button(label="Output On",
                           callback=self.output_on if not self.simulation else None,
                           user_data={'channel': channel, 'response': f'output_response_{channel}'},
                           parent=f"Channel {channel} Controls")
            dpg.add_button(label="Output Off",
                           callback=self.output_off if not self.simulation else None,
                           user_data={'channel': channel, 'response': f'output_response_{channel}'},
                           parent=f"Channel {channel} Controls")
            dpg.add_text("", tag=f'current_response_{channel}', parent=f"Channel {channel} Controls")
            dpg.add_text("", tag=f'voltage_response_{channel}', parent=f"Channel {channel} Controls")
            dpg.add_text("", tag=f'output_response_{channel}', parent=f"Channel {channel} Controls")

        dpg.add_button(label="Identify", tag="Identify",
                       callback=self.identify if not self.simulation else None,
                       user_data={'response': 'identify_response'},
                       parent="mainPWR_SUP_window")
        dpg.add_text("", tag='identify_response', parent=f"Identify")
import dearpygui.dearpygui as dpg
from HW_wrapper import AttoDry800


class AttoDry800GUI:
    def __init__(self, address: str):
        """
        Initialize the GUI for AttoDry800 cryostat.

        :param address: The IP address of the cryostat.
        """
        self.cryostat = AttoDry800(address)
        self.cryostat.connect()

    def set_temperature(self, sender, app_data, user_data):
        """
        Set the temperature of the cryostat.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        temperature = dpg.get_value(sender)
        self.cryostat.set_temperature(temperature)
        dpg.set_value(user_data['response'], f"Temperature set to {temperature} K")

    def get_temperature(self, sender, app_data, user_data):
        """
        Get the current temperature of the cryostat.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        temperature = self.cryostat.get_temperature()
        dpg.set_value(user_data['response'], f"Current Temperature: {temperature} K")

    def stabilize_temperature(self, sender, app_data, user_data):
        """
        Stabilize the temperature of the cryostat.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        stabilize = user_data['stabilize']
        self.cryostat.stabilize_temperature(stabilize)
        status = "enabled" if stabilize else "disabled"
        dpg.set_value(user_data['response'], f"Temperature stabilization {status}")

    def set_position(self, sender, app_data, user_data):
        """
        Set the position for a specific axis.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        axis = user_data['axis']
        position = dpg.get_value(sender)
        self.cryostat.set_position(axis, position)
        dpg.set_value(user_data['response'], f"Position of axis {axis} set to: {position}")

    def get_position(self, sender, app_data, user_data):
        """
        Get the current position of a specific axis.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        axis = user_data['axis']
        position = self.cryostat.get_position(axis)
        dpg.set_value(user_data['response'], f"Current Position of axis {axis}: {position}")

    def move_reference(self, sender, app_data, user_data):
        """
        Move to the reference position for a specific axis.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        axis = user_data['axis']
        self.cryostat.move_reference(axis)
        dpg.set_value(user_data['response'], f"Moved to reference position for axis {axis}")

    def identify(self, sender, app_data, user_data):
        """
        Identify the cryostat.

        :param sender: The sender of the event.
        :param app_data: The data of the event.
        :param user_data: The user data passed to the callback.
        """
        identity = self.cryostat.identify()
        dpg.set_value(user_data['response'], f"Identity: {identity}")

    def create_gui(self):
        """
        Create and run the GUI for controlling the AttoDry800 cryostat.
        """
        with dpg.window(label="AttoDry800 Control", width=600, height=400):
            dpg.add_text("Temperature Control")
            dpg.add_slider_float(label="Set Temperature (K)", min_value=0.0, max_value=300.0, callback=self.set_temperature, user_data={'response': 'temperature_response'})
            dpg.add_button(label="Get Temperature", callback=self.get_temperature, user_data={'response': 'temperature_response'})
            dpg.add_button(label="Stabilize Temperature", callback=self.stabilize_temperature, user_data={'stabilize': True, 'response': 'temperature_stabilization_response'})
            dpg.add_button(label="Disable Temperature Stabilization", callback=self.stabilize_temperature, user_data={'stabilize': False, 'response': 'temperature_stabilization_response'})
            dpg.add_text("", tag='temperature_response')
            dpg.add_text("", tag='temperature_stabilization_response')

            for axis in range(3):
                with dpg.group(label=f"Axis {axis} Controls"):
                    dpg.add_text(f"Axis {axis}")
                    dpg.add_slider_float(label="Set Position (nm or µ°)", min_value=0.0, max_value=10000.0, callback=self.set_position, user_data={'axis': axis, 'response': f'position_response_{axis}'})
                    dpg.add_button(label="Get Position", callback=self.get_position, user_data={'axis': axis, 'response': f'position_response_{axis}'})
                    dpg.add_button(label="Move to Reference", callback=self.move_reference, user_data={'axis': axis, 'response': f'reference_response_{axis}'})
                    dpg.add_text("", tag=f'position_response_{axis}')
                    dpg.add_text("", tag=f'reference_response_{axis}')

            dpg.add_button(label="Identify", callback=self.identify, user_data={'response': 'identify_response'})
            dpg.add_text("", tag='identify_response')

        dpg.start_dearpygui()
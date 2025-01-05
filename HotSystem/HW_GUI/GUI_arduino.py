import dearpygui.dearpygui as dpg
from HW_wrapper import ArduinoController  # Import the modified ArduinoController


class GUIArduino:
    """
    GUI interface for Arduino communication using DearPyGui.
    """

    def __init__(self, arduino: ArduinoController):
        """
        Initializes the GUI for Arduino control.

        :param arduino: The ArduinoController instance.
        """
        self.arduino = arduino

        # Subscribe GUI elements to observable fields
        self.arduino.communication_result.add_observer(self.update_results_display)
        self.arduino.num_points.add_observer(self.update_num_points)
        self.arduino.time_interval_us.add_observer(self.update_time_interval)

        # Create GUI window
        with dpg.window(tag="ArduinoWin", label="Arduino Communication", width=500, height=300):
            dpg.add_text("Arduino Communication Panel", color=(0, 255, 0))

            # Input Fields
            dpg.add_input_int(label="Number of Points", tag="num_points", default_value=self.arduino.num_points.get(),
                              callback=self.set_num_points)
            dpg.add_input_int(label="Time Interval (μs)", tag="time_interval", default_value=self.arduino.time_interval_us.get(),
                              callback=self.set_time_interval)

            # Buttons
            dpg.add_button(label="Start Measurement", callback=self.arduino.start_measurement)
            dpg.add_button(label="Read Measurement", callback=self.arduino.read_measurement)

            # Response Display
            dpg.add_text("Results:", tag="results_label")
            dpg.add_text("", tag="results_display", wrap=450)

    def update_results_display(self, result: str):
        """
        Updates the GUI text element when new data is received.
        """
        dpg.set_value("results_display", result)

    def update_num_points(self, value: int):
        """
        Updates the number of points field in the GUI.
        """
        dpg.set_value("num_points", value)

    def update_time_interval(self, value: int):
        """
        Updates the time interval field in the GUI.
        """
        dpg.set_value("time_interval", value)

    def set_num_points(self, sender, app_data):
        """
        Callback to update the observable num_points field when changed in GUI.
        """
        self.arduino.num_points.set(app_data)

    def set_time_interval(self, sender, app_data):
        """
        Callback to update the observable time_interval_us field when changed in GUI.
        """
        self.arduino.time_interval_us.set(app_data)
from typing import List

import dearpygui.dearpygui as dpg

from HW_wrapper import NI_DAQ_Controller


class GUIDAQ:
    """
    GUI interface for NI-DAQ communication using DearPyGui.
    """
    def __init__(self, daq: NI_DAQ_Controller):
        """
        Initializes the GUI for NI-DAQ control.

        :param daq: The NI_DAQ_Controller instance.
        """
        self.unique_id = "daq_gui"
        self.daq = daq
        self._measuring = False

        # Subscribe to observable fields for live updates.
        self.daq.communication_result.add_observer(self.update_results_display)
        self.daq.observable_num_samples.add_observer(self.update_num_samples)
        self.daq.time_interval_us.add_observer(self.update_time_interval)
        self.daq.measurement_data.add_observer(self.update_graph)

        with dpg.window(tag="DAQ_Win", label="NI-DAQ Communication", width=460, height=420, pos=[30, 30]):
            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Samples", tag="num_samples",
                                  default_value=self.daq.observable_num_samples.get(),
                                  callback=self.set_num_samples, width=150)
                dpg.add_input_int(label="Time Interval (us)", tag="time_interval",
                                  default_value=self.daq.time_interval_us.get(),
                                  callback=self.set_time_interval, width=150)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Open DAQ", callback=self.open_daq)
                dpg.add_button(label="Read Once", callback=self.read_measurement_and_update_graph)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Start Measure", callback=self.start_measure_cb)
                dpg.add_button(label="Stop Measure", callback=self.stop_measure_cb)
                dpg.add_button(label="Close DAQ", callback=self.close_daq)
            with dpg.group(horizontal=True):
                dpg.add_input_int(label="Pulse Width (us)", tag="pulse_width",
                                  default_value=self.daq.pulse_width_us.get(), width=100)
                dpg.add_input_int(label="Pulse Spacing (us)", tag="pulse_spacing",
                                  default_value=self.daq.pulse_spacing_us.get(), width=100)
                dpg.add_button(label="Set Pulse", callback=self.set_pulse, width=50)
                dpg.add_button(label="Stop Pulse", callback=self.stop_pulse, width=50)
            with dpg.plot(label="Measurement Plot", height=300, width=400):
                x_axis_tag = f"x_axis_{self.unique_id}"
                y_axis_tag = f"y_axis_{self.unique_id}"
                dpg.add_plot_axis(dpg.mvXAxis, label="Time (s)", tag=x_axis_tag)
                with dpg.plot_axis(dpg.mvYAxis, label="Measurement", tag=y_axis_tag):
                    dpg.add_line_series([], [], label="Measurements", tag="measurement_series")
            dpg.add_text("", tag="results_display")

    def update_results_display(self, result: str) -> None:
        dpg.set_value("results_display", result)

    def update_num_samples(self, value: int) -> None:
        dpg.set_value("num_samples", value)

    def update_time_interval(self, value: int) -> None:
        dpg.set_value("time_interval", value)

    def set_num_samples(self, sender, app_data) -> None:
        self.daq.observable_num_samples.set(app_data)

    def set_time_interval(self, sender, app_data) -> None:
        self.daq.time_interval_us.set(app_data)

    def open_daq(self, sender, app_data) -> None:
        try:
            self.daq.open()
        except Exception as e:
            dpg.set_value("results_display", f"Open DAQ error: {e}")

    def close_daq(self, sender, app_data) -> None:
        try:
            self.daq.close()
            dpg.set_value("results_display", "DAQ closed.")
        except Exception as e:
            dpg.set_value("results_display", f"Close DAQ error: {e}")

    def read_measurement_and_update_graph(self, sender, app_data) -> None:
        try:
            data = self.daq.acquire_data()
            time_interval = self.daq.time_interval_us.get() * 1e-6
            x_values = [i * time_interval for i in range(data.shape[0])]
            if dpg.does_item_exist("measurement_series"):
                dpg.set_value("measurement_series", [x_values, data.flatten().tolist()])
                dpg.fit_axis_data(f"x_axis_{self.unique_id}")
                dpg.fit_axis_data(f"y_axis_{self.unique_id}")
                dpg.set_value("results_display", "Graph updated.")
            else:
                dpg.set_value("results_display", "Plot series not found.")
        except Exception as e:
            dpg.set_value("results_display", f"Read error: {e}")

    def update_graph(self, measurements: List[float]) -> None:
        try:
            time_interval = self.daq.time_interval_us.get() * 1e-6
            x_values = [i * time_interval for i in range(len(measurements))]
            if dpg.does_item_exist("measurement_series"):
                dpg.set_value("measurement_series", [x_values, measurements])
                dpg.fit_axis_data(f"x_axis_{self.unique_id}")
                dpg.fit_axis_data(f"y_axis_{self.unique_id}")
            dpg.set_value("results_display", f"Graph updated with {len(measurements)} points.")
        except Exception as e:
            dpg.set_value("results_display", f"Graph update error: {e}")

    def start_measure_cb(self, sender, app_data) -> None:
        try:
            self.daq.start_measure()
            self._measuring = True
            dpg.set_value("results_display", "Measurement started.")
        except Exception as e:
            dpg.set_value("results_display", f"Start measure error: {e}")

    def stop_measure_cb(self, sender, app_data) -> None:
        try:
            self.daq.stop_measure()
            self._measuring = False
            dpg.set_value("results_display", "Measurement stopped.")
        except Exception as e:
            dpg.set_value("results_display", f"Stop measure error: {e}")

    def set_pulse(self, sender, app_data) -> None:
        try:
            pulse_width = dpg.get_value("pulse_width")
            pulse_spacing = dpg.get_value("pulse_spacing")
            if pulse_width <= 0 or pulse_spacing <= 0:
                dpg.set_value("results_display", "Pulse parameters must be > 0.")
                return
            self.daq.set_pulse(int(pulse_width), int(pulse_spacing))
        except Exception as e:
            dpg.set_value("results_display", f"Set pulse error: {e}")

    def stop_pulse(self, sender, app_data) -> None:
        try:
            self.daq.stop_pulse()
        except Exception as e:
            dpg.set_value("results_display", f"Stop pulse error: {e}")
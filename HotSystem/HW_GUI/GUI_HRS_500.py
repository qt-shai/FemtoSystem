import dearpygui.dearpygui as dpg
import numpy as np
from HW_wrapper.Wrapper_HRS_500 import LightFieldSpectrometer
import System.Diagnostics as diag
import os

class GUI_HRS500():

    def __init__(self, device) -> None:
        self.dev = device
        self.prefix = "hrs500"
        self.window_tag:str = f"{self.prefix}_Win"
        self.series_tag = f"spectrum_series_{self.prefix}"
        if self.dev:
            self.dev.set_save_directory("Q:\\QT-Quantum_Optic_Lab\\expData\\Spectrometer")
        self.create_gui()
        self.data = None


    def _cleanup(self):
        """Runs the moment the window is closed."""
        self.dev.close()
        os.system("taskkill /im AddInProcess.exe")

    def create_gui(self):
        Child_Width = 100
        line_color = (255, 140, 0, 255)
        LINE_WIDTH = 2
        self.define_hrs_themes()
        with dpg.window(label=f"{self.prefix} spectrometer", no_title_bar=False,
                        height=150, width=400, pos=[0, 0],
                        collapsed=False, tag=self.window_tag, on_close=self._cleanup):
            with dpg.group(horizontal=True, tag=f"group 1_{self.prefix}"):
                #dpg.add_button(label="Acquire", callback=self.acquire_callback)
                dpg.add_button(label="Acquire",
                               width=80, height=70,  # square → circle
                               callback=self.acquire_callback,
                               tag=f"acq_btn_{self.prefix}")  # give it an explicit tag
                dpg.bind_item_theme(f"acq_btn_{self.prefix}", f"acquire_red_theme_{self.prefix}")  # attach the theme
                dpg.add_button(label=" Load \n Exp",
                               width=70, height=70,
                               callback=self.load_callback,
                               tag=f"load_btn_{self.prefix}")
                dpg.bind_item_theme(f"load_btn_{self.prefix}", f"load_green_theme_{self.prefix}")
            with dpg.group(horizontal=True,tag=f"group 2_{self.prefix}"):
                with dpg.group(horizontal=True, tag=f"group 3_{self.prefix}"):
                    dpg.add_input_text(label="", tag="HRS_set_filename_input", indent=-1,
                                       callback=self.input_set_filename_callback)
                    dpg.add_button(label="Remember Name", callback=self.set_choose_directory_callback)
                dpg.add_group(tag=f"Graph_group_{self.prefix}", parent=self.window_tag, horizontal=True)
                dpg.add_plot(label="Graph", crosshairs=True, tag=f"graphXY_{self.prefix}", parent=f"Graph_group_{self.prefix}", height=-1,
                             width=-1)  # width=int(win_size[0]), height=int(win_size[1]))  # height=-1, width=-1,no_menus = False )
                dpg.add_plot_legend(parent=f"graphXY_{self.prefix}")  # optionally create legend
                dpg.add_plot_axis(dpg.mvXAxis, label="Wavelength [nm]", tag=f"x_axi_{self.prefix}", parent = f"graphXY_{self.prefix}")  # REQUIRED: create x and y axes
                dpg.add_plot_axis(dpg.mvYAxis, label="Intensity", tag=f"y_axis_{self.prefix}", invert=False,
                                  parent=f"graphXY_{self.prefix}")  # REQUIRED: create x and y axes
                dpg.add_line_series([], [], label="Spectrum",
                                    parent=f"y_axis_{self.prefix}", weigth = LINE_WIDTH, color = line_color,
                                    tag=self.series_tag)

    def acquire_callback(self):
        self.data = self.dev.acquire_Data()
        # sp = LightFieldSpectrometer(self.dev)
        # self.data = sp.load_experiment()
        self.data = np.asarray(self.data, dtype = float)
        self.data = self.data[self.data[:,0].argsort()]
        print(f"Data : {self.data}")
        if self.data is None or len(self.data) == 0:
            print("No data returned!")
            return

            # 2) split into x / y columns
        x_vals = self.data[:, 0].tolist()  # DearPyGui accepts Python lists
        y_vals = self.data[:, 1].tolist()

        # 3) if the series already exists → just overwrite its value
        if dpg.does_item_exist(self.series_tag):
            dpg.set_value(self.series_tag, [x_vals, y_vals])
        else:  # first run or series was deleted
            dpg.add_line_series(x_vals, y_vals, label="Spectrum",
                                parent=f"y_axis_{self.prefix}",
                                tag=self.series_tag)

        # 4) optionally fit axes to new data
        dpg.fit_axis_data(f"x_axi_{self.prefix}")
        dpg.fit_axis_data(f"y_axis_{self.prefix}")

    def load_callback(self):
        #file_path = "C:\\Users\\ice\\Work Folders\\Documents\\LightField\\Experiments\\Experiment2.lfe"
        self.dev.load_experiment()
        print("Loaded Experiment")

    def input_set_filename_callback(self, appdata, sender):
        self.file_name = sender

    def set_choose_directory_callback(self):
        self.dev.set_filename(self.file_name)

    def define_hrs_themes(self):
        with dpg.theme(tag=f"acquire_red_theme_{self.prefix}"):
            with dpg.theme_component(dpg.mvButton):
                # colours
                dpg.add_theme_color(dpg.mvThemeCol_Button, (200, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (220, 20, 20))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (150, 0, 0))
                # make the frame circular
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 100)  # ≥ half of width/height
                # keep the click area fully circular
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 0)

        with dpg.theme(tag=f"load_green_theme_{self.prefix}"):
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button,        (  0, 180,   0))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, ( 20, 220,  20))
                dpg.add_theme_color(dpg.mvThemeCol_ButtonActive,  (  0, 140,   0))
                dpg.add_theme_style(dpg.mvStyleVar_FrameRounding, 100)
                dpg.add_theme_style(dpg.mvStyleVar_FramePadding,  12, 12)



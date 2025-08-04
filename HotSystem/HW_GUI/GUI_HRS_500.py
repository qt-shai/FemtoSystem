from os.path import defpath

import dearpygui.dearpygui as dpg
import numpy as np
from HW_wrapper.Wrapper_HRS_500 import LightFieldSpectrometer
import System.Diagnostics as diag
import os, time
from Utils import open_file_dialog

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

    def DeleteMainWindow(self):
        """
        Safely delete the HRS_500 main window from DearPyGui.
        """
        if hasattr(self, "window_tag"):
            if dpg.does_item_exist(self.window_tag):
                dpg.delete_item(self.window_tag)
                print(f"{self.window_tag} deleted.")
            else:
                print(f"{self.window_tag} does not exist. Nothing to delete.")
        else:
            print("No window_tag attribute defined on HRS_500 GUI.")

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
                dpg.add_button(label=" Load \n Data",
                               width=70, height=70,
                               callback=self.load_data_callback,
                               tag=f"load_data_{self.prefix}")
                dpg.bind_item_theme(f"load_data_{self.prefix}", f"load_green_theme_{self.prefix}")
                dpg.add_input_text(label="", tag="HRS_set_filename_input", indent=-1,
                                   callback=self.input_set_filename_callback)
                dpg.add_button(label="Remember", callback=self.set_choose_directory_callback)
            dpg.add_group(tag=f"Graph_group_{self.prefix}", parent=self.window_tag, horizontal=True)
            dpg.add_plot(label="Graph", crosshairs=True, tag=f"graphXY_{self.prefix}", parent=f"Graph_group_{self.prefix}", height=-1,
                         width=-1)  # width=int(win_size[0]), height=int(win_size[1]))  # height=-1, width=-1,no_menus = False )
            dpg.add_plot_legend(parent=f"graphXY_{self.prefix}",tag="spectrum_graph_legend" )
            dpg.add_plot_axis(dpg.mvXAxis, label="Wavelength [nm]", tag=f"x_axi_{self.prefix}", parent = f"graphXY_{self.prefix}")  # REQUIRED: create x and y axes
            dpg.add_plot_axis(dpg.mvYAxis, label="Intensity", tag=f"y_axis_{self.prefix}", invert=False,
                              parent=f"graphXY_{self.prefix}")  # REQUIRED: create x and y axes
            dpg.add_line_series([], [], label="Spectrum",
                                parent=f"y_axis_{self.prefix}",
                                tag=self.series_tag)
    def load_data_callback(self):
        # Bring up a file dialog for CSV filesa
        start_dir = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"
        file_path = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],initial_folder=start_dir)
        if not file_path:
            print("Load canceled or no file selected.")
            return

        try:
            # load & sort
            data = np.genfromtxt(file_path, delimiter=',', skip_header=1)  # adjust if you have header
            data = data[data[:,0].argsort()]
            self.data = data
            print(f"Loaded data from: {file_path}")
        except Exception as e:
            print(f"Failed to load CSV '{file_path}': {e}")
            return

        # split into x/y
        x_vals = data[:,0].tolist()
        y_vals = data[:,1].tolist()

        # plot (overwrite or create)
        if dpg.does_item_exist(self.series_tag):
            dpg.set_value(self.series_tag, [x_vals, y_vals])
        else:
            dpg.add_line_series(x_vals, y_vals,
                                label="Spectrum",
                                parent=f"y_axis_{self.prefix}",
                                tag=self.series_tag)

        # hide the legend if desired
        if dpg.does_item_exist("spectrum_graph_legend"):
            dpg.hide_item("spectrum_graph_legend")

        # fit axes
        dpg.fit_axis_data(f"x_axi_{self.prefix}")
        dpg.fit_axis_data(f"y_axis_{self.prefix}")

        # update window title to filename only
        fname = os.path.basename(file_path)
        dpg.set_item_label(f"graphXY_{self.prefix}", fname)

    def acquire_callback(self):
        start_time = time.time()  # ✅ Start the timer
        self.data = self.dev.acquire_Data()
        # sp = LightFieldSpectrometer(self.dev)
        # self.data = sp.load_experiment()
        self.data = np.asarray(self.data, dtype = float)
        self.data = self.data[self.data[:,0].argsort()]

        # ✅ Remove outliers: drop rows where y >> mean
        y_mean = np.mean(self.data[:, 1])
        y_std = np.std(self.data[:, 1])

        # Define threshold (e.g., keep only values within 5× std from mean)
        threshold = y_mean + 8 * y_std
        mask = self.data[:, 1] < threshold
        filtered = self.data[mask]
        if len(filtered) < len(self.data):
            print(f"Removed {len(self.data) - len(filtered)} outlier(s) with Y > {threshold:.2f}")
        self.data = filtered

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
        if dpg.does_item_exist("spectrum_graph_legend"):
            dpg.hide_item("spectrum_graph_legend")
        # 4) optionally fit axes to new data
        dpg.fit_axis_data(f"x_axi_{self.prefix}")
        dpg.fit_axis_data(f"y_axis_{self.prefix}")
        # ─── rename the plot window to the filename ───
        try:
            # If your device stored the last file path:
            filepath = getattr(self.dev, 'last_saved_csv', None)
            if filepath is None:
                # fallback: use the current input‐box value
                filepath = getattr(self, 'file_name', None)

            if filepath:
                elapsed = time.time() - start_time  # ✅ Compute elapsed time
                elapsed_str = f"{elapsed:.0f}s"

                dirname, fname = os.path.split(filepath)
                base, ext = os.path.splitext(fname)
                new_fname = f"{base}_{elapsed_str}{ext}"
                new_fp = os.path.join(dirname, new_fname)

                try:
                    os.rename(filepath, new_fp)
                    print(f"Renamed file → {new_fp} | Time elapsed: {elapsed:.2f}s")
                    # Update your device’s last_saved_csv to the new name too:
                    self.dev.last_saved_csv = new_fp
                except Exception as e:
                    print(f"Failed to rename file with elapsed time: {e}")

                dpg.set_item_label(f"graphXY_{self.prefix}", os.path.basename(new_fp))
            else:
                dpg.set_item_label(f"graphXY_{self.prefix}", "Spectrum")
        except Exception as e:
            print(f"Could not update plot label to filename: {e}")

    def load_callback(self):
        #file_path = "C:\\Users\\ice\\Work Folders\\Documents\\LightField\\Experiments\\Experiment2.lfe"
        self.dev.load_experiment()
        print("Loaded Experiment")

    def input_set_filename_callback(self, appdata, sender):
        self.file_name = sender

    def set_choose_directory_callback(self):
        self.dev.set_filename(self.file_name)

    def define_hrs_themes(self):
        theme_tag = f"acquire_red_theme_{self.prefix}"
        if dpg.does_item_exist(theme_tag):
            print(f"Theme {theme_tag} already exists — skipping creation.")
            return

        with dpg.theme(tag=theme_tag):
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



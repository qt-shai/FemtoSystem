import dearpygui.dearpygui as dpg
import numpy as np
from Utils.Common import loadFromCSV
from Utils import open_file_dialog
import matplotlib.pyplot as plt
import os

class GUI_Survey_Interface:
    def __init__(self):
        self.endLoc = None
        self.startLoc = None
        self.file_path = "C://users//daniel//Work Folders//Documents//2024_7_1_7_5_41scan.csv"
        self.win_pos = None
        self.win_w = 1200
        self.win_h = 800
        self.data = None
        self.chosen_z_value = 126
        self.viewport_width = 800
        self.viewport_height = 600
        self.plot_size = [int(self.viewport_width * 0.3), int(self.viewport_height * 0.4)]
        self.scan_data = None
        self.result_arrayXY = None
        self.result_arrayXY_ = None
        self.arrXY = None
        self.idx_scan = None

    def GetWindowSize(self) -> None:
        win_size = [self.win_w, self.win_h]
        self.win_pos = [0, 100]
        item_width = int(200)

    def on_file_select_csv(self, sender, app_data) -> None:
        """Called when a CSV file is selected for heatmap generation."""
        file_path = app_data["file_path_name"]
        if not os.path.isfile(file_path):
            print("Invalid CSV file selected.")
            return

    def get_data_from_csv(self) -> None:
        fn = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if fn:  # Check if a file is selected
            self.idx_scan = [0, 0, 0]
            self.data = loadFromCSV(fn)
            print(np.shape(np.flipud(self.data)))
            self.process_data()
        print("Loaded csv data from file")

    def intensity_to_rgb_heatmap(self, intensity):
        # Define a colormap (you can choose any colormap from Matplotlib)
        # cmap = plt.get_cmap('hot')
        cmap = plt.get_cmap('jet')

        # Normalize the intensity to the range [0, 1] (if necessary)
        intensity = max(0, min(0.99999999, intensity))

        # Map the intensity value to a color in the colormap
        rgba_color = cmap(intensity)

        # Convert RGBA tuple to RGB tuple (discard alpha channel)
        rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))

        return rgb_color

    def process_data(self):
        self.data = np.array(self.data)
        self.scan_data = self.data[0:, 3].astype(float)
        self.im_arr_x = self.data[0:, 4].astype(float) / 1e6  # x data of the Smaract values from the csv
        self.im_arr_y = self.data[0:, 5].astype(float) / 1e6  # y data of the Smaract values from the csv
        self.im_arr_z = self.data[0:, 6].astype(float) / 1e6

        Nx = int(round((self.im_arr_x[-1] - self.im_arr_x[0]) / (self.im_arr_x[1] - self.im_arr_x[0])) + 1)
        Ny = int(round((self.im_arr_y[-1] - self.im_arr_y[0]) / (self.im_arr_y[Nx] - self.im_arr_y[0])) + 1)

        self.startLoc = [int(self.data[1, 4].astype(float) / 1e6), int(self.data[1, 5].astype(float) / 1e6),
                         int(self.data[1, 6].astype(float) / 1e6)]  # um
        self.endLoc = [int(self.data[-1, 4].astype(float) / 1e6), int(self.data[-1, 5].astype(float) / 1e6),
                       int(self.data[-1, 6].astype(float) / 1e6)]  # um

        #I feel like I only need one of those since z is constant
        self.arrXY = np.flipud(np.reshape(self.scan_data, (Nx,Ny))) #Needs to be reshaped to size (N_x,N_y,0). If the shape does not match Nx*Ny might fail
        #arrXY = np.flipud(self.scan_data[, :, :])

        self.result_arrayXY = (self.arrXY * 255 / self.arrXY.max())
        self.result_arrayXY_ = []
        for i in range(self.arrXY.shape[0]):
            for j in range(self.arrXY.shape[1]):
                # Convert the value at (i, j) to an 8-bit unsigned int and normalize it
                res = self.intensity_to_rgb_heatmap(self.arrXY.astype(np.uint8)[i][j] / 255)
                self.result_arrayXY_.extend([res[0] / 255, res[1] / 255, res[2] / 255, res[3] / 255])


    def queryXY_callback(self, app_data):
        # print("queryXY_callback")
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # Find the closest index in Yv for a[3]
            y_index = np.argmin(np.abs(self.im_arr_y - a[3]))
            # Find the closest index in Xv for a[1]
            x_index = np.argmin(np.abs(self.im_arr_x - a[1]))

            self.idx_scan[1] = y_index
            self.idx_scan[0] = x_index

            self.queried_area = a
            self.queried_plane = 0
        else:
            self.queried_area = None
            self.queried_plane = None

    def set_main_interface(self):
        # Add a child window for displaying the images in the future
        with dpg.window(label="Survey Window", tag="Survey_Window", no_title_bar=True, height=-1, width=1200, pos=self.win_pos):
            with dpg.group(horizontal=True):
                dpg.add_button(label="Load Data", callback=self.get_data_from_csv)
                dpg.add_button(label="Show Image", callback=self.add_image_graphics)

            dpg.add_texture_registry(show=False, tag="texture_reg")

        with dpg.file_dialog(directory_selector=False, show=False, callback=self.on_file_select_csv,
                             tag="csv_dialog",
                             modal=True, file_count=1,
                             default_path=self.file_path,
                             width=700, height=400):
            dpg.add_file_extension(".csv")

        dpg.add_group(horizontal=True, tag="survey_group", parent="Survey_Window")

    def add_image_graphics(self):
        #You can put the height and width to regular numbers for now
        #The code this was taken from had a 3d array
        dpg.add_dynamic_texture(width=self.arrXY.shape[1], height=self.arrXY.shape[0], default_value=self.result_arrayXY_,
                                tag="textureXY_tag",
                                parent="texture_reg")

        dpg.add_plot(parent="survey_group", tag="plotImage", width=self.plot_size[0], height=self.plot_size[1], equal_aspects=True,
                     crosshairs=True,
                     query=True, callback=self.queryXY_callback)
        dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z=" + "{0:.2f}".format(self.im_arr_z[0]),
                          parent="plotImage")
        dpg.add_plot_axis(dpg.mvYAxis, label="y axis", parent="plotImage", tag="plotImage_Y")
        dpg.add_image_series("textureXY_tag", bounds_min=[self.startLoc[0], self.startLoc[1]],
                             bounds_max=[self.endLoc[0], self.endLoc[1]],
                             label="Survey data", parent="plotImage_Y")
        dpg.add_colormap_scale(show=True, parent="survey_group", tag="colormapXY", min_scale=np.min(self.arrXY),
                               max_scale=np.max(self.arrXY),
                               colormap=dpg.mvPlotColormap_Jet)

        item_width = dpg.get_item_width("plotImage")
        item_height = dpg.get_item_height("plotImage")
        if (item_width is None) or (item_height is None):
            raise Exception("Window does not exist")
        dpg.set_item_height("Survey_Window", item_height + 150)
        # with dpg.plot(label="title", height=-1, width=-1, crosshairs=True, anti_aliased=False, delay_search=True,
        #               tag=f"_plot_with", parent = "Survey_Window"):
        #     dpg.add_plot_axis(dpg.mvXAxis)
        #     with dpg.plot_axis(dpg.mvYAxis):
        #         dpg.add_image_series("textureXY_tag", [0, 0], [800, 800])

    def run_gui(self) -> None:
        dpg.create_viewport(title="Dear PyGui Survey Interface", width=self.viewport_width, height=self.viewport_height)
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()

if __name__ == '__main__':
    dpg.create_context()
    gui = GUI_Survey_Interface()
    gui.GetWindowSize()
    gui.set_main_interface()
    gui.run_gui()
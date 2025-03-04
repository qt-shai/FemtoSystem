import dearpygui.dearpygui as dpg
import numpy as np
from Utils.Common import loadFromCSV
from Utils import open_file_dialog
import matplotlib.pyplot as plt
import os
from scipy import stats

class GUI_Survey_Interface:
    def __init__(self):
        self.total_selected_points = []
        self.endLoc = None
        self.startLoc = None
        self.file_path = "C://users//daniel//Work Folders//Documents//"
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
        self.selection_mode = True
        self.selected_points = []
        self.image_id = None

    def GetWindowSize(self) -> None:
        win_size = [self.win_w, self.win_h]
        self.win_pos = [100, 50]
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
        cmap = plt.get_cmap('jet')
        intensity = max(0, min(0.99999999, intensity))
        rgba_color = cmap(intensity)
        rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))

        return rgb_color

    def process_data(self):
        self.data = np.array(self.data)
        self.intensity_data = self.data[0:, 3].astype(float)
        self.im_arr_x = self.data[0:, 4].astype(float) / 1e6  # x data of the Smaract values from the csv
        self.im_arr_y = self.data[0:, 5].astype(float) / 1e6  # y data of the Smaract values from the csv
        self.im_arr_z = self.data[0:, 6].astype(float) / 1e6

        Nx = int(round((self.im_arr_x[-1] - self.im_arr_x[0]) / (self.im_arr_x[1] - self.im_arr_x[0])) + 1)
        Ny = int(round((self.im_arr_y[-1] - self.im_arr_y[0]) / (self.im_arr_y[Nx] - self.im_arr_y[0])) + 1)
        # Nx = len(np.unique(self.im_arr_x))
        # Ny = len(np.unique(self.im_arr_y))

        self.startLoc = [int(self.data[1, 4].astype(float) / 1e6), int(self.data[1, 5].astype(float) / 1e6),
                         int(self.data[1, 6].astype(float) / 1e6)]  # um
        self.endLoc = [int(self.data[-1, 4].astype(float) / 1e6), int(self.data[-1, 5].astype(float) / 1e6),
                       int(self.data[-1, 6].astype(float) / 1e6)]  # um

        #I feel like I only need one of those since z is constant
        self.scan_data = np.reshape(self.intensity_data[0:Nx*Ny], (Ny,Nx))
        self.im_arr_x = self.im_arr_x[0:Nx]
        self.im_arr_y = self.im_arr_y[0:Nx * Ny:Nx]
        print(self.scan_data.shape)
        self.arrXY = np.flipud(self.scan_data) #Needs to be reshaped to size (N_x,N_y,0). If the shape does not match Nx*Ny might fail
        #print(self.arrXY.shape)

        self.result_arrayXY = (self.arrXY * 255 / self.arrXY.max())
        self.result_arrayXY_ = []
        for i in range(self.arrXY.shape[0]):
            for j in range(self.arrXY.shape[1]):
                # Convert the value at (i, j) to an 8-bit unsigned int and normalize it
                res = self.intensity_to_rgb_heatmap(self.arrXY.astype(np.uint8)[i][j] / 255)
                self.result_arrayXY_.extend([res[0] / 255, res[1] / 255, res[2] / 255, res[3] / 255])


    def queryXY_callback(self, app_data):
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # If it's a point click, x_min ~ x_max and y_min ~ y_max.
            x_click = (a[0] + a[2]) / 2
            y_click = (a[1] + a[3]) / 2
            print(f"Clicked at: ({x_click}, {y_click})")
        if np.any(a):
            y_index = np.argmin(np.abs(self.im_arr_y - a[3]))
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
        with dpg.window(label="Survey Window", tag="Survey_Window", no_title_bar=True, width=-1, height = -1, pos=self.win_pos):
            with dpg.group(tag = "plot_group", horizontal=True):
                with dpg.group(tag = "general_group"):
                    with dpg.group(horizontal=True):
                        dpg.add_button(label="Load Data", callback=self.get_data_from_csv)
                        dpg.add_button(label="Show Image", callback=self.add_image_graphics)
                        dpg.add_button(label="Start Selecting Points", callback=self.select_points, tag = "btnSelect")
                        dpg.add_button(label="Return all points", callback=self.return_all_clicks)
                    dpg.add_group(tag = "heatmap_group", horizontal=True)

                with dpg.child_window(label="Options", width=200, height=self.plot_size[1],
                                      border=True, autosize_x=False, autosize_y=False):
                    dpg.add_text("Select an Option:")
                    dpg.add_button(label="Option 1", callback=None)
                    dpg.add_button(label="Option 2", callback=None)
                    dpg.add_button(label="Option 3", callback=None)

            dpg.add_texture_registry(show=False, tag="texture_reg")

        with dpg.file_dialog(directory_selector=False, show=False, callback=self.on_file_select_csv,
                             tag="csv_dialog",
                             modal=True, file_count=1,
                             default_path=self.file_path,
                             width=700, height=400):
            dpg.add_file_extension(".csv")


    def add_image_graphics(self):
        #You can put the height and width to regular numbers for now
        #The code this was taken from had a 3d array
        dpg.add_dynamic_texture(width=self.arrXY.shape[1], height=self.arrXY.shape[0], default_value=self.result_arrayXY_,
                                tag="textureXY_tag",
                                parent="texture_reg")

        dpg.add_plot(parent="heatmap_group", tag="plotImage", width=self.plot_size[0]*1.5, height=self.plot_size[1]*1.5, equal_aspects=True,
                     crosshairs=True,
                     query=True, callback=self.queryXY_callback)
        dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z=" + "{0:.2f}".format(self.im_arr_z[0]),
                          parent="plotImage",tag="plotImage_X")
        dpg.add_plot_axis(dpg.mvYAxis, label="y axis", parent="plotImage", tag="plotImage_Y")
        dpg.add_image_series("textureXY_tag", bounds_min=[self.startLoc[0], self.startLoc[1]],
                             bounds_max=[self.endLoc[0], self.endLoc[1]],
                             label="Survey data", parent="plotImage_Y", tag = "image_series")
        dpg.add_colormap_scale(show=True, parent="heatmap_group", tag="colormapXY", min_scale=np.min(self.arrXY),
                               max_scale=np.max(self.arrXY),
                               colormap=dpg.mvPlotColormap_Jet)

        item_width = dpg.get_item_width("plotImage")
        item_height = dpg.get_item_height("plotImage")
        if (item_width is None) or (item_height is None):
            raise Exception("Window does not exist")
        dpg.set_item_height("Survey_Window", item_height + 150)

    def configure_handler(self):
        with dpg.item_handler_registry(tag="handler_registry"):
            #dpg.add_item_clicked_handler(callback=self.item_clicked_callback)
            dpg.add_item_clicked_handler(callback=self.get_mouse_plot_coordinates)

    def select_points(self):
        if self.selection_mode:
            dpg.configure_item("btnSelect", label="Stop Selecting Points")
            self.selected_points = []
            dpg.bind_item_handler_registry("plotImage", "handler_registry")
        else:
            dpg.configure_item("btnSelect", label="Start Selecting Points")
            dpg.bind_item_handler_registry("plotImage", None)
            # For now, simply print the selected points.
            print("Recorded points:", self.selected_points)
            # Clear stored points.
            self.selected_points = []
        self.selection_mode = not self.selection_mode

    def item_clicked_callback(sender, app_data, user_data):
        # 'sender' will typically be the item handler registry, not the clicked item
        # 'app_data' will be the mouse button (e.g. 0 for left click, 1 for right click, etc.)

        clicked_item = dpg.last_item()
        print(f"Clicked item: {clicked_item}")

        # If you want detailed info about the clicked item, you can do:
        info = dpg.get_item_info(clicked_item)
        print("Item info:", info)

    def get_mouse_plot_coordinates(self, sender, app_data):
        """
        Callback to convert the mouse click's screen position into plot data coordinates.
        """
        # Get the current global mouse position (in screen coordinates)
        mouse_pos = dpg.get_mouse_pos(local = False)
        print(f"mouse_pos: {mouse_pos}")
        # Get the plot widget's screen position and size
        window_pos = [0,0]
        plot_min = dpg.get_item_rect_min("plotImage")
        plot_max = dpg.get_item_rect_max("plotImage")
        print(f"plot_min: {plot_min}")
        print(f"plot_max: {plot_max}")
        print(f"window_pos: {window_pos}")

        relative_plot_top_left = [plot_min[0] - window_pos[0], plot_min[1] - window_pos[1]]
        relative_plot_bottom_right = [plot_max[0] - window_pos[0], plot_max[1] - window_pos[1]]
        print(f"relative_plot_top_left: {relative_plot_top_left}")
        print(f"relative_plot_bottom_right: {relative_plot_bottom_right}")

        clicked_item = dpg.last_item()
        info = dpg.get_item_info(clicked_item)
        print("Item info:", info)

        if plot_min is None or plot_max is None:
            print("Plot bounds not available.")
            return

        # Compute the size of the plot area in pixels
        plot_width = plot_max[0] - plot_min[0]
        plot_height = plot_max[1] - plot_min[1]
        print(f"plot_width: {plot_width}")
        print(f"plot_height: {plot_height}")

        axis_x_lim = dpg.get_axis_limits("plotImage_X")
        axis_y_lim = dpg.get_axis_limits("plotImage_Y")
        print(f"axis_x_lim: {axis_x_lim}")
        print(f"axis_y_lim: {axis_y_lim}")

        # Determine the relative position of the mouse inside the plot area (0-1)
        rel_x = (mouse_pos[0]-69)/ (597-69) * (axis_x_lim[1] - axis_x_lim[0]) #Update this according to whiteboard
        rel_y = (1-(mouse_pos[1]-23)/ (565-23)) * (axis_y_lim[1] - axis_y_lim[0]) #Update this according to whiteboard

        print(f"self.startLoc: {self.startLoc}")
        print(f"self.endLoc: {self.endLoc}")

        # Use your plot's data bounds (startLoc and endLoc) to map the relative position to data coordinates.
        # Assuming startLoc[0] is the left bound (min x) and endLoc[0] is the right bound (max x)
        # and similarly for y.
        # data_x = axis_x_lim[0] + rel_x * (axis_x_lim[1] - axis_x_lim[0])
        # data_y = axis_y_lim[0] + (1 - rel_y) * (axis_y_lim[1] - axis_y_lim[0])
        data_x = axis_x_lim[0] + rel_x
        data_y = axis_y_lim[0] + rel_y

        print(f"Mouse clicked at data coordinates: ({data_x}, {data_y})")
        self.last_clicked = (data_x, data_y)
        self.total_selected_points.append(self.last_clicked)

    def return_all_clicks(self):
        print(self.total_selected_points)

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
    gui.configure_handler()
    gui.set_main_interface()
    gui.run_gui()
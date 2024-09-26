import dearpygui.dearpygui as dpg
import numpy as np

# Create sample 2D array
array_2d = np.random.rand(10, 10)

def draw_plot():
    dpg.delete_item("Plot")  # Clear the existing plot
    with dpg.plot("Plot", height=500, width=500):
        dpg.add_heat_series(array_2d, rows=10, cols=10, label="Heatmap")
        
dpg.add_window(label="2D Array Plot", tag= "win")
dpg.add_button(label="Plot", callback=draw_plot, parent="win")

dpg.create_context()
dpg.create_viewport(title='Dear PyGui', width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()

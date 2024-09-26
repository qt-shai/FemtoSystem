import os
import dearpygui.dearpygui as dpg

# cwd = os.getcwd()
# os.chdir("C://Users//amir//Desktop//")

dpg.create_context()

_width, _height, _channels, _data = dpg.load_image('C:\\Users\\amir\\Desktop\\Untitled.png') # 0: width, 1: height, 2: channels, 3: data

with dpg.texture_registry():
    dpg.add_static_texture(width=_width, height=_height, default_value=_data, tag="image_id")

with dpg.window(label="Tutorial", width=1200, height=1000):

    with dpg.drawlist(width=_width+400, height=_height+400):

        dpg.draw_image("image_id", (50, 50), (_width, _height), uv_min=(0, 0), uv_max=(1, 1))
        # dpg.draw_image("image_id", (400, 300), (600, 500), uv_min=(0, 0), uv_max=(0.5, 0.5))
        # dpg.draw_image("image_id", (0, 0), (300, 300), uv_min=(0, 0), uv_max=(2.5, 2.5))

dpg.create_viewport(title='Custom Title', width=1200, height=1000)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
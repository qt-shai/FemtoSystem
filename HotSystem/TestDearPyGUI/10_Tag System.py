import dearpygui.dearpygui as dpg

dpg.create_context()

unique_id = 0 # to be filled out later

def callback():
    # dpg.set_value(unique_id,10)
    print(dpg.get_value(unique_id))
    print(unique_id)

with dpg.window(label="Example"):
    dpg.add_button(label="Press me (print to output)", callback=callback)
    unique_id = dpg.add_input_int(label="Input")

dpg.create_viewport(title='Custom Title', width=600, height=200)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
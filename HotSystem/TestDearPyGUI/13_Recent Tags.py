import dearpygui.dearpygui as dpg

dpg.create_context()

with dpg.window(label="Example"):
    with dpg.group():
        dpg.add_button(label="View the Terminal for item tags")
        print(dpg.last_item())
        print(dpg.last_container())
        print(dpg.last_root())

dpg.create_viewport(title='Custom Title', width=600, height=200)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
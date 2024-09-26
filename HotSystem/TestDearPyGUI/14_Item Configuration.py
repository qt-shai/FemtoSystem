import dearpygui.dearpygui as dpg

dpg.create_context()

with dpg.window(width=500, height=300):
    dpg.add_button(enabled=True, label="Press me", tag="item")

    # at a later time, change the item's configuration
    dpg.configure_item("item", enabled=False, label="New Label")

dpg.create_viewport(title='Custom Title', width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
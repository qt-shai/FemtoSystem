import dearpygui.dearpygui as dpg

def callback_func(sender, app_data):
    print(app_data)
    # print(sender)
    # dpg.set_value(item="text_item",value="event was handled")
    # dpg.set_value("text_item", f"Mouse Button: {app_data[0]}, Down Time: {app_data[1]} seconds")

dpg.create_context()
dpg.configure_app(manual_callback_management=True)
dpg.add_handler_registry(tag="registryHandler")
dpg.add_mouse_click_handler(parent="registryHandler", callback=callback_func)
dpg.add_mouse_double_click_handler(parent="registryHandler",callback=callback_func)
dpg.add_mouse_down_handler(parent="registryHandler",callback=callback_func)
dpg.add_mouse_drag_handler(parent="registryHandler",callback=callback_func)
dpg.add_mouse_move_handler(parent="registryHandler",callback=callback_func)
dpg.add_mouse_release_handler(parent="registryHandler",callback=callback_func)
dpg.add_mouse_wheel_handler(parent="registryHandler",callback=callback_func)
dpg.add_key_down_handler(parent="registryHandler",callback=callback_func)
dpg.add_key_press_handler(parent="registryHandler",callback=callback_func)
dpg.add_key_release_handler(parent="registryHandler",callback=callback_func)

# with dpg.handler_registry():
#     dpg.add_mouse_down_handler(callback=callback_func)

with dpg.window(width=500, height=300):
    dpg.add_text("Press any mouse button", tag="text_item")

dpg.create_viewport(title='Custom Title', width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
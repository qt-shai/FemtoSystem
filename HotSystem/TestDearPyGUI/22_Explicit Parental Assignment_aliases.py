import dearpygui.dearpygui as dpg

dpg.create_context()

dpg.add_window(label="Main", tag="w")

dpg.add_menu_bar(parent="w", tag="mb")

dpg.add_menu(label="Themes", parent="mb", tag="themes")
dpg.add_menu_item(label="Dark", parent="themes")
dpg.add_menu_item(label="Light", parent="themes")

dpg.add_menu(label="Other Themes", parent="themes", tag="other_themes")
dpg.add_menu_item(label="Purple", parent="other_themes")
dpg.add_menu_item(label="Gold", parent="other_themes")
dpg.add_menu_item(label="Red", parent="other_themes")

dpg.add_menu(label="Tools", parent="mb", tag="tools")
dpg.add_menu_item(label="Show Logger", parent="tools")
dpg.add_menu_item(label="Show About", parent="tools")

dpg.add_menu(label="Oddities", parent="mb", tag="Oddities")
dpg.add_button(label="A Button", parent="Oddities")
dpg.add_simple_plot(label="A menu plot", default_value=(0.3, 0.9, 2.5, 8.9), height=80, parent="Oddities")

dpg.create_viewport(title='Custom Title', width=800, height=600)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
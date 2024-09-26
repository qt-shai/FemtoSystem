import dearpygui.dearpygui as dpg

dpg.create_context()

def delete_children():
    dpg.delete_item("window", children_only=True)

with dpg.window(label="Tutorial", pos=(200, 200), tag="window"):
    dpg.add_child(label="test",tag="test", width = 100, height = 100)
    dpg.add_button(label="Delete Children", callback=delete_children,parent="test")
    dpg.add_button(label="Button_1")
    dpg.add_button(label="Button_2")
    dpg.add_button(label="Button_3")

dpg.create_viewport(title='Custom Title', width=600, height=400)
dpg.setup_dearpygui()
dpg.show_viewport()
dpg.start_dearpygui()
dpg.destroy_context()
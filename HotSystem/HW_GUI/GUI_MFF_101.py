"""The code below incorporates the MFF_101 flippers into Zelux GUI as sliders.
Separate GUI also exists(commented out), however so far having it in zelux is preferred by users.
"""

from HW_GUI.GUI_motors import GUIMotor
import dearpygui.dearpygui as dpg
from Utils.Common import set_on_off_themes
import time

class GUI_MFF(GUIMotor):
    def __init__(self, serial_number, device) -> None:
        self.serial_number = serial_number
        self.dev = device
        self.unique_id = self._get_unique_id_from_device()
        self.prefix = "MFF_101"
        self.window_tag: str = f"{self.prefix}_Win_{self.unique_id}"
        self.button_tag = f"Toggle_Button_{self.unique_id}"
        self.toggle_state = self.dev.get_position()
        self.toggle_label = "Down" if self.toggle_state == 2 else "Up"
        self.create_gui_into_zelux()
        set_on_off_themes()

    def get_opposite_state(self, toggle_state):
        toggle_state = 2 if self.toggle_state == 1 else 1
        return toggle_state

    def get_toggle_label(self, toggle_state):
        self.toggle_label = "Down" if toggle_state == 2 else "Up"

    def get_toggle_theme(self,toggle_label):
        return "OnTheme" if self.toggle_state == 2 else "OffTheme"

    def create_gui_into_zelux(self):
        if dpg.does_item_exist("groupZeluxControls"):
            toggle_to_state = self.get_opposite_state(self.toggle_state)
            motor_str = "M"
            motor_label = motor_str + " " + self.serial_number[-2:]
            self.get_toggle_label(toggle_to_state)
            dpg.add_slider_int(label=motor_label,
                               tag=f"on_off_slider_{self.unique_id}", width=80,
                               default_value=self.toggle_state - 1, parent="groupZeluxControls",
                               min_value=0, max_value=1,
                               callback=self.on_off_slider_callback, indent=-1,
                               format=self.toggle_label)
            dpg.bind_item_theme(f"on_off_slider_{self.unique_id}", self.get_toggle_theme(self.toggle_label))
            dpg.set_exit_callback(self.on_exit_callback)
        else:
            print("Could not find groupZeluxControls in Zelux GUI")

    def move_flipper(self):
        try:
            self.dev.toggle()
        except Exception as e:
            print(e)

    def on_off_slider_callback(self, sender, app_data):
        # app_data is the new slider value (0 or 1)
        if app_data == 1:
            self.move_flipper()
            self.toggle_state = self.dev.get_position()
            if self.toggle_state == 2:
                dpg.configure_item(sender, format="Up")
            else:
                dpg.configure_item(sender, format="Down")
            dpg.bind_item_theme(sender, "OnTheme")
        else:
            self.move_flipper()

            self.toggle_state = self.dev.get_position()
            if self.toggle_state == 2:
                dpg.configure_item(sender, format="Up")
            else:
                dpg.configure_item(sender, format="Down")
            dpg.bind_item_theme(sender, "OffTheme")

    def on_exit_callback(self):
        print("Exiting GUI, disconnecting from motor.")
        self.dev.disconnect()



# class GUI_MFF(GUIMotor):
#     def __init__(self, serial_number, device) -> None:
#         self.serial_number = serial_number
#         self.dev = device
#         self.unique_id = self._get_unique_id_from_device()
#         self.prefix = "MFF_101"
#         self.window_tag: str = f"{self.prefix}_Win_{self.unique_id}"
#         self.button_tag = f"Toggle_Button_{self.unique_id}"
#         self.toggle_state = self.dev.get_position()
#         self.toggle_label = "Down" if self.toggle_state == 2 else "Up"
#         self.create_themes()
#         self.create_gui()
#
#     def toggle_callback(self, sender, app_data, user_data):
#         # Toggle the button state and update the label.
#         self.change_theme()
#         self.change_label()
#         new_position = self.dev.toggle()
#         self.toggle_state = new_position
#         self.toggle_state = 2 if self.toggle_state == 1 else 1
#         new_label = f"Toggle ({self.toggle_label})"
#         dpg.set_item_label(self.button_tag, new_label)
#         self.change_theme()
#         self.change_label()
#
#
#     def get_opposite_state(self, toggle_state):
#         toggle_state = 2 if self.toggle_state == 1 else 1
#         return toggle_state
#
#     def change_theme(self):
#         if self.toggle_state == 2:
#             dpg.bind_item_theme(self.button_tag, self.default_theme)
#         if self.toggle_state == 1:
#             dpg.bind_item_theme(self.button_tag, self.pressed_theme)
#
#     def change_label(self):
#         if self.toggle_state == 1:
#             self.toggle_label = "Up"
#         if self.toggle_state == 2:
#             self.toggle_label = "Down"
#
#     def on_exit_callback(self):
#         print("Exiting GUI, disconnecting from motor.")
#         self.dev.disconnect()
#
#     def create_themes(self):
#         # Theme for the default state.
#         with dpg.theme() as self.default_theme:
#             with dpg.theme_component(dpg.mvButton):
#                 dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 250), category=dpg.mvThemeCat_Core)
#         # Theme for the pressed state.
#         with dpg.theme() as self.pressed_theme:
#             with dpg.theme_component(dpg.mvButton):
#                 dpg.add_theme_color(dpg.mvThemeCol_Button, (250, 100, 100), category=dpg.mvThemeCat_Core)
#
#     def add_new_button(self, serial_number):
#         try:
#             self.serial_number = serial_number
#             self.unique_id = self._get_unique_id_from_device()
#             button_tag = f"button_{self.unique_id}"
#             dpg.add_text(f"Flipper_{self.unique_id}", parent = self.window_tag)
#             dpg.add_button(label=f"Toggle ({self.toggle_label})", tag=button_tag, width=100, height=50,
#                            callback=self.toggle_callback, parent = self.window_tag)
#         except Exception as e:
#             print(e)
#
#     def create_gui(self):
#         self.toggle_state = self.get_opposite_state(self.toggle_state)
#         with dpg.window(label="Filter Flipper Controller", tag=self.window_tag, width=300, height=150):
#             dpg.add_text("Flipper 1", parent = self.window_tag)
#             dpg.add_button(label=f"Toggle ({self.toggle_label})", tag=self.button_tag, width = 100, height = 50,
#                            callback=self.toggle_callback)
#             self.change_label()
#             self.change_theme()
#             dpg.set_exit_callback(self.on_exit_callback)
#
#
#

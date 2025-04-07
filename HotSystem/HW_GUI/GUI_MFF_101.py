from HW_GUI.GUI_motors import GUIMotor
from HW_wrapper.Wrapper_MFF_101 import FilterFlipperController
import dearpygui.dearpygui as dpg
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
        self.create_themes()
        self.create_gui()

    def toggle_callback(self, sender, app_data, user_data):
        # Toggle the button state and update the label.
        self.change_theme()
        self.change_label()
        new_position = self.dev.toggle()
        self.toggle_state = new_position
        self.toggle_state = 2 if self.toggle_state == 1 else 1
        new_label = f"Toggle ({self.toggle_label})"
        dpg.set_item_label(self.button_tag, new_label)
        self.change_theme()
        self.change_label()


    def get_opposite_state(self, toggle_state):
        toggle_state = 2 if self.toggle_state == 1 else 1
        return toggle_state

    def change_theme(self):
        if self.toggle_state == 2:
            dpg.bind_item_theme(self.button_tag, self.default_theme)
        if self.toggle_state == 1:
            dpg.bind_item_theme(self.button_tag, self.pressed_theme)

    def change_label(self):
        if self.toggle_state == 1:
            self.toggle_label = "Up"
        if self.toggle_state == 2:
            self.toggle_label = "Down"

    def on_exit_callback(self):
        print("Exiting GUI, disconnecting from motor.")
        self.dev.disconnect()

    def create_themes(self):
        # Theme for the default state.
        with dpg.theme() as self.default_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (100, 100, 250), category=dpg.mvThemeCat_Core)
        # Theme for the pressed state.
        with dpg.theme() as self.pressed_theme:
            with dpg.theme_component(dpg.mvButton):
                dpg.add_theme_color(dpg.mvThemeCol_Button, (250, 100, 100), category=dpg.mvThemeCat_Core)

    def add_new_button(self, serial_number):
        self.serial_number = serial_number
        self.unique_id = self._get_unique_id_from_device()
        dpg.add_text(f"Flipper_{self.unique_id}", parent = self.window_tag)
        dpg.add_button(label=f"Toggle ({self.toggle_label})", tag=self.button_tag, width=100, height=50,
                       callback=self.toggle_callback, parent = self.window_tag)

    def create_gui(self):
        self.toggle_state = self.get_opposite_state(self.toggle_state)
        with dpg.window(label="Filter Flipper Controller", tag=self.window_tag, width=300, height=150):
            dpg.add_text("Flipper 1", parent = self.window_tag)
            dpg.add_button(label=f"Toggle ({self.toggle_label})", tag=self.button_tag, width = 100, height = 50,
                           callback=self.toggle_callback)
            self.change_label()
            self.change_theme()
            dpg.set_exit_callback(self.on_exit_callback)



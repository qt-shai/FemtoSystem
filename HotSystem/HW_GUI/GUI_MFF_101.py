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

    def get_toggle_theme(self):
        return "OnTheme" if self.toggle_state == 2 else "OffTheme"

    def create_gui_into_zelux(self):
        if dpg.does_item_exist("groupZeluxControls"):
            toggle_to_state = self.get_opposite_state(self.toggle_state)
            motor_str = "M"
            motor_label = motor_str + self.serial_number[-2:]
            self.get_toggle_label(toggle_to_state)
            dpg.add_slider_int(label=motor_label,
                               tag=f"on_off_slider_{self.unique_id}", width=60,
                               default_value=self.toggle_state - 1, parent="groupZeluxControls",
                               min_value=0, max_value=1,
                               callback=self.on_off_slider_callback, indent=-1,
                               format=self.toggle_label)
            dpg.bind_item_theme(f"on_off_slider_{self.unique_id}", self.get_toggle_theme())
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
        def try_update_toggle():
            try:
                self.move_flipper()
                self.toggle_state = self.dev.get_position()
                dpg.configure_item(sender, format="Up" if self.toggle_state == 2 else "Down")
                dpg.bind_item_theme(sender, self.get_toggle_theme())
                return True
            except Exception as e:
                print(f"First attempt failed: {e}")
                return False

        success = try_update_toggle()
        if not success:
            time.sleep(0.3)
            try:
                try_update_toggle()
            except Exception as e:
                print(f"Retry failed: {e}")

        dpg.set_value(f"on_off_slider_{self.unique_id}", app_data)

    def on_exit_callback(self):
        print("Exiting GUI, disconnecting from motor.")
        self.dev.disconnect()


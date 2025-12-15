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

        # slider value/state convention in your code:
        # dev.get_position(): 1/2
        # you *intend* 2 = Down, 1 = Up (based on your __init__ label)

    STATUS_BY_M = {
        "M32": {"Up": "proem-off", "Down": "proem-on"},
        "M55": {"Up": "blocker-off", "Down": "blocker-on"},
        "M48": {"Up": "spectrometer", "Down": "apds"},
    }

    def _motor_label(self) -> str:
        return "M" + str(self.serial_number)[-2:]

    def _state_to_updown(self, pos: int) -> str:
        # pos is dev.get_position() -> 1 or 2
        return "Up" if pos == 2 else "Down"

    def update_status_from_state(self):
        m = self._motor_label()
        updown = self._state_to_updown(self.toggle_state)
        txt = self.STATUS_BY_M.get(m, {}).get(updown, "")
        self.set_status_text(txt)

    def get_opposite_state(self, toggle_state):
        toggle_state = 2 if self.toggle_state == 1 else 1
        return toggle_state

    def get_toggle_label(self, toggle_state):
        self.toggle_label = "Down" if toggle_state == 2 else "Up"

    def get_toggle_theme(self):
        return "OnTheme" if self.toggle_state == 2 else "OffTheme"

    def create_gui_into_zelux(self):
        if dpg.does_item_exist("groupZeluxControls"):

            motor_label = self._motor_label()

            # make a small vertical block so text is *below* the slider
            block_tag = f"mff_block_{self.unique_id}"
            if not dpg.does_item_exist(block_tag):
                dpg.add_group(tag=block_tag, parent="groupZeluxControls", horizontal=False)

            dpg.add_slider_int(
                label=motor_label,
                tag=f"on_off_slider_{self.unique_id}",
                width=60,
                default_value=self.toggle_state - 1,
                parent=block_tag,
                min_value=0, max_value=1,
                callback=self.on_off_slider_callback,
                indent=-1,
                format=self._state_to_updown(self.toggle_state),
            )
            dpg.bind_item_theme(f"on_off_slider_{self.unique_id}", self.get_toggle_theme())

            # text widget below slider
            self.text_tag = f"mff_text_{self.unique_id}"
            if not dpg.does_item_exist(self.text_tag):
                dpg.add_text("", tag=self.text_tag, parent=block_tag)

            self.update_status_from_state()

            dpg.set_exit_callback(self.on_exit_callback)
        else:
            print("Could not find groupZeluxControls in Zelux GUI")

    def set_status_text(self, text: str):
        if hasattr(self, "text_tag") and dpg.does_item_exist(self.text_tag):
            dpg.configure_item(self.text_tag, show=True)
            dpg.set_value(self.text_tag, text)

    def move_flipper(self):
        try:
            self.dev.toggle()
        except Exception as e:
            print(e)

    def on_off_slider_callback(self, sender, app_data):
        def try_update_toggle():
            try:
                self.move_flipper()
                self.toggle_state = self.dev.get_position()

                # IMPORTANT: keep format consistent with your convention
                dpg.configure_item(sender, format=self._state_to_updown(self.toggle_state))
                dpg.bind_item_theme(sender, self.get_toggle_theme())

                self.update_status_from_state()
                return True
            except Exception as e:
                print(f"First attempt failed: {e}")
                return False

        success = try_update_toggle()
        if not success:
            time.sleep(0.3)
            try_update_toggle()

        dpg.set_value(f"on_off_slider_{self.unique_id}", app_data)

    def on_exit_callback(self):
        print("Exiting GUI, disconnecting from motor.")
        self.dev.disconnect()


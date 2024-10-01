import dearpygui.dearpygui as dpg
from Common import DpgThemes
from HW_wrapper.abstract_motor import Motor
from SystemConfig import Instruments, load_instrument_images


class GUIMotor:
    def __init__(self, motor: Motor, instrument:Instruments, simulation: bool = False) -> None:
        """
        Generalized GUI class for motor control.

        :param motor: The type of motor to control (e.g., "pico_motor", "smaract_motor, atto_motor").
        :param simulation: Flag to indicate if the simulation mode is enabled.
        """
        self.is_collapsed:bool = False
        load_instrument_images()
        self.dev = motor  # Dynamically assign the motor device based on the motor_type
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()  # Automatically infer the unique identifier from the device
        self.instrument = instrument
        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        child_width = 100
        self.window_tag = f"MotorWin_{self.unique_id}"
        with dpg.window(tag=self.window_tag, label=f"{self.instrument.value}",
                        no_title_bar=False, height=200, width=1800, pos=[0, 0], collapsed=False):
            with dpg.group(horizontal=True):
                self.create_instrument_image()
                self.create_position_controls(red_button_theme)
                self.create_movement_controls(red_button_theme)
                self.create_reference_controls(child_width)
                self.create_zero_controls(child_width)
                self.create_absolute_position_controls(child_width)
                self.create_home_controls(child_width)
                self.create_status_display(child_width)
                # self.toggle_gui_collapse()

        if not simulation:
            self.connect()

    def _get_unique_id_from_device(self) -> str:
        """
        Generate a unique identifier for the GUI instance based on the motor device properties.

        :return: A string that uniquely identifies this motor device.
        """
        # Example: Use the device's name or serial number or any other unique attribute
        if hasattr(self.dev, 'serial_number') and self.dev.serial_number is not None:
            return self.dev.serial_number
        elif hasattr(self.dev, 'name') and self.dev.name is not None:
            return self.dev.name
        else:
            # Fallback: Use the memory address of the device instance as a unique identifier
            return str(id(self.dev))

    def create_instrument_image(self):
        with dpg.group(horizontal=False, tag=f"column_0_{self.unique_id}"):
            dpg.add_image_button(
                f"{self.instrument.value}_texture", width=80, height=80,
                callback=self.toggle_gui_collapse,
                user_data=None
            )

    def create_position_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_1_{self.unique_id}"):
            dpg.add_text("Position")
            for ch in self.dev.channels:
                dpg.add_text(f"Ch{ch}", tag=f"MotorCh{ch}_{self.unique_id}")
            dpg.add_button(label="Stop all axes", callback=self.btn_stop_all_axes)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_movement_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_2_{self.unique_id}"):
            dpg.add_text("Coarse (µm)")
            for ch in self.dev.channels:
                with dpg.group(horizontal=True):
                    dpg.add_button(label="-", width=25, callback=self.btn_move_negative_coarse, user_data=ch)
                    dpg.bind_item_theme(dpg.last_item(), theme)
                    dpg.add_button(label="+", width=25, callback=self.btn_move_positive_coarse, user_data=ch)
                    dpg.bind_item_theme(dpg.last_item(), theme)
                    dpg.add_input_float(label="", default_value=100, tag=f"ch{ch}_coarse_{self.unique_id}",
                                        indent=-1,
                                        format='%.1f', width=200, step=10, step_fast=100)
                    dpg.add_text("µm", indent=-10)

        with dpg.group(horizontal=False, tag=f"column_3_{self.unique_id}"):
            dpg.add_text("Fine (nm)")
            for ch in self.dev.channels:
                with dpg.group(horizontal=True):
                    dpg.add_button(label="-", width=25, callback=self.btn_move_negative_fine, user_data=ch)
                    dpg.bind_item_theme(dpg.last_item(), theme)
                    dpg.add_button(label="+", width=25, callback=self.btn_move_positive_fine, user_data=ch)
                    dpg.bind_item_theme(dpg.last_item(), theme)
                    dpg.add_input_float(label="", default_value=1000, tag=f"ch{ch}_fine_{self.unique_id}",
                                        indent=-1,
                                        format='%.1f', width=200, step=100, step_fast=1000)
                    dpg.add_text("nm", indent=-10)

    def create_reference_controls(self, width):
        with dpg.group(horizontal=False, tag=f"column_4_{self.unique_id}", width=width):
            dpg.add_text("Go to Ref.")
            for ch in self.dev.channels:
                dpg.add_button(label=f"Ref. {ch}")

    def create_zero_controls(self, width):
        with dpg.group(horizontal=False, tag=f"column_5_{self.unique_id}", width=width):
            dpg.add_text("Zero")
            for ch in self.dev.channels:
                dpg.add_button(label=f"Zero {ch}", callback=self.btn_set_zero, user_data=ch)

    def create_absolute_position_controls(self, width):
        with dpg.group(horizontal=False, tag=f"column_6_{self.unique_id}", width=width * 2):
            dpg.add_text("Move Abs. Position (µm)")
            for ch in self.dev.channels:
                with dpg.group(horizontal=True):
                    dpg.add_input_float(label="", default_value=0, tag=f"ch{ch}_ABS_{self.unique_id}", indent=-1,
                                        format='%.1f', width=60, step=100, step_fast=1000)
                    dpg.add_button(label="GO", callback=self.btn_move_absolute, user_data=ch)

    def create_home_controls(self, width):
        with dpg.group(horizontal=False, tag=f"column_7_{self.unique_id}", width=width):
            dpg.add_text("Home")
            for ch in self.dev.channels:
                dpg.add_button(label=f"Home {ch}", callback=self.btn_move_to_home, user_data=ch)

    def create_status_display(self, width):
        with dpg.group(horizontal=False, tag=f"column_8_{self.unique_id}", width=width):
            dpg.add_text("Status")
            for ch in self.dev.channels:
                dpg.add_combo(["idle",""], tag=f"MotorStatus{ch}_{self.unique_id}")

    def toggle_gui_collapse(self):
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column in range(1,9):
                dpg.show_item(f"column_{column}_{self.unique_id}")
            dpg.set_item_width(self.window_tag,1800)
            dpg.set_item_height(self.window_tag, 200)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for column in range(1, 9):
                dpg.hide_item(f"column_{column}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    def btn_stop_all_axes(self):
        self.dev.stop_all_axes()

    def btn_move_to_home(self, sender, app_data, ch):
        self.dev.move_to_home(ch)

    def btn_move_absolute(self, sender, app_data, ch):
        position = int(dpg.get_value(f"ch{ch}_ABS_{self.unique_id}") * self.dev.StepsIn1mm / 1e6)
        self.dev.move_absolute(ch, position)

    def btn_move_negative_coarse(self, sender, app_data, ch):
        step = int(-dpg.get_value(f"ch{ch}_coarse_{self.unique_id}") * self.dev.StepsIn1mm / 1e3)
        self.dev.move_relative(ch, step)

    def btn_move_positive_coarse(self, sender, app_data, ch):
        step = int(dpg.get_value(f"ch{ch}_coarse_{self.unique_id}") * self.dev.StepsIn1mm / 1e3)
        self.dev.move_relative(ch, step)

    def btn_move_negative_fine(self, sender, app_data, ch):
        step = int(-dpg.get_value(f"ch{ch}_fine_{self.unique_id}") * self.dev.StepsIn1mm/1e6)
        self.dev.move_relative(ch, step)

    def btn_move_positive_fine(self, sender, app_data, ch):
        step = int(dpg.get_value(f"ch{ch}_fine_{self.unique_id}") * self.dev.StepsIn1mm/1e6)
        self.dev.move_relative(ch, step)

    def btn_set_zero(self, sender, app_data, ch):
        self.dev.set_zero_position(ch)

    def connect(self):
        self.dev.connect()
        print("Connecting")
        if self.dev.is_connected:
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} connected")

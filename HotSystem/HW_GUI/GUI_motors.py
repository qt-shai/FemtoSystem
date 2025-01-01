from enum import Enum, auto
from typing import Optional, List, Callable, Dict

import dearpygui.dearpygui as dpg
from Common import DpgThemes, KeyboardKeys
from HW_wrapper.HW_devices import HW_devices
from HW_wrapper.abstract_motor import Motor
from SystemConfig import Instruments, load_instrument_images

class GUIMotorConfig(Enum):
    CREATE_INSTRUMENT_IMAGE = auto()
    CREATE_POSITION_CONTROLS = auto()
    CREATE_MOVEMENT_CONTROLS = auto()
    CREATE_REFERENCE_CONTROLS = auto()
    CREATE_ZERO_CONTROLS = auto()
    CREATE_ABSOLUTE_POSITION_CONTROLS = auto()
    CREATE_HOME_CONTROLS = auto()
    CREATE_STATUS_DISPLAY = auto()

class GUIMotor:
    def __init__(self, motor: Motor, instrument: Instruments, simulation: bool = False,
                 config_options: Optional[List[GUIMotorConfig]] = None) -> None:
        """
        Generalized GUI class for motor control.

        :param motor: The motor instance to control.
        :param instrument: The instrument associated with the motor.
        :param simulation: Flag to indicate if the simulation mode is enabled.
        :param config_options: Select GUI elements to be loaded.
        """
        if config_options is None:
            config_options = list(GUIMotorConfig)

        self.active_key: Optional[KeyboardKeys] = KeyboardKeys.CTRL_KEY
        self.is_collapsed: bool = False
        self.is_active_motor_keyboard: bool = False
        load_instrument_images()
        self.dev = motor  # The motor device instance
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()  # Automatically infer the unique identifier from the device
        self.instrument = instrument
        red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))
        child_width = 100
        self.window_tag = f"MotorWin_{self.unique_id}"
        self.window_label = f"{self.instrument.value}" + "(simulation)" if simulation else f"({motor.serial_number})"
        self.hw_devices = HW_devices(simulation=simulation)

        with dpg.window(tag=self.window_tag, label=f"{self.window_label}",
                        no_title_bar=False, height=270, width=1800, pos=[0, 0], collapsed=False):
            with dpg.group(horizontal=True):
                if GUIMotorConfig.CREATE_INSTRUMENT_IMAGE in config_options:
                    self.create_instrument_image()

                if GUIMotorConfig.CREATE_POSITION_CONTROLS in config_options:
                    self.create_position_controls(red_button_theme)

                if GUIMotorConfig.CREATE_MOVEMENT_CONTROLS in config_options:
                    self.create_movement_controls(red_button_theme)

                if GUIMotorConfig.CREATE_REFERENCE_CONTROLS in config_options:
                    self.create_reference_controls(child_width)

                if GUIMotorConfig.CREATE_ZERO_CONTROLS in config_options:
                    self.create_zero_controls(child_width)

                if GUIMotorConfig.CREATE_ABSOLUTE_POSITION_CONTROLS in config_options:
                    self.create_absolute_position_controls(child_width)

                if GUIMotorConfig.CREATE_HOME_CONTROLS in config_options:
                    self.create_home_controls(child_width)

                if GUIMotorConfig.CREATE_STATUS_DISPLAY in config_options:
                    self.create_status_display(child_width)

        # Subscribe to motor position updates
        for ch in self.dev.channels:
            self.dev.axes_positions[ch].add_observer(lambda value, cha=ch: self.on_position_update(cha, value))

        if not simulation:
            self.connect()
        else:
            for ch in self.dev.channels:
                print(f"setting {self} positions channle {ch} to 0")
                self.dev.set_position(ch,0)

        self.dev.start_position_updates()


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
                dpg.add_combo(["idle", ""], tag=f"MotorStatus{ch}_{self.unique_id}")

    def toggle_gui_collapse(self):
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column in range(1, 9):
                dpg.show_item(f"column_{column}_{self.unique_id}")
            dpg.set_item_width(self.window_tag, 1800)
            dpg.set_item_height(self.window_tag, 270)
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
        position = dpg.get_value(f"ch{ch}_ABS_{self.unique_id}")
        self.dev.MoveABSOLUTE(ch, position)

    def btn_move_negative_coarse(self, sender, app_data, ch):
        step = -dpg.get_value(f"ch{ch}_coarse_{self.unique_id}")
        self.dev.move_relative(ch, step)

    def btn_move_positive_coarse(self, sender, app_data, ch):
        step = dpg.get_value(f"ch{ch}_coarse_{self.unique_id}")
        self.dev.move_relative(ch, step)

    def btn_move_negative_fine(self, sender, app_data, ch):
        step = -dpg.get_value(f"ch{ch}_fine_{self.unique_id}") * 1e-3
        self.dev.move_relative(ch, step)

    def btn_move_positive_fine(self, sender, app_data, ch):
        step = dpg.get_value(f"ch{ch}_fine_{self.unique_id}") * 1e-3
        self.dev.move_relative(ch, step)

    def btn_set_zero(self, sender, app_data, ch):
        self.dev.set_zero_position(ch)

    def connect(self):
        self.dev.connect()
        print("Connecting")
        if self.dev.is_connected:
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} connected")

    # def on_position_update(self, channel: int, position: float) -> None:
    #     """
    #     Callback method that is called when the motor's position is updated.
    #
    #     :param channel: The channel number.
    #     :param position: The new position.
    #     """
    #     # Update the GUI element displaying the position
    #     position_text = f"Ch{channel}: {position:.2f} {self.dev.get_position_unit(channel)}"
    #     dpg.set_value(f"MotorCh{channel}_{self.unique_id}", position_text)

    def on_position_update(self, channel: int, position: float) -> None:
        """
        Callback method that is called when the motor's position is updated.

        :param channel: The channel number.
        :param position: The new position.
        """
        position_text = f"Ch{channel}: {position:.3f} {self.dev.get_position_unit(channel)}"
        dpg.set_value(f"MotorCh{channel}_{self.unique_id}", position_text)
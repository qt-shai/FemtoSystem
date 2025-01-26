from HW_GUI.GUI_motors import GUIMotor, GUIMotorConfig
from HW_wrapper.Attocube import Anc300Wrapper, ANC300Modes
from SystemConfig import Instruments
import dearpygui.dearpygui as dpg


class GUIAttoScanner(GUIMotor):
    """
    Enhanced GUI class for the AttoScanner device, adding offset voltage controls.
    """
    def __init__(self, motor: Anc300Wrapper, instrument: Instruments, simulation: bool = False) -> None:
        """
        Initialize the enhanced atto scanner GUI.

        :param motor: The atto_scanner motor instance.
        :param instrument: The associated instrument.
        :param simulation: Simulation mode flag.
        """
        config_options = [GUIMotorConfig.CREATE_INSTRUMENT_IMAGE,
                          GUIMotorConfig.CREATE_ABSOLUTE_POSITION_CONTROLS,
                          GUIMotorConfig.CREATE_MOVEMENT_CONTROLS,
                          GUIMotorConfig.CREATE_POSITION_CONTROLS]

        super().__init__(motor=motor, instrument=instrument, simulation=simulation, config_options= config_options)
        self.dev: Anc300Wrapper = motor
        with dpg.group(horizontal=True, parent=f"{self.window_tag}"):
            self._add_mode_controls()

    def btn_set_mode(self, sender, app_data, ch: int) -> None:
        """
        Set the mode for a given channel from the GUI input.

        :param ch: The channel number.
        """
        mode_value = dpg.get_value(f"ch{ch}_mode_{self.unique_id}")
        try:
            mode = ANC300Modes(mode_value)
            self.dev.set_mode(ch, mode)
        except ValueError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Error: {e}")

    def btn_get_mode(self, sender, app_data, ch: int) -> None:
        """
        Get and display the mode for a given channel.

        :param ch: The channel number.
        """
        try:
            mode = self.dev.get_mode(ch)
            dpg.set_value(f"ch{ch}_mode_{self.unique_id}", mode.value)
        except Exception as e:
            print(f"Error in btn_get_mode click: {e}")

    def _add_mode_controls(self) -> None:
        """
        Add mode controls to the GUI.
        """
        with dpg.group(horizontal=False, tag=f"mode_controls_{self.unique_id}", width=150):
            dpg.add_text("Channel Modes")
            for ch in self.dev.channels:
                with dpg.group(horizontal=True):
                    dpg.add_combo(
                        items=[mode.value for mode in ANC300Modes],
                        default_value=ANC300Modes.GND.value,
                        tag=f"ch{ch}_mode_{self.unique_id}",
                        width=150,
                    )
                    dpg.add_button(label="Set", callback=self.btn_set_mode, user_data=ch, width=60)
                    dpg.add_button(label="Get", callback=self.btn_get_mode, user_data=ch, width=60)

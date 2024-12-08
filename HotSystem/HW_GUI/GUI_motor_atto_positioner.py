from HW_GUI.GUI_motors import GUIMotor
from HW_wrapper import Motor, AttoDry800
from SystemConfig import Instruments
import dearpygui.dearpygui as dpg


class GUIMotorAttoPositioner(GUIMotor):
    def __init__(self, motor: AttoDry800, instrument: Instruments, simulation: bool = False) -> None:
        """
        Extended GUI class for motor control with velocity, single step, fixed voltage, and actuator voltage control.

        :param motor: The motor instance to control.
        :param instrument: The instrument associated with the motor.
        :param simulation: Flag to indicate if the simulation mode is enabled.
        """
        super().__init__(motor, instrument, simulation)
        self.dev = motor
        with dpg.group(horizontal=True, parent=f"{self.window_tag}"):
            self.create_velocity_control()
            self.create_single_step_controls()
            self.create_fix_voltage_controls()
            self.create_actuator_voltage_controls()

        dpg.set_item_height(self.window_tag, 350)

    def create_velocity_control(self):
        """Add controls for velocity adjustment."""
        with dpg.group(horizontal=False, tag=f"velocity_control_{self.unique_id}", width=200):
            dpg.add_text("Velocity Control (Hz)")
            for ch in self.dev.channels:
                dpg.add_input_float(
                    label=f"Channel {ch}", default_value=100,
                    callback=self.set_velocity, tag=f"velocity_ch{ch}_{self.unique_id}",
                    format="%.1f", step=1, step_fast=10, user_data=ch
                )

    def set_velocity(self, sender, app_data,ch):
        """Callback to adjust the motor's velocity by changing polling rate."""
        new_rate = dpg.get_value(f"velocity_ch{ch}_{self.unique_id}")
        if new_rate > 0:
            self.dev.set_control_frequency(ch,new_rate*1000)
            print(f"Velocity of channel {ch} updated to {new_rate} Hz")

    def create_single_step_controls(self):
        """Add controls for single-step movement."""
        with dpg.group(horizontal=False, tag=f"single_step_controls_{self.unique_id}", width=200):
            dpg.add_text("Single Step Movement")
            for ch in self.dev.channels:
                with dpg.group(horizontal=True):
                    dpg.add_button(label=f"Step Forward {ch}", callback=self.btn_step_forward, user_data=ch)
                    dpg.add_button(label=f"Step Backward {ch}", callback=self.btn_step_backward, user_data=ch)

    def btn_step_forward(self, sender, app_data, ch):
        """Move the specified channel one step forward."""
        self.dev.move_one_step(ch, backward=False)

    def btn_step_backward(self, sender, app_data, ch):
        """Move the specified channel one step backward."""
        self.dev.move_one_step(ch, backward=True)

    def create_fix_voltage_controls(self):
        """Add controls for fixed voltage."""
        with dpg.group(horizontal=False, tag=f"fix_voltage_controls_{self.unique_id}", width=200):
            dpg.add_text("Fixed DC Voltage (mV)")
            for ch in self.dev.channels:
                dpg.add_input_int(
                    label=f"Ch{ch}",
                    default_value=int(self.dev.get_control_fix_output_voltage(ch)),
                    callback=self.set_fix_voltage,
                    tag=f"fix_voltage_ch{ch}_{self.unique_id}",
                    user_data=ch
                )


    def create_actuator_voltage_controls(self):
        """Add controls for actuator voltage."""
        with dpg.group(horizontal=False, tag=f"actuator_voltage_controls_{self.unique_id}", width=200):
            dpg.add_text("Actuator Voltage(mV)")
            for ch in self.dev.channels:
                dpg.add_input_int(
                    label=f"Ch{ch}",
                    default_value=int(self.dev.get_actuator_voltage(ch)),
                    callback=self.set_actuator_voltage,
                    tag=f"actuator_voltage_ch{ch}_{self.unique_id}",
                    user_data=ch
                )

    def set_fix_voltage(self, sender, app_data, ch):
        """Set the fixed output voltage for a specific channel."""
        voltage = dpg.get_value(f"fix_voltage_ch{ch}_{self.unique_id}")
        self.dev.set_control_fix_output_voltage(ch, voltage)
        print(f"Fixed voltage for channel {ch} set to {voltage} mV.")

    def set_actuator_voltage(self, sender, app_data, ch):
        """Set the actuator voltage for a specific channel."""
        voltage = dpg.get_value(f"actuator_voltage_ch{ch}_{self.unique_id}")
        if 0 <= voltage <= 60000:
            self.dev.set_actuator_voltage(ch, voltage)
            print(f"Actuator voltage for channel {ch} set to {voltage} mV.")
        else:
            print(f"Voltage {voltage} mV is out of range (0-60000 mV).")

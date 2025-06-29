from HW_wrapper.Wrapper_KDC101 import MotorStage
from HW_wrapper.Wrapper_Pharos import PharosLaserAPI
import dearpygui.dearpygui as dpg
import numpy as np

class FemtoPowerCalculator:
    def __init__(self, motor_stage):
        self.motor = motor_stage  # must support get_current_position()
        self.pharos = PharosLaserAPI(host="192.168.101.58")      # must support getBasicTargetAttenuatorPercentage()

        self.prefix = "Femto"
        self.unique_id = "PowerCalc"

        self.window_tag = f"{self.prefix}_Window_{self.unique_id}"
        self.combo_tag = f"{self.prefix}_Mode_{self.unique_id}"
        self.angle_tag = f"{self.prefix}_HWPAngle_{self.unique_id}"
        self.power_tag = f"{self.prefix}_LaserPower_{self.unique_id}"
        self.energy_tag = f"{self.prefix}_PulseEnergy_{self.unique_id}"

        self.create_gui()

    def create_gui(self):
        with dpg.window(label="Femto Power Calculations", tag=self.window_tag, width=400, height=200):
            dpg.add_combo(items=["Default", "50um pinhole"],
                          default_value="50um pinhole",
                          tag=self.combo_tag,
                          label="Mode")
            dpg.add_button(label="Calculate", callback=self.calculate_button)
            with dpg.group(horizontal=True):
                dpg.add_text("HWP [°]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.angle_tag)
            with dpg.group(horizontal=True):
                dpg.add_text("P [µW]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.power_tag)
            with dpg.group(horizontal=True):
                dpg.add_text("E [nJ]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.energy_tag)

    def calculate_laser_pulse(self, HWP_deg: float, Att_percent: float, mode: str, rep_rate: float = 50e3) -> tuple[float, float]:
        # Choose polynomial based on mode
        if mode == "50um pinhole":
            A2, A1, A0 = 0.12, 12.09, -40.27
        else:
            A2, A1, A0 = 13.86, 16.70, 2.42

        P_att = A2 * Att_percent ** 2 + A1 * Att_percent + A0
        theta0 = -7.2
        modulation = np.sin(np.radians(2 * (HWP_deg - theta0))) ** 2 / np.sin(np.radians(2 * (40 - theta0))) ** 2
        P_uW = P_att * modulation
        pulse_energy_nJ = P_uW * 1e-6 / rep_rate * 1e9
        return P_uW, pulse_energy_nJ

    def calculate_button(self):
        try:
            HWP_deg = float(self.motor.dev.get_current_position())
            Att_percent = float(self.pharos.getBasicTargetAttenuatorPercentage())
            mode = dpg.get_value(self.combo_tag)

            P_uW, pulse_energy_nJ = self.calculate_laser_pulse(HWP_deg, Att_percent, mode)

            dpg.set_value(self.angle_tag, f"{HWP_deg:.3f}")
            dpg.set_value(self.power_tag, f"{P_uW:.1f}")
            dpg.set_value(self.energy_tag, f"{pulse_energy_nJ:.1f}")

            print(f"Mode: {mode} | Angle: {HWP_deg:.3f}°, Att: {Att_percent:.1f}%, P: {P_uW:.1f} µW, E: {pulse_energy_nJ:.1f} nJ")

        except Exception as e:
            print(f"Error in calculation: {e}")
            dpg.set_value(self.angle_tag, "Error")
            dpg.set_value(self.power_tag, "Error")
            dpg.set_value(self.energy_tag, "Error")

if __name__ == "__main__":
    motor = MotorStage(serial_number="YOUR_SERIAL")  # adjust as needed
    pharos = PharosLaserAPI(host="192.168.101.58")

    gui = FemtoPowerCalculator(motor, pharos)

    dpg.create_context()
    dpg.create_viewport(title='Femto Power Calc')
    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

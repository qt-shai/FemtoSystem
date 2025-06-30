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
        self.att_tag = f"{self.prefix}_Att_{self.unique_id}"
        self.power_tag = f"{self.prefix}_LaserPower_{self.unique_id}"
        self.energy_tag = f"{self.prefix}_PulseEnergy_{self.unique_id}"

        self.future_input_tag = f"{self.prefix}_FutureInput_{self.unique_id}"
        self.future_output_group = f"{self.prefix}_FutureOutputGroup_{self.unique_id}"

        self.create_gui()

    def create_gui(self):
        with dpg.window(label="Femto Power Calculations", tag=self.window_tag, width=400, height=200):
            dpg.add_combo(items=["Default", "50um pinhole"],
                          default_value="Default",
                          tag=self.combo_tag,
                          label="Mode")
            dpg.add_button(label="Calculate", callback=self.calculate_button)
            with dpg.group(horizontal=True):
                dpg.add_text("HWP [°]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.angle_tag)
            with dpg.group(horizontal=True):
                dpg.add_text("Att [%]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.att_tag)
            with dpg.group(horizontal=True):
                dpg.add_text("P [µW]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.power_tag)
            with dpg.group(horizontal=True):
                dpg.add_text("E [nJ]:", color=(0, 255, 0))
                dpg.add_text("N/A", tag=self.energy_tag)

            dpg.add_input_text(label="Future angles (start:step:end)",
                               tag=self.future_input_tag,
                               hint="e.g., 5:5:20,10%",
                               default_value="1:1:15,10%",
                               on_enter=True,
                               callback=self.calculate_future)
            dpg.add_separator()
            dpg.add_text("Future Results:", color=(255, 255, 0))
            with dpg.group(tag=self.future_output_group):
                pass  # This will hold the dynamic output rows

    def calculate_laser_pulse(self, HWP_deg: float, Att_percent: float, mode: str, rep_rate: float = 50e3) -> tuple[float, float]:
        # Choose polynomial based on mode
        if mode == "50um pinhole":
            A3, A2, A1, A0 = -0.0055, 0.4814, 5.6756, -16.8214
            P_att = A3 * Att_percent ** 3 + A2 * Att_percent ** 2 + A1 * Att_percent + A0
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

            dpg.set_value(self.angle_tag, f"{HWP_deg:.1f}")
            dpg.set_value(self.att_tag, f"{Att_percent:.2f}")
            dpg.set_value(self.power_tag, f"{P_uW:.1f}")
            dpg.set_value(self.energy_tag, f"{pulse_energy_nJ:.1f}")

            print(f"Mode: {mode} | Angle: {HWP_deg:.3f}°, Att: {Att_percent:.1f}%, P: {P_uW:.1f} µW, E: {pulse_energy_nJ:.1f} nJ")

        except Exception as e:
            print(f"Error in calculation: {e}")
            dpg.set_value(self.angle_tag, "Error")
            dpg.set_value(self.power_tag, "Error")
            dpg.set_value(self.energy_tag, "Error")

    def calculate_future(self, sender, app_data, user_data):
        try:
            input_str = dpg.get_value(self.future_input_tag)

            # Split by comma if user added Att
            if "," in input_str:
                range_part, att_part = input_str.split(",")
                range_part = range_part.strip()
                att_part = att_part.strip().replace("%", "")
                override_att = float(att_part)
            else:
                range_part = input_str.strip()
                override_att = None

            parts = [float(x.strip()) for x in range_part.split(":")]
            if len(parts) != 3:
                raise ValueError("Input must be start:step:end")

            start, step, end = parts
            angles = np.arange(start, end + step, step)

            # Use override if provided, else read Pharos
            if override_att is not None:
                Att_percent = override_att
            else:
                Att_percent = float(self.pharos.getBasicTargetAttenuatorPercentage())

            mode = dpg.get_value(self.combo_tag)

            children = dpg.get_item_children(self.future_output_group, 1)
            if children:
                for child in children:
                    dpg.delete_item(child)

            for angle in angles:
                P, E = self.calculate_laser_pulse(angle, Att_percent, mode)
                with dpg.group(parent=self.future_output_group, horizontal=True):
                    dpg.add_text(f"{angle:.1f}°", color=(200, 255, 0))
                    dpg.add_text(f"E: {E:.1f} nJ", color=(0, 255, 255))
                    dpg.add_text(f"P: {P:.1f} µW", color=(0, 255, 255))


                print(f"Future → {angle:.1f}°, Att: {Att_percent:.1f}%, E: {E:.1f} nJ, P: {P:.1f} µW")

        except Exception as e:
            print(f"Error in future calculation: {e}")
            with dpg.group(parent=self.future_output_group):
                dpg.add_text("Error parsing input or calculating.", color=(255, 0, 0))

    def get_future_energies(self):
        """
        Return a list of (angle, E) for future pulse energies.
        """
        input_str = dpg.get_value(self.future_input_tag).strip()

        if "," in input_str:
            range_part, att_part = input_str.split(",")
            range_part = range_part.strip()
            att_part = att_part.strip().replace("%", "")
            override_att = float(att_part)
        else:
            range_part = input_str
            override_att = None

        parts = [float(x.strip()) for x in range_part.split(":")]
        if len(parts) != 3:
            raise ValueError("Input must be start:step:end")

        start, step, end = parts
        angles = np.arange(start, end + step, step)

        if override_att is not None:
            Att_percent = override_att
        else:
            Att_percent = float(self.pharos.getBasicTargetAttenuatorPercentage())

        mode = dpg.get_value(self.combo_tag)

        data = []
        for angle in angles:
            _, E = self.calculate_laser_pulse(angle, Att_percent, mode)
            data.append((angle, E))

        return data


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

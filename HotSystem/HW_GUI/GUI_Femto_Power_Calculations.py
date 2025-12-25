from HW_wrapper.Wrapper_KDC101 import MotorStage
from HW_wrapper.Wrapper_Pharos import PharosLaserAPI
import dearpygui.dearpygui as dpg
import numpy as np
import pyperclip

class FemtoPowerCalculator:
    prefix = "Femto"
    unique_id = "PowerCalc"
    future_input_tag = f"{prefix}_FutureInput_{unique_id}"

    def __init__(self, motor_stage):
        self.motor = motor_stage  # must support get_current_position()
        self.pharos = PharosLaserAPI(host="192.168.101.58")      # must support getBasicTargetAttenuatorPercentage()
        self.window_tag = f"{self.prefix}_Window_{self.unique_id}"
        self.combo_tag = f"{self.prefix}_Mode_{self.unique_id}"
        self.angle_tag = f"{self.prefix}_HWPAngle_{self.unique_id}"
        self.att_tag = f"{self.prefix}_Att_{self.unique_id}"
        self.power_tag = f"{self.prefix}_LaserPower_{self.unique_id}"
        self.energy_tag = f"{self.prefix}_PulseEnergy_{self.unique_id}"

        # self.future_input_tag = "Femto_FutureInput"
        self.future_output_group = f"{self.prefix}_FutureOutputGroup_{self.unique_id}"

    def DeleteMainWindow(self):
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

    def create_gui(self):
        default_future_value = self.load_future_input()
        with dpg.window(label="Femto Power Calculations", tag=self.window_tag, width=400, height=200):
            dpg.add_combo(items=["Default", "Compressor1"],
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
                               default_value=default_future_value,
                               on_enter=True,
                               callback=lambda s, a, u: [self.store_future_input(s, a), self.calculate_future(s, a, u)])
            dpg.add_separator()
            dpg.add_text("Future Results:", color=(255, 255, 0))
            with dpg.group(tag=self.future_output_group):
                pass  # This will hold the dynamic output rows
            self.calculate_future()

    def store_future_input(self, sender, app_data):
        """
        Stores the future input text to a file.
        """
        filename = "future_angles.txt"
        try:
            with open(filename, "w") as f:
                f.write(app_data)
            print(f"Stored future input to {filename}: {app_data}")
        except Exception as e:
            print(f"Failed to store future input: {e}")

    def load_future_input(self):
        """
        Loads the future input text from file if it exists,
        otherwise returns a default value.
        """
        filename = "future_angles.txt"
        try:
            with open(filename, "r") as f:
                value = f.read().strip()
                if value:
                    # print(f"Loaded future input from {filename}: {value}")
                    return value
        except FileNotFoundError:
            pass  # No file yet, use default

        # Fallback default
        return "1:1:15,10%"

    def calculate_laser_pulse(self, HWP_deg: float, Att_percent: float, mode: str, rep_rate: float = 50e3) -> tuple[float, float]:
        # Choose polynomial based on mode
        if mode == "Compressor1":
            A3, A2, A1, A0 = -0.1920, 17.8686, 34.3261, -97.1116
            P_att = A3 * Att_percent ** 3 + A2 * Att_percent ** 2 + A1 * Att_percent + A0
        else:
            A3, A2, A1, A0 = -0.106, 9.7757, 12.3629, -26.1961
            P_att = A3 * Att_percent ** 3 + A2 * Att_percent ** 2 + A1 * Att_percent + A0

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

    def calculate_future(self, sender=None, app_data=None, user_data=None):
        try:
            input_str = dpg.get_value(self.future_input_tag)
            # If prefixed with "!", treat as no-op and return Ly = 0
            if input_str.startswith("!"):
                # print("Future calculation skipped (bang-prefix).")
                return 0

            # Parse mode from suffix
            mode = dpg.get_value(self.combo_tag)  # fallback to GUI combo
            if "mode1" in input_str or "mode 1" in input_str:
                mode = "Compressor1"
                dpg.set_value(self.combo_tag, mode)
            elif "mode0" in input_str or "mode 0" in input_str:
                mode = "Default"
                dpg.set_value(self.combo_tag, mode)

            # ✅ Copy to clipboard with "future " prefix
            try:
                pyperclip.copy(f"future {input_str}")
                print(f"Copied to clipboard: future {input_str}")
            except Exception as copy_error:
                print(f"Clipboard copy failed: {copy_error}")

            # Clean input_str of any mode tokens
            for token in ["mode1", "mode 1", "mode0", "mode 0"]:
                input_str = input_str.replace(token, "")
            input_str = input_str.strip()

            # ✅ Split by ',' to separate range and Att, then detect 'xN'
            if "," in input_str:
                range_part, rest_part = input_str.split(",", 1)
                range_part = range_part.strip()
                # Support formats like '30%x100'
                if "x" in rest_part:
                    att_part, pulse_part = rest_part.split("x", 1)
                    att_part = att_part.strip().replace("%", "")
                    pulse_count = int(pulse_part.strip())
                else:
                    att_part = rest_part.strip().replace("%", "")
                    pulse_count = 1
                override_att = float(att_part)
            else:
                range_part = input_str.strip()
                override_att = None
                pulse_count = 1
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

            # Clear previous output
            children = dpg.get_item_children(self.future_output_group, 1)
            if children:
                for child in children:
                    dpg.delete_item(child)
            dy = 2000  # nm
            num_points = len(angles)
            Ly = (num_points - 1) * dy * 1e-3 # um
            dpg.add_text(f"# pnts:{num_points}, Ly:{Ly} um, Pulses: x{pulse_count}",
                         color=(255, 255, 0), parent=self.future_output_group)
            for angle in angles:
                P, E = self.calculate_laser_pulse(angle, Att_percent, mode)
                with dpg.group(parent=self.future_output_group, horizontal=True):
                    dpg.add_text(f"{angle:.1f}°", color=(200, 255, 0))
                    dpg.add_text(f"E: {E:.1f} nJ x {pulse_count}",
                                 color=(0, 255, 255))
                print(
                    f"HWP -> {angle:.1f}°, Att: {Att_percent:.1f}%, E: {E:.1f} nJ x {pulse_count}, P: {P:.1f} µW")
            return Ly
        except Exception as e:
            print(f"Error in future calculation: {e}")
            with dpg.group(parent=self.future_output_group):
                dpg.add_text("Error parsing input or calculating.", color=(255, 0, 0))

    def get_future_energies(self):
        """
        Return a list of (angle, E) for future pulse energies.
        Accepts input like: "3:1:5,15%x100"
        """
        input_str = dpg.get_value(self.future_input_tag).strip()
        # Parse mode override
        mode = dpg.get_value(self.combo_tag)
        if "mode1" in input_str or "mode 1" in input_str:
            mode = "Compressor1"
        elif "mode0" in input_str or "mode 0" in input_str:
            mode = "Default"

        # Remove mode from input_str
        for token in ["mode1", "mode 1", "mode0", "mode 0"]:
            input_str = input_str.replace(token, "")
        input_str = input_str.strip()

        if "," in input_str:
            range_part, rest_part = input_str.split(",", 1)
            range_part = range_part.strip()
            # Support formats like '15%x100'
            if "x" in rest_part:
                att_part, _ = rest_part.split("x", 1)
                att_part = att_part.strip().replace("%", "")
            else:
                att_part = rest_part.strip().replace("%", "")
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

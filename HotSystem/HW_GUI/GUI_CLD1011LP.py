import dearpygui.dearpygui as dpg
import HW_wrapper
import serial.tools.list_ports
from Common import DpgThemes
import HW_wrapper.Wrapper_Cobolt
import HW_wrapper.Wrapper_CLD1011
from HW_wrapper.HW_devices import HW_devices
import re

class GUI_CLD1011LP():
    def __init__(self, simulation: bool = False):
        self.HW = HW_devices()
        self.window_tag = "CLD1011LP_Win"
        self.laser = self.HW.CLD1011LP
        self.simulation = simulation

        # --- build window (unchanged) ---
        laser_info = "Simulating laser CLD10111LP" if simulation else getattr(self.laser, "info", "CLD1011LP")
        dpg.add_window(tag=self.window_tag, label=laser_info, no_title_bar=False,
                       height=440, width=1600, collapsed=True)

        dpg.add_group(tag="cld1011lp Laser_sections", horizontal=True, parent=self.window_tag)
        dpg.add_group(tag="cld1011lp control",    horizontal=False, parent="cld1011lp Laser_sections")
        dpg.add_group(tag="cld1011lp info",       horizontal=False, parent="cld1011lp Laser_sections")
        dpg.add_group(tag="cld1011lp parameters", horizontal=False, parent="cld1011lp Laser_sections")

        # --- controls (your existing buttons) ---
        dpg.add_button(parent="cld1011lp control",tag="cld1011lp btn_turn_on_off_laser",
                       label="Turn laser on", callback=self.turn_on_off_laser)
        dpg.add_button(parent="cld1011lp control",tag="cld1011lp btn_turn_on_off_tec",
                       label="tec on", callback=self.turn_on_off_tec)
        dpg.add_button(parent="cld1011lp control",tag="cld1011lp btn_turn_on_off_modulation",
                       label="Enable Modulation", callback=self.set_modulation_ena_dis)
        dpg.add_button(parent="cld1011lp control",tag="cld1011lp btn_switch_mode",
                       label="set power mode", callback=self.switch_to_pwr_cur_mode)

        # --- NEW: verify/refresh helpers ---
        dpg.add_spacer(parent="cld1011lp control", height=8)
        dpg.add_button(parent="cld1011lp control", label="Verify connection", callback=self.verify_connection)
        dpg.add_button(parent="cld1011lp control", label="Refresh info",      callback=self.refresh_info)
        dpg.add_button(parent="cld1011lp control", label="List serial ports", callback=self.print_ports)
        dpg.add_button(parent="cld1011lp control", tag="cld1011lp btn_get_current", label="Get current", callback=self.on_get_current)

        # --- info panel (existing + status line) ---
        dpg.add_text(parent="cld1011lp info", default_value="Laser Information", color=(255, 255, 0))
        dpg.add_text(parent="cld1011lp info", default_value="Status: UNKNOWN", tag="cld1011lp Status", color=(255, 100, 100))
        dpg.add_text(parent="cld1011lp info", default_value="Current ---",     tag="cld1011lp Laser Current")
        dpg.add_text(parent="cld1011lp info", default_value="Temperature ---", tag="cld1011lp Laser Temp")
        dpg.add_text(parent="cld1011lp info", default_value="Modulation ---",  tag="cld1011lp Laser Modulation")
        dpg.add_text(parent="cld1011lp info", default_value="Mode ---",        tag="cld1011lp Laser Mode")

        dpg.add_text(parent="cld1011lp parameters", default_value="Laser parameters", color=(255, 255, 0))
        dpg.add_input_float(parent="cld1011lp parameters", label="Set current(mA)", default_value=0,
                            callback=self.set_current, tag="cld1011lp current_input",
                            format='%.3f', width=200, min_value=0, max_value=250)

        # initial populate
        self.refresh_info()
        self.verify_connection()
        self.update_laser_button_label()

    # ---------- NEW helpers ----------
    def print_ports(self):
        ports = list(serial.tools.list_ports.comports())
        if not ports:
            print("No serial ports found.")
        for p in ports:
            print(f"PORT: {p.device} | {p.description} | {p.hwid}")

    def _set_status(self, ok: bool, msg: str = ""):
        color = (100, 255, 100) if ok else (255, 100, 100)
        text  = "Status: CONNECTED" if ok else "Status: DISCONNECTED"
        if msg:
            text += f" ({msg})"
        dpg.set_value("cld1011lp Status", text)
        dpg.configure_item("cld1011lp Status", color=color)

    def verify_connection(self):
        """Try a few safe queries to confirm comms."""
        if self.simulation:
            self._set_status(True, "simulation")
            return
        ok = True
        err = ""
        try:
            # identity string usually non-empty if the wrapper is live
            idn = getattr(self.laser, "info", "")
            if not idn:
                ok = False
                err = "no id"
            # benign reads (guard with hasattr in case wrapper names differ)
            if hasattr(self.laser, "get_lasing_state"):    self.laser.get_lasing_state()
            if hasattr(self.laser, "get_tec_state"):       self.laser.get_tec_state()
            if hasattr(self.laser, "get_mode"):            self.laser.get_mode()
            if hasattr(self.laser, "get_current"):         self.laser.get_current()
            if hasattr(self.laser, "get_temperature"):     self.laser.get_temperature()
            if hasattr(self.laser, "get_modulation_state"): self.laser.get_modulation_state()
        except Exception as e:
            ok = False
            err = str(e)[:120]
        self._set_status(ok, err)
        if ok:
            self.refresh_info()

    def refresh_info(self):
        """Populate info fields from the device, if available."""
        try:
            # current (mA)
            # cur_txt = "Current ---"
            # if hasattr(self.laser, "get_current"):
            #     val = self.laser.get_current()
            #     cur_txt = f"Current {val:.3f} mA" if isinstance(val, (int, float)) else f"Current {val}"
            # dpg.set_value("cld1011lp Laser Current", cur_txt)

            val = self.read_current_mA()
            cur_txt = "Current ---" if val is None else f"Current {val:.3f} A"
            dpg.set_value("cld1011lp Laser Current", cur_txt)

            # temperature (°C or raw)
            t_txt = "Temperature ---"
            if hasattr(self.laser, "get_temperature"):
                t = self.laser.get_temperature()
                t_txt = f"Temperature {t:.3f} °C" if isinstance(t, (int, float)) else f"Temperature {t}"
            dpg.set_value("cld1011lp Laser Temp", t_txt)

            # modulation
            m_txt = "Modulation ---"
            if hasattr(self.laser, "get_modulation_state"):
                m = self.laser.get_modulation_state()
                m_txt = f"Modulation {m}"
            elif hasattr(self.laser, "modulation_mod"):
                m_txt = f"Modulation {self.laser.modulation_mod}"
            dpg.set_value("cld1011lp Laser Modulation", m_txt)

            # mode (POW/CUR, etc.)
            md_txt = "Mode ---"
            if hasattr(self.laser, "get_mode"):
                self.laser.get_mode()
                md_txt = f"Mode {getattr(self.laser, 'mode', '---')}"
            dpg.set_value("cld1011lp Laser Mode", md_txt)

            # update title with id info, if available
            idn = getattr(self.laser, "info", "")
            if idn:
                dpg.configure_item(self.window_tag, label=idn)

        except Exception as e:
            self._set_status(False, str(e)[:120])

    def _try_float_from_any(self, v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            m = re.search(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', v)
            return float(m.group(0)) if m else None
        if isinstance(v, dict):
            # common keys wrappers use
            for k in ("current", "i", "mA", "setpoint", "actual"):
                if k in v:
                    return self._try_float_from_any(v[k])
        return None

    def read_current_mA(self):
        """Try several common wrapper APIs; return float mA or None."""
        cand = []
        las = self.laser
        # callables first
        for name in ("get_current", "read_current", "get_actual_current_mA",
                     "get_current_mA", "get_current_setpoint"):
            if hasattr(las, name) and callable(getattr(las, name)):
                cand.append(getattr(las, name))
        # attributes last
        for name in ("current", "current_mA"):
            if hasattr(las, name) and not callable(getattr(las, name)):
                cand.append(lambda n=name: getattr(las, n))

        for fn in cand:
            try:
                v = fn()
                f = self._try_float_from_any(v)
                if f is not None:
                    return f
            except Exception:
                pass
        return None

    def on_get_current(self):
        val = self.read_current_mA()
        if val is None:
            dpg.set_value("cld1011lp Laser Current", "Current (read failed)")
        else:
            dpg.set_value("cld1011lp Laser Current", f"Current {val:.3f} A")

    def set_current(self, sender, app_data, user_data):
        try:
            val = float(app_data)  # this is the input's value
        except (TypeError, ValueError):
            return
        if 0 <= val <= 250:
            try:
                self.laser.set_current(val)
            finally:
                # refresh the readback after commanding a new setpoint
                self.on_get_current()

    def switch_to_pwr_cur_mode(self):
        self.laser.get_mode()
        if self.laser.mode in ['POW']:
            self.laser.set_current_mode()
        else:
            self.laser.set_power_mode()

    def set_modulation_ena_dis(self):
        if self.laser.modulation_mod in ['enabled']:
            self.laser.disable_modulation()
        else:
            self.laser.enable_modulation()

    def turn_on_off_tec(self):
        self.laser.get_tec_state()
        if self.laser.tec_state in ['TEC is ON']:
            self.laser.disable_tec()
        else:
            self.laser.enable_tec()

    def _lasing_is_on(self) -> bool:
        """Robustly determine ON/OFF from wrapper."""
        try:
            ret = self.laser.get_lasing_state()  # some wrappers return a value, some only update an attribute
        except Exception:
            ret = None
        raw = ret if (ret is not None) else getattr(self.laser, "lasing_state", "")
        s = str(raw).strip().lower().replace("\r", "").replace("\n", "")
        # accept common synonyms
        return (s in {"laser is on", "on", "enabled", "true", "1"}) or ("on" in s and "off" not in s)

    def update_laser_button_label(self):
        """Set button label to the NEXT action."""
        try:
            label = "Turn laser off" if self._lasing_is_on() else "Turn laser on"
            dpg.configure_item("cld1011lp btn_turn_on_off_laser", label=label)
        except Exception:
            pass

    def turn_on_off_laser(self, sender=None, app_data=None, user_data=None):
        """Toggle laser and update the button to show the next action."""
        is_on = False
        try:
            is_on = self._lasing_is_on()
        except Exception:
            pass

        try:
            if is_on:
                self.laser.disable_laser()
            else:
                self.laser.enable_laser()
        finally:
            # Refresh status and ensure the button shows the next action
            if hasattr(self, "verify_connection"):
                self.verify_connection()
            if hasattr(self, "refresh_info"):
                self.refresh_info()
            self.update_laser_button_label()


import dearpygui.dearpygui as dpg
from HW_wrapper import Keysight33500B
from Common import DpgThemes
from SystemConfig import Instruments, load_instrument_images
import os
import json
import traceback

class GUIKeysight33500B:
    def __init__(self, device: Keysight33500B, instrument: Instruments = Instruments.KEYSIGHT_AWG, simulation: bool = False) -> None:
        """
        GUI class for Keysight 33500B waveform generator control.

        :param device: The Keysight 33500B waveform generator device object.
        :param instrument: The instrument identifier.
        :param simulation: Flag to indicate if simulation mode is enabled.
        """
        self.is_collapsed: bool = False
        load_instrument_images()
        self.dev = device
        self.simulation = simulation
        self.unique_id = self._get_unique_id_from_device()
        self.instrument = instrument
        # self.volts_per_um = -2e-6
        self.volts_per_um = -3000e-6

        self.volts_per_um_x = -3000e-6
        self.volts_per_um_y = -9600e-6

        # self.base1 = 0.7319
        self.base1 = 0
        # self.base2 = -0.5159
        self.base2 = 0

        self.xy_step = 0.002
        self.kx_ratio = 3.3
        self.ky_ratio = -0.3

        # 1) where to store settings
        self._settings_file = os.path.join(os.getcwd(), "awg_settings.json")
        # 2) load last channel (defaults to 1)
        self._saved_channel = self._load_saved_channel()
        # 3) make sure the device wrapper knows about it
        self.dev.channel = self._saved_channel

        self.red_button_theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))

        self.window_tag = f"Keysight33500B_Win_{self.unique_id}"
        with dpg.window(tag=self.window_tag, label=f"{self.instrument.value}",
                        no_title_bar=False, height=270, width=1800, pos=[0, 0], collapsed=False):
            with dpg.group(horizontal=True):
                # self.create_instrument_image()
                self.create_waveform_controls(self.red_button_theme)

                self.create_frequency_controls(self.red_button_theme)
                self.create_amplitude_controls(self.red_button_theme)
                self.create_duty_cycle_controls(self.red_button_theme)
                self.create_phase_controls(self.red_button_theme)
                self.create_trigger_controls(self.red_button_theme)

        # Store column tags for easy access and interchangeability
        self.column_tags = [
            f"column_waveform_{self.unique_id}",
            f"column_frequency_{self.unique_id}",
            f"column_amplitude_{self.unique_id}",
            f"column_offset_{self.unique_id}",
            f"column_duty_cycle_{self.unique_id}",
            f"column_phase_{self.unique_id}",
            f"column_phase_{self.unique_id}",
            f"column_output_{self.unique_id}",
        ]

        if not simulation:
            self.connect()

        # Finally, populate everything from the AWG
        # dpg.set_frame_callback(1, self.btn_get_current_parameters)
        self.btn_get_current_parameters()

    def _load_saved_channel(self) -> int:
        """Read saved channel from JSON, default to 1 if anything goes wrong."""
        try:
            with open(self._settings_file, "r") as f:
                data = json.load(f)
            print(f"JSON contents: {data!r}")
            return int(data.get("last_channel", 1))
        except Exception:
            return 1

    def _save_channel(self, ch: int):
        data = {}
        if os.path.exists(self._settings_file):
            try:
                data = json.load(open(self._settings_file, "r"))
            except Exception:
                data = {}
        data["last_channel"] = ch
        with open(self._settings_file, "w") as f:
            json.dump(data, f, indent=2)

    def _get_unique_id_from_device(self) -> str:
        """
        Generate a unique identifier for the GUI instance based on the device properties.

        :return: A string that uniquely identifies this device.
        """
        if hasattr(self.dev, 'addr') and self.dev.address is not None:
            return self.dev.addr
        else:
            return str(id(self.dev))

    def create_instrument_image(self):
        with dpg.group(horizontal=False, tag=f"column_instrument_image_{self.unique_id}"):
            dpg.add_image_button(
                f"{self.instrument.value}_texture", width=80, height=80,
                callback=self.toggle_gui_collapse,
                user_data=None
            )

    def create_waveform_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_waveform_{self.unique_id}", width=180):
            dpg.add_text("Waveform")
            dpg.add_combo(["SINE", "SQUARE", "TRIANGLE", "RAMP", "NOISE"], default_value="SINE",
                          tag=f"WaveformType_{self.unique_id}", width=100)
            dpg.add_button(label="Set Waveform", callback=self.btn_set_waveform)
            dpg.bind_item_theme(dpg.last_item(), theme)
             # ─── New “Get Current Parameters” row ───
            with dpg.group(horizontal=False):
                dpg.add_button(label="Get  Params",callback = self.btn_get_current_parameters)
                dpg.add_input_text(tag=f"CurrentParams_{self.unique_id}",multiline = True, readonly = True,
                                   width = 250, height = 200)
            self.create_offset_controls(self.red_button_theme)

    def create_frequency_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_frequency_{self.unique_id}", width=200):
            dpg.add_text("Frequency (Hz)")
            dpg.add_input_float(default_value=1000.0, tag=f"Frequency_{self.unique_id}",
                                format='%.1f', width=100, callback=self.validate_frequency_input)
            dpg.add_button(label="Set Frequency", callback=self.btn_set_frequency)
            dpg.bind_item_theme(dpg.last_item(), theme)
            # --- NEW: number of lines for raster (slow axis frequency = fast / lines) ---
            dpg.add_text("Lines")
            dpg.add_input_int(default_value=128, min_value=1, min_clamped=True,
                              tag=f"Lines_{self.unique_id}", width=100)

            # --- NEW: generate ramps (CH1 fast, CH2 slow) ---
            dpg.add_button(label="Gen Ramps", callback=self.btn_gen_ramps)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def btn_gen_ramps(self, sender=None, app_data=None):
        """
        Generate a raster scan:
          - CH1: fast symmetric triangle around base1 at Frequency & Amplitude from GUI
          - CH2: slow saw/ramp around base2 with frequency = fast_freq / lines
        Uses single 'Amplitude' field for both channels. Offsets = base1/base2.
        """
        try:
            # Read GUI values
            fast_freq = float(dpg.get_value(f"Frequency_{self.unique_id}"))
            amp_vpp = float(dpg.get_value(f"Amplitude_{self.unique_id}"))
            lines = int(dpg.get_value(f"Lines_{self.unique_id}"))
            lines = max(1, lines)

            # Compute slow frequency
            slow_freq = fast_freq / lines

            # Cache + set/restore current selected channel to avoid side-effects
            prev_ch = getattr(self.dev, "channel", 1)

            # ---------------- CH1 (FAST) : TRIANGLE around base1 ----------------
            try:
                # If your wrapper's set_waveform_type applies to self.dev.channel,
                # switch the active channel first:
                self.dev.channel = 1
                self.dev.set_waveform_type("TRIANGLE")
            except Exception:
                # If your wrapper supported per-channel type, you'd call it here.
                pass

            self.dev.set_frequency(fast_freq, channel=1)
            self.dev.set_amplitude(amp_vpp, channel=1)
            # Center around base1 (DC offset)
            self.dev.set_offset(self.base1, channel=1)
            # Symmetric triangle → duty 50%
            try:
                self.dev.set_duty_cycle(50.0, channel=1)
            except Exception:
                pass
            self.dev.set_output_state(True, channel=1)

            # ---------------- CH2 (SLOW) : RAMP/Saw around base2 ----------------
            try:
                self.dev.channel = 2
                self.dev.set_waveform_type("RAMP")  # sawtooth
            except Exception:
                pass

            self.dev.set_frequency(slow_freq, channel=2)
            self.dev.set_amplitude(amp_vpp, channel=2)
            self.dev.set_offset(self.base2, channel=2)
            # Optional: a standard sawtooth usually uses 50% duty = symmetric rise/fall.
            # If you want a classic 'ramp up / quick return', you can change duty here.
            try:
                self.dev.set_duty_cycle(50.0, channel=2)
            except Exception:
                pass
            self.dev.set_output_state(True, channel=2)

            # Restore previous channel selection in the GUI/device
            try:
                self.dev.channel = prev_ch
            except Exception:
                pass

            # Reflect some info back to the readonly text box
            summary = (f"Gen Ramps:\n"
                       f"  CH1 fast: TRIANGLE, f={fast_freq:.6g} Hz, A={amp_vpp:.3f} Vpp, offset={self.base1:.4f} V\n"
                       f"  CH2 slow: RAMP,     f={slow_freq:.6g} Hz, A={amp_vpp:.3f} Vpp, offset={self.base2:.4f} V\n"
                       f"  lines={lines}")
            dpg.set_value(f"CurrentParams_{self.unique_id}", summary)
            print(summary)

        except Exception as e:
            print(f"Error generating ramps: {e}")
            traceback.print_exc()

    def cb_select_channel(self, sender, app_data):
        """
        Radio‐button callback: app_data is the string "1" or "2".
        We store it on self.dev so later commands default to that channel.
        """
        try:
            ch = int(app_data)
        except ValueError:
            ch = 1
        # tack on a new attribute to your wrapper instance
        self.dev.channel = ch
        self._save_channel(ch)
        print(f"Selected AWG channel {ch} (saved)")

    def create_amplitude_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_amplitude_{self.unique_id}", width=200):
            dpg.add_text("Amplitude (Vpp)")
            dpg.add_input_float(default_value=1.0, tag=f"Amplitude_{self.unique_id}",
                                format='%.2f', width=100, callback=self.validate_amplitude_input)
            dpg.add_button(label="Set Amplitude", callback=self.btn_set_amplitude)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_offset_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_offset_{self.unique_id}", width=150):
            dpg.add_text("Offset (V)")
            dpg.add_input_float(default_value=0.0, tag=f"Offset_{self.unique_id}",step=0.01,
                                format='%.4f', width=100, callback=self.validate_offset_input)
            dpg.add_button(label="Set Offset", callback=self.btn_set_offset)
            dpg.bind_item_theme(dpg.last_item(), theme)

            self.create_output_controls(self.red_button_theme)

            # ─── Channel selector ───
            dpg.add_text("Channel:")
            dpg.add_radio_button(
                items=["1", "2"],
                default_value=str(self._saved_channel),
                tag=f"ChannelSelect_{self.unique_id}",
                horizontal=True,
                callback=self.cb_select_channel,
            )
            with dpg.group(horizontal=True):
                dpg.add_text("uV/um:")
                volts_input = dpg.add_input_float(
                    default_value=self.volts_per_um*1e6,  # Default value for volts_per_um
                    tag=f"mVoltsPerUm_{self.unique_id}",
                    step=0.01,
                    format='%.3f',
                    callback=lambda sender, app_data: setattr(self, 'volts_per_um', app_data*1e-6)  # Set self.volts_per_um with the input value
                )
            with dpg.group(horizontal=True):
                dpg.add_text("Step:")
                dpg.add_input_float(
                    default_value=2,  # Default value for volts_per_um
                    tag=f"XY_step_{self.unique_id}",
                    step=0.01,
                    format='%.3f',
                    callback=lambda sender, app_data: setattr(self, 'xy_step', app_data * 1e-3)
                    # Set self.volts_per_um with the input value
                )
            dpg.add_button(label="Set Lxy", callback=self.btn_set_offset)


    def create_duty_cycle_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_duty_cycle_{self.unique_id}", width=200):
            dpg.add_text("Duty Cycle (%)")
            dpg.add_input_float(default_value=50.0, tag=f"DutyCycle_{self.unique_id}",
                                format='%.1f', width=100, callback=self.validate_duty_cycle_input)
            dpg.add_button(label="Set Duty Cycle", callback=self.btn_set_duty_cycle)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_phase_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_phase_{self.unique_id}", width=200):
            dpg.add_text("Phase (°)")
            dpg.add_input_float(default_value=0.0, tag=f"Phase_{self.unique_id}",
                                format='%.1f', width=100, callback=self.validate_phase_input)
            dpg.add_button(label="Set Phase", callback=self.btn_set_phase)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_output_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_output_{self.unique_id}", width=150):
            dpg.add_text("Output")
            dpg.add_combo(["ON", "OFF"], default_value="OFF", tag=f"OutputState_{self.unique_id}", width=100)
            dpg.add_button(label="Set Output", callback=self.btn_set_output_state)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_trigger_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_trigger_{self.unique_id}", width=200):
            dpg.add_text("Trigger Controls")
            dpg.add_combo(["Internal", "External Once", "External Advance"],
                          default_value="Internal", tag=f"TriggerMode_{self.unique_id}", width=150)
            dpg.add_button(label="Apply Trigger Mode", callback=self.btn_apply_trigger_mode)
            dpg.add_text("Repetition Rate (Hz)")
            dpg.add_input_float(default_value=1.0, tag=f"RepRate_{self.unique_id}",
                                width=100)
            dpg.bind_item_theme(dpg.last_item(), theme)

    def create_arb_waveform_controls(self, theme):
        with dpg.group(horizontal=False, tag=f"column_arb_waveform_{self.unique_id}", width=200):
            dpg.add_text("Arbitrary Waveform (Ch 1)")
            dpg.add_input_text(label="Waveform Points (comma-separated)", tag=f"ArbWaveform_1_{self.unique_id}",
                               width=300)
            dpg.add_button(label="Upload Arbitrary Waveform Ch 1", callback=self.btn_upload_arbitrary_waveform_ch1)

            dpg.add_text("Arbitrary Waveform (Ch 2)")
            dpg.add_input_text(label="Waveform Points (comma-separated)", tag=f"ArbWaveform_2_{self.unique_id}",
                               width=300)
            dpg.add_button(label="Upload Arbitrary Waveform Ch 2", callback=self.btn_upload_arbitrary_waveform_ch2)

            dpg.bind_item_theme(dpg.last_item(), theme)

    def validate_frequency_input(self):
        """
        Ensure the frequency value is within valid limits (20 Hz to 20 MHz).
        """
        value = dpg.get_value(f"Frequency_{self.unique_id}")
        if value < 20:
            value = 20
        elif value > 20e6:
            value = 20e6
        dpg.set_value(f"Frequency_{self.unique_id}", value)

    def validate_amplitude_input(self):
        """
        Ensure the amplitude value is within valid limits (0.01 Vpp to 10 Vpp).
        """
        value = dpg.get_value(f"Amplitude_{self.unique_id}")
        if value < 0.01:
            value = 0.01
        elif value > 10:
            value = 10
        dpg.set_value(f"Amplitude_{self.unique_id}", value)

    def validate_offset_input(self):
        """
        Ensure the offset value is within valid limits (-5V to 5V).
        """
        value = dpg.get_value(f"Offset_{self.unique_id}")
        if value < -5:
            value = -5
        elif value > 5:
            value = 5
        dpg.set_value(f"Offset_{self.unique_id}", value)

    def validate_duty_cycle_input(self):
        """
        Ensure the duty cycle value is within valid limits (0% to 100%).
        """
        value = dpg.get_value(f"DutyCycle_{self.unique_id}")
        if value < 0:
            value = 0
        elif value > 100:
            value = 100
        dpg.set_value(f"DutyCycle_{self.unique_id}", value)

    def validate_phase_input(self):
        """
        Ensure the phase value is within valid limits (0° to 360°).
        """
        value = dpg.get_value(f"Phase_{self.unique_id}")
        if value < 0:
            value = 0
        elif value > 360:
            value = 360
        dpg.set_value(f"Phase_{self.unique_id}", value)

    def btn_set_waveform(self):
        """
        Set the waveform type.
        """
        waveform_type = dpg.get_value(f"WaveformType_{self.unique_id}")
        self.dev.set_waveform_type(waveform_type)

    def btn_get_current_parameters(self, sender=None, app_data=None):
        """
        Pull back each parameter safely—using wrapper methods
        where possible—and populate the readonly text box.
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))
        out = {}

        # 1) Waveform type
        try:
            wf = self.dev.query(f"source{ch}:func?").strip()
            out['Waveform'] = wf
            dpg.set_value(f"WaveformType_{self.unique_id}", wf)
        except Exception as e:
            out['Waveform'] = f"<err: {e}>"

        # 2) Frequency (use stored value)
        try:
            freq = f"{self.dev.get_frequency()} Hz"
            out['Frequency'] = freq
        except Exception as e:
            out['Frequency'] = f"<err: {e}>"

        # 3) Amplitude
        try:
            amp = self.dev.query(f"source{ch}:volt?").strip()
            out['Amplitude'] = f"{float(amp)} Vpp"
            dpg.set_value(f"Amplitude_{self.unique_id}", float(amp))
        except Exception as e:
            traceback.print_exc()
            out['Amplitude'] = f"<err: {e}>"

        # 4) Offset (use wrapper helper)
        try:
            offs = self.dev.get_current_voltage(ch)
            out['Offset'] = f"{float(offs)} V"
            dpg.set_value(f"Offset_{self.unique_id}", float(offs))
        except Exception as e:
            traceback.print_exc()
            out['Offset'] = f"<err: {e}>"

        # 6) Phase
        try:
            phase = self.dev.query(f"source{ch}:phase?").strip()
            out['Phase'] = f"{float(phase)}°"
        except Exception as e:
            out['Phase'] = f"<err: {e}>"

        # 7) Output state
        try:
            st = self.dev.query(f"output{ch}:stat?").strip()
            out['Output'] = "ON" if st.upper() in ("1", "ON") else "OFF"
            dpg.set_value(f"OutputState_{self.unique_id}", "ON" if st.upper() in ("1", "ON") else "OFF")
        except Exception as e:
            out['Output'] = f"<err: {e}>"

        text = "\n".join(f"{k}: {v}" for k, v in out.items())
        dpg.set_value(f"CurrentParams_{self.unique_id}", text)

    def btn_set_frequency(self):
        """
        Set the frequency of the waveform using the value from the input field.
        Ensure that the value is within the valid range of 20 Hz to 20 MHz.
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))

        frequency = dpg.get_value(f"Frequency_{self.unique_id}")
        try:
            # Set the frequency via the Keysight 33500B device wrapper
            self.dev.set_frequency(frequency, channel=ch)
            print(f"Frequency set to {frequency} Hz")
        except ValueError as e:
            print(f"Error in keysight GUI: {e}")

    def btn_set_amplitude(self):
        """
        Set the amplitude of the waveform.
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))
        amplitude = dpg.get_value(f"Amplitude_{self.unique_id}")
        self.dev.set_amplitude(amplitude,channel=ch)

    def btn_set_output_state(self):
        """
        Set the output state (ON/OFF).
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))
        output_state = dpg.get_value(f"OutputState_{self.unique_id}")
        self.dev.set_output_state(output_state == "ON",channel=ch)

    def btn_set_offset(self):
        """
        Set the DC offset of the waveform using the value from the input field.
        Ensure that the value is within the range of -5V to 5V.
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))
        offset = dpg.get_value(f"Offset_{self.unique_id}")
        try:
            # Set the offset via the Keysight 33500B device wrapper
            self.dev.set_offset(offset,channel=ch)
            print(f"Offset set to {offset} V")
        except ValueError as e:
            print(f"Error in keysight set offset: {e}")

    def btn_set_duty_cycle(self):
        """
        Set the duty cycle for the waveform using the value from the input field.
        Ensure that the value is within the range of 0% to 100%.
        """
        ch = int(dpg.get_value(f"ChannelSelect_{self.unique_id}"))
        duty_cycle = dpg.get_value(f"DutyCycle_{self.unique_id}")
        try:
            # Set the duty cycle via the Keysight 33500B device wrapper
            self.dev.set_duty_cycle(duty_cycle,channel=ch)
            print(f"Duty cycle set to {duty_cycle}%")
        except ValueError as e:
            print(f"Error: {e}")

    def btn_set_phase(self):
        """
        Set the phase of the waveform using the value from the input field.
        Ensure that the value is within the range of 0° to 360°.
        """
        phase = dpg.get_value(f"Phase_{self.unique_id}")
        try:
            # Set the phase via the Keysight 33500B device wrapper
            self.dev.set_phase(phase)
            print(f"Phase set to {phase}°")
        except ValueError as e:
            print(f"Error: {e}")

    def btn_set_external_trigger(self):
        self.dev.set_external_trigger()
        print("AWG set to external trigger mode.")

    def btn_set_sequence_mode(self):
        rep_rate = dpg.get_value(f"RepRate_{self.unique_id}")
        self.dev.set_external_trigger_advance(rep_rate)
        print(f"AWG set to sequence mode with {rep_rate} Hz repetition rate.")

    def btn_upload_arbitrary_waveform(self):
        points_str = dpg.get_value(f"ArbWaveform_{self.unique_id}")
        points = [float(x) for x in points_str.split(',')]
        self.dev.write_arbitrary_waveform(points)
        print("Arbitrary waveform uploaded.")

    def btn_apply_trigger_mode(self):
        """
        Apply the selected trigger mode from the combo box and set up the device accordingly.
        """
        trigger_mode = dpg.get_value(f"TriggerMode_{self.unique_id}")
        rep_rate = dpg.get_value(f"RepRate_{self.unique_id}")

        if trigger_mode == "Internal":
            self.dev.set_internal_trigger()
            print("AWG set to internal trigger mode.")
        elif trigger_mode == "External Once":
            self.dev.set_external_trigger_once(rep_rate)
            print(f"AWG set to external trigger (once) mode with {rep_rate} Hz.")
        elif trigger_mode == "External Advance":
            self.dev.set_external_trigger_advance()
            print("AWG set to external trigger (advance) mode.")

    def toggle_gui_collapse(self):
        if self.is_collapsed:
            print(f"Expanding {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.show_item(column_tag)
            dpg.set_item_width(self.window_tag, 1800)
            dpg.set_item_height(self.window_tag, 270)
        else:
            print(f"Collapsing {self.instrument.value} window")
            for column_tag in self.column_tags:
                dpg.hide_item(column_tag)
            dpg.set_item_width(self.window_tag, 130)
            dpg.set_item_height(self.window_tag, 130)
        self.is_collapsed = not self.is_collapsed

    def connect(self):
        try:
            self.dev.connect()
            print("Connected to Keysight 33500B")
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} connected")
        except Exception as e:
            print(f"Failed to connect to Keysight 33500B: {e}")
            dpg.set_item_label(self.window_tag, f"{self.dev.__class__.__name__} not connected")






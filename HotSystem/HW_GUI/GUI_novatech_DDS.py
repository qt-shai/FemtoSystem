import logging
from typing import Dict
from HW_wrapper import NovatechDDS426A
import dearpygui.dearpygui as dpg


# ---------------------------------------------------------------------------
# GUI for NovatechDDS426A using the observer pattern
# ---------------------------------------------------------------------------
class GUINovatechDDS426A:
    """
    A Dear PyGui-based GUI for controlling a NovatechDDS426A device.
    Uses observer pattern to auto-update the GUI on wrapper changes,
    and single callbacks for both channels using user_data.
    """

    def __init__(self, dds: NovatechDDS426A, simulation: bool = False) -> None:
        """
        Create the GUI for the NovatechDDS426A device.

        :param dds: Instance of NovatechDDS426A to control.
        :param simulation: Whether we are in simulation mode (disables hardware actions).
        """
        self.dds = dds
        self.simulation = simulation
        self.win_tag = f"Novatech426A_{id(self.dds)}"
        self.win_label = f"Novatech 426A DDS ({self.dds.address}) [SIM]" if simulation else f"Novatech 426A DDS ({self.dds.address})"
        self.is_collapsed = False

        # Main window
        with dpg.window(tag=self.win_tag,
                        label=self.win_label,
                        no_title_bar=False, height=400, width=900,
                        pos=[100, 100], collapsed=False):
            with dpg.group(horizontal=True):
                self.create_device_image()
                self.create_channel_controls()
                self.create_clock_controls()
                self.create_utility_controls()
                self.create_status_display()

        # Subscribe to device status changes
        self.dds.add_status_observer(self.on_dds_status_update)

    def show(self) -> None:
        """Display the window. Typically followed by dpg.start_dearpygui()."""
        dpg.show_item(self.win_tag)

    # --------------------------------------------------
    # Device Image (use an image button)
    # --------------------------------------------------
    def create_device_image(self) -> None:
        with dpg.group(horizontal=False, tag=f"{self.win_tag}_img_grp"):
            # Instead of a plain button, use an image button.
            # For an actual image, one would load a texture, but here we simulate with a placeholder.
            dpg.add_image_button(
                texture_tag=0,  # Typically a texture ID loaded via dpg.load_image(...)
                label="426A Image",
                width=80,
                height=80,
                callback=lambda: self.toggle_gui_collapse_button_callback()
            )

    # --------------------------------------------------
    # Channel Controls (CH0, CH1) in a single approach
    # --------------------------------------------------
    def create_channel_controls(self) -> None:
        with dpg.group(horizontal=False, tag=f"{self.win_tag}_chan_grp", width=300):
            dpg.add_text("Channel 0")
            dpg.add_input_float(
                tag=f"{self.win_tag}_freq_0",
                label="Frequency (MHz)",
                default_value=10.0,
                format="%.6f",
                step=1.0,
                callback=self.cb_set_frequency,
                user_data=Channel.CH0,     # store channel
                min_value=NovatechDDS426A.MIN_FREQ,
                max_value=MAX_FREQ
            )
            dpg.add_input_int(
                tag=f"{self.win_tag}_phase_0",
                label="Phase (0..16383)",
                default_value=0,
                callback=self.cb_set_phase,
                user_data=Channel.CH0,     # store channel
                min_value=MIN_PHASE,
                max_value=MAX_PHASE
            )
            dpg.add_input_int(
                tag=f"{self.win_tag}_amp_0",
                label="Amp (0..1023)",
                default_value=1023,
                callback=self.cb_set_amplitude,
                user_data=Channel.CH0,     # store channel
                min_value=MIN_ATTENUATION,
                max_value=MAX_ATTENUATION
            )

            dpg.add_spacer(height=10)

            dpg.add_text("Channel 1")
            dpg.add_input_float(
                tag=f"{self.win_tag}_freq_1",
                label="Frequency (MHz)",
                default_value=10.0,
                format="%.6f",
                step=1.0,
                callback=self.cb_set_frequency,
                user_data=Channel.CH1,
                min_value=MIN_FREQ,
                max_value=MAX_FREQ
            )
            dpg.add_input_int(
                tag=f"{self.win_tag}_phase_1",
                label="Phase (0..16383)",
                default_value=0,
                callback=self.cb_set_phase,
                user_data=Channel.CH1,
                min_value=MIN_PHASE,
                max_value=MAX_PHASE
            )
            dpg.add_input_int(
                tag=f"{self.win_tag}_amp_1",
                label="Amp (0..1023)",
                default_value=1023,
                callback=self.cb_set_amplitude,
                user_data=Channel.CH1,
                min_value=MIN_ATTENUATION,
                max_value=MAX_ATTENUATION
            )

    # --------------------------------------------------
    # Clock and Reference Controls
    # --------------------------------------------------
    def create_clock_controls(self) -> None:
        with dpg.group(horizontal=False, tag=f"{self.win_tag}_clock_grp", width=200):
            dpg.add_text("Clock/Ref Settings")

            # Use a combo to select clock mode
            dpg.add_combo(
                label="Clock Mode",
                tag=f"{self.win_tag}_clock_mode",
                items=[m.name for m in ClockMode],
                default_value=ClockMode.INTERNAL.name,
                callback=self.cb_set_clock_mode
            )
            dpg.add_input_float(
                label="Ref Freq (MHz)",
                tag=f"{self.win_tag}_ref_freq",
                default_value=10.0,
                format="%.3f",
                step=1.0,
                callback=self.cb_set_ref_freq,
                min_value=MIN_REF_FREQ,
                max_value=MAX_REF_FREQ
            )
            dpg.add_input_float(
                label="Direct Freq (MHz)",
                tag=f"{self.win_tag}_direct_freq",
                default_value=400.0,
                format="%.3f",
                step=10.0,
                callback=self.cb_set_direct_freq,
                min_value=MIN_DIRECT_FREQ,
                max_value=MAX_DIRECT_FREQ
            )

    # --------------------------------------------------
    # Utility Controls (PS, Save, Reset, Factory Reset)
    # --------------------------------------------------
    def create_utility_controls(self) -> None:
        with dpg.group(horizontal=False, tag=f"{self.win_tag}_util_grp", width=150):
            dpg.add_text("Utility")
            dpg.add_button(label="PS (Sync Phase)", callback=self.cb_sync_phase)
            dpg.add_button(label="Save (S)", callback=self.cb_save_settings)
            dpg.add_button(label="Reset (R)", callback=self.cb_reset_device)
            dpg.add_button(label="Factory Reset (CLR)", callback=self.cb_factory_reset)

    # --------------------------------------------------
    # Status Display Area
    # --------------------------------------------------
    def create_status_display(self) -> None:
        with dpg.group(horizontal=False, tag=f"{self.win_tag}_status_grp", width=200):
            dpg.add_text("Status:")
            dpg.add_text("", tag=f"{self.win_tag}_device_status")

    # --------------------------------------------------
    # Unified callbacks using user_data for channel
    # --------------------------------------------------
    def cb_set_frequency(self, sender, app_data, user_data):
        """Set the frequency for the channel provided in user_data."""
        if self.simulation:
            return
        channel = user_data
        freq = dpg.get_value(sender)
        try:
            self.dds.set_frequency(channel, freq)
        except Exception as exc:
            logging.error(f"Failed to set frequency for {channel.name}: {exc}")

    def cb_set_phase(self, sender, app_data, user_data):
        """Set the phase for the channel provided in user_data."""
        if self.simulation:
            return
        channel = user_data
        val = dpg.get_value(sender)
        try:
            self.dds.set_phase(channel, val)
        except Exception as exc:
            logging.error(f"Failed to set phase for {channel.name}: {exc}")

    def cb_set_amplitude(self, sender, app_data, user_data):
        """Set the amplitude for the channel provided in user_data."""
        if self.simulation:
            return
        channel = user_data
        val = dpg.get_value(sender)
        try:
            self.dds.set_amplitude(channel, val)
        except Exception as exc:
            logging.error(f"Failed to set amplitude for {channel.name}: {exc}")

    def cb_set_clock_mode(self, sender, app_data):
        if self.simulation:
            return
        # The combo returns the .name, so let's map that to the enum
        mode_name = dpg.get_value(sender)
        try:
            mode_enum = ClockMode[mode_name]
            self.dds.set_clock_mode(mode_enum)
        except Exception as exc:
            logging.error(f"Failed to set clock mode: {exc}")

    def cb_set_ref_freq(self, sender, app_data):
        if self.simulation:
            return
        val = dpg.get_value(sender)
        try:
            self.dds.set_reference_frequency(val)
        except Exception as exc:
            logging.error(f"Failed to set reference frequency: {exc}")

    def cb_set_direct_freq(self, sender, app_data):
        if self.simulation:
            return
        val = dpg.get_value(sender)
        try:
            self.dds.set_direct_frequency(val)
        except Exception as exc:
            logging.error(f"Failed to set direct frequency: {exc}")

    # --------------------------------------------------
    # Utility Command Callbacks
    # --------------------------------------------------
    def cb_sync_phase(self):
        if self.simulation:
            return
        try:
            self.dds.synchronize_phase()
        except Exception as exc:
            logging.error(f"Failed to sync phase: {exc}")

    def cb_save_settings(self):
        if self.simulation:
            return
        try:
            self.dds.save_settings()
        except Exception as exc:
            logging.error(f"Failed to save settings: {exc}")

    def cb_reset_device(self):
        if self.simulation:
            return
        try:
            self.dds.reset_device()
        except Exception as exc:
            logging.error(f"Failed to reset device: {exc}")

    def cb_factory_reset(self):
        if self.simulation:
            return
        try:
            self.dds.factory_reset()
        except Exception as exc:
            logging.error(f"Failed to factory reset device: {exc}")

    # --------------------------------------------------
    # Observer Callback (Auto-update GUI)
    # --------------------------------------------------
    def on_dds_status_update(self, status: Dict[str, str]) -> None:
        """
        Called by the wrapper whenever the device status changes.
        Also update each channel's frequency, phase, amplitude, etc.
        """
        # 1) Update the text status area
        if dpg.does_item_exist(f"{self.win_tag}_device_status"):
            # Just a summary line, as before
            lines = [f"{k}={v}" for k, v in status.items()]
            dpg.set_value(f"{self.win_tag}_device_status", " | ".join(lines))

        # 2) Update channel widgets if data is present
        #    E.g. F0, P0, V0 for channel 0, F1, P1, V1 for channel 1
        #    Also FR, FD, Clock mode, etc.

        # Channel 0
        if "F0" in status:
            freq_0 = float(status["F0"])
            dpg.configure_item(f"{self.win_tag}_freq_0", default_value=freq_0, value=freq_0)
        if "P0" in status:
            phase_0 = float(status["P0"])
            dpg.configure_item(f"{self.win_tag}_phase_0", default_value=phase_0, value=int(phase_0))
        if "V0" in status:
            amp_0 = float(status["V0"])
            dpg.configure_item(f"{self.win_tag}_amp_0", default_value=amp_0, value=int(amp_0))

        # Channel 1
        if "F1" in status:
            freq_1 = float(status["F1"])
            dpg.configure_item(f"{self.win_tag}_freq_1", default_value=freq_1, value=freq_1)
        if "P1" in status:
            phase_1 = float(status["P1"])
            dpg.configure_item(f"{self.win_tag}_phase_1", default_value=phase_1, value=int(phase_1))
        if "V1" in status:
            amp_1 = float(status["V1"])
            dpg.configure_item(f"{self.win_tag}_amp_1", default_value=amp_1, value=int(amp_1))

        # Reference Freq
        if "FR" in status:
            ref_val = float(status["FR"])
            dpg.configure_item(f"{self.win_tag}_ref_freq", default_value=ref_val, value=ref_val)

        # Direct Freq
        if "FD" in status:
            dir_val = float(status["FD"])
            dpg.configure_item(f"{self.win_tag}_direct_freq", default_value=dir_val, value=dir_val)

        # Clock mode
        if "Clock mode" in status:
            # status might have 'Clock mode: D', 'E', or 'P'
            cval = status["Clock mode"].upper()
            # We invert the dictionary from ClockMode => str
            # to figure out the correct mode name for the combo
            # e.g. "D" -> ClockMode.INTERNAL -> .name => "INTERNAL"
            clock_mode_lookup = {m.value: m.name for m in ClockMode}
            if cval in clock_mode_lookup:
                dpg.set_value(f"{self.win_tag}_clock_mode", clock_mode_lookup[cval])

    # --------------------------------------------------
    # Collapse/Expand Logic
    # --------------------------------------------------
    def toggle_gui_collapse_button_callback(self):
        """Callback from the image button. Toggles the GUI collapsed state."""
        self.toggle_gui_elements(not self.is_collapsed)

    def toggle_gui_elements(self, show: bool) -> None:
        """
        Show or hide certain GUI items depending on the boolean.
        """
        if show:
            # Expand window
            dpg.set_item_width(self.win_tag, 900)
            dpg.set_item_height(self.win_tag, 400)
            for grp in (f"{self.win_tag}_chan_grp",
                        f"{self.win_tag}_clock_grp",
                        f"{self.win_tag}_util_grp",
                        f"{self.win_tag}_status_grp"):
                dpg.show_item(grp)
        else:
            # Collapse window
            dpg.set_item_width(self.win_tag, 150)
            dpg.set_item_height(self.win_tag, 150)
            for grp in (f"{self.win_tag}_chan_grp",
                        f"{self.win_tag}_clock_grp",
                        f"{self.win_tag}_util_grp",
                        f"{self.win_tag}_status_grp"):
                dpg.hide_item(grp)
        self.is_collapsed = show
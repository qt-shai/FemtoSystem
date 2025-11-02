"""
gui_wavemeter.py
----------------
Super-compact GUI for a HighFinesse wavemeter.

* Use LiveObservablePlot to visualise Δf in real time.
* Only core Dear PyGui calls — works on every 1.x release.
"""

from __future__ import annotations

import logging
from typing import Final

import dearpygui.dearpygui as dpg

from Common import DpgThemes
from HW_wrapper.wrapper_wavemeter import HighFinesseWLM
from SystemConfig import Instruments, load_instrument_images
from HW_GUI.CommonUI.observable_plot import LiveObservablePlot
_logger: Final = logging.getLogger(__name__)


class GUIWavemeter:
    """Minimal control panel for HighFinesse WLM."""

    def __init__(self, device: HighFinesseWLM, *, instrument: Instruments = Instruments.WAVEMETER) -> None:
        if not isinstance(device, HighFinesseWLM):
            raise TypeError("device must be HighFinesseWLM")
        self._dev = device
        self._instr = instrument
        self._uniq = f"{id(self._dev):x}"
        self._ctrl_tag = f"controls_{self._uniq}"
        self._plot: LiveObservablePlot | None = None

        load_instrument_images()
        self._build_window()
        self._attach_plot()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_window(self) -> None:
        theme = DpgThemes.color_theme((255, 0, 0), (0, 0, 0))
        self._window = f"WLM_{self._uniq}"

        with dpg.window(label=self._instr.value, width=720, height=560, tag=self._window):
            tex_tag = f"{self._instr.value}_texture"
            with dpg.group(horizontal=True):
                if dpg.does_item_exist(tex_tag):
                    dpg.add_image_button(texture_tag=tex_tag, width=90, height=90, callback=self._toggle_controls)

                with dpg.group(horizontal=False, tag=self._ctrl_tag):
                    dpg.add_button(label="Connect", width=160, callback=self._connect)
                    dpg.bind_item_theme(dpg.last_item(), theme)

                    dpg.add_button(label="Disconnect", width=160, callback=self._disconnect)
                    dpg.bind_item_theme(dpg.last_item(), theme)

                    dpg.add_button(label="Start/Stop Updates", width=160, callback=self._toggle_updates)
                    dpg.bind_item_theme(dpg.last_item(), theme)

                    dpg.add_button(label="Reset Graph", width=160, callback=self._reset_plot)
                    dpg.bind_item_theme(dpg.last_item(), theme)
            self._base_lbl = dpg.add_text("Base: –", bullet=True)

    def _attach_plot(self) -> None:
        self._plot = LiveObservablePlot(
            self._dev.frequency,
            parent=self._ctrl_tag,
            title="Frequency",
            transform=lambda raw, base: raw - base,
            units={"GHz": 1e-9, "MHz": 1e-6, "THz": 1e-12},
            max_points=4000,
                )

    def _reset_plot(self) -> None:
        """Clear history + base-frequency."""
        if self._plot:
            freq = self._dev.get_frequency()
            dpg.set_value(self._base_lbl, f"Base: {freq * 1e-12:.3f} THz")
            self._plot._base = freq * 1e-9
            self._plot.reset()

    # ------------------------------------------------------------------
    # Button callbacks
    # ------------------------------------------------------------------
    def _connect(self) -> None:
        try:
            self._dev.connect()
            dpg.set_item_label(self._window, f"{self._dev.__class__.__name__} [CONNECTED]")
        except Exception as exc:
            _logger.error("Connect failed: %s", exc)

    def _disconnect(self) -> None:
        try:
            self._dev.close()
            dpg.set_item_label(self._window, f"{self._dev.__class__.__name__} [DISCONNECTED]")
        except Exception as exc:
            _logger.error("Disconnect failed: %s", exc)

    def _toggle_updates(self) -> None:
        if self._dev.updates_running:
            self._dev.stop_updates()
        else:
            freq = self._dev.get_frequency()
            dpg.set_value(self._base_lbl, f"Base: {freq*1e-12:.3f} THz")
            self._plot._base = freq * 1e-9
            self._dev.start_updates()

    def _toggle_controls(self) -> None:
        if dpg.is_item_shown(self._ctrl_tag):
            dpg.hide_item(self._ctrl_tag)
        else:
            dpg.show_item(self._ctrl_tag)

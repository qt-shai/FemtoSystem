# HW_GUI/GUI_PROEM.py
from __future__ import annotations

import os
import dearpygui.dearpygui as dpg
from HW_GUI.GUI_HRS_500 import GUI_HRS500


class GUI_PROEM(GUI_HRS500):
    """
    A dedicated GUI for the ProEM (LightField) spectrometer.
    Keeps the regular HRS GUI untouched by using its own prefix, tags and title.
    """

    DEFAULT_LFE = r"C:\Users\Femto\Work Folders\Documents\LightField\Experiments\ProEM_shai.lfe"
    DEFAULT_SAVE_DIR = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer\ProEM"

    def __init__(self, device, *, prefix: str = "proem", title: str = "ProEM Camera") -> None:
        # Use the extended ctor in GUI_HRS500 (prefix/title support)
        super().__init__(device, prefix=prefix, title=title)

        # ProEM-specific defaults
        try:
            if hasattr(self.dev, "set_save_directory"):
                self.dev.set_save_directory(self.DEFAULT_SAVE_DIR)
        except Exception:
            pass

        # If a ProEM experiment path is known, preload it (non-fatal on failure)
        try:
            if hasattr(self.dev, "file_path"):
                self.dev.file_path = self.DEFAULT_LFE
            if hasattr(self.dev, "load_experiment"):
                self.dev.load_experiment()
        except Exception:
            pass

    # (Optional) Keep ProEM cleanup separate if you want different behavior
    def _cleanup(self):
        try:
            if hasattr(self, "dev") and hasattr(self.dev, "close"):
                self.dev.close()
        except Exception:
            pass
        # Kill LightField side-process if it exists (same as HRS)
        try:
            os.system("taskkill /im AddInProcess.exe")
        except Exception:
            pass

    def create_gui(self, title: str | None = None):
        """ProEM: no buttons, no graph — just a minimal window."""
        with dpg.window(
                label=(title or "Spectrometer (ProEM)"),
                no_title_bar=False,
                height=140,
                width=360,
                pos=[100, 100],
                collapsed=False,
                tag=self.window_tag,
                on_close=self._cleanup,
        ):
            dpg.add_text("ProEM device is active.")
            # Add any lightweight status fields you want here (no controls/plots).

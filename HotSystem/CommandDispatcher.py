import atexit
import glob
import json
import sys
import os
import re
import tempfile
import threading
import time
import pyperclip
import traceback
import subprocess
import numpy as np
from PIL import ImageGrab, Image
import pytesseract
import dearpygui.dearpygui as dpg
from bokeh.util.terminal import yellow
import signal
from Utils.extract_positions import preprocess_image, extract_positions, TESSERACT_CONFIG
from Utils import loadFromCSV
from Utils.export_points import export_points
from Survey_Analysis.Scan_Image_Analysis import ScanImageAnalysis
import HW_wrapper.HW_devices as hw_devices
from HW_GUI.GUI_MFF_101 import GUI_MFF
from Common import *
from PrincetonInstruments.LightField.AddIns import CameraSettings
from PrincetonInstruments.LightField.AddIns import ExperimentSettings
from Utils import open_file_dialog
import Utils.python_displayer as disp
from PIL import ImageGrab, Image
import io
import win32com.client
import pythoncom
import json
import subprocess
import win32com.client
import pythoncom
import json
import time
from PIL import ImageGrab
import io, json, os
from pptx import Presentation
from pptx.util import Inches
from PIL import ImageGrab
from HW_GUI.GUI_Femto_Power_Calculations import FemtoPowerCalculator
from pathlib import Path
from HW_wrapper.Wrapper_HRS_500 import LightFieldSpectrometer
import os
import re
import glob
import math
import tempfile
from PIL import Image, ImageDraw
import pythoncom
import win32com.client


# Textbox: Alt + n X
# Font color: Alt + H F C
# Paste as pic: Alt + H V U
CHIP_ANGLE=-2.3

STATE_FILENAME = "coup_state.json"
CONFIG_PATH = r"C:\WC\HotSystem\SystemConfig\xml_configs\system_info.xml"
DEFAULT_COUP_DIR = r"c:\WC\HotSystem\Utils\macro"

# ----- CGH helpers -----
_CGH_PIDFILE = Path.home() / ".cgh_fullscreen.pid"
def _write_pidfile(pid: int):
    try:
        _CGH_PIDFILE.write_text(str(pid), encoding="utf-8")
    except Exception:
        pass
def _read_pidfile() -> int | None:
    try:
        return int(_CGH_PIDFILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None
def _clear_pidfile():
    try:
        if _CGH_PIDFILE.exists():
            _CGH_PIDFILE.unlink()
    except Exception:
        pass
def _proc_is_alive(pid: int) -> bool:
    import subprocess, os
    try:
        if os.name != "nt":
            os.kill(pid, 0)
            return True
        else:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
            return str(pid) in out.stdout
    except Exception:
        return False
def _terminate_pid(pid: int) -> bool:
    import subprocess, os, time, signal
    try:
        if os.name == "nt":
            try:
                os.kill(pid, signal.CTRL_BREAK_EVENT)  # may fail if not same console group
                time.sleep(0.3)
            except Exception:
                pass
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGTERM)
        return True
    except Exception:
        return False
def _send_key_p_to_cgh_window(window_title: str = "SLM CGH") -> bool:
    """
    Posts a 'P' keypress to the CGH window. Works even if not foreground.
    Returns True on success.
    """
    try:
        import ctypes, time
        user32 = ctypes.windll.user32
        FindWindowW   = user32.FindWindowW
        PostMessageW  = user32.PostMessageW

        hwnd = FindWindowW(None, window_title)
        if not hwnd:
            return False

        WM_KEYDOWN = 0x0100
        WM_KEYUP   = 0x0101
        VK_P       = 0x50  # 'P'

        # Press and release
        PostMessageW(hwnd, WM_KEYDOWN, VK_P, 0)
        time.sleep(0.02)
        PostMessageW(hwnd, WM_KEYUP,   VK_P, 0)
        return True
    except Exception:
        return False
def _poke_cgh_window(window_title: str = "SLM CGH") -> bool:
    """Send a harmless WM_NULL to nudge the window message loop (no behavior change)."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, window_title)
        if not hwnd:
            return False
        # WM_NULL = 0x0000
        user32.PostMessageW(hwnd, 0x0000, 0, 0)
        return True
    except Exception:
        return False
def _find_cgh_hwnd(window_title: str = "SLM CGH") -> int | None:
    try:
        import ctypes
        hwnd = ctypes.windll.user32.FindWindowW(None, window_title)
        return hwnd or None
    except Exception:
        return None
def _wait_for_cgh_window(timeout_s: float = 3.0, window_title: str = "SLM CGH") -> bool:
    import time
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if _find_cgh_hwnd(window_title):
            return True
        time.sleep(0.05)
    return False
# ------------------------------------------
def _dispatcher_base_dir(self) -> str:
    """Folder of CommandDispatcher.py (works even if module path is indirect)."""
    mod = sys.modules.get(self.__class__.__module__) or sys.modules.get(__name__)
    here = getattr(mod, "__file__", __file__)
    return os.path.dirname(os.path.abspath(here))
def _prefer_py(path: str) -> str:
    """Prefer .py over .pyc/.pyo when available."""
    if path.endswith((".pyc", ".pyo")) and os.path.exists(path[:-1]):
        return path[:-1]
    return path
def _open_path(path: str):
    """Open a file with the default app (Windows) and print a status line."""
    path = _prefer_py(path)
    if not os.path.exists(path):
        print(f"[show] File not found: {path}")
        return
    try:
        os.startfile(path)  # Windows default opener
        print(f"[show] Opened: {path}")
    except Exception as e:
        print(f"[show] Failed to open {path}: {e}")
def _open_module_or_fallback(module_name: str, fallback_rel: str, base_dir: str):
    """
    Try to open the source file of module_name; if not found, open base_dir/fallback_rel.
    """
    try:
        mod = sys.modules.get(module_name) or importlib.import_module(module_name)
        path = os.path.abspath(getattr(mod, "__file__", ""))
        if path and os.path.exists(path):
            _open_path(path)
            return
    except Exception as e:
        # Not fatal; we'll try the fallback below.
        print(f"[show] Import fallback for {module_name}: {e}")

    fall = os.path.join(base_dir, *fallback_rel.split("\\"))
    _open_path(fall)

# Primary mapping: alias(es) -> (module, fallback_relative_path)
SHOW_MAP = {
    # GUIs
    ("opx", "hwrap_opx", "opxwrap"): ("HWrap_OPX", r"HWrap_OPX.py"),
    ("disp", "display", "zslices", "zslice"): ("Utils.display_all_z_slices_with_slider", r"Utils\display_all_z_slices_with_slider.py"),
    ("awg", "keysight", "keysight_awg"): ("HW_GUI.GUI_keysight_AWG", r"HW_GUI\GUI_keysight_AWG.py"),
    ("cld", "cld1011", "cld1011lp"): ("HW_GUI.GUI_CLD1011LP", r"HW_GUI\GUI_CLD1011LP.py"),
    ("cob", "cobolt"): ("HW_GUI.GUI_Cobolt", r"HW_GUI\GUI_Cobolt.py"),
    ("femto",): ("HW_GUI.GUI_Femto_Power_Calculations", r"HW_GUI\GUI_Femto_Power_Calculations.py"),
    ("hrs", "hrs500", "hrs_500"): ("HW_GUI.GUI_HRS_500", r"HW_GUI\GUI_HRS_500.py"),
    ("kdc", "kdc101", "kdc_101"): ("HW_GUI.GUI_KDC101", r"HW_GUI\GUI_KDC101.py"),
    ("smaract",): ("HW_GUI.GUI_Smaract", r"HW_GUI\GUI_Smaract.py"),
    ("zelux",): ("HW_GUI.GUI_Zelux", r"HW_GUI\GUI_Zelux.py"),
    # App root
    ("app",): ("Application", r"Application.py"),
}

# Wrapper mapping for: show wrap <thing>
WRAP_MAP = {
    "cld":     ("HW_wrapper.Wrapper_CLD1011", r"HW_wrapper\Wrapper_CLD1011.py"),
    "zelux":   ("HW_wrapper.Wrapper_Zelux",   r"HW_wrapper\Wrapper_Zelux.py"),
    "cob":     ("HW_wrapper.Wrapper_Cobolt",  r"HW_wrapper\Wrapper_Cobolt.py"),
    "smaract": ("HW_wrapper.Wrapper_Smaract", r"HW_wrapper\Wrapper_Smaract.py"),
    "hrs":     ("HW_wrapper.Wrapper_HRS_500", r"HW_wrapper\Wrapper_HRS_500.py"),
    "hrs500":  ("HW_wrapper.Wrapper_HRS_500", r"HW_wrapper\Wrapper_HRS_500.py"),
    "hrs_500": ("HW_wrapper.Wrapper_HRS_500", r"HW_wrapper\Wrapper_HRS_500.py"),
    "wave":    ("HW_wrapper.wrapper_wavemeter", r"HW_wrapper\wrapper_wavemeter.py"),
    "wavemeter":    ("wrapper_wavemeter", r"HW_GUI\wrapper_wavemeter.py"),
}

class DualOutput:
    def __init__(self, original_stream):
        """
        Initialize the dual output.
        :param append_to_console: Function to append messages to the Dear PyGui console.
        :param original_stream: The original output stream (e.g., sys.stdout or sys.stderr).
        """
        self.append_callback =  self.append_to_console
        self.original_stream = original_stream
        self.messages = []  # Store the last 10 messages
        self.MAX_MESSAGES = 50

    def write(self, message):
        """
        Write a message to both the GUI console and the original stream.
        :param message: The message to display.
        """
        if message.strip():  # Ignore empty messages
            if not message.endswith("\n"):
                message += "\n"
            self.append_callback(message)
            self.original_stream.write(message)  # Print to the original console

    def append_to_console(self, message):
        """Appends a message to the console."""
        self.messages.append(message)
        if len(self.messages) > self.MAX_MESSAGES:
            self.messages.pop(0)

        if dpg.does_item_exist("console_log"):  # Ensure the widget exists
            dpg.set_value("console_log", "".join(self.messages))
            dpg.set_y_scroll("console_output", 99999)  # Auto-scroll to bottom

    def flush(self):
        """
        Flush the output (required for compatibility with file-like objects).
        """
        self.original_stream.flush()

class Axis(Enum):
    Z = 0
    Y = 1
    X = 2

class CommandDispatcher:
    """
    Wraps all command handlers into methods and dispatches via a dictionary lookup,
    eliminating any long if/elif chains.
    """
    def __init__(self):
        self._coup_shift_x_factor=5
        self._coup_shift_y_factor=5.43
        self._coupx_move_um = 80
        self._coupy_move_um = 70
        self._dual_output = DualOutput(sys.stdout)
        self._last_cmd = None
        self._last_fq_idx = None
        self._cgh_proc = None  # track the fullscreen CGH process
        self.proEM_mode = False
        self._coup_thread = None
        self._coup_abort_evt = threading.Event()
        self._coup_active_evt = threading.Event()  # optional: mark active
        self.default_graph_size = (None, None)
        self.handlers = {
            # simple commands
            "a":                 self.handle_add_slide,
            "ax":                self.handle_toggle_ax,
            "c":                 self.handle_copy_window,
            "cc":                self.handle_screenshot_delayed,
            "hl":                self.handle_hide_legend,
            "mark":              self.handle_mark,
            "unmark":            self.handle_unmark,
            "mv":                self.handle_move_files,
            "clog":              self.handle_clog,
            "clogq":             self.handle_clogq,
            "fn":                self.handle_copy_filename,
            "sc":                self.handle_prepare_for_scan,
            "l":                 self.handle_start_camera,
            "sub":               self.handle_set_subfolder,
            "cob":               self.handle_set_cobolt_power,
            "pp":                self.handle_external_clipboard,
            "cn":                self.handle_start_counter,
            "lpos":              self.handle_load_positions,
            "spos":              self.handle_save_positions,
            "reload":            self.handle_reload,
            "plf":               self.handle_plot_future_femto,
            "ld":                self.handle_load_csv,
            "coords":            self.handle_toggle_coords,
            "coo":               self.handle_toggle_coords,
            "fq":                self.handle_fill_query,
            "findq":             self.handle_find_max_in_area,
            "lastz":             self.handle_move_last_z,
            "xabs":              self.handle_move_abs_x,
            "yabs":              self.handle_move_abs_y,
            "zabs":              self.handle_move_abs_z,
            "down":              self.handle_save_and_down,
            "round":             self.handle_round_position,
            "list":              self.handle_list_points,
            "listzel":           self.handle_list_zelux,
            "zellist":           self.handle_list_zelux,
            "zelshiftx":         self.handle_zel_shift_x,
            "zelshifty":         self.handle_zel_shift_y,
            "clear":             self.handle_clear,
            "shift":             self.handle_shift_point,
            "insert":            self.handle_insert_points,
            "savelist":          self.handle_save_list,
            "loadlist":          self.handle_load_list,
            "gen list":          self.handle_generate_list,
            "genlist":           self.handle_generate_list,
            "spc":               self.handle_acquire_spectrum,
            "hrs":               self.handle_hrs,
            "msg":               self.handle_message,
            "msgclear":          self.handle_message_clear,
            "st":                self.handle_set_xyz,
            "pst":               lambda arg="": self.get_parent().smaractGUI.paste_clipboard_to_moveabs(),
            "paste":             lambda arg="": self.get_parent().smaractGUI.paste_clipboard_to_moveabs(),
            "note":              self.handle_update_note,
            "att":               self.handle_set_attenuator,
            "future":            self.handle_future,
            "fmc":               self.handle_femto_calculate,
            "fmp":               self.handle_femto_pulses,
            "stp":               self.handle_stop_scan,
            "stop":              self.handle_stop_scan,
            "angle":             self.handle_set_angle,
            "start":             self.handle_start_scan,
            "stt":               self.handle_start_scan,
            "kst":               self.handle_start_scan_with_galvo,
            "startscan":         self.handle_start_scan,
            "dx":                self.handle_set_dx,
            "dy":                self.handle_set_dy,
            "dz":                self.handle_toggle_or_set_dz,
            "d":                 self.handle_set_all_steps,
            "lx":                self.handle_set_Lx,
            "ly":                self.handle_set_Ly,
            "lz":                self.handle_set_Lz,
            "savehistory":       self.handle_save_history,
            "savehist":          self.handle_save_history,
            "loadhistory":       self.handle_load_history,
            "loadhist":          self.handle_load_history,
            "delhistory":        self.handle_del_history,
            "delhist":           self.handle_del_history,
            "hist":              self.handle_hist,
            "sv":                self.handle_save_processed_image,
            "shww":              self.handle_list_windows,
            "shw":               self.handle_show_window,
            "hide":              self.handle_hide_window,
            "scpos":             self.handle_copy_scan_position,
            "exp":               self.handle_set_exposure,
            "disp":              self.handle_display_slices,
            "dc":                lambda arg: self.handle_display_slices("clip"),
            "int":               self.handle_set_integration_time,
            "nextrun":           self.handle_nextrun,
            "help":              self.handle_help,
            "wait":              self.handle_wait,
            "ocr":               self.handle_ocr,
            "go":                self.handle_go,
            "move0":             self.handle_move0,
            "move1":             self.handle_move1,
            "move2":             self.handle_move2,
            "movex":             self.handle_moveX,
            "movey":             self.handle_moveY,
            "movez":             self.handle_moveZ,
            "lastdir":           self.handle_open_lastdir,
            "dir":               self.handle_open_lastdir,
            "det":               self.handle_detect_and_draw,
            "fmax":              self.handle_fmax,
            "kfmax":             self.handle_kfmax,
            "ntrack":            self.handle_ntrack,
            "gr":                self.handle_set_graph_size,
            "auto":              self.handle_auto,
            "file":              self.handle_file,
            "copy":              self.handle_copy_last_msg,
            "exit":              self.handle_exit,
            "quit":              self.handle_exit,
            "fillspan":          self.handle_fill_span,
            "enablepp":          self.handle_enablepp,
            "pulsecount":        self.handle_pulsecount,
            "focus":             self.handle_focus,
            "standby":           self.handle_standby,
            "standby?":          self.handle_standby_query,
            "pharos?":           self.handle_standby_query,
            "enable":            self.handle_enable_pharos,
            "enable?":           self.handle_enable_pharos_query,
            "execute":           self.handle_execute,
            "spot":              self.handle_spot,
            "spot1":             self.handle_spot1,
            "ll":                self.handle_lens_toggle,
            "scanmv":            self.handle_scanmv,
            "g2":                self.handle_g2,
            "restore":           self.handle_restore,
            "koff":              self.handle_keysight_offset,
            "kabs":              self.handle_kabs,
            "kx":                self.handle_kx,
            "ky":                self.handle_ky,
            "lf":                self.handle_lf,
            "clearconsole":      self.handle_clear_console,
            "revive":            self.handle_revive_app,
            "close qm":          self.handle_close_qm,
            "qmm":               self.handle_close_qm,
            "up":                self.handle_up,
            "reset":             self.handle_reset_smaract,
            "show":              self.handle_show,
            "collapse":          self.handle_collapse,
            "expand":            self.handle_expand,
            "sym":               self.handle_sym,  # sym start | sym stop | sym status
            "g":                 self.handle_g, # Add a phase grating (carrier) with X,Y periods across the apert
            "coupx":             self.handle_coupx,
            "coupy":             self.handle_coupy,
            "coup":              self.handle_coup,
            "coupon":            self.handle_coupon,
            "cgh":               self.handle_cgh,
            "n":                 self.handle_negative,
            "wv":                self.handle_wv,
            "wave":              self.handle_wv,
            "plot":              self.handle_plot, # show spectrum
            "disable":           self.handle_disable, #disable unused experiments or pharos
            "uv":                self.handle_uv,
            "chip":              self.handle_chip,
            "last":              self.handle_last_message,
            "cr":                self.handle_cr,
            "proem":             self.handle_proem,
            "uz": lambda arg="": self.handle_uvz("uz", arg),
            "vz": lambda arg="": self.handle_uvz("vz", arg),
            "replace":           self.handle_replace,
            "abs":               self.handle_move_abs_xyz,
            "maxi":              self.handle_moveabs_to_max_intensity,
            "copy":              self.handle_copy,
            "addmap":           self.handle_add_map,
        }
        # Register exit hook
        atexit.register(self.savehistory_on_exit)
        # Disable unused experiments
        # self.handle_disable("exp") # BUG HERE !!!
        self.handle_coup("load")
    def get_parent(self):
        return getattr(sys.stdout, "parent", None)
    def _ensure_exec_ns(self):
        # Shared namespace for exec/eval across runs
        if not hasattr(self, "_exec_ns"):
            self._exec_ns = {"parent": self.get_parent()}
        else:
            # keep parent fresh
            self._exec_ns["parent"] = self.get_parent()
        return self._exec_ns
    def run(self, command: str, record_history: bool = True):
        """
            Execute one or more console commands.

            Overview
            --------
            - Accepts a single command or a ';'-separated list and dispatches each
              segment to a registered handler in self.handlers.
            - If no handler matches, supports:
                1) Inline Python helpers: 'import', 'from', 'py', 'py?' executed
                   in a shared namespace returned by _ensure_exec_ns().
                2) History-assisted recall: searches previous commands for a match and
                   replays the most recent one.
                3) Python fallback: tries eval/exec of the raw text.
                4) Shell fallback: runs the text in the OS shell (subprocess).
            - Maintains GUI focus and clears the input widget when done.

            Parameters
            ----------
            command : str
                The raw command line. May contain multiple commands separated by ';'.
                Examples:
                    "xabs10; yabs-5; zabs0"
                    "wait500; opx start"
                    "py dpg.get_value('cmd_input')"
            record_history : bool, default True
                If True, appends the original command line to parent.command_history
                and advances parent.history_index. Set False for internal or replayed
                executions you do not want to store.

            Command Grammar
            ---------------
            A command line is split by ';' into segments:
                segment := verb [SP arg]
                verb    := first token (case-insensitive)
                arg     := the remainder of the segment (may be empty)

            Handler dispatch:
                - The lowercase verb is looked up in self.handlers.
                - If found, handler(arg) is called (with special handling for 'wait').
                - If not found, proceed to Python helpers, history recall, Python
                  fallback, then shell fallback (in that order).

            Special Cases
            -------------
            1) Embedded-number verbs:
                If a segment's verb starts with one of:
                    xabs, yabs, zabs, dx, dy, dz, angle, att, lastz, int
                and there is no exact handler for the full token, the numeric suffix
                is moved into arg and 'verb' is rewritten to the prefix.
                Example:
                    "xabs12"  -> key="xabs", arg="12"
                    "dz-200"  -> key="dz",   arg="-200"

            2) Multi-word verbs:
                - "show windows" is normalized from: key=="show" and arg.lower()=="windows"
                - "gen list"     is normalized from: key=="gen"  and arg.lower()=="list"
                After normalization, key becomes "show windows" or "gen list" with arg="".

            3) 'wait' handler (scheduling):
                - If key=="wait", arg is parsed as milliseconds.
                - The remaining segments are scheduled to run after the delay in a daemon
                  thread (non-blocking). Example:
                      "wait500; xabs10; yabs20"
                  will delay 500 ms, then run the two remaining commands in order.
                - On parse error, prints usage and continues.

            Python Helpers (no handler match)
            ---------------------------------
            The console provides lightweight Python execution in a shared namespace:
                - "import ..." or "from ... import ...":
                    Executes the statement in the shared namespace.
                    Useful for one-time setup, e.g. "import dearpygui.dearpygui as dpg".
                - "py <stmt>":
                    Executes an arbitrary Python statement via exec().
                    Example: "py dpg.set_value('cmd_input','')"
                - "py? <expr>":
                    Evaluates a Python expression via eval() and prints the result.
                    Example: "py? dpg.does_item_exist('cmd_input')"

            Notes:
                - The shared namespace comes from _ensure_exec_ns(). If you need access
                  to the dispatcher or GUI, you can extend that namespace (e.g., inject
                  'self' or 'parent') inside _ensure_exec_ns() or right before exec/eval.
                - If you added ns['self'] = self, you can do:
                      "py self.proEM_mode = False"
                      "py? self.proEM_mode"

            History Recall
            --------------
            If no handler and no Python-helper verb matched:
                - Searches parent.command_history (most-recent-first) for a previous
                  command containing the exact typed segment as a substring, excluding
                  the current segment itself.
                - If found, the matched command is placed back into the input widget,
                  focused, printed as recalled, and immediately executed in the same
                  shared namespace:
                      * If it starts with "import"/"from": exec()
                      * Else if it contains '=' or ';': exec()
                      * Else: eval() and print result if not None
                - If nothing is found, the console proceeds to Python fallback then shell.

            Python Fallback, then Shell
            ---------------------------
            Python fallback:
                - If the segment contains '=', uses exec(); otherwise tries eval().
                - Prints the evaluated result if not None.
                - On failure, prints the Python error and continues to shell.
            Shell fallback:
                - If Python fails, attempts to run the exact text via subprocess.run()
                  with shell=True. Errors are reported to the console.

            GUI Behavior
            ------------
            - If command is empty: focuses "OPX Window" and returns.
            - After processing segments, focuses "OPX Window" and clears the "cmd_input"
              widget (if present).
            - Uses parent.update_command_history(...) and maintains parent.history_index.

            Threading
            ---------
            - The 'loop' meta-command and the 'wait' scheduling both spawn daemon threads:
                * loop worker executes a generated series of commands with a 0.2 s pause.
                * wait schedules remaining segments after a millisecond delay.
              Daemon threads will not block program exit.

            'loop' Meta-command
            -------------------
            Syntax:
                loop <start> <end> <template>
            Behavior:
                - Parses start/end as integers and splits <template> by ';'.
                - For each i in [start, end], runs each subcommand with i substituted
                  only if your template logic uses i (the current implementation prints
                  the index and calls run(sub) directly; you can embed i into sub
                  yourself before invoking, or adapt this block to format templates).
                - Runs in a daemon thread and prints a status line.

            Return Value
            ------------
            None. Results and status are printed to the console. Side effects include:
                - Mutations in UI state via Dear PyGui.
                - Updates to parent.command_history and parent.history_index.
                - Background threads for 'loop' and 'wait'.

            Examples
            --------
            Simple handler:
                "show windows"

            Embedded-number:
                "xabs12; dz-200"

            Multi-word normalization:
                "show windows"
                "gen list"

            Delay with 'wait':
                "wait1000; xabs0; yabs0; zabs0"

            Loop:
                "loop 1 3 xabs10; yabs20"

            Python helpers:
                "import dearpygui.dearpygui as dpg"
                "py dpg.set_value('cmd_input','')"
                "py? dpg.does_item_exist('cmd_input')"

            History recall:
                If you previously ran "opx start acquisition", typing "start acquisition"
                (without quotes) will recall and execute the last matching command.

            Error Handling
            --------------
            - All per-segment execution is wrapped in try/except; Python or shell errors
              are printed but do not crash the console.
            - A top-level try/except around the segment loop also prints a traceback on
              unexpected failures.
        """

        parent = self.get_parent()
        if parent is None:
            print("Warning: run() called but sys.stdout.parent not set.")
            return

        def _refocus():
            if not record_history:
                return
            try:
                dpg.focus_item("cmd_input")
                dpg.set_value("cmd_input", "")
            except Exception:
                pass

        cmd_line = command.strip()
        if not cmd_line:
            _refocus()
            return

        print(f"{cmd_line}")
        # --- NEW: "1" repeats the last command line (entire pipeline) ---
        if cmd_line == "1":
            history = getattr(parent, "command_history", [])
            # Find the last non-empty, non-"1" entry (skip this very call too)
            found = None
            for prev in reversed(history):
                prev_s = (prev or "").strip()
                if prev_s and prev_s != "1":
                    found = prev_s
                    break
            if not found:
                print("No previous command to repeat.")
                _refocus()
                return
            print(f"[repeat] {found}")
            # Re-run it without re-adding to history (avoids infinite loops)
            self.run(found, record_history=False)
            _refocus()
            return

        if not hasattr(parent, "command_history"):
            parent.command_history = []

        if record_history:
            parent.update_command_history(cmd_line)
            parent.history_index = len(parent.command_history)

        # --- '>>' Override Macros (define/override) ---------------------------------
        # Usage:
        #   >> fq next;spc 60      -> overrides key 'f' with that command
        #   >>s spc 30             -> overrides key 's' explicitly
        #   >>f2 fq 1;spc 60       -> overrides numbered key 'f2'
        if cmd_line.startswith(">>"):
            import re
            body_raw = cmd_line[2:]  # drop leading '>>'
            body = body_raw.lstrip()
            if not hasattr(self, "cmd_macros"):
                self.cmd_macros = {}

            # Explicit key form: >>f <command>  or >>f2 <command>
            m = re.match(r"^([A-Za-z]\d*)\s+(.+)$", body, flags=re.DOTALL)
            if m:
                key, payload = m.group(1).lower(), m.group(2).strip()
            else:
                # Infer key from first alphabetic char of the payload
                m2 = re.search(r"[A-Za-z]", body)
                if not m2:
                    print("Nothing to bind after '>>'.")
                    _refocus()
                    return
                key = m2.group(0).lower()
                payload = body

            self.cmd_macros[key] = payload
            print(f"Overridden macro '>{key}': {payload!r}")
            _refocus()
            return
        # ---------------------------------------------------------------------------

        # --- '>' Macro DEFINE (top-level only when '> ' prefix) ----------------------
        # Usage:
        #   > <command...>   -> define new macro (auto-pick first-letter key, auto-number on dup)
        # Notes:
        #   - No define if there's no space after '>' (e.g., '>c' = run, handled in segment loop)
        if cmd_line.startswith(">") and (len(cmd_line) > 1 and cmd_line[1].isspace()):
            import re
            body_raw = cmd_line[1:]  # keep the original to preserve user spacing
            body = body_raw.lstrip()  # normalized payload for key detection

            if not hasattr(self, "cmd_macros"):
                self.cmd_macros = {}

            # Require at least one alphabetic char to determine the base key
            m = re.search(r"[A-Za-z]", body)
            if not m:
                print("Nothing to bind after '>'.")
                _refocus()
                return
            base = m.group(0).lower()

            # Find next free key: base, base2, base3, ...
            existing = [k for k in self.cmd_macros.keys() if re.fullmatch(fr"{base}\d*", k)]
            if base not in existing:
                key = base
            else:
                used_nums = {1}
                for k in existing:
                    suf = k[len(base):]
                    if suf.isdigit():
                        used_nums.add(int(suf))
                key = f"{base}{max(used_nums) + 1}"

            self.cmd_macros[key] = body
            print(f"Saved macro '>{key}': {body!r}")
            _refocus()
            return
        # ---------------------------------------------------------------------------

        # Handle 'loop' specially
        if cmd_line.startswith("loop "):
            parts = cmd_line.split(" ", 3)
            if len(parts) < 4:
                print("Usage: loop <start> <end> <template>")
                return
            try:
                start, end = int(parts[1]), int(parts[2])
                template = parts[3]
            except:
                print("loop: start/end must be integers.")
                return
            def loop_worker():
                for i in range(start, end + 1):
                    for sub in [c.strip() for c in template.split(";") if c.strip()]:
                        print(f"[loop {i}] running: {sub}")
                        self.run(sub)
                        time.sleep(0.2)
            threading.Thread(target=loop_worker, daemon=True).start()
            print(f"Looping from {start} to {end} in background…")
            return

        # Split and dispatch
        segments = [seg.strip() for seg in cmd_line.split(";") if seg.strip()]
        for i, seg in enumerate(segments):
            try:
                verb, *rest = seg.split(" ", 1)
                key = verb.lower()
                arg = rest[0] if rest else ""

                # Handle embedded-number verbs (xabs12, dx200, etc.)
                for prefix in ("xabs","yabs","zabs","dx","dy","dz","angle","att","lastz","int"):
                    if key.startswith(prefix) and prefix not in ("show","help") and key not in self.handlers:
                        arg = key[len(prefix):]; key = prefix
                        break

                # Special multi-word verbs
                if key == "show" and arg.lower()=="windows":
                    key="show windows"; arg=""
                if key=="gen" and arg.lower()=="list":
                    key="gen list"; arg=""

                # handle '>' macro segments inside pipelines (invoke/query/list)
                if key.startswith(">"):
                    import re
                    body = seg[1:].strip()
                    if not hasattr(self, "cmd_macros"):
                        self.cmd_macros = {}

                    # delete one: '>p-' or '>p4-'
                    m = re.fullmatch(r"([A-Za-z]\d*)-", body)
                    if m:
                        k = m.group(1).lower()
                        if hasattr(self, "cmd_macros") and k in self.cmd_macros:
                            del self.cmd_macros[k]
                            print(f"Deleted macro '>{k}'.")
                        else:
                            print(f"No macro bound to '>{k}'.")
                        _refocus()
                        continue

                    # list all: '>?'
                    if body == "?":
                        if not self.cmd_macros:
                            print("No macros defined.")
                        else:
                            print("Macros:")
                            for k in sorted(self.cmd_macros.keys(), key=lambda s: (s[0], len(s), s)):
                                print(f"  >{k}  ->  {self.cmd_macros[k]}")
                        _refocus()
                        continue

                    # query one: '>?f' or '>f?'  (supports digits: f2)
                    m = re.fullmatch(r"\?\s*([A-Za-z]\d*)", body) or re.fullmatch(r"([A-Za-z]\d*)\s*\?", body)
                    if m:
                        k = m.group(1).lower()
                        tgt = self.cmd_macros.get(k)
                        print(f"[>{k}] {tgt}" if tgt else f"No macro bound to '>{k}'.")
                        _refocus()
                        continue

                    # invoke: '>f' or '>f2'
                    if re.fullmatch(r"[A-Za-z]\d*", body or ""):
                        k = body.lower()
                        tgt = self.cmd_macros.get(k)
                        if tgt:
                            print(f"[>{k}] {tgt}")
                            self.run(tgt)
                        else:
                            print(f"No macro bound to '>{k}'. Use '> <command>' to define.")
                        _refocus()
                        continue

                    print("Macro usage: '>X' (run), '>X?' (show), '>?' (list), '>X-' (delete)")
                    _refocus()
                    continue

                handler = self.handlers.get(key)
                if handler:
                    # 'wait' delays subsequent commands
                    if key=="wait":
                        try:
                            ms = int(arg)
                        except:
                            print("Invalid wait syntax; use wait<ms>")
                            continue
                        rest_cmds = segments[i + 1:]
                        def delayed():
                            time.sleep(ms/1000)
                            if rest_cmds:
                                self.run("; ".join(rest_cmds))
                        threading.Thread(target=delayed, daemon=True).start()
                        print(f"Waiting {ms}ms before running {rest_cmds}")
                        break
                    # 'await' waits for a condition, then runs subsequent commands
                    if key == "await":
                        target = (arg or "").strip().lower()
                        rest_cmds = segments[i + 1:]

                        if target == "scan":
                            evt = getattr(self, "_scan_done_evt", None)
                            if not isinstance(evt, threading.Event):
                                evt = threading.Event()
                                self._scan_done_evt = evt

                            def after_scan():
                                print(f"Awaiting SCAN… then running {rest_cmds}")
                                evt.wait()
                                # run as a single pipeline so 'await' continues to gate properly
                                if rest_cmds:
                                    self.run("; ".join(rest_cmds))

                            threading.Thread(target=after_scan, daemon=True).start()
                            break

                        if target == "spc":
                            evt = getattr(self, "_spc_done_evt", None)
                            if not isinstance(evt, threading.Event):
                                evt = threading.Event()
                                self._spc_done_evt = evt

                            def after_spc():
                                print(f"Awaiting SPC… then running {rest_cmds}")
                                evt.wait()
                                if rest_cmds:
                                    self.run("; ".join(rest_cmds), record_history=False)  # ← join + don't re-log

                            threading.Thread(target=after_spc, daemon=True).start()
                            break
                        else:
                            print(f"Unknown await target: {target!r} (try: await spc)")
                            break

                    handler(arg)
                else:
                    # --- NEW: direct Python helpers ---
                    # Usage examples(now super easy)
                    # Import DearPyGui once; persists in the command environment
                    # self.run("import dearpygui.dearpygui as dpg")

                    # Query your tag immediately
                    # self.run("py print(dpg.does_item_exist('cmd_input'))")

                    # You can chain with semicolons too:
                    # self.run("import dearpygui.dearpygui as dpg; py print(dpg.does_item_exist('cmd_input
                    # 2.1 import / from  (persist in shared namespace)
                    if key in ("import", "from"):
                        ns = self._ensure_exec_ns()
                        stmt = f"{key} {arg}".strip()
                        try:
                            exec(stmt, ns)
                            print(f"Executed: {stmt}")
                            _refocus()
                        except Exception as e:
                            print(f"Import failed: {stmt}\n   {e}")
                        continue

                    # 2.2 py <stmt>  (exec arbitrary Python statement in shared namespace)
                    #     py? <expr> (eval expression and print result)
                    if key in ("py", "py?"):
                        ns = self._ensure_exec_ns()
                        ns.setdefault("self", self)  # <-- add
                        ns.setdefault("parent", self.get_parent())  # optional, handy
                        code = arg
                        try:
                            if key == "py":
                                exec(code, ns)
                                _refocus()
                            else:
                                result = eval(code, ns)
                                print(result)
                                _refocus()
                        except Exception as e:
                            print(f"❌ Python error: {e}")
                        continue

                    history = getattr(parent, "command_history", [])
                    # Prefer exact match only
                    matches = [cmd for cmd in reversed(history) if cmd.strip() == seg]

                    # If no exact match, optionally allow substring matches ONLY when the candidate
                    # has no ';' (i.e., it’s a single-segment command). This prevents recalling
                    # 'await spc;>c' for the sub-segment 'await spc'.
                    if not matches:
                        matches = [cmd for cmd in reversed(history)
                                   if (seg in cmd) and (";" not in cmd) and (cmd != seg)]

                    if matches:
                        found = matches[0]
                        _refocus()
                        print(f"Recalled from history: {found}")
                        ns = self._ensure_exec_ns()
                        try:
                            head = found.lstrip()
                            low = head.lower()

                            # Route explicit Python helpers directly
                            if low.startswith("import ") or low.startswith("from "):
                                exec(found, ns)
                                return
                            if low.startswith("py? "):
                                result = eval(found[3:], ns)
                                if result is not None: print(result)
                                return
                            if low.startswith("py "):
                                exec(found[3:], ns)
                                return

                            # For console syntax (await, >, >>, etc.), re-enter the console
                            # without re-logging to avoid loops.
                            # self.run(found, record_history=False)
                            return
                        except Exception as e:
                            print(f"❌ Error while executing recalled command: {e}")
                        return
            except Exception:
                    traceback.print_exc()
            _refocus()

        if record_history:
            self._last_cmd = cmd_line
    def savehistory_on_exit(self):
        try:
            self.handle_save_history()
            print("Command history saved on exit.")
        except Exception as e:
            print(f"Failed to save history on exit: {e}")
    def _refocus_cmd_input(self):
        try:
            dpg.focus_item("cmd_input")
            dpg.set_value("cmd_input", "")
        except Exception:
            pass
    # --- Handlers (methods) ---
    def handle_uv(self, arg: str = ""):
        """
        Show or set the U/V basis vectors.

        Usage:
          uv                      -> print U, V, norms, dot, cross, and rotated U/V
          uv u=[x,y,z]            -> set U to the normalized vector [x,y,z]
          uv v=(x, y, z)          -> set V to the normalized vector (x,y,z)

        Notes:
          - Input may use [] or (), spaces are OK, commas optional (e.g. "u=1 0 0").
          - Vectors are normalized to unit length. Zero-length is rejected.
          - After any change, the rotated basis (by current ch2 angle) is shown.
        """
        parent = self.get_parent()
        if parent is None:
            print("uv: no parent GUI found.")
            return

        try:
            dev = parent.smaractGUI.dev
            smg = parent.smaractGUI  # for _uv_rotated and angle readout
        except Exception:
            print("uv: SmarAct GUI/device not available.")
            return

        # Helper: parse "u=..." or "v=..."
        def _try_parse_vector(s: str):
            import re
            s = s.strip()
            # Accept formats like: u=[1,2,3], u=(1 2 3), u=1, 2, 3, u=1 2 3
            m = re.match(r"^(u|v)\s*=\s*(.*)$", s, flags=re.IGNORECASE)
            if not m:
                return None, None
            which = m.group(1).lower()
            payload = m.group(2).strip()

            # Strip wrapping brackets/parentheses if present
            if (payload.startswith("[") and payload.endswith("]")) or (
                    payload.startswith("(") and payload.endswith(")")):
                payload = payload[1:-1].strip()

            # Split on commas or whitespace
            parts = re.split(r"[,\s]+", payload)
            parts = [p for p in parts if p]  # remove empties

            if len(parts) != 3:
                raise ValueError(f"Expected 3 numbers for {which}=..., got {len(parts)}")

            try:
                vec = [float(p) for p in parts]
            except Exception:
                raise ValueError(f"Could not parse numbers for {which}=... : {parts}")

            return which, vec

        # If arg contains an assignment, set the corresponding vector
        arg = (arg or "").strip()
        if arg:
            try:
                which, vec = _try_parse_vector(arg)
            except ValueError as e:
                print(f"uv: {e}")
                return

            if which is None:
                print("uv: to set, use 'uv u=[x,y,z]' or 'uv v=(x,y,z)'.")
                # fall through to printing current state
            else:
                # Normalize
                import math
                norm = math.sqrt(sum(x * x for x in vec))
                if norm == 0:
                    print(f"uv: cannot set {which} to the zero vector.")
                    return
                vec = [x / norm for x in vec]

                if which == "u":
                    dev.U = vec
                else:
                    dev.V = vec

                print(f"uv: set {which.upper()} to unit vector [{', '.join(f'{x:.6g}' for x in vec)}]")

        # Fetch current U/V (after any update)
        U = getattr(dev, "U", None)
        V = getattr(dev, "V", None)
        if U is None or V is None:
            print("uv: U/V vectors are not set on the device.")
            return

        try:
            U = [float(x) for x in U]
            V = [float(x) for x in V]
        except Exception:
            print(f"uv: could not parse device vectors. U={U}, V={V}")
            return

        # Diagnostics in base frame
        dot = sum(u * v for u, v in zip(U, V))
        nu = (sum(u * u for u in U)) ** 0.5
        nv = (sum(v * v for v in V)) ** 0.5

        cross_str = ""
        if len(U) == 3 and len(V) == 3:
            cx = U[1] * V[2] - U[2] * V[1]
            cy = U[2] * V[0] - U[0] * V[2]
            cz = U[0] * V[1] - U[1] * V[0]
            cross_str = f"\nU×V = [{cx:.6g}, {cy:.6g}, {cz:.6g}]"

        # Rotated basis (by current ch2 angle, via your GUI helper)
        try:
            U_rot, V_rot = smg._uv_rotated()
            angle_deg = smg._get_rot_deg_from_ch2()
            rot_str = (
                f"\n-- rotated by ch2={angle_deg:.3f}° --\n"
                f"U_rot = [{', '.join(f'{x:.6g}' for x in U_rot)}]\n"
                f"V_rot = [{', '.join(f'{x:.6g}' for x in V_rot)}]"
            )
        except Exception:
            rot_str = "\n(rotated basis unavailable)"

        print(
            "== UV basis ==\n"
            f"U = [{', '.join(f'{x:.6g}' for x in U)}]\n"
            f"V = [{', '.join(f'{x:.6g}' for x in V)}]\n"
            f"|U| = {nu:.6g}, |V| = {nv:.6g}, U·V = {dot:.6g}"
            f"{cross_str}"
            f"{rot_str}"
        )
    def _apply_disable_exp_ui(self):  # NEW
        """Hide/delete all experiment buttons except Counter & G2."""  # NEW
        def zap(tag):  # NEW
            if dpg.does_item_exist(tag):  # NEW
                dpg.delete_item(tag)  # NEW

        # Keep: btnOPX_StartCounter, G2 buttons & width input  # NEW
        REMOVE = [  # NEW
            "btnOPX_StartODMR", "btnOPX_StartPulsedODMR", "btnOPX_StartODMR_Bfield",  # NEW
            "btnOPX_StartNuclearFastRot", "btnOPX_StartRABI", "btnOPX_StartNuclearRABI",  # NEW
            "btnOPX_StartNuclearMR", "btnOPX_StartNuclearPolESR",  # NEW
            "btnOPX_StartNuclearLifetimeS0", "btnOPX_StartNuclearLifetimeS1",  # NEW
            "btnOPX_StartNuclearRamsay", "btnOPX_StartHahn",  # NEW
            "btnOPX_StartElectronLifetime", "btnOPX_StartElectron_Coherence",  # NEW
            "btnOPX_PopulationGateTomography", "btnOPX_EntanglementStateTomography",  # NEW
            "btnOPX_Eilons", "btnOPX_RandomBenchmark", "btnOPX_StartTimeBinEntanglement",  # NEW
            "btnPLE", "btnExternalFrequencyScan", "btnAWG_FP_SCAN",  "btnOPX_StartG2Survey",
            "btnOPX_StartElectronCoherence",
        ]  # NEW
        for t in REMOVE:  # NEW
            zap(t)  # NEW
    def _invert_numeric_args(self, cmd: str) -> str:
        """
        Negate every standalone numeric token in 'cmd'.
        Keeps decimal comma and original decimal precision when possible.
        """
        num_pat = re.compile(r'(?<![\w.])([+\-]?\d+(?:[.,]\d+)?)(?![\w.])')

        def repl(m):
            s = m.group(1)
            use_comma = (',' in s)
            # parse
            try:
                v = float(s.replace(',', '.'))
            except Exception:
                return s  # leave unchanged if somehow unparsable
            v = -v  # invert sign

            # preserve integer/decimal formatting
            if ('.' not in s) and (',' not in s):
                out = str(int(round(v)))
            else:
                # keep original number of decimals
                decs = len(s.split(',' if use_comma else '.')[1])
                out = f"{v:.{decs}f}"
            if use_comma:
                out = out.replace('.', ',')
            return out

        return num_pat.sub(repl, cmd)
    def handle_disable(self, arg):  # NEW
        """
        disable commands:
          disable exp            -> hide experiment buttons (keep Counter & G2)
          disable pharos         -> disable Pharos laser output
          disable femto          -> alias of 'disable pharos'
        """  # NEW
        sub = (arg or "").strip().lower()  # NEW
        if not sub:  # NEW
            print("Usage: disable exp | disable pharos | disable femto")  # NEW
            return False  # NEW

        if sub in ("pharos", "femto"):  # NEW
            return self.handle_disable_pharos("")  # delegate; no OPX changes needed  # NEW

        if sub in ("exp", "experiments"):  # if you already implemented 'disable exp'
            # … your existing logic for hiding experiment buttons …
            # e.g., self._exp_disabled = True;
            self._apply_disable_exp_ui()
            print("[disable] Experiments hidden; only Counter and G2 remain.")
            return True

        print("Usage: disable exp | disable pharos | disable femto")  # NEW
        return False  # NEW
    def handle_close_qm(self, arg):
        """Close all Quantum Machines (QM).  Usage: 'close qm' or 'qmm'"""
        try:
            p = self.get_parent()
            p.opx.qmm.close_all_quantum_machines()
            print("QM: closed all quantum machines.")
        except Exception as e:
            print(f"QM close failed: {e}")
    def handle_auto(self, arg):
        """Apply auto‑fit to OPX graph axes: 'auto', 'auto x', 'auto y'."""
        x_tag = "plotImaga_X"
        y_tag = "plotImaga_Y"

        which = arg.strip().lower()
        if which == "x":
            if dpg.does_item_exist(x_tag):
                dpg.fit_axis_data(x_tag)
                print("Auto-fit X applied")
            else:
                print(f"Axis '{x_tag}' not found; skipping.")
        elif which == "y":
            if dpg.does_item_exist(y_tag):
                dpg.fit_axis_data(y_tag)
                print("Auto-fit Y applied")
            else:
                print(f"Axis '{y_tag}' not found; skipping.")
        elif which == "":
            # Fit both axes
            for tag, label in ((x_tag, "X"), (y_tag, "Y")):
                if dpg.does_item_exist(tag):
                    dpg.fit_axis_data(tag)
                    print(f"Auto‑fit {label} applied")
                else:
                    print(f"Axis '{tag}' not found; skipping.")
        else:
            print("Invalid syntax. Use: auto, auto x, or auto y.")
    def handle_g2(self, arg):
        """Start G2 scan or set correlation width (e.g. 'g2 1000')."""
        p = self.get_parent()
        time.sleep(1)

        if not hasattr(p, "opx") or not hasattr(p.opx, "btnStartG2"):
            print("OPX or btnStartG2 not available.")
            return

        arg = str(arg).strip()

        if arg.isdigit():
            # Update correlation width via input field (triggers callback)
            width = int(arg)
            try:
                p.opx.UpdateCorrelationWidth(user_data=width)
                print(f"Correlation width set to {width}")
            except Exception as e:
                print(f"Failed to set correlation width: {e}")
        else:
            try:
                p.opx.btnStartG2()
                print("✅ Started G2 scan.")
            except Exception as e:
                print(f"❌ Failed to start G2 scan: {e}")
    def handle_mark(self, arg):
        """
        Draw a marker on the plotImaga plot.

        Usage:
          mark                           -> mark current OPX stage position (µm)
          mark c | mark center           -> mark the center of the current plot view
          mark proem [px] [py]           -> mark a ProEM pixel using LightField calibration
          mark k | mark g | mark b | mark keysight | mark galvo
                                         -> mark current galvo (kabs) XY position (µm)
                                         -> b = very big
        """
        try:
            PLOT_TAG = "plotImaga"
            X_AXIS_TAG = "plotImaga_X"
            Y_AXIS_TAG = "plotImaga_Y"
            DRAW_LAYER_TAG = "plot_draw_layer"

            # ------- helpers -------
            def _ensure_draw_layer():
                # Create the draw layer on plotImaga if missing
                if not dpg.does_item_exist(DRAW_LAYER_TAG):
                    if not dpg.does_item_exist(PLOT_TAG):
                        print("mark: plotImaga does not exist.")
                        return False
                    dpg.add_draw_layer(parent=PLOT_TAG, tag=DRAW_LAYER_TAG)
                return True

            def _draw_marker(x_um: float, y_um: float, label: str, size: str = "normal"):
                if not _ensure_draw_layer():
                    return
                tag = "temp_cross_marker"
                # clear previous cross parts if present
                for s in ("_h_left", "_h_right", "_v_top", "_v_bottom", "_circle"):
                    if dpg.does_item_exist(tag + s):
                        dpg.delete_item(tag + s)

                if size == "small":
                    gap, length, line_t, circ_t = 0.1, 0.5, 0.05, 1.5
                elif size == "big":
                    gap, length, line_t, circ_t = 1.0, 28.0, 0.6, 3.5  # very big cross
                else:  # normal
                    gap, length, line_t, circ_t = 0.5, 3.0, 0.3, 2.0

                white = (255, 255, 255, 255)
                black = (0, 0, 0, 255)
                yellow = (255, 255, 0, 255)

                dpg.draw_line((x_um - length, y_um), (x_um - gap, y_um), color=white,
                              thickness=line_t, parent=DRAW_LAYER_TAG, tag=tag + "_h_left")
                dpg.draw_line((x_um + gap, y_um), (x_um + length, y_um), color=white,
                              thickness=line_t, parent=DRAW_LAYER_TAG, tag=tag + "_h_right")
                dpg.draw_line((x_um, y_um - length), (x_um, y_um - gap), color=white,
                              thickness=line_t, parent=DRAW_LAYER_TAG, tag=tag + "_v_top")
                dpg.draw_line((x_um, y_um + gap), (x_um, y_um + length), color=white,
                              thickness=line_t, parent=DRAW_LAYER_TAG, tag=tag + "_v_bottom")
                dpg.draw_circle(center=(x_um, y_um), radius=length, color=black,
                                thickness=circ_t, parent=DRAW_LAYER_TAG, tag=tag + "_circle")
                if size == "big":
                    dpg.draw_circle(center=(x_um, y_um), radius=length*2, color=yellow,
                                    thickness=circ_t*2, parent=DRAW_LAYER_TAG, tag=tag + "_yellow_circle")
                print(f"Marked {label} at X={x_um:.4f} µm, Y={y_um:.4f} µm")

            def _get_axis_limits():
                """Get current visible ranges of plotImaga axes."""
                if not (dpg.does_item_exist(X_AXIS_TAG) and dpg.does_item_exist(Y_AXIS_TAG)):
                    print("mark: plotImaga axes not found (plotImaga_X/plotImaga_Y).")
                    return None
                x_min, x_max = dpg.get_axis_limits(X_AXIS_TAG)
                y_min, y_max = dpg.get_axis_limits(Y_AXIS_TAG)
                return (x_min, x_max, y_min, y_max)

            # ------- parse -------
            tokens = (arg or "").strip().split()
            kw = tokens[0].lower() if tokens else ""

            # --- Center-of-plot marking ---
            if kw in ("c", "center", "centre"):
                lims = _get_axis_limits()
                if not lims:
                    return
                x_min, x_max, y_min, y_max = lims
                x_um = 0.5 * (x_min + x_max)
                y_um = 0.5 * (y_min + y_max)
                _draw_marker(x_um, y_um, "center", size = "small")
                return

            # --- ProEM pixel marking ---
            if kw in ("proem", "px", "pixel"):
                px = py = None
                if len(tokens) == 1:
                    pass  # use stored values
                elif len(tokens) == 3:
                    try:
                        px = int(float(tokens[1]))
                        py = int(float(tokens[2]))
                    except Exception:
                        print("mark proem: <px> and <py> must be numbers.")
                        return
                else:
                    print("Usage: mark proem  OR  mark proem <px> <py>")
                    return
                self.mark_proem_pixel(px, py)
                return

            # --- Galvo (kabs) marking ---
            if kw in ("k", "g", "keysight", "galvo"):
                parent = self.get_parent()
                gui = getattr(parent, "keysight_gui", None)
                if not gui or not hasattr(gui, "dev"):
                    print("mark k/g: Keysight AWG GUI/device not available.")
                    return
                try:
                    v1 = float(gui.dev.get_current_voltage(1))
                    v2 = float(gui.dev.get_current_voltage(2))
                    base1 = float(getattr(gui, "base1", 0.0))
                    base2 = float(getattr(gui, "base2", 0.0))
                    volts_per_um = float(getattr(gui, "volts_per_um", 0.128 / 15))
                    kx_ratio = float(getattr(gui, "kx_ratio", 3.3))
                    ky_ratio = float(getattr(gui, "ky_ratio", -0.3))

                    dv1 = v1 - base1
                    dv2 = v2 - base2
                    denom = (kx_ratio - ky_ratio)
                    if abs(denom) < 1e-12:
                        print("mark k/g: ill-conditioned kx/ky ratios.")
                        return

                    alpha_x_volts = (dv2 - dv1 * ky_ratio) / denom
                    beta_y_volts = (dv2 - dv1 * kx_ratio) / (ky_ratio - kx_ratio)
                    x_um = alpha_x_volts / volts_per_um
                    y_um = beta_y_volts / volts_per_um

                    size = "small" if kw == "g" else ("big" if kw == "b" else "normal")
                    _draw_marker(x_um, y_um, "galvo (kabs)", size=size)
                    return
                except Exception as e:
                    print(f"mark k/g failed: {e}")
                    return

            # --- Default: mark current OPX stage XY (µm) ---
            parent = self.get_parent()
            x_um, y_um = [p * 1e-6 for p in parent.opx.positioner.AxesPositions[:2]]
            size = "small" if kw == "g" else ("big" if kw == "b" else "normal")
            _draw_marker(x_um, y_um, "stage",size=size)

        except Exception as e:
            traceback.print_exc()
            print(f"Error in mark: {e}")
    def handle_unmark(self, arg):
        """Remove the temporary marker."""
        try:
            tag = "temp_cross_marker"
            removed = False
            for s in ("_h_left","_h_right","_v_top","_v_bottom","_circle"):
                t = tag+s
                if dpg.does_item_exist(t):
                    dpg.delete_item(t)
                    removed = True
            print("Marker cleared." if removed else "No marker to clear.")
        except Exception as e:
            print(f"Error in unmark: {e}")
    def handle_add_slide(self, arg):
        """
        Command: a [option]
        --------------------
        Adds a new slide to the currently opened PowerPoint presentation, pastes the GUI window as an image,
        and embeds relevant metadata in the image's Alt Text (as a compact JSON string).

        Usage:
            a           → Full metadata: scan grid, position (µm), future command, filename.
            a 1         → Minimal metadata: only position, future, and filename (no scan_data).
            a 2 or a g2 → Add G2 graph data: X_vec, Y_vec, g2 result, iteration, total counts.
            a 3         → Add stored query points: [(index, x, y, z), ...].
            a 5 or a spc→ Add HRS500 spectrum data and associated CSV file path.

        Metadata Fields:
            x, y               : Stage position in microns (float)
            future             : String from Femto_FutureInput (optional)
            filename           : Path to last loaded scan CSV
            Nx, Ny, Nz         : Scan dimensions (int)
            startLoc           : Starting scan location [x, y, z]
            dL_scan            : Step size per axis [dx, dy, dz]
            scan_data          : Converted scan CSV as nested dict (excluded if option 1/2/3/5 used)
            g2_graph           : Dict with X_vec, Y_vec, g2_value, iteration, total_counts (only with a 2 / g2)
            query_points       : Stored points (list of tuples) (only with a 3)
            spc_csv            : Path to last saved SPC spectrum (only with a 5 / spc)
            spc_data           : Dict with x and y arrays of SPC spectrum (only with a 5 / spc)

        Notes:
            - Metadata is embedded in the Alt Text of the pasted image.
            - Useful for later recovery using `disp clip`.
            - All JSON is minified (compact separators) to reduce Alt Text size.

        Example:
            a       → Full metadata
            a 1     → Just core info, no scan_data
            a g2    → Include G2 result graph
            a 3     → Include stored query points
            a spc   → Include SPC spectrum (data + filename)
        """

        try:
            p = self.get_parent()
            meta = {}

            # Always include core metadata
            meta["x"], meta["y"] = [pos * 1e-6 for pos in p.opx.positioner.AxesPositions[:2]]
            meta["future"] = dpg.get_value(FemtoPowerCalculator.future_input_tag) if dpg.does_item_exist(FemtoPowerCalculator.future_input_tag) else None
            meta["filename"] = getattr(p.opx, "last_loaded_file", None)

            arg = arg.strip().lower() if arg else ""
            include_graph = arg in ("2", "g2")
            include_query_list = arg == "3"
            include_spc = arg in ("5", "spc")

            # Add scan structure (but not raw scan_Out) unless user passed 1/2/3/5/spc
            if arg not in ("1", "2", "g2", "3", "5", "spc"):
                try:
                    scan_out = getattr(p.opx, "scan_Out", None)
                    Nx, Ny, Nz = tuple(getattr(p.opx, "N_scan", (0, 0, 0)))
                    startLoc = getattr(p.opx, "startLoc", None)
                    dL_scan = getattr(p.opx, "dL_scan", None)

                    # only include scan_data if scan_Out is a 2D array with at least 2 columns
                    if isinstance(scan_out, np.ndarray) and scan_out.ndim >= 2 and scan_out.shape[1] >= 2:
                        meta.update({
                            "Nx": Nx,
                            "Ny": Ny,
                            "Nz": Nz,
                            "startLoc": startLoc,
                            "dL_scan": dL_scan,
                        })
                        meta["scan_data"] = self.convert_loaded_csv_to_scan_data(
                            scan_out=scan_out,
                            Nx=Nx,
                            Ny=Ny,
                            Nz=Nz,
                            startLoc=startLoc,
                            dL_scan=dL_scan,
                        )
                    # else: silently skip scan_data when shape is incompatible
                except Exception as e:
                    print(f"Skipping scan_data: {e}")

            # Include G2 graph
            # Include G2 graph
            if arg.strip() in ("2", "g2"):
                meta["g2_graph"] = {
                    "X_vec": p.opx.X_vec.tolist() if isinstance(p.opx.X_vec, np.ndarray) else list(p.opx.X_vec),
                    "Y_vec": p.opx.Y_vec.tolist() if isinstance(p.opx.Y_vec, np.ndarray) else list(p.opx.Y_vec),
                    "g2_value": float(p.opx.calculate_g2(p.opx.Y_vec)),
                    "iteration": int(p.opx.iteration),
                    "total_counts": int(p.opx.g2_totalCounts)
                }

            # Include query points
            if include_query_list and hasattr(p, "saved_query_points"):
                meta["query_points"] = p.saved_query_points

            # Include SPC data and file
            if include_spc:
                spc_fp = getattr(p.hrs_500_gui.dev, "last_saved_csv", None)
                spc_data = getattr(p.hrs_500_gui, "data", None)
                if spc_fp:
                    meta["spc_csv"] = spc_fp
                if isinstance(spc_data, np.ndarray) and spc_data.ndim >= 2 and spc_data.shape[1] >= 2:
                    meta["spc_data"] = {
                        "x": spc_data[:, 0].tolist(),
                        "y": spc_data[:, 1].tolist()
                    }

            # Copy annotated image to clipboard
            copy_quti_window_to_clipboard(metadata_dict=meta)
            time.sleep(0.1)
            # Insert slide
            pythoncom.CoInitialize()
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                raise RuntimeError("No PowerPoint presentations are open!")
            pres = ppt.ActivePresentation
            new_slide = pres.Slides.Add(pres.Slides.Count + 1, 12)
            try:
                ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)
            except Exception as e:
                print(f"[a] GotoSlide skipped: {e}")

            # Paste image and embed Alt Text metadata
            img = ImageGrab.grabclipboard()
            if not isinstance(img, Image.Image):
                print("Clipboard does not contain an image.")
                return
            shapes = new_slide.Shapes.Paste()
            if shapes.Count > 0:
                shape = shapes[0]
                shape.AlternativeText = json.dumps(meta, separators=(",", ":"))

            print(f"Added slide #{new_slide.SlideIndex} with metadata.")

        except Exception as e:
            print(f"Could not add slide: {e}")
    def convert_loaded_csv_to_scan_data(self,scan_out, Nx, Ny, Nz, startLoc, dL_scan):
        """
        Reconstructs scan_data dictionary (x, y, z, I) from scan_Out and dimensions.
        Returns a JSON-serializable dict ready for clipboard embedding.
        """

        # Flattened arrays
        scan_out = np.array(scan_out)
        I = scan_out[:, 3]

        # Ensure numeric types
        startLoc = list(map(float, startLoc))
        dL_scan = list(map(float, dL_scan))

        # Generate axes using start location and spacing
        x = np.linspace(startLoc[0], startLoc[0] + dL_scan[0] * (Nx - 1) / 1e3, Nx)
        y = np.linspace(startLoc[1], startLoc[1] + dL_scan[1] * (Ny - 1) / 1e3, Ny)
        z = np.linspace(startLoc[2], startLoc[2] + dL_scan[2] * (Nz - 1) / 1e3, Nz)

        print(f"Nx = {Nx}, Ny = {Ny}, Nz = {Nz}, I size = {len(I)}")
        expected_size = Nx * Ny * Nz
        if len(I) < expected_size:
            print("⚠️ Not enough data to reshape — adjust dimensions")
            return

        # Reshape intensity to match grid
        I_reshaped = I[:Nx * Ny * Nz].reshape((Nz, Ny, Nx))

        return {
            "x": x.tolist(),
            "y": y.tolist(),
            "z": z.tolist(),
            "I": I_reshaped.tolist()
        }
    def handle_copy_window(self, arg):
        """Copy QuTi SW window to clipboard."""
        try:
            p = self.get_parent()

            scan_dict = self.convert_loaded_csv_to_scan_data(
                scan_out=p.opx.scan_Out,
                Nx=p.opx.N_scan[0],
                Ny=p.opx.N_scan[1],
                Nz=p.opx.N_scan[2],
                startLoc=p.opx.startLoc,
                dL_scan=p.opx.dL_scan,
            )
            meta = {"scan_data": json.dumps(scan_dict, separators=(",", ":"))}

            copy_quti_window_to_clipboard(metadata_dict=meta)
            print("Window copied to clipboard with scan_data.")
        except Exception as e:
            print(f"Copy window failed: {e}")
    def handle_set_graph_size(self, arg):
        """Set OPX graph width and height: gr<width> or gr<width>,<height>; no arg resets to defaults. e.g. gr 1100"""
        tag = "plotImaga"
        # 1) Ensure the graph exists
        if not dpg.does_item_exist(tag):
            print(f"Graph tag '{tag}' not found.")
            return

        # 2) On first call, capture the default size
        # Initialize or refresh default size if missing or incomplete
        if (not hasattr(self, "default_graph_size")
                or self.default_graph_size is None
                or self.default_graph_size[0] is None
                or self.default_graph_size[1] is None):
            try:
                default_w = dpg.get_item_width(tag)
                default_h = dpg.get_item_height(tag)
            except Exception:
                default_w, default_h = None, None
            self.default_graph_size = (default_w, default_h)

        # 3) No args → reset to default size
        if not arg.strip():
            default_w, default_h = self.default_graph_size
            if default_w is None or default_h is None:
                print("Default graph size is unknown; cannot reset.")
                return
            dpg.set_item_width(tag, default_w)
            dpg.set_item_height(tag, default_h)
            print(f"Graph size reset to default: {default_w}×{default_h}")
            return

        # 4) Parse width and optional height
        parts = arg.strip().split(",", 1)
        try:
            w = int(parts[0])
        except ValueError:
            print("Invalid syntax. Use: gr<width> or gr<width>,<height>, e.g. gr100 or gr100,200")
            return

        if len(parts) > 1 and parts[1].strip():
            try:
                h = int(parts[1])
            except ValueError:
                print("Invalid syntax. Use: gr<width> or gr<width>,<height>, e.g. gr100 or gr100,200")
                return
        else:
            # Only width specified → keep default height
            _, default_h = self.default_graph_size
            if default_h is None:
                print("Default graph height is unknown; cannot set width only.")
                return
            h = default_h

        # 5) Apply the new size
        dpg.set_item_width(tag, w)
        dpg.set_item_height(tag, h)
        print(f"Graph size set to {w}×{h}")
        self.get_parent().opx.graph_size_override = (w, h)  # ✅ Store override for future redraws
    def handle_screenshot_delayed(self, arg):
        """Schedule a delayed screenshot (cc) with optional suffix."""
        p = self.get_parent()
        notes = getattr(getattr(p, "opx", None), "expNotes", None)
        user_suffix = arg.strip()
        # replicate original suffix logic
        if user_suffix and notes:
            suffix = f"{user_suffix}_{notes}"
        elif user_suffix:
            suffix = user_suffix
        elif notes:
            suffix = notes
        else:
            suffix = None
        print(f"cc: scheduling screenshot{' with suffix ' + suffix if suffix else ''}")
        def delayed_save():
            try:
                save_quti_window_screenshot(suffix)
                # print("cc: delayed save complete.")
            except Exception as e:
                print(f"cc: delayed save failed: {e}")

        timer = threading.Timer(0.3, delayed_save)
        timer.daemon = True
        timer.start()
        print("cc: screenshot scheduled in ~0.3 s")
    def handle_hide_legend(self, arg):
        """Hide OPX legend."""
        p = self.get_parent()
        if hasattr(p, "opx") and hasattr(p.opx, "hide_legend"):
            p.opx.hide_legend(); print("Legend hidden.")
        else:
            print("Cannot hide legend.")
    def handle_toggle_sc(self, reverse=False):
        """Start/stop camera & flippers."""
        p = self.get_parent()
        try:
            cam = getattr(p, "cam", None)
            if cam:
                if reverse:
                    cam.StartLive(); print("Camera started."); p.opx.btnStartCounterLive()
                else:
                    if hasattr(cam, "LiveTh") and cam.LiveTh is not None:
                        cam.StopLive();  print("Camera stopped.")
            for flipper in getattr(p, "mff_101_gui", []):
                if flipper.serial_number[-2:] == '32':
                    print("Skipping M32 flipper toggle")
                    continue
                tag = f"on_off_slider_{flipper.unique_id}"
                pos = flipper.dev.get_position()
                if (not reverse and pos==1) or (reverse and pos==2):
                    flipper.on_off_slider_callback(tag, 1 if not reverse else 0)
        except Exception as e:
            print(f"toggle_sc error: {e}")
    def handle_move_files(self, arg):
        """Move last saved files."""
        self.get_parent().opx.move_last_saved_files()
    def handle_clog(self, arg):
        """Run clog.py."""
        try:
            result = subprocess.run(
                [sys.executable, "clog.py", arg.strip().lower()],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            if result.stdout:
                print(result.stdout)
        except Exception as e:
            print(f"clog failed: {e}")
    def handle_clogq(self, arg):
        """Run clog.py with 'q' prefix."""
        try:
            full_arg = f"q{arg.strip()}"
            result = subprocess.run(
                [sys.executable, "clog.py", full_arg],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True
            )
            if result.stdout:
                print(result.stdout)
        except Exception as e:
            print(f"clogq failed: {e}")
    def handle_copy_filename(self, arg):
        """Copy the most-recently logged filepath (with a slash) to the clipboard."""
        msgs = getattr(sys.stdout, "messages", [])
        if not msgs:
            print("No messages to parse.")
            return

        path = None
        # 1) First pass: look for any path matching drive-letter or leading slash
        path_regex = re.compile(r'(?:[A-Za-z]:[\\/]|[/\\]).+?\.\w+')
        for message in reversed(msgs):
            matches = path_regex.findall(message)
            if matches:
                path = matches[-1]
                break

        # 2) Fallback: look for tokens containing both a dot and a slash
        if not path:
            for message in reversed(msgs):
                for tok in message.split():
                    tok_stripped = tok.strip('"\',;')
                    if '.' in tok_stripped and ('/' in tok_stripped or '\\' in tok_stripped):
                        path = tok_stripped
                        break
                if path:
                    break

        if path:
            pyperclip.copy(path)
            print(f"Filename copied: {path}")
        else:
            print("No valid filepath found in recent messages.")
    def handle_set_subfolder(self, arg):
        """Set subfolder for scans."""
        p = self.get_parent()
        try:
            dpg.set_value("MoveSubfolderInput", arg.strip())
            with open("last_scan_dir.txt","w") as f: f.write(arg.strip())
            print(f"Subfolder set: {arg.strip()}")
        except Exception as e:
            print(f"Error in sub: {e}")
    def handle_set_cobolt_power(self, arg):
        """Set Cobolt laser power."""
        p = self.get_parent()
        try:
            mw = float(arg); p.coboltGUI.laser.set_modulation_power(mw)
            print(f"Cobolt power set to {mw:.2f} mW")
        except Exception as e:
            print(f"cob failed: {e}")
    def handle_external_clipboard(self, arg):
        """Launch external clipboard script."""
        try:
            subprocess.Popen([sys.executable,"copy_window_to_clipboard.py"])
            print("Clipboard script launched.")
        except Exception as e:
            print(f"pp failed: {e}")
    def handle_start_counter(self, arg=""):
        """Start counter live."""
        p = self.get_parent()
        try:
            if not p.opx.counter_is_live:
                p.opx.btnStartCounterLive()
            print("Counter live started.")
        except:
            print("Counter start failed.")
    def handle_load_positions(self, arg):
        """Load window positions profile.

        Usage:
          lpos                 -> load 'local'
          lpos r               -> load 'remote'
          lpos <name>          -> load profile <name>
          lpos !<main_tag>     -> load 'local' + resize main window/viewport using size in file
          lpos <name> !<tag>   -> load <name> + resize main window/viewport using size in file
          (example: lpos !console)
        """
        p = self.get_parent()
        raw = (arg or "").strip()

        # parse profile + optional '!main_tag'
        include_main = False
        main_tag = None
        tokens = [t for t in raw.split() if t]
        prof = None
        for t in tokens:
            if t.startswith("!"):
                include_main = True
                main_tag = t[1:] or None
            else:
                prof = t

        profile = "local" if not prof else ("remote" if prof.lower() == "r" else prof)

        if hasattr(p, "smaractGUI"):
            try:
                p.smaractGUI.load_pos(profile, include_main=include_main, main_tag=main_tag)
                print("Loaded positions." + (" (incl. main window size)" if include_main else ""))
            except Exception as e:
                print(f"Error loading positions: {e}")
        else:
            print("smaractGUI not available.")
    def handle_save_positions(self, arg):
        """Save window positions profile."""
        p = self.get_parent()
        prof = arg.strip() or ("remote" if is_remote_resolution() else "local")
        try:
            p.smaractGUI.save_pos(prof)
            print(f"Positions saved: {prof}")
        except:
            print("Save positions failed.")
    def handle_reload(self, arg):
        """
            Reload modules or specific GUI components.

            Usage
            -----
              reload <option>

            Examples
            --------
              reload keys
              reload mattise
              reload wlm / wavemeter
              reload zelux
              reload femto
              reload opx
              reload kdc_101
              reload smaract
              reload hrs_proem
              reload hrs
              reload keysight_awg
              reload cld1011lp
              reload disp
              reload GUI_MyWidget         # → reloads HW_GUI.GUI_MyWidget
              reload my.custom.module     # → generic importlib reload
              reload                      # → defaults to module 'CommandDispatcher'

            Options (synonyms) & What They Do
            ---------------------------------
            keys
              • Rebuilds the global key press handler (tag: "key_press_handler").
              • Deletes the old handler if present, then registers a new one bound to p.Callback_key_press.

            gui_zelux, zel, zelux
              • Reloads HW_GUI.GUI_Zelux.
              • Deletes the existing Zelux window (if present) while saving its position/size.
              • Creates a new ZeluxGUI, re-adds its "bring window" button (tag "Zelux_button"),
                appends to p.active_instrument_list.
              • If cameras are available, (re)adds the window, rebuilds controls ("ZeluxControls"),
                and restores geometry.
              • Recreates MFF-101 flipper GUIs for all devices in hw_devices.HW_devices().mff_101_list.

            femto, femto_gui
              • Reloads HW_GUI.GUI_Femto_Power_Calculations.
              • Removes the old Femto GUI (saving position/size), instantiates FemtoPowerCalculator(p.kdc_101_gui),
                calls create_gui(), re-adds "Femto_button", restores geometry, and tracks as active.

            opx
              • Reloads HWrap_OPX.
              • Removes old OPX GUI (saving position/size), instantiates wrap_OPX.GUI_OPX(),
                calls controls(), re-adds "OPX_button", calls p.create_sequencer_button(),
                restores geometry, and tracks as active.

            kdc, kdc_101
              • Reloads HW_GUI.GUI_KDC101.
              • Removes old KDC GUI (saving position/size).
              • Creates GUI_KDC101 with serial_number taken from the previous GUI
                and device from hw_devices.HW_devices().kdc_101.
              • Re-adds "kdc_101_button", restores geometry, and tracks as active.

            smaract, smaract_gui
              • Reloads HW_GUI.GUI_Smaract.
              • Removes old Smaract GUI (saving position/size).
              • Creates GUI_smaract(simulation=p.smaractGUI.simulation,
                serial_number=p.smaractGUI.selectedDevice), calls create_gui(),
                re-adds "Smaract_button", restores geometry, and tracks as active.
              • If not in simulation, starts p.smaract_thread targeting p.render_smaract.

            hrs proem, hrs_proem, hrsproem, proem
              • Reloads HW_GUI.GUI_HRS_500 for the ProEM LightField experiment.
              • Disconnects any existing devs.hrs_500 (if possible).
              • Creates a new LightFieldSpectrometer(visible=True, file_path="...ProEM_shai.lfe"),
                connects it, and builds GUI_HRS500 with that device.
              • Re-adds "HRS_500_button" (label "Spectrometer (ProEM)"), restores geometry, tracks as active.

            hrs, hrs500, hrs_500
              • Reloads HW_GUI.GUI_HRS_500 (standard path).
              • Removes old GUI (saving position/size), creates GUI_HRS500(hw_devices.HW_devices().hrs_500),
                re-adds "HRS_500_button" (label "Spectrometer"), restores geometry, tracks as active.

            keysight, awg, keysight_awg
              • Reloads HW_GUI.GUI_keysight_AWG.
              • If an old GUI exists, preserves pos/size, device, and simulation; deletes its window tag.
              • Creates GUIKeysight33500B(device=<preserved or default>, simulation=<preserved or False>),
                re-adds "keysight_button" (label "KEYSIGHT_AWG"), restores geometry, tracks as active.

            cld, cld1011, cld1011lp
              • Reloads HW_GUI.GUI_CLD1011LP and tries to reload the wrapper HW_wrapper.Wrapper_CLD1011.
              • Attempts to reuse HW_devices().CLD1011LP; if missing, tries to (re)create it.
              • Deletes old GUI by window tag (no DeleteMainWindow), then creates GUI_CLD1011LP(simulation=<device.simulation or False>).
              • Re-adds "CLD1011LP_button", restores geometry, tracks as active.

            mattise, matisse
              • Reloads HW_GUI.GUI_Matisse and recreates GUIMatisse with hw_devices.HW_devices().matisse_device.
              • Preserves window geometry and rebuilds "MATTISE_button".

            wavemeter, wlm
              • Reloads HW_GUI.GUI_Wavemeter and recreates GUIWavemeter with hw_devices.HW_devices().wavemeter.
              • Preserves window geometry and rebuilds "WAVEMETER_button".

            disp, display_slices, zslider, zslice
              • Reloads Utils.display_all_z_slices_with_slider and rebinds:
                  p.display_all_z_slices = display_all_z_slices

            GUI_* (prefix match)
              • If the argument starts with "GUI_", it is resolved as "HW_GUI.<ARG>" (e.g., GUI_Zelux → HW_GUI.GUI_Zelux)
                and then reloaded.

            <module> (generic)
              • If the argument is any other module name:
                  - If it's already imported (in sys.modules), importlib.reload() is used.
                  - Otherwise, importlib.import_module() is used.
              • With no argument, reloads "CommandDispatcher".

            Behavior & Side Effects
            -----------------------
              • Most GUI paths attempt to preserve window geometry by reading the old window's position and size,
                deleting the window/GUI, then restoring geometry on the newly created GUI.
              • Each GUI path re-creates its "bring window" button with a fixed tag:
                  - Zelux_button, Femto_button, OPX_button, kdc_101_button,
                    Smaract_button, HRS_500_button, keysight_button, CLD1011LP_button
                and appends the window tag to p.active_instrument_list.
              • Smaract spawns a rendering thread when not in simulation.
              • ProEM path sets up a LightFieldSpectrometer with a specific .lfe experiment file.

            Errors
            ------
              • Any exception prints a full traceback and "Reload failed for '<module_name>'".
              • Some geometry restoration calls are wrapped in try/except and may be skipped if the window/tag is absent.

        """

        p = self.get_parent()
        try:
            import importlib
            raw_name = arg.strip()
            name = raw_name.lower()

            self.handle_save_history(None)

            # === reload keys ===
            if name == "keys":
                handler_tag = "key_press_handler"
                if dpg.does_item_exist(handler_tag):
                    dpg.delete_item(handler_tag)
                    print(f"[reload keys] Deleted existing key press handler: {handler_tag}")
                with dpg.handler_registry():
                    dpg.add_key_press_handler(callback=p.Callback_key_press, tag=handler_tag)
                print(f"[reload keys] Added new key press handler: {handler_tag}")
                return

            # Determine module name for generic reload
            if not raw_name:
                module_name = "CommandDispatcher"
            elif raw_name.startswith("GUI_"):
                module_name = f"HW_GUI.{raw_name}"
            else:
                module_name = raw_name

            print(f"Trying to reload: {module_name}")

            # === GUI_Zelux ===
            if name in ("gui_zelux", "zel", "zelux"):
                import HW_GUI.GUI_Zelux as gui_Zelux
                importlib.reload(gui_Zelux)
                # Cleanup old window
                if hasattr(p, "cam") and p.cam:
                    try:
                        pos = dpg.get_item_pos(p.cam.window_tag)
                        size = dpg.get_item_rect_size(p.cam.window_tag)
                        p.cam.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old window removal failed: {e}")
                # Recreate
                p.cam = gui_Zelux.ZeluxGUI()
                if dpg.does_item_exist("Zelux_button"):
                    dpg.delete_item("Zelux_button")
                p.create_bring_window_button(
                    p.cam.window_tag, button_label="Zelux",
                    tag="Zelux_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.cam.window_tag)
                # Restore controls & position
                if getattr(p.cam, "cam", None) and p.cam.cam.available_cameras:
                    if not dpg.does_item_exist(p.cam.window_tag):
                        p.cam.AddNewWindow()
                    if dpg.does_item_exist("ZeluxControls"):
                        dpg.delete_item("ZeluxControls")
                    p.cam.Controls()
                    dpg.set_item_pos(p.cam.window_tag, pos)
                    dpg.set_item_width(p.cam.window_tag, size[0])
                    dpg.set_item_height(p.cam.window_tag, size[1])
                # Recreate MFF flippers
                p.mff_101_gui = []
                for flipper in hw_devices.HW_devices().mff_101_list:
                    mff_gui = GUI_MFF(serial_number=flipper.serial_no, device=flipper)
                    p.mff_101_gui.append(mff_gui)
                print("Reloaded HW_GUI.GUI_Zelux and recreated ZeluxGUI.")
                return

            # === MATTISE GUI ===
            if name in ("mattise", "matisse"):
                import HW_GUI.GUI_mattise as gui_Matisse
                import importlib
                importlib.reload(gui_Matisse)

                # preserve geometry if exists
                pos, size = [60, 60], [900, 500]
                old = getattr(p, "mattise_gui", None)
                if old:
                    try:
                        pos = dpg.get_item_pos(old.window_tag)
                        size = dpg.get_item_rect_size(old.window_tag)
                        # safest is to delete window tag (some GUIs don’t implement DeleteMainWindow)
                        dpg.delete_item(old.window_tag)
                    except Exception as e:
                        print(f"Old MATTISE GUI removal failed: {e}")

                # (re)create device and GUI
                devs = hw_devices.HW_devices()
                device = getattr(devs, "matisse_device", None)
                sim = bool(getattr(old, "simulation", False)) if old else bool(getattr(device, "simulation", False))

                p.mattise_gui = gui_Matisse.GUIMatisse(device=device, simulation=sim)

                # rebuild bring-window button
                if dpg.does_item_exist("MATTISE_button"):
                    dpg.delete_item("MATTISE_button")
                p.create_bring_window_button(
                    p.mattise_gui.window_tag, button_label="MATTISE",
                    tag="MATTISE_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.mattise_gui.window_tag)

                # restore geometry
                try:
                    dpg.set_item_pos(p.mattise_gui.window_tag, pos)
                    dpg.set_item_width(p.mattise_gui.window_tag, size[0])
                    dpg.set_item_height(p.mattise_gui.window_tag, size[1])
                except Exception:
                    pass

                print("Reloaded HW_GUI.GUI_Matisse and recreated GUIMatisse.")
                return

            # === WAVEMETER GUI ===
            if name in ("wavemeter", "wlm"):
                import HW_GUI.GUI_Wavemeter as gui_WLM
                import importlib
                importlib.reload(gui_WLM)

                # preserve geometry if exists
                pos, size = [60, 60], [900, 420]
                old = getattr(p, "wlm_gui", None)
                if old:
                    try:
                        pos = dpg.get_item_pos(old.window_tag)
                        size = dpg.get_item_rect_size(old.window_tag)
                        dpg.delete_item(old.window_tag)
                    except Exception as e:
                        print(f"Old WAVEMETER GUI removal failed: {e}")

                devs = hw_devices.HW_devices()
                device = getattr(devs, "wavemeter", None)
                sim = bool(getattr(old, "simulation", False)) if old else bool(getattr(device, "simulation", False))

                # Some builds require an Instruments enum; try to pass it if available.
                try:
                    from HW_wrapper.HW_devices import Instruments
                    p.wlm_gui = gui_WLM.GUIWavemeter(device=device, instrument=Instruments.WAVEMETER, simulation=sim)
                except Exception:
                    # fallback without instrument arg
                    p.wlm_gui = gui_WLM.GUIWavemeter(device=device, simulation=sim)

                if dpg.does_item_exist("WAVEMETER_button"):
                    dpg.delete_item("WAVEMETER_button")
                p.create_bring_window_button(
                    p.wlm_gui.window_tag, button_label="WAVEMETER",
                    tag="WAVEMETER_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.wlm_gui.window_tag)

                try:
                    dpg.set_item_pos(p.wlm_gui.window_tag, pos)
                    dpg.set_item_width(p.wlm_gui.window_tag, size[0])
                    dpg.set_item_height(p.wlm_gui.window_tag, size[1])
                except Exception:
                    pass

                print("Reloaded HW_GUI.GUI_Wavemeter and recreated GUIWavemeter.")
                return

            # === Femto GUI ===
            if name in ("femto", "femto_gui"):
                import HW_GUI.GUI_Femto_Power_Calculations as gui_Femto
                importlib.reload(gui_Femto)
                if hasattr(p, "femto_gui") and p.femto_gui:
                    try:
                        pos = dpg.get_item_pos(p.femto_gui.window_tag)
                        size = dpg.get_item_rect_size(p.femto_gui.window_tag)
                        p.femto_gui.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old Femto GUI removal failed: {e}")
                p.femto_gui = gui_Femto.FemtoPowerCalculator(p.kdc_101_gui)
                p.femto_gui.create_gui()
                if dpg.does_item_exist("Femto_button"):
                    dpg.delete_item("Femto_button")
                p.create_bring_window_button(
                    p.femto_gui.window_tag, button_label="Femto",
                    tag="Femto_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.femto_gui.window_tag)
                dpg.set_item_pos(p.femto_gui.window_tag, pos)
                dpg.set_item_width(p.femto_gui.window_tag, size[0])
                dpg.set_item_height(p.femto_gui.window_tag, size[1])
                print("Reloaded HW_GUI.GUI_Femto and recreated FemtoPowerCalculator.")
                return

            # === OPX GUI ===
            if name == "opx":
                import HWrap_OPX as wrap_OPX
                importlib.reload(wrap_OPX)
                if hasattr(p, "opx") and p.opx:
                    try:
                        pos = dpg.get_item_pos(p.opx.window_tag)
                        size = dpg.get_item_rect_size(p.opx.window_tag)
                        p.opx.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old OPX GUI removal failed: {e}")
                p.opx = wrap_OPX.GUI_OPX()
                p.opx.controls()
                if dpg.does_item_exist("OPX_button"):
                    dpg.delete_item("OPX_button")
                p.create_bring_window_button(
                    p.opx.window_tag, button_label="OPX",
                    tag="OPX_button", parent="focus_group"
                )
                p.create_sequencer_button()
                p.active_instrument_list.append(p.opx.window_tag)
                dpg.set_item_pos(p.opx.window_tag, pos)
                dpg.set_item_width(p.opx.window_tag, size[0])
                dpg.set_item_height(p.opx.window_tag, size[1])
                print("Reloaded HWrap_OPX and recreated GUI_OPX.")
                return

            # === KDC_101 GUI ===
            if name in ("kdc", "kdc_101"):
                import HW_GUI.GUI_KDC101 as gui_KDC
                importlib.reload(gui_KDC)
                if hasattr(p, "kdc_101_gui") and p.kdc_101_gui:
                    try:
                        pos = dpg.get_item_pos(p.kdc_101_gui.window_tag)
                        size = dpg.get_item_rect_size(p.kdc_101_gui.window_tag)
                        p.kdc_101_gui.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old KDC_101 GUI removal failed: {e}")
                p.kdc_101_gui = gui_KDC.GUI_KDC101(
                    serial_number=p.kdc_101_gui.device.serial_number,
                    device=hw_devices.HW_devices().kdc_101
                )
                if dpg.does_item_exist("kdc_101_button"):
                    dpg.delete_item("kdc_101_button")
                p.create_bring_window_button(
                    p.kdc_101_gui.window_tag, button_label="kdc_101",
                    tag="kdc_101_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.kdc_101_gui.window_tag)
                dpg.set_item_pos(p.kdc_101_gui.window_tag, pos)
                dpg.set_item_width(p.kdc_101_gui.window_tag, size[0])
                dpg.set_item_height(p.kdc_101_gui.window_tag, size[1])
                print("Reloaded HW_GUI.GUI_KDC101 and recreated KDC_101 GUI.")
                return

            # === Smaract GUI ===
            if name in ("smaract", "smaract_gui"):
                import HW_GUI.GUI_Smaract as gui_Smaract
                importlib.reload(gui_Smaract)
                if hasattr(p, "smaractGUI") and p.smaractGUI:
                    try:
                        pos = dpg.get_item_pos(p.smaractGUI.window_tag)
                        size = dpg.get_item_rect_size(p.smaractGUI.window_tag)
                        p.smaractGUI.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old Smaract GUI removal failed: {e}")
                p.smaractGUI = gui_Smaract.GUI_smaract(
                    simulation=p.smaractGUI.simulation,
                    serial_number=p.smaractGUI.selectedDevice
                )
                p.smaractGUI.create_gui()
                if dpg.does_item_exist("Smaract_button"):
                    dpg.delete_item("Smaract_button")
                p.create_bring_window_button(
                    p.smaractGUI.window_tag, button_label="Smaract",
                    tag="Smaract_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.smaractGUI.window_tag)
                dpg.set_item_pos(p.smaractGUI.window_tag, pos)
                dpg.set_item_width(p.smaractGUI.window_tag, size[0])
                dpg.set_item_height(p.smaractGUI.window_tag, size[1])
                if not p.smaractGUI.simulation:
                    p.smaract_thread = threading.Thread(target=p.render_smaract)
                    p.smaract_thread.start()
                print("Reloaded HW_GUI.GUI_Smaract and recreated GUI_smaract.")
                return

            # === Dedicated PROEM GUI (separate instance in its own file) ===
            if name in ("hrs proem", "hrs_proem", "hrsproem", "proem"):
                import HW_GUI.GUI_PROEM as gui_PROEM
                importlib.reload(gui_PROEM)

                PROEM_LFE = gui_PROEM.GUI_PROEM.DEFAULT_LFE  # keep single source of truth

                # Create a brand-new ProEM device (do NOT overwrite devs.hrs_500)
                try:
                    devs = hw_devices.HW_devices()
                    device_proem = LightFieldSpectrometer(visible=True, file_path=PROEM_LFE)
                    device_proem.connect()
                except Exception as e:
                    print(f"Failed to initialize ProEM spectrometer: {e}")
                    raise

                # If a previous ProEM GUI exists, offset the new window a bit
                pos = [100, 100]
                size = [1200, 800]
                old_proem = getattr(p, "proem_gui", None)
                if old_proem:
                    try:
                        lp = dpg.get_item_pos(old_proem.window_tag)
                        pos = [lp[0] + 40, lp[1] + 40]
                    except Exception:
                        pass

                # Create the dedicated ProEM GUI
                p.proem_gui = gui_PROEM.GUI_PROEM(device_proem, prefix="proem", title="ProEM Camera")

                # Bring-window button (distinct tag)
                if dpg.does_item_exist("PROEM_button"):
                    dpg.delete_item("PROEM_button")
                p.create_bring_window_button(
                    p.proem_gui.window_tag,
                    button_label="PROEM",
                    tag="PROEM_button",
                    parent="focus_group"
                )
                p.active_instrument_list.append(p.proem_gui.window_tag)

                # Place & size
                try:
                    dpg.set_item_pos(p.proem_gui.window_tag, pos)
                    dpg.set_item_width(p.proem_gui.window_tag, size[0])
                    dpg.set_item_height(p.proem_gui.window_tag, size[1])
                except Exception:
                    pass

                print("Loaded NEW GUI_PROEM (separate ProEM GUI).")
                return

            # # === OLD!!!!!!!  HRS_500 GUI with ProEM experiment ===
            # if name in ("hrs proem", "hrs_proem", "hrsproem", "proem"):
            #     import HW_GUI.GUI_HRS_500 as gui_HRS500
            #     importlib.reload(gui_HRS500)
            #
            #     PROEM_LFE = r"C:\Users\Femto\Work Folders\Documents\LightField\Experiments\ProEM_shai.lfe"
            #
            #     # Try to preserve the current window position/size if it exists
            #     pos, size = [60, 60], [1200, 800]
            #     if hasattr(p, "hrs_500_gui") and p.hrs_500_gui:
            #         try:
            #             pos = dpg.get_item_pos(p.hrs_500_gui.window_tag)
            #             size = dpg.get_item_rect_size(p.hrs_500_gui.window_tag)
            #             p.hrs_500_gui.DeleteMainWindow()
            #         except Exception as e:
            #             print(f"Old HRS_500 GUI removal failed (ProEM): {e}")
            #
            #     # (Re)create the LightField spectrometer specifically with the ProEM experiment
            #     try:
            #         devs = hw_devices.HW_devices()
            #
            #         # Cleanly disconnect the existing device if possible
            #         try:
            #             if getattr(devs, "hrs_500", None) and hasattr(devs.hrs_500, "disconnect"):
            #                 devs.hrs_500.disconnect()
            #         except Exception as e:
            #             print(f"Warning: could not disconnect previous HRS_500 device: {e}")
            #
            #         # New instance with the ProEM experiment path
            #         devs.hrs_500 = LightFieldSpectrometer(
            #             visible=True,
            #             file_path=PROEM_LFE
            #         )
            #         devs.hrs_500.connect()
            #     except Exception as e:
            #         print(f"Failed to initialize HRS_500 with ProEM experiment: {e}")
            #         raise
            #
            #     # Rebuild the GUI using the (re)initialized device
            #     p.hrs_500_gui = gui_HRS500.GUI_HRS500(devs.hrs_500)
            #
            #     # Rebuild the “bring window” button
            #     if dpg.does_item_exist("HRS_500_button"):
            #         dpg.delete_item("HRS_500_button")
            #     p.create_bring_window_button(
            #         p.hrs_500_gui.window_tag, button_label="Spectrometer (ProEM)",
            #         tag="HRS_500_button", parent="focus_group"
            #     )
            #
            #     # Track as active instrument and restore geometry
            #     p.active_instrument_list.append(p.hrs_500_gui.window_tag)
            #     try:
            #         dpg.set_item_pos(p.hrs_500_gui.window_tag, pos)
            #         dpg.set_item_width(p.hrs_500_gui.window_tag, size[0])
            #         dpg.set_item_height(p.hrs_500_gui.window_tag, size[1])
            #     except Exception:
            #         pass
            #
            #     print("Reloaded HW_GUI.GUI_HRS500 with ProEM experiment and recreated Spectrometer GUI.")
            #     return

            # === HRS_500 GUI ===
            if name in ("hrs", "hrs500", "hrs_500"):
                import HW_GUI.GUI_HRS_500 as gui_HRS500
                importlib.reload(gui_HRS500)

                EXP3_LFE = r"C:\Users\Femto\Work Folders\Documents\LightField\Experiments\Experiment3.lfe"

                # Find a free GUI slot without overriding existing ones (after 'reload proem', etc.)
                gui_slots = ["hrs_500_gui", "hrs_500_gui2", "hrs_500_gui3", "hrs_500_gui4"]
                free_slot = None
                for s in gui_slots:
                    if not hasattr(p, s) or getattr(p, s) is None:
                        free_slot = s
                        break
                if free_slot is None:
                    print("Max HRS_500 GUI instances reached.")
                    return

                # Pick geometry: if we already have an instance, offset new window a bit
                base_pos, base_size = [60, 60], [1200, 800]
                existing_guis = [getattr(p, s) for s in gui_slots if hasattr(p, s) and getattr(p, s)]
                if existing_guis:
                    try:
                        last = existing_guis[-1]
                        lp = dpg.get_item_pos(last.window_tag)
                        base_pos = [lp[0] + 40, lp[1] + 40]
                    except Exception:
                        pass

                # (Re)create the LightField spectrometer with the Experiment3.lfe
                try:
                    devs = hw_devices.HW_devices()

                    # Cleanly disconnect the existing device if possible
                    try:
                        if getattr(devs, "hrs_500", None) and hasattr(devs.hrs_500, "disconnect"):
                            devs.hrs_500.disconnect()
                    except Exception as e:
                        print(f"Warning: could not disconnect previous HRS_500 device: {e}")

                    # New instance with the Experiment3 experiment path
                    devs.hrs_500 = LightFieldSpectrometer(
                        visible=True,
                        file_path=EXP3_LFE
                    )
                    devs.hrs_500.connect()
                except Exception as e:
                    print(f"Failed to initialize HRS_500 with Experiment3 experiment: {e}")
                    raise

                # Rebuild the GUI using the (re)initialized device
                p.hrs_500_gui = gui_HRS500.GUI_HRS500(devs.hrs_500)

                # Rebuild the “bring window” button
                if dpg.does_item_exist("HRS_500_button"):
                    dpg.delete_item("HRS_500_button")
                p.create_bring_window_button(
                    p.hrs_500_gui.window_tag, button_label="Spectrometer (Experiment3)",
                    tag="HRS_500_button", parent="focus_group"
                )

                # Track as active instrument and restore geometry
                p.active_instrument_list.append(p.hrs_500_gui.window_tag)
                try:
                    dpg.set_item_pos(p.hrs_500_gui.window_tag, pos)
                    dpg.set_item_width(p.hrs_500_gui.window_tag, size[0])
                    dpg.set_item_height(p.hrs_500_gui.window_tag, size[1])
                except Exception:
                    pass

                print("Reloaded HW_GUI.GUI_HRS500 with Experiment3.lfe and recreated Spectrometer GUI.")
                self.proEM_mode = False
                return

            # === reload Keysight AWG GUI ===
            if name in ("keysight", "awg", "keysight_awg"):
                import HW_GUI.GUI_keysight_AWG as gui_awg
                importlib.reload(gui_awg)

                # grab old GUI if it exists
                old = getattr(p, "keysight_gui", None)
                if old:
                    try:
                        pos = dpg.get_item_pos(old.window_tag)
                        size = dpg.get_item_rect_size(old.window_tag)
                        device = old.dev
                        simulation = old.simulation
                        # old.DeleteMainWindow()
                        # explicitly delete the old DearPyGui window
                        dpg.delete_item(old.window_tag)
                    except Exception as e:
                        print(f"Old Keysight GUI removal failed: {e}")
                else:
                    # fallback defaults if first load
                    pos = [20, 20]
                    size = [1800, 270]
                    device = hw_devices.HW_devices().keysight_awg_device
                    simulation = False

                # recreate
                p.keysight_gui = gui_awg.GUIKeysight33500B(
                    device=device,
                    simulation=simulation
                )

                # rebuild the “bring window” button
                if dpg.does_item_exist("keysight_button"):
                    dpg.delete_item("keysight_button")
                p.create_bring_window_button(
                    p.keysight_gui.window_tag,
                    button_label="KEYSIGHT_AWG",
                    tag="keysight_button",
                    parent="focus_group"
                )
                p.active_instrument_list.append(p.keysight_gui.window_tag)

                # restore position & size
                dpg.set_item_pos(p.keysight_gui.window_tag, pos)
                dpg.set_item_width(p.keysight_gui.window_tag, size[0])
                dpg.set_item_height(p.keysight_gui.window_tag, size[1])

                print("Reloaded GUI_keysight_AWG and recreated GUIKeysight33500B.")
                return

            # === CLD1011LP GUI ===
            if name in ("cld", "cld1011", "cld1011lp"):
                import HW_GUI.GUI_CLD1011LP as gui_CLD
                importlib.reload(gui_CLD)

                # Try to keep the existing device; if missing, try to recreate it
                from HW_wrapper.HW_devices import HW_devices
                devs = HW_devices()
                device = getattr(devs, "CLD1011LP", None)

                # Optionally reload the wrapper and recreate device if needed
                try:
                    import HW_wrapper.Wrapper_CLD1011 as wrap_CLD
                    importlib.reload(wrap_CLD)
                except Exception as e:
                    wrap_CLD = None
                    print(f"Warning: could not reload Wrapper_CLD1011: {e}")

                if device is None and wrap_CLD is not None:
                    try:
                        # If you have a config-driven simulation flag, read it here instead:
                        sim_flag = False
                        device = wrap_CLD.ThorlabsCLD1011LP(simulation=sim_flag)
                        devs.CLD1011LP = device
                    except Exception as e:
                        print(f"Warning: could not (re)create CLD1011LP device: {e}")

                # Cleanup previous GUI (no DeleteMainWindow in this GUI; remove by tag)
                if hasattr(p, "cld1011lp_gui") and p.cld1011lp_gui:
                    try:
                        pos = dpg.get_item_pos(p.cld1011lp_gui.window_tag)
                        size = dpg.get_item_rect_size(p.cld1011lp_gui.window_tag)
                        dpg.delete_item(p.cld1011lp_gui.window_tag)
                    except Exception as e:
                        print(f"Old CLD1011LP GUI removal failed: {e}")
                        pos, size = [60, 60], [600, 440]
                else:
                    pos, size = [60, 60], [600, 440]

                # Create the GUI (constructor builds the window)
                sim_flag = bool(getattr(device, "simulation", False)) if device is not None else False
                p.cld1011lp_gui = gui_CLD.GUI_CLD1011LP(simulation=sim_flag)

                # Rebuild the “bring window” button
                if dpg.does_item_exist("CLD1011LP_button"):
                    dpg.delete_item("CLD1011LP_button")
                p.create_bring_window_button(
                    p.cld1011lp_gui.window_tag, button_label="CLD1011LP",
                    tag="CLD1011LP_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.cld1011lp_gui.window_tag)

                # Restore geometry
                try:
                    dpg.set_item_pos(p.cld1011lp_gui.window_tag, pos)
                    dpg.set_item_width(p.cld1011lp_gui.window_tag, size[0])
                    dpg.set_item_height(p.cld1011lp_gui.window_tag, size[1])
                except Exception:
                    pass

                print("Reloaded HW_GUI.GUI_CLD1011LP and recreated CLD1011LP GUI.")
                return

            # === Display Z-Slices Viewer ===
            if name in ("disp", "display_slices", "zslider", "zslice"):
                import Utils.python_displayer as disp_mod
                importlib.reload(disp_mod)
                p.display_all_z_slices = disp_mod.display_all_z_slices
                print("Reloaded display_all_z_slices from python_displayer.py.")
                return

            # === Generic fallback reload ===
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            print(f"Reloaded module: {module_name}")

            print("Now it is time to loadhist if you want")

        except Exception:
            traceback.print_exc()
            print(f"Reload failed for '{module_name}'")
    def handle_plot_future_femto(self, arg):
        """Annotate future Femto energies on plot (fully restoring previous behavior)."""
        p = self.get_parent()
        try:
            # 1) Preconditions
            if not hasattr(p, "opx") or not hasattr(p, "femto_gui"):
                print("Missing 'opx' or 'femto_gui' in parent.")
                return
            # 2) Grab start/end positions and future data
            startLoc = p.opx.startLoc
            endLoc = p.opx.endLoc
            future_data = p.femto_gui.get_future_energies()
            # 3) Store on Zelux camera if available
            if hasattr(p, "cam"):
                p.cam.all_future_data = future_data
                print(f"Stored {len(future_data)} future data points in Zelux.")
            else:
                print("cam not found to store future data.")
            # 4) Clear old annotations
            if not hasattr(p, "future_annots"):
                p.future_annots = []
            else:
                for tag in p.future_annots:
                    if dpg.does_item_exist(tag):
                        dpg.delete_item(tag)
                p.future_annots = []
            # 5) Ensure draw layer
            layer = "plot_draw_layer"
            if not dpg.does_item_exist(layer):
                dpg.add_draw_layer(parent="plotImaga", tag=layer)
            # 6) Base Y at startLoc
            base_y = float(startLoc[1]) / 1e6
            # 7) Draw each annotation, updating if existing
            for idx, (angle, E) in enumerate(future_data):
                x_val = float(endLoc[0]) / 1e6
                y_val = base_y + idx * 2 + 0.5
                if not dpg.does_item_exist("plotImaga_Y"):
                    print("Error: Axis 'plotImaga_Y' does not exist.")
                    return
                tag = f"future_annot_{idx}"
                if dpg.does_item_exist(tag):
                    dpg.configure_item(tag, pos=(x_val, y_val), text=f"{E:.1f} nJ")
                    print(f"Updated existing annotation {tag}")
                else:
                    dpg.draw_text(
                        pos=(x_val, y_val),
                        text=f"{E:.1f} nJ",
                        color=(255, 255, 255, 255),
                        size=1.0,
                        parent=layer,
                        tag=tag
                    )
                p.future_annots.append(tag)
        except Exception as e:
            print(f"Error running 'plf': {e}")
    def handle_file(self, arg=None):
        """With no arg: print & copy last_loaded_file.
        With <path>: open that file if it exists."""
        p = self.get_parent()

        # 1) If no path given, fall back to last_loaded_file
        file_arg = (arg or "").strip()
        if not file_arg:
            if not hasattr(p, "opx") or not hasattr(p.opx, "last_loaded_file"):
                print("No file loaded/scanned yet.")
                return
            path = p.opx.last_loaded_file
            print(f"Last loaded/scan file: {path}")
            pyperclip.copy(path)
            return

        # 2) Otherwise treat arg as the file to open
        path = os.path.expanduser(file_arg)
        if not os.path.isabs(path):
            # interpret relative to last_scan_dir if set, else cwd
            try:
                base_dir = open("last_scan_dir.txt").read().strip()
            except Exception:
                base_dir = os.getcwd()
            path = os.path.join(base_dir, path)

        path = os.path.normpath(path)

        if not os.path.exists(path):
            print(f"File not found: {path}")
            return

        try:
            # Copy path to clipboard for convenience
            pyperclip.copy(path)
            print(f"Copied path: {path}")
            # Open with default application / Explorer
            if os.name == "nt":
                os.startfile(path)
            else:
                # macOS / Linux fallback
                import subprocess, shlex
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, path])
            print(f"Opened file: {path}")
        except Exception as e:
            print(f"Failed to open file: {e}")
    def handle_load_csv(self, arg):
        """Load & plot most recent CSV from last scan dir."""
        p = self.get_parent()
        try:
            # 1) Ensure OPX is available
            if not hasattr(p, "opx"):
                print("Parent has no opx.")
                return
            # 2) Parse optional dz offset
            limit_val = None
            stripped = arg.strip()

            # If "1", load from last scan dir (no dialog)
            if stripped == "1":
                p.opx.btnLoadScan(app_data="open_from_last")
                return

            if stripped.isdigit():
                limit_val = int(stripped)

            if limit_val is not None:
                print(f"Setting limit to {limit_val} and enabling limit.")
                p.opx.toggle_limit(app_data=None, user_data=True)
                dpg.set_value("inInt_limit", limit_val)

            p.opx.btnLoadScan(app_data="last")

        except Exception as e:
            print(f"Error in ld command: {e}")
    def handle_toggle_coords(self, arg):
        """Toggle coordinate grid."""
        p = self.get_parent()
        try:
            cur = getattr(p.cam, "show_coords_grid", False)
            p.cam.toggle_coords_display(None, not cur)
            print(f"Coords grid {'shown' if not cur else 'hidden'}.")
        except:
            print("toggle_coords failed.")
    def handle_fill_query(self, arg):
        """
            Fill/move/store query points (fq).

            Usage
            -----
            fq
                Fill ABS inputs from the current "query" (via opx.fill_moveabs_from_query()),
                move X and Y to those ABS values, read Z from the stage, and store a new point
                with the next available index. Prints the stored point and then lists points.

            fq <idx>
                If a point with index <idx> exists:
                    - Set the ABS inputs to that point's (x,y,z) in meters,
                    - Move ALL axes (X,Y,Z) to those values,
                    - Print "Moved to point #<idx>".
                If it does not exist:
                    - Store the CURRENT STAGE POSITION as point <idx> (no movement),
                    - Positions are taken from p.opx.positioner.AxesPositions (assumed µm),
                      converted to meters,
                    - Print "Stored point #<idx>: (...)".

            fq !
                Fill ABS inputs from the current "query" but DO NOT MOVE, then append a new
                point at the next available index using the ABS inputs (x,y,z) as-is (meters).

            fq <idx> !
                Fill ABS inputs from the current "query" but DO NOT MOVE, then store/overwrite
                point <idx> with the ABS inputs (x,y,z) as-is (meters).

            fq next
                Same as 'fq <idx>' but with <idx> = next available index (max saved idx + 1).

            fq next !
                Same as 'fq <idx> !' but with <idx> = next available index.

            Notes
            -----
            - All saved points are stored as tuples: (idx, x, y, z) with units in meters.
            - Hardware stage readings (p.opx.positioner.AxesPositions) are assumed to be in µm
              and are converted to meters by multiplying by 1e-6.
            - "Query" here refers to whatever p.opx.fill_moveabs_from_query() pulls into the
              ABS widgets (e.g., parsed text fields), WITHOUT moving the stage by itself.
            - After any action, the points list is shown via self.handle_list_points().

            Examples
            --------
            fq               # fill from query, move X/Y, store as new point
            fq 3             # move to stored point #3, or store current stage pos as #3 if missing
            fq !             # store a new point from query ABS values without moving
            fq 10 !          # store/overwrite point #10 from query ABS values without moving
            fq next          # act like 'fq <next_idx>'
            fq next !        # act like 'fq <next_idx> !'
            """
        p = self.get_parent()
        try:
            # --- Parse arg: support "<idx>", "!", "<idx> !", "! <idx>", etc.
            tokens = str(arg).split() if isinstance(arg, str) else []
            no_move = "!" in tokens
            want_next = any(t.lower() == "next" for t in tokens)

            idx = None
            for t in tokens:
                if t.isdigit():
                    idx = int(t)
                    break

            if want_next and idx is None:
                last = getattr(self, "_last_fq_idx", None)
                idx = (last + 1) if isinstance(last, int) else 1

            # Convenience accessors
            def _get_abs_xyz_from_gui():
                x = dpg.get_value("mcs_ch0_ABS")
                y = dpg.get_value("mcs_ch1_ABS")
                z = dpg.get_value("mcs_ch2_ABS")
                return x, y, z

            def _get_xyz_from_stage_m():
                # Stage returns µm -> convert to meters
                return tuple(v * 1e-6 for v in p.opx.positioner.AxesPositions)

            pts = getattr(p, "saved_query_points", [])

            if idx is not None:
                if no_move:
                    # --- "fq <idx> !" : fill ABS from query, DO NOT MOVE, store/overwrite idx
                    p.opx.fill_moveabs_from_query()  # fills ABS widgets only
                    x, y, z = _get_abs_xyz_from_gui()

                    # Replace existing or append new with this idx (no motion)
                    updated = False
                    for i, (j, *_rest) in enumerate(pts):
                        if j == idx:
                            pts[i] = (idx, x, y, z)
                            updated = True
                            break
                    if not updated:
                        pts.append((idx, x, y, z))
                    p.saved_query_points = pts
                    self._last_fq_idx = idx
                    print(f"Stored point #{idx} without moving: {(x, y, z)}")

                else:
                    # --- "fq <idx>" : move to stored idx OR store current stage position at idx
                    found = [pt for pt in pts if pt[0] == idx]
                    if found:
                        _, x, y, z = found[0]
                        for ax, val in enumerate((x, y, z)):
                            dpg.set_value(f"mcs_ch{ax}_ABS", val)
                            p.smaractGUI.move_absolute(None, None, ax)
                        print(f"Moved to point #{idx}")
                        self._last_fq_idx = idx
                    else:
                        x, y, z = _get_xyz_from_stage_m()
                        pts.append((idx, x, y, z))
                        p.saved_query_points = pts
                        self._last_fq_idx = idx
                        print(f"Stored point #{idx}: {(x, y, z)}")

            else:
                if no_move:
                    # --- "fq !" : fill ABS from query, DO NOT MOVE, append new index
                    p.opx.fill_moveabs_from_query()  # fills ABS widgets only
                    x, y, z = _get_abs_xyz_from_gui()
                    new_idx = pts[-1][0] + 1 if pts else 1
                    pts.append((new_idx, x, y, z))
                    p.saved_query_points = pts
                    self._last_fq_idx = new_idx
                    print(f"Stored point #{new_idx} without moving: {(x, y, z)}")

                else:
                    # --- "fq" : regular fill + move X/Y, update Z from stage, store new index
                    p.opx.fill_moveabs_from_query()
                    for ax in range(2):  # move X and Y only
                        p.smaractGUI.move_absolute(None, None, ax)
                    # Z from stage after any controller updates
                    z = p.opx.positioner.AxesPositions[2] * 1e-6
                    dpg.set_value("mcs_ch2_ABS", z)
                    x, y = [dpg.get_value(f"mcs_ch{ax}_ABS") for ax in range(2)]
                    new_idx = pts[-1][0] + 1 if pts else 1
                    pts.append((new_idx, x, y, z))
                    p.saved_query_points = pts
                    self._last_fq_idx = new_idx
                    print(f"Stored point #{new_idx}: {(x, y, z)}")

            # Show list (pass a clean arg: just the idx if present, else empty)
            self.handle_list_points(str(idx) if idx is not None else "")
        except Exception as e:
            print(f"fq failed: {e}")
    def handle_toggle_ax(self, arg):
        """
        Toggle the angled axis overlay in the Zelux GUI.
        Usage: ax
        """
        p = self.get_parent()

        # 1) If user supplied a number, set ax_alpha
        try:
            angle = float(arg.strip())
            p.cam.ax_alpha = angle
            print(f"Axis angle set to {angle}°")
            return
        except ValueError:
            pass  # not a number, so treat as toggle

        current = getattr(p.cam, "show_axis", False)
        p.cam.toggle_show_axis(app_data=not current)
    def handle_find_max_in_area(self, arg):
        """Find the maximum Z value inside the currently defined queried_area.
           Move the stage to the X,Y location of the maximum, update the GUI,
           and store the location as a new query point in saved_query_points."""
        p = self.get_parent()
        try:
            from HWrap_OPX import Axis
            # 1) Ensure OPX exists
            if not hasattr(p, "opx"):
                print("OPX unavailable.")
                return

            opx = p.opx

            # 2) Check queried area
            area = getattr(opx, "queried_area", None)
            if area is None or len(area) < 4:
                print("No queried area defined.")
                return
            x0, x1, y0, y1 = area
            xmin, xmax = min(x0, x1), max(x0, x1)
            ymin, ymax = min(y0, y1), max(y0, y1)

            # 3) Get scan data & coordinate vectors
            scan = getattr(opx, "scan_data", None)
            if scan is None or not hasattr(opx, "Xv") or not hasattr(opx, "Yv") or not hasattr(opx, "idx_scan"):
                print("Scan data or coordinate vectors are missing.")
                return
            Xv = np.array(opx.Xv)
            Yv = np.array(opx.Yv)
            flipped_Yv = Yv[::-1]  # for display orientation

            # 4) Extract Z‐slice
            z_idx = opx.idx_scan[Axis.Z.value]
            z_value = float(opx.Zv[z_idx])
            flipped_arrXY = np.flipud(scan[z_idx, :, :])

            # 5) Mask to queried rectangle
            mask_x = (Xv >= xmin) & (Xv <= xmax)
            mask_y = (flipped_Yv >= ymin) & (flipped_Yv <= ymax)
            ix = np.where(mask_x)[0]
            iy = np.where(mask_y)[0]
            if ix.size == 0 or iy.size == 0:
                print("No scan points inside queried area.")
                return

            # 6) Find max within sub‐region
            sub_arr = flipped_arrXY[np.ix_(iy, ix)]
            if sub_arr.size == 0:
                print("Sub-region is empty.")
                return
            iy_max, ix_max = np.unravel_index(np.argmax(sub_arr), sub_arr.shape)
            x_max = Xv[ix[ix_max]]
            y_max = flipped_Yv[iy[iy_max]]
            z_max = sub_arr[iy_max, ix_max]

            print(f"Max Z={z_max:.2f} found at X={x_max:.2f}, Y={y_max:.2f}, Z slice={z_value:.2f}")

            # 7) Move GUI sliders & axes 0/1
            dpg.set_value("mcs_ch0_ABS", x_max)
            dpg.set_value("mcs_ch1_ABS", y_max)
            z = dpg.get_value("mcs_ch2_ABS")
            if hasattr(p, "smaractGUI") and hasattr(p.smaractGUI, "move_absolute"):
                p.smaractGUI.move_absolute(None, None, 0)
                p.smaractGUI.move_absolute(None, None, 1)

            # 8) Save as a new query point
            if not hasattr(p, "saved_query_points"):
                p.saved_query_points = []
            new_index = p.saved_query_points[-1][0] + 1 if p.saved_query_points else 1
            p.saved_query_points.append((new_index, x_max, y_max, z))
            print(f"Stored query point #{new_index}: X={x_max:.2f}, Y={y_max:.2f}")

            # 9) Redraw list of points without recording this in history
            self.run("list", record_history=False)

        except Exception as e:
            print(f"Error in findq command: {e}")
    def handle_move_last_z(self, arg):
        """Move to last_z_value + offset."""
        p = self.get_parent()
        try:
            base = p.smaractGUI.last_z_value
            offset = float(arg) if arg else 0.0
            z = base + offset
            dpg.set_value("mcs_ch2_ABS", z)
            p.smaractGUI.move_absolute(None,None,2)
            print(f"Moved Z to {z:.2f}")
        except Exception as e:
            print(f"lastz failed: {e}")
    def handle_move_abs_x(self, arg):
        """Set X absolute."""
        self._move_abs_axis(0,arg)
    def handle_move_abs_y(self, arg):
        """Set Y absolute."""
        self._move_abs_axis(1,arg)
    def handle_move_abs_z(self, arg):
        """Set Z absolute."""
        self._move_abs_axis(2,arg)
    def _move_abs_axis(self, axis, arg):
        p = self.get_parent()
        try:
            val = float(arg)
            dpg.set_value(f"mcs_ch{axis}_ABS", val)
            p.smaractGUI.move_absolute(None,None,axis)
            print(f"Moved axis {axis} to {val:.3f}")
        except Exception as e:
            print(f"moveabs{axis} failed: {e}")
    def handle_save_and_down(self, arg):
        """Save last_z and move Z down by a TOTAL of 10,000 µm in 2,000 µm steps (relative)."""
        p = self.get_parent()
        try:
            # Current Z in µm (AxesPositions are in meters)
            curr_um = p.smaractGUI.dev.AxesPositions[2] * 1e6
            p.smaractGUI.last_z_value = curr_um

            step_um = 2000.0
            total_um = 10000.0
            n_steps = int(total_um // step_um)  # = 5

            print(f"Saved Z={curr_um:.2f} µm. Moving down {total_um:.0f} µm in {n_steps}×{step_um:.0f} µm steps…")

            for i in range(1, n_steps + 1):
                # Negative = "down". Flip sign if your axis convention is opposite.
                self._move_delta(2, step_um)
                print(f"  step {i}/{n_steps}: ΔZ = -{step_um:.0f} µm")

            est_final = curr_um - total_um
            print(f"Done. Estimated Z = {est_final:.2f} µm (moved total dZ = -{total_um:.0f} µm).")
        except Exception as e:
            print(f"down failed: {e}")
    def handle_up(self, arg):
        """Move Z to last saved value; 'up ?' prints it; 'up 1' or no saved -> Z=600 (relative)."""
        try:
            p = self.get_parent()
            s = (arg or "").strip()
            last = getattr(p.smaractGUI, "last_z_value", None)

            # Current Z in µm
            curr_um = p.smaractGUI.dev.AxesPositions[2] * 1e6

            if s == "?":
                if last is None:
                    print("up? -> no last Z saved")
                else:
                    print(f"up? -> last Z = {last:.2f} µm")
                return

            # If "up 1" or nothing saved yet -> go to 600 µm
            if s == "1" or last is None:
                target_um = 600.0
            else:
                target_um = float(last)

            dz_um = target_um - curr_um

            if abs(dz_um) < 1e-3:
                print(f"Z already at ~{target_um:.2f} µm (no move).")
                return

            self._move_delta(2, dz_um)
            print(f"Moved Z by ΔZ={dz_um:.2f} µm to ~{target_um:.2f} µm")
        except Exception as e:
            print(f"up failed: {e}")
    def handle_round_position(self, arg):
        """Round XYZ to given precision."""
        p = self.get_parent()
        try:
            prec = int(arg) if arg else 0
            pos = [round(v*1e-6,prec) for v in p.opx.positioner.AxesPositions]
            for ax,val in enumerate(pos):
                dpg.set_value(f"mcs_ch{ax}_ABS", val)
                p.smaractGUI.move_absolute(None,None,ax)
            print(f"Rounded to {pos}")
        except Exception as e:
            print(f"round failed: {e}")
    def handle_list_points(self, arg=None):
        """List and draw stored query points."""
        p = self.get_parent()
        pts = getattr(p, "saved_query_points", [])
        # Determine whether to draw hollow/thin
        hollow_mode = str(arg).strip() == "1"
        if pts:
            print("Stored points:")
            for index, x, y, z in pts:
                # 1) Print to console
                print(f"{index}: X={x:.6f}, Y={y:.6f}, Z={z:.6f}")

                # 2) Ensure the plot axis exists
                if not dpg.does_item_exist("plotImaga_Y"):
                    print("Axis 'plotImaga_Y' does not exist. Cannot plot points.")
                    continue

                # 3) Ensure a draw layer
                if not dpg.does_item_exist("plot_draw_layer"):
                    dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

                # 4) Draw or update the point dot
                dot_tag = f"stored_point_dot_{index}"
                if dpg.does_item_exist(dot_tag):
                    dpg.configure_item(dot_tag,
                                       center=(x, y),
                                       fill=None if hollow_mode else (0, 0, 0, 255),
                                       thickness=0.5 if hollow_mode else 1.0,
                                       )
                else:
                    dpg.draw_circle(
                        center=(x, y),
                        radius=0.15,
                        color=(255, 0, 0, 255),
                        fill= None if hollow_mode else (0, 0, 0, 255),
                        parent="plot_draw_layer",
                        tag=dot_tag,
                        thickness=0.5 if hollow_mode else 1.0,
                    )

                # 5) Draw or update the annotation text
                annot_tag = f"stored_point_annot_{index}"
                if dpg.does_item_exist(annot_tag):
                    dpg.configure_item(annot_tag, pos=(x, y), text=f"{int(index)}")
                else:
                    dpg.draw_text(
                        pos=(x, y),
                        text=f"{int(index)}",
                        color=(255, 255, 0, 255),
                        size=1.2,
                        parent="plot_draw_layer",
                        tag=annot_tag
                    )

                # 6) Track these tags for later clearing if needed
                if not hasattr(p, "query_annots"):
                    p.query_annots = []
                p.query_annots.extend([dot_tag, annot_tag])
        else:
            print("No points stored.")
    def handle_list_zelux(self, arg=None):
        """Display stored query points on the Zelux camera image."""
        p = self.get_parent()
        pts = getattr(p, "saved_query_points", [])
        cam = getattr(p, "cam", None)
        cam.query_points = pts
        print(f"✅ Stored {len(pts)} points to Zelux camera for display.")
    def handle_zel_shift_x(self, arg):
        """Shift all query points in Zelux display along X by given microns."""
        p = self.get_parent()
        cam = getattr(p, "cam", None)
        try:
            cam.zel_shift_x = float(arg.strip())
            print(f"Zelux X-shift set to {cam.zel_shift_x} µm")
        except Exception as e:
            print(f"Invalid shift X: {e}")
    def handle_zel_shift_y(self, arg):
        """Shift all query points in Zelux display along Y by given microns."""
        p = self.get_parent()
        cam = getattr(p, "cam", None)
        try:
            cam.zel_shift_y = float(arg.strip())
            print(f"Zelux Y-shift set to {cam.zel_shift_y} µm")
        except Exception as e:
            print(f"Invalid shift Y: {e}")
    def handle_clear(self, arg):
        """Clear points or annotations."""
        p = self.get_parent()
        cmd = arg.strip().lower()
        if cmd in ("ann","annotation","annotations"):
            if dpg.does_item_exist("plot_draw_layer"):
                dpg.delete_item("plot_draw_layer")
                dpg.add_draw_layer(parent="plotImaga",tag="plot_draw_layer")
            print("Annotations cleared.")
        elif cmd.isdigit():
            idx=int(cmd)
            pts=getattr(p,"saved_query_points",[])
            p.saved_query_points=[pt for pt in pts if pt[0]!=idx]
            print(f"Point #{idx} deleted.")
        else:
            p.saved_query_points=[]
            if dpg.does_item_exist("plot_draw_layer"):
                dpg.delete_item("plot_draw_layer")
                dpg.add_draw_layer(parent="plotImaga",tag="plot_draw_layer")
            print("All cleared.")
            self._last_fq_idx = 0
            print("fq next index reset to 0.")
    def handle_shift_point(self, arg):
        """Shift a stored point by ΔX,ΔY."""
        p = self.get_parent()
        try:
            m = re.match(r"(\d+)\(([^,]+),([^)]+)\)",arg)
            idx,dx,dy = int(m[1]),float(m[2]),float(m[3])
            pts = p.saved_query_points
            for i,pt in enumerate(pts):
                if pt[0]==idx:
                    pts[i]=(idx,pt[1]+dx,pt[2]+dy,pt[3])
                    print(f"Shifted #{idx} by ({dx},{dy})")
                    return
            print(f"No point #{idx}")
        except Exception as e:
            print(f"shift failed: {e}")
    def handle_insert_points(self, arg):
        """Insert new points relative to last."""
        p = self.get_parent()
        try:
            m=re.match(r"(\d+)(?:\(([^,]+),([^)]+)\))?",arg)
            n=int(m[1])
            dx,dy=(float(m[2]),float(m[3])) if m[2] else (None,None)
            pts=p.saved_query_points
            if dx is None and dy is None and len(pts)>=2:
                dx=(pts[-1][1]-pts[-2][1])
                dy=(pts[-1][2]-pts[-2][2])
            last=pts[-1]
            for i in range(1,n+1):
                idx=last[0]+i
                pts.append((idx, last[1]+i*dx, last[2]+i*dy, last[3]))
                print(f"Inserted #{idx}")
        except Exception as e:
            print(f"insert failed: {e}")
    def handle_save_list(self, arg):
        """Save points to file."""
        p = self.get_parent()
        try:
            with open("saved_query_points.txt","w") as f:
                for idx,x,y,z in p.saved_query_points:
                    f.write(f"{idx},{x:.6f},{y:.6f},{z:.6f}\n")
            print("Points saved.")
        except Exception as e:
            print(f"savelist failed: {e}")
    def handle_load_list(self, arg):
        """Load points from file. Accepts a filename path or falls back to default."""
        p = self.get_parent()
        try:
            file_path = arg.strip() if arg.strip() else "saved_query_points.txt"
            with open(file_path, "r") as f:
                p.saved_query_points = [tuple(map(float, line.strip().split(","))) for line in f]
            print(f"Points loaded from {file_path}.")
            self.handle_list_points()
        except Exception as e:
            print(f"loadlist failed: {e}")
    def handle_generate_list(self, arg):
        """Generate point file from CSV and load if small. 'genlist1' prompts for file."""
        p = self.get_parent()
        try:
            # Determine source CSV
            if arg.strip() == "1":
                fn = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
                if not fn:
                    print("No file selected.")
                    return
                csv_file = fn
                print(f"Selected file: {csv_file}")
            else:
                csv_file = getattr(p.opx, "last_loaded_file", None)
                if not csv_file:
                    print("No CSV file loaded.")
                    return

            out = export_points(csv_file)
            size = sum(1 for _ in open(out))
            print(f"Generated {out} ({size} lines).")

            if size < 1000:
                self.handle_load_list(out)
        except Exception as e:
            print(f"genlist failed: {e}")
    def handle_hrs(self, arg: str):
        p = self.get_parent()
        a = (arg or "").strip().lower()

        if a == "local":
            target = r"C:\Users\Femto\Work Folders\Documents\LightField"
            try:
                dev = getattr(p.hrs_500_gui, "dev", None)
                exp = getattr(dev, "_exp", None)
                if exp is None:
                    print("HRS: no experiment instance.")
                    return

                # wait out any UI updating before SetValue
                while getattr(exp, "IsUpdating", False):
                    time.sleep(0.05)

                # this is the “Save In” directory
                exp.SetValue(ExperimentSettings.FileNameGenerationDirectory, target)

                dev.save_directory = target
                print(f"HRS Save In set to: {target}")
            except Exception as e:
                print(f"Failed to set Save In folder: {e}")
            return

        print(f"Unknown hrs command: {arg!r}")
    def handle_acquire_spectrum(self, arg):
        """Launch threaded spectrum acquisition process.
        Usage: spc [st] [exposure_s]

          spc               Acquire spectrum with current settings.
          spc <time_s>      Acquire with integration time in seconds.
          spc st            Run 'set XYZ' + paste clipboard into experiment notes, then acquire.
          spc st <time_s>   Same as 'st' but sets exposure time.
          spc fname=<name>  Override filename *stem* (quotes allowed). Example:
            spc fname="My sample 01"
            spc st fname='Run A' t=2 n=3

          spc note <text>  Remember a note; it will be appended to every filename until cleared.
          spc note clear   Clear the persistent note.

        Notes:
          • Exposure time is given in seconds (float).
          • Last saved CSV is renamed with experiment note appended.
          • New file path is copied to clipboard after acquisition.
        """
        import threading,re,shlex

        # --- NEW: support "spc note <text>" to persist a note across acquisitions ---
        _arg = (arg or "").strip()
        if _arg.lower().startswith("note"):
            # Accept:
            #   spc note <text>
            #   spc note clear
            #   spc note coupon   <-- NEW
            note_raw = _arg[4:].strip()  # remove "note"

            # --- NEW: handle "spc note coupon" ---
            if note_raw.lower() == "coupon":
                name = self._nearest_coupon_name()
                if not name:
                    print("SPC note coupon: no coupon near the current position.")
                    setattr(self, "_spc_note", None)
                else:
                    setattr(self, "_spc_note", name)
                    print(f"SPC note set to nearest coupon: '{name}'")
                return
            # --- END NEW ---

            # strip quotes
            if (len(note_raw) >= 2) and (note_raw[0] == note_raw[-1] in ("'", '"')):
                note_raw = note_raw[1:-1].strip()

            # clear note
            if note_raw.lower() in ("", "clear", "none", "off"):
                setattr(self, "_spc_note", None)
                print("SPC note cleared.")
                return

            # normal text note
            import re
            safe = re.sub(r'[<>:"/\\|?*]', "_", note_raw).strip()
            setattr(self, "_spc_note", safe if safe else None)
            print(f"SPC note set to: '{getattr(self, '_spc_note', '')}'")
            return
        # --- end NEW ---


        run("cn")

        # --- make sure the event exists and running flag is set ---
        if not isinstance(getattr(self, "_spc_done_evt", None), __import__("threading").Event):
            self._spc_done_evt = threading.Event()
        self._spc_done_evt.clear()
        self._spc_running = True  # <— NEW: running flag

        threading.Thread(target=self._acquire_spectrum_worker, args=(arg,), daemon=True).start()
    def _nearest_coupon_name(self, tol_um: float = 600.0):
        """
        Return the nearest coupon name to the current (U,V) position,
        or None if none within tol_um.
        """
        import math

        # must match the same store used by handle_coupon
        labels = getattr(self, "_coupon_labels", None)
        if not labels:
            return None

        try:
            u_cur, v_cur, _ = self._read_current_position_um()
        except Exception:
            return None

        best = None
        for name, info in labels.items():
            try:
                du = u_cur - float(info.get("u_um", 0.0))
                dv = v_cur - float(info.get("v_um", 0.0))
                d2 = du * du + dv * dv
            except Exception:
                continue
            if best is None or d2 < best[0]:
                best = (d2, name)

        if best is None:
            return None

        d2, name = best
        if d2 > tol_um * tol_um:
            return None
        return name
    def _acquire_spectrum_worker(self, arg):
        """Actual spectrum acquisition logic, run in a background thread."""
        import re, os, glob, time, threading
        from pathlib import Path
        # import pyperclip

        p = self.get_parent()

        # --- choose target spectrometer GUI (default: PROEM; override with leading 'hrs') ---  # NEW
        _raw_tokens = (arg or "").strip().split()  # NEW
        _use_hrs = bool(_raw_tokens and _raw_tokens[0].lower() == "hrs")  # NEW
        if _use_hrs:  # NEW
            _raw_tokens = _raw_tokens[1:]  # strip 'hrs'  # NEW
            arg = " ".join(_raw_tokens)  # pass the remaining args downstream  # NEW
        target_gui = getattr(p, "proem_gui", None) if not _use_hrs else getattr(p, "hrs_500_gui", None)  # NEW
        if target_gui is None:
            target_gui = getattr(p, "hrs_500_gui", None)  # fallback if ProEM missing  # NEW
        if target_gui is None:  # NEW
            print("No spectrometer GUI available (neither ProEM nor HRS).")  # NEW
            return  # NEW

        dev = getattr(target_gui, "dev", None)  # NEW
        if dev is None:  # NEW
            print("Target spectrometer device is not available.")  # NEW
            return  # NEW

        try:  # NEW
            dev._exp.Stop()  # NEW
        except Exception:  # NEW
            pass  # NEW

        # --- SPC done event ---
        evt = getattr(self, "_spc_done_evt", None)
        if not isinstance(evt, threading.Event):
            evt = threading.Event()
            self._spc_done_evt = evt
        evt.clear()

        # -------- parse args --------
        # Examples:
        #   ""                       -> st ON, 1 shot, current exposure
        #   "2.0"                    -> st ON, 1 shot, t=2.0s
        #   "n=10 t=2 !"             -> st ON, 10 shots, t=2s, no preview
        #   "nost n=3"               -> st OFF, 3 shots

        # --- Helpers to parse/format/replace Site(x y z) in names ---
        _SITE_RE = re.compile(r"(?i)Site\s*\(\s*([^\s\)]+)\s+([^\s\)]+)(?:\s+([^\s\)]+))?\s*\)")

        def _parse_site_from_string(name: str):
            """
            Return (x_um, y_um, z_um_or_None, use_comma) if 'Site(...)' found; else None.
            Accepts decimal comma.
            """
            m = _SITE_RE.search(name or "")
            if not m:
                return None
            xs, ys, zs = m.group(1), m.group(2), m.group(3)
            use_comma = ("," in xs) or ("," in ys) or (zs is not None and "," in zs)

            def _nf(s):
                return float(str(s).replace(",", ".")) if s is not None else None

            return (_nf(xs), _nf(ys), _nf(zs) if zs is not None else None, use_comma)

        def _fmt_num(v: float, use_comma: bool) -> str:
            s = f"{v:.2f}"
            return s.replace(".", ",") if use_comma else s

        def _replace_or_append_site(name: str, x_um: float, y_um: float, z_um, use_comma: bool) -> str:
            """
            Replace existing Site(...) or append ' Site(x y [z])' at the end.
            Keeps the rest of the filename intact (we operate on the stem you already sanitize).
            """

            def repl(m):
                zpart = f" {_fmt_num(z_um, use_comma)}" if z_um is not None else ""
                return f"Site ({_fmt_num(x_um, use_comma)} {_fmt_num(y_um, use_comma)}{zpart})"

            if _SITE_RE.search(name):
                return _SITE_RE.sub(repl, name, count=1)
            # append if missing
            zpart = f" {_fmt_num(z_um, use_comma)}" if z_um is not None else ""
            tail = f" Site ({_fmt_num(x_um, use_comma)} {_fmt_num(y_um, use_comma)}{zpart})"
            # keep below your 100-char sanitize later; we’ll let your truncation handle length
            return f"{name}{tail}"

        # --- NEW: get current filename *stem* from device instead of clipboard ---
        def _get_dev_filename_stem() -> str:
            import os

            name = ""
            # Try common attributes first
            for attr in ("filename", "file_name", "current_filename"):
                val = getattr(dev, attr, None)
                if isinstance(val, str) and val.strip():
                    name = val.strip()
                    break

            # Optional SDK getter, if available
            if not name:
                try:
                    name = str(dev.get_filename()).strip()
                except Exception:
                    name = ""

            if not name:
                return ""

            name = name.replace("\r", "").replace("\n", " ")
            base = os.path.basename(name)
            base, _ext = os.path.splitext(base)
            return base
        # --- NEW: helper to append persistent note to filename stem ---
        def _append_persistent_note(base: str) -> str:
            import re
            note = getattr(self, "_spc_note", None)
            if not note:
                return base
            # safe & concise; final length still bounded by your set_filename slicing
            note_safe = re.sub(r'[<>:"/\\|?*]', "_", str(note)).strip()
            if not note_safe:
                return base
            return f"{base} {note_safe}"

        # -------- parse args (unchanged) --------
        tokens = (arg or "").strip().split()

        def _kv(name, cast, default=None):
            import re
            pat = re.compile(rf"(?i)\b{name}\s*=\s*([^\s]+)")
            for t in tokens:
                m = pat.match(t)
                if m:
                    try:
                        return cast(m.group(1))
                    except Exception:
                        pass
            return default

        def _kvq(name: str):  # new
            import re  # new
            pat = re.compile(rf'(?is)\b{name}\s*=\s*(?:"([^"]+)"|\'([^\']+)\'|([^\s]+))')  # new
            m = pat.search(arg or "")  # new
            if not m:  # new
                return None  # new
            return m.group(1) or m.group(2) or m.group(3)  # new
            # new

        def _sanitize_name(s: str) -> str:  # new
            import re, os  # new
            s = (s or "").strip().strip('"').strip("'")  # new
            s = s.replace("\r", "").replace("\n", " ")  # new
            base = os.path.basename(s)  # new
            base, _ext = os.path.splitext(base)  # new
            base = re.sub(r'[<>:"/\\|?*]', "_", base)  # new
            return base[:100]  # new

        forced_fname = _kvq("fname")  # new

        # --- NEW: detect "shift" mode and parse its step (µm) ---
        shift_mode = False
        shift_um = 5.0  # default step in micrometers
        if any(t.lower() == "shift" for t in tokens):
            shift_mode = True
            # if a number immediately follows 'shift', use it as µm step
            for i, t in enumerate(tokens):
                if t.lower() == "shift":
                    if i + 1 < len(tokens):
                        try:
                            shift_um = float(tokens[i + 1])
                        except Exception:
                            pass
                    break

        shots = _kv("n", int, 1)
        t_explicit = _kv("t", float, None)

        # keep your “bare float” support
        bare_time = None
        for t in tokens:
            try:
                bare_time = float(t)
                break
            except Exception:
                pass

        no_preview = any(t == "!" for t in tokens)
        is_st = not any(t.lower() == "nost" for t in tokens)  # default ST=ON

        def _is_float(s):
            try:
                float(s);
                return True
            except Exception:
                return False

        # Clean string for your old "bare float" path, but:
        #   - remove 'shift' and its numeric so they never become a bare-time
        rest_arg_clean_for_time = []
        skip_next_numeric_after_shift = False
        for t in tokens:
            tl = t.lower()
            if skip_next_numeric_after_shift:
                skip_next_numeric_after_shift = False
                continue
            if tl == "shift":
                skip_next_numeric_after_shift = True
                continue
            if t in ("!", "st", "nost") or "=" in t or _is_float(t):
                continue
            rest_arg_clean_for_time.append(t)
        rest_arg_clean_for_time = " ".join(rest_arg_clean_for_time).strip()

        # --- TIME SETTING RULES ---
        # If in shift mode: DO NOT change integration time unless t=... is provided.
        # If not in shift mode: keep your original behavior (t=... or bare float).
        if shift_mode:
            secs_str = str(t_explicit) if (t_explicit is not None) else ""  # no bare float
        else:
            secs_str = str(t_explicit) if (t_explicit is not None) else rest_arg_clean_for_time

        if secs_str:
            try:
                secs_ms = float(secs_str) * 1000.0
                dev.set_value(CameraSettings.ShutterTimingExposureTime, secs_ms)
                print(f"Integration time set to {secs_str}s")
            except Exception as e:
                print(f"Could not set integration time to '{secs_str}': {e}")

        # For later re-assert:
        if shift_mode:
            time_s = t_explicit  # None if not given, so we won't touch exposure
        else:
            # preserve your original bare-float semantics outside shift mode
            bare_time = None
            for t in tokens:
                try:
                    bare_time = float(t)
                    break
                except Exception as e:
                    print(f"Could not parse {t} as float: {e}")
                    pass
            time_s = t_explicit if (t_explicit is not None) else bare_time

        # defaults
        shots = _kv("n", int, 1)
        no_preview = any(t == "!" for t in tokens)

        # Use the *cleaned* arg for your mark (drop kvs and !, and NEW: drop 'shift' + its number)
        def _clean_mark_arg():
            keep = []
            skip_next_numeric_after_shift = False
            for t in tokens:
                tl = t.lower()
                if skip_next_numeric_after_shift:
                    skip_next_numeric_after_shift = False
                    continue
                if tl in ("st", "nost") or t == "!" or "=" in t:
                    continue
                if tl == "shift":
                    skip_next_numeric_after_shift = True
                    continue
                # skip any lone numeric that could be mistaken for exposure text
                try:
                    float(t);
                    continue
                except Exception:
                    pass
                keep.append(t)
            return " ".join(keep)
        rest_arg_clean = _clean_mark_arg()
        try:
            self.handle_mark(rest_arg_clean)
        except Exception:
            pass
        time.sleep(0.1)

        # --- helpers for relative positioning to origin ---
        x_off_um = 0.0
        y_off_um = 0.0

        def _move_rel(axis, delta_um: float):
            # axis: "X" or "Y"
            try:
                if axis == "X":
                    self.handle_moveX(f"{delta_um}")
                elif axis == "Y":
                    self.handle_moveY(f"{delta_um}")
                return True
            except Exception as e:
                print(f"Relative move {axis} {delta_um}um failed: {e}")
                return False

        def _back_to_origin():
            nonlocal x_off_um, y_off_um
            try:
                if abs(x_off_um) > 0:
                    _move_rel("X", -x_off_um)
                if abs(y_off_um) > 0:
                    _move_rel("Y", -y_off_um)
                x_off_um = 0.0
                y_off_um = 0.0
            except Exception as e:
                print(f"Return-to-origin failed: {e}")

        # 1) Stop camera & flippers
        try:
            self.handle_toggle_sc(False)
        except Exception:
            pass

        # Build move plan
        if shift_mode:
            shots = 9  # exactly nine frames
            s = float(shift_um)

            # target offsets (X,Y) in µm relative to origin (0,0)
            # Order: start at origin (0,0), then snake rows across the 3×3 centered on origin.
            # We include origin only once (first shot).
            targets = [
                (0.0, 0.0),  # Shot 1: origin
                (-s, -s), (0.0, -s), (s, -s),  # Row y = -s, left->right
                (s, 0.0), (-s, 0.0),  # Row y = 0, right->left (skip origin here)
                (-s, s), (0.0, s), (s, s),  # Row y = +s, left->right
            ]

            # We will *not* return-to-origin between shots in this mode; only at the very end.
            # Provide helpers to move to absolute target offsets from current (x_off_um,y_off_um).
            def _goto_offset_abs(tx_um: float, ty_um: float):
                nonlocal x_off_um, y_off_um
                dx = tx_um - x_off_um
                dy = ty_um - y_off_um
                if abs(dx) > 0:
                    _move_rel("X", dx)
                    x_off_um += dx
                if abs(dy) > 0:
                    _move_rel("Y", dy)
                    y_off_um += dy

            # --- Acquire loop (custom path for 9-frame snake) ---
            for k, (tx, ty) in enumerate(targets, start=1):
                # Move from current offset to target offset (no back-to-origin here)
                _goto_offset_abs(tx, ty)
                if k == 2:
                    time.sleep(1.0)  # keep your spec: wait 1s after the first move

                # ----- your existing proEM capture block (unchanged) -----
                dev._exp.Stop()

                # Build filename from current device filename + update Site(...) with current offsets
                try:
                    if forced_fname:
                        base = _sanitize_name(forced_fname)
                    else:
                        base = _sanitize_name(_get_dev_filename_stem())

                    # Always read current stage position for Site(...), not from filename/clipboard
                    try:
                        x_um, y_um, z_um = self._read_current_position_um()
                        base = _replace_or_append_site(base, x_um, y_um, z_um, use_comma=True)
                    except Exception as e:
                        print(f"Could not read stage position for filename: {e}")

                    base = f"{base} #{k}"
                    base = _append_persistent_note(base)

                    dev.set_filename(base[:100])
                except Exception:
                    pass

                # DO NOT touch exposure unless time_s is set (your rule)
                if time_s is not None:
                    try:
                        ms = float(time_s) * 1000.0
                        dev.set_value(CameraSettings.ShutterTimingExposureTime, ms)
                    except Exception:
                        pass

                # wait until not updating, then acquire
                try:
                    while getattr(dev._exp, "IsUpdating", False):
                        time.sleep(0.05)
                except Exception:
                    pass

                try:
                    target_gui.acquire_callback()
                except Exception as e:
                    print(f"acquire_callback failed on shot {k}: {e}")
                    continue

                time.sleep(0.4)
                try:
                    if getattr(dev._exp, "IsReadyToRun", True):
                        p.hrs_500_gui.dev.set_value(CameraSettings.ShutterTimingExposureTime, 3000.0)
                        while getattr(dev._exp, "IsUpdating", False):
                            time.sleep(0.05)
                        if not no_preview and self.proEM_mode:
                            dev._exp.Preview()
                except Exception:
                    pass


            # Return to origin once at the end (required)
            try:
                _back_to_origin()
            except Exception:
                pass

            try:
                self._spc_running = False  # <— NEW: clear running
                self._spc_done_evt.set()
                print("SPC finished.")
            except Exception:
                pass

            return  # <<< IMPORTANT: we handled the whole flow for the 9-frame mode

        # 2) Acquire loop
        # proEM behavior is kept as in your original code-path.
        for k in range(1, int(max(1, shots)) + 1):

            dev._exp.Stop()

            # Optional: refresh XYZ each shot if you want; currently leave as once before
            try:
                base = _sanitize_name(_get_dev_filename_stem())
                if forced_fname:
                    base = base + " " + _sanitize_name(forced_fname)

                # Always read current stage position for Site(...)
                try:
                    x_um, y_um, z_um = self._read_current_position_um()
                    base = _replace_or_append_site(base, x_um, y_um, z_um, use_comma=True)
                except Exception as e:
                    print(f"Could not read stage position for filename: {e}")

                if shots > 1:
                    base = f"{base}_#{k:02d}"

                base = _append_persistent_note(base)

                dev.set_filename(base)
            except Exception:
                pass

            # if exposure provided, re-assert it (some SDKs reset)
            if time_s is not None:
                try:
                    ms = float(time_s) * 1000.0
                    dev.set_value(CameraSettings.ShutterTimingExposureTime, ms)
                except Exception:
                    pass

            # wait until not updating, then acquire
            try:
                while getattr(dev._exp, "IsUpdating", False):
                    time.sleep(0.05)
            except Exception:
                pass

            try:
                target_gui.acquire_callback()
            except Exception as e:
                print(f"acquire_callback failed on shot {k}: {e}")
                continue

            time.sleep(0.4)
            try:
                if getattr(dev._exp, "IsReadyToRun", True):
                    # restore default preview exposure if desired by you
                    dev.set_value(CameraSettings.ShutterTimingExposureTime, 3000.0)
                    while getattr(dev._exp, "IsUpdating", False):
                        time.sleep(0.05)
                    if not no_preview and self.proEM_mode:
                        dev._exp.Preview()
            except Exception:
                pass


            # If not in proEM_mode, rename CSV now (per shot)
            if not self.proEM_mode:
                # 3) Locate saved CSV for this shot
                fp = getattr(dev, "last_saved_csv", None)
                if not fp or not os.path.isfile(fp):
                    save_dir = getattr(dev, "save_directory", None)
                    if not save_dir:
                        print("No CSV found to rename.")
                        continue
                    matches = glob.glob(os.path.join(save_dir, "*.csv"))
                    if not matches:
                        print("No CSV found to rename.")
                        continue
                    fp = max(matches, key=os.path.getmtime)

        # Ensure we end at the original position
        try:
            _back_to_origin()
        except Exception:
            pass

        try:
            self._spc_running = False  # <— NEW: clear running
            self._spc_done_evt.set()
            print("SPC finished.")
        except Exception:
            pass
    def handle_message(self, arg):
        """Show large message window."""
        show_msg_window(arg)
    def handle_message_clear(self, arg):
        """Clear message window."""
        if dpg.does_item_exist("msg_Win"):
            dpg.delete_item("msg_Win")
        print("Message cleared.")
    def handle_set_xyz(self, arg):
        """Fill XYZ from current position."""
        p=self.get_parent()
        p.smaractGUI.fill_current_position_to_moveabs()
        print("XYZ filled.")
    def handle_update_note(self, arg):
        """Set or append to experiment notes.

        note <text>        -> set notes to <text>
        note !<text>       -> append <text> to existing notes
        note hide          -> hide/close the notes window
        """
        p = self.get_parent()
        raw = (arg or "").strip()

        # --- special: note hide / off / close -> hide the message window ---
        if raw.lower() in ("hide", "off", "close"):
            window_tag = "msg_Win"
            if dpg.does_item_exist(window_tag):
                # either delete or just hide; delete is fine since show recreates it
                try:
                    dpg.delete_item(window_tag)
                    print(f"Notes window '{window_tag}' closed.")
                except Exception as e:
                    print(f"Failed to close notes window '{window_tag}': {e}")
            else:
                print("Notes window not currently open.")
            return

        # --- normal behavior: set / append note text and show window ---
        # Determine new note text
        if raw.startswith("!"):
            append = raw[1:].strip()
            existing = getattr(p.opx, "expNotes", "")
            note_text = (existing + ", " + append).strip()
        else:
            note_text = raw.capitalize()

        show_msg_window(note_text)
        p.opx.expNotes = note_text

        # Update GUI text box if present
        if dpg.does_item_exist("inTxtScan_expText"):
            dpg.set_value("inTxtScan_expText", note_text)
            p.opx.saveExperimentsNotes(note=note_text)
        print(f"Notes updated: {note_text}")
    def handle_set_attenuator(self, arg):
        """Set femto attenuator to percent."""
        p = self.get_parent()
        try:
            percent = float(arg.strip())
        except ValueError:
            print("Invalid syntax. Use: att<percent>, e.g. att12.5")
            return
        # Update GUI widget if it exists
        widget = "femto_attenuator"
        if dpg.does_item_exist(widget):
            dpg.set_value(widget, percent)
        else:
            print(f"Widget '{widget}' not found; value will still be applied.")
        # Apply to hardware and recalc future
        if hasattr(p, "femto_gui") and hasattr(p.opx, "pharos") \
                and hasattr(p.opx.pharos, "setBasicTargetAttenuatorPercentage"):
            try:
                p.opx.pharos.setBasicTargetAttenuatorPercentage(percent)
                print(f"Attenuator set to {percent:.1f}%")
                tag = getattr(p.femto_gui, "future_input_tag", None)
                if tag and dpg.does_item_exist(tag):
                    existing = dpg.get_value(tag) or ""
                    base = existing.split(",", 1)[0].strip()
                    newtxt = f"{base},{percent:.1f}%"
                    dpg.set_value(tag, newtxt)
                    p.femto_gui.calculate_future(None, None, None)
                    print(f"Future attenuator set to {percent:.1f}% and recalculated.")
            except Exception as e:
                print(f"Failed to set attenuator: {e}")
        else:
            print("Femto GUI or Pharos API not available.")
    def handle_future(self, arg):
        """Parse future pulses input, update widgets, and calculate femto-pulse steps."""
        p = self.get_parent()
        future_args = arg.strip()

        # 1) Syntax check
        if not future_args:
            print("Syntax: future <start:step:end,percent>xN [mode1|mode0]")
            return

        # 2) Cancel with '!'
        if future_args.startswith("!"):
            return

        # 3) Ensure femto_gui and input tag exist
        if not hasattr(p, "femto_gui"):
            print("Femto GUI not available.")
            return

        tag = getattr(p.femto_gui, "future_input_tag", None)
        if not tag or not dpg.does_item_exist(tag):
            print("Future input widget not found.")
            return

        # 4) Extract and clean mode override
        mode = dpg.get_value(p.femto_gui.combo_tag) if dpg.does_item_exist(p.femto_gui.combo_tag) else "Default"
        lower_arg = future_args.lower()
        if "mode1" in lower_arg or "mode 1" in lower_arg:
            mode = "Compressor1"
        elif "mode0" in lower_arg or "mode 0" in lower_arg:
            mode = "Default"

        # Remove mode tokens from string
        for token in ("mode1", "mode 1", "mode0", "mode 0"):
            future_args = future_args.replace(token, "")
        future_args = future_args.strip()

        # 5) Write cleaned input to GUI
        dpg.set_value(tag, future_args)

        # 6) Parse input
        parts = future_args.split(",", 1)
        range_part = parts[0].strip()
        att_value = None
        pulse_count = 1

        if len(parts) > 1:
            att_part = parts[1].strip()
            if "x" in att_part:
                try:
                    att_str, x_part = att_part.split("x", 1)
                    att_value = float(att_str.strip().rstrip("%"))
                    pulse_count = int(x_part.strip())
                except Exception:
                    print("Invalid attenuation or pulse count format.")
                    return
            else:
                try:
                    att_value = float(att_part.strip().rstrip("%"))
                except Exception:
                    print("Invalid attenuation value.")
                    return

            if dpg.does_item_exist("femto_attenuator"):
                dpg.set_value("femto_attenuator", att_value)
                print(f"Attenuator set to {att_value}%")
                try:
                    p.opx.pharos.setBasicTargetAttenuatorPercentage(att_value)
                except Exception as e:
                    print(f"Failed to set Pharos attenuator: {e}")
            else:
                print("Attenuator input widget not found.")

        # 7) Parse range and set angle
        try:
            start, step, end = [float(x) for x in range_part.split(":")]
            if dpg.does_item_exist("femto_increment_hwp"):
                dpg.set_value("femto_increment_hwp", step)
                print(f"HWPInc set to {step}")
            else:
                print("HWPInc input widget not found.")

            if hasattr(p.opx, "set_hwp_angle"):
                p.opx.set_hwp_angle(start)
            if dpg.does_item_exist(p.kdc_101_gui.position_input_tag):
                dpg.set_value(p.kdc_101_gui.position_input_tag, start)
            self.handle_set_angle(start)

        except Exception:
            print("Invalid range format. Expected format: start:step:end")
            return

        # 8) Anneal pulse parameters
        if pulse_count is not None:
            if dpg.does_item_exist("femto_anneal_pulse_count"):
                dpg.set_value("femto_anneal_pulse_count", pulse_count - 1)
                print(f"nPlsAnn set to {pulse_count - 1}")
            if dpg.does_item_exist("femto_increment_hwp_anneal"):
                val = 0.01 if pulse_count > 1 else 0.0
                dpg.set_value("femto_increment_hwp_anneal", val)
                print(f"HWPAnn set to {val}")

        # 9) Call Femto GUI future calculation
        try:
            Ly = p.femto_gui.calculate_future(sender=None, app_data=None, user_data=None)
            print(f"Future calculation done for input: {arg.strip()}")

            if Ly and dpg.does_item_exist("inInt_Ly_scan") and Ly > 0:
                dpg.set_value("inInt_Ly_scan", int(Ly))
                p.opx.Update_Ly_Scan(user_data=int(Ly))
                print(f"Ly set to {int(Ly)} nm in scan settings.")
                p.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                p.opx.Update_dY_Scan("inInt_dy_scan", 2000)
            else:
                print("Ly is 0 or inInt_Ly_scan not found.")
        except Exception as e:
            print(f"Error calculating future: {e}")
    def handle_femto_calculate(self, arg):
        """Press femto calculate."""
        p=self.get_parent()
        p.femto_gui.calculate_button()
        print("Femto calculate pressed.")
    def handle_femto_pulses(self, arg):
        """Trigger Femto pulses in OPX GUI."""
        p = self.get_parent()
        # 1) Existence check
        if hasattr(p, "opx") and hasattr(p.opx, "btnFemtoPulses"):
            try:
                self.handle_enable_pharos()
                # 2) Ensure dx=2000
                if dpg.does_item_exist("inInt_dx_scan"):
                    p.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                    print("dx step set to 2000 nm")
                else:
                    print("DX input widget not found.")
                # 3) Ensure dy=2000
                if dpg.does_item_exist("inInt_dy_scan"):
                    p.opx.Update_dY_Scan("inInt_dy_scan", 2000)
                    print("dy step set to 2000 nm")
                else:
                    print("DY input widget not found.")
                # 4) Fire the pulses
                p.opx.btnFemtoPulses()
                print("Femto pulses triggered (btnFemtoPulses called).")
            except Exception as e:
                print(f"Error calling btnFemtoPulses: {e}")
        else:
            print("OPX or btnFemtoPulses method not available.")
    def handle_fill_span(self, arg):
        """Compute dx, dy, Lx, Ly from the loaded scan and fill the Scan Parameters inputs."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)

        try:
            if gui.scan_data is None or gui.idx_scan is None:
                print("No scan is loaded—can't fill span.")
                return

            # XY slice at the current Z index
            z_idx = gui.idx_scan[Axis.Z.value]
            arrXY = gui.scan_data[z_idx, :, :]
            ny, nx = arrXY.shape

            # --- CAST TO FLOAT ---
            x0 = float(gui.startLoc[0])
            y0 = float(gui.startLoc[1])
            x1 = float(gui.endLoc[0])
            y1 = float(gui.endLoc[1])

            # compute spans (in nm)
            Lx_um = (x1 - x0)*1e-6
            Ly_um = (y1 - y0)*1e-6
            dx_nm = Lx_um / (nx - 3)
            dy_nm = Ly_um / (ny - 2)

            # push into your scan parameters UI
            gui.Update_dX_Scan(app_data=None, user_data=int(round(dx_nm*1e3)))
            gui.Update_Lx_Scan(app_data=None, user_data=round(Lx_um))
            gui.Update_dY_Scan(app_data=None, user_data=int(round(dy_nm*1e3)))
            gui.Update_Ly_Scan(app_data=None, user_data=round(Ly_um))

            print(
                f"Filled span → dx={dx_nm:.3f}nm, dy={dy_nm:.3f}nm, "
                f"Lx={Lx_um:.3f}µm, Ly={Ly_um:.3f}µm"
            )

        except Exception as e:
            print(f"fill span failed: {e}")
    def handle_prepare_for_scan(self,arg):
        """Stop camera live view & retract flippers."""
        self.handle_toggle_sc(reverse=False)
    def handle_start_camera(self,arg):
        """Start camera live view & extend flippers."""
        self.handle_toggle_sc(reverse=True)
    def handle_stop_scan(self, arg):
        """Stop scan.
        - 'stp' / 'stop'           -> normal stop (restore at end)
        - 'stp scan' / 'stop scan' -> stop and KEEP current galvo/stage (no restore)
        """
        try:
            p = self.get_parent()
            keep = str(arg or "").strip().lower() == "scan"
            if keep:
                p.opx.stopScanNoRestore = True
            p.opx.btnStop() # stop OPX/QUA job if running
            if keep:
                print("Scan stopped. Keeping current position and galvo voltages (no restore).")
            else:
                print("Stopped.")
        except Exception:
            pass
    def handle_set_angle(self, arg):
        """Set HWP angle and wait until the hardware reaches it."""
        p = self.get_parent()
        try:
            ang = float(arg)
            # send the move command
            p.opx.set_hwp_angle(ang)
            # if you have a GUI element to refresh, do it once immediately
            if hasattr(p, "kdc_101_gui"):
                p.kdc_101_gui.read_current_angle()

            # now poll the actual position until it’s within 0.01°
            # assuming p.kdc_101.get_current_position() returns the live angle
            current = p.opx.kdc_101.get_current_position()
            while abs(current - ang) > 0.01:
                time.sleep(0.2)
                # update the GUI readout if available
                if hasattr(p, "kdc_101_gui"):
                    p.opx.kdc_101_gui.read_current_angle()
                current = p.opx.kdc_101.get_current_position()

            # one final GUI refresh
            if hasattr(p, "kdc_101_gui"):
                p.kdc_101_gui.read_current_angle()

            print(f"HWP angle reached: {current:.2f}° (target {ang:.2f}°)")
        except Exception as e:
            print(f"angle failed: {e}")
    def handle_start_scan(self, arg):
        """
        Start OPX scan.

        Usage:
          stt              : fresh scan
          stt add          : add to previous scan (accumulate)
          stt left         : fresh scan with X all to the left
          stt add left     : add-scan with X all to the left
          stt q            : scan queried XY (plot query)
          stt p            : scan queried XY from ProEM ROI (dispatcher fields)
          (if both q and p present, 'p' (ProEM) takes priority)
        """
        p = self.get_parent()
        parts = [t for t in (arg or "").strip().lower().split() if t]

        add_scan = ("add" in parts)
        is_left_scan = ("left" in parts)
        use_queried_proem = ("p" in parts) or ("proem" in parts)
        use_queried_area = (("q" in parts) or ("query" in parts)) and not use_queried_proem

        try:
            # sync position + stop camera/previous job
            p.smaractGUI.fill_current_position_to_moveabs()
            self.handle_toggle_sc(reverse=False)

            # if ProEM path: refresh ROI in the dispatcher (no p.opx)
            if use_queried_proem and hasattr(self, "refresh_proem_query_from_lightfield"):
                self.refresh_proem_query_from_lightfield()

            # kick off OPX scan; make sure OPX btnStartScan accepts the extra kwargs
            p.opx.add_scan = add_scan
            p.opx.is_left_scan =is_left_scan
            p.opx.use_queried_proem =use_queried_proem
            p.opx.use_queried_area =use_queried_area
            p.opx.btnStartScan()

            mode = "add" if add_scan else "fresh"
            side = " (left)" if is_left_scan else ""
            src = " [plot-query]" if use_queried_area else (" [ProEM-ROI]" if use_queried_proem else "")
            print(f"Scan started: {mode}{side}{src}.")

        except Exception as e:
            print(f"Error Start Scan: {e}")
    def handle_start_scan_with_galvo(self, arg):
        """
        Start OPX scan with Galvo.
        kst            -> default (X:-L..0, Y:centered)
        kst q          -> use plot query bounds
        kst p          -> use ProEM ROI bounds
        kst c          -> center X & Y ([-L/2, +L/2])
        kst left       -> X: centered range, start at left (overrides 'c' for X)
        kst right      -> X: centered range, start at right (overrides 'c' for X)
        kst top        -> Y: start at 0 and go up to +L (overrides 'c' for Y)
        kst top left   -> combine both
        kst add ...    -> keep 'add' flag
        kst r          -> alias for 'right'
        """
        p = self.get_parent()
        parts = (arg or "").strip().lower().split()

        # reset flags
        p.opx.add_scan = False
        p.opx.use_queried_area = False
        p.opx.use_queried_proem = False
        p.opx.centered_xy = False
        p.opx.start_top = False
        p.opx.start_left = False

        # parse
        p.opx.add_scan = "add" in parts
        if "q" in parts:
            p.opx.use_queried_area = True
        if "p" in parts:
            p.opx.use_queried_proem = True
        if "c" in parts:
            p.opx.centered_xy = True

        # new flags (order-agnostic)
        if "left" in parts:
            p.opx.centered_xy = False
            p.opx.start_left = True
        if ("right" in parts) or ("r" in parts):
            p.opx.centered_xy = False  # override 'c' for X
            p.opx.start_left = False
        if "top" in parts:
            p.opx.start_top = True

        try:
            p.smaractGUI.fill_current_position_to_moveabs()
            self.handle_toggle_sc(reverse=False)

            p.opx.btnStartGalvoScan()  # scan worker will read the opx flags directly
            print(
                "Scan started. "
                f"add={p.opx.add_scan}, queried_area={p.opx.use_queried_area}, "
                f"centered_xy={p.opx.centered_xy}, start_left={p.opx.start_left}, start_top={p.opx.start_top}"
            )
        except Exception as e:
            print(f"Error Start Scan: {e}")
    def handle_set_dx(self, arg):
        """Set dx scan step."""
        p=self.get_parent()
        try:
            dx=int(arg); p.opx.Update_dX_Scan("inInt_dx_scan",dx)
            print(f"dx={dx}")
        except:
            print("dx failed.")
    def handle_set_dy(self, arg):
        """Set dy scan step."""
        p=self.get_parent()
        try:
            dy=int(arg); p.opx.Update_dY_Scan("inInt_dy_scan",dy)
            print(f"dy={dy}")
        except:
            print("dy failed.")
    def handle_toggle_or_set_dz(self, arg):
        """Toggle or set dz scan step."""
        p=self.get_parent()
        if arg:
            try:
                dz=int(arg); p.opx.Update_dZ_Scan("inInt_dz_scan",dz)
                print(f"dz={dz}")
            except:
                print("dz set failed.")
        else:
            cur=dpg.get_value("chkbox_bZ_Scan")
            dpg.set_value("chkbox_bZ_Scan",not cur)
            print(f"dz toggled to {not cur}")
    def handle_set_all_steps(self, arg):
        """Set dx, dy, and dz scan step sizes to the same value."""
        p = self.get_parent()
        # 1) Parse the value as an integer
        try:
            v = int(arg.strip())
        except ValueError:
            print("Invalid syntax. Use: allsteps<value>, e.g. allsteps200")
            return
        # 2) Update each axis in turn, with the same print style as individual commands
        try:
            p.opx.Update_dX_Scan("inInt_dx_scan", v)
            print(f"-> dx set to {v} nm")
        except Exception as e:
            print(f"-> failed to set dx: {e}")
        try:
            p.opx.Update_dY_Scan("inInt_dy_scan", v)
            print(f"-> dy set to {v} nm")
        except Exception as e:
            print(f"-> failed to set dy: {e}")
        try:
            p.opx.Update_dZ_Scan("inInt_dz_scan", v)
            print(f"-> dz set to {v} nm")
        except Exception as e:
            print(f"-> failed to set dz: {e}")
    def handle_set_Lx(self, arg):
        """Set Lx scan length."""
        p=self.get_parent()
        try:
            Lx=float(arg); p.opx.Update_Lx_Scan(user_data=Lx)
            print(f"Lx={Lx}")
        except:
            print("lx failed.")
    def handle_set_Ly(self, arg):
        """Set Ly scan length."""
        p=self.get_parent()
        try:
            Ly=float(arg); p.opx.Update_Ly_Scan(user_data=Ly)
            print(f"Ly={Ly}")
        except:
            print("ly failed.")
    def handle_set_Lz(self, arg):
        """Set Lz scan length."""
        p=self.get_parent()
        try:
            Lz=float(arg); p.opx.Update_Lz_Scan(user_data=Lz)
            print(f"Lz={Lz}")
        except:
            print("lz failed.")
    def handle_save_history(self, arg=None):
        """Save command history and '>' macros to files. Optional suffix: savehist <suffix>"""
        import json, os
        p = self.get_parent()
        suffix = (arg or "").strip()
        hist_fn = f"history_{suffix}.txt" if suffix else "history.txt"
        macro_fn = f"macros_{suffix}.json" if suffix else "macros.json"
        try:
            with open(hist_fn, "w", encoding="utf-8") as f:
                for cmd in getattr(p, "command_history", []):
                    f.write(cmd + "\n")
            with open(macro_fn, "w", encoding="utf-8") as mf:
                json.dump(getattr(self, "cmd_macros", {}), mf, ensure_ascii=False, indent=2)
            print(f"History and macros saved to: {hist_fn}, {macro_fn}")
        except Exception as e:
            print(f"savehistory failed: {e}")
    def handle_load_history(self, arg):
        """Load command history and '>' macros from files. Optional suffix: loadhist <suffix>"""
        import json, os
        p = self.get_parent()
        suffix = (arg or "").strip()
        hist_fn = f"history_{suffix}.txt" if suffix else "history.txt"
        macro_fn = f"macros_{suffix}.json" if suffix else "macros.json"
        try:
            with open(hist_fn, encoding="utf-8") as f:
                p.command_history = [l.rstrip("\n") for l in f]
            try:
                with open(macro_fn, encoding="utf-8") as mf:
                    self.cmd_macros = json.load(mf)
            except FileNotFoundError:
                self.cmd_macros = {}
            print(f"History and macros loaded from: {hist_fn}, {macro_fn}")
        except Exception as e:
            print(f"loadhistory failed: {e}")
    def handle_del_history(self, arg):
        """Clears command history and '>' macros (memory) and deletes files. Optional suffix: delhist <suffix>"""
        import os, json
        p = self.get_parent()
        suffix = (arg or "").strip()
        hist_fn = f"history_{suffix}.txt" if suffix else "history.txt"
        macro_fn = f"macros_{suffix}.json" if suffix else "macros.json"

        # clear in-memory
        p.command_history = []
        p.history_index = 0
        self.cmd_macros = {}
        print("Command history and macros cleared (memory).")

        # delete files if present
        for fn in (hist_fn, macro_fn):
            try:
                os.remove(fn)
                print(f"Deleted file: {fn}")
            except FileNotFoundError:
                pass
            except Exception as e:
                print(f"Failed to delete {fn}: {e}")
        return
    def handle_save_processed_image(self, arg):
        """Save processed image from Zelux."""
        p=self.get_parent()
        try:
            fn = p.cam.SaveProcessedImage()
            notes=getattr(p.opx,"expNotes","")
            if notes:
                base,ext=os.path.splitext(fn)
                new=f"{base}_{notes}{ext}"
                os.replace(fn,new)
                print(f"Image saved as {new}")
            else:
                print(f"Image saved as {fn}")
        except:
            print("sv failed.")
    def handle_list_windows(self, arg):
        """List all DPG windows."""
        items = dpg.get_all_items()
        wins = [(dpg.get_item_alias(i), i) for i in items if "Window" in dpg.get_item_type(i)]
        print("DPG Windows:")
        for alias,item in wins:
            print(f" {alias} shown={dpg.is_item_shown(item)}")
    def handle_show_window(self, arg):
        """Show a DPG window."""
        t=arg.strip()
        if dpg.does_item_exist(t):
            dpg.show_item(t); print(f"{t} shown.")
        else:
            print(f"{t} not found.")
    def handle_hide_window(self, arg):
        """Hide a DPG window."""
        t=arg.strip()
        if dpg.does_item_exist(t):
            dpg.hide_item(t); print(f"{t} hidden.")
        else:
            print(f"{t} not found.")
    def handle_copy_scan_position(self, arg):
        """Copy OPX initial scan Location to clipboard."""
        try:
            import pyperclip
            p=self.get_parent()
            x,y,z = [v*1e-6 for v in p.opx.initial_scan_Location]
            s=f"Site ({x:.1f},{y:.1f},{z:.1f})"
            pyperclip.copy(s)
            print(f"Copied {s}")
        except:
            print("scpos failed.")
    def handle_set_exposure(self, arg):
        """Set Zelux camera exposure."""
        try:
            ms=float(arg)*1e3
            p=self.get_parent()
            p.cam.cam.SetExposureTime(int(ms))
            time.sleep(0.001)
            actual = p.cam.cam.camera.exposure_time_us/1e3
            dpg.set_value("slideExposure", actual)
            print(f"Exposure {actual:.1f} ms")
        except:
            print("exp failed.")
    def handle_display_slices(self, arg):
        """
        Run Z-slices viewer.

        - Use 'disp clip' to read scan_data or G2 graph from clipboard image's Alt Text (PowerPoint).
         - If scan_data → display Z-slices
         - If g2_graph → plot G2 correlation
         - If spc_data → plot spectrum
        - Use 'disp tif' to display the latest TIFF saved by LightField.
        """
        from pathlib import Path
        import cv2
        import numpy as np
        def _resolve_existing_scan_file(fn: str, move_subfolder_tag: str = "MoveSubfolderInput") -> str | None:
            """
            Try to resolve an existing scan file:
              - normalize slashes
              - try the subfolder from MoveSubfolderInput
              - search under the 'scan' root if still missing
            Returns the resolved absolute path or None.
            """
            if not fn:
                return None

            # 1) Normalize slashes like Q:/...\\... -> Q:\...
            pth = Path(os.path.normpath(str(fn)))
            if pth.is_file():
                return str(pth)

            # 2) Figure out the base 'scan' directory from the provided path
            parts_lower = [s.lower() for s in pth.parts]
            base = pth.parent
            if "scan" in parts_lower:
                idx = parts_lower.index("scan")
                base = Path(*pth.parts[:idx + 1])  # .../scan

            # 3) Try the GUI-provided subfolder (e.g., "10-8-25")
            subfolder = None
            try:
                if dpg.does_item_exist(move_subfolder_tag):
                    subfolder = dpg.get_value(move_subfolder_tag)
            except Exception:
                subfolder = None

            if subfolder:
                candidate = base / str(subfolder) / pth.name
                if candidate.is_file():
                    return str(candidate)

            # 4) Fallback: search under base for the basename
            try:
                matches = list(base.rglob(pth.name))
            except Exception:
                matches = []

            if matches:
                # Prefer a match in the selected subfolder if present
                if subfolder:
                    for m in matches:
                        if m.parent.name == str(subfolder):
                            return str(m)
                # Otherwise pick the newest
                matches.sort(key=lambda m: m.stat().st_mtime, reverse=True)
                return str(matches[0])

            return None

        try:
            fn = None
            p=self.get_parent()
            arg_clean = arg.strip().lower()

            base_dir = None
            if arg_clean == "tif":
                base_dir = Path(r"C:\Users\Femto\Work Folders\Documents\LightField")

            elif arg_clean == "tif1":
                base_dir = Path(r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer")

            if arg_clean in ("tif","tif1"):
                if not base_dir.exists():
                    print(f"LightField folder not found: {base_dir}")
                    return

                # search recursively for .tif/.tiff and pick the newest by mtime
                matches = list(base_dir.rglob("*.tif")) + list(base_dir.rglob("*.tiff"))
                if not matches:
                    print(f"No .tif/.tiff files found under: {base_dir}")
                    return

                latest = max(matches, key=lambda m: m.stat().st_mtime)
                print(f"Opening latest TIFF: {latest}")

                # launch the existing viewer
                subprocess.Popen([sys.executable, "Utils/python_displayer.py", str(latest)])
                return

            if arg_clean == "temp":
                from pathlib import Path

                base_dir = Path(r"C:\temp\TempScanData")
                if not base_dir.exists():
                    print(f"TempScanData folder not found: {base_dir}")
                    return

                # Find most recent CSV
                csv_files = sorted(base_dir.glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True)
                if not csv_files:
                    print("No CSV files found in TempScanData.")
                    return

                latest_file = csv_files[0]
                print(f"Displaying most recent CSV: {latest_file.name}")

                try:
                    disp.display_all_z_slices(str(latest_file))  # Only filepath passed
                except Exception as e:
                    print(f"disp failed: {e}")
                return

            if arg_clean == "clip":
                # 1. Grab image from clipboard
                img = ImageGrab.grabclipboard()
                if not isinstance(img, Image.Image):
                    print("No image found in clipboard.")
                    return
                # 2. Access PowerPoint and look for shape with that image
                pythoncom.CoInitialize()
                ppt = win32com.client.Dispatch("PowerPoint.Application")
                if ppt.Presentations.Count == 0:
                    print("No PowerPoint presentations open.")
                    return
                pres = ppt.ActivePresentation
                slide = ppt.ActiveWindow.View.Slide
                # Try to find the most recently added shape with alt text
                alt_text = None
                for shape in slide.Shapes:
                    if shape.Type == 13:  # msoPicture
                        if shape.AlternativeText.strip():
                            alt_text = shape.AlternativeText.strip()
                            break
                if not alt_text:
                    print("No metadata found in Alt Text of pasted image.")
                    return
                try:
                    meta_data = json.loads(alt_text)
                    # Extract and print x, y, and future from Alt Text
                    x = meta_data.get("x")
                    y = meta_data.get("y")
                    future = meta_data.get("future")
                    filename = meta_data.get("filename")
                    print(f"Position: x = {x}, y = {y}")
                    print(f"Future command: {future}")
                    print(f"Filename: {filename}")
                    fn = meta_data.get("scan_data")
                    if fn:
                        disp.display_all_z_slices(data=fn)
                    elif "g2_graph" in meta_data:
                        graph = meta_data["g2_graph"]
                        X = graph.get("X_vec", [])
                        Y = graph.get("Y_vec", [])
                        g2_val = graph.get("g2_value", None)
                        iteration = graph.get("iteration", "?")
                        total_counts = graph.get("total_counts", "?")
                        # Plot the G2 graph
                        dpg.set_item_label("graphXY",
                                           f"G2, Iteration = {iteration}, Total Counts = {total_counts}, g2 = {g2_val:.3f}")
                        dpg.set_value("series_counts", [X, Y])
                        dpg.set_value("series_counts_ref", [[], []])
                        dpg.set_value("series_counts_ref2", [[], []])
                        dpg.set_value("series_res_calcualted", [[], []])
                        dpg.set_item_label("series_counts", "G2 val")
                        dpg.set_item_label("series_counts_ref", "_")
                        dpg.set_item_label("series_counts_ref2", "_")
                        dpg.set_item_label("series_res_calcualted", "_")
                        dpg.set_item_label("y_axis", "events")
                        dpg.set_item_label("x_axis", "dt [nsec]")
                        dpg.fit_axis_data("x_axis")
                        dpg.fit_axis_data("y_axis")
                        dpg.bind_item_theme("series_counts", "LineYellowTheme")
                        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                        dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
                        dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")
                        print("G2 graph plotted from Alt Text.")
                    elif "spc_data" in meta_data:
                        spc = meta_data["spc_data"]
                        X = spc.get("X", [])
                        Y = spc.get("Y", [])
                        label = spc.get("label", "Spectrum")
                        tag = p.hrs_500_gui.series_tag
                        if dpg.does_item_exist(tag):
                            dpg.set_value(tag, [X, Y])
                        else:
                            dpg.add_line_series(X, Y, label=label,
                                                parent=f"y_axis_{p.hrs_500_gui.prefix}",
                                                tag=tag)
                        dpg.set_item_label(f"graphXY_{p.hrs_500_gui.prefix}", label)
                        dpg.fit_axis_data(f"x_axi_{p.hrs_500_gui.prefix}")
                        dpg.fit_axis_data(f"y_axis_{p.hrs_500_gui.prefix}")
                        print("✅ Spectrum plotted from Alt Text.")
                    else:
                        print("No scan_data, g2_graph, or spc_data found in metadata.")
                except Exception as e:
                    print(f"Failed to parse Alt Text metadata: {e}")
                    return

            # --- helpers for site-averaging series like:  "Site (...)_#10 21-10-2025 17_04_00.tif"
            import re
            def _find_latest_numbered_tif(roots):
                # newest .tif anywhere under roots that has pattern _#NN (NN two digits)
                cands = []
                for root in roots:
                    if not root.exists():
                        continue
                    try:
                        for m in root.rglob("*.tif"):
                            if re.search(r"_#\d{2}\b", m.name):
                                cands.append(m)
                        for m in root.rglob("*.tiff"):
                            if re.search(r"_#\d{2}\b", m.name):
                                cands.append(m)
                    except Exception:
                        pass
                if not cands:
                    return None
                cands.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                return cands[0]

            def _series_from_latest(latest: "Path"):
                """
                From 'Prefix_#NN rest.tif', build the full series with same 'Prefix_' (before _#)
                Return sorted ascending by # (01..NN)
                """
                name = latest.name
                m = re.search(r"^(.*)_#(\d{2})\b", name)
                if not m:
                    return []
                prefix = m.group(1)  # everything before _#NN
                folder = latest.parent
                series = []
                for p in folder.glob("*.tif"):
                    if p.name.startswith(prefix + "_#") and re.search(r"_#\d{2}\b", p.name):
                        series.append(p)
                for p in folder.glob("*.tiff"):
                    if p.name.startswith(prefix + "_#") and re.search(r"_#\d{2}\b", p.name):
                        series.append(p)

                # sort by their NN number
                def _num(pth):
                    mm = re.search(r"_#(\d{2})\b", pth.name)
                    return int(mm.group(1)) if mm else -1

                series.sort(key=_num)  # 01..NN
                return series

            def _imread_16(path_str):
                # Prefer tifffile if present to preserve dtype; else fallback to cv2
                try:
                    import tifffile as tiff
                    arr = tiff.imread(str(path_str))
                    return arr
                except Exception:
                    img = cv2.imread(str(path_str), cv2.IMREAD_UNCHANGED)
                    return img

            def _imwrite_16(path_str, img):
                try:
                    import tifffile as tiff
                    tiff.imwrite(str(path_str), img)
                    return True
                except Exception:
                    return cv2.imwrite(str(path_str), img)

            # ---------- NEW: disp avg / siteavg ----------
            if arg_clean in ("avg", "siteavg"):
                roots = [
                    Path(r"C:\Users\Femto\Work Folders\Documents\LightField"),
                    Path(r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"),
                ]
                latest = _find_latest_numbered_tif(roots)
                if latest is None:
                    print("No numbered TIF (pattern *_#NN*.tif) found in the search roots.")
                    return
                series = _series_from_latest(latest)
                if not series:
                    print(f"No series found for prefix of: {latest.name}")
                    return

                print(f"Found series of {len(series)} image(s) for: {latest.name}")

                first = _imread_16(series[0])
                if first is None:
                    print(f"Failed to read: {series[0]}")
                    return

                # ------------------------
                # siteavg = plain mean
                # avg     = pairwise abs-diff mean to suppress DC
                # ------------------------
                if arg_clean == "siteavg":
                    acc = np.zeros_like(first, dtype=np.float64)
                    used = 0
                    for pth in series:
                        im = _imread_16(pth)
                        if im is None or im.shape != first.shape:
                            print(f"Skipping (shape mismatch): {pth.name}")
                            continue
                        acc += im.astype(np.float64)
                        used += 1
                    if used == 0:
                        print("No usable frames to average.")
                        return
                    out = acc / float(used)
                    out_name = re.sub(r"_#\d{2}\b.*$", "", latest.name) + "_AVG.tif"
                else:
                    # arg_clean == "avg" → pairwise abs-diff
                    diffsum = np.zeros_like(first, dtype=np.float64)
                    pairs = 0
                    for k in range(0, len(series) - 1, 2):
                        im1 = _imread_16(series[k])
                        im2 = _imread_16(series[k + 1])
                        if (im1 is None) or (im2 is None) or (im1.shape != first.shape) or (im2.shape != first.shape):
                            print(
                                f"Skipping pair #{k // 2 + 1} (missing/shape mismatch): {series[k].name} / {series[k + 1].name}")
                            continue
                        # absolute difference to remove common DC pedestal
                        d = np.abs(im2.astype(np.float64) - im1.astype(np.float64))
                        diffsum += d
                        pairs += 1

                    if pairs == 0:
                        print("No valid pairs for DC-suppressed averaging (need at least two frames).")
                        return

                    out = diffsum / float(pairs)
                    out_name = re.sub(r"_#\d{2}\b.*$", "", latest.name) + "_AVGDIFF.tif"

                # Convert back to a displayable dtype
                if first.dtype == np.uint16:
                    out = np.clip(np.rint(out), 0, 65535).astype(np.uint16)
                elif first.dtype == np.uint8:
                    out = np.clip(np.rint(out), 0, 255).astype(np.uint8)
                else:
                    # keep float if it was float
                    out = out.astype(first.dtype, copy=False)

                out_path = latest.parent / out_name
                if _imwrite_16(out_path, out):
                    print(f"Average written: {out_path}")
                    subprocess.Popen([sys.executable, "Utils/python_displayer.py", str(out_path)])
                else:
                    print(f"Failed to write avg TIF: {out_path}")
                return

            # ---------- Pattern search: e.g. "*16_47_54.tif" or "scan123" ----------
            # If the arg isn't one of the known keywords, treat it as a filename pattern
            if arg and arg_clean not in ("tif", "tif1", "temp", "clip"):
                # sanitize incoming pattern (allow quotes/wildcards)
                pattern = arg.strip().strip('"').strip("'")
                # if no wildcard provided, search by substring
                if not any(ch in pattern for ch in "*?"):
                    # if user didn't specify an extension, search common ones
                    # We'll try tif/tiff/csv automatically by expanding the pattern
                    exts = [".tif", ".tiff", ".csv"] if "." not in os.path.basename(pattern) else [""]
                    patterns = [f"*{pattern}*{ext}" for ext in exts] if exts != [""] else [f"*{pattern}*"]
                else:
                    patterns = [pattern]

                # candidate roots to search
                roots = [
                    Path(r"C:\Users\Femto\Work Folders\Documents\LightField"),
                    Path(r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"),
                    Path.cwd(),
                ]

                matches = []
                for root in roots:
                    if not root.exists():
                        continue
                    for pat in patterns:
                        try:
                            # Path.rglob uses glob-style patterns
                            matches.extend([m for m in root.rglob(pat) if m.is_file()])
                        except Exception:
                            pass

                if not matches:
                    print(f'No files found matching pattern(s): {patterns} in roots: {", ".join(str(r) for r in roots if r.exists())}')
                    return

                # Prefer newest by modification time
                matches.sort(key=lambda m: m.stat().st_mtime, reverse=True)
                target = matches[0]
                print(f"Opening match: {target}")
                subprocess.Popen([sys.executable, "Utils/python_displayer.py", str(target)])
                return


            else:
                # Load from file
                fn = self.get_parent().opx.last_loaded_file
                resolved_fn = _resolve_existing_scan_file(fn)
                if not resolved_fn:
                    print("No last loaded file found or could not resolve it. "
                          "Check 'MoveSubfolderInput' and that the file exists under the 'scan' folder.")
                    return
                subprocess.Popen([sys.executable, "Utils/python_displayer.py", resolved_fn])
                # subprocess.Popen(["python", "Utils/python_displayer.py", fn])
                print("Displaying slices from file.")
        except Exception as e:
            print(f"disp failed: {e}")
    def handle_set_integration_time(self, arg):
        """Set/query integration time (ms).  Usage: 'int <ms>' or 'int ?'"""
        import re
        p = self.get_parent()
        opx = getattr(p, "opx", None)
        if opx is None:
            print("int: OPX not available.")
            return

        s = (arg or "").strip()
        if s == "?":
            ms = getattr(opx, "total_integration_time", None)
            print(f"int? -> {ms} ms" if ms is not None else "int? -> unknown")
            return

        m = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)\s*(?:ms)?\s*$", s, re.IGNORECASE)
        if not m:
            print("int failed. Usage: 'int <ms>' or 'int ?'")
            return

        ms = int(round(float(m.group(1))))
        try:
            # Use your OPX setter exactly as defined
            opx.UpdateCounterIntegrationTime(user_data=ms)
            self.handle_update_note(f"!Int {ms} ms")
        except Exception as e:
            print(f"int failed: {e}")
    def handle_nextrun(self, arg):
        """
        Enable or disable devices in system_info.xml:
          • nextrun hrs        → enable HRS_500
          • nextrun !hrs       → disable HRS_500
          • nextrun awg/key/keysight  → enable Keysight AWG
          • nextrun !awg/awg off      → disable Keysight AWG
        This will only unwrap/wrap the matching <Device>…</Device> block,
        leaving every other instrument block untouched (with all its line breaks).
        """
        import os, re

        action = arg.strip().lower()
        xml_path = os.path.join("SystemConfig", "xml_configs", "system_info.xml")

        # map commands to (instrument-tag, friendly name)
        DEVICES = {
            "hrs": ("HRS_500", "HRS_500"),
            "awg": ("keysight_awg", "Keysight AWG"),
            "key": ("keysight_awg", "Keysight AWG"),
            "keysight": ("keysight_awg", "Keysight AWG"),
        }

        # figure out which device + enable/disable
        for key, (instr, friendly) in DEVICES.items():
            if action in (key, f"{key} on"):
                enable = True
                break
            if action in (f"!{key}", f"{key} off"):
                enable = False
                break
        else:
            print(f"Unknown action: '{arg}'. Use 'nextrun hrs', 'nextrun !hrs', 'nextrun awg', etc.")
            return

        try:
            text = open(xml_path, "r", encoding="utf-8").read()

            # 1) Unwrap any already-commented block for this instrument:
            #    <!-- <Device>…<Instrument>{instr}</Instrument>…</Device> -->
            pat_unwrap = rf'<!--\s*(<Device>\s*<Instrument>{instr}</Instrument>[\s\S]*?</Device>)\s*-->'
            text = re.sub(pat_unwrap, r'\1', text, flags=re.DOTALL)

            # 2) If disabling, wrap the raw block in <!-- … -->; if enabling, leave as-is
            if not enable:
                pat_wrap = rf'(<Device>\s*<Instrument>{instr}</Instrument>[\s\S]*?</Device>)'
                text = re.sub(pat_wrap, r'<!--\1-->', text, flags=re.DOTALL)

            # 3) Write it back
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(text)

            state = "enabled" if enable else "disabled"
            print(f"{friendly} {state} for next run.")
        except Exception as e:
            print(f"Failed to process 'nextrun': {e}")
    def handle_help(self, arg: str | None = None):
        """Show help with searchable command list; 'help <cmd>' opens that command."""
        # Local imports to avoid module-level deps if you embed this function somewhere else
        import inspect
        import textwrap
        import difflib
        import functools

        # --- help catalog (handlers + extras like 'run') ---
        extras = {"run": self.run}
        catalog = dict(self.handlers)
        catalog.update(extras)

        # ---------- helpers ----------
        def _unwrap_callable(fn):
            """
            Return (base, meta) where base is the best callable for signature/doc extraction.
            meta includes binding/partial info.
            """
            meta = {"bound_to": None, "is_partial": False, "partial_args": (), "partial_kwargs": {}}

            # Bound method?
            if hasattr(fn, "__self__") and fn.__self__ is not None:
                meta["bound_to"] = fn.__self__.__class__.__name__
                base = getattr(fn, "__func__", fn)
            else:
                base = fn

            # functools.partial ?
            if isinstance(base, functools.partial):
                meta["is_partial"] = True
                meta["partial_args"] = base.args
                meta["partial_kwargs"] = base.keywords or {}
                base = base.func

            # Unwrap decorators (respects __wrapped__ if wraps() was used)
            try:
                base = inspect.unwrap(base)
            except Exception:
                pass

            return base, meta

        def _safe_signature(obj):
            import inspect
            try:
                return inspect.signature(obj)
            except Exception:
                pass
            call = getattr(obj, "__call__", None)
            if call:
                try:
                    return inspect.signature(call)
                except Exception:
                    pass
            return None

        def _get_doc(obj):
            import inspect
            doc = inspect.getdoc(obj)  # dedented or None
            if not doc:
                doc = getattr(obj, "HELP", None) or getattr(obj, "help", None)
            return (doc or "").rstrip()

        def _first_line(text: str) -> str:
            return text.strip().splitlines()[0] if text else ""

        def _aliases_for(fn_base):
            """Group all handler keys that point to the same underlying callable."""
            # Build once and cache map: id(base) -> [aliases]
            if not hasattr(_aliases_for, "_cache"):
                mapping = {}
                for k, fn in self.handlers.items():
                    b, _ = _unwrap_callable(fn)
                    mapping.setdefault(id(b), []).append(k)
                _aliases_for._cache = mapping
            return sorted(_aliases_for._cache.get(id(fn_base), []), key=str.lower)

        def _build_index():
            idx = []
            for k, fn in catalog.items():
                base, _ = _unwrap_callable(fn)
                idx.append((k, _first_line(_get_doc(base))))
            idx.sort(key=lambda t: t[0].lower())
            return idx

        def _usage_from_signature(cmd: str, sig):
            if not sig:
                return None
            import inspect as _insp
            params = []
            for p in sig.parameters.values():
                if p.name in ("self", "cls"):
                    continue
                if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
                    params.append(f"[{p.name}]")
                elif p.default is not _insp._empty:
                    params.append(f"[{p.name}=…]")
                else:
                    params.append(f"<{p.name}>")
            return f"{cmd} {' '.join(params)}".rstrip()

        def _format_detail(cmd: str, fn) -> str:
            base, meta = _unwrap_callable(fn)
            sig = _safe_signature(base)
            doc = _get_doc(base)

            lines = []
            # Header
            lines.append(f"{cmd}")
            lines.append("=" * max(4, len(cmd)))
            # Signature and usage
            if sig:
                lines.append(f"Signature: {cmd}{sig}")
                usage = _usage_from_signature(cmd, sig)
                if usage:
                    lines.append(f"Usage: {usage}")
            else:
                lines.append("Signature: (unavailable)")

            # Owner/Module/Qualname
            owner = meta["bound_to"]
            mod = getattr(base, "__module__", "(unknown)")
            qn = getattr(base, "__qualname__", getattr(base, "__name__", "(unknown)"))
            if owner:
                lines.append(f"Owner: {owner}")
            lines.append(f"Module: {mod}")
            lines.append(f"Object: {qn}")

            # Partial info
            if meta["is_partial"]:
                lines.append(f"Partial: args={meta['partial_args']}, kwargs={meta['partial_kwargs']}")

            # Aliases
            aliases = _aliases_for(base)
            if aliases:
                # Put the focused cmd first, then the rest
                ordered = [cmd] + [a for a in aliases if a != cmd]
                lines.append("Aliases: " + ", ".join(ordered))

            # Docstring
            lines.append("")
            lines.append(doc if doc else "(no documentation provided)")
            return "\n".join(lines)

        def _format_summary(index):
            width = max((len(k) for k, _ in index), default=12)
            out = []
            for k, doc in index:
                out.append(f"{k.ljust(width)}  -  {doc}")
            return "\n".join(out)

        # ---------- state ----------
        index = _build_index()
        full_help_text = _format_summary(index)

        # ---------- destroy prior window ----------
        if dpg.does_item_exist("help_window"):
            dpg.delete_item("help_window")

        # ---------- callbacks (close over index) ----------
        def _help_set_list(items):
            dpg.configure_item("help_cmd_list", items=items)
            if items:
                dpg.set_value("help_cmd_list", items[0])

        def _show_detail_for(cmd: str):
            fn = catalog.get(cmd)

            if not fn:
                dpg.set_value("help_text", f"Command '{cmd}' not found.")
                return
            dpg.set_value("help_text", _format_detail(cmd, fn))

        def _on_select(sender, app_data, user_data):
            _show_detail_for(app_data)

        def _search(sender=None, app_data=None, user_data=None):
            q = (dpg.get_value("help_search_input") or "").strip().lower()
            if not q:
                items = [k for k, _ in index]
                _help_set_list(items)
                dpg.set_value("help_text", full_help_text)
                return
            # Filter by substring in command or first-line doc
            filtered = [k for (k, doc) in index if (q in k.lower() or q in (doc or "").lower())]
            if not filtered:
                # Fuzzy suggestions
                candidates = [k for k, _ in index]
                fuzzy = difflib.get_close_matches(q, candidates, n=8, cutoff=0.5)
                if fuzzy:
                    _help_set_list(fuzzy)
                    _show_detail_for(fuzzy[0])
                else:
                    _help_set_list([])
                    dpg.set_value("help_text", f"No matches for '{q}'.")
                return
            _help_set_list(filtered)
            _show_detail_for(filtered[0])

        def _copy_detail(sender=None, app_data=None, user_data=None):
            text = dpg.get_value("help_text") or ""
            try:
                dpg.set_clipboard_text(text)
            except Exception:
                pass

        # ---------- UI ----------
        with dpg.window(tag="help_window", label="Command Help", width=820, height=520, autosize=False):
            # Top bar
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="help_search_input",
                    hint="Type to search… (Enter)",
                    width=300,
                    on_enter=True,
                    callback=_search
                )
                dpg.add_button(label="Lookup", callback=_search)
                dpg.add_button(label="Copy", callback=_copy_detail)
            # Split panes
            with dpg.group(horizontal=True):
                # Left: command list
                with dpg.child_window(width=240, height=-1, border=True):
                    dpg.add_text("Commands")
                    dpg.add_listbox(
                        tag="help_cmd_list",
                        items=[k for k, _ in index],
                        num_items=16,
                        callback=_on_select,
                        width=-1
                    )
                # Right: detail / text area
                with dpg.child_window(width=-1, height=-1, border=True):
                    dpg.add_input_text(
                        tag="help_text",
                        default_value=full_help_text,
                        multiline=True,
                        readonly=True,
                        width=-1,
                        height=-1
                    )

        # ---------- initial selection logic ----------
        initial_cmd = None
        if arg:
            q = str(arg).strip()
            if q in catalog:
                initial_cmd = q
            else:
                candidates = list(catalog.keys())
                match = difflib.get_close_matches(q, candidates, n=1, cutoff=0.6)
                if match:
                    initial_cmd = match[0]

        if initial_cmd:
            items = [k for k, _ in index]
            if initial_cmd in items:
                items.remove(initial_cmd)
                items.insert(0, initial_cmd)
            _help_set_list(items)
            _show_detail_for(initial_cmd)
        else:
            _help_set_list([k for k, _ in index])
    def _help_search(self):
        """Callback for help lookup."""
        query = dpg.get_value("help_search_input").strip().lower()
        if not query:
            print("Please type a search term first.")
            return

        matches = []
        for cmd, fn in self.handlers.items():
            if query in cmd.lower():
                doc = fn.__doc__.strip().splitlines()[0] if fn.__doc__ else ""
                matches.append(f"{cmd:<12} - {doc}")

        if matches:
            print("Help search results:")
            for line in matches:
                print("  " + line)
        else:
            print(f"No commands matching '{query}' found.")
    def handle_wait(self, arg):
        """Delay subsequent commands by <ms> then execute them."""
        # arg: "<ms> cmd1;cmd2;cmd3"
        parts = arg.strip().split(' ', 1)
        ms_str = parts[0]
        try:
            ms = int(ms_str)
        except ValueError:
            print(f"Invalid syntax. Use: wait<ms> <cmd1>;... Got '{ms_str}'")
            return

        if len(parts) == 1 or not parts[1].strip():
            time.sleep(ms / 1000.0)
            print("No commands to run after wait.")
            return

        # split remaining text into individual commands
        remaining = [c.strip() for c in parts[1].split(';') if c.strip()]

        def _delayed_runner():
            time.sleep(ms / 1000.0)
            print(f"[wait] {ms} ms elapsed -> now running {remaining}")
            if remaining:
                self.run("; ".join(remaining))

        threading.Thread(target=_delayed_runner, daemon=True).start()
        print(f"Started background wait for {ms}ms... deferring {remaining}")
    def handle_ocr(self, arg):
        """Perform OCR and set XYZ fields."""
        p=self.get_parent()
        try:
            img=ImageGrab.grabclipboard()
            proc=preprocess_image(img)
            txt=pytesseract.image_to_string(proc,config=TESSERACT_CONFIG)
            _,pos=extract_positions(txt)
            for i,ch in enumerate(("Ch0","Ch1","Ch2")):
                v=pos.get(ch)
                if v is not None:
                    dpg.set_value(f"mcs_ch{i}_ABS",v)
                    print(f"{ch}:{v:.2f}")
        except:
            print("ocr failed.")
    def handle_go(self, arg):
        """Move one or all axes: go, go0, go1, go2."""
        p=self.get_parent()
        key=arg.strip().lower()
        axes = {"":(0,1,2),"go0":(0,),"go1":(1,),"go2":(2,),"gox":(0,),"goy":(1,),"goz":(2,)}.get(key)
        if axes is None:
            print("Unknown go syntax.")
            return
        for ax in axes:
            p.smaractGUI.move_absolute(None,None,ax)
        print(f"Moved axes {axes}.")
    def handle_move0(self, arg):
        """Move axis0 (X) by the specified delta."""
        self._move_delta(0,arg)
    def handle_move1(self, arg):
        """Move axis1(Y) by the specified delta."""
        self._move_delta(1,arg)
    def handle_move2(self, arg):
        """Move axis2 (Z) by the specified delta."""
        self._move_delta(2,arg)
    def handle_moveX(self, arg):
        """move X axis by the specified delta."""
        self._move_delta(0,arg)
    def handle_moveY(self, arg):
        """move Y axis by the specified delta."""
        self._move_delta(1,arg)
    def handle_moveZ(self, arg):
        """move Z axis by the specified delta."""
        self._move_delta(2,arg)
        time.sleep(0.3)
    def _move_delta(self, axis, arg):
        p=self.get_parent()
        try:
            amount=int(float(arg)*1e6)
            p.smaractGUI.dev.MoveRelative(axis, amount)
            print(f"Axis {axis} moved by {amount*1e-6:.2f} um")
        except Exception as e:
            print(f"move{axis} failed {e}.")
    def handle_open_lastdir(self, arg):
        """With no arg: act as lastdir (copy last_scan_dir.txt).
        With a filepath: copy its folder and open it in Explorer."""
        arg_clean = arg.strip()

        # —— No argument: use last_scan_dir.txt
        if not arg_clean:
            try:
                last = open("last_scan_dir.txt").read().strip()
                folder = last.replace('/', '\\')
                pyperclip.copy(folder)
                print(f"Copied {folder}")
                # Verify the folder really exists
                if not os.path.isdir(folder):
                    print(f"Directory does not exist: {folder}")
                    return
                # Open with explorer, passing args as a list so explorer sees it correctly
                subprocess.Popen(["explorer", folder])
            except Exception:
                print("lastdir failed.")
            return
        # —— Argument given: treat it as a filepath
        path = arg_clean
        folder = os.path.dirname(path)
        if not folder:
            print(f"Could not determine directory for '{path}'.")
            return
        try:
            pyperclip.copy(folder)
            # Convert forward slashes to Windows backslashes
            folder = folder.replace('/', '\\')
            # Verify the folder really exists
            if not os.path.isdir(folder):
                print(f"Directory does not exist: {folder}")
                return
            # Open with explorer, passing args as a list so explorer sees it correctly
            subprocess.Popen(["explorer", folder])
        except Exception as e:
            print(f"dir failed: {e}")
    def handle_detect_and_draw(self, arg):
        """Detect pillars and draw them."""
        p=self.get_parent()
        try:
            arr = np.asarray(p.opx.scan_Out)
            x=arr[:,4].astype(float)/1e6
            y=arr[:,5].astype(float)/1e6
            inten=arr[:,3].astype(float)
            img=ScanImageAnalysis(); img.image=np.column_stack((x,y,inten))
            img._build_grid(); clim=3000; img._grid=np.clip(img._grid,0,clim)
            contours=img.compute_pillar_contours(img._grid,clim,0.21)
            centres,_=img.compute_circle_fit(contours)
            layer="plot_draw_layer"
            if dpg.does_item_exist(layer): dpg.delete_item(layer)
            dpg.add_draw_layer(parent="plotImaga",tag=layer)
            p.saved_query_points=[]
            for i,(cx,cy) in enumerate(centres,1):
                p.saved_query_points.append((i,cx,cy,p.opx.positioner.AxesPositions[2]*1e-6))
                dpg.draw_circle(center=(cx,cy),radius=0.1,fill=(255,0,0,255),parent=layer,tag=f"p_dot_{i}")
                dpg.draw_text(pos=(cx,cy),text=str(i),color=(255,255,0,255),parent=layer,tag=f"p_txt_{i}")
            print(f"Detected {len(centres)} pillars.")
        except Exception as e:
            print(f"det failed: {e}")
    def handle_fmax(self, arg):
        """Find max signal and update saved point."""
        p=self.get_parent()
        idx = int(arg) if arg.isdigit() else None
        def worker():
            p.opx.btnStartCounterLive()
            time.sleep(1)
            p.opx.FindMaxSignal()
            if idx:
                pos = [v*1e-6 for v in p.opx.positioner.AxesPositions]
                pts=getattr(p,"saved_query_points",[])
                updated=False
                for j,pt in enumerate(pts):
                    if pt[0]==idx:
                        pts[j]=(idx,*pos); updated=True; break
                if not updated:
                    pts.append((idx,*pos))
                p.saved_query_points=pts
                print(f"fmax updated point #{idx}: {pos}")
        threading.Thread(target=worker,daemon=True).start()
    def handle_kfmax(self, arg):
        """
        Sweep the Keysight AWG offset to find the maximum signal,
        then optionally save that point under an index.
        Usage: kfmax [<point_index>]
        """
        p = self.get_parent()
        idx = int(arg) if arg.isdigit() else None

        def worker():
            # start live counter so GlobalFetchData will update
            p.opx.btnStartCounterLive()
            time.sleep(1)

            # call your AWG‐offset sweep routine
            # (make sure this method is defined on p.opx)
            p.opx.Find_max_signal_by_keysight_offset()

            # read back the AWG’s current (best) offset
            ch = p.keysight_gui.dev.channel
            best_off = p.keysight_gui.dev.get_current_voltage(ch)

            # if an index was provided, save (idx, x, y, z…, offset)
            if idx is not None:
                # convert axes positions (in whatever units) → microns
                pos = [v * 1e-6 for v in p.opx.positioner.AxesPositions]
                pts = getattr(p, "saved_query_points", [])
                for j, pt in enumerate(pts):
                    if pt[0] == idx:
                        pts[j] = (idx, *pos, best_off)
                        break
                else:
                    pts.append((idx, *pos, best_off))
                p.saved_query_points = pts

                print(f"kfmax updated point #{idx}: pos={pos}, offset={best_off}V")

        threading.Thread(target=worker, daemon=True).start()
    def handle_ntrack(self, arg):
        """
        Get or set tracking parameters.

        Usage:
          ntrack                      -> show N_tracking_search and tracking integration time (ms)
          ntrack 10                   -> set N_tracking_search = 10
          ntrack 10 ms                -> set tracking integration time to 10 ms
          ntrack 250us                -> set tracking integration time to 0.25 ms
          ntrack 0.5 s                -> set tracking integration time to 500 ms
          ntrack 1000ms               -> set tracking integration time to 1000 ms
          ntrack 5 10 ms              -> set N_tracking_search=5 and time=10 ms
          ntrack 10 ms 5              -> set time=10 ms and N_tracking_search=5

          Example:
              ntrack 10 10 ms
              focus 2000
        """
        import re, traceback
        p = self.get_parent()
        s = (arg or "").strip()

        def _show():
            try:
                n = getattr(p.opx, "N_tracking_search", None)
                t_ms = getattr(p.opx, "tTrackingSignaIntegrationTime", None)
                n_txt = f"{n}" if n is not None else "unknown"
                try:
                    t_txt = f"{float(t_ms):.3f} ms" if t_ms is not None else "unknown"
                except Exception:
                    t_txt = f"{t_ms} (units unknown)" if t_ms is not None else "unknown"
                print(f"N_tracking_search = {n_txt} | Tracking integration time = {t_txt}")
            except Exception:
                traceback.print_exc()
                print("ntrack: failed to read current values.")

        # No args: just display
        if not s or s.strip() == "?":
            _show()
            return

        tokens = s.lower().split()
        units_set = {"ms", "us", "µs", "s"}

        N_val = None
        ms_val = None

        i = 0
        while i < len(tokens):
            tok = tokens[i]

            # number+unit in one token (e.g., 10ms, 250us, 0.5s)
            m = re.fullmatch(r"([+-]?\d*\.?\d+)(us|µs|ms|s)", tok)
            if m:
                val = float(m.group(1))
                unit = m.group(2)
                if unit == "s":
                    ms_val = val * 1000.0
                elif unit in ("us", "µs"):
                    ms_val = val / 1000.0
                else:
                    ms_val = val
                i += 1
                continue

            # number followed by separate unit (e.g., 10 ms)
            if re.fullmatch(r"[+-]?\d*\.?\d+", tok) and i + 1 < len(tokens) and tokens[i + 1] in units_set:
                val = float(tok)
                unit = tokens[i + 1]
                if unit == "s":
                    ms_val = val * 1000.0
                elif unit in ("us", "µs"):
                    ms_val = val / 1000.0
                else:
                    ms_val = val
                i += 2
                continue

            # pure number without unit
            if re.fullmatch(r"[+-]?\d*\.?\d+", tok):
                # integers without unit -> N; decimals without unit -> time in ms
                if "." in tok or "e" in tok or "E" in tokens[i] if i < len(tokens) else False:
                    ms_val = float(tok)
                else:
                    # integer
                    if N_val is None:
                        N_val = int(tok)
                    else:
                        # if N already set, treat additional bare number as ms
                        ms_val = float(tok)
                i += 1
                continue

            # unknown token (ignore, allows 'plot' or others to coexist harmlessly)
            i += 1

        # Apply updates (both if provided)
        try:
            if N_val is not None:
                p.opx.UpdateN_tracking_search(user_data=int(N_val))
                print(f"N_tracking_search set to {int(N_val)}")
        except Exception:
            traceback.print_exc()
            print("ntrack: failed to set N_tracking_search.")

        try:
            if ms_val is not None:
                ms_int = int(round(ms_val))
                # API: Update_tTrackingSignaIntegrationTime(user_data=ms_int[, app_data=None])
                try:
                    p.opx.Update_tTrackingSignaIntegrationTime(user_data=ms_int, app_data=None)
                except TypeError:
                    p.opx.Update_tTrackingSignaIntegrationTime(user_data=ms_int)
                # mirror for display if OPX doesn't keep it
                try:
                    setattr(p.opx, "tTrackingSignaIntegrationTime", ms_int)
                except Exception:
                    pass
                print(f"Tracking integration time set to {ms_val:.3f} ms")
        except Exception:
            traceback.print_exc()
            print("ntrack: failed to set tracking integration time.")

        _show()
    def handle_copy_last_msg(self, arg):
        """Copy the last console message to the clipboard."""
        msgs = getattr(sys.stdout, "messages", [])
        if not msgs:
            print("No messages to copy.")
            return
        last = msgs[-1].rstrip("\n")
        try:
            pyperclip.copy(last)
            print(f"Copied to clipboard: {last}")
        except Exception as e:
            print(f"Copy failed: {e}")
    def handle_exit(self, arg):
        """Exit the application immediately."""
        print("Exiting application...")
        # stop the DPG render loop
        dpg.stop_dearpygui()
        # terminate Python process
        os._exit(0)
    def handle_enablepp(self, arg):
        """Enable the pharos pulse picker (PP)."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)
        self.handle_toggle_sc(reverse=False)
        time.sleep(3)
        try:
            gui.pharos.enablePp()
            print("Pharos pulse picker enabled.")
        except Exception as e:
            print(f"enablepp failed: {e}")
    def handle_pulsecount(self, arg):
        """Set the number of pulses per trigger: pulsecount <num>."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)
        try:
            count = int(arg)
        except Exception:
            print(f"Invalid pulse count: '{arg}'. Must be an integer.")
            return

        try:
            gui.pharos.setAdvancedTargetPulseCount(count)
            print(f"Pulse count set to {count}.")
        except Exception as e:
            print(f"pulsecount failed: {e}")
    def handle_focus(self, arg):
        """
        Run FindFocus (channel 2).
        If 'plot' is present, show the Signal vs Z graph.
        If a number is present (e.g., '150' or '-80'), move SmarAct ch2 by that many
        nanometers AFTER the focus completes.

        Conversion to steps:
          value_nm -> value_um = value_nm / 1000
          steps = value_um * dev.StepsIn1mm / 1e3
        """
        p = self.get_parent()

        tokens = (arg or "").strip().split()
        do_plot = any(t.lower() == "plot" for t in tokens)

        delta_nm = 0.0
        for t in tokens:
            try:
                delta_nm = float(t)
                break
            except Exception:
                pass

        def worker():
            try:
                p.opx.btnStartCounterLive()
                time.sleep(1)
                p.opx.FindFocus()

                if do_plot:
                    try:
                        self._focus_plot(p.opx.coordinate, p.opx.track_X)
                    except Exception as e:
                        print(f"focus plot failed: {e}")

                if delta_nm != 0:
                    dev = getattr(getattr(p, "smaractGUI", None), "dev", None)
                    if dev is None:
                        print("SmarAct device not available for post-focus move.")
                    else:
                        try:
                            value_um = delta_nm / 1000.0
                            steps_per_mm = getattr(dev, "StepsIn1mm", None)
                            if steps_per_mm is None:
                                print("SmarAct dev.StepsIn1mm not available.")
                                return
                            rel_steps = int(round(value_um * steps_per_mm / 1e3))
                            dev.MoveRelative(2, rel_steps)
                            print(f"Post-focus: moved SmarAct ch2 by {delta_nm} nm -> {rel_steps} steps.")
                        except Exception as e:
                            print(f"Post-focus move failed: {e}")


            except Exception as e:
                traceback.print_exc()
                print(f"focus failed: {e}")

            finally:
                # Signal that focus finished (for 'await focus')
                try:
                    if not hasattr(self, "_focus_done_evt"):
                        import threading
                        self._focus_done_evt = threading.Event()
                    self._focus_done_evt.set()
                    print("[focus] done.")
                except Exception:
                    pass


        threading.Thread(target=worker, daemon=True).start()
    def _focus_plot(self, coords, signals):
        """Create/update a DPG window with Signal vs Z, marking the max point."""
        # Remove old window if it exists
        if dpg.does_item_exist("focus_window"):
            dpg.delete_item("focus_window", children_only=False)

        with dpg.window(label="Focus Plot", tag="focus_window", width=600, height=400):
            plot = dpg.add_plot(label="Signal vs Z", height=350, width=580)

            # X and Y axes
            dpg.add_plot_axis(dpg.mvXAxis, label="Z (µm)", parent=plot)
            dpg.add_plot_axis(dpg.mvYAxis, label="Signal", parent=plot, tag="focus_plot_y")

            # Convert to µm
            z_um = [c * 1e-6 for c in coords]

            # Plot line
            dpg.add_line_series(z_um, signals, label="Signal", parent="focus_plot_y")

            # Highlight the max
            idx_max = int(np.argmax(signals))
            dpg.add_scatter_series(
                [z_um[idx_max]],
                [signals[idx_max]],
                label="Max",
                parent="focus_plot_y",
            )
    def handle_standby(self, arg):
        """Put the Pharos laser into standby mode."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)
        try:
            gui.pharos.goToStandby()
            print("Pharos: entered standby mode.")
        except Exception as e:
            print(f"standby failed: {e}")
    def handle_standby_query(self, arg):
        """Print yes if Pharos is currently in standby mode."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)
        try:
            # Call the API to get the current state name
            resp = gui.pharos.getBasicActualStateName2()  # :contentReference[oaicite:0]{index=0}
            # Extract the state string
            if isinstance(resp, dict):
                # The key is usually "ActualStateName2" or similar
                state = next(iter(resp.values()))
            else:
                state = str(resp)
            # Check for "standby"
            if "standby" in state.lower():
                print("yes pharos in standby mode")
            else:
                print(f"pharos state is {state}")
        except Exception as e:
            print(f"standby? failed: {e}")
    def handle_execute(self, arg):
        """Reload last-selected Pharos preset and turn the laser on."""
        p = self.get_parent()
        gui = getattr(p, "opx", p)
        try:
            # apply whatever preset index is currently selected
            gui.pharos.applySelectedPreset()
            print("Pharos: applied selected preset.")
            # then turn the laser on
            gui.pharos.turnOn()
            print("Pharos: laser turned ON.")
        except Exception as e:
            print(f"execute failed: {e}")
    def handle_enable_pharos_query(self, arg):
        """Print Pharos output status."""
        p = self.get_parent()
        try:
            # returns True if the laser output is enabled :contentReference[oaicite:0]{index=0}
            enabled = p.opx.pharos.getBasicIsOutputEnabled()
            # returns True if the output port shutter is open :contentReference[oaicite:1]{index=1}
            open_ = p.opx.pharos.getBasicIsOutputOpen()
            print(f"Pharos output enabled: {enabled}, output open: {open_}")
        except Exception as e:
            print(f"enable? failed: {e}")
    def handle_enable_pharos(self, arg=None):
        """Enable the Pharos laser output."""
        p = self.get_parent()
        try:
            enabled = p.opx.pharos.getBasicIsOutputEnabled()  # :contentReference[oaicite:0]{index=0}
            if enabled:
                print("Pharos output enabled.")
                return
            p.opx.pharos.enableOutput()
            print("Pharos output enabled.")
        except Exception as e:
            print(f"enable failed: {e}")
    def handle_disable_pharos(self, arg):
        """Disable the Pharos laser output."""
        p = self.get_parent()
        try:
            p.opx.pharos.closeOutput()
            print("Pharos output disabled.")
        except Exception as e:
            print(f"disable failed: {e}")
    def handle_spot(self, arg, skip_restore=False):
        """Verify counter is on, camera is live, first MFF is down, second is up."""
        p = self.get_parent()

        # 1) Capture original live states
        initial_cam_live = getattr(p.cam.cam, "constantGrabbing", False)
        initial_counter_live = getattr(p.opx, "counter_is_live", False)

        # 1) Counter live
        p.opx.btnStartCounterLive()

        # 2) Camera live
        getattr(p.cam, "constantGrabbing", False)
        p.cam.StartLive()
        previous_exp = p.cam.cam.camera.exposure_time_us
        p.cam.cam.SetExposureTime(0)

        # 3) MFF positions
        mffs = getattr(p, "mff_101_gui", [])
        if len(mffs) < 2:
            print("Error: less than two MFF devices found.")
            return
        # Record original positions
        orig_states = []
        for fl in mffs[:2]:
            try:
                orig_states.append(fl.dev.get_position())
            except:
                orig_states.append(None)
        # desired: first flipper DOWN (position=1), second flipper UP (position=2)
        for idx, desired_pos in ((0, 1), (1, 2)):
            fl = mffs[idx]
            tag = f"on_off_slider_{fl.unique_id}"
            try:
                current = fl.dev.get_position()
            except Exception as e:
                print(f"Could not read MFF #{idx} position: {e}")
                continue

            if current == desired_pos:
                state = "down" if desired_pos == 1 else "up"
                # print(f"MFF #{idx + 1} already {state}.")
            else:
                # flip via the same callback your UI uses
                # callback takes (tag, value), where value=1→down, 0→up
                val = desired_pos - 1
                fl.on_off_slider_callback(tag, val)
                state = "down" if desired_pos == 1 else "up"
                time.sleep(0.5)
                # print(f"MFF #{idx + 1} moved {state}.")

        # 4) Save spot image
        fn = p.cam.SaveProcessedImage()
        notes = getattr(p.opx, "expNotes", "")
        base, ext = os.path.splitext(fn)
        new = f"{base}_{notes}_Spot{ext}"
        os.replace(fn, new)
        print(f"Image saved as {new}")
        pyperclip.copy(new)
        if not skip_restore:
            self.handle_file(new)

        # 5) Schedule restore in 500ms
        if not skip_restore:
            def _restore():
                # — restore exposure (in ms)
                # print(f"Restoring exposure to {previous_exp}µs")
                p.cam.UpdateExposure(user_data=previous_exp * 1e-3)
                # restore camera live state if it was OFF
                if not initial_cam_live:
                    p.cam.StopLive()
                # restore counter live state if it was OFF
                if not initial_counter_live:
                    p.opx.btnStop()
                # — restore each flipper only if it's no longer in its original state
                for idx, orig in enumerate(orig_states):
                    if orig is None:
                        continue
                    fl = mffs[idx]
                    tag = f"on_off_slider_{fl.unique_id}"
                    try:
                        current = fl.dev.get_position()
                    except Exception as e:
                        print(f"Could not read MFF #{idx + 1}: {e}")
                        continue
                    if current != orig:
                        # callback expects 0 for down(1), 1 for up(2)
                        val = orig - 1
                        fl.on_off_slider_callback(tag, val)
            threading.Timer(0.5, _restore).start()
            print("Scheduled exposure & flipper restore in 500ms.")
    def handle_spot1(self, arg):
        """Same as spot, but do NOT restore after saving."""
        # call handle_spot with skip_restore=True
        self.handle_spot(arg, skip_restore=True)
    def handle_lens_toggle(self, arg):
        """
        Toggle the second MFF (MFF #2) between UP and DOWN.
        """
        try:
            p = self.get_parent()
            mffs = getattr(p, "mff_101_gui", [])
            if len(mffs) < 2:
                print("Error: less than two MFF devices found.")
                return

            fl = mffs[1]  # Second MFF
            tag = f"on_off_slider_{fl.unique_id}"
            current = fl.dev.get_position()
            if current not in (1, 2):
                print(f"Invalid position: {current}")
                return

            new_pos = 2 if current == 1 else 1  # Toggle
            val = new_pos - 1  # 0 for down(1), 1 for up(2)
            fl.on_off_slider_callback(tag, val)

            state = "up" if new_pos == 2 else "down"
            print(f"MFF #2 toggled {state}.")

        except Exception as e:
            print(f"Lens toggle failed: {e}")
    def handle_scanmv(self, arg):
        """Start a thread to monitor scan status and move files when done."""
        t = threading.Thread(target=self._watch_scan_and_move, args=(arg,), daemon=True)
        t.start()
        print("Watching scan progress...")
    def _watch_scan_and_move(self, arg):
        """
        Waits until scan is done (i.e., Stop button disappears),
        then moves files using handle_move_files().
        """
        try:
            import time
            while dpg.does_item_exist("btnOPX_Stop"):
                time.sleep(1)  # Check every second

            print("Scan ended. Running handle_move_files...")
            self.handle_move_files(arg)

        except Exception as e:
            print(f"[watch_scan_and_move] Error: {e}")
    def handle_restore(self, arg):
        """Restore SmarAct absolute positions from <initial_scan_Location> in OPX_params.xml."""
        try:
            import xml.etree.ElementTree as ET

            xml_path = "OPX_params.xml"  # adjust if needed
            if not os.path.isfile(xml_path):
                print(f"File not found: {xml_path}")
                return

            tree = ET.parse(xml_path)
            root = tree.getroot()
            loc = root.find("initial_scan_Location")
            if loc is None:
                print("initial_scan_Location not found in XML.")
                return

            items = loc.findall("item")
            if len(items) != 3:
                print(f"Expected 3 items in initial_scan_Location, found {len(items)}.")
                return

            values = [int(item.text)*1e-6 for item in items]
            print(f"Restoring SmarAct absolute positions to: {values}")

            for axis, val in enumerate(values):
                tag = f"mcs_ch{axis}_ABS"
                if dpg.does_item_exist(tag):
                    dpg.set_value(tag, float(val))
                else:
                    print(f"Tag not found: {tag}")
        except Exception as e:
            print(f"Failed to restore positions: {e}")
    def handle_keysight_offset(self, arg):
        """
        Set the Keysight AWG offset for one or both channels.

        Usage:
          # Single value → applies to the GUI-selected channel
          koff <voltage>            # absolute (V)
          koff <shift><u|um>        # shift by microns

          # Two values → CH1 and CH2
          koff <voltage1> <voltage2>
          koff <shift1>u <shift2>u
          koff <shift1>u,<shift2>u
          koff <voltage1>,<shift2>u   # mixed absolute & shift

        Calibration: 0.128 V → 15 µm
        """

        parent = self.get_parent()
        gui = getattr(parent, "keysight_gui", None)
        if not gui:
            print("No Keysight AWG GUI is active.")
            return

        # 1) parse up to two values (with optional 'u' or 'um' for microns)
        parts = re.findall(r'([+-]?\d*\.?\d+)(?:\s*(u|um))?', arg, re.IGNORECASE)
        if not parts:
            print("Invalid usage: koff <value>[u|um] [<value>[u|um]]")
            return
        if len(parts) > 2:
            print("Error: Too many values. Provide one or two.")
            return

        volts_per_um = gui.volts_per_um

        def apply_to_channel(channel, num_str, unit):
            val = float(num_str)
            curr = float(gui.dev.get_current_voltage(channel))
            # choose conversion factor: microns→volts_per_um, volts→1
            factor = volts_per_um if unit else 1.0
            delta_v = val * factor
            new_off = curr + delta_v

            if unit:
                print(f"CH{channel}: shift {val:.2f} µm -> d{delta_v:.4f} V (new {new_off:.4f} V)")
            else:
                print(f"CH{channel}: shift {val:.4f} V -> d{delta_v:.4f} V (new {new_off:.4f} V)")

            gui.dev.set_offset(new_off, channel=channel)

        try:
            if len(parts) == 1:
                # single value → use GUI's selected channel
                sel = dpg.get_value(f"ChannelSelect_{gui.unique_id}")
                try:
                    ch = int(sel)
                except ValueError:
                    ch = 1
                num_str, unit = parts[0]
                apply_to_channel(ch, num_str, unit)
            else:
                # two values → CH1 & CH2
                for idx, (num_str, unit) in enumerate(parts):
                    apply_to_channel(idx + 1, num_str, unit)

            # refresh GUI parameters
            gui.btn_get_current_parameters()

        except Exception as e:
            print(f"Failed to set offset(s): {e}")
    def handle_kabs(self, arg):
        """
        Set absolute AWG offsets based on either micron positions or direct voltages.

        Usage:
          kabs                     # shorthand for kabs 0,0 -> both channels to baselines
          kabs 1.67                # micron mode -> CH1
          kabs 1.67 2.45           # micron mode -> CH1 & CH2
          kabs 1.67u,2.45um
          kabs 1.2v                # voltage mode -> CH1 = 1.2 V
          kabs 1.2v 2.3v
          kabs 1.2,2.3 v
          kabs 0.5,0.8 u?          # QUERY ONLY: print voltages for 0.5um, 0.8um (no apply)
          kabs 1.2,2.3 v?          # QUERY ONLY: echo voltages (no apply)
          kabs ?                   # QUERY ONLY: print current CH1/CH2 voltages (no apply)
        """
        import re

        parent = self.get_parent()
        gui = getattr(parent, "keysight_gui", None)
        if not gui:
            print("No Keysight AWG GUI is active.")
            return

        arg = (arg or "").strip()

        # --- Detect trailing query flag like 'u?' / 'um?' / 'v?' / '?' ---
        m_q = re.search(r'(?:\s*(u|um|v))?\s*\?$', arg, re.IGNORECASE)
        query_mode = bool(m_q)
        query_unit = (m_q.group(1) or "").lower() if query_mode else None
        if query_mode:
            arg = arg[:m_q.start()].strip()  # strip the '?'-suffix before parsing numbers

        # 1) Extract all (number, optional-unit) pairs (commas or spaces as separators)
        parts = re.findall(r'([+-]?\d*\.?\d+)(?:\s*(u|um|v))?', arg, re.IGNORECASE)

        # --- Special case: plain "kabs ?" (no numbers) -> read & print current voltages ---
        if query_mode and len(parts) == 0:
            try:
                v1 = float(gui.dev.get_current_voltage(1))
                v2 = float(gui.dev.get_current_voltage(2))
                print(f"kabs? -> CH1: {v1:.4f} V; CH2: {v2:.4f} V")
            except Exception as e:
                print(f"kabs? failed to read voltages: {e}")
            return

        # —— default no-arg to zero for both channels ——
        if not parts:
            parts = [('0', None), ('0', None)]

        # 2) Separate floats and units
        vals, unts = [], []
        for num, unit in parts:
            vals.append(float(num))
            unts.append((unit or "").lower() if unit else None)

        # 3) Determine mode
        if query_unit in ("v",):
            voltage_mode = True
        elif query_unit in ("u", "um"):
            voltage_mode = False
        else:
            # If any 'v' and no 'u'/'um' found in tokens -> voltage mode
            voltage_mode = any(u == 'v' for u in unts) and not any(u in ('u', 'um') for u in unts)

        # 4) Baselines and calibration
        base1 = getattr(gui, "base1", 0.0)
        base2 = getattr(gui, "base2", 0.0)
        volts_per_um = gui.volts_per_um

        # 5) Compute planned offsets (absolute voltages to send)
        offsets = []
        for idx, (val, unit) in enumerate(zip(vals, unts)):
            if voltage_mode:
                offsets.append(val)  # absolute voltage (already volts)
            else:
                baseline = base1 if idx == 0 else base2
                offsets.append(baseline + val * volts_per_um)

        # If only one value was given, leave CH2 untouched
        if len(offsets) == 1:
            offsets.append(None)

        # --- QUERY MODE: just print the planned voltages and return ---
        if query_mode:
            ch1 = "N/A" if offsets[0] is None else f"{offsets[0]:.4f} V"
            ch2 = "N/A" if offsets[1] is None else f"{offsets[1]:.4f} V"
            unit_lbl = "volts" if voltage_mode else "microns"
            print(
                f"kabs? ({unit_lbl}) -> CH1: {ch1}; CH2: {ch2}  [base1={base1:.4f}, base2={base2:.4f}, V/um={volts_per_um:.6f}]")
            return

        # 6) Apply offsets
        try:
            if offsets[0] is not None:
                gui.dev.set_offset(offsets[0], channel=1)
            if offsets[1] is not None:
                gui.dev.set_offset(offsets[1], channel=2)

            gui.btn_get_current_parameters()

            # 7) Read back actual voltages
            v1 = float(gui.dev.get_current_voltage(1))
            v2 = float(gui.dev.get_current_voltage(2))

            # 8) Compute XY (um) relative to baselines using the 2-basis ([1,kx], [1,ky])
            kx_ratio = getattr(gui, "kx_ratio", 3.3)
            ky_ratio = getattr(gui, "ky_ratio", -0.3)

            dv1 = v1 - base1
            dv2 = v2 - base2
            denom = (kx_ratio - ky_ratio)

            if abs(denom) < 1e-12:
                xy_msg = " | Pos: X=?, Y=? (ill-conditioned ratios)"
            else:
                # Solve: [dv1, dv2]^T = alpha*[1, kx]^T + beta*[1, ky]^T
                alpha_x_volts = (dv2 - dv1 * ky_ratio) / denom
                beta_y_volts = (dv2 - dv1 * kx_ratio) / (ky_ratio - kx_ratio)
                x_um = alpha_x_volts / volts_per_um
                y_um = beta_y_volts / volts_per_um
                xy_msg = f" | Pos: X={x_um:.3f} um, Y={y_um:.3f} um"

            msg = (
                    f"kabs: CH1 -> {v1:.4f} V; CH2 -> {v2:.4f} V" + xy_msg +
                    f" [base1={base1:.4f}, base2={base2:.4f}, kx={kx_ratio:.3f}, ky={ky_ratio:.3f}]"
            )
            print(msg)

        except Exception as e:
            print(f"Failed to set kabs offset(s): {e}")
    def handle_kx(self, arg):
        """
        Shift both AWG channels for X-axis motion.
        Usage:
          kx <value>[u|um|v] [<kx_ratio> [<ky_ratio>]]
        – no unit treats value as µm (× volts_per_um)
        – 'u'/'um'      treats value as µm (× volts_per_um)
        – 'v'           treats value as volts directly
        – optional <kx_ratio> overrides CH2:CH1 ratio for X motion
        – optional <ky_ratio> overrides the Y basis ratio used for XY position solve
        """

        parent = self.get_parent()
        gui = getattr(parent, "keysight_gui", None)
        if not gui:
            print("No Keysight AWG GUI is active.")
            return

        # split on whitespace or comma, allow up to 3 parts: value, kx_ratio, ky_ratio
        parts = re.split(r'[,\s]+', arg.strip())
        if not parts or len(parts) > 3:
            print("Invalid usage: kx <value>[u|um|v] [<kx_ratio> [<ky_ratio>]]")
            return

        # parse the motion value (with optional unit)
        m = re.match(r'^([+-]?\d*\.?\d+)(u|um|v)?$', parts[0], re.IGNORECASE)
        if not m:
            print("Invalid value for kx:", parts[0])
            return
        val = float(m.group(1))
        # DEFAULT TO µm WHEN NO UNIT IS PROVIDED
        unit = (m.group(2) or "um").lower()

        # at the top of each handler, after fetching gui:
        vpu_x = getattr(gui, "volts_per_um_x", gui.volts_per_um)  # V per µm along X
        vpu_y = getattr(gui, "volts_per_um_y", gui.volts_per_um)  # V per µm along Y

        if unit in ("u", "um"):
            delta_v = val * vpu_x
            label = "µm"
        else:
            delta_v = val
            label = "V"

        # parse optional ratio overrides
        try:
            kx_ratio = float(parts[1]) if len(parts) >= 2 else gui.kx_ratio
        except ValueError:
            print("Invalid kx_ratio:", parts[1])
            return

        try:
            ky_ratio = float(parts[2]) if len(parts) == 3 else getattr(gui, "ky_ratio", -0.3)
        except ValueError:
            print("Invalid ky_ratio:", parts[2])
            return
        try:
            c1 = float(gui.dev.get_current_voltage(1))
            c2 = float(gui.dev.get_current_voltage(2))
            n1 = c1 + delta_v
            n2 = c2 + delta_v * kx_ratio

            gui.dev.set_offset(n1, channel=1)
            gui.dev.set_offset(n2, channel=2)
            gui.btn_get_current_parameters()

            # --- Compute current XY position (µm) from (n1, n2) using the two-basis (kx, ky) ---
            base1 = getattr(gui, "base1", 0.0)
            base2 = getattr(gui, "base2", 0.0)

            dv1 = n1 - base1
            dv2 = n2 - base2
            denom = (kx_ratio - ky_ratio)

            if abs(denom) < 1e-12:
                xy_msg = " (XY: undefined, kx_ratio == ky_ratio)"
            else:
                # Solve v = α*[1, kx] + β*[1, ky] for α (X-volts) and β (Y-volts)
                # n1 = α + β
                # n2 = α*kx + β*ky
                alpha_x_volts = (dv2 - dv1 * ky_ratio) / denom
                beta_y_volts = (dv2 - dv1 * kx_ratio) / (ky_ratio - kx_ratio)

                # Convert volts to position (keep same scale convention as the rest of your codebase)
                x_um = alpha_x_volts / vpu_x
                y_um = beta_y_volts / vpu_y
                xy_msg = f" | Pos: X={x_um:.3f} µm, Y={y_um:.3f} µm"

            print(
                f"kx: CH1 +{val:.2f}{label} -> d{delta_v:.4f} V (now {n1:.4f} V); "
                f"CH2 -> Δ{delta_v * kx_ratio:.4f} V (now {n2:.4f} V) "
                f"[kx_ratio={kx_ratio:.3f}, ky_ratio={ky_ratio:.3f}, base1={base1:.4f}, base2={base2:.4f}]\n{xy_msg}"
            )

            self.handle_mark("k")
        except Exception as e:
            print(f"Failed to perform kx: {e}")
    def handle_ky(self, arg):
        """
        Shift both AWG channels for Y-axis motion.
        Usage:
          ky <value>[u|um|v] [<ratio>]
        – no unit or 'um' treats value as um directly
        – 'u'/'um'      treats value as µm (× volts_per_um)
        – optional <ratio> overrides default CH2:CH1 ratio
        """
        parent = self.get_parent()
        gui = getattr(parent, "keysight_gui", None)
        if not gui:
            print("No Keysight AWG GUI is active.")
            return

        parts = re.split(r'[,\s]+', arg.strip())
        if not parts or len(parts) > 2:
            print("Invalid usage: ky <value>[u|um|v] [<ratio>]")
            return

        m = re.match(r'^([+-]?\d*\.?\d+)(u|um|v)?$', parts[0], re.IGNORECASE)
        if not m:
            print("Invalid value for ky:", parts[0])
            return
        val = float(m.group(1))
        unit = (m.group(2) or "um").lower()

        # at the top of each handler, after fetching gui:
        vpu_x = getattr(gui, "volts_per_um_x", gui.volts_per_um)  # V per µm along X
        vpu_y = getattr(gui, "volts_per_um_y", gui.volts_per_um)  # V per µm along Y

        if unit in ("u", "um"):
            delta_v = val * vpu_y
            label = "µm"
        else:
            delta_v = val
            label = "V"

        try:
            ky_ratio = float(parts[1]) if len(parts) == 2 else gui.ky_ratio
        except ValueError:
            print("Invalid ratio:", parts[1])
            return

        try:
            c1 = float(gui.dev.get_current_voltage(1))
            c2 = float(gui.dev.get_current_voltage(2))
            n1 = c1 + delta_v
            n2 = c2 + delta_v * ky_ratio

            gui.dev.set_offset(n1, channel=1)
            gui.dev.set_offset(n2, channel=2)
            gui.btn_get_current_parameters()

            # ---- XY print relative to baselines ----
            base1 = getattr(gui, "base1", 0.0)
            base2 = getattr(gui, "base2", 0.0)
            kx_ratio = getattr(gui, "kx_ratio", 3.3)

            dv1 = n1 - gui.base1
            dv2 = n2 - gui.base2
            denom = (kx_ratio - ky_ratio)
            if abs(denom) < 1e-12:
                xy_msg = " | Pos: X=?, Y=? (ill-conditioned ratios)"
            else:
                # [dv1, dv2]^T = α*[1, kx]^T + β*[1, ky]^T
                alpha_x_volts = (dv2 - dv1 * ky_ratio) / denom
                beta_y_volts = (dv2 - dv1 * kx_ratio) / (ky_ratio - kx_ratio)
                x_um = alpha_x_volts / vpu_x
                y_um = beta_y_volts / vpu_y
                xy_msg = f" | Pos: X={x_um:.3f} µm, Y={y_um:.3f} µm"
            print(
                f"ky: CH1 +{val:.2f}{label} -> d{delta_v:.4f} V (now {n1:.4f} V); "
                f"CH2 -> Δ{delta_v * ky_ratio:.4f} V (now {n2:.4f} V) "
                f"[kx_ratio={kx_ratio:.3f}, ky_ratio={ky_ratio:.3f}, base1={base1:.4f}, base2={base2:.4f}]\n{xy_msg}"
            )
            self.handle_mark("k")

        except Exception as e:
            print(f"Failed to perform ky: {e}")
    def handle_lf(self, arg):
        """
        LightField / ProEM utilities.

        Usage:
          lf roi        -> refresh ROI from LightField (stores in self.proem_query)
          lf roi print  -> also print approximate µm bounds (if calibrated)
          lf inf        -> trigger the LightField 'Run INF' action
        """
        p = self.get_parent()
        tokens = (arg or "").strip().lower().split()
        # ✅ NEW BEHAVIOR: no arguments → open LightField folder
        if not tokens:
            folder = r"C:\Users\Femto\Work Folders\Documents\LightField"
            try:
                subprocess.Popen(f'explorer "{folder}"')
                print(f"lf: opened LightField folder → {folder}")
            except Exception as e:
                print(f"lf: failed to open folder: {e}")
            return

        lf_gui = getattr(p, "hrs_500_gui", None)
        if lf_gui is None:
            print("lf inf: hrs_500_gui not available.")
            return

        sub = tokens[0]

        if sub == "roi":
            ok = lf_gui.refresh_proem_query_from_lightfield()
            if not ok:
                return
            print(f"lf roi: ProEM ROI (pixels) = {lf_gui.proem_query}")

            if len(tokens) > 1 and tokens[1] == "print":
                sx = lf_gui.proem_sx_um_per_px
                sy = lf_gui.proem_sy_um_per_px
                if lf_gui.proem_query and (sx is not None) and (sy is not None):
                    x0, y0 = [pos * 1e-6 for pos in p.opx.positioner.AxesPositions[:2]]
                    lf_gui.proem_x0_um = x0
                    lf_gui.proem_y0_um = y0
                    px0, py0 = lf_gui.proem_px0, lf_gui.proem_py0
                    flip_x, flip_y = lf_gui.proem_flip_x, lf_gui.proem_flip_y

                    x_min_px, y_min_px, x_max_px, y_max_px = map(float, lf_gui.proem_query)

                    def px_to_um(px, py):
                        x_um = x0 + sx * (px - px0)
                        y_um = y0 + sy * (py - py0)
                        if flip_x: x_um = -x_um
                        if flip_y: y_um = -y_um
                        return x_um, y_um

                    x1_um, y1_um = px_to_um(x_min_px, y_min_px)
                    x2_um, y2_um = px_to_um(x_max_px, y_max_px)
                    xmin_um, xmax_um = (x1_um, x2_um) if x1_um <= x2_um else (x2_um, x1_um)
                    ymin_um, ymax_um = (y1_um, y2_um) if y1_um <= y2_um else (y2_um, y1_um)
                    print(
                        f"lf roi: approx µm bounds -> x:[{xmin_um:.2f}, {xmax_um:.2f}]  y:[{ymin_um:.2f}, {ymax_um:.2f}]")
                else:
                    print("lf roi print: calibration (sx/sy) not set; skipping µm bounds.")
        elif sub == "inf":
            try:

                if hasattr(lf_gui, "run_inf") and callable(lf_gui.run_inf):
                    lf_gui.run_inf()
                    print("lf inf: run_inf() on hrs_500_gui invoked.")
                    return

                if hasattr(lf_gui, "dev"):
                    dev = lf_gui.dev
                    for meth in ("run_inf", "RunINF", "start_inf", "StartINF", "acquire_inf", "AcquireINF"):
                        if hasattr(dev, meth) and callable(getattr(dev, meth)):
                            getattr(dev, meth)()
                            print(f"lf inf: {meth}() on hrs_500_gui.dev invoked.")
                            return

                print("lf inf: no suitable method found (define run_inf/acquire_inf on GUI/dev).")
            except Exception as e:
                print(f"lf inf failed: {e}")
        elif sub == "anchor":
            # Usage: lf anchor <px> <py>
            if len(tokens) < 3:
                print("lf anchor: usage → lf anchor <px> <py>")
                return

            try:
                px = int(tokens[1])
                py = int(tokens[2])
            except Exception:
                print("lf anchor: px/py must be integers.")
                return

            # Current absolute stage position (µm)
            try:
                x_um, y_um = [pos * 1e-6 for pos in p.opx.positioner.AxesPositions[:2]]
            except Exception as e:
                print(f"lf anchor: could not read stage position: {e}")
                return

            # Save anchor on the dispatcher (same place you store sx/sy etc.)
            setattr(lf_gui, "proem_px0", px)
            setattr(lf_gui, "proem_py0", py)
            setattr(lf_gui, "proem_x0_um", x_um)
            setattr(lf_gui, "proem_y0_um", y_um)

            # Keep or initialize flips if not set yet
            if not hasattr(lf_gui, "proem_flip_x"): setattr(lf_gui, "proem_flip_x", False)
            if not hasattr(lf_gui, "proem_flip_y"): setattr(lf_gui, "proem_flip_y", False)

            print(f"lf anchor: pixel ({px},{py}) <-> stage ({x_um:.2f} µm, {y_um:.2f} µm)")
            # Optional quick check if calibration exists:
            sx = getattr(lf_gui, "proem_sx_um_per_px", None)
            sy = getattr(lf_gui, "proem_sy_um_per_px", None)
            if sx is not None and sy is not None:
                print(f"lf anchor: using scale sx={sx:.4f} µm/px, sy={sy:.4f} µm/px")
            else:
                print("lf anchor: note—sx/sy (µm/px) not set yet.")
        elif sub in ("sx", "sy"):
            # Usage: lf sx <num>, lf sy <num>
            if len(tokens) < 2:
                print(f"lf {sub}: usage → lf {sub} <µm_per_px>")
                return
            try:
                val = float(tokens[1])
            except Exception:
                print(f"lf {sub}: value must be a number (µm/px).")
                return

            if sub == "sx":
                setattr(lf_gui, "proem_sx_um_per_px", val)
                print(f"lf sx: set sx = {val:.4f} µm/px")
            else:
                setattr(lf_gui, "proem_sy_um_per_px", val)
                print(f"lf sy: set sy = {val:.4f} µm/px")
        else:
            print(f"lf: unknown subcommand '{sub}'. Try: 'lf roi' or 'lf inf'.")
    def handle_clear_console(self, arg=None):
        dpg.set_value("console_log", "")  # Replace with your console tag
        print("Console cleared.")
    def mark_proem_pixel(self, px: int | None = None, py: int | None = None):
        """
        Mark a ProEM pixel in the plot.
        If px/py not provided, uses the stored values from the HRS LightField GUI.
        """

        p = self.get_parent()
        lf_gui = getattr(p, "hrs_500_gui", None)

        self.handle_lf(arg="anchor 665 476")
        # Calibration & anchor
        sx = getattr(lf_gui, "proem_sx_um_per_px", None)
        sy = getattr(lf_gui, "proem_sy_um_per_px", None)
        px0 = getattr(lf_gui, "proem_px0", None)
        py0 = getattr(lf_gui, "proem_py0", None)
        x0 = getattr(lf_gui, "proem_x0_um", None)
        y0 = getattr(lf_gui, "proem_y0_um", None)
        flip_x = bool(getattr(lf_gui, "proem_flip_x", False))
        flip_y = bool(getattr(lf_gui, "proem_flip_y", False))

        # --- Pixel source ---
        if px is None or py is None:
            px = getattr(lf_gui, "proem_last_px", None)
            py = getattr(lf_gui, "proem_last_py", None)
            if px is None or py is None:
                print("mark_proem_pixel: no px/py given and no stored pixel available.")
                return

        # --- Check calibration ---
        if None in (sx, sy, px0, py0, x0, y0):
            print("mark_proem_pixel: calibration/anchor not set.")
            return

        # --- Convert pixel → µm ---
        x_um = x0 + sx * (px - px0)
        y_um = y0 + sy * (py - py0)
        if flip_x:
            x_um = -x_um
        if flip_y:
            y_um = -y_um

        # --- Draw marker ---
        try:
            tag = "temp_cross_marker"
            for s in ("_h_left", "_h_right", "_v_top", "_v_bottom", "_circle"):
                if dpg.does_item_exist(tag + s):
                    dpg.delete_item(tag + s)
            if not dpg.does_item_exist("plot_draw_layer"):
                dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

            gap, length = 0.5, 3
            line_color = (255, 255, 255, 255)  # white
            circle_color = (0, 0, 0, 255)  # black

            dpg.draw_line((x_um - length, y_um), (x_um - gap, y_um),
                          color=line_color, thickness=0.3,
                          parent="plot_draw_layer", tag=tag + "_h_left")
            dpg.draw_line((x_um + gap, y_um), (x_um + length, y_um),
                          color=line_color, thickness=0.3,
                          parent="plot_draw_layer", tag=tag + "_h_right")
            dpg.draw_line((x_um, y_um - length), (x_um, y_um - gap),
                          color=line_color, thickness=0.3,
                          parent="plot_draw_layer", tag=tag + "_v_top")
            dpg.draw_line((x_um, y_um + gap), (x_um, y_um + length),
                          color=line_color, thickness=0.3,
                          parent="plot_draw_layer", tag=tag + "_v_bottom")
            dpg.draw_circle(center=(x_um, y_um), radius=length,
                            color=circle_color, thickness=2,
                            parent="plot_draw_layer", tag=tag + "_circle")

            print(f"Marked ProEM px=({px},{py}) → ({x_um:.2f}, {y_um:.2f}) µm")

            # Store last used px/py back
            setattr(lf_gui, "proem_last_px", px)
            setattr(lf_gui, "proem_last_py", py)


        except Exception as e:
            print(f"mark_proem_pixel error: {e}")
    def handle_revive_app(self, arg=None):
        """
        Soft-revive the GUI if a long callback/scan left things unresponsive.

        What it does:
          • Signals any running scan to stop
          • Attempts to release stuck resources & threads
          • Rebuilds draw layers/plot textures
          • Re-enables common disabled controls
          • Pumps DPG frames a few times
          • Restarts camera live view (if it was running before)
        """
        import gc
        try:
            print("[revive] attempting to revive UI...")

            # ── 1) Signal long loops to stop ──
            try:
                self.stopScan = True
            except Exception:
                pass
            try:
                if hasattr(self, "btnStop") and callable(self.btnStop):
                    self.btnStop()
            except Exception as e:
                print(f"[revive] btnStop failed: {e}")

            # ── 2) Try to gracefully wind down scanner/acq threads ──
            for th_name in ("ScanTh", "AWG_switch_thread", "survey_thread"):
                th = getattr(self, th_name, None)
                if th and getattr(th, "is_alive", lambda: False)():
                    try:
                        # Non-blocking join attempt
                        th.join(timeout=0.05)
                    except Exception as e:
                        print(f"[revive] join {th_name} failed: {e}")

            # Replace any stuck lock with a fresh one
            try:
                if hasattr(self, "lock"):
                    self.lock = threading.Lock()
            except Exception:
                pass

            # ── 3) Reset result handles that might be stuck ──
            for hname in ("counts_handle", "meas_idx_handle", "ref_counts_handle", "job"):
                try:
                    setattr(self, hname, None)
                except Exception:
                    pass

            # ── 4) Rebuild DPG draw layer / textures if they got invalid ──
            try:
                if dpg.does_item_exist("plot_draw_layer"):
                    dpg.delete_item("plot_draw_layer")
                if dpg.does_item_exist("plotImaga"):
                    dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")
            except Exception as e:
                print(f"[revive] draw layer rebuild failed: {e}")

            try:
                # Texture refresh (if you use 'texture_tag' for the live image/heatmap)
                if dpg.does_item_exist("texture_tag"):
                    w = h = 256  # safe small buffer
                    import numpy as np
                    blank = (np.zeros((h, w, 4), dtype=np.float32)).ravel()
                    dpg.set_value("texture_tag", blank)
            except Exception as e:
                print(f"[revive] texture refresh failed: {e}")

            # ── 5) Re-enable common controls that might be disabled ──
            for tag in ("btnOPX_StartScan", "btnOPX_Stop", "OPX_button", "HRS_500_button", "keysight_button"):
                if dpg.does_item_exist(tag):
                    try:
                        dpg.enable_item(tag)
                    except Exception:
                        pass

            # ── 6) Pump a few frames to flush the UI ──
            try:
                for _ in range(5):
                    dpg.split_frame()
            except Exception:
                pass

            # ── 7) Nudge instrument GUIs to refresh their state (best-effort) ──
            p = self.get_parent()
            try:
                if hasattr(p, "keysight_gui") and hasattr(p.keysight_gui, "btn_get_current_parameters"):
                    p.keysight_gui.btn_get_current_parameters()
            except Exception:
                pass

            # Restart camera live view if that’s your normal idle state
            try:
                cam = self.HW.camera
                if hasattr(cam, "constantGrabbing") and not cam.constantGrabbing:
                    # your own toggle that starts grabbing
                    if hasattr(self, "handle_start_camera"):
                        self.handle_start_camera("")
            except Exception:
                pass

            # ── 8) GC to release any lingering large arrays ──
            try:
                gc.collect()
            except Exception:
                pass

            print("[revive] done. If UI still looks frozen, try 'reload opx' or 'reload hrs'.")
        except Exception as e:
            print(f"[revive] unexpected error: {e}")
    def handle_reset_smaract(self, arg: str):
        """
        Usage:
          reset smaract [small_um] [large_um] [reps]
          e.g., 'reset smaract 3 30 2'
        """
        p = self.get_parent()
        try:
            parts = (arg or "").split()
            small = float(parts[0]) if len(parts) > 0 else 2.0
            large = float(parts[1]) if len(parts) > 1 else 20.0
            reps = int(parts[2]) if len(parts) > 2 else 1

            # capture current absolute position in microns
            start_um = [v * 1e-6 for v in p.opx.positioner.AxesPositions]  # [X,Y,Z] µm

            def go(ax: int, val_um: float):
                dpg.set_value(f"mcs_ch{ax}_ABS", float(val_um))
                p.smaractGUI.move_absolute(None, None, ax)

            for _ in range(reps):
                # Pre-jog Z (large up/down) to shake encoders
                for dz in (large, -large):
                    go(2, start_um[2] + dz)
                go(2, start_um[2])

                # XY figure-8 around center, with tiny Z nibbles at each vertex
                cx, cy = start_um[0], start_um[1]
                path = [
                    (cx + large, cy + small),
                    (cx, cy - large),
                    (cx - large, cy + small),
                    (cx, cy + large),
                    (cx + small, cy),
                    (cx - small, cy),
                    (cx, cy - small),
                    (cx, cy),
                ]
                for x_um, y_um in path:
                    go(0, x_um)
                    go(1, y_um)
                    # small Z shake
                    go(2, start_um[2] + small)
                    go(2, start_um[2] - small)
                go(2, start_um[2])

            # Return home exactly
            for ax, val_um in enumerate(start_um):
                go(ax, val_um)

            print("Reset SmarAct done. Returned to: "
                  f"X={start_um[0]:.2f} µm, Y={start_um[1]:.2f} µm, Z={start_um[2]:.2f} µm")
        except Exception as e:
            print(f"reset smaract failed: {e}")
    def handle_show(self, arg):
        """
        show commands:
          show config
          show cmd | dispatcher
          show opx | disp | awg | cld | cob | femto | hrs | kdc | smaract | zelux
          show wrap <cld|zelux|cob|smaract|hrs>
          show map clib
          show app
          show wave
          show macro
          show map
          show coup
          show state
          show <file>
        """
        import json, os
        sub = (arg or "").strip()

        if not sub:
            print(
                "Usage: show config | show cmd | show <opx|disp|awg|cld|cob|femto|hrs|kdc|smaract|zelux|wave|app> | "
                "show wrap <cld|zelux|cob|smaract|hrs|wave> | show map clib | show macro | show coup"
            )
            return

        toks = sub.split()
        key = toks[0].lower()
        base_dir = _dispatcher_base_dir(self)

        # ----- show coup (open coup_state.json used by coup save/load) -----
        if key in ("coup", "state"):
            try:
                # Same directory used by coup macros / state
                try:
                    coup_dir = DEFAULT_COUP_DIR
                except NameError:
                    coup_dir = r"c:\WC\HotSystem\Utils\macro"

                state_path = os.path.join(coup_dir, "coup_state.json")
                if not os.path.exists(state_path):
                    print(f"[show coup] State file not found: {state_path}")
                    return

                _open_path(os.path.abspath(state_path))
            except Exception as e:
                print(f"[show coup] Failed to open coup state file: {e}")
            return

        # ----- show macro (list macro .txt files and open selected) -----
        # show macro 3 -> opens item #3
        if key == "macro":
            try:
                # Resolve default macro dir (same place your coup loader uses)
                try:
                    macro_dir = DEFAULT_COUP_DIR
                except NameError:
                    macro_dir = r"c:\WC\HotSystem\Utils\macro"

                if not os.path.isdir(macro_dir):
                    print(f"[show macro] Macro directory not found: {macro_dir}")
                    return

                # Collect only .txt files
                files = [f for f in os.listdir(macro_dir)
                         if f.lower().endswith(".txt") and os.path.isfile(os.path.join(macro_dir, f))]
                files.sort(key=lambda s: s.lower())

                if not files:
                    print(f"[show macro] No .txt macros found in {macro_dir}")
                    return

                # Print list with indices
                print(f"--- Macros in {macro_dir} ---")
                for i, name in enumerate(files, 1):
                    print(f"{i:3d}. {name}")

                # If user typed an index right after 'macro', use it; else prompt
                idx = None
                if len(toks) >= 2 and toks[1].isdigit():
                    idx = int(toks[1])
                else:
                    ans = input("Choose macro index to open: ").strip()
                    if not ans.isdigit():
                        print("[show macro] Please enter a numeric index.")
                        return
                    idx = int(ans)

                if not (1 <= idx <= len(files)):
                    print(f"[show macro] Index out of range (1..{len(files)}).")
                    return

                chosen = os.path.join(macro_dir, files[idx - 1])
                try:
                    _open_path(os.path.abspath(chosen))
                except Exception as e:
                    print(f"[show macro] Failed to open '{chosen}': {e}")
                return
            except Exception as e:
                print(f"[show macro] Unexpected error: {e}")
            return

        if key in ("wave", "wavemeter"):
            try:
                _open_path(os.path.join(base_dir, r"HW_GUI\GUI_wavemeter.py"))
            except Exception as e:
                print(f"[show wave] Failed to open wavemeter GUI: {e}")
            return

        # ----- show config -----
        if key == "config":
            _open_path(CONFIG_PATH)
            return

        # ----- show cmd / dispatcher (open CommandDispatcher.py) -----
        if key in ("cmd", "command", "dispatcher"):
            try:
                mod = sys.modules.get(self.__class__.__module__) or sys.modules.get(__name__)
                dispatcher_path = os.path.abspath(getattr(mod, "__file__", "CommandDispatcher.py"))
                if not os.path.isabs(dispatcher_path):
                    dispatcher_path = os.path.abspath(dispatcher_path)
                _open_path(dispatcher_path)
            except Exception as e:
                print(f"[show] Could not determine CommandDispatcher.py path: {e}")
            return

        # ----- show wrap <name> -----
        if key == "wrap":
            if len(toks) < 2:
                print("Usage: show wrap <cld|zelux|cob|smaract|wave>")
                return
            which = toks[1].lower()
            if which not in WRAP_MAP:
                print(f"[show] Unknown wrap '{which}'. Options: {', '.join(WRAP_MAP.keys())}")
                return
            mod_name, fallback_rel = WRAP_MAP[which]
            _open_module_or_fallback(mod_name, fallback_rel, base_dir)
            return

        # ----- show map clib (or calib) -----
        # ----- show map -----            # NEW (header comment tweak)
        if key == "map":
            # No args -> open the map image in the default app                 # NEW
            if len(toks) == 1 or (len(toks) >= 2 and toks[1].lower() in ("img", "image", "jpg")):  # NEW
                try:  # NEW
                    _open_path(r"C:\WC\HotSystem\map.jpg")  # NEW
                except Exception as e:  # NEW
                    print(f"[show map] Failed to open map image: {e}")  # NEW
                return  # NEW

            submap = toks[1].lower()  # NEW
            # Support calibration JSON (accept: calibration | calib | clib)    # NEW
            if submap in ("calibration", "calib", "clib"):  # NEW
                _open_path(os.path.join(base_dir, r"Utils\map_calibration.json"))  # NEW
                return  # NEW

            if len(toks) >= 2 and toks[1].lower() in ("calibration", "calib"):
                _open_path(os.path.join(base_dir, r"Utils\map_calibration.json"))
                return

            print("Usage: show map [img|calib]")  # NEW
            return  # NEW

        # ----- show hist / history (print + open files, optional suffix) -----
        if key in ("hist", "history"):
            suffix = toks[1] if len(toks) >= 2 else ""
            hist_fn  = f"history_{suffix}.txt" if suffix else "history.txt"
            macro_fn = f"macros_{suffix}.json" if suffix else "macros.json"

            # Print history
            try:
                with open(hist_fn, encoding="utf-8") as f:
                    lines = [l.rstrip("\n") for l in f]
                print(f"--- History ({len(lines)} lines) [{hist_fn}] ---")
                for i, line in enumerate(lines, 1):
                    print(f"{i:4d}  {line}")
            except FileNotFoundError:
                print(f"--- History ---\nNo {hist_fn} found.")
            except Exception as e:
                print(f"[show history] Failed to read {hist_fn}: {e}")

            # Print macros
            try:
                with open(macro_fn, encoding="utf-8") as mf:
                    macros = json.load(mf)
            except FileNotFoundError:
                macros = {}
            except Exception as e:
                print(f"[show history] Failed to read {macro_fn}: {e}")
                macros = {}

            print(f"--- Macros ({len(macros)} entries) [{macro_fn}] ---")
            if macros:
                for k in sorted(macros.keys(), key=lambda s: (s[0], len(s), s)):
                    print(f">{k}  ->  {macros[k]}")
            else:
                print("No macros defined.")

            # Open the files like other 'show' commands do
            try:
                if os.path.exists(hist_fn):
                    _open_path(os.path.abspath(hist_fn))
                else:
                    print(f"[show history] Not found: {hist_fn}")
                if os.path.exists(macro_fn):
                    _open_path(os.path.abspath(macro_fn))
                else:
                    print(f"[show history] Not found: {macro_fn}")
            except Exception as e:
                print(f"[show history] Failed to open files: {e}")
            return

        # ----- simple mapped opens (GUIs / app) -----
        for aliases, (mod_name, fallback_rel) in SHOW_MAP.items():
            if key in aliases:
                _open_module_or_fallback(mod_name, fallback_rel, base_dir)
                return

        # ----- generic: show <file> -> open <file>.py if it exists -----
        if len(toks) == 1:
            candidate = key

            # Add .py if user didn't type it
            if not candidate.lower().endswith(".py"):
                candidate_py = candidate + ".py"
            else:
                candidate_py = candidate

            # Third search location: macro directory
            try:
                macro_dir = DEFAULT_COUP_DIR  # same location used in your macro handler
            except NameError:
                macro_dir = r"C:\WC\HotSystem\Utils\macro"

            search_paths = [
                os.path.join(os.getcwd(), candidate_py),  # current working directory
                os.path.join(base_dir, candidate_py),  # dispatcher base dir
                os.path.join(macro_dir, candidate_py),  # NEW: macro directory
            ]

            for path in search_paths:
                if os.path.isfile(path):
                    try:
                        _open_path(os.path.abspath(path))
                    except Exception as e:
                        print(f"[show] Failed to open '{path}': {e}")
                    return

        # If we got here, we really don't know this subcommand
        print(f"[show] Unknown subcommand: {sub}")
    def handle_collapse(self, arg: str):
        """Collapse instrument windows: zelux / hrs / cobolt / cld / all.
           Examples:
             collapse zelux
             collapse hrs zelux
             collapse all
        """
        import dearpygui.dearpygui as dpg
        p = self.get_parent()
        words = [w.strip().lower() for w in (arg or "").split() if w.strip()]
        if not words:
            print("Usage: collapse [zelux|hrs|cobolt|cld|all] ...")
            return

        # Resolve window tags for each target
        def _win_tags_for(kind: str):
            tags = []

            # Zelux
            if kind in ("zelux", "zel"):
                if getattr(p, "cam", None) and getattr(p.cam, "window_tag", None):
                    tags.append(p.cam.window_tag)
                else:
                    # fallback: any window alias starting with "Zelux"
                    tags += [a for a in dpg.get_aliases() if a.lower().startswith("zelux")]

            # HRS / Spectrometer
            elif kind in ("hrs", "hrs500", "hrs_500"):
                if getattr(p, "hrs_500_gui", None) and getattr(p.hrs_500_gui, "window_tag", None):
                    tags.append(p.hrs_500_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if
                             a.lower().startswith("hrs_500") or "spectrometer" in a.lower()]

            # Cobolt
            elif kind in ("cobolt", "cob"):
                if getattr(p, "cobolt_gui", None) and getattr(p.cobolt_gui, "window_tag", None):
                    tags.append(p.cobolt_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if a.lower().startswith("cobolt")]

            # CLD1011LP
            elif kind in ("cld", "cld1011", "cld1011lp"):
                if getattr(p, "cld1011lp_gui", None) and getattr(p.cld1011lp_gui, "window_tag", None):
                    tags.append(p.cld1011lp_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if
                             a.lower().startswith("cld1011") or a.lower().startswith("cld")]

            return [t for t in tags if t and dpg.does_item_exist(t)]

        # Expand 'all' to all groups
        targets = []
        if "all" in words:
            targets = ["zelux", "hrs", "cobolt", "cld"]
        else:
            targets = words

        # Collapse each resolved window
        total = 0
        for kind in targets:
            found = _win_tags_for(kind)
            if not found:
                print(f"[collapse] No window found for '{kind}'.")
                continue
            for tag in found:
                try:
                    dpg.configure_item(tag, collapsed=True)
                    print(f"[collapse] {kind}: collapsed '{tag}'.")
                    total += 1
                except Exception as e:
                    print(f"[collapse] Failed to collapse '{tag}': {e}")

        if total == 0:
            print("[collapse] Nothing collapsed.")
    def handle_expand(self, arg: str):
        """Expand instrument windows: zelux / hrs / cobolt / cld / all.
           Examples:
             expand zelux
             expand hrs zelux
             expand all
        """
        import dearpygui.dearpygui as dpg
        p = self.get_parent()
        words = [w.strip().lower() for w in (arg or "").split() if w.strip()]
        if not words:
            print("Usage: expand [zelux|hrs|cobolt|cld|all] ...")
            return

        def _win_tags_for(kind: str):
            tags = []

            # Zelux
            if kind in ("zelux", "zel"):
                if getattr(p, "cam", None) and getattr(p.cam, "window_tag", None):
                    tags.append(p.cam.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if a.lower().startswith("zelux")]

            # HRS / Spectrometer
            elif kind in ("hrs", "hrs500", "hrs_500"):
                if getattr(p, "hrs_500_gui", None) and getattr(p.hrs_500_gui, "window_tag", None):
                    tags.append(p.hrs_500_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if
                             a.lower().startswith("hrs_500") or "spectrometer" in a.lower()]

            # Cobolt
            elif kind in ("cobolt", "cob"):
                if getattr(p, "cobolt_gui", None) and getattr(p.cobolt_gui, "window_tag", None):
                    tags.append(p.cobolt_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if a.lower().startswith("cobolt")]

            # CLD1011LP
            elif kind in ("cld", "cld1011", "cld1011lp"):
                if getattr(p, "cld1011lp_gui", None) and getattr(p.cld1011lp_gui, "window_tag", None):
                    tags.append(p.cld1011lp_gui.window_tag)
                else:
                    tags += [a for a in dpg.get_aliases() if
                             a.lower().startswith("cld1011") or a.lower().startswith("cld")]

            return [t for t in tags if t and dpg.does_item_exist(t)]

        targets = ["zelux", "hrs", "cobolt", "cld"] if "all" in words else words

        total = 0
        for kind in targets:
            found = _win_tags_for(kind)
            if not found:
                print(f"[expand] No window found for '{kind}'.")
                continue
            for tag in found:
                try:
                    dpg.configure_item(tag, collapsed=False)
                    print(f"[expand] {kind}: expanded '{tag}'.")
                    total += 1
                except Exception as e:
                    print(f"[expand] Failed to expand '{tag}': {e}")

        if total == 0:
            print("[expand] Nothing expanded.")
    def handle_hist(self, arg: str):
        """Bind a '>' macro from a history line number.
           Usage:
             hist <n>      # e.g., hist 30  -> saves history[29] as a macro ('> <that line>')
        """
        import re
        p = self.get_parent()
        try:
            n = int((arg or "").strip())
        except Exception:
            print("Usage: hist <line_number>")
            return

        hist = getattr(p, "command_history", [])
        if n < 1 or n > len(hist):
            print(f"[hist] Out of range. Have {len(hist)} history lines.")
            return

        body = hist[n - 1].strip()  # the command to bind as a macro (same as '> <body>')

        if not hasattr(self, "cmd_macros"):
            self.cmd_macros = {}

        # Take first alphabetic char as base key
        m = re.search(r"[A-Za-z]", body)
        if not m:
            print("[hist] No alphabetic command found to bind.")
            return
        base = m.group(0).lower()

        # Find next free key: base, base2, base3, ...
        existing = [k for k in self.cmd_macros.keys() if re.fullmatch(fr"{base}\d*", k)]
        if base not in existing:
            key = base
        else:
            used_nums = {1}
            for k in existing:
                suf = k[len(base):]
                if suf.isdigit():
                    used_nums.add(int(suf))
            key = f"{base}{max(used_nums) + 1}"

        self.cmd_macros[key] = body
        print(f"Saved macro '>{key}': {body!r}")
    def handle_sym(self, arg: str):
        """
        sym start            – launch AutoSym on current ZeluxGUI
        sym stop             – stop AutoSym/FlatTop worker (best effort)
        sym status           – show thread/flag status
        sym reset            – STOP worker and restore OUT_BMP = CORR_BMP
        sym flattop [opts]   – camera-in-the-loop flat-top until uniform
          (examples)
            sym flattop r=0.40 e=0.12 zero !
            sym flattop r=0.40 e=0.12 !
            sym flattop r=0.45 edge=0.10 init=100 m=20 cv=0.10 n=50 seed=1 !
            sym flattop r=0.20 edge=0.22 init=120 m=22 cv=0.08 n=60 ! !!!
            sym flattop r=0.18 e=0.05 profile=supergauss m=8 init=100 more=15 cv=0.08 maxit=50 seed=1 !
            sym flattop r=0.28 e=0.10 profile=supergauss m=6 init=120 more=20 cv=0.08 maxit=50 seed=1 !
            sym flattop r=0.38 e=0.12 profile=supergauss m=6 init=140 more=25 cv=0.08 maxit=60 seed=1 !
            sym flattop r=0.45 e=0.14 profile=supergauss m=6 init=180 more=25 cv=0.10 maxit=70 seed=1 !!!
            sym flattop r=0.32 e=0.12 profile=raisedcos init=140 more=20 cv=0.08 maxit=60 seed=1 !
            sym flattop r=0.30 e=0.18 profile=gauss init=120 more=20 cv=0.08 maxit=50 seed=1 !
            sym flattop r=0.25 e=0.08 profile=supergauss m=6 init=60 more=10 cv=0.12 maxit=25 seed=1 !
            sym flattop r=0.40 e=0.12 profile=raisedcos init=160 more=20 cv=0.08 maxit=60 seed=1 !
            sym flattop r=0.30 e=0.10 profile=supergauss m=6 init=120 more=20 cv=0.08 maxit=50 seed=42 !
            For small spot
            sym flattop r=0.16 e=0.05 profile=supergauss m=10 init=140 more=25 cv=0.08 maxit=60 seed=1 zero !
            sym flattop r=0.18 e=0.06 profile=supergauss m=8 init=140 more=25 cv=0.10 maxit=60 seed=1 zero !
        sym carrier X,Y      – set carrier (grating periods across aperture)
        sym car X,Y          – alias
        sym c X,Y            – alias

        sym dc
        sym dc list
        sym dc 3 --> uses index 3 from the list
        sym dc name=r0.32 vort=2 cb=12 k0=0.03 apod=0.22
        sym dc k0=0.00 cb=0 vort=0 apod=0 demean=1 (only mean-remove)
        """
        import threading, os, shutil, re, cv2, numpy as np

        p = self.get_parent()
        tail = (arg or "").strip()

        cam = getattr(p, "cam", None)
        thr = getattr(p, "_autosym_thread", None)
        owner = getattr(p, "_autosym_owner", None)

        # --- carrier helpers ---
        def get_carrier():
            if cam is None:
                return (250.0, 0.0)
            return tuple(getattr(cam, "_autosym_carrier", (250.0, 0.0)))
        def set_carrier(xy):
            if cam is not None:
                setattr(cam, "_autosym_carrier", (float(xy[0]), float(xy[1])))

        CORR_BMP = getattr(cam, "AUTOSYM_CORR_BMP",
                           r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp")
        OUT_BMP = getattr(cam, "AUTOSYM_OUT_BMP",
                          r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp")

        # ---- split once into sub/rest (robust to extra spaces) ----
        toks = tail.split(maxsplit=1)
        sub = toks[0].lower() if toks else ""
        rest = toks[1] if len(toks) > 1 else ""

        # ---------- carrier ----------
        if sub in ("carrier", "car", "c"):
            s = rest.replace(",", " ").strip()
            if not s:
                cx, cy = get_carrier()
                print(f"carrier = ({cx:.3f}, {cy:.3f})")
                return
            parts = [t for t in s.split() if t]
            if len(parts) < 2:
                print("Usage: sym carrier X,Y   e.g.  sym carrier 100,0")
                return
            try:
                cx, cy = float(parts[0]), float(parts[1])
            except ValueError:
                print("Could not parse carrier numbers. Example: sym car 50.0,3.0")
                return
            set_carrier((cx, cy))
            print(f"carrier set to ({cx:.3f}, {cy:.3f})")
            return

        # ---------- start AutoSym ----------
        if sub in ("start", "run", "go"):
            if thr and thr.is_alive():
                print("AutoSym already running.")
                return
            if cam is None or not hasattr(cam, "_AutoSymWorker"):
                print("ZeluxGUI not available—try 'reload zelux' first.")
                return
            setattr(cam, "_autosym_stop", False)
            t = threading.Thread(target=cam._AutoSymWorker, name="AutoSym", daemon=True)
            p._autosym_thread = t
            p._autosym_owner = cam
            t.start()
            print("AutoSym started.")
            return

        # ---------- stop (AutoSym or FlatTop) ----------
        elif sub in ("stop", "halt", "end"):
            # Prefer stopping on the actual owner (ZeluxGUI)
            tgt = owner if owner is not None else cam
            if tgt is None:
                print("No Zelux owner to signal.")
                return
            # One place sets both flags and joins the thread
            if hasattr(tgt, "_request_stop_and_join"):
                tgt._request_stop_and_join(join_timeout=2.0)
            else:
                # Fallback (older code paths)
                setattr(tgt, "_autosym_stop", True)
                setattr(tgt, "_flattop_stop", True)
                t = getattr(self.get_parent(), "_autosym_thread", None)
                if t and t.is_alive():
                    t.join(timeout=2.0)
                    if t.is_alive():
                        print("Stop requested; worker will exit after current step…")
                    else:
                        print("Worker stopped.")
                else:
                    print("Stop flag set.")
            return

        # ---------- status ----------
        if sub in ("status", "stat"):
            alive = bool(thr and thr.is_alive())
            cur_car = get_carrier()
            print(
                f"Worker running={alive}, "
                f"autosym_stop={bool(getattr(cam, '_autosym_stop', False)) if cam else None}, "
                f"flattop_stop={bool(getattr(cam, '_flattop_stop', False)) if cam else None}, "
                f"carrier=({cur_car[0]:.3f}, {cur_car[1]:.3f})"
            )
            return

        # ---------- reset ----------
        if sub in ("reset", "clear", "flat"):
            tgt = owner if owner is not None else cam
            if tgt is not None:
                setattr(tgt, "_autosym_stop", True)
                setattr(tgt, "_flattop_stop", True)
            t = getattr(p, "_autosym_thread", None)
            if t and t.is_alive():
                t.join(timeout=1.5)

            try:
                if os.path.exists(CORR_BMP):
                    shutil.copy2(CORR_BMP, OUT_BMP)
                    print(f"sym reset → copied correction map to OUT: {OUT_BMP}")
                else:
                    if cam is None or not hasattr(cam, "_write_phase_with_corr"):
                        print("sym reset: correction BMP not found and Zelux writer unavailable.")
                        return
                    corr_u8 = np.zeros((1080, 1920), np.uint8)
                    cam._write_phase_with_corr(np.zeros_like(corr_u8, np.float32), corr_u8, OUT_BMP,
                                               carrier_cmd=(0.0, 0.0), steer_cmd=(0.0, 0.0), settle_s=0.0)
                    print("sym reset → wrote flat phase (fallback) to OUT.")
            except Exception as e:
                print(f"sym reset failed: {e}")
            return

        # ---------- flattop ----------
        if sub.startswith("flattop"):
            if thr and thr.is_alive():
                print("Another worker is running; use 'sym stop' first.")
                return
            if cam is None or not hasattr(cam, "_FlatTopWorker"):
                print("ZeluxGUI not available or _FlatTopWorker missing.")
                return

            import re

            def _normalize_aliases(names: str) -> str:
                """
                Accept either "a|b|c" or "(a|b|c)" and return "a|b|c".
                Also strips surrounding whitespace.
                """
                names = (names or "").strip()
                if len(names) >= 2 and names[0] == "(" and names[-1] == ")":
                    names = names[1:-1].strip()
                return names
            def opt_float(names: str, default: float):
                """
                Match aliases like r|radius|rad and capture a float after '='.
                Examples matched: r=0.25, radius = .3, rad=-1.0
                """
                names = _normalize_aliases(names)
                num = r"(-?(?:\d+(?:\.\d*)?|\.\d+))"
                pat = rf"(?<!\w)(?:{names})\s*=\s*{num}"
                m = re.search(pat, opts, flags=re.IGNORECASE)
                return float(m.group(1)) if m else default
            def opt_int(names: str, default: int):
                """
                Match aliases like m|order and capture an int after '='.
                Examples matched: m=6, order = 8, m=-2
                """
                names = _normalize_aliases(names)
                num = r"(-?\d+)"
                pat = rf"(?<!\w)(?:{names})\s*=\s*{num}"
                m = re.search(pat, opts, flags=re.IGNORECASE)
                return int(m.group(1)) if m else default
            def opt_str(names: str, default: str):
                """
                Match simple word strings after '=' (letters, digits, dash/underscore).
                Examples: profile=supergauss, prof = raisedcos
                """
                names = _normalize_aliases(names)
                word = r"([A-Za-z0-9_\-]+)"
                pat = rf"(?<!\w)(?:{names})\s*=\s*{word}"
                m = re.search(pat, opts, flags=re.IGNORECASE)
                return m.group(1) if m else default

            # parse options
            opts = tail[len("flattop"):]
            zero_car = bool(re.search(r"(?<!\w)(zero)(?!\w)", opts, flags=re.IGNORECASE))

            # NEW: detect open-loop flag "!"
            open_loop = ("!" in opts)
            if open_loop:
                # remove all '!' so they don't interfere with regex parsing
                opts = opts.replace("!", "")

            # ... keep your opt_* helpers as-is ...

            radius_frac = opt_float(r"(r|radius|rad)", 0.22)
            edge_frac = opt_float(r"(edge|e)", 0.06)
            init_steps = opt_int(r"(init|i)", 80)
            more_steps = opt_int(r"(more|m)", 15)
            cv_thr = opt_float(r"(thr|cv)", 0.10)
            max_iter = opt_int(r"(maxit|n)", 40)
            profile_str = opt_str(r"(profile|prof|p)", "supergauss")
            order_m = opt_int(r"(m|order)", 6)

            # seed supports 'None' or an integer
            mseed = re.search(r"(?<!\w)seed\s*=\s*(None|-?\d+)", opts, flags=re.IGNORECASE)
            seed_val = None if (mseed and mseed.group(1).lower() == "none") else (int(mseed.group(1)) if mseed else 1)

            setattr(cam, "_flattop_params", dict(
                rfrac=radius_frac,
                edge=edge_frac,
                init=init_steps,
                more=more_steps,
                cv_thr=cv_thr,
                maxit=max_iter,
                seed=seed_val,
                profile=profile_str,
                m=order_m,
                open_loop=bool(open_loop),
                zero_carrier=zero_car,
            ))
            setattr(cam, "_flattop_stop", False)

            t = threading.Thread(target=cam._FlatTopWorker, name="FlatTop", daemon=True)
            p._autosym_thread = t
            p._autosym_owner = cam
            t.start()
            mode_note = " (OPEN-LOOP)" if open_loop else ""
            print(f"FlatTop started{mode_note} (r={radius_frac:.3f}, edge={edge_frac:.3f}, "
                  f"init={init_steps}, more={more_steps}, cv_thr={cv_thr:.3f}, "
                  f"maxit={max_iter}, seed={seed_val}, profile={profile_str}, m={order_m})")
            return

        # ---------- add carrier to saved zero (zcar / zerocar) ----------
        if sub in ("zcar", "zerocar", "zeroadd"):
            import time, glob, os, re, numpy as np, cv2

            ZERO_DIR = r"C:\WC\SLM_bmp\zero_carrier"

            def _list_zero_files():
                os.makedirs(ZERO_DIR, exist_ok=True)
                paths = glob.glob(os.path.join(ZERO_DIR, "*.npy")) + \
                        glob.glob(os.path.join(ZERO_DIR, "*.bmp"))
                # newest first
                paths.sort(key=os.path.getmtime, reverse=True)
                return paths

            def _print_list(paths):
                print(f"Zero files in {ZERO_DIR} (newest first):")
                for i, pth in enumerate(paths, start=1):
                    ts = os.path.getmtime(pth)
                    print(f"  {i:2d}: {os.path.basename(pth)}  "
                          f"({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))})")

            def _load_phase(path):
                # return phase float32 radians
                if path.lower().endswith(".npy"):
                    ph = np.load(path).astype(np.float32)
                    return np.mod(ph, 2*np.pi).astype(np.float32)
                # bmp fallback (was written with zero carrier)
                u8 = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if u8 is None:
                    raise FileNotFoundError(path)
                if u8.ndim == 3:
                    if u8.shape[2] == 4:
                        u8 = cv2.cvtColor(u8, cv2.COLOR_BGRA2GRAY)
                    else:
                        u8 = cv2.cvtColor(u8, cv2.COLOR_BGR2GRAY)
                u8 = np.clip(u8, 0, 255).astype(np.uint8)
                return (u8.astype(np.float32) * (2*np.pi/255.0)).astype(np.float32)

            paths = _list_zero_files()
            if not paths:
                print(f"No zero-carrier files found in {ZERO_DIR}. Run 'sym flattop ... zero' or 'sym dc' first.")
                return

            rest_str = (rest or "").strip()
            if rest_str.lower() == "list":
                _print_list(paths)
                print("Usage:\n"
                      "  sym zcar list\n"
                      "  sym zcar <idx>  X,Y\n"
                      "  sym zcar name=<substr>  X,Y\n"
                      "  sym zcar X,Y   (latest)")
                return

            # 1) parse the carrier at the end: "... X,Y" or "... X Y"
            mcar = re.search(r"(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)\s*$", rest_str)
            if not mcar:
                print("Usage:\n"
                      "  sym zcar list\n"
                      "  sym zcar <idx>  X,Y\n"
                      "  sym zcar name=<substr>  X,Y\n"
                      "  sym zcar X,Y   (latest)")
                return
            cx, cy = float(mcar.group(1)), float(mcar.group(2))
            sel_part = rest_str[:mcar.start()].strip()

            # 2) selector: index or name=<substr>
            chosen = None
            if sel_part:
                mname = re.search(r"(?i)\bname\s*=\s*([^\s,]+)", sel_part)
                if mname:
                    subname = mname.group(1).lower()
                    for p in paths:
                        if subname in os.path.basename(p).lower():
                            chosen = p
                            break
                    if chosen is None:
                        print(f"No zero file matching name='{subname}'. Try 'sym zcar list'.")
                        return
                else:
                    mind = re.match(r"\s*(\d+)\s*$", sel_part)
                    if mind:
                        idx = int(mind.group(1))
                        if not (1 <= idx <= len(paths)):
                            print(f"Index out of range (1..{len(paths)}). Try 'sym zcar list'.")
                            return
                        chosen = paths[idx - 1]
                    else:
                        print("Could not parse selector. Use an index or name=<substr> before X,Y.")
                        return
            else:
                chosen = paths[0]  # latest by default

            if cam is None or not hasattr(cam, "_write_phase_with_corr"):
                print("ZeluxGUI not available or writer missing.")
                return

            CORR_BMP = getattr(cam, "AUTOSYM_CORR_BMP",
                               r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp")
            OUT_BMP = getattr(cam, "AUTOSYM_OUT_BMP",
                               r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp")
            corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
            if corr_u8 is None:
                print(f"Cannot read correction BMP: {CORR_BMP}")
                return

            try:
                phase = _load_phase(chosen)
            except Exception as e:
                print(f"Failed to load '{chosen}': {e}")
                return

            cam._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                       carrier_cmd=(cx, cy), steer_cmd=(0.0, 0.0), settle_s=0.0)
            print(f"Applied carrier ({cx:.3f},{cy:.3f}) to '{os.path.basename(chosen)}' → {OUT_BMP}")
            return

        # ---------- DC killer on a saved zero-carrier phase ----------
        if sub == "dc":
            import re, glob, time, numpy as np, cv2, os

            ZERO_DIR = r"C:\WC\SLM_bmp\zero_carrier"
            CORR_BMP = getattr(cam, "AUTOSYM_CORR_BMP",
                               r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp")
            OUT_BMP  = getattr(cam, "AUTOSYM_OUT_BMP",
                               r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp")

            def list_zero_candidates():
                os.makedirs(ZERO_DIR, exist_ok=True)
                # prefer .npy (raw phase), fall back to .bmp previews
                npys = sorted(glob.glob(os.path.join(ZERO_DIR, "*.npy")), key=os.path.getmtime)
                bmps = sorted(glob.glob(os.path.join(ZERO_DIR, "*.bmp")), key=os.path.getmtime)
                return npys, bmps

            def load_phase_from(path):
                """Return phase (float32 radians), H,W."""
                if path.lower().endswith(".npy"):
                    ph = np.load(path).astype(np.float32)
                    return np.mod(ph, 2*np.pi).astype(np.float32)
                # .bmp fallback: interpret as *written* phase with ZERO carrier (already corr-applied)
                u8 = cv2.imread(path, cv2.IMREAD_UNCHANGED)
                if u8 is None:
                    raise FileNotFoundError(path)
                if u8.ndim == 3:
                    if u8.shape[2] == 4: u8 = cv2.cvtColor(u8, cv2.COLOR_BGRA2GRAY)
                    else:                u8 = cv2.cvtColor(u8, cv2.COLOR_BGR2GRAY)
                u8 = np.clip(u8, 0, 255).astype(np.uint8)
                # interpret grayscale as 0..2π
                return (u8.astype(np.float32) * (2*np.pi/255.0)).astype(np.float32)

            # --- opts parsing (like your flattop) ---
            opts = rest
            def opt_float(names, default):
                names = names.strip()[1:-1] if names and names[0]=='(' and names[-1]==')' else names
                m = re.search(rf"(?<!\w)(?:{names})\s*=\s*(-?(?:\d+(?:\.\d*)?|\.\d+))", opts, flags=re.I)
                return float(m.group(1)) if m else default
            def opt_int(names, default):
                names = names.strip()[1:-1] if names and names[0]=='(' and names[-1]==')' else names
                m = re.search(rf"(?<!\w)(?:{names})\s*=\s*(-?\d+)", opts, flags=re.I)
                return int(m.group(1)) if m else default
            def opt_bool(name, default):
                m = re.search(rf"(?<!\w){name}\s*=\s*(0|1|true|false)", opts, flags=re.I)
                if not m: return default
                v = m.group(1).lower()
                return v in ("1","true","t","yes","y")

            # defaults
            k0_frac = opt_float("(k0|kzero)", 0.02)   # dark disk radius in k-space, as fraction of min(W,H)
            cb_tile = opt_int("(cb|checker)", 16)      # pixels; 0 disables
            vort    = opt_int("(vort|l)", 1)          # vortex charge; 0 disables
            apod    = opt_float("(apod|sigma)", 0.18) # relative (0..~0.4); 0 disables
            demean  = opt_bool("demean", True)        # complex-mean removal

            # subcommands: list / choose by index / name filter
            if rest.strip().lower().startswith("list"):
                npys, bmps = list_zero_candidates()
                if not (npys or bmps):
                    print(f"No zero-carrier files in {ZERO_DIR}")
                    return
                print("Zero-carrier files (newest last):")
                idx = 1
                for p in npys + bmps:
                    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(p)))
                    print(f"  [{idx:2d}] {os.path.basename(p)}   {ts}")
                    idx += 1
                print("Usage:\n  sym dc <idx> [opts]\n  sym dc name=<substr> [opts]\n  sym dc [opts]  (latest)")
                return

            # pick source
            src_path = None
            m_idx = re.match(r"\s*(\d+)\b", rest.strip())
            m_name = re.search(r"name\s*=\s*([A-Za-z0-9_\-\.]+)", rest, flags=re.I)
            npys, bmps = list_zero_candidates()
            cand = (npys + bmps)
            if not cand:
                print(f"No zero-carrier files in {ZERO_DIR}")
                return

            if m_idx:
                i = int(m_idx.group(1))
                if not (1 <= i <= len(cand)):
                    print(f"Index out of range (1..{len(cand)})")
                    return
                src_path = cand[i-1]
            elif m_name:
                subname = m_name.group(1).lower()
                matches = [p for p in cand if subname in os.path.basename(p).lower()]
                if not matches:
                    print(f"No zero-carrier matches for '{subname}'")
                    return
                src_path = matches[-1]  # newest match
            else:
                src_path = cand[-1]     # latest

            try:
                phase = load_phase_from(src_path)
            except Exception as e:
                print(f"Failed to load zero-carrier: {e}")
                return

            H, W = phase.shape
            # --- DC-kill pipeline ---
            field = np.exp(1j*phase)

            # (1) k-space dark disk
            if k0_frac and k0_frac > 0:
                F = np.fft.fftshift(np.fft.fft2(field))
                yy, xx = np.mgrid[0:H, 0:W]
                cx, cy = W/2.0, H/2.0
                r = np.hypot(xx-cx, yy-cy)
                R0 = max(1.0, k0_frac * min(W, H))  # pixels
                F[r <= R0] = 0
                field = np.fft.ifft2(np.fft.ifftshift(F))

            # (2) π checkerboard
            if cb_tile and cb_tile > 0:
                yy, xx = np.mgrid[0:H, 0:W]
                mask = ((xx//cb_tile + yy//cb_tile) % 2).astype(np.float32)
                cb = np.exp(1j * (np.pi * mask))
                field = field * cb

            # (3) small vortex bias
            if vort and vort != 0:
                yy, xx = np.mgrid[0:H, 0:W]
                ang = np.arctan2(yy - H/2.0, xx - W/2.0)
                field = field * np.exp(1j * vort * ang)

            # (4) gentle apodization
            if apod and apod > 0:
                yy, xx = np.mgrid[0:H, 0:W]
                x = (xx - W/2.0) / (W/2.0)
                y = (yy - H/2.0) / (H/2.0)
                r2 = x*x + y*y
                win = np.exp(-r2 / (2.0 * (apod**2))).astype(np.float32)
                field = field * win

            # (5) complex-mean removal
            if demean:
                field = field - field.mean()

            phase_out = np.angle(field).astype(np.float32)

            # write to OUT_BMP using correction and ZERO carrier
            corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
            if corr_u8 is None:
                print(f"Could not read CORR_BMP: {CORR_BMP}")
                return

            # ZERO carrier here; you can add carrier later with zcar if desired
            cam._write_phase_with_corr(phase_out, corr_u8, OUT_BMP,
                                       carrier_cmd=(0.0, 0.0), steer_cmd=(0.0, 0.0), settle_s=0.0)

            # Save artifacts in ZERO_DIR (timestamped)
            ts = time.strftime("%Y%m%d_%H%M%S")
            base = os.path.splitext(os.path.basename(src_path))[0]
            tag = f"dc_k0{float(k0_frac):.3f}_cb{int(cb_tile)}_v{int(vort)}_a{float(apod):.2f}_dm{int(bool(demean))}"
            npy_out = os.path.join(ZERO_DIR, f"{base}__{tag}__{ts}.npy")
            bmp_out = os.path.join(ZERO_DIR, f"{base}__{tag}__{ts}.bmp")
            try:
                np.save(npy_out, phase_out.astype(np.float32))
                cam._write_phase_with_corr(phase_out, corr_u8, bmp_out,
                                           carrier_cmd=(0.0, 0.0), steer_cmd=(0.0, 0.0), settle_s=0.0)
            except Exception as e:
                print(f"Saved OUT_BMP, but cache save failed: {e}")

            print(f"[dc] Applied DC-kill to '{os.path.basename(src_path)}' → OUT_BMP and '{os.path.basename(bmp_out)}'")
            print(f"     opts: k0={k0_frac:.3f}, cb={cb_tile}, vort={vort}, apod={apod:.2f}, demean={int(bool(demean))}")
            return

        print("Usage: sym start | sym stop | sym status | sym reset | "
              "sym carrier X,Y | sym car X,Y | sym c X,Y | "
              "sym flattop [r=0.22 edge=0.06 init=80 more=15 thr=0.10 maxit=40 seed=1]")
    def handle_g(self, arg: str):
        """
        g [X,Y]
          Add a phase grating (carrier) with X,Y periods across the aperture,
          composed through _write_phase_with_corr, and write to OUT_BMP.

          Examples:  g 100,0   |   g 50.3 3   |   g     (defaults to 100,0)
        """
        import os, cv2, numpy as np

        p = self.get_parent()
        cam = getattr(p, "cam", None)
        if cam is None or not hasattr(cam, "_write_phase_with_corr"):
            print("g: ZeluxGUI/_write_phase_with_corr not available.")
            return

        # Parse "g 100,0" / "g 50.3 3" / "g"
        tail = (arg or "").strip()
        if tail.startswith("g"):
            tail = tail[1:].strip()
        s = tail.replace(",", " ")
        parts = [t for t in s.split() if t]

        try:
            cx = float(parts[0]) if len(parts) >= 1 else 100.0
            cy = float(parts[1]) if len(parts) >= 2 else 0.0
        except ValueError:
            print("g: could not parse numbers. Usage: g 100,0  or  g 50.3 3  or  g")
            return

        # Keep carrier consistent with AutoSym/FlatTop
        setattr(cam, "_autosym_carrier", (cx, cy))

        # Paths (use same ones as AutoSym/FlatTop, with safe defaults)
        CORR_BMP = getattr(cam, "AUTOSYM_CORR_BMP",
                           r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp")
        OUT_BMP = getattr(cam, "AUTOSYM_OUT_BMP",
                          r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp")

        # Load correction to size the zero residual
        corr_u8 = cv2.imread(CORR_BMP, cv2.IMREAD_GRAYSCALE)
        if corr_u8 is None:
            print(f"g: cannot read correction BMP: {CORR_BMP}")
            return

        H, W = corr_u8.shape
        zero_phase = np.zeros((H, W), np.float32)

        # Write: zero residual + requested carrier, no steering
        try:
            cam._write_phase_with_corr(
                zero_phase,  # residual phase = 0
                corr_u8,  # correction map
                OUT_BMP,  # destination BMP (watched by SLM app)
                carrier_cmd=(cx, cy),  # requested grating
                steer_cmd=(0.0, 0.0),
                settle_s=0.0
            )
            print(f"g: wrote grating with carrier=({cx:.3f}, {cy:.3f}) to {OUT_BMP}")
        except Exception as e:
            print(f"g: write failed: {e}")
    def handle_coupx(self, arg: str = ""):
        """
        U-axis move.

        Forms:
          coupx <n>          -> move by <n> coupons
          coupx <um> set     -> set default U move in micrometers (e.g. 'coupx 52.5 set', 'coupx 52.5um set')
          coupx              -> move by stored default (1 coupon worth of µm)
        """
        import shlex

        text = (arg or "").strip()
        # no args -> move by 1 coupon (using self._coupx_move_um)
        if not text:
            return self._coupon_move(axis="u", n=1.0)

        try:
            tokens = shlex.split(text)
        except Exception:
            tokens = text.split()

        # SET MODE: "coupx 52.5 set" or "coupx 52.5um set"
        if len(tokens) >= 2 and tokens[1].lower() == "set":
            raw = tokens[0].lower().replace("um", "").replace("µm", "").strip()
            try:
                um = float(raw)
            except Exception:
                print("coupx set: expected something like 'coupx 52.5 set' or 'coupx 52.5um set'.")
                return False

            # store the per-call move in µm (i.e. one 'coupx' worth)
            self._coupx_move_um = um
            print(f"[coup] coupx set: default U move = {um:.3f} µm")
            return True

        # MOVE MODE: first token must be coupon count
        try:
            n_coupons = float(tokens[0])
        except Exception:
            print("coupx: expected number of coupons or 'coupx <um> set'.")
            return False

        return self._coupon_move(axis="u", n=n_coupons)
    def handle_coupy(self, arg: str = ""):
        """
        V-axis move.

        Forms:
          coupy <n>          -> move by <n> coupons
          coupy <um> set     -> set default V move in micrometers (e.g. 'coupy 40 set', 'coupy 40um set')
          coupy              -> move by stored default (1 coupon worth of µm)
        """
        import shlex

        text = (arg or "").strip()
        if not text:
            return self._coupon_move(axis="v", n=1.0)

        try:
            tokens = shlex.split(text)
        except Exception:
            tokens = text.split()

        # SET MODE
        if len(tokens) >= 2 and tokens[1].lower() == "set":
            raw = tokens[0].lower().replace("um", "").replace("µm", "").strip()
            try:
                um = float(raw)
            except Exception:
                print("coupy set: expected something like 'coupy 40 set' or 'coupy 40um set'.")
                return False

            self._coupy_move_um = um
            print(f"[coup] coupy set: default V move = {um:.3f} µm")
            return True

        # MOVE MODE
        try:
            n_coupons = float(tokens[0])
        except Exception:
            print("coupy: expected number of coupons or 'coupy <um> set'.")
            return False

        return self._coupon_move(axis="v", n=n_coupons)
    def _coupon_move(self, axis: str, n: float):
        """
        Move by n coupons along U or V.

        axis:
          'u' -> ch0  (U axis, uses self._coupx_move_um µm per coupon)
          'v' -> ch1  (V axis, uses self._coupy_move_um µm per coupon)
        n   : coupon count (sign sets direction).
        """
        gui = getattr(self.get_parent(), "smaractGUI", None)
        if gui is None:
            print("Smaract GUI not available (expected at parent.smaractGUI)")
            return False

        axis = axis.lower()
        if axis not in ("u", "v"):
            print(f"Unknown axis '{axis}', expected 'u' or 'v'.")
            return False

        if axis == "u":
            ch = 0
            per_coupon_um = float(getattr(self, "_coupx_move_um", 80.0))
        else:
            ch = 1
            per_coupon_um = float(getattr(self, "_coupy_move_um", 70.0))

        direction = +1.0 if n >= 0 else -1.0
        mag_um = abs(n) * per_coupon_um

        angle_deg = float(getattr(self, "_coupon_angle_deg", CHIP_ANGLE))
        dpg.set_value(f"{gui.prefix}_ch2_Cset", angle_deg)

        wid = f"{gui.prefix}_ch{ch}_Cset"
        dpg.set_value(wid, mag_um)

        try:
            gui.move_uv(sender=None, app_data=None, user_data=(ch, direction, True))
            print(
                f"coupon move: axis={axis.upper()} ch={ch} n={n} "
                f"→ {mag_um:.1f} µm (per-coupon={per_coupon_um:.1f}), dir={int(direction)}"
            )
            return True
        except Exception as e:
            print(f"coupon move failed: {e}")
            return False
    def _get_spc_handles(self):
        """Best-effort grab of (evt, running_flag_ref, exp_obj) for waiting."""
        # CommandDispatcher -> parent -> hrs_500_gui.dev._exp
        parent = self.get_parent()
        # evt/running live on the object that owns handle_acquire_spectrum (often self)
        # Try self-first, then parent.
        owner = self
        evt = getattr(owner, "_spc_done_evt", None)
        running = getattr(owner, "_spc_running", None)
        if not isinstance(evt, threading.Event):
            owner = parent if parent is not None else self
            evt = getattr(owner, "_spc_done_evt", None)
            running = getattr(owner, "_spc_running", None)

        exp = None
        try:
            p = self.get_parent()
            exp = getattr(getattr(getattr(p, "hrs_500_gui", None), "dev", None), "_exp", None)
        except Exception:
            pass
        return evt if isinstance(evt, threading.Event) else None, owner, exp
    def _wait_spc_done(self, min_quiet_ms=600, hard_timeout_s=900):
        """
        Wait until SPC is done using multiple signals:
          1) _spc_running becomes False (if available)
          2) _spc_done_evt is set (if available)
          3) _exp.IsUpdating == False continuously for min_quiet_ms
        """
        evt, owner, exp = self._get_spc_handles()
        t0 = time.time()
        quiet_start = None

        def _is_updating():
            try:
                return bool(getattr(exp, "IsUpdating", False))
            except Exception:
                return False

        while True:
            # Hard timeout guard
            if hard_timeout_s is not None and (time.time() - t0) > hard_timeout_s:
                print("[wait] timed out; proceeding anyway.")
                return False

            # Check event
            if evt is not None and evt.is_set():
                # still enforce a brief quiet window to be safe
                if not _is_updating():
                    if quiet_start is None:
                        quiet_start = time.time()
                    if (time.time() - quiet_start) * 1000 >= min_quiet_ms:
                        return True
                else:
                    quiet_start = None

            # Check running flag
            running = getattr(owner, "_spc_running", None)
            if running is False:
                # again, enforce quiet
                if not _is_updating():
                    if quiet_start is None:
                        quiet_start = time.time()
                    if (time.time() - quiet_start) * 1000 >= min_quiet_ms:
                        return True
                else:
                    quiet_start = None

            # If we have no signals at all, fall back to watching IsUpdating only
            if evt is None and running is None:
                if not _is_updating():
                    if quiet_start is None:
                        quiet_start = time.time()
                    if (time.time() - quiet_start) * 1000 >= min_quiet_ms:
                        return True
                else:
                    quiet_start = None

            time.sleep(0.05)
    def _get_coupon_center_uv(self):
        """Return saved (U,V) center in µm; default (16,28)."""
        if not hasattr(self, "_coupon_center_uv") or not isinstance(self._coupon_center_uv, (tuple, list)) or len(
                self._coupon_center_uv) != 2:
            self._coupon_center_uv = (16.0, 28.0)
        return float(self._coupon_center_uv[0]), float(self._coupon_center_uv[1])
    def _set_coupon_center_uv(self, u_um: float, v_um: float):
        """Save (U,V) center in µm."""
        self._coupon_center_uv = (float(u_um), float(v_um))
        print(f"[coup] center saved: U={u_um:.3f} µm, V={v_um:.3f} µm")
    def _read_current_position_um(self):
        """
        Try to read current position µm from the Smaract GUI (parent.smaractGUI).
        First tries common DPG widgets '<prefix>_ch0_Cpos'/'_ch1_Cpos'; add your own getter if available.
        """
        p=self.get_parent()
        p.smaractGUI.dev.GetPosition()
        pos = p.smaractGUI.dev.AxesPositions
        x_value = pos[0] * 1e-6  # convert pm to µm
        y_value = pos[1] * 1e-6
        z_value = pos[2] * 1e-6
        return x_value, y_value, z_value
    def handle_coup(self, *args, nested: bool = False):
        """
        COUP COMMANDS
        ------------------------------------------------------------
        General:
          coup stop
              Request cancellation of the running coup sequence.

          coup status
              Print whether coup engine is running or idle.

          coup <steps.txt>
              Run step file (one command per line; ';' also splits).

        ------------------------------------------------------------
        Coupon Grid Navigation:
          coup bottom left [<label>]
          coup bot left [<label>]
          coup corner [<label>]
              Move from the provided label (or ask interactively)
              to the bottom-left coupon (NORM4L). Aliases supported.

          coup shiftx
          coup shifty
              Shift one array position along U or V using the
              stored shift factors.

          coup shiftx <factor>
          coup shifty <factor>
              Move by:  <factor> * (stored shift factor).

          coup shiftx set <val>
          coup shifty set <val>
              Set shift factor.
                • If <val> is a plain number → coupons factor.
                • If <val> ends with 'um' → interpreted as microns
                  and automatically converted to coupon units.

        ------------------------------------------------------------
        Coupon Center Calibration:
          coup center
              Move to the nearest coupon center based on the stored
              chip angle, center reference, and coupon geometry.

          coup center set
              Store current position as the coupon center reference.

          coup center <U> <V>
              Explicitly set coupon center reference in µm.

          coup center from label <dU, dV>
              Store that the chip center is offset from the current
              coupon *label* position by (dU, dV) µm.
              (No movement.)

          coup center from label
              Apply the previously stored offsets (dU, dV):
              Move from the current (label) position to the chip
              center. Also updates the coupon-center reference.

        ------------------------------------------------------------
        Label From Center (inverse move):
          coup label from center
              Use the stored (dU, dV) offsets and move from the
              chip center back to the corresponding coupon label.
              Move = (−dU, −dV).
              Requires prior 'coup center from label ...'.

        ------------------------------------------------------------
        Chip Angle / Chip State:
          coup angle set
              Store current axis-2 angle widget value as chip angle.

          coup inv set
              Mark chip as inverted (affects corner orientation).

        ------------------------------------------------------------
        State Management:
          coup save
              Save chip angle, coupon center, shift factors,
              move-per-coupon values, label offsets, chip name,
              and saved coupon names to coup_state.json.

          coup save name
              Also save a named copy: coup_state_<chip>.json

          coup load [file.json]
              Load angle, center, shift factors, move-per-coupon,
              label offsets, chip name, and saved coupon labels.
              If no file is given, the default coup_state.json is used.

        ----------------
        coup ?
        coup <name>
        coup next
        """

        import threading, os, math, shlex, re, json, time

        # Auto-detect nested context: if we're already inside the running coup thread,
        # treat this invocation as nested even if the caller forgot to pass nested=True.
        try:
            if not nested:
                cur = threading.current_thread()
                if getattr(self, "_coup_active_evt", None) and self._coup_active_evt.is_set():
                    if cur is getattr(self, "_coup_thread", None):
                        nested = True
        except Exception:
            pass

        use_shift = False

        # --- Coupon sequence order for coup <name> / coup next ---
        # Visit order on the 4x3 grid:
        #   Row4: NORM4L  7L  8L
        #   Row3: NORM3L  5L  6L
        #   Row2: NORM2L  3L  4L
        #   Row1: NORM1L  1L  2L
        COUP_SEQ = [
            "NORM4", "7", "8",
            "NORM3", "5", "6",
            "NORM2", "3", "4",
            "NORM1", "1", "2",
        ]
        COUP_SEQ_SET = set(COUP_SEQ)
        def _canon_coupon_name(name: str) -> str:
            """
            Normalize coupon name:
              - case-insensitive
              - NORM4     -> NORM4L
              - NORM4A    -> NORM4A  (letter kept)
              - 7         -> 7L
              - 7A        -> 7A
              - 7b        -> 7B
              - Reject invalid formats.
            """
            s = (name or "").strip().upper()

            if not s:
                raise ValueError("empty coupon name")

            # Case 1: NORM row
            if s.startswith("NORM"):
                body = s[4:]  # after NORM
                if not body:
                    raise ValueError(f"invalid NORM coupon '{name}'")

                # body may be: "4", "4A", etc.
                if len(body) == 1:
                    # only number, default letter L
                    if body.isdigit():
                        return f"NORM{body}L"
                    else:
                        raise ValueError(f"invalid NORM label '{name}'")

                # length >= 2 → number + letter
                num = body[:-1]
                letter = body[-1]

                if not num.isdigit():
                    raise ValueError(f"invalid NORM number in '{name}'")

                if not letter.isalpha():
                    raise ValueError(f"invalid NORM suffix in '{name}'")

                return f"NORM{num}{letter}"

            # Case 2: Numeric coupon (1..8) with optional trailing letter
            if s[0].isdigit():
                # Get numeric prefix
                num = ""
                i = 0
                while i < len(s) and s[i].isdigit():
                    num += s[i]
                    i += 1

                if not num:
                    raise ValueError(f"invalid coupon '{name}'")

                # If nothing after number → default letter L
                if i == len(s):
                    return f"{num}L"

                # Else suffix must be a letter
                letter = s[i:]
                if len(letter) != 1 or not letter.isalpha():
                    raise ValueError(f"invalid suffix '{letter}' in '{name}'")

                return f"{num}{letter}"

            raise ValueError(f"unrecognized coupon label '{name}'")
        def _seq_key(name: str) -> str:
            """
            Map NORM4A, NORM4B → NORM4
            Map 7A, 7B, 7C     → 7
            Used to find sequence position.
            """
            n = name.upper()
            if n.startswith("NORM"):
                # Strip trailing letter: NORM4X -> NORM4
                return n[:-1] if n[-1].isalpha() else n
            else:
                # numeric: 7A -> 7
                return n[:-1] if n[-1].isalpha() else n
        def _is_coup_busy() -> bool:
            try:
                return bool(getattr(self, "_coup_active_evt", None)) and self._coup_active_evt.is_set()
            except Exception:
                return False
        def _get_coup_state_path() -> str:
            """Return full path for coup state file, ensuring base dir exists."""
            try:
                base_dir = DEFAULT_COUP_DIR
            except NameError:
                base_dir = r"c:\WC\HotSystem\Utils\macro"
            try:
                os.makedirs(base_dir, exist_ok=True)
            except Exception:
                pass
            return os.path.join(base_dir, STATE_FILENAME)
        def _coup_save_state(extra_named_copy: bool = False) -> bool:
            """Save angle, center, and shift factors to JSON. Returns True/False."""
            import json

            # Angle: use stored coupon angle if present, else fall back to CHIP_ANGLE
            try:
                angle_deg = float(getattr(self, "_coupon_angle_deg", CHIP_ANGLE))
            except Exception:
                angle_deg = float(CHIP_ANGLE)

            # Round to 1 decimal (e.g. -2.29999 -> -2.3)
            angle_deg_rounded = round(angle_deg, 3)

            # Center: read from your existing reference storage
            try:
                u_ref, v_ref = self._get_coupon_center_uv()
            except Exception as e:
                print(f"[coup] save: cannot read coupon center UV: {e}")
                return False

            # Shift factors: per-instance, with constants as defaults
            shift_x = float(getattr(self, "_coup_shift_x_factor", 5))
            shift_y = float(getattr(self, "_coup_shift_y_factor", 5.43))

            # Chip name (optional)
            chip_name = str(getattr(self, "_chip_name", "") or "").strip()

            # Chip inverted flag (optional)
            chip_inverted = bool(getattr(self, "_chip_inverted", False))

            # Center-from-label offsets (optional)
            dU_from_label = float(getattr(self, "_center_from_label_dU_um", 0.0))
            dV_from_label = float(getattr(self, "_center_from_label_dV_um", 0.0))

            # uz/vz overrides from Smaract GUI (optional)
            uz_override = vz_override = None
            try:
                gui = getattr(self.get_parent(), "smaractGUI", None)
                if gui is not None:
                    uz_override = getattr(gui, "_uz_override", None)
                    vz_override = getattr(gui, "_vz_override", None)
                    # Make sure they're JSON-friendly
                    if uz_override is not None:
                        uz_override = float(uz_override)
                    if vz_override is not None:
                        vz_override = float(vz_override)
            except Exception:
                uz_override = vz_override = None


            # Collect coupon labels (if any) in a JSON-friendly way
            labels_to_save = {}
            try:
                lbls = getattr(self, "_coupon_labels", {}) or {}
                for name, info in lbls.items():
                    try:
                        key = str(name)
                        u = float(info.get("u_um"))
                        v = float(info.get("v_um"))
                        labels_to_save[key] = {
                            "u_um": u,
                            "v_um": v,
                        }
                    except Exception:
                        # Skip malformed entries
                        continue
            except Exception:
                labels_to_save = {}

            # Custom "coup next" sequence + moves (optional)
            custom_seq_to_save = []
            custom_moves_to_save = {}

            try:
                seq = getattr(self, "_coup_next_seq", None)
                if isinstance(seq, list) and seq:
                    custom_seq_to_save = [str(s) for s in seq]
            except Exception:
                custom_seq_to_save = []

            try:
                moves = getattr(self, "_coup_next_moves", None)
                if isinstance(moves, dict) and moves:
                    for base, val in moves.items():
                        try:
                            dx = float(val.get("dx", 0.0))
                            dy = float(val.get("dy", 0.0))
                            custom_moves_to_save[str(base)] = {"dx": dx, "dy": dy}
                        except Exception:
                            continue
            except Exception:
                custom_moves_to_save = {}

            state = {
                "angle_deg": angle_deg_rounded,
                "center_u_um": float(u_ref),
                "center_v_um": float(v_ref),
                "shift_x_factor": shift_x,
                "shift_y_factor": shift_y,
                "chip_inverted": chip_inverted,
                "coupx_move_um": float(getattr(self, "_coupx_move_um", 0.0)),
                "coupy_move_um": float(getattr(self, "_coupy_move_um", 0.0)),
                "center_from_label_dU_um": dU_from_label,  # NEW
                "center_from_label_dV_um": dV_from_label,  # NEW
                "uz_override": uz_override,
                "vz_override": vz_override,
                "coupon_labels": labels_to_save,
                "chip_name": chip_name,
            }

            if custom_seq_to_save:
                state["coup_next_seq"] = custom_seq_to_save
            if custom_moves_to_save:
                state["coup_next_moves"] = custom_moves_to_save

            path = _get_coup_state_path()
            ok = True
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(state, f, indent=2)
                print(
                    f"[coup] save: angle={angle_deg_rounded:.1f}°, "
                    f"center=(U={u_ref:.3f}, V={v_ref:.3f}) µm, "
                    f"shiftX={shift_x:.3f}, shiftY={shift_y:.3f} -> '{path}'"
                    f"chip='{chip_name}' -> '{path}'"
                )
            except Exception as e:
                print(f"[coup] save: failed to write '{path}': {e}")
                return False

            # Optional per-chip extra copy: coup_state_<chip_name>.json
            if extra_named_copy:
                if not chip_name:
                    print("[coup] save name: chip_name not set; use 'chip name <name>' first.")
                    return ok

                base_dir = os.path.dirname(path)
                safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", chip_name)
                named_path = os.path.join(base_dir, f"coup_state_{safe_name}.json")
                try:
                    with open(named_path, "w", encoding="utf-8") as f:
                        json.dump(state, f, indent=2)
                    print(f"[coup] save name: also wrote '{named_path}'")
                except Exception as e:
                    print(f"[coup] save name: failed to write '{named_path}': {e}")
                    ok = False

            return ok

        # --- ensure events exist (compat with _coup_abort_evt / _coup_cancel) ---
        if not hasattr(self, "_coup_active_evt") or not isinstance(getattr(self, "_coup_active_evt"), threading.Event):
            self._coup_active_evt = threading.Event()
        if not hasattr(self, "_coup_abort_evt") or not isinstance(getattr(self, "_coup_abort_evt"), threading.Event):
            self._coup_abort_evt = threading.Event()
        if not hasattr(self, "_coup_cancel") or not isinstance(getattr(self, "_coup_cancel"), threading.Event):
            self._coup_cancel = threading.Event()
        if not hasattr(self, "_coup_pause_evt") or not isinstance(getattr(self, "_coup_pause_evt"), threading.Event):
            self._coup_pause_evt = threading.Event()

        if not args:
            print("Usage: coup [shiftx|shifty|stop|status|<steps.txt>]")
            return False

        # Turn args into a clean token list (handles quoting)
        try:
            tokens = shlex.split(" ".join(str(a) for a in args))
        except Exception:
            tokens = [str(a).strip() for a in args if str(a).strip()]

        if not tokens:
            print("Usage: coup [shiftx [factor]|shifty [factor]|stop|status|<steps>]")
            return False

        sub = tokens[0].lower()

        # --- coup ? : print stored sequence label ---
        if sub == "?":
            cur = getattr(self, "_coup_seq_label", None)
            if cur:
                print(f"[coup] current sequence label: {cur}")
            else:
                print("[coup] no sequence label stored. Use 'coup NORM4L' (or 7L, 8L, etc.) first.")
            return True


        # --- coup save/load: persist coupon angle + center ---
        if sub == "save":
            # `coup save`      -> normal save
            # `coup save name` -> normal save + per-chip copy
            extra_named_copy = len(tokens) >= 2 and tokens[1].lower() == "name"
            _coup_save_state(extra_named_copy=extra_named_copy)
            return True
        if sub == "load":
            # Optional: coup load <file_name>
            # - No argument  -> default coup_state.json via _get_coup_state_path()
            # - With argument -> resolve relative to DEFAULT_COUP_DIR (or fallback), default .json extension
            if len(tokens) >= 2 and tokens[1].strip():
                raw_name = tokens[1].strip().strip('"').strip("'")

                # Add .json if no extension given
                fname = raw_name
                if not os.path.splitext(fname)[1]:
                    fname = fname + ".json"

                # If no directory given, look in the coup/macro dir
                if not os.path.isabs(fname) and not os.path.dirname(fname):
                    try:
                        base_dir = DEFAULT_COUP_DIR
                    except NameError:
                        base_dir = r"c:\WC\HotSystem\Utils\macro"
                    path = os.path.join(base_dir, fname)
                else:
                    path = fname
            else:
                # Default behavior: load the main coup_state.json
                path = _get_coup_state_path()

            if not os.path.isfile(path):
                print(f"[coup] load: state file not found: '{path}'.")
                return False

            try:
                with open(path, "r", encoding="utf-8") as f:
                    state = json.load(f)
            except Exception as e:
                print(f"[coup] load: failed to read '{path}': {e}")
                return False

            try:
                angle_deg = float(state["angle_deg"])
                u_ref = float(state["center_u_um"])
                v_ref = float(state["center_v_um"])
            except Exception as e:
                print(f"[coup] load: invalid core data in '{path}': {e}")
                return False

            # Optional shift factors
            shift_x = state.get("shift_x_factor", None)
            shift_y = state.get("shift_y_factor", None)

            # Center-from-label offsets (optional)
            if "center_from_label_dU_um" in state:
                try:
                    self._center_from_label_dU_um = float(state["center_from_label_dU_um"])
                except Exception:
                    pass
            if "center_from_label_dV_um" in state:
                try:
                    self._center_from_label_dV_um = float(state["center_from_label_dV_um"])
                except Exception:
                    pass


            # Optional chip name
            chip_name = state.get("chip_name", "")
            if chip_name is not None:
                self._chip_name = str(chip_name).strip()

            # Optional chip inverted flag
            chip_inverted = state.get("chip_inverted", False)
            self._chip_inverted = bool(chip_inverted)

            if "coupx_move_um" in state:
                self._coupx_move_um = float(state["coupx_move_um"])
            if "coupy_move_um" in state:
                self._coupy_move_um = float(state["coupy_move_um"])

            # Apply angle
            self._coupon_angle_deg = angle_deg

            # Apply center
            try:
                self._set_coupon_center_uv(u_ref, v_ref)
            except Exception as e:
                print(f"[coup] load: failed to set center: {e}")
                return False

            # Apply shift factors if present
            if shift_x is not None:
                try:
                    self._coup_shift_x_factor = float(shift_x)
                except Exception:
                    print(f"[coup] load: warning: invalid shift_x_factor '{shift_x}' in state; ignoring.")
            if shift_y is not None:
                try:
                    self._coup_shift_y_factor = float(shift_y)
                except Exception:
                    print(f"[coup] load: warning: invalid shift_y_factor '{shift_y}' in state; ignoring.")

            # Reflect loaded angle into GUI axis-2 (best-effort) and restore uz/vz overrides
            try:
                gui = getattr(self.get_parent(), "smaractGUI", None)
                if gui is not None:
                    # angle
                    try:
                        dpg.set_value(f"{gui.prefix}_ch2_Cset", angle_deg)
                    except Exception:
                        pass
                    # NEW: uz/vz overrides
                    try:
                        uz_override = state.get("uz_override", None)
                        if uz_override is not None:
                            gui._uz_override = float(uz_override)
                    except Exception:
                        pass
                    try:
                        vz_override = state.get("vz_override", None)
                        if vz_override is not None:
                            gui._vz_override = float(vz_override)
                    except Exception:
                        pass
            except Exception:
                pass

            # Restore coupon labels if present
            labels_from_state = state.get("coupon_labels", None)
            if isinstance(labels_from_state, dict):
                clean_labels = {}
                for name, info in labels_from_state.items():
                    try:
                        u = float(info.get("u_um"))
                        v = float(info.get("v_um"))
                        clean_labels[str(name)] = {
                            "u_um": u,
                            "v_um": v,
                        }
                    except Exception:
                        continue
                self._coupon_labels = clean_labels
                print(f"[coup] load: restored {len(clean_labels)} coupon name(s).")

            # Restore custom "coup next" sequence + moves, if present
            seq_state = state.get("coup_next_seq", None)
            moves_state = state.get("coup_next_moves", None)

            if isinstance(seq_state, list) and seq_state:
                clean_seq = [str(s) for s in seq_state if str(s).strip()]
                if clean_seq:
                    self._coup_next_seq = clean_seq
                    print(f"[coup] load: restored custom 'next' sequence ({len(clean_seq)} step(s)).")

            if isinstance(moves_state, dict) and moves_state:
                clean_moves = {}
                for base, val in moves_state.items():
                    try:
                        dx = float(val.get("dx", 0.0))
                        dy = float(val.get("dy", 0.0))
                        clean_moves[str(base)] = {"dx": dx, "dy": dy}
                    except Exception:
                        continue
                if clean_moves:
                    self._coup_next_moves = clean_moves
                    print(f"[coup] load: restored custom 'next' moves for {len(clean_moves)} base name(s).")


            print(
                f"[coup] load: restored angle={angle_deg:.3f}°, "
                f"center=(U={u_ref:.3f}, V={v_ref:.3f}) µm, "
                f"shiftX={getattr(self, '_coup_shift_x_factor', 5):.3f}, "
                f"shiftY={getattr(self, '_coup_shift_y_factor', 5.43):.3f}, "
                f"chip='{getattr(self, '_chip_name', '')}' "
                f"inverted={getattr(self, '_chip_inverted', False)} "
                f"from '{path}'."
            )
            return True
        if sub == "status":
            if self._coup_active_evt.is_set():
                cur = getattr(self, "_current_coup_cmd", None)
                line_no = getattr(self, "_coup_current_line_no", None)
                if cur and line_no is not None:
                    print(f"[coup] running → line {line_no}: {cur}")
                if cur:
                    print(f"[coup] running → current command: {cur}")
                else:
                    print("[coup] running → preparing next command...")
            else:
                print("[coup] idle")
            return True
        # --- coup resume [factor] : resume from pause and set pause factor ---
        #   coup resume       -> factor = 1.0  (pause every 3 SPC)
        #   coup resume 2     -> factor = 2.0  (pause every 6 SPC)
        #   coup resume 0.5   -> factor = 0.5  (pause every 1–2 SPC, rounded)
        if sub == "resume":
            factor = 1.0
            if len(tokens) >= 2:
                try:
                    factor = float(tokens[1])
                except Exception:
                    print(f"[coup] resume: invalid factor '{tokens[1]}'. Use e.g. 'coup resume 2'.")
                    return False

            if factor <= 0:
                print("[coup] resume: factor must be > 0.")
                return False

            self._coup_pause_factor = factor

            # make sure pause event exists and signal resume
            import threading as _th
            evt = getattr(self, "_coup_pause_evt", None)
            if not isinstance(evt, _th.Event):
                self._coup_pause_evt = _th.Event()
                evt = self._coup_pause_evt
            evt.set()

            spc_threshold = max(1, int(round(3 * factor)))
            print(f"[coup] resume: pause factor set to {factor:.3f} "
                  f"(will pause every {spc_threshold} SPC commands).")
            return True
        if sub == "stop":
            # signal all known cancel flags
            try:
                self._coup_abort_evt.set()
            except Exception:
                pass
            try:
                self._coup_cancel.set()
            except Exception:
                pass

            # try to stop an in-flight SPC so waits unblock quickly
            try:
                p = self.get_parent()
                exp = getattr(getattr(getattr(p, "hrs_500_gui", None), "dev", None), "_exp", None)
                if exp:
                    try:
                        exp.Stop()
                    except Exception:
                        pass
                exp = getattr(getattr(getattr(p, "proem_gui", None), "dev", None), "_exp", None)
                if exp:
                    try:
                        exp.Stop()
                    except Exception:
                        pass
            except Exception:
                pass
            print("[coup] stop requested.")
            return True
        # --- coup angle: set coupon chip angle from current axis-2 position ---
        if sub == "angle":
            if len(tokens) >= 2 and tokens[1].lower() == "set":
                # Find the GUI_Smaract instance
                gui = getattr(self.get_parent(), "smaractGUI", None)
                if gui is None:
                    print("[coup] angle set: Smaract GUI not available (expected at parent.smaractGUI).")
                    return False

                # Try to read current axis-2 angle from GUI widgets
                angle_val = None
                try:
                    # Adjust the widget id to whatever you actually use for axis-2 current angle
                    angle_val = dpg.get_value(f"{gui.prefix}_ch2_Cset")
                    angle_val = round(float(angle_val), 3)
                except Exception as e:
                    print(f"[coup] angle set: failed to read axis-2 angle: {e}")
                    return False

                try:
                    self._coupon_angle_deg = float(angle_val)
                except Exception as e:
                    print(f"[coup] angle set: invalid angle value '{angle_val}': {e}")
                    return False

                print(f"[coup] angle set: chip angle now {self._coupon_angle_deg:.3f}° "
                      f"(taken from axis-2 current position).")
                _coup_save_state()
                return True

            # Usage/help if someone just types `coup angle`
            print("[coup] angle: use 'coup angle set' to store current axis-2 as chip angle.")
            return False
        # --- coup inv set: mark chip as inverted and save ---
        if sub == "inv":
            if len(tokens) >= 2 and tokens[1].lower() == "set":
                self._chip_inverted = True
                print("[coup] inv set: chip is now marked as inverted (chip_inverted=True).")

                # Auto-save state (like angle/center/shift setters)
                _coup_save_state()
                return True

            print("Usage: coup inv set")
            return False

        # --- coup copy [state] [chip_name]: copy map/sb/state (+ optionally TIFs) to chip folder ---
        if sub == "copy":
            import shutil

            # 1) Mode flags
            copy_tifs = True

            # Syntax:
            #   coup copy                 -> use stored _chip_name, copy everything
            #   coup copy <name>          -> chip=<name>, copy everything
            #   coup copy state           -> use stored _chip_name, copy only state (no TIFs)
            #   coup copy state <name>    -> chip=<name>, copy only state (no TIFs)

            arg_idx = 1
            if len(tokens) >= 2 and tokens[1].lower() == "state":
                copy_tifs = False
                arg_idx = 2

            # 2) Determine chip name
            if len(tokens) > arg_idx:
                chip_name_raw = " ".join(tokens[arg_idx:]).strip().strip('"').strip("'")
            else:
                chip_name_raw = str(getattr(self, "_chip_name", "") or "").strip()

            if not chip_name_raw:
                print("[coup] copy: chip name not set. Use 'chip name <name>' or 'coup copy [state] <name>'.")
                return False

            # Sanitize for folder name
            safe_chip = re.sub(r'[^A-Za-z0-9_.\- ]+', "_", chip_name_raw)

            base_out = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\FemtoSys\Chip Characterizations"
            chip_dir = os.path.join(base_out, safe_chip)
            tif_dir = os.path.join(chip_dir, "tif_files")

            try:
                os.makedirs(chip_dir, exist_ok=True)
                if copy_tifs:
                    os.makedirs(tif_dir, exist_ok=True)
            except Exception as e:
                print(f"[coup] copy: failed to create output dirs: {e}")
                return False

            print(f"[coup] copy: target folder = '{chip_dir}' "
                  f"({'state-only, no TIFs' if not copy_tifs else 'full copy incl. TIFs'})")

            # 3) Figure out where coup_state.json + my_next.json live
            try:
                state_path = _get_coup_state_path()  # e.g. C:\WC\HotSystem\Utils\macro\coup_state.json
                state_dir = os.path.dirname(state_path)
            except Exception:
                # Fallback to old behavior if something weird happens
                state_dir = r"C:\WC\HotSystem\Utils\macro"
                state_path = os.path.join(state_dir, "coup_state.json")

            my_next_path = os.path.join(state_dir, "my_next.json")

            # 4) Copy fixed files
            fixed_sources = [
                r"C:\WC\HotSystem\map.jpg",
                r"C:\WC\HotSystem\Utils\macro\sb.py",
                state_path,          # coup_state.json from its real location
                r"C:\WC\SLM_bmp\Calib\Averaged_calibration.tif",
                r"C:\WC\HotSystem\Utils\map_calibration.json",
            ]

            # Add my_next.json *from the same folder as coup_state.json* if it exists
            if os.path.isfile(my_next_path):
                fixed_sources.append(my_next_path)

            for src in fixed_sources:
                try:
                    if not os.path.isfile(src):
                        print(f"[coup] copy: missing file (skipped): {src}")
                        continue
                    dst = os.path.join(chip_dir, os.path.basename(src))
                    shutil.copy2(src, dst)
                    print(f"[coup] copy: {src} -> {dst}")
                except Exception as e:
                    print(f"[coup] copy: failed to copy '{src}': {e}")

            # 5) Optionally copy all TIF files
            if copy_tifs:
                tif_src_dir = r"C:\Users\Femto\Work Folders\Documents\LightField"
                if not os.path.isdir(tif_src_dir):
                    print(f"[coup] copy: TIF source directory not found: '{tif_src_dir}'")
                    return False

                tif_count = 0
                try:
                    for name in os.listdir(tif_src_dir):
                        if not name.lower().endswith(".tif"):
                            continue
                        src = os.path.join(tif_src_dir, name)
                        if not os.path.isfile(src):
                            continue
                        dst = os.path.join(tif_dir, name)
                        try:
                            shutil.copy2(src, dst)
                            tif_count += 1
                        except Exception as e:
                            print(f"[coup] copy: failed to copy TIF '{src}': {e}")
                    print(f"[coup] copy: copied {tif_count} TIF file(s) to '{tif_dir}'.")
                except Exception as e:
                    print(f"[coup] copy: error while scanning TIF directory: {e}")
                    return False

            print(f"[coup] copy: done for chip '{chip_name_raw}' → '{chip_dir}'")
            return True

        # --- coup clear / coup clear <label> ---
        if sub == "clear":
            # No argument → clear all coupon labels
            if len(tokens) == 1:
                return self.handle_coupon("clear")
            # With argument(s) → clear only that label
            label = " ".join(tokens[1:]).strip()
            if not label:
                print("[coup] clear: missing label. Usage: coup clear <label>")
                return False
            return self.handle_coupon(f"clear {label}")

        # --- SINGLE busy guard (applies only to top-level invocations) ---
        non_blocking = {"status", "stop", "save", "load", "angle","resume","copy","clear"}
        if (sub not in non_blocking) and _is_coup_busy() and not nested:
            print("[coup] already running.")
            return False

        # --- coup label from center: inverse of "center from label" ---
        if sub == "label":
            # --- NEW: "coup label from center set" ---
            if len(tokens) == 4 and tokens[3].lower() == "set":
                try:
                    # Current stage position (µm)
                    u_cur, v_cur, _ = self._read_current_position_um()

                    # MOVE absolute positions (µm)
                    u_abs = float(dpg.get_value("mcs_ch0_ABS"))
                    v_abs = float(dpg.get_value("mcs_ch1_ABS"))

                    # Opposite offsets (current stage - MOVE abs)
                    dU = u_cur - u_abs
                    dV = v_cur - v_abs

                    # Store as the NEGATIVE (so same convention as center-from-label)
                    self._center_from_label_dU_um = -dU
                    self._center_from_label_dV_um = -dV

                    print(
                        f"[coup] label from center set: stored reverse offsets "
                        f"dU={-dU:.3f} µm, dV={-dV:.3f} µm  (current − MOVE abs)."
                    )
                    _coup_save_state()
                    return True
                except Exception as e:
                    print(f"[coup] label from center set: failed to read positions: {e}")
                    return False

            if len(tokens) >= 3 and tokens[1].lower() == "from" and tokens[2].lower() == "center":
                # Use stored offsets (label → center), but move opposite (center → label)
                dU = float(getattr(self, "_center_from_label_dU_um", 0.0))
                dV = float(getattr(self, "_center_from_label_dV_um", 0.0))
                if dU == 0.0 and dV == 0.0:
                    print("[coup] label from center: no stored offsets. Use 'coup center from label dU,dV' first.")
                    return False

                try:
                    u_cur, v_cur, _ = self._read_current_position_um()
                except Exception as e:
                    print(f"[coup] label from center: cannot read current position: {e}")
                    return False

                # Inverse move: center → label
                dU_label = -dU
                dV_label = -dV
                u_label = u_cur + dU_label
                v_label = v_cur + dV_label

                try:
                    if abs(dU_label) > 1e-6:
                        self._move_delta(0, dU_label)
                    if abs(dV_label) > 1e-6:
                        self._move_delta(1, dV_label)
                except Exception as e:
                    print(f"[coup] label from center: move failed: {e}")
                    return False

                print(
                    f"[coup] label from center: moved by (dU={dU_label:.3f}, dV={dV_label:.3f}) µm "
                    f"to label at (U={u_label:.3f}, V={v_label:.3f}) µm."
                )
                return True

            # Unknown "coup label ..." usage
            print("Usage: coup label from center")
            return False

        # --- coup center: set reference center or move to nearest coupon center ---
        if sub == "center":
            # --- center from label [dU,dV] ---
            # coup center from label -100,95   -> store offsets (no move)
            # coup center from label          -> move by stored offsets to center
            # --- NEW: "coup center from label set" ---
            if len(tokens) == 4 and tokens[3].lower() == "set":
                try:
                    # Current stage position (µm)
                    u_cur, v_cur, _ = self._read_current_position_um()

                    # MOVE absolute positions (µm) from DPG GUI
                    u_abs = float(dpg.get_value("mcs_ch0_ABS"))
                    v_abs = float(dpg.get_value("mcs_ch1_ABS"))

                    # Compute offsets (MOVE abs - current stage)
                    dU = round(u_cur- u_abs,3)
                    dV = round(v_cur - v_abs,3)

                    # Store in attributes
                    self._center_from_label_dU_um = dU
                    self._center_from_label_dV_um = dV

                    print(
                        f"[coup] center from label set: stored dU={dU:.3f} µm, "
                        f"dV={dV:.3f} µm  (MOVE abs − current stage)."
                    )
                    _coup_save_state()
                    return True
                except Exception as e:
                    print(f"[coup] center from label set: failed to read positions: {e}")
                    return False
            if len(tokens) >= 3 and tokens[1].lower() == "from" and tokens[2].lower() == "label":
                # SET MODE: explicit offsets
                if len(tokens) >= 4:
                    # parse everything after "center from label" as "dU dV" or "dU,dV"
                    offs_str = " ".join(tokens[3:]).replace(",", " ").split()
                    if len(offs_str) != 2:
                        print("[coup] center from label: expected two numbers, e.g. 'coup center from label -100,95'")
                        return False
                    try:
                        dU = float(offs_str[0])
                        dV = float(offs_str[1])
                    except Exception:
                        print("[coup] center from label: invalid numbers. Use e.g. -100,95")
                        return False

                    self._center_from_label_dU_um = dU
                    self._center_from_label_dV_um = dV
                    print(f"[coup] center from label: stored offsets dU={dU:.3f} µm, dV={dV:.3f} µm.")
                    _coup_save_state()
                    return True

                # MOVE MODE: no offsets given, use stored values
                dU = float(getattr(self, "_center_from_label_dU_um", 0.0))
                dV = float(getattr(self, "_center_from_label_dV_um", 0.0))
                if dU == 0.0 and dV == 0.0:
                    print("[coup] center from label: no stored offsets. Use 'coup center from label dU,dV' first.")
                    return False

                try:
                    u_cur, v_cur, _ = self._read_current_position_um()
                except Exception as e:
                    print(f"[coup] center from label: cannot read current position: {e}")
                    return False

                u_center = u_cur + dU
                v_center = v_cur + dV

                # Move WITHOUT MAX_JUMP limitation (your example uses -100,95)
                try:
                    if abs(dU) > 1e-6:
                        self._move_delta(0, dU)
                    if abs(dV) > 1e-6:
                        self._move_delta(1, dV)
                except Exception as e:
                    print(f"[coup] center from label: move failed: {e}")
                    return False

                # Also update the coupon center reference
                try:
                    self._set_coupon_center_uv(u_center, v_center)
                except Exception as e:
                    print(f"[coup] center from label: moved, but failed to store new center: {e}")
                    return False

                print(
                    f"[coup] center from label: moved by (dU={dU:.3f}, dV={dV:.3f}) µm "
                    f"to center at (U={u_center:.3f}, V={v_center:.3f}) µm."
                )
                return True

            if not hasattr(self, "_coupon_angle_deg"):
                self._coupon_angle_deg = CHIP_ANGLE  # skew so right-neighbor ~ (95.9, 31.48) from (16,28)

            # Parse optional args: "center set" | "center 16,28" | "center 16 28"
            u_set = v_set = None
            if len(tokens) >= 2:
                if tokens[1].strip().lower() == "set":
                    try:
                        u_cur, v_cur, _ = self._read_current_position_um()
                        self._set_coupon_center_uv(u_cur, v_cur)
                        print(f"[coup] center: reference set to current position (U={u_cur:.3f}, V={v_cur:.3f}) µm.")
                        _coup_save_state()
                        return True
                    except Exception as e:
                        print(f"[coup] center set: {e}")
                        return False
                # otherwise try explicit numeric U,V
                rest = " ".join(tokens[1:]).replace(",", " ").split()
                if len(rest) == 2:
                    try:
                        u_set = float(rest[0]);
                        v_set = float(rest[1])
                    except ValueError:
                        print("[coup] center: invalid numbers. Use: coup center <U>, <V>")
                        return False
                elif len(rest) > 0:
                    print("[coup] center: provide both U and V, 'set', or no args. Examples: "
                          "coup center 16, 28 | coup center set | coup center")
                    return False

            # Setter mode
            if u_set is not None and v_set is not None:
                self._set_coupon_center_uv(u_set, v_set)
                return True

            # Move mode: snap to nearest coupon center around the reference, then move there (relative)
            try:
                u_ref, v_ref = self._get_coupon_center_uv()
                u_cur, v_cur, z_cur = self._read_current_position_um()
            except Exception as e:
                print(f"[coup] center: {e}")
                return False

            # Build neighbor grid using rotation
            theta = math.radians(float(self._coupon_angle_deg))
            cos_t, sin_t = math.cos(theta), math.sin(theta)

            # One-coupon vectors in lab (U-right, V-up with rotation)
            dUx, dUy = self._coupx_move_um * cos_t, self._coupx_move_um * sin_t
            dVx, dVy = -self._coupy_move_um * sin_t, self._coupy_move_um * cos_t

            # One-array vectors (3.75 U coupons, 5 V coupons)
            aUx, aUy = 3.75 * dUx, 3.75 * dUy
            aVx, aVy = 5 * dVx, 5 * dVy

            # Search ranges: arrays a,b ∈ [-2..2]; coupons i,j ∈ [-2..2]
            best = None
            for a in range(-4, 4):
                for b in range(-4, 4):
                    base_x = u_ref + a * aUx + b * aVx
                    base_y = v_ref + a * aUy + b * aVy
                    for i in range(-2, 3):
                        for j in range(-2, 3):
                            cx = base_x + i * dUx + j * dVx
                            cy = base_y + i * dUy + j * dVy
                            dist2 = (cx - u_cur) ** 2 + (cy - v_cur) ** 2
                            if best is None or dist2 < best[0]:
                                best = (dist2, cx, cy, a, b, i, j)

            _, cx, cy, a_sel, b_sel, i_sel, j_sel = best
            print(f"[coup] center: nearest at arrays(U={a_sel},V={b_sel}), coupons(U={i_sel},V={j_sel}) "
                  f"→ target=({cx:.3f}, {cy:.3f}) µm")

            # Relative move via your _move_delta in µm
            du = cx - u_cur
            dv = cy - v_cur
            print(f"du = {du}, dv = {dv}")

            MAX_JUMP = 60.0
            if abs(du) > MAX_JUMP or abs(dv) > MAX_JUMP:
                print(f"[coup] center: exceeds {MAX_JUMP} µm per-axis limit (du={du:.3f}, dv={dv:.3f}).")
                return False

            try:
                if abs(du) > 1e-6:
                    self._move_delta(0, du)
                if abs(dv) > 1e-6:
                    self._move_delta(1, dv)
            except Exception as e:
                print(f"[coup] center: move failed: {e}")
                return False

            print(f"[coup] center: moved from (U={u_cur:.3f}, V={v_cur:.3f}) to (U={cx:.3f}, V={cy:.3f}).")
            return True

        # --- array-shift helpers (accept factor OR '<µm> set') ---
        if sub in ("shiftx", "shifty"):
            is_x = (sub == "shiftx")

            # µm per coupon from __init__
            per_coupon_um = float(self._coupx_move_um if is_x else self._coupy_move_um)

            # ----- SET MODE -----
            # Supports:
            #   coup shiftx 3 set
            #   coup shiftx 310um set
            #   coup shifty -2 set
            #   coup shifty 140um set
            if len(tokens) >= 3 and tokens[-1].lower() == "set":
                # everything between 'shiftx' and 'set' is the value (usually one token)
                val_str = " ".join(tokens[1:-1]).strip()
                raw = val_str.lower()

                # A) contains units -> interpret as microns
                if "um" in raw or "µm" in raw:
                    raw_num = raw.replace("um", "").replace("µm", "").strip()
                    try:
                        microns = float(raw_num)
                    except Exception:
                        print(f"[coup] {sub} set: invalid µm value '{val_str}'")
                        return False

                    factor = microns / per_coupon_um
                    print(
                        f"[coup] {sub} set: {microns:.3f} µm / {per_coupon_um:.3f} µm-per-coupon "
                        f"→ factor={factor:.6f} coupons"
                    )

                else:
                    # B) plain factor, no units
                    try:
                        factor = float(val_str)
                    except Exception:
                        print(f"[coup] {sub} set: invalid factor '{val_str}'")
                        return False

                    microns = factor * per_coupon_um
                    print(
                        f"[coup] {sub} set: factor={factor:.6f} coupons "
                        f"→ {microns:.3f} µm (per_coupon={per_coupon_um:.3f} µm)"
                    )

                # store factor
                if is_x:
                    self._coup_shift_x_factor = factor
                else:
                    self._coup_shift_y_factor = factor

                _coup_save_state()
                return True

            # ----- MOVE MODE -----
            # coup shiftx          -> factor = 1.0 (use base factor as-is)
            # coup shiftx 2.5      -> factor = 2.5 * base_factor
            if len(tokens) >= 2:
                try:
                    factor = float(tokens[1])
                except Exception:
                    print(f"[coup] {sub}: invalid factor '{tokens[1]}'.")
                    return False
            else:
                factor = 1.0

            base_factor = float(
                self._coup_shift_x_factor if is_x else self._coup_shift_y_factor
            )

            coupons_to_move = base_factor * factor
            axis = "u" if is_x else "v"

            ok = self._coupon_move(axis=axis, n=coupons_to_move)

            print(
                f"[coup] {sub}: factor={factor:.3f}, base={base_factor:.3f} "
                f"→ move {coupons_to_move:+.3f} coupons on {axis.upper()} "
                f"({'done' if ok else 'failed'})"
            )
            return ok

        # --- shiftx? and shifty? : print current settings ---
        if sub in ("shiftx?", "shifty?"):
            is_x = (sub == "shiftx?")
            axis_name = "X/U" if is_x else "Y/V"

            per_coupon_um = self._coupx_move_um if is_x else self._coupy_move_um
            factor = self._coup_shift_x_factor if is_x else self._coup_shift_y_factor

            print(
                f"[coup] {sub}\n"
                f"  axis: {axis_name}\n"
                f"  µm per coupon: {per_coupon_um:.6f} µm\n"
                f"  stored factor: {factor:.6f} coupons\n"
                f"  → movement per 'coup shiftx' call: {factor * per_coupon_um:.6f} µm"
                if is_x else
                f"[coup] {sub}\n"
                f"  axis: {axis_name}\n"
                f"  µm per coupon: {per_coupon_um:.6f} µm\n"
                f"  stored factor: {factor:.6f} coupons\n"
                f"  → movement per 'coup shifty' call: {factor * per_coupon_um:.6f} µm"
            )
            return True

        # --- corner/bottom-left + inverted-corner aliases ---
        def _label_to_rc(label: str):
            """
            Map label -> (row, col, letter) on a 4x3 grid:
              Row1: NORM1L  1L  2L
              Row2: NORM2L  3L  4L
              Row3: NORM3L  5L  6L
              Row4: NORM4L  7L  8L

            Supported labels:
              NORM1L, NORM2L, ..., NORM4L
              NORM1, NORM2, ..., NORM4    (letter defaults to 'L')
              1L..8L
              1..8                        (letter defaults to 'L')
            """
            s = label.strip().upper()

            # NORM row: NORM1L / NORM1
            m = re.fullmatch(r"NORM([1-4])([A-Z])?", s)
            if m:
                row = int(m.group(1))
                letter = m.group(2) or "L"
                return row, 1, letter  # NORM column is col=1

            # Numeric coupon: 1L..8L or bare 1..8 (default letter L)
            m = re.fullmatch(r"([1-8])([A-Z])?", s)
            if m:
                num = int(m.group(1))
                letter = m.group(2) or "L"
                table = {
                    1: (1, 2), 2: (1, 3),
                    3: (2, 2), 4: (2, 3),
                    5: (3, 2), 6: (3, 3),
                    7: (4, 2), 8: (4, 3),
                }
                r, c = table[num]
                return r, c, letter

            raise ValueError(f"Unrecognized coupon label '{label}'. Use like 'NORM3L', 'NORM1', '5L' or '5'.")
        def _move_to_corner_from_label(label: str, inverted: bool = False) -> bool:
            r, c, letter = _label_to_rc(label)

            # Always move to bottom-left NORM4L (row 4, col 1),
            # even when inverted. For INV we just reverse the direction.
            target_r = 4
            target_c = 1

            # Base deltas from current (r,c) to NORM4L
            base_dU = target_c - c  # columns -> U axis
            base_dV = target_r - r  # rows    -> V axis

            if inverted:
                dU = -base_dU
                dV = -base_dV
            else:
                dU = base_dU
                dV = base_dV

            tag = "INV" if inverted else "STD"
            print(
                f"[coup] corner({tag}): from {label.upper()} (r{r},c{c}) → NORM4L "
                f"(ΔU={dU}, ΔV={dV})"
            )

            ok_u = True if dU == 0 else self._coupon_move(axis="u", n=dU)
            ok_v = True if dV == 0 else self._coupon_move(axis="v", n=dV)
            return bool(ok_u and ok_v)

        bl_aliases = {"bottom left", "bot left", "bottom-left", "bottomleft", "corner"}
        inv_aliases = {"inv", "neg", "-", "flipud"}  # 180° rotation helpers
        first_two = " ".join([t.lower() for t in tokens[:2]]) if len(tokens) >= 2 else sub

        # Detect 'corner inv/neg/-/flipud' specifically
        is_corner = (sub in bl_aliases) or (first_two in bl_aliases)
        if is_corner:
            inverted = False
            label_token_start = 1
            if sub == "corner" and len(tokens) >= 2 and tokens[1].lower() in inv_aliases:
                inverted = True
                label_token_start = 2  # label comes after the inv keyword

            # 1) Try explicit label after "corner" / "bottom left" / etc.
            provided = None
            for t in tokens[label_token_start:]:
                ts = str(t).strip()
                if ts:
                    provided = ts
                    break

            # 2) If none given, fall back to stored coup sequence label (e.g. NORM4A)
            stored = getattr(self, "_coup_seq_label", None)

            try:
                if provided:
                    label = provided
                    print(f"[coup] corner: using explicit label '{label}'.")
                elif stored:
                    label = stored
                    print(f"[coup] corner: using stored coup label '{label}'.")
                else:
                    # 3) Last resort: interactive prompt
                    label = input("Enter current coupon label (e.g., NORM3L or 5L): ").strip()
                    if not label:
                        print("[coup] no label provided.")
                        return False

                moved = _move_to_corner_from_label(label, inverted=inverted)
                print(
                    f"[coup] corner move {'(inverted) ' if inverted else ''}done."
                    if moved else
                    f"[coup] corner move {'(inverted) ' if inverted else ''}failed."
                )
                return moved
            except Exception as e:
                print(f"[coup] corner: {e}")
                return False

        # --- coup <name> / coup next: cycle through coupons (default or custom) ---
        #
        # Default sequence (physical slots):
        #   COUP_SEQ = [
        #       "NORM4", "7", "8",
        #       "NORM3", "5", "6",
        #       "NORM2", "3", "4",
        #       "NORM1", "1", "2",
        #   ]
        #
        # New features:
        #   - coup next <file>   -> load custom sequence and optional dx,dy from file
        #   - coup next reset    -> forget custom sequence, go back to built-in one
        #
        #   File format (JSON), example:
        #   {
        #     "sequence": ["MZI", "Dil5", "Foo", "Bar", "Baz", "Q1", "Q2", "Q3", "Q4", "R1", "R2", "R3"],
        #     "moves": {
        #       "MZI":  { "dx":  1, "dy":  0 },
        #       "Dil5": { "dx":  1, "dy":  0 },
        #       "Foo":  { "dx": -2, "dy": -1 },
        #       ...
        #     }
        #   }
        #
        # IMPORTANT:
        #   - The LETTER (A/B/L/…) is taken from your current label and NEVER changed.
        #   - The config only changes:
        #       * the order of base names (sequence)
        #       * the dx,dy used for each CURRENT base name.
        if sub == "next":
            # --- CONFIG MODE: coup next <file> / coup next reset ---
            if len(tokens) >= 2:
                opt = tokens[1].strip().strip('"').strip("'")
                opt_l = opt.lower()

                # Reset to built-in behavior
                if opt_l in ("reset", "default", "clear"):
                    if hasattr(self, "_coup_next_seq"):
                        delattr(self, "_coup_next_seq")
                    if hasattr(self, "_coup_next_moves"):
                        delattr(self, "_coup_next_moves")
                    print("[coup] next: custom sequence cleared; using built-in COUP_SEQ + slot_dx/slot_dy.")
                    _coup_save_state()
                    return True

                # Treat argument as config file
                cfg_name = opt

                # Default extension: .json
                import os
                if not os.path.splitext(cfg_name)[1]:
                    cfg_name = cfg_name + ".json"

                # Resolve relative to the SAME folder as coup_state.json
                try:
                    state_path = _get_coup_state_path()
                    base_dir = os.path.dirname(state_path)
                except Exception:
                    # fallback if anything weird happens
                    try:
                        base_dir = DEFAULT_COUP_DIR
                    except NameError:
                        base_dir = r"c:\WC\HotSystem\Utils\macro"

                if not os.path.isabs(cfg_name) and not os.path.dirname(cfg_name):
                    cfg_path = os.path.join(base_dir, cfg_name)
                else:
                    cfg_path = cfg_name

                if not os.path.isfile(cfg_path):
                    print(f"[coup] next: custom config file not found: '{cfg_path}'.")
                    return False

                # Expected JSON:
                # {
                #   "sequence": ["BASE1", "BASE2", ...],
                #   "moves": {
                #       "BASE1": {"dx": ..., "dy": ...},
                #       ...
                #   }
                # }
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                except Exception as e:
                    print(f"[coup] next: failed to read config '{cfg_path}': {e}")
                    return False

                seq = cfg.get("sequence", None)
                if not isinstance(seq, list) or not seq:
                    print("[coup] next: config must contain non-empty 'sequence' array.")
                    return False

                clean_seq = []
                for item in seq:
                    s = str(item).strip()
                    if not s:
                        continue
                    clean_seq.append(s)
                if not clean_seq:
                    print("[coup] next: no valid names in 'sequence'.")
                    return False

                moves_cfg = cfg.get("moves", {})
                clean_moves = {}
                if isinstance(moves_cfg, dict):
                    for base, val in moves_cfg.items():
                        try:
                            dx = float(val.get("dx", 0.0))
                            dy = float(val.get("dy", 0.0))
                            clean_moves[str(base)] = {"dx": dx, "dy": dy}
                        except Exception:
                            print(f"[coup] next: ignoring invalid moves for '{base}'.")
                            continue

                self._coup_next_seq = clean_seq
                self._coup_next_moves = clean_moves

                print(
                    f"[coup] next: loaded custom sequence ({len(clean_seq)} step(s)) "
                    f"from '{cfg_path}'. "
                    f"Custom moves for {len(clean_moves)} base name(s)."
                )
                _coup_save_state()
                return True

            # --- STEP MODE: coup next ---
            # 1) Determine current logical label (base + letter)
            cur_raw = getattr(self, "_coup_seq_label", None)
            if not cur_raw:
                print("[coup] next: no current label set. Use 'coup NORM4A' or 'coup <name>' first.")
                return False

            # Try to interpret as coupon label first (NORM4A, 7L, etc.)
            base = None
            letter = None
            try:
                canon = _canon_coupon_name(cur_raw)   # → NORM4A
                # base is the part without trailing letter if any
                if canon[-1].isalpha():
                    base = canon[:-1]
                    letter = canon[-1]      # keep existing letter
                else:
                    base = canon
                    letter = None
            except Exception:
                # If it is NOT a standard coupon label, treat the whole thing as the base.
                s = str(cur_raw).strip()
                if not s:
                    print(f"[coup] next: invalid current label '{cur_raw}'.")
                    return False
                base = s
                # No explicit letter → none; we will not add/change letters.

            # 2) Decide which sequence to use
            seq = getattr(self, "_coup_next_seq", None)
            if not isinstance(seq, list) or not seq:
                # Fall back to original COUP_SEQ
                seq = COUP_SEQ

            # Find current index in sequence (case-insensitive)
            cur_idx = None
            base_up = str(base).upper()
            for i, name in enumerate(seq):
                if str(name).upper() == base_up:
                    cur_idx = i
                    break
            if cur_idx is None:
                print(f"[coup] next: current base '{base}' not found in active sequence.")
                return False

            next_idx = (cur_idx + 1) % len(seq)
            next_base = seq[next_idx]

            # 3) Determine dx,dy for this step
            dx = dy = 0.0
            moves = getattr(self, "_coup_next_moves", None)

            if isinstance(moves, dict):
                # Prefer custom moves if present
                entry = moves.get(base) or moves.get(base_up) or moves.get(str(base))
                if isinstance(entry, dict):
                    try:
                        dx = float(entry.get("dx", 0.0))
                        dy = float(entry.get("dy", 0.0))
                    except Exception:
                        print(f"[coup] next: invalid custom dx/dy for '{base}', falling back to built-in.")
                        entry = None
                if entry is None:
                    # fall back to built-in if we didn't find a valid entry
                    moves = None

            if moves is None:
                # Built-in movement using original slot_dx/slot_dy tables
                # Map base -> original "slot" key (NORM4, 7, etc.) if possible
                try:
                    slot = _seq_key(base)   #  NORM4A/B → NORM4 ; 7A → 7
                except Exception:
                    slot = base

                slot_dx = {
                    "NORM4": +1,
                    "7":     +1,
                    "8":     -2,
                    "NORM3": +1,
                    "5":     +1,
                    "6":     -2,
                    "NORM2": +1,
                    "3":     +1,
                    "4":     -2,
                    "NORM1": +1,
                    "1":     +1,
                    "2":     -2,
                }
                slot_dy = {
                    "NORM4":  0,
                    "7":      0,
                    "8":     -1,
                    "NORM3":  0,
                    "5":      0,
                    "6":     -1,
                    "NORM2":  0,
                    "3":      0,
                    "4":     -1,
                    "NORM1":  0,
                    "1":      0,
                    "2":     +3,
                }
                dx = float(slot_dx.get(slot, 0.0))
                dy = float(slot_dy.get(slot, 0.0))

            # 4) Build the next label:
            #    - NEVER change letter; just reuse it if it exists.
            if letter is not None:
                next_label = f"{next_base}{letter}"
            else:
                next_label = str(next_base)

            # 5) Actually move using your coupx/coupy helpers
            try:
                if dx != 0:
                    self.handle_coupx(str(dx))
                if dy != 0:
                    self.handle_coupy(str(dy))
            except Exception as e:
                print(f"[coup] next: move failed via coupx/coupy: {e}")
                return False

            # 6) Update stored logical label + note
            self._coup_seq_label = next_label

            try:
                self.handle_acquire_spectrum(f"note {next_label}")
            except Exception as e:
                print(f"[coup] warning: handle_acquire_spectrum failed for '{next_label}': {e}")

            print(
                f"[coup] next: {cur_raw} (base '{base}') → {next_label} (base '{next_base}') "
                f"via coupx({dx}) coupy({dy})."
            )
            return True

        # Single-token 'coup <name>' → set start label, acquire spectrum note, then advance to next
        if len(tokens) == 1:
            raw = tokens[0]
            try:
                canon = _canon_coupon_name(raw)  # e.g. "norm4a" -> "NORM4A"
                key = _seq_key(canon)  # e.g. "NORM4A" -> "NORM4"
            except Exception as e:
                canon = None
                key = None

            if canon and key in COUP_SEQ_SET:
                # 1) store sequence label
                self._coup_seq_label = canon
                print(f"[coup] sequence start label set to '{canon}' (slot '{key}').")

                # 2) note
                try:
                    # use canonical name in the note; you can change to `raw` if you prefer original text
                    self.handle_acquire_spectrum(f"note {canon}")
                except Exception as e:
                    print(f"[coup] warning: handle_acquire_spectrum failed for '{canon}': {e}")

                return True

        # --- steps-file mode detection (supports bare numbers like `coup 5` -> "5.txt") ---
        # tokens[0] is the "filename-ish" part (e.g. "sb" in: coup sb pause)
        cand_path = tokens[0].strip('"').strip("'")

        # Optional "pause" modifier anywhere after the filename:
        #   coup sb pause
        #   coup sb.txt pause
        pause_mode = any(t.lower() == "pause" for t in tokens[1:])

        allowed_exts = (".txt", ".cmd", ".lst", ".seq",".py")

        # If no recognized extension was provided, default to .txt
        if not any(cand_path.lower().endswith(ext) for ext in allowed_exts):
            cand_path += ".py"

        # Resolve default dir if user passed only a filename (no folder)
        def _resolve_macro_path(pth: str) -> str:
            if os.path.isabs(pth) or os.path.dirname(pth):
                return pth
            try:
                base_dir = DEFAULT_COUP_DIR
            except NameError:
                base_dir = r"c:\WC\HotSystem\Utils\macro"
            return os.path.join(base_dir, pth)
        if any(cand_path.lower().endswith(ext) for ext in allowed_exts):
            resolved = _resolve_macro_path(cand_path)
            if not os.path.isfile(resolved):
                # Fallback to original path in case caller used relative CWD
                if os.path.isfile(cand_path):
                    resolved = cand_path
                else:
                    print(f"[coup] steps file not found: '{cand_path}'. Tried: '{resolved}'.")
                    return False

            # Clear cancel flags (even when nested — nested runs can still be canceled)
            try:
                self._coup_abort_evt.clear()
            except Exception:
                pass
            try:
                self._coup_cancel.clear()
            except Exception:
                pass

            # Parse steps
            try:
                steps = self._parse_coup_steps_file(resolved)
                if not steps:
                    print(f"[coup] no runnable steps found in '{resolved}'.")
                    return False
            except Exception as e:
                print(f"[coup] failed to read steps file '{resolved}': {e}")
                return False

            # --- NEW: remember which macro is running + reset line counter ---
            self._current_coup_macro = resolved
            self._coup_current_line_no = None

            # Decide which loop implementation to use
            def _run_steps():
                if pause_mode:
                    self._coup_loop_from_steps_with_pause(steps)
                else:
                    self._coup_loop_from_steps(steps=steps, wait_for_spc=True)

            # If we're already inside a coup run (nested), execute INLINE
            if nested:
                print(
                    f"[coup] running nested steps inline from '{resolved}' "
                    f"(pause={'ON' if pause_mode else 'OFF'})."
                )
                try:
                    _run_steps()
                    return True
                except Exception as e:
                    print(f"[coup] nested steps failed: {e}")
                    return False

            # Top-level launch
            def _run():
                try:
                    _run_steps()
                except Exception as e:
                    print(f"[coup] steps thread failed: {e}")

            self._coup_thread = threading.Thread(target=_run, daemon=True)
            self._coup_thread.start()
            print(
                f"[coup] steps from '{resolved}' started "
                f"(pause={'ON' if pause_mode else 'OFF'}; use 'coup stop' to cancel)."
            )
            return True
    def _parse_coup_steps_file(self, path):
        """
        Parse a coup steps file.

        - Supports plain lines: 'spc 3', 'movez 0.3', 'coup next', ...
        - Supports Python-like for-loops:

            for i in range(12):
                spc 3
                movez 0.3
                coup next

          which are expanded into a flat list of commands.
        """
        with open(path, "r", encoding="utf-8") as f:
            raw_lines = f.readlines()

        # strip empty / comment-only lines
        lines = []
        for ln in raw_lines:
            if not ln.strip():
                continue
            if ln.lstrip().startswith("#"):
                continue
            lines.append(ln.rstrip("\n"))

        # Detect any "for ...:" at all
        has_for = any(l.lstrip().startswith("for ") and l.rstrip().endswith(":") for l in lines)
        if has_for:
            cmd_lines = self._expand_for_loops(lines, path)
        else:
            cmd_lines = lines

        # final split on ';' like before
        steps = []
        for line in cmd_lines:
            parts = [p.strip() for p in line.split(";") if p.strip()]
            steps.extend(parts)

        return steps
    def _expand_for_loops(self, lines, filename):
        """
        Expand Python-like for-loops into a flat list of coup commands.

        Supported syntax (only):

            for i in range(12):
                spc 3
                movez 0.3
                coup next

        - Only 'for ... in <expr>:' where <expr> is something like range(12).
        - We evaluate <expr> with globals={'range': range} to get the repeat count.
        - We ignore the loop variable name (no substitution into commands yet).
        """

        # Normalize indentation and keep (indent, text) pairs
        parsed = []
        for ln in lines:
            expanded = ln.replace("\t", "    ")
            indent = len(expanded) - len(expanded.lstrip(" "))
            text = expanded.lstrip(" ")
            parsed.append((indent, text))

        n = len(parsed)

        def process_block(i, cur_indent):
            """
            Recursively process lines starting at index i with baseline indent = cur_indent.
            Returns (commands_list, next_index).
            """
            out = []
            while i < n:
                indent, text = parsed[i]

                # block ends when indentation drops
                if indent < cur_indent:
                    break

                if indent > cur_indent:
                    # This should only happen when called from a for-body with higher indent.
                    # If we ever see indent > cur_indent at top-level, it's malformed.
                    raise SyntaxError(
                        f"Unexpected extra indentation in {filename} at line {i + 1}: '{text}'"
                    )

                # --- handle "for ... in ...:" ---
                if text.startswith("for ") and text.endswith(":"):
                    header = text[4:-1].strip()  # between 'for' and ':'
                    if " in " not in header:
                        raise SyntaxError(
                            f"Bad for-loop header in {filename} at line {i + 1}: '{text}'"
                        )
                    # we ignore the variable part, just use the iterable expression
                    _, iter_expr = header.split(" in ", 1)
                    iter_expr = iter_expr.strip()

                    # body must start at next line with larger indent
                    body_start = i + 1
                    if body_start >= n:
                        raise SyntaxError(
                            f"For-loop without body in {filename} at line {i + 1}."
                        )

                    body_indent, _ = parsed[body_start]
                    if body_indent <= indent:
                        raise SyntaxError(
                            f"For-loop body must be indented in {filename} at line {i + 1}."
                        )

                    # Evaluate iterable (e.g. range(12)) with restricted globals
                    try:
                        iterable = eval(iter_expr, {"range": range}, {})
                    except Exception as e:
                        raise SyntaxError(
                            f"Error evaluating iterable '{iter_expr}' in {filename} at line {i + 1}: {e}"
                        )

                    # Parse the body once, then replicate it len(iterable) times
                    body_cmds, new_i = process_block(body_start, body_indent)

                    # We only care about repetition count; we ignore the loop variable.
                    for _ in iterable:
                        out.extend(body_cmds)

                    # continue after the loop body
                    i = new_i
                    continue

                # --- normal command line ---
                out.append(text)
                i += 1

            return out, i

        try:
            commands, _ = process_block(0, 0)
            return commands
        except Exception as e:
            print(f"[coup] ERROR parsing python-like for loops in {filename}: {e}")
            raise
    def _expand_python_loops(self, lines, filename):
        """
        Convert Python-like indented loop blocks into flat coup commands.
        """

        import textwrap

        # Build a pseudo-python script
        py = "output = []\n"
        py += "def emit(x): output.append(x)\n"
        py += "def run():\n"

        # indent the body lines
        for l in lines:
            py += "    " + l + "\n"

        # Execute the script in a sandboxed environment
        env = {
            "output": [],
            "emit": lambda x: None,
            "range": range,
            "__file__": filename,
        }

        # Replace plain coup/spc/move commands with emit("command args")
        transformed = py.replace("spc ", "emit('spc ").replace("movez ", "emit('movez ") \
            .replace("coup ", "emit('coup ")

        # Close the string properly → emit('spc 3') style
        transformed = transformed.replace("\n", "')\n").replace("emit(')", "")

        try:
            exec(transformed, env, env)
            env["run"]()
            return env["output"]
        except Exception as e:
            print(f"[coup] ERROR parsing python syntax in {filename}: {e}")
            raise
    def _wait_spc_done_or_abort(self, poll_ms=100, hard_timeout_s=120):
        """
        Wait until SPC thread signals done OR a stop is requested OR timeout.
        Assumes your SPC sets self._spc_done_evt (Event) as in your code.
        """
        evt = getattr(self, "_spc_done_evt", None)
        if not isinstance(evt, threading.Event):
            # fallback: short sleep loop that can still be aborted
            t0 = time.time()
            while (time.time() - t0) < hard_timeout_s:
                if self._coup_abort_evt.is_set(): return False
                time.sleep(poll_ms / 1000.0)
            return False

        t0 = time.time()
        while (time.time() - t0) < hard_timeout_s:
            if self._coup_abort_evt.is_set(): return False
            if evt.wait(timeout=poll_ms / 1000.0):  # finished
                return True
        return False
    def _wait_scan_done_or_abort(self, poll_ms=500, hard_timeout_s=None):
        """
        Wait until a scan finishes (StartScan3D sets _scan_done_evt),
        or until 'coup stop' / abort is requested, or optional timeout.
        """
        time.sleep(25)
        return True
    def _wait_focus_done_or_abort(self, poll_ms=200, hard_timeout_s=None):
        """
        Wait until focus completes (handle_focus worker sets _focus_done_evt),
        or until coup stop/abort.
        """
        import time, threading

        evt = getattr(self, "_focus_done_evt", None)
        if not isinstance(evt, threading.Event):
            evt = threading.Event()
            self._focus_done_evt = evt
        evt.clear()  # ensure clean state

        t0 = time.time()
        while True:
            # Abort or cancel
            if getattr(self, "_coup_abort_evt", None) and self._coup_abort_evt.is_set():
                return False
            if getattr(self, "_coup_cancel", None) and self._coup_cancel.is_set():
                return False

            if evt.is_set():
                return True

            if hard_timeout_s and (time.time() - t0) > hard_timeout_s:
                print("[coup] wait focus: timed out.")
                return False

            time.sleep(poll_ms / 1000.0)
    def _run_one_cmd(self, cmd: str) -> bool:
        if self._coup_abort_evt.is_set():
            print(f"[coup] aborted before '{cmd}'")
            return False

        # --- record the currently running command ---
        try:
            self._current_coup_cmd = cmd.strip()
        except Exception:
            pass

        line = cmd.strip()
        toks = line.lower().split()

        # --- SPECIAL: 'await scan' or 'await focus' ---
        if len(toks) >= 2 and toks[0] == "await":
            if toks[1] == "scan":
                self._current_coup_cmd = "await scan (waiting...)"

                print("[coup] awaiting scan completion...")
                ok = self._wait_scan_done_or_abort()
                if not ok:
                    print("[coup] wait scan: aborted or timed out.")
                    return False
                print("[coup] scan finished; continuing coup steps.")
                return True

            if toks[1] == "focus":
                self._current_coup_cmd = "await focus (waiting...)"

                print("[coup] awaiting focus completion...")
                ok = self._wait_focus_done_or_abort()
                if not ok:
                    print("[coup] wait focus: aborted or timed out.")
                    return False
                print("[coup] focus finished; continuing coup steps.")
                return True


        try:
            run(cmd, record_history=False)
        except Exception as e:
            print(f"[coup] step failed '{cmd}': {e}")
            return False

        # if it was 'spc shift' we must wait until acquisition finishes (but remain cancellable)
        # --- NEW: if this was "spc note ...", signal immediate completion
        toks = cmd.strip().lower().split()
        if toks and toks[0] == "spc" and len(toks) >= 2 and toks[1] == "note":
            try:
                import threading
                evt = getattr(self, "_spc_done_evt", None)
                if not isinstance(evt, threading.Event):
                    self._spc_done_evt = threading.Event()
                    evt = self._spc_done_evt
                evt.set()
            except Exception:
                pass
            return True

        if toks and toks[0] == "spc" and "shift" in toks[1:]:
            print("[coup] waiting for 'spc shift' to finish… (use 'coup stop' to cancel)")
            ok = self._wait_spc_done_or_abort()
            if not ok:
                print("[coup] stop/timeout during 'spc shift' wait.")
                return False

        # Reset current command when done
        try:
            self._current_coup_cmd = None
        except Exception:
            pass

        return True
    def _coup_loop_from_steps_with_pause(self, steps):
        """
        Like _coup_loop_from_steps(wait_for_spc=True), but after every
        K real SPC acquisitions (not 'spc note ...') it runs a preview
        at 1000 ms exposure and then PAUSES until 'coup resume' / 'cr'
        or 'coup stop'.

        K is computed dynamically as:
            K = max(1, round(3 * self._coup_pause_factor))

        where self._coup_pause_factor is set by:
            coup resume [factor]
        """
        import re, time, threading as _th

        p = self.get_parent()
        target_gui = getattr(p, "proem_gui", None)
        dev = getattr(target_gui, "dev", None) if target_gui is not None else None

        # make sure pause event exists
        evt = getattr(self, "_coup_pause_evt", None)
        if not isinstance(evt, _th.Event):
            self._coup_pause_evt = _th.Event()
            evt = self._coup_pause_evt

        spc_count = 0

        self._coup_active_evt.set()
        try:
            for cmd in steps:
                if not self._run_one_cmd(cmd):
                    print("[coup] loop stopped.")
                    return

                line = cmd.strip().lower()

                # Same SPC wait logic as _coup_loop_from_steps
                if re.search(r"\b(spc|save)\b", line) and not re.search(r"\bspc\s+note\b", line):
                    print("[coup] waiting for 'spc' to finish…")
                    time.sleep(3.0)
                    ok = self._wait_spc_done_or_abort()
                    if not ok:
                        print("[coup] stop/timeout during 'spc' wait.")
                        return

                    # Count real SPCs (not 'spc note') for pause logic
                    if line.startswith("spc") and not line.startswith("spc note"):
                        spc_count += 1

                        # compute current pause threshold from factor
                        pause_factor = float(getattr(self, "_coup_pause_factor", 1.0))
                        pause_every = max(1, int(round(3 * pause_factor)))

                        if pause_every and (spc_count % pause_every == 0):
                            # --- Preview at 1000 ms ---
                            print(
                                f"[coup] pause: after {pause_every} SPCs "
                                "→ Preview at 1000 ms"
                            )
                            if dev is not None:
                                try:
                                    dev.set_value(CameraSettings.ShutterTimingExposureTime, 1000.0)
                                except Exception as e:
                                    print(f"[coup] pause: failed to set preview exposure: {e}")

                                try:
                                    exp = getattr(dev, "_exp", None)
                                    if exp is not None:
                                        try:
                                            while getattr(exp, "IsUpdating", False):
                                                time.sleep(0.05)
                                        except Exception:
                                            pass

                                        if getattr(exp, "IsReadyToRun", True):
                                            try:
                                                exp.Preview()
                                            except Exception as e:
                                                print(f"[coup] pause: Preview() failed: {e}")
                                except Exception as e:
                                    print(f"[coup] pause: error around preview: {e}")

                            # --- REAL PAUSE HERE ---
                            dpg.set_value("cmd_input", "cr 3")

                            try:
                                evt.clear()
                            except Exception:
                                pass

                            print(
                                "[coup] pause: waiting. Use 'coup resume [factor]' or 'cr [factor]' "
                                "to continue, or 'coup stop' to abort."
                            )
                            while True:
                                # abort / stop?
                                if self._coup_abort_evt.is_set() or self._coup_cancel.is_set():
                                    print("[coup] aborted during pause.")
                                    return
                                if evt.is_set():
                                    # user called 'coup resume' / 'cr'
                                    # (pause_factor may have changed; we'll recompute next time)
                                    break
                                time.sleep(0.1)

            # finished all steps
            self.handle_stop_scan("")
            print("[coup] loop complete.")
        finally:
            self._coup_active_evt.clear()
    def _coup_loop_from_steps(self, use_shift: bool = True, steps: str = "", wait_for_spc: bool = True):
        self._coup_active_evt.set()
        try:
            for idx, cmd in enumerate(steps, start=1):  # <<< NEW: track index as line number
                # expose current cmd + line for 'coup status'
                self._current_coup_cmd = cmd  # <<< NEW
                self._coup_current_line_no = idx  # <<< NEW

                if not self._run_one_cmd(cmd):
                    print("[coup] loop stopped.")
                    return
                time.sleep(2)
                line = cmd.strip().lower()
                # If the command is exactly "g2" (or "g2 " etc.), pause 10 s before next command
                if line == "g2" or line.startswith("g2 "):
                    print("[coup] g2 executed → pausing 60 s before next command...")
                    time.sleep(60)

                # --- don't wait on "spc note ..."
                if wait_for_spc and re.search(r"\b(spc|save)\b", line) and not re.search(r"\bspc\s+note\b", line):
                    print("[coup] waiting for 'spc' to finish…")
                    time.sleep(3)
                    ok = self._wait_spc_done_or_abort()
                    if not ok:
                        print("[coup] stop/timeout during 'spc' wait.")
                        return

            print("[coup] loop complete.")
        finally:
            self._coup_active_evt.clear()
    def _resolve_cgh_utils_path(self, override: str | None = None) -> Path | None:
        """Locate cgh_fullscreen.py inside a Utils folder (or use explicit override)."""
        if override:
            p = Path(override)
            return p if p.exists() else None

        here = Path(__file__).resolve().parent
        candidates = [
            here / "Utils" / "cgh_fullscreen.py",  # same folder -> Utils
            here.parent / "Utils" / "cgh_fullscreen.py",  # parent -> Utils
            Path.cwd() / "Utils" / "cgh_fullscreen.py",  # CWD -> Utils
        ]
        for p in candidates:
            if p.exists():
                return p
        return None
    def handle_cgh(self, *args):
        """
        Usage:
          cgh                    # run Utils/cgh_fullscreen.py detached
          cgh --kill             # stop the previously launched process
          cgh --path <file.py>   # run a specific script instead
          cgh -- <extra args>    # pass extra args to the script after '--'
        """
        args = list(args)

        # normalize subcommand (status/kill/play/p)
        sub = str(args[0]).lower() if args else ""
        is_status = sub in {"--status", "status"}
        is_kill = sub in {"--kill", "kill"}
        is_play = sub in {"p", "play"}
        is_stop  = sub in {"--stop", "stop"}


        if is_status:
            proc = getattr(self, "_cgh_proc", None)
            if proc and proc.poll() is None:
                print(f"[cgh] running (pid={proc.pid}) via handle.")
                self._refocus_cmd_input()
                return True

            # pidfile fallback (if you added the helpers earlier)
            try:
                pid = _read_pidfile()
                if pid and _proc_is_alive(pid):
                    print(f"[cgh] running (pid={pid}) via pidfile.")
                    self._refocus_cmd_input()
                    return True
            except Exception:
                pass

            print("[cgh] not running.")
            self._refocus_cmd_input()
            return True

        if is_kill:
            # robust kill for DETACHED GUI: try terminate -> then taskkill /T /F
            def _force_kill_tree(pid: int):
                try:
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
                    return True
                except Exception:
                    return False

            proc = getattr(self, "_cgh_proc", None)
            if proc and proc.poll() is None:
                pid = proc.pid
                try:
                    proc.terminate()
                except Exception:
                    pass

                # small grace
                for _ in range(15):
                    if proc.poll() is not None:
                        break
                    time.sleep(0.1)

                if proc.poll() is None:
                    _force_kill_tree(pid)

                if proc.poll() is None:
                    print("[cgh] force-terminate attempted; process may still be shutting down.")
                else:
                    print("[cgh] terminated fullscreen CGH process.")

                self._cgh_proc = None
                try: _clear_pidfile()
                except Exception: pass
                self._refocus_cmd_input()
                return True

            # pidfile fallback
            try:
                pid = _read_pidfile()
            except Exception:
                pid = None

            if pid:
                _ = _force_kill_tree(pid)
                # verify
                out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"], capture_output=True, text=True)
                if str(pid) not in out.stdout:
                    print(f"[cgh] terminated fullscreen CGH process by pid={pid}.")
                else:
                    print(f"[cgh] could not terminate pid={pid}.")
                try: _clear_pidfile()
                except Exception: pass
                self._refocus_cmd_input()
                return True

            print("[cgh] no running fullscreen CGH process.")
            self._refocus_cmd_input()
            return True

        if is_play:
            # 1) Is the app running already? (prefer window check; fallback to handle/pidfile)
            running = bool(_find_cgh_hwnd("SLM CGH"))
            proc = getattr(self, "_cgh_proc", None)
            if not running:
                if proc and proc.poll() is None:
                    running = True
                else:
                    try:
                        pid = _read_pidfile()
                        if pid and _proc_is_alive(pid):
                            running = True
                    except Exception:
                        pass

            # 2) If not running, launch it (same flags as your normal 'cgh' launch)
            if not running:
                script_path = self._resolve_cgh_utils_path(None)
                if not script_path:
                    print("[cgh] could not find Utils/cgh_fullscreen.py (use 'cgh --path <file.py>')")
                    self._refocus_cmd_input()
                    return False

                creationflags = 0
                startupinfo = None
                popen_kwargs = {}
                if os.name == "nt":
                    creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                else:
                    popen_kwargs["start_new_session"] = True

                cmd = [sys.executable, "-u", str(script_path)]
                try:
                    proc = subprocess.Popen(
                        cmd,
                        cwd=str(script_path.parent),
                        creationflags=creationflags,
                        startupinfo=startupinfo,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        text=True,
                        **popen_kwargs
                    )
                    self._cgh_proc = proc
                    try: _write_pidfile(proc.pid)
                    except Exception: pass
                    print(f"[cgh] launched: {cmd}  (pid={proc.pid})")
                except Exception as e:
                    print(f"[cgh] launch failed: {e}")
                    self._refocus_cmd_input()
                    return False

                # wait briefly for the window to appear
                _wait_for_cgh_window(timeout_s=3.0, window_title="SLM CGH")
                time.sleep(5)

            # 3) Send 'p' to start playback
            ok = _send_key_p_to_cgh_window("SLM CGH")
            if ok:
                print("[cgh] sent 'p' to SLM CGH window (play).")
            else:
                # last-chance: small extra wait then retry once
                if _wait_for_cgh_window(timeout_s=1.0, window_title="SLM CGH") and _send_key_p_to_cgh_window("SLM CGH"):
                    print("[cgh] sent 'p' after window appeared (play).")
                else:
                    print("[cgh] could not find 'SLM CGH' window to send 'p'. Is CGH running?")

            self._refocus_cmd_input()
            return True

        if is_stop:
            # Create the control flag so the CGH process stops playback and shows CORR_BMP
            try:
                flag = r"C:\WC\HotSystem\Utils\cgh_stop.flag"
                os.makedirs(os.path.dirname(flag), exist_ok=True)
                with open(flag, "w", encoding="utf-8") as f:
                    f.write("stop")
                print("[cgh] stop requested → STOP flag written. CGH will switch to CORR_BMP (zero-order).")
            except Exception as e:
                print(f"[cgh] failed to write STOP flag: {e}")

            # Optional: nudge the window to process messages (no quit)
            try:
                _poke_cgh_window("SLM CGH")
            except Exception:
                pass

            # Do NOT kill or quit the process here.
            self._refocus_cmd_input()
            return True

        # optional --path and extra args after --
        override = None
        extra = []
        if args[:1] == ["--path"] and len(args) >= 2:
            override = args[1]
            args = args[2:]
        if "--" in args:
            idx = args.index("--")
            extra = args[idx + 1:]
            args = args[:idx]

        script_path = self._resolve_cgh_utils_path(override)
        if not script_path:
            print("[cgh] could not find Utils/cgh_fullscreen.py (use 'cgh --path <file.py>')")
            self._refocus_cmd_input()
            return False

        # detached spawn
        creationflags = 0
        startupinfo = None
        popen_kwargs = {}

        if os.name == "nt":
            # New process group to allow CTRL_BREAK; hide window
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        else:
            # POSIX: new session so we can signal the group if needed
            popen_kwargs["start_new_session"] = True

        cmd = [sys.executable, "-u", str(script_path), *extra]
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(script_path.parent),
                creationflags=creationflags,
                startupinfo=startupinfo,
                stdout=subprocess.DEVNULL,  # don't pipe if you won't read
                stderr=subprocess.DEVNULL,
                **popen_kwargs
            )
            self._cgh_proc = proc
            _write_pidfile(proc.pid)
            print(f"[cgh] launched: {cmd}  (pid={proc.pid})")
            self._refocus_cmd_input()
            return True

        except Exception as e:
            print(f"[cgh] launch failed: {e}")
            self._refocus_cmd_input()
            return False
    def handle_negative(self, *args):
        """
        Repeat the last command with all numeric arguments sign-inverted.
        Example: 'movex 3;movey -5' -> 'movex -3;movey 5'
        """
        last = getattr(self, "_last_cmd", "") or getattr(self, "_last_seq", "")
        if not last.strip():
            print("No last command to invert.")
            return False

        inv = self._invert_numeric_args(last)
        try:
            run(inv, record_history=True)
            # make the inverted version the new "last" so '1' repeats what was just done
            self._last_cmd = inv
            print(f"[2] ran: {inv}")
            return True
        except Exception as e:
            print(f"[2] failed: {e}")
            return False
    def handle_wv(self, *args):
        """
            wv ?         -> print current wavelength (nm)
            wave ?       -> same as above
            wv bifi move [pos] -> move BIFI to optional [pos] and execute move
            wv bifi up             -> lower BIFI by 100; if |Δλ|>0.1 nm, lower another 100
            wv exp                 -> print current exposure (ms)
            wv exp +               -> increase exposure by 0.5 ms
        """
        # Normalize args like the rest of your handlers do
        arg = " ".join(a for a in args if isinstance(a, str)).strip()
        toks = arg.split()
        p = self.get_parent()

        import time as _time

        def _read_wavelength_nm_with_autoexp(max_adj: int = 5):
            """
            Try to read wavelength (nm). If status is 'over' or 'under', auto-tweak exposure:
              - 'over'  -> Expo.1 -= 1 ms; if still 'over' on the next read, also Expo.2 -= 1 ms
              - 'under' -> Expo.1 += 1 ms
            Wait 1 s after each tweak and retry. Up to max_adj total adjustments.
            Returns (lam_nm, status) where status is None on success or one of:
              'over','under','badsig','nosig','noval','nowlm','autoexp_exhausted','error:<msg>'
            """
            wwrap = getattr(p, "wlm_gui", None)
            if wwrap is None or getattr(wwrap, "_dev", None) is None:
                return None, "nowlm"

            w = wwrap._dev  # your HighFinesseWLM (ms API)
            dev = getattr(w, "_device", None)  # pylablib WLM (seconds API)

            # Track whether we already adjusted sensor 1 on the immediately previous loop
            last_adjusted_s1 = False

            def _get_status_or_value():
                if dev is not None:
                    with w.lock:
                        return dev.get_wavelength(error_on_invalid=False, wait=False)
                # fallback to wrapper (will raise on invalid; treat that as error)
                return w.get_wavelength()

            def _tweak_s1(delta_ms: float):
                """Use wrapper (ms API) for sensor 1."""
                cur = float(w.get_exposure() or 10.0)  # ms
                new = max(1.0, min(60000.0, cur + delta_ms))
                w.set_exposure(new)  # wrapper converts to seconds for driver
                print(f"[wv] Auto-adjust Expo.1: {cur:.1f} → {new:.1f} ms")

            def _tweak_s2_down_1ms():
                """Use driver (seconds API) for sensor 2 ('2+'); allow reaching 0 ms."""
                if dev is None:
                    return False
                try:
                    with w.lock:
                        # driver getters return seconds
                        try:
                            e2_s = dev.get_exposure(sensor=2)  # seconds
                        except Exception:
                            lst = dev.get_exposure(sensor="all")  # list of seconds
                            e2_s = float(lst[1]) if (lst and len(lst) > 1) else None
                        if e2_s is None:
                            return False
                        new_s = max(0.0, e2_s - 0.001)  # allow 0 ms (0.0 s)
                        dev.set_exposure(new_s, sensor=2)
                    print(f"[wv] Auto-adjust Expo.2+: {e2_s * 1e3:.1f} → {new_s * 1e3:.1f} ms")
                    return True
                except Exception as ee:
                    print(f"[wv] Expo.2+ adjust failed: {ee}")
                    return False

            for _ in range(max_adj + 1):
                try:
                    v = _get_status_or_value()
                except Exception as e:
                    return None, f"error:{e}"

                if isinstance(v, str):
                    if v == "over":
                        # First try: adjust sensor 1 down by 1 ms
                        if not last_adjusted_s1:
                            try:
                                _tweak_s1(-1.0)
                                last_adjusted_s1 = True
                            except Exception as ee:
                                print(f"[wv] Expo.1 adjust failed: {ee}")
                                return None, "over"
                            _time.sleep(1.0)
                            continue
                        # Second consecutive 'over': also tweak 2+ down by 1 ms
                        else:
                            _tweak_s2_down_1ms()
                            last_adjusted_s1 = False  # reset; next loop re-check status
                            _time.sleep(1.0)
                            continue

                    if v == "under":
                        try:
                            _tweak_s1(+1.0)
                            last_adjusted_s1 = False
                        except Exception as ee:
                            print(f"[wv] Expo.1 adjust failed: {ee}")
                            return None, "under"
                        _time.sleep(1.0)
                        continue

                    # other statuses: 'badsig','nosig','noval','nowlm'
                    return None, v

                # numeric wavelength (meters) → nm
                return float(v) * 1e9, None

            return None, "autoexp_exhausted"

        # ---- wavelength query ----
        if arg in ("", "?"):
            lam_nm, status = _read_wavelength_nm_with_autoexp()
            if status is None:
                print(f"Wavelength: {lam_nm:.3f} nm")
            elif status == "over":
                print("Status: overexposed (auto-adjusted)")
            elif status == "under":
                print("Status: underexposed (auto-adjusted)")
            else:
                print(f"Status: {status}")
            return

        # ---- exposure commands ----
        if len(toks) >= 1 and toks[0].lower() in ("exp", "exposure"):
            wlm = getattr(p, "wlm_gui", None)
            if wlm is None:
                print("[wv exp] WLM wrapper not available.")
                return

            w = getattr(wlm, "_dev", None)  # your HighFinesseWLM wrapper

            # --- direct-driver helpers (ms throughout) ---
            def _read_exposure_ms() -> float | None:
                try:
                    return None if w is None else float(w.get_exposure())
                except Exception as e:
                    print(f"[wv exp] Wrapper read error: {e}")
                    return None

            def _write_exposure_ms(new_ms: float) -> bool:
                new_ms = max(1.0, min(60000.0, float(new_ms)))  # clamp 1–60000 ms
                try:
                    w.set_exposure(new_ms)
                    return True
                except Exception as e:
                    print(f"[wv exp] Wrapper write error: {e}")
                    return False


            # Query: wv exp
            if len(toks) == 1:
                exp_ms = _read_exposure_ms()
                if exp_ms is None:
                    print("[wv exp] Unable to read exposure.")
                else:
                    print(f"Exposure: {exp_ms:.3f} ms")
                return

            # Increment: wv exp +
            if len(toks) == 2 and toks[1] == "+":
                exp_ms = _read_exposure_ms()
                if exp_ms is None:
                    print("[wv exp] Unable to read current exposure; cannot increment.")
                    return
                new_ms = exp_ms + 1
                if not _write_exposure_ms(new_ms):
                    print("[wv exp] Failed to write exposure.")
                    return
                exp_ms2 = _read_exposure_ms()
                if exp_ms2 is None:
                    print(f"[wv exp] Set exposure to ~{new_ms:.3f} ms (read-back unavailable).")
                else:
                    print(f"[wv exp] Exposure: {exp_ms:.3f} → {exp_ms2:.3f} ms (+1.0 ms)")
                return

            print("Usage: wv exp  |  wv exp +")
            return

        # ---- bifi move ----
        if len(toks) >= 2 and toks[0].lower() == "bifi" and toks[1].lower() == "move":
            # Optional numeric position: wv bifi move 123
            if len(toks) >= 3:
                try:
                    pos = int(float(toks[2]))
                    dpg.set_value(f"BifiMoveTo_{p.mattise_gui.unique_id}", pos)
                except Exception as e:
                    print(f"[wv bifi move] Ignoring invalid position '{toks[2]}': {e}")
            p.mattise_gui.btn_move_bifi()
            print("[wv] BIFI move commanded.")
            return

        # ---- move max (go to fixed position 67000) ----
        if len(toks) == 2 and toks[0].lower() == "move" and toks[1].lower() == "max":
            try:
                mat_gui = getattr(p, "matisse_gui", None) or getattr(p, "mattise_gui", None)
                if mat_gui is None:
                    print("[wv move max] Matisse GUI not available.")
                    return
                target = 67000
                dpg.set_value(f"BifiMoveTo_{mat_gui.unique_id}", int(target))
                mat_gui.btn_move_bifi()
                print(f"[wv] Moved to {target}.")
            except Exception as e:
                print(f"[wv move max] Failed: {e}")
            return

        # ---- bifi up save (iterate -50 until |Δλ| >= 0.1 nm, then spc fname="<λ>") ----
        if len(toks) >= 3 and toks[0].lower() == "bifi" and toks[1].lower() == "up" and toks[2].lower() == "save":
            import time
            try:
                mat_gui = getattr(p, "matisse_gui", None) or getattr(p, "mattise_gui", None)
                if mat_gui is None:
                    print("[wv bifi up save] Matisse GUI not available.")
                    return

                # Optional iterations: wv bifi up save 5
                try:
                    max_iters = int(toks[3]) if len(toks) >= 4 else 3
                    if max_iters < 1:
                        max_iters = 1
                except Exception:
                    max_iters = 3

                step_units = 50  # device units per iteration
                th_total_nm = 0.1  # stop when total |Δλ| >= 0.1 nm
                settle_s = 0.5  # settle time between moves

                # Baseline wavelength (nm)
                lam0, st0 = _read_wavelength_nm_with_autoexp()
                if st0 is not None:
                    raise RuntimeError(f"[wv bifi up] Baseline failed: {st0}")

                # Helper: get current BIFI position
                def _get_bifi_pos():
                    if hasattr(mat_gui.dev, "get_bifi_position"):
                        try:
                            return float(mat_gui.dev.get_bifi_position())
                        except Exception:
                            pass
                    try:
                        return float(dpg.get_value(f"BifiMoveTo_{mat_gui.unique_id}"))
                    except Exception:
                        return 0.0

                curr_pos = _get_bifi_pos()
                reached_threshold = False

                for i in range(1, max_iters + 1):
                    target = curr_pos - step_units
                    dpg.set_value(f"BifiMoveTo_{mat_gui.unique_id}", int(target))
                    mat_gui.btn_move_bifi()

                    time.sleep(settle_s)

                    lam, st = _read_wavelength_nm_with_autoexp()
                    if st is not None:
                        print(f"[wv bifi up] Read status: {st}")
                        break

                    dlam_total = abs(lam - lam0)
                    print(f"[wv bifi up save] iter {i}: pos {curr_pos:.0f} -> {target:.0f}, "
                          f"λ={lam:.3f} nm |Δλ_total|={dlam_total:.3f} nm")

                    curr_pos = target
                    if dlam_total >= th_total_nm:
                        print(f"[wv bifi up save] Reached total Δλ ≥ {th_total_nm:.3f} nm; stopping.")
                        reached_threshold = True
                        break

                # Final wavelength and save
                lam_final = p.wlm_gui._dev.get_wavelength() * 1e9
                fname = f"{lam_final:.3f}".replace(".", ",")

                print(f'[wv bifi up save] Saving with fname="{fname}"')
                try:
                    run(f'spc fname="{fname}"')
                except Exception as e:
                    print(f"[wv bifi up save] Failed to run spc: {e}")

                if not reached_threshold:
                    print("[wv bifi up save] Done. Total threshold not reached (saved anyway).")

            except Exception as e:
                print(f"[wv bifi up save] Failed: {e}")
            return

        # ---- bifi up (lower position by 100, check Δλ, maybe lower another 100) ----
        if len(toks) >= 2 and toks[0].lower() == "bifi" and toks[1].lower() == "up":
            import time
            try:
                # Optional: import pyvisa error if available
                try:
                    from pyvisa.errors import VisaIOError as _VisaIOError
                except Exception:
                    _VisaIOError = None

                def _is_locked_error(e: Exception) -> bool:
                    msg = str(e)
                    return ("VI_ERROR_RSRC_LOCKED" in msg) or (
                            _VisaIOError is not None and isinstance(e, _VisaIOError)
                    )

                def _retry(callable_, *, retries=3, base_delay=0.25, backoff=1.8, action_desc=""):
                    """
                    Retry helper for flaky VISA ops. Raises last exception if retries exhausted.
                    """
                    attempt = 0
                    delay = base_delay
                    while True:
                        try:
                            return callable_()
                        except Exception as e:
                            if not _is_locked_error(e) or attempt >= retries:
                                raise
                            attempt += 1
                            print(f"[wv bifi up] {action_desc} locked; retry {attempt}/{retries} after {delay:.2f}s...")
                            time.sleep(delay)
                            delay *= backoff

                mat_gui = getattr(p, "matisse_gui", None) or getattr(p, "mattise_gui", None)
                if mat_gui is None:
                    print("[wv bifi up] Matisse GUI not available.")
                    return

                # Optional iterations: wv bifi up 5
                try:
                    max_iters = int(toks[2]) if len(toks) >= 3 else 3
                    if max_iters < 1:
                        max_iters = 1
                except Exception:
                    max_iters = 3

                step_units = 50  # move amount per iteration (device units)
                th_total_nm = 0.1  # stop when |λ - λ0| >= this
                settle_s = 0.5

                # Baseline wavelength (nm)
                lam0, st0 = _read_wavelength_nm_with_autoexp()
                if st0 is not None:
                    raise RuntimeError(f"[wv bifi up] Baseline failed: {st0}")

                # Helper: get current BIFI position
                def _get_bifi_pos():
                    if hasattr(mat_gui.dev, "get_bifi_position"):
                        try:
                            return float(_retry(lambda: mat_gui.dev.get_bifi_position(),
                                                action_desc="get BIFI position"))
                        except Exception as e:
                            if not _is_locked_error(e):
                                pass  # fall through to UI value
                    try:
                        return float(dpg.get_value(f"BifiMoveTo_{mat_gui.unique_id}"))
                    except Exception:
                        return 0.0

                curr_pos = _get_bifi_pos()
                prev_lam = lam0
                reached_threshold = False

                for i in range(1, max_iters + 1):
                    target = curr_pos - step_units
                    dpg.set_value(f"BifiMoveTo_{mat_gui.unique_id}", int(target))

                    # Moving BIFI may hit lock; retry it
                    _retry(lambda: mat_gui.btn_move_bifi(), action_desc="move BIFI")

                    time.sleep(settle_s)  # brief settle

                    # Wavelength read can also hit lock; retry it
                    lam, st = _read_wavelength_nm_with_autoexp()
                    if st is not None:
                        print(f"[wv bifi up] Read status: {st}")
                        # if it's still not a number after auto-adjusts, break or continue as you prefer:
                        # continue  # try next iteration
                        # or:
                        break

                    dlam_total = abs(lam - lam0)
                    dlam_step = abs(lam - prev_lam)
                    print(f"[wv bifi up] iter {i}: pos {curr_pos:.0f} -> {target:.0f}, "
                          f"λ={lam:.3f} nm |dlambda_total|={dlam_total:.3f} nm (dstep={dlam_step:.3f} nm)")

                    curr_pos = target
                    if dlam_total >= th_total_nm:
                        print(f"[wv bifi up] Reached total dlambda ≥ {th_total_nm:.3f} nm; stopping.")
                        reached_threshold = True
                        break

                    prev_lam = lam

                if not reached_threshold:
                    print("[wv bifi up] Done. Total threshold not reached or early stop triggered.")

            except Exception as e:
                print(f"[wv bifi up] Failed after retries: {e}")
            return

        # ---- bifi min (go to fixed position 84000) ----
        if len(toks) == 2 and toks[0].lower() == "bifi" and toks[1].lower() == "min":
            try:
                mat_gui = getattr(p, "matisse_gui", None) or getattr(p, "mattise_gui", None)
                if mat_gui is None:
                    print("[wv bifi min] Matisse GUI not available.")
                    return
                target = 84000
                dpg.set_value(f"BifiMoveTo_{mat_gui.unique_id}", int(target))
                mat_gui.btn_move_bifi()
                print(f"[wv] BIFI moved to {target}.")
            except Exception as e:
                print(f"[wv bifi min] Failed: {e}")
            return

        print("Usage: wv ?  |  wave ?  |  wv bifi move [pos]  |  wv exp  |  wv exp +")
    def handle_plot(self, arg: str = ""):
        """
        plot                     -> choose a CSV and plot (wavelength[nm], intensity)
        plot spc | plot spectrum -> same as 'plot'
        plot add                 -> choose a CSV and add as a NEW line to the existing plot
        plot "C:\\path\\file.csv" [add] -> plot given file (optional 'add' to overlay)
        plot mult <num>                -> multiply the last displayed line's intensity by <num>
        """
        import os
        import numpy as np
        import dearpygui.dearpygui as dpg
        from Utils import open_file_dialog

        # --- tags for the standalone plot window ---
        win = "csv_plot_win"
        plot = "csv_plot"
        xax = "csv_plot_x"
        yax = "csv_plot_y"

        # parse mode
        a = (arg or "").strip().strip('"').strip("'")
        tokens = a.split()
        add_mode = False

        # ---------- MULTIPLY MODE ----------
        # Usage: plot mult <num>
        if a.lower().startswith("mult"):
            toks = a.split()
            if len(toks) < 2:
                print("Usage: plot mult <factor>")
                return
            try:
                factor = float(toks[1])
            except Exception:
                print(f"Invalid factor: {toks[1]}")
                return

            if not dpg.does_item_exist(yax):
                print("No plot available. Run 'plot' first.")
                return

            # choose the last series:
            series_tag = None
            # preference 1: last-known
            if getattr(self, "_plot_last_series", None) and dpg.does_item_exist(self._plot_last_series):
                series_tag = self._plot_last_series
            else:
                # preference 2: the highest csv_series_XX present
                try:
                    children = dpg.get_item_children(yax, 1) or []
                except TypeError:
                    info = dpg.get_item_children(yax)
                    children = info.get(1, []) if isinstance(info, dict) else []
                # filter to our series tags; keep order
                candidates = []
                for cid in children:
                    try:
                        tag = dpg.get_item_alias(cid) or str(cid)
                    except Exception:
                        tag = str(cid)
                    if tag.startswith("csv_series_"):
                        candidates.append(tag)
                if candidates:
                    # pick last in draw order
                    series_tag = candidates[-1]
                elif dpg.does_item_exist("csv_series_00"):
                    series_tag = "csv_series_00"

            if not series_tag or not dpg.does_item_exist(series_tag):
                print("No line series found to multiply.")
                return

            # apply multiplication
            try:
                val = dpg.get_value(series_tag)

                # Handle both list/tuple [x, y] and dict {"x": [...], "y": [...], ...}
                if isinstance(val, dict):
                    x_vals = list(val.get("x", []))
                    y_vals = list(val.get("y", []))
                elif isinstance(val, (list, tuple)) and len(val) >= 2:
                    x_vals, y_vals = val[0], val[1]
                else:
                    print(f"Unexpected series value type/shape for '{series_tag}': {type(val)}")
                    return

                y_scaled = [float(y) * factor for y in y_vals]

                if isinstance(val, dict):
                    new_val = dict(val)
                    new_val["y"] = y_scaled
                    dpg.set_value(series_tag, new_val)
                else:
                    dpg.set_value(series_tag, [x_vals, y_scaled])

                # update legend label to indicate scaling
                old_label = dpg.get_item_label(series_tag)
                if "×" in old_label:
                    base = old_label.split("×", 1)[0].rstrip()
                else:
                    base = old_label
                dpg.set_item_label(series_tag, f"{base} ×{factor:g}")

                self._plot_last_series = series_tag
                dpg.fit_axis_data(xax)
                dpg.fit_axis_data(yax)
                print(f"Scaled '{series_tag}' by factor {factor:g}.")
                return
            except Exception as e:
                print(f"Failed to scale series: {e}")
                return

        # ---------- END MULTIPLY MODE ----------

        # accept: plot add
        if tokens[:1] == ["add"]:
            add_mode = True
            tokens = tokens[1:]

        # accept: plot spc / plot spectrum (same as plot)
        if tokens[:1] and tokens[0].lower() in ("spc", "spectrum"):
            tokens = tokens[1:]

        # optional explicit file path remains in tokens
        explicit_path = " ".join(tokens).strip() if tokens else ""

        # pick file
        if explicit_path and os.path.isfile(explicit_path):
            file_path = explicit_path
        else:
            start_dir = r"Q:\QT-Quantum_Optic_Lab\expData\Spectrometer"
            file_path = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                                         initial_folder=start_dir)
            if not file_path:
                print("Plot canceled or no file selected.")
                return

        # load csv: first col = wavelength (nm), second col = intensity
        try:
            data = np.genfromtxt(file_path, delimiter=",")
            if data.ndim != 2 or data.shape[1] < 2:
                print(f"CSV does not have at least two columns: {file_path}")
                return
            data = data[data[:, 0].argsort()]
            x_vals = data[:, 0].tolist()
            y_vals = data[:, 1].tolist()
        except Exception as e:
            print(f"Failed to read CSV '{file_path}': {e}")
            return

        # ensure window/plot exist
        if not dpg.does_item_exist(win):
            with dpg.window(label="Spectrum (CSV)", width=1200, height=720, pos=[120, 120], tag=win):
                dpg.add_plot(label=os.path.basename(file_path), tag=plot, crosshairs=True, width=-1, height=-1)
                dpg.add_plot_axis(dpg.mvXAxis, label="Wavelength [nm]", tag=xax, parent=plot)
                dpg.add_plot_axis(dpg.mvYAxis, label="Intensity", tag=yax, parent=plot)
        else:
            dpg.show_item(win)
            dpg.focus_item(win)
            dpg.set_item_width(win, 1200)
            dpg.set_item_height(win, 720)
            if not dpg.does_item_exist(plot):
                dpg.add_plot(label=os.path.basename(file_path), tag=plot, crosshairs=True, width=-1, height=-1,
                             parent=win)
            if not dpg.does_item_exist(xax):
                dpg.add_plot_axis(dpg.mvXAxis, label="Wavelength [nm]", tag=xax, parent=plot)
            if not dpg.does_item_exist(yax):
                dpg.add_plot_axis(dpg.mvYAxis, label="Intensity", tag=yax, parent=plot)

        # choose a unique series tag for 'add' mode; reuse primary tag on non-add
        if not hasattr(self, "_plot_series_counter"):
            self._plot_series_counter = 0

        if add_mode:
            self._plot_series_counter += 1
            series_tag = f"csv_series_{self._plot_series_counter:02d}"
            label = os.path.basename(file_path)
            dpg.add_line_series(x_vals, y_vals, label=label, parent=yax, tag=series_tag)
        else:
            series_tag = "csv_series_00"
            label = os.path.basename(file_path)

            # remove any other series so only one line remains
            try:
                children = dpg.get_item_children(yax, 1) or []
            except TypeError:
                info = dpg.get_item_children(yax)
                children = info.get(1, []) if isinstance(info, dict) else []
            for cid in list(children):
                if dpg.does_item_exist(cid) and cid != series_tag:
                    dpg.delete_item(cid)

            # reset counter since we're back to a single line
            self._plot_series_counter = 0

            if dpg.does_item_exist(series_tag):
                dpg.set_value(series_tag, [x_vals, y_vals])
                dpg.set_item_label(plot, label)
            else:
                dpg.add_line_series(x_vals, y_vals, label=label, parent=yax, tag=series_tag)
                dpg.set_item_label(plot, label)

        # fit axes
        dpg.fit_axis_data(xax)
        dpg.fit_axis_data(yax)
    def handle_chip(self, *args):
        """
        chip commands:
            chip name <the name>   -> set chip_name and save it
            chip name?             -> print the currently stored chip name
        """
        import shlex
        # Join dispatcher args
        text = " ".join(str(a) for a in args).strip()
        # If user typed exactly:  chip name?
        if text.lower() == "name?":
            name = getattr(self, "_chip_name", "")
            if name:
                print(f"[chip] name = '{name}'")
            else:
                print("[chip] name not set.")
            return True
        # No args or incomplete
        if not text:
            print("Usage:")
            print("  chip name <chip-name>")
            print("  chip name?         # show current chip name")
            return False
        # Tokenize
        try:
            tokens = shlex.split(text)
        except Exception:
            tokens = text.split()
        if not tokens:
            print("Usage: chip name <chip-name>")
            return False
        sub = tokens[0].lower()
        # Wrong subcommand
        if sub != "name":
            print("Usage:")
            print("  chip name <chip-name>")
            print("  chip name?")
            return False
        # Handle plain: chip name?
        if len(tokens) == 1:
            print("Usage: chip name <chip-name>   or   chip name?")
            return False
        # SET MODE (chip name <name...>)
        name = " ".join(tokens[1:]).strip()
        if not name:
            print("[chip] empty chip name not allowed.")
            return False
        # Store chip name
        self._chip_name = name
        print(f"[chip] name set to '{name}'")
        # Persist via coup save
        try:
            self.handle_coup("save")
        except Exception as e:
            print(f"[chip] warning: failed to save coup state after setting name: {e}")
            return False
        return True
    def handle_coupon(self, arg: str = ""):
        """
        coupon name <name>        -> save current coordinates with label <name>
        coupon <name>             -> same as 'coupon name <name>'
        coupon listx <n1> <n2>…   -> record names along X using coup shiftx geometry (no movement)
        coupon listy <n1> <n2>…   -> record names along Y using coup shifty geometry (no movement)
        coupon listxy A1-E6       -> record a 2D grid from current position (A1) using shiftx/shifty (no movement)
        coupon list               -> list all stored coupon names and positions
        coupon clear              -> clear all stored coupon names
        coupon ?                  -> show the nearest coupon name at current position
        coupon go <name>          -> move to stored coupon <name>
        """
        import shlex
        import math
        import re

        # Ensure store exists: name -> dict(u_um, v_um)
        if not hasattr(self, "_coupon_labels"):
            self._coupon_labels = {}
        text = (arg or "").strip()
        # Helper: remove any existing labels closer than tol_um
        def _override_nearby(u_new: float, v_new: float, tol_um: float = 1.0):
            removed = []
            for name, info in list(self._coupon_labels.items()):
                try:
                    du = u_new - float(info.get("u_um", 0.0))
                    dv = v_new - float(info.get("v_um", 0.0))
                    if (du * du + dv * dv) ** 0.5 < tol_um:
                        del self._coupon_labels[name]
                        removed.append(name)
                except Exception:
                    continue
            for name in removed:
                print(f"[coupon] overriding old name '{name}' at nearly the same position.")
        # --- coupon ? -> query nearest coupon name by (U,V) ---
        if text == "?":
            try:
                u_cur, v_cur, _ = self._read_current_position_um()
            except Exception as e:
                print(f"[coupon] ?: cannot read current position: {e}")
                return False

            best = None
            TOL_UM = 560.0  # how close [µm] to consider "same vicinity"

            for name, info in self._coupon_labels.items():
                try:
                    du = u_cur - float(info.get("u_um", 0.0))
                    dv = v_cur - float(info.get("v_um", 0.0))
                    d2 = du * du + dv * dv
                except Exception:
                    continue
                if best is None or d2 < best[0]:
                    best = (d2, name, du, dv)

            if best is None or best[0] > TOL_UM * TOL_UM:
                print("[coupon] no named coupon found near the current position.")
                return True

            d2, name, du, dv = best
            dist = math.sqrt(d2)
            print(f"[coupon] nearest name: '{name}' (distance = {dist:.3f} µm)")
            return True
        # --- coupon list -> list all labels ---
        if text.lower() == "list":
            if not self._coupon_labels:
                print("[coupon] list: no coupon names stored.")
                return True
            print(f"[coupon] list: {len(self._coupon_labels)} name(s):")
            for name in sorted(self._coupon_labels.keys(), key=str):
                info = self._coupon_labels[name]
                u = float(info.get("u_um", 0.0))
                v = float(info.get("v_um", 0.0))
                print(f"  {name!r}: U={u:.3f} µm, V={v:.3f} µm")
            self.handle_coup("save")
            return True

        # No arg → show usage
        if not text:
            print("Usage:")
            print("  coupon name <name>")
            print("  coupon <name>")
            print("  coupon listx <n1> <n2> ...")
            print("  coupon listy <n1> <n2> ...")
            print("  coupon listxy A1-E6")
            print("  coupon list")
            print("  coupon clear")
            print("  coupon go <name>")
            print("  coupon ?")
            return False
        try:
            tokens = shlex.split(text)
        except Exception:
            tokens = text.split()
        if not tokens:
            print(
                "Usage: coupon name <name> | coupon <name> | "
                "coupon listx <n1> <n2> ... | coupon listy <n1> <n2> ... | "
                "coupon listxy A1-E6 | coupon list | coupon clear | coupon go <name> | coupon ?"
            )
            return False
        sub = tokens[0].lower()

        # --- coupon clear <label> -> remove a single label ---
        if sub == "clear":
            if len(tokens) == 1:
                # already handled above (global clear), but here for safety:
                self._coupon_labels.clear()
                print("[coupon] clear: all coupon names removed.")
                self.handle_coup("save")
                return True

            label = " ".join(tokens[1:]).strip()
            if not label:
                print("[coupon] clear: missing label. Usage: coupon clear <label>")
                return False

            if label in self._coupon_labels:
                del self._coupon_labels[label]
                print(f"[coupon] clear: removed label '{label}'.")
                self.handle_coup("save")
                return True
            else:
                print(f"[coupon] clear: no such label '{label}'.")
                return False
        # --- coupon go <name> ---
        if sub == "go":
            if len(tokens) < 2:
                print("[coupon] go: missing name. Usage: coupon go <name>")
                return False

            label = " ".join(tokens[1:]).strip()
            if label not in self._coupon_labels:
                print(f"[coupon] go: no such coupon '{label}'. Use 'coupon list' to see available names.")
                return False

            target = self._coupon_labels[label]
            try:
                u_tgt = float(target["u_um"])
                v_tgt = float(target["v_um"])
            except Exception:
                print(f"[coupon] go: invalid data for '{label}'.")
                return False

            # Read current position
            try:
                u_cur, v_cur, _ = self._read_current_position_um()
            except Exception as e:
                print(f"[coupon] go: cannot read current position: {e}")
                return False

            # Compute required delta
            dU = u_tgt - u_cur
            dV = v_tgt - v_cur

            # Perform move in real UV axes
            try:
                if abs(dU) > 1e-6:
                    self._move_delta(0, dU)
                if abs(dV) > 1e-6:
                    self._move_delta(1, dV)
            except Exception as e:
                print(f"[coupon] go: move failed: {e}")
                return False

            print(f"[coupon] go: moved to '{label}' → (U={u_tgt:.3f} µm, V={v_tgt:.3f} µm)")
            return True
        # --- coupon name <name>  OR  coupon <name> ---
        if sub == "name" or sub not in ("listx", "listy", "listxy", "list", "clear", "go", "?"):
            # If user wrote 'coupon name foo', label is tokens[1:]
            # If user wrote 'coupon foo', label is tokens[0:] (because sub is not a keyword)
            if sub == "name":
                if len(tokens) < 2:
                    print("[coupon] name: missing name. Usage: coupon name <name> or coupon <name>")
                    return False
                label = " ".join(tokens[1:]).strip()
            else:
                # coupon <name> path
                label = " ".join(tokens).strip()

            if not label:
                print("[coupon] name: empty name not allowed.")
                return False

            try:
                u_cur, v_cur, _ = self._read_current_position_um()
            except Exception as e:
                print(f"[coupon] name: cannot read current position: {e}")
                return False

            _override_nearby(u_cur, v_cur, tol_um=1.0)

            self._coupon_labels[label] = {
                "u_um": float(u_cur),
                "v_um": float(v_cur),
            }
            print(f"[coupon] name: '{label}' recorded at (U={u_cur:.3f} µm, V={v_cur:.3f} µm)")
            self.handle_coup("save")
            return True
        # --- geometric helpers (used by listx, listy, listxy) ---
        def _geom_steps():
            """Return (dUx, dVx, dUy, dVy) in µm for one step in X (shiftx) and Y (shifty)."""
            angle = math.radians(float(getattr(self, "_coupon_angle_deg", 0.0)))
            cos_t = math.cos(angle)
            sin_t = math.sin(angle)

            # step along U (shiftx)
            step_x_um = float(getattr(self, "_coup_shift_x_factor", 5.0)) * float(
                getattr(self, "_coupx_move_um", 80.0)
            )
            dUx = step_x_um * cos_t
            dVx = step_x_um * sin_t

            # step along V (shifty)
            step_y_um = float(getattr(self, "_coup_shift_y_factor", 5.43)) * float(
                getattr(self, "_coupy_move_um", 70.0)
            )
            dUy = -step_y_um * sin_t
            dVy = step_y_um * cos_t

            return dUx, dVx, dUy, dVy
        # --- coupon listx / listy <n1> <n2> ... (no physical movement) ---
        if sub in ("listx", "listy"):
            along_x = (sub == "listx")
            names = tokens[1:]
            if not names:
                print(f"[coupon] {sub}: need at least one name.")
                return False
            # Read current stage position once
            try:
                u0, v0, _ = self._read_current_position_um()
            except Exception as e:
                print(f"[coupon] {sub}: cannot read current position: {e}")
                return False
            dUx, dVx, dUy, dVy = _geom_steps()
            # Use only one axis of the geometry
            if along_x:
                step_u = dUx
                step_v = dVx
            else:
                step_u = dUy
                step_v = dVy
            for idx, label in enumerate(names):
                label = label.strip()
                if not label:
                    continue
                u_est = u0 + idx * step_u
                v_est = v0 + idx * step_v
                _override_nearby(u_est, v_est, tol_um=1.0)
                self._coupon_labels[label] = {
                    "u_um": float(u_est),
                    "v_um": float(v_est),
                }
                print(f"[coupon] {sub}: '{label}' recorded at simulated (U={u_est:.3f} µm, V={v_est:.3f} µm)")
            self.handle_coup("save")
            return True
        # --- coupon listxy A1-E6 (no physical movement) ---
        if sub == "listxy":
            if len(tokens) < 2:
                print("[coupon] listxy: missing range. Usage: coupon listxy A1-E6")
                return False
            rng = tokens[1].strip()
            m = re.fullmatch(r"([A-Za-z])(\d+)\s*-\s*([A-Za-z])(\d+)", rng)
            if not m:
                print("[coupon] listxy: invalid range. Use like: coupon listxy A1-E6")
                return False
            row_start_char, col_start_str, row_end_char, col_end_str = m.groups()
            row_start = ord(row_start_char.upper()) - ord("A")
            row_end = ord(row_end_char.upper()) - ord("A")
            col_start = int(col_start_str)
            col_end = int(col_end_str)
            if row_end < row_start or col_end < col_start:
                print("[coupon] listxy: range must be increasing, e.g. A1-E6.")
                return False
            n_rows = row_end - row_start + 1
            n_cols = col_end - col_start + 1
            # Read current stage position once (A1)
            try:
                u0, v0, _ = self._read_current_position_um()
            except Exception as e:
                print(f"[coupon] listxy: cannot read current position: {e}")
                return False
            dUx, dVx, dUy, dVy = _geom_steps()
            for r_idx in range(n_rows):
                for c_idx in range(n_cols):
                    row_char = chr(ord("A") + row_start + r_idx)
                    col_num = col_start + c_idx
                    label = f"{row_char}{col_num}"
                    u_est = u0 + c_idx * dUx + r_idx * dUy
                    v_est = v0 + c_idx * dVx + r_idx * dVy
                    _override_nearby(u_est, v_est, tol_um=1.0)
                    self._coupon_labels[label] = {
                        "u_um": float(u_est),
                        "v_um": float(v_est),
                    }
                    print(f"[coupon] listxy: '{label}' recorded at simulated (U={u_est:.3f} µm, V={v_est:.3f} µm)")
            self.handle_coup("save")
            return True
        # Unknown subcommand
        print("Usage:")
        print("  coupon name <name>")
        print("  coupon <name>")
        print("  coupon listx <n1> <n2> ...")
        print("  coupon listy <n1> <n2> ...")
        print("  coupon listxy A1-E6")
        print("  coupon list")
        print("  coupon clear")
        print("  coupon go <name>")
        print("  coupon ?")
        return False
    def handle_last_message(self, *args):
        """
        last            -> copy the last message to the clipboard
        last N          -> copy the last N messages to the clipboard
        """
        import pyperclip
        try:
            dual = sys.stdout

            # How many messages to copy
            if args and str(args[0]).isdigit():
                n = int(args[0])
                if n < 1:
                    print("[last] N must be >= 1")
                    return False
            else:
                n = 1

            if not hasattr(dual, "messages") or not dual.messages:
                print("[last] no messages available.")
                return False

            # Select last N messages
            msgs = dual.messages[-n:]

            # Clean and join
            cleaned = [m.rstrip("\n") for m in msgs]
            final_text = "\n".join(cleaned)

            pyperclip.copy(final_text)
            print(f"[last] copied last {n} message(s) to clipboard.")
            return True

        except Exception as e:
            print(f"[last] failed: {e}")
            return False
    def handle_cr(self, arg: str = ""):
        """
        cr [factor]
          Alias for 'coup resume [factor]'.

          cr         -> same as 'coup resume'      (factor default = 1.0)
          cr 3       -> same as 'coup resume 3'
        """
        text = (arg or "").strip()
        if not text:
            # no factor → just plain 'resume'
            return self.handle_coup("resume")

        # take first token as factor, ignore the rest if any
        factor_token = text.split()[0]
        return self.handle_coup(f"resume {factor_token}")
    def handle_proem(self, arg: str = ""):
        self.handle_start_counter()
        p = self.get_parent()
        target_gui = getattr(p, "proem_gui", None)
        dev = getattr(target_gui, "dev", None) if target_gui is not None else None
        dev._exp.Stop()
        time.sleep(0.2)
        dev.set_value(CameraSettings.ShutterTimingExposureTime, 1000.0)
        dev._exp.Preview()
    def handle_uvz(self, axis: str, arg: str = ""):
        """
        Set Z coupling for U or V vector.
        Examples:
          uz -2 600 set          → z changes -2 µm per 600 µm U move
          uz -2um 600um set      → same as above
          uz -2 600um set        → same as above
          vz 1 800 set           → z changes +1 µm per 800 µm V move
        """

        import re, shlex

        try:
            tokens = shlex.split(arg) if arg else []
        except Exception:
            tokens = [s for s in (arg or "").strip().split() if s]

        if len(tokens) not in (2, 3) or tokens[-1].lower() != "set":
            print(f"Usage: {axis} <Δz_um> <Δxy_um> set   (e.g. {axis} -2 600 set)")
            return False

        # Handle simple two-value case: uz 0.5 set
        if len(tokens) == 2:
            try:
                val = float(re.sub(r"um$", "", tokens[0], flags=re.IGNORECASE))
            except Exception as e:
                print(f"[Smaract] {axis} set: invalid number '{tokens[0]}' ({e})")
                return False
            gui = getattr(self.get_parent(), "smaractGUI", None)
            if gui is None:
                print("[Smaract] uz/vz: smaractGUI not available on parent.")
                return False
            if axis == "uz":
                gui._uz_override = val
            else:
                gui._vz_override = val
            print(f"[Smaract] set {axis} = {val}")
            return True

        # Full 3-token normalization: uz -2 600 set
        try:
            dz_str, dxy_str = tokens[0], tokens[1]

            # Remove optional 'um'
            dz = float(re.sub(r"um$", "", dz_str, flags=re.IGNORECASE))
            dxy = float(re.sub(r"um$", "", dxy_str, flags=re.IGNORECASE))
        except Exception as e:
            print(f"[Smaract] {axis} set: invalid numbers ({e})")
            return False

        if abs(dxy) < 1e-9:
            print(f"[Smaract] {axis} set: Δxy cannot be zero.")
            return False

        # Ratio (µm Z per µm XY)
        ratio = dz / dxy

        gui = getattr(self.get_parent(), "smaractGUI", None)
        if gui is None:
            print("[Smaract] uz/vz: smaractGUI not available on parent.")
            return False

        if axis == "uz":
            gui._uz_override = ratio
        else:
            gui._vz_override = ratio

        print(
            f"[Smaract] normalized {axis}: ΔZ={dz} µm, ΔXY={dxy} µm "
            f"→ stored {axis}={ratio:.6f} (µm Z per µm XY)"
        )
        return True
    def handle_replace(self, arg: str):
        """
        Replace the letter used in 'spc note <LETTER><N>' lines in sb.py.

        Usage:
            replace +          # increment current letter  (C -> D)
            replace -          # decrement current letter  (C -> B)
            replace D          # change current letter -> D
            replace C D        # explicitly C -> D

        The file is assumed to be:
            C:\\WC\\HotSystem\\Utils\\macro\\sb.py
        """
        import re

        path = r"C:\WC\HotSystem\Utils\macro\sb.py"
        arg = (arg or "").strip()

        if not arg:
            print("Usage: replace + | replace - | replace <TO> | replace <FROM> <TO>")
            return

        # Read the file
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"replace: failed to read {path}: {e}")
            return

        # Find all 'spc note XN' occurrences and deduce the current letter
        matches = re.findall(r"\bspc\s+note\s+([A-Z])(\d+)", content)
        if not matches:
            print("replace: no 'spc note <LETTER><N>' patterns found in file.")
            return

        letters = sorted({m[0] for m in matches})
        # If multiple letters exist, we still pick one but warn
        if len(letters) > 1:
            print(f"replace: multiple note letters found in file: {letters}. Using '{letters[-1]}' as current.")
        current = letters[-1]  # pick the last in sorted list, e.g. 'C'

        # Decide from_letter and to_letter based on arg
        if arg in ("+", "-"):
            # Shift current letter by ±1
            shift = 1 if arg == "+" else -1
            idx = (ord(current) - ord("A") + shift) % 26
            from_letter = current
            to_letter = chr(ord("A") + idx)
        else:
            parts = arg.split()
            if len(parts) == 1:
                # 'replace D' -> current -> D
                from_letter = current
                to_letter = parts[0].upper()
            elif len(parts) == 2:
                # 'replace C D'
                from_letter = parts[0].upper()
                to_letter = parts[1].upper()
            else:
                print("replace: too many arguments.")
                return

        if len(from_letter) != 1 or len(to_letter) != 1:
            print("replace: FROM and TO must be single letters.")
            return

        if from_letter == to_letter:
            print(f"replace: '{from_letter}' == '{to_letter}', nothing to do.")
            return

        # Replace only in 'spc note XN' patterns
        pattern = rf"(\bspc\s+note\s+){from_letter}(\d+)"
        new_content, count = re.subn(pattern, rf"\1{to_letter}\2", content)

        if count == 0:
            print(f"replace: no 'spc note {from_letter}<N>' occurrences found.")
            return

        # Write back to file
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
        except Exception as e:
            print(f"replace: failed to write {path}: {e}")
            return

        print(f"replace: changed letter {from_letter} -> {to_letter} in {count} 'spc note' lines.")
    def handle_move_abs_xyz(self, arg):
        """Set X, Y, Z absolute in one command: abs x,y,z or abs (x,y,z)."""
        try:
            if not arg:
                raise ValueError("No coordinates supplied")

            coords_str = arg.strip()

            # allow formats like "(10, 20, 30)" or "10,20,30"
            if coords_str[0] == "(" and coords_str[-1] == ")":
                coords_str = coords_str[1:-1]

            parts = [p.strip() for p in coords_str.split(",") if p.strip()]
            if len(parts) != 3:
                raise ValueError(f"Expected 3 values, got {len(parts)}")

            x_str, y_str, z_str = parts

            # reuse existing per-axis helper
            self._move_abs_axis(0, x_str)
            self._move_abs_axis(1, y_str)
            self._move_abs_axis(2, z_str)

            x, y, z = map(float, (x_str, y_str, z_str))
            print(f"Moved to abs position X={x:.3f}, Y={y:.3f}, Z={z:.3f}")
        except Exception as e:
            print(f"abs xyz failed: {e}")
    def handle_moveabs_to_max_intensity(self, arg):
        """Move stage to position of max intensity. Usage: 'maxi'"""
        try:
            p = self.get_parent()
            p.opx.set_moveabs_to_max_intensity()
            print("OPX: moved to max intensity position.")
            p.smaractGUI.move_absolute(None,None,0)
            p.smaractGUI.move_absolute(None, None, 1)
            p.smaractGUI.move_absolute(None, None, 2)
        except Exception as e:
            print(f"OPX max intensity move failed: {e}")
    def handle_copy(self, arg):
        """
        copy <dest>  -> set destination folder for copies
        copy         -> copy last saved file (and its .xml pair) to destination
        """
        import shutil
        import os

        try:
            # 1) If we got an argument: treat it as destination folder
            if arg:
                dest = arg.strip().strip('"').strip("'")
                if not dest:
                    raise ValueError("Empty destination path")

                self._copy_dest = dest
                os.makedirs(self._copy_dest, exist_ok=True)
                print(f"copy: destination set to '{self._copy_dest}'")
                return

            # 2) No argument: copy last saved file (and .xml if present)
            if not self._copy_dest:
                raise RuntimeError("Copy destination not set. Use: copy <dest>")

            src = self.get_parent().opx._last_saved_file
            if not src:
                raise RuntimeError("No last saved file. Set self._last_saved_file when saving.")

            if not os.path.isfile(src):
                raise FileNotFoundError(f"Last saved file not found: {src}")

            # Copy main file
            dst = os.path.join(self._copy_dest, os.path.basename(src))
            shutil.copy2(src, dst)
            print(f"copy: '{src}' -> '{dst}'")

            # Try to copy XML file with same base name
            base, _ = os.path.splitext(src)
            xml_src = base + ".xml"
            if os.path.isfile(xml_src):
                xml_dst = os.path.join(self._copy_dest, os.path.basename(xml_src))
                shutil.copy2(xml_src, xml_dst)
                print(f"copy: '{xml_src}' -> '{xml_dst}' (XML)")
            else:
                print(f"copy: no XML file found for '{src}'")

        except Exception as e:
            print(f"copy failed: {e}")
    def _read_g2_sites(self, path):
        """Parse all abs (x,y,z) lines from g2.py and return list of (x,y,z)."""
        coords = []
        if not os.path.isfile(path):
            print(f"add map: g2 file not found: {path}")
            return coords

        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("abs"):
                        m = re.search(r'\(([^)]*)\)', line)
                        if not m:
                            continue
                        parts = [p.strip() for p in m.group(1).split(",")]
                        if len(parts) < 3:
                            continue
                        try:
                            x = float(parts[0])
                            y = float(parts[1])
                            z = float(parts[2])
                            coords.append((x, y, z))
                        except ValueError:
                            continue
        except Exception as e:
            print(f"add map: error reading {path}: {e}")
        return coords
    def _parse_center_from_tif_name(self, filename):
        """
        Extract center (X,Y,Z) in µm from TIF filename, e.g.
        'Site (-100,45 183,5 -98,2) B8 ... .tif'
        -> (-100.45, 183.5, -98.2)
        """
        name = os.path.basename(filename)
        m = re.search(r'\(([^)]*)\)', name)
        if not m:
            return None
        coord_str = m.group(1)  # e.g. "-100,45 183,5 -98,2"
        coord_str = coord_str.replace(",", ".")
        parts = coord_str.split()
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                pass

        if len(nums) >= 3:
            return (nums[0], nums[1], nums[2])
        elif len(nums) == 2:
            return (nums[0], nums[1], 0.0)
        else:
            return None
    def _find_best_tif_for_site(self, site_coord, lf_dir):
        """
        In LightField folder, find the TIF whose encoded center coords
        are closest to the given site_coord (x,y,z).
        """
        best_path = None
        best_center = None
        best_d2 = None

        pattern = os.path.join(lf_dir, "*.tif")
        for path in glob.glob(pattern):
            center = self._parse_center_from_tif_name(path)
            if center is None:
                continue
            dx = site_coord[0] - center[0]
            dy = site_coord[1] - center[1]
            dz = site_coord[2] - center[2]
            d2 = dx * dx + dy * dy + dz * dz
            if best_path is None or d2 < best_d2:
                best_path = path
                best_center = center
                best_d2 = d2

        return best_path, best_center
    def _load_lightfield_tif_for_display(self,tif_path):
        """
        Robustly load LightField .tif as visible 8-bit RGB image.
        Handles 16-bit grayscale, float32, or multi-frame data.
        """
        import tifffile
        import numpy as np
        from PIL import Image, ImageDraw

        with tifffile.TiffFile(tif_path) as tif:
            data = tif.asarray()

        # If multi-frame or multi-channel, pick the first frame
        if data.ndim > 2:
            data = data[..., 0] if data.shape[-1] < data.shape[0] else data[0]

        # Convert to float and normalize to [0, 255]
        arr = np.array(data, dtype=np.float32)
        vmin, vmax = np.percentile(arr, [0.5, 99.5])
        if vmax <= vmin:
            vmax = vmin + 1
        arr = np.clip((arr - vmin) / (vmax - vmin), 0, 1)
        arr8 = (arr * 255).astype(np.uint8)
        img = Image.fromarray(arr8, mode="L").convert("RGB")
        return img
    def handle_add_map(self, arg):
        """
        Command: add map
        ----------------
        Reads C:\\WC\\HotSystem\\Utils\\macro\\g2.py, finds the site closest to the
        current position (self._read_current_position_um()), then in
        C:\\Users\\Femto\\Work Folders\\Documents\\LightField finds the TIF whose
        encoded coordinates match that site best, overlays a red cross at the
        current position, and adds it as a new slide to PowerPoint.
        """
        try:
            # 1) current position from stage in µm
            Xum, Yum, Zum = self._read_current_position_um()

            # 2) nearest site from g2.py
            g2_path = r"C:\WC\HotSystem\Utils\macro\g2.py"
            sites = self._read_g2_sites(g2_path)
            if not sites:
                print("add map: no sites found in g2.py")
                return

            def d2(site):
                dx = Xum - site[0]
                dy = Yum - site[1]
                dz = Zum - site[2]
                return dx*dx + dy*dy + dz*dz

            site = min(sites, key=d2)
            print(f"add map: closest site from g2.py: ({site[0]:.2f}, {site[1]:.2f}, {site[2]:.2f})")

            # 3) find matching TIF in LightField folder
            lf_dir = r"C:\Users\Femto\Work Folders\Documents\LightField"
            tif_path, center_um = self._find_best_tif_for_site(site, lf_dir)
            if tif_path is None or center_um is None:
                print("add map: no matching TIF found in LightField folder")
                return

            print(f"add map: using TIF '{tif_path}' with center {center_um}")

            # 4) open image and compute pixel coords for *current* position
            img = self._load_lightfield_tif_for_display(tif_path)
            width, height = img.size          # (cols, rows)

            # MATLAB: imgSize=[rows,cols]; centerPix=(imgSize+1)/2
            row_center = (height + 1) / 2.0
            col_center = (width + 1) / 2.0

            # Same parameters as in MATLAB script
            pixel_size = 0.072    # µm per pixel
            theta = -0.09         # radians
            x_offset = -16.6      # µm
            y_offset = -3.4       # µm

            Xc, Yc, Zc = center_um

            # Forward in MATLAB:
            # dX = dCol*pixelSize; dY = dRow*pixelSize
            # dX_rot =  dX*cosθ + dY*sinθ
            # dY_rot = -dX*sinθ + dY*cosθ
            # Xum = Xc + dX_rot + xOffset
            # Yum = Yc + dY_rot + yOffset
            #
            # Here we invert: from Xum,Yum to dX,dY
            dX_rot = Xum - Xc - x_offset
            dY_rot = Yum - Yc - y_offset

            cos_t = math.cos(theta)
            sin_t = math.sin(theta)

            # inverse rotation: rotate by -θ
            dX =  dX_rot * cos_t - dY_rot * sin_t
            dY =  dX_rot * sin_t + dY_rot * cos_t

            dCol = dX / pixel_size
            dRow = dY / pixel_size

            xPix = col_center + dCol   # column index
            yPix = row_center + dRow   # row index

            # 5) draw a red cross at (xPix, yPix)
            draw = ImageDraw.Draw(img)
            cx = int(round(xPix))
            cy = int(round(yPix))
            arm = 10  # pixels
            draw.line((cx - arm, cy, cx + arm, cy), fill=(255, 0, 0), width=3)
            draw.line((cx, cy - arm, cx, cy + arm), fill=(255, 0, 0), width=3)

            # 6) save to temp PNG and insert into PowerPoint
            tmp_png = os.path.join(tempfile.gettempdir(), "g2_map_overlay.png")
            img.save(tmp_png)

            pythoncom.CoInitialize()
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                raise RuntimeError("No PowerPoint presentations are open!")
            pres = ppt.ActivePresentation
            slide = pres.Slides.Add(pres.Slides.Count + 1, 12)
            try:
                ppt.ActiveWindow.View.GotoSlide(slide.SlideIndex)
            except Exception as e:
                print(f"[add map] GotoSlide skipped: {e}")

            shape = slide.Shapes.AddPicture(
                FileName=tmp_png,
                LinkToFile=False,
                SaveWithDocument=True,
                Left=0,
                Top=0
            )

            # Minimal AltText metadata
            meta = {
                "type": "g2_map",
                "current_pos_um": {"x": Xum, "y": Yum, "z": Zum},
                "site_from_g2":   {"x": site[0], "y": site[1], "z": site[2]},
                "tif_path":       tif_path,
                "center_um":      {"x": center_um[0], "y": center_um[1], "z": center_um[2]},
            }
            shape.AlternativeText = json.dumps(meta, separators=(",", ":"))

            print(f"add map: added slide #{slide.SlideIndex} from '{tif_path}'")

        except Exception as e:
            print(f"add map failed: {e}")


# Wrapper function
dispatcher = CommandDispatcher()

def run(command: str, record_history: bool = True):
    dispatcher.run(command, record_history)


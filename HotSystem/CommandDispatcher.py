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
import Utils.display_all_z_slices_with_slider as disp
from PIL import ImageGrab, Image
import io
import win32com.client
import pythoncom
import json
import tempfile
import os
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

# Textbox: Alt + n X
# Font color: Alt + H F C
# Paste as pic: Alt + H V U

CONFIG_PATH = r"C:\WC\HotSystem\SystemConfig\xml_configs\system_info.xml"

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
        # Map command verbs to handler methods
        # self.proEM_mode = True
        self._last_fq_idx = None
        self.proEM_mode = False
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
            "disable":           self.handle_disable_pharos,
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
        }
        # Register exit hook
        atexit.register(self.savehistory_on_exit)

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

    def savehistory_on_exit(self):
        try:
            self.handle_save_history()
            print("Command history saved on exit.")
        except Exception as e:
            print(f"Failed to save history on exit: {e}")

    # --- Handlers (methods) ---
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
                if reverse: cam.StartLive(); print("Camera started."); p.opx.btnStartCounterLive()
                else:       cam.StopLive();  print("Camera stopped.")
            for flipper in getattr(p, "mff_101_gui", []):
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

    def handle_start_counter(self, arg):
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

            # === HRS_500 GUI with ProEM experiment ===
            if name in ("hrs proem", "hrs_proem", "hrsproem", "proem"):
                import HW_GUI.GUI_HRS_500 as gui_HRS500
                importlib.reload(gui_HRS500)

                PROEM_LFE = r"C:\Users\Femto\Work Folders\Documents\LightField\Experiments\ProEM_shai.lfe"

                # Try to preserve the current window position/size if it exists
                pos, size = [60, 60], [1200, 800]
                if hasattr(p, "hrs_500_gui") and p.hrs_500_gui:
                    try:
                        pos = dpg.get_item_pos(p.hrs_500_gui.window_tag)
                        size = dpg.get_item_rect_size(p.hrs_500_gui.window_tag)
                        p.hrs_500_gui.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old HRS_500 GUI removal failed (ProEM): {e}")

                # (Re)create the LightField spectrometer specifically with the ProEM experiment
                try:
                    devs = hw_devices.HW_devices()

                    # Cleanly disconnect the existing device if possible
                    try:
                        if getattr(devs, "hrs_500", None) and hasattr(devs.hrs_500, "disconnect"):
                            devs.hrs_500.disconnect()
                    except Exception as e:
                        print(f"Warning: could not disconnect previous HRS_500 device: {e}")

                    # New instance with the ProEM experiment path
                    devs.hrs_500 = LightFieldSpectrometer(
                        visible=True,
                        file_path=PROEM_LFE
                    )
                    devs.hrs_500.connect()
                except Exception as e:
                    print(f"Failed to initialize HRS_500 with ProEM experiment: {e}")
                    raise

                # Rebuild the GUI using the (re)initialized device
                p.hrs_500_gui = gui_HRS500.GUI_HRS500(devs.hrs_500)

                # Rebuild the “bring window” button
                if dpg.does_item_exist("HRS_500_button"):
                    dpg.delete_item("HRS_500_button")
                p.create_bring_window_button(
                    p.hrs_500_gui.window_tag, button_label="Spectrometer (ProEM)",
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

                print("Reloaded HW_GUI.GUI_HRS500 with ProEM experiment and recreated Spectrometer GUI.")
                return

            # === HRS_500 GUI ===
            if name in ("hrs", "hrs500", "hrs_500"):
                import HW_GUI.GUI_HRS_500 as gui_HRS500
                importlib.reload(gui_HRS500)

                EXP3_LFE = r"C:\Users\Femto\Work Folders\Documents\LightField\Experiments\Experiment3.lfe"

                # Try to preserve the current window position/size if it exists
                pos, size = [60, 60], [1200, 800]
                if hasattr(p, "hrs_500_gui") and p.hrs_500_gui:
                    try:
                        pos = dpg.get_item_pos(p.hrs_500_gui.window_tag)
                        size = dpg.get_item_rect_size(p.hrs_500_gui.window_tag)
                        p.hrs_500_gui.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old HRS_500 GUI removal failed: {e}")

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
                import Utils.display_all_z_slices_with_slider as disp_mod
                importlib.reload(disp_mod)
                p.display_all_z_slices = disp_mod.display_all_z_slices
                print("Reloaded display_all_z_slices from display_all_z_slices_with_slider.py.")
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
        """Save last_z and move to 11500."""
        p = self.get_parent()
        try:
            curr = p.smaractGUI.dev.AxesPositions[2]*1e-6
            p.smaractGUI.last_z_value = curr
            dpg.set_value("mcs_ch2_ABS",11500.0)
            p.smaractGUI.move_absolute(None,None,2)
            print(f"Saved Z={curr:.2f}, moved to 11500")
        except Exception as e:
            print(f"down failed: {e}")

    def handle_up(self, arg):
        """Move Z to last saved value; 'up ?' prints it; 'up 1' or no saved -> Z=600."""
        try:
            p = self.get_parent()
            s = (arg or "").strip()
            last = getattr(p.smaractGUI, "last_z_value", None)

            if s == "?":
                print("up? -> no last Z saved" if last is None else f"up? -> last Z = {last:.2f}")
                return

            if s == "1" or last is None:
                z = 600.0
                dpg.set_value("mcs_ch2_ABS", z)
                p.smaractGUI.move_absolute(None, None, 2)
                print(f"Moved Z to {z:.2f}")
                return

            dpg.set_value("mcs_ch2_ABS", float(last))
            p.smaractGUI.move_absolute(None, None, 2)
            print(f"Moved to last Z = {last:.2f}")
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

        Notes:
          • Exposure time is given in seconds (float).
          • 'st' = run handle_set_xyz first, then use clipboard text as experiment note.
          • Last saved CSV is renamed with experiment note appended.
          • New file path is copied to clipboard after acquisition.
        """
        run("cn")
        threading.Thread(target=self._acquire_spectrum_worker, args=(arg,), daemon=True).start()

    def _acquire_spectrum_worker(self, arg):
        """Actual spectrum acquisition logic, run in a background thread."""
        p = self.get_parent()
        is_st=False

        # --- SPC done event ---
        evt = getattr(self, "_spc_done_evt", None)
        if not isinstance(evt, threading.Event):
            evt = threading.Event()
            self._spc_done_evt = evt
        evt.clear()

        # --- NEW: special 'st' pre-sequence ---
        try:
            tokens = (arg or "").strip().split()
            is_st = len(tokens) > 0 and tokens[0].lower() == "st"
            work_tokens = tokens[1:] if is_st else tokens
            no_preview = "!" in work_tokens
            rest_arg = " ".join(work_tokens)  # may include '!'
            rest_arg_clean = " ".join(t for t in work_tokens if t != "!").strip()

            if is_st:
                # 1) set XYZ first
                try:
                    self.handle_set_xyz("")  # pass args if you need (e.g., current cursor, etc.)
                    print("handle_set_xyz done.")
                except Exception as e:
                    print(f"handle_set_xyz failed: {e}")

                # 2) paste clipboard into expNotes
                try:
                    clip = (pyperclip.paste() or "").strip()
                    if clip:
                        # set (overwrite) note with clipboard text
                        self.handle_update_note(clip)
                        print("Experiment note updated from clipboard.")
                    else:
                        print("Clipboard empty — note not updated.")
                except Exception as e:
                    print(f"Could not read clipboard / update note: {e}")
        except Exception as e:
            print(f"'st' pre-sequence failed: {e}")
        # --- end NEW ---

        self.handle_mark(rest_arg_clean)
        time.sleep(0.1)

        # 0) Try to set exposure time
        secs_str = rest_arg_clean
        if secs_str:
            try:
                secs = float(secs_str) * 1000
                p.hrs_500_gui.dev.set_value(CameraSettings.ShutterTimingExposureTime, secs)
                print(f"Integration time set to {secs}s")
            except Exception as e:
                print(f"Could not set integration time to '{secs_str}': {e}")

        # 1) Stop camera & flippers
        try:
            self.handle_toggle_sc(False)
        except Exception:
            pass

        # 2) Acquire spectrum
        # if hasattr(p.opx, "spc") and hasattr(p.opx.spc, "acquire_Data") and not self.proEM_mode:
        #     try:
        #         p.hrs_500_gui.acquire_callback()
        #     except Exception as e:
        #         print(f"acquire_callback failed: {e}")
        #         return
        # else:
        if hasattr(p, "hrs_500_gui"): # and self.proEM_mode: # proEM mode
            p.hrs_500_gui.dev._exp.Stop()
            self.handle_set_xyz("")
            fn=__import__('pyperclip').paste()
            # Clean clipboard -> base name
            s = (fn or "").strip().strip('"').strip("'")
            s = s.replace("\r", "").replace("\n", " ")
            pt = Path(s)
            base = pt.stem if pt.suffix else os.path.basename(s)
            base = re.sub(r'[<>:"/\\|?*]', "_", base)[:120]  # keep it short & legal
            p.hrs_500_gui.dev.set_filename(base)
            while getattr(p.hrs_500_gui.dev._exp, "IsUpdating", False):
                time.sleep(0.1)
            p.hrs_500_gui.acquire_callback()
            # p.hrs_500_gui.dev.acquire_Data()
            time.sleep(0.5)
            if getattr(p.hrs_500_gui.dev._exp, "IsReadyToRun", True):
                p.hrs_500_gui.dev.set_value(CameraSettings.ShutterTimingExposureTime, 1000.0)
                while getattr(p.hrs_500_gui.dev._exp, "IsUpdating", False):
                    time.sleep(0.1)
                if not no_preview and self.proEM_mode:
                    p.hrs_500_gui.dev._exp.Preview()
        else:
            print("Parent OPX or SPC not available.")

        if self.proEM_mode:
            return

        # 3) Locate saved CSV
        fp = getattr(p.hrs_500_gui.dev, "last_saved_csv", None)
        if not fp or not os.path.isfile(fp):
            save_dir = getattr(p.hrs_500_gui.dev, "save_directory", None)
            if not save_dir:
                print("No CSV found to rename.")
                return
            matches = glob.glob(os.path.join(save_dir, "*.csv"))
            if not matches:
                print("No CSV found to rename.")
                return
            fp = max(matches, key=os.path.getmtime)

        # 4) Rename with notes
        notes = getattr(p.opx, "expNotes", "")
        dirname, basename = os.path.split(fp)
        base, ext = os.path.splitext(basename)
        if notes:
            new_name = f"{base}_{notes}{ext}"
            new_fp = os.path.join(dirname, new_name)
            try:
                os.replace(fp, new_fp)
                print(f"Renamed SPC file → {new_fp}")
                pyperclip.copy(new_fp)
                p.hrs_500_gui.dev.last_saved_csv = new_fp  # Update path
            except Exception as e:
                print(f"Failed to rename SPC file: {e}")

        # --- NEW: If in 'st' mode, run "disp tif" at the end ---
        if is_st:
            try:
                self.handle_display_slices("tif")
                print('Executed: disp tif')
            except Exception as e:
                print(f'Failed to run "disp tif": {e}')

        run("wait 2000;a")
        try:
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
        """Set or append to experiment notes."""
        p = self.get_parent()
        raw = arg.strip()
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
                subprocess.Popen([sys.executable, "Utils/display_all_z_slices_with_slider.py", str(latest)])
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
                subprocess.Popen([sys.executable, "Utils/display_all_z_slices_with_slider.py", str(target)])
                return


            else:
                # Load from file
                fn = self.get_parent().opx.last_loaded_file
                resolved_fn = _resolve_existing_scan_file(fn)
                if not resolved_fn:
                    print("No last loaded file found or could not resolve it. "
                          "Check 'MoveSubfolderInput' and that the file exists under the 'scan' folder.")
                    return
                subprocess.Popen([sys.executable, "Utils/display_all_z_slices_with_slider.py", resolved_fn])
                # subprocess.Popen(["python", "Utils/display_all_z_slices_with_slider.py", fn])
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

    def _move_delta(self, axis, arg):
        p=self.get_parent()
        try:
            amount=float(arg)*1e6
            p.smaractGUI.dev.MoveRelative(axis, int(amount))
            print(f"Axis {axis} moved by {amount*1e-6:.2f} um")
        except:
            print(f"move{axis} failed.")

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
        lf_gui = getattr(p, "hrs_500_gui", None)
        if lf_gui is None:
            print("lf inf: hrs_500_gui not available.")
            return

        tokens = (arg or "").strip().lower().split()
        if not tokens:
            print("lf: missing subcommand (try: 'lf roi' or 'lf inf').")
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
        """
        import json, os
        sub = (arg or "").strip()
        if not sub:
            print(
                "Usage: show config | show cmd | show <opx|disp|awg|cld|cob|femto|hrs|kdc|smaract|zelux|app> | show wrap <cld|zelux|cob|smaract|hrs> | show map clib")
            return

        toks = sub.split()
        key = toks[0].lower()
        base_dir = _dispatcher_base_dir(self)

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
                print("Usage: show wrap <cld|zelux|cob|smaract>")
                return
            which = toks[1].lower()
            if which not in WRAP_MAP:
                print(f"[show] Unknown wrap '{which}'. Options: {', '.join(WRAP_MAP.keys())}")
                return
            mod_name, fallback_rel = WRAP_MAP[which]
            _open_module_or_fallback(mod_name, fallback_rel, base_dir)
            return

        # ----- show map clib (or calib) -----
        if key == "map":
            if len(toks) >= 2 and toks[1].lower() in ("calibration", "calib"):
                _open_path(os.path.join(base_dir, r"Utils\map_calibration.json"))
                return
            print("Usage: show map clib")
            return

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

        sym carrier X,Y      – set carrier (grating periods across aperture)
        sym car X,Y          – alias
        sym c X,Y            – alias
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
            npys = glob.glob(os.path.join(ZERO_DIR, "*.npy"))
            if not npys:
                print(f"No zero-carrier phases found in {ZERO_DIR}. Run 'sym flattop ... zero' first.")
                return
            npys.sort(key=os.path.getmtime, reverse=True)

            def _print_list():
                print(f"Zero files in {ZERO_DIR} (newest first):")
                for i, pth in enumerate(npys, start=1):
                    ts = os.path.getmtime(pth)
                    print(
                        f"  {i:2d}: {os.path.basename(pth)}  (mtime={time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))})")

            rest_str = (rest or "").strip()
            if rest_str.lower() == "list":
                _print_list()
                return

            # --- 1) Extract carrier at the END of the string: "... X,Y" or "... X Y"
            mcar = re.search(r"(-?\d+(?:\.\d+)?)[,\s]+(-?\d+(?:\.\d+)?)\s*$", rest_str)
            if not mcar:
                print("Usage:\n"
                      "  sym zcar list\n"
                      "  sym zcar <idx>  X,Y\n"
                      "  sym zcar name=<substr>  X,Y\n"
                      "  sym zcar X,Y   (latest)")
                return
            cx, cy = float(mcar.group(1)), float(mcar.group(2))
            # Remove the carrier tail; the remaining text (if any) is the selector
            sel_part = rest_str[:mcar.start()].strip()

            # --- 2) Optional selector: name=<substr> or leading integer index
            sel_name = None
            sel_idx = None

            mname = re.search(r"(?i)\bname\s*=\s*([^\s,]+)", sel_part)
            if mname:
                sel_name = mname.group(1)
            else:
                mind = re.match(r"\s*(\d+)\s*$", sel_part)  # index must be the whole remaining token
                if mind:
                    sel_idx = int(mind.group(1))

            # --- 3) Choose the zero file
            if sel_name:
                low = sel_name.lower()
                chosen = next((p for p in npys if low in os.path.basename(p).lower()), None)
                if chosen is None:
                    print(f"No zero file matching name='{sel_name}'. Try 'sym zcar list'.")
                    return
            elif sel_idx is not None:
                if not (1 <= sel_idx <= len(npys)):
                    print(f"Index out of range (1..{len(npys)}). Try 'sym zcar list'.")
                    return
                chosen = npys[sel_idx - 1]
            else:
                chosen = npys[0]  # latest by default

            # --- 4) Apply carrier with your writer
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

            phase = np.load(chosen).astype(np.float32)  # radians, pre-correction
            cam._write_phase_with_corr(phase, corr_u8, OUT_BMP,
                                       carrier_cmd=(cx, cy), steer_cmd=(0.0, 0.0), settle_s=0.0)
            print(f"Applied carrier ({cx:.3f},{cy:.3f}) to '{os.path.basename(chosen)}' → {OUT_BMP}")
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


# Wrapper function
dispatcher = CommandDispatcher()

def run(command: str, record_history: bool = True):
    dispatcher.run(command, record_history)

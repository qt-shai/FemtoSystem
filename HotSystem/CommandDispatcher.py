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
from Utils.extract_positions import preprocess_image, extract_positions, TESSERACT_CONFIG
from Utils import loadFromCSV
from Utils.export_points import export_points
from Survey_Analysis.Scan_Image_Analysis import ScanImageAnalysis
import HW_wrapper.HW_devices as hw_devices
from HW_GUI.GUI_MFF_101 import GUI_MFF
from Common import *
from PrincetonInstruments.LightField.AddIns import CameraSettings
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
        self.default_graph_size = (None, None)
        self.handlers = {
            # simple commands
            "a":                 self.handle_add_slide,
            "c":                 self.handle_copy_window,
            "cc":                self.handle_screenshot_delayed,
            "hl":                self.handle_hide_legend,
            "mark":              self.handle_mark,
            "unmark":            self.handle_unmark,
            "mv":                self.handle_move_files,
            "clog":              self.handle_clog,
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
            "msg":               self.handle_message,
            "msgclear":          self.handle_message_clear,
            "st":                self.handle_set_xyz,
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
            "startscan":         self.handle_start_scan,
            "dx":                self.handle_set_dx,
            "dy":                self.handle_set_dy,
            "dz":                self.handle_toggle_or_set_dz,
            "d":                 self.handle_set_all_steps,
            "lx":                self.handle_set_Lx,
            "ly":                self.handle_set_Ly,
            "lz":                self.handle_set_Lz,
            "savehistory":       self.handle_save_history,
            "loadhistory":       self.handle_load_history,
            "sv":                self.handle_save_processed_image,
            "show windows":      self.handle_list_windows,
            "show":              self.handle_show_window,
            "hide":              self.handle_hide_window,
            "scpos":             self.handle_copy_scan_position,
            "exp":               self.handle_set_exposure,
            "disp":              self.handle_display_slices,
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
            "scanmv":            self.handle_scanmv,
        }
        # Register exit hook
        atexit.register(self.savehistory_on_exit)

    def get_parent(self):
        return getattr(sys.stdout, "parent", None)

    def run(self, command: str, record_history: bool = True):
        """
        Main entry: accept a single command or ';'-separated list,
        dispatching each verb to the appropriate handler.
        """
        parent = self.get_parent()
        if parent is None:
            print("Warning: run() called but sys.stdout.parent not set.")
            return
        cmd_line = command.strip()
        if not cmd_line:
            dpg.focus_item("OPX Window")
            return
        if not hasattr(parent, "command_history"):
            parent.command_history = []
        if record_history:
            parent.update_command_history(cmd_line)
            parent.history_index = len(parent.command_history)

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
        for seg in segments:
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

                handler = self.handlers.get(key)
                if handler:
                    # 'wait' delays subsequent commands
                    if key=="wait":
                        try:
                            ms = int(arg)
                        except:
                            print("Invalid wait syntax; use wait<ms>")
                            continue
                        rest_cmds = segments[segments.index(seg)+1:]
                        def delayed():
                            time.sleep(ms/1000)
                            for c in rest_cmds:
                                self.run(c)
                        threading.Thread(target=delayed, daemon=True).start()
                        print(f"Waiting {ms}ms before running {rest_cmds}")
                        break
                    handler(arg)
                else:
                    # not a known command → try to recall from history
                    parent = self.get_parent()
                    history = getattr(parent, "command_history", [])
                    # look backwards for the first entry that contains seg, but isn’t exactly seg
                    matches = [
                        cmd for cmd in reversed(history)
                        if seg in cmd and cmd != seg
                    ]
                    if matches:
                        found = matches[0]
                        dpg.set_value("cmd_input", found)
                        dpg.focus_item("cmd_input")
                        print(f"Recalled from history: {found}")
                        return
                    else:
                        print(f"Didn't find '{seg}' in history.")
            except Exception:
                traceback.print_exc()
        dpg.focus_item("cmd_input")
        dpg.set_value("cmd_input", "")

    def savehistory_on_exit(self):
        try:
            self.handle_save_history()
            print("Command history saved on exit.")
        except Exception as e:
            print(f"Failed to save history on exit: {e}")

    # --- Handlers (methods) ---
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

    def handle_mark(self, arg):
        """Draw cross+circle at OPX position."""
        try:
            parent = self.get_parent()
            x, y = [p*1e-6 for p in parent.opx.positioner.AxesPositions[:2]]
            tag = "temp_cross_marker"
            for s in ("_h_left","_h_right","_v_top","_v_bottom","_circle"):
                if dpg.does_item_exist(tag+s):
                    dpg.delete_item(tag+s)
            if not dpg.does_item_exist("plot_draw_layer"):
                dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")
            gap, length = 0.5, 3
            # draw lines...
            dpg.draw_line((x-length,y),(x-gap,y),color=(255,0,0,255),thickness=0.3,
                          parent="plot_draw_layer",tag=tag+"_h_left")
            dpg.draw_line((x+gap,y),(x+length,y),color=(255,0,0,255),thickness=0.3,
                          parent="plot_draw_layer",tag=tag+"_h_right")
            dpg.draw_line((x,y-length),(x,y-gap),color=(255,0,0,255),thickness=0.3,
                          parent="plot_draw_layer",tag=tag+"_v_top")
            dpg.draw_line((x,y+gap),(x,y+length),color=(255,0,0,255),thickness=0.3,
                          parent="plot_draw_layer",tag=tag+"_v_bottom")
            dpg.draw_circle(center=(x,y),radius=length,color=(255,0,0,255),
                            thickness=2,parent="plot_draw_layer",tag=tag+"_circle")
            print(f"Marked at X={x:.4f}, Y={y:.4f}")
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
        """Add PPT slide & paste clipboard image with metadata in Alt Text."""
        try:
            # 1) Prepare metadata
            p = self.get_parent()
            scan_dict = self.convert_loaded_csv_to_scan_data(
                scan_out=p.opx.scan_Out,
                Nx=p.opx.N_scan[0],
                Ny=p.opx.N_scan[1],
                Nz=p.opx.N_scan[2],
                startLoc=p.opx.startLoc,
                dL_scan=p.opx.dL_scan,
            )
            # Position in µm
            x, y = [pos * 1e-6 for pos in p.opx.positioner.AxesPositions[:2]]

            # Future value
            try:
                future = dpg.get_value("Femto_FutureInput")
            except Exception:
                future = None

            # Metadata dictionary
            meta = {
                "scan_data": scan_dict,
                "x": x,
                "y": y,
                "future": future,
                "filename": getattr(p.opx, "last_loaded_file", None)
            }

            # Copy image with metadata
            copy_quti_window_to_clipboard(metadata_dict=meta)

            # Initialize COM
            pythoncom.CoInitialize()

            # Connect to PowerPoint
            ppt = win32com.client.Dispatch("PowerPoint.Application")
            if ppt.Presentations.Count == 0:
                raise RuntimeError("No PowerPoint presentations are open!")

            pres = ppt.ActivePresentation
            slide_count = pres.Slides.Count
            new_slide = pres.Slides.Add(slide_count + 1, 12)  # 12 = ppLayoutBlank
            ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)

            # Ensure image is available in clipboard
            img = ImageGrab.grabclipboard()
            if not isinstance(img, Image.Image):
                print("❌ Clipboard does not contain an image.")
                return

            # Paste and embed metadata in Alt Text
            shapes = new_slide.Shapes.Paste()
            if shapes.Count > 0:
                shape = shapes[0]
                shape.AlternativeText = json.dumps(meta, separators=(",", ":"))

            print(f"Added slide #{new_slide.SlideIndex} and pasted image with metadata.")
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
            subprocess.run([sys.executable,"clog.py",arg.strip().lower()])
        except Exception as e:
            print(f"clog failed: {e}")

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
        """Load window positions profile."""
        p = self.get_parent()
        raw = arg.strip()
        # default to "local", but treat "r" as "remote"
        profile = "local" if not raw else ("remote" if raw.lower() == "r" else raw)
        # only attempt load if smaractGUI exists
        if hasattr(p, "smaractGUI"):
            try:
                p.smaractGUI.load_pos(profile)
                print("Loaded positions.")
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
        """Reload modules or specific GUI components exactly as before."""
        p = self.get_parent()
        try:
            import importlib
            raw_name = arg.strip()
            name = raw_name.lower()

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

            # === HRS_500 GUI ===
            if name in ("hrs", "hrs500", "hrs_500"):
                import HW_GUI.GUI_HRS_500 as gui_HRS500
                importlib.reload(gui_HRS500)
                if hasattr(p, "hrs_500_gui") and p.hrs_500_gui:
                    try:
                        pos = dpg.get_item_pos(p.hrs_500_gui.window_tag)
                        size = dpg.get_item_rect_size(p.hrs_500_gui.window_tag)
                        p.hrs_500_gui.DeleteMainWindow()
                    except Exception as e:
                        print(f"Old HRS_500 GUI removal failed: {e}")
                p.hrs_500_gui = gui_HRS500.GUI_HRS500(hw_devices.HW_devices().hrs_500)
                if dpg.does_item_exist("HRS_500_button"):
                    dpg.delete_item("HRS_500_button")
                p.create_bring_window_button(
                    p.hrs_500_gui.window_tag, button_label="Spectrometer",
                    tag="HRS_500_button", parent="focus_group"
                )
                p.active_instrument_list.append(p.hrs_500_gui.window_tag)
                try:
                    dpg.set_item_pos(p.hrs_500_gui.window_tag, pos)
                    dpg.set_item_width(p.hrs_500_gui.window_tag, size[0])
                    dpg.set_item_height(p.hrs_500_gui.window_tag, size[1])
                except:
                    pass
                print("Reloaded HW_GUI.GUI_HRS500 and recreated Spectrometer GUI.")
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
            dz_val = None
            try:
                dz_val = int(arg)
            except ValueError:
                dz_val = None
            if dz_val is not None:
                print(f"Setting dz to {dz_val} and enabling limit.")
                p.opx.toggle_limit(app_data=None, user_data=True)
                p.opx.Update_dZ_Scan(app_data=None, user_data=dz_val)
            # 3) Read last_scan_dir
            try:
                with open("last_scan_dir.txt", "r") as f:
                    last_scan_dir = f.read().strip()
                    print(f"Loaded last scan dir: {last_scan_dir}")
            except FileNotFoundError:
                print("No last_scan_dir.txt found.")
                return
            # 4) Validate directory
            if not last_scan_dir or not os.path.isdir(last_scan_dir):
                print(f"Invalid last scan dir: {last_scan_dir}")
                return
            # 5) Find all CSV files
            csv_files = [
                os.path.join(last_scan_dir, fn)
                for fn in os.listdir(last_scan_dir)
                if fn.lower().endswith(".csv")
            ]
            if not csv_files:
                print("No CSV files found in last scan directory.")
                return
            # 6) Pick newest and plot
            csv_files.sort(key=os.path.getmtime, reverse=True)
            fn = None
            for candidate in csv_files:
                if not candidate.lower().endswith("_pulse_data.csv"):
                    fn = candidate
                    break
            if fn is None:
                print("No non‑pulse_data CSV files found.")
                return
            print(f"Loading most recent CSV: {fn}")

            p.opx.btnLoadScan(app_data=fn)

            print(f"Loaded and plotted: {fn}")

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
        """Fill/move/store query points (fq)."""
        p = self.get_parent()
        try:
            idx = int(arg) if arg.isdigit() else None
            if idx:
                # move to stored idx or store if none
                pts = getattr(p, "saved_query_points", [])
                found = [pt for pt in pts if pt[0]==idx]
                if found:
                    _,x,y,z = found[0]
                    for ax, val in enumerate((x,y,z)):
                        dpg.set_value(f"mcs_ch{ax}_ABS", val)
                        p.smaractGUI.move_absolute(None,None,ax)
                    print(f"Moved to point #{idx}")
                else:
                    pos = [v*1e-6 for v in p.opx.positioner.AxesPositions]
                    pts.append((idx, *pos))
                    p.saved_query_points = pts
                    print(f"Stored point #{idx}: {pos}")
            else:
                # regular fill+move
                p.opx.fill_moveabs_from_query()
                for ax in range(2):
                    p.smaractGUI.move_absolute(None,None,ax)
                z = p.opx.positioner.AxesPositions[2]*1e-6
                dpg.set_value(f"mcs_ch2_ABS", z)
                x,y = [dpg.get_value(f"mcs_ch{ax}_ABS") for ax in range(2)]
                pts = getattr(p,"saved_query_points",[])
                new_idx = pts[-1][0]+1 if pts else 1
                pts.append((new_idx,x,y,z))
                p.saved_query_points = pts
                print(f"Stored point #{new_idx}: {(x,y,z)}")
            self.handle_list_points(arg)
        except Exception as e:
            print(f"fq failed: {e}")

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
                    dpg.configure_item(dot_tag, center=(x, y))
                else:
                    dpg.draw_circle(
                        center=(x, y),
                        radius=0.15,
                        color=(255, 0, 0, 255),
                        fill=(0, 0, 0, 255),
                        parent="plot_draw_layer",
                        tag=dot_tag
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

    def handle_acquire_spectrum(self, arg):
        """Launch threaded spectrum acquisition process."""
        threading.Thread(target=self._acquire_spectrum_worker, args=(arg,), daemon=True).start()

    def _acquire_spectrum_worker(self, arg):
        """Actual spectrum acquisition logic, run in a background thread."""
        p = self.get_parent()
        self.handle_mark(arg)
        time.sleep(0.1)

        # 0) Try to set exposure time
        secs_str = arg.strip()
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
        if hasattr(p.opx, "spc") and hasattr(p.opx.spc, "acquire_Data"):
            try:
                p.hrs_500_gui.acquire_callback()
            except Exception as e:
                print(f"acquire_callback failed: {e}")
                return
        else:
            print("Parent OPX or SPC not available.")
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
        """Stop OPX scan."""
        p=self.get_parent()
        p.opx.btnStop()
        print("Scan stopped.")

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
        """Start OPX scan."""
        p=self.get_parent()
        try:
            p.smaractGUI.fill_current_position_to_moveabs()
            self.handle_toggle_sc(reverse=False)
            p.opx.btnStartScan()
            print("Scan started.")
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
        """Save command history to file."""
        p=self.get_parent()
        try:
            with open("history.txt","w") as f:
                for cmd in p.command_history:
                    f.write(cmd+"\n")
            print("History saved.")
        except:
            print("savehistory failed.")

    def handle_load_history(self, arg):
        """Load command history from file."""
        p=self.get_parent()
        try:
            with open("history.txt") as f:
                p.command_history = [l.strip() for l in f]
            print("History loaded.")
        except:
            print("loadhistory failed.")

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
        """Run Z-slices viewer. Use 'disp clip' to read scan_data from clipboard image's Alt Text (PowerPoint)."""
        try:
            fn = None
            if arg.strip() == "clip":
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
                except Exception as e:
                    print(f"Failed to parse Alt Text metadata: {e}")
                    return
                # 3. Launch display
                disp.display_all_z_slices(data=fn)
            else:
                # Load from file
                fn = self.get_parent().opx.last_loaded_file
                if not fn or not os.path.isfile(fn):
                    print("No last loaded file found.")
                    return
                subprocess.Popen(["python", "Utils/display_all_z_slices_with_slider.py", fn])
                print("Displaying slices from file.")

        except Exception as e:
            print(f"disp failed: {e}")

    def handle_set_integration_time(self, arg):
        """Set integration time and append note."""
        p=self.get_parent()
        try:
            ms=int(arg)
            p.opx.UpdateCounterIntegrationTime(user_data=ms)
            self.handle_update_note(f"!Int {ms} ms")
        except:
            print("int failed.")

    def handle_nextrun(self, arg):
        """Enable or disable HRS_500 in system_info.xml—will always find & toggle the full block."""
        action = arg
        xml_path = os.path.join("SystemConfig", "xml_configs", "system_info.xml")
        try:
            text = open(xml_path, "r").read()
            if action in ("hrs", "hrs on"):
                # Uncomment HRS_500 block
                new_text = re.sub(
                    r'<!--\s*(<Device>\s*<Instrument>HRS_500</Instrument>[\s\S]*?</Device>)\s*-->',
                    r'\1', text, flags=re.DOTALL
                )
                open(xml_path, "w").write(new_text)
                print("HRS_500 enabled for next run.")
            elif action in ("!hrs", "hrs off", "hrs off"):
                # Comment HRS_500 block
                new_text = re.sub(
                    r'(<Device>\s*<Instrument>HRS_500</Instrument>[\s\S]*?</Device>)',
                    r'<!--\1-->', text, flags=re.DOTALL
                )
                open(xml_path, "w").write(new_text)
                print("HRS_500 disabled for next run.")
            else:
                print(f"Unknown action for nextrun: '{action}'. Use 'nextrun hrs' or 'nextrun !hrs'.")
        except Exception as e:
            print(f"Failed to process 'nextrun': {e}")

    def handle_help(self, arg):
        """Show help for commands in a larger window with search."""
        # 1) Build the full help text
        lines = []
        for k, fn in self.handlers.items():
            doc = fn.__doc__.strip().splitlines()[0] if fn.__doc__ else ""
            lines.append(f"{k:<12} - {doc}")
        full_help = "\n".join(lines)

        # 2) Remove any existing help window
        if dpg.does_item_exist("help_window"):
            dpg.delete_item("help_window")

        # 3) Create the help window
        with dpg.window(tag="help_window", label="Command Help", width=600, height=400, autosize=False):
            # --- Search bar & button in a horizontal group ---
            with dpg.group(horizontal=True):
                dpg.add_input_text(
                    tag="help_search_input",
                    label="",
                    width=200,
                    hint="Type part of a command and press Enter",
                    on_enter=True,
                    callback=lambda s, a, u: self._help_search()
                )
                dpg.add_button(
                    label="Lookup",
                    callback=lambda s, a, u: self._help_search()
                )

            # --- Main help text area ---
            dpg.add_input_text(
                tag="help_text",
                default_value=full_help,
                multiline=True,
                readonly=True,
                width=-1,
                height=-1
            )

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
            for cmd in remaining:
                try:
                    # invoke your dispatcher’s run() on each command
                    self.run(cmd)
                except Exception as e:
                    print(f"Error running '{cmd}': {e}")

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

    def handle_ntrack(self, arg):
        """Get or set N_tracking_search."""
        p=self.get_parent()
        try:
            if arg:
                p.opx.UpdateN_tracking_search(user_data=int(arg))
            else:
                print(f"N_tracking_search = {p.opx.N_tracking_search}")
        except:
            traceback.print_exc()
            print("ntrack failed.")

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
        """Run FindFocus (channel 2); if arg=='plot', also pop up a Signal vs Z graph."""
        p = self.get_parent()
        do_plot = arg.strip().lower() == "plot"

        def worker():
            try:
                # 1) Kick off live counting
                p.opx.btnStartCounterLive()
                time.sleep(1)

                # 2) Do the focus scan
                p.opx.FindFocus()

                # 3) Optionally plot
                if do_plot:
                    # Directly call the UI method
                    self._focus_plot(p.opx.coordinate, p.opx.track_X)
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


# Wrapper function
dispatcher = CommandDispatcher()

def run(command: str, record_history: bool = True):
    dispatcher.run(command, record_history)

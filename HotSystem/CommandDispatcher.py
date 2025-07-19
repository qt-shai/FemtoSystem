import sys
import os
import re
import threading
import time
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


class CommandDispatcher:
    """
    Wraps all command handlers into methods and dispatches via a dictionary lookup,
    eliminating any long if/elif chains.
    """
    def __init__(self):
        # Map command verbs to handler methods
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
            "det":               self.handle_detect_and_draw,
            "fmax":              self.handle_fmax,
            "ntrack":            self.handle_ntrack,
        }

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
                    # fallback: try eval
                    try:
                        res = eval(seg, {"__builtins__": {}})
                        print(f"{seg} = {res}")
                    except:
                        print(f"Unknown command: {seg}")
            except Exception:
                traceback.print_exc()
        dpg.focus_item("cmd_input")

    # --- Handlers (methods) ---
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
        """Add PPT slide & paste clipboard image."""
        try:
            # 1) copy the QuTi SW window into the clipboard
            copy_quti_window_to_clipboard()

            # 2) run the slide‑adding script
            script = os.path.join("Utils", "add_slide_paste_clipboard.py")
            subprocess.run([sys.executable, script], check=True)

            print("Added slide & pasted clipboard image to PowerPoint.")
        except Exception as e:
            print(f"Could not add slide: {e}")

    def handle_copy_window(self, arg):
        """Copy QuTi SW window to clipboard."""
        try:
            copy_quti_window_to_clipboard()
            print("Window copied to clipboard.")
        except Exception as e:
            print(f"Copy window failed: {e}")

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
        """Copy filename from last console message."""
        import pyperclip
        msgs = getattr(sys.stdout, "messages", [])
        if not msgs:
            print("No messages to parse.")
            return
        last = msgs[-1]
        m = re.findall(r'(?:[A-Za-z]:[\\/]|[/\\]).+?\.\w+', last)
        path = m[-1] if m else None
        if not path:
            for tok in last.split():
                if '.' in tok:
                    path = tok.strip('",;'); break
        if path:
            fn = os.path.basename(path)
            pyperclip.copy(fn)
            print(f"Filename copied: {fn}")
        else:
            print("No filepath found.")

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
                y_val = base_y + idx * 2
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
            fn = csv_files[0]
            print(f"Loading most recent CSV: {fn}")
            data = loadFromCSV(fn)
            p.opx.Plot_data(data, True)
            p.opx.last_loaded_file = fn
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
                for ax in range(3):
                    p.smaractGUI.move_absolute(None,None,ax)
                x,y,z = [dpg.get_value(f"mcs_ch{ax}_ABS") for ax in range(3)]
                pts = getattr(p,"saved_query_points",[])
                new_idx = pts[-1][0]+1 if pts else 1
                pts.append((new_idx,x,y,z))
                p.saved_query_points = pts
                print(f"Stored point #{new_idx}: {(x,y,z)}")
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

    def handle_list_points(self, arg):
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
                    dpg.configure_item(annot_tag, pos=(x, y), text=f"{index}")
                else:
                    dpg.draw_text(
                        pos=(x, y),
                        text=f"{index}",
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
        """Load points from file."""
        p = self.get_parent()
        try:
            with open("saved_query_points.txt","r") as f:
                p.saved_query_points=[tuple(map(float,line.strip().split(","))) for line in f]
            print("Points loaded.")
        except Exception as e:
            print(f"loadlist failed: {e}")

    def handle_generate_list(self, arg):
        """Generate point file from CSV and load if small."""
        p = self.get_parent()
        try:
            csv_file = p.opx.last_loaded_file
            out = export_points(csv_file)
            size = sum(1 for _ in open(out))
            print(f"Generated {out} ({size} lines).")
            if size<1000:
                self.handle_load_list("")
        except Exception as e:
            print(f"genlist failed: {e}")

    def handle_acquire_spectrum(self, arg):
        """Acquire HRS500 spectrum and rename with notes."""
        p = self.get_parent()
        import glob, os
        # 1) Stop camera & flippers
        try:
            self.handle_toggle_sc(False)
        except Exception:
            pass
        # 2) Acquire data
        if hasattr(p.opx, "spc") and hasattr(p.opx.spc, "acquire_Data"):
            p.opx.spc.acquire_Data()
        else:
            print("Parent OPX or SPC not available.")
            return
        # 3) Locate CSV file
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
        # 4) Rename file with notes
        notes = getattr(p.opx, "expNotes", "")
        dirname, basename = os.path.split(fp)
        base, ext = os.path.splitext(basename)
        if notes:
            new_name = f"{base}_{notes}{ext}"
            new_fp = os.path.join(dirname, new_name)
            try:
                os.replace(fp, new_fp)
                print(f"Renamed SPC file → {new_fp}")
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
        """Parse future pulses input, update widgets, and calculate femto‐pulse steps."""
        p = self.get_parent()
        future_args = arg.strip()
        # 1) Syntax check
        if not future_args:
            print("Syntax: future<start:step:end,percent>xN")
            return
        # 2) Bail out if user wants to cancel (leading '!')
        if future_args.startswith("!"):
            return
        # 3) Must have femto GUI input tag
        tag = getattr(p.femto_gui, "future_input_tag", None)
        if not (hasattr(p, "femto_gui") and tag):
            print("Femto GUI or input tag not available.")
            return
        # 4) Write the raw input string into the future‐input widget
        dpg.set_value(tag, future_args)
        # 5) Split off the attenuation part, if present
        parts = future_args.split(",", 1)
        range_part = parts[0].strip()
        att_value = None
        pulse_count = None
        if len(parts) > 1:
            att_part = parts[1].strip()
            # detect “xN” suffix (pulse count)
            if "x" in att_part:
                att_str, x_part = att_part.split("x", 1)
                att_value = float(att_str.rstrip("%"))
                pulse_count = int(x_part)
            else:
                att_value = float(att_part.rstrip("%"))
            # apply attenuator
            if dpg.does_item_exist("femto_attenuator"):
                dpg.set_value("femto_attenuator", att_value)
                print(f"Attenuator set to {att_value}%")
                try:
                    p.opx.pharos.setBasicTargetAttenuatorPercentage(att_value)
                except Exception as e:
                    print(f"Failed to set Pharos attenuator: {e}")
            else:
                print("Attenuator input widget not found.")
        # 6) Parse and apply HWP increment
        try:
            start, step, end = [float(x) for x in range_part.split(":")]
            if dpg.does_item_exist("femto_increment_hwp"):
                dpg.set_value("femto_increment_hwp", step)
                print(f"HWPInc set to {step}")
            else:
                print("HWPInc input widget not found.")
        except Exception:
            print("Invalid range format, expected start:step:end")
        # 7) If pulse_count was given, set anneal params
        if pulse_count is not None:
            if dpg.does_item_exist("femto_anneal_pulse_count"):
                dpg.set_value("femto_anneal_pulse_count", pulse_count - 1)
                print(f"nPlsAnn set to {pulse_count - 1}")
            if dpg.does_item_exist("femto_increment_hwp_anneal"):
                val = 0.01 if pulse_count > 1 else 0.0
                dpg.set_value("femto_increment_hwp_anneal", val)
                print(f"HWPAnn set to {val}")
        # 8) Finally call the calculate_future logic
        try:
            Ly = p.femto_gui.calculate_future(sender=None, app_data=None, user_data=None)
            print(f"Future calculation done for input: {future_args}")
            # 9) Update scan settings if Ly valid
            if Ly and dpg.does_item_exist("inInt_Ly_scan") and Ly > 0:
                dpg.set_value("inInt_Ly_scan", int(Ly))
                p.opx.Update_Ly_Scan(user_data=int(Ly))
                print(f"Ly set to {int(Ly)} nm in scan settings.")
                p.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                p.opx.Update_dY_Scan("inInt_dy_scan", 2000)
            else:
                print("inInt_Ly_scan not found or Ly = 0.")
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

    def handle_prepare_for_scan(self,arg):
        """Stop camera live view & retract flippers."""
        self.handle_toggle_sc(reverse=False)

    def handle_start_camera(selfself,arg):
        """Start camera live view & extend flippers."""
        self.handle_toggle_sc(reverse=True)

    def handle_stop_scan(self, arg):
        """Stop OPX scan."""
        p=self.get_parent()
        p.opx.btnStop()
        print("Scan stopped.")

    def handle_set_angle(self, arg):
        """Set HWP angle."""
        p=self.get_parent()
        try:
            ang=float(arg)
            p.opx.set_hwp_angle(ang)
            if hasattr(p, "kdc_101_gui"):
                p.kdc_101_gui.read_current_angle()
            print(f"HWP angle command: moved to {ang:.2f}°")
        except:
            print("angle failed.")

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

    def handle_save_history(self, arg):
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
        """Run Z-slices viewer."""
        try:
            fn=self.get_parent().opx.last_loaded_file
            subprocess.Popen(["python","Utils/display_all_z_slices_with_slider.py",fn])
            print("Displaying slices.")
        except:
            print("disp failed.")

    def handle_set_integration_time(self, arg):
        """Set integration time and append note."""
        p=self.get_parent()
        try:
            ms=int(arg)
            p.opx.UpdateCounterIntegrationTime(user_data=ms)
            self.handle_note(f"!Int {ms} ms")
        except:
            print("int failed.")

    def handle_nextrun(self, arg):
        """Enable/disable HRS_500 in system_info.xml."""
        try:
            path=os.path.join("SystemConfig","xml_configs","system_info.xml")
            txt=open(path).read()
            if arg.strip().lower() in ("hrs","hrs on"):
                new=re.sub(r'<!--(<Device>.*?HRS_500.*?</Device>)-->',r'\1',txt,flags=re.DOTALL)
            else:
                new=re.sub(r'(<Device>.*?HRS_500.*?</Device>)',r'<!--\1-->',txt,flags=re.DOTALL)
            open(path,"w").write(new)
            print("nextrun applied.")
        except:
            print("nextrun failed.")

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
        """Delay subsequent commands (handled in run())."""
        print(f"wait command scheduling.")

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
            d=float(arg)
            cur=dpg.get_value(f"mcs_ch{axis}_ABS")
            n=cur+d
            dpg.set_value(f"mcs_ch{axis}_ABS",n)
            p.smaractGUI.move_absolute(None,None,axis)
            print(f"Axis {axis} moved by {d:.2f} to {n:.2f}")
        except:
            print(f"move{axis} failed.")

    def handle_open_lastdir(self, arg):
        """Copy or open last_scan_dir."""
        import pyperclip
        try:
            d=open("last_scan_dir.txt").read().strip()
            pyperclip.copy(d); print(f"Copied {d}")
            if arg.strip().lower() in ("open","1"):
                subprocess.Popen(f'explorer "{d}"')
        except:
            print("lastdir failed.")

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
            print("ntrack failed.")

# Wrapper function
dispatcher = CommandDispatcher()

def run(command: str, record_history: bool = True):
    dispatcher.run(command, record_history)

import sys

import numpy as np

# import dearpygui.dearpygui as dpg
from Common import *
# import pyperclip, os
from Utils import loadFromCSV
# import importlib
import HW_wrapper.HW_devices as hw_devices
from HW_GUI.GUI_MFF_101 import GUI_MFF
import traceback
import time

# To copy the last message to the clipboard:
# import pyperclip; pyperclip.copy(sys.stdout.messages[-2])

# To copy all messages as a single block:
# import pyperclip; pyperclip.copy("".join(sys.stdout.messages))

# Terminal logged_points.txt commands:
# python clog.py o
# python clog.py e

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

def toggle_sc(reverse=False):
    try:
        parent = getattr(sys.stdout, "parent", None)
        cam = getattr(parent, "cam", None)
        mff = getattr(parent, "mff_101_gui", [])
        if cam:
            if reverse and hasattr(cam, "StartLive"):
                cam.StartLive()
                print("Camera live view started.")
                parent.opx.btnStartCounterLive()
            elif not reverse and hasattr(cam, "StopLive"):
                cam.StopLive()
                print("Camera live view stopped.")
        for flipper in mff:
            slider_tag = f"on_off_slider_{flipper.unique_id}"
            pos = flipper.dev.get_position()
            if (not reverse and pos == 1) or (reverse and pos == 2):
                flipper.on_off_slider_callback(slider_tag, 1 if not reverse else 0)


    except Exception as e:
        print(f"Error in toggle_sc: {e}")

def load_saved_points(parent, file_name="saved_query_points.txt"):
    """Load saved query points from file and populate parent.saved_query_points"""
    if not os.path.exists(file_name):
        print(f"❌ File {file_name} not found.")
        return False

    try:
        with open(file_name, "r") as f:
            lines = f.readlines()
        parent.saved_query_points = []
        for line in lines:
            parts = line.strip().split(",")
            if len(parts) == 3:
                idx = int(parts[0])
                x = float(parts[1])
                y = float(parts[2])
                parent.saved_query_points.append((idx, x, y))
        print(f"✅ Loaded {len(parent.saved_query_points)} points from {file_name}")
        run("list")
        return True
    except Exception as e:
        print(f"❌ Error loading points: {e}")
        return False

def run(command: str):
    """
        # Loop syntax:
        #   expects: loop <start> <end> <template>
        #   e.g.    loop 10 11 fq{i};msg Site {i} Spectrum…;spc;cc Site{i}

        Simple command handler for the Dear PyGui console.
        Supports single or multiple commands separated by ';':
        """
    import os
    command = command.strip()
    parent = getattr(sys.stdout, "parent", None)
    if parent is None:
        print("Warning: run() called but sys.stdout.parent is not set yet.")
        return
    if not hasattr(parent, "command_history"):
        parent.command_history = []
    parent.update_command_history(command)
    parent.history_index = len(parent.command_history)  # Always reset index to END
    # expects: loop <start> <end> <template> e.g. loop 10 11 fq{i};mark;spc;cc
    if command.startswith("loop "):
        import threading
        parts = command.split(" ", 3)
        if len(parts) < 4:
            print("Usage: loop <start> <end> <template>")
            return
        try:
            start = int(parts[1])
            end = int(parts[2])
            template = parts[3]
        except:
            print("loop: start and end must be integers.")
            return
        def worker():
            for i in range(start, end + 1):
                # 1) Format sub-commands for this iteration
                subs = [c.strip().format(i=i) for c in template.split(";") if c.strip()]
                # 2) Run everything *except* cc immediately or via DPG callback
                cc_suffixes = []
                for sub_cmd in subs:
                    if sub_cmd.lower().startswith("msg "):
                        msg_text1 = sub_cmd.split(" ", 1)[1]
                        show_msg_window(msg_text1)
                        print(f"[loop {i}] scheduled: {sub_cmd}")
                    elif sub_cmd.lower().startswith("cc "):
                        # collect suffix for later
                        cc_suffixes.append(sub_cmd .split(" ", 1)[1])
                    else:
                        print(f"[loop {i}] running: {sub_cmd}")
                        run(sub_cmd)
                # 3) Wait for UI to paint msg & for spc to finish
                time.sleep(0.5)
                # 4) Now do all your cc’s synchronously
                for suffix in cc_suffixes:
                    print(f"[loop {i}] saving screenshot for: {suffix}")
                    save_quti_window_screenshot(suffix)
                    # tiny pause so Windows has time to write each file
                    time.sleep(0.2)
        threading.Thread(target=worker, daemon=True).start()
        print(f"Looping from {start} to {end} in background…")
        return
    # Split into individual commands
    commands = [c.strip() for c in command.split(";") if c.strip()]
    for single_command in commands:
        try:
            verb, sep, rest = single_command.partition(" ")
            single_command = verb.lower() + sep + rest
            if single_command == "":
                print("This line cannot be reached")
            # @desc: add new PPT slide & paste clipboard image
            elif single_command == "a":
                import subprocess
                try:
                    copy_quti_window_to_clipboard()
                    script_path = os.path.join("Utils", "add_slide_paste_clipboard.py")
                    subprocess.run(
                        [sys.executable, script_path],
                        check=True
                    )
                    print("Added slide & pasted clipboard image to PowerPoint.")
                except Exception as e:
                    print(f"Could not add slide: {e}")
            # @desc: Copy 'QuTi SW' window to clipboard
            elif single_command == "c":
                copy_quti_window_to_clipboard()
            # @desc: Schedule a delayed screenshot (optional suffix) & save to file
            elif single_command.startswith("cc"):
                import threading
                # parse optional suffix
                parts = single_command.split(" ", 1)
                notes = getattr(getattr(parent, "opx", None), "expNotes", None)
                user_suffix = parts[1].strip() if len(parts) > 1 else ""
                # build the final suffix
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
            # @desc: Hide OPX plot legend
            elif single_command == "hl":
                if hasattr(parent, "opx") and hasattr(parent.opx, "hide_legend"):
                    parent.opx.hide_legend()
                    print("OPX legend hidden.")
                else:
                    print("OPX or hide_legend() not available.")
            # @desc: Draw a cross + circle marker on the plot
            elif single_command == "mark":
                try:
                    x = dpg.get_value("mcs_ch0_ABS")
                    y = dpg.get_value("mcs_ch1_ABS")
                    cross_tag = "temp_cross_marker"

                    # Remove any old parts
                    for suffix in [
                        "_h_left", "_h_right",
                        "_v_top", "_v_bottom",
                        "_circle"
                    ]:
                        if dpg.does_item_exist(f"{cross_tag}{suffix}"):
                            dpg.delete_item(f"{cross_tag}{suffix}")

                    if not dpg.does_item_exist("plot_draw_layer"):
                        dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

                    # === Cross with a small hole ===
                    gap_size = 0.5  # Half gap length at center
                    line_len = 3

                    # Horizontal left part
                    dpg.draw_line(
                        (x - line_len, y), (x - gap_size, y),
                        color=(255, 0, 0, 255), thickness=0.3,
                        parent="plot_draw_layer", tag=f"{cross_tag}_h_left"
                    )
                    # Horizontal right part
                    dpg.draw_line(
                        (x + gap_size, y), (x + line_len, y),
                        color=(255, 0, 0, 255), thickness=0.3,
                        parent="plot_draw_layer", tag=f"{cross_tag}_h_right"
                    )
                    # Vertical top part
                    dpg.draw_line(
                        (x, y - line_len), (x, y - gap_size),
                        color=(255, 0, 0, 255), thickness=0.3,
                        parent="plot_draw_layer", tag=f"{cross_tag}_v_top"
                    )
                    # Vertical bottom part
                    dpg.draw_line(
                        (x, y + gap_size), (x, y + line_len),
                        color=(255, 0, 0, 255), thickness=0.3,
                        parent="plot_draw_layer", tag=f"{cross_tag}_v_bottom"
                    )

                    # === Circle ===
                    dpg.draw_circle(
                        center=(x, y), radius=line_len,
                        color=(255, 0, 0, 255),
                        thickness=2,
                        parent="plot_draw_layer", tag=f"{cross_tag}_circle"
                    )

                    print(f"Marked cross + circle at X={x:.4f}, Y={y:.4f} with center gap")
                except Exception as e:
                    print(f"Error in 'mark': {e}")
            # @desc: Remove the temporary marker
            elif single_command == "unmark":
                try:
                    cross_tag = "temp_cross_marker"
                    removed_any = False
                    for suffix in [
                        "_h_left", "_h_right",
                        "_v_top", "_v_bottom",
                        "_circle"
                    ]:
                        tag = f"{cross_tag}{suffix}"
                        if dpg.does_item_exist(tag):
                            dpg.delete_item(tag)
                            removed_any = True
                    if removed_any:
                        print("Marker cleared.")
                    else:
                        print("No marker to remove.")
                except Exception as e:
                    print(f"Error in 'unmark': {e}")
            # @desc: Move last saved files
            elif single_command == "mv":
                parent.opx.move_last_saved_files()
            # @desc: Call external clog script with argument
            elif single_command.startswith("clog "):
                arg = single_command.split("clog ", 1)[1].strip().lower()
                import subprocess
                subprocess.run([sys.executable, "clog.py", arg])
            # @desc: Copy filename from last message to clipboard
            elif single_command == "fn":
                import os, re, pyperclip
                # Ensure we have console messages
                if not (hasattr(sys.stdout, 'messages') and sys.stdout.messages):
                    print("No messages found in sys.stdout.")
                    return
                last_msg = sys.stdout.messages[-1].strip()
                filepath = None
                # 1) Try to find any Windows/Unix‐style absolute path with an extension
                #    e.g. C:/folder/file.ext or /home/user/file.ext
                pattern = r'(?:[A-Za-z]:[\\/]|[/\\]).+?\.\w+'
                matches = re.findall(pattern, last_msg)
                if matches:
                    filepath = matches[-1]
                else:
                    # 2) Fallback: find the last token that contains a dot (e.g. "file.ext")
                    tokens = re.split(r'\s+', last_msg)
                    for tok in reversed(tokens):
                        tok_clean = tok.strip('",;')
                        if '.' in tok_clean:
                            filepath = tok_clean
                            break
                if filepath:
                    filename = os.path.basename(filepath)
                    pyperclip.copy(filename)
                    print(f"Filename copied: {filename}")
                else:
                    print("No filepath found in last message.")
            # @desc: Stop camera & retract flippers
            elif single_command == "sc":
                toggle_sc(reverse=False)
            # @desc: Start camera & extend flippers
            elif single_command in ("!sc", "l"):
                toggle_sc(reverse=True)
            # @desc: Set subfolder suffix for MoveSubfolderInput
            elif single_command.startswith("sub "):
                try:
                    folder = single_command.split("sub ", 1)[1].strip()
                    if not dpg.does_item_exist("MoveSubfolderInput"):
                        dpg.set_value("chkbox_scan", True)
                        if hasattr(parent, "opx"):
                            parent.opx.Update_scan(app_data=None, user_data=True)
                    wait_for_item_and_set("MoveSubfolderInput", folder)
                    print(f"Subfolder set to: {folder}")
                    with open("last_scan_dir.txt", "w") as f:
                        f.write(folder)
                except Exception as e:
                    print(f"Error in 'sub' command: {e}")
            # @desc: Run COBOLT power set command
            elif single_command.startswith("cob "):
                try:
                    power_mw = float(single_command.split("cob ", 1)[1].strip())
                    if parent and hasattr(parent,"coboltGUI") and parent.coboltGUI and parent.coboltGUI.laser and parent.coboltGUI.laser.is_connected():
                        parent.coboltGUI.laser.set_modulation_power(power_mw)
                        print(f"Cobolt modulation power set to {power_mw:.2f} mW")
                    else:
                        print("Cobolt laser not connected or unavailable.")
                except Exception as e:
                    print(f"Failed to set Cobolt power: {e}")
            # @desc: Launched external clipboard script
            elif single_command == "pp":
                import subprocess
                subprocess.Popen([
                    sys.executable, "copy_window_to_clipboard.py"
                ])
                print("Launched external clipboard script.")
            # @desc: Start counter live in OPX
            elif single_command == "cn":
                if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "opx"):
                    sys.stdout.parent.opx.btnStartCounterLive()
                    print("Counter live started.")
                else:
                    print("Counter live not available.")
            # @desc: Load windows position profile
            elif single_command.startswith("lpos"):
                parts = single_command.split(" ", 1)
                if len(parts) == 1:
                    profile_name = "local"  # or whatever default you want
                else:
                    arg = parts[1].strip()
                    profile_name = "remote" if arg == "r" else arg
                if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                    sys.stdout.parent.smaractGUI.load_pos(profile_name)
                    print(f"Loaded positions.")
                else:
                    print("smaractGUI not available.")
            # @desc: Save windows position profile
            elif single_command.startswith("spos"):
                parts = single_command.split(" ", 1)
                if len(parts) == 1 or not parts[1].strip():
                    # No argument → auto pick based on resolution
                    if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                        # Example: use your actual check here
                        if is_remote_resolution():
                            profile_name = "remote"
                        else:
                            profile_name = "local"
                    else:
                        print("smaractGUI not available.")
                        profile_name = "local"
                else:
                    arg = parts[1].strip()
                    profile_name = "remote" if arg.lower() == "r" else arg

                if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                    sys.stdout.parent.smaractGUI.save_pos(profile_name)
                    print(f"Saved positions with profile: {profile_name}")
                else:
                    print("smaractGUI not available.")
            # @desc: Reload keys handler / GUI / given module
            elif single_command.startswith("reload"):
                if single_command.strip().lower() == "reload keys":
                    handler_tag = "key_press_handler"

                    if dpg.does_item_exist(handler_tag):
                        dpg.delete_item(handler_tag)
                        print(f"[reload keys] Deleted existing key press handler: {handler_tag}")

                    # Create a new one inside a fresh registry
                    with dpg.handler_registry():
                        dpg.add_key_press_handler(callback=parent.Callback_key_press, tag=handler_tag)
                    print(f"[reload keys] Added new key press handler: {handler_tag}")
                    return
                try:
                    import importlib
                    parts = single_command.split()
                    raw_name = None
                    if len(parts) == 1:
                        module_name = "Outout_to_gui"
                    elif len(parts) == 2:
                        raw_name = parts[1]
                        # Handle known GUI naming: reload GUI_Zelux => HW_GUI.GUI_Zelux
                        if raw_name.startswith("GUI_"):
                            module_name = f"HW_GUI.{raw_name}"
                        else:
                            module_name = raw_name
                    else:
                        print("Usage: reload <module>")
                        return

                    print(f"Trying to reload: {module_name}")

                    if raw_name and raw_name.lower() in ["gui_zelux", "zel","zelux"]:
                        import HW_GUI.GUI_Zelux as gui_Zelux
                        importlib.reload(gui_Zelux)
                        # Clean up old window if needed:
                        if hasattr(parent, "cam") and parent.cam:
                            try:
                                # Store before delete
                                pos = dpg.get_item_pos(parent.cam.window_tag)
                                size = dpg.get_item_rect_size(parent.cam.window_tag)
                                parent.cam.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old window removal failed: {e}")
                        # Recreate:
                        parent.cam = gui_Zelux.ZeluxGUI()

                        if dpg.does_item_exist("Zelux_button"):
                            dpg.delete_item("Zelux_button")
                        parent.create_bring_window_button(
                            parent.cam.window_tag,
                            button_label="Zelux",
                            tag="Zelux_button",
                            parent="focus_group"
                        )
                        parent.active_instrument_list.append(parent.cam.window_tag)
                        # If cameras found: redo Controls & pos
                        if len(parent.cam.cam.available_cameras) > 0:
                            # Ensure window exists
                            if not dpg.does_item_exist(parent.cam.window_tag):
                                parent.cam.AddNewWindow()

                            # Ensure group tag does not exist
                            if dpg.does_item_exist("ZeluxControls"):
                                dpg.delete_item("ZeluxControls")

                            parent.cam.Controls()

                            dpg.set_item_pos(parent.cam.window_tag, pos)
                            dpg.set_item_width(parent.cam.window_tag, size[0])
                            dpg.set_item_height(parent.cam.window_tag, size[1])

                        # Recreate MFF flippers into the Zelux GUI
                        parent.mff_101_gui = []  # Clear old list if any

                        flipper_list = hw_devices.HW_devices().mff_101_list  # your original list
                        for flipper in flipper_list:
                            mff_gui = GUI_MFF(serial_number=flipper.serial_no, device=flipper)
                            parent.mff_101_gui.append(mff_gui)

                        print("Reloaded HW_GUI.GUI_Zelux and recreated ZeluxGUI.")
                    elif raw_name and raw_name.lower() in ["femto", "femto_gui"]:
                        import HW_GUI.GUI_Femto_Power_Calculations as gui_Femto
                        importlib.reload(gui_Femto)

                        # Clean up old window if needed:
                        if hasattr(parent, "femto_gui") and parent.femto_gui:
                            try:
                                pos = dpg.get_item_pos(parent.femto_gui.window_tag)
                                size = dpg.get_item_rect_size(parent.femto_gui.window_tag)
                                parent.femto_gui.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old Femto GUI removal failed: {e}")

                        # Recreate Femto GUI
                        parent.femto_gui = gui_Femto.FemtoPowerCalculator(parent.kdc_101_gui)
                        parent.femto_gui.create_gui()

                        # Recreate bring-to-front button if needed
                        if dpg.does_item_exist("Femto_button"):
                            dpg.delete_item("Femto_button")

                        parent.create_bring_window_button(
                            parent.femto_gui.window_tag,
                            button_label="Femto",
                            tag="Femto_button",
                            parent="focus_group"
                        )
                        parent.active_instrument_list.append(parent.femto_gui.window_tag)

                        # Restore previous position & size if possible
                        dpg.set_item_pos(parent.femto_gui.window_tag, pos)
                        dpg.set_item_width(parent.femto_gui.window_tag, size[0])
                        dpg.set_item_height(parent.femto_gui.window_tag, size[1])

                        print("Reloaded HW_GUI.GUI_Femto and recreated FemtoPowerCalculator.")
                    elif raw_name and raw_name.lower() in ["opx"]:
                        import HWrap_OPX as wrap_OPX
                        importlib.reload(wrap_OPX)

                        # Clean up old window if needed:
                        if hasattr(parent, "opx") and parent.opx:
                            try:
                                pos = dpg.get_item_pos(parent.opx.window_tag)
                                size = dpg.get_item_rect_size(parent.opx.window_tag)
                                simulation = parent.opx.simulation
                                parent.opx.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old OPX GUI removal failed: {e}")

                        # Recreate OPX
                        parent.opx = wrap_OPX.GUI_OPX()  # or whatever device ref you use
                        parent.opx.controls()

                        if dpg.does_item_exist("OPX_button"):
                            dpg.delete_item("OPX_button")

                        parent.create_bring_window_button(
                            parent.opx.window_tag,
                            button_label="OPX",
                            tag="OPX_button",
                            parent="focus_group"
                        )
                        parent.create_sequencer_button()
                        parent.active_instrument_list.append(parent.opx.window_tag)

                        dpg.set_item_pos(parent.opx.window_tag, pos)
                        dpg.set_item_width(parent.opx.window_tag, size[0])
                        dpg.set_item_height(parent.opx.window_tag, size[1])

                        print("Reloaded HWrap_OPX and recreated GUI_OPX.")
                    elif raw_name and raw_name.lower() in ["kdc", "kdc_101"]:
                        import HW_GUI.GUI_KDC101 as gui_KDC
                        importlib.reload(gui_KDC)

                        # Remove old window if it exists
                        if hasattr(parent, "kdc_101_gui") and parent.kdc_101_gui:
                            try:
                                pos = dpg.get_item_pos(parent.kdc_101_gui.window_tag)
                                size = dpg.get_item_rect_size(parent.kdc_101_gui.window_tag)
                                parent.kdc_101_gui.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old KDC_101 GUI removal failed: {e}")

                        # Recreate KDC_101 GUI
                        parent.kdc_101_gui = gui_KDC.GUI_KDC101(
                            serial_number=parent.kdc_101_gui.device.serial_number,
                            device=hw_devices.HW_devices().kdc_101
                        )

                        # Bring-to-front button
                        if dpg.does_item_exist("kdc_101_button"):
                            dpg.delete_item("kdc_101_button")

                        parent.create_bring_window_button(
                            parent.kdc_101_gui.window_tag,
                            button_label="kdc_101",
                            tag="kdc_101_button",
                            parent="focus_group"
                        )
                        parent.active_instrument_list.append(parent.kdc_101_gui.window_tag)

                        # Restore position & size
                        dpg.set_item_pos(parent.kdc_101_gui.window_tag, pos)
                        dpg.set_item_width(parent.kdc_101_gui.window_tag, size[0])
                        dpg.set_item_height(parent.kdc_101_gui.window_tag, size[1])

                        print("Reloaded HW_GUI.GUI_KDC101 and recreated KDC_101 GUI.")
                    elif raw_name and raw_name.lower() in ["smaract", "smaract_gui"]:
                        import HW_GUI.GUI_Smaract as gui_Smaract
                        importlib.reload(gui_Smaract)
                        if hasattr(parent, "smaractGUI") and parent.smaractGUI:
                            try:
                                pos = dpg.get_item_pos(parent.smaractGUI.window_tag)
                                size = dpg.get_item_rect_size(parent.smaractGUI.window_tag)
                                parent.smaractGUI.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old Smaract GUI removal failed: {e}")
                        # Recreate Smaract GUI
                        parent.smaractGUI = gui_Smaract.GUI_smaract(
                            simulation=parent.smaractGUI.simulation,
                            serial_number=parent.smaractGUI.selectedDevice
                        )
                        parent.smaractGUI.create_gui()
                        if dpg.does_item_exist("Smaract_button"):
                            dpg.delete_item("Smaract_button")
                        parent.create_bring_window_button(
                            parent.smaractGUI.window_tag,
                            button_label="Smaract",
                            tag="Smaract_button",
                            parent="focus_group"
                        )
                        parent.active_instrument_list.append(parent.smaractGUI.window_tag)
                        dpg.set_item_pos(parent.smaractGUI.window_tag, pos)
                        dpg.set_item_width(parent.smaractGUI.window_tag, size[0])
                        dpg.set_item_height(parent.smaractGUI.window_tag, size[1])
                        # If not simulation, restart the Smaract thread
                        if not parent.smaractGUI.simulation:
                            import threading
                            parent.smaract_thread = threading.Thread(target=parent.render_smaract)
                            parent.smaract_thread.start()
                        print("Reloaded HW_GUI.GUI_Smaract and recreated GUI_smaract.")
                    elif raw_name and raw_name.lower() in ["hrs", "hrs500", "hrs_500"]:
                        import HW_GUI.GUI_HRS_500 as gui_HRS500
                        importlib.reload(gui_HRS500)

                        # Remove old window if it exists
                        if hasattr(parent, "hrs_500_gui") and parent.hrs_500_gui:
                            try:
                                pos = dpg.get_item_pos(parent.hrs_500_gui.window_tag)
                                size = dpg.get_item_rect_size(parent.hrs_500_gui.window_tag)
                                parent.hrs_500_gui.DeleteMainWindow()
                            except Exception as e:
                                print(f"Old HRS_500 GUI removal failed: {e}")

                        # === Recreate the GUI exactly like your Instruments.HRS_500 branch ===
                        parent.hrs_500_gui = gui_HRS500.GUI_HRS500(hw_devices.HW_devices().hrs_500)

                        # Bring button
                        if dpg.does_item_exist("HRS_500_button"):
                            dpg.delete_item("HRS_500_button")

                        parent.create_bring_window_button(
                            parent.hrs_500_gui.window_tag,
                            button_label="Spectrometer",
                            tag="HRS_500_button",
                            parent="focus_group"
                        )

                        parent.active_instrument_list.append(parent.hrs_500_gui.window_tag)

                        # Restore previous position/size if we had them
                        try:
                            dpg.set_item_pos(parent.hrs_500_gui.window_tag, pos)
                            dpg.set_item_width(parent.hrs_500_gui.window_tag, size[0])
                            dpg.set_item_height(parent.hrs_500_gui.window_tag, size[1])
                        except Exception:
                            pass

                        print("Reloaded HW_GUI.GUI_HRS500 and recreated Spectrometer GUI.")

                    else:
                        if module_name in sys.modules:
                            module = sys.modules[module_name]
                            importlib.reload(module)
                            print(f"Reloaded: {module_name}")
                        else:
                            module = importlib.import_module(module_name)
                            print(f"Imported and reloaded: {module_name}")
                    # dpg.focus_item("console_window")
                except Exception as e:
                    traceback.print_exc()
                    print(f"Reload failed for '{module_name}': {e}")
            # @desc: Plot future femto annotations
            elif single_command == "plf":
                try:
                    if not (hasattr(parent, "opx") and hasattr(parent, "femto_gui")):
                        print("Missing 'opx' or 'femto_gui' in parent.")
                        return

                    # Get the scan start & end from OPX
                    startLoc = parent.opx.startLoc
                    endLoc = parent.opx.endLoc

                    # Get future data from Femto
                    future_data = parent.femto_gui.get_future_energies()

                    if hasattr(parent, "cam"):
                        parent.cam.all_future_data = future_data  # List of (angle, E)
                        print(f"Stored {len(future_data)} future data points in Zelux.")
                    else:
                        print("cam not found to store future data.")

                    # Remove previous annotations if needed
                    if not hasattr(parent, "future_annots"):
                        parent.future_annots = []
                    else:
                        for annot in parent.future_annots:
                            if dpg.does_item_exist(annot):
                                dpg.delete_item(annot)
                        parent.future_annots = []

                    # Use the minimum Y coordinate
                    base_y_val = float(startLoc[1]) / 1e6

                    for idx, (angle, E) in enumerate(future_data):
                        # Example X: angle, Y: mid-Y
                        angle = float(angle)
                        E = float(E)
                        x_val = float(endLoc[0]) / 1e6
                        y_val = base_y_val + idx * 2
                        if not dpg.does_item_exist("plotImaga_Y"):
                            print("Error: Axis 'plotImaga_Y' does not exist.")
                            return
                        if not dpg.does_item_exist("plot_draw_layer"):
                            dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")
                        annot_tag = f"future_annot_{idx}"
                        # If the tag exists, just update its properties
                        if dpg.does_item_exist(annot_tag):
                            dpg.configure_item(annot_tag, pos=(x_val, y_val), text=f"{E:.1f} nJ")
                            print(f"Updated existing annotation {annot_tag}")
                        else:
                            dpg.draw_text(
                                pos=(x_val, y_val),
                                text=f"{E:.1f} nJ",
                                color=(255, 255, 255, 255),
                                size=1.0,
                                parent="plot_draw_layer",
                                tag=annot_tag
                            )
                        parent.future_annots.append(annot_tag)
                except Exception as e:
                    print(f"Error running 'plf': {e}")
            # @desc: Load & plot most recent CSV
            elif single_command.startswith("ld"):
                try:
                    if not hasattr(parent, "opx"):
                        print("Parent has no opx.")
                        return
                    # Parse dz value if present
                    dz_val = None
                    try:
                        dz_val = int(single_command[2:])
                    except ValueError:
                        pass  # No numeric value; it's just "ld"
                    # If dz value is specified, enable limit and set dz
                    if dz_val is not None:
                        print(f"Setting dz to {dz_val} and enabling limit...")
                        parent.opx.toggle_limit(app_data=None, user_data=True)
                        parent.opx.Update_dZ_Scan(app_data=None, user_data=dz_val)
                    try:
                        with open("last_scan_dir.txt", "r") as f:
                            last_scan_dir = f.read().strip()
                            print(f"Loaded last scan dir: {last_scan_dir}")
                    except FileNotFoundError:
                        print("No last_scan_dir.txt found.")
                        return

                    if not last_scan_dir or not os.path.isdir(last_scan_dir):
                        print(f"Invalid last scan dir: {last_scan_dir}")
                        return
                    # Get all CSV files and sort by modification time (newest first)
                    csv_files = [
                        os.path.join(last_scan_dir, f)
                        for f in os.listdir(last_scan_dir)
                        if f.lower().endswith(".csv")
                    ]
                    if not csv_files:
                        print("No CSV files found in last scan directory.")
                        return
                    csv_files.sort(key=os.path.getmtime, reverse=True)
                    fn = csv_files[0]
                    print(f"Loading most recent CSV: {fn}")
                    # Load it using your Common.loadFromCSV
                    data = loadFromCSV(fn)
                    # Call your OPX plot method
                    parent.opx.Plot_data(data, True)
                    parent.opx.last_loaded_file = fn
                    print(f"Loaded and plotted: {fn}")
                except Exception as e:
                    print(f"Error in ld command: {e}")
            # @desc: Toggle coordinate grid in Zelux plot
            elif single_command in ("coords", "coo"):
                parent = getattr(sys.stdout, "parent", None)
                if parent and hasattr(parent, "cam") and hasattr(parent.cam, "toggle_coords_display"):
                    # Flip the current flag
                    current = getattr(parent.cam, "show_coords_grid", False)
                    new_value = not current
                    parent.cam.toggle_coords_display(None, new_value)
                    print(f"Coordinate grid display set to: {new_value}")
                else:
                    print("cam or toggle_coords_display not available.")
            # @desc: Fill & move to N-th stored query point
            elif single_command.startswith("fq"):
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "fill_moveabs_from_query"):
                    # If user wrote fq7 → extract number
                    parts = single_command.strip()
                    index_to_go = None
                    if len(parts) > 2:
                        try:
                            index_to_go = int(parts[2:])
                        except ValueError:
                            print(f"Invalid index in command: {parts}")
                    if index_to_go:
                        # If no points yet, store current position as point #N
                        if not hasattr(parent, "saved_query_points") or not parent.saved_query_points:
                            parent.saved_query_points = []
                            x = dpg.get_value("mcs_ch0_ABS")
                            y = dpg.get_value("mcs_ch1_ABS")
                            parent.saved_query_points.append((index_to_go, x, y))
                            print(
                                f"No points yet → stored current position as point #{index_to_go}: X={x:.2f}, Y={y:.2f}")
                        # === Move to stored index ===
                        else:
                            found = [pt for pt in parent.saved_query_points if pt[0] == index_to_go]
                            if found:
                                _, x, y = found[0]
                                dpg.set_value("mcs_ch0_ABS", x)
                                dpg.set_value("mcs_ch1_ABS", y)
                                if hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "move_absolute"):
                                    parent.smaractGUI.move_absolute(None, None, 0)
                                    parent.smaractGUI.move_absolute(None, None, 1)
                                print(f"Moved to stored point #{index_to_go}: X={x:.2f}, Y={y:.2f}")
                                note_text=f"Point #{index_to_go}"
                                show_msg_window(note_text)
                                parent.opx.expNotes = note_text
                                if dpg.does_item_exist("inTxtScan_expText"):
                                    dpg.set_value("inTxtScan_expText", note_text)
                                    parent.opx.saveExperimentsNotes(note=note_text)
                            else:
                                print(f"No stored point with index {index_to_go}.")
                        run("list")
                    else:
                        # === Regular fill/move/store ===
                        parent.opx.fill_moveabs_from_query()
                        if hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "move_absolute"):
                            parent.smaractGUI.move_absolute(None, None, 0)
                            parent.smaractGUI.move_absolute(None, None, 1)
                        else:
                            print("Smaract GUI not available or missing 'move_absolute'.")
                        # Save new queried point
                        try:
                            x = dpg.get_value("mcs_ch0_ABS")
                            y = dpg.get_value("mcs_ch1_ABS")
                            if not hasattr(parent, "saved_query_points"):
                                parent.saved_query_points = []
                            if parent.saved_query_points:
                                last_index = parent.saved_query_points[-1][0]
                                new_index = last_index + 1
                            else:
                                new_index = 1
                            parent.saved_query_points.append((new_index, x, y))
                            print(f"Stored queried point #{new_index}: X={x:.2f}, Y={y:.2f}")
                            run("list")
                        except Exception as e:
                            print(f"Could not store queried point: {e}")
                else:
                    print("OPX not available or missing 'fill_moveabs_from_query'.")
            # @desc: Find the maximum Z value inside the currently defined queried_area.
            #        Move the stage to the X,Y location of the maximum, update the GUI,
            #        and store the location as a new query point in saved_query_points.
            elif single_command == "findq":
                try:
                    from HWrap_OPX import Axis
                    if not hasattr(parent, "opx"):
                        print("OPX unavailable.")
                        return

                    opx = parent.opx

                    # Check queried area
                    queried_area = getattr(opx, "queried_area", None)
                    if queried_area is None or len(queried_area) < 4:
                        print("No queried area defined.")
                        return

                    x0, x1, y0, y1 = queried_area
                    xmin, xmax = min(x0, x1), max(x0, x1)
                    ymin, ymax = min(y0, y1), max(y0, y1)

                    # Get scan data and coordinate vectors
                    scan = getattr(opx, "scan_data", None)
                    if scan is None or not hasattr(opx, "Xv") or not hasattr(opx, "Yv") or not hasattr(opx, "idx_scan"):
                        print("Scan data or coordinate vectors are missing.")
                        return

                    Xv = np.array(opx.Xv)
                    Yv = np.array(opx.Yv)
                    flipped_Yv = Yv[::-1]  # Flip Y for flipped image

                    z_idx = opx.idx_scan[Axis.Z.value]
                    z_value = float(opx.Zv[z_idx])

                    # Extract 2D Z-slice (XY plane at current Z index) and flip
                    flipped_arrXY = np.flipud(scan[z_idx, :, :])  # Match display orientation

                    # Get index masks inside queried rectangle
                    mask_x = (Xv >= xmin) & (Xv <= xmax)
                    mask_y = (flipped_Yv >= ymin) & (flipped_Yv <= ymax)

                    ix = np.where(mask_x)[0]
                    iy = np.where(mask_y)[0]

                    if ix.size == 0 or iy.size == 0:
                        print("No scan points inside queried area.")
                        return

                    # Extract the sub-region and find max
                    sub_arr = flipped_arrXY[np.ix_(iy, ix)]
                    if sub_arr.size == 0:
                        print("Sub-region is empty.")
                        return

                    iy_max, ix_max = np.unravel_index(np.argmax(sub_arr), sub_arr.shape)
                    x_max = Xv[ix[ix_max]]
                    y_max = flipped_Yv[iy[iy_max]]
                    z_max = sub_arr[iy_max, ix_max]

                    print(f"Max Z={z_max:.2f} found at X={x_max:.2f}, Y={y_max:.2f}, Z slice={z_value:.2f}")

                    # Move GUI sliders
                    dpg.set_value("mcs_ch0_ABS", x_max)
                    dpg.set_value("mcs_ch1_ABS", y_max)

                    if hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "move_absolute"):
                        parent.smaractGUI.move_absolute(None, None, 0)
                        parent.smaractGUI.move_absolute(None, None, 1)

                    # Save as a query point
                    if not hasattr(parent, "saved_query_points"):
                        parent.saved_query_points = []
                    new_index = parent.saved_query_points[-1][0] + 1 if parent.saved_query_points else 1
                    parent.saved_query_points.append((new_index, x_max, y_max))
                    print(f"Stored query point #{new_index}: X={x_max:.2f}, Y={y_max:.2f}")
                    run("list")

                except Exception as e:
                    print(f"Error in findq command: {e}")
            # @desc: Move to last recorded Z value (optionally add offset) and note
            elif single_command.strip().lower().startswith("z"):
                if parent and hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "last_z_value"):
                    base_z = parent.smaractGUI.last_z_value
                    offset = 0.0
                    try: # Try parsing offset from command (e.g., "z-10")
                        if len(single_command.strip()) > 1:
                            offset = float(single_command.strip()[1:])
                    except Exception as e:
                        print(f"Could not parse offset from '{single_command}': {e}")
                        offset = 0.0
                    target_z = base_z + offset
                    dpg.set_value("mcs_ch2_ABS", target_z)
                    if hasattr(parent.smaractGUI, "move_absolute"):
                        parent.smaractGUI.move_absolute(None, None, 2)
                        print(f"Moved to Z = {target_z:.2f} µm (base: {base_z:.2f}, offset: {offset:+.2f})")
                        # ✅ Generate note based on offset
                        if abs(offset) < 1e-6:
                            note_text = "Surface"
                        else:
                            note_text = f"{abs(offset):.1f} µm Deep"

                        try:
                            setpoint_mW = parent.coboltGUI.laser.get_power_setpoint()*1e-3
                            if setpoint_mW > 0.9:
                                note_text += f", Green {setpoint_mW:.1f} mW"
                            else:
                                note_text += ", Red 250 mA"
                        except Exception as e:
                            print(f"Could not get Cobolt setpoint: {e}")

                        show_msg_window(note_text)
                        parent.opx.expNotes = note_text
                        if dpg.does_item_exist("inTxtScan_expText"):
                            dpg.set_value("inTxtScan_expText", note_text)
                            parent.opx.saveExperimentsNotes(note=note_text)
                    else:
                        print("move_absolute not found in smaractGUI.")
                else:
                    print("smaractGUI or last_z_value not available.")
            # @desc: Round current position to <n> digits, move, update XYZ. Example: round2
            elif single_command.strip().lower().startswith("round"):
                try:
                    # Extract number from command (e.g., round1 → 1)
                    suffix = single_command.strip()[5:]
                    precision = int(suffix) if suffix else 0

                    if hasattr(parent.opx, "positioner") and hasattr(parent.opx.positioner, "AxesPositions"):
                        pos_pm = parent.opx.positioner.AxesPositions
                        pos_um = [p * 1e-6 for p in pos_pm]
                        raw = [round(p, precision) for p in pos_um]

                        snap = []
                        eps = 0.5 * 10 ** (-precision)  # half of one least significant digit
                        for p in raw:
                            integer = float(int(p))
                            frac = p - integer
                            if frac > 1 - eps:
                                integer += 1.0
                                p = integer  # drop fraction
                            snap.append(p)

                        dpg.set_value("mcs_ch0_ABS", snap[0])
                        dpg.set_value("mcs_ch1_ABS", snap[1])
                        dpg.set_value("mcs_ch2_ABS", snap[2])
                        parent.smaractGUI.move_absolute(None, None, 0)
                        parent.smaractGUI.move_absolute(None, None, 1)
                        parent.smaractGUI.move_absolute(None, None, 2)
                        time.sleep(0.5)

                        note = f"Rounded to ({snap[0]:.{precision}f}, {snap[1]:.{precision}f}, {snap[2]:.{precision}f})"
                        print(note)
                        run("st")

                    else:
                        print("Positioner or AxesPositions not available.")
                except Exception as e:
                    print(f"Error in round<n> command: {e}")
            # @desc: List all stored query points on the OPX graph
            elif single_command == "list":
                if parent and hasattr(parent, "saved_query_points") and parent.saved_query_points:
                    print("Stored points:")
                    for idx, (index, x, y) in enumerate(parent.saved_query_points):
                        print(f"{index}: X={x:.6f}, Y={y:.6f}")
                        x_val = x
                        y_val = y
                        if not dpg.does_item_exist("plotImaga_Y"):
                            print("Axis 'plotImaga_Y' does not exist. Cannot plot points.")
                            continue

                        if not dpg.does_item_exist("plot_draw_layer"):
                            dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

                        dot_tag = f"stored_point_dot_{index}"
                        if dpg.does_item_exist(dot_tag):
                            dpg.configure_item(dot_tag, center=(x_val, y_val))
                        else:
                            dpg.draw_circle(
                                center=(x_val, y_val),
                                radius=0.15,  # Adjust size as needed
                                color=(255, 0, 0, 255),
                                fill=(0, 0, 0, 255),
                                parent="plot_draw_layer",
                                tag=dot_tag
                            )

                        annot_tag = f"stored_point_annot_{index}"
                        if dpg.does_item_exist(annot_tag):
                            dpg.configure_item(annot_tag, pos=(x_val, y_val), text=f"{index}")
                            print(f"Updated existing annotation {annot_tag}")
                        else:
                            dpg.draw_text(
                                pos=(x_val, y_val),
                                text=f"{index}",
                                color=(255, 255, 0, 255),
                                size=1.2,
                                parent="plot_draw_layer",
                                tag=annot_tag
                            )

                        if not hasattr(parent, "query_annots"):
                            parent.query_annots = []
                        parent.query_annots.extend([dot_tag, annot_tag])
                else:
                    print("No points stored.")
            # @desc: Clear stored query points
            elif single_command.startswith("clear"):
                parent = getattr(sys.stdout, "parent", None)
                # If user gave index list: e.g. clear4,5,6
                if len(single_command) > len("clear"):
                    try:
                        index_part = single_command[len("clear"):].strip()
                        index_list = [int(x.strip()) for x in index_part.split(",") if x.strip()]
                    except Exception as e:
                        print(f"Invalid syntax. Use: clearN or clearN,M,...  Error: {e}")
                        return
                    if not index_list:
                        print("No valid indices provided.")
                        return
                    # Remove matching points
                    if parent and hasattr(parent, "saved_query_points"):
                        before_len = len(parent.saved_query_points)
                        parent.saved_query_points = [
                            (idx, x, y) for (idx, x, y) in parent.saved_query_points if idx not in index_list
                        ]
                        removed_count = before_len - len(parent.saved_query_points)
                        print(f"Removed {removed_count} points with indices {index_list}.")
                    # Remove matching annotations
                    if parent and hasattr(parent, "query_annots") and parent.query_annots:
                        new_annots = []
                        for tag in parent.query_annots:
                            if any(f"_{idx}" in tag for idx in index_list):
                                if dpg.does_item_exist(tag):
                                    dpg.delete_item(tag)
                                    print(f"Deleted annotation: {tag}")
                            else:
                                new_annots.append(tag)
                        parent.query_annots = new_annots
                else:
                    # If no index, clear everything
                    if parent and hasattr(parent, "saved_query_points"):
                        parent.saved_query_points = []
                        print("Stored points cleared.")
                    else:
                        print("No stored points to clear.")
                    if parent and hasattr(parent, "query_annots") and parent.query_annots:
                        for tag in parent.query_annots:
                            if dpg.does_item_exist(tag):
                                dpg.delete_item(tag)
                        parent.query_annots = []
                        print("All query annotations cleared.")
                    else:
                        print("No query annotations to clear.")
            # @desc: Shift stored query point by dx, dy
            elif single_command.startswith("shift"):
                parent = getattr(sys.stdout, "parent", None)
                if not parent or not hasattr(parent, "saved_query_points"):
                    print("No saved points found.")
                    return

                try:
                    # Example: shift3(0,-1)
                    inside = single_command.strip()[len("shift"):].strip()
                    index_part, args_part = inside.split("(")
                    index_to_shift = int(index_part)
                    dx, dy = [float(v.strip()) for v in args_part.strip(")").split(",")]
                except Exception as e:
                    print(f"Invalid syntax. Use: shift3(ΔX, ΔY). Error: {e}")
                    return

                # Find the point with matching index
                found = False
                for i, (stored_index, x, y) in enumerate(parent.saved_query_points):
                    if stored_index == index_to_shift:
                        new_x = x + dx
                        new_y = y + dy
                        parent.saved_query_points[i] = (stored_index, new_x, new_y)
                        print(f"Shifted point #{stored_index} by ΔX={dx}, ΔY={dy} → New: X={new_x:.6f}, Y={new_y:.6f}")
                        found = True
                        break

                if not found:
                    print(f"No point with index {index_to_shift} found.")
                else:
                    print("Updated points:")
                    for idx_num, x_val, y_val in parent.saved_query_points:
                        print(f"{idx_num}: X={x_val:.6f}, Y={y_val:.6f}")
            # @desc: Insert new points based on last
            elif single_command.startswith("insert"):
                pts = getattr(parent, "saved_query_points", None)
                if not parent or not pts or len(pts) < 1:
                    print("Need at least 1 existing point to insert relative to.")
                    return

                body = single_command[len("insert"):].strip()  # e.g. "3" or "5(0,-2)"
                # extract count N
                if "(" in body and body.endswith(")"):
                    num_str, args = body.split("(", 1)
                    num_to_insert = int(num_str)
                    args = args[:-1]  # strip trailing ")"
                    try:
                        dx_str, dy_str = args.split(",", 1)
                        dx = float(dx_str)
                        dy = float(dy_str)
                        print(f"Inserting {num_to_insert} points each shifted by ΔX={dx}, ΔY={dy}")
                    except:
                        print("Invalid syntax. Use insertN or insertN(dx,dy), e.g. insert3 or insert5(0,-2)")
                        return
                else:
                    # no custom shift, only a count
                    num_to_insert = int(body)
                    if len(pts) < 2:
                        print("Need at least 2 points to compute average shift.")
                        return
                    # compute average adjacent shift
                    dxs = []
                    dys = []
                    for a, b in zip(pts, pts[1:]):
                        _, x1, y1 = a
                        _, x2, y2 = b
                        dxs.append(x2 - x1)
                        dys.append(y2 - y1)
                    dx = sum(dxs) / len(dxs)
                    dy = sum(dys) / len(dys)
                    print(f"No custom shift given; averaging shifts: ΔX={dx:.6f}, ΔY={dy:.6f}")

                if num_to_insert <= 0:
                    print("Number of points to insert must be positive.")
                    return

                # start from last point
                last_index, last_x, last_y = pts[-1]
                for i in range(1, num_to_insert + 1):
                    new_index = last_index + i
                    new_x = last_x + i * dx
                    new_y = last_y + i * dy
                    pts.append((new_index, new_x, new_y))
                    print(f"Inserted point #{new_index}: X={new_x:.6f}, Y={new_y:.6f}")

                # print updated list
                print("Updated points:")
                for idx_num, x_val, y_val in pts:
                    print(f"{idx_num}: X={x_val:.6f}, Y={y_val:.6f}")
            # @desc: Save stored query points to file
            elif single_command == "savelist":
                if parent and hasattr(parent, "saved_query_points") and parent.saved_query_points:
                    file_name = "saved_query_points.txt"
                    try:
                        with open(file_name, "w") as f:
                            for point in parent.saved_query_points:
                                idx, x, y = point
                                f.write(f"{idx},{x:.6f},{y:.6f}\n")
                        print(f"Saved {len(parent.saved_query_points)} points to {file_name}")
                    except Exception as e:
                        print(f"Error saving list: {e}")
                else:
                    print("No stored points to save.")
            # @desc: Load stored query points from default file
            elif single_command == "loadlist":
                load_saved_points(parent)
            # @desc: Generate points file from last loaded CSV and load if < 1000
            elif single_command in ("gen list", "genlist"):
                if hasattr(parent, "opx") and hasattr(parent.opx, "last_loaded_file"):
                    from Utils.export_points import export_points
                    csv_file = parent.opx.last_loaded_file
                    if not os.path.exists(csv_file):
                        print(f"❌ Last loaded file not found: {csv_file}")
                        return

                    output_file = export_points(csv_file)
                    print(f"✅ Points file generated: {output_file}")

                    # Try to auto-load if reasonable
                    if output_file and os.path.exists(output_file):
                        with open(output_file, "r") as f:
                            line_count = sum(1 for _ in f)
                        if line_count < 1000:
                            load_saved_points(parent, output_file)
                        else:
                            print(f"⚠️ Not auto-loading: {line_count} points > 1000.")
                else:
                    print("❌ parent.opx.last_loaded_file not available.")
            # @desc: Acquire HRS500 spectrum and rename
            elif single_command == "spc":
                import glob
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "spc"):
                    if hasattr(parent.opx.spc, "acquire_Data"):
                        toggle_sc(reverse=False)

                        hrs = getattr(parent, "hrs_500_gui", None)
                        hrs.acquire_callback()
                        notes = getattr(parent.opx, "expNotes", None) if hasattr(parent, "opx") else None
                        fp = getattr(hrs.dev, "last_saved_csv", None)
                        if not fp or not os.path.isfile(fp):
                            # fallback: search the save directory for the newest *.csv
                            save_dir = hrs.dev.save_directory  # wherever you set it
                            matches = glob.glob(os.path.join(save_dir, "*.csv"))
                            if not matches:
                                print("No CSV found to rename.")
                                return
                            fp = max(matches, key=os.path.getmtime)

                        # 3) Rename to include expNotes (if any)
                        dirname, fname = os.path.split(fp)
                        base, ext = os.path.splitext(fname)
                        if notes:
                            new_fname = f"{base}_{notes}{ext}"
                            new_fp = os.path.join(dirname, new_fname)
                            try:
                                os.replace(fp, new_fp)
                                print(f"Renamed SPC file → {new_fp}")
                            except Exception as e:
                                print(f"Failed to rename SPC file: {e}")
                    else:
                        print("OPX SPC has no 'acquire_Data' method.")
                else:
                    print("Parent OPX or SPC not available.")
            # @desc: display a message window with large yellow text
            elif single_command.startswith("msg "):
                msg_text = single_command.split(" ", 1)[1]
                show_msg_window(msg_text)
            # @desc: Clear the message window
            elif single_command == "msgclear":
                if dpg.does_item_exist("msg_Win"):
                    dpg.delete_item("msg_Win")
                    print("Message window cleared.")
                else:
                    print("No message window to clear.")
            # @desc: Fill Smaract absolute XYZ from current position
            elif single_command == "st":
                if parent and hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "fill_current_position_to_moveabs"):
                    parent.smaractGUI.fill_current_position_to_moveabs()
                else:
                    print("smaractGUI or Set XYZ callback not available.")
            # @desc: Set or append to the experiment notes
            elif single_command.lower().startswith("note "):
                note_text = single_command[len("note "):].strip()
                if note_text.startswith("!"): # Check if we should append to the existing note
                    append_text = note_text[1:].strip()
                    if append_text:
                        append_text = append_text[:1].upper() + append_text[1:]
                    existing_note = getattr(parent.opx, "expNotes", "")
                    note_text = (existing_note + ", " + append_text).strip()
                else:
                    note_text = note_text[:1].upper() + note_text[1:] # Capitalize first letter of a new note
                show_msg_window(note_text)
                parent.opx.expNotes = note_text
                if dpg.does_item_exist("inTxtScan_expText"):
                    dpg.set_value("inTxtScan_expText", note_text)
                    parent.opx.saveExperimentsNotes(note=note_text)
                print(f"Notes updated: {note_text}")
            # @desc: Set femto attenuator to percent
            elif single_command.lower().startswith("att"):
                # att<value> → override the femto attenuator to <value>%
                try:
                    # parse the number after "att"
                    val_str = single_command[3:].strip()
                    Att_percent = float(val_str)
                except Exception:
                    print(f"Invalid syntax. Use: att<percent>, e.g. att12.5")
                    return

                # Update the input widget if it exists
                widget_tag = "femto_attenuator"
                if dpg.does_item_exist(widget_tag):
                    dpg.set_value(widget_tag, Att_percent)
                else:
                    print(f"Widget '{widget_tag}' not found; value will still be applied.")
                if parent and hasattr(parent, "femto_gui") and hasattr(parent.opx.pharos, "setBasicTargetAttenuatorPercentage"):
                    try:
                        parent.opx.pharos.setBasicTargetAttenuatorPercentage(Att_percent)
                        print(f"Attenuator set to {Att_percent:.1f}%")
                        tag = parent.femto_gui.future_input_tag if parent and hasattr(parent, "femto_gui") else None
                        if tag and dpg.does_item_exist(tag):
                            # grab the existing range (everything before any comma)
                            existing = dpg.get_value(tag) or ""
                            base = existing.split(",", 1)[0].strip()
                            new_text = f"{base},{Att_percent:.1f}%"
                            dpg.set_value(tag, new_text)
                            # call the same callback that the input uses
                            try:
                                parent.femto_gui.calculate_future(sender=None, app_data=None, user_data=None)
                                print(f"Future attenuator set to {Att_percent:.1f}% and recalculated.")
                            except Exception as e:
                                print(f"Error recalculating future angles: {e}")
                    except Exception as e:
                        print(f"Failed to set attenuator: {e}")
                else:
                    print("Femto GUI or Pharos API not available.")
            # @desc: Calculate future femto pulses steps
            elif single_command.lower().startswith("future"):
                # Example: future10:3:29,20%x100
                future_args = single_command[len("future"):].strip()
                if not future_args:
                    print("Syntax: future<start:step:end,percent>xN")
                    continue

                if hasattr(parent, "femto_gui") and hasattr(parent.femto_gui, "future_input_tag"):
                    # Write the input string to the input widget
                    dpg.set_value(parent.femto_gui.future_input_tag, future_args)

                    # Split range, att and optional xN
                    range_part, *rest = future_args.split(",")
                    pulse_count = None

                    if rest:
                        att_part = rest[0].strip()
                        if "x" in att_part:
                            att_str, x_part = att_part.split("x", 1)
                            att_str = att_str.strip().replace("%", "")
                            x_part = x_part.strip()
                            pulse_count = int(x_part)
                        else:
                            att_str = att_part.strip().replace("%", "")
                            x_part = None

                        try:
                            att_value = float(att_str)
                            if dpg.does_item_exist("femto_attenuator"):
                                dpg.set_value("femto_attenuator", att_value)
                                print(f"Attenuator set to {att_value}%")
                                parent.opx.pharos.setBasicTargetAttenuatorPercentage(att_value)
                            else:
                                print("Attenuator input widget not found.")
                        except Exception as e:
                            print(f"Could not parse Att %: {e}")

                    # Always parse the range and update step
                    parts = [float(x.strip()) for x in range_part.strip().split(":")]
                    if len(parts) == 3:
                        step_size = parts[1]
                        if dpg.does_item_exist("femto_increment_hwp"):
                            dpg.set_value("femto_increment_hwp", step_size)
                            print(f"HWPInc set to {step_size}")
                        else:
                            print("HWPInc input widget not found.")
                    else:
                        print("Invalid range format, expected start:step:end")

                    # ✅ If xN found, set anneal params
                    if pulse_count is not None:
                        if dpg.does_item_exist("femto_anneal_pulse_count"):
                            dpg.set_value("femto_anneal_pulse_count", pulse_count - 1)
                            print(f"nPlsAnn set to {pulse_count - 1}")
                        if dpg.does_item_exist("femto_increment_hwp_anneal"):
                            hwp_ann_val = 0.01 if pulse_count > 1 else 0.0
                            dpg.set_value("femto_increment_hwp_anneal", hwp_ann_val)
                            print(f"HWPAnn set to 0.01")

                    # Call future logic
                    try:
                        Ly = parent.femto_gui.calculate_future(sender=None, app_data=None, user_data=None)
                        print(f"Future calculation done for input: {future_args}")
                        if Ly is not None and dpg.does_item_exist("inInt_Ly_scan") and Ly > 0:
                            dpg.set_value("inInt_Ly_scan", int(Ly))
                            parent.opx.Update_Ly_Scan(user_data=int(Ly))
                            print(f"Ly set to {int(Ly)} nm in scan settings.")
                            parent.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                            parent.opx.Update_dY_Scan("inInt_dy_scan", 2000)
                        else:
                            print("inInt_Ly_scan not found or Ly = 0.")

                    except Exception as e:
                        print(f"Error calculating future: {e}")
                else:
                    print("Femto GUI or input tag not available.")
            # @desc: Press Femto calculate button
            elif single_command.lower() == "fmc":
                if parent and hasattr(parent, "femto_gui"):
                    try:
                        parent.femto_gui.calculate_button()
                    except Exception as e:
                        print(f"❌ Error running Femto calculate_button: {e}")
                else:
                    print("❌ Femto GUI not available.")
            # @desc: Trigger Femto pulses in OPX GUI
            elif single_command.lower() == "fmp":
                # Trigger the Femto Pulses button in the OPX GUI
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "btnFemtoPulses"):
                    try:
                        # 1) Set dx and dy to 2000 nm
                        if dpg.does_item_exist("inInt_dx_scan"):
                            parent.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                            print("dx step set to 2000 nm")
                        else:
                            print("DX input widget not found.")
                        if dpg.does_item_exist("inInt_dy_scan"):
                            parent.opx.Update_dY_Scan("inInt_dy_scan", 2000)
                            print("dy step set to 2000 nm")
                        else:
                            print("DY input widget not found.")
                        parent.opx.btnFemtoPulses()
                        print("Femto pulses triggered (btnFemtoPulses called).")
                    except Exception as e:
                        print(f"Error calling btnFemtoPulses: {e}")
                else:
                    print("OPX or btnFemtoPulses method not available.")
            # @desc: Stop OPX scan
            elif single_command.lower() in ("stp","stop"):
                # Trigger the Stop button in the OPX GUI
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "btnStop"):
                    try:
                        parent.opx.btnStop()
                        print("OPX scan stopped (btnStop called).")
                    except Exception as e:
                        print(f"Error calling btnStop: {e}")
                else:
                    print("OPX or btnStop method not available.")
            # @desc: Set HWP angle to degrees
            elif single_command.lower().startswith("angle"):
                # angle<value> → set the HWP to that angle in degrees
                try:
                    angle_val = float(single_command[len("angle"):].strip())
                except ValueError:
                    print("Invalid syntax. Use: angle<degrees>, e.g. angle22.5")
                    return
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "set_hwp_angle"):
                    try:
                        parent.opx.set_hwp_angle(angle_val)
                        parent.kdc_101_gui.read_current_angle()
                        print(f"HWP angle command: moved to {angle_val:.2f}°")
                    except Exception as e:
                        print(f"Failed to set HWP angle: {e}")
                else:
                    print("OPX GUI or set_hwp_angle() not available.")
            # @desc: Trigger OPX StartScan
            elif single_command.lower() in ("start", "startscan"):
                # Trigger the OPX “StartScan” button
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "btnStartScan"):
                    try:
                        toggle_sc(reverse=False)

                        # If dx > 200, reset both dx & dy based on dz
                        if dpg.does_item_exist("inInt_dx_scan"):
                            dx = dpg.get_value("inInt_dx_scan")
                            if dx > 200:
                                dz_value = 150  # fallback default
                                if dpg.does_item_exist("inInt_dz_scan"):
                                    dz_value = dpg.get_value("inInt_dz_scan")
                                parent = getattr(sys.stdout, "parent", None)
                                if parent and hasattr(parent, "opx"):
                                    if hasattr(parent.opx, "Update_dX_Scan"):
                                        parent.opx.Update_dX_Scan("inInt_dx_scan", dz_value)
                                    if hasattr(parent.opx, "Update_dY_Scan"):
                                        parent.opx.Update_dY_Scan("inInt_dy_scan", dz_value)
                                print(f"dx > 200: reset dx & dy to dz value {dz_value} nm")
                                time.sleep(0.5)

                        parent.opx.btnStartScan()
                        print("OPX scan started (btnStartScan called).")
                    except Exception as e:
                        print(f"Error calling btnStartScan: {e}")
                else:
                    print("OPX or btnStartScan method not available.")
            # @desc: Save recent command history to file
            elif single_command.lower() == "savehistory":
                # Save the current  history buffer to a file
                if parent and hasattr(parent, "command_history"):
                    fname = "command_history.txt"
                    try:
                        with open(fname, "w") as f:
                            for cmd in parent.command_history:
                                f.write(cmd.replace("\n", "") + "\n")
                        print(f"Saved {len(parent.command_history)} history entries to {fname}")
                    except Exception as e:
                        print(f"Error saving history: {e}")
                else:
                    print("No command history to save.")
            # @desc: Load command history from file
            elif single_command.lower() == "loadhistory":
                # Load history back from disk (overwrites current buffer)
                fname = "command_history.txt"
                if not os.path.exists(fname):
                    print(f"History file not found: {fname}")
                else:
                    try:
                        with open(fname, "r") as f:
                            lines = [line.strip() for line in f if line.strip()]
                        parent.command_history = lines[-10:]  # enforce your 10-item limit
                        parent.history_index = len(parent.command_history)
                        print(f"Loaded {len(parent.command_history)} entries from {fname}")
                    except Exception as e:
                        print(f"Error loading history: {e}")
            # @desc: Save processed image from Zelux GUI
            elif single_command.lower() == "sv":
                filename = parent.cam.SaveProcessedImage()
                if not filename:
                    print("SaveProcessedImage executed but returned no filename.")
                    break
                notes = getattr(parent.opx, "expNotes", "").strip().replace(" ", "_")
                base, ext = os.path.splitext(filename)
                new_name = f"{base}_{notes}{ext}" if notes else filename
                try:
                    if new_name != filename:
                        os.rename(filename, new_name)
                    print(f"Saved processed image: {new_name}")
                except Exception as e:
                    print(f"Image saved as {filename}, but could not rename: {e}")
            # @desc: Show all DPG windows
            elif single_command.lower() == "show windows":
                try:
                    window_names = []
                    for item in dpg.get_all_items():
                        item_type = dpg.get_item_type(item)
                        if "Window" in item_type:
                            tag = dpg.get_item_alias(item)
                            window_names.append((tag, item, item_type))
                    if window_names:
                        print("📋 DPG windows & child windows:")
                        for tag, item, item_type in window_names:
                            is_shown = dpg.is_item_shown(item)
                            print(f" {tag} [shown={is_shown}] type={item_type}")
                    else:
                        print("No DPG windows found.")
                except Exception as e:
                    print(f"Error listing windows: {e}")
            # @desc: Show a given DPG window
            elif single_command.lower().startswith("show "):
                try:
                    _, _, tag = single_command.partition(" ")
                    tag = tag.strip()
                    if not tag:
                        print("Usage: show <window_tag>")
                    elif dpg.does_item_exist(tag):
                        dpg.show_item(tag)
                        print(f"✅ Shown: {tag}")
                    else:
                        print(f"❌ Window '{tag}' not found.")
                except Exception as e:
                    print(f"Error showing window '{tag}': {e}")
            # @desc: Hide a given DPG window
            elif single_command.lower().startswith("hide "):
                try:
                    _, _, tag = single_command.partition(" ")
                    tag = tag.strip()
                    if not tag:
                        print("Usage: hide <window_tag>")
                    elif dpg.does_item_exist(tag):
                        dpg.hide_item(tag)
                        print(f"✅ Hidden: {tag}")
                    else:
                        print(f"❌ Window '{tag}' not found.")
                except Exception as e:
                    print(f"Error hiding window '{tag}': {e}")
            # @desc: Copy OPX initial scan location as Site (X,Y,Z)
            elif single_command.strip().lower() == "scpos":
                if hasattr(parent, "opx") and hasattr(parent.opx, "initial_scan_Location"):
                    import pyperclip
                    initial_pos = [v * 1e-6 for v in parent.opx.initial_scan_Location]
                    pos_str = f"Site ({initial_pos[0]:.1f}, {initial_pos[1]:.1f}, {initial_pos[2]:.1f})"
                    pyperclip.copy(pos_str)
                    print(f"Copied scan start location to clipboard: {pos_str}")
                else:
                    print("OPX or initial_scan_Location not available.")
            # @desc: Set Zelux camera exposure time to <N> milliseconds
            elif single_command.lower().startswith("exp"):
                try:
                    value_str = single_command[3:].strip()
                    if not value_str:
                        print("Usage: exp<N> → e.g. exp100 or exp15.5 for 15.5 ms.")
                        return

                    exposure_ms = float(value_str)  # ✅ Accept decimal values

                    if hasattr(parent, "cam") and hasattr(parent.cam, "cam") and hasattr(parent.cam.cam, "camera"):
                        parent.cam.cam.SetExposureTime(int(exposure_ms * 1e3))  # ms → µs, then int
                        time.sleep(0.001)

                        dpg.set_value("slideExposure", parent.cam.cam.camera.exposure_time_us / 1e3)
                        print(f"Actual exposure time: {parent.cam.cam.camera.exposure_time_us / 1e3:.1f} ms")
                    else:
                        print("Zelux camera not found.")
                except Exception as e:
                    print(f"Invalid exposure command or value: {e}")
            # @desc: Interactive viewer for visualizing all Z-slices in a CSV scan file; automatically uses the last loaded file.
            elif single_command.lower() == "disp":
                try:
                    if hasattr(parent.opx, "last_loaded_file") and parent.opx.last_loaded_file:
                        disp_script = os.path.join("Utils", "display_all_z_slices_with_slider.py")
                        filepath = parent.opx.last_loaded_file
                        import subprocess
                        subprocess.Popen(["python", disp_script, filepath], shell=True)
                        print(f"Displaying Z slices for {filepath}")
                    else:
                        print("No file loaded to display.")
                except Exception as e:
                    print(f"Error running 'disp': {e}")
            # @desc: Set total integration time and append note (e.g., int200)
            elif single_command.lower().startswith("int"):
                import re
                match = re.match(r"int(\d+)", single_command.lower())
                if match:
                    value_ms = int(match.group(1))
                    print(f"Setting integration time to {value_ms} ms")
                    parent.opx.UpdateCounterIntegrationTime(user_data=value_ms)
                    appended_note = f"!Int {value_ms} ms" # Append to note
                    run(f"note {appended_note}")
                else:
                    print(f"Could not parse integration time from: {single_command}, remove spaces.")
            # @desc: Enable or disable HRS_500 device for next run
            elif single_command.lower().startswith("nextrun "):
                import re
                action = single_command[len("nextrun "):].strip().lower()
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
            # @desc: Auto-scan all `elif` branches and display command descriptions; also supports `help <cmd>` for single command info
            elif single_command.lower().startswith("help"):
                import inspect, re
                parts = single_command.strip().split()
                query_cmd = parts[1].lower() if len(parts) > 1 else None
                run_src = inspect.getsource(run)
                pattern = r"#\s*@desc:(.*?)\n\s*elif\s+single_command.*?(\.\w+|\s*==|\s*!=|\s*startswith).*?['\"](.*?)['\"]"
                matches = re.findall(pattern, run_src, flags=re.DOTALL)
                if not matches:
                    print("No commands with @desc found.")
                    return

                lines = []
                for desc, _, cmd in matches:
                    desc = desc.strip()
                    cmd = cmd.strip()
                    lines.append((cmd.lower(), f"{cmd} -> {desc}"))

                lines.sort(key=lambda x: x[0]) # Sort by command name

                if query_cmd: # Search for specific command
                    filtered = [line for cmd, line in lines if query_cmd == cmd]
                    if filtered:
                        print(filtered[0])  # normal size
                    else:
                        print(f"Command '{query_cmd}' not found.")
                else: # Show all
                    help_txt = "Available commands:\n\n" + "\n".join(f" {l}" for _, l in lines)
                    show_msg_window(help_txt, height=1400)
                # help_txt = "Available commands:\n\n" + "\n".join(f" {l}" for l in lines)
                # show_msg_window(help_txt, height=1400)
            else: # Try to evaluate as a simple expression
                try:
                    result = eval(single_command, {"__builtins__": {}})
                    print(f"{single_command} = {result}")
                except Exception:
                    print(f"Unknown command: {single_command}")
        except Exception as e:
            print(f"Error running command '{single_command}': {e}")
        # dpg.focus_item("OPX Window")
        dpg.focus_item("cmd_input")

import builtins
builtins.run = run







import sys
import dearpygui.dearpygui as dpg
from Common import *
import pyperclip, os
from Utils import loadFromCSV
import importlib
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
        :param append_callback: Function to append messages to the Dear PyGui console.
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
        parent = sys.stdout.parent
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

        # If dx > 200, reset both dx & dy to 150 nm
        if dpg.does_item_exist("inInt_dx_scan"):
            dx = dpg.get_value("inInt_dx_scan")
            if dx > 200:
                dpg.set_value("inInt_dx_scan", 150)
                dpg.set_value("inInt_dy_scan", 150)
                parent = getattr(sys.stdout, "parent", None)
                if parent and hasattr(parent, "opx"):
                    # Trigger the same callbacks your GUI uses
                    if hasattr(parent.opx, "Update_dX_Scan"):
                        parent.opx.Update_dX_Scan("inInt_dx_scan", 150, None)
                    if hasattr(parent.opx, "Update_dY_Scan"):
                        parent.opx.Update_dY_Scan("inInt_dy_scan", 150, None)
                print("dx > 200: reset dx & dy to 150 nm")
    except Exception as e:
        print(f"Error in toggle_sc: {e}")

def run(command: str):
    """
        # Loop syntax:
        #   expects: loop <start> <end> <template>
        #   e.g.    loop 10 11 fq{i};msg Site {i} Spectrum…;spc;cc Site{i}

        Simple command handler for the Dear PyGui console.
        Supports single or multiple commands separated by ';':
          • 'angle<N>'        -> move half-wave plate to <N> degrees
          • 'att<N>'          -> set femto attenuator to <N>% and recalc future
          • 'c'               -> copy 'QuTi SW' window to clipboard
          • 'cc [suffix]'     -> schedule a delayed screenshot (optional suffix)
          • 'cn'              -> start live counter in OPX GUI
          • 'coords' / 'coo'  -> toggle coordinate grid in Zelux plot
          • 'fmp'             -> trigger femto pulses in OPX GUI
          • 'fn'              -> copy only filename from last message
          • 'fq[N]'           -> fill & move to N-th stored query point (or store new)
          • 'help'            -> show this menu
          • 'hl'              -> hide OPX plot legend
          • 'ld'              -> load & plot most recent CSV from last_scan_dir
          • 'loadhistory'     -> load command history from disk
          • 'loadlist'        -> load saved query points from file
          • 'loop'            -> loop a sequence of sub-commands from start to end
          • 'lp [name]'       -> load Smaract positions profile <name> ('r' for remote)
          • 'mark'            -> draw a temporary cross+circle at current position
          • 'msg <text>'      -> pop up a centered message window
          • 'msgclear'        -> close the message window
          • 'mv'              -> call move_last_saved_files()
          • 'note <text>'     -> write <text> into Notes field and save
          • 'plf'             -> annotate future femto energies on plot
          • 'reload [mod]'    -> reload a module or GUI component
          • 'sc' / '!sc'      -> stop/start camera & retract/extend flippers
          • 'savelist'        -> write stored query points to disk
          • 'savehistory'     -> write recent commands to disk
          • 'sp [name]'       -> save Smaract positions profile <name> ('r' for remote)
          • 'spc'             -> acquire HRS500 spectrum & tag with Notes
          • 'startscan'       -> trigger OPX StartScan
          • 'st'              -> fill Smaract XYZ from current position
          • 'stop' / 'stp'    -> trigger OPX Stop
          • 'sub <folder>'    -> set MoveSubfolderInput to '<folder>_suffix'
          • 'sv'              -> call SaveProcessedImage()
    """

    import os

    command = command.strip()
    parent = getattr(sys.stdout, "parent", None)
    cam = getattr(parent, "cam", None)
    if not hasattr(parent, "command_history"):
        parent.command_history = []
    parent.command_history.append(command)
    parent.command_history = parent.command_history[-100:]  # Keep last 100 commands
    parent.history_index = len(parent.command_history)  # Always reset index to END
    # expects: loop <start> <end> <template>
    # e.g. loop 10 11 fq{i};msg Site {i} Spectrum, Exposure 30s;spc;cc Site{i}
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
                subs = [cmd.strip().format(i=i)
                        for cmd in template.split(";") if cmd.strip()]
                # 2) Run everything *except* cc immediately or via DPG callback
                cc_suffixes = []
                for cmd in subs:
                    if cmd.lower().startswith("msg "):
                        msg_text1 = cmd.split(" ", 1)[1]
                        show_msg_window(msg_text1)
                        print(f"[loop {i}] scheduled: {cmd}")
                    elif cmd.lower().startswith("cc "):
                        # collect suffix for later
                        cc_suffixes.append(cmd.split(" ", 1)[1])
                    else:
                        print(f"[loop {i}] running: {cmd}")
                        run(cmd)
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
            if single_command == "c":
                copy_quti_window_to_clipboard()
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
                        print("cc: delayed save complete.")
                    except Exception as e:
                        print(f"cc: delayed save failed: {e}")
                timer = threading.Timer(0.3, delayed_save)
                timer.daemon = True
                timer.start()
                print("cc: screenshot scheduled in ~0.3 s")
            elif single_command == "hl":
                if hasattr(parent, "opx") and hasattr(parent.opx, "hide_legend"):
                    parent.opx.hide_legend()
                    print("OPX legend hidden.")
                else:
                    print("OPX or hide_legend() not available.")
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
            elif single_command == "mv":
                parent.opx.move_last_saved_files()
            elif single_command.startswith("clog "):
                arg = single_command.split("clog ", 1)[1].strip().lower()
                import subprocess
                subprocess.run([sys.executable, "clog.py", arg])
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
            elif single_command == "sc":
                toggle_sc(reverse=False)
            elif single_command in ("!sc", "l"):
                toggle_sc(reverse=True)
            elif single_command.startswith("sub "):
                try:
                    folder = single_command.split("sub ", 1)[1].strip()
                    suffix_file = "folder_suffix.txt"

                    # Ensure the suffix file exists
                    if not os.path.exists(suffix_file):
                        with open(suffix_file, "w") as f:
                            pass  # Create empty file

                    # Read suffix (default to empty string if file is empty)
                    with open(suffix_file, "r") as f:
                        suffix = f.read().strip()

                    full_folder = f"{folder}_{suffix}"

                    # Check if MoveSubfolderInput exists
                    if not dpg.does_item_exist("MoveSubfolderInput"):
                        dpg.set_value("chkbox_scan", True)
                        if hasattr(sys.stdout.parent, "opx"):
                            sys.stdout.parent.opx.Update_scan(app_data=None, user_data=True)

                    wait_for_item_and_set("MoveSubfolderInput", full_folder)
                    print(f"Subfolder set to: {full_folder}")
                except Exception as e:
                    print(f"Error in 'sub' command: {e}")
            elif single_command.startswith("cob "):
                try:
                    power_mw = float(single_command.split("cob ", 1)[1].strip())
                    p = getattr(sys.stdout, "parent", None)
                    if p and hasattr(p,"coboltGUI") and p.coboltGUI and p.coboltGUI.laser and p.coboltGUI.laser.is_connected():
                        p.coboltGUI.laser.set_modulation_power(power_mw)
                        print(f"Cobolt modulation power set to {power_mw:.2f} mW")
                    else:
                        print("Cobolt laser not connected or unavailable.")
                except Exception as e:
                    print(f"Failed to set Cobolt power: {e}")
            elif single_command == "pp":
                import subprocess
                subprocess.Popen([
                    sys.executable, "copy_window_to_clipboard.py"
                ])
                print("Launched external clipboard script.")
            elif single_command == "cn":
                if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "opx"):
                    sys.stdout.parent.opx.btnStartCounterLive()
                    print("Counter live started.")
                else:
                    print("Counter live not available.")
            elif single_command.startswith("lp"):
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
            elif single_command.startswith("sp "):
                # Example: sp r → save_pos("remote"), sp xyz → save_pos("xyz")
                arg = single_command.split("sp ", 1)[1].strip()
                profile_name = "remote" if arg == "r" else arg
                if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                    sys.stdout.parent.smaractGUI.save_pos(profile_name)
                    print(f"Saved positions with profile: {profile_name}")
                else:
                    print("smaractGUI not available.")
            elif single_command.startswith("reload"):
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

                    if raw_name and raw_name.lower() in ["gui_zelux", "zel"]:
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
            elif single_command == "plf":
                try:
                    parent = sys.stdout.parent
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
            elif single_command == "ld":
                try:
                    parent = sys.stdout.parent
                    if not hasattr(parent, "opx"):
                        print("Parent has no opx.")
                        return
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
            elif single_command.startswith("fq"):
                parent = getattr(sys.stdout, "parent", None)
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
                                    parent.opx.saveExperimentsNotes(sender=None, app_data=note_text)
                            else:
                                print(f"No stored point with index {index_to_go}.")
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
                        except Exception as e:
                            print(f"Could not store queried point: {e}")
                else:
                    print("OPX not available or missing 'fill_moveabs_from_query'.")
            elif single_command == "list":
                parent = getattr(sys.stdout, "parent", None)

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
            elif single_command == "loadlist":
                file_name = "saved_query_points.txt"
                if not os.path.exists(file_name):
                    print(f"File {file_name} not found.")
                    return
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
                    print(f"Loaded {len(parent.saved_query_points)} points from {file_name}")
                except Exception as e:
                    print(f"Error loading list: {e}")
            elif single_command == "spc":
                parent = getattr(sys.stdout, "parent", None)
                import glob
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "spc"):
                    if hasattr(parent.opx.spc, "acquire_Data"):
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
            elif single_command.startswith("msg "):
                msg_text = single_command.split(" ", 1)[1]
                show_msg_window(msg_text)
            elif single_command == "msgclear":
                if dpg.does_item_exist("msg_Win"):
                    dpg.delete_item("msg_Win")
                    print("Message window cleared.")
                else:
                    print("No message window to clear.")
            elif single_command == "st":
                if parent and hasattr(parent, "smaractGUI") and hasattr(parent.smaractGUI, "fill_current_position_to_moveabs"):
                    parent.smaractGUI.fill_current_position_to_moveabs()
                else:
                    print("smaractGUI or Set XYZ callback not available.")
            elif single_command.lower().startswith("note "):
                # Update the Notes field with the rest of the text
                note_text = single_command[len("note "):]
                show_msg_window(note_text)
                parent.opx.expNotes = note_text
                if dpg.does_item_exist("inTxtScan_expText"):
                    dpg.set_value("inTxtScan_expText", note_text)
                    try:
                        parent.opx.saveExperimentsNotes(sender=None, app_data=note_text)
                    except Exception:
                        pass
                print(f"Notes updated: {note_text}")
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
            elif single_command.lower() == "fmp":
                # Trigger the Femto Pulses button in the OPX GUI
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "btnFemtoPulses"):
                    try:
                        # 1) Set dx and dy to 2000 nm
                        if dpg.does_item_exist("inInt_dx_scan"):
                            dpg.set_value("inInt_dx_scan", 2000)
                            # trigger the same callback you wired up in the GUI
                            parent.opx.Update_dX_Scan("inInt_dx_scan", 2000)
                            print("dx step set to 2000 nm")
                        else:
                            print("DX input widget not found.")
                        if dpg.does_item_exist("inInt_dy_scan"):
                            dpg.set_value("inInt_dy_scan", 2000)
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
            elif single_command.lower() == "startscan":
                # Trigger the OPX “StartScan” button
                if parent and hasattr(parent, "opx") and hasattr(parent.opx, "btnStartScan"):
                    try:
                        parent.opx.btnStartScan()
                        print("OPX scan started (btnStartScan called).")
                    except Exception as e:
                        print(f"Error calling btnStartScan: {e}")
                else:
                    print("OPX or btnStartScan method not available.")
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
            elif single_command.lower() == "help":
                # Extract the bullet-list from our own docstring and display it
                import inspect
                doc = inspect.getdoc(run) or ""
                # grab only the lines starting with a bullet
                lines = [l.strip()[2:] for l in doc.splitlines() if l.strip().startswith("•")]
                help_txt = "\n".join(lines)
                show_msg_window(help_txt)
                print("Displayed help menu in msg window.")
            else: # Try to evaluate as a simple expression
                try:
                    result = eval(single_command, {"__builtins__": {}})
                    print(f"{single_command} = {result}")
                except Exception:
                    print(f"Unknown command: {single_command}")
        except Exception as e:
            print(f"Error running command '{single_command}': {e}")

import builtins
builtins.run = run







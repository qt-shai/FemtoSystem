import sys
import dearpygui.dearpygui as dpg
from Common import *
import pyperclip, os
from Utils import loadFromCSV
import importlib
import HW_wrapper.HW_devices as hw_devices
from HW_GUI.GUI_MFF_101 import GUI_MFF


# To copy the last message to the clipboard:
# import pyperclip; pyperclip.copy(sys.stdout.messages[-2])

# To copy all messages as a single block:
# import pyperclip; pyperclip.copy("".join(sys.stdout.messages))

# To extract and copy only the filename from the last message in your console
# import pyperclip, os; pyperclip.copy(os.path.basename(sys.stdout.messages[-1].strip().split("→")[-1].strip()))

# To fill the Dear PyGui input field with tag "MoveSubfolderInput" with the text "Omri_6-5-25" from your console GUI, simply run this one-liner command:
# dpg.set_value("MoveSubfolderInput", "Omri_6-5-25")
# dpg.set_value("MoveSubfolderInput", "ELSC_6-5-25")

# Terminal logged_points.txt commands:
# python clog.py o
# python clog.py e

# self.mff_101_gui[0].on_off_slider_callback(self.mff_101_gui[0],1)
# self.mff_101_gui[0].dev.get_position()

# import importlib, Outout_to_gui; importlib.reload(Outout_to_gui

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


def run(command: str):
    """
    Simple command handler for the Dear PyGui console.
    Supports:
    - 'c' → copy 'QuTi SW' window to clipboard
    - 'sv' → call SaveProcessedImage()
    - 'mv' → call move_last_saved_files()
    - 'sub <folder>' → set MoveSubfolderInput to '<folder>_6-5-25'
    - 'fn' → copy only filename from last message like: "Copied ... → .../file.ext"
    - 'sc or !sc' toggles both flippers using the existing on_off_slider_callback method only if each flipper is in position 1
    - 'sub'
    - 'cn' counter
    - 'reload'
    - 'ld' load last file
    -- ("coords", "coo"): shows coordinates in zelux
    """
    command = command.strip()
    try:
        parent = getattr(sys.stdout, "parent", None)
        cam = getattr(parent, "cam", None)
        if command == "c":
            copy_quti_window_to_clipboard()
        elif command == "sv":
            if cam and hasattr(cam, "SaveProcessedImage"):
                cam.SaveProcessedImage()
                print("SaveProcessedImage executed.")
            else:
                print("SaveProcessedImage not available.")
        elif command == "mv":
            if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "move_last_saved_files"):
                sys.stdout.parent.move_last_saved_files()
                # Try to extract and copy the last moved filename
                if hasattr(sys.stdout, "messages") and sys.stdout.messages:
                    last_msg = sys.stdout.messages[-1].strip()
                    if "→" in last_msg:
                        filepath = last_msg.split("→")[-1].strip()
                        filename = os.path.basename(filepath)
                        import pyperclip
                        pyperclip.copy(filename)
                        print(f"Filename copied to clipboard: {filename}")
            else:
                print("move_last_saved_files not available.")
        elif command.startswith("clog "):
            arg = command.split("clog ", 1)[1].strip().lower()
            import subprocess
            subprocess.run([sys.executable, "clog.py", arg])
        elif command == "fn":
            import pyperclip
            if hasattr(sys.stdout, 'messages') and sys.stdout.messages:
                last_msg = sys.stdout.messages[-1].strip()
                if "→" in last_msg:
                    filepath = last_msg.split("→")[-1].strip()
                    filename = os.path.basename(filepath)
                    pyperclip.copy(filename)
                    print(f"Filename copied: {filename}")
                else:
                    print("No '→' found in last message.")
            else:
                print("No messages found in sys.stdout.")
        elif command == "sc":
            toggle_sc(reverse=False)
        elif command in ("!sc", "!"):
            toggle_sc(reverse=True)
        elif command.startswith("sub "):
            try:
                folder = command.split("sub ", 1)[1].strip()
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
        elif command.startswith("cob "):
            try:
                power_mw = float(command.split("cob ", 1)[1].strip())
                p = getattr(sys.stdout, "parent", None)
                if p and hasattr(p,"coboltGUI") and p.coboltGUI and p.coboltGUI.laser and p.coboltGUI.laser.is_connected():
                    p.coboltGUI.laser.set_modulation_power(power_mw)
                    print(f"Cobolt modulation power set to {power_mw:.2f} mW")
                else:
                    print("Cobolt laser not connected or unavailable.")
            except Exception as e:
                print(f"Failed to set Cobolt power: {e}")
        elif command == "pp":
            import subprocess
            subprocess.Popen([
                sys.executable, "copy_window_to_clipboard.py"
            ])
            print("Launched external clipboard script.")
        elif command == "cn":
            if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "opx"):
                sys.stdout.parent.opx.btnStartCounterLive()
                print("Counter live started.")
            else:
                print("Counter live not available.")
        elif command.startswith("lp "):
            # Example: lp r → load_pos("remote"), lp xyz → load_pos("xyz")
            arg = command.split("lp ", 1)[1].strip()
            profile_name = "remote" if arg == "r" else arg
            if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                sys.stdout.parent.smaractGUI.load_pos(profile_name)
                print(f"Loaded positions with profile: {profile_name}")
            else:
                print("smaractGUI not available.")
        elif command.startswith("sp "):
            # Example: sp r → save_pos("remote"), sp xyz → save_pos("xyz")
            arg = command.split("sp ", 1)[1].strip()
            profile_name = "remote" if arg == "r" else arg
            if hasattr(sys.stdout, "parent") and hasattr(sys.stdout.parent, "smaractGUI"):
                sys.stdout.parent.smaractGUI.save_pos(profile_name)
                print(f"Saved positions with profile: {profile_name}")
            else:
                print("smaractGUI not available.")
        elif command.startswith("reload"):
            try:
                import importlib
                parts = command.split()
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
                else:
                    if module_name in sys.modules:
                        module = sys.modules[module_name]
                        importlib.reload(module)
                        print(f"Reloaded: {module_name}")
                    else:
                        module = importlib.import_module(module_name)
                        print(f"Imported and reloaded: {module_name}")
            except Exception as e:
                print(f"Reload failed for '{module_name}': {e}")
        elif command == "plf":
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
        elif command == "ld":
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
                print(f"Loaded and plotted: {fn}")
            except Exception as e:
                print(f"Error in ld command: {e}")
        elif command in ("coords", "coo"):
            parent = getattr(sys.stdout, "parent", None)
            if parent and hasattr(parent, "cam") and hasattr(parent.cam, "toggle_coords_display"):
                # Flip the current flag
                current = getattr(parent.cam, "show_coords_grid", False)
                new_value = not current
                parent.cam.toggle_coords_display(None, new_value)
                print(f"Coordinate grid display set to: {new_value}")
            else:
                print("cam or toggle_coords_display not available.")
        else: # Try to evaluate as a simple expression
            try:
                result = eval(command, {"__builtins__": {}})
                print(f"{command} = {result}")
            except Exception:
                print(f"Unknown command: {command}")
    except Exception as e:
        print(f"Error running command '{command}': {e}")
    finally:
        # 🟢 Always refocus your input box
        if dpg.does_item_exist("cmd_input"):
            dpg.focus_item("cmd_input")
import builtins
builtins.run = run







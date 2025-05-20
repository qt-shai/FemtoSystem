import sys
import dearpygui.dearpygui as dpg
from Common import *
import pyperclip, os

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
    """
    command = command.strip().lower()
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
            try:
                parent = sys.stdout.parent
                cam = getattr(parent, "cam", None)
                mff = getattr(parent, "mff_101_gui", [])

                for flipper in mff:
                    slider_tag = f"on_off_slider_{flipper.unique_id}"
                    if flipper.dev.get_position() == 1:
                        flipper.on_off_slider_callback(slider_tag,1)

                # Stop live camera feed if active
                if cam and hasattr(cam, "StopLive"):
                    cam.StopLive()
                    print("Camera live view stopped.")

            except Exception as e:
                print(f"Error running 'sc': {e}")

        elif command == "!sc":
            try:
                parent = sys.stdout.parent
                cam = getattr(parent, "cam", None)
                mff = getattr(parent, "mff_101_gui", [])

                # Flip flippers where position is 2
                for flipper in mff:
                    slider_tag = f"on_off_slider_{flipper.unique_id}"
                    if flipper.dev.get_position() == 2:
                        flipper.on_off_slider_callback(slider_tag, 0)

                # Start live view
                if cam and hasattr(cam, "StartLive"):
                    cam.StartLive()
                    print("Camera live view started.")
            except Exception as e:
                print(f"Error running '!sc': {e}")


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

                # Check if MoveSubfolderInput existss
                if not dpg.does_item_exist("MoveSubfolderInput"):
                    dpg.set_value("chkbox_scan", True)
                    if hasattr(sys.stdout.parent, "opx"):
                        sys.stdout.parent.opx.Update_scan(app_data=None, user_data=True)

                wait_for_item_and_set("MoveSubfolderInput", full_folder)
                print(f"Subfolder set to: {full_folder}")
            except Exception as e:
                print(f"Error in 'sub' command: {e}")

        elif command == "pp":
            import subprocess
            subprocess.Popen([
                sys.executable, "copy_window_to_clipboard.py"
            ])
            print("Launched external clipboard script.")


        else:
            print(f"Unknown command: {command}")
    except Exception as e:
        print(f"Error running command '{command}': {e}")

import builtins
builtins.run = run







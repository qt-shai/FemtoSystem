import sys
import dearpygui.dearpygui as dpg
from Common import *

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
                print("move_last_saved_files executed.")
            else:
                print("move_last_saved_files not available.")

        elif command.startswith("clog "):
            arg = command.split("clog ", 1)[1].strip().lower()
            if arg in ["e", "o", "p"]:
                import subprocess
                subprocess.run([sys.executable, "clog.py", arg])
            else:
                print("Invalid clog argument. Use e, o, or p.")

        elif command == "fn":
            import pyperclip, os
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


        else:
            print(f"Unknown command: {command}")
    except Exception as e:
        print(f"Error running command '{command}': {e}")

import builtins
builtins.run = run







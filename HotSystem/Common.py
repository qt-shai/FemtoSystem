import datetime
import json
import sys
import tempfile
import traceback
from datetime import datetime
import socket
import threading
from enum import Enum
import os
import time
import dearpygui.dearpygui as dpg
from matplotlib import pyplot as plt

import pyautogui
import win32gui
import win32clipboard
from PIL import ImageGrab
import io

import win32con
from datetime import datetime
import ctypes
import win32process
from screeninfo import get_monitors
from PIL import ImageGrab, PngImagePlugin
from pathlib import Path

def get_primary_resolution():
    for m in get_monitors():
        if m.is_primary:
            return (m.width, m.height)
    return (0, 0)
    # USAGE
    # w, h = get_primary_resolution()
    # print(f"Primary screen resolution: {w} x {h}")

# add bubble sort
class Common_Counter_Singletone:
    # create singleton
    _instance = None
    _lock = threading.Lock()

    def __new__(self):
        with self._lock:
            if self._instance is None:
                self._instance = super(Common_Counter_Singletone, self).__new__(self)
            else:
                # print("Application all ready exist!")
                pass
        return self._instance

    # def __init__(self):
    #     self.counter = 0
    #     pass

    def Reset(self):
        self.counter = 0

    def Step_up(self):
        self.counter += 1

    def Step_down(self):
        self.counter -= 1

def get_ip_address(domain_name: str) -> str:
    """
    Look up a domain name in the DNS and return the corresponding IP address.

    :param domain_name: The domain name to look up.
    :return: The corresponding IP address.
    """
    try:
        ip_address = socket.gethostbyname(domain_name)
        return ip_address
    except socket.gaierror:
        return "Invalid domain name or DNS lookup failure."

def getCurrentTimeStamp() -> str:
    """Get the current timestamp in the format: Year_Month_Day_Hour_Minute_Second."""
    try:
        # Attempt to get the current time
        now = datetime.now()
        # Create a timestamp string using the current time
        timestamp = f"{now.year}_{now.month}_{now.day}_{now.hour}_{now.minute}_{now.second}"
        return timestamp
    except AttributeError as e:
        print(f"AttributeError encountered: {e}. Returning generic timestamp.")
    except Exception as e:
        print(f"An error occurred while getting the timestamp: {e}. Returning generic timestamp.")

    # Return a generic timestamp if an error occurs
    return "1970_01_01_00_00_00"

# Example usage:
# ip = get_ip_address("example.com")
# print(ip)

class KeyboardKeys(Enum): # Mapping keys to custom values
    CTRL_KEY = 17
    ALT_KEY = 18
    UP_KEY = 38
    DOWN_KEY = 40
    LEFT_KEY = 37
    RIGHT_KEY = 39
    SHIFT_KEY = 16
    PAGEUP_KEY = 33
    PAGEDOWN_KEY = 34
    SPACE_KEY = 32
    PLUS_KEY = 107
    MINUS_KEY = 109
    ENTER_KEY = 13
    BACK_KEY = 8
    HOME_KEY = 36
    END_KEY = 35
    INSERT_KEY = 45
    DEL_KEY = 46

    ESC_KEY = 27
    TAB_KEY = 9
    F1_KEY = 112
    F2_KEY = 113
    F3_KEY = 114
    F4_KEY = 115
    F5_KEY = 116
    F6_KEY = 117
    F7_KEY = 118
    F8_KEY = 119
    F9_KEY = 120
    F10_KEY = 121
    F11_KEY = 122
    F12_KEY = 123

    A_KEY = 65
    B_KEY = 66
    C_KEY = 67
    D_KEY = 68
    E_KEY = 69
    F_KEY = 70
    G_KEY = 71
    H_KEY = 72
    I_KEY = 73
    J_KEY = 74
    K_KEY = 75
    L_KEY = 76
    M_KEY = 77
    N_KEY = 78
    O_KEY = 79
    P_KEY = 80
    Q_KEY = 81
    R_KEY = 82
    S_KEY = 83
    T_KEY = 84
    U_KEY = 85
    V_KEY = 86
    W_KEY = 87
    X_KEY = 88
    Y_KEY = 89
    Z_KEY = 90

    # ─── OEM keys and punctuation ───
    OEM_COMMA = 188  # ,
    OEM_PERIOD = 190  # .
    OEM_1 = 186  # ; :
    OEM_2 = 191  # / ?
    OEM_3 = 192  # ` ~  backtick/tilde
    OEM_4 = 219  # [ {
    OEM_5 = 220  # \ |
    OEM_6 = 221  # ] }
    OEM_7 = 222  # ' "
    OEM_PLUS = 187  # = +
    OEM_MINUS = 189  # - _

    # ─── Printable digits ───
    KEY_0 = 48
    KEY_1 = 49
    KEY_2 = 50
    KEY_3 = 51
    KEY_4 = 52
    KEY_5 = 53
    KEY_6 = 54
    KEY_7 = 55
    KEY_8 = 56
    KEY_9 = 57

from PIL import Image, ImageEnhance

def increase_brightness(image_path: str, output_path: str, factor: float) -> None:
    """
    Increase the brightness of a PNG image and save the result.

    :param image_path: Path to the input PNG image.
    :param output_path: Path to save the modified image.
    :param factor: Brightness adjustment factor. 1.0 means no change,
                   less than 1.0 will decrease brightness, more than 1.0 will increase brightness.
    :return: None
    """
    # Open the image
    with Image.open(image_path) as img:
        # Create an enhancer object for brightness
        enhancer = ImageEnhance.Brightness(img)
        # Apply the brightness factor
        img_enhanced = enhancer.enhance(factor)
        # Save the enhanced image
        img_enhanced.save(output_path)

class DpgThemes:
    
    def __init__(self):
        pass
    
    @staticmethod
    def color_theme(color, text_color, use_background: bool = False):
        with dpg.theme() as theme:
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, color, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Text, text_color, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, color, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, color, category=dpg.mvThemeCat_Core)
                dpg.add_theme_color(dpg.mvThemeCol_Button, color, category=dpg.mvThemeCat_Core)    # + and - buttons background
                dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, color, category=dpg.mvThemeCat_Core)  # Hover color for + and - buttons
                dpg.add_theme_color(dpg.mvThemeCol_WindowBg, color)  # Green color with full opacity

        return theme
                

def save_figure(fileName, data, format_ext:str = "jpg"):
    # Save slice2D as a high-resolution image with a Jet colormap using Matplotlib
    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)  # Set high resolution (300 DPI)
    cax = ax.imshow(data, cmap='jet', interpolation='nearest')  # Apply Jet colormap
    fig.colorbar(cax)  # Add colorbar for reference
    plt.axis('off')  # Remove axis for a cleaner image
    plt.savefig(fileName + "." + format_ext, bbox_inches='tight', pad_inches=0)  # Save as high-resolution image
    plt.close()  # Close the plot to free up resources

class WindowNames(Enum):
    PICO = "pico_Win"
    MCS = "mcs_Win"
    ZELUX = "Zelux Window"
    WAVEMETER = "Wavemeter_Win"
    HIGHLAND_T130 = "HighlandT130_Win"
    MATISSE = "Matisse_Win"
    OPX = "OPX Window"
    MAP = "Map_window"
    SCAN = "Scan_Window"
    LASER = "LaserWin"
    ARDUINO = "Arduino_Win"
    SIM960 = "SIM960_Win"
    ATTO_SCANNER = "MotorWin_ANC300"
    ATTO_POSITIONER = "MotorWin_atto_positioner"
    MOKUGO = "Moku_Win"
    CONSOL = "console_window"

def is_remote_resolution() -> bool:
    """
    Detect if the system is running on the 'remote' resolution.
    This matches the check used in load_window_positions().
    """
    try:
        w, h = get_primary_resolution()
        print(f"[is_remote_resolution] Primary resolution: {w} x {h}")

        # Adjust to your real remote screen dimensions
        if w == 3840 and h == 1600:
            print("[is_remote_resolution] Remote resolution detected -> True")
            return True
        else:
            print("[is_remote_resolution] Local resolution -> False")
            return False

    except Exception as e:
        print(f"[is_remote_resolution] Error detecting resolution: {e}")
        return False

def toggle_sc(reverse=False):
    try:
        parent = getattr(sys.stdout, "parent", None)
        cam = getattr(parent, "cam", None)
        mff = getattr(parent, "mff_101_gui", [])
        if cam:
            if reverse and hasattr(cam, "StartLive"):
                cam.StartLive()
                print("Camera live view started.")
                if not parent.opx.counter_is_live:
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

def load_window_positions(file_name: str | None = None, *cb_args, **cb_kwargs) -> None:
    """
    Can be used as a DearPyGui callback (extra args ignored).
    If bound without args, DearPyGui will pass the sender (int) as the first positional arg,
    so we must NOT assume the first arg is a path.
    """

    def _safe_log(msg: str) -> None:
        try:
            sys.__stdout__.write(str(msg) + "\n")
            sys.__stdout__.flush()
        except Exception:
            try:
                import dearpygui.dearpygui as dpg
                dpg.log_error(str(msg))
            except Exception:
                pass

    # ---- COERCE/RESOLVE file_name ----
    # If load_window_positions is called as a DPG callback, file_name may be an int (sender).
    # Use it only if it's a path-like; otherwise treat as None and pick default.
    def _is_pathlike(x):
        try:
            from os import PathLike
            return isinstance(x, (str, bytes, PathLike))
        except Exception:
            return isinstance(x, (str, bytes))

    # NEW: read options
    include_main = bool(cb_kwargs.get("include_main", False))
    main_tag_opt = cb_kwargs.get("main_tag")  # may be None

    # If caller passed file_name as a kw-only or normal arg AND it's path-like, keep it;
    # else ignore and choose default below.
    file_name = file_name if _is_pathlike(file_name) else None

    # Optionally allow passing the filename via app_data in cb_args[1]
    if file_name is None and cb_args:
        # DearPyGui passes: sender, app_data, user_data
        app_data = cb_args[1] if len(cb_args) > 1 else None
        if _is_pathlike(app_data):
            file_name = app_data

    try:
        import dearpygui.dearpygui as dpg
    except Exception as e:
        _safe_log(f"[load] DearPyGui not available: {e}")
        return

    # Pick default file if still None
    if not file_name:
        try:
            is_remote = False
            try:
                is_remote = is_remote_resolution()
            except Exception:
                pass
            file_name = "win_pos_remote.txt" if is_remote else "win_pos_local.txt"
            _safe_log(f"Using {file_name}{' (remote)' if is_remote else ''}")
        except Exception as e:
            _safe_log(f"[load] Failed to resolve filename: {e}")
            return

    pth = Path(file_name)
    if not pth.exists():
        _safe_log(f"{file_name} not found.")
        return

    # Read safely
    try:
        text = pth.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
    except Exception as e:
        _safe_log(f"[load] Failed reading '{file_name}': {e}")
        return

    window_positions = {}
    window_sizes = {}

    # Parse lines
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if "_Pos:" in line:
            try:
                name, val = line.split("_Pos:")
                x, y = map(float, val.split(","))
                window_positions[name.strip()] = (x, y)
            except Exception as e:
                _safe_log(f"[parse] Bad pos line '{line}': {e}")
        elif "_Size:" in line:
            try:
                name, val = line.split("_Size:")
                w, h = map(float, val.split(","))
                window_sizes[name.strip()] = (int(w), int(h))
            except Exception as e:
                _safe_log(f"[parse] Bad size line '{line}': {e}")

    # Apply positions/sizes (with Keysight prefix fallback)
    try:
        all_items = dpg.get_all_items()
        aliases = {dpg.get_item_alias(i) or str(i): i for i in all_items}
    except Exception as e:
        _safe_log(f"[load] Could not enumerate DPG items: {e}")
        aliases = {}

    for key, pos in window_positions.items():
        applied = False
        try:
            if key in aliases or dpg.does_item_exist(key):
                dpg.set_item_pos(key, pos)
                applied = True
            elif key.startswith("Keysight33500B_Win"):
                for alias in aliases:
                    if alias.startswith("Keysight33500B_Win"):
                        dpg.set_item_pos(alias, pos)
                        applied = True
                        break
            _safe_log(f"Loaded position for '{key}' -> {pos}" if applied
                      else f"[load] position target not found: '{key}'")
        except Exception as e:
            _safe_log(f"[load] Failed setting pos for '{key}': {e}")

    for key, (w, h) in window_sizes.items():
        if key == "plotImaga":
            continue
        applied = False
        try:
            if key in aliases or dpg.does_item_exist(key):
                dpg.set_item_width(key, w)
                dpg.set_item_height(key, h)
                applied = True
            elif key.startswith("Keysight33500B_Win"):
                for alias in aliases:
                    if alias.startswith("Keysight33500B_Win"):
                        dpg.set_item_width(alias, w)
                        dpg.set_item_height(alias, h)
                        applied = True
                        break
            _safe_log(f"Loaded size for '{key}' → {w}×{h}" if applied
                      else f"[load] size target not found: '{key}'")
        except Exception as e:
            _safe_log(f"[load] Failed setting size for '{key}': {e}")

    # Restore plotImaga if present
    graph_tag = "plotImaga"
    try:
        if graph_tag in window_sizes and dpg.does_item_exist(graph_tag):
            w, h = window_sizes[graph_tag]
            dpg.set_item_width(graph_tag, w)
            dpg.set_item_height(graph_tag, h)
            p = getattr(sys.stdout, "parent", None)
            if p is not None and hasattr(p, "opx"):
                setattr(p.opx, "graph_size_override", (w, h))
            _safe_log(f"Loaded graph size for '{graph_tag}': {w}×{h}")
        else:
            _safe_log(f"No saved size for graph '{graph_tag}', or it wasn't found.")
    except Exception as e:
        _safe_log(f"[load] Failed restoring plot '{graph_tag}': {e}")

    # ---------- NEW: optionally resize the main window / viewport ----------
    if include_main:
        try:
            sizes_ci = {k.lower(): v for k, v in window_sizes.items()}
            pick_w_h = None
            if "viewport" in sizes_ci:
                pick_w_h = sizes_ci["viewport"]
            w, h = map(int, pick_w_h)
            try:
                dpg.set_viewport_width(w)
                dpg.set_viewport_height(h)
                _safe_log(f"Resized primary viewport from Viewport_Size' → {w}x{h}")
                return
            except Exception:
                pass
        except Exception as e:
            _safe_log(f"[load] Failed resizing main window/viewport: {e}")

def copy_image_to_clipboard(image_path):
    image = Image.open(image_path)

    # Convert image to DIB format for Windows clipboard
    output = io.BytesIO()
    image.convert("RGB").save(output, "BMP")
    data = output.getvalue()[14:]  # skip BMP header (14 bytes)
    output.close()

    # Set clipboard data
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()
    print("Image copied to clipboard.")

def save_quti_window_screenshot(suffix: str = None):
    window_title = "QuTi SW"
    hwnd = win32gui.FindWindow(None, None)

    def enum_handler(h, _):
        if window_title.lower() in win32gui.GetWindowText(h).lower():
            nonlocal hwnd
            hwnd = h
    win32gui.EnumWindows(enum_handler, None)

    if hwnd == 0:
        print("Window 'QuTi SW' not found.")
        return

    # Bring to front
    win32gui.ShowWindow(hwnd, 5)  # SW_SHOW
    win32gui.SetForegroundWindow(hwnd)
    win32gui.BringWindowToTop(hwnd)

    # Get window rect
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)

    # Screenshot
    screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))

    # Get save directory from last_scan_dir.txt
    try:
        with open("last_scan_dir.txt", "r") as f:
            save_dir = f.read().strip()
    except Exception as e:
        print(f"Error reading last_scan_dir.txt: {e}")
        return

    if not os.path.isdir(save_dir):
        print(f"Directory does not exist: {save_dir}")
        return

    # Build filename
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    # sanitize suffix for filesystem
    if suffix:
        safe = "".join(c for c in suffix if c.isalnum() or c in (" ", "_", "-")).rstrip()
        fname = f"QUTI_{timestamp}_{safe}.png"
    else:
        fname = f"QUTI_{timestamp}.png"

    save_path = os.path.join(save_dir, fname)

    # Save it
    try:
        screenshot.save(save_path)
        print(f"Saved QUTI window screenshot: {save_path}")
    except Exception as e:
        print(f"Failed to save screenshot: {e}")

def show_msg_window(msg_text: str,height=110):
    window_tag = "msg_Win"
    drawlist_tag = "msg_drawlist"
    # Remove old window if it exists
    if dpg.does_item_exist(window_tag):
        dpg.delete_item(window_tag)
    width = 1450
    # Create a new window in the center-ish
    with dpg.window(
        label="Message",
        tag=window_tag,
        no_title_bar=True,
        no_resize=False,
        pos=[0, 40],
        width=width,
        height=height
    ):
        # A drawlist lets us use draw_text with size
        dpg.add_drawlist(width=width, height=100, tag="msg_drawlist")
        dpg.draw_text(
            pos=(0, 0),
            text=msg_text,
            color=(255, 255, 0, 255),
            size=100,
            parent=drawlist_tag
        )
        # child_window for scrolling
        dpg.add_child_window(tag="msg_child", parent=window_tag)
        dpg.add_text(
            default_value=msg_text,
            wrap=width,  # wrap just inside the child width
            parent="msg_child",
            color=(255, 255, 0, 255),
        )
        dpg.add_button(label="Close", callback=lambda: dpg.delete_item(window_tag))

    print(f"Displayed message in {window_tag}: {msg_text}")

def copy_quti_window_to_clipboard(metadata_dict: dict = None):
    window_title = "QuTi SW"
    hwnd = win32gui.FindWindow(None, None)

    def enum_handler(h, _):
        if window_title.lower() in win32gui.GetWindowText(h).lower():
            nonlocal hwnd
            hwnd = h
    win32gui.EnumWindows(enum_handler, None)

    if hwnd == 0:
        print("Window 'QuTi SW' not found.")
        return

    # If minimized, restore (doesn't force foreground)
    if win32gui.IsIconic(hwnd):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        time.sleep(0.15)

    try:
        win32gui.ShowWindow(hwnd, 5)
        win32gui.SetForegroundWindow(hwnd)
        win32gui.BringWindowToTop(hwnd)
    except Exception as e:
        print(f"Error copying window screenshot: {e}")

    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))

    png_info = PngImagePlugin.PngInfo()
    if metadata_dict:
        try:
            metadata_json = json.dumps(metadata_dict)
            png_info.add_text("Description", metadata_json)
        except Exception as e:
            print(f"Failed to encode metadata: {e}")

    # Save to temp file with metadata
    tmp_path = os.path.join(tempfile.gettempdir(), "quti_clip_with_meta.png")
    screenshot.save(tmp_path, "PNG", pnginfo=png_info)

    # Copy screenshot to clipboard as BMP (no metadata, just visual)
    output = io.BytesIO()
    screenshot.convert("RGB").save(output, "BMP")
    bmp_data = output.getvalue()[14:]
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp_data)
    win32clipboard.CloseClipboard()

    print(f"Copied 'QuTi SW' to clipboard (visual only); metadata saved in temp: {tmp_path}")

def wait_for_item_and_set(tag: str, value: str, max_retries=50, delay=0.1):
    import threading, time
    def check_loop():
        for _ in range(max_retries):
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, value)
                print(f"Set {tag} to: {value}")
                return
            time.sleep(delay)
        print(f"[!] Failed to set {tag}, item not found after {max_retries} retries.")
    threading.Thread(target=check_loop, daemon=True).start()

class Experiment(Enum):
    SCRIPT = 0
    RABI = 1
    ODMR_CW = 2
    POPULATION_GATE_TOMOGRAPHY = 3
    COUNTER = 4
    PULSED_ODMR = 5
    NUCLEAR_RABI = 6
    NUCLEAR_POL_ESR = 7
    NUCLEAR_MR = 8
    ENTANGLEMENT_GATE_TOMOGRAPHY = 9
    G2 = 10
    SCAN = 11
    Nuclear_spin_lifetimeS0 = 12
    Nuclear_spin_lifetimeS1 = 13
    Nuclear_Ramsay = 14
    Hahn = 15
    Electron_lifetime = 16
    Electron_Coherence = 17
    ODMR_Bfield = 18
    Nuclear_Fast_Rot = 19
    TIME_BIN_ENTANGLEMENT = 20
    PLE = 21 # Photoluminescence excitation
    EXTERNAL_FREQUENCY_SCAN = 22
    AWG_FP_SCAN = 23
    testCrap = 24
    RandomBenchmark = 25
    test_electron_spinPump = 1001
    test_electron_spinMeasure = 1002


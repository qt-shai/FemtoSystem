import datetime
from datetime import datetime
import socket
import threading
from enum import Enum

import dearpygui.dearpygui as dpg
from matplotlib import pyplot as plt


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

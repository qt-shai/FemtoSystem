import pygetwindow as gw
import win32clipboard
import time
import io
import mss
from PIL import Image
import unicodedata
import keyboard
import time


def normalize_title(title):
    """Normalize title by removing invisible Unicode characters and lowercasing."""
    return unicodedata.normalize('NFKD', title).encode('ascii', errors='ignore').decode().lower()

def copy_browser_window_to_clipboard(target_substring, crop_top_px=0, crop_bottom_px=0,
                                     crop_left_px=0, crop_right_px=0, resize_ratio=0.5):
    """Copy a browser window to clipboard with optional cropping and resizing."""

    target_substring = normalize_title(target_substring)
    matches = [
        w for w in gw.getWindowsWithTitle("")
        if w.visible and target_substring in normalize_title(w.title)
    ]

    if not matches:
        print(f"❌ No window found matching title substring: {target_substring}")
        return

    win = matches[0]
    print(f"✅ Found window: {win.title}")

    # Bring window to front
    win.restore()
    win.activate()
    time.sleep(0.5)

    # Grab screenshot and crop
    with mss.mss() as sct:
        full_bbox = {
            "top": win.top + crop_top_px,
            "left": win.left + crop_left_px,
            "width": max(1, win.width - crop_left_px - crop_right_px),
            "height": max(1, win.height - crop_top_px - crop_bottom_px)
        }
        screenshot = sct.grab(full_bbox)
        img = Image.frombytes("RGB", screenshot.size, screenshot.rgb)

    # Resize the image
    new_size = (max(1, int(img.width * resize_ratio)), max(1, int(img.height * resize_ratio)))
    img = img.resize(new_size, Image.LANCZOS)

    # Copy to clipboard
    output = io.BytesIO()
    img.convert("RGB").save(output, format="BMP")
    data = output.getvalue()[14:]  # Skip BMP header
    output.close()

    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
    win32clipboard.CloseClipboard()

    print("📋 Cropped and resized window copied to clipboard.")

    # 🔁 Activate PowerPoint window
    ppt_matches = [w for w in gw.getWindowsWithTitle("") if "powerpoint" in normalize_title(w.title)]
    if ppt_matches:
        ppt_window = ppt_matches[0]
        ppt_window.restore()
        ppt_window.activate()
        print(f"✅ Activated PowerPoint: {ppt_window.title}")
        # After activating PowerPoint window
        time.sleep(0.5)
        keyboard.press_and_release('ctrl+v')
        print("📥 Ctrl+V sent using `keyboard` module.")
    else:
        print("⚠️ PowerPoint window not found.")

# === Example Usage ===
if __name__ == "__main__":
    copy_browser_window_to_clipboard(
        "PH2 web app",
        crop_top_px=240,
        crop_bottom_px=1350,
        crop_left_px=80,
        crop_right_px=80,
        resize_ratio=0.5  # Reduce size by 50%
    )

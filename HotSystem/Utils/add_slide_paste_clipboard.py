import win32com.client
import win32clipboard
import win32con
import pythoncom
import time

def ensure_clipboard_image():
    win32clipboard.OpenClipboard()
    has_image = win32clipboard.IsClipboardFormatAvailable(win32con.CF_DIB)
    win32clipboard.CloseClipboard()
    if not has_image:
        raise RuntimeError("Clipboard does not contain an image. Copy an image first!")

def add_slide_and_paste_image():
    # Initialize COM
    pythoncom.CoInitialize()

    # Connect to PowerPoint
    ppt = win32com.client.Dispatch("PowerPoint.Application")
    if ppt.Presentations.Count == 0:
        raise RuntimeError("No PowerPoint presentations are open!")

    # Use the active presentation
    pres = ppt.ActivePresentation

    # Add new blank slide at end
    slide_count = pres.Slides.Count
    new_slide = pres.Slides.Add(slide_count + 1, 12)  # 12 = ppLayoutBlank

    # Select the new slide
    ppt.ActiveWindow.View.GotoSlide(new_slide.SlideIndex)

    # Ensure clipboard has an image
    ensure_clipboard_image()

    # Paste the image
    new_slide.Shapes.Paste()

    print(f"✅ Added new slide #{new_slide.SlideIndex} and pasted clipboard image.")

if __name__ == "__main__":
    try:
        add_slide_and_paste_image()
    except Exception as e:
        print(f"❌ {e}")

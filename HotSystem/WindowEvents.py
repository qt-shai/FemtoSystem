from ECM import *

class KeyboardEvent:
    def __init__(cls, key, scancode, action, mods):
        if False:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        cls.key = key
        cls.scancode = scancode
        cls.action = action
        cls.mods = mods
        cls._event_type = cls.__class__.__name__
class MouseEvent:
    def __init__(cls, *args, **kwargs):
        if False:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        # print(args) # args can be parsed to determind which button pressed
        cls.args = args
        cls.kwargs = kwargs
        cls._event_type = cls.__class__.__name__
class WindowResizeEvent:
    def __init__(cls, width, height):
        if False:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        cls.width = width
        cls.height = height
        cls._event_type = cls.__class__.__name__
class CharEvent:
    def __init__(cls, char):
        if False:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        cls.char = char
        cls._event_type = cls.__class__.__name__
class ScrollEvent:
    def __init__(cls, x_offset, y_offset):
        if False:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        cls.x_offset = x_offset
        cls.y_offset = y_offset
        cls._event_type = cls.__class__.__name__
class WindowCloseEvent:
    def __init__(cls):
        if True:
            print("event from "+cls.__class__.__name__ +"::"+ inspect.currentframe().f_code.co_name )
        cls._event_type = cls.__class__.__name__

# fire events
def keyboard_callback(window, key, scancode, action, mods):
    data = glfw.get_window_user_pointer(window)
    event = KeyboardEvent(key, scancode, action, mods)
    if data.event_callback:
        data.event_callback(event) 
def mouse_callback(window, *args, **kwargs):
    data = glfw.get_window_user_pointer(window)
    event = MouseEvent(args, kwargs)
    if data.event_callback:
        data.event_callback(event)
def window_size_callback(window, width, height):
    data = glfw.get_window_user_pointer(window)
    event = WindowResizeEvent(width, height)
    if data.event_callback:
        data.event_callback(event) 
def char_callback(window, char):
    data = glfw.get_window_user_pointer(window)
    event = CharEvent(char)
    if data.event_callback:
        data.event_callback(event) 
def scroll_callback(window, x_offset, y_offset):
    data = glfw.get_window_user_pointer(window)
    event = ScrollEvent(x_offset, y_offset)
    if data.event_callback:
        data.event_callback(event)
def window_close_callback(window):
    data = glfw.get_window_user_pointer(window)
    event = WindowCloseEvent()
    if data.event_callback:
        data.event_callback(event) 

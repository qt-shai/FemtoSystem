from ECM import *
from WindowEvents import *

class WindowProps:
    def __init__(self, Title = "HotSystem", Width = 1600, Height = 800, Major = 4, Minor = 5):
            self.Title = Title
            self.Width = Width
            self.Height = Height
            self.Major = Major
            self.Minor = Minor

class WindowData:
        def __init__(cls, callback = None, Title = "", Width = 0, Height = 0, last_Width = 0, last_Height = 0, win_pos = [0,0]):
            cls.Title = Title
            cls.Width = Width
            cls.Height = Height
            cls.last_Width = last_Width
            cls.last_Height = last_Height
            cls.win_pos = win_pos # vector with two parameters (x,y)
            cls.is_FullScreen = False
            cls.VSync = False
            cls.event_callback = callback

class Window_singleton:
    # create singleton
    _instance = None
    _lock = threading.Lock()
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(Window_singleton, cls).__new__(cls)
        return cls._instance
    def __init__(cls):
        cls.init()
    # Windows control
    winProps = WindowProps()
    winData = WindowData()
    s_GLFWInitialized = False
    def error_callback(error, description):
        print(f"Error {error}: {description}")
    def init(cls):
        cls.winData.Title = cls.winProps.Title
        cls.winData.Width = cls.winProps.Width
        cls.winData.Height = cls.winProps.Height
        if not (cls.s_GLFWInitialized):
            success = glfw.init()
            if not(success):
                print("Failed to initialize GLFW")
                exit()

            glfw.set_error_callback(cls.error_callback)
            cls.s_GLFWInitialized = True

        # Dynamically adjust new window size (by detecting monitor resolution)
        primary = glfw.get_primary_monitor()
        if (primary and cls.winData.is_FullScreen):
            mode = glfw.get_video_mode(primary)
            cls.winData.Width = mode.width
            cls.winData.Height = mode.GL_MAX_HEIGHT

        glfw.window_hint(glfw.DECORATED, glfw.TRUE)

        cls.m_Window_GL = glfw.create_window(cls.winData.Width, cls.winData.Height, cls.winData.Title, (primary if cls.winData.is_FullScreen else None), None)
        if (cls.m_Window_GL == None):
            glfw.terminate()
            print("Failed to create GLFW window!")
        glfw.make_context_current(cls.m_Window_GL)
        # glfw.set_window_user_pointer(cls.m_Window_GL, cls.winData)
        cls.SetVSync() #// at init it will flip state from flase to true

        # set pointer to winData object
        glfw.set_window_user_pointer(cls.m_Window_GL, cls.winData) 
        # set GLFW callbacks
        glfw.set_key_callback(cls.m_Window_GL, keyboard_callback)
        glfw.set_cursor_pos_callback(cls.m_Window_GL, mouse_callback)
        glfw.set_window_size_callback(cls.m_Window_GL, window_size_callback)
        glfw.set_char_callback(cls.m_Window_GL, char_callback)
        glfw.set_scroll_callback(cls.m_Window_GL, scroll_callback)
        glfw.set_window_close_callback(cls.m_Window_GL, window_close_callback)
        glfw.set_mouse_button_callback(cls.m_Window_GL, mouse_callback)
    
    def SetVSync(cls):
        if not (cls.winData.VSync):
            glfw.swap_interval(1)
            cls.winData.VSync = True
        else:
            glfw.swap_interval(0)
            cls.winData.VSync = False
    def Shutdown(cls): 
        glfw.DestroyWindow(cls.m_Window_GL)
    def OnUpdate(cls):
        glfw.poll_events()
        glfw.swap_buffers(cls.m_Window_GL)
    def FullScreen(cls):
        # Get the monitor of the current window
        current_monitor = glfw.get_window_monitor(cls.m_Window_GL)

        # Alternatively, you can get the primary monitor
        primary_monitor = glfw.get_primary_monitor()
        
        if (current_monitor and not cls.winData.is_FullScreen):
            cls.winData.win_pos = glfw.get_window_pos(cls.m_Window_GL)
            cls.winData.last_Width, cls.winData.last_Height = glfw.get_window_size(cls.m_Window_GL)
            cls.winData.is_FullScreen = True
            mode = glfw.get_video_mode(current_monitor)
            glfw.set_window_monitor(cls.m_Window_GL, current_monitor, 0, 0, mode.width, mode.height, 0)
        elif (current_monitor):
            cls.winData.is_FullScreen = False
            glfw.set_window_monitor(cls.m_Window_GL, None, cls.winData.win_pos[0], cls.winData.win_pos[1], cls.winData.last_Width, cls.winData.last_Height, 0)
    def IsVSync(cls):
        return cls.winData.VSync
    # def SetEventCallback
             
        
        


'''
Entry point to our SW
'''

import os

from imgui import create_context

# from Application import Application_singletone,PyGuiOverlay,ImGuiOverlay
from Application import Application_singletone,PyGuiOverlay


# todo:
# handle error for each device and for entire SW
# add search for devices fo Rohde Schwarz

def main():
    # gui = ImGuiOverlay() #pyimgui
    guiDPG = PyGuiOverlay() # dear imgui
    app = Application_singletone()
    # app.PushOverLay(gui)
    app.PushOverLay(layer=guiDPG)
    app.Run()


if __name__ == "__main__":
    print(f"running from {os.getcwd()}")
    main()

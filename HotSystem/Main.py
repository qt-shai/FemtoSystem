'''
Entry point to our SW
'''
import os

from Application import Application_singletone,PyGuiOverlay,ImGuiOverlay
# todo:
# handle error for each device and for entire SW
# add search for devices fo Rohde Schwarz


def main(simulation:bool = False):
    gui = ImGuiOverlay(simulation) #pyimgui
    guiDPG = PyGuiOverlay(simulation) # dear imgui
    app = Application_singletone()
    app.PushOverLay(gui)
    app.PushOverLay(layer=guiDPG,simulation=simulation)
    app.Run()


if __name__ == "__main__":
    print(f"running from {os.getcwd()}")
    simulation: bool = True
    main(simulation)

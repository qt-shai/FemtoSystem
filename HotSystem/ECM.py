'''
This file import all packages, modules, external code, etc which need to be called.
rest of modules call only to this module, External Code Modules (ECM.py)
'''
# SW versiob 0
# for due to time limitation the simple and naive method is used alons the entire version 0 of the code
# in the futre the entire code need to be review and as needed make it more common from SW Engineering point of view

# event
from EventDispatcher import *

# gen
import os
import threading
import inspect
from enum import Enum
import tkinter as tk
from tkinter import filedialog

# unique ID
import uuid

# imgui and OpenGL
import glfw
from OpenGL.GL import *
from OpenGL.GLUT import *
import imgui
from ctypes import c_float
from imgui.integrations.glfw import GlfwRenderer
import dearpygui._dearpygui as _dpg
import dearpygui.experimental as exp_dpg
import dearpygui.dearpygui as dpg #imgui + implot
import dearpygui.demo as DPGdemo
from Utils.Common import *

#XML
import xml.etree.ElementTree as ET

# logger
import logging # todo: add log to SW

# Savedata
import csv

# time
import time
from datetime import datetime

#  TimeTagger
import TimeTagger
import numpy as np

# Rohde Schwarz
try:
    import pyvisa 
except ImportError:
    import visa

# smaract
#import smaract.si as si
import smaract.ctl as ctl
#import smaract.hsdr as hsdr

#qua
from qm import QuantumMachinesManager
from qm.qua import *
import matplotlib

# matplotlib.use('TkAgg')
from qm import SimulationConfig
import matplotlib.pyplot as plt

# Zelux
from thorlabs_tsi_sdk.tl_camera import TLCameraSDK, OPERATION_MODE

# import pyperclip # SHAI 8-9-24 pip install pyperclip
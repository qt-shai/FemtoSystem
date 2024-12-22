# ***************************************************************
#              --------- note ---------                         *
# this file was a workaround to make fast integration to OPX    *
# actually we need to split to OPX wrapper and OPX GUI          *
# ***************************************************************
import csv
import pdb
import traceback
from datetime import datetime
import os
import sys
import threading
import time
from enum import Enum
from tkinter import filedialog
from typing import Union, Optional, Callable
import glfw
import numpy as np
import tkinter as tk

from gevent.libev.corecext import callback
from matplotlib import pyplot as plt
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, assign, elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger
from qualang_tools.results import progress_counter, fetching_tool
from functools import partial
from qualang_tools.units import unit
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from smaract import ctl
import matplotlib

from HW_GUI.GUI_map import Map
from HW_wrapper import HW_devices as hw_devices, smaractMCS2
from SystemConfig import SystemType, Instruments
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized
import dearpygui.dearpygui as dpg
from PIL import Image
import subprocess
import shutil
import xml.etree.ElementTree as ET
import math
import SystemConfig as configs
from Utils import OptimizerMethod,find_max_signal
matplotlib.use('qtagg')

def create_logger(log_file_path: str):
    log_file = open(log_file_path, 'w')
    return subprocess.Popen(['npx', 'pino-pretty'], stdin=subprocess.PIPE, stdout=log_file)

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

class queried_plane(Enum):
    XY = 0
    YZ = 1
    XZ = 2

class Axis(Enum):
    Z = 0
    Y = 1
    X = 2

class GUI_OPX():
    # init parameters
    def __init__(self, simulation: bool = False):
        # HW
        self.tracking_function: Callable = None
        self.limit = None
        self.verbose:bool = False
        self.window_tag = "OPX Window"
        self.plt_max1 = None
        self.plt_max = None
        self.max1 = None
        self.max = None
        self.plt_y = None
        self.plt_x = None
        self.HW = hw_devices.HW_devices(simulation)
        self.system_name = self.HW.config.system_type.value
        self.mwModule = self.HW.microwave
        self.positioner = self.HW.positioner
        self.pico = self.HW.picomotor
        self.laser = self.HW.cobolt
        if (self.HW.config.system_type == configs.SystemType.FEMTO):
            self.ScanTrigger = 101  # IO2
            self.TrackingTrigger = 101  # IO1
        if (self.HW.config.system_type == configs.SystemType.HOT_SYSTEM):
            self.ScanTrigger = 1
            self.TrackingTrigger = 1
        if (self.HW.config.system_type == configs.SystemType.ATTO):
            self.ScanTrigger = 1001  # IO2
            self.TrackingTrigger = 1001  # IO1
            if self.HW.atto_scanner:
                self.tracking_function = self.FindMaxSignal_atto_positioner_and_scanner
            else:
                self.tracking_function = self.FindMaxSignal_atto_positioner


        # At the end of the init - all values are overwritten from XML!
        # To update values of the parameters - update the XML or the corresponding place in the GUI
        self.map: Optional[Map] = None
        self.simulation = simulation
        self.click_coord = None
        self.clicked_position = None
        self.map_item_x = 0
        self.map_item_y = 0
        self.map_keyboard_enable = False
        self.move_mode = "marker"
        self.text_color = (0, 0, 0, 255)  # Set color to black
        self.active_marker_index = -1
        self.active_area_marker_index = -1

        self.area_markers = []
        self.Map_aspect_ratio = None
        self.markers = []
        self.z_correction_threshold = 10000
        self.expected_pos = None
        self.smaract_ttl_duration = 0.001  # ms, updated from XML (loaded using 'self.update_from_xml()')
        self.lock = threading.Lock()

        # Coordinates + scan XYZ parameters
        self.scan_Out = []
        self.scan_data = np.zeros(shape=[80, 80, 60])
        self.queried_area = None
        self.queried_plane = None  # 0 - XY, 1 - YZ, 2 -XZ
        self.bScanChkbox = False
        self.L_scan = [5000, 5000, 5000]  # [nm]
        self.dL_scan = [100, 100, 100]  # [nm]
        self.b_Scan = [True, True, False]
        self.b_Zcorrection = False
        self.use_picomotor = False
        self.ZCalibrationData: np.ndarray | None = None
        self.Zcorrection_threshold = 10  # [nm]
        self.iniShift_scan = [0, 0, 0]  # [nm]
        self.idx_scan = [0, 0, 0]  # Z Y X
        self.startLoc = [0, 0, 0]
        self.endLoc = [0, 0, 0]
        self.dir = 1
        self.estimatedScanTime = 0.0  # [minutes]
        self.singleStepTime_scan = 0.033  # [sec]
        self.stopScan = True
        self.scanFN = ""

        self.bEnableShuffle = True
        self.bEnableSimulate = False
        # tracking ref
        self.bEnableSignalIntensityCorrection = True
        self.trackingPeriodTime = 10000000  # [nsec]
        self.refSignal = 0.0
        self.TrackIsRunning = True
        self.tTrackingSignaIntegrationTime = 50  # [msec]
        self.tGetTrackingSignalEveryTime = float(3)  # [sec]
        self.TrackingThreshold = 0.95  # track signal threshold
        self.N_tracking_search = 5  # max number of point to scan on each axis

        # Qua config object
        self.quaCFG = configs.QuaConfigSelector.get_qua_config(self.HW.config.system_type)
        self.u = unit()

        # common parameters
        self.exp = Experiment.COUNTER

        self.mw_Pwr = -20.0  # [dBm]
        self.mw_freq = 2.177  # [GHz], base frequency. Both start freq for scan and base frequency
        self.mw_freq_scan_range = 10.0  # [MHz]
        self.mw_df = float(0.1)  # [MHz]
        self.mw_freq_resonance = 2.18018  # [GHz]
        self.mw_2ndfreq_resonance = 2.18318 # [GHz]
        self.mw_P_amp = 1.0    # proportional amplitude
        self.mw_P_amp2 = 1.0   # proportional amplitude

        self.n_avg = int(1000000)  # number of averages
        self.n_nuc_pump = 4  # number of times to try nuclear pumping
        self.n_CPMG = 1  # CPMG repeatetions
        self.N_p_amp = 20

        self.scan_t_start = 20  # [nsec], must above 16ns (4 cycle)
        self.scan_t_end = 2000  # [nsec]
        self.scan_t_dt = 40  # [nsec], must above 4ns (1 cycle)

        self.MeasProcessTime = 300  # [nsec], time required for measure element to finish process
        self.Tpump = 500  # [nsec]
        self.Tcounter = 10000  # [nsec], for scan it is the single integration time
        self.TcounterPulsed = 500  # [nsec]
        self.total_integration_time = 5.0  # [msec]
        self.Tsettle = 2000 # [nsec]
        self.t_mw = 289  # [nsec] # from rabi experiment
        self.t_mw2 = 164  # [nsec] # from rabi experiment
        self.Tedge = 100 # [nsec]
        self.Twait = 2.0 # [usec]

        self.OPX_rf_amp = 0.5  # [V], OPX max amplitude
        self.rf_Pwr = 0.1  # [V], requied OPX amplitude
        self.rf_proportional_pwr = self.rf_Pwr / self.OPX_rf_amp  # [1], multiply by wafeform to actually change amplitude
        self.rf_resonance_freq = 2.963  # [MHz]
        self.rf_freq = 3.03  # [MHz]
        self.rf_freq_scan_range_gui = 100000.0  # [kHz]
        self.rf_freq_scan_range = 100.0  # [MHz]
        self.rf_df = float(0.1)  # [MHz]
        self.rf_df_gui = float(100)  # [kHz]
        self.rf_pulse_time = 100000  # [nsec]

        self.waitForMW = 0.05  # [sec], time to wait till mw settled (slow ODMR)

        # Graph parameters
        self.NumOfPoints = 800  # to include in counter Graph
        self.reset_data_val()

        self.Xv = []
        self.Yv = []
        self.Zv = []

        self.StopFetch = True

        self.expNotes = "_"

        # load class parameters from XML
        self.update_from_xml()
        self.bScanChkbox = False

        self.chkbox_close_all_qm = False
        # self.bEnableSignalIntensityCorrection = False # tdo: remove after fixing intensity method

        # self.ZCalibrationData = np.array([[1274289050, 1099174441, -5215799855],[1274289385, -1900825080, -5239700330],[-1852010640, -1900825498, -5277599782]])

        if simulation:
            print("OPX in simulation mode ***********************")
        else:
            try:
                # self.qmm = QuantumMachinesManager(self.HW.config.opx_ip, self.HW.config.opx_port)
                self.qmm = QuantumMachinesManager(host=self.HW.config.opx_ip, cluster_name=self.HW.config.opx_cluster, timeout=60)  # in seconds
                time.sleep(1)

            except Exception as e:
                print(f"Could not connect to OPX. Error: {e}.")

    def Calc_estimatedScanTime(self):
        N = np.ones(len(self.L_scan))
        for i in range(len(self.L_scan)):
            if self.b_Scan[i] == True:
                if self.dL_scan[i] > 0:
                    N[i] = self.L_scan[i] / self.dL_scan[i]
        self.estimatedScanTime = round(np.prod(N) * (self.singleStepTime_scan + self.total_integration_time / 1e3) / 60, 1)

    # Callbacks
    def time_in_multiples_cycle_time(self, val, cycleTime: int = 4, min: int = 16, max: int = 50000000):
        val = (val // cycleTime) * cycleTime
        if val < min:
            val = min
        if val > max:
            val = max
        return int(val)

    def UpdateCounterIntegrationTime(sender, app_data, user_data):
        sender.total_integration_time = user_data
        time.sleep(0.001)
        dpg.set_value(item="inDbl_total_integration_time", value=sender.total_integration_time)
        print("Set total_integration_time to: " + str(sender.total_integration_time) + "usec")

    def UpdateWaitTime(sender, app_data, user_data):
        sender.Twait = user_data
        time.sleep(0.001)
        dpg.set_value(item="inDbl_wait_time", value=sender.Twait)
        print("Set Twait to: " + str(sender.Twait) + "usec")

    def UpdateEdgeTime(sender, app_data, user_data):
        sender.Tedge = int(user_data)
        time.sleep(0.001)
        dpg.set_value(item="inInt_edge_time", value=sender.Tedge)
        print("Set Tedge to: " + str(sender.Tedge) + "nsec")

    def UpdateTcounter(sender, app_data, user_data):
        sender.Tcounter = sender.time_in_multiples_cycle_time(int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Tcounter", value=sender.Tcounter)
        print("Set Tcounter to: " + str(sender.Tcounter) + "nsec")

    def UpdateTpump(sender, app_data, user_data):
        sender.Tpump = sender.time_in_multiples_cycle_time(int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Tpump", value=sender.Tpump)
        print("Set Tpump to: " + str(sender.Tpump) + "nsec")

    def UpdateTcounterPulsed(sender, app_data, user_data):
        sender.TcounterPulsed = sender.time_in_multiples_cycle_time(int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_TcounterPulsed", value=sender.TcounterPulsed)
        print("Set TcounterPulsed to: " + str(sender.TcounterPulsed) + "nsec")

    def UpdateNumOfPoint(sender, app_data, user_data):
        sender.NumOfPoints = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="slideNumPts", value=sender.NumOfPoints)
        print("Set NumOfPoints to: " + str(sender.NumOfPoints))

    def Update_mwResonanceFreq(sender, app_data, user_data):
        sender.mw_freq_resonance = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwResonanceFreq", value=sender.mw_freq_resonance)
        print("Set mw_freq_resonance to: " + str(sender.mw_freq_resonance))

    def Update_mwP_amp(sender, app_data, user_data):
        sender.mw_P_amp = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwP_amp", value=sender.mw_P_amp)
        print("Set mw_Pamp to: " + str(sender.mw_P_amp))

    def Update_mwP_amp2(sender, app_data, user_data):
        sender.mw_P_amp2 = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwP_amp2", value=sender.mw_P_amp2)
        print("Set mw_Pamp2 to: " + str(sender.mw_P_amp2))

    def Update_mw_2ndfreq_resonance(sender, app_data, user_data):
        sender.mw_2ndfreq_resonance = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mw_2ndfreq_resonance", value=sender.mw_2ndfreq_resonance)
        print("Set mw_2ndfreq_resonance to: " + str(sender.mw_2ndfreq_resonance))

    def Update_mwFreq(sender, app_data, user_data):
        sender.mw_freq = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwFreq", value=sender.mw_freq)
        print("Set mw_freq to: " + str(sender.mw_freq))

    def Update_df(sender, app_data, user_data):
        sender.mw_df = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mw_df", value=sender.mw_df)
        print("Set MW df to: " + str(sender.mw_df))

    def UpdateScanRange(sender, app_data, user_data):
        sender.mw_freq_scan_range = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwScanRange", value=sender.mw_freq_scan_range)
        print("Set freq_scan_range to: " + str(sender.mw_freq_scan_range))

    def UpdateMWpwr(sender, app_data, user_data):
        sender.mw_Pwr = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mw_pwr", value=sender.mw_Pwr)
        print("Set mwPwr to: " + str(sender.mw_Pwr))

    def UpdateN_nuc_pump(sender, app_data, user_data):
        sender.n_nuc_pump = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_N_nuc_pump", value=sender.n_nuc_pump)
        print("Set n_nuc_pump to: " + str(sender.n_nuc_pump))

    def UpdateN_p_amp(sender, app_data, user_data):
        sender.N_p_amp = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_N_p_amp", value=sender.N_p_amp)
        print("Set N_p_amp to: " + str(sender.N_p_amp))

    def UpdateN_CPMG(sender, app_data, user_data):
        sender.n_CPMG = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_N_CPMG", value=sender.n_CPMG)
        print("Set n_CPMG to: " + str(sender.n_CPMG))

    def UpdateNavg(sender, app_data, user_data):
        sender.n_avg = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_n_avg", value=sender.n_avg)
        print("Set n_avg to: " + str(sender.n_avg))

    def UpdateN_tracking_search(sender, app_data, user_data):
        sender.N_tracking_search = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_N_tracking_search", value=sender.N_tracking_search)
        print("Set N_tracking_search to: " + str(sender.N_tracking_search))

    def UpdateT_rf_pulse_time(sender, app_data, user_data):
        sender.rf_pulse_time = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_rf_pulse_time", value=sender.rf_pulse_time)
        print("Set rf_pulse_time to: " + str(sender.rf_pulse_time))

    def UpdateT_mw(sender, app_data, user_data):
        sender.t_mw = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_t_mw", value=sender.t_mw)
        print("Set t_mw to: " + str(sender.t_mw))

    def UpdateT_mw2(sender, app_data, user_data):
        sender.t_mw2 = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_t_mw2", value=sender.t_mw2)
        print("Set t_mw2 to: " + str(sender.t_mw2))

    def Update_rf_pulse_time(sender, app_data, user_data):
        sender.rf_pulse_time = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_rf_pulse_time", value=sender.rf_pulse_time)
        print("Set rf_pulse_time to: " + str(sender.rf_pulse_time))

    def Update_tGetTrackingSignalEveryTime(sender, app_data, user_data):
        sender.tGetTrackingSignalEveryTime = (user_data)
        time.sleep(0.001)
        dpg.set_value(item="inDbl_tGetTrackingSignalEveryTime", value=sender.tGetTrackingSignalEveryTime)
        print("Set tGetTrackingSignalEveryTime to: " + str(sender.tGetTrackingSignalEveryTime))

    def Update_tTrackingSignaIntegrationTime(sender, app_data, user_data):
        sender.tTrackingSignaIntegrationTime = (user_data)
        time.sleep(0.001)
        dpg.set_value(item="inDbl_tTrackingSignaIntegrationTime", value=sender.tTrackingSignaIntegrationTime)
        print("Set tTrackingSignaIntegrationTime to: " + str(sender.tTrackingSignaIntegrationTime))

    def Update_TrackingThreshold(sender, app_data, user_data):
        sender.TrackingThreshold = (user_data)
        time.sleep(0.001)
        dpg.set_value(item="inDbl_TrackingThreshold", value=sender.TrackingThreshold)
        print("Set TrackingThreshold to: " + str(sender.TrackingThreshold))

    def UpdateScanTstart(sender, app_data, user_data):
        sender.scan_t_start = (int(user_data))
        sender.scan_t_start = sender.scan_t_start if sender.scan_t_start >= 20 else 20
        sender.scan_t_start = int(sender.scan_t_start / 4) * 4
        time.sleep(0.001)
        dpg.set_value(item="inInt_scan_t_start", value=sender.scan_t_start)
        print("Set scan_t_start to: " + str(sender.scan_t_start))

    def UpdateTsettle(sender, app_data, user_data):
        sender.Tsettle = sender.time_in_multiples_cycle_time(int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Tsettle", value=sender.Tsettle)
        print("Set measure_time to: " + str(sender.Tsettle))

    def UpdateScanT_dt(sender, app_data, user_data):
        sender.scan_t_dt = (int(user_data))
        sender.scan_t_dt = int(sender.scan_t_dt if sender.scan_t_dt >= 4 else 4)
        time.sleep(0.001)
        dpg.set_value(item="inInt_scan_t_dt", value=sender.scan_t_dt)
        print("Set scan_t_dt to: " + str(sender.scan_t_dt))

    def UpdateScanTend(sender, app_data, user_data):
        sender.scan_t_end = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_scan_t_end", value=sender.scan_t_end)
        print("Set scan_t_end to: " + str(sender.scan_t_end))

    def Update_rf_resonance_Freq(sender, app_data, user_data):
        sender.rf_resonance_freq = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_rf_resonance_freq", value=sender.rf_resonance_freq)
        print("Set rf_resonance_freq to: " + str(sender.rf_resonance_freq))

    def Update_rf_Freq(sender, app_data, user_data):
        sender.rf_freq = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_rf_freq", value=sender.rf_freq)
        print("Set rf_freq to: " + str(sender.rf_freq))

    def Update_rf_ScanRange(sender, app_data, user_data):
        sender.rf_freq_scan_range_gui = (float(user_data))
        sender.rf_freq_scan_range = sender.rf_freq_scan_range_gui / 1e3
        time.sleep(0.001)
        dpg.set_value(item="inDbl_rf_ScanRange", value=sender.rf_freq_scan_range_gui)
        print("Set rf_freq_scan_range_gui to: " + str(sender.rf_freq_scan_range_gui))

    def Update_rf_df(sender, app_data, user_data):
        sender.rf_df_gui = (float(user_data))
        sender.rf_df = sender.rf_df_gui / 1e3  # to [MHz]
        time.sleep(0.001)
        dpg.set_value(item="inDbl_rf_df", value=sender.rf_df_gui)
        print("Set rf_df to: " + str(sender.rf_df_gui))

    def Update_rf_pwr(sender, app_data, user_data):
        sender.rf_Pwr = (float(user_data))
        sender.rf_proportional_pwr = sender.rf_Pwr / sender.OPX_rf_amp
        time.sleep(0.001)
        dpg.set_value(item="inDbl_rf_pwr", value=sender.rf_Pwr)
        print("Set rf_Pwr to: " + str(sender.rf_Pwr))

    def Update_Intensity_Tracking_state(sender, app_data, user_data):
        sender.bEnableSignalIntensityCorrection = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_intensity_correction", value=sender.bEnableSignalIntensityCorrection)
        print("Set chkbox_intensity_correction to: " + str(sender.bEnableSignalIntensityCorrection))

    def Update_QUA_Shuffle_state(sender, app_data, user_data):
        sender.bEnableShuffle = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_QUA_shuffle", value=sender.bEnableShuffle)
        print("Set bEnableShuffle to: " + str(sender.bEnableShuffle))

    def Update_QUA_Simulate_state(sender, add_data, user_data):
        sender.bEnableSimulate = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_QUA_simulate", value=sender.bEnableSimulate)
        print("Set bEnableSimulate to: " + str(sender.bEnableSimulate))

    # GUI controls
    def GetWindowSize(self):
        monitor = glfw.get_primary_monitor()  # Get the primary monitor
        mode = glfw.get_video_mode(monitor)  # Get the physical size of the monitor
        width, height = mode.size
        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()
        self.window_scale_factor = width / 3840

    def controls(self, _width=1600, _Height=1000):
        self.GetWindowSize()
        pos = [int(self.viewport_width * 0.0), int(self.viewport_height * 0.4)]
        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.425)]

        dpg.add_window(label=self.window_tag, tag=self.window_tag, no_title_bar=True, height=-1, width=-1,
                       pos=[int(pos[0]), int(pos[1])])
        dpg.add_group(tag="Graph_group", parent=self.window_tag, horizontal=True)
        dpg.add_plot(label="Graph", width=int(win_size[0]), height=int(win_size[1]), crosshairs=True, tag="graphXY",
                     parent="Graph_group")  # height=-1, width=-1,no_menus = False )
        dpg.add_plot_legend(parent="graphXY")  # optionally create legend
        dpg.add_plot_axis(dpg.mvXAxis, label="time", tag="x_axis", parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvYAxis, label="I [counts/sec]", tag="y_axis", invert=False,
                          parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_line_series(self.X_vec, self.Y_vec, label="counts", parent="y_axis", tag="series_counts")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref, label="counts_ref", parent="y_axis", tag="series_counts_ref")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref2, label="counts_ref2", parent="y_axis", tag="series_counts_ref2")
        dpg.add_line_series(self.X_vec_ref,self.Y_resCalculated, label="resCalculated", parent="y_axis", tag="series_res_calcualted")

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
        dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
        dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

        dpg.add_group(tag="Params_Controls", before="Graph_group", parent=self.window_tag, horizontal=False)
        self.GUI_ParametersControl(True)

    def GUI_ParametersControl(self, isStart):
        child_width = int(2900 * self.window_scale_factor)
        child_height = int(80 * self.window_scale_factor)
        item_width = int(270 * self.window_scale_factor)
        dpg.delete_item("Params_Controls")
        dpg.delete_item("Buttons_Controls")

        if isStart:
            dpg.add_group(tag="Params_Controls", before="Graph_group", parent=self.window_tag, horizontal=False)

            # Create a single collapsible header to contain all controls, collapsed by default
            with dpg.collapsing_header(label="Parameter Controls", tag="Parameter_Controls_Header", parent="Params_Controls", default_open=False):
                # Child window and group for integration controls
                with dpg.child_window(tag="child_Integration_Controls", horizontal_scrollbar=True, width=child_width, height=child_height):
                    with dpg.group(tag="Integration_Controls", horizontal=True):
                        dpg.add_text(default_value="Tcounter [nsec]", tag="text_integration_time")
                        dpg.add_input_int(label="", tag="inInt_Tcounter", width=item_width, callback=self.UpdateTcounter, default_value=self.Tcounter,
                                          min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="Tpump [nsec]", tag="text_Tpump")
                        dpg.add_input_int(label="", tag="inInt_Tpump", width=item_width, callback=self.UpdateTpump,
                                          default_value=self.Tpump, min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="TcounterPulsed [nsec]", tag="text_TcounterPulsed")
                        dpg.add_input_int(label="", tag="inInt_TcounterPulsed", width=item_width, callback=self.UpdateTcounterPulsed,
                                          default_value=self.TcounterPulsed, min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="Tsettle [nsec]", tag="text_measure_time")
                        dpg.add_input_int(label="", tag="inInt_Tsettle", width=item_width, callback=self.UpdateTsettle, default_value=self.Tsettle,
                                          min_value=1, max_value=60000000, step=1)
                        dpg.add_text(default_value="total integration time [msec]", tag="text_total_integration_time")
                        dpg.add_input_double(label="", tag="inDbl_total_integration_time", width=item_width, callback=self.UpdateCounterIntegrationTime, default_value=self.total_integration_time, min_value=1, max_value=1000, step=1)
                        dpg.add_text(default_value="Twait [usec]", tag="text_wait_time")
                        dpg.add_input_double(label="", tag="inDbl_wait_time", width=item_width, callback=self.UpdateWaitTime, default_value=self.Twait, min_value=0.001, max_value=10000000000, step=0.001,format="%.5f")
                        dpg.add_text(default_value="Tedge [nsec]", tag="text_edge_time")
                        dpg.add_input_int(label="", tag="inInt_edge_time", width=item_width, callback=self.UpdateEdgeTime, default_value=self.Tedge, min_value=1, max_value=1000, step=1)

                        dpg.add_text(default_value="Tprocess [nsec]", tag="text_process_time")
                        dpg.add_input_int(label="", tag="inInt_process_time", width=item_width, default_value=300, min_value=1, max_value=1000, step=1)

                dpg.add_child_window(label="", tag="child_Freq_Controls", parent="Parameter_Controls_Header", horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Freq_Controls", parent="child_Freq_Controls", horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="MW res [GHz]", parent="Freq_Controls", tag="text_mwResonanceFreq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwResonanceFreq", indent=-1, parent="Freq_Controls", format="%.9f", width=item_width, callback=self.Update_mwResonanceFreq, default_value=self.mw_freq_resonance, min_value=0.001, max_value=6, step=0.001)

                dpg.add_text(default_value="MW 2nd_res [GHz]", parent="Freq_Controls", tag="text_mw2ndResonanceFreq",
                             indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_2ndfreq_resonance", indent=-1, parent="Freq_Controls",
                                     format="%.9f",
                                     width=item_width, callback=self.Update_mw_2ndfreq_resonance,
                                     default_value=self.mw_2ndfreq_resonance,
                                     min_value=0.001, max_value=6, step=0.001)
                dpg.add_text(default_value="MW freq [GHz] (base)", parent="Freq_Controls", tag="text_mwFreq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwFreq", indent=-1, parent="Freq_Controls", format="%.9f", width=item_width,
                                     callback=self.Update_mwFreq, default_value=self.mw_freq, min_value=0.001, max_value=6, step=0.001)
                dpg.add_text(default_value="range [MHz]", parent="Freq_Controls", tag="text_mwScanRange", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwScanRange", indent=-1, parent="Freq_Controls", width=item_width,
                                     callback=self.UpdateScanRange, default_value=self.mw_freq_scan_range, min_value=1, max_value=400, step=1)
                dpg.add_text(default_value="df [MHz]", parent="Freq_Controls", tag="text_mw_df", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_df", indent=-1, parent="Freq_Controls", format="%.5f", width=item_width,
                                     callback=self.Update_df, default_value=self.mw_df, min_value=0.000001, max_value=500, step=0.1)
                dpg.add_text(default_value="Power [dBm]", parent="Freq_Controls", tag="text_mw_pwr", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_pwr", indent=-1, parent="Freq_Controls", width=item_width, callback=self.UpdateMWpwr,
                                     default_value=self.mw_Pwr, min_value=0.01, max_value=500, step=0.1)

                dpg.add_child_window(label="", tag="child_rf_Controls", parent="Parameter_Controls_Header", horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="rf_Controls", parent="child_rf_Controls", horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="RF resonance freq [MHz]", parent="rf_Controls", tag="text_rf_resonance_Freq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_resonance_freq", indent=-1, parent="rf_Controls", format="%.9f", width=item_width,
                                     callback=self.Update_rf_resonance_Freq, default_value=self.rf_resonance_freq, min_value=0.001, max_value=6,
                                     step=0.001)

                dpg.add_text(default_value="RF freq [MHz]", parent="rf_Controls", tag="text_rf_Freq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_freq", indent=-1, parent="rf_Controls", format="%.9f", width=item_width,
                                     callback=self.Update_rf_Freq, default_value=self.rf_freq, min_value=0.001, max_value=6, step=0.001)
                dpg.add_text(default_value="range [kHz]", parent="rf_Controls", tag="text_rfScanRange", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_ScanRange", indent=-1, parent="rf_Controls", width=item_width,
                                     callback=self.Update_rf_ScanRange, default_value=self.rf_freq_scan_range_gui, min_value=1, max_value=400, step=1)
                dpg.add_text(default_value="df [kHz]", parent="rf_Controls", tag="text_rf_df", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_df", indent=-1, parent="rf_Controls", format="%.5f", width=item_width,
                                     callback=self.Update_rf_df, default_value=self.rf_df_gui, min_value=0.00001, max_value=500, step=0.1)
                dpg.add_text(default_value="Power [V]", parent="rf_Controls", tag="text_rf_pwr", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_pwr", indent=-1, parent="rf_Controls", width=item_width, callback=self.Update_rf_pwr,
                                     default_value=self.rf_Pwr, min_value=0.01, max_value=500, step=0.1)

                dpg.add_child_window(label="", tag="child_Time_Scan_Controls", parent="Parameter_Controls_Header", horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Time_Scan_Controls", parent="child_Time_Scan_Controls", horizontal=True)  # , before="Graph_group")
                dpg.add_text(default_value="scan t start [ns]", parent="Time_Scan_Controls", tag="text_scan_time_start", indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_start", indent=-1, parent="Time_Scan_Controls", width=item_width,
                                  callback=self.UpdateScanTstart, default_value=self.scan_t_start, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="dt [ns]", parent="Time_Scan_Controls", tag="text_scan_time_dt", indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_dt", indent=-1, parent="Time_Scan_Controls", width=item_width,
                                  callback=self.UpdateScanT_dt, default_value=self.scan_t_dt, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="t end [ns]", parent="Time_Scan_Controls", tag="text_scan_time_end", indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_end", indent=-1, parent="Time_Scan_Controls", width=item_width,
                                  callback=self.UpdateScanTend, default_value=self.scan_t_end, min_value=0, max_value=50000, step=1)

                dpg.add_child_window(label="", tag="child_Time_delay_Controls", parent="Parameter_Controls_Header", horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Time_delay_Controls", parent="child_Time_delay_Controls", horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="t_mw [ns]", parent="Time_delay_Controls", tag="text_t_mw", indent=-1)
                dpg.add_input_int(label="", tag="inInt_t_mw", indent=-1, parent="Time_delay_Controls", width=item_width, callback=self.UpdateT_mw, default_value=self.t_mw, min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="t_mw2 [ns]", parent="Time_delay_Controls", tag="text_t_mw2", indent=-1)
                dpg.add_input_int(label="", tag="inInt_t_mw2", indent=-1, parent="Time_delay_Controls", width=item_width, callback=self.UpdateT_mw2, default_value=self.t_mw2, min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="rf_pulse_time [ns]", parent="Time_delay_Controls", tag="text_rf_pulse_time", indent=-1)
                dpg.add_input_int(label="", tag="inInt_rf_pulse_time", indent=-1, parent="Time_delay_Controls", width=item_width, callback=self.Update_rf_pulse_time, default_value=self.rf_pulse_time, min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="GetTrackingSignalEveryTime [ns]", parent="Time_delay_Controls", tag="text_GetTrackingSignalEveryTime", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_tGetTrackingSignalEveryTime", indent=-1, parent="Time_delay_Controls", format="%.3f",
                                     width=item_width, callback=self.Update_tGetTrackingSignalEveryTime,
                                     default_value=self.tGetTrackingSignalEveryTime, min_value=0.001, max_value=10, step=0.1)

                dpg.add_text(default_value="tTrackingSignaIntegrationTime [msec]", parent="Time_delay_Controls",
                             tag="text_tTrackingSignaIntegrationTime", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_tTrackingSignaIntegrationTime", indent=-1, parent="Time_delay_Controls", format="%.0f",
                                     width=item_width, callback=self.Update_tTrackingSignaIntegrationTime,
                                     default_value=self.tTrackingSignaIntegrationTime, min_value=1, max_value=500000, step=10.0)

                dpg.add_child_window(label="", tag="child_Repetitions_Controls", parent="Parameter_Controls_Header", horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Repetitions_Controls", parent="child_Repetitions_Controls", horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="N nuc pump", parent="Repetitions_Controls", tag="text_N_nuc_pump", indent=-1)
                dpg.add_input_int(label="", tag="inInt_N_nuc_pump", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_nuc_pump,
                                  default_value=self.n_nuc_pump,
                                  min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="N P amp", parent="Repetitions_Controls", tag="text_N_p_amp", indent=-1)
                dpg.add_input_int(label="", tag="inInt_N_p_amp", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_p_amp,
                                  default_value=self.N_p_amp,
                                  min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="N CPMG", parent="Repetitions_Controls", tag="text_N_CPMG", indent=-1)
                dpg.add_input_int(label="", tag="inInt_N_CPMG", indent=-1, parent="Repetitions_Controls", width=item_width,
                                  callback=self.UpdateN_CPMG, default_value=self.n_CPMG, min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="N avg", parent="Repetitions_Controls", tag="text_n_avg", indent=-1)
                dpg.add_input_int(label="", tag="inInt_n_avg", indent=-1, parent="Repetitions_Controls", width=item_width, callback=self.UpdateNavg,
                                  default_value=self.n_avg, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="TrackingThreshold", parent="Repetitions_Controls", tag="text_TrackingThreshold", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_TrackingThreshold", indent=-1, parent="Repetitions_Controls", format="%.2f",
                                     width=item_width, callback=self.Update_TrackingThreshold, default_value=self.TrackingThreshold, min_value=0,
                                     max_value=1, step=0.01)
                dpg.add_text(default_value="N search (Itracking)", parent="Repetitions_Controls", tag="text_N_tracking_search", indent=-1)
                dpg.add_input_int(label="", tag="inInt_N_tracking_search", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_tracking_search,
                                  default_value=self.N_tracking_search,
                                  min_value=0, max_value=50000, step=1)

                dpg.add_group(tag="MW_amplitudes", parent="Parameter_Controls_Header", horizontal=True)  #, before="Graph_group")
                dpg.add_text(default_value="MW P_amp", parent="MW_amplitudes", tag="text_mwP_amp", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwP_amp", indent=-1, parent="MW_amplitudes", format="%.6f", width=item_width, callback=self.Update_mwP_amp, default_value=self.mw_P_amp, min_value=0.0, max_value=1.0, step=0.001)
                dpg.add_text(default_value="MW P_amp2", parent="MW_amplitudes", tag="text_mwP_amp2", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwP_amp2", indent=-1, parent="MW_amplitudes", format="%.6f", width=item_width, callback=self.Update_mwP_amp2, default_value=self.mw_P_amp2, min_value=0.0, max_value=1.0, step=0.001)


                dpg.add_group(tag="chkbox_group", parent="Params_Controls", horizontal=True)
                dpg.add_checkbox(label="Intensity Correction", tag="chkbox_intensity_correction", parent="chkbox_group",
                                 callback=self.Update_Intensity_Tracking_state, indent=-1, default_value=self.bEnableSignalIntensityCorrection)
                dpg.add_checkbox(label="QUA shuffle", tag="chkbox_QUA_shuffle", parent="chkbox_group", callback=self.Update_QUA_Shuffle_state,
                                 indent=-1, default_value=self.bEnableShuffle)
                dpg.add_checkbox(label="QUA simulate", tag="chkbox_QUA_simulate", parent="chkbox_group", callback=self.Update_QUA_Simulate_state,
                                 indent=-1, default_value=self.bEnableSimulate)
                dpg.add_checkbox(label="Scan XYZ", tag="chkbox_scan", parent="chkbox_group", indent=-1, callback=self.Update_scan,
                                 default_value=self.bScanChkbox)
                dpg.add_checkbox(label="Close All QM", tag="chkbox_close_all_qm", parent="chkbox_group", indent=-1, callback=self.Update_close_all_qm,
                                 default_value=self.chkbox_close_all_qm)

                dpg.add_group(tag="Buttons_Controls", parent="Graph_group",
                              horizontal=False)  # parent="Params_Controls",horizontal=False)
                _width = 300 # was 220
                dpg.add_button(label="Counter", parent="Buttons_Controls", tag="btnOPX_StartCounter",
                               callback=self.btnStartCounterLive, indent=-1, width=_width)
                dpg.add_button(label="ODMR_CW", parent="Buttons_Controls", tag="btnOPX_StartODMR", callback=self.btnStartODMR_CW, indent=-1, width=_width)
                dpg.add_button(label="Start Pulsed ODMR", parent="Buttons_Controls", tag="btnOPX_StartPulsedODMR", callback=self.btnStartPulsedODMR, indent=-1, width=_width)

                dpg.add_button(label="ODMR_Bfield", parent="Buttons_Controls", tag="btnOPX_StartODMR_Bfield", callback=self.btnStartODMR_Bfield, indent=-1, width=_width)
                dpg.add_button(label="NuclearFastRot", parent="Buttons_Controls", tag="btnOPX_StartNuclearFastRot", callback=self.btnStartNuclearFastRot, indent=-1, width=_width)

                dpg.add_button(label="RABI", parent="Buttons_Controls", tag="btnOPX_StartRABI", callback=self.btnStartRABI, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear RABI", parent="Buttons_Controls", tag="btnOPX_StartNuclearRABI",
                               callback=self.btnStartNuclearRABI, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear MR", parent="Buttons_Controls", tag="btnOPX_StartNuclearMR", callback=self.btnStartNuclearMR,
                               indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear PolESR", parent="Buttons_Controls", tag="btnOPX_StartNuclearPolESR",
                               callback=self.btnStartNuclearPolESR, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear lifetime S0", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS0",
                               callback=self.btnStartNuclearSpinLifetimeS0, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear lifetime S1", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS1",
                               callback=self.btnStartNuclearSpinLifetimeS1, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear Ramsay", parent="Buttons_Controls", tag="btnOPX_StartNuclearRamsay",
                               callback=self.btnStartNuclearRamsay, indent=-1, width=_width)
                dpg.add_button(label="Start Hahn", parent="Buttons_Controls", tag="btnOPX_StartHahn", callback=self.btnStartHahn, indent=-1,
                               width=_width)
                dpg.add_button(label="Start Electron Lifetime", parent="Buttons_Controls", tag="btnOPX_StartElectronLifetime",
                               callback=self.btnStartElectronLifetime, indent=-1, width=_width)
                dpg.add_button(label="Start Electron Coherence", parent="Buttons_Controls", tag="btnOPX_StartElectronCoherence",
                               callback=self.btnStartElectron_Coherence, indent=-1, width=_width)

                dpg.add_button(label="Start population gate tomography", parent="Buttons_Controls", tag="btnOPX_PopulationGateTomography",
                               callback=self.btnStartPopulateGateTomography, indent=-1, width=_width)
                dpg.add_button(label="Start Entanglement state tomography", parent="Buttons_Controls", tag="btnOPX_EntanglementStateTomography",
                               callback=self.btnStartStateTomography, indent=-1, width=_width)
                dpg.add_button(label="Start G2", parent="Buttons_Controls", tag="btnOPX_G2",
                               callback=self.btnStartG2, indent=-1, width=_width)

                # save exp data
                dpg.add_group(tag="Save_Controls", parent="Parameter_Controls_Header", horizontal=True)
                dpg.add_input_text(label="", parent="Save_Controls", tag="inTxtOPX_expText", indent=-1, callback=self.saveExperimentsNotes)
                dpg.add_button(label="Save", parent="Save_Controls", tag="btnOPX_save", callback=self.btnSave,
                               indent=-1)  # remove save btn, it should save automatically

            # dpg.add_checkbox(label="Radio Button1", source="bool_value")
            dpg.bind_item_theme(item="Params_Controls", theme="NewTheme")
            dpg.bind_item_theme(item="btnOPX_StartCounter", theme="btnYellowTheme")
            dpg.bind_item_theme(item="btnOPX_StartODMR", theme="btnRedTheme")
            dpg.bind_item_theme(item="btnOPX_StartPulsedODMR", theme="btnRedTheme")
            dpg.bind_item_theme(item="btnOPX_StartRABI", theme="btnBlueTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearRABI", theme="btnBlueTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearMR", theme="btnGreenTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearPolESR", theme="btnGreenTheme")
        else:
            dpg.add_group(tag="Params_Controls", before="Graph_group", parent=self.window_tag, horizontal=True)
            dpg.add_button(label="Stop", parent="Params_Controls", tag="btnOPX_Stop", callback=self.btnStop, indent=-1)
            dpg.bind_item_theme(item="btnOPX_Stop", theme="btnRedTheme")
            dpg.add_button(label="Find Max Intensity", parent="Params_Controls", tag="btnOPX_StartFindMaxIntensity",
                           callback=self.MoveToPeakIntensity, indent=-1)

    def GUI_ScanControls(self):
        self.Calc_estimatedScanTime()
        self.maintain_aspect_ratio = True

        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.3)]
        win_pos = [int(self.viewport_width * 0.05) * 0, int(self.viewport_height * 0.5)]
        scan_time_in_seconds = self.estimatedScanTime * 60

        item_width = int(200 * self.window_scale_factor)
        if self.bScanChkbox:

            self.map = Map(ZCalibrationData=self.ZCalibrationData, use_picomotor=self.use_picomotor)
            self.use_picomotor = self.map.use_picomotor
            self.expNotes = self.map.exp_notes

            with dpg.window(label="Scan Window", tag="Scan_Window", no_title_bar=True, height=-1, width=1200, pos=win_pos):
                with dpg.group(horizontal=True):
                    # Left side: Scan settings and controls
                    with dpg.group(tag="Scan_Range", horizontal=False):
                        with dpg.group(tag="Scan_Parameters", horizontal=False):
                            with dpg.group(tag="X_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bX_Scan", indent=-1, callback=self.Update_bX_Scan,
                                                 default_value=self.b_Scan[0])
                                dpg.add_text(default_value="dx [nm]", tag="text_dx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dx_scan", indent=-1, width=item_width, callback=self.Update_dX_Scan,
                                                  default_value=self.dL_scan[0], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lx [nm]", tag="text_Lx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lx_scan", indent=-1, width=item_width, callback=self.Update_Lx_Scan,
                                                  default_value=self.L_scan[0], min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Y_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bY_Scan", indent=-1, callback=self.Update_bY_Scan,
                                                 default_value=self.b_Scan[1])
                                dpg.add_text(default_value="dy [nm]", tag="text_dy_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dy_scan", indent=-1, width=item_width, callback=self.Update_dY_Scan,
                                                  default_value=self.dL_scan[1], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Ly [nm]", tag="text_Ly_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Ly_scan", indent=-1, width=item_width, callback=self.Update_Ly_Scan,
                                                  default_value=self.L_scan[1], min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Z_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bZ_Scan", indent=-1, callback=self.Update_bZ_Scan,
                                                 default_value=self.b_Scan[2])
                                dpg.add_text(default_value="dz [nm]", tag="text_dz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dz_scan", indent=-1, width=item_width, callback=self.Update_dZ_Scan,
                                                  default_value=self.dL_scan[2], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lz [nm]", tag="text_Lz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lz_scan", indent=-1, width=item_width, callback=self.Update_Lz_Scan,
                                                  default_value=self.L_scan[2], min_value=0, max_value=500000, step=1)

                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label="Notes", tag="inTxtScan_expText", indent=-1, width=200, callback=self.saveExperimentsNotes, default_value=self.expNotes)

                                dpg.add_text(default_value=f"~scan time: {self.format_time(scan_time_in_seconds)}", tag="text_expectedScanTime",
                                             indent=-1)

                            with dpg.group(horizontal=True):
                                dpg.add_text(label="Message: ", tag="Scan_Message")
                                dpg.add_checkbox(label="", tag="chkbox_Zcorrection", indent=-1, callback=self.Update_bZcorrection,
                                                 default_value=self.b_Zcorrection)
                                dpg.add_text(default_value="Use Z Correction", tag="text_Zcorrection", indent=-1)

                            dpg.add_input_text(label="CMD", callback=self.execute_input_string, multiline=True, width=400, height=20)

                    with dpg.group(tag="start_Scan_btngroup", horizontal=False):
                        dpg.add_button(label="Start Scan", tag="btnOPX_StartScan", callback=self.btnStartScan, indent=-1, width=130)
                        dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")
                        dpg.add_button(label="Load Scan", tag="btnOPX_LoadScan", callback=self.btnLoadScan, indent=-1, width=130)
                        dpg.bind_item_theme(item="btnOPX_LoadScan", theme="btnGreenTheme")
                        dpg.add_button(label="Update images", tag="btnOPX_UpdateImages", callback=self.btnUpdateImages, indent=1, width=130)
                        dpg.bind_item_theme(item="btnOPX_UpdateImages", theme="btnGreenTheme")
                        dpg.add_button(label="Auto Focus", tag="btnOPX_AutoFocus", callback=self.btnAutoFocus, indent=-1, width=130)
                        dpg.bind_item_theme(item="btnOPX_AutoFocus", theme="btnYellowTheme")
                        dpg.add_button(label="Get Log from Pico", tag="btnOPX_GetLoggedPoint", callback=self.btnGetLoggedPoints, indent=-1, width=130)

                    with dpg.group(horizontal=False):
                        dpg.add_button(label="Updt from map", callback=self.update_from_map, width=130)
                        dpg.add_button(label="scan all markers", callback=self.scan_all_markers, width=130)
                        dpg.add_button(label="Z-calibrate", callback=self.btn_z_calibrate, width=130)
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="plot", callback=self.plot_graph)
                            dpg.add_checkbox(label="use Pico", indent=-1, tag="checkbox_use_picomotor", callback=self.toggle_use_picomotor,
                                             default_value=self.use_picomotor)

                    _width = 200
                    with dpg.group(horizontal=False):
                        dpg.add_input_float(label="Step (um)", default_value=0.2, width=_width, tag="step_um", format='%.4f')
                        dpg.add_input_float(label="Z Span (um)", default_value=6.0, width=_width, tag="z_span_um", format='%.1f')
                        dpg.add_input_float(label="Laser Power (mW)", default_value=40.0, width=_width, tag="laser_power_mw", format='%.1f')
                        dpg.add_input_float(label="Int time (ms)", default_value=200.0, width=_width, tag="int_time_ms", format='%.1f')
                        dpg.add_input_float(label="X-Y span (um)", default_value=10.0, width=_width, tag="xy_span_um", format='%.4f')
                        dpg.add_input_float(label="Offset (nm)", default_value=1500.0, width=_width, tag="offset_from_focus_nm", format='%.1f')

                    self.btnGetLoggedPoints()  # get logged points
                    # self.map = Map(ZCalibrationData = self.ZCalibrationData, use_picomotor = self.use_picomotor)
                    self.map.create_map_gui(win_size, win_pos)  # dpg.set_frame_callback(1, self.load_pos)
        else:
            self.map.delete_map_gui()
            del self.map
            dpg.delete_item("Scan_Window")

    def btn_z_calibrate(self):
        self.ScanTh = threading.Thread(target=self.z_calibrate)
        self.ScanTh.start()

    def z_calibrate(self):
        # pdb.set_trace()  # Insert a manual breakpoint
        xy_span_um = dpg.get_value("xy_span_um")
        if xy_span_um > 60:
            self.use_picomotor = True

        device = self.pico if self.use_picomotor else self.positioner

        self.auto_focus()

        for ch in range(2):
            position = self.get_device_position(device)
            # pdb.set_trace()  # Insert a manual breakpoint
            device.LoggedPoints.append(position.copy())
            device.MoveRelative(ch if not self.use_picomotor else ch + 1, int(xy_span_um * 1e-3 * device.StepsIn1mm))
            self.auto_focus()

        position = self.get_device_position(device)
        # pdb.set_trace()  # Insert a manual breakpoint
        device.LoggedPoints.append(position.copy())
        device.calc_uv()

    def get_device_position(self, device):
        device.GetPosition()
        position = [0] * 3
        for channel in range(3):
            position[channel] = int(device.AxesPositions[channel] / device.StepsIn1mm * 1e3 * 1e6) #[pm]
        return position


    # Define the callback function to run the input string
    def execute_input_string(self, app_data, user_data):
        try:
            print(f"Executing: {user_data}")
            # Run the input string as code
            exec(user_data)

        except Exception as e:
            print(f"Error executing input string: {e}")

    def toggle_use_picomotor(self, app_data, user_data):
        self.use_picomotor = user_data
        time.sleep(0.001)
        dpg.set_value(item="checkbox_use_picomotor", value=self.use_picomotor)
        self.map.toggle_use_picomotor(app_data = app_data, user_data = user_data)
        print("Set use_picomotor to: " + str(self.use_picomotor))

    def plot_graph(self):
        # Check if plt_x and plt_y are not None
        if self.plt_x is not None and self.plt_y is not None:
            plt.plot(self.plt_x, self.plt_y, label="Data")

            # Check if self.max and self.max1 are not None before plotting vertical lines
            if self.plt_max is not None:
                plt.axvline(x=self.plt_max, color='r', linestyle='--', label=f"Max: {self.plt_max}")
            # if self.plt_max1 is not None:
            #     plt.axvline(x=self.plt_max1, color='g', linestyle='--', label=f"Max1: {self.plt_max1}")

            # Add labels and legend
            plt.xlabel("Z-axis")
            plt.ylabel("Intensity")
            plt.title("Graph with Max and Max1 Lines")
            plt.legend()
            plt.grid(True)
            plt.show()

            # Save the plot as a PNG file
            file_path = "saved_plot.png"
            plt.savefig(file_path)
        else:
            print("Error: plt_x or plt_y is None. Unable to plot the graph.")

    def update_from_map(self, index=0):
        """Update scan parameters based on the selected area marker."""
        point = (0, 0, 0)
        if index < len(self.map.area_markers):
            # Get the selected rectangle from area_markers by index, including Z scan state
            selected_rectangle = self.map.area_markers[index]
            min_x, min_y, max_x, max_y, z_scan_state = selected_rectangle

            # Calculate the width and height of the rectangle
            Lx_scan = int(max_x - min_x) * 1e3  # Convert to micrometers
            Ly_scan = int(max_y - min_y) * 1e3  # Convert to micrometers
            X_pos = (max_x + min_x) / 2
            Y_pos = (max_y + min_y) / 2

            # Calculate the Z evaluation
            z_evaluation = float(calculate_z_series(self.map.ZCalibrationData, np.array([int(X_pos * 1e6)]), int(Y_pos * 1e6))) / 1e6

            # Call Update_Lx_Scan and Update_Ly_Scan with the calculated values
            self.Update_Lx_Scan(app_data=None, user_data=Lx_scan)
            self.Update_Ly_Scan(app_data=None, user_data=Ly_scan)

            # Update MCS fields with the new absolute positions
            point = (X_pos * 1e6, Y_pos * 1e6, z_evaluation * 1e6)
            # for ch, value in enumerate(point):
            #     dpg.set_value(f"mcs_ch{ch}_ABS", value / 1e6)

            # Toggle Z scan state based on z_scan_state
            self.Update_bZ_Scan(app_data=None, user_data=(z_scan_state == "Z scan enabled"))

            # Recalculate the estimated scan time based on the new scan parameters
            self.Calc_estimatedScanTime()

            # Update the GUI with the estimated scan time and relevant messages
            dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {self.format_time(self.estimatedScanTime * 60)}")
            dpg.set_value("Scan_Message", "Please press GO ABS in Smaract GUI")
        else:
            print("Invalid area marker index or no area markers available.")  # NE

        return point

    def scan_all_markers(self):
        """Automatically scan all area markers sequentially without user interaction, handling errors and skipping problematic markers."""
        if len(self.map.area_markers) == 0:
            print("No area markers available for scanning.")
            return

        print(f"Starting scan for {len(self.map.area_markers)} area markers.")

        # Iterate over all area markers
        for index in range(len(self.map.area_markers)):
            try:
                print(f"Activating area marker {index + 1}/{len(self.map.area_markers)}.")

                # Activate the area marker before scanning
                self.map.act_area_marker(index)

                print(f"Updating scan parameters for area marker {index + 1}.")
                # Update the scan parameters for the selected area marker
                point = self.update_from_map(index)

                # Move to the calculated scan start position for each axis
                for ch in range(3):
                    if self.map.use_picomotor:
                        self.pico.MoveABSOLUTE(ch + 1, int(point[ch]*self.pico.StepsIn1mm/1e6))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm, by picomotor.")
                    else:
                        self.positioner.MoveABSOLUTE(ch, int(point[ch]))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm. by smaract")

                # Ensure the stage has reached its position
                time.sleep(0.005)  # Allow motion to start
                for ch in range(3):
                    res = self.readInpos(ch)  # Wait for motion to complete
                    if res:
                        print(f"Axis {ch} in position at {self.positioner.AxesPositions[ch]}.")
                    else:
                        print(f"Failed to move axis {ch} to position.")

                # autofocus
                if self.map.use_picomotor:
                    self.auto_focus()

                # Start the scan automatically
                print(f"Starting scan for area marker {index + 1}.")
                self.StartScan3D()

            except Exception as e:
                print(f"An error occurred while scanning area marker {index + 1}: {e}")
                # Skip to the next area marker if an error occurs
                continue

        print("Completed scanning all area markers.")

    # not done need to be tested and verify bugs free
    def Save_2D_matrix2IMG(self, array_2d, fileName="fileName", img_format='png'):
        image = Image.fromarray(array_2d.astype(np.uint8))  # Convert the NumPy array to an image
        self.image_path = fileName + "." + img_format  # Save the image to a file
        image.save(self.image_path)

    def intensity_to_rgb_heatmap(self, intensity):
        # Define a colormap (you can choose any colormap from Matplotlib)
        # cmap = plt.get_cmap('hot')
        cmap = plt.get_cmap('jet')

        # Normalize the intensity to the range [0, 1] (if necessary)
        intensity = max(0, min(0.99999999, intensity))

        # Map the intensity value to a color in the colormap
        rgba_color = cmap(intensity)

        # Convert RGBA tuple to RGB tuple (discard alpha channel)
        rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))

        return rgb_color

    def queryXY_callback(self, app_data):
        # print("queryXY_callback")
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # Find the closest index in Yv for a[3]
            y_index = np.argmin(np.abs(self.Yv - a[3]))
            # Find the closest index in Xv for a[1]
            x_index = np.argmin(np.abs(self.Xv - a[1]))

            self.idx_scan[Axis.Y.value] = y_index
            self.idx_scan[Axis.X.value] = x_index

            self.queried_area = a
            self.queried_plane = queried_plane.XY
        else:
            self.queried_area = None
            self.queried_plane = None

    def queryYZ_callback(self, app_data):
        # print("queryYZ_callback")
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # Find the closest index in Zv for a[3]
            z_index = np.argmin(np.abs(self.Zv - a[3]))
            # Find the closest index in Yv for a[1]
            y_index = np.argmin(np.abs(self.Yv - a[1]))

            self.idx_scan[Axis.Z.value] = z_index
            self.idx_scan[Axis.Y.value] = y_index

            self.queried_area = a
            self.queried_plane = queried_plane.YZ
        else:
            self.queried_area = None
            self.queried_plane = None

    def queryXZ_callback(self, app_data):
        # print("queryXZ_callback")
        a = dpg.get_plot_query_area(app_data)
        if np.any(a):
            # Find the closest index in Zv for a[3]
            z_index = np.argmin(np.abs(self.Zv - a[3]))
            # Find the closest index in Xv for a[1]
            x_index = np.argmin(np.abs(self.Xv - a[1]))

            self.idx_scan[Axis.Z.value] = z_index
            self.idx_scan[Axis.X.value] = x_index

            self.queried_area = a
            self.queried_plane = queried_plane.XZ
        else:
            self.queried_area = None
            self.queried_plane = None

    def Plot_Loaded_Scan(self, use_fast_rgb: bool = False):
        try:
            start_Plot_time = time.time()

            plot_size = [int(self.viewport_width * 0.3), int(self.viewport_height * 0.4)]

            # Check if scan_data and idx_scan are available
            if self.scan_data is None or self.idx_scan is None:
                raise ValueError("Scan data or index scan is not available.")

            # Prepare scan data arrays
            arrYZ = np.flipud(self.scan_data[:, :, self.idx_scan[Axis.X.value]])
            arrXZ = np.flipud(self.scan_data[:, self.idx_scan[Axis.Y.value], :])
            arrXY = np.flipud(self.scan_data[self.idx_scan[Axis.Z.value], :, :])

            # Normalize the arrays
            result_arrayXY = (arrXY * 255 / arrXY.max())
            result_arrayXY_ = []
            result_arrayXZ = (arrXZ * 255 / arrXZ.max())
            result_arrayXZ_ = []
            result_arrayYZ = (arrYZ * 255 / arrYZ.max())
            result_arrayYZ_ = []

            # Convert intensity values to RGB
            if use_fast_rgb:
                result_arrayXY_ = self.fast_rgb_convert(result_arrayXY)
                result_arrayXZ_ = self.fast_rgb_convert(result_arrayXZ)
                result_arrayYZ_ = self.fast_rgb_convert(result_arrayYZ)
            else:
                for arr, result_array in zip([arrXY, arrXZ, arrYZ], [result_arrayXY_, result_arrayXZ_, result_arrayYZ_]):
                    for i in range(arr.shape[0]):
                        for j in range(arr.shape[1]):
                            res = self.intensity_to_rgb_heatmap(arr.astype(np.uint8)[i][j] / 255)
                            result_array.extend([res[0] / 255, res[1] / 255, res[2] / 255, res[3] / 255])

            # Delete previous items if they exist
            for item in ["scan_group", "texture_reg", "textureXY_tag", "textureXZ_tag", "textureYZ_tag"]:
                if dpg.does_item_exist(item):
                    dpg.delete_item(item)

            # Add textures
            dpg.add_texture_registry(show=False, tag="texture_reg")
            dpg.add_dynamic_texture(width=arrXY.shape[1], height=arrXY.shape[0], default_value=result_arrayXY_, tag="textureXY_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrXZ.shape[1], height=arrXZ.shape[0], default_value=result_arrayXZ_, tag="textureXZ_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrYZ.shape[1], height=arrYZ.shape[0], default_value=result_arrayYZ_, tag="textureYZ_tag",
                                    parent="texture_reg")

            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")

            # XY plot
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True,
                         query=True, callback=self.queryXY_callback)
            dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z=" + "{0:.2f}".format(self.Zv[self.idx_scan[Axis.Z.value]]), parent="plotImaga")
            dpg.add_plot_axis(dpg.mvYAxis, label="y axis", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series("textureXY_tag", bounds_min=[self.startLoc[0], self.startLoc[1]], bounds_max=[self.endLoc[0], self.endLoc[1]],
                                 label="Scan data", parent="plotImaga_Y")
            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(arrXY), max_scale=np.max(arrXY),
                                   colormap=dpg.mvPlotColormap_Jet)

            # Update width based on conditions
            item_width = dpg.get_item_width("plotImaga")
            item_height = dpg.get_item_height("plotImaga")
            if (item_width is None) or (item_height is None):
                raise Exception("Window does not exist")

            if len(arrYZ) == 1:
                dpg.set_item_width("Scan_Window", item_width + 50)
            else:
                dpg.set_item_width("Scan_Window", item_width * 3 + 50)
                # XZ plot
                dpg.add_plot(parent="scan_group", tag="plotImagb", width=plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True,
                             query=True, callback=self.queryXZ_callback)
                dpg.add_plot_axis(dpg.mvXAxis, label="x (um), y=" + "{0:.2f}".format(self.Yv[self.idx_scan[Axis.Y.value]]), parent="plotImagb")
                dpg.add_plot_axis(dpg.mvYAxis, label="z (um)", parent="plotImagb", tag="plotImagb_Y")
                dpg.add_image_series(f"textureXZ_tag", bounds_min=[self.startLoc[0], self.startLoc[2]], bounds_max=[self.endLoc[0], self.endLoc[2]],
                                     label="Scan data", parent="plotImagb_Y")

                # YZ plot
                dpg.add_plot(parent="scan_group", tag="plotImagc", width=plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True,
                             query=True, callback=self.queryYZ_callback)
                dpg.add_plot_axis(dpg.mvXAxis, label="y (um), x=" + "{0:.2f}".format(self.Xv[self.idx_scan[Axis.X.value]]), parent="plotImagc")
                dpg.add_plot_axis(dpg.mvYAxis, label="z (um)", parent="plotImagc", tag="plotImagc_Y")
                dpg.add_image_series(f"textureYZ_tag", bounds_min=[self.startLoc[1], self.startLoc[2]], bounds_max=[self.endLoc[1], self.endLoc[2]],
                                     label="Scan data", parent="plotImagc_Y")

            dpg.set_item_height("Scan_Window", item_height + 150)

            end_Plot_time = time.time()
            print(f"time to plot scan: {end_Plot_time - start_Plot_time}")

        except Exception as e:
            print(f"An error occurred while plotting the scan: {e}")

    def Plot_Scan(self, Nx=250, Ny=250, array_2d=None, startLoc=None, endLoc=None, switchAxes=False):
        """
        Plots a 2D scan using the provided array. If a division by zero occurs,
        the array will be set to zeros.
        """

        if array_2d is None:
            array_2d = np.zeros((Nx, Ny))  # Default to zeros if array is not provided

        if startLoc is None:
            startLoc = [0, 0]

        if endLoc is None:
            endLoc = [Nx, Ny]

        start_Plot_time = time.time()
        plot_size = [int(self.viewport_width * 0.4), int(self.viewport_height * 0.4)]

        try:
            # Attempt to normalize the array
            max_value = array_2d.max()
            if max_value == 0:
                raise ZeroDivisionError("Maximum value of the array is zero, cannot normalize.")

            # Normalize and multiply by 255
            result_array = (array_2d * 255) / max_value
        except ZeroDivisionError:
            print("Division by zero encountered. Setting entire array to zero.")
            result_array = np.zeros_like(array_2d)  # Set entire array to zeros
        except Exception as e:
            print(f"An unexpected error occurred during array normalization: {e}")
            result_array = np.zeros_like(array_2d)  # Fallback to zeros in case of any other error

        result_array_ = []
        for i in range(array_2d.shape[0]):
            for j in range(array_2d.shape[1]):
                if switchAxes:  # switchAxes = workaround. need to be fixed
                    try:
                        res = self.intensity_to_rgb_heatmap(result_array.astype(np.uint8)[i][j] / 255)
                        result_array_.append(res[0] / 255)
                        result_array_.append(res[1] / 255)
                        result_array_.append(res[2] / 255)
                        result_array_.append(res[3] / 255)
                    except Exception as e:
                        print(f"Error in intensity to RGB heatmap conversion: {e}")
                        result_array_.extend([0, 0, 0, 0])  # Append zeros if an error occurs
                else:
                    try:
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(result_array[i][j] / 255)
                        result_array_.append(255 / 255)
                    except Exception as e:
                        print(f"Error while appending normalized values: {e}")
                        result_array_.extend([0, 0, 0, 1])  # Append zeros if an error occurs

        # Plot XY graph (image)
        try:
            dpg.delete_item("scan_group")
            dpg.delete_item("texture_reg")
            dpg.delete_item("texture_tag")
        except Exception as e:
            print(f"Error deleting items: {e}")

        time.sleep(0)
        dpg.add_texture_registry(show=False, tag="texture_reg")

        try:
            if switchAxes:
                dpg.add_dynamic_texture(width=array_2d.shape[1], height=array_2d.shape[0], default_value=result_array_, tag="texture_tag",
                                        parent="texture_reg")
            else:
                dpg.add_dynamic_texture(width=array_2d.shape[0], height=array_2d.shape[1], default_value=result_array_, tag="texture_tag",
                                        parent="texture_reg")
        except Exception as e:
            print(f"Error adding dynamic texture: {e}")

        try:
            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True)
            dpg.add_plot_axis(dpg.mvXAxis, label="x axis [um]", parent="plotImaga")
            dpg.add_plot_axis(dpg.mvYAxis, label="y axis [um]", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series(f"texture_tag", bounds_min=[startLoc[0], startLoc[1]], bounds_max=[endLoc[0], endLoc[1]], label="Scan data",
                                 parent="plotImaga_Y")
            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(array_2d), max_scale=np.max(array_2d),
                                   colormap=dpg.mvPlotColormap_Jet)
        except Exception as e:
            print(f"Error during plotting: {e}")

        try:
            # Update window width and height
            item_width = dpg.get_item_width("plotImaga")
            item_height = dpg.get_item_height("plotImaga")
            dpg.set_item_width("Scan_Window", item_width + 150)
            dpg.set_item_height("Scan_Window", item_height + 200)
        except Exception as e:
            print(f"Error updating window size: {e}")

        end_Plot_time = time.time()
        print(f"time to plot scan: {end_Plot_time - start_Plot_time}")

        try:
            dpg.set_value("texture_tag", result_array_)
        except Exception as e:
            print(f"Error setting texture tag value: {e}")

    def UpdateGuiDuringScan(self, Array2D, use_fast_rgb: bool = False):
        val = Array2D.reshape(-1)
        idx = np.where(val != 0)[0]
        minI = val[idx].min()

        result_array_ = self.fast_rgb_convert(np.flipud(Array2D.T))

        dpg.set_value("texture_tag", result_array_)
        dpg.delete_item("colormapXY")
        dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=minI, max_scale=Array2D.max(),
                               colormap=dpg.mvPlotColormap_Jet)

    def UpdateGuiDuringScan_____(self, Array2D: np.ndarray):  # $$$
        # todo: remove loops keep only when an imgae is needed
        start_updatePlot_time = time.time()
        result_array_ = []

        Array2D = Array2D * 255 / Array2D.max()  # BBB
        Array2D = np.fliplr(Array2D)

        for i in range(Array2D.shape[0]):  # Y
            for j in range(Array2D.shape[1]):  # X
                res = self.intensity_to_rgb_heatmap(Array2D.astype(np.uint8)[j, i] / 255)
                result_array_.append(res[0] / 255)  # shai 30-7-24
                result_array_.append(res[1] / 255)
                result_array_.append(res[2] / 255)
                result_array_.append(res[3] / 255)

        # dpg.set_value("textureXY_tag", result_array_) # 444
        dpg.set_value("texture_tag", result_array_)  # 444

    def Update_scan(sender, app_data, user_data):
        sender.bScanChkbox = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_scan", value=sender.bScanChkbox)
        print("Set bScan to: " + str(sender.bScanChkbox))
        sender.GUI_ScanControls()

    def Update_close_all_qm(sender, app_data, user_data):
        sender.chkbox_close_all_qm = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_close_all_qm", value=sender.chkbox_close_all_qm)
        print("Set chkbox_close_all_qm to: " + str(sender.chkbox_close_all_qm))

    def Update_bX_Scan(sender, app_data, user_data):
        sender.b_Scan[0] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bX_Scan", value=sender.b_Scan[0])
        print("Set b_Scan[0] to: " + str(sender.b_Scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

        sender.to_xml()

    def Update_bY_Scan(sender, app_data, user_data):
        sender.b_Scan[1] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bY_Scan", value=sender.b_Scan[1])
        print("Set bY_Scan to: " + str(sender.b_Scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_bZ_Scan(sender, app_data, user_data):
        sender.b_Scan[2] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bZ_Scan", value=sender.b_Scan[2])
        print("Set bZ_Scan to: " + str(sender.b_Scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dX_Scan(sender, app_data, user_data):
        sender.dL_scan[0] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dx_scan", value=sender.dL_scan[0])
        print("Set dx_scan to: " + str(sender.dL_scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Lx_Scan(sender, app_data, user_data):
        sender.L_scan[0] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Lx_scan", value=sender.L_scan[0])
        print("Set Lx_scan to: " + str(sender.L_scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dY_Scan(sender, app_data, user_data):
        sender.dL_scan[1] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dy_scan", value=sender.dL_scan[1])
        print("Set dy_scan to: " + str(sender.dL_scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Ly_Scan(sender, app_data, user_data):
        sender.L_scan[1] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Ly_scan", value=sender.L_scan[1])
        print("Set Ly_scan to: " + str(sender.L_scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dZ_Scan(sender, app_data, user_data):
        sender.dL_scan[2] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dz_scan", value=sender.dL_scan[2])
        print("Set dz_scan to: " + str(sender.dL_scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Lz_Scan(sender, app_data, user_data):
        sender.L_scan[2] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Lz_scan", value=sender.L_scan[2])
        print("Set Lz_scan to: " + str(sender.L_scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime", value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_bZcorrection(sender, app_data, user_data):
        sender.b_Zcorrection = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_Zcorrection", value=sender.b_Zcorrection)
        print("Set b_Zcorrection to: " + str(sender.b_Zcorrection))
        print(sender.ZCalibrationData)

    # gets values from gui using items tag
    def GetItemsVal(self,items_tag=[]):
        items_val = {}
        # Using a for loop to get each value and assign it to the auto_focus dictionary
        for tag in items_tag:
            items_val[tag] = dpg.get_value(tag)
            print(f"{tag}: {items_val[tag]}")

        return items_val

    # QUA
    # common
    def reset_data_val(self):
        self.X_vec = []
        self.X_vec_ref = []
        self.Y_vec = []
        self.Y_vec_ref = []
        self.Y_vec_ref2 = []
        self.Y_resCalculated = []
        self.iteration = 0
        self.counter = -10

    def initQUA_gen(self, n_count=1, num_measurement_per_array=1):
        self.reset_data_val()
        if self.exp == Experiment.COUNTER:
            self.counter_QUA_PGM(n_count=int(n_count))
        if self.exp == Experiment.ODMR_CW:
            self.ODMR_CW_QUA_PGM()
        if self.exp == Experiment.RABI:
            self.RABI_QUA_PGM()
        if self.exp == Experiment.PULSED_ODMR:
            self.PulsedODMR_QUA_PGM()
        if self.exp == Experiment.NUCLEAR_RABI:
            self.NuclearRABI_QUA_PGM()
        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
            self.Entanglement_gate_tomography_QUA_PGM(execute_qua=True)
        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
            self.Population_gate_tomography_QUA_PGM(execute_qua=True)
        if self.exp == Experiment.NUCLEAR_POL_ESR:
            self.Nuclear_Pol_ESR_QUA_PGM(execute_qua=True)
        if self.exp == Experiment.NUCLEAR_MR:
            self.NuclearMR_QUA_PGM()
        if self.exp == Experiment.Nuclear_spin_lifetimeS0:
            self.Nuclear_spin_lifetimeS0_QUA_PGM()
        if self.exp == Experiment.Nuclear_spin_lifetimeS1:
            self.Nuclear_spin_lifetimeS1_QUA_PGM()
        if self.exp == Experiment.Nuclear_Ramsay:
            self.Nuclear_Ramsay_QUA_PGM()
        if self.exp == Experiment.Hahn:
            self.Hahn_QUA_PGM()
        if self.exp == Experiment.Electron_lifetime:
            self.Electron_lifetime_QUA_PGM()
        if self.exp == Experiment.Electron_Coherence:
            self.Electron_Coherence_QUA_PGM()
        if self.exp == Experiment.SCAN: # ~ 35 msec per measurement for on average for larage scans
            self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count), num_measurement_per_array=int(num_measurement_per_array),triggerThreshold=self.ScanTrigger)
        if self.exp == Experiment.ODMR_Bfield:
            self.ODMR_Bfield_QUA_PGM()
        if self.exp == Experiment.Nuclear_Fast_Rot:
            self.NuclearFastRotation_QUA_PGM()
        if self.exp == Experiment.G2:
            self.g2_raw_QUA()

    def QUA_execute(self, closeQM = False, quaPGM = None,QuaCFG = None):
        if QuaCFG == None:
            QuaCFG = self.quaCFG

        if self.bEnableSimulate:
            sourceFile = open('debug.py', 'w')
            print(generate_qua_script(self.quaPGM, QuaCFG), file=sourceFile)
            sourceFile.close()
            simulation_config = SimulationConfig(duration=28000)  # clock cycles
            job_sim = self.qmm.simulate(QuaCFG, self.quaPGM, simulation_config)
            # Simulate blocks python until the simulation is done
            job_sim.get_simulated_samples().con1.plot()
            plt.show()

            return None, None
        else:
            if closeQM or self.chkbox_close_all_qm:
                self.chkbox_close_all_qm = False
                self.qmm.close_all_quantum_machines()

            if quaPGM is None:
                quaPGM = self.quaPGM

            qm = self.qmm.open_qm(config=QuaCFG, close_other_machines=closeQM)
            job = qm.execute(quaPGM)

            newQM = self.qmm.list_open_quantum_machines()
            print(f"before close: {newQM}")

            return qm, job
    def verify_insideQUA_FreqValues(self, freq, min=0, max=400):  # [MHz]
        if freq < min * self.u.MHz or freq > max * self.u.MHz:
            raise Exception('freq is out of range. verify base freq is up to 400 MHz relative to resonance')
    def GenVector(self,min,max,delta, asInt = False, N = "none" ):
        if N == "none":
            N = int((max - min)/delta + 1)
        vec1 = np.linspace(min,max,N,endpoint=True)
        if asInt:
            vec1 = vec1.astype(int)
        # vec2 = np.arange(min, max + delta/10, delta)
        return vec1

    '''
        array = array to shuffle (QUA variable)
        array_len = size of 'array' [int]
    '''
    def QUA_shuffle(self, array, array_len):
        temp = declare(int)
        j = declare(int)
        i = declare(int)
        with for_(i, 0, i < array_len, i + 1):
            assign(j, Random().rand_int(array_len - i))
            assign(temp, array[j])
            assign(array[j], array[array_len - 1 - i])
            assign(array[array_len - 1 - i], temp)
    '''
        t_pump = time to pump state [nsec]
        t_mw = time to rotate (MW) [nsec]
        f_mw = resonance frequncy of relevant state (MW) [Hz]
        p_mw = power (MW) [between 0 to 1, float]
        t_rf = time to rotate (RF) [nsec]
        f_rf = resonance frequncy of relevant state (RF) [Hz]
        p_rf = power (RF) [between 0 to 1, float]
    '''
    def QUA_Pump(self,t_pump,t_mw, t_rf, f_mw,f_rf, p_mw, p_rf,t_wait):
        align()
        # set frequencies to resonance
        update_frequency("MW", f_mw)
        update_frequency("RF", f_rf)

        # play MW
        play("xPulse"* amp(p_mw), "MW", duration=t_mw // 4)
        # play RF (@resonance freq & pulsed time)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=t_rf // 4)
        # turn on laser to polarize
        align("RF", "Laser")
        play("Turn_ON", "Laser", duration=t_pump // 4)
        align()
        if t_wait>4:
            wait(t_wait)
    def QUA_PGM(self):#, exp_params, QUA_exp_sequence):
        if self.exp == Experiment.G2:
                self.g2_raw_QUA()
        else:
            with program() as self.quaPGM:
                self.n = declare(int)             # iteration variable
                self.n_st = declare_stream()      # stream iteration number
                self.times = declare(int, size=100)
                self.times_ref = declare(int, size=100)

                self.f = declare(int)         # frequency variable which we change during scan - here f is according to calibration function
                self.t = declare(int)         # [cycles] time variable which we change during scan
                self.p = declare(fixed)       # [unit less] proportional amp factor which we change during scan


                self.m = declare(int)             # number of pumping iterations
                self.i_idx = declare(int)         # iteration variable
                self.j_idx = declare(int)         # iteration variable
                self.k_idx = declare(int)         # iteration variable

                self.site_state = declare(int)  # site preperation state
                self.m_state = declare(int)     # measure state

                self.counts_tmp = declare(int)                    # temporary variable for number of counts
                self.counts_ref_tmp = declare(int)                # temporary variable for number of counts reference
                self.counts_ref2_tmp = declare(int)               # 2nd temporary variable for number of counts reference

                self.runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
                self.track_idx = declare(int, value=0)              # iteration variable
                self.tracking_signal_tmp = declare(int)             # tracking temporary variable
                self.tracking_signal = declare(int, value=0)        # tracking variable
                self.tracking_signal_st = declare_stream()          # tracking strean variable
                self.sequenceState = declare(int,value=0)           # IO1 variable

                self.counts = declare(int, size=self.vectorLength)     # experiment signal (vector)
                self.counts_ref = declare(int, size=self.vectorLength) # reference signal (vector)
                self.counts_ref2 = declare(int, size=self.vectorLength) # reference signal (vector)
                self.resCalculated = declare(int, size=self.vectorLength) # normalized values vector

                # Shuffle parameters
                # self.val_vec_qua = declare(fixed, value=self.p_vec_ini)    # volts QUA vector
                # self.f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
                self.val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # volts QUA vector
                self.idx_vec_qua = declare(int, value=self.idx_vec_ini)                               # indexes QUA vector
                self.idx = declare(int)                                                          # index variable to sweep over all indexes

                # stream parameters
                self.counts_st = declare_stream()      # experiment signal
                self.counts_ref_st = declare_stream()  # reference signal
                self.counts_ref2_st = declare_stream()  # reference signal
                self.resCalculated_st = declare_stream()  # reference signal

                with for_(self.n, 0, self.n < self.n_avg, self.n + 1): # AVG loop
                    # reset vectors
                    with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
                        assign(self.counts_ref2[self.idx], 0)  # shuffle - assign new val from randon index
                        assign(self.counts_ref[self.idx], 0)  # shuffle - assign new val from randon index
                        assign(self.counts[self.idx], 0)  # shuffle - assign new val from randon index
                        assign(self.resCalculated[self.idx], 0)  # shuffle - assign new val from randon index

                    # shuffle index
                    with if_(self.bEnableShuffle):
                        self.QUA_shuffle(self.idx_vec_qua, self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

                    # sequence
                    with for_(self.idx, 0, self.idx < self.array_length, self.idx + 1): # loop over scan vector
                        assign(self.sequenceState, IO1)
                        with if_(self.sequenceState == 0):
                            self.execute_QUA()

                        with else_():
                            assign(self.tracking_signal, 0)
                            with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                                play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                                measure("min_readout", "Detector_OPD", None, time_tagging.digital(self.times_ref, self.time_in_multiples_cycle_time(self.Tcounter), self.tracking_signal_tmp))
                                assign(self.tracking_signal,self.tracking_signal+self.tracking_signal_tmp)
                            align()

                    # tracking signal
                    with if_(self.runTracking):
                        assign(self.track_idx,self.track_idx + 1) # step up tracking counter
                        with if_(self.track_idx > self.trackingNumRepeatition-1):
                            assign(self.tracking_signal, 0)  # shuffle - assign new val from randon index
                            # reference sequence
                            with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                                play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                                measure("min_readout", "Detector_OPD", None, time_tagging.digital(self.times_ref, self.time_in_multiples_cycle_time(self.Tcounter), self.tracking_signal_tmp))
                                assign(self.tracking_signal,self.tracking_signal+self.tracking_signal_tmp)
                            assign(self.track_idx,0)

                    # stream
                    with if_(self.sequenceState == 0):
                        with for_(self.idx, 0, self.idx < self.vectorLength,self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                            save(self.counts[self.idx], self.counts_st)
                            save(self.counts_ref[self.idx], self.counts_ref_st)
                            save(self.counts_ref2[self.idx], self.counts_ref2_st)
                            save(self.resCalculated[self.idx], self.resCalculated_st)

                    save(self.n, self.n_st)  # save number of iteration inside for_loop
                    save(self.tracking_signal, self.tracking_signal_st)  # save number of iteration inside for_loop

                with stream_processing():
                    self.counts_st.buffer(self.vectorLength).average().save("counts")
                    self.counts_ref_st.buffer(self.vectorLength).average().save("counts_ref")
                    self.counts_ref2_st.buffer(self.vectorLength).average().save("counts_ref2")
                    self.resCalculated_st.buffer(self.vectorLength).average().save("resCalculated")
                    self.n_st.save("iteration")
                    self.tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def execute_QUA(self):
        if self.exp == Experiment.NUCLEAR_POL_ESR:
            self.Nuclear_Pol_ESR_QUA_PGM(Generate_QUA_sequance = True)
        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
            self.Population_gate_tomography_QUA_PGM(Generate_QUA_sequance = True)
        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
            self.Entanglement_gate_tomography_QUA_PGM(Generate_QUA_sequance = True)
    def Nuclear_Pol_ESR_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):  # NUCLEAR_POL_ESR
        if generate_params:
            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
            self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed)
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
            self.tMW = self.t_mw
            self.tMW2 = self.t_mw2
            self.tWait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
            # fMW_res = 0 if fMW_res < 0 else fMW_res
            # self.fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
            self.fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_res)
            self.tRF = self.rf_pulse_time
            self.Npump = self.n_nuc_pump

            # frequency scan vector
            self.f_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # length and idx vector
            self.vectorLength = len(self.f_vec) # size of arrays
            self.array_length = len(self.f_vec)  # frquencies vector size
            self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector

            # tracking signal
            self.tSequencePeriod = ((self.tMW + self.tLaser) * (self.Npump + 2) + self.tRF * self.Npump) * self.array_length
            self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
            self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6) # []
            self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(self.Tcounter)
            self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1
        if Generate_QUA_sequance:
            assign(self.f, self.val_vec_qua[self.idx_vec_qua[self.idx]])  # shuffle - assign new val from randon index

            # signal
            # polarize (@fMW_res @ fRF_res)
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=0)#self.tWait)
            align()

            # update MW frequency
            update_frequency("MW", self.f)
            # play MW
            play("xPulse"*amp(self.mw_P_amp2), "MW", duration=self.tMW2 // 4)
            # play Laser
            align()
            # align("MW", "Laser")
            play("Turn_ON", "Laser", duration=(self.tLaser + self.tMeasureProcess) // 4)
            # play Laser
            # align("MW", "Detector_OPD")
            # measure signal
            measure("readout", "Detector_OPD", None, time_tagging.digital(self.times, self.tMeasure, self.counts_tmp))
            assign(self.counts[self.idx_vec_qua[self.idx]], self.counts[self.idx_vec_qua[self.idx]] + self.counts_tmp)
            align()

            # reference
            wait(self.tMW2 // 4)  # don't Play MW
            # Play laser
            play("Turn_ON", "Laser", duration=(self.tLaser + self.tMeasureProcess) // 4)
            # Measure ref
            measure("readout", "Detector_OPD", None, time_tagging.digital(self.times_ref, self.tMeasure, self.counts_ref_tmp))
            assign(self.counts_ref[self.idx_vec_qua[self.idx]], self.counts_ref[self.idx_vec_qua[self.idx]] + self.counts_ref_tmp)
        if execute_qua:
            self.Nuclear_Pol_ESR_QUA_PGM(generate_params=True)
            self.QUA_PGM()
    '''
        site_state = QUA varible
    '''
    def QUA_prepare_state(self, site_state):
        # ************ shift to gen parameters ************
        # self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
        # self.verify_insideQUA_FreqValues(self.fMW_1st_res)
        # self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
        # self.verify_insideQUA_FreqValues(self.fMW_2nd_res)
        # ************ shift to gen parameters ************

        # reset
        align()
        play("Turn_ON", "Laser", self.tPump // 4)
        wait(self.tWait)
        align()
        with if_(site_state == 0): #|00>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            wait(self.tMW)

        with if_(site_state == 1): #|01>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_1st_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            wait(self.tMW)

        with if_(site_state == 2): #|10>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            # play MW
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

        with if_(site_state == 3): #|11>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_1st_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            # play MW
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.tMW // 4)

        with if_(site_state == 4): #|10>+|11>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            # play MW
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

            align("MW","RF")
            # RF Y pulse
            frame_rotation_2pi(0.25,"RF")
            play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
    '''
    idx = QUA variable
    m_state = QUA variable
    '''
    def QUA_measure(self,m_state,idx,tMeasure,t_rf,t_mw,p_rf):
        # ************ shift to gen parameters ************
        # self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # [nsec]
        # ************ shift to gen parameters ************
        align()

        # populations
        with if_(m_state==1):
            wait((self.tRF+2*t_mw) // 4)
        with if_(m_state==2):
            wait((self.tRF+t_mw) // 4)
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
        with if_(m_state==3):
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=self.tRF // 4)
            align("RF","MW")
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)

        # e-coherences
        with if_(m_state==4):
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            wait(int((self.tRF+2*self.t_mw-self.t_mw2/2) // 4))
        with if_(m_state==5):
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            wait(int((self.tRF+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==6):
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            wait(int((self.tRF+2*self.t_mw-self.t_mw2/2) // 4))
        with if_(m_state==7):
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            wait(int((self.tRF+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        # n-coherences
        with if_(m_state==8):
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            wait(int((self.tRF/2+self.t_mw) // 4))
            align("RF","MW")
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==9):
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==10):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==11):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        # e-n-coherences
        with if_(m_state==12):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==13):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==14):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==15):
            update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(self.t_mw2/2) // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(self.tRF/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((self.tRF/2+self.t_mw-self.t_mw2/2) // 4))
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        align()
        # Play laser
        play("Turn_ON", "Laser", duration=(tMeasure + self.tMeasureProcess) // 4)
        # Measure ref
        measure("readout", "Detector_OPD", None, time_tagging.digital(self.times_ref, tMeasure, self.counts_tmp))
        assign(self.counts[idx], self.counts[idx] + self.counts_tmp)
    def QUA_ref0(self,idx,tPump,tMeasure,tWait):
        # pump
        align()
        play("Turn_ON", "Laser", duration=tPump // 4)
        wait(int(tWait//4))
        # measure
        align()
        play("Turn_ON", "Laser", duration=tMeasure // 4)
        measure("readout", "Detector_OPD", None,time_tagging.digital(self.times_ref, tMeasure, self.counts_ref_tmp))
        assign(self.counts_ref[idx], self.counts_ref[idx] + self.counts_ref_tmp)
    def QUA_ref1(self,idx,tPump,tMeasure,tWait,t_mw,f_mw,p_mw):
        # pump
        align()
        play("Turn_ON", "Laser", duration=tPump // 4)
        wait(int(tWait//4))
        # play MW
        align()
        update_frequency("MW", f_mw)
        play("xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw) // 4)
        align()
        # measure
        play("Turn_ON", "Laser", duration=tMeasure // 4)
        measure("readout", "Detector_OPD", None,time_tagging.digital(self.times_ref, tMeasure, self.counts_ref2_tmp))
        assign(self.counts_ref2[idx], self.counts_ref2[idx] + self.counts_ref2_tmp)
    def Entanglement_gate_tomography_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):
        if generate_params:
            # todo update parameters if needed for this sequence
            # dummy vectors to be aligned with QUA_PGM convention
            self.array_length = 1
            self.idx_vec_ini = np.arange(0, self.array_length, 1)
            self.f_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime) # [nsec]
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump) # [nsec]
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # [nsec]
            self.tWait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            self.Npump = self.n_nuc_pump

            # MW parameters
            self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
            self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_1st_res)
            self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

            # RF parameters
            self.tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
            self.f_rf = self.rf_resonance_freq

            # length and idx vector
            self.first_state = 0 # serial number of first initial state
            self.last_state = 0 # serial number of last initial state
            self.number_of_states = 1 # number of initial states
            self.number_of_measurement = 15 # number of measurements
            self.vectorLength = self.number_of_states*self.number_of_measurement  # total number of measurements
            self.idx_vec_ini = np.arange(0, self.vectorLength, 1) # for visualization purpose

            # tracking signal
            self.tSequencePeriod = (self.tMW + self.tRF) * self.array_length
            self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
            self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6) # []
            self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(self.Tcounter)
            self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

            self.bEnableShuffle = False

        if Generate_QUA_sequance:
            with for_(self.site_state, self.first_state, self.site_state < self.last_state + 1, self.site_state + 1): # site state loop
                with for_(self.j_idx, 0, self.j_idx < self.number_of_measurement, self.j_idx + 1): # measure loop
                    assign(self.i_idx,self.site_state*(self.number_of_states-1)+self.j_idx)
                    # prepare state
                    self.QUA_prepare_state(site_state=self.site_state)
                    # C-NOT
                    #align()
                    #update_frequency("MW", self.fMW_2nd_res)
                    #play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
                    # measure
                    self.QUA_measure(m_state=self.j_idx+1,idx=self.i_idx,tMeasure=self.tMeasure,t_rf=self.tRF,t_mw=self.tMW,p_rf = self.rf_proportional_pwr)
                    # reference
                    self.QUA_ref0(idx=self.i_idx,tPump=self.tPump,tMeasure=self.tMeasure,tWait=self.tWait+3*self.tRF/2+4*self.tMW)
                    self.QUA_ref1(idx=self.i_idx,
                                  tPump=self.tPump,tMeasure=self.tMeasure,tWait=self.tWait+3*self.tRF/2+4*self.tMW-self.t_mw2,
                                  t_mw=self.time_in_multiples_cycle_time(self.t_mw2),f_mw=(self.fMW_1st_res+self.fMW_2nd_res)/2,p_mw=self.mw_P_amp2)

            with for_(self.i_idx, 0, self.i_idx < self.vectorLength, self.i_idx + 1):
                assign(self.resCalculated[self.i_idx],(self.counts[self.i_idx]-self.counts_ref2[self.i_idx])*1000000/(self.counts_ref2[self.i_idx]-self.counts_ref[self.i_idx]))

        if execute_qua:
            self.Entanglement_gate_tomography_QUA_PGM(generate_params=True)
            self.QUA_PGM()
    def Population_gate_tomography_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):
        if generate_params:
            # dummy vectors to be aligned with QUA_PGM convention
            self.array_length = 1
            self.idx_vec_ini = np.arange(0, self.array_length, 1)
            self.f_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime) # [nsec]
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump) # [nsec]
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # [nsec]
            self.tWait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            self.Npump = self.n_nuc_pump

            # MW parameters
            self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
            self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_1st_res)
            self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

            # RF parameters
            self.tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
            self.f_rf = self.rf_resonance_freq

            # length and idx vector
            self.number_of_states = 4 # number of initial states |00>, |01>, |10>, |11>
            self.number_of_measurement = 3 # number of intensities measurements
            self.vectorLength = self.number_of_states*self.number_of_measurement  # total number of measurements
            self.idx_vec_ini = np.arange(0, self.vectorLength, 1) # for visualization purpose

            # tracking signal
            self.tSequencePeriod = (self.tMW + self.tRF) * self.array_length
            self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
            self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6) # []
            self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(self.Tcounter)
            self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

            self.bEnableShuffle = False

        if Generate_QUA_sequance:
            with for_(self.site_state, 0, self.site_state < self.number_of_states, self.site_state + 1): # site state loop
                with for_(self.j_idx, 0, self.j_idx < self.number_of_measurement, self.j_idx + 1): # measure loop
                    assign(self.i_idx,self.site_state*(self.number_of_states-1)+self.j_idx)
                    # prepare state
                    self.QUA_prepare_state(site_state=self.site_state)
                    # C-NOT
                    update_frequency("MW", self.fMW_2nd_res)
                    play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
                    # measure
                    self.QUA_measure(m_state=self.j_idx+1,idx=self.i_idx,tMeasure=self.tMeasure,t_rf=self.tRF,t_mw=self.tMW,p_rf = self.rf_proportional_pwr)
                    # reference
                    self.QUA_ref0(idx=self.i_idx,tPump=self.tPump,tMeasure=self.tMeasure,tWait=self.tWait+self.tRF+3*self.tMW)
                    self.QUA_ref1(idx=self.i_idx,
                                  tPump=self.tPump,tMeasure=self.tMeasure,tWait=self.tWait+self.tRF+3*self.tMW-self.t_mw2,
                                  t_mw=self.time_in_multiples_cycle_time(self.t_mw2),f_mw=(self.fMW_1st_res+self.fMW_2nd_res)/2,p_mw=self.mw_P_amp2)

            with for_(self.i_idx, 0, self.i_idx < self.vectorLength, self.i_idx + 1):
                assign(self.resCalculated[self.i_idx],(self.counts[self.i_idx]-self.counts_ref2[self.i_idx])*1000000/(self.counts_ref2[self.i_idx]-self.counts_ref[self.i_idx]))

        if execute_qua:
            self.Population_gate_tomography_QUA_PGM(generate_params=True)
            self.QUA_PGM()

    def MZI_g2(self,g2, times_1, counts_1, times_2, counts_2, correlation_width):
        """
        Calculate the second order correlation of click times between two counting channels

        :param g2: (QUA array of type int) - g2 measurement from the previous iteration.
        The size must be greater than correlation width.
        :param times_1: (QUA array of type int) - Click times in nanoseconds from channel 1
        :param counts_1: (QUA int) - Number of total clicks at channel 1
        :param times_2: (QUA array of type int) - Click times in nanoseconds from channel 2
        :param counts_2: (QUA int) - Number of total clicks at channel 2
        :param correlation_width: (int) - Relevant correlation window to analyze data
        :return: (QUA array of type int) - Updated g2
        """
        j = declare(int)
        k = declare(int)
        diff = declare(int)
        diff_ind = declare(int)
        lower_index_tracker = declare(int)
        # set the lower index tracker for each dataset
        assign(lower_index_tracker, 0)
        with for_(k, 0, k < counts_1, k + 1):
            with for_(j, lower_index_tracker, j < counts_2, j + 1):
                assign(diff, times_2[j]-times_1[k])
                # if correlation is outside the relevant window move to the next photon
                with if_(diff > correlation_width):
                    assign(j, counts_2+1)
                with elif_((diff <= correlation_width) & (diff >= -correlation_width)):
                    assign(diff_ind, diff + correlation_width)
                    assign(g2[diff_ind], g2[diff_ind] + 1)
                # Track and evolve the lower bound forward every time a photon falls behind the lower bound
                with elif_(diff < -correlation_width):
                    assign(lower_index_tracker, lower_index_tracker+1)
        return g2
    def g2_raw_QUA(self):
        # Scan Parameters
        n_avg = self.n_avg
        correlation_width = 200*self.u.ns
        self.correlation_width = int(correlation_width)
        expected_counts = 150
        N = 1000 # every N cycles it tries to update the stream

        with program() as self.quaPGM:
            counts_1 = declare(int)  # variable for the number of counts on SPCM1
            counts_2 = declare(int)  # variable for the number of counts on SPCM2
            times_1 = declare(int, size=expected_counts)  # array of count clicks on SPCM1
            times_2 = declare(int, size=expected_counts)  # array of count clicks on SPCM2

            # g2 = declare(int,value=self.GenVector(min=0,max=0,delta=0,N=int(2*correlation_width),asInt=True))  # array for g2 to be saved
            g2 = declare(int, size=int(2*correlation_width))  # array for g2 to be saved
            total_counts = declare(int)

            # Streamables
            g2_st = declare_stream()  # g2 stream
            total_counts_st = declare_stream()  # total counts stream
            n_st = declare_stream() # iteration stream

            # Variables for computation
            p = declare(int)  # Some index to run over
            n = declare(int)  # n: repeat index
            # with infinite_loop_():
                # play("Turn_ON", "Laser")
            idxN = declare(int, value=0) # every N steps it will try to update the stream

            with for_(n, 0, n < n_avg, n+1):
                assign(idxN, idxN + 1)
                play("Turn_ON", "Laser")
                measure("readout", "Detector_OPD", None, time_tagging.digital(times_1, self.Tcounter, counts_1))
                measure("readout", "Detector2_OPD", None, time_tagging.digital(times_2, self.Tcounter, counts_2))

                with if_((counts_1 > 0) & (counts_2 > 0)):
                    g2 = self.MZI_g2(g2, times_1, counts_1, times_2, counts_2, correlation_width)

                assign(total_counts, counts_1+counts_2+total_counts)

                with if_(idxN > N-1):
                    assign(idxN, 0)
                    with for_(p, 0, p < g2.length(), p + 1):
                        save(g2[p], g2_st)
                        # assign(g2[p], 0)

                    save(n, n_st)
                    save(total_counts, total_counts_st)

            save(n, n_st)
            save(total_counts, total_counts_st)

            with stream_processing():
                # g2_st.buffer(correlation_width*2).save("g2")
                g2_st.buffer(correlation_width*2).average().save("g2")
                total_counts_st.save("total_counts")
                n_st.save("iteration")

        self.qm, self.job = self.QUA_execute()

    def ODMR_Bfield_QUA_PGM(self):  # CW_ODMR

        # specific per experiment
        # get experiment values from GUI
        items_val = self.GetItemsVal(items_tag=["inInt_process_time","inInt_TcounterPulsed","inInt_Tsettle","inInt_t_mw","inInt_edge_time"])

        # Experiment time period parameters
        tLaser = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"] +
                                                   items_val["inInt_Tsettle"] +
                                                   items_val["inInt_process_time"]) #self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tMW = self.time_in_multiples_cycle_time(items_val["inInt_t_mw"])#self.t_mw)
        tMeasure = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"])#self.TcounterPulsed)
        tSettle = self.time_in_multiples_cycle_time(items_val["inInt_Tsettle"])#self.Tsettle)
        tEdge = self.time_in_multiples_cycle_time(items_val["inInt_edge_time"])#self.Tedge)
        tBfield = self.time_in_multiples_cycle_time(tMW + 2*tEdge)

        # Scan over MW frequency - gen its vector
        vec = self.GenVector(min=0 * self.u.MHz,max = self.mw_freq_scan_range * self.u.MHz ,delta=self.mw_df * self.u.MHz)
        array_length = len(vec)
        self.f_vec = vec

        # length and idx vector
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = (tBfield+tLaser)*2*array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan

            n = declare(int)         # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)                    # temporary variable for number of counts
            counts_ref_tmp = declare(int)                # temporary variable for number of counts reference

            runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)         # iteration variable
            tracking_signal_tmp = declare(int)                # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)                # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int,value=0)

            counts = declare(int, size=array_length)     # experiment signal (vector)
            counts_ref = declare(int, size=array_length) # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            idx = declare(int)                                                          # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()      # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to zero - DC pulse
            update_frequency("RF", 0 * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new MW frequency
                        assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        update_frequency("MW", f)  # update frequency

                        # Signal
                        wait(tEdge//4,"MW")
                        play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                        # wait(300//4,"RF")
                        play("const" * amp(p), "RF",duration=tBfield // 4)

                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # don't play MW
                        wait(tEdge//4,"MW")
                        play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                        align()

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal,tracking_signal+tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx,track_idx + 1) # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition-1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal,tracking_signal+tracking_signal_tmp)
                        assign(track_idx,0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def NuclearFastRotation_QUA_PGM(self):
        # time
        tMeasueProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tMW = self.time_in_multiples_cycle_time(self.t_mw)
        tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tEdge = self.time_in_multiples_cycle_time(self.Tedge)
        tWait = self.time_in_multiples_cycle_time(self.Twait*1e3)
        tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
        tBfield = self.time_in_multiples_cycle_time(tMW2+2*tEdge)
        Npump = self.n_nuc_pump

        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res # here should be zero
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        # time scan vector
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # amp scan vector
        # set RF frequency:
        pRF = self.rf_Pwr / self.OPX_rf_amp  # p should be between 0 to 1
        pRF = pRF if 0 < pRF < 1 else 0
        if pRF == 0:
            print(f"error RF freq is out of limit {pRF}")
        dp_N = float(self.N_p_amp)
        p_vec_ini = np.arange(0, 0.4, 1/dp_N, dtype=float)  # proportion vect
        self.rf_Pwr_vec = p_vec_ini*self.OPX_rf_amp       # in [V], used to plot the graph

        # MW frequency scan vector
        # fitCoff - see Eilon's Onenote
        # f2_GHz*1e9 + (b*V/(V + c))*1e9
        b = 0.0344
        c = 0.124
        self.f_vec = ((fMW_res1+fMW_res2)/2 + (self.rf_Pwr_vec*b/(self.rf_Pwr_vec + c))*1e9)    # [Hz], frequencies vector
        self.f_vec = self.f_vec.astype(int)

        # length and idx vector
        array_length = len(p_vec_ini)                      # amps vector size
        # array_length = len(self.t_vec)                      # time vector size
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+tBfield+tWait+tMW+tLaser)*3*array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan - here f is according to calibration function
            t = declare(int)         # [cycles] time variable which we change during scan
            p = declare(fixed)         # [unit less] proportional amp factor which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)                    # temporary variable for number of counts
            counts_ref_tmp = declare(int)                # temporary variable for number of counts reference
            counts_ref2_tmp = declare(int)                # temporary variable for number of counts reference

            runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)         # iteration variable
            tracking_signal_tmp = declare(int)                # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)                # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int,value=0)

            counts = declare(int, size=array_length)     # experiment signal (vector)
            counts_ref = declare(int, size=array_length) # reference signal (vector)
            counts_ref2 = declare(int, size=array_length) # reference signal (vector)

            # Shuffle parameters
            # f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))
            f_vec_qua = declare(int, value=self.f_vec)    # frequencies QUA vector
            val_vec_qua = declare(fixed, value=p_vec_ini)    # volts QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            idx = declare(int)                                                          # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()      # experiment signal
            counts_ref_st = declare_stream()  # reference signal
            counts_ref2_st = declare_stream()  # reference signal

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref2[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new RF proportional amplitude
                        assign(p, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index

                        assign(f, f_vec_qua[idx_vec_qua[idx]])

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw"*amp(self.mw_P_amp), "MW", duration=tMW//4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz) # set RF frequency to resonance
                            play("const" * amp(pRF), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()

                        wait(tEdge//4,"MW")
                        update_frequency("MW", f)
                        play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(20//4,"RF") # manual calibration
                        update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                        play("const" * amp(p), "RF",duration=tBfield // 4)

                        align()
                        wait(tWait//4)
                        update_frequency("MW", fMW_res1)
                        play("cw"*amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw"*amp(self.mw_P_amp), "MW", duration=tMW//4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz) # set RF frequency to resonance
                            play("const" * amp(pRF), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()

                        wait((tEdge+tMW2+tWait)//4,"MW")
                        # update_frequency("MW", fMW_res2)
                        # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(300//4,"RF") # manual calibration
                        # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        # align()
                        # wait(tWait)
                        update_frequency("MW", fMW_res1)
                        play("cw"*amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                        align()

                        # reference sequence
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw"*amp(self.mw_P_amp), "MW", duration=tMW//4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz) # set RF frequency to resonance
                            play("const" * amp(pRF), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()

                        wait((tEdge+tMW2+tWait)//4,"MW")
                        # update_frequency("MW", fMW_res2)
                        # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(300//4,"RF") # manual calibration
                        # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        # align()
                        # wait(tWait//4)
                        update_frequency("MW", fMW_res2)
                        play("cw"*amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times_ref, tMeasure, counts_ref2_tmp))
                        assign(counts_ref2[idx_vec_qua[idx]], counts_ref2[idx_vec_qua[idx]] + counts_ref2_tmp)

                        align()

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal,tracking_signal+tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx,track_idx + 1) # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition-1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal,tracking_signal+tracking_signal_tmp)
                        assign(track_idx,0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)
                        save(counts_ref2[idx], counts_ref2_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_ref2_st.buffer(len(self.f_vec)).average().save("counts_ref2")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Electron_lifetime_QUA_PGM(self): #T1
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + tScan_max / 2 + tMW + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index
                        # signal
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        wait(t)
                        align()
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Nuclear_spin_lifetimeS0_QUA_PGM(self):
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + tScan_max / 2 + tMW + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Nuclear_spin_lifetimeS1_QUA_PGM(self):
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + tScan_max / 2 + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Nuclear_Ramsay_QUA_PGM(self):
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + tRF + tScan_max / 2 + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF pi/2
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi/2
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                        # play Laser
                        align("RF", "Laser")
                        play("Turn_ON", "Laser", duration=tSettle // 4)

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # do not play RF
                        wait(t + tRF // 4)
                        # play Laser
                        play("Turn_ON", "Laser", duration=tSettle // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Electron_Coherence_QUA_PGM(self): # Also CPMG when N>0
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.time_in_multiples_cycle_time(self.t_mw)
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Ncpmg = self.n_CPMG

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector (Twait)
        tStart = self.time_in_multiples_cycle_time(self.scan_t_start)  # [nsec]
        if Ncpmg > 0:
            if ((tStart / (2 * Ncpmg) - tMW / 2) <= 20):  # [nsec]
                tStart = (40 + tMW) * Ncpmg
        tScan_min = tStart // 4 if tStart // 4 > 0 else 1  # in [cycles]
        self.scan_t_start = tScan_min * 4

        tEnd = self.time_in_multiples_cycle_time(self.scan_t_end)
        tScan_max = tEnd // 4 if tEnd // 4 > 0 else 1  # in [cycles]
        if tScan_max < tScan_min + self.scan_t_dt // 4:
            tScan_max = tScan_min + self.scan_t_dt // 4

        self.scan_t_end = tScan_max * 4

        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = (tMW + tScan_max / 2 + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            tWait = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            # update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            # p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index

                        assign(tWait, val_vec_qua[idx_vec_qua[idx]])

                        with if_(Ncpmg > 0):
                            assign(t, tWait / (2 * Ncpmg) - (tMW / 2) // 4)

                            # signal
                        update_frequency("MW", 0)  # const I&Q
                        # play MW (I=1,Q=0) @ Pi/2
                        play("xPulse", "MW", duration=(tMW / 2) // 4)  # xPulse I = 0.5V, Q = zero
                        # wait t unit
                        with if_(Ncpmg == 0):
                            wait(tWait)

                        # "CPMG section" I=0, Q=1 @ Pi
                        with for_(m, 0, m < Ncpmg, m + 1):
                            wait(t)
                            # play MW
                            update_frequency("MW", 0)
                            play("xPulse", "MW", duration=tMW // 4)  # yPulse I = zero, Q = 0.5V
                            # wait t unit
                            wait(t)
                        # align()

                        # play MW (I=1,Q=0) @ Pi/2
                        play("xPulse", "MW", duration=(tMW / 2) // 4)

                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference 
                        # wait Tmw + Twait
                        wait(tWait + tMW // 4)
                        # play laser
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def Hahn_QUA_PGM(self):
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + 2 * tMW + 2 * tRF + tScan_max + tLaser) * array_length * 2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new frequency from randon index
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new time from randon index

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play RF pi/2
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi
                        play("const" * amp(p), "RF", duration=tRF // 4)
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi/2
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("RF", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw", "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=tRF // 4)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # do not play RF
                        wait(2 * t + (2 * tRF) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def NuclearSpinPolarization_pulsedODMR_QUA_PGM(self):  # NUCLEAR_POL_ESR
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        fMW_res = 0 if fMW_res < 0 else fMW_res
        fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
        tRF = self.rf_pulse_time
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # length and idx vector
        array_length = len(self.f_vec)  # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tLaser) * (Npump + 2) + tRF * Npump) * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index

                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # # set MW frequency to resonance
                            # update_frequency("MW", fMW_res)
                            # # play MW
                            # play("cw", "MW", duration=tMW // 4)
                            # # play RF (@resonance freq & pulsed time)
                            # align("MW", "RF")
                            # play("const" * amp(p), "RF", duration=tRF // 4)
                            # # turn on laser to polarize
                            # align("RF", "Laser")
                            # play("Turn_ON", "Laser", duration=tPump // 4)

                            self.QUA_Pump(t_pump = tPump,t_mw = tMW, t_rf = tRF, f_mw = fMW_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw = self.mw_P_amp, p_rf = p, t_wait=self.tWait)
                        align()

                        # update MW frequency
                        update_frequency("MW", f)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # play Laser
                        align("MW", "Detector_OPD")
                        # measure signal 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        wait(tMW // 4)  # don't Play MW
                        # Play laser
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def NuclearMR_QUA_PGM(self):  # v
        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        tRF = self.rf_pulse_time

        # RF frequency scan vector
        f_min = (self.rf_freq + 0) * self.u.MHz  # [MHz],start of freq sweep
        f_max = (self.rf_freq + self.rf_freq_scan_range) * self.u.MHz  # [MHz], end of freq sweep
        df = self.rf_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # length and idx vector
        array_length = len(self.f_vec)  # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = (tMW * 2 + tRF + tLaser) * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)
            p = declare(fixed)  # fixed is similar to float 4bit.28bit

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set RF freq
                        assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        update_frequency("RF", f)

                        # Signal
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW // 4)
                        # play RF after MW
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=tRF // 4)  # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW // 4)
                        # Don't play RF after MW just wait
                        wait(tRF // 4)
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)
                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def NuclearRABI_QUA_PGM(self):  # v
        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw

        # time scan vector
        tRabi_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tRabi_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tRabi_min, tRabi_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt / 10, dt)  # in [cycles]

        # indexes vector
        array_length = len(self.t_vec)
        idx_vec_ini = np.arange(0, array_length, 1)

        # tracking signal
        tSequencePeriod = (tMW * 2 + tRabi_max + tLaser) * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            t = declare(int)  # time variable which we change during scan
            p = declare(fixed)  # fixed is similar to float 4bit.28bit

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            # Set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # updates RF frerquency
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)
                    assign(counts[idx], 0)

                # Shuffel
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new random Trf 
                        assign(t, val_vec_qua[idx_vec_qua[idx]])

                        # Signal
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW // 4)
                        # play RF after MW
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=t)  # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF", "MW")
                        play("cw", "MW", duration=tMW // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW // 4)
                        # Don't play RF after MW just wait
                        wait(t)  # t already devide by four
                        # play MW
                        play("cw", "MW", duration=tMW // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)
                save(tracking_signal, tracking_signal_st)

            with stream_processing():
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def PulsedODMR_QUA_PGM(self):
        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMW2 = self.t_mw2
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)

        # MW frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # length and idx vector
        array_length = len(self.f_vec)  # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = (tMW2 + tLaser) * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # assign new frequency val from randon index
                        assign(f, val_vec_qua[idx_vec_qua[idx]])
                        update_frequency("MW", f)

                        # play MW for time Tmw
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # don't play MW for time t
                        wait(tMW2 // 4)
                        # play laser after MW
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        # align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # add one by one elements from counts (which is a vector) into counts_st
                        save(counts[idx], counts_st)  # here counts_st = counts[t]
                        save(counts_ref[idx], counts_ref_st)  # here counts_st = counts[t]

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def RABI_QUA_PGM(self):  # v
        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)

        # time scan vector
        tRabi_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tRabi_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tRabi_min, tRabi_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt / 10, dt)  # in [cycles]

        # indexes vector
        array_length = len(self.t_vec)
        idx_vec_ini = np.arange(0, array_length, 1)

        # tracking signal
        tSequencePeriod = (tRabi_max + tLaser) * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            t = declare(int)  # time variable which we change during scan

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes
            t_pad = declare(int)

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal
            # CheckIndexes_st = declare_stream()                      # stream iteration number - due to qua bug/issue

            pad_wait_time = declare(int, value = 0)

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)
                    assign(counts[idx], 0)

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):  # range over Tmw
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new random TmW
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        assign(t_pad,int(self.t_vec_ini[-1])-t+5)

                        wait(t_pad) # pad zeros to make the total time between perp and meas constant
                        # play MW for time t
                        update_frequency("MW", 0)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=t)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("min_readout_pulse", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)

                        align()
                        # don't play MW for the maximal mw pulsae duration
                        wait(int(self.t_vec_ini[-1])+5)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        wait(12,"Detector_OPD")
                        measure("min_readout_pulse", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def ODMR_CW_QUA_PGM(self):  # CW_ODMR
        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.Tcounter + self.Tsettle + tMeasueProcess)
        tMW = tLaser
        tMeasure = self.time_in_multiples_cycle_time(self.Tcounter)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)

        # MW frequency scan vector
        f_min = 0 * self.u.MHz  # [Hz], start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # [Hz] end of freq sweep
        df = self.mw_df * self.u.MHz  # [Hz], freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # [Hz], frequencies vector

        # length and idx vector
        array_length = len(self.f_vec)  # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = tLaser * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // tMeasure
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)  # frequency variable which we change during scan

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # frequencies QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new MW frequency
                        assign(f, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                        update_frequency("MW", f)  # update frequency

                        # Signal
                        play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        wait(tSettle // 4, "Detector_OPD")
                        measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # don't play MW
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        wait(tSettle // 4, "Detector_OPD")
                        measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=tLaser // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter), tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length, idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                counts_st.buffer(len(self.f_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")

        self.qm, self.job = self.QUA_execute()
    def TrackingCounterSignal_QUA_PGM(self): # obsolete. keep in order to learn on how to swithc between two PGM
        # integration time for single loop
        tTrackingSignaIntegrationTime_nsec = self.tTrackingSignaIntegrationTime * 1e6
        tMeasure = self.time_in_multiples_cycle_time(
            50000 if tTrackingSignaIntegrationTime_nsec > 50000 else tTrackingSignaIntegrationTime_nsec)  # 50000 [nsec]
        # number of repeatitions
        n_count = tTrackingSignaIntegrationTime_nsec // tMeasure if tTrackingSignaIntegrationTime_nsec // tMeasure > 1 else 1
        # total integration time
        self.tTrackingSignaIntegrationTime = n_count * tMeasure / 1e6  # [msec]

        with program() as self.quaTrackingPGM:
            times = declare(int, size=100)
            n = declare(int)
            counts_tracking = declare(int)
            total_counts_tracking = declare(int, value=0)
            counts_tracking_st = declare_stream()  # stream for counts

            pause()
            with infinite_loop_():
                assign(total_counts_tracking, 0)
                with for_(n, 0, n < n_count, n + 1):  # number of averages / total integation time
                    play("Turn_ON", "Laser", duration=tMeasure // 4)
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure), counts_tracking)
                    assign(total_counts_tracking, total_counts_tracking + counts_tracking)

                save(total_counts_tracking, counts_tracking_st)

            with stream_processing():
                counts_tracking_st.save("counts_tracking")

        self.qmTracking, self.job_Tracking = self.QUA_execute(closeQM=False, quaPGM=self.quaTrackingPGM)
    def counter_QUA_PGM(self, n_count=1):
        with program() as self.quaPGM:
            self.times = declare(int, size=1000)
            self.times_ref = declare(int, size=1000)
            self.counts = declare(int)  # apd1
            self.counts_ref = declare(int)  # apd2
            self.total_counts = declare(int, value=0)  # apd1
            self.total_counts2 = declare(int, value=0)  # apd1
            self.n = declare(int)  #
            self.counts_st = declare_stream()
            self.counts_ref_st = declare_stream()  # stream for counts
            self.n_st = declare_stream()  # stream for number of iterations
            with infinite_loop_():
                with for_(self.n, 0, self.n < n_count, self.n + 1):  # number of averages / total integation time
                    play("Turn_ON", "Laser", duration=int(self.Tcounter * self.u.ns // 4))  #
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(self.times, int(self.Tcounter * self.u.ns), self.counts))
                    measure("min_readout", "Detector2_OPD", None, time_tagging.digital(self.times_ref, int(self.Tcounter * self.u.ns), self.counts_ref))

                    assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language  # align()
                    assign(self.total_counts2, self.total_counts2 + self.counts_ref)  # assign is equal in qua language  # align()

                save(self.total_counts, self.counts_st)
                save(self.total_counts2, self.counts_ref_st) # only to keep on convention
                assign(self.total_counts, 0)
                assign(self.total_counts2, 0)
                # save(self.n, self.n_st)  # save number of iteration inside for_loop

            with stream_processing():
                self.counts_st.with_timestamps().save("counts")
                self.counts_ref_st.with_timestamps().save("counts_ref")
                # self.counts_st.with_timestamps().save("counts_reg")
                # self.n_st.save("iteration")

        self.qm, self.job = self.QUA_execute()
    def MeasureByTrigger_QUA_PGM(self, num_bins_per_measurement: int = 1, num_measurement_per_array: int = 1, triggerThreshold: int = 1):
        # MeasureByTrigger_QUA_PGM function measures counts.
        # It will run a single measurement every trigger.
        # each measurement will be append to buffer.
        laser_on_duration = int(self.Tcounter * self.u.ns // 4)
        single_integration_time = int(self.Tcounter * self.u.ns)
        smaract_ttl_duration = int(self.smaract_ttl_duration * self.u.ms // 4)

        with program() as self.quaPGM:
            times = declare(int, size=1000)  # maximum number of counts allowed per measurements
            counts = declare(int)  # apd1
            total_counts = declare(int, value=0)  # apd1
            n = declare(int)  #
            meas_idx = declare(int, value=0)
            counts_st = declare_stream()
            meas_idx_st = declare_stream()

            pulsesTriggerDelay = 5000000 // 4
            sequenceState = declare(int, value=0)
            triggerTh = declare(int, value=triggerThreshold)
            assign(IO2, 0)

            with infinite_loop_():
                # wait_for_trigger("Laser") # wait for smaract trigger
                assign(sequenceState, IO2)
                with if_((sequenceState + 1 > triggerTh) & (sequenceState - 1 < triggerTh)):
                    assign(IO2, 0)
                    assign(sequenceState, 0)
                    align()
                    align()
                    # pause()
                    with for_(n, 0, n < num_bins_per_measurement, n + 1):
                        play("Turn_ON", "Laser", duration=laser_on_duration)
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, single_integration_time, counts))
                        assign(total_counts, total_counts + counts)

                    save(total_counts, counts_st)
                    assign(total_counts, 0)

                    align()
                    wait(pulsesTriggerDelay)
                    # wait(pulsesTriggerDelay, "SmaractTrigger")
                    # play("Turn_ON", "SmaractTrigger", duration=smaract_ttl_duration)

                    align()
                    assign(meas_idx, meas_idx + 1)
                    save(meas_idx, meas_idx_st)

            with stream_processing():
                meas_idx_st.save("meas_idx_scanLine")
                counts_st.buffer(num_measurement_per_array).save("counts_scanLine")

        self.qm, self.job = self.QUA_execute()

    def Common_updateGraph(self, _xLabel="?? [??],", _yLabel="I [kCounts/sec]"):
        try:
            # todo: use this function as general update graph for all experiments
            self.lock.acquire()
            dpg.set_item_label("graphXY",f"{self.exp.name}, iteration = {self.iteration}, tracking_ref = {self.tracking_ref: .1f}, ref Threshold = {self.refSignal: .1f},shuffle = {self.bEnableShuffle}, Tracking = {self.bEnableSignalIntensityCorrection}")
            dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
            dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
            if self.exp == Experiment.Nuclear_Fast_Rot:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            if self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY,Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
                dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_resCalculated])
            dpg.set_item_label("y_axis", _yLabel)
            dpg.set_item_label("x_axis", _xLabel)
            dpg.fit_axis_data('x_axis')
            dpg.fit_axis_data('y_axis')
            self.lock.release()


        except Exception as e:
            self.btnStop()

    def FastScan_updateGraph(self):
        # Update the graph label with the current experiment name, iteration, and last Y value
        dpg.set_item_label("graphXY", f"{self.exp.name}, iteration = {self.iteration}, lastVal = {round(self.Y_vec[-1], 0)}")

        # Set the values for the X and Y data series
        dpg.set_value("series_counts", [self.X_vec, self.Y_vec])

        # Set the reference counts series to be empty
        dpg.set_value("series_counts_ref", [[], []])

        # Update the axis labels
        dpg.set_item_label("y_axis", "Intensity [kCounts/sec]")
        dpg.set_item_label("x_axis", "Position [pm]")

        # Fit the axis data to the new data range
        dpg.fit_axis_data('x_axis')
        dpg.fit_axis_data('y_axis')

        # Bind themes to the data series for visual distinction
        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")

    def FetchData(self):
        self.refSignal = 0
        if self.bEnableSignalIntensityCorrection:  # prepare search maxI thread
            self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)

        # verify job has started
        while not self.job._is_job_running:
            time.sleep(0.1)
        time.sleep(0.1)

        # fetch right parameters
        if self.exp == Experiment.COUNTER:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref"], mode="live")
        elif self.exp == Experiment.G2:
            self.results = fetching_tool(self.job, data_list=["g2", "total_counts", "iteration"], mode="live")
        elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "counts_ref2", "resCalculated", "iteration","tracking_ref"], mode="live")
        elif self.exp == Experiment.Nuclear_Fast_Rot:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "counts_ref2", "iteration","tracking_ref"], mode="live")
        else:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "iteration", "tracking_ref"], mode="live")

        self.reset_data_val()

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
        dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
        dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

        lastTime = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6
        while self.results.is_processing():
            self.GlobalFetchData()

            dpg.set_item_label("series_counts", "counts")
            dpg.set_item_label("series_counts_ref", "counts_ref")

            if self.exp == Experiment.COUNTER:
                dpg.set_item_label("graphXY", f"{self.exp.name},  lastVal = {round(self.Y_vec[-1], 2)}")
                dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
                dpg.set_value("series_counts_ref2", [[], []])
                dpg.set_value("series_res_calcualted", [[], []])
                dpg.set_item_label("series_counts", "det_1")
                dpg.set_item_label("series_counts_ref", "det_2")
                dpg.set_item_label("y_axis", "I [kCounts/sec]")
                dpg.set_item_label("x_axis", "time [sec]")
                dpg.fit_axis_data('x_axis')
                dpg.fit_axis_data('y_axis')

                dpg.bind_item_theme("series_counts", "LineYellowTheme")
                dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
                dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")
                # self.Counter_updateGraph()
            if self.exp == Experiment.ODMR_CW:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.RABI:  # time
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experiment.ODMR_Bfield:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.PULSED_ODMR:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.NUCLEAR_RABI:  # time
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experiment.NUCLEAR_MR:  # freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [MHz]")
            if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.Nuclear_spin_lifetimeS0:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Nuclear_spin_lifetimeS1:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Nuclear_Ramsay:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Hahn:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Electron_lifetime:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Electron_Coherence:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experiment.Nuclear_Fast_Rot:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="amp [v]")
            if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="index")
            if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="index")
            if self.exp == Experiment.G2:
                dpg.set_item_label("graphXY", f"{self.exp.name}, iteration = {self.iteration}, Totalounts = {round(self.g2_totalCounts, 0)}")
                dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                dpg.set_value("series_counts_ref", [[], []])
                dpg.set_value("series_counts_ref2", [[], []])
                dpg.set_value("series_res_calcualted", [[], []])
                dpg.set_item_label("series_counts", "G2 val")
                dpg.set_item_label("series_counts_ref", "_")
                dpg.set_item_label("series_counts_ref2", "_")
                dpg.set_item_label("series_res_calcualted", "_")
                dpg.set_item_label("y_axis", "events")
                dpg.set_item_label("x_axis", "dt [nsec]")
                dpg.fit_axis_data('x_axis')
                dpg.fit_axis_data('y_axis')

                dpg.bind_item_theme("series_counts", "LineYellowTheme")
                dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
                dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")



            current_time = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6
            if not(self.exp == Experiment.COUNTER) and (current_time-lastTime)>self.tGetTrackingSignalEveryTime:
                folder = "d:/temp/"
                if not os.path.exists(folder):
                    folder = "c:/temp/"
                self.btnSave(folder=folder)

                lastTime = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6

            if self.StopFetch:
                break

    def GlobalFetchData(self):
        self.lock.acquire()

        if self.exp == Experiment.COUNTER:
            self.counter_Signal, self.ref_signal = self.results.fetch_all()
        elif self.exp == Experiment.G2:
            self.g2Vec, self.g2_totalCounts, self.iteration = self.results.fetch_all()
        elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
            self.signal, self.ref_signal, self.ref_signal2, self.resCalculated, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
        elif self.exp == Experiment.Nuclear_Fast_Rot:
            self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
        else:
            self.signal, self.ref_signal, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream

        if self.exp == Experiment.COUNTER:
            if len(self.X_vec) > self.NumOfPoints:
                self.Y_vec = self.Y_vec[-self.NumOfPoints:]  # get last NumOfPoint elements from end
                self.Y_vec_ref = self.Y_vec_ref[-self.NumOfPoints:]  # get last NumOfPoint elements from end
                self.X_vec = self.X_vec[-self.NumOfPoints:]

            self.Y_vec.append(self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            self.Y_vec_ref.append(self.ref_signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            self.X_vec.append(self.counter_Signal[1] / self.u.s)  # Convert timestamps to seconds

        if self.exp == Experiment.ODMR_CW:  # freq
            self.X_vec = self.f_vec / self.u.MHz / 1e3 + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / 1000 / (self.Tcounter * 1e-9)
            self.Y_vec_ref = self.ref_signal / 1000 / (self.Tcounter * 1e-9)
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.RABI:  # time
            self.X_vec = self.t_vec  # [nsec]]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.ODMR_Bfield:  #freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.PULSED_ODMR:  #freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.NUCLEAR_RABI:  # time
            self.X_vec = self.t_vec  # [nsec]]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.NUCLEAR_MR:  # freq
            self.X_vec = self.f_vec / float(1e6)  # [MHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Nuclear_spin_lifetimeS0:  # time
            self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Nuclear_spin_lifetimeS1:  # time
            self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Nuclear_Ramsay or self.exp == Experiment.Electron_Coherence:  # time
            self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Hahn:  # time
            self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Electron_lifetime:  # time
            self.X_vec = [e / 1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.Nuclear_Fast_Rot: # time
            self.X_vec = [e for e in self.rf_Pwr_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY: # todo: convert graph to bars instead of line
            self.X_vec = self.idx_vec_ini # index
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_resCalculated = self.resCalculated /1e6
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY: # todo: convert graph to bars instead of line
            self.X_vec = self.idx_vec_ini # index
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_resCalculated = self.resCalculated /1e6
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.G2:
            self.X_vec = self.GenVector(-self.correlation_width+1,self.correlation_width,True)
            self.Y_vec = self.g2Vec#*self.iteration

        self.lock.release()

    def btnStartG2(self):
        self.exp = Experiment.G2
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)



    def StartFetch(self, _target):
        self.to_xml()  # write class parameters to XML
        self.timeStamp = self.getCurrentTimeStamp()

        self.StopFetch = False
        self.fetchTh = threading.Thread(target=_target)
        self.fetchTh.start()

    def btnStartCounterLive(self, b_startFetch=True):
        self.exp = Experiment.COUNTER
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)
        # TODO: Boaz - Check for edge cases in number of measurements per array
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
            num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

        if b_startFetch and not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartODMR_CW(self):
        self.exp = Experiment.ODMR_CW
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()

        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartRABI(self):
        self.exp = Experiment.RABI
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        # self.mwModule.Set_IQ_mode_OFF()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartODMR_Bfield(self):
        self.exp = Experiment.ODMR_Bfield

        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearFastRot(self):
        self.exp = Experiment.Nuclear_Fast_Rot
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz] # todo: remove in all other experiment and also fix QUA
        self.mw_freq = self.mw_freq_resonance
        # self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartPulsedODMR(self):
        self.exp = Experiment.PULSED_ODMR
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearRABI(self):
        self.exp = Experiment.NUCLEAR_RABI
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)
        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_OFF()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartPopulateGateTomography(self):
        self.exp = Experiment.POPULATION_GATE_TOMOGRAPHY
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartStateTomography(self):
        self.exp = Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearPolESR(self):
        self.exp = Experiment.NUCLEAR_POL_ESR
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearMR(self):
        self.exp = Experiment.NUCLEAR_MR
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_OFF()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearSpinLifetimeS0(self):
        self.exp = Experiment.Nuclear_spin_lifetimeS0
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearSpinLifetimeS1(self):
        self.exp = Experiment.Nuclear_spin_lifetimeS1
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartNuclearRamsay(self):
        self.exp = Experiment.Nuclear_Ramsay
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartElectron_Coherence(self):
        self.exp = Experiment.Electron_Coherence
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartHahn(self):
        self.exp = Experiment.Hahn
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance, self.mw_2ndfreq_resonance) - 0.001  # [GHz]
        self.mwModule.Set_freq(self.mw_freq)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_ON()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartElectronLifetime(self):
        self.exp = Experiment.Electron_lifetime
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mwModule.Set_freq(self.mw_freq_resonance)
        self.mwModule.Set_power(self.mw_Pwr)
        self.mwModule.Set_IQ_mode_OFF()
        self.mwModule.Set_PulseModulation_ON()
        if not self.bEnableSimulate:
            self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def StopJob(self, job, qm):
        job.halt()
        report = job.execution_report()
        print(report)
        qm.close()
        newQM = self.qmm.list_open_quantum_machines()
        print(f"after close: {newQM}")
        return report

    def btnStop(self):  # Stop Exp
        try:
            # todo: creat methode that handle OPX close job and instances
            self.stopScan = True
            self.StopFetch = True
            if not self.exp == Experiment.SCAN:
                if self.bEnableSignalIntensityCorrection:
                    if self.MAxSignalTh.is_alive():
                        self.MAxSignalTh.join()
            else:
                dpg.set_item_label("btnOPX_StartScan", "Start Scan")
                dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")

            self.GUI_ParametersControl(True)
            if not self.exp == Experiment.SCAN:
                if (self.fetchTh.is_alive()):
                    self.fetchTh.join()
            else:
                dpg.enable_item("btnOPX_StartScan")

            if (self.job):
                self.StopJob(self.job, self.qm)

            if self.exp == Experiment.COUNTER or self.exp == Experiment.SCAN:
                pass
            else:
                self.mwModule.Get_RF_state()
                if self.mwModule.RFstate:
                    self.mwModule.Turn_RF_OFF()

            if self.exp not in [Experiment.COUNTER, Experiment.SCAN]:
                self.btnSave()
        except Exception as e:
            print(f"An error occurred in btnStop: {e}")

    def btnSave(self, folder=None):  # save data
        print("Saving data...")
        try:
            # file name
            # timeStamp = self.getCurrentTimeStamp()  # get current time stamp
            if folder is None:
                folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + '/'
            else:
                folder_path = folder + self.exp.name + '/'
            if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
                os.makedirs(folder_path)
            fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)

            # parameters + note        
            self.writeParametersToXML(fileName + ".xml")
            print(f'XML file saved to {fileName}.xml')

            # raw data
            RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y_ref2': self.Y_vec_ref2, 'Y_resCalc': self.Y_resCalculated}


            self.saveToCSV(fileName + ".csv", RawData_to_save)
            print(f"CSV file saved to {fileName}.csv")

            # save data as image (using matplotlib)
            if folder is None:
                width = 1920  # Set the width of the image
                height = 1080  # Set the height of the image
                # Create a blank figure with the specified width and height, Convert width and height to inches
                fig, ax = plt.subplots(figsize=(width / 100, height / 100), visible=True)
                plt.plot(self.X_vec, self.Y_vec, label='data')  # Plot Y_vec
                plt.plot(self.X_vec, self.Y_vec_ref, label='ref')  # Plot reference

                # Adjust axes limits (optional)
                # ax.set_xlim(0, 10)
                # ax.set_ylim(-1, 1)

                # Add legend
                plt.legend()

                # Save the figure as a PNG file
                plt.savefig(fileName + '.png', format='png', dpi=300, bbox_inches='tight')
                print(f"Figure saved to {fileName}.png")
                # close figure
                plt.close(fig)

                dpg.set_value("inTxtOPX_expText", "data saved to: " + fileName + ".csv")


        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))  # raise
            print(f"Error while saving data: {ex}")

    def btnStartScan(self):
        self.ScanTh = threading.Thread(target=self.StartScan)
        self.ScanTh.start()

    def btnAutoFocus(self):
        self.ScanTh = threading.Thread(target=self.auto_focus)
        self.ScanTh.start()

    def StartScan(self):
        if self.positioner:
            self.positioner.KeyboardEnabled = False  # TODO: Update the check box in the gui!!
        self.StartScan3D()
        if self.positioner:
            self.positioner.KeyboardEnabled = True  # TODO: Update the check box in the gui!!


    def fetch_peak_intensity(self, integration_time):
        self.qm.set_io2_value(self.ScanTrigger)  # should trigger measurement by QUA io
        time.sleep(integration_time * 1e-3 + 1e-3)  # wait for measurement do occur

        if self.counts_handle.is_processing():
            # print('Waiting for QUA counts')
            self.counts_handle.wait_for_values(1)
            time.sleep(0.1)
            counts = self.counts_handle.fetch_all()
            # print(f"counts.size =  {counts.size}")

            self.qmm.clear_all_job_results()
            return counts

    def auto_focus(self, ch=2):  # units microns
        # Dictionary to store the retrieved values
        auto_focus = {}
        dpg.set_value("Scan_Message", "Auto-focus started")
        print("Auto-focus started")

        # List of item tags to retrieve values from
        item_tags = ["step_um", "z_span_um", "laser_power_mw", "int_time_ms", "offset_from_focus_nm"]

        # Using a for loop to get each value and assign it to the auto_focus dictionary
        for tag in item_tags:
            auto_focus[tag] = dpg.get_value(tag)
            print(f"{tag}: {auto_focus[tag]}")

        # start Qua pgm
        self.exp = Experiment.SCAN
        self.initQUA_gen(n_count=int(auto_focus["int_time_ms"] * self.u.ms / self.Tcounter / self.u.ns), num_measurement_per_array=1)
        res_handles = self.job.result_handles
        self.counts_handle = res_handles.get("counts_scanLine")

        # init
        N = int(auto_focus["z_span_um"] / auto_focus["step_um"])
        initialShift = -1 * int(auto_focus["step_um"] * N / 2)  # [um]
        intensities = []
        coordinate = []

        # set laser PWR
        # original_power = dpg.get_value("power_input")
        # print(f"Original power: {original_power}")
        # print(f"set power: {auto_focus['laser_power_mw']}")
        # self.HW.cobolt.set_power(auto_focus["laser_power_mw"])

        time.sleep(0.1)

        # goto start location - relative to current position
        self.positioner.MoveRelative(ch, int(initialShift * self.positioner.StepsIn1mm * 1e-3))
        time.sleep(0.001)
        while not (self.positioner.ReadIsInPosition(ch)):
            time.sleep(0.001)
        print(f"is in position = {self.positioner.ReadIsInPosition(ch)}")
        self.positioner.GetPosition()
        self.absPosunits = self.positioner.AxesPosUnits[ch]
        self.absPos = self.positioner.AxesPositions[ch]

        # init - fetch data
        self.fetch_peak_intensity(auto_focus["int_time_ms"])

        # loop over all locations
        for i in range(N):
            # Calculate the progress percentage
            progress_percentage = (i + 1) / N * 100

            # Update the message with the progress percentage
            dpg.set_value("Scan_Message", f"Auto-focus in progress: {progress_percentage:.1f}%")

            # fetch new data from stream
            last_intensity = self.fetch_peak_intensity(auto_focus["int_time_ms"])[0]

            # Log data
            coordinate.append(i * auto_focus["step_um"] * self.positioner.StepsIn1mm * 1e-3 + self.absPos)  # Log axis position
            intensities.append(last_intensity)  # Loa signal to array

            # move to next location (relative move)
            self.positioner.MoveRelative(ch, int(auto_focus["step_um"] * self.positioner.StepsIn1mm * 1e-3))
            time.sleep(0.001)
            res = self.positioner.ReadIsInPosition(ch)
            while not (res):
                time.sleep(0.001)
                res = self.positioner.ReadIsInPosition(ch)

        # print
        print(f"z(ch={ch}): ", end="")
        for i in range(len(coordinate)):
            print(f", {coordinate[i] / 1e3: .3f}", end="")
        print("")
        print(f"i(ch={ch}): ", end="")
        for i in range(len(intensities)):
            print(f", {intensities[i]: .3f}", end="")

        # find peak intensity
        # optional: fit to parabula
        if True:
            coefficients = np.polyfit(coordinate, intensities, 2)
            a, b, c = coefficients
            maxPos_parabula = int(-b / (2 * a))
            print(f"ch = {ch}: a = {a}, b = {b}, c = {c}, maxPos_parabula={maxPos_parabula / 1e3}")

        # find max signal
        max_pos = coordinate[intensities.index(max(intensities))]
        print(f"maxPos={max_pos / 1e3}")
        max_pos = max_pos - auto_focus["offset_from_focus_nm"] * self.positioner.StepsIn1mm * 1e-6
        print(f"maxPos after offset={max_pos / 1e3}")

        self.plt_x = np.array(coordinate) * 1e-3
        self.plt_y = intensities
        self.plt_max = round(max_pos / 1e3, 2)
        self.plt_max1 = round(maxPos_parabula / 1e3, 2)

        # move to max signal position
        self.positioner.MoveABSOLUTE(ch, int(max_pos))

        # print(f"Original power: {original_power}")
        # self.HW.cobolt.set_power(original_power)

        # if self.use_picomotor:
        #     print(f"Moving pico {-max_pos * 1e-9}")
        #     self.HW.picomotor.MoveRelative(Motor=ch + 1, Steps=int(-max_pos * 1e-9 * self.pico.StepsIn1mm))
        #     self.positioner.MoveABSOLUTE(ch, 0)

        # shift back tp experiment sequence
        self.qm.set_io1_value(0)
        time.sleep(0.1)

        # stop and close job
        self.StopJob(self.job, self.qm)
        dpg.set_value("Scan_Message", "Auto-focus done")
        print("Auto-focus done")


    def StartScan3D(self):  # currently flurascence scan
        print("start scan steps")
        start_time = time.time()
        print(f"start_time: {self.format_time(start_time)}")

        # init
        self.exp = Experiment.SCAN
        self.GUI_ParametersControl(isStart=False)
        self.to_xml()  # save last params to xml
        self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")  # moved near end of scan

        try:
            # Define the source files and destinations
            file_mappings = [{"src": 'Q:/QT-Quantum_Optic_Lab/expData/Images/Zelux_Last_Image.png',
                "dest_local": self.create_scan_file_name(local=True) + "_ZELUX.png",
                "dest_remote": self.create_scan_file_name(local=False) + "_ZELUX.png"},
                {"src": 'C:/WC/HotSystem/map_config.txt', "dest_local": self.create_scan_file_name(local=True) + "_map_config.txt",
                    "dest_remote": self.create_scan_file_name(local=False) + "_map_config.txt"}]

            # Move each file for both local and remote
            for file_map in file_mappings:
                for dest in [file_map["dest_local"], file_map["dest_remote"]]:
                    if os.path.exists(file_map["src"]):
                        shutil.copy(file_map["src"], dest)
                        print(f"File moved to {dest}")
                    else:
                        print(f"Source file {file_map['src']} does not exist.")
        except Exception as e:
            print(f"Error occurred: {e}")

        self.stopScan = False
        isDebug = True
        self.scan_Out = []
        self.scan_intensities = []

        if self.positioner is smaractMCS2:
            # reset stage motion parameters (stream, motion delays, mav velocity)
            self.positioner.set_in_position_delay(0, delay=0)  # reset delays yo minimal
            self.positioner.DisablePositionTrigger(0)  # disable triggers
            self.positioner.SetVelocity(0, 0)  # set max velocity (ch 0)
            self.positioner.setIOmoduleEnable(dev=0)
            self.positioner.set_Channel_Constant_Mode_State(channel=0)

        # GUI - convert Start Scan to Stop scan
        dpg.disable_item("btnOPX_StartScan")

        # reset res vectors 
        self.X_vec = []
        self.Y_vec = []
        self.Y_vec_ref = []
        self.iteration = 0

        self.Xv = [0]
        self.Yv = [0]
        self.Zv = [0]
        self.initial_scan_Location = []
        self.V_scan = []
        t_wait_motionStart = 0.005
        N = [1, 1, 1]

        # get current (initial) position
        for ch in self.positioner.channels:  # verify in postion
            res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = list(self.positioner.AxesPosUnits)
        self.initial_scan_Location = list(self.positioner.AxesPositions)
        for ch in self.positioner.channels:
            if isDebug:
                print(f"ch{ch}: in position = {res}, position = {self.initial_scan_Location[ch]} {self.positioner.AxesPosUnits[ch]}")

        # goto scan start location
        ini_scan_pos = [0, 0, 0]
        for ch in self.positioner.channels:
            V_scan = []
            if self.b_Scan[ch]:
                ini_scan_pos[ch] = self.initial_scan_Location[ch] - self.L_scan[ch] * 1e3 / 2  # [pm]
                self.positioner.MoveABSOLUTE(ch, int(ini_scan_pos[ch]))  # move absolute to start location
                N[ch] = (int(self.L_scan[ch] / self.dL_scan[ch]))+1
                for i in range(N[ch]):
                    V_scan.append(i * self.dL_scan[ch] * 1e3 + ini_scan_pos[ch])

                time.sleep(t_wait_motionStart)  # allow motion to start
                res = self.readInpos(ch)  # wait motion ends
                if isDebug:
                    print(f"ch{ch} at initial scan position")

            else:
                ini_scan_pos[ch] = self.initial_scan_Location[ch]
                V_scan.append(self.initial_scan_Location[ch])

            self.V_scan.append(V_scan)
        self.positioner.GetPosition()
        if isDebug:
            for i in self.positioner.channels:
                print(f"ch[{i}] Pos = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        Nx = len(self.V_scan[0])
        Ny = len(self.V_scan[1])
        if len(self.V_scan) > 2:
            Nz = len(self.V_scan[2])
        else:
            Nz = 1
            self.V_scan.append([0])
        self.scan_intensities = np.zeros((Nx, Ny, Nz))
        self.scan_data = self.scan_intensities
        self.idx_scan = [0, 0, 0]

        self.startLoc = [self.V_scan[0][0] / 1e6, self.V_scan[1][0] / 1e6, self.V_scan[2][0] / 1e6]
        self.endLoc = [self.V_scan[0][-1] / 1e6, self.V_scan[1][-1] / 1e6, self.V_scan[2][-1] / 1e6]

        self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0], startLoc=self.startLoc, endLoc=self.endLoc)

        # Start Qua PGM
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns), num_measurement_per_array=Nx)
        res_handles = self.job.result_handles
        self.counts_handle = res_handles.get("counts_scanLine")
        self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

        # offset in X start point from 
        x_channel = 0
        scanPx_Start = int(list(self.V_scan[0])[0] - self.dL_scan[x_channel] * 1e3)
        self.positioner.MoveABSOLUTE(channel=x_channel, newPosition=scanPx_Start)
        time.sleep(0.005)  # allow motion to start
        for q in self.positioner.channels:
            self.readInpos(q)  # wait motion ends

        self.dir = 1
        self.scanFN = self.create_scan_file_name(local=True)

        # init measurements index
        previousMeas_idx = 0  # used as workaround to reapet line if an error occur in number of measurements
        meas_idx = 0

        # Calculate the z calibration offset at the origin of the scan
        if self.b_Zcorrection and not self.ZCalibrationData is None:
            z_calibration_offset = int(
                calculate_z_series(self.ZCalibrationData, np.array([self.initial_scan_Location[0]]), self.initial_scan_Location[1])[0])
        z_correction_previous = 0
        for i in range(N[2]):  # Z
            if self.stopScan:
                break
            if 2 in self.positioner.channels:
                self.positioner.MoveABSOLUTE(2, int(self.V_scan[2][i]))

            j = 0
            # for j in range(N[1]):  # Y
            while j < N[1]:  # Y
                if self.stopScan:
                    break
                self.positioner.MoveABSOLUTE(1, int(self.V_scan[1][j]))
                self.dir = self.dir * -1  # change direction to create S shape scan
                V = []

                Line_time_start = time.time()
                for k in range(N[0]):
                    if self.stopScan:
                        break

                    if k == 0:
                        V = list(self.V_scan[0])

                    # Z correction
                    new_z_pos = int(self.V_scan[2][i])
                    if self.b_Zcorrection and not self.ZCalibrationData is None:
                        z_correction_new = int(
                            calculate_z_series(self.ZCalibrationData, np.array([int(V[k])]), int(self.V_scan[1][j]))[0] - z_calibration_offset)
                        if abs(z_correction_new - z_correction_previous) > self.z_correction_threshold:
                            new_z_pos = int(self.V_scan[2][i] + z_correction_new)
                            z_correction_previous = z_correction_new
                            self.positioner.MoveABSOLUTE(2, new_z_pos)
                        else:
                            new_z_pos = new_z_pos + z_correction_previous

                    # move to next X - when trigger the OPX will measure and append the results
                    self.positioner.MoveABSOLUTE(0, int(V[k]))
                    time.sleep(5e-3)
                    for q in self.positioner.channels:
                        self.readInpos(q)  # wait motion ends
                    # self.positioner.generatePulse(channel=0) # should triggere measurement by smaract trigger
                    self.qm.set_io2_value(self.ScanTrigger)  # should triggere measurement by QUA io
                    time.sleep(self.total_integration_time * 1e-3 + 1e-3)  # wait for measurement do occur

                    # fetch X scanned results
                if self.counts_handle.is_processing():
                    print('Waiting for QUA counts')
                    self.counts_handle.wait_for_values(1)
                    self.meas_idx_handle.wait_for_values(1)
                    time.sleep(0.1)
                    meas_idx = self.meas_idx_handle.fetch_all()
                    print(f"meas_idx =  {meas_idx}")
                    counts = self.counts_handle.fetch_all()
                    print(f"counts.size =  {counts.size}")

                    self.qmm.clear_all_job_results()
                    self.scan_intensities[:, j, i] = counts / self.total_integration_time  # counts/ms = Kcounts/s
                    self.UpdateGuiDuringScan(self.scan_intensities[:, :, i], use_fast_rgb=True)

                if (meas_idx - previousMeas_idx) % counts.size == 0:  # if no skips in measurements
                    j = j + 1
                    self.prepare_scan_data(max_position_x_scan = self.endLoc[0] * 1e6 + self.dL_scan[0] * 1e3, min_position_x_scan = self.startLoc[0] * 1e6,start_pos=ini_scan_pos)
                    self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.scanFN)
                else:
                    print("****** error: ******\nNumber of measurements is not consistent with excpected.\nthis line will be repeated.")
                    pass

                previousMeas_idx = meas_idx

                # offset in X start point from 
                self.positioner.MoveABSOLUTE(channel=x_channel, newPosition=scanPx_Start)
                time.sleep(0.005)  # allow motion to start
                for q in self.positioner.channels:
                    self.readInpos(q)  # wait motion ends

                Line_time_End = time.time()
                elapsed_time = time.time() - start_time
                delta = (Line_time_End - Line_time_start)
                estimated_time_left = delta * (N[2] - i) * (N[1] - j) - delta
                estimated_time_left = estimated_time_left if estimated_time_left > 0 else 0
                dpg.set_value("Scan_Message", f"time left: {self.format_time(estimated_time_left)}")

        # back to start position
        for i in self.positioner.channels:
            self.positioner.MoveABSOLUTE(i, self.initial_scan_Location[i])
            res = self.readInpos(i)
            self.positioner.GetPosition()
            print(f"ch{i}: in position = {res}, position = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        fn = self.save_scan_data(Nx, Ny, Nz, self.create_scan_file_name(local=False))  # 333
        self.writeParametersToXML(fn + ".xml")

        end_time = time.time()
        print(f"end_time: {end_time}")
        elapsed_time = end_time - start_time
        print(f"number of points ={N[0] * N[1] * N[2]}")
        print(f"Elapsed time: {elapsed_time} seconds")

        if not (self.stopScan):
            self.btnStop()

    def prepare_scan_data(self, max_position_x_scan, min_position_x_scan, start_pos):
        # Create object to be saved in excel
        self.scan_Out = []
        # probably unit issue
        x_vec = np.linspace(min_position_x_scan, max_position_x_scan, np.size(self.scan_intensities, 0), endpoint=False)
        y_vec = np.linspace(start_pos[1], start_pos[1] + self.L_scan[1] * 1e3, np.size(self.scan_intensities, 1), endpoint=False)
        z_vec = np.linspace(start_pos[2], start_pos[2] + self.L_scan[2] * 1e3, np.size(self.scan_intensities, 2), endpoint=False)
        for i in range(np.size(self.scan_intensities, 2)):
            for j in range(np.size(self.scan_intensities, 1)):
                for k in range(np.size(self.scan_intensities, 0)):
                    x = x_vec[k]
                    y = y_vec[j]
                    z = z_vec[i]
                    I = self.scan_intensities[k, j, i]
                    self.scan_Out.append([x, y, z, I, x, y, z])

    def OpenDialog(self, filetypes=None):  # move to common
        if filetypes is None:
            filetypes = [("All Files", "*.*")]
        root = tk.Tk()  # Create the root window
        root.withdraw()  # Hide the main window
        file_path = filedialog.askopenfilename(filetypes=filetypes)  # Open a file dialog

        if file_path:  # Check if a file was selected
            print(f"Selected file: {file_path}")  # add to logger
        else:
            print("No file selected")  # add to logger

        root.destroy()  # Close the main window if your application has finished using it

        return file_path

    def btnUpdateImages(self):
        self.Plot_Loaded_Scan(use_fast_rgb=True)

    def Plot_data(self, data, bLoad=False):
        np_array = np.array(data)
        # Nx = int(np_array[1,10])
        # Ny = int(np_array[1,11])
        # Nz = int(np_array[1,12])
        allPoints = np_array[0:, 3]
        self.Xv = np_array[0:, 4].astype(float) / 1e6
        self.Yv = np_array[0:, 5].astype(float) / 1e6
        self.Zv = np_array[0:, 6].astype(float) / 1e6

        allPoints = allPoints.astype(float)  # intensities
        Nx = int(round((self.Xv[-1] - self.Xv[0]) / (self.Xv[1] - self.Xv[0])) + 1)
        if self.Yv[Nx] - self.Yv[0] == 0:
            if bLoad:
                dpg.set_value("Scan_Message", "Stopped in the middle of a frame")
                Nx, allPoints = self.attempt_to_display_unfinished_frame(allPoints=allPoints)
            else:
                return 0  # Running mode

        Ny = int(round((self.Yv[-1] - self.Yv[0]) / (self.Yv[Nx] - self.Yv[0])) + 1)  # 777
        if Nx * Ny < len(self.Zv) and self.Zv[Ny * Nx] - self.Zv[0] > 0:  # Z[Ny*Nx]-Z[0] > 0:
            Nz = int(round((self.Zv[-1] - self.Zv[0]) / (self.Zv[Ny * Nx] - self.Zv[0])) + 1)
            res = np.reshape(allPoints, (Nz, Ny, Nx))
            dpg.set_value("Scan_Message", f"Number of Z slices is {Nz}")
        else:
            Nz = 1
            res = np.reshape(allPoints[0:Nx * Ny], (Nz, Ny, Nx))
            dpg.set_value("Scan_Message", f"Number of Z slices is {Nz}")

        self.scan_data = res

        self.Xv = self.Xv[0:Nx]
        self.Yv = self.Yv[0:Nx * Ny:Nx]
        self.Zv = self.Zv[0:-1:Nx * Ny]
        # xy
        self.startLoc = [int(np_array[1, 4].astype(float) / 1e6), int(np_array[1, 5].astype(float) / 1e6),
                         int(np_array[1, 6].astype(float) / 1e6)]  # um
        self.endLoc = [int(np_array[-1, 4].astype(float) / 1e6), int(np_array[-1, 5].astype(float) / 1e6),
                       int(np_array[-1, 6].astype(float) / 1e6)]  # um

        # todo align image (camera) with xy grap (scan output)

        if bLoad:
            self.Plot_Loaded_Scan(use_fast_rgb=True)  ### HERE
            print("Done.")
        else:
            self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=np.flipud(res[0, :, :]), startLoc=self.startLoc, endLoc=self.endLoc, switchAxes=bLoad)

    def attempt_to_display_unfinished_frame(self, allPoints):
        # Check and remove incomplete repetition if needed
        self.Xv, self.Yv, self.Zv, allPoints, Nx = self.check_last_period(self.Xv, self.Yv, self.Zv, allPoints)
        return Nx, allPoints

    def check_last_period(self, x, y, z, allPoints):
        X_length = len(x)
        tolerance = 1e-10  # Set tolerance for floating point comparisons

        # Find the difference between the last two elements
        last_diff = x[-1] - x[-2]

        # Find the maximum value and its last occurrence using NumPy
        max_x = np.max(x)
        LastIdx = X_length - np.argmax(x[::-1] == max_x)  # Index of the last occurrence of max_x

        # Remove the incomplete section at the end based on LastIdx
        x_fixed = x[:LastIdx]
        y_fixed = y[:LastIdx]
        z_fixed = z[:LastIdx]
        allPoints_fixed = allPoints[:LastIdx]

        # Calculate the pattern length
        if len(x_fixed) > 1:
            pattern_length = int(np.ceil((x_fixed[-1] - x_fixed[0]) / last_diff) + 1)  # Round up
        else:
            pattern_length = 0  # Handle edge case where pattern cannot be calculated

        print(f'Pattern length: {pattern_length}')
        print(f'LastIdx: {LastIdx}')

        return x_fixed, y_fixed, z_fixed, allPoints_fixed, pattern_length

    def btnGetLoggedPoints(self):
        current_label = dpg.get_item_label("btnOPX_GetLoggedPoint")
        prefix = "mcs"
        num_of_logged_points = 0

        try:
            if current_label == "Get Log from MCS":
                dpg.set_item_label("btnOPX_GetLoggedPoint", "Logged from MCS")
                num_of_logged_points = len(self.positioner.LoggedPoints)
            elif current_label == "Logged from MCS":
                # pdb.set_trace()  # Insert a manual breakpoint
                if self.use_picomotor:
                    dpg.set_item_label("btnOPX_GetLoggedPoint", "Get Log from Pico")
                else:
                    dpg.set_item_label("btnOPX_GetLoggedPoint", "Get Log from MCS")
                return
            elif current_label == "Get Log from Pico":
                if hasattr(self, 'pico') and self.pico is not None:
                    dpg.set_item_label("btnOPX_GetLoggedPoint", "Logged from Pico")
                    prefix = "pico"
                    num_of_logged_points = len(self.pico.LoggedPoints)
                else:
                    # If Pico does not exist, maintain prefix as mcs
                    dpg.set_item_label("btnOPX_GetLoggedPoint", "Logged from MCS")
                    error_message = "Pico does not exist; defaulting to MCS."
                    print(error_message)
                    num_of_logged_points = len(self.positioner.LoggedPoints)
            elif current_label == "Logged from Pico":
                dpg.set_item_label("btnOPX_GetLoggedPoint", "Get Log from MCS")
                return

            if num_of_logged_points < 3:
                try:
                    with open("map_config.txt", "r") as file:
                        lines = file.readlines()
                        self.positioner.LoggedPoints = []
                        for line in lines:
                            if line.startswith(prefix + "LoggedPoint"):
                                coords = line.split(": ")[1].split(", ")
                                if len(coords) == 3:
                                    logged_point = (float(coords[0]), float(coords[1]), float(coords[2]))
                                    if prefix == "mcs":
                                        self.positioner.LoggedPoints.append(logged_point)
                                    else:
                                        self.pico.LoggedPoints.append(logged_point)
                except FileNotFoundError:
                    print("map_config.txt not found.")
                    dpg.set_value("Scan_Message", "Error: map_config.txt not found.")
                    return
                except Exception as e:
                    print(f"Error loading logged points: {e}")
                    error_message = "Error: Less than three points are logged. Please log more points."
                    print(error_message)
                    dpg.set_value("Scan_Message", error_message)

            print("Logged points loaded from " + prefix)
            if prefix == "mcs":
                self.map.ZCalibrationData = np.array(self.positioner.LoggedPoints[:3])
            else:
                self.map.ZCalibrationData = np.array(self.pico.LoggedPoints[:3])

            self.to_xml()
            dpg.set_value("Scan_Message", "Logged points loaded from " + prefix)
            print(self.map.ZCalibrationData)

        except Exception as e:
            print(f"Unexpected error while getting log points: {e}")
            traceback.print_exc()  # This will print the full traceback
            dpg.set_value("Scan_Message", "An unexpected error occurred.")

    def btnLoadScan(self):
        # Open the dialog with a filter for .csv files and all file types
        fn = self.OpenDialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])  # Show .csv and all file types
        if fn:  # Check if a file is selected
            data = self.loadFromCSV(fn)
            self.idx_scan = [0, 0, 0]
            self.Plot_data(data, True)

    def save_scan_data(self, Nx, Ny, Nz, fileName=None):
        if fileName == None:
            fileName = self.create_scan_file_name()

        # parameters + note --- cause crash during scan. no need to update every slice.
        # self.writeParametersToXML(fileName + ".xml")

        # raw data
        Scan_array = np.array(self.scan_Out)
        RawData_to_save = {'X': Scan_array[:, 0].tolist(), 'Y': Scan_array[:, 1].tolist(), 'Z': Scan_array[:, 2].tolist(),
            'Intensity': Scan_array[:, 3].tolist(), 'Xexpected': Scan_array[:, 4].tolist(), 'Yexpected': Scan_array[:, 5].tolist(),
            'Zexpected': Scan_array[:, 6].tolist(), }

        self.saveToCSV(fileName + ".csv", RawData_to_save)

        if self.stopScan != True:
            # prepare image for plot
            self.Scan_intensity = Scan_array[:, 3]
            # self.Scan_matrix = np.reshape(self.Scan_intensity,
            #                               (len(self.V_scan[2]), len(self.V_scan[1]), len(self.V_scan[0])))
            self.Scan_matrix = np.reshape(self.scan_intensities, (Nz, Ny, Nx))  # shai 30-7-24
            # Nz = int(len(self.V_scan[2]) / 2)
            slice2D = self.Scan_matrix[int(Nz / 2), :, :]  # ~ middle layer
            self.Save_2D_matrix2IMG(slice2D)

            # Convert the NumPy array to an image
            image = Image.fromarray(slice2D.astype(np.uint8))
            self.image_path = fileName + ".jpg"  # Save the image to a file
            image.save(self.image_path)

            self.scan_data = self.Scan_matrix
            self.idx_scan = [Nz-1, 0, 0]

            self.startLoc = [Scan_array[1, 4] / 1e6, Scan_array[1, 5] / 1e6, Scan_array[1, 6] / 1e6]
            if Nz == 0:
                self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3, self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3, 0]
            else:
                self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3, self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3,
                               self.startLoc[2] + self.dL_scan[2] * (Nz - 1) / 1e3]

            # self.Plot_Scan()

        return fileName

    def create_scan_file_name(self, local=False):
        # file name
        timeStamp = self.getCurrentTimeStamp()  # get current time stamp
        if local:
            folder_path = "C:/temp/TempScanData/"
        else:
            folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/scan/'
        if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
            os.makedirs(folder_path)
        fileName = os.path.join(folder_path, timeStamp + "scan_" + self.expNotes)
        return fileName

    def move_single_step(self, ch, step):
        self.positioner.MoveRelative(ch, step)
        res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = self.positioner.AxesPosUnits[ch]
        self.absPos = self.positioner.AxesPositions[ch]
        print(f"ch{ch}: in position = {res}, position = {self.absPos} [{self.absPosunits}]")

    def readInpos(self, ch):
        res = self.positioner.ReadIsInPosition(ch)
        while not (res):
            res = self.positioner.ReadIsInPosition(ch)
        return res

    def FindMaxSignal(self):
        self.track_numberOfPoints = self.N_tracking_search  # number of point to scan for each axis
        self.trackStep = 75000  # [pm], step size
        initialShift = int(self.trackStep * self.track_numberOfPoints / 2)
        # self.numberOfRefPoints = 1000

        self.track_X = []
        self.coordinate = []

        for ch in range(3):
            self.track_X = []
            self.coordinate = []

            if (ch == 2):
                self.trackStep = 2 * 75000  # [pm]
                initialShift = int(self.trackStep * self.track_numberOfPoints / 2)

            # goto start location
            self.positioner.MoveRelative(ch, -1 * initialShift)
            time.sleep(0.001)
            while not (self.positioner.ReadIsInPosition(ch)):
                time.sleep(0.001)
            print(f"is in position = {self.positioner.ReadIsInPosition(ch)}")
            self.positioner.GetPosition()
            self.absPosunits = self.positioner.AxesPosUnits[ch]
            self.absPos = self.positioner.AxesPositions[ch]

            self.GlobalFetchData()
            lastRef = self.tracking_ref
            last_iteration = self.iteration

            for i in range(self.track_numberOfPoints):
                # grab/fetch new data from stream
                time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.001)  # [sec]
                self.GlobalFetchData()
                while (last_iteration == self.iteration):  # wait for new data
                    time.sleep(0.01)  # according to OS priorities
                    self.GlobalFetchData()
                self.lock.acquire()
                lastRef = self.tracking_ref
                last_iteration = self.iteration
                self.lock.release()

                # Log data                
                self.coordinate.append(i * self.trackStep + self.absPos)  # Log axis position
                self.track_X.append(lastRef)  # Loa signal to array

                # move to next location (relative move)
                self.positioner.MoveRelative(ch, self.trackStep)
                res = self.positioner.ReadIsInPosition(ch)
                while not (res):
                    res = self.positioner.ReadIsInPosition(ch)  # print(f"i = {i}, ch = {ch}, is in position = {res}")

            print(f"x(ch={ch}): ", end="")
            for i in range(len(self.coordinate)):
                print(f", {self.coordinate[i]: .3f}", end="")
            print("")
            print(f"y(ch={ch}): ", end="")
            for i in range(len(self.track_X)):
                print(f", {self.track_X[i]: .3f}", end="")
            print("")

            # optional: fit to parabula
            # if False:
            #     coefficients = np.polyfit(self.coordinate, self.track_X, 2)
            #     a, b, c = coefficients
            #     maxPos_parabula = int(-b / (2 * a))
            #     print(f"ch = {ch}: a = {a}, b = {b}, c = {c}, maxPos_parabula={maxPos_parabula}")

            # find max signal
            maxPos = self.coordinate[self.track_X.index(max(self.track_X))]
            print(f"maxPos={maxPos}")

            # move to max signal position
            self.positioner.MoveABSOLUTE(ch, maxPos)

        # update new ref signal
        self.refSignal = max(self.track_X)
        print(f"new ref Signal = {self.refSignal}")

        # get new val for comparison
        time.sleep(self.tTrackingSignaIntegrationTime * 1e-3 + 0.001 + 0.1)  # [sec]
        self.GlobalFetchData()
        print(f"self.tracking_ref = {self.tracking_ref}")

        # shift back tp experiment sequence
        self.qm.set_io1_value(0)
        time.sleep(0.1)

    def FindMaxSignal_atto_positioner_and_scanner(self):
        """
        Find the peak intensity by optimizing offset voltages:
        - X and Y axes are controlled by the atto_scanner.
        - Z axis is controlled by the atto_positioner.
        """
        print('Start looking for peak intensity using FindMaxSignal2')

        # Move and read functions for mixed axes control
        def move_axes(channel: int, position: float):
            """
            Set offset voltage for the corresponding axis.
            """
            if channel in [0, 1]:  # X and Y axes: atto_scanner
                self.HW.atto_scanner.set_offset_voltage(channel, position)
            elif channel == 2:  # Z axis: atto_positioner
                self.HW.atto_positioner.set_control_fix_output_voltage(2, int(position))

        def get_positions():
            """
            Get current positions for all three axes.
            """
            x = self.HW.atto_scanner.get_offset_voltage(0)  # X axis
            y = self.HW.atto_scanner.get_offset_voltage(1)  # Y axis
            z = self.HW.atto_positioner.get_control_fix_output_voltage(2)  # Z axis
            return x, y, z

        # Initial guess: current position for all axes
        initial_guess = get_positions()

        # Bounds: [0, 40000] mV for all axes
        bounds = ((self.HW.atto_scanner.offset_voltage_min,self.HW.atto_scanner.offset_voltage_max),
                  (self.HW.atto_scanner.offset_voltage_min, self.HW.atto_scanner.offset_voltage_max),
                  (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max))

        # Call the generalized find_max_signal function
        x_opt, y_opt, z_opt, intensity = find_max_signal(
            move_abs_fn=move_axes,
            read_in_pos_fn=lambda ch: (time.sleep(30e-3), True)[1],  # Ensure move has settled
            get_positions_fn=get_positions,
            fetch_data_fn=self.GlobalFetchData,  # Function to fetch new data
            get_signal_fn=lambda: -self.counter_Signal[0] if self.exp == Experiment.COUNTER else -self.tracking_ref,
            # Signal to maximize
            bounds=bounds,
            method=OptimizerMethod.ADAM,
            initial_guess=initial_guess,
            max_iter=30,
            use_coarse_scan=True
        )

        # Reset the output state or finalize settings
        self.qm.set_io1_value(0)

        print(
            f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV, z={z_opt:.2f} mV with intensity={intensity:.4f}"
        )

    def FindMaxSignal_atto_positioner(self):

        print('Start looking for peak intensity using FindMaxSignal2')
        initial_position = [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in self.HW.atto_positioner.channels]

        bounds = ((self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
                  (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
                  (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max))

        # Now we call our generalized FindMaxSignal function with these parameters

        x_opt, y_opt, z_opt, intensity = find_max_signal(
            move_abs_fn= self.HW.atto_positioner.set_control_fix_output_voltage,
            read_in_pos_fn= lambda ch: (time.sleep(30e-3), True)[1],
            get_positions_fn=lambda: [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in self.HW.atto_positioner.channels],
            fetch_data_fn=self.GlobalFetchData,
            get_signal_fn=lambda: self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref,
            bounds=bounds,
            method=OptimizerMethod.DIRECTIONAL,
            initial_guess=initial_position,
            max_iter=30,
            use_coarse_scan= True
        )

        time.sleep(0.1)
        self.GlobalFetchData()

        self.refSignal = self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref
        print(f"new ref Signal = {self.refSignal}")

        self.qm.set_io1_value(0)
        time.sleep(0.1)

        print(
            f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV, z={z_opt:.2f} mV with intensity={intensity:.4f}")

    def MoveToPeakIntensity(self):
        print('Start looking for peak intensity')
        if self.bEnableSignalIntensityCorrection:
            if self.system_name == SystemType.ATTO.value:
                self.MAxSignalTh = threading.Thread(target=self.tracking_function)
            else:
                self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
            self.MAxSignalTh.start()

    def SearchPeakIntensity(self):
        if self.bEnableSignalIntensityCorrection:
            if (self.refSignal == 0) and (not (self.MAxSignalTh.is_alive())):
                self.refSignal = self.tracking_ref  # round(sum(self.Y_Last_ref) / len(self.Y_Last_ref))
            elif (self.refSignal * self.TrackingThreshold > self.tracking_ref) and (not (self.MAxSignalTh.is_alive())):
                self.qm.set_io1_value(1)  # shift to reference only
                if self.system_name == SystemType.ATTO.value:
                    self.MAxSignalTh = threading.Thread(target=self.tracking_function)
                else:
                    self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
                self.MAxSignalTh.start()
            elif (not (self.MAxSignalTh.is_alive())):
                self.refSignal = self.refSignal if self.refSignal > self.tracking_ref else self.tracking_ref

    def format_time(self, seconds):
        """
        Convert time from seconds to human-readable format.
        """
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        time_str = ""
        if days > 0:
            time_str += f"{int(days)} days, "
        if hours > 0:
            time_str += f"{int(hours)} hours, "
        if minutes > 0:
            time_str += f"{int(minutes)} minutes, "
        if seconds > 0 or time_str == "":
            time_str += f"{int(seconds)} seconds"

        return time_str

    def getCurrentTimeStamp(self):
        now = datetime.now()
        return str(now.year) + "_" + str(now.month) + "_" + str(now.day) + "_" + str(now.hour) + "_" + str(now.minute) + "_" + str(now.second)

    def saveExperimentsNotes(self, appdata, sender):
        # dpg.set_value("text item", f"Mouse Button ID: {app_data}")
        self.expNotes = sender
        self.HW.camera.imageNotes = sender

    def saveToCSV(self, file_name, data):
        print("Saving to CSV")
        # Find the length of the longest list

        max_length = max(len(values) for values in data.values())

        # Pad shorter lists with None  # I guess data was changed
        for key in data:
            while len(data[key]) < max_length:
                data[key].append(None)

        # Writing to CSV
        # todo: add protection try ...
        try:
            with open(file_name, mode='w', newline='') as file:
                writer = csv.writer(file)

                # Write titles
                writer.writerow(data.keys())

                # Write data
                writer.writerows(zip(*data.values()))
        except Exception as e:
            error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{error_time}] An error occurred while writing to the file '{file_name}'. Error: {e}")
            self.scanFN = self.create_scan_file_name(local=True)
            print(f"Changed save location to {self.scanFN}")

        print("Data has been saved to", file_name)

    def loadFromCSV(self, file_name):
        data = []
        with open(file_name, 'r', newline='') as file:
            reader = csv.reader(file)
            for row in reader:
                data.append(row)
        del data[0]
        return data

    def writeParametersToXML(self, fileName):
        self.to_xml(fileName)
        print("Parameters has been saved to", fileName)

    def to_xml(self, filename="OPX_params.xml"):
        root = ET.Element("Parameters")

        for key, value in self.__dict__.items():
            if isinstance(value, (int, float, str, bool)):
                param = ET.SubElement(root, key)
                param.text = str(value)
                if False:
                    print(str(key))

            elif isinstance(value, list):
                list_elem = ET.SubElement(root, key)
                if (list_elem.tag not in ["scan_Out","X_vec", "Y_vec", "Z_vec","X_vec_ref","Y_vec_ref","Z_vec_ref","V_scan","expected_pos","t_vec",
                                              "startLoc","endLoc","Xv","Yv","Zv","viewport_width","viewport_height","window_scale_factor",
                                              "timeStamp","counter","maintain_aspect_ratio","scan_intensities","initial_scan_Location","V_scan",
                                              "absPosunits","Scan_intensity","Scan_matrix","image_path","f_vec","signal","ref_signal","tracking_ref","t_vec","t_vec_ini"]
                        ):
                    for item in value:
                        item_elem = ET.SubElement(list_elem, "item")
                        item_elem.text = str(item)
                else:
                    1
            elif isinstance(value, (np.ndarray)):
                list_elem = ET.SubElement(root, key)
                if list_elem.tag == "ZCalibrationData":
                    for item in value:
                        item_elem = ET.SubElement(list_elem, "item")
                        for sub_item in item:
                            item_sub_elem = ET.SubElement(item_elem, "item")
                            item_sub_elem.text = str(sub_item)

        tree = ET.ElementTree(root)
        with open(filename, "wb") as f:
            tree.write(f)

    def update_from_xml(self, filename="OPX_params.xml"):
        try:
            tree = ET.parse(filename)
            root = tree.getroot()

            # Get only the properties of the class
            properties = vars(self).keys()

            for param in root:
                # Update only if the parameter is a property of the class
                if param.tag in properties:

                    if isinstance(getattr(self, param.tag), Union[list, np.ndarray]):
                        list_items = []
                        counter = 0
                        for item in param:
                            converted_item = self.convert_to_correct_type(attribute=param.tag, value=item.text, idx=counter)
                            list_items.append(converted_item)
                            counter += 1
                        setattr(self, param.tag, list_items if isinstance(getattr(self, param.tag), list) else np.array(list_items))
                    else:
                        # Convert text value from XML to appropriate type
                        value = self.convert_to_correct_type(param.tag, param.text)
                        setattr(self, param.tag, value)

        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))

    def convert_to_correct_type(self, attribute, value, idx='none'):
        # Get the type of the attribute
        attribute_type = type(getattr(self, attribute))

        if not (idx == 'none'):
            attribute_type = type(getattr(self, attribute)[idx])

        # Convert value to the appropriate type
        if attribute_type is int:
            return int(value)
        elif attribute_type is float:
            return float(value)
        elif attribute_type is bool:
            return value.lower() == 'true'
        else:
            return value

    def fast_rgb_convert(self, Array2D):
        # Mask for non-zero values
        mask_non_zero = Array2D > 0

        # Normalize non-zero values to stretch across the entire color scale
        normalized_array = np.zeros_like(Array2D, dtype=float)
        normalized_array[mask_non_zero] = Array2D[mask_non_zero] / Array2D[mask_non_zero].max()

        # Generate the RGB heatmap, ignoring zeros
        result_array_ = intensity_to_rgb_heatmap_normalized(normalized_array)

        # Add the alpha channel: 1 for non-zero values, 0 for zero values
        alpha_channel = mask_non_zero.astype(float)

        return np.dstack((result_array_, alpha_channel))

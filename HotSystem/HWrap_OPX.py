# ***************************************************************
#              --------- note ---------                         *
# this file was a workaround to make fast integration to OPX    *
# actually we need to split to OPX wrapper and OPX GUI          *
# ***************************************************************
import csv
import random
import pdb
import traceback
from datetime import datetime
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime
from enum import Enum
from typing import Union, Optional, Callable, List, Tuple

import dearpygui.dearpygui as dpg
import glfw
import matplotlib
import numpy as np
from PIL import Image
import tkinter as tk
import functools
from collections import Counter
from qm_saas import QmSaas, QoPVersion

from gevent.libev.corecext import callback
from matplotlib import pyplot as plt
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, while_, \
    assign, elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger, case_, switch_
from qm_saas import QmSaas, QoPVersion
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from qm.qua import update_frequency, frame_rotation_2pi, declare_stream, declare, program, for_, assign, elif_, if_, \
    IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_
from qualang_tools.results import fetching_tool
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, assign, \
    elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger, counting, Math, Cast, case_, \
    switch_, strict_timing_, declare_input_stream
from qualang_tools.results import progress_counter, fetching_tool
from functools import partial
from qualang_tools.units import unit

import SystemConfig as configs
from Common import WindowNames
from HW_GUI.GUI_map import Map
from HW_wrapper import HW_devices as hw_devices, smaractMCS2
from SystemConfig import SystemType
from Utils import OptimizerMethod, find_max_signal
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized, create_scan_vectors, loadFromCSV, \
    open_file_dialog, create_gaussian_vector,\
    open_file_dialog, create_gaussian_vector, create_counts_vector
import dearpygui.dearpygui as dpg
from PIL import Image
import subprocess
import shutil
import xml.etree.ElementTree as ET
import math
import SystemConfig as configs
from Utils import OptimizerMethod, find_max_signal
import JobTesting_OPX

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
    TIME_BIN_ENTANGLEMENT = 20
    PLE = 21 # Photoluminescence excitation
    EXTERNAL_FREQUENCY_SCAN = 22
    AWG_FP_SCAN = 23
    testCrap = 24
    RandomBenchmark = 25
    test_electron_spinPump = 1001
    test_electron_spinMeasure = 1002

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
        self.sum_counters_flag: bool = False
        self.csv_file: Optional[str] = None
        self.is_green = False
        self.ref_counts_handle = None
        self.mattise_frequency_offset: float = 0
        self.job = None
        self.qm = None
        self.Y_vec_ref = None
        self.X_vec_ref = None
        self.Z_vec = None

        self.n_pause = 1
        self.is_green = True
        self.times_by_measurement = []
        self.AWG_switch_thread = None
        self.current_awg_freq = 0
        self.awg_freq_list = []
        self.list_of_pulse_type = []
        self.times_of_signal = None
        self.counts_handle = None
        self.meas_idx_handle = None
        self.scan_intensities = None
        self.X_vec = None
        self.Y_vec = None
        self.Y_vec_2 = None
        self.Y_vec_aggregated: list[list[float]] = []
        self.scan_default_sleep_time: float = 5e-3
        self.initial_scan_Location: List[float] = []
        self.iteration: int = 0
        self.iteration_list = []
        self.tracking_function: Callable = None
        self.fMW_1 = 0
        self.limit = None
        self.verbose:bool = False
        self.window_tag = "OPX Window"
        self.plt_max1 = None
        self.plt_max = None
        self.max1 = None
        self.max = None
        self.plt_y = None
        self.plt_x = None
        self.statistics_pulse_type = None
        self.HW = hw_devices.HW_devices()
        self.system_name = self.HW.config.system_type.value
        self.mwModule = self.HW.microwave
        self.positioner = self.HW.positioner
        self.awg = self.HW.keysight_awg_device
        self.pico = self.HW.picomotor
        self.laser = self.HW.cobolt
        self.matisse = self.HW.matisse_device
        self.my_qua_jobs = []

        if (self.HW.config.system_type == configs.SystemType.FEMTO):
            self.ScanTrigger = 101  # IO2
            self.TrackingTrigger = 101  # IO1
        if (self.HW.config.system_type == configs.SystemType.HOT_SYSTEM):
            self.ScanTrigger = 1
            self.TrackingTrigger = 1
        if (self.HW.config.system_type == configs.SystemType.ATTO):
            print("Setting up parameters for the atto system")
            self.ScanTrigger = 1001  # IO2
            self.TrackingTrigger = 1001  # IO1
            if self.HW.atto_scanner:
                print("Setting up tracking function with atto scanner + positioner")
                self.tracking_function = self.FindMaxSignal_atto_positioner_and_scanner
            else:
                print("Setting up tracking function with atto positioner")
                self.tracking_function = self.FindMaxSignal_atto_positioner
        if (self.HW.config.system_type == configs.SystemType.DANIEL):
            self.ScanTrigger = 1001  # IO2
            self.TrackingTrigger = 1001  # IO1
        if (self.HW.config.system_type == configs.SystemType.ICE):
            self.ScanTrigger = 10001  # IO2
            self.TrackingTrigger = 10001  # IO1

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
        self.connect_to_QM_OPX = False

        self.mw_Pwr = -6.0  # [dBm]
        self.mw_freq = 2.597  # [GHz], base frequency. Both start freq for scan and base frequency
        self.mw_freq_2 = 2.60166 # [GHz]
        self.mw_freq_scan_range = 6  # [MHz]
        self.mw_df = float(0.1)  # [MHz]
        self.mw_freq_resonance = 2.60166  # [GHz]
        self.mw_2ndfreq_resonance = 2.60166 # [GHz]
        self.mw_P_amp = 0.69    # proportional amplitude
        self.mw_P_amp2 = 0.1   # proportional amplitude
        self.mw_P_amp3 = 0.1  # proportional amplitude

        self.n_avg = int(6)  # number of averages
        self.n_nuc_pump = 0  # number of times to try nuclear pumping
        self.AWG_f_1 = 150  # [GHz](?)
        self.AWG_f_2 = 150  # [GHz](?)
        self.AWG_interval = 1000  # [ns]
        self.T_bin = 28  # [ns]
        self.off_time = 1  # [ns] Can not be lower than 4
        self.n_of_awg_changes = 10

        self.n_avg = int(1000000)  # number of averages
        self.n_nuc_pump = 4  # number of times to try nuclear pumping
        self.n_CPMG = 1  # CPMG repeatetions
        self.N_p_amp = 20

        self.scan_t_start = 20  # [nsec], must above 16ns (4 cycle)
        self.scan_t_end = 1000  # [nsec]
        self.scan_t_dt = 8  # [nsec], must above 4ns (1 cycle)

        # self.MeasProcessTime = 300  # [nsec], time required for measure element to finish process
        self.MeasProcessTime = 458  # [nsec], time required for measure element to finish process (correct for counter program)
        self.Tpump = 500  # [nsec]
        self.MeasProcessTime = 300  # [nsec], time required for measure element to finish process
        self.Tpump = 300  # [nsec]
        self.Tcounter = 10000  # [nsec], for scan it is the single integration time
        self.TcounterPulsed = 300  # [nsec]
        self.total_integration_time = 100  # [msec]
        self.Tsettle = 300 # [nsec]
        self.t_mw = 232  # [nsec] # from rabi experiment
        self.t_mw2 = 2500  # [nsec] # from rabi experiment
        self.t_mw3 = 232  # [nsec] # from rabi experiment
        self.Tcounter -= self.MeasProcessTime  # [nsec], for scan it is the single integration time
        self.TcounterPulsed = 5000  # [nsec]
        self.total_integration_time:float = 5.0  # [msec]
        self.Tsettle = 2000 # [nsec]
        self.t_mw = 20  # [nsec] # from rabi experiment
        self.t_mw2 = 10  # [nsec] # from rabi experiment
        self.Tedge = 100 # [nsec]
        self.Twait = 20.0 # [usec]

        self.TRed = 1  # [nsec]
        self.TRedStatistics = 100  # [nsec]
        self.TwaitTimeBin = 16  # [nsec]
        self.TwaitTimeBinMeasure = 25 + 28  # [nsec]
        self.TwaitForBlinding = self.TwaitTimeBinMeasure + 22  # [nsec]

        self.OPX_rf_amp = 0.5  # [V], OPX max amplitude
        self.rf_Pwr = 0.5  # [V], requied OPX amplitude
        self.rf_proportional_pwr = self.rf_Pwr / self.OPX_rf_amp  # [1], multiply by wafeform to actually change amplitude
        self.rf_resonance_freq = 2.9898  # [MHz]
        self.rf_freq = 2.95  # [MHz]
        self.rf_freq_scan_range_gui = 100  # [kHz]
        self.rf_freq_scan_range = 0.1  # [MHz]
        self.rf_df = float(0.001)  # [MHz]
        self.rf_df_gui = float(1)  # [kHz]
        self.rf_pulse_time = 7800  # [nsec]

        self.waitForMW = 0.05  # [sec], time to wait till mw settled (slow ODMR)

        self.dN = 10
        self.back_freq = self.mw_2ndfreq_resonance
        self.n_measure = 6
        self.MW_dif = 3  # [MHz]
        self.Wait_time_benchmark = 10
        self.t_wait_benchmark = 0
        self.gate_number = 0

        # Graph parameters
        self.NumOfPoints = 1000  # to include in counter Graph
        self.reset_data_val()

        self.Xv = []
        self.Yv = []
        self.Zv = []

        self.StopFetch = True

        self.expNotes = "_"
        self.added_comments = None

        # load class parameters from XML
        self.update_from_xml()
        self.connect_to_QM_OPX = False
        self.benchmark_switch_flag = True
        self.benchmark_one_gate_only = True
        self.bScanChkbox = False

        self.chkbox_close_all_qm = True
        # self.bEnableSignalIntensityCorrection = False # tdo: remove after fixing intensity method

        dpg.set_frame_callback(1, self.load_pos)

        if simulation:
            print("OPX in simulation mode ***********************")
        else:
            try:
                # self.qmm = QuantumMachinesManager(self.HW.config.opx_ip, self.HW.config.opx_port)
                if self.connect_to_QM_OPX:
                    # Currently does not work
                    client = QmSaas(email="daniel@quantumtransistors.com", password="oNv9Uk4B6gL3")
                    self.instance = client.simulator(version = QoPVersion.v2_4_0)
                    self.instance.spawn()
                    self.qmm = QuantumMachinesManager(host=self.instance.host,
                                                     port=self.instance.port,
                                                     connection_headers=self.instance.default_connection_headers)
                else:
                    self.qmm = QuantumMachinesManager(host=self.HW.config.opx_ip, cluster_name=self.HW.config.opx_cluster,
                                                      timeout=60)  # in seconds
                    time.sleep(1)
                    self.close_qm_jobs()

            except Exception as e:
                print(f"Could not connect to OPX. Error: {e}.")

    def close_qm_jobs(self, fn="qua_jobs.txt"):
        with open(fn, 'r') as f:
            loaded_jobs = f.readlines()
            for line in loaded_jobs:
                qm_id, job_id = line.strip().split(',')
                try:
                    qm = self.qmm.get_qm(qm_id)
                    job = qm.get_job(job_id)
                    job.halt()
                    qm.close()
                except Exception as e:
                    print(f"Error at close_qm_jobs: {e}")

    def Calc_estimatedScanTime(self):
        N = np.ones(len(self.L_scan))
        for i in range(len(self.L_scan)):
            if self.b_Scan[i] == True:
                if self.dL_scan[i] > 0:
                    N[i] = self.L_scan[i] / self.dL_scan[i]
        self.estimatedScanTime = round(np.prod(N) * (self.singleStepTime_scan + self.total_integration_time / 1e3) / 60,
                                       1)

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
        print("Set total_integration_time to: " + str(sender.total_integration_time) + "msec")

    def toggle_sum_counters(self):
        self.sum_counters_flag = not self.sum_counters_flag
        print(f"Set counter sum flag to {self.sum_counters_flag}")

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
        print("Set mw_Pamp to: " + str(sender.mw_P_amp2))

    def Update_off_time(sender, app_data, user_data):
        sender.off_time = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_f1", value=sender.off_time)
        print("Set off_time to: " + str(sender.off_time))

    def Update_T_bin(sender, app_data, user_data):
        sender.T_bin = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_f1", value=sender.T_bin)
        print("Set T_bin to: " + str(sender.T_bin))

    def Update_AWG_interval(sender, app_data, user_data):
        sender.AWG_interval = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_f1", value=sender.AWG_interval)
        print("Set AWG_interval to: " + str(sender.AWG_interval))

    def Update_AWG_f_1(sender, app_data, user_data):
        sender.AWG_f_1 = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_f1", value=sender.AWG_f_1)
        print("Set AWG_f_1 to: " + str(sender.AWG_f_1))

    def Update_AWG_f_2(sender, app_data, user_data):
        sender.AWG_f_2 = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_f2", value=sender.AWG_f_2)
        print("Set AWG_f_2 to: " + str(sender.AWG_f_2))

    def Update_mwP_amp3(sender, app_data, user_data):
        sender.mw_P_amp3 = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inDbl_mwP_amp3", value=sender.mw_P_amp3)
        print("Set mw_Pamp3 to: " + str(sender.mw_P_amp3))

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

    def UpdateN_measure(sender, app_data, user_data):
        sender.n_measure = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_n_measure", value=sender.n_measure)
        print("Set n_measur to: " + str(sender.n_measure))

    def UpdateMW_dif(sender, app_data, user_data):
        sender.MW_dif = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_MW_dif", value=sender.MW_dif)
        print("Set MW_dif to: " + str(sender.MW_dif))

    def UpdatedN(sender, app_data, user_data):
        sender.dN = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="indN", value=sender.dN)
        print("Set dN to: " + str(sender.dN))

    def Update_back_freq(sender, app_data, user_data):
        sender.back_freq = (float(user_data))
        time.sleep(0.001)
        dpg.set_value(item="in_back_freq", value=sender.back_freq)
        print("Set back_freq to: " + str(sender.back_freq))

    def Update_gate_number(sender, app_data, user_data):
        sender.gate_number = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="ind_gate_number", value=sender.gate_number)
        print("Set gate_number to: " + str(sender.gate_number))

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

    def UpdateT_mw3(sender, app_data, user_data):
        sender.t_mw3 = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_t_mw3", value=sender.t_mw3)
        print("Set t_mw3 to: " + str(sender.t_mw3))

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

    def on_off_slider_callback(self, sender, app_data):
        # app_data is the new slider value (0 or 1)
        if app_data == 1:
            self.is_green = True
            dpg.configure_item(sender, format="GREEN")
            dpg.bind_item_theme(sender, "OnTheme")
            print("Laser is Green!")
        else:
            self.is_green = False
            dpg.configure_item(sender, format="RED")
            dpg.bind_item_theme(sender, "OffTheme")
            print("Laser is Red!")

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
        # Move to Common
        monitor = glfw.get_primary_monitor()  # Get the primary monitor
        mode = glfw.get_video_mode(monitor)  # Get the physical size of the monitor
        width, height = mode.size
        self.viewport_width = dpg.get_viewport_client_width()
        self.viewport_height = dpg.get_viewport_client_height()
        self.window_scale_factor = width / 3840

    def set_all_themes(self):
        with dpg.theme(tag="OnTheme"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (0, 200, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (0, 180, 0))  # handle when pressed
                # Optionally color the track:
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (50, 70, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (60, 80, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (70, 90, 70))

        # OFF Theme: keep the slider handle red in all states.
        with dpg.theme(tag="OffTheme"):
            with dpg.theme_component(dpg.mvSliderInt):
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrab, (200, 0, 0))  # idle handle color
                dpg.add_theme_color(dpg.mvThemeCol_SliderGrabActive, (180, 0, 0))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (70, 50, 50))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (80, 60, 60))
                dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (90, 70, 70))

    def controls(self, _width=1600, _Height=1000):
        self.GetWindowSize()
        pos = [int(self.viewport_width * 0.0), int(self.viewport_height * 0.4)]
        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.425)]
        self.set_all_themes()

        dpg.add_window(label=self.window_tag, tag=self.window_tag,no_title_bar=True, height=-1, width=-1,
                       pos=[int(pos[0]), int(pos[1])])
        dpg.add_group(tag="Graph_group", parent=self.window_tag, horizontal=True)
        dpg.add_plot(label="Graph", width=int(win_size[0]), height=int(win_size[1]), crosshairs=True, tag="graphXY",
                     parent="Graph_group")  # height=-1, width=-1,no_menus = False )
        dpg.add_plot_legend(parent="graphXY")  # optionally create legend
        dpg.add_plot_axis(dpg.mvXAxis, label="time", tag="x_axis", parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvYAxis, label="I [counts/sec]", tag="y_axis", invert=False,
                          parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_line_series(self.X_vec, self.Y_vec, label="counts", parent="y_axis", tag="series_counts")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref, label="counts_ref", parent="y_axis",
                            tag="series_counts_ref")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref2, label="counts_ref2", parent="y_axis",
                            tag="series_counts_ref2")
        dpg.add_line_series(self.X_vec_ref, self.Y_resCalculated, label="resCalculated", parent="y_axis",
                            tag="series_res_calcualted")

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
            with dpg.collapsing_header(label="Parameter Controls", tag="Parameter_Controls_Header",
                                       parent="Params_Controls", default_open=False):
                # Child window and group for integration controls
                with dpg.child_window(tag="child_Integration_Controls", horizontal_scrollbar=True, width=child_width,
                                      height=child_height):
                    with dpg.group(tag="Integration_Controls", horizontal=True):
                        dpg.add_text(default_value="Tcounter [nsec]", tag="text_integration_time")
                        dpg.add_input_int(label="", tag="inInt_Tcounter", width=item_width,
                                          callback=self.UpdateTcounter, default_value=self.Tcounter,
                                          min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="Tpump [nsec]", tag="text_Tpump")
                        dpg.add_input_int(label="", tag="inInt_Tpump", width=item_width, callback=self.UpdateTpump,
                                          default_value=self.Tpump, min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="TcounterPulsed [nsec]", tag="text_TcounterPulsed")
                        dpg.add_input_int(label="", tag="inInt_TcounterPulsed", width=item_width,
                                          callback=self.UpdateTcounterPulsed,
                                          default_value=self.TcounterPulsed, min_value=1, max_value=60000000, step=100)
                        dpg.add_text(default_value="Tsettle [nsec]", tag="text_measure_time")
                        dpg.add_input_int(label="", tag="inInt_Tsettle", width=item_width, callback=self.UpdateTsettle,
                                          default_value=self.Tsettle,
                                          min_value=1, max_value=60000000, step=1)
                        dpg.add_text(default_value="total integration time [msec]", tag="text_total_integration_time")
                        dpg.add_input_double(label="", tag="inDbl_total_integration_time", width=item_width, callback=self.UpdateCounterIntegrationTime, default_value=self.total_integration_time, min_value=1e-6, max_value=1000, step=1e-6)
                        dpg.add_text(default_value="Twait [usec]", tag="text_wait_time")
                        dpg.add_input_double(label="", tag="inDbl_wait_time", width=item_width,
                                             callback=self.UpdateWaitTime, default_value=self.Twait, min_value=0.001,
                                             max_value=10000000000, step=0.001, format="%.5f")
                        dpg.add_text(default_value="Tedge [nsec]", tag="text_edge_time")
                        dpg.add_input_int(label="", tag="inInt_edge_time", width=item_width,
                                          callback=self.UpdateEdgeTime, default_value=self.Tedge, min_value=1,
                                          max_value=1000, step=1)

                        dpg.add_text(default_value="Tprocess [nsec]", tag="text_process_time")
                        dpg.add_input_int(label="", tag="inInt_process_time", width=item_width, default_value=300,
                                          min_value=1, max_value=1000, step=1)

                dpg.add_child_window(label="", tag="child_Freq_Controls", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Freq_Controls", parent="child_Freq_Controls",
                              horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="MW res [GHz]", parent="Freq_Controls", tag="text_mwResonanceFreq",
                             indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwResonanceFreq", indent=-1, parent="Freq_Controls",
                                     format="%.9f", width=item_width, callback=self.Update_mwResonanceFreq,
                                     default_value=self.mw_freq_resonance, min_value=0.001, max_value=6, step=0.001)

                dpg.add_text(default_value="MW 2nd_res [GHz]", parent="Freq_Controls", tag="text_mw2ndResonanceFreq",
                             indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_2ndfreq_resonance", indent=-1, parent="Freq_Controls",
                                     format="%.9f",
                                     width=item_width, callback=self.Update_mw_2ndfreq_resonance,
                                     default_value=self.mw_2ndfreq_resonance,
                                     min_value=0.001, max_value=6, step=0.001)
                dpg.add_text(default_value="MW freq [GHz] (base)", parent="Freq_Controls", tag="text_mwFreq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwFreq", indent=-1, parent="Freq_Controls", format="%.9f",
                                     width=item_width,
                                     callback=self.Update_mwFreq, default_value=self.mw_freq, min_value=0.001,
                                     max_value=6, step=0.001)
                dpg.add_text(default_value="range [MHz]", parent="Freq_Controls", tag="text_mwScanRange", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwScanRange", indent=-1, parent="Freq_Controls",
                                     width=item_width,
                                     callback=self.UpdateScanRange, default_value=self.mw_freq_scan_range, min_value=1,
                                     max_value=400, step=1)
                dpg.add_text(default_value="df [MHz]", parent="Freq_Controls", tag="text_mw_df", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_df", indent=-1, parent="Freq_Controls", format="%.5f",
                                     width=item_width,
                                     callback=self.Update_df, default_value=self.mw_df, min_value=0.000001,
                                     max_value=500, step=0.1)
                dpg.add_text(default_value="Power [dBm]", parent="Freq_Controls", tag="text_mw_pwr", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mw_pwr", indent=-1, parent="Freq_Controls", width=item_width,
                                     callback=self.UpdateMWpwr,
                                     default_value=self.mw_Pwr, min_value=0.01, max_value=500, step=0.1)

                dpg.add_child_window(label="", tag="child_rf_Controls", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="rf_Controls", parent="child_rf_Controls", horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="RF resonance freq [MHz]", parent="rf_Controls",
                             tag="text_rf_resonance_Freq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_resonance_freq", indent=-1, parent="rf_Controls",
                                     format="%.9f", width=item_width,
                                     callback=self.Update_rf_resonance_Freq, default_value=self.rf_resonance_freq,
                                     min_value=0.001, max_value=6,
                                     step=0.001)

                dpg.add_text(default_value="RF freq [MHz]", parent="rf_Controls", tag="text_rf_Freq", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_freq", indent=-1, parent="rf_Controls", format="%.9f",
                                     width=item_width,
                                     callback=self.Update_rf_Freq, default_value=self.rf_freq, min_value=0.001,
                                     max_value=6, step=0.001)
                dpg.add_text(default_value="range [kHz]", parent="rf_Controls", tag="text_rfScanRange", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_ScanRange", indent=-1, parent="rf_Controls",
                                     width=item_width,
                                     callback=self.Update_rf_ScanRange, default_value=self.rf_freq_scan_range_gui,
                                     min_value=1, max_value=400, step=1)
                dpg.add_text(default_value="df [kHz]", parent="rf_Controls", tag="text_rf_df", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_df", indent=-1, parent="rf_Controls", format="%.5f",
                                     width=item_width,
                                     callback=self.Update_rf_df, default_value=self.rf_df_gui, min_value=0.00001,
                                     max_value=500, step=0.1)
                dpg.add_text(default_value="Power [V]", parent="rf_Controls", tag="text_rf_pwr", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_rf_pwr", indent=-1, parent="rf_Controls", width=item_width,
                                     callback=self.Update_rf_pwr,
                                     default_value=self.rf_Pwr, min_value=0.01, max_value=500, step=0.1)

                dpg.add_child_window(label="", tag="child_Time_Scan_Controls", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Time_Scan_Controls", parent="child_Time_Scan_Controls",
                              horizontal=True)  # , before="Graph_group")
                dpg.add_text(default_value="scan t start [ns]", parent="Time_Scan_Controls", tag="text_scan_time_start",
                             indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_start", indent=-1, parent="Time_Scan_Controls",
                                  width=item_width,
                                  callback=self.UpdateScanTstart, default_value=self.scan_t_start, min_value=0,
                                  max_value=50000, step=1)
                dpg.add_text(default_value="dt [ns]", parent="Time_Scan_Controls", tag="text_scan_time_dt", indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_dt", indent=-1, parent="Time_Scan_Controls",
                                  width=item_width,
                                  callback=self.UpdateScanT_dt, default_value=self.scan_t_dt, min_value=0,
                                  max_value=50000, step=1)
                dpg.add_text(default_value="t end [ns]", parent="Time_Scan_Controls", tag="text_scan_time_end",
                             indent=-1)
                dpg.add_input_int(label="", tag="inInt_scan_t_end", indent=-1, parent="Time_Scan_Controls",
                                  width=item_width,
                                  callback=self.UpdateScanTend, default_value=self.scan_t_end, min_value=0,
                                  max_value=50000, step=1)

                dpg.add_child_window(label="", tag="child_Time_delay_Controls", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Time_delay_Controls", parent="child_Time_delay_Controls",
                              horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="t_mw [ns]", parent="Time_delay_Controls", tag="text_t_mw", indent=-1)
                dpg.add_input_int(label="", tag="inInt_t_mw", indent=-1, parent="Time_delay_Controls", width=item_width,
                                  callback=self.UpdateT_mw, default_value=self.t_mw, min_value=0, max_value=50000,
                                  step=1)

                dpg.add_text(default_value="t_mw2 [ns]", parent="Time_delay_Controls", tag="text_t_mw2", indent=-1)
                dpg.add_input_int(label="", tag="inInt_t_mw2", indent=-1, parent="Time_delay_Controls",
                                  width=item_width, callback=self.UpdateT_mw2, default_value=self.t_mw2, min_value=0,
                                  max_value=50000, step=1)

                dpg.add_text(default_value="t_mw3 [ns]", parent="Time_delay_Controls", tag="text_t_mw3", indent=-1)
                dpg.add_input_int(label="", tag="inInt_t_mw3", indent=-1, parent="Time_delay_Controls",
                                  width=item_width, callback=self.UpdateT_mw3, default_value=self.t_mw3, min_value=0,
                                  max_value=50000, step=1)

                dpg.add_text(default_value="rf_pulse_time [ns]", parent="Time_delay_Controls", tag="text_rf_pulse_time", indent=-1)
                dpg.add_input_int(label="", tag="inInt_rf_pulse_time", indent=-1, parent="Time_delay_Controls", width=item_width, callback=self.Update_rf_pulse_time, default_value=self.rf_pulse_time, min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="GetTrackingSignalEveryTime [ns]", parent="Time_delay_Controls",
                             tag="text_GetTrackingSignalEveryTime", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_tGetTrackingSignalEveryTime", indent=-1,
                                     parent="Time_delay_Controls", format="%.3f",
                                     width=item_width, callback=self.Update_tGetTrackingSignalEveryTime,
                                     default_value=self.tGetTrackingSignalEveryTime, min_value=0.001, max_value=10,
                                     step=0.1)

                dpg.add_text(default_value="tTrackingSignaIntegrationTime [msec]", parent="Time_delay_Controls",
                             tag="text_tTrackingSignaIntegrationTime", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_tTrackingSignaIntegrationTime", indent=-1,
                                     parent="Time_delay_Controls", format="%.0f",
                                     width=item_width, callback=self.Update_tTrackingSignaIntegrationTime,
                                     default_value=self.tTrackingSignaIntegrationTime, min_value=1, max_value=500000,
                                     step=10.0)

                dpg.add_child_window(label="", tag="child_Repetitions_Controls", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Repetitions_Controls", parent="child_Repetitions_Controls",
                              horizontal=True)  # , before="Graph_group")

                dpg.add_text(default_value="N nuc pump", parent="Repetitions_Controls", tag="text_N_nuc_pump",
                             indent=-1)
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
                dpg.add_input_int(label="", tag="inInt_N_CPMG", indent=-1, parent="Repetitions_Controls",
                                  width=item_width,
                                  callback=self.UpdateN_CPMG, default_value=self.n_CPMG, min_value=0, max_value=50000,
                                  step=1)

                dpg.add_text(default_value="N avg", parent="Repetitions_Controls", tag="text_n_avg", indent=-1)
                dpg.add_input_int(label="", tag="inInt_n_avg", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateNavg,
                                  default_value=self.n_avg, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="TrackingThreshold", parent="Repetitions_Controls",
                             tag="text_TrackingThreshold", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_TrackingThreshold", indent=-1, parent="Repetitions_Controls",
                                     format="%.2f",
                                     width=item_width, callback=self.Update_TrackingThreshold,
                                     default_value=self.TrackingThreshold, min_value=0,
                                     max_value=1, step=0.01)
                dpg.add_text(default_value="N search (Itracking)", parent="Repetitions_Controls",
                             tag="text_N_tracking_search", indent=-1)
                dpg.add_input_int(label="", tag="inInt_N_tracking_search", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_tracking_search,
                                  default_value=self.N_tracking_search,
                                  min_value=0, max_value=50000, step=1)

                dpg.add_group(tag="MW_amplitudes", parent="Parameter_Controls_Header",
                              horizontal=True)  # , before="Graph_group")
                dpg.add_text(default_value="MW P_amp", parent="MW_amplitudes", tag="text_mwP_amp", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwP_amp", indent=-1, parent="MW_amplitudes", format="%.6f",
                                     width=item_width, callback=self.Update_mwP_amp, default_value=self.mw_P_amp,
                                     min_value=0.0, max_value=1.0, step=0.001)
                dpg.add_text(default_value="MW P_amp2", parent="MW_amplitudes", tag="text_mwP_amp2", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwP_amp2", indent=-1, parent="MW_amplitudes", format="%.6f",
                                     width=item_width, callback=self.Update_mwP_amp2, default_value=self.mw_P_amp2,
                                     min_value=0.0, max_value=1.0, step=0.001)
                dpg.add_text(default_value="MW P_amp3", parent="MW_amplitudes", tag="text_mwP_amp3", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_mwP_amp3", indent=-1, parent="MW_amplitudes", format="%.6f",
                                     width=item_width, callback=self.Update_mwP_amp3, default_value=self.mw_P_amp3,
                                     min_value=0.0, max_value=1.0, step=0.001)

                dpg.add_child_window(label="", tag="child_benchmark", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Benchmark_group", parent="child_benchmark",
                              horizontal=True)  # , before="Graph_group")
                dpg.add_text(default_value="N measure", parent="Benchmark_group", tag="text_n_measure", indent=-1)
                dpg.add_input_int(label="", tag="inInt_n_measure", indent=-1, parent="Benchmark_group",
                                  width=item_width, callback=self.UpdateN_measure,
                                  default_value=self.n_measure, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="MW_dif", parent="Benchmark_group", tag="text_MW_dif", indent=-1)
                dpg.add_input_int(label="", tag="inInt_MW_dif", indent=-1, parent="Benchmark_group",
                                  width=item_width, callback=self.UpdateMW_dif,
                                  default_value=self.MW_dif, min_value=0, max_value=50000, step=1)
                dpg.add_text(default_value="dN", parent="Benchmark_group", tag="dN_benchmark", indent=-1)
                dpg.add_input_int(label="", tag="indN", indent=-1, parent="Benchmark_group",
                                  width=item_width, callback=self.UpdatedN,
                                  default_value=self.dN, min_value=0, max_value=100, step=1)
                dpg.add_text(default_value="back freq [GHz]", parent="Benchmark_group", tag="back_freq_benchmark",
                             indent=-1)
                dpg.add_input_double(label="", tag="in_back_freq", indent=-1, parent="Benchmark_group",
                                     format="%.9f", width=item_width, callback=self.Update_back_freq,
                                     default_value=self.back_freq, min_value=0.001, max_value=6, step=0.001)
                dpg.add_text(default_value="gate_number", parent="Benchmark_group", tag="gate_number_benchmark", indent=-1)
                dpg.add_input_int(label="", tag="ind_gate_number", indent=-1, parent="Benchmark_group",
                                  width=item_width, callback=self.Update_gate_number,
                                  default_value=self.gate_number, min_value=0, max_value=9, step=1)

                dpg.add_child_window(label="", tag="child_Time_bin", parent="Parameter_Controls_Header",
                                     horizontal_scrollbar=True,
                                     width=child_width, height=child_height)
                dpg.add_group(tag="Time_bin_parameters", parent="child_Time_bin",
                              horizontal=True)  # , before="Graph_group")
                dpg.add_text(default_value="AWG_f_1", parent="Time_bin_parameters", tag="text_f_1", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_f1", indent=-1, parent="Time_bin_parameters", format="%.6f",
                                     width=item_width, callback=self.Update_AWG_f_1, default_value=self.AWG_f_1,
                                     min_value=0.0, max_value=55.0, step=0.1)
                dpg.add_text(default_value="AWG_f_2", parent="Time_bin_parameters", tag="text_f_2", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_f2", indent=-1, parent="Time_bin_parameters", format="%.6f",
                                     width=item_width, callback=self.Update_AWG_f_2, default_value=self.AWG_f_2,
                                     min_value=0.0, max_value=55.0, step=0.1)
                dpg.add_text(default_value="T_bin", parent="Time_bin_parameters", tag="T_bin", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_T_bin", indent=-1, parent="Time_bin_parameters",
                                     format="%.6f",
                                     width=item_width, callback=self.Update_T_bin, default_value=self.T_bin,
                                     min_value=16, max_value=28, step=1)
                dpg.add_text(default_value="off_time", parent="Time_bin_parameters", tag="off_time", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_off_time", indent=-1, parent="Time_bin_parameters",
                                     format="%.6f",
                                     width=item_width, callback=self.Update_off_time, default_value=self.off_time,
                                     min_value=0, max_value=4, step=1)
                dpg.add_text(default_value="AWG_interval", parent="Time_bin_parameters", tag="AWG_interval", indent=-1)
                dpg.add_input_double(label="", tag="inDbl_AWG_interval", indent=-1, parent="Time_bin_parameters",
                                     format="%.6f",
                                     width=item_width, callback=self.Update_AWG_interval,
                                     default_value=self.AWG_interval,
                                     min_value=0, max_value=10000, step=4)

                dpg.add_group(tag="chkbox_group", parent="Params_Controls", horizontal=True)
                dpg.add_checkbox(label="Intensity Correction", tag="chkbox_intensity_correction", parent="chkbox_group",
                                 callback=self.Update_Intensity_Tracking_state, indent=-1,
                                 default_value=self.bEnableSignalIntensityCorrection)
                dpg.add_checkbox(label="QUA shuffle", tag="chkbox_QUA_shuffle", parent="chkbox_group",
                                 callback=self.Update_QUA_Shuffle_state,
                                 indent=-1, default_value=self.bEnableShuffle)
                dpg.add_checkbox(label="QUA simulate", tag="chkbox_QUA_simulate", parent="chkbox_group",
                                 callback=self.Update_QUA_Simulate_state,
                                 indent=-1, default_value=self.bEnableSimulate)
                dpg.add_checkbox(label="Scan XYZ", tag="chkbox_scan", parent="chkbox_group", indent=-1,
                                 callback=self.Update_scan,
                                 default_value=self.bScanChkbox)
                dpg.add_checkbox(label="Close All QM", tag="chkbox_close_all_qm", parent="chkbox_group", indent=-1,
                                 callback=self.Update_close_all_qm,
                                 default_value=self.chkbox_close_all_qm)
                dpg.add_checkbox(label="Two Qubit Benchmark", tag="chkbox_no_gate_benchmark", parent="chkbox_group", indent=-1,
                                 callback=self.Update_benchmark_switch_flag,
                                 default_value=self.benchmark_switch_flag)
                dpg.add_checkbox(label="One Gate Only Benchmark", tag="chkbox_single_gate_benchmark", parent="chkbox_group", indent=-1,
                                 callback=self.Update_benchmark_one_gate_only,default_value=self.benchmark_one_gate_only)
                dpg.add_checkbox(label="Sum Counters", tag="chkbox_sum_counters", parent="chkbox_group",
                                 callback=self.toggle_sum_counters, indent=-1,
                                 default_value=self.sum_counters_flag)

                dpg.add_button(label="SavePos", parent="chkbox_group", callback=self.save_pos)
                dpg.add_button(label="LoadPos", parent="chkbox_group", callback=self.load_pos)

                dpg.add_slider_int(label="Laser Type",
                                   tag="on_off_slider", width = 80,
                                   default_value=1, parent="chkbox_group",
                                   min_value=0, max_value=1,
                                   callback=self.on_off_slider_callback,indent = -1,
                                   format="Green")

                dpg.add_group(tag="Buttons_Controls", parent="Graph_group",
                              horizontal=False)  # parent="Params_Controls",horizontal=False)
                _width = 300  # was 220
                dpg.add_button(label="Counter", parent="Buttons_Controls", tag="btnOPX_StartCounter",
                               callback=self.btnStartCounterLive, indent=-1, width=_width)
                dpg.add_button(label="ODMR_CW", parent="Buttons_Controls", tag="btnOPX_StartODMR",
                               callback=self.btnStartODMR_CW, indent=-1, width=_width)
                dpg.add_button(label="Start Pulsed ODMR", parent="Buttons_Controls", tag="btnOPX_StartPulsedODMR",
                               callback=self.btnStartPulsedODMR, indent=-1, width=_width)
                dpg.add_button(label="ODMR_Bfield", parent="Buttons_Controls", tag="btnOPX_StartODMR_Bfield", callback=self.btnStartODMR_Bfield, indent=-1, width=_width)
                dpg.add_button(label="Ext. Frequency Scan", parent="Buttons_Controls", tag="btnExternalFrequencyScan",
                               callback=self.btnStartExternalFrequencyScan,
                               indent=-1, width=_width)
                dpg.add_button(label="FP SCAN (AWG)", parent="Buttons_Controls", tag="btnAWG_FP_SCAN",
                               callback=self.btnStartAWG_FP_SCAN,
                               indent=-1, width=_width)
                dpg.add_button(label="RABI", parent="Buttons_Controls", tag="btnOPX_StartRABI", callback=self.btnStartRABI, indent=-1, width=_width)
                dpg.add_button(label="NuclearFastRot", parent="Buttons_Controls", tag="btnOPX_StartNuclearFastRot",
                               callback=self.btnStartNuclearFastRot, indent=-1, width=_width)
                dpg.add_button(label="PLE", parent="Buttons_Controls", tag="btnPLE", callback=self.btnStartPLE,
                               indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear RABI", parent="Buttons_Controls", tag="btnOPX_StartNuclearRABI",
                               callback=self.btnStartNuclearRABI, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear MR", parent="Buttons_Controls", tag="btnOPX_StartNuclearMR",
                               callback=self.btnStartNuclearMR,
                               indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear PolESR", parent="Buttons_Controls", tag="btnOPX_StartNuclearPolESR",
                               callback=self.btnStartNuclearPolESR, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear lifetime S0", parent="Buttons_Controls",
                               tag="btnOPX_StartNuclearLifetimeS0",
                               callback=self.btnStartNuclearSpinLifetimeS0, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear lifetime S1", parent="Buttons_Controls",
                               tag="btnOPX_StartNuclearLifetimeS1",
                               callback=self.btnStartNuclearSpinLifetimeS1, indent=-1, width=_width)
                dpg.add_button(label="Start Nuclear Ramsay", parent="Buttons_Controls", tag="btnOPX_StartNuclearRamsay",
                               callback=self.btnStartNuclearRamsay, indent=-1, width=_width)
                dpg.add_button(label="Start Hahn", parent="Buttons_Controls", tag="btnOPX_StartHahn",
                               callback=self.btnStartHahn, indent=-1,
                               width=_width)
                dpg.add_button(label="Start Electron Lifetime", parent="Buttons_Controls",
                               tag="btnOPX_StartElectronLifetime",
                               callback=self.btnStartElectronLifetime, indent=-1, width=_width)
                dpg.add_button(label="Start Electron Coherence", parent="Buttons_Controls",
                               tag="btnOPX_StartElectronCoherence",
                               callback=self.btnStartElectron_Coherence, indent=-1, width=_width)

                dpg.add_button(label="Start population gate tomography", parent="Buttons_Controls",
                               tag="btnOPX_PopulationGateTomography",
                               callback=self.btnStartPopulateGateTomography, indent=-1, width=_width)
                dpg.add_button(label="Start Entanglement state tomography", parent="Buttons_Controls",
                               tag="btnOPX_EntanglementStateTomography",
                               callback=self.btnStartStateTomography, indent=-1, width=_width)
                dpg.add_button(label="Start G2", parent="Buttons_Controls", tag="btnOPX_G2",
                               callback=self.btnStartG2, indent=-1, width=_width)
                dpg.add_button(label="Eilon's", parent="Buttons_Controls", tag="btnOPX_Eilons",
                               callback=self.btnStartEilons, indent=-1, width=_width)
                dpg.add_button(label="Random Benchmark", parent="Buttons_Controls", tag="btnOPX_RandomBenchmark",
                               callback=self.btnStartRandomBenchmark, indent=-1, width=_width)
                dpg.add_button(label="Start Time Bin Entanglement", parent="Buttons_Controls",
                               tag="btnOPX_StartTimeBinEntanglement",
                               callback=self.btnStartTimeBinEntanglement, indent=-1, width=_width)

                # save exp data
                dpg.add_group(tag="Save_Controls", parent="Parameter_Controls_Header", horizontal=True)
                dpg.add_input_text(label="", parent="Save_Controls", tag="inTxtOPX_expText", indent=-1,
                                   callback=self.saveExperimentsNotes)
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
            dpg.bind_item_theme("on_off_slider", "OnTheme")

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

            with dpg.window(label="Scan Window", tag="Scan_Window", no_title_bar=True, height=-1, width=1200,
                            pos=win_pos):
                with dpg.group(horizontal=True):
                    # Left side: Scan settings and controls
                    with dpg.group(tag="Scan_Range", horizontal=False):
                        with dpg.group(tag="Scan_Parameters", horizontal=False):
                            with dpg.group(tag="X_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bX_Scan", indent=-1,
                                                 callback=self.Update_bX_Scan,
                                                 default_value=self.b_Scan[0])
                                dpg.add_text(default_value="dx [nm]", tag="text_dx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dx_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dX_Scan,
                                                  default_value=self.dL_scan[0], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lx [nm]", tag="text_Lx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lx_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lx_Scan,
                                                  default_value=self.L_scan[0], min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Y_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bY_Scan", indent=-1,
                                                 callback=self.Update_bY_Scan,
                                                 default_value=self.b_Scan[1])
                                dpg.add_text(default_value="dy [nm]", tag="text_dy_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dy_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dY_Scan,
                                                  default_value=self.dL_scan[1], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Ly [nm]", tag="text_Ly_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Ly_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Ly_Scan,
                                                  default_value=self.L_scan[1], min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Z_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bZ_Scan", indent=-1,
                                                 callback=self.Update_bZ_Scan,
                                                 default_value=self.b_Scan[2])
                                dpg.add_text(default_value="dz [nm]", tag="text_dz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dZ_Scan,
                                                  default_value=self.dL_scan[2], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lz [nm]", tag="text_Lz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lz_Scan,
                                                  default_value=self.L_scan[2], min_value=0, max_value=500000, step=1)

                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label="Notes", tag="inTxtScan_expText", indent=-1, width=200,
                                                   callback=self.saveExperimentsNotes, default_value=self.expNotes)

                                dpg.add_text(default_value=f"~scan time: {self.format_time(scan_time_in_seconds)}",
                                             tag="text_expectedScanTime",
                                             indent=-1)

                            with dpg.group(horizontal=True):
                                dpg.add_text(label="Message: ", tag="Scan_Message")
                                dpg.add_checkbox(label="", tag="chkbox_Zcorrection", indent=-1,
                                                 callback=self.Update_bZcorrection,
                                                 default_value=self.b_Zcorrection)
                                dpg.add_text(default_value="Use Z Correction", tag="text_Zcorrection", indent=-1)

                            dpg.add_input_text(label="CMD", callback=self.execute_input_string, multiline=True,
                                               width=400, height=20)

                    with dpg.group(tag="start_Scan_btngroup", horizontal=False):
                        dpg.add_button(label="Start Scan", tag="btnOPX_StartScan", callback=self.btnStartScan,
                                       indent=-1, width=130)
                        dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")
                        dpg.add_button(label="Load Scan", tag="btnOPX_LoadScan", callback=self.btnLoadScan, indent=-1,
                                       width=130)
                        dpg.bind_item_theme(item="btnOPX_LoadScan", theme="btnGreenTheme")
                        dpg.add_button(label="Update images", tag="btnOPX_UpdateImages", callback=self.btnUpdateImages,
                                       indent=1, width=130)
                        dpg.bind_item_theme(item="btnOPX_UpdateImages", theme="btnGreenTheme")
                        dpg.add_button(label="Auto Focus", tag="btnOPX_AutoFocus", callback=self.btnAutoFocus,
                                       indent=-1, width=130)
                        dpg.bind_item_theme(item="btnOPX_AutoFocus", theme="btnYellowTheme")
                        dpg.add_button(label="Get Log from Pico", tag="btnOPX_GetLoggedPoint",
                                       callback=self.btnGetLoggedPoints, indent=-1, width=130)

                    with dpg.group(horizontal=False):
                        dpg.add_button(label="Updt from map", callback=self.update_from_map, width=130)
                        dpg.add_button(label="scan all markers", callback=self.scan_all_markers, width=130)
                        dpg.add_button(label="Z-calibrate", callback=self.btn_z_calibrate, width=130)
                        with dpg.group(horizontal=True):
                            dpg.add_button(label="plot", callback=self.plot_graph)
                            dpg.add_checkbox(label="use Pico", indent=-1, tag="checkbox_use_picomotor",
                                             callback=self.toggle_use_picomotor,
                                             default_value=self.use_picomotor)

                    _width = 200
                    with dpg.group(horizontal=False):
                        dpg.add_input_float(label="Step (um)", default_value=0.2, width=_width, tag="step_um",
                                            format='%.4f')
                        dpg.add_input_float(label="Z Span (um)", default_value=6.0, width=_width, tag="z_span_um",
                                            format='%.1f')
                        dpg.add_input_float(label="Laser Power (mW)", default_value=40.0, width=_width,
                                            tag="laser_power_mw", format='%.1f')
                        dpg.add_input_float(label="Int time (ms)", default_value=200.0, width=_width, tag="int_time_ms",
                                            format='%.1f')
                        dpg.add_input_float(label="X-Y span (um)", default_value=10.0, width=_width, tag="xy_span_um",
                                            format='%.4f')
                        dpg.add_input_float(label="Offset (nm)", default_value=1500.0, width=_width,
                                            tag="offset_from_focus_nm", format='%.1f')

                    self.btnGetLoggedPoints()  # get logged points
                    # self.map = Map(ZCalibrationData = self.ZCalibrationData, use_picomotor = self.use_picomotor)
                    self.map.create_map_gui(win_size, win_pos)  # dpg.set_frame_callback(1, self.load_pos)
        else:
            self.map.delete_map_gui()
            del self.map
            dpg.delete_item("Scan_Window")

    def save_pos(self):
        # Define the list of windows to check and save positions for
        window_names = [
            "pico_Win", "mcs_Win", "Zelux Window", "Wavemeter_Win", "HighlandT130_Win", "Matisse_Win",
            "OPX Window", "Map_window", "Scan_Window", "LaserWin", "Arduino_Win", "SIM960_Win"
        ]
        # Dictionary to store window positions, sizes, and collapsed states
        window_data = {}

        # Iterate through the list of window names and collect their positions and sizes if they exist
        for win_name in window_names:
            if dpg.does_item_exist(win_name):
                win_pos = dpg.get_item_pos(win_name)
                win_size = dpg.get_item_width(win_name), dpg.get_item_height(win_name)
                config = dpg.get_item_configuration(win_name)
                collapsed = config.get("collapsed", False)
                window_data[win_name] = (win_pos, win_size, collapsed)
                print(f"Position of {win_name}: {win_pos}, Size: {win_size}, Collapsed: {collapsed}")

        try:
            # Read existing map_config.txt content, if available
            try:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
            except FileNotFoundError:
                lines = []

            # Remove any existing entries for the windows
            new_content = [
                line for line in lines if not any(win_name in line for win_name in window_data.keys())
            ]

            # Append the new window positions, sizes, and collapsed states
            for win_name, (position, size, collapsed) in window_data.items():
                new_content.append(f"{win_name}_Pos: {position[0]}, {position[1]}\n")
                new_content.append(f"{win_name}_Size: {size[0]}, {size[1]}\n")
                new_content.append(f"{win_name}_Collapsed: {collapsed}\n")

            # Write back the updated content to the file
            with open("map_config.txt", "w") as file:
                file.writelines(new_content)

            print("Window positions, sizes, and collapsed states saved successfully to map_config.txt.")
        except Exception as e:
            print(f"Error saving window data: {e}")

    def load_pos(self):
        try:
            # Check if map_config.txt exists and read the contents
            if not os.path.exists("map_config.txt"):
                print("map_config.txt not found.")
                return

            # Dictionaries to store positions, sizes, and collapsed states
            window_positions = {}
            window_sizes = {}
            window_collapsed = {}

            with open("map_config.txt", "r") as file:
                lines = file.readlines()
                for line in lines:
                    # Split the line to get key and value
                    parts = line.split(": ")
                    if len(parts) != 2:
                        continue  # Skip lines that don't have the expected format

                    key = parts[0].strip()
                    value = parts[1].strip()

                    # Check if the key is a window position entry
                    if "_Pos" in key:
                        window_name = key.replace("_Pos", "")
                        x, y = value.split(", ")
                        window_positions[window_name] = (float(x), float(y))

                    # Check if the key is a window size entry
                    elif "_Size" in key:
                        window_name = key.replace("_Size", "")
                        width, height = value.split(", ")
                        window_sizes[window_name] = (int(width), int(height))

                    # Check if the key is a window collapsed entry
                    elif "_Collapsed" in key:
                        window_name = key.replace("_Collapsed", "")
                        window_collapsed[window_name] = value == "True"

            # Update window positions, sizes, and collapsed states in Dear PyGui if the windows exist
            for window_name, pos in window_positions.items():
                if dpg.does_item_exist(window_name):
                    dpg.set_item_pos(window_name, pos)
                    print(f"Loaded position for {window_name}: {pos}")
                else:
                    print(f"{window_name} does not exist in the current context.")

            for window_name, size in window_sizes.items():
                if dpg.does_item_exist(window_name):
                    dpg.set_item_width(window_name, size[0])
                    dpg.set_item_height(window_name, size[1])
                    print(f"Loaded size for {window_name}: {size}")
                else:
                    print(f"{window_name} does not exist in the current context.")

            for window_name, collapsed in window_collapsed.items():
                if dpg.does_item_exist(window_name):
                    dpg.configure_item(window_name, collapsed=collapsed)
                    print(f"Loaded collapsed state for {window_name}: {collapsed}")
                else:
                    print(f"{window_name} does not exist in the current context.")

        except Exception as e:
            print(f"Error loading window data: {e}")

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
            position[channel] = int(device.AxesPositions[channel] / device.StepsIn1mm * 1e3 * 1e6)  # [pm]
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
        self.map.toggle_use_picomotor(app_data=app_data, user_data=user_data)
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
            z_evaluation = float(
                calculate_z_series(self.map.ZCalibrationData, np.array([int(X_pos * 1e6)]), int(Y_pos * 1e6))) / 1e6

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
            dpg.set_value(item="text_expectedScanTime",
                          value=f"~scan time: {self.format_time(self.estimatedScanTime * 60)}")
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
                        self.pico.MoveABSOLUTE(ch + 1, int(
                            point[ch] * self.pico.StepsIn1mm / 1e6))  # Move absolute to start location
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
                for arr, result_array in zip([arrXY, arrXZ, arrYZ],
                                             [result_arrayXY_, result_arrayXZ_, result_arrayYZ_]):
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
            dpg.add_dynamic_texture(width=arrXY.shape[1], height=arrXY.shape[0], default_value=result_arrayXY_,
                                    tag="textureXY_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrXZ.shape[1], height=arrXZ.shape[0], default_value=result_arrayXZ_,
                                    tag="textureXZ_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrYZ.shape[1], height=arrYZ.shape[0], default_value=result_arrayYZ_,
                                    tag="textureYZ_tag",
                                    parent="texture_reg")

            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")

            # XY plot
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1],
                         equal_aspects=True, crosshairs=True,
                         query=True, callback=self.queryXY_callback)
            dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z=" + "{0:.2f}".format(self.Zv[self.idx_scan[Axis.Z.value]]),
                              parent="plotImaga")
            dpg.add_plot_axis(dpg.mvYAxis, label="y axis", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series("textureXY_tag", bounds_min=[self.startLoc[0], self.startLoc[1]],
                                 bounds_max=[self.endLoc[0], self.endLoc[1]],
                                 label="Scan data", parent="plotImaga_Y")
            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(arrXY),
                                   max_scale=np.max(arrXY),
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
                dpg.add_plot(parent="scan_group", tag="plotImagb", width=plot_size[0], height=plot_size[1],
                             equal_aspects=True, crosshairs=True,
                             query=True, callback=self.queryXZ_callback)
                dpg.add_plot_axis(dpg.mvXAxis,
                                  label="x (um), y=" + "{0:.2f}".format(self.Yv[self.idx_scan[Axis.Y.value]]),
                                  parent="plotImagb")
                dpg.add_plot_axis(dpg.mvYAxis, label="z (um)", parent="plotImagb", tag="plotImagb_Y")
                dpg.add_image_series(f"textureXZ_tag", bounds_min=[self.startLoc[0], self.startLoc[2]],
                                     bounds_max=[self.endLoc[0], self.endLoc[2]],
                                     label="Scan data", parent="plotImagb_Y")

                # YZ plot
                dpg.add_plot(parent="scan_group", tag="plotImagc", width=plot_size[0], height=plot_size[1],
                             equal_aspects=True, crosshairs=True,
                             query=True, callback=self.queryYZ_callback)
                dpg.add_plot_axis(dpg.mvXAxis,
                                  label="y (um), x=" + "{0:.2f}".format(self.Xv[self.idx_scan[Axis.X.value]]),
                                  parent="plotImagc")
                dpg.add_plot_axis(dpg.mvYAxis, label="z (um)", parent="plotImagc", tag="plotImagc_Y")
                dpg.add_image_series(f"textureYZ_tag", bounds_min=[self.startLoc[1], self.startLoc[2]],
                                     bounds_max=[self.endLoc[1], self.endLoc[2]],
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
                dpg.add_dynamic_texture(width=array_2d.shape[1], height=array_2d.shape[0], default_value=result_array_,
                                        tag="texture_tag",
                                        parent="texture_reg")
            else:
                dpg.add_dynamic_texture(width=array_2d.shape[0], height=array_2d.shape[1], default_value=result_array_,
                                        tag="texture_tag",
                                        parent="texture_reg")
        except Exception as e:
            print(f"Error adding dynamic texture: {e}")

        try:
            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1],
                         equal_aspects=True, crosshairs=True)
            dpg.add_plot_axis(dpg.mvXAxis, label="x axis [um]", parent="plotImaga")
            dpg.add_plot_axis(dpg.mvYAxis, label="y axis [um]", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series(f"texture_tag", bounds_min=[startLoc[0], startLoc[1]],
                                 bounds_max=[endLoc[0], endLoc[1]], label="Scan data",
                                 parent="plotImaga_Y")
            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(array_2d),
                                   max_scale=np.max(array_2d),
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
        dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=minI,
                               max_scale=Array2D.max(),
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

    def Update_benchmark_switch_flag(sender, app_data, user_data):
        sender.benchmark_switch_flag = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_no_gate_benchmark", value=sender.benchmark_switch_flag)
        print("Set chkbox_no_gate_benchmark to: " + str(sender.benchmark_switch_flag))

    def Update_benchmark_one_gate_only(sender, app_data, user_data):
        sender.benchmark_one_gate_only = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_single_gate_benchmark", value=sender.benchmark_one_gate_only)
        print("Set chkbox_single_gate_benchmark to: " + str(sender.benchmark_one_gate_only))

    def Update_bX_Scan(sender, app_data, user_data):
        sender.b_Scan[0] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bX_Scan", value=sender.b_Scan[0])
        print("Set b_Scan[0] to: " + str(sender.b_Scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

        sender.to_xml()

    def Update_bY_Scan(sender, app_data, user_data):
        sender.b_Scan[1] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bY_Scan", value=sender.b_Scan[1])
        print("Set bY_Scan to: " + str(sender.b_Scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_bZ_Scan(sender, app_data, user_data):
        sender.b_Scan[2] = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_bZ_Scan", value=sender.b_Scan[2])
        print("Set bZ_Scan to: " + str(sender.b_Scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dX_Scan(sender, app_data, user_data):
        sender.dL_scan[0] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dx_scan", value=sender.dL_scan[0])
        print("Set dx_scan to: " + str(sender.dL_scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Lx_Scan(sender, app_data, user_data):
        sender.L_scan[0] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Lx_scan", value=sender.L_scan[0])
        print("Set Lx_scan to: " + str(sender.L_scan[0]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dY_Scan(sender, app_data, user_data):
        sender.dL_scan[1] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dy_scan", value=sender.dL_scan[1])
        print("Set dy_scan to: " + str(sender.dL_scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Ly_Scan(sender, app_data, user_data):
        sender.L_scan[1] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Ly_scan", value=sender.L_scan[1])
        print("Set Ly_scan to: " + str(sender.L_scan[1]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_dZ_Scan(sender, app_data, user_data):
        sender.dL_scan[2] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_dz_scan", value=sender.dL_scan[2])
        print("Set dz_scan to: " + str(sender.dL_scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_Lz_Scan(sender, app_data, user_data):
        sender.L_scan[2] = (int(user_data))
        time.sleep(0.001)
        dpg.set_value(item="inInt_Lz_scan", value=sender.L_scan[2])
        print("Set Lz_scan to: " + str(sender.L_scan[2]))

        sender.Calc_estimatedScanTime()
        dpg.set_value(item="text_expectedScanTime",
                      value=f"~scan time: {sender.format_time(sender.estimatedScanTime * 60)}")

    def Update_bZcorrection(sender, app_data, user_data):
        sender.b_Zcorrection = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_Zcorrection", value=sender.b_Zcorrection)
        print("Set b_Zcorrection to: " + str(sender.b_Zcorrection))
        print(sender.ZCalibrationData)

    # gets values from gui using items tag
    def GetItemsVal(self, items_tag=[]):
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
        self.Y_vec_squared = []
        self.benchmark_number_order = []
        self.benchmark_reverse_number_order = []
        self.benchmark_number_order_first_iteration = []
        self.benchmark_number_order_first_iteration = []
        self.tracking_ref = 0
        self.refSignal = 0
        self.iteration = 0
        self.counter = -10

    def initQUA_gen(self, n_count=1, num_measurement_per_array=1):
        self.reset_data_val()
        if self.exp == Experiment.COUNTER:
            self.counter_QUA_PGM(n_count=int(n_count))
        if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
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
        if self.exp == Experiment.SCAN:  # ~ 35 msec per measurement for on average for larage scans
            self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count),
                                          num_measurement_per_array=int(num_measurement_per_array),
                                          triggerThreshold=self.ScanTrigger)
        if self.exp == Experiment.ODMR_Bfield:
            self.ODMR_Bfield_QUA_PGM()
        if self.exp == Experiment.Nuclear_Fast_Rot:
            self.NuclearFastRotation_QUA_PGM()
        if self.exp == Experiment.G2:
            self.g2_raw_QUA()
        if self.exp == Experiment.testCrap:
            self.Test_Crap_QUA_PGM()
        if self.exp == Experiment.RandomBenchmark:
            self.Random_Benchmark_QUA_PGM()
        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            self.time_bin_entanglement_QUA_PGM(execute_qua=True)
        if self.exp == Experiment.PLE:
            self.bEnableShuffle = False
            # self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count), num_measurement_per_array=int(num_measurement_per_array), triggerThreshold=self.ScanTrigger)
            self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count),
                                          num_measurement_per_array=int(num_measurement_per_array),
                                          triggerThreshold=self.ScanTrigger,
                                          play_element=configs.QUAConfigBase.Elements.RESONANT_LASER.value)
            # self.MeasureByTrigger_Track_QUA_PGM(num_bins_per_measurement=int(n_count), num_measurement_per_array=int(num_measurement_per_array),triggerThreshold=self.ScanTrigger)
            self.bEnableShuffle=False
            self.MeasurePLE_QUA_PGM(trigger_threshold=self.ScanTrigger)
        if self.exp == Experiment.AWG_FP_SCAN:
            self.Y_vec_aggregated = []
            self.awg_sync_counter_QUA_PGM()

    def QUA_execute(self, closeQM=False, quaPGM=None, QuaCFG=None):
        if QuaCFG == None:
            QuaCFG = self.quaCFG

        if self.bEnableSimulate:
            sourceFile = open('debug.py', 'w')
            print(generate_qua_script(self.quaPGM, QuaCFG), file=sourceFile)
            sourceFile.close()
            simulation_config = SimulationConfig(duration=48000)  # clock cycles
            job_sim = self.qmm.simulate(QuaCFG, self.quaPGM, simulation_config)
            # Simulate blocks python until the simulation is done
            waveform_report = job_sim.get_simulated_waveform_report()
            waveform_report.create_plot(plot=True, save_path="./")
            job_sim.get_simulated_samples().con1.plot()
            if self.connect_to_QM_OPX:
                self.instance.close()
            if self.exp == Experiment.RandomBenchmark:
                waveform_report = job_sim.get_simulated_waveform_report()
                waveform_report.create_plot(plot=True, save_path="./")
            if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
                # waveform_report = job_sim.get_simulated_waveform_report()
                # waveform_report.create_plot(plot=True, save_path="./")
                pass
            plt.show()

            return None, None
        else:
            if closeQM or self.chkbox_close_all_qm:
                self.chkbox_close_all_qm = False
                self.qmm.close_all_quantum_machines()

            if quaPGM is None:
                quaPGM = self.quaPGM

            list_before = self.qmm.list_open_qms()
            print(f"before open new job: {list_before}")

            qm = self.qmm.open_qm(config=QuaCFG, close_other_machines=closeQM)
            qm_id = qm.id
            job = qm.execute(quaPGM)
            job_id = job.id

            list_after = self.qmm.list_open_qms()
            print(f"after open new job: {list_after}")

            self.my_qua_jobs = []  # todo: optional so have more then one program open from same QMachine
            self.my_qua_jobs.append({"qm_id": qm_id, "job_id": job_id})
            # Save the jobs to a text file
            with open('qua_jobs.txt', 'w') as f:
                for _job in self.my_qua_jobs:
                    f.write(f"{_job['qm_id']},{_job['job_id']}\n")

            if self.connect_to_QM_OPX:
                self.instance.close()

            if self.connect_to_QM_OPX:
                self.instance.close()

            return qm, job

    def verify_insideQUA_FreqValues(self, freq, min=0, max=400):  # [MHz]
        if freq < min * self.u.MHz or freq > max * self.u.MHz:
            raise Exception('freq is out of range. verify base freq is up to 400 MHz relative to resonance')

    def GenVector(self, min, max, delta, asInt=False, N="none"):
        if N == "none":
            N = int((max - min) / delta + 1)
        vec1 = np.linspace(min, max, N, endpoint=True)
        if asInt:
            vec1 = vec1.astype(int)
        # vec2 = np.arange(min, max + delta/10, delta)
        return vec1

    '''
        array = array to shuffle (QUA variable)
        array_len = size of 'array' [int]
    '''

    def get_detector_input_type(self, detector_name: str) -> str:
        """
        Determines the input channel type (analog or digital) of a detector based on its configuration file.

        :param detector_name: The name of the detector (e.g., "Detector_OPD").
        :param config: The configuration dictionary containing all element configurations.
        :return: "analog" if the detector uses an analog channel, "digital" if it uses a digital channel,
                 or "unknown" if the type cannot be determined.
        """
        try:
            # Check if the detector uses a digital channel
            if "digitalOutputs" in detector_name:
                return "digital"
            else:
                return "analog"
        except Exception as e:
            print(f"An error has occurred in finding detector input type: {e}")

    def get_time_tagging_func(self, detector_name):
        """
        Return the appropriate time-tagging function (digital or analog)
        but do not call it yet.
        """
        input_type = self.get_detector_input_type(detector_name)
        dispatch_map = {
            "digital": time_tagging.digital,
            "analog": time_tagging.analog,
        }
        if input_type not in dispatch_map:
            raise ValueError(f"Unknown detector input type: {input_type}")

        return dispatch_map[input_type]

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
    def MW_and_reverse(self, p_mw, t_mw):
        play("xPulse" * amp(p_mw), "MW", duration=t_mw)
        play("-xPulse" * amp(p_mw), "MW", duration=t_mw)

    def QUA_Pump(self,t_pump,t_mw, t_rf, f_mw,f_rf, p_mw, p_rf,t_wait):
        align()

        # set frequencies to resonance
        update_frequency("MW", f_mw)
        update_frequency("RF", f_rf)

        #print(t_wait)
        # play MW
        #play("xPulse"* amp(p_mw), "MW", duration=t_mw // 4)
        self.MW_and_reverse(p_mw, (t_mw / 2) // 4)
        # play RF (@resonance freq & pulsed time)
        align("MW", "RF")
        play("const" * amp(p_rf), "RF", duration=t_rf // 4)
        # turn on laser to polarize
        align("RF", "Laser")
        play("Turn_ON", "Laser", duration=t_pump // 4)
        align()
        if t_wait>16:
            wait(t_wait//4)

    def QUA_PGM(self):#, exp_params, QUA_exp_sequence):
        if self.exp == Experiment.G2:
            self.g2_raw_QUA()
        else:
            with program() as self.quaPGM:
                self.n = declare(int)  # iteration variable
                self.n_st = declare_stream()  # stream iteration number
                self.n_st_2 = declare_stream()
                self.times = declare(int, size=100)
                self.times_ref = declare(int, size=100)

                self.f = declare(int)         # frequency variable which we change during scan - here f is according to calibration function
                self.t = declare(int)         # [cycles] time variable which we change during scan
                self.p = declare(fixed)       # [unit less] proportional amp factor which we change during scan

                self.m = declare(int)  # number of pumping iterations
                self.n_m = declare(int)           # Number of iteration inside a loop
                self.i_idx = declare(int)  # iteration variable
                self.j_idx = declare(int)  # iteration variable
                self.k_idx = declare(int)  # iteration variable

                self.site_state = declare(int)  # site preperation state
                self.m_state = declare(int)     # measure state

                self.simulation_random_integer = declare(int, size = 100)
                # assign(self.simulation_random_integer, self.random_int)

                self.counts_tmp = declare(int)  # temporary variable for number of counts
                self.counts_tmp2 = declare(int)  # temporary variable for number of counts
                self.counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
                self.counts_ref2_tmp = declare(int)  # 2nd temporary variable for number of counts reference
                self.total_counts = declare(int, value=0)

                self.runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
                self.track_idx = declare(int, value=0)  # iteration variable
                self.tracking_signal_tmp = declare(int)  # tracking temporary variable
                self.tracking_signal = declare(int, value=0)  # tracking variable
                self.tracking_signal_st = declare_stream()  # tracking stream variable
                self.sequenceState = declare(int, value=0)  # IO1 variable

                self.counts = declare(int, size=self.vectorLength)     # experiment signal (vector)
                self.counts_ref = declare(int, size=self.vectorLength) # reference signal (vector)
                self.counts_ref2 = declare(int, size=self.vectorLength) # reference signal (vector)
                self.resCalculated = declare(int, size=self.vectorLength) # normalized values vector

                # Shuffle parameters
                # self.val_vec_qua = declare(fixed, value=self.p_vec_ini)    # volts QUA vector
                # self.f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
                self.val_vec_qua = declare(int, value=np.array([int(i) for i in self.scan_param_vec]))  # volts QUA vector
                self.idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
                self.idx = declare(int)  # index variable to sweep over all indexes

                # stream parameters
                self.counts_st = declare_stream()      # experiment signal
                self.counts_ref_st = declare_stream()  # reference signal
                self.counts_ref2_st = declare_stream()  # reference signal
                self.resCalculated_st = declare_stream()  # reference signal
                self.total_counts_st = declare_stream()

                # if self.benchmark_switch_flag and self.exp == Experiment.RandomBenchmark:
                #     self.QUA_Pump(t_pump=self.tLaser, t_mw=self.tMW / 2, t_rf=self.tRF,
                #               f_mw=self.mw_freq * self.u.MHz,
                #               f_rf=self.rf_resonance_freq * self.u.MHz,
                #               p_mw=self.mw_P_amp, p_rf=self.rf_proportional_pwr, t_wait=self.t_wait_benchmark)
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
                        if self.exp == Experiment.RandomBenchmark:
                            save(self.total_counts, self.counts_st)
                            save(self.counts_ref[self.idx], self.counts_ref_st)
                            save(self.counts_ref2[self.idx], self.counts_ref2_st)
                            save(self.resCalculated[self.idx], self.resCalculated_st)
                        else:
                            with for_(self.idx, 0, self.idx < self.vectorLength,self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                                save(self.counts[self.idx], self.counts_st)
                                save(self.counts_ref[self.idx], self.counts_ref_st)
                                save(self.counts_ref2[self.idx], self.counts_ref2_st)
                                save(self.resCalculated[self.idx], self.resCalculated_st)

                    save(self.n, self.n_st)  # save number of iteration inside for_loop
                    save(self.tracking_signal, self.tracking_signal_st)  # save number of iteration inside for_loop

                with stream_processing():
                    if self.exp == Experiment.RandomBenchmark:
                        # self.counts_st.save_all("counts")
                        # self.n_st.save_all("iteration")
                        self.counts_st.save_all("counts")
                        self.n_st.save_all("iteration")
                    else:
                        self.counts_st.buffer(self.vectorLength).average().save("counts")
                        self.counts_ref_st.buffer(self.vectorLength).average().save("counts_ref")
                        self.counts_ref2_st.buffer(self.vectorLength).average().save("counts_ref2")
                        self.resCalculated_st.buffer(self.vectorLength).average().save("resCalculated")
                        self.n_st.save("iteration")
                        self.tracking_signal_st.save("tracking_ref")
            
        self.qm, self.job = self.QUA_execute()

    def QUA_PGM_No_Tracking(self):
        with program() as self.quaPGM:
            self.simulation_flag = declare(bool)
            assign(self.simulation_flag, self.simulation)

            self.n = declare(int)  # iteration variable
            self.n_st = declare_stream()  # stream iteration number
            self.times = declare(int, size=100)
            self.times2 = declare(int, size=100)
            self.times_ref = declare(int, size=100)

            self.r = declare(fixed)
            self.ln_to_int = declare(fixed)
            self.assign_input = declare(fixed, size = 10)

            self.f = declare(
                int)  # frequency variable which we change during scan - here f is according to calibration function
            self.t = declare(int)  # [cycles] time variable which we change during scan
            self.p = declare(fixed)  # [unit less] proportional amp factor which we change during scan

            self.m = declare(int)  # number of pumping iterations
            self.i_idx = declare(int)  # iteration variable
            self.j_idx = declare(int)  # iteration variable
            self.k_idx = declare(int)  # iteration variable
            self.offset = declare(int)  # variables used for iteration assignment
            self.pulse_type = declare(int)
            self.bool_condition = declare(bool)
            self.n_pause_qua = declare(int)

            self.site_state = declare(int)  # site preperation state
            self.m_state = declare(int)  # measure state

            self.counts_tmp = declare(int)  # temporary variable for number of counts
            self.counts_tmp2 = declare(int)  # temporary variable for number of counts
            self.counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
            self.counts_ref2_tmp = declare(int)  # 2nd temporary variable for number of counts reference

            self.runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            self.track_idx = declare(int, value=0)  # iteration variable
            self.tracking_signal_tmp = declare(int)  # tracking temporary variable
            self.tracking_signal = declare(int, value=0)  # tracking variable
            self.tracking_signal_st = declare_stream()  # tracking stream variable
            self.sequenceState = declare(int, value=0)  # IO1 variable

            self.counts = declare(int, size=self.vectorLength)  # experiment signal (vector)
            self.counts2 = declare(int, size=self.vectorLength)  # experiment signal (vector)
            self.resCalculated = declare(int, size=self.vectorLength)  # normalized values vector

            # Shuffle parameters
            # self.val_vec_qua = declare(fixed, value=self.p_vec_ini)    # volts QUA vector
            # self.f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            self.val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))  # volts QUA vector
            self.idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
            self.idx = declare(int)  # index variable to sweep over all indexes

            self.mod4 = declare(int)
            self.stat_pulse_type_qua = declare(fixed)
            self.tMWPiStat = declare(int)
            self.awg_freq_qua = declare(int)

            #Variables for output simulation
            self.time_of_distributed_simulation_value = declare(fixed)
            self.exp_a_simulated = declare(fixed)
            self.exp_b_simulated = declare(fixed)
            assign(self.exp_a_simulated, self.lower_simulation_bound)
            assign(self.exp_b_simulated, self.higher_simulation_bound)

            #Input stream
            #awg_freq_qua = declare_input_stream(fixed, name = 'awg_freq')

            # stream parameters
            self.counts_st = declare_stream()  # experiment signal
            self.times_st = declare_stream()  # times during experiment signal
            self.pulse_type_st = declare_stream()
            self.counts_st2 = declare_stream()  # experiment signal for the second detector
            self.counts_ref_st = declare_stream()  # reference signal
            self.counts_ref2_st = declare_stream()  # reference signal
            self.resCalculated_st = declare_stream()  # reference signal
            self.awg_st = declare_stream()

            # with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
            #     assign(self.counts_ref[self.idx], 0)
            self.n_avg = 30
            self.n_pause = 8
            assign(self.n_pause_qua, self.n_pause)
            assign(self.bool_condition, False)
            with for_(self.n, 0, self.n < self.n_avg, self.n + 1):  # AVG loop
                assign(self.mod4, ((self.n+1) & 3))
                # reset vectors
                with for_(self.idx, 0, self.idx < self.vectorLength, self.idx + 1):
                    assign(self.counts[self.idx], 0)  # shuffle - assign new val from randon index
                    assign(self.counts2[self.idx], 0)  # shuffle - assign new val from randon index
                    assign(self.times[self.idx], 0)  # shuffle - assign new val from randon index

                # shuffle index
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(self.idx_vec_qua,
                                     self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(self.idx, 0, self.idx < self.array_length, self.idx + 1):  # loop over scan vector
                    assign(self.sequenceState, IO1)
                    with if_(self.sequenceState == 0):
                        update_frequency("MW", self.f)
                        #assign(self.awg_freq_qua, self.current_awg_freq)
                        # # pi pulse type for statistics measurement (X ot Y)
                        # with if_(self.mod4 == 0):
                        #     # Group of 4
                        #     assign(self.pulse_type, 4)
                        # with if_(self.mod4 == 3):
                        #     # Group of 3
                        #     assign(self.pulse_type, 3)
                        # with if_(self.mod4 == 2):
                        #     # Group of 2
                        #     assign(self.pulse_type, 2)
                        # with if_(self.mod4 == 1):
                        #     # Group of 1
                        #     assign(self.pulse_type, 1)
                        with if_((self.n - (self.n//self.n_pause_qua) * self.n_pause_qua) == 0):
                            pause()
                            self.execute_QUA()
                        with else_():
                            self.execute_QUA()

                    with else_():
                        assign(self.tracking_signal, 0)
                        with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.analog(self.times_ref,
                                                                                              self.time_in_multiples_cycle_time(
                                                                                                  self.Tcounter),
                                                                                              self.tracking_signal_tmp))
                            assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                        align()

                # tracking signal
                with if_(self.runTracking):
                    assign(self.track_idx, self.track_idx + 1)  # step up tracking counter
                    with if_(self.track_idx > self.trackingNumRepeatition - 1):
                        assign(self.tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(self.idx, 0, self.idx < self.tTrackingIntegrationCycles, self.idx + 1):
                            play("Turn_ON", "Laser",
                                 duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.analog(self.times_ref,
                                                                                              self.time_in_multiples_cycle_time(
                                                                                                  self.Tcounter),
                                                                                              self.tracking_signal_tmp))
                            assign(self.tracking_signal, self.tracking_signal + self.tracking_signal_tmp)
                        assign(self.track_idx, 0)

                # stream
                with if_(self.sequenceState == 0):
                    with for_(self.idx, 0, self.idx < self.vectorLength,
                              self.idx + 1):  # in shuffle all elements need to be saved later to send to the stream
                        save(self.counts[self.idx], self.counts_st)
                        save(self.counts2[self.idx], self.counts_st2)
                    with for_(self.idx, 0, self.idx < self.counts[0], self.idx + 1):
                        save(self.times[self.idx], self.times_st)
                save(self.n, self.n_st)  # save number of iteration inside for_loop
                save(self.tracking_signal, self.tracking_signal_st)  # save number of iteration inside for_loop
                save(self.pulse_type, self.pulse_type_st)
                #save(self.awg_freq_qua,self.awg_st)

            with stream_processing():
                # It makes sense to use save instead of save_all since stream_processing work parallel to sequence
                self.n_st.save_all("iteration_list")
                self.times_st.save_all("times")
                self.counts_st.save_all("counts")
                self.counts_st2.save_all("statistics_counts")
                self.pulse_type_st.save_all("pulse_type")
                #self.awg_st.save_all("awg_freq")
                # self.times_st.histogram([[i, i + 1] for i in range(0, self.tMeasure)]).save("times_hist")
        if not self.simulation:
            self.qm, self.job = self.QUA_execute()
        elif self.simulation and self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            self.qm, self.job = self.QUA_execute()
        #self.change_AWG_freq(channel=1)
        #self.job.resume()

    def execute_QUA(self):
        if self.exp == Experiment.NUCLEAR_POL_ESR:
            self.Nuclear_Pol_ESR_QUA_PGM(Generate_QUA_sequance = True)
        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:
            self.Population_gate_tomography_QUA_PGM(Generate_QUA_sequance = True)
        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:
            self.Entanglement_gate_tomography_QUA_PGM(Generate_QUA_sequance = True)
        if self.exp == Experiment.testCrap:
            self.Test_Crap_QUA_PGM(Generate_QUA_sequance = True)
        # if self.exp == Experiment.RandomBenchmark:
        #     self.Random_Benchmark_QUA_PGM(Generate_QUA_sequance = True)

    def tile_to_length(self, array, final_length):
        """
        Return a 1D array of exactly 'final_length' by repeating 'array'
        as many times as needed (and possibly truncating the last repetition).
        """
        if final_length <= 0:
            # Return empty array if final_length is not positive
            return np.array([], dtype=array.dtype)

        array_len = len(array)
        # Number of complete repeats
        num_full_repeats = final_length // array_len
        # Remaining elements needed for the partial repeat
        remainder = final_length % array_len

        # Repeat fully num_full_repeats times, then take the first 'remainder' elements
        repeated = np.concatenate([
            np.tile(array, num_full_repeats),
            array[:remainder]
        ])

        return repeated

    # def play_random_qua_gate(self, N_vec, t_RF, amp_RF):
    #     with switch_(N_vec[self.n_m]):
    #         with case_(0):
    #             #Identity
    #             pass
    #         with case_(1):
    #             #X gate
    #             play("const" * amp(amp_RF), "RF", duration=(t_RF))
    #             assign(self.total_rf_wait, self.total_rf_wait + t_RF)
    #         with case_(2):
    #             #Y gate
    #             frame_rotation_2pi(0.25, "RF")
    #             play("const" * amp(amp_RF), "RF", duration=(2*t_RF))
    #             frame_rotation_2pi(1 - 0.25, "RF")
    #             assign(self.total_rf_wait, self.total_rf_wait + 2 * t_RF)
    #
    # def play_random_reverse_qua_gate(self, N_vec_reversed, t_RF, amp_RF):
    #     with switch_(N_vec_reversed[self.n_m]):
    #         with case_(0):
    #             #Identity
    #             pass
    #         with case_(1):
    #             #X gate
    #             play("const" * amp(amp_RF), "RF", duration=(t_RF))
    #             assign(self.total_rf_wait, self.total_rf_wait + t_RF)
    #         with case_(2):
    #             #Y gate
    #             frame_rotation_2pi(1 - 0.25, "RF")
    #             play("const" * amp(amp_RF), "RF", duration=(2*t_RF))
    #             frame_rotation_2pi(0.25, "RF")
    #             assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
    def play_random_qua_gate(self, N_vec, t_RF, amp_RF):
        # Both amp_RF and t_RF are python variables
        with switch_(N_vec[self.n_m]):
            with case_(0):
                # Identity
                pass
            with case_(1):
                # X +pi/2 gate
                # X(pi/2)
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(2):
                # Y +pi/2 gate
                # Z(-pi/2)X(pi/2)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(3):
                # Z +pi/2 gate
                # Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
            with case_(4):
                # X -pi/2 gate
                # X(-pi/2)
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(5):
                # Y -pi/2 gate
                # Z(-pi/2)X(-pi/2)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(6):
                # Z -pi/2 gate
                # Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
            with case_(7):
                # X +pi gate
                # X(pi)
                play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(8):
                # Y +pi gate
                # Z(-pi/2)X(pi)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(9):
                # Z pi gate
                # Z(pi)
                frame_rotation_2pi(0.5, "RF")
            with case_(10):
                # 0X+Y+Z pi gate
                # Z(pi)X(pi/2)
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(11):
                # +X0Y+Z pi gate
                # Z(pi/2)X(pi/2)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(12):
                # +X+Y0Z pi gate
                # Z(pi/4)X(pi)Z(-pi/4)
                frame_rotation_2pi(1 - 0.125, "RF")
                play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(0.125, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(13):
                # 0X+Y-Z pi gate
                # X(pi/2)Z(-pi)
                frame_rotation_2pi(1 - 0.5, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(14):
                # -X0Y+Z pi gate
                # Z(3pi/2)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.75, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(15):
                # +X-Y0Z pi gate
                # Z(-pi/4)X(pi)Z(pi/4)
                frame_rotation_2pi(0.125, "RF")
                play("const" * amp(amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(1 - 0.125, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(16):
                # +X+Y+Z +pi*2/3 gate
                # Z(pi/2)X(pi/2)Z(0)
                # frame_rotation_2pi(0.125, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(17):
                # +X+Y+Z -pi*2/3 gate
                # Z(0)X(-pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(18):
                # -X+Y+Z +pi*2/3 gate
                # Z(pi)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(19):
                # -X+Y+Z -pi*2/3 gate
                # Z(pi/2)X(-pi/2)Z(-pi)
                frame_rotation_2pi(1 - 0.5, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(20):
                # +X-Y+Z +pi*2/3 gate
                # Z(0)X(pi/2)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(21):
                # +X-Y+Z -pi*2/3 gate
                # Z(-pi/2)X(-pi/2)Z(0)
                # frame_rotation_2pi(0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(22):
                # +X+Y-Z +pi*2/3 gate
                # Z(0)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(23):
                # +X+Y-Z -pi*2/3 gate
                # Z(pi/2)X(-pi/2)Z(0)
                # frame_rotation_2pi(1-0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)

    def play_random_reverse_qua_gate(self, N_vec, t_RF, amp_RF):
        # Both amp_RF and t_RF are python variables
        with switch_(N_vec[self.n_m]):
            with case_(0):
                # Identity
                pass
            with case_(1):
                # X pi/2 gate
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(2):
                # Y pi/2 gate
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(3):
                # Z pi/2 gate
                frame_rotation_2pi(1 - 0.25, "RF")
            with case_(4):
                # X -pi/2 gate
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(5):
                # Y -pi/2 gate
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(6):
                # Z -pi/2 gate
                frame_rotation_2pi(0.25, "RF")
            with case_(7):
                # X +pi gate
                play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(8):
                # Y +pi gate
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(9):
                # Z pi gate
                frame_rotation_2pi(1 - 0.5, "RF")
            with case_(10):
                # 0X+Y+Z pi gate
                frame_rotation_2pi(1 - 0.5, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(11):
                # +X0Y+Z pi gate
                # Z(pi/2)X(pi/2)Z(pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(12):
                # +X+Y0Z pi gate
                # Z(pi/4)X(pi)Z(-pi/4)
                frame_rotation_2pi(0.125, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(1 - 0.125, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(13):
                # 0X+Y-Z pi gate
                # X(pi/2)Z(-pi)
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(14):
                # -X0Y+Z pi gate
                # Z(3pi/2)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.75, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(15):
                # +X-Y0Z pi gate
                # Z(-pi/4)X(pi)Z(pi/4)
                frame_rotation_2pi(0.125, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(2 * t_RF))
                frame_rotation_2pi(1 - 0.125, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + 2*t_RF)
            with case_(17):  # 16 & 17 are the inverse of each other
                # +X+Y+Z +pi*2/3 gate
                # Z(pi/2)X(pi/2)Z(0)
                # frame_rotation_2pi(0.125, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(16):
                # +X+Y+Z -pi*2/3 gate
                # Z(0)X(-pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(19):  # 18 & 19 are the inverse of each other
                # -X+Y+Z +pi*2/3 gate
                # Z(pi)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(18):
                # -X+Y+Z -pi*2/3 gate
                # Z(pi/2)X(-pi/2)Z(-pi)
                frame_rotation_2pi(1 - 0.5, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(21):  # 20 & 21 are the inverse of each other
                # +X-Y+Z +pi*2/3 gate
                # Z(0)X(pi/2)Z(pi/2)
                frame_rotation_2pi(0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(20):
                # +X-Y+Z -pi*2/3 gate
                # Z(-pi/2)X(-pi/2)Z(0)
                # frame_rotation_2pi(0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(1 - 0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(23):  # 22 & 23 are the inverse of each other
                # +X+Y-Z +pi*2/3 gate
                # Z(0)X(pi/2)Z(-pi/2)
                frame_rotation_2pi(1 - 0.25, "RF")
                play("const" * amp(amp_RF), "RF", duration=(t_RF))
                # frame_rotation_2pi(0.5, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)
            with case_(22):
                # +X+Y-Z -pi*2/3 gate
                # Z(pi/2)X(-pi/2)Z(0)
                # frame_rotation_2pi(1-0.25, "RF")
                play("const" * amp(-amp_RF), "RF", duration=(t_RF))
                frame_rotation_2pi(0.25, "RF")
                assign(self.total_rf_wait, self.total_rf_wait + t_RF)

    def play_random_qua_two_qubit_gate(self, N_vec, t_MW1, amp_MW1, t_MW2, amp_MW2, t_MW3, amp_MW3, f_mw1, f_mw2, back_freq, keep_phase = False):
        with switch_(N_vec[self.n_m]):
            with case_(0):
                # C_{n}NOT_{e}
                update_frequency("MW",f_mw1, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                assign(self.total_mw_wait,self.total_mw_wait + t_MW1)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(1):
                # IC_{n}NOT_{e}
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(2):
                # C_{n}H_{y_e}
                update_frequency("MW", f_mw1, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(3):
                # IC_{n}H_{y_e}
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(4):
                # C_{n}H_{x_e}
                update_frequency("MW", f_mw1, keep_phase = keep_phase)
                play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(5):
                # IC_{n}H_{x_e}
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(6):
                # Add to reference
                #HCH_{n}H_{y_e}
                update_frequency("MW", (f_mw1 + f_mw2)/2, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(7):
                #HCH_{n}IH_{y_e}
                update_frequency("MW", (f_mw1 + f_mw2)/2, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(8):
                #HCH_{n}H_{x_e}
                update_frequency("MW", (f_mw1 + f_mw2)/2, keep_phase = keep_phase)
                play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(9):
                #HCH_{n}IH_{x_e}
                update_frequency("MW", (f_mw1 + f_mw2)/2, keep_phase = keep_phase)
                play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)

    def play_random_reverse_qua_two_qubit_gate(self, N_vec, t_MW1, amp_MW1, t_MW2, amp_MW2, t_MW3, amp_MW3, f_mw1, f_mw2, back_freq, keep_phase = False):
        with switch_(N_vec[self.n_m]):
            with case_(0):
                update_frequency("MW", f_mw1, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(1):
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                play("xPulse" * amp(amp_MW1), "MW", duration=(t_MW1 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW1)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(2):
                update_frequency("MW", f_mw1, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(3):
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("xPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(4):
                update_frequency("MW", f_mw1, keep_phase = keep_phase)
                play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(5):
                update_frequency("MW", f_mw2, keep_phase = keep_phase)
                play("-yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                play("yPulse" * amp(amp_MW2), "MW", duration=(t_MW2 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW2)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(6):
                update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase = keep_phase)
                play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(7):
                update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase = keep_phase)
                play("xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("-xPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(8):
                update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase = keep_phase)
                play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)
            with case_(9):
                update_frequency("MW", (f_mw1 + f_mw2) / 2, keep_phase = keep_phase)
                play("yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                play("-yPulse" * amp(amp_MW3), "MW", duration=(t_MW3 / 2))
                assign(self.total_mw_wait, self.total_mw_wait + t_MW3)
                update_frequency("MW", back_freq, keep_phase=keep_phase)


    def benchmark_play_list_of_gates(self,N_vec, N_vec_reversed,n,idx):
        with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
            # Gates
            self.play_random_qua_gate(N_vec = N_vec, t_RF = self.tRF, amp_RF = self.rf_proportional_pwr)
        with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
            # Inverse Gates
            self.play_random_reverse_qua_gate(N_vec=N_vec_reversed, t_RF=self.tRF, amp_RF=-self.rf_proportional_pwr)

    def benchmark_play_list_of_two_qubit_gates(self, N_vec, N_vec_reversed, n, idx, keep_phase):
        with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
            self.play_random_qua_two_qubit_gate(N_vec = N_vec, t_MW1 = (self.t_mw / 2), amp_MW1 = self.mw_P_amp,
                                                t_MW2 = (self.t_mw2 / 2), amp_MW2 = self.mw_P_amp2, t_MW3 = (self.t_mw3 / 2),
                                                amp_MW3 = self.mw_P_amp3, f_mw1 = self.fMW_res, f_mw2 = self.fMW_2nd_res, back_freq =(self.fMW_res + self.fMW_2nd_res)/2, keep_phase = keep_phase)
        with for_(self.n_m, 0, self.n_m < idx, self.n_m + 1):
            self.play_random_reverse_qua_two_qubit_gate(N_vec = N_vec_reversed, t_MW1 = (self.t_mw / 2), amp_MW1 = self.mw_P_amp,
                                                        t_MW2 = (self.t_mw2 / 2), amp_MW2 = self.mw_P_amp2,
                                                        t_MW3 = (self.t_mw3 / 2), amp_MW3 = self.mw_P_amp3, f_mw1 = self.fMW_res,
                                                        f_mw2 = self.fMW_2nd_res, back_freq =(self.fMW_res + self.fMW_2nd_res)/2, keep_phase = keep_phase)


    def create_random_qua_vector(self, jdx, vec_size, max_rand, n):
        random_qua = Random()
        random_qua.set_seed(n)
        with for_(jdx, 0,jdx < vec_size, jdx+1):
            assign(self.idx_vec_ini_shaffle_qua[jdx], random_qua.rand_int(max_rand))
            save(self.idx_vec_ini_shaffle_qua[jdx], self.number_order_st)

    def create_non_random_qua_vector(self, jdx, vec_size, max_rand, n):
        assign(self.one_gate_only_values_qua, self.gate_number)
        with for_(jdx, 0,jdx < vec_size, jdx+1):
            assign(self.idx_vec_ini_shaffle_qua[jdx], self.one_gate_only_values_qua)
            save(self.idx_vec_ini_shaffle_qua[jdx], self.number_order_st)

    def generate_random_qua_integer_benchmark(self, rand_val, number_of_gates):
        """Generates a random integer from 0 to 23 in QUA"""
        assign(rand_val, Random().rand_int(number_of_gates))

    def reverse_qua_vector(self, idx, jdx):
        with for_(jdx, 0, jdx < idx, jdx + 1):
            with if_(jdx == 0):
                assign(self.idx_vec_ini_shaffle_qua_reversed[jdx], self.idx_vec_ini_shaffle_qua[idx - 1])
            with else_():
                assign(self.temp_idx, idx - jdx - 1)
                assign(self.idx_vec_ini_shaffle_qua_reversed[jdx],self.idx_vec_ini_shaffle_qua[self.temp_idx])


    def Random_Benchmark_QUA_PGM(self):
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        self.fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(self.fMW_res)
        fMW_res1 = self.fMW_res
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz
        self.verify_insideQUA_FreqValues(self.fMW_2nd_res)
        fMW_res2 = self.fMW_2nd_res

        if self.benchmark_switch_flag:
            number_of_gates = 10
        else:
            number_of_gates = 24

        self.tRF = self.rf_pulse_time //4
        Npump = self.n_nuc_pump

        # frequency scan vector
        f_min = 0 * self.u.MHz  # start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz  # end of freq sweep
        df = self.mw_df * self.u.MHz  # freq step
        self.f_vec = np.arange(f_min, f_max + df / 10, df)  # f_max + 0.1 so that f_max is included

        # time scan vector
        tScan_min = 0  # in [cycles]
        tScan_max = self.n_measure  # in [cycles]
        t_wait = self.time_in_multiples_cycle_time(self.Twait * 1000) //4
        # self.dN = 10  # in [cycles]
        self.t_vec = [i * 1 for i in range(tScan_min, tScan_max, self.dN)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + self.dN, self.dN)  # in [cycles]

        # length and idx vector
        array_length = self.n_measure
        # array_length = len(self.f_vec)                      # frquencies vector size
        gate_vector = np.arange(0,number_of_gates)
        idx_vec_ini = np.arange(0, array_length + 1, 1)  # indexes vector
        idx_vec_ini_shaffle = self.tile_to_length(gate_vector, array_length)
        #idx_vec_ini_shaffle = np.ones(self.n_measure)

        # tracking signal
        #tSequencePeriod = ((tMW + self.tRF + tPump) * Npump + 2 * tMW + self.tRF + tScan_max / 2 + tLaser) * array_length * 2
        tSequencePeriod = (2 * self.tRF * np.sum(self.t_vec) + np.size(self.t_vec) * ((tPump + self.tRF * 2 + self.t_mw) + self.t_mw2 + self.t_mw2 + tLaser)) * 3
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)
            self.reverse_rf_amp = declare(int)
            self.temp_idx = declare(int)
            self.one_gate_only_values_qua = declare(int)

            self.tRF_qua = declare(int)
            self.t_mw_qua = declare(int)
            assign(self.t_mw_qua, (self.t_mw / 2) // 4)
            self.t_mw_qua2 = declare(int)
            assign(self.t_mw_qua2, (self.t_mw2 / 2) // 4)

            f = declare(int)  # frequency variable which we change during scan
            t = declare(int)  # [cycles] time variable which we change during scan
            self.total_rf_wait = declare(int)
            self.total_mw_wait = declare(int)

            n = declare(int)  # iteration variable
            self.n_m = declare(int)
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_tmp_squared = declare(int)
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
            counts_loop_size = array_length // self.dN

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)
            counts_ref2 = declare(int, size=array_length)
            counts_square = declare(int, size=array_length)
            idx_counts_qua = declare(int)

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))  # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            self.idx_vec_ini_shaffle_qua = declare(int, value=idx_vec_ini_shaffle)
            self.idx_vec_ini_shaffle_qua_reversed = declare(int, value=idx_vec_ini_shaffle)
            # self.idx_vec_ini_shaffle_qua = declare(int, value=self.n_measure)
            # self.idx_vec_ini_shaffle_qua_reversed = declare(int, value=self.n_measure)
            idx = declare(int)  # index variable to sweep over all indexes
            jdx = declare(int)
            self.wait_ref = declare(int)

            # stream parameters
            counts_st = declare_stream()  # experiment signal
            counts_ref_st = declare_stream()  # reference signal
            counts_ref_st2 = declare_stream()  # reference signal
            self.number_order_st = declare_stream()
            self.reverse_number_order_st = declare_stream()
            counts_square_st = declare_stream()

            # set RF frequency to resonance
            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)
            p = self.rf_proportional_pwr  # p should be between 0 to 1

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < array_length, idx + self.dN):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts_ref2[idx], 0)
                    assign(counts_square[idx], 0)

                # Create random vector
                if self.benchmark_one_gate_only:
                    self.create_non_random_qua_vector(jdx = jdx, vec_size = array_length, max_rand = number_of_gates, n = n)
                else:
                    self.create_random_qua_vector(jdx = jdx, vec_size = array_length, max_rand = number_of_gates, n = n)

                # sequence
                with for_(idx, 0, idx < array_length, idx + self.dN):
                    assign(sequenceState, IO1)
                    assign(self.tRF_qua, (self.tRF))
                    #assign(self.wait_ref, (2 * self.tRF_qua * idx))
                    # Create reverse
                    self.reverse_qua_vector(idx = idx,jdx = jdx)
                    assign(self.total_rf_wait, 4)
                    assign(self.total_mw_wait, 4)
                    with if_(sequenceState == 0):
                        # signal
                        # polarize (@fMW_res @ fRF_res)
                        # play("Turn_ON", "Laser", duration=tPump // 4)
                        # align("Laser", "MW")
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", self.fMW_res)
                            # play MW
                            play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            #play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=self.tRF * 2)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                            wait(t_wait)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", self.fMW_2nd_res)
                        # play MW
                        #play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)

                        align("MW", "RF")
                        if self.benchmark_switch_flag:
                            play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                            align("RF", "MW")
                            wait(t_wait)
                            self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua, self.idx_vec_ini_shaffle_qua_reversed,n, idx, keep_phase = False)
                            align("MW","RF")
                            play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                        else:
                            self.benchmark_play_list_of_gates(self.idx_vec_ini_shaffle_qua, self.idx_vec_ini_shaffle_qua_reversed,n, idx)
                        #align("RF", "MW")
                        wait(t_wait)
                        # play Laser
                        align("RF", "MW")
                        # play("Turn_ON", "Laser", duration=tSettle // 4)
                        # align("Laser","MW")

                        # play MW
                        #play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # measure signal
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        assign(counts_tmp_squared, counts_tmp * counts_tmp)
                        assign(counts_square[idx_vec_qua[idx]], counts_square[idx_vec_qua[idx]] + counts_tmp_squared)
                        align()

                        # reference
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", self.fMW_res)
                            # play MW
                            play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=self.tRF * 2)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                            wait(t_wait)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", self.fMW_2nd_res)
                        # play MW
                        #play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)

                        with if_((idx == 0)):
                            pass
                        with else_():
                            if self.benchmark_switch_flag:
                                #Correct
                                #wait(self.total_mw_wait)
                                # Test run
                                play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                                align("RF", "MW")
                                wait(t_wait)
                                self.benchmark_play_list_of_two_qubit_gates(self.idx_vec_ini_shaffle_qua,
                                                                            self.idx_vec_ini_shaffle_qua_reversed, n,
                                                                            idx, keep_phase = True)
                                align("MW", "RF")
                                play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                            else:
                                wait(self.total_rf_wait)
                        wait(t_wait)
                        # play Laser
                        # align("RF", "Laser")
                        # play("Turn_ON", "Laser", duration=tSettle // 4)
                        # align("Laser","MW")

                        # play MW
                        #play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # measure signal
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference 2
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", self.fMW_res)
                            # play MW
                            play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            # play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            play("const" * amp(p), "RF", duration=self.tRF * 2)
                            # turn on laser to pump
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                            wait(t_wait)
                        align()

                        if not self.benchmark_switch_flag:
                            # set MW frequency to resonance
                            update_frequency("MW", self.fMW_2nd_res)
                            # play MW
                            # play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                            play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            align("MW","RF")

                        with if_((idx == 0)):
                            pass
                        with else_():
                            if self.benchmark_switch_flag:
                                #align("MW", "RF")
                                #wait(t_wait)
                                update_frequency("MW", self.fMW_2nd_res)
                                play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(self.t_mw2 / 2))
                                play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(self.t_mw2 / 2))
                                wait(self.total_mw_wait)
                                play("-xPulse" * amp(self.mw_P_amp2), "MW", duration=(self.t_mw2 / 2))
                                play("xPulse" * amp(self.mw_P_amp2), "MW", duration=(self.t_mw2 / 2))
                                #align("RF", "MW")
                            else:
                                play("const" * amp(self.rf_proportional_pwr), "RF", duration=self.tRF)
                                wait(self.total_rf_wait)
                                play("const" * amp(-self.rf_proportional_pwr), "RF", duration=self.tRF)
                                align("RF","MW")
                        wait(t_wait)
                        # play Laser
                        # align("RF", "Laser")
                        # play("Turn_ON", "Laser", duration=tSettle // 4)
                        # align("Laser","MW")

                        # play MW
                        # play("xPulse" * amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        if not self.benchmark_switch_flag:
                            play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                            play("-xPulse" * amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # measure signal
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts_ref2[idx_vec_qua[idx]], counts_ref2[idx_vec_qua[idx]] + counts_tmp)
                        align()

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        align()

                    with if_(idx == array_length - 1):
                        with for_(jdx, 0, jdx < idx, jdx + 1):
                            save(self.idx_vec_ini_shaffle_qua_reversed[jdx], self.reverse_number_order_st)

                # tracking signal
                with if_(runTracking):
                    assign(track_idx, track_idx + 1)  # step up tracking counter
                    with if_(track_idx > trackingNumRepeatition - 1):
                        assign(tracking_signal, 0)  # shuffle - assign new val from randon index
                        # reference sequence
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + self.dN):  # in shuffle all elements need to be saved later to send to the stream
                        save(counts[idx], counts_st)
                        save(counts_ref[idx], counts_ref_st)
                        save(counts_ref2[idx], counts_ref_st2)
                        save(counts_square[idx],counts_square_st)

                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                # counts_st.buffer(len(self.f_vec)).average().save("counts")
                # counts_ref_st.buffer(len(self.f_vec)).average().save("counts_ref")
                counts_st.buffer(len(self.t_vec)).average().save("counts")
                counts_ref_st.buffer(len(self.t_vec)).average().save("counts_ref")
                counts_ref_st2.buffer(len(self.t_vec)).average().save("counts_ref2")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")
                self.number_order_st.buffer(len(self.t_vec)).average().save("number_order")
                self.reverse_number_order_st.buffer(len(self.t_vec)).average().save("reverse_number_order")
                counts_square_st.buffer(len(self.t_vec)).average().save("counts_square")

        self.qm, self.job = self.QUA_execute()

    def Test_Crap_QUA_PGM(self):
        if self.test_type == Experiment.test_electron_spinPump:
            # wait time
            self.t_wait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            # scan variable
            min_scan_val = self.time_in_multiples_cycle_time(self.scan_t_start)//4
            max_scan_val = self.time_in_multiples_cycle_time(self.scan_t_end)//4
            self.scan_param_vec = self.GenVector(min = min_scan_val, max = max_scan_val,delta=self.scan_t_dt//4, asInt=True) # laser time [nsec]
            self.t_measure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # till solving the measure error

            # length and idx vector
            self.vectorLength = len(self.scan_param_vec) # size of arrays
            self.array_length = len(self.scan_param_vec)  # frquencies vector size
            self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector
            self.cycle_tot_time = (self.t_wait + max_scan_val*2+min_scan_val*2)* self.array_length

        if self.test_type == Experiment.test_electron_spinMeasure:
            # wait time
            self.t_wait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            # scan variable
            min_scan_val = self.time_in_multiples_cycle_time(self.scan_t_start)//4
            max_scan_val = self.time_in_multiples_cycle_time(self.scan_t_end)//4
            self.scan_param_vec = self.GenVector(min = min_scan_val, max = max_scan_val,delta=self.scan_t_dt//4, asInt=True) # laser time [nsec]
            self.t_measure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # till solving the measure error
            self.tLaser = self.time_in_multiples_cycle_time(self.Tpump)
            self.tMW = self.t_mw

            self.fMW_1st_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_1st_res)
            self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

            # length and idx vector
            self.vectorLength = len(self.scan_param_vec) # size of arrays
            self.array_length = len(self.scan_param_vec)  # frquencies vector size
            self.idx_vec_ini = np.arange(0, self.array_length, 1)  # indexes vector
            self.cycle_tot_time = (self.t_wait + max_scan_val*2+min_scan_val*2)* self.array_length

        # tracking signal
        tSequencePeriod = self.cycle_tot_time
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            n = declare(int)  # iteration variable

            # QUA program parameters
            times = declare(int, size=20)
            times_ref = declare(int, size=20)

            with for_(n, 0, n < 20, n + 1):
                assign(times[n],0)
                assign(times_ref[n],0)

            tRead = declare(float)

            f = declare(int)  # frequency variable which we change during scan
            self.scan_param = declare(int)
            self.idx_timestamp = declare(int)
            self.measure_param = declare(int)
            self.wait_param = declare(int)


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

            counts = declare(int, size=self.array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=self.array_length)  # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.scan_param_vec]))
            idx_vec_qua = declare(int, value=self.idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes
            idx1 = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            time_st = declare_stream()
            time_ref_st = declare_stream()
            #counts_st = declare_stream()  # experiment signal
            #counts_ref_st = declare_stream()  # reference signal

            with for_(n, 0, n < self.n_avg, n + 1):
                # reset
                with for_(idx, 0, idx < self.array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                # Shuffle
                with if_(self.bEnableShuffle and not (self.test_type == Experiment.test_electron_spinMeasure)):
                    self.QUA_shuffle(idx_vec_qua, self.array_length)  # shuffle - idx_vec_qua vector is after shuffle

                # sequence
                with for_(idx, 0, idx < self.array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        if self.test_type == Experiment.test_electron_spinPump:
                            assign(self.scan_param, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                            play("Turn_ON", "Laser", duration=self.scan_param)
                            assign(self.wait_param,self.scan_param-self.t_measure//4)
                            wait(self.wait_param,"Detector_OPD")
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, self.t_measure, counts_tmp))
                            assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                            assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_tmp)
                            wait(self.t_wait//4)

                        if self.test_type == Experiment.test_electron_spinMeasure:
                            assign(idx,self.array_length) # only one cycle

                            # assign(self.scan_param, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index
                            # tRead = self.scan_param

                            wait(self.MeasProcessTime//4)

                            update_frequency("MW", self.fMW_1st_res)
                            play("Turn_ON", "Laser", duration=self.tLaser // 4)
                            #wait(self.tMW // 4)
                            # play MW (pi pulse)
                            align("Laser","MW")
                            play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)

                            # Measure
                            align("MW","Laser")
                            play("Turn_ON", "Laser", duration=self.tLaser // 4)
                            align("MW","Detector_OPD")
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, self.tLaser, counts_tmp))
                            align()

                            wait(self.MeasProcessTime//4)

                            # assign(self.idx_timestamp,0)
                            # with for_(idx1, 1, idx1 < self.array_length + 1, idx1 + 1):
                            #     #with if_(~(idx1==0)):
                            #     #    assign(counts[idx1], counts[idx1] + counts[idx1-1])
                            #     with while_((times[self.idx_timestamp]<val_vec_qua[idx1]*4)&(times[self.idx_timestamp]>=val_vec_qua[idx1-1]*4)&(self.idx_timestamp<counts_tmp)):
                            #         assign(counts[idx1-1], counts[idx1-1] + 1)
                            #         assign(self.idx_timestamp, self.idx_timestamp+1)

                            # Take reference (without pi pulse)
                            wait(self.tMW // 4)
                            play("Turn_ON", "Laser", duration=self.tLaser // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, self.tLaser, counts_ref_tmp))
                            align()

                            wait(self.MeasProcessTime//4)

                            # assign(self.idx_timestamp,0)
                            # with for_(idx1, 1, idx1 < self.array_length + 1, idx1 + 1):
                            #     #with if_(~(idx1==0)):
                            #     #    assign(counts_ref[idx1], counts_ref[idx1] + counts_ref[idx1-1])
                            #     with while_((times_ref[self.idx_timestamp]<val_vec_qua[idx1]*4)&(times_ref[self.idx_timestamp]>=val_vec_qua[idx1-1]*4)&(self.idx_timestamp<counts_ref_tmp)):
                            #         assign(counts_ref[idx1-1], counts_ref[idx1-1] + 1)
                            #         assign(self.idx_timestamp, self.idx_timestamp+1)

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
                    with for_(idx1, 0, idx1 < self.array_length, idx1 + 1):  # in shuffle all elements need to be saved later to send to the stream
                        # save(counts[idx1], counts_st)
                        # save(counts_ref[idx1], counts_ref_st)
                        save(times[idx1],time_st)
                        save(times_ref[idx1],time_ref_st)
                save(n, n_st)  # save number of iteration inside for_loop
                save(tracking_signal, tracking_signal_st)  # save number of iteration inside for_loop

            with stream_processing():
                #counts_st.buffer(self.array_length).average().save("counts")
                #counts_ref_st.buffer(self.array_length).average().save("counts_ref")
                n_st.save("iteration")
                tracking_signal_st.save("tracking_ref")
                time_st.histogram([[i, i + (self.scan_t_dt - 1)] for i in range(self.scan_t_start, self.scan_t_end, self.scan_t_dt)]).save("counts")
                time_ref_st.histogram([[i, i + (self.scan_t_dt - 1)] for i in range(self.scan_t_start, self.scan_t_end, self.scan_t_dt)]).save("counts_ref")


        self.qm, self.job = self.QUA_execute()

    '''
        site_state = QUA varible
    '''
    def Nuclear_Pol_ESR_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):  # NUCLEAR_POL_ESR
        self.Entanglement_gate_tomography_QUA_PGM(Generate_QUA_sequance=True)
        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            # for i in range(self.n_of_awg_changes):
            #     self.change_AWG_freq(channel = 1)
            #     if self.simulation:
            #         self.awg_freq_list.append(self.current_awg_freq)
            #     else:
            #         self.awg_freq_list.append(self.awg.get_frequency())
                self.time_bin_entanglement_QUA_PGM(Generate_QUA_sequance=True)

    def Nuclear_Pol_ESR_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False,
                                execute_qua=False):  # NUCLEAR_POL_ESR
        if generate_params:
            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime)
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
            self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
            self.tMW = self.t_mw
            self.tMW2 = self.t_mw2
            self.tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)  # [nsec]
            # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
            # fMW_res = 0 if fMW_res < 0 else fMW_res
            # self.fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
            self.fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
            self.verify_insideQUA_FreqValues(self.fMW_res)
            self.tRF = self.rf_pulse_time
            self.Npump = self.n_nuc_pump

            # frequency scan vector
            self.scan_param_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # length and idx vector
            self.vectorLength = len(self.scan_param_vec) # size of arrays
            self.array_length = len(self.scan_param_vec)  # frquencies vector size
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
            #play("Turn_ON", "Laser", duration=(self.tLaser) // 4)

            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()

            # CNOT
            #update_frequency("MW", self.fMW_2nd_res)
            #play MW
            ##play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
            #
            #play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
            #play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
            #
           ## align("MW","RF")
            # RF pi/2 Y pulse
            #frame_rotation_2pi(0.25,"RF")
           ## play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF/2) // 4)
            #frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            #
           ## align("RF","MW")

            # CNOT
           ## update_frequency("MW", self.fMW_res)
            # play MW
            #play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)

           ## play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
           ## play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)

            # update MW frequency
            update_frequency("MW", self.f)
            # play MW
            play("xPulse"*amp(self.mw_P_amp2), "MW", duration=self.tMW2 // 4)
            #play("xPulse"*amp(self.mw_P_amp2), "MW", duration=(self.tMW2/2) // 4)
            #play("-xPulse"*amp(self.mw_P_amp2), "MW", duration=(self.tMW2/2) // 4)
            # play Laser
            align()
            #align("MW", "Laser")
            play("Turn_ON", "Laser", duration=(self.tLaser) // 4)
            # play Laser
            # align("MW", "Detector_OPD")
            # measure signal 
            measure("readout", "Detector_OPD", None, time_tagging.digital(self.times, self.tMeasure, self.counts_tmp))
            assign(self.counts[self.idx_vec_qua[self.idx]], self.counts[self.idx_vec_qua[self.idx]] + self.counts_tmp)
            align()

            # reference
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            wait((self.tMW2+self.tMW) // 4)  # don't Play MW
            # Play laser
            play("Turn_ON", "Laser", duration=(self.tLaser) // 4)
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

        self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)

        # duration of preps 0 to 3 (incl. reset) is  tLaser+tWait+Npump*(tWait+tPump+tRF+tMW)+tMW
        # duration of prep 4 (incl. reset) is  tLaser+tWait+Npump*(tWait+tPump+tRF+tMW)+tMW+tRF/2

        # reset
        align()
        play("Turn_ON", "Laser", self.tLaser // 4)
        align()
        wait(int(self.tWait)//4)


        with if_(site_state == 0): #|00>
            # pump
            with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_1st_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
            align()
            wait(int(self.tMW)//4)

        with if_(site_state == 1): #|01>
           # pump
           with for_(self.m, 0, self.m < self.Npump, self.m + 1):
               self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
           align()
           wait(int(self.tMW)//4)

        with if_(site_state == 2): #|10>
           # pump
           with for_(self.m, 0, self.m < self.Npump, self.m + 1):
               self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_1st_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
           align()
           # play MW
           #update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
           #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)
           update_frequency("MW", self.fMW_2nd_res)
           play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
           play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)

        with if_(site_state == 3): #|11>
           # pump
           with for_(self.m, 0, self.m < self.Npump, self.m + 1):
               self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
           # play MW
           #update_frequency("MW", self.fMW_2nd_res)
           #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
           update_frequency("MW", self.fMW_1st_res)
           play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
           play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)

        with if_(site_state == 4): #|10>+|11>
           # pump
           with for_(self.m, 0, self.m < self.Npump, self.m + 1):
               self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_1st_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=self.tWait)
           align()
           # play MW
           update_frequency("MW", self.fMW_2nd_res)
           play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
           play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
           #update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
           #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=self.t_mw2 // 4)

           align("MW","RF")
           # RF Y pulse
           frame_rotation_2pi(0.25,"RF")
           play("const" * amp(self.rf_proportional_pwr), "RF", duration=(self.tRF/2) // 4)
           frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
    '''
    idx = QUA variable
    m_state = QUA variable
    '''
    def QUA_measure(self,m_state,idx,tLaser,tMeasure,t_rf,t_mw,t_mw2,p_rf):
        align()
        # durations of all measurements should be t_rf+2*t_mw
        # populations
        with if_(m_state==1):
            wait(int(t_rf+2*t_mw) // 4)

        with if_(m_state==2):
            wait((t_rf+t_mw) // 4)
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)

        with if_(m_state==3):
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=t_rf // 4)
            align("RF","MW")
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=t_mw // 4)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        
        # e-coherences
        with if_(m_state==4):
            #update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            #wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            play("-yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            update_frequency("MW", self.fMW_2nd_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            wait(int((t_rf+t_mw-t_mw2) // 4))
        with if_(m_state==5):
            #update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            play("-yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            wait(int((t_rf+2*t_mw-t_mw2) // 4))
            #wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
            #update_frequency("MW", self.fMW_1st_res)
            #play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==6):
            #update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            #play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            #wait(int((t_rf+2*t_mw-t_mw2/2) // 4))
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            play("-xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            update_frequency("MW", self.fMW_2nd_res)
            play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            wait(int((t_rf+t_mw-t_mw2) // 4))
        with if_(m_state==7):
            #update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            #play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            #wait(int((t_rf+t_mw-t_mw2/2) // 4))
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            play("-xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            wait(int((t_rf+2*t_mw-t_mw2) // 4))
            #update_frequency("MW", self.fMW_1st_res)
            #play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        # n-coherences
        with if_(m_state==8):
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            wait(int((t_rf/2+t_mw) // 4))
            align("RF","MW")
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==9):
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((t_rf/2+t_mw) // 4))
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==10):
            #update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=t_mw2 // 4)
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"* amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"* amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            update_frequency("MW", self.fMW_2nd_res)
            play("yPulse"* amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"* amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            align("RF","MW")
            wait(int((t_rf/2-t_mw) // 4))
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==11):
            #update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
            #play("xPulse"* amp(self.mw_P_amp2), "MW", duration=t_mw2 // 4)
            update_frequency("MW", (self.fMW_1st_res + self.fMW_2nd_res)/2)
            play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            play("-yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
            update_frequency("MW", self.fMW_2nd_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((t_rf/2-t_mw) // 4))
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        with if_(m_state==12):
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            wait(int((t_rf/2) // 4))
            align("RF","MW")
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==13):
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((t_rf/2) // 4))
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==14):
            update_frequency("MW", self.fMW_2nd_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            align("RF","MW")
            wait(int((t_rf/2) // 4))
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        with if_(m_state==15):
            update_frequency("MW", self.fMW_2nd_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            align("MW","RF")
            frame_rotation_2pi(0.25,"RF") # RF Y pulse
            play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
            frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
            align("RF","MW")
            wait(int((t_rf/2) // 4))
            update_frequency("MW", self.fMW_1st_res)
            play("yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            play("-yPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
            #update_frequency("MW", self.fMW_2nd_res)
            #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        # # e-n-coherences
        # with if_(m_state==12):
        #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        #     play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        #     align("MW","RF")
        #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
        #     align("RF","MW")
        #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
        #     update_frequency("MW", self.fMW_1st_res)
        #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     #update_frequency("MW", self.fMW_2nd_res)
        #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        # with if_(m_state==13):
        #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        #     play("xPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        #     align("MW","RF")
        #     frame_rotation_2pi(0.25,"RF") # RF Y pulse
        #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
        #     frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
        #     align("RF","MW")
        #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
        #     update_frequency("MW", self.fMW_1st_res)
        #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     #update_frequency("MW", self.fMW_2nd_res)
        #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        # with if_(m_state==14):
        #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        #     play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        #     align("MW","RF")
        #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
        #     align("RF","MW")
        #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
        #     update_frequency("MW", self.fMW_1st_res)
        #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     #update_frequency("MW", self.fMW_2nd_res)
        #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)
        # with if_(m_state==15):
        #     update_frequency("MW", (self.fMW_1st_res+self.fMW_2nd_res)/2)
        #     play("yPulse"* amp(self.mw_P_amp2), "MW", duration=(t_mw2/2) // 4)
        #     align("MW","RF")
        #     frame_rotation_2pi(0.25,"RF") # RF Y pulse
        #     play("const" * amp(p_rf), "RF", duration=(t_rf/2) // 4)
        #     frame_rotation_2pi(-0.25,"RF") # reset phase back to zero
        #     align("RF","MW")
        #     wait(int((t_rf/2+t_mw-t_mw2/2) // 4))
        #     update_frequency("MW", self.fMW_1st_res)
        #     play("xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(t_mw/2) // 4)
        #     #update_frequency("MW", self.fMW_2nd_res)
        #     #play("xPulse"* amp(self.mw_P_amp), "MW", duration=self.t_mw // 4)

        align()
        # Play laser
        play("Turn_ON", "Laser", duration=tLaser // 4)
        # Measure ref
        measure("readout", "Detector_OPD", None, time_tagging.digital(self.times_ref, tMeasure, self.counts_tmp))
        assign(self.counts[idx], self.counts[idx] + self.counts_tmp)

    def QUA_ref0(self,idx,tPump,tLaser,tMeasure,tWait1,tWait2):
        # pump
        align()
        wait(int(tWait1//4))
        play("Turn_ON", "Laser", duration=tPump // 4)
        align()
        wait(int(tWait2//4))
        # measure
        align()
        play("Turn_ON", "Laser", duration=tLaser // 4)
        measure("readout", "Detector_OPD", None,time_tagging.digital(self.times_ref, tMeasure, self.counts_ref_tmp))
        assign(self.counts_ref[idx], self.counts_ref[idx] + self.counts_ref_tmp)

    def QUA_ref1(self,idx,tPump,tLaser,tMeasure,tWait1,tWait2,t_mw,f_mw1,f_mw2,p_mw):
        # pump
        align()
        wait(int(tWait1//4))
        play("Turn_ON", "Laser", duration=tPump // 4)
        align()
        wait(int(tWait2//4))
        # play MW
        align()
        update_frequency("MW", f_mw1)
        ##play("xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw) // 4)
        play("xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw/2) // 4)
        play("-xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw/2) // 4)
        update_frequency("MW", f_mw2)
        play("xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw/2) // 4)
        play("-xPulse"*amp(p_mw), "MW", duration=self.time_in_multiples_cycle_time(t_mw/2) // 4)
        align()
        # measure
        play("Turn_ON", "Laser", duration=tLaser // 4)
        measure("readout", "Detector_OPD", None,time_tagging.digital(self.times_ref, tMeasure, self.counts_ref2_tmp))
        assign(self.counts_ref2[idx], self.counts_ref2[idx] + self.counts_ref2_tmp)

    def Entanglement_gate_tomography_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):
        if generate_params:
            # todo update parameters if needed for this sequence
            # dummy vectors to be aligned with QUA_PGM convention
            self.array_length = 1 
            self.idx_vec_ini = np.arange(0, self.array_length, 1)
            self.scan_param_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime) # [nsec]
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump) # [nsec]
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # [nsec]
            self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle) # [nsec]
            self.tWait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            self.Npump = self.n_nuc_pump

            # MW parameters
            self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
            self.tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
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
            self.number_of_measurement = 3 # number of measurements
            self.vectorLength = self.number_of_states*self.number_of_measurement  # total number of measurements
            self.idx_vec_ini = np.arange(0, self.vectorLength, 1) # for visualization purpose

            # tracking signal
            self.tSequencePeriod = (self.tMW + self.tRF) * self.array_length
            self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
            self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6) # []
            self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(self.Tcounter)
            self.trackingNumRepeatition = 1000#self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

            self.bEnableShuffle = False
        
        if Generate_QUA_sequance: 
            with for_(self.site_state, self.first_state, self.site_state < self.last_state + 1, self.site_state + 1): # site state loop
                with for_(self.j_idx, 0, self.j_idx < self.number_of_measurement, self.j_idx + 1): # measure loop
                    assign(self.i_idx,self.site_state*(self.number_of_states-1)+self.j_idx)
                    # prepare state
                    self.QUA_prepare_state(site_state=self.site_state)

                    # duration of CNOT or NOOP is tMW.
                    # C-NOT
                    align()
                    #update_frequency("MW", self.fMW_1st_res)
                    #play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                    #play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                    #update_frequency("MW", self.fMW_2nd_res)
                    #play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.tMW // 4)
                    wait(self.tMW//4)
                    # measure
                    self.QUA_measure(m_state=self.j_idx+1,idx=self.i_idx,tLaser=self.tLaser,tMeasure=self.tMeasure,t_rf=self.tRF,t_mw=self.tMW,t_mw2=self.tMW2,p_rf = self.rf_proportional_pwr)
                    # reference
                    #total duration of reference for prep 4 is tLaser+tWait +Npump*(tWait+tPump+tRF+tMW)+tMW+tRF/2 +tMW +tRF+2tMW +tLaser
                    self.QUA_ref0(idx=self.i_idx,tPump=self.tPump,tLaser=self.tLaser,tMeasure=self.tMeasure,tWait1=self.tWait+self.tRF+self.tMW,tWait2=self.tWait+4*self.tMW+3/2*self.tRF)
                    self.QUA_ref1(idx=self.i_idx,
                                  tPump=self.tPump,tLaser=self.tLaser,tMeasure=self.tMeasure,tWait1=self.tWait+self.tRF+self.tMW,tWait2=self.tWait+4*self.tMW+3/2*self.tRF-self.t_mw2,
                                  t_mw=self.time_in_multiples_cycle_time(self.t_mw2),f_mw1=self.fMW_1st_res,f_mw2=self.fMW_2nd_res,p_mw=self.mw_P_amp)
            
            with for_(self.i_idx, 0, self.i_idx < self.vectorLength, self.i_idx + 1):
                assign(self.resCalculated[self.i_idx],(self.counts[self.i_idx]-self.counts_ref2[self.i_idx])*1000000/(self.counts_ref2[self.i_idx]-self.counts_ref[self.i_idx]))

        if execute_qua:
            self.Entanglement_gate_tomography_QUA_PGM(generate_params=True)
            self.QUA_PGM()

    def repeated_time_bin_qua_sequence_start(self):
        time_tagger = self.get_time_tagging_func("Detector_OPD")
        # In the first part of the experiment we want information on the timing of the photon arrivals.
        # Only one photon can be recorded at the detector at a time
        align("Laser", "Blinding")
        play("Turn_ON", "Laser", duration=self.tLaser)
        play("Turn_ON", "Blinding", duration=self.tBlinding_pump)
        play(f"opr_{int(self.off_time + 1)}", "Blinding")  # Calibrated for 1ns Laser trigger time
        play(f"opr_left_{int(self.tblidning_2_to_3_first_waveform_length)}", "Blinding")
        align("Laser", "MW")
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
        align("MW", "Resonant_Laser")
        play("Turn_ON", "Resonant_Laser", duration=self.tRed)
        # Records #self.times at points where self.counts_tmp is recorded
        # self.times is NOT a vector of length self.tMeasure
        # self.counts_tmp stores the total number of photon arrivals as an integer
        align("Laser", "Detector_OPD")
        measure("readout", "Detector_OPD", None,
                time_tagger(self.times, int(self.MeasProcessTime), self.counts_tmp))
        assign(self.counts[self.idx], self.counts[self.idx] + self.counts_tmp)
        align("Blinding", "MW")
        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMW)
        play("Turn_ON", "Blinding", duration=self.tBlinding)
        play(f"opr_{int(self.off_time + 1)}", "Blinding")
        align("MW", "Resonant_Laser")
        play("Turn_ON", "Resonant_Laser", duration=self.tRed)
        play(f"opr_left_{int(self.tblidning_2_to_3_first_waveform_length)}", "Blinding")
        # The pulse below is to enforce total length of 16 ns, can be changes to any length above self.tblidning_2_to_3_first_waveform_length
        play(f"opr_{int(self.tblidning_2_to_3_second_waveform_length)}", "Blinding")
        # Insert an if condition here in the future
        # In the second half of the experiment we want the number of counts and not their timing
        align("Blinding", "MW")  # Check the timing correctly
        wait(self.T_bin_qua)  # +1 to give the pulses some space

    def repeated_time_bin_qua_sequence_end(self):
        time_tagger = self.get_time_tagging_func("Detector_OPD")
        # align("MW", self.laser_type_stat)
        # play("Turn_ON", self.laser_type_stat, duration=self.tStatistics)
        # align("MW", "Detector2_OPD")
        # measure("min_readout", "Detector2_OPD", None,
        #         time_tagger(self.times2, int(self.tStatistics), self.counts_tmp2))
        # assign(self.counts2[self.idx], self.counts2[self.idx] + self.counts_tmp2)

    def time_bin_entanglement_QUA_PGM(self, generate_params=False, Generate_QUA_sequance=False, execute_qua=False):
        if generate_params:
            # dummy vectors to be aligned with QUA_PGM convention
            self.array_length = 1  # time vector size
            self.idx_vec_ini = np.arange(0, self.array_length, 1)  # Index array for QUA_PGM
            self.f_vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                                        delta=self.mw_df * self.u.MHz,
                                        asInt=False)  # Don't need it, but QUA_PGM requires it

            # Updated experiment parameters
            self.collection_time = 25  # time of light collection in a single bin in ns
            self.red_laser_wait = 3  # time to wait after shooting a red laser pulse in ns
            self.Tpump = 5000  # [nsec]
            self.t_mw = 32  # [nsec]
            self.t_blinding_pump = 5000  # First blinding, to cover the detector before the first measure
            self.tblinding_2_to_3 = 16 # [nsec]
            #self.bin_times = [[20, 48], [84, 112], [128, 156]] # Does not change as of 12.02.2025
            self.tblidning_2_to_3_first_waveform_length = self.tblinding_2_to_3 - (self.T_bin - self.tblinding_2_to_3) - 1 #To understand, check how waveforms are defined in the config
            self.tblidning_2_to_3_second_waveform_length = self.tblinding_2_to_3 - self.tblidning_2_to_3_first_waveform_length

            # sequence parameters.
            self.tLaser = self.time_in_multiples_cycle_time(self.Tpump) // 4
            self.tWaitTimeGateSuppression = self.time_in_multiples_cycle_time(
                self.TwaitTimeBin) // 4  # This returns 16ns
            self.tWaitDectorMeasure = self.time_in_multiples_cycle_time(self.TwaitTimeBinMeasure) // 4
            self.tWaitfroblinding = self.time_in_multiples_cycle_time(self.TwaitForBlinding) // 4

            # New red laser parameters:
            self.tRed = self.time_in_multiples_cycle_time(self.TRed) // 4
            self.tCollectionWait = self.time_in_multiples_cycle_time(1)
            self.tStatistics = self.time_in_multiples_cycle_time(self.TRedStatistics) // 4  # change to resonant measure

            # MW parameters
            self.tMW = self.time_in_multiples_cycle_time(self.t_mw) // 4
            self.tMWPiHalf = self.time_in_multiples_cycle_time(self.t_mw / 2) // 4
            #self.tMWPiStat = self.tMW
            # Change to time between blidning and MW
            self.time_to_next_MW = self.time_in_multiples_cycle_time(self.T_bin) // 4
            self.T_bin_qua = self.time_in_multiples_cycle_time(self.T_bin) // 4

            self.tBlinding_pump = self.tLaser + self.tMWPiHalf # +1 to prevent recording laser light
            self.tBlinding = self.tMW  # Second blinding, between the first and second measurement bin
            self.tBlinding_2_to_3 = self.time_in_multiples_cycle_time(self.tblinding_2_to_3)//4  # Third blinding, between 2 and 3 measure, fixed to 16ns for now
            self.wait_before_stat = self.time_in_multiples_cycle_time(2*self.T_bin)//4

            # length and idx vector
            # Move to qua units below
            self.MeasProcessTime = self.tMWPiHalf + (self.off_time+1) + self.T_bin + self.tMW + (self.off_time+1) + 2*self.T_bin + self.tblinding_2_to_3 + 1 # time required of measure, 4 is red laser trigger+2ns wait
            # self.tMeasure = self.time_in_multiples_cycle_time(
            #     self.MeasProcessTime) // 4  # Measurement time of the detector
            self.vectorLength = 1  # Length of the counts vector
            self.idx_vec = np.arange(0, self.vectorLength, 1)  # indexes vector for fetch and plot
            self.all_times_vec = np.arange(0, self.MeasProcessTime, 1)
            self.number_of_statistical_measurements = 1000
            self.statistics_pulse_type = "xPulse"

            # tracking signal
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump)
            self.Npump = self.n_nuc_pump
            self.tSequencePeriod = ((self.tMW + self.tLaser) * (
                        self.Npump + 2) * self.Npump) * self.array_length
            self.tGetTrackingSignalEveryTime_nsec = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
            self.tTrackingSignaIntegrationTime_usec = int(self.tTrackingSignaIntegrationTime * 1e6)  # []
            self.tTrackingIntegrationCycles = self.tTrackingSignaIntegrationTime_usec // self.time_in_multiples_cycle_time(
                self.Tcounter)
            self.trackingNumRepeatition = self.tGetTrackingSignalEveryTime_nsec // (
                self.tSequencePeriod) if self.tGetTrackingSignalEveryTime_nsec // (self.tSequencePeriod) > 1 else 1

            #Defining the type of laser to use in the second half of the experiment
            if self.is_green:
                self.laser_type_stat = "Laser"
            else:
                self.laser_type_stat = "Resonant_Laser"

            start_bin_1 = self.t_mw // 2 + 1 + self.off_time  # +1 [ns] is red laser trigger time
            start_bin_2 = start_bin_1 + self.T_bin + self.t_mw + 1 + self.off_time
            start_bin_3 = start_bin_2 + self.T_bin + self.tblinding_2_to_3
            self.bin_times = [[start_bin_1, start_bin_1 + self.T_bin], [start_bin_2, start_bin_2 + self.T_bin],
                              [start_bin_3, start_bin_3 + self.T_bin]]

            #Variables for simulation
            a = 20
            b = 48
            self.tau = 1.2
            self.lower_simulation_bound = np.exp(-a / self.tau)
            self.higher_simulation_bound = np.exp(-b / self.tau)

        if Generate_QUA_sequance:
            with if_(self.simulation_flag):
                #rand = Random()
                #assign(self.r,rand.rand_fixed())
                #assign(self.times[self.n_avg], -self.tau * Math.ln(self.exp_a_simulated - self.r * (self.exp_a_simulated - self.exp_b_simulated)))
                assign(self.counts[self.idx], 4)
                with for_(self.j_idx, 0, self.j_idx < self.counts[self.idx], self.j_idx + 1):
                     assign(self.times[self.j_idx], self.j_idx*10)
                #     #assign(self.times[self.j_idx], Cast.to_int(-1.2 * Math.ln(1.0 - self.r)))
                #     #assign(self.assign_input[self.j_idx], -1.2 * Math.ln(1.0 - self.r)) #Despite declared as a fixed array, takes int
                assign(self.counts2[self.idx], 15)
            with else_():
                with switch_(self.mod4, unsafe=True):
                    with case_(0):
                        self.repeated_time_bin_qua_sequence_start()
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
                        self.repeated_time_bin_qua_sequence_end()
                        assign(self.pulse_type, 4)

                    with case_(3):
                        self.repeated_time_bin_qua_sequence_start()
                        play("yPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf)
                        self.repeated_time_bin_qua_sequence_end()
                        assign(self.pulse_type, 3)

                    with case_(2):
                        self.repeated_time_bin_qua_sequence_start()
                        play("xPulse" * amp(self.mw_P_amp), "MW", duration=self.tMW)
                        self.repeated_time_bin_qua_sequence_end()
                        assign(self.pulse_type, 2)


                    with case_(1):
                        self.repeated_time_bin_qua_sequence_start()
                        play("yPulse" * amp(self.mw_P_amp), "MW", duration=self.tMWPiHalf, condition = self.bool_condition)
                        self.repeated_time_bin_qua_sequence_end()
                        assign(self.pulse_type, 1)


            ## The code below simulates 20 pulses with increasing pulse length by 1ns.
            # with for_(self.k_idx, 0, self.k_idx < 20+5, self.k_idx + 1):
            #     with if_(self.k_idx < 16):
            #         with switch_(self.k_idx, unsafe=True):
            #             for jdx in range(16):
            #                 with case_(jdx):
            #                     play(f"opr_{jdx}", "Blinding")
            #     with else_():
            #         with switch_(self.k_idx, unsafe=True):
            #             for jdx in range(4):
            #                 with case_(jdx + 16):
            #                     play(f"opr2_{jdx}", "Blinding")
            #                     play('Turn_ON', 'Blinding', duration=4)#Required for pulses longer than 16ns

                ##Below is testing of playing of a single command
                # play(f"opr2_{3}", "Blinding") # Length is n-1, where opr2_n
                # play('Turn_ON', 'Blinding', duration=4)
            #     wait(25, 'Blinding')

        if execute_qua:
            self.time_bin_entanglement_QUA_PGM(generate_params=True)
            # counts = create_counts_vector(vector_size=96)
            self.QUA_PGM_No_Tracking()

    def Population_gate_tomography_QUA_PGM(self, generate_params = False, Generate_QUA_sequance = False, execute_qua = False):
        if generate_params:
            # dummy vectors to be aligned with QUA_PGM convention
            self.array_length = 1 
            self.idx_vec_ini = np.arange(0, self.array_length, 1)
            self.scan_param_vec = self.GenVector(min = 0 * self.u.MHz, max = self.mw_freq_scan_range * self.u.MHz, delta= self.mw_df * self.u.MHz, asInt=False)

            # sequence parameters
            self.tMeasureProcess = self.time_in_multiples_cycle_time(self.MeasProcessTime) # [nsec]
            self.tPump = self.time_in_multiples_cycle_time(self.Tpump) # [nsec]
            self.tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle) # [nsec]
            self.tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed) # [nsec]
            self.tWait = self.time_in_multiples_cycle_time(self.Twait*1e3) # [nsec]
            self.Npump = self.n_nuc_pump

            # MW parameters
            self.tMW = self.time_in_multiples_cycle_time(self.t_mw)
            self.tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
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
                    update_frequency("MW", self.fMW_1st_res)
                    play("xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                    play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(self.tMW/2) // 4)
                    #wait(self.tMW//4)
                    # measure
                    self.QUA_measure(m_state=self.j_idx+1,idx=self.i_idx,tLaser=self.tLaser,tMeasure=self.tMeasure,t_rf=self.tRF,t_mw=self.tMW,t_mw2=self.tMW2,p_rf = self.rf_proportional_pwr)
                    # reference
                    self.QUA_ref0(idx=self.i_idx,tPump=self.tPump,tLaser=self.tLaser,tMeasure=self.tMeasure,tWait1=self.tWait+self.tRF+self.tMW,tWait2=self.tWait+4*self.tMW+3/2*self.tRF)
                    self.QUA_ref1(idx=self.i_idx,
                                  tPump=self.tPump,tLaser=self.tLaser,tMeasure=self.tMeasure,tWait1=self.tWait+self.tRF+self.tMW,tWait2=self.tWait+4*self.tMW+3/2*self.tRF-self.t_mw2,
                                  t_mw=self.time_in_multiples_cycle_time(self.t_mw2),f_mw1=self.fMW_1st_res,f_mw2=self.fMW_2nd_res,p_mw=self.mw_P_amp)
            
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
        correlation_width = 400*self.u.ns
        self.correlation_width = int(correlation_width)
        expected_counts = 150
        N = 1000 # every N cycles it tries to update the stream

        with program() as self.quaPGM:
            counts_1 = declare(int)  # variable for the number of counts on SPCM1
            counts_2 = declare(int)  # variable for the number of counts on SPCM2
            times_1 = declare(int, size=expected_counts)  # array of count clicks on SPCM1
            times_2 = declare(int, size=expected_counts)  # array of count clicks on SPCM2

            # g2 = declare(int,value=self.GenVector(min=0,max=0,delta=0,N=int(2*correlation_width),asInt=True))  # array for g2 to be saved
            g2 = declare(int, size=int(2 * correlation_width))  # array for g2 to be saved
            total_counts = declare(int)

            # Streamables
            g2_st = declare_stream()  # g2 stream
            total_counts_st = declare_stream()  # total counts stream
            n_st = declare_stream()  # iteration stream

            # Variables for computation
            p = declare(int)  # Some index to run over
            n = declare(int)  # n: repeat index
            # with infinite_loop_():
            # play("Turn_ON", "Laser")
            idxN = declare(int, value=0)  # every N steps it will try to update the stream
            iteration_number = declare(int, value=0)  # every N steps it will try to update the stream


            with infinite_loop_():
                assign(idxN, idxN + 1)
                assign(iteration_number, iteration_number + 1)

                play("Turn_ON", "Laser")
                measure("readout", "Detector_OPD", None, time_tagging.digital(times_1, self.Tcounter, counts_1))
                measure("readout", "Detector2_OPD", None, time_tagging.digital(times_2, self.Tcounter, counts_2))

                with if_((counts_1 > 0) & (counts_2 > 0)):
                    g2 = self.MZI_g2(g2, times_1, counts_1, times_2, counts_2, correlation_width)

                assign(total_counts, counts_1 + counts_2 + total_counts)

                with if_(idxN > N - 1):
                    assign(idxN, 0)
                    with for_(p, 0, p < g2.length(), p + 1):
                        save(g2[p], g2_st)
                        # assign(g2[p], 0)

                    save(iteration_number, n_st)
                    save(total_counts, total_counts_st)

            save(iteration_number, n_st)
            save(total_counts, total_counts_st)

            with stream_processing():
                # g2_st.buffer(correlation_width*2).save("g2")
                g2_st.buffer(correlation_width * 2).average().save("g2")
                total_counts_st.save("total_counts")
                n_st.save("iteration")

        self.qm, self.job = self.QUA_execute()
    def ODMR_Bfield_QUA_PGM(self):  # CW_ODMR

        # specific per experiment
        # get experiment values from GUI
        items_val = self.GetItemsVal(
            items_tag=["inInt_process_time", "inInt_TcounterPulsed", "inInt_Tsettle", "inInt_t_mw", "inInt_edge_time"])

        # Experiment time period parameters
        tLaser = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"] +
                                                   items_val["inInt_Tsettle"] +
                                                   items_val[
                                                       "inInt_process_time"])  # self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tMW = self.time_in_multiples_cycle_time(items_val["inInt_t_mw"])  # self.t_mw)
        tMeasure = self.time_in_multiples_cycle_time(items_val["inInt_TcounterPulsed"])  # self.TcounterPulsed)
        tSettle = self.time_in_multiples_cycle_time(items_val["inInt_Tsettle"])  # self.Tsettle)
        tEdge = self.time_in_multiples_cycle_time(items_val["inInt_edge_time"])  # self.Tedge)
        tBfield = self.time_in_multiples_cycle_time(tMW + 2 * tEdge)

        # Scan over MW frequency - gen its vector
        vec = self.GenVector(min=0 * self.u.MHz, max=self.mw_freq_scan_range * self.u.MHz,
                             delta=self.mw_df * self.u.MHz)
        array_length = len(vec)
        self.f_vec = vec

        # length and idx vector
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = (tBfield + tLaser) * 2 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        wait(tEdge // 4, "MW")
                        play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                        # wait(300//4,"RF")
                        play("const" * amp(p), "RF", duration=tBfield // 4)

                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # don't play MW
                        wait(tEdge // 4, "MW")
                        play("cw", "MW", duration=tMW // 4)  # play microwave pulse
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                        align()

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tMW = self.time_in_multiples_cycle_time(self.t_mw)
        tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        tEdge = self.time_in_multiples_cycle_time(self.Tedge)
        tWait = self.time_in_multiples_cycle_time(self.Twait * 1e3)
        tRF = self.time_in_multiples_cycle_time(self.rf_pulse_time)
        tBfield = self.time_in_multiples_cycle_time(tMW2 + 2 * tEdge)
        Npump = self.n_nuc_pump

        fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(fMW_res)
        fMW_res1 = fMW_res  # here should be zero
        fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz  # Hz
        self.verify_insideQUA_FreqValues(fMW_2nd_res)
        fMW_res2 = fMW_2nd_res

        # time scan vector
        tScan_min = self.scan_t_start // 4 if self.scan_t_start // 4 > 0 else 1  # in [cycles]
        tScan_max = self.scan_t_end // 4 if self.scan_t_end // 4 > 0 else 1  # in [cycles]
        dt = self.scan_t_dt // 4  # in [cycles]
        self.t_vec = [i * 4 for i in range(tScan_min, tScan_max + 1, dt)]  # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt / 10, dt)  # in [cycles]

        # amp scan vector
        # set RF frequency:
        pRF = self.rf_Pwr / self.OPX_rf_amp  # p should be between 0 to 1
        pRF = pRF if 0 < pRF < 1 else 0
        if pRF == 0:
            print(f"error RF freq is out of limit {pRF}")
        dp_N = float(self.N_p_amp)
        p_vec_ini = np.arange(0, 0.4, 1 / dp_N, dtype=float)  # proportion vect
        self.rf_Pwr_vec = p_vec_ini * self.OPX_rf_amp  # in [V], used to plot the graph

        # MW frequency scan vector
        # fitCoff - see Eilon's Onenote
        # f2_GHz*1e9 + (b*V/(V + c))*1e9
        b = 0.0344
        c = 0.124
        self.f_vec = ((fMW_res1 + fMW_res2) / 2 + (
                    self.rf_Pwr_vec * b / (self.rf_Pwr_vec + c)) * 1e9)  # [Hz], frequencies vector
        self.f_vec = self.f_vec.astype(int)

        # length and idx vector
        array_length = len(p_vec_ini)  # amps vector size
        # array_length = len(self.t_vec)                      # time vector size
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)  # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW + tRF + tPump) * Npump + tBfield + tWait + tMW + tLaser) * 3 * array_length
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9)  # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime // self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(
                int)  # frequency variable which we change during scan - here f is according to calibration function
            t = declare(int)  # [cycles] time variable which we change during scan
            p = declare(fixed)  # [unit less] proportional amp factor which we change during scan

            n = declare(int)  # iteration variable
            m = declare(int)  # number of pumping iterations
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference
            counts_ref2_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool, value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)  # iteration variable
            tracking_signal_tmp = declare(int)  # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)  # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int, value=0)

            counts = declare(int, size=array_length)  # experiment signal (vector)
            counts_ref = declare(int, size=array_length)  # reference signal (vector)
            counts_ref2 = declare(int, size=array_length)  # reference signal (vector)

            # Shuffle parameters
            # f_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))
            f_vec_qua = declare(int, value=self.f_vec)  # frequencies QUA vector
            val_vec_qua = declare(fixed, value=p_vec_ini)  # volts QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)  # indexes QUA vector
            idx = declare(int)  # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()  # experiment signal
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
                            # play MW
                            play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                            play("const" * amp(pRF), "RF", duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        wait(tEdge // 4, "MW")
                        update_frequency("MW", f)
                        play("cw" * amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(20//4,"RF") # manual calibration
                        update_frequency("RF", 0 * self.u.MHz)  # set RF frequency to resonance
                        play("const" * amp(p), "RF", duration=tBfield // 4)

                        align()
                        wait(tWait // 4)
                        update_frequency("MW", fMW_res1)
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                            play("const" * amp(pRF), "RF", duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        wait((tEdge + tMW2 + tWait) // 4, "MW")
                        # update_frequency("MW", fMW_res2)
                        # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(300//4,"RF") # manual calibration
                        # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        # align()
                        # wait(tWait)
                        update_frequency("MW", fMW_res1)
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                        align()

                        # reference sequence
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                            # play RF (@resonance freq & pulsed time)
                            align("MW", "RF")
                            update_frequency("RF", self.rf_resonance_freq * self.u.MHz)  # set RF frequency to resonance
                            play("const" * amp(pRF), "RF", duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF", "Laser")
                            play("Turn_ON", "Laser", duration=tPump // 4)
                        align()

                        wait((tEdge + tMW2 + tWait) // 4, "MW")
                        # update_frequency("MW", fMW_res2)
                        # play("cw"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)  # play microwave pulse
                        # wait(300//4,"RF") # manual calibration
                        # update_frequency("RF", 0 * self.u.MHz) # set RF frequency to resonance
                        # play("const" * amp(p), "RF",duration=tBfield // 4)

                        # align()
                        # wait(tWait//4)
                        update_frequency("MW", fMW_res2)
                        play("cw" * amp(self.mw_P_amp), "MW", duration=tMW // 4)  # play microwave pulse

                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref2_tmp))
                        assign(counts_ref2[idx_vec_qua[idx]], counts_ref2[idx_vec_qua[idx]] + counts_ref2_tmp)

                        align()

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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

    def Electron_lifetime_QUA_PGM(self):  # T1
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # measure signal 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()
                        # play MW
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        wait(t)
                        align()
                        # play Laser
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        play("Turn_ON", "Laser", duration=tPump // 4)
                        align("Laser","MW")
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
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
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW // 4)

                        # play RF pi/2
                        align("MW", "RF")
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)

                        # Twait, note: t is already in cycles!
                        wait(t)

                        # play RF pi/2
                        play("const" * amp(p), "RF", duration=(tRF / 2) // 4)
                        # play Laser
                        #align("RF", "Laser")
                        #play("Turn_ON", "Laser", duration=tSettle // 4)

                        # play MW
                        align("RF", "MW")
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser  // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        play("Turn_ON", "Laser", duration=tPump // 4)
                        align("Laser","MW")
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            # play MW
                            play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
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
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW // 4)

                        # do not play RF
                        wait(t + tRF // 4)
                        # play Laser
                        #play("Turn_ON", "Laser", duration=tSettle // 4)

                        # play MW
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW // 4)
                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser  // 4)
                        # Measure ref
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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

    def Electron_Coherence_QUA_PGM(self):  # Also CPMG when N>0
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)  # xPulse I = 0.5V, Q = zero
                        # wait t unit
                        with if_(Ncpmg == 0):
                            wait(tWait)

                        # "CPMG section" I=0, Q=1 @ Pi
                        with for_(m, 0, m < Ncpmg, m + 1):
                            wait(t)
                            # play MW
                            update_frequency("MW", 0)
                            play("yPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)  # yPulse I = zero, Q = 0.5V
                            # wait t unit
                            wait(t)
                        # align()

                        # play MW (I=1,Q=0) @ Pi/2
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW / 2) // 4)

                        # play Laser
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=(tLaser) // 4)
                        # measure signal 
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference 
                        # wait Tmw + Twait
                        with if_(Ncpmg==0):
                            wait(tWait + tMW // 4)
                        with if_(Ncpmg>0):
                            wait(Ncpmg*(2*t+ tMW // 4) + tMW //4)

                        # play laser
                        play("Turn_ON", "Laser", duration=(tLaser) // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        tMW2 = self.t_mw2
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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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

                            self.QUA_Pump(t_pump=tPump, t_mw=tMW, t_rf=tRF, f_mw=fMW_res,
                                          f_rf=self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf=p,
                                          t_wait=self.tWait)
                        align()

                        # update MW frequency
                        update_frequency("MW", f)
                        # play MW
                        play("xPulse"*amp(self.mw_P_amp2), "MW", duration=tMW2 // 4)
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
                        wait(tMW2 // 4)  # don't Play MW
                        # Play laser
                        play("Turn_ON", "Laser", duration=(tLaser + tMeasureProcess) // 4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # in shuffle all elements need to be saved later to send to the stream
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
        pMW=self.mw_P_amp


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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        update_frequency("MW", 0)
                        #play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)

                        #play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        #play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        # play RF after MW
                        align("MW", "RF")
                        play("const" * amp(p), "RF",
                             duration=tRF // 4)  # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF", "MW")
                        #play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        #play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        #play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
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
                        #play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        #play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        #play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        # Don't play RF after MW just wait
                        wait(tRF // 4)
                        # play MW
                        #play("xPulse"*amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=(tMW/2) // 4)
                        #play("xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        #play("-xPulse" * amp(pMW), "MW", duration=(tMW/2) // 4)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq) * self.u.GHz # Hz
        self.verify_insideQUA_FreqValues(self.fMW_res)
        self.tRF = self.rf_pulse_time
        self.Npump = self.n_nuc_pump
        # Pump parameters
        # tPump = self.time_in_multiples_cycle_time(self.Tpump)
        # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz
        # fMW_res = 0 if fMW_res < 0 else fMW_res
        # fMW_res = 400 * self.u.MHz if fMW_res > 400 * self.u.MHz else fMW_res
        # tRF = self.rf_pulse_time
        # Npump = self.n_nuc_pump

        # time
        tMeasueProcess = self.MeasProcessTime
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed + self.Tsettle + tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        # tRF = self.rf_pulse_time
        # fMW_res = (self.mw_freq_resonance - self.mw_freq) * self.u.GHz

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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            t = declare(int)  # time variable which we change during scan
            p = declare(fixed)  # fixed is similar to float 4bit.28bit

            self.t_mw_qua = declare(int)
            assign(self.t_mw_qua, (self.t_mw/2) // 4)

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number
            self.m = declare(int)  # number of pumping iterations
            self.t_wait = declare(int)  # [cycles] time variable which we change during scan
            self.Npump = self.n_nuc_pump
            assign(self.t_wait,self.Twait * 1000//4)

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

                # Shuffle
                with if_(self.bEnableShuffle):
                    self.QUA_shuffle(idx_vec_qua, array_length)

                # sequence
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new random Trf 
                        assign(t, val_vec_qua[idx_vec_qua[idx]])

                        # polarize (@fMW_res @ fRF_res)
                        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                            self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=0)#self.tWait)
                        align()


                        # Signal
                        # play MW for time Tmw
                        #update_frequency("MW", self.fMW_res)
                        #play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)

                        update_frequency("MW", self.fMW_res)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)

                        # play RF after MW
                        align("MW", "RF")
                        play("const" * amp(p), "RF",
                             duration=t)  # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF", "MW")
                        #play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        #update_frequency("MW", self.fMW_2nd_res)
                        wait(self.t_wait)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        with for_(self.m, 0, self.m < self.Npump, self.m + 1):
                            self.QUA_Pump(t_pump = self.tPump,t_mw = self.tMW, t_rf = self.tRF, f_mw = self.fMW_2nd_res,f_rf = self.rf_resonance_freq * self.u.MHz, p_mw=self.mw_P_amp, p_rf = self.rf_proportional_pwr, t_wait=0)#self.tWait)
                        align()

                        # play MW for time Tmw
                        #play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        #update_frequency("MW", self.fMW_2nd_res)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # Don't play RF after MW just wait
                        wait(t)
                        wait(self.t_wait)  # t already devide by four
                        # play MW
                        #play("xPulse" * amp(self.mw_P_amp), "MW", duration=tMW // 4)
                        #update_frequency("MW", self.fMW_2nd_res)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        play("-xPulse"*amp(self.mw_P_amp), "MW", duration=self.t_mw_qua)
                        # play laser after MW
                        align("MW", "Laser")
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        # play measure after MW
                        align("MW", "Detector_OPD")
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW2 = self.time_in_multiples_cycle_time(self.t_mw2)

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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        play("xPulse" * amp(self.mw_P_amp2), "MW",
                             duration=tMW2 // 4)  # tMW2 defines the Rabi time and length of pi pulse
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
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        # align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=self.time_in_multiples_cycle_time(self.Tcounter) // 4)
                            measure("min_readout", "Detector_OPD", None,
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
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
                                    time_tagging.digital(times_ref, self.time_in_multiples_cycle_time(self.Tcounter),
                                                         tracking_signal_tmp))
                            assign(tracking_signal, tracking_signal + tracking_signal_tmp)
                        assign(track_idx, 0)

                # stream
                with if_(sequenceState == 0):
                    with for_(idx, 0, idx < array_length,
                              idx + 1):  # add one by one elements from counts (which is a vector) into counts_st
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

        # MW parameters
        self.fMW_1st_res = 0 #(self.mw_freq_resonance - self.mw_freq) * self.u.GHz # Hz
        self.verify_insideQUA_FreqValues(self.fMW_1st_res)
        self.fMW_2nd_res = (self.mw_2ndfreq_resonance - self.mw_freq_resonance) * self.u.GHz # Hz
        self.verify_insideQUA_FreqValues(self.fMW_2nd_res)

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
        trackingNumRepeatition = tGetTrackingSignalEveryTime // (tSequencePeriod) if tGetTrackingSignalEveryTime // (
            tSequencePeriod) > 1 else 1

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
                        #update_frequency("MW", 0)
                        update_frequency("MW", self.fMW_1st_res)
                        play("xPulse"*amp(self.mw_P_amp), "MW", duration=t)
                        #play("xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                        #play("-xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                        # update_frequency("MW", self.fMW_2nd_res)
                        # ## play("xPulse"*amp(self.mw_P_amp), "MW", duration=t)
                        # play("xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
                        # play("-xPulse"*amp(self.mw_P_amp), "MW", duration=t/2)
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

        if self.is_green:
            self.laser_type = "Laser"
        else:
            self.laser_type = "Resonant_Laser"

        with program() as self.quaPGM:
            # self.MeasProcessTime = 510 # [nsec] - delay due to OPX measure process time
            # self.Tcounter -= self.MeasProcessTime
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
            pump_pulse = declare(bool,value=False)
            scan_freq_experiment = self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN

            with infinite_loop_():
                if scan_freq_experiment:
                    assign(pump_pulse, IO2)
                    with if_(pump_pulse):
                        play("Turn_ON", "Laser", duration=int(self.Tpump * self.u.ns // 4))  #
                        wait(250)
                        align()
                        assign(IO2,False)
                with for_(self.n, 0, self.n < n_count, self.n + 1):  # number of averages / total integation time
                    if scan_freq_experiment:
                        play("Turn_ON", "Resonant_Laser", duration=int(self.Tcounter * self.u.ns // 4))  #
                    else:
                        play("Turn_ON", self.laser_type, duration=int(self.Tcounter * self.u.ns // 4))  #
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(self.times, int(self.Tcounter * self.u.ns), self.counts))
                    # measure("min_readout", "Detector2_OPD", None, time_tagging.digital(self.times_ref, int(self.Tcounter * self.u.ns), self.counts_ref))
                    measure("min_readout", "Detector2_OPD", None, time_tagging.digital(self.times_ref, int(self.Tcounter * self.u.ns), self.counts_ref))

                    assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language  # align()
                    if self.sum_counters_flag:
                        assign(self.total_counts, self.total_counts + self.counts_ref)
                    else:
                        assign(self.total_counts2,self.total_counts2 + self.counts_ref)
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

    def awg_sync_counter_QUA_PGM(self, n_count=1):

        if self.is_green:
            self.laser_type = "Laser"
        else:
            self.laser_type = "Resonant_Laser"

        with program() as self.quaPGM:
            # self.MeasProcessTime = 510 # [nsec] - delay due to OPX measure process time
            # self.Tcounter -= self.MeasProcessTime
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
                play("Turn_ON",configs.QUAConfigBase.Elements.AWG_TRigger.value , duration=int(1000 * self.u.ns // 4))  #
                wait(1000//4)
                align()
                with for_(self.n, 0, self.n < self.total_integration_time * self.u.ms, self.n + self.Tcounter):  # number of averages / total integation time
                    play("Turn_ON", self.laser_type, duration=int(self.Tcounter * self.u.ns // 4))  #
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(self.times, int(self.Tcounter * self.u.ns), self.counts))
                    assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language  # align()

                save(self.total_counts, self.counts_st)
                assign(self.total_counts, 0)

            with stream_processing():
                # TODO: Change buffer size to not be hardcoded
                self.counts_st.buffer(400).average().save("counts")
                # self.counts_st.buffer(400).save("counts")

        self.qm, self.job = self.QUA_execute()

    def MeasureByTrigger_QUA_PGM(self, num_bins_per_measurement: int = 1, num_measurement_per_array: int = 1,
                                 triggerThreshold: int = 1, play_element=configs.QUAConfigBase.Elements.LASER.value):
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
                        play("Turn_ON", play_element, duration=laser_on_duration)
                        measure("readout", "Detector_OPD", None,
                                time_tagging.digital(times, single_integration_time, counts))
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


    def MeasurePLE_QUA_PGM(self, trigger_threshold: int = 1):
        # MeasureByTrigger_QUA_PGM function measures counts.
        # It will run a single measurement every trigger.
        # each measurement will be append to buffer.
        laser_on_duration = int(self.total_integration_time * self.u.ms // 4)
        single_integration_time = int(self.Tcounter * self.u.ns)
        init_pulse_time = self.Tpump * self.u.ns // 4
        tracking_pulse_time = int(5 * self.u.ms // 4)
        tracking_measure_time =  int(self.Tcounter*self.u.ns)
        num_tracking_signal_loops = int((5 * self.u.ms / int(self.Tcounter * self.u.ns)))
        t_wait_after_init = int(500*self.u.ns//4)
        n_count = int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns)

        with program() as self.quaPGM:
            times = declare(int, size=1000)  # maximum number of counts allowed per measurements
            counts = declare(int)  # apd1
            total_counts = declare(int, value=0)  # apd1
            n = declare(int)  #
            meas_idx = declare(int, value=0)
            counts_st = declare_stream()
            counts_ref_st = declare_stream()
            meas_idx_st = declare_stream()

            sequence_state = declare(int, value=0)
            should_we_track = declare(int, value=0)
            trigger_threshold = declare(int, value=trigger_threshold)
            assign(IO2, 0)
            assign(IO1, 0)

            with infinite_loop_():
                # wait_for_trigger("Laser")
                assign(sequence_state, IO2)
                with if_((sequence_state + 1 > trigger_threshold) & (sequence_state - 1 < trigger_threshold)):
                    assign(IO2, 0)
                    assign(sequence_state, 0)
                    assign(total_counts, 0)
                    align()
                    # Tracking pulse
                    play("Turn_ON", configs.QUAConfigBase.Elements.LASER.value, duration=tracking_pulse_time)
                    with for_(n, 0, n < num_tracking_signal_loops, n + 1):
                        measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, tracking_measure_time, counts))
                        assign(total_counts, total_counts + counts)
                    save(total_counts, counts_ref_st)
                    align()

                    assign(total_counts, 0)
                    # assign(should_we_track, IO1)
                    with if_(should_we_track==0):
                        with for_(n, 0, n < self.n_avg, n + 1):
                            wait(500//4)
                            wait(t_wait_after_init - 28 // 4)
                            play("Turn_ON", configs.QUAConfigBase.Elements.LASER.value, duration=init_pulse_time)
                            wait(t_wait_after_init-28//4)
                            align()
                            # we have 28ns delay between measure command and actual measure start due to tof delay
                            with for_(n, 0, n < n_count, n + 1):
                                play("Turn_ON", configs.QUAConfigBase.Elements.RESONANT_LASER.value,duration=single_integration_time//4)
                                measure("readout", "Detector_OPD", None,time_tagging.digital(times, single_integration_time, counts))
                                assign(total_counts,total_counts + counts)
                        save(total_counts, counts_st)
                        assign(meas_idx, meas_idx + 1)
                        save(meas_idx, meas_idx_st)

            with stream_processing():
                meas_idx_st.save("meas_idx_scanLine")
                counts_st.save("counts_scanLine")
                counts_ref_st.save("counts_Ref") # fix
        self.qm, self.job = self.QUA_execute()



    def Common_updateGraph(self, _xLabel="?? [??],", _yLabel="I [kCounts/sec]"):
        try:
            # todo: use this function as general update graph for all experiments
            self.lock.acquire()
            dpg.set_item_label("graphXY",f"{self.exp.name}, iteration = {self.iteration}, tracking_ref = {self.tracking_ref: .1f}, ref Threshold = {self.refSignal: .1f},shuffle = {self.bEnableShuffle}, Tracking = {self.bEnableSignalIntensityCorrection}")
            dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
            if any(self.Y_vec_ref):
                dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
            if self.exp == Experiment.Nuclear_Fast_Rot or self.exp == Experiment.RandomBenchmark:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            if self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY,Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
                dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_resCalculated])
            if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
                #dpg.set_value("Statistical counts", [self.X_vec, self.Y_vec_2])
                pass
            dpg.set_item_label("y_axis", _yLabel)
            dpg.set_item_label("x_axis", _xLabel)
            dpg.fit_axis_data('x_axis')
            dpg.fit_axis_data('y_axis')
            self.lock.release()


        except Exception as e:
            print(f"{e}")
            self.btnStop()

    def generate_x_y_vectors_for_average(self):
        if len(self.scan_frequencies_aggregated) == 0:
            print("One or more input arrays are empty")
            return

        # Use bins from X_vec and ensure they are sorted and unique
        bins = np.array(self.X_vec)
        # bins = np.unique(np.sort(bins))  # Ensure bins are monotonically increasing

        counts_aggregated = np.array(self.scan_counts_aggregated)
        freqs_aggregated = np.array(self.scan_frequencies_aggregated)

        if bins.size == 0 or counts_aggregated.size == 0 or freqs_aggregated.size == 0:
            print("One or more input arrays are empty")
            return

        # Flatten and concatenate the arrays
        flat_freqs = np.concatenate(freqs_aggregated)/1e6
        flat_counts = np.concatenate(counts_aggregated)

        # Initialize Y_vec_ref with NaNs, keeping the same shape as X_vec
        self.Y_vec_ref = np.full(len(bins), np.nan)

        # Align Y_vec_ref with X_vec bins
        for i in range(len(bins)):
            mask = (flat_freqs >= bins[i]) & (flat_freqs < (bins[i + 1] if i + 1 < len(bins) else float('inf')))
            if np.any(mask):  # Ensure there's data in this bin
                self.Y_vec_ref[i] = np.mean(flat_counts[mask])  # Store mean count for this bin

        # Normalizing mean values
        try:
            min_ref = min(self.Y_vec_ref)
            max_ref = max(self.Y_vec_ref)
            max_y = max(self.Y_vec)

            if max_ref == min_ref:
                print("All elements in Y_vec_ref are the same. Normalization cannot be performed.")
                return

            # Normalize Y_vec_ref to the range [0, max(Y_vec)]
            self.Y_vec_ref = [
                (value - min_ref) / (max_ref - min_ref) * max_y for value in self.Y_vec_ref
            ]
            # print("Y_vec_ref normalized successfully.")
        except Exception as e:
            print(f"An error occurred in generate_x_y_vectors_for_average: {e}")

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
        # if not self.simulation:
        self.refSignal = 0
        if self.bEnableSignalIntensityCorrection:  # prepare search maxI thread
            self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
            # Do all the checks here. This includes motor positioning, laser stability and interforometer checks
            # Later those are to be made into buttons

        # verify job has started
        if not self.simulation:
            while not self.job._is_job_running:
                time.sleep(0.1)
            time.sleep(0.1)

        # fetch right parameters
        if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref"], mode="live")
        elif self.exp == Experiment.AWG_FP_SCAN:
            self.results = fetching_tool(self.job, data_list=["counts"], mode="live")
        elif self.exp == Experiment.G2:
            self.results = fetching_tool(self.job, data_list=["g2", "total_counts", "iteration"], mode="live")
        elif self.exp == Experiment.RandomBenchmark:
            #If nothing else get added you can put it in with counter
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "counts_ref2", "iteration", "tracking_ref", "number_order", "reverse_number_order", "counts_square"], mode="live")
        elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
            self.results = fetching_tool(self.job,
                                         data_list=["counts", "counts_ref", "counts_ref2", "resCalculated", "iteration",
                                                    "tracking_ref"], mode="live")
        elif self.exp == Experiment.Nuclear_Fast_Rot:
            self.results = fetching_tool(self.job,
                                         data_list=["counts", "counts_ref", "counts_ref2", "iteration", "tracking_ref"],
                                         mode="live")
        elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            # if not self.simulation:
            self.results = fetching_tool(self.job, data_list=["iteration_list", "times", "counts", "statistics_counts",
                                                              "pulse_type"], mode="live")
            # if self.simulation:
            #     self.job = JobTesting_OPX.MockJob()
            # else:
            #     counts = create_counts_vector(vector_size=96)
            #     self.results = fetching_tool(job = JobTesting_OPX.MockJob(counts), data_list=["counts"], mode="live")
        else:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "iteration", "tracking_ref"], mode="live")

        self.reset_data_val()

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
        dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
        dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

        self.lastTime = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6
        while self.results.is_processing():
            self.GlobalFetchData()

            dpg.set_item_label("series_counts", "counts")
            dpg.set_item_label("series_counts_ref", "counts_ref")

            if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
                try:
                    dpg.set_item_label("graphXY", f"{self.exp.name},  lastVal = {round(self.Y_vec[-1], 2)}")
                    dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                    dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
                    dpg.set_value("series_counts_ref2", [[], []])
                    dpg.set_value("series_res_calcualted", [[], []])
                    dpg.set_item_label("series_counts", "det_1")
                    dpg.set_item_label("series_counts_ref", "det_2")
                    dpg.set_item_label("y_axis", "I [kCounts/sec]")
                    dpg.set_item_label("x_axis", "time [sec]" if self.exp == Experiment.COUNTER else "Frequency [GHz]")
                    dpg.fit_axis_data('x_axis')
                    dpg.fit_axis_data('y_axis')

                    dpg.bind_item_theme("series_counts", "LineYellowTheme")
                    dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                    dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
                    dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

                except:
                    print('Failed updaitng graph')
                # self.Counter_updateGraph()

            if self.exp == Experiment.AWG_FP_SCAN:
                try:
                    dpg.set_item_label("graphXY", f"{self.exp.name},  lastVal = {round(self.Y_vec[-1], 2)}")
                    dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                    dpg.set_item_label("y_axis", "I [kCounts/sec]")
                    dpg.set_item_label("x_axis", "Frequency [GHz]")
                    dpg.fit_axis_data('x_axis')
                    dpg.fit_axis_data('y_axis')

                    dpg.bind_item_theme("series_counts", "LineYellowTheme")
                except:
                    print('Failed updating graph in experiment AWG_FP_SCAN')

            if self.exp == Experiment.ODMR_CW:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.RABI:  # time
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experiment.ODMR_Bfield:  # freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.PULSED_ODMR:  # freq
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
            if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
                # No MOCU since Shai said it is not yet tested
                self.SearchPeakIntensity()
                self.check_srs_stability()
                #self.change_AWG_freq(channel = 1)
                self.Common_updateGraph(_xLabel="times", _yLabel="counts")
            if self.exp == Experiment.G2:
                dpg.set_item_label("graphXY",
                                   f"{self.exp.name}, Iteration = {self.iteration}, Total Counts = {round(self.g2_totalCounts, 0)}, g2 = {np.min(self.Y_vec)/self.Y_vec[0]:.3f}")
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
            if self.exp == Experiment.testCrap:  # freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experiment.NUCLEAR_POL_ESR:  # freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experiment.RandomBenchmark:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="Number of gates")

            if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
                wavelengths = self.HW.wavemeter.measured_wavelength[-30:]
                if len(wavelengths) == 30 and any(
                    sum(wavelengths[i] < wavelengths[i-1] for i in range(j, j+5)) == 5 and
                    sum(wavelengths[i] > wavelengths[i-1] for i in range(j+5, j+10)) == 5
                    for j in range(21) ):
                    self.qm.set_io2_value(True)
                    print("Green repump pulse")

            self.current_time = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6
            if not(self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]) and (self.current_time-self.lastTime)>self.tGetTrackingSignalEveryTime:
                folder = "d:/temp/"
                if not os.path.exists(folder):
                    folder = "c:/temp/"
                    if not os.path.exists(folder):
                        folder = None
                self.btnSave(folder=folder)
                self.lastTime = datetime.now().hour * 3600 + datetime.now().minute * 60 + datetime.now().second + datetime.now().microsecond / 1e6# if self.exp == Experiment.RandomBenchmark:


            if self.StopFetch:
                break
        
    def GlobalFetchData(self):
        self.lock.acquire()

        if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
            self.counter_Signal, self.ref_signal = self.results.fetch_all()
        elif self.exp == Experiment.AWG_FP_SCAN:
            self.counter_signal = self.results.fetch_all()
        elif self.exp == Experiment.G2:
            self.g2Vec, self.g2_totalCounts, self.iteration = self.results.fetch_all()
        elif self.exp == Experiment.RandomBenchmark:
            self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal, self.number_order, self.reverse_number_order, self.signal_squared = self.results.fetch_all()  # grab/fetch new data from stream
        elif self.exp in [Experiment.POPULATION_GATE_TOMOGRAPHY, Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY]:
            self.signal, self.ref_signal, self.ref_signal2, self.resCalculated, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
        elif self.exp == Experiment.Nuclear_Fast_Rot:
            self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
        elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            self.iteration_list, self.times_of_signal, self.signal, self.statistics_signal, self.type_of_pulse = self.results.fetch_all()
        else:
            self.signal, self.ref_signal, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream

        if self.exp == Experiment.COUNTER:
            if len(self.X_vec) > self.NumOfPoints:
                self.Y_vec = self.Y_vec[-self.NumOfPoints:]  # get last NumOfPoint elements from end
                self.Y_vec_ref = self.Y_vec_ref[-self.NumOfPoints:]  # get last NumOfPoint elements from end
                self.X_vec = self.X_vec[-self.NumOfPoints:]

            self.Y_vec.append(
                self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            self.Y_vec_ref.append(
                self.ref_signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            self.X_vec.append(self.counter_Signal[1] / self.u.s)  # Convert timestamps to seconds

        if self.exp == Experiment.AWG_FP_SCAN:
            new_data = list(np.array(self.counter_signal[0]) / self.total_integration_time)
            if not self.Y_vec == new_data:
                self.X_vec = list(np.linspace(0, 10, 200)) + list(np.linspace(10, 20, 200))
                self.Y_vec_aggregated.extend(new_data)
                self.Y_vec = new_data

        if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
            if len(self.X_vec) > self.NumOfPoints:
                data_to_save = {"Frequency[GHz]": self.X_vec,"Intensity[KCounts/sec]":self.Y_vec, "Resonant Laser Power Reading [V]": self.Y_vec_ref}
                self.save_to_cvs(file_name = self.csv_file, data = data_to_save,to_append= True)
                print(f"Saved data to {self.csv_file}.")
                self.Y_vec = []  # get last NumOfPoint elements from end
                self.Y_vec_ref = []  # get last NumOfPoint elements from end
                self.X_vec = []

            self.Y_vec.append(self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            if self.HW.arduino:
                with self.HW.arduino.lock:
                    self.Y_vec_ref.append(self.HW.arduino.last_measured_value)  # counts/second
            with self.HW.wavemeter.lock:
                y1 = self.HW.wavemeter.measured_wavelength[-2]
                y2 = self.HW.wavemeter.measured_wavelength[-1]
                dx1 = self.HW.wavemeter.measurement_times[-1] - self.HW.wavemeter.measurement_times[-2] # time interval for frequency measurements
                dx2 = time.time() - self.HW.wavemeter.measurement_times[-1]
                # TODO: Fix wrong values at frequency turning points
            self.X_vec.append(y2 + (y2 - y1) * dx2 / dx1) # Linear extrapolation from last point.

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

        if self.exp == Experiment.ODMR_Bfield:  # freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.PULSED_ODMR:  # freq
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
            self.X_vec = self.scan_param_vec / float(1e9) + self.mw_freq  # [GHz]
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

        if self.exp == Experiment.Nuclear_Fast_Rot:  # time
            self.X_vec = [e for e in self.rf_Pwr_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.POPULATION_GATE_TOMOGRAPHY:  # todo: convert graph to bars instead of line
            self.X_vec = self.idx_vec_ini  # index
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_resCalculated = self.resCalculated / 1e6
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.ENTANGLEMENT_GATE_TOMOGRAPHY:  # todo: convert graph to bars instead of line
            self.X_vec = self.idx_vec_ini  # index
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_resCalculated = self.resCalculated / 1e6
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.G2:
            self.X_vec = self.GenVector(-self.correlation_width + 1, self.correlation_width, True)
            self.Y_vec = self.g2Vec  # *self.iteration

        if self.exp == Experiment.RandomBenchmark:
            # Add Y^2 and first measure order and reverse
            self.X_vec = [e for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal/ (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.ref_signal/ (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.benchmark_number_order = self.number_order
            self.benchmark_reverse_number_order = self.reverse_number_order
            self.Y_vec_squared = self.signal_squared/ ((self.TcounterPulsed * 1e-9)*(self.TcounterPulsed * 1e-9)) / 1e6
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experiment.testCrap:  # freq or time oe something else
            ## todo add switch per test for correct normalization
            # if self.test_type == Experiment.test_electron_spinMeasure:
            #     self.X_vec = self.scan_param_vec * 4
            #     if self.iteration == 0:
            #         self.Y_vec = np.array(self.signal)/np.array(self.scan_param_vec)/1e-9/1e3
            #         self.Y_vec_ref = ((self.iteration)*self.Y_vec_ref + np.array(self.ref_signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
            #     elif self.iteration > 0:
            #         self.Y_vec = ((self.iteration)*self.Y_vec + np.array(self.signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
            #         self.Y_vec_ref = ((self.iteration)*self.Y_vec_ref + np.array(self.ref_signal)/np.array(self.scan_param_vec)/1e-9/1e3)/(self.iteration+1)
            #     self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
            # else:
            self.X_vec = self.scan_param_vec * 4 # [nsec]/ float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = np.array(self.signal)/np.array(self.scan_param_vec)/1e-9/1e3 # [kcounts] # / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = np.array(self.ref_signal)/np.array(self.scan_param_vec)/1e-9/1e3 #
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)


        if self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
            print(4)
            offset = 0
            all_times = []
            counts_vector = np.ones(np.size(self.signal))
            self.awg_freq_list = self.repeat_elements(self.awg_freq_list,self.n_avg)
            self.counts_in_bin1 = []
            self.counts_in_bin2 = []
            self.counts_in_bin3 = []
            for i in range(np.size(self.type_of_pulse)):
                if self.type_of_pulse is not None:
                    if self.type_of_pulse[i] == 4:
                        self.list_of_pulse_type.append("xPulse_Pi")
                    elif self.type_of_pulse[i] == 3:
                        self.list_of_pulse_type.append("yPulse_Pi")
                    elif self.type_of_pulse[i] == 2:
                        self.list_of_pulse_type.append("xPulse_Pi_Half")
                    elif self.type_of_pulse[i] == 1:
                        self.list_of_pulse_type.append("yPulse_Pi_Half")
                else:
                    self.list_of_pulse_type.append("Simulation")
            for counts in self.signal:
                if counts > 0:
                    relevant_times = self.times_of_signal[offset: offset + counts]
                    self.times_by_measurement.append(relevant_times)
                    offset += counts
                else:
                    self.times_by_measurement.append([])

            for time_tag in self.times_by_measurement:
                # Timing is according to the blinking in the measure command
                # The timing needs to be parametrized somehow
                time_tag = np.array(time_tag)
                bin1_count = np.sum((time_tag >= self.bin_times[0][0]) & (time_tag < self.bin_times[0][1]))
                bin2_count = np.sum((time_tag >= self.bin_times[1][0]) & (time_tag < self.bin_times[1][1]))
                bin3_count = np.sum((time_tag >= self.bin_times[2][0]) & (time_tag < self.bin_times[2][1]))

                self.counts_in_bin1.append(bin1_count)
                self.counts_in_bin2.append(bin2_count)
                self.counts_in_bin3.append(bin3_count)

                all_times.extend(time_tag)

            time_counter = Counter(all_times)
            # sorted_times = sorted(time_counter.keys())
            # sorted_counts = [time_counter[t] for t in sorted_times]
            times = np.arange(0, self.bin_times[2][1], 1)
            counts = np.zeros(len(times), dtype=int)
            for i, t in enumerate(times):
                if t in time_counter:
                    counts[i] = time_counter[t]
            #self.exact_counts_all_times = dict(time_counter) #Times: counts
            self.X_vec = times.tolist()
            self.Y_vec = counts.tolist()
            self.Y_vec_2 = self.statistics_signal
        self.lock.release()

    def btnStartG2(self):
        self.exp = Experiment.G2
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartEilons(self):
        self.exp = Experiment.testCrap
        self.test_type = Experiment.test_electron_spinPump # add comobox
        self.test_type = Experiment.test_electron_spinMeasure # add comobox
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        if self.test_type == Experiment.test_electron_spinPump:
            # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
            # self.mwModule.Set_freq(self.mw_freq)
            # self.mwModule.Set_power(self.mw_Pwr)
            # self.mwModule.Set_IQ_mode_ON()
            # self.mwModule.Set_PulseModulation_ON()
            # if not self.bEnableSimulate:
            #     self.mwModule.Turn_RF_ON()
            pass
        if self.test_type == Experiment.test_electron_spinMeasure:
            pass


        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def StartFetch(self, _target):
        self.to_xml()  # write class parameters to XML
        self.timeStamp = self.getCurrentTimeStamp()

        self.StopFetch = False
        self.fetchTh = threading.Thread(target=_target)
        self.fetchTh.start()

    def repeat_elements(self, lst, k):
        return [item for item in lst for _ in range(k)]

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
        if not self.bEnableSimulate and not self.mwModule.simulation:
            self.mwModule.Set_freq(self.mw_freq_resonance)
            self.mwModule.Set_power(self.mw_Pwr)
            self.mwModule.Set_IQ_mode_ON()
            # self.mwModule.Set_IQ_mode_OFF()
            self.mwModule.Set_PulseModulation_ON()
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

    def btnStartRandomBenchmark(self):
        self.exp = Experiment.RandomBenchmark
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)
        print("reached button callback")
        if self.mwModule is not None:
            self.mwModule.Set_freq(self.mw_freq_resonance)
            self.mwModule.Set_power(self.mw_Pwr)
            self.mwModule.Set_IQ_mode_OFF()
            self.mwModule.Set_PulseModulation_ON()
            if not self.bEnableSimulate:
                self.mwModule.Turn_RF_ON()

        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)
            #self.FetchData()

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

    def btnStartTimeBinEntanglement(self):
        self.exp = Experiment.TIME_BIN_ENTANGLEMENT
        if self.simulation:
            self.qmm = QuantumMachinesManager(host=self.HW.config.opx_ip, cluster_name=self.HW.config.opx_cluster,
                                              timeout=60)  # in seconds
            time.sleep(1)
            self.close_qm_jobs()
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        # self.mw_freq = self.mw_freq_resonance-0.001 # [GHz]
        # self.mwModule.Set_freq(self.mw_freq)
        # self.mwModule.Set_power(self.mw_Pwr)
        # self.mwModule.Set_IQ_mode_ON()
        # self.mwModule.Set_PulseModulation_ON()
        # if not self.bEnableSimulate:
        #     self.mwModule.Turn_RF_ON()
        # calculates the count based on division due to timing limitaiton of the counter
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms) / int(self.Tcounter * self.u.ns))

        if not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)
            print("Fetching Data")

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
        if self.mwModule is not None:
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
        newQM = self.qmm.list_open_qms()
        print(f"after close: {newQM}")
        return report

    def stop_benchmark(self):
        self.stopScan = True
        self.StopFetch = True

        self.btnSave()

    def btnStop(self):  # Stop Exp
        try:
            # todo: creat methode that handle OPX close job and instances
            self.stopScan = True
            self.StopFetch = True
            if not self.exp == Experiment.SCAN:
                if hasattr(self, 'MAxSignalTh') and self.bEnableSignalIntensityCorrection:
                    if self.MAxSignalTh.is_alive():
                        self.MAxSignalTh.join()
            else:
                dpg.set_item_label("btnOPX_StartScan", "Start Scan")
                dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")

            self.GUI_ParametersControl(True)

            if not self.exp == Experiment.SCAN:
                if hasattr(self, 'fetchTh'):
                    if (self.fetchTh.is_alive()):
                        self.fetchTh.join()
            else:
                dpg.enable_item("btnOPX_StartScan")

            if not self.simulation and self.job:
                self.StopJob(self.job, self.qm)

            if self.exp == Experiment.COUNTER or self.exp == Experiment.SCAN:
                pass
            else:
                if hasattr(self.mwModule, 'RFstate'):
                    self.mwModule.Get_RF_state()
                    if self.mwModule.RFstate:
                        self.mwModule.Turn_RF_OFF()

            if self.exp not in [Experiment.COUNTER, Experiment.SCAN, Experiment.PLE, Experiment.EXTERNAL_FREQUENCY_SCAN]:
                self.btnSave()
            if self.exp == Experiment.EXTERNAL_FREQUENCY_SCAN:
                data_to_save = {"Frequency[GHz]": self.X_vec, "Intensity[KCounts/sec]": self.Y_vec,
                                "Resonant Laser Power Reading [V]": self.Y_vec_ref}
                self.save_to_cvs(file_name=self.csv_file, data=data_to_save, to_append=True)
                print(f"Saved data to {self.csv_file}.")
                print('Scan finished. Copying files.')
                folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + '/'
                destination_csv = os.path.join(folder_path, os.path.basename(self.csv_file))
                print(f"Copying file {self.csv_file} to {destination_csv}.")
                shutil.copy(self.csv_file, destination_csv)


        except Exception as e:
            print(f"An error occurred in btnStop: {e}")

    def btnSave(self, folder=None):  # save data
        print("Saving data...")
        try:
            # file name
            # timeStamp = self.getCurrentTimeStamp()  # get current time stamp
            self.timeStamp = self.getCurrentTimeStamp()

            if folder is None:
                folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + '/'
            else:
                folder_path = folder + self.exp.name + '/'
            if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
                os.makedirs(folder_path)
            if self.exp == Experiment.RandomBenchmark:
                #self.added_comments = dpg.get_value("inTxtOPX_expText")
                if self.added_comments is not None:
                    fileName = os.path.join(folder_path, self.timeStamp + self.exp.name + '_' + self.added_comments)
                else:
                    fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)
            else:
                fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)

            # parameters + note        
            self.writeParametersToXML(fileName + ".xml")
            print(f'XML file saved to {fileName}.xml')

            # raw data
            if self.exp == Experiment.RandomBenchmark:
                RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y_ref2': self.Y_vec_ref2, 'Y_squared': self.Y_vec_squared,'Gate_Order': self.benchmark_number_order, 'Reverse_Gate_order': self.benchmark_reverse_number_order}
            elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
                # Modify below to have some pre-post-processed data for further data analysis
                if self.simulation:
                    RawData_to_save = {'Iteration': self.iteration_list.tolist(), 'Times': self.times_by_measurement,
                                       'Total_Counts': self.signal.tolist(),
                                       'Counts_stat': self.Y_vec_2.tolist(), f'Counts_Bin_1_{self.bin_times[0][0]}:{self.bin_times[0][1]}': self.counts_in_bin1,
                                       f'Counts_Bin_2_{self.bin_times[1][0]}:{self.bin_times[1][1]}': self.counts_in_bin2, f'Counts_Bin_3_{self.bin_times[2][0]}:{self.bin_times[2][1]}': self.counts_in_bin3,
                                       'Pulse_type': self.list_of_pulse_type, 'awg_freq': self.awg_freq_list}
                else:
                    RawData_to_save = {'Iteration': self.iteration_list.tolist(), 'Times': self.times_by_measurement,
                                       'Total_Counts': self.signal.tolist(),
                                       'Counts_stat': self.Y_vec_2.tolist(),
                                       f'Counts_Bin_1_{self.bin_times[0][0]}:{self.bin_times[0][1]}': self.counts_in_bin1,
                                       f'Counts_Bin_2_{self.bin_times[1][0]}:{self.bin_times[1][1]}': self.counts_in_bin2,
                                       f'Counts_Bin_3_{self.bin_times[2][0]}:{self.bin_times[2][1]}': self.counts_in_bin3,
                                       'Pulse_type': self.list_of_pulse_type}
            else:
                RawData_to_save = {
                    'X': self.X_vec if isinstance(self.X_vec, list) else list(self.X_vec),
                    'Y': self.Y_vec if isinstance(self.Y_vec, list) else list(self.Y_vec),
                    'Y_ref': self.Y_vec_ref if isinstance(self.Y_vec_ref, list) else list(self.Y_vec_ref),
                    'Y_ref2': self.Y_vec_ref2 if isinstance(self.Y_vec_ref2, list) else list(self.Y_vec_ref2),
                    'Y_resCalc': self.Y_resCalculated if isinstance(self.Y_resCalculated, list) else list(self.Y_resCalculated)
                }

            self.save_to_cvs(fileName + ".csv", RawData_to_save, to_append=True)
            if self.exp == Experiment.AWG_FP_SCAN:
                RawData_to_save['Y_Aggregated'] = self.Y_vec_aggregated

            self.save_to_cvs(fileName + ".csv", RawData_to_save)
            print(f"CSV file saved to {fileName}.csv")

            # save data as image (using matplotlib)
            if folder is None and self.exp != Experiment.TIME_BIN_ENTANGLEMENT:
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
            self.error = (
                "Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))  # raise
            print(f"Error while saving data: {ex}")

    def btnStartScan(self):
        self.ScanTh = threading.Thread(target=self.StartScan)
        self.ScanTh.start()

    def btnAutoFocus(self):
        self.ScanTh = threading.Thread(target=self.auto_focus)
        self.ScanTh.start()

    def btnStartPLE(self):
        self.ScanTh = threading.Thread(target=self.StartPLE)
        self.ScanTh.start()

    def btnStartExternalFrequencyScan(self, b_startFetch=True):
        self.exp = Experiment.EXTERNAL_FREQUENCY_SCAN
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.timeStamp = self.getCurrentTimeStamp()
        folder_path = 'C:/temp/' + self.exp.name + '/'
        if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
            os.makedirs(folder_path)
        self.csv_file = os.path.join(folder_path, self.timeStamp + self.exp.name + ".csv")
        # TODO: Boaz - Check for edge cases in number of measurements per array
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                         num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

        if b_startFetch and not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def btnStartAWG_FP_SCAN(self, b_startFetch=True):
        self.exp = Experiment.AWG_FP_SCAN
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.timeStamp = self.getCurrentTimeStamp()
        folder_path = 'C:/temp/' + self.exp.name + '/'
        if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
            os.makedirs(folder_path)
        self.csv_file = os.path.join(folder_path, self.timeStamp + self.exp.name + ".csv")
        # TODO: Boaz - Check for edge cases in number of measurements per array
        self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                         num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

        if b_startFetch and not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)

    def StartPLE(self):
        self.exp = Experiment.PLE
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        try:
            # Get initial wavelength position in MHz
            scan_device = self.matisse.scan_device
            initial_position = self.matisse.get_wavelength_position(scan_device)
            self.mattise_frequency_offset = self.HW.wavemeter.get_frequency() - initial_position*1e6

        except Exception as e:
            print(f"Failed to retrieve initial wavelength position: {e}")
            return

        check_srs_stability=self.matisse.check_srs_stability
        if self.HW.SRS_PID_list is None and check_srs_stability:
            print('Cannot check SRS stability, device not found.')
            check_srs_stability=False

        num_points = self.matisse.num_scan_points
        half_length = self.matisse.scan_range / 2
        vec = list(
            np.concatenate((np.linspace(initial_position - half_length, initial_position + half_length, num_points),
                            np.linspace(initial_position + half_length, initial_position - half_length, num_points)[
                            1:])))

        self.start_scan_general(move_abs_fn=self.matisse.move_wavelength,
                                read_in_pos_fn=lambda ch: (time.sleep(self.matisse.ple_waiting_time), True)[1],
                                get_positions_fn=self.HW.wavemeter.get_frequency,
                                device_reset_fn=None,
                                x_vec=vec,
                                y_vec=None,
                                z_vec=None,
                                current_experiment=Experiment.PLE,
                                is_not_ple=False,
                                meas_continuously=True,
                                UseDisplayDuring=False,
                                check_srs_stability=check_srs_stability)

    def StartScan(self):
        if self.positioner:
            self.positioner.KeyboardEnabled = False  # TODO: Update the check box in the gui!!
        if self.HW.atto_scanner:

            # Move and read functions for mixed axes control
            def move_axes(channel: int, position: float):
                """
                Set offset voltage for the corresponding axis.
                """
                print(f"Moving channel {channel} to position {position}")
                if channel in [0, 1]:  # X and Y axes: atto_scanner
                    self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
                    time.sleep(10e-3)
                    # actual_voltage = self.HW.atto_scanner.get_output_voltage(self.HW.atto_scanner.channels[channel])
                    # while not np.isclose(actual_voltage, position,0.1):
                    #     self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
                    #     time.sleep(10e-3)
                    #     actual_voltage = self.HW.atto_scanner.get_output_voltage(self.HW.atto_scanner.channels[channel])
                    #     print(f"Actual voltage: {actual_voltage}. Requested voltage: {position}")
                elif channel == 2:  # Z axis: atto_positioner
                    # if self.L_scan[2] > 1e6:
                    self.HW.atto_positioner.MoveABSOLUTE(channel, position)
                    # else:
                    #     self.HW.atto_positioner.set_control_fix_output_voltage(self.HW.atto_positioner.channels[channel],
                    #                                                        int(position))

            def get_positions():
                """
                Get current positions for all three axes.
                """
                x = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[0])  # X axis
                y = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[1])  # Y axis
                z = self.HW.atto_positioner.get_position(2)  # Z axis
                # z = self.HW.atto_positioner.get_control_output_voltage(2)  # Z axis
                # print(f"control voltage: {z}, fixed_offset_voltage: {self.HW.atto_positioner.get_control_output_voltage(2)}")
                return x, y, z

            self.HW.atto_scanner.stop_updates()
            self.HW.atto_positioner.stop_updates()

            self.initial_scan_Location = list(get_positions())
            print(f"Initial scan location: {self.initial_scan_Location}")
            scan_lengths = [self.L_scan[ch] * int(self.b_Scan[ch]) * 1e-3 for ch in range(3)]
            scan_steps = [self.dL_scan[ch] * 1e-3 for ch in range(3)]

            # Extract bounds for axis 0 and 1 from the atto_scanner
            scanner_min = self.HW.atto_scanner.offset_voltage_min
            scanner_max = self.HW.atto_scanner.offset_voltage_max

            # Extract bounds for axis 2 from the atto_positioner
            positioner_min = self.HW.atto_positioner.fix_output_voltage_min
            positioner_max = self.HW.atto_positioner.fix_output_voltage_max

            # Create lower and upper bounds
            lower_bounds = [scanner_min, scanner_min, positioner_min]
            upper_bounds = [scanner_max, scanner_max, positioner_max]

            x_vec, y_vec, z_vec = create_scan_vectors(self.initial_scan_Location,
                                                      scan_lengths, scan_steps,
                                                      (lower_bounds, upper_bounds))
            print(f"x_vec: {x_vec}")
            print(f"y_vec: {y_vec}")
            print(f"z_vec: {z_vec}")
            self.start_scan_general(move_abs_fn=move_axes,
                                    read_in_pos_fn=lambda ch: (time.sleep(self.scan_default_sleep_time), True)[1],
                                    get_positions_fn=get_positions, device_reset_fn=None, x_vec=x_vec, y_vec=y_vec,
                                    z_vec=z_vec, meas_continuously=False)
            self.HW.atto_scanner.start_updates()
            self.HW.atto_positioner.start_updates()
        else:
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
        self.initQUA_gen(n_count=int(auto_focus["int_time_ms"] * self.u.ms / self.Tcounter / self.u.ns),
                         num_measurement_per_array=1)
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
            coordinate.append(
                i * auto_focus["step_um"] * self.positioner.StepsIn1mm * 1e-3 + self.absPos)  # Log axis position
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
                    self.prepare_scan_data()  #max_position_x_scan = self.endLoc[0] * 1e6 + self.dL_scan[0] * 1e3, min_position_x_scan = self.startLoc[0] * 1e6,start_pos=ini_scan_pos)
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

    def start_scan_general(self, move_abs_fn, read_in_pos_fn, get_positions_fn, device_reset_fn, x_vec=None, y_vec=None,
                           z_vec=None, current_experiment=Experiment.SCAN, is_not_ple=True,
                           UseDisplayDuring=True,
                           meas_continuously=False,
                           check_srs_stability=False):
        self.refSignal = 0

        x_vec = x_vec if x_vec else []
        y_vec = y_vec if y_vec else []
        z_vec = z_vec if z_vec else []

        Nx, Ny, Nz = len(x_vec) or 1, len(y_vec) or 1, len(z_vec) or 1
        dim = sum(bool(v) for v in [x_vec, y_vec, z_vec])
        print(f"Starting {dim}D scan: Nx={Nx}, Ny={Ny}, Nz={Nz}")

        start_time = time.time()
        print(f"start_time: {self.format_time(start_time)}")

        self.exp = current_experiment
        self.GUI_ParametersControl(isStart=False)
        self.to_xml()  # Save last params to XML
        self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml")

        # Copy relevant config & image files, if they exist
        try:
            file_mappings = [
                {
                    "src": 'Q:/QT-Quantum_Optic_Lab/expData/Images/Zelux_Last_Image.png',
                    "dest_local": self.create_scan_file_name(local=True) + "_ZELUX.png",
                    "dest_remote": self.create_scan_file_name(local=False) + "_ZELUX.png"
                },
                {
                    "src": 'C:/WC/HotSystem/map_config.txt',
                    "dest_local": self.create_scan_file_name(local=True) + "_map_config.txt",
                    "dest_remote": self.create_scan_file_name(local=False) + "_map_config.txt"
                }
            ]
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
        self.scan_Out = []
        self.scan_intensities = []

        if device_reset_fn:
            device_reset_fn()

        # Disable the “Start Scan” button in the GUI
        if dpg.does_item_exist("btnOPX_StartScan"):
            dpg.disable_item("btnOPX_StartScan")

        # Prepare internal references
        self.X_vec, self.Y_vec, self.Z_vec = [], [], []
        self.Y_vec_ref = []
        self.iteration = 0

        # For original code continuity, store these as internal references
        self.Xv, self.Yv, self.Zv = x_vec, y_vec, z_vec
        self.V_scan = []
        self.initial_scan_Location = []

        # Acquire initial positions (for reference)
        # This can be done via get_positions_fn() or from the device directly.
        expected_axes = 3  # X, Y, Z
        for ax in range(expected_axes):
            read_in_pos_fn(ax)  # Ensure in position
        current_positions = get_positions_fn()
        if isinstance(current_positions, float):
            current_positions = [current_positions]  # Wrap single float in a list
        initial_pos=current_positions
        initial_pos=[round(initial_pos[0] / 1e12, 0)*1e12]
        initial_pos_offset=current_positions[0]-initial_pos[0]

        # Pad with zeros if fewer than expected_axes
        if self.exp == Experiment.PLE:
            self.initial_scan_Location = [x_vec[0]] + [0] * (expected_axes - len(current_positions))
        else:
            self.initial_scan_Location = list(current_positions) + [0] * (expected_axes - len(current_positions))

        # Build scanning arrays for each axis (like original “V_scan” concept)
        self.V_scan = [
            x_vec if x_vec else [self.initial_scan_Location[0]],
            y_vec if y_vec else [self.initial_scan_Location[1]],
            z_vec if z_vec else [self.initial_scan_Location[2]],
        ]

        Nx, Ny, Nz = len(self.V_scan[0]), len(self.V_scan[1]), len(self.V_scan[2])

        # Initialize the 3D array for intensities
        self.scan_intensities = np.zeros((Nx, Ny, Nz), dtype=float)

        # For user reference
        self.scan_data = self.scan_intensities
        self.idx_scan = [0, 0, 0]

        # Start and End for Plot
        self.startLoc = [
            self.V_scan[0][0] if Nx > 1 else self.initial_scan_Location[0],
            self.V_scan[1][0] if Ny > 1 else self.initial_scan_Location[1],
            self.V_scan[2][0] if Nz > 1 else self.initial_scan_Location[2]
        ]
        self.endLoc = [
            self.V_scan[0][-1] if Nx > 1 else self.initial_scan_Location[0],
            self.V_scan[1][-1] if Ny > 1 else self.initial_scan_Location[1],
            self.V_scan[2][-1] if Nz > 1 else self.initial_scan_Location[2]
        ]

        if UseDisplayDuring and is_not_ple:
            self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=self.scan_intensities[:, :, 0], startLoc=self.startLoc,
                           endLoc=self.endLoc)

        # QUA program init (example)
        if not self.simulation:
            if is_not_ple:
                self.initQUA_gen(
                    n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                    num_measurement_per_array=Nx
                )
            else:
                self.initQUA_gen(
                    n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                    num_measurement_per_array=1
                )

            res_handles = getattr(self.job, 'result_handles', None)
            if res_handles is None:
                print("No results")
                self.btnStop()
                return

            self.counts_handle = res_handles.get("counts_scanLine")
            self.ref_counts_handle = res_handles.get("counts_Ref")
            self.meas_idx_handle = res_handles.get("meas_idx_scanLine")

        # Example: offset for X start
        if Nx > 1:
            x_channel = 0
            scanPx_Start = self.V_scan[x_channel][0]  # - (self.dL_scan[x_channel] if self.dL_scan[x_channel] else 0)
            move_abs_fn(x_channel, scanPx_Start)
            time.sleep(0.005)
            read_in_pos_fn(x_channel)

        self.dir = 1
        self.scanFN = self.create_scan_file_name(local=True)
        previousMeas_idx = 0
        meas_idx = 0

        # Z-calibration offset
        z_correction_previous = 0
        z_calibration_offset = 0
        if self.b_Zcorrection and (self.ZCalibrationData is not None):
            # at the origin
            z_correction_origin = calculate_z_series(
                self.ZCalibrationData,
                np.array([self.initial_scan_Location[0]]),
                self.initial_scan_Location[1]
            )[0]
            z_calibration_offset = int(z_correction_origin)

        # Initialize the 3D array for intensities
        self.scan_intensities = np.zeros((Nx, Ny, Nz), dtype=float)
        scan_counts = np.zeros_like(self.scan_intensities)
        self.scan_iterations = 0

        def perform_scan_pass(Nx, Ny, Nz, continuous=False, check_srs_stability=True, ):
            nonlocal z_correction_previous, previousMeas_idx, meas_idx
            # For time estimations
            pass_start_time = time.time()
            current_positions_array = []
            data = []

            self.x_expected=[]
            self.y_expected=[]
            self.z_expected=[]
            for iz in range(Nz):
                if self.stopScan:
                    break
                # Move Z axis if scanning in Z
                if Nz > 1:
                    move_abs_fn(2, self.V_scan[2][iz])
                    read_in_pos_fn(2)
                    self.z_expected = self.V_scan[2][iz]
                else:
                    self.z_expected = -1

                iy = 0
                while iy < Ny:
                    if self.stopScan:
                        break
                    # Move Y axis if scanning in Y
                    if Ny > 1:
                        move_abs_fn(1, self.V_scan[1][iy])
                        read_in_pos_fn(1)
                        self.y_expected = self.V_scan[1][iy]
                    else:
                        self.y_expected = -1

                    # Flip direction for S-shape scanning
                    self.dir *= -1

                    line_start_time = time.time()
                    # X loop
                    current_positions_array=[]
                    counts=[]
                    for ix in range(Nx):
                        if self.stopScan:
                            break

                        # Z correction if needed
                        new_z_pos = self.V_scan[2][iz] if Nz > 1 else self.initial_scan_Location[2]
                        if self.b_Zcorrection and (self.ZCalibrationData is not None):
                            z_correction_new = (
                                    calculate_z_series(
                                        self.ZCalibrationData,
                                        np.array([int(self.V_scan[0][ix])]),
                                        int(self.V_scan[1][iy]) if Ny > 1 else self.initial_scan_Location[1],
                                    )[0]
                                    - z_calibration_offset
                            )

                            if abs(z_correction_new - z_correction_previous) > self.z_correction_threshold:
                                new_z_pos += int(z_correction_new)
                                z_correction_previous = z_correction_new
                                move_abs_fn(2, new_z_pos)
                                read_in_pos_fn(2)
                                self.z_expected = new_z_pos
                            else:
                                new_z_pos += z_correction_previous

                        # Move X
                        move_abs_fn(0, self.V_scan[0][ix])
                        read_in_pos_fn(0)
                        self.x_expected.append(self.V_scan[0][ix])

                        current_positions = get_positions_fn()
                        if is_not_ple:
                            current_positions_array.append(current_positions)
                        else:
                            current_positions_array.append(current_positions - initial_pos[0])
                        self.extract_vectors(current_positions_array)

                        # Ensure SRS stable
                        if self.exp == Experiment.PLE and check_srs_stability and not self.simulation:
                            while not self.HW.SRS_PID_list[0].is_stable:
                                if self.stopScan:
                                    return False
                                print("Waiting for SRS to stabilize")
                                time.sleep(1)

                        if not self.simulation:
                            # Trigger measurement
                            self.qm.set_io2_value(self.ScanTrigger)
                            if self.exp == Experiment.PLE:
                                sleep_time = (self.total_integration_time * 1e-3 + self.Tpump*1e-9) * (self.n_avg+1) + self.Tpump*1e-9 + 6e-3
                            else:
                                sleep_time = (self.total_integration_time * 1e-3 + self.Tpump * 1e-9) + self.Tpump*1e-9 + 1e-3
                            time.sleep(sleep_time)

                        if not is_not_ple: # Only in PLE
                            current_measurement=0
                            if self.simulation:
                                current_measurement=[np.array(float(np.random.randint(1, 1000)))]
                            elif self.counts_handle.is_processing():  # TODO: add count_ref and enable tracking
                                # block until at least 1 data chunk is there
                                self.counts_handle.wait_for_values(1)
                                self.meas_idx_handle.wait_for_values(1)
                                time.sleep(0.1)
                                meas_idx = self.meas_idx_handle.fetch_all()
                                current_measurement=self.counts_handle.fetch_all()
                                self.tracking_ref = self.ref_counts_handle.fetch_all()/5
                                if self.refSignal == 0:
                                    self.refSignal = self.tracking_ref / self.TrackingThreshold
                                self.qmm.clear_all_job_results()

                            current_measurement = current_measurement / int(self.total_integration_time*self.u.ms) *1e9 /1e3 / self.n_avg # [KCounts/s]
                            counts.append(current_measurement) # [counts/s]

                            # Correct mistmatch between wavemeter measurements (actual frequency) and mattise wavenlength
                            # measurement of the contribution of the slow piezo

                            self.Y_vec = [0] * len(self.V_scan[0]) # Initialize Y_vec with zeros

                            for i in range(ix + 1): # Override Y_vec values for i = 0 up to ix with counts
                                self.Y_vec[i] = counts[i] if i < len(counts) else 0

                            self.X_vec=list((np.array(self.V_scan[0][:])*1e6+self.mattise_frequency_offset-initial_pos)/1e6)

                            for i in range(ix + 1): # Override X_vec values for i = 0 up to ix
                                self.X_vec[i] = round(current_positions_array[i] / 1e6, 2)  # Convert to MHz

                            self.generate_x_y_vectors_for_average()
                            self.Common_updateGraph(_xLabel="Frequency[MHz]", _yLabel="I[KCounts/s]")
                            # if type(current_measurement) == int:
                            #     current_measurement=[-1]

                            self.scan_Out.append([current_positions_array[ix],  -1, -1,current_measurement,self.V_scan[0][ix],-1,-1,self.tracking_ref ])
                    # End X loop
                    if self.stopScan:
                        break


                    self.extract_vectors(current_positions_array)
                    # Fetch data from QUA
                    if self.simulation:
                        counts = np.concatenate([
                            create_gaussian_vector(Nx // 2, center=1.5, width=10),
                            create_gaussian_vector(Nx - Nx // 2, center=3.5, width=10)
                        ])
                    elif is_not_ple and self.counts_handle.is_processing():
                        # block until at least 1 data chunk is there
                        self.counts_handle.wait_for_values(1)
                        self.meas_idx_handle.wait_for_values(1)
                        time.sleep(0.1)

                        meas_idx = self.meas_idx_handle.fetch_all()
                        counts = self.counts_handle.fetch_all()

                        self.qmm.clear_all_job_results()


                    if counts is not None:
                        self.scan_counts_aggregated.append(np.squeeze(counts))
                        self.scan_frequencies_aggregated.append(np.squeeze(current_positions_array))
                        if is_not_ple:
                            for i in range(len(self.X_vec)):
                                self.scan_Out.append([self.X_vec[i],  # X coordinate
                                    self.Y_vec[i],  # Y coordinate
                                    self.Z_vec[i],  # Z coordinate
                                    (np.squeeze(counts)[i] / self.total_integration_time),  # Normalized counts
                                    self.x_expected[i],  # Expected X
                                    self.y_expected,  # Expected Y (assumes it's the same for all)
                                    self.z_expected  # Expected Z (assumes it's the same for all)
                                ])

                        # Validate data
                        if type(counts)==list:
                            counts = np.array(counts)

                        if counts.size == Nx:
                            self.scan_intensities[:, iy, iz] = counts / self.total_integration_time

                            if UseDisplayDuring and is_not_ple:
                                self.UpdateGuiDuringScan(self.scan_intensities[:, :, iz], use_fast_rgb=True)
                                self.extract_vectors(current_positions_array)
                            else:
                                self.generate_x_y_vectors_for_average()
                                half_length = len(self.V_scan[0]) // 2  # Assuming symmetric up and down scan
                                self.X_vec = list((np.array(current_positions_array[:half_length]) -
                                                   current_positions_array[0]) * 1e-6)
                                data = self.scan_intensities[:, :, iz]
                                if data.shape[1] == 1:
                                    data = data.squeeze()
                                self.Y_vec = data.tolist()

                                # Split the data into up scan and down scan
                                up_scan_length = len(self.V_scan[0]) // 2  # Assuming symmetric up and down scan
                                self.Y_vec = data[:up_scan_length].tolist()  # Data for up scan
                                self.Y_vec_ref = data[up_scan_length:].tolist()  # Data for down scan
                                self.V_scan[1] = list(range(self.scan_iterations+1))
                                self.Common_updateGraph(_xLabel="Frequency[MHz]", _yLabel="I[counts]")
                                self.Y_vec = list(range(self.scan_iterations + 1))
                                self.Z_vec = list(range(Nz))
                        else:
                            print(
                                "Warning: counts size mismatch. Possibly partial line or measurement error."
                            )
                            return False

                        # Check if line is “complete”
                        save_partial = True
                        if not continuous:
                            if (meas_idx - previousMeas_idx) % (Nx if Nx > 1 else 1) == 0:
                                # Good line: increment
                                iy += 1
                            else:
                                print(
                                    "****** Error: ******\n"
                                    "Number of measurements is not consistent with expected.\n"
                                    "Repeating line..."
                                )
                                # do not increment iy => repeat line
                                save_partial = False
                        else:
                            # If continuous, just move to the next line
                            iy += 1

                        # Save partial data
                        if save_partial:
                            print(f"file : {self.scanFN}.csv")
                            self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.scanFN, to_append=True)

                    # End while over iy
                # End iz loop

            pass_end_time = time.time()
            if not continuous:
                print(f"Pass time: {pass_end_time - pass_start_time:.2f} s")
            previousMeas_idx = meas_idx
            return not self.stopScan  # If we got here, presumably okay

        def prepare_and_save_data(Nx, Ny, Nz):
            self.prepare_scan_data()
            self.save_scan_data(
                Nx=Nx, Ny=Ny, Nz=Nz,
                fileName=self.scanFN,
                to_append=True
            )

        # ----------------------------------------------------------------------
        # Main Scanning Loops
        # ----------------------------------------------------------------------
        self.scan_counts_aggregated = []
        self.scan_frequencies_aggregated = []
        self.scan_Out = []
        if meas_continuously:
            print("Entering infinite averaging mode...")
            while not self.stopScan:
                success = perform_scan_pass(Nx, Ny, Nz, continuous=True, check_srs_stability=check_srs_stability)
                self.scan_iterations += success
                if not success:
                    print("scanning pass is not complete")
        else:
            success = perform_scan_pass(Nx, Ny, Nz, continuous=False, check_srs_stability=check_srs_stability)
            self.scan_iterations += success
            if not success:
                print("Error in scanning pass")
                return

        # ----------------------------------------------------------------------
        # Return to Original Position (Only for Scanned Axes)
        # ----------------------------------------------------------------------
        if x_vec:
            move_abs_fn(0, self.initial_scan_Location[0])  # Move X axis back to initial position
            read_in_pos_fn(0)

        if y_vec:
            move_abs_fn(1, self.initial_scan_Location[1])  # Move Y axis back to initial position
            read_in_pos_fn(1)

        if z_vec:
            move_abs_fn(2, self.initial_scan_Location[2])  # Move Z axis back to initial position
            read_in_pos_fn(2)

        # TODO: If saving doesnt work, try deleting all of the lines below
        # Final save
        # Determine the expected number of columns (length of the longest row)
        max_length = max(len(row) for row in self.scan_frequencies_aggregated)
        self.scan_frequencies_aggregated = np.array(
            [np.pad(row, (0, max_length - len(row)), constant_values=0) for row in self.scan_frequencies_aggregated])
        self.scan_counts_aggregated = np.array(
            [np.pad(row, (0, max_length - len(row)), constant_values=0) for row in self.scan_counts_aggregated])
        self.X_vec = np.array([list(positions) for positions in self.scan_frequencies_aggregated])
        self.scan_intensities = np.array([list(counts) for counts in self.scan_counts_aggregated])[:, :, np.newaxis]

        Nx = self.scan_intensities.shape[0]  # X-axis (number of points per line)
        Ny = self.scan_intensities.shape[1]  # Y-axis (number of lines in the data)
        Nz = 1  # Default Z-axis since no additional layers are specified

        if UseDisplayDuring:
            self.V_scan[1] = list(range(Ny))  # Y dimension represents line indices
            self.V_scan[2] = [0]  # Keep Z dimension as a single layer
            self.Y_vec = list(range(Ny))
            self.Z_vec = list(range(Nz))
            self.prepare_scan_data()
        else:
            self.X_vec = list(np.array(self.scan_frequencies_aggregated).flatten())
            self.Y_vec = list(range(self.scan_iterations))
            self.Z_vec = list(range(Nz))
            self.V_scan[1] = list(range(self.scan_iterations))
            self.scan_intensities = list(np.array(self.scan_counts_aggregated).flatten())
            self.prepare_scan_data()
        # end part to delete if save doesnt work
        fn = self.save_scan_data(Nx=Nx, Ny=Ny, Nz=Nz, fileName=self.create_scan_file_name(local=False))
        self.writeParametersToXML(fn + ".xml")

        end_time = time.time()
        print(f"end_time: {end_time}")
        print(f"number of points = {Nx * Ny * Nz}")
        print(f"Elapsed time: {end_time - start_time} seconds")

        if not self.stopScan:
            self.btnStop()

        return self.scan_intensities

    def prepare_scan_data(self):
        """
        Prepare scan data with actual positions (X_vec, Y_vec, Z_vec), intensities,
        and expected positions derived from V_scan. If actual positions are None,
        they default to expected positions.
        """
        # Create an object to be saved in Excel
        self.scan_Out = []

        # Get dimensions
        Nx, Ny, Nz = len(self.V_scan[0]), len(self.V_scan[1]), len(self.V_scan[2])

        # self.scan_intensities = np.array(self.scan_intensities).flatten().reshape(Nx, Ny, Nz)
        intensities_data = np.array(self.scan_counts_aggregated).flatten().reshape(Nx, -1, Nz)
        Ny = intensities_data.shape[1]
        # Loop over Z, Y, and X scan coordinates
        for i in range(Nz):  # Z dimension
            for j in range(Ny):  # Y dimension
                for k in range(Nx):  # X dimension
                    # Expected positions derived from V_scan
                    x_expected = self.V_scan[0][k]
                    y_expected = self.V_scan[1][j]
                    z_expected = self.V_scan[2][i]

                    # Actual positions
                    x_actual = (self.X_vec[k] if self.X_vec is not None and k < len(self.X_vec) else x_expected)
                    y_actual = (self.Y_vec[j] if self.Y_vec is not None and j < len(self.Y_vec) else y_expected)
                    z_actual = (self.Z_vec[i] if self.Z_vec is not None and i < len(self.Z_vec) else z_expected)

                    # Intensity at the current position
                    intensities = (
                        intensities_data[k, j, i]
                        if intensities_data is not None
                           and k < intensities_data.shape[0]
                           and j < intensities_data.shape[1]
                           and i < intensities_data.shape[2]
                        else 0
                    )

                    # Append data for this point
                    self.scan_Out.append(
                        [x_actual, y_actual, z_actual, intensities, x_expected, y_expected, z_expected])

    def btnUpdateImages(self):
        self.Plot_Loaded_Scan(use_fast_rgb=True)

    def Plot_data(self, data, bLoad=False):
        np_array = np.array(data) #numpy array of the csv data
        # Nx = int(np_array[1,10])
        # Ny = int(np_array[1,11])
        # Nz = int(np_array[1,12])
        allPoints = np_array[0:, 3] #Intensity
        self.Xv = np_array[0:, 4].astype(float) / 1e6 # x data of the Smaract values from the csv
        self.Yv = np_array[0:, 5].astype(float) / 1e6 # y data of the Smaract values from the csv
        self.Zv = np_array[0:, 6].astype(float) / 1e6 # z data of the Smaract values from the csv

        allPoints = allPoints.astype(float)  # intensities
        Nx = int(round((self.Xv[-1] - self.Xv[0]) / (self.Xv[1] - self.Xv[0])) + 1) #Total range divided by step size
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

        if bLoad:
            self.Plot_Loaded_Scan(use_fast_rgb=True)  ### HERE
            print("Done.")
        else:
            self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=np.flipud(res[0, :, :]), startLoc=self.startLoc, endLoc=self.endLoc,
                           switchAxes=bLoad)

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
        if self.HW.atto_scanner:
            return
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
        fn = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])  # Show .csv and all file types
        if fn:  # Check if a file is selected
            data = loadFromCSV(fn)
            self.idx_scan = [0, 0, 0]
            self.Plot_data(data, True)

    def save_scan_data(self, Nx, Ny, Nz, fileName=None, to_append: bool = False):
        if fileName == None:
            fileName = self.create_scan_file_name()

        # parameters + note --- cause crash during scan. no need to update every slice.
        # self.writeParametersToXML(fileName + ".xml")

        # raw data
        Scan_array = np.array(self.scan_Out)
        if to_append:
            RawData_to_save = {'X': Scan_array[-Nx:, 0].tolist(), 'Y': Scan_array[-Nx:, 1].tolist(),
                               'Z': Scan_array[-Nx:, 2].tolist(),
                               'Intensity': Scan_array[-Nx:, 3].tolist(), 'Xexpected': Scan_array[-Nx:, 4].tolist(),
                               'Yexpected': Scan_array[-Nx:, 5].tolist(),
                               'Zexpected': Scan_array[-Nx:, 6].tolist(), }
            if np.shape(Scan_array)[1] > 7:
                RawData_to_save['Ref_signal'] = Scan_array[-Nx:, 7].tolist()
        else:
            RawData_to_save = {'X': Scan_array[:, 0].tolist(), 'Y': Scan_array[:, 1].tolist(),
                               'Z': Scan_array[:, 2].tolist(),
                               'Intensity': Scan_array[:, 3].tolist(), 'Xexpected': Scan_array[:, 4].tolist(),
                               'Yexpected': Scan_array[:, 5].tolist(),
                               'Zexpected': Scan_array[:, 6].tolist(), }

        self.save_to_cvs(fileName + ".csv", RawData_to_save, to_append)

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
            self.idx_scan = [Nz - 1, 0, 0]

            self.startLoc = [Scan_array[1, 4] / 1e6, Scan_array[1, 5] / 1e6, Scan_array[1, 6] / 1e6]
            if Nz == 0:
                self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3,
                               self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3, 0]
            else:
                self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3,
                               self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3,
                               self.startLoc[2] + self.dL_scan[2] * (Nz - 1) / 1e3]

            # self.Plot_Scan()

        return fileName

    def create_scan_file_name(self, local=False):
        # file name
        timeStamp = self.getCurrentTimeStamp()  # get current time stamp
        if local:
            folder_path = "C:/temp/TempScanData/"
        else:
            folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/scan/{self.HW.config.system_type}'
        if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
            try:
                os.makedirs(folder_path)
            except FileNotFoundError as ex:
                print(f"An error occurd when trying to create {folder_path}")
                print("Saving to local folder instead.")
                return self.create_scan_file_name(local=True)
        fileName = os.path.join(folder_path, f"{timeStamp}_{self.exp.name}_{self.expNotes}")
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
        print('Start looking for peak intensity using atto_positioner_and_scanner')

        # Move and read functions for mixed axes control
        def move_axes(channel: int, position: float):
            """
            Set offset voltage for the corresponding axis.
            """
            if channel in [0, 1]:  # X and Y axes: atto_scanner
                self.HW.atto_scanner.set_offset_voltage(self.HW.atto_scanner.channels[channel], position)
            # elif channel == 2:  # Z axis: atto_positioner
            #     self.HW.atto_positioner.set_control_fix_output_voltage(self.HW.atto_positioner.channels[channel],
            #                                                            int(position))

        def get_positions():
            """
            Get current positions for all three axes.
            """
            x = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[0])  # X axis
            y = self.HW.atto_scanner.get_offset_voltage(self.HW.atto_scanner.channels[1])  # Y axis
            # z = self.HW.atto_positioner.get_control_fix_output_voltage(2)  # Z axis
            # return x, y, z
            return x, y

        # Example scan radii for each axis
        # tracking_scan_radius = [2.5, 2.5, 10000]
        tracking_scan_radius = [10, 10]

        initial_guess = get_positions()
        bounds = self.calculate_tracking_bounds(initial_guess, tracking_scan_radius)

        # Call the generalized find_max_signal function
        x_opt, y_opt, z_opt, intensity = find_max_signal(
            move_abs_fn=move_axes,
            read_in_pos_fn=lambda ch: (time.sleep(30e-3), True)[1],  # Ensure move has settled
            get_positions_fn=get_positions,
            fetch_data_fn=self.GlobalFetchData,  # Function to fetch new data
            get_signal_fn=lambda: self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref,
            # Signal to maximize
            bounds=bounds,
            method=OptimizerMethod.DIRECTIONAL,
            initial_guess=initial_guess,
            max_iter=30,
            use_coarse_scan=True
        )

        # Reset the output state or finalize settings
        self.qm.set_io1_value(0)

        print(
            f"Optimal position found: x={x_opt:.2f} mV, y={y_opt:.2f} mV, z={z_opt:.2f} mV with intensity={intensity:.4f}"
        )

    def calculate_tracking_bounds(self, initial_guess, scan_radius):
        # Check if initial_guess is XY (2 elements) or XYZ (3 elements)
        if len(initial_guess) == 2:
            # For XY case, z_guess and scan_radius for z are not used
            x_guess, y_guess = initial_guess
            z_guess = 0  # Default to 0 for z in XY mode
            scan_radius.append(0)  # Append 0 to the scan_radius for z-axis (not used)
        elif len(initial_guess) == 3:
            # For XYZ case, all values are used
            x_guess, y_guess, z_guess = initial_guess
        else:
            raise ValueError("initial_guess must have either 2 (XY) or 3 (XYZ) elements.")

        # Clip around each axis with respective scan radii
        x_bounds = (
            np.clip(x_guess - scan_radius[0], self.HW.atto_scanner.offset_voltage_min,
                    self.HW.atto_scanner.offset_voltage_max),
            np.clip(x_guess + scan_radius[0], self.HW.atto_scanner.offset_voltage_min,
                    self.HW.atto_scanner.offset_voltage_max),
        )
        y_bounds = (
            np.clip(y_guess - scan_radius[1], self.HW.atto_scanner.offset_voltage_min,
                    self.HW.atto_scanner.offset_voltage_max),
            np.clip(y_guess + scan_radius[1], self.HW.atto_scanner.offset_voltage_min,
                    self.HW.atto_scanner.offset_voltage_max),
        )
        # Only include z_bounds if it's an XYZ case
        if len(initial_guess) == 3:
            z_bounds = (
                np.clip(z_guess - scan_radius[2], self.HW.atto_positioner.fix_output_voltage_min,
                        self.HW.atto_positioner.fix_output_voltage_max),
                np.clip(z_guess + scan_radius[2], self.HW.atto_positioner.fix_output_voltage_min,
                        self.HW.atto_positioner.fix_output_voltage_max),
            )
            bounds = (x_bounds, y_bounds, z_bounds)
        else:
            bounds = (x_bounds, y_bounds)

        print(f"Bounds are: {bounds}")
        return bounds

    def FindMaxSignal_atto_positioner(self):

        print('Start looking for peak intensity using atto_positioner')
        initial_position = [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in
                            self.HW.atto_positioner.channels]

        bounds = ((self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
                  (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max),
                  (self.HW.atto_positioner.fix_output_voltage_min, self.HW.atto_positioner.fix_output_voltage_max))

        # Now we call our generalized FindMaxSignal function with these parameters

        x_opt, y_opt, z_opt, intensity = find_max_signal(
            move_abs_fn=self.HW.atto_positioner.set_control_fix_output_voltage,
            read_in_pos_fn=lambda ch: (time.sleep(30e-3), True)[1],
            get_positions_fn=lambda: [self.HW.atto_positioner.get_control_fix_output_voltage(ch) for ch in
                                      self.HW.atto_positioner.channels],
            fetch_data_fn=self.GlobalFetchData,
            get_signal_fn=lambda: self.counter_Signal[0] if self.exp == Experiment.COUNTER else self.tracking_ref,
            bounds=bounds,
            method=OptimizerMethod.DIRECTIONAL,
            initial_guess=initial_position,
            max_iter=30,
            use_coarse_scan=True
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
            print(f"self.HW.atto_scanner is {self.HW.atto_scanner}")
            print(f"self.HW.atto_positioner is {self.HW.atto_positioner}")
            if self.HW.atto_scanner or self.HW.atto_positioner:
                print("Working in Atto system")
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

    def check_srs_stability(self):
        if self.bEnableSignalIntensityCorrection:
            while not self.HW.SRS_PID_list[0].is_stable:
                if self.stopScan:
                    return False
                print("Waiting for SRS to stabilize")
                time.sleep(1)

    def change_AWG_freq(self, channel):
        # Get the current time
        if not self.simulation:
            current_time = time.time()

            # Initialize last_change_time if it doesn't exist yet.
            if not hasattr(self, 'last_change_time'):
                self.last_change_time = current_time

            # Check if enough time has passed since the last change.
            if current_time - self.last_change_time >= self.AWG_interval:
                # Toggle the frequency based on the current value.
                if self.current_awg_freq == self.AWG_f_1:
                    self.awg.set_frequency(self.AWG_f_2, channel)
                elif self.current_awg_freq == self.AWG_f_2:
                    self.awg.set_frequency(self.AWG_f_1, channel)

                # Update the current frequency by reading it back.
                self.current_awg_freq = self.awg.get_frequency()

                # Update the last change time.
                self.last_change_time = current_time
        else:
            current_time = time.time()
            if not hasattr(self, 'last_change_time'):
                self.last_change_time = current_time
            if current_time - self.last_change_time >= 0.00001:
                self.current_awg_freq = 5
                if self.current_awg_freq == 5:
                    self.current_awg_freq = 7
                elif self.current_awg_freq == 7:
                    self.current_awg_freq = 5
                self.awg_freq_list.append(self.current_awg_freq)
            #self.job.push_to_input_stream('awg_freq', self.current_awg_freq)
            print("Passed change_AWG_freq successfully")

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
        return str(now.year) + "_" + str(now.month) + "_" + str(now.day) + "_" + str(now.hour) + "_" + str(
            now.minute) + "_" + str(now.second)

    def saveExperimentsNotes(self, appdata, sender):
        # dpg.set_value("text item", f"Mouse Button ID: {app_data}")
        self.expNotes = sender
        self.HW.camera.imageNotes = sender
        if self.added_comments is not None:
            self.added_comments = sender

    def save_to_cvs(self, file_name, data, to_append: bool = False):
        print("Starting to save data to CSV.")


        # Ensure data is a dictionary
        if not isinstance(data, dict) or not all(isinstance(v, list) for v in data.values()):
            raise ValueError("Data must be a dictionary with list-like values.")

        # Find the length of the longest list
        max_length = max(len(values) for values in data.values())

        # Pad shorter lists with None
        for key in data:
            while len(data[key]) < max_length:
                data[key].append(None)

        # Check if file exists (to avoid rewriting headers when appending)
        file_exists = os.path.exists(file_name)

        try:
            # Open the file in append or write mode
            with open(file_name, mode='a' if to_append else 'w', newline='') as file:
                writer = csv.writer(file)

                # Write headers if not appending or file doesn't exist
                if not to_append or not file_exists:
                    print("Writing headers...")
                    writer.writerow(data.keys())

                # Write data rows
                print("Preparing to write rows...")
                zipped_rows = list(zip(*data.values()))
                print(f"Number of rows to write: {len(zipped_rows)}")

                writer.writerows(zipped_rows)
                print("Rows written successfully.")

            print(f"Data successfully saved to {file_name}.")

        except Exception as e:
            # Log the error with a timestamp
            error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{error_time}] Error while writing to '{file_name}': {e}")

            # Fallback: Save to a new file location
            self.scanFN = self.create_scan_file_name(local=True)
            try:
                print(f"Attempting to save to fallback location: {self.scanFN}")
                with open(self.scanFN, mode='w', newline='') as fallback_file:
                    writer = csv.writer(fallback_file)
                    writer.writerow(data.keys())
                    writer.writerows(zip(*data.values()))
                print(f"Data successfully saved to fallback location: {self.scanFN}")
            except Exception as fallback_error:
                fallback_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                print(
                    f"[{fallback_time}] Critical error: Unable to save data to fallback location. Error: {fallback_error}")

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
                if (list_elem.tag not in ["scan_Out", "X_vec", "Y_vec", "Z_vec", "X_vec_ref", "Y_vec_ref", "Z_vec_ref",
                                          "V_scan", "expected_pos", "t_vec",
                                          "startLoc", "endLoc", "Xv", "Yv", "Zv", "viewport_width", "viewport_height",
                                          "window_scale_factor",
                                          "timeStamp", "counter", "maintain_aspect_ratio", "scan_intensities",
                                          "initial_scan_Location", "V_scan",
                                          "absPosunits", "Scan_intensity", "Scan_matrix", "image_path", "f_vec",
                                          "signal", "ref_signal", "tracking_ref", "t_vec", "t_vec_ini"]
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
                            converted_item = self.convert_to_correct_type(attribute=param.tag, value=item.text,
                                                                          idx=counter)
                            list_items.append(converted_item)
                            counter += 1
                        setattr(self, param.tag,
                                list_items if isinstance(getattr(self, param.tag), list) else np.array(list_items))
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

    def extract_vectors(self, current_positions_array: List[Union[float, Tuple[float, ...]]]) -> None:
        """
        Extract X, Y, Z vectors from an array of N-dimensional tuples (up to 3 dimensions)
        or floats (treated as X coordinates with Y and Z set to 0).

        :param current_positions_array: A list containing floats or tuples,
                                        each containing up to 3 coordinates (x, y, z).
        """
        # Initialize empty lists
        self.X_vec, self.Y_vec, self.Z_vec = [], [], []

        for pos in current_positions_array:
            if isinstance(pos, float):  # If pos is a float, treat it as an X coordinate
                self.X_vec.append(pos)
                self.Y_vec.append(0.0)  # Append 0 for missing Y
                self.Z_vec.append(0.0)  # Append 0 for missing Z
            elif isinstance(pos, tuple):  # If pos is a tuple, process it as coordinates
                if len(pos) > 0:  # X coordinate exists
                    self.X_vec.append(pos[0])
                else:
                    self.X_vec.append(0.0)
                if len(pos) > 1:  # Y coordinate exists
                    self.Y_vec.append(pos[1])
                else:
                    self.Y_vec.append(0.0)
                if len(pos) > 2:  # Z coordinate exists
                    self.Z_vec.append(pos[2])
                else:
                    self.Z_vec.append(0.0)
            else:
                raise TypeError(f"Invalid type in current_positions_array: {type(pos)}")

        # Convert empty lists to None if a dimension is missing (optional)
        self.X_vec = self.X_vec if self.X_vec else 0
        self.Y_vec = self.Y_vec if self.Y_vec else 0
        self.Z_vec = self.Z_vec if self.Z_vec else 0

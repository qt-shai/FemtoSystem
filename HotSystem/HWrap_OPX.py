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
from typing import Union, Optional, Callable, List, Tuple, Any

import dearpygui.dearpygui as dpg
import glfw
import matplotlib
import numpy as np
from collections import Counter
import json

from qm.jobs.base_job import QmBaseJob
from qm.qua._expressions import QuaVariable, QuaVariableType
#from qm_saas import QmSaas, QoPVersion
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig, QuantumMachine, QmJob, QmPendingJob
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, assign, \
    elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger, counting, Math, Cast, case_, \
    switch_, strict_timing_, declare_input_stream
from gevent.libev.corecext import callback
from matplotlib import pyplot as plt
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from qualang_tools.results import fetching_tool
from qualang_tools.results import progress_counter, fetching_tool
from functools import partial
from qualang_tools.units import unit

import SystemConfig as configs
from Common import WindowNames
from Common import load_window_positions
from Common import toggle_sc

from HW_GUI.GUI_map import Map
from HW_wrapper import HW_devices as hw_devices, smaractMCS2
from SystemConfig import SystemType
from Utils import OptimizerMethod, find_max_signal
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized, create_scan_vectors, loadFromCSV, \
    open_file_dialog, create_gaussian_vector,\
    open_file_dialog, create_gaussian_vector, create_counts_vector, OptimizerMethod, find_max_signal
import dearpygui.dearpygui as dpg
from PIL import Image
import subprocess
import shutil
import xml.etree.ElementTree as ET
import math
import SystemConfig as configs
import copy
import JobTesting_OPX

from HW_wrapper.Wrapper_Pharos import PharosLaserAPI
from Common import show_msg_window
from Common import Experiment
from Experiment_handlers.scan3d_handler import StartScan3D, scan3d_femto_pulses, scan3d_with_galvo, start_scan_general, scan_reset_data, scan_reset_positioner, scan_get_current_pos, StartScan
from Experiment_handlers.save_load_handler import save_to_cvs, writeParametersToXML, to_xml, update_from_xml, saveExperimentsNotes, save_scan_data, btnLoadScan, prepare_scan_data, save_scan_parameters, load_scan_parameters, move_last_saved_files, Save_2D_matrix2IMG, Plot_Loaded_Scan
from Experiment_handlers.Opx_gui_handler import (
    Update_bX_Scan, Update_bY_Scan, Update_bZ_Scan,
    Update_dX_Scan, Update_dY_Scan, Update_dZ_Scan,
    Update_Lx_Scan, Update_Ly_Scan, Update_Lz_Scan,
    Update_bZcorrection, GetItemsVal, set_moveabs_to_max_intensity,
    fill_moveabs_with_picture_center, fill_moveabs_from_query,
    fill_z, toggle_limit, queryXY_callback, queryYZ_callback,
    queryXZ_callback, Calc_estimatedScanTime,
    time_in_multiples_cycle_time, UpdateCounterIntegrationTime,
    toggle_sum_counters, UpdateWaitTime, UpdateEdgeTime,
    UpdateTcounter, UpdateTpump, UpdateTcounterPulsed,
    UpdateNumOfPoint, Update_mwResonanceFreq, Update_mwP_amp,
    Update_mwP_amp2, Update_off_time, Update_T_bin,
    Update_AWG_interval, Update_AWG_f_1, Update_AWG_f_2,
    Update_mwP_amp3, Update_mw_2ndfreq_resonance, Update_mwFreq,
    Update_df, UpdateScanRange, UpdateMWpwr, UpdateN_nuc_pump,
    UpdateN_p_amp, UpdateN_CPMG, UpdateNavg,
    UpdateCorrelationWidth, UpdateN_measure, UpdateMW_dif,
    UpdatedN, Update_back_freq, Update_gate_number,
    UpdateN_tracking_search, UpdateN_survey_g2_counts,
    UpdateN_survey_g2_threshold, UpdateN_survey_g2_timeout,
    toggle_stop_survey, UpdateT_rf_pulse_time, UpdateT_mw,
    UpdateT_mw2, UpdateT_mw3, Update_rf_pulse_time,
    Update_tGetTrackingSignalEveryTime, Update_tTrackingSignaIntegrationTime,
    Update_TrackingThreshold, UpdateScanTstart, on_off_slider_callback,
    UpdateTsettle, UpdateScanT_dt, UpdateScanTend,
    Update_rf_resonance_Freq, Update_rf_Freq, Update_rf_ScanRange,
    Update_rf_df, Update_rf_pwr, Update_Intensity_Tracking_state,
    Update_QUA_Shuffle_state, Update_QUA_Simulate_state, hide_legend,
    GetWindowSize, set_all_themes
)

from Experiment_handlers.QUA_handler import *
from Experiment_handlers.Find_max_handler import *

matplotlib.use('qtagg')

def create_logger(log_file_path: str):
    log_file = open(log_file_path, 'w')
    return subprocess.Popen(['npx', 'pino-pretty'], stdin=subprocess.PIPE, stdout=log_file)

class MeasurementType(Enum):
    ANALOG = 'analog'
    DIGITAL = 'digital'
    HIGH_RES = 'high_res'

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

        # TODO: Move measure_type definition to be read from config
        # measure_type = MeasurementType.ANALOG
        # self.time_tagging_fn: Callable = time_tagging.digital if measure_type == MeasurementType.DIGITAL else time_tagging.analog
        self.counter_is_live = False
        self.last_loaded_file = None
        self.stop_survey: bool = False
        self.survey_stop_flag = False
        self.survey_g2_threshold: float = 0.4
        self.survey_g2_timeout: int = 120
        self.survey_g2_counts: int = 100
        self.survey_thread = None
        self.survey: bool = False
        self.sum_counters_flag: bool = False
        self.csv_file: Optional[str] = None
        self.is_green = False
        self.ref_counts_handle = None
        self.mattise_frequency_offset: float = 0
        self.job:Optional[QmPendingJob]  = None
        self.qm: Optional[QuantumMachine] = None
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
        self.Y_vec2 = None
        self.Y_vec_aggregated: list[list[float]] = []
        self.scan_default_sleep_time: float = 5e-3
        self.initial_scan_Location: List[float] = []
        self.iteration: int = 0
        self.iteration_list = []
        self.tracking_function: Callable = None
        self.fMW_1 = 0
        self.limit = False
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
        self.kdc_101 = self.HW.kdc_101
        self.awg = self.HW.keysight_awg_device
        self.pico = self.HW.picomotor
        self.laser = self.HW.cobolt
        self.matisse = self.HW.matisse_device
        self.my_qua_jobs = []
        self.spc= self.HW.hrs_500

        if (self.HW.config.system_type == configs.SystemType.FEMTO):
            self.ScanTrigger = 101  # IO2
            self.TrackingTrigger = 101  # IO1
            measure_type = MeasurementType.ANALOG
        if (self.HW.config.system_type == configs.SystemType.HOT_SYSTEM):
            self.ScanTrigger = 1
            self.TrackingTrigger = 1
            measure_type = MeasurementType.DIGITAL
        if (self.HW.config.system_type == configs.SystemType.ATTO):
            print("Setting up parameters for the atto system")
            self.ScanTrigger = 1001  # IO2
            self.TrackingTrigger = 1001  # IO1
            measure_type = MeasurementType.DIGITAL
            if self.HW.atto_scanner:
                print("Setting up tracking function with atto scanner + positioner")
                self.tracking_function = self.FindMaxSignal_atto_positioner_and_scanner
            else:
                print("Setting up tracking function with atto positioner")
                self.tracking_function = self.FindMaxSignal_atto_positioner
        if (self.HW.config.system_type == configs.SystemType.DANIEL):
            self.ScanTrigger = 2001  # IO2
            self.TrackingTrigger = 2001  # IO1
        if (self.HW.config.system_type == configs.SystemType.ICE):
            self.ScanTrigger = 10001  # IO2
            self.TrackingTrigger = 10001  # IO1
        self.my_qua_jobs = []
        self.time_tagging_fn: Callable = time_tagging.digital if measure_type == MeasurementType.DIGITAL else time_tagging.analog
        self.StartScan3D = StartScan3D.__get__(self)
        self.scan3d_femto_pulses = scan3d_femto_pulses.__get__(self)
        self.scan3d_with_galvo = scan3d_with_galvo.__get__(self)
        self.start_scan_general = start_scan_general.__get__(self)
        self.scan_reset_data = scan_reset_data.__get__(self)
        self.scan_reset_positioner = scan_reset_positioner.__get__(self)
        self.scan_get_current_pos = scan_get_current_pos.__get__(self)
        self.StartScan = StartScan.__get__(self)

        self.save_to_cvs = save_to_cvs.__get__(self)
        self.writeParametersToXML = writeParametersToXML.__get__(self)
        self.to_xml = to_xml.__get__(self)
        self.update_from_xml = update_from_xml.__get__(self)
        self.saveExperimentsNotes = saveExperimentsNotes.__get__(self)
        self.save_scan_data = save_scan_data.__get__(self)
        self.btnLoadScan = btnLoadScan.__get__(self)
        self.prepare_scan_data = prepare_scan_data.__get__(self)
        self.save_scan_parameters = save_scan_parameters.__get__(self)
        self.load_scan_parameters = load_scan_parameters.__get__(self)
        self.move_last_saved_files = move_last_saved_files.__get__(self)
        self.Save_2D_matrix2IMG = Save_2D_matrix2IMG.__get__(self)
        self.Plot_Loaded_Scan = Plot_Loaded_Scan.__get__(self)

        self.Update_bX_Scan = Update_bX_Scan.__get__(self)
        self.Update_bY_Scan = Update_bY_Scan.__get__(self)
        self.Update_bZ_Scan = Update_bZ_Scan.__get__(self)
        self.Update_dX_Scan = Update_dX_Scan.__get__(self)
        self.Update_dY_Scan = Update_dY_Scan.__get__(self)
        self.Update_dZ_Scan = Update_dZ_Scan.__get__(self)
        self.Update_Lx_Scan = Update_Lx_Scan.__get__(self)
        self.Update_Ly_Scan = Update_Ly_Scan.__get__(self)
        self.Update_Lz_Scan = Update_Lz_Scan.__get__(self)
        self.Update_bZcorrection = Update_bZcorrection.__get__(self)
        self.GetItemsVal = GetItemsVal.__get__(self)
        self.set_moveabs_to_max_intensity = set_moveabs_to_max_intensity.__get__(self)
        self.fill_moveabs_with_picture_center = fill_moveabs_with_picture_center.__get__(self)
        self.fill_moveabs_from_query = fill_moveabs_from_query.__get__(self)
        self.fill_z = fill_z.__get__(self)
        self.toggle_limit = toggle_limit.__get__(self)
        self.queryXY_callback = queryXY_callback.__get__(self)
        self.queryYZ_callback = queryYZ_callback.__get__(self)
        self.queryXZ_callback = queryXZ_callback.__get__(self)
        self.Calc_estimatedScanTime = Calc_estimatedScanTime.__get__(self)
        self.time_in_multiples_cycle_time = time_in_multiples_cycle_time.__get__(self)
        self.UpdateCounterIntegrationTime = UpdateCounterIntegrationTime.__get__(self)
        self.toggle_sum_counters = toggle_sum_counters.__get__(self)
        self.UpdateWaitTime = UpdateWaitTime.__get__(self)
        self.UpdateEdgeTime = UpdateEdgeTime.__get__(self)
        self.UpdateTcounter = UpdateTcounter.__get__(self)
        self.UpdateTpump = UpdateTpump.__get__(self)
        self.UpdateTcounterPulsed = UpdateTcounterPulsed.__get__(self)
        self.UpdateNumOfPoint = UpdateNumOfPoint.__get__(self)
        self.Update_mwResonanceFreq = Update_mwResonanceFreq.__get__(self)
        self.Update_mwP_amp = Update_mwP_amp.__get__(self)
        self.Update_mwP_amp2 = Update_mwP_amp2.__get__(self)
        self.Update_off_time = Update_off_time.__get__(self)
        self.Update_T_bin = Update_T_bin.__get__(self)
        self.Update_AWG_interval = Update_AWG_interval.__get__(self)
        self.Update_AWG_f_1 = Update_AWG_f_1.__get__(self)
        self.Update_AWG_f_2 = Update_AWG_f_2.__get__(self)
        self.Update_mwP_amp3 = Update_mwP_amp3.__get__(self)
        self.Update_mw_2ndfreq_resonance = Update_mw_2ndfreq_resonance.__get__(self)
        self.Update_mwFreq = Update_mwFreq.__get__(self)
        self.Update_df = Update_df.__get__(self)
        self.UpdateScanRange = UpdateScanRange.__get__(self)
        self.UpdateMWpwr = UpdateMWpwr.__get__(self)
        self.UpdateN_nuc_pump = UpdateN_nuc_pump.__get__(self)
        self.UpdateN_p_amp = UpdateN_p_amp.__get__(self)
        self.UpdateN_CPMG = UpdateN_CPMG.__get__(self)
        self.UpdateNavg = UpdateNavg.__get__(self)
        self.UpdateCorrelationWidth = UpdateCorrelationWidth.__get__(self)
        self.UpdateN_measure = UpdateN_measure.__get__(self)
        self.UpdateMW_dif = UpdateMW_dif.__get__(self)
        self.UpdatedN = UpdatedN.__get__(self)
        self.Update_back_freq = Update_back_freq.__get__(self)
        self.Update_gate_number = Update_gate_number.__get__(self)
        self.UpdateN_tracking_search = UpdateN_tracking_search.__get__(self)
        self.UpdateN_survey_g2_counts = UpdateN_survey_g2_counts.__get__(self)
        self.UpdateN_survey_g2_threshold = UpdateN_survey_g2_threshold.__get__(self)
        self.UpdateN_survey_g2_timeout = UpdateN_survey_g2_timeout.__get__(self)
        self.toggle_stop_survey = toggle_stop_survey.__get__(self)
        self.UpdateT_rf_pulse_time = UpdateT_rf_pulse_time.__get__(self)
        self.UpdateT_mw = UpdateT_mw.__get__(self)
        self.UpdateT_mw2 = UpdateT_mw2.__get__(self)
        self.UpdateT_mw3 = UpdateT_mw3.__get__(self)
        self.Update_rf_pulse_time = Update_rf_pulse_time.__get__(self)
        self.Update_tGetTrackingSignalEveryTime = Update_tGetTrackingSignalEveryTime.__get__(self)
        self.Update_tTrackingSignaIntegrationTime = Update_tTrackingSignaIntegrationTime.__get__(self)
        self.Update_TrackingThreshold = Update_TrackingThreshold.__get__(self)
        self.UpdateScanTstart = UpdateScanTstart.__get__(self)
        self.on_off_slider_callback = on_off_slider_callback.__get__(self)
        self.UpdateTsettle = UpdateTsettle.__get__(self)
        self.UpdateScanT_dt = UpdateScanT_dt.__get__(self)
        self.UpdateScanTend = UpdateScanTend.__get__(self)
        self.Update_rf_resonance_Freq = Update_rf_resonance_Freq.__get__(self)
        self.Update_rf_Freq = Update_rf_Freq.__get__(self)
        self.Update_rf_ScanRange = Update_rf_ScanRange.__get__(self)
        self.Update_rf_df = Update_rf_df.__get__(self)
        self.Update_rf_pwr = Update_rf_pwr.__get__(self)
        self.Update_Intensity_Tracking_state = Update_Intensity_Tracking_state.__get__(self)
        self.Update_QUA_Shuffle_state = Update_QUA_Shuffle_state.__get__(self)
        self.Update_QUA_Simulate_state = Update_QUA_Simulate_state.__get__(self)
        self.hide_legend = hide_legend.__get__(self)
        self.GetWindowSize = GetWindowSize.__get__(self)
        self.set_all_themes = set_all_themes.__get__(self)

        self.reset_data_val = reset_data_val.__get__(self)
        self.initQUA_gen = initQUA_gen.__get__(self)
        self.QUA_execute = QUA_execute.__get__(self)
        self.verify_insideQUA_FreqValues = verify_insideQUA_FreqValues.__get__(self)
        self.GenVector = GenVector.__get__(self)
        self.get_detector_input_type = get_detector_input_type.__get__(self)
        self.get_time_tagging_func = get_time_tagging_func.__get__(self)
        self.QUA_shuffle = QUA_shuffle.__get__(self)
        self.MW_and_reverse = MW_and_reverse.__get__(self)
        self.MW_and_reverse_general = MW_and_reverse_general.__get__(self)
        self.QUA_Pump = QUA_Pump.__get__(self)
        self.QUA_PGM = QUA_PGM.__get__(self)
        self.QUA_PGM_No_Tracking = QUA_PGM_No_Tracking.__get__(self)
        self.execute_QUA = execute_QUA.__get__(self)
        self.QUA_measure_with_sum_counters = QUA_measure_with_sum_counters.__get__(self)
        self.tile_to_length = tile_to_length.__get__(self)
        # Benchmark random gate sequences
        self.play_random_qua_gate = play_random_qua_gate.__get__(self)
        self.play_random_reverse_qua_gate = play_random_reverse_qua_gate.__get__(self)
        self.play_random_qua_two_qubit_gate = play_random_qua_two_qubit_gate.__get__(self)
        self.play_random_reverse_qua_two_qubit_gate = play_random_reverse_qua_two_qubit_gate.__get__(self)
        self.benchmark_play_list_of_gates = benchmark_play_list_of_gates.__get__(self)
        self.benchmark_play_list_of_two_qubit_gates = benchmark_play_list_of_two_qubit_gates.__get__(self)
        self.create_random_qua_vector = create_random_qua_vector.__get__(self)
        self.create_non_random_qua_vector = create_non_random_qua_vector.__get__(self)
        self.generate_random_qua_integer_benchmark = generate_random_qua_integer_benchmark.__get__(self)
        self.reverse_qua_vector = reverse_qua_vector.__get__(self)
        self.benchmark_state_preparation = benchmark_state_preparation.__get__(self)
        self.benchmark_state_readout = benchmark_state_readout.__get__(self)
        self.Random_Benchmark_QUA_PGM = Random_Benchmark_QUA_PGM.__get__(self)
        self.single_shot_play_list_of_gates = single_shot_play_list_of_gates.__get__(self)
        self.single_shot_measure_nuclear_spin = single_shot_measure_nuclear_spin.__get__(self)
        self.Single_shot_QUA_PGM = Single_shot_QUA_PGM.__get__(self)
        self.Test_Crap_QUA_PGM = Test_Crap_QUA_PGM.__get__(self)
        self.Nuclear_Pol_ESR_QUA_PGM = Nuclear_Pol_ESR_QUA_PGM.__get__(self)
        self.QUA_prepare_state = QUA_prepare_state.__get__(self)
        self.QUA_measure = QUA_measure.__get__(self)
        self.QUA_ref0 = QUA_ref0.__get__(self)
        self.QUA_ref1 = QUA_ref1.__get__(self)
        self.Entanglement_gate_tomography_QUA_PGM = Entanglement_gate_tomography_QUA_PGM.__get__(self)
        self.repeated_time_bin_qua_sequence_start = repeated_time_bin_qua_sequence_start.__get__(self)
        self.repeated_time_bin_qua_sequence_end = repeated_time_bin_qua_sequence_end.__get__(self)
        self.time_bin_entanglement_QUA_PGM = time_bin_entanglement_QUA_PGM.__get__(self)
        self.Population_gate_tomography_QUA_PGM = Population_gate_tomography_QUA_PGM.__get__(self)
        self.MZI_g2 = MZI_g2.__get__(self)
        self.g2_raw_QUA = g2_raw_QUA.__get__(self)
        self.ODMR_Bfield_QUA_PGM = ODMR_Bfield_QUA_PGM.__get__(self)
        self.NuclearFastRotation_QUA_PGM = NuclearFastRotation_QUA_PGM.__get__(self)
        self.Electron_lifetime_QUA_PGM = Electron_lifetime_QUA_PGM.__get__(self)
        self.Nuclear_spin_lifetimeS0_QUA_PGM = Nuclear_spin_lifetimeS0_QUA_PGM.__get__(self)
        self.Nuclear_spin_lifetimeS1_QUA_PGM = Nuclear_spin_lifetimeS1_QUA_PGM.__get__(self)
        self.Nuclear_Ramsay_QUA_PGM = Nuclear_Ramsay_QUA_PGM.__get__(self)
        self.Electron_Coherence_QUA_PGM = Electron_Coherence_QUA_PGM.__get__(self)
        self.Hahn_QUA_PGM = Hahn_QUA_PGM.__get__(self)
        self.NuclearSpinPolarization_pulsedODMR_QUA_PGM = NuclearSpinPolarization_pulsedODMR_QUA_PGM.__get__(self)
        self.NuclearMR_QUA_PGM = NuclearMR_QUA_PGM.__get__(self)
        self.NuclearRABI_QUA_PGM = NuclearRABI_QUA_PGM.__get__(self)
        self.PulsedODMR_QUA_PGM = PulsedODMR_QUA_PGM.__get__(self)
        self.RABI_QUA_PGM = RABI_QUA_PGM.__get__(self)
        self.ODMR_CW_QUA_PGM = ODMR_CW_QUA_PGM.__get__(self)
        self.TrackingCounterSignal_QUA_PGM = TrackingCounterSignal_QUA_PGM.__get__(self)
        self.counter_QUA_PGM = counter_QUA_PGM.__get__(self)
        self.awg_sync_counter_QUA_PGM = awg_sync_counter_QUA_PGM.__get__(self)
        self.MeasureByTrigger_QUA_PGM = MeasureByTrigger_QUA_PGM.__get__(self)
        self.MeasurePLE_QUA_PGM = MeasurePLE_QUA_PGM.__get__(self)

        self.FindMaxSignal = FindMaxSignal.__get__(self)
        self.FindFocus = FindFocus.__get__(self)
        self.Find_max_signal_by_keysight_offset = Find_max_signal_by_keysight_offset.__get__(self)
        self.FindMaxSignal_atto_positioner_and_scanner = FindMaxSignal_atto_positioner_and_scanner.__get__(self)
        self.FindMaxSignal_atto_positioner = FindMaxSignal_atto_positioner.__get__(self)
        self.MoveToPeakIntensity = MoveToPeakIntensity.__get__(self)
        self.SearchPeakIntensity = SearchPeakIntensity.__get__(self)
        self.calculate_tracking_bounds = calculate_tracking_bounds.__get__(self)

        # At the end of the init - all values are overwritten from XML!
        # To update values of the parameters - update the XML or the corresponding place in the GUI
        self.simulation = simulation
        self.graph_size_override = None  # (w, h) tuple

        self.text_color = (0, 0, 0, 255)  # Set color to black
        self.N_scan = [0, 0, 0]

        self.z_correction_threshold = 10000
        self.expected_pos = None
        self.smaract_ttl_duration = 0.001  # ms, updated from XML (loaded using 'self.update_from_xml()')
        self.lock = threading.Lock()

        # Coordinates + scan XYZ parameters
        self.scan_Out = []
        self.scan_data = np.zeros(shape=[80, 80, 60])
        self.queried_area = None
        self.queried_plane = None  # 0 - XY, 1 - YZ, 2 -XZ
        self.bScanChkbox = True
        self.L_scan = [3000, 3000, 3000]  # [nm]
        self.dL_scan = [300, 300, 300]  # [nm]
        self.b_Scan = [True, True, False]
        self.b_Zcorrection = True
        self.ZCalibrationData: np.ndarray | None = None
        self.Zcorrection_threshold = 10  # [nm]
        self.iniShift_scan = [0, 0, 0]  # [nm]
        self.idx_scan = [0, 0, 0]  # Z Y X
        self.startLoc = [0, 0, 0]
        self.endLoc = [0, 0, 0]
        # self.dir = 1
        self.estimatedScanTime = 0.0  # [minutes]
        self.singleStepTime_scan = 0.033  # [sec]
        self.stopScan = True
        self.scanFN = ""

        self.bEnableShuffle = True
        self.bEnableSimulate = False
        # tracking ref
        self.bEnableSignalIntensityCorrection = False
        self.trackingPeriodTime = 10000000  # [nsec]
        self.refSignal = 0.0
        self.TrackIsRunning = True
        self.tTrackingSignaIntegrationTime = 50  # [msec]
        self.tGetTrackingSignalEveryTime = float(3)  # [sec]
        self.TrackingThreshold = 0.95  # track signal threshold
        self.N_tracking_search = 20  # max number of point to scan on each axis

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
        self.mw_P_amp = 0.5    # proportional amplitude
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

        # G2 correlation width
        self.correlation_width = 500 # [nsec]

        self.dN  = 10
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
        self.bScanChkbox = True

        self.chkbox_close_all_qm = False
        self.pharos = PharosLaserAPI(host="192.168.101.58")
        self.Shoot_Femto_Pulses = False

        dpg.set_frame_callback(1, load_window_positions)

        if simulation:
            print("OPX in simulation mode ***********************")
        else:
            try:
                # self.qmm = QuantumMachinesManager(self.HW.config.opx_ip, self.HW.config.opx_port)
                if self.connect_to_QM_OPX:
                    # # Currently does not work
                    # client = QmSaas(email="daniel@quantumtransistors.com", password="oNv9Uk4B6gL3")
                    # self.instance = client.simulator(version = QoPVersion.v2_4_0)
                    # self.instance.spawn()
                    # self.qmm = QuantumMachinesManager(host=self.instance.host,
                    #                                  port=self.instance.port,
                    #                                  connection_headers=self.instance.default_connection_headers)
                    pass
                else:
                    self.qmm = QuantumMachinesManager(host=self.HW.config.opx_ip, cluster_name=self.HW.config.opx_cluster,
                                                      timeout=60)  # in seconds
                    time.sleep(1)
                    self.close_qm_jobs()

            except Exception as e:
                print(f"Could not connect to OPX. Error: {e}.")

    def DeleteMainWindow(self):
        if dpg.does_item_exist(self.window_tag):
            dpg.delete_item(self.window_tag)

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

    def controls(self, _width=1600, _Height=1000):
        self.GetWindowSize()
        pos = [int(self.viewport_width * 0.0), int(self.viewport_height * 0.4)]
        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.425)]
        self.set_all_themes()

        if dpg.does_item_exist("graph_window"):
            pos_graph = dpg.get_item_pos("graph_window")
            size_graph = [
                dpg.get_item_width("graph_window"),
                dpg.get_item_height("graph_window")
            ]
            dpg.delete_item("graph_window")
        else:
            pos_graph = pos
            size_graph = [780, 400]  # fallback

        if dpg.does_item_exist("experiments_window"):
            pos_exp = dpg.get_item_pos("experiments_window")
            size_exp = [
                dpg.get_item_width("experiments_window"),
                dpg.get_item_height("experiments_window")
            ]
            dpg.delete_item("experiments_window")
        else:
            pos_exp = [100, 100]
            size_exp = [400, 400]

        dpg.add_window(label=self.window_tag, tag=self.window_tag, no_title_bar=True, height=-1, width=-1, pos=[int(pos[0]), int(pos[1])])
        dpg.add_window(label="Exp graph", tag="experiments_window", no_title_bar=True, height=size_exp[1], width=size_exp[0], pos=[int(pos_exp[0]), int(pos_exp[1])])
        dpg.add_window(label="Exp graph", tag="graph_window", no_title_bar=True, height=size_graph[1], width=size_graph[0], pos=[int(pos_graph[0]), int(pos_graph[1])])
        dpg.add_button(label = "Hide legend", tag = "Hide_legend", parent = "graph_window", callback = self.hide_legend)

        dpg.add_group(tag="Graph_group", parent=self.window_tag, horizontal=True)
        dpg.add_plot(label="Graph", crosshairs=True, tag="graphXY", parent="graph_window", height=-1, width=-1)# width=int(win_size[0]), height=int(win_size[1]))  # height=-1, width=-1,no_menus = False )
        dpg.add_plot_legend(tag="graph_legend", parent="graphXY")
        dpg.add_plot_axis(dpg.mvXAxis, label="time", tag="x_axis", parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvYAxis, label="I [counts/sec]", tag="y_axis", invert=False, parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_line_series(self.X_vec, self.Y_vec, label="counts", parent="y_axis", tag="series_counts")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref, label="counts_ref", parent="y_axis", tag="series_counts_ref")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref2, label="counts_ref2", parent="y_axis", tag="series_counts_ref2")
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref3, label="counts_ref3", parent="y_axis", tag="series_counts_ref3")
        dpg.add_line_series(self.X_vec_ref,self.Y_resCalculated, label="resCalculated", parent="y_axis", tag="series_res_calcualted")

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
        dpg.bind_item_theme("series_counts_ref2", "LineCyanTheme")
        dpg.bind_item_theme("series_counts_ref3", "LineBlueTheme")
        dpg.bind_item_theme("series_res_calcualted", "LineRedTheme")

        #dpg.add_group(tag="Params_Controls", before="Graph_group", parent=self.window_tag, horizontal=False)
        self.GUI_ParametersControl(True)

    def GUI_ParametersControl(self, isStart):
        child_width = int(2900 * self.window_scale_factor)
        child_height = int(80 * self.window_scale_factor)
        item_width = int(150 * self.window_scale_factor)
        dpg.delete_item("Params_Controls")
        dpg.delete_item("Buttons_Controls")

        if isStart:
            dpg.add_group(tag="Params_Controls", before="Graph_group", parent=self.window_tag, horizontal=False)

            dpg.add_group(tag="chkbox_group", parent="Params_Controls", horizontal=True)
            dpg.add_checkbox(label="Intensity Correction", tag="chkbox_intensity_correction", parent="chkbox_group", callback=self.Update_Intensity_Tracking_state, indent=-1, default_value=self.bEnableSignalIntensityCorrection)
            dpg.add_checkbox(label="QUA shuffle", tag="chkbox_QUA_shuffle", parent="chkbox_group", callback=self.Update_QUA_Shuffle_state, indent=-1, default_value=self.bEnableShuffle)
            dpg.add_checkbox(label="QUA simulate", tag="chkbox_QUA_simulate", parent="chkbox_group", callback=self.Update_QUA_Simulate_state, indent=-1, default_value=self.bEnableSimulate)
            dpg.add_checkbox(label="Scan XYZ", tag="chkbox_scan", parent="chkbox_group", indent=-1, callback=self.Update_scan, default_value=self.bScanChkbox)
            dpg.add_checkbox(label="Close All QM", tag="chkbox_close_all_qm", parent="chkbox_group", indent=-1, callback=self.Update_close_all_qm, default_value=self.chkbox_close_all_qm)
            dpg.add_checkbox(label="Two Qubit Benchmark", tag="chkbox_no_gate_benchmark", parent="chkbox_group",
                             indent=-1,
                             callback=self.Update_benchmark_switch_flag,
                             default_value=self.benchmark_switch_flag)
            dpg.add_checkbox(label="One Gate Only Benchmark", tag="chkbox_single_gate_benchmark", parent="chkbox_group",
                             indent=-1,
                             callback=self.Update_benchmark_one_gate_only, default_value=self.benchmark_one_gate_only)
            dpg.add_checkbox(label="Sum Counters", tag="chkbox_sum_counters", parent="chkbox_group",
                             callback=self.toggle_sum_counters, indent=-1,
                             default_value=self.sum_counters_flag)
            dpg.add_checkbox(label="Stop Survey", tag="chkbox_stop_survey", parent="chkbox_group",
                             callback=self.toggle_stop_survey, indent=-1,
                             default_value=self.stop_survey)

            # Create a single collapsible header to contain all controls, collapsed by default
            with dpg.collapsing_header(label="Parameters Control", tag="Parameter_Controls_Header",
                                       parent="Params_Controls", default_open=True):
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
                dpg.add_text(default_value="Survey g2 counts", parent="Repetitions_Controls",
                             tag="text_survey_g2_counts", indent=-1)
                dpg.add_input_int(label="", tag="inInt_survey_g2_counts", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_survey_g2_counts,
                                  default_value=self.survey_g2_counts,
                                  min_value=0, max_value=50000, step=1)

                dpg.add_text(default_value="Survey g2 threshold", parent="Repetitions_Controls",
                             tag="text_survey_g2_threshold", indent=-1)
                dpg.add_input_float(label="", tag="inInt_survey_g2_threshold", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_survey_g2_threshold,
                                  default_value=self.survey_g2_threshold,
                                  min_value=0, max_value=1, step=0.001)

                dpg.add_text(default_value="Survey g2 timeout", parent="Repetitions_Controls",
                             tag="text_survey_g2_timeout", indent=-1)
                dpg.add_input_float(label="", tag="inInt_survey_g2_timeout", indent=-1, parent="Repetitions_Controls",
                                  width=item_width, callback=self.UpdateN_survey_g2_timeout,
                                  default_value=self.survey_g2_timeout,
                                  min_value=1, max_value=10000, step=1)

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

                # save exp data
                dpg.add_group(tag="Save_Controls", parent="Parameter_Controls_Header", horizontal=True)
                dpg.add_input_text(label="", parent="Save_Controls", tag="inTxtOPX_expText", indent=-1,
                                   callback=self.saveExperimentsNotes)
                dpg.add_button(label="Save", parent="Save_Controls", tag="btnOPX_save", callback=self.btnSave,
                               indent=-1)  # remove save btn, it should save automatically
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

                dpg.add_slider_int(label="Laser Type",
                                   tag="on_off_slider_OPX", width = 80,
                                   default_value=1, parent="chkbox_group",
                                   min_value=0, max_value=1,
                                   callback=self.on_off_slider_callback,indent = -1,
                                   format="Green")

            _width = -1
            dpg.add_group(tag="Buttons_Controls", parent="experiments_window", horizontal=False)  # parent="Params_Controls",horizontal=False)
            dpg.add_button(label="Counter", parent="Buttons_Controls", tag="btnOPX_StartCounter",callback=self.btnStartCounterLive, indent=-1, width=_width)
            dpg.add_button(label="ODMR_CW", parent="Buttons_Controls", tag="btnOPX_StartODMR", callback=self.btnStartODMR_CW, indent=-1, width=_width)
            dpg.add_button(label="Start Pulsed ODMR", parent="Buttons_Controls", tag="btnOPX_StartPulsedODMR", callback=self.btnStartPulsedODMR, indent=-1, width=_width)
            dpg.add_button(label="ODMR_Bfield", parent="Buttons_Controls", tag="btnOPX_StartODMR_Bfield", callback=self.btnStartODMR_Bfield, indent=-1, width=_width)
            dpg.add_button(label="NuclearFastRot", parent="Buttons_Controls", tag="btnOPX_StartNuclearFastRot", callback=self.btnStartNuclearFastRot, indent=-1, width=_width)
            dpg.add_button(label="RABI", parent="Buttons_Controls", tag="btnOPX_StartRABI", callback=self.btnStartRABI, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear RABI", parent="Buttons_Controls", tag="btnOPX_StartNuclearRABI", callback=self.btnStartNuclearRABI, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear MR", parent="Buttons_Controls", tag="btnOPX_StartNuclearMR", callback=self.btnStartNuclearMR, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear PolESR", parent="Buttons_Controls", tag="btnOPX_StartNuclearPolESR", callback=self.btnStartNuclearPolESR, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear lifetime S0", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS0", callback=self.btnStartNuclearSpinLifetimeS0, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear lifetime S1", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS1", callback=self.btnStartNuclearSpinLifetimeS1, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear Ramsay", parent="Buttons_Controls", tag="btnOPX_StartNuclearRamsay", callback=self.btnStartNuclearRamsay, indent=-1, width=_width)
            dpg.add_button(label="Start Hahn", parent="Buttons_Controls", tag="btnOPX_StartHahn", callback=self.btnStartHahn, indent=-1, width=_width)
            dpg.add_button(label="Start Electron Lifetime", parent="Buttons_Controls", tag="btnOPX_StartElectronLifetime", callback=self.btnStartElectronLifetime, indent=-1, width=_width)
            dpg.add_button(label="Start Electron Coherence", parent="Buttons_Controls", tag="btnOPX_StartElectronCoherence", callback=self.btnStartElectron_Coherence, indent=-1, width=_width)
            dpg.add_button(label="Start population gate tomography", parent="Buttons_Controls", tag="btnOPX_PopulationGateTomography", callback=self.btnStartPopulateGateTomography, indent=-1, width=_width)
            dpg.add_button(label="Start Entanglement state tomography", parent="Buttons_Controls", tag="btnOPX_EntanglementStateTomography", callback=self.btnStartStateTomography, indent=-1, width=_width)
            dpg.add_group(tag="G2_Controls", parent="Buttons_Controls", horizontal=True)
            dpg.add_button(label="Start G2", parent="G2_Controls", tag="btnOPX_G2", callback=self.btnStartG2, indent=-1, width=200)
            dpg.add_input_int(label="", tag="inInt_G2_correlation_width", indent=-1, parent="G2_Controls", width=150, callback=self.UpdateCorrelationWidth, default_value=self.correlation_width,
                              min_value=1, max_value=50000, step=1)
            dpg.add_button(label="Start G2 Survey", parent="Buttons_Controls", tag="btnOPX_StartG2Survey", callback=self.btnStartG2Survey, indent=-1,
                           width=_width)
            dpg.add_button(label="Eilon's", parent="Buttons_Controls", tag="btnOPX_Eilons",
                           callback=self.btnStartEilons, indent=-1, width=_width)
            dpg.add_button(label="Random Benchmark", parent="Buttons_Controls", tag="btnOPX_RandomBenchmark",
                           callback=self.btnStartRandomBenchmark, indent=-1, width=_width)
            dpg.add_button(label="Start Time Bin Entanglement", parent="Buttons_Controls",
                           tag="btnOPX_StartTimeBinEntanglement",
                           callback=self.btnStartTimeBinEntanglement, indent=-1, width=_width)
            dpg.add_button(label="PLE", parent="Buttons_Controls", tag="btnPLE", callback=self.btnStartPLE,
                           indent=-1, width=_width)
            dpg.add_button(label="Ext. Frequency Scan", parent="Buttons_Controls", tag="btnExternalFrequencyScan",
                           callback=self.btnStartExternalFrequencyScan,
                           indent=-1, width=_width)
            dpg.add_button(label="FP SCAN (AWG)", parent="Buttons_Controls", tag="btnAWG_FP_SCAN",
                           callback=self.btnStartAWG_FP_SCAN,
                           indent=-1, width=_width)

            dpg.bind_item_theme(item="Params_Controls", theme="NewTheme")
            dpg.bind_item_theme(item="btnOPX_StartCounter", theme="btnYellowTheme")
            dpg.bind_item_theme(item="btnOPX_StartODMR", theme="btnRedTheme")
            dpg.bind_item_theme(item="btnOPX_StartPulsedODMR", theme="btnRedTheme")
            dpg.bind_item_theme(item="btnOPX_StartRABI", theme="btnBlueTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearRABI", theme="btnBlueTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearMR", theme="btnGreenTheme")
            dpg.bind_item_theme(item="btnOPX_StartNuclearPolESR", theme="btnGreenTheme")
            dpg.bind_item_theme("on_off_slider_OPX", "OnTheme_OPX")
            dpg.bind_item_theme(item="btnOPX_StartG2Survey", theme="btnPurpleTheme")

            self.load_scan_parameters()
            self.GUI_ScanControls()
            dpg.set_frame_callback(1, load_window_positions)
        else:
            dpg.add_group(tag="Params_Controls", parent="experiments_window", horizontal=False)
            dpg.add_button(label="Stop", parent="Params_Controls", tag="btnOPX_Stop", callback=self.btnStop, indent=-1,width=-1)
            dpg.bind_item_theme(item="btnOPX_Stop", theme="btnRedTheme")
            dpg.add_button(label="Find Max Intensity", parent="Params_Controls", tag="btnOPX_StartFindMaxIntensity",
                           callback=self.MoveToPeakIntensity, indent=-1)
            dpg.add_text(parent="Params_Controls",default_value = f"Int.time:\n{self.total_integration_time:.1f} ms",tag = "text_total_integration_time_display",indent = 10)

    def GUI_ScanControls(self):
        self.Calc_estimatedScanTime()
        self.maintain_aspect_ratio = True

        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.3)]
        win_pos = [int(self.viewport_width * 0.05) * 0, int(self.viewport_height * 0.5)]
        scan_time_in_seconds = self.estimatedScanTime * 60

        item_width = int(190 * self.window_scale_factor)

        # ✅ Prevent duplicate creation
        if dpg.does_item_exist("Scan_Window"):
            dpg.show_item("Scan_Window")  # Optional: bring it to front
            return

        if self.bScanChkbox:
            last_dir = ""
            if os.path.exists("last_scan_dir.txt"):
                with open("last_scan_dir.txt", "r") as f:
                    last_dir = f.read().strip().replace("\\", "/").split("/")[-1]
            with dpg.window(label="Scan Window", tag="Scan_Window", no_title_bar=True, height=1600, width=1200,
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
                                dpg.add_text(default_value="Lx [um]", tag="text_Lx_scan", indent=-1)
                                dpg.add_input_float(label="", tag="inInt_Lx_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lx_Scan,
                                                  default_value=self.L_scan[0]/1000, min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Y_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bY_Scan", indent=-1,
                                                 callback=self.Update_bY_Scan,
                                                 default_value=self.b_Scan[1])
                                dpg.add_text(default_value="dy [nm]", tag="text_dy_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dy_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dY_Scan,
                                                  default_value=self.dL_scan[1], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Ly [um]", tag="text_Ly_scan", indent=-1)
                                dpg.add_input_float(label="", tag="inInt_Ly_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Ly_Scan,
                                                  default_value=self.L_scan[1]/1000, min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Z_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bZ_Scan", indent=-1,
                                                 callback=self.Update_bZ_Scan,
                                                 default_value=self.b_Scan[2])
                                dpg.add_text(default_value="dz [nm]", tag="text_dz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dZ_Scan,
                                                  default_value=self.dL_scan[2], min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lz [um]", tag="text_Lz_scan", indent=-1)
                                dpg.add_input_float(label="", tag="inInt_Lz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lz_Scan,
                                                  default_value=self.L_scan[2]/1000, min_value=0, max_value=500000, step=1)

                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label="Notes", tag="inTxtScan_expText", indent=-1, width=300,
                                                   callback=self.saveExperimentsNotes, default_value=self.expNotes)
                                dpg.add_checkbox(label="", tag="chkbox_Zcorrection", indent=-1,
                                                 callback=self.Update_bZcorrection,
                                                 default_value=self.b_Zcorrection)
                                dpg.add_text(default_value="Z", tag="text_Zcorrection", indent=-1)
                                dpg.add_input_int(label="Limit", tag="inInt_limit", indent=-1, width=item_width*.8,
                                                  default_value=self.dL_scan[2], min_value=0, max_value=500000, step=1)

                            dpg.add_text(default_value=f"~scan time: {self.format_time(scan_time_in_seconds)}",
                                         tag="text_expectedScanTime",
                                         indent=-1)

                            with dpg.group(horizontal=True):
                                dpg.add_text(label="Message: ", tag="Scan_Message")

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
                        dpg.add_button(label="Femto Pls", tag="btnOPX_Femto_Pulses", callback=self.btnFemtoPulses, indent=-1, width=130)
                        dpg.add_input_text(label="", tag="MoveSubfolderInput", width=130, default_value=last_dir)
                        dpg.add_button(label="Mv File", callback=self.move_last_saved_files)
                    _width = 150
                    with dpg.group(horizontal=False):
                        dpg.add_input_float(label="AnnTH", tag="femto_anneal_threshold", default_value=800, width=_width)
                        dpg.add_input_int(label="Att",tag="femto_attenuator",default_value=10,width=_width,callback=lambda s, a, u: self.pharos.setBasicTargetAttenuatorPercentage(dpg.get_value(s)))
                        dpg.add_input_int(label="AttInc", tag="femto_increment_att",default_value=0,width=_width)
                        dpg.add_input_float(label="HWPInc", tag="femto_increment_hwp", default_value=1, width=_width)
                        dpg.add_input_float(label="HWPAnn", tag="femto_increment_hwp_anneal", default_value=0.01, width=_width)
                        dpg.add_input_int(label="nPlsAnn", tag="femto_anneal_pulse_count", default_value=100, width=_width)
                    _width = 100
                    with dpg.group(horizontal=False):
                        dpg.add_checkbox(label="Limit", indent=-1, tag="checkbox_limit", callback=self.toggle_limit,
                                         default_value=self.limit)
                        dpg.add_button(label="Fill Z", callback=self.fill_z)
                        dpg.add_button(label="Fill Max", callback=self.set_moveabs_to_max_intensity)
                        dpg.add_button(label="Fill Qry", callback=self.fill_moveabs_from_query)
                        dpg.add_button(label="Fill Cnt", callback=self.fill_moveabs_with_picture_center)
                        dpg.add_button(label="Galvo Sc", callback=self.btnStartGalvoScan)
                    # Schedule the call to happen after 1 frame
                    self.delayed_actions()
                    # dpg.set_frame_callback(dpg.get_frame_count() + 1, self.delayed_actions)

            self.hide_legend()
        else:
            dpg.delete_item("Scan_Window")

    def delayed_actions(self):
        # ✅ Setup dummy zero scan data (5×5×5)
        self.scan_data = np.zeros((5, 5, 5), dtype=float)
        self.idx_scan = [2, 2, 2]  # Middle slice for each axis
        self.Xv = np.linspace(0, 1, 5)
        self.Yv = np.linspace(0, 1, 5)
        self.Zv = np.linspace(0, 1, 5)
        self.startLoc = [0, 0, 0]
        self.endLoc = [1, 1, 1]

        # Call plot function
        load_window_positions()
        self.Plot_Loaded_Scan()
        load_window_positions()
        self.hide_legend()

    def get_device_position(self, device):
        device.GetPosition()
        position = [0] * 3
        for channel in range(3):
            position[channel] = int(device.AxesPositions[channel] / device.StepsIn1mm * 1e3 * 1e6)  # [pm]
        return position

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

    def Plot_Scan(self, Nx=250, Ny=250, array_2d=None, startLoc=None, endLoc=None, switchAxes=False, current_z=None):
        """
        Plots a 2D scan using the provided array. If a division by zero occurs,
        the array will be set to zeros.
        """
        if dpg.does_item_exist("plot_draw_layer"):
            dpg.delete_item("plot_draw_layer", children_only=True)

        if array_2d is None:
            array_2d = np.zeros((Nx, Ny))  # Default to zeros if array is not provided

        if startLoc is None:
            startLoc = [0, 0]

        if endLoc is None:
            endLoc = [Nx, Ny]

        start_Plot_time = time.time()
        plot_size = [int(self.viewport_width * 0.2), int(self.viewport_height * 0.4)] #1-7-2025

        try:
            # Attempt to normalize the array
            max_value = array_2d.max()
            if max_value == 0:
                raise ZeroDivisionError("Maximum value of the array is zero, cannot normalize.")

            # Normalize and multiply by 255
            result_array = (array_2d * 255) / max_value
        except ZeroDivisionError:
            # print("Division by zero encountered. Setting entire array to zero.")
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
                         equal_aspects=True, crosshairs=True,query=True, callback=self.queryXY_callback)
            z_label = f"x axis [um]{f' @ Z={current_z:.1f} µm' if current_z is not None else ''}"
            dpg.add_plot_axis(dpg.mvXAxis, label=z_label, parent="plotImaga",tag="plotImaga_X")

            dpg.add_plot_axis(dpg.mvYAxis, label="y axis [um]", parent="plotImaga", tag="plotImaga_Y")
            dpg.add_image_series(f"texture_tag", bounds_min=[startLoc[0], startLoc[1]], bounds_max=[endLoc[0], endLoc[1]], label="Scan data", parent="plotImaga_Y")
            # Add a draw layer for text annotations (e.g., pulse energy)

            dpg.add_draw_layer(parent="plotImaga", tag="plot_draw_layer")

            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(array_2d), max_scale=np.max(array_2d), colormap=dpg.mvPlotColormap_Jet)

            # ✅ Apply persistent graph size override if exists
            if hasattr(self, "graph_size_override") and self.graph_size_override:
                w, h = self.graph_size_override
                dpg.set_item_width("plotImaga", w)
                dpg.set_item_height("plotImaga", h)
                print(f"Graph resized to override: {w}×{h}")

        except Exception as e:
            print(f"Error during plotting: {e}")
        end_Plot_time = time.time()
        print(f"time to plot scan: {end_Plot_time - start_Plot_time}")
        try:
            dpg.set_value("texture_tag", result_array_)
        except Exception as e:
            print(f"Error setting texture tag value: {e}")

    def UpdateGuiDuringScan(self, Array2D, use_fast_rgb: bool = False):
        # If self.limit is true, cap the values in Array2D at dz (nm) value
        if self.limit:
            limit = dpg.get_value("inInt_limit")
            Array2D = np.where(Array2D > limit, limit, Array2D)

        val = Array2D.reshape(-1)
        idx = np.where(val != 0)[0]
        if len(idx) == 0:
            minI = 0
        else:
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
        sender.load_scan_parameters()
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

    def Common_updateGraph(self, _xLabel="?? [??],", _yLabel="I [kCounts/sec]"):
        try:
            # todo: use this function as general update graph for all experiments
            self.lock.acquire()
            dpg.set_item_label("graphXY",f"{self.exp.name}, iteration = {self.iteration}, tracking_ref = {self.tracking_ref: .1f}, ref Threshold = {self.refSignal: .1f},shuffle = {self.bEnableShuffle}, Tracking = {self.bEnableSignalIntensityCorrection}")
            dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
            if any(self.Y_vec_ref):
                dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
            if self.exp == Experiment.Nuclear_Fast_Rot:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
            if self.exp == Experiment.RandomBenchmark:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
                dpg.set_value("series_counts_ref3", [self.X_vec, self.Y_vec_ref3])
                dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_vec_squared]) # MIC: works!
            if self.exp == Experiment.NUCLEAR_MR:
                dpg.set_value("series_counts_ref2", [self.X_vec, self.Y_vec_ref2])
                dpg.set_value("series_counts_ref3", [self.X_vec, self.Y_vec2])
                #dpg.set_value("series_res_calcualted", [self.X_vec, self.Y_vec_squared]) # MIC: works!
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
            self.lock.release()#self.lock.acquire()


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

    def ensure_list(self,x):
        """Return x if it is a list, otherwise wrap x in a list."""
        return x if isinstance(x, list) else [x]

    def FetchData(self):
        self.pgm_end = False
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
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "counts_ref2", "iteration", "tracking_ref", "number_order", "counts_square","counts_ref3"], mode="live")
        elif self.exp == Experiment.NUCLEAR_MR:
            self.results = fetching_tool(self.job, data_list=["counts", "counts2", "counts_ref", "counts_ref2", "iteration", "tracking_ref"], mode="live")
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
        dpg.bind_item_theme("series_counts_ref3", "LineBlueTheme")
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
                                   f"{self.exp.name}, Iteration = {self.iteration}, Total Counts = {round(self.g2_totalCounts, 0)}, g2 = {self.calculate_g2(self.Y_vec):.3f}")
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
                # self.btnSave(folder= "Q:/QT-Quantum_Optic_Lab/expData/G2/")
                pass

        if not(self.StopFetch):
            self.pgm_end = True
            self.btnStop()
        
    def GlobalFetchData(self):
        self.lock.acquire()

        data = [self.ensure_list(x) for x in self.results.fetch_all()]

        if self.exp in [Experiment.COUNTER, Experiment.EXTERNAL_FREQUENCY_SCAN]:
            self.counter_Signal, self.ref_signal = self.results.fetch_all()
        elif self.exp == Experiment.AWG_FP_SCAN:
            self.counter_signal = self.results.fetch_all()
        elif self.exp == Experiment.G2:
            self.g2Vec, self.g2_totalCounts, self.iteration = self.results.fetch_all()
        elif self.exp == Experiment.RandomBenchmark:
            self.signal, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal, self.number_order, self.signal_squared, self.ref_signal3  = self.results.fetch_all()  # grab/fetch new data from stream
        elif self.exp == Experiment.NUCLEAR_MR:
            self.signal, self.signal2, self.ref_signal, self.ref_signal2, self.iteration, self.tracking_ref_signal  = self.results.fetch_all()  # grab/fetch new data from stream
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
            self.X_vec = self.X_vec.tolist()
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec = self.Y_vec.tolist()
            self.Y_vec2 = self.signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec2 = self.Y_vec2.tolist()
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.Y_vec_ref.tolist()
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.Y_vec_ref2.tolist()
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
            self.Y_vec = self.Y_vec.tolist()
            self.Y_vec_ref = self.ref_signal/ (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref = self.Y_vec_ref.tolist()
            self.Y_vec_ref2 = self.ref_signal2 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref2 = self.Y_vec_ref2.tolist()
            self.benchmark_number_order = self.number_order
            self.benchmark_number_order = self.benchmark_number_order.tolist()
            # self.benchmark_reverse_number_order = self.reverse_number_order
            # self.benchmark_reverse_number_order = self.benchmark_reverse_number_order.tolist()
            self.Y_vec_squared = self.signal_squared/ (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_squared = self.Y_vec_squared.tolist()
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
            self.Y_vec_ref3 = self.ref_signal3 / (self.TcounterPulsed * 1e-9) / 1e3
            self.Y_vec_ref3 = self.Y_vec_ref3.tolist()

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
        try:
            if self.counter_is_live:
                print('Counter is already live')
                return
            self.exp = Experiment.COUNTER
            self.GUI_ParametersControl(isStart=self.bEnableSimulate)
            self.initQUA_gen(n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                             num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)
            if b_startFetch and not self.bEnableSimulate:
                self.StartFetch(_target=self.FetchData)
            self.counter_is_live = True
        except Exception as e:
            print(f"Failed to start counter live: {e}")

    def btnStartG2Survey(self) -> None:
        """
        Wrapper function to prompt the user for a CSV file containing survey points, extract the points,
        select the appropriate move and position functions, and start the g2 survey.

        The CSV file is expected to have rows with at least two columns representing the x and y coordinates.
        The move function is chosen based on the existence of self.HW.atto_positioner.MoveABSOLUTE or
        self.positioner.MoveABSOLUTE. Similarly, the position function is selected from self.HW.atto_positioner.get_position
        or self.positioner.get_position, and the wait function is wrapped from either
        self.HW.atto_positioner.wait_for_axes_to_stop or self.positioner.ReadIsInPosition.

        Recommended survey parameters:
          - g2_threshold: 0.45
          - g2_counts: 200

        :return: None
        """
        try:
            # Prompt user for CSV file path
            system_name=None
            file_path = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])  # Show .csv and all file types
            points = []
            with open(file_path, 'r') as csvfile:
                reader = csv.reader(csvfile)
                for row in reader:
                    if len(row) >= 2:
                        try:
                            x = float(row[0].strip())
                            y = float(row[1].strip())
                            points.append((x, y))
                        except ValueError:
                            print(f"Skipping row with invalid coordinates: {row}")
            if not points:
                print("No valid points found in the CSV file.")
                return

            # Select move, position, and wait functions based on available hardware
            if hasattr(self, "HW") and hasattr(self.HW, "atto_positioner") and hasattr(self.HW.atto_positioner,
                                                                                       "MoveABSOLUTE"):
                move_fn = self.HW.atto_positioner.MoveABSOLUTE
                get_positions_fn = self.HW.atto_positioner.get_position
                read_in_pos_fn = lambda ax: self.HW.atto_positioner.wait_for_axes_to_stop([ax], max_wait_time=20.0)
                system_name = "Atto"
            elif hasattr(self, "positioner") and hasattr(self.positioner, "MoveABSOLUTE"):
                move_fn = self.positioner.MoveABSOLUTE
                get_positions_fn = self.positioner.GetPosition
                read_in_pos_fn = lambda ch: self.positioner.ReadIsInPosition(ch)
                system_name = "Femto"
            else:
                print("No valid move function found.")
                return

            # Determine the expected number of axes based on the current positions
            if system_name == "Femto":
                get_positions_fn()
                positions = [self.positioner.AxesPositions[x] for x in range(len(points[0]))]
            else:
                positions = [get_positions_fn(x) for x in range(len(points[0]))]
            if not positions:
                print("Unable to retrieve current positions. Aborting survey.")
                return

            def run_survey():
                self.perform_survey(
                    points=points,
                    move_fn=move_fn,
                    read_in_pos_fn=read_in_pos_fn,
                    get_positions_fn=get_positions_fn,
                    g2_counts=self.survey_g2_counts,
                    g2_threshold=self.survey_g2_threshold,
                    g2_timeout=self.survey_g2_timeout,
                    move_only=False,
                    search_peak_intensity_near_positions=True
                )

            self.survey_thread = threading.Thread(target=run_survey, daemon=True)
            self.survey_thread.start()
        except Exception as e:
            print(f"An error occurred in btnStartG2Survey: {e}")

    def perform_survey(
            self,
            points: List[Tuple[float, float]],
            move_fn: Callable[[int, int|float], Any],
            g2_threshold: float,
            g2_counts: int,
            g2_timeout: int,
            read_in_pos_fn: Callable[[int], Any],
            get_positions_fn: Callable[[int], Any],
            move_only: bool = False,
            search_peak_intensity_near_positions: bool = True
    ) -> None:
            """
            Perform a survey of g2 and PL scans of NV centers.

            For each (x, y) point in the provided list, the function performs the following:
              1. Sets the survey flag to True.
              2. Moves to the given point using the provided move function.
              3. Verifies positioning by reading each axis position via read_in_pos_fn and gets current positions using get_positions_fn.
              4. Starts a live counter by invoking self.btnStartCounterLive.
              5. Searches for peak intensity using self.MoveToPeakIntensity.
              6. Waits for the thread self.MAxSignalTh to complete.
              7. Stops the live counter via self.btnStop.
              8. Initiates a g2 measurement using self.btnStartG2.
              9. Waits until self.Y_vec[0] equals g2_counts (with a timeout safeguard).
             10. Stops the g2 measurement with self.btnStop.
             11. If the ratio (min(self.Y_vec) / self.Y_vec[0]) exceeds g2_threshold, starts a scan by invoking self.btnStartScan and waits for self.ScanTh to finish.
                 Otherwise, it moves on to the next point.

            Throughout the survey, progress updates are printed, including:
              - Percentage completion.
              - Number of points processed out of the total.
              - Time elapsed for the current point and overall.
              - Estimated Time of Arrival (ETA) for survey completion.

            :param points: List of (x, y) tuples representing the coordinates to survey.
            :param move_fn: A callable function that moves the system to a specified (x, y) coordinate.
            :param g2_threshold: Threshold ratio to decide whether to perform a scan.
            :param g2_counts: Expected count value for g2 measurement to wait for.
            :param g2_timeout: timeout of the g2 measurement if counts threshold was not reached. [seconds]
            :param read_in_pos_fn: A callable that accepts an axis index (int) and ensures that axis is in position.
            :param get_positions_fn: A callable that returns the current positions after reading all axes.
            :param move_only: boolean that controls if the survey only moves to positions or performs the measurements as well.
            :param search_peak_intensity_near_positions: boolean that controls if peak search is required around each location
            """
            try:
                # Set survey flag to indicate that the survey is running
                self.survey = True
                self.survey_stop_flag = False
                total_points = len(points)

                if self.HW.atto_scanner:
                    self.HW.atto_scanner.MoveABSOLUTE(1, 25)
                    self.HW.atto_scanner.MoveABSOLUTE(2, 25)

                if total_points == 0:
                    print("No points provided for the survey. Exiting function.")
                    return

                overall_start_time = time.time()  # Record the overall start time

                # Iterate over each survey point
                for idx, point in enumerate(points, start=1):
                    if self.survey_stop_flag:
                        return
                    point_start_time = time.time()
                    print(f"\n--- Starting point {idx}/{total_points}: {point} ---")

                    if self.HW.atto_scanner:
                        self.HW.atto_scanner.MoveABSOLUTE(1, 25)
                        self.HW.atto_scanner.MoveABSOLUTE(2, 25)
                        system_name="Atto"
                    else:
                        system_name="Femto"

                    # Move to the specified point using the provided move function
                    try:
                        for ax in range(len(point)):
                            move_fn(ax, point[ax])
                            read_in_pos_fn(ax)  # Ensure in position
                        current_positions = [get_positions_fn(x) for x in range(len(point))]
                        print(f"Current positions after move: {current_positions}")
                        print(f"Moved to point {point} successfully.")
                    except Exception as move_error:
                        print(f"Error moving to point {point}: {move_error}. Skipping this point.")
                        continue

                    if search_peak_intensity_near_positions:
                        # Start the live counter and search for peak intensity
                        try:
                            print("Starting live counter.")
                            self.Y_vec = []
                            self.btnStartCounterLive()
                            time.sleep(1)
                            self.wait_for_job()
                            print("Moving to peak intensity.")
                            self.MoveToPeakIntensity()
                            time.sleep(1)
                        except Exception as intensity_error:
                            print(f"Error during live counter/peak intensity at point {point}: {intensity_error}.")
                            continue
                        if self.survey_stop_flag:
                            return
                            # Wait for the MAxSignal thread to finish
                        try:
                            if hasattr(self, 'MAxSignalTh') and self.MAxSignalTh is not None:
                                print("Waiting for MAxSignal thread to complete...")
                                while self.MAxSignalTh.is_alive():
                                    time.sleep(0.1)
                                print("MAxSignal thread completed.")
                                time.sleep(3)
                            else:
                                print("MAxSignal thread not found; proceeding without waiting.")
                        except Exception as thread_error:
                            print(f"Error while waiting for MAxSignal thread at point {point}: {thread_error}.")
                            continue

                        # Stop the live counter
                        try:
                            print("Stopping live counter.")
                            self.btnStop()
                            self.wait_for_job()
                        except Exception as stop_error:
                            print(f"Error stopping live counter at point {point}: {stop_error}.")
                            continue

                    if move_only:
                        continue

                    # Start the g2 measurement
                    try:
                        print("Starting g2 measurement.")
                        self.btnStartG2()
                        g2_wait_start = time.time()
                        self.wait_for_job()
                    except Exception as g2_start_error:
                        print(f"Error starting g2 measurement at point {point}: {g2_start_error}.")
                        continue

                    # Wait until self.Y_vec[0] equals the expected g2_counts (with a timeout safeguard)
                    try:
                        print(f"Waiting for g2 measurement to reach {g2_counts} counts...")
                        timeout = g2_timeout  # maximum wait time in seconds
                        while True:
                            if self.survey_stop_flag:
                                return
                                # Ensure self.Y_vec exists and has at least one element
                            time.sleep(0.1)
                            if hasattr(self, "Y_vec") and self.Y_vec is not None and len(self.Y_vec) > 0 and self.Y_vec[0] == g2_counts:
                                break
                            if time.time() - g2_wait_start > timeout:
                                print(f"Timeout reached while waiting for g2 counts at point {point}.")
                                break

                        print("g2 measurement condition met or timeout occurred.")
                    except Exception as g2_wait_error:
                        print(f"Error during g2 measurement wait at point {point}: {g2_wait_error}.")
                        continue

                    # Stop the g2 measurement
                    try:
                        print("Stopping g2 measurement.")
                        self.btnStop()
                        if hasattr(self, 'fetchTh'):
                            while self.fetchTh.is_alive():
                                time.sleep(0.1)
                    except Exception as g2_stop_error:
                        print(f"Error stopping g2 measurement at point {point}: {g2_stop_error}.")
                        continue

                    # Evaluate g2 measurement results and decide whether to perform a scan
                    try:
                        if hasattr(self, "Y_vec") and self.Y_vec is not None and self.Y_vec[0] != 0:
                            ratio = min(self.Y_vec) / self.Y_vec[0]
                            print(f"g2 ratio: {ratio:.3f} (Threshold: {g2_threshold})")
                            if ratio < g2_threshold:
                                print("g2 condition satisfied. Initiating scan.")
                                self.btnStartScan()
                                time.sleep(1)
                                self.wait_for_job()
                                if hasattr(self, 'ScanTh') and self.ScanTh is not None:
                                    print("Waiting for Scan thread to complete...")
                                    while self.ScanTh.is_alive():
                                        time.sleep(0.1)
                                    print("Scan thread completed.")
                                    time.sleep(1)
                                else:
                                    print("Scan thread not found; proceeding without waiting.")
                            else:
                                print("g2 condition not met. Skipping scan at this point.")
                        else:
                            print("Invalid g2 measurement data. Skipping scan evaluation for this point.")
                    except Exception as scan_error:
                        print(f"Error during scan evaluation at point {point}: {scan_error}.")

                    # Calculate and display progress, elapsed time, and ETA
                    elapsed_point = time.time() - point_start_time
                    elapsed_total = time.time() - overall_start_time
                    progress_percent = (idx / total_points) * 100
                    estimated_total = (elapsed_total / idx) * total_points
                    eta = estimated_total - elapsed_total

                    print(
                        f"Point {idx}/{total_points} completed in {elapsed_point:.2f} sec. "
                        f"Overall progress: {progress_percent:.2f}% | Total elapsed: {elapsed_total:.2f} sec | ETA: {eta:.2f} sec."
                    )

                print("\nSurvey completed successfully.")

            except Exception as general_error:
                print(f"An unexpected error occurred during the survey: {general_error}.")

            finally:
                # Reset the survey flag when done
                self.survey = False

    def wait_for_job(self):
        try:
            while not self.job:
                time.sleep(1)
            if hasattr(self.job, "wait_for_execution"):
                self.job.wait_for_execution()
            time.sleep(1)
        except Exception as e:
            print(f'Error while waiting for job: {e}')

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
        self.mwModule.Set_IQ_mode_ON()
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
            self.mwModule.Set_IQ_mode_ON()
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
        self.mwModule.Set_IQ_mode_ON()
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
        self.mwModule.Set_IQ_mode_ON()
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
            if self.survey_thread is not None and self.survey_thread.is_alive() and self.stop_survey:
                # Signal the survey thread to stop gracefully, e.g., by setting a stop flag
                self.survey_stop_flag = True
                self.survey_thread.join()
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

            if not self.simulation and self.job:
                self.StopJob(self.job, self.qm)

            if not self.exp == Experiment.SCAN:
                if hasattr(self, 'fetchTh'):
                    while self.fetchTh.is_alive():
                        # if not(self.pgm_end):
                        time.sleep(0.1)
            else:
                dpg.enable_item("btnOPX_StartScan")

            self.Shoot_Femto_Pulses = False

            if self.exp == Experiment.COUNTER or self.exp == Experiment.SCAN or self.exp == Experiment.G2:
                self.counter_is_live=False
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
                # folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + (fr'Survey{self.HW.config.system_type}/' if self.survey else '') + self.exp.name + '/'
                folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + f'/{self.HW.config.system_type}'
            else:
                folder_path = folder + (fr'Survey{self.HW.config.system_type}/' if self.survey else '') + self.exp.name + '/'

            if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
                os.makedirs(folder_path)
            if self.exp == Experiment.RandomBenchmark:
                #self.added_comments = dpg.get_value("inTxtOPX_expText")
                if self.added_comments is not None:
                    fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name + '_' + self.added_comments)
                else:
                    fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name)
            else:
                fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name+ '_' + self.expNotes)
            # fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)

            # parameters + note        
            self.writeParametersToXML(fileName + ".xml")
            print(f'XML file saved to {fileName}.xml')
            self.to_xml()

            # raw data
            if self.exp == Experiment.RandomBenchmark:
                RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y_ref2': self.Y_vec_ref2,'Gate_Order': self.benchmark_number_order, 'Y_vec_squared': self.Y_vec_squared, 'Y_ref3': self.Y_vec_ref3}
            elif self.exp == Experiment.NUCLEAR_MR:
                RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y2': self.Y_vec2, 'Y_ref2': self.Y_vec_ref2}
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

    def btnFemtoPulses(self):
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!! Shooting femto pulses !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        self.Shoot_Femto_Pulses = True
        self.ScanTh = threading.Thread(target=self.scan3d_femto_pulses)
        self.ScanTh.start()

    def btnStartScan(self, add_scan=False, isLeftScan = False):
        self.ScanTh = threading.Thread(target=self.StartScan,args=(add_scan, isLeftScan))
        self.ScanTh.start()

    def btnStartGalvoScan(self, add_scan=False):
        self.ScanTh = threading.Thread(target=self.scan3d_with_galvo)
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

    def Z_correction(self, _refp: list, _point: list):
        # Define the points (self.positioner.LoggedPoints equivalent)
        P = np.array(self.positioner.LoggedPoints)
        refP = np.array(_refp)
        point = np.array(_point)

        # Vector U and normalization
        U = P[1, :] - P[0, :]
        u = U / np.linalg.norm(U)

        # Vector V and normalization
        V = P[2, :] - P[0, :]
        v = V / np.linalg.norm(V)

        # Cross product to find the normal vector N
        N = np.cross(u, v)

        # Calculate D
        D = -np.dot(refP, N)

        # Calculate the new points Pnew
        # Pnew = -(point[:, :2] @ N[:2] + D) / N[2]
        Znew = -(point[:2] @ N[:2] + D) / N[2]

        # print(Znew)

        return Znew

    def set_hwp_angle(self, new_hwp_angle: float):
        """
        Move the half-wave plate (HWP) to exactly new_hwp_angle degrees.
        Blocks until the motion is within 0.01°.
        """
        try:
            print(f"!!!!! set HWP to {new_hwp_angle:.2f} deg !!!!!")
            # Kick off the motion
            self.kdc_101.MoveABSOLUTE(new_hwp_angle)
            time.sleep(0.2)

            # Poll until within 0.01°
            current_hwp = self.kdc_101.get_current_position()
            while abs(current_hwp - new_hwp_angle) > 0.01:
                time.sleep(0.2)
                current_hwp = self.kdc_101.get_current_position()

            return current_hwp
        except Exception as e:
            print(f"Error in set_hwp_angle: {e}")

    def btnUpdateImages(self):
        self.Plot_Loaded_Scan(use_fast_rgb=True)

    def Plot_data(self, data, bLoad=False):
        np_array = np.array(data) #numpy array of the csv data
        self.scan_Out=np_array # new
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
        self.startLoc = [np_array[1, x] for x in [4,5,6]]
        self.endLoc = [np_array[-1, x] for x in [4,5,6]]

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

    def create_scan_file_name(self, local=False):
        """
            Create a file name for saving a scan, adjusting the folder path based on survey mode.

            If 'local' is True, the scan data will be saved to a local temporary folder.
            Otherwise, if self.survey is True, the scan will be saved into:
                Q:/QT-Quantum_Optic_Lab/expData/survey{system_type}/scan
            If self.survey is False, the scan will be saved into:
                Q:/QT-Quantum_Optic_Lab/expData/scan/{system_type}

            The file name includes a timestamp, experiment name, and experiment notes.

            :param local: Boolean flag indicating whether to use a local folder.
            :return: The full file path for the scan file.
            """
        # file name
        timeStamp = self.getCurrentTimeStamp()  # get current time stamp
        if local:
            folder_path = "C:/temp/TempScanData/"
        else:
            # Determine folder path based on survey mode
            if hasattr(self, "survey") and self.survey:
                folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/survey{self.HW.config.system_type}/scan'
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
        self.timeStamp = timeStamp
        self.last_loaded_file=fileName
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

        # Initialize normalized array
        normalized_array = np.zeros_like(Array2D, dtype=float)

        # Prevent division by zero
        if np.any(mask_non_zero):
            max_val = Array2D[mask_non_zero].max()
            if max_val > 0:
                normalized_array[mask_non_zero] = Array2D[mask_non_zero] / max_val

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

    def calculate_g2(self, correlated_histogram: Union[List[float], np.ndarray]) -> float:
        # Ensure that correlated_histogram has at least 40 elements
        if len(correlated_histogram) < 40:
            print("correlated_histogram should have at least 40 elements.")
            return 1

        # Compute the average of the first 10 points
        avg_first_10 = np.mean(correlated_histogram[:10])

        # Compute the center index (center of the array)
        center_index = len(correlated_histogram) // 2

        # Compute the indices for the 10 points around the center (+-5 from the center)
        start_idx = max(center_index - 5, 0)
        end_idx = min(center_index + 5 + 1, len(correlated_histogram))

        # Use the minimum of the 10 center values
        min_center_10 = np.min(correlated_histogram[start_idx:end_idx])

        # Return the ratio: min(center 10) / avg(first 10)
        return np.min([min_center_10 / (avg_first_10 + np.finfo(float).eps), 1])

# ***************************************************************
#              --------- note ---------                         *
# this file was a workaround to make fast integration to OPX    *
# actually we need to split to OPX wrapper and OPX GUI          *
# ***************************************************************
import csv, random, pdb
import traceback
from datetime import datetime
import os, shutil, subprocess, sys, threading, time, traceback, math, copy, JobTesting_OPX
import xml.etree.ElementTree as ET
from enum import Enum
from typing import Union, Optional, Callable, List, Tuple, Any
import dearpygui.dearpygui as dpg
import glfw, matplotlib, json
import numpy as np
from collections import Counter
from qm.jobs.base_job import QmBaseJob
from qm.qua._expressions import QuaVariable, QuaVariableType
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig, QuantumMachine, QmJob, QmPendingJob
from qm.qua import update_frequency, frame_rotation, frame_rotation_2pi, declare_stream, declare, program, for_, assign, \
    elif_, if_, IO1, IO2, time_tagging, measure, play, wait, align, else_, \
    save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger, counting, Math, Cast, case_, \
    switch_, strict_timing_, declare_input_stream
from gevent.libev.corecext import callback
from matplotlib import pyplot as plt
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from qualang_tools.results import progress_counter, fetching_tool
from functools import partial
from qualang_tools.units import unit
import SystemConfig as configs
from Common import WindowNames, load_window_positions, toggle_sc, show_msg_window, Experiment
from HW_wrapper import HW_devices as hw_devices, smaractMCS2
from SystemConfig import SystemType
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized, create_scan_vectors, loadFromCSV, \
    open_file_dialog, create_gaussian_vector,\
    open_file_dialog, create_gaussian_vector, create_counts_vector, OptimizerMethod, find_max_signal
from PIL import Image
from HW_wrapper.Wrapper_Pharos import PharosLaserAPI
from Experiment_handlers.scan3d_handler import *
from Experiment_handlers.save_load_handler import *
from Experiment_handlers.Opx_gui_handler import *
from Experiment_handlers.QUA_handler import *
from Experiment_handlers.Find_max_handler import *
from Experiment_handlers.btn_experiments_handler import *

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
        self._bind_by_names([
            "StartScan3D", "scan3d_femto_pulses", "scan3d_with_galvo", "start_scan_general",
            "scan_reset_data", "scan_reset_positioner", "scan_get_current_pos", "StartScan",
            "save_to_cvs", "writeParametersToXML", "to_xml", "update_from_xml", "saveExperimentsNotes",
            "save_scan_data", "btnLoadScan", "prepare_scan_data", "save_scan_parameters",
            "load_scan_parameters", "move_last_saved_files", "Save_2D_matrix2IMG", "Plot_Loaded_Scan",
            "Update_bX_Scan", "Update_bY_Scan", "Update_bZ_Scan", "Update_dX_Scan", "Update_dY_Scan",
            "Update_dZ_Scan", "Update_Lx_Scan", "Update_Ly_Scan", "Update_Lz_Scan", "Update_bZcorrection",
            "GetItemsVal", "set_moveabs_to_max_intensity", "fill_moveabs_with_picture_center",
            "fill_moveabs_from_query", "fill_z", "toggle_limit", "queryXY_callback", "queryYZ_callback",
            "queryXZ_callback", "Calc_estimatedScanTime", "time_in_multiples_cycle_time",
            "UpdateCounterIntegrationTime", "toggle_sum_counters", "UpdateWaitTime", "UpdateEdgeTime",
            "UpdateTcounter", "UpdateTpump", "UpdateTcounterPulsed", "UpdateNumOfPoint",
            "Update_mwResonanceFreq", "Update_mwP_amp", "Update_mwP_amp2", "Update_off_time",
            "Update_T_bin", "Update_AWG_interval", "Update_AWG_f_1", "Update_AWG_f_2", "Update_mwP_amp3",
            "Update_mw_2ndfreq_resonance", "Update_mwFreq", "Update_df", "UpdateScanRange", "UpdateMWpwr",
            "UpdateN_nuc_pump", "UpdateN_p_amp", "UpdateN_CPMG", "UpdateNavg", "UpdateCorrelationWidth",
            "UpdateN_measure", "UpdateMW_dif", "UpdatedN", "Update_back_freq", "Update_gate_number",
            "UpdateN_tracking_search", "UpdateN_survey_g2_counts", "UpdateN_survey_g2_threshold",
            "UpdateN_survey_g2_timeout", "toggle_stop_survey", "UpdateT_rf_pulse_time", "UpdateT_mw",
            "UpdateT_mw2", "UpdateT_mw3", "Update_rf_pulse_time", "Update_tGetTrackingSignalEveryTime",
            "Update_tTrackingSignaIntegrationTime", "Update_TrackingThreshold", "UpdateScanTstart",
            "on_off_slider_callback", "UpdateTsettle", "UpdateScanT_dt", "UpdateScanTend",
            "Update_rf_resonance_Freq", "Update_rf_Freq", "Update_rf_ScanRange", "Update_rf_df",
            "Update_rf_pwr", "Update_Intensity_Tracking_state", "Update_QUA_Shuffle_state",
            "Update_QUA_Simulate_state", "hide_legend", "GetWindowSize", "set_all_themes", "Plot_Scan",
            "UpdateGuiDuringScan", "UpdateGuiDuringScan_____", "Update_scan", "reset_data_val",
            "initQUA_gen", "QUA_execute", "verify_insideQUA_FreqValues", "GenVector",
            "get_detector_input_type", "get_time_tagging_func", "QUA_shuffle", "MW_and_reverse",
            "MW_and_reverse_general", "QUA_Pump", "QUA_PGM", "QUA_PGM_No_Tracking", "execute_QUA",
            "QUA_measure_with_sum_counters", "tile_to_length", "play_random_qua_gate",
            "play_random_reverse_qua_gate", "play_random_qua_two_qubit_gate",
            "play_random_reverse_qua_two_qubit_gate", "benchmark_play_list_of_gates",
            "benchmark_play_list_of_two_qubit_gates", "create_random_qua_vector",
            "create_non_random_qua_vector", "generate_random_qua_integer_benchmark", "reverse_qua_vector",
            "benchmark_state_preparation", "benchmark_state_readout", "Random_Benchmark_QUA_PGM",
            "single_shot_play_list_of_gates", "single_shot_measure_nuclear_spin", "Single_shot_QUA_PGM",
            "Test_Crap_QUA_PGM", "Nuclear_Pol_ESR_QUA_PGM", "QUA_prepare_state", "QUA_measure", "QUA_ref0",
            "QUA_ref1", "Entanglement_gate_tomography_QUA_PGM", "repeated_time_bin_qua_sequence_start",
            "repeated_time_bin_qua_sequence_end", "time_bin_entanglement_QUA_PGM", "Population_gate_tomography_QUA_PGM",
            "MZI_g2", "g2_raw_QUA", "ODMR_Bfield_QUA_PGM", "NuclearFastRotation_QUA_PGM",
            "Electron_lifetime_QUA_PGM", "Nuclear_spin_lifetimeS0_QUA_PGM",
            "Nuclear_spin_lifetimeS1_QUA_PGM", "Nuclear_Ramsay_QUA_PGM", "Electron_Coherence_QUA_PGM",
            "Hahn_QUA_PGM", "NuclearSpinPolarization_pulsedODMR_QUA_PGM", "NuclearMR_QUA_PGM",
            "NuclearRABI_QUA_PGM", "PulsedODMR_QUA_PGM", "RABI_QUA_PGM", "ODMR_CW_QUA_PGM",
            "TrackingCounterSignal_QUA_PGM", "counter_QUA_PGM", "awg_sync_counter_QUA_PGM",
            "MeasureByTrigger_QUA_PGM", "MeasurePLE_QUA_PGM", "FindMaxSignal", "FindFocus",
            "Find_max_signal_by_keysight_offset", "FindMaxSignal_atto_positioner_and_scanner",
            "FindMaxSignal_atto_positioner", "MoveToPeakIntensity", "SearchPeakIntensity",
            "calculate_tracking_bounds","Z_correction", "set_hwp_angle","btnUpdateImages","Plot_data",
            "attempt_to_display_unfinished_frame", "check_last_period", "create_scan_file_name",
            "move_single_step", "readInpos", "check_srs_stability", "change_AWG_freq","change_AWG_freq",
            "getCurrentTimeStamp","convert_to_correct_type","fast_rgb_convert","extract_vectors",
            "calculate_g2","btnFemtoPulses","btnStartScan","btnStartGalvoScan","btnStartPLE",
            "btnStartExternalFrequencyScan","btnStartAWG_FP_SCAN","StartPLE","btnStartG2Survey",
            "perform_survey","btnSave","fetch_peak_intensity","Update_close_all_qm",
            "Update_benchmark_switch_flag","Update_benchmark_one_gate_only","Common_updateGraph",
            "generate_x_y_vectors_for_average","ensure_list","FetchData","GlobalFetchData","btnStartG2",
            "btnStartEilons","StartFetch","repeat_elements","btnStartCounterLive","wait_for_job",
            "btnStartODMR_CW","btnStartRABI","btnStartODMR_Bfield","btnStartNuclearFastRot","btnStartPulsedODMR",
            "btnStartNuclearRABI","btnStartRandomBenchmark","btnStartPopulateGateTomography",
            "btnStartStateTomography","btnStartTimeBinEntanglement","btnStartNuclearPolESR",
            "btnStartNuclearMR","btnStartNuclearSpinLifetimeS0","btnStartNuclearSpinLifetimeS1",
            "btnStartNuclearRamsay","btnStartElectron_Coherence","btnStartHahn","btnStartElectronLifetime",
            "StopJob","stop_benchmark","btnStop","delayed_actions","get_device_position",
            "intensity_to_rgb_heatmap","FastScan_updateGraph"
        ])
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

    def _bind_by_names(self, names, ns=None):
        ns = ns or globals()
        for name in names:
            setattr(self, name, ns[name].__get__(self))

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






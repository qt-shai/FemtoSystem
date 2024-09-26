# ***************************************************************
#              --------- note ---------                         *
# this file was a workaround to make fast integration to OPX    *
# actually we need to split to OPX wrapper and OPX GUI          *
# ***************************************************************
import csv
from datetime import datetime
import os
import sys
import threading
import time
from enum import Enum
from tkinter import filedialog
from typing import Union
import glfw
import numpy as np
import tkinter as tk
from matplotlib import pyplot as plt
from qm.qua import update_frequency, declare_stream, declare, program, for_, assign, if_, IO1, time_tagging, measure, \
    play, wait, align, else_, save, stream_processing, amp, Random, fixed, pause, infinite_loop_, wait_for_trigger
from qualang_tools.results import fetching_tool
from functools import partial
from qualang_tools.units import unit
from qm import generate_qua_script, QuantumMachinesManager, SimulationConfig
from smaract import ctl
import matplotlib
from HW_wrapper import HW_devices as hw_devices
from Utils import calculate_z_series, intensity_to_rgb_heatmap_normalized
import dearpygui.dearpygui as dpg
from PIL import Image
import subprocess
import shutil
import xml.etree.ElementTree as ET
import math
import SystemConfig as configs

matplotlib.use('qtagg')

def create_logger(log_file_path: str):
    log_file = open(log_file_path, 'w')
    return subprocess.Popen(['npx', 'pino-pretty'], stdin=subprocess.PIPE, stdout=log_file)

class QuaCFG():
    # init variables 
    # todo: create Qua calibration/parameters table
    def __init__(self) -> None:
        self.u = unit()
        self.opx_ip = '192.168.101.56'
        self.opx_port = 80
        self.opx_cluster = 'Cluster_1'

        # Frequencies
        self.NV_IF_freq = 124e6  # in units of Hz
        self.NV_LO_freq = 2.7e9  # in units of Hz (Omega_0, not relevant when using calibrated oscillator e.g R&S)

        # Pulses lengths
        self.initialization_len = 5000  # in ns
        self.meas_len = 300  # in ns
        self.minimal_meas_len = 16  # in ns
        self.long_meas_len = 5e3  # in ns
        self.very_long_meas_len = 25e3  # in ns

        # MW parameters
        self.mw_amp_NV = 0.5  # in units of volts
        self.mw_len_NV = 100  # in units of ns

        self.pi_amp_NV = 0.5  # in units of volts
        self.pi_len_NV = 16  # in units of ns

        self.pi_half_amp_NV = self.pi_amp_NV / 2  # in units of volts
        self.pi_half_len_NV = self.pi_len_NV  # in units of ns

        # MW Switch parameters
        self.switch_delay = 94#410  # in ns add delay of 94 ns to the digital signal
        self.switch_buffer = 0#10  # in ns add extra 10 ns at the beginning and end of the digital pulse
        self.switch_len = 100  # in ns

        # Readout parameters
        self.signal_threshold = -400  # in ADC units #12bit signal -0.5 to +0.5 ==> 4096/1 (bits/volt)
        self.signal_threshold_OPD = 0.1  # in voltage

        # Delays
        self.detection_delay = 112  # ns (mod4 > 36)
        self.detection_delay_OPD = 308#160
        self.mw_delay = 0#300  # ns
        self.laser_delay = 120

        # RF parameters
        self.rf_frequency = 3.03 * self.u.MHz
        self.rf_amp = 0.1
        self.rf_length = 1000
        self.rf_delay = 8 #* self.u.ns

        self.logger = None

        # IQ imbalance matrix

    def iq_imbalance(self, g, phi):
        """
        Creates the correction matrix for the mixer imbalance caused by the gain and phase imbalances, more information can
        be seen here:
        https://docs.qualang.io/libs/examples/mixer-calibration/#non-ideal-mixer

        :param g: relative gain imbalance between the I & Q ports (unit-less). Set to 0 for no gain imbalance.
        :param phi: relative phase imbalance between the I & Q ports (radians). Set to 0 for no phase imbalance.
        """
        c = np.cos(phi)
        s = np.sin(phi)
        N = 1 / ((1 - g ** 2) * (2 * c ** 2 - 1))
        return [float(N * x) for x in [(1 - g) * c, (1 + g) * s, (1 - g) * s, (1 + g) * c]]

    # Hot system
    def GetConfig(self):
        return {
            "version": 1,

            "controllers": {
                "con1": {
                    "type": "opx1",
                    "analog_outputs": {  # OPX outputs
                        1: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},  # MW I, offset = amplitude (v), delay = time (ns)
                        2: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},  # MW Q
                        3: {"offset": 0.0, "delay": self.rf_delay, "shareable": True},  # RF 
                    },
                    "digital_outputs": {  # OPX outputs
                        1: {"shareable": True},  # Laser
                        2: {"shareable": True},  # MW switch
                        3: {"shareable": True},  # Photo diode. Actual cable is not connected (kind of virtual, however we cannot use this channel when in use)
                        4: {"shareable": True},  # Smaract TTL
                        # 5: {"shareable": True},  # Laser in new location 
                    },
                    "analog_inputs": {  # OPX inputs
                        1: {"offset": 0.00979, 'gain_db': 0, "shareable": True},
                        # Detector, use 02_raw_adc_traces.py to calc the offset. minus to attenuate and pluse to amplify (range: -12db up to +20db, )
                    },
                    'digital_inputs': {  #OPD inputs
                        1: {'polarity': 'RISING', 'deadtime': 4, "threshold": self.signal_threshold_OPD, "shareable": True},  #4 to 16nsec,
                    },
                }
            },

            "elements": {  # OPX output will be written here as input and vice versa
                "RF": {
                    "singleInput": {"port": ("con1", 3)},
                    "intermediate_frequency": self.rf_frequency,
                    "operations": {
                        "const": "const_pulse_single",
                    },
                },
                # "NV": {  # example how to write inside program: play("cw", "NV")
                "MW": {  # example how to write inside program: play("cw", "MW")
                    "mixInputs": {"I": ("con1", 1), "Q": ("con1", 2), "lo_frequency": self.NV_LO_freq,
                                  "mixer": "mixer_NV"},
                    # 'mixInputs' is QUA specifically for i&q which automatically refers to 'analog_outputs' in this example 1 &2
                    "intermediate_frequency": self.NV_IF_freq,
                    "digitalInputs": {  # 'digitalInputs' is actually 'digital_outputs'. RF switch (ON/OFF)
                        "marker": {
                            "port": ("con1", 2),
                            "delay": self.switch_delay,  # delay in digital channel
                            "buffer": self.switch_buffer,  # widen the pulse in the beginning and the end of this pulse
                        },
                        # "marker2": {
                        #     "port": ("con1", 3),
                        #     "delay": switch_delay,
                        #     "buffer": switch_buffer,
                        # },
                    },
                    # "digitalInputs": {  # RF switch (ON/OFF
                    #     "marker": {
                    #         "port": ("con1", 3),
                    #         "delay": switch_delay,
                    #         "buffer": switch_buffer,
                    #     },
                    # },
                    "operations": {  # waveform + pulses
                        "xPulse": "x_pulse",
                        "yPulse": "y_pulse",
                        "cw": "const_pulse",
                        "pi": "x180_pulse",
                        "pi_half": "x90_pulse",
                        "x180": "x180_pulse",
                        "x90": "x90_pulse",
                        "-x90": "-x90_pulse",
                        "y180": "y180_pulse",
                        "y90": "y90_pulse",
                    },
                },

                # "AOM": { # AOM is arbitrary name, in our system it is just LASER
                "Laser": {  # Laser is arbitrary name, in our system it is just LASER
                    "digitalInputs": {  # for the OPX it is digital outputs
                        "marker": {  # marker is arbitrary name
                            "port": ("con1", 1),  # CH NUM
                            "delay": self.laser_delay,
                            "buffer": 0,  # buffer <= laser_delay, amir: TBD to understand it
                        },
                    },
                    "operations": {
                        # "laser_ON": "laser_ON",
                        "Turn_ON": "laser_ON",
                    },
                },

                # TODO: With Daniel - Set correct parameters for triggering smaract
                "SmaractTrigger": {  # Send trigger to Smaract to go to next point in motion stream
                    "digitalInputs": {  # for the OPX it is digital outputs
                        "marker": {  # marker is arbitrary name
                            "port": ("con1", 4),  # CH NUM
                            "delay": 0,
                            "buffer": 0,  # buffer <= laser_delay, amir: TBD to understand it
                        },
                    },
                    "operations": {
                        # "laser_ON": "laser_ON",
                        "Turn_ON": "laser_ON",
                    },
                },

                "MW_switch": {
                    "digitalInputs": {
                        "marker": {
                            "port": ("con1", 2),
                            "delay": self.switch_delay,
                            "buffer": self.switch_buffer,
                        },
                    },
                    "operations": {
                        "ON": "switch_ON",
                    },
                },

                # "SPCM": {
                "Detector": {
                    "singleInput": {"port": ("con1", 1)},  # not used but must stay here

                    "digitalInputs": {
                        # 'digitalInputs' is actually 'digital_outputs' in OPX. needed for gating for raw ADC (optional) relevant for calibration
                        "marker": {
                            "port": ("con1", 3),
                            "delay": self.detection_delay,
                            # for example measure laser + detector howevr there is a delay since the photons have time of flight (so compensation is required)
                            "buffer": 0,
                        },
                    },
                    "operations": {
                        "readout": "readout_pulse",
                        "long_readout": "long_readout_pulse",
                    },
                    "outputs": {"out1": ("con1", 1)},  # 'output' here is actually analog input of OPX

                    "outputPulseParameters": {
                        "signalThreshold": self.signal_threshold,
                        "signalPolarity": "Descending",
                        "derivativeThreshold": 1023,
                        "derivativePolarity": "Descending",
                    },
                    "time_of_flight": self.detection_delay,
                    "smearing": 0,
                },

                "Detector_OPD": {
                    "singleInput": {"port": ("con1", 1)},  # not used
                    "digitalInputs": {
                        "marker": {
                            "port": ("con1", 3),
                            "delay": self.detection_delay_OPD,
                            "buffer": 0,
                        },
                    },
                    'digitalOutputs': {  # 'digitalOutputs' here is actually 'digital input' of OPD
                        'out1': ('con1', 1)
                    },
                    "outputs": {"out1": ("con1", 1)},
                    "operations": {
                        "readout": "readout_pulse",
                        "min_readout": "min_readout_pulse",
                        "long_readout": "long_readout_pulse",
                        "very_long_readout": "very_long_readout_pulse",
                    },
                    "time_of_flight": self.detection_delay_OPD,
                    "smearing": 0,
                },
            },

            "pulses": {
                "const_pulse_single": {
                    "operation": "control",
                    "length": self.rf_length,  # in ns
                    "waveforms": {"single": "rf_const_wf"},
                },
                "x_pulse": {
                    "operation": "control",
                    "length": self.mw_len_NV,
                    "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
                    "digital_marker": "ON",  # 'ON' is digital waveform name
                },
                "y_pulse": {
                    "operation": "control",
                    "length": self.mw_len_NV,
                    "waveforms": {"I": "zero_wf", "Q": "cw_wf"},  # 'cw_wf' is analog waveform name
                    "digital_marker": "ON",  # 'ON' is digital waveform name
                },
                "const_pulse": {
                    "operation": "control",
                    "length": self.mw_len_NV,
                    "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
                    "digital_marker": "ON",  # 'ON' is digital waveform name
                },
                "x180_pulse": {
                    "operation": "control",
                    "length": self.pi_len_NV,
                    "waveforms": {"I": "pi_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "x90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "pi_half_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "-x90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "-pi_half_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "y180_pulse": {
                    "operation": "control",
                    "length": self.pi_len_NV,
                    "waveforms": {"I": "zero_wf", "Q": "pi_wf"},
                    "digital_marker": "ON",
                },
                "y90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "zero_wf", "Q": "pi_half_wf"},
                    "digital_marker": "ON",
                },
                # TODO: With Daniel - understand how pulse length is determined
                "laser_ON": {
                    "operation": "control",
                    "length": self.initialization_len,
                    "digital_marker": "ON",
                },                
                "switch_ON": {
                    "operation": "control",
                    "length": self.switch_len,
                    "digital_marker": "ON",
                },
                "readout_pulse": {
                    "operation": "measurement",
                    "length": self.meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "min_readout_pulse": {
                    "operation": "measurement",
                    "length": self.minimal_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "long_readout_pulse": {
                    "operation": "measurement",
                    "length": self.long_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "very_long_readout_pulse": {
                    "operation": "measurement",
                    "length": self.very_long_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },                
            },

            "waveforms": {
                "rf_const_wf": {"type": "constant", "sample": self.rf_amp},
                "cw_wf": {"type": "constant", "sample": self.mw_amp_NV},
                "pi_wf": {"type": "constant", "sample": self.pi_amp_NV},
                "pi_half_wf": {"type": "constant", "sample": self.pi_half_amp_NV},
                "-pi_half_wf": {"type": "constant", "sample": -self.pi_half_amp_NV},
                "zero_wf": {"type": "constant", "sample": 0.0},
            },

            "digital_waveforms": {
                "ON": {"samples": [(1, 0)]},  # [(on/off, ns)]
                "test": {"samples": [(1, 4), (0, 8), (1, 12)]},
                # [(on/off, ns)] arbitrary example digital waveform total length /4 shoult be integer
                "OFF": {"samples": [(0, 0)]},  # [(on/off, ns)]
            },

            "mixers": {
                "mixer_NV": [
                    {"intermediate_frequency": self.NV_IF_freq, "lo_frequency": self.NV_LO_freq,
                     "correction": self.iq_imbalance(0.0, 0.0)},
                ],
            },

        }

    # Femto/scan
    def GetConfigFemto(self):
        return {
            "version": 1,

            "controllers": {
                "con1": {
                    "type": "opx1",
                    "analog_outputs": {  # OPX outputs
                        1: {"offset": 0.0, "delay": self.rf_delay, "shareable": True},   
                    },
                    "digital_outputs": {  # OPX outputs
                        6: {"shareable": True},  # Smaract TTL 
                        7: {"shareable": True},  # Laser 
                        8: {"shareable": True},  # Photo diode marker. Actual cable is not connected (kind of virtual, however we cannot use this channel when in use)
                    },
                    "analog_inputs": {  # OPX inputs
                        1: {"offset": 0.00979, 'gain_db': 0, "shareable": True},
                        2: {"offset": 0.00979, 'gain_db': 0, "shareable": True},
                    },
                    'digital_inputs': {  #OPD inputs
                        2: {'polarity': 'RISING', 'deadtime': 4, "threshold": self.signal_threshold_OPD, "shareable": True},  #4 to 16nsec,
                    },
                }
            },

            "elements": { 
                "Laser": {  # Laser is arbitrary name, in our system it is just LASER
                    "digitalInputs": {  # for the OPX it is digital outputs
                        "marker": {  # marker is arbitrary name
                            "port": ("con1", 7),  # CH NUM
                            "delay": self.laser_delay,
                            "buffer": 0,  # buffer <= laser_delay
                        },
                    },
                    "operations": {
                        # "laser_ON": "laser_ON",
                        "Turn_ON": "laser_ON",
                    },
                },

                "Detector_OPD": {
                    "singleInput": {"port": ("con1", 1)},  # not used
                    "digitalInputs": {
                        # "marker": {
                        #     "port": ("con1", 8),
                        #     "delay": self.detection_delay_OPD,
                        #     "buffer": 0,
                        # },
                    },
                    'digitalOutputs': {  # 'digitalOutputs' here is actually 'digital input' of OPD
                        'out1': ('con1', 2)
                    },
                    "outputs": {"out1": ("con1", 2)},
                    "operations": {
                        "readout": "readout_pulse",
                        "min_readout": "min_readout_pulse",
                        "long_readout": "long_readout_pulse",
                        "very_long_readout": "very_long_readout_pulse",
                    },
                    "time_of_flight": self.detection_delay_OPD,
                    "smearing": 0,
                }, 
                
                "SmaractTrigger": {  # Send trigger to Smaract to go to next point in motion stream
                    "digitalInputs": {  # for the OPX it is digital outputs
                        "marker": {  # marker is arbitrary name
                            "port": ("con1", 6),  # CH NUM
                            "delay": 0,
                            "buffer": 0,  # buffer <= laser_delay, amir: TBD to understand it
                        },
                    },
                    "operations": {
                        "Turn_ON": "laser_ON",
                    },
                },
            },

            "pulses": {
                "const_pulse_single": {
                    "operation": "control",
                    "length": self.rf_length,  # in ns
                    "waveforms": {"single": "rf_const_wf"},
                },

                "const_pulse": {
                    "operation": "control",
                    "length": self.mw_len_NV,
                    "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
                    "digital_marker": "ON",  # 'ON' is digital waveform name
                },
                "x180_pulse": {
                    "operation": "control",
                    "length": self.pi_len_NV,
                    "waveforms": {"I": "pi_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "x90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "pi_half_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "-x90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "-pi_half_wf", "Q": "zero_wf"},
                    "digital_marker": "ON",
                },
                "y180_pulse": {
                    "operation": "control",
                    "length": self.pi_len_NV,
                    "waveforms": {"I": "zero_wf", "Q": "pi_wf"},
                    "digital_marker": "ON",
                },
                "y90_pulse": {
                    "operation": "control",
                    "length": self.pi_half_len_NV,
                    "waveforms": {"I": "zero_wf", "Q": "pi_half_wf"},
                    "digital_marker": "ON",
                },
                "laser_ON": {
                    "operation": "control",
                    "length": self.initialization_len,
                    "digital_marker": "ON",
                },                
                "switch_ON": {
                    "operation": "control",
                    "length": self.switch_len,
                    "digital_marker": "ON",
                },
                "readout_pulse": {
                    "operation": "measurement",
                    "length": self.meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "min_readout_pulse": {
                    "operation": "measurement",
                    "length": self.minimal_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "long_readout_pulse": {
                    "operation": "measurement",
                    "length": self.long_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },
                "very_long_readout_pulse": {
                    "operation": "measurement",
                    "length": self.very_long_meas_len,
                    "digital_marker": "ON",
                    "waveforms": {"single": "zero_wf"},
                },                
            },

            "waveforms": {
                "rf_const_wf": {"type": "constant", "sample": self.rf_amp},
                "cw_wf": {"type": "constant", "sample": self.mw_amp_NV},
                "pi_wf": {"type": "constant", "sample": self.pi_amp_NV},
                "pi_half_wf": {"type": "constant", "sample": self.pi_half_amp_NV},
                "-pi_half_wf": {"type": "constant", "sample": -self.pi_half_amp_NV},
                "zero_wf": {"type": "constant", "sample": 0.0},
            },

            "digital_waveforms": {
                "ON": {"samples": [(1, 0)]},  # [(on/off, ns)]
                "test": {"samples": [(1, 4), (0, 8), (1, 12)]},
                "OFF": {"samples": [(0, 0)]},  # [(on/off, ns)]
            },

            "mixers": {
                "mixer_NV": [
                    {"intermediate_frequency": self.NV_IF_freq, "lo_frequency": self.NV_LO_freq,
                    "correction": self.iq_imbalance(0.0, 0.0)},
                ],
            },

        }   

class Experimet(Enum):
    SCRIPT = 0
    RABI = 1
    ODMR_CW = 2
    COUNTER = 4
    PULSED_ODMR = 5
    NUCLEAR_RABI = 6
    NUCLEAR_POL_ESR = 7
    NUCLEAR_MR = 8
    FAST_SCAN = 10
    SCAN = 11
    Nuclear_spin_lifetimeS0 = 12
    Nuclear_spin_lifetimeS1 = 13
    Nuclear_Ramsay = 14
    Hahn = 15
    Electron_lifetime = 16
    Electron_Coherence = 17

class queried_plane(Enum):
    XY = 0
    YZ = 1
    XZ = 2
    
class Axis(Enum):
    Z = 0
    Y = 1
    X = 2

class GUI_OPX(): #todo: support several device
    # init parameters
    def __init__(self, simulation:bool = False):
        # At the end of the init - all values are overwritten from XML!
        # To update values of the parameters - update the XML or the corresponding place in the GUI

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
        self.smaract_ttl_duration = 0.001  #ms, updated from XML (loaded using 'self.update_from_xml()')
        self.fast_scan_enabled = False
        self.lock = threading.Lock()

        # Coordinates + scan XYZ parameters
        self.scan_Out = []
        self.scan_data = np.zeros(shape=[80, 80, 60])
        self.queried_area = None
        self.queried_plane = None # 0 - XY, 1 - YZ, 2 -XZ
        self.bScanChkbox = False
        self.L_scan = [5000, 5000, 5000]  # [nm]
        self.dL_scan = [100, 100, 100]  # [nm]
        self.b_Scan = [True, True, False]
        self.b_Zcorrection = False
        self.use_picomotor = False
        self.ZCalibrationData: np.ndarray | None = None
        self.Zcorrection_threshold = 10 # [nm]
        self.iniShift_scan = [0, 0, 0]  # [nm]
        self.ini_scan_pos = [0, 0, 0]  # [nm]
        self.idx_scan = [0, 0, 0] # Z Y X
        self.startLoc=[0, 0, 0] 
        self.endLoc=[0, 0, 0]
        self.dir = 1
        self.estimatedScanTime = 0  # [minutes]
        self.singleStepTime_scan = 0.033  # [sec]
        self.stopScan = True
        self.scanFN = ""

        self.bEnableShuffle = True
        self.bEnableSimulate = False
        # tracking ref
        self.bEnableSignalIntensityCorrection = True
        self.trackingPeriodTime = 10000000 # [nsec]
        self.refSignal = 0.0
        self.TrackIsRunning = True
        self.tTrackingSignaIntegrationTime = 50 #[msec]
        self.tGetTrackingSignalEveryTime = float(3) #[sec]
        self.TrackingThreshold = 0.95  # track signal threshold
        self.N_tracking_search = 5 # max number of point to scan on each axis

        # HW
        self.HW = hw_devices.HW_devices(simulation)
        self.mwModule = self.HW.microwave
        self.positioner = self.HW.positioner
        self.pico = self.HW.picomotor

        # Qua config object
        self.quaCFG =  configs.QuaConfigSelector.get_qua_config(self.HW.config.system_type)
        self.u = unit()

        #common parameters
        self.exp = Experimet.COUNTER

        self.mw_Pwr = -20.0  # [dBm]
        self.mw_freq = 2.177  # [GHz], base frequency. Both start freq for scan and base frequency
        self.mw_freq_scan_range = 10.0  # [MHz]
        self.mw_df = float(0.1)  # [MHz]
        self.mw_freq_resonance = 2.18018  # [GHz]
        self.mw_2ndfreq_resonance = 2.18318 # [GHz]

        self.n_avg = int(1000000)  # number of averages
        self.n_nuc_pump = 4  # number of times to try nuclear pumping
        self.n_CPMG = 1  # CPMG repeatetions

        self.scan_t_start = 20  # [nsec], must above 16ns (4 cycle)
        self.scan_t_end = 2000  # [nsec]
        self.scan_t_dt = 40  # [nsec], must above 4ns (1 cycle)

        self.MeasProcessTime = 300  # [nsec], time required for measure element to finish process
        self.Tpump = 500 # [nsec]
        self.Tcounter = 10000  # [nsec], for scan it is the single integration time
        self.TcounterPulsed = 500 # [nsec]
        self.total_integration_time = 5  # [msec]
        self.Tsettle = 2000 # [nsec]
        self.t_mw = 1100  # [nsec] # from rabi experiment

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


        #Graph parameters
        self.NumOfPoints = 800  # to include in counter Graph
        self.X_vec = []
        self.Y_vec = []
        self.X_vec_ref = []
        self.Y_vec_ref = []

        self.Xv=[]
        self.Yv=[]
        self.Zv=[]

        self.StopFetch = True

        self.expNotes = "_"

        # load class parameters from XML
        self.update_from_xml()
        self.bScanChkbox = False
        # self.bEnableSignalIntensityCorrection = False # tdo: remove after fixing intensity method

        # self.ZCalibrationData = np.array([[1274289050, 1099174441, -5215799855],[1274289385, -1900825080, -5239700330],[-1852010640, -1900825498, -5277599782]])

        if not simulation:
            try:
                # self.qmm = QuantumMachinesManager(self.HW.config.opx_ip, self.HW.config.opx_port)
                self.qmm = QuantumMachinesManager(host = self.HW.config.opx_ip,
                                                  cluster_name = self.HW.config.opx_cluster,
                                                  timeout = 60) # in seconds
                # self.qmm.close_all_quantum_machines() # close all open Quantum machines
            except Exception as e:
                print(f"Could not connect to OPX. Error: {e}.")

    def Calc_estimatedScanTime(self):
        N = np.ones(len(self.L_scan))
        for i in range(len(self.L_scan)):
            if self.b_Scan[i] == True:
                if self.dL_scan[i] > 0:
                    N[i] = self.L_scan[i] / self.dL_scan[i]
        self.estimatedScanTime = round(np.prod(N) * (self.singleStepTime_scan + self.total_integration_time/1e3) / 60, 1)

    # Callbacks
    def time_in_multiples_cycle_time(self, val, cycleTime: int = 4, min:int = 16, max:int = 50000000 ):
        val = (val//cycleTime)*cycleTime
        if val < min:
            val  = min
        if val > max:
            val  = max
        return int(val)

    def UpdateCounterIntegrationTime(sender, app_data, user_data):
        sender.total_integration_time = int(user_data)
        time.sleep(0.001)
        dpg.set_value(item="inInt_total_integration_time", value=sender.total_integration_time)
        print("Set total_integration_time to: " + str(sender.total_integration_time) + "usec")

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
        sender.rf_df = sender.rf_df_gui / 1e3 # to [MHz]
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
        pos = [int(self.viewport_width * 0.0), int(self.viewport_height * 0.25)]
        win_size = [int(self.viewport_width * 0.6), int(self.viewport_height * 0.425)]

        dpg.add_window(label="OPX Window", tag="OPX Window", no_title_bar=True, height=-1, width=-1,
                       pos=[int(pos[0]), int(pos[1])])
        dpg.add_group(tag="Graph_group", parent="OPX Window", horizontal=True)
        dpg.add_plot(label="Graph", width=int(win_size[0]), height=int(win_size[1]), crosshairs=True, tag="graphXY",
                     parent="Graph_group")  #height=-1, width=-1,no_menus = False )
        dpg.add_plot_legend(parent="graphXY")  # optionally create legend
        dpg.add_plot_axis(dpg.mvXAxis, label="time", tag="x_axis", parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_plot_axis(dpg.mvYAxis, label="I [counts/sec]", tag="y_axis", invert=False,
                          parent="graphXY")  # REQUIRED: create x and y axes
        dpg.add_line_series(self.X_vec, self.Y_vec, label="counts", parent="y_axis",
                            tag="series_counts")  # series belong to a y axis
        dpg.add_line_series(self.X_vec_ref, self.Y_vec_ref, label="counts_ref", parent="y_axis",
                            tag="series_counts_ref")  # series belong to a y axis

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")

        dpg.add_group(tag="Params_Controls", before="Graph_group", parent="OPX Window", horizontal=False)
        self.GUI_ParametersControl(True)
    def GUI_ParametersControl(self, isStart):
        child_width = int(2900 * self.window_scale_factor)
        child_height = int(80 * self.window_scale_factor)
        item_width = int(270 * self.window_scale_factor)
        dpg.delete_item("Params_Controls")
        dpg.delete_item("Buttons_Controls")

        if isStart:
            dpg.add_group(tag="Params_Controls", before="Graph_group", parent="OPX Window", horizontal=False)

            dpg.add_child_window(label="", tag="child_Integration_Controls", parent="Params_Controls",
                          horizontal_scrollbar=True, width=child_width, height=child_height)
            dpg.add_group(tag="Integration_Controls", parent="child_Integration_Controls", horizontal=True)
            dpg.add_text(default_value="Tcounter [nsec]", parent="Integration_Controls",
                         tag="text_integration_time", indent=-1)
            dpg.add_input_int(label="", tag="inInt_Tcounter", indent=-1, parent="Integration_Controls",
                              width=item_width, callback=self.UpdateTcounter,
                              default_value=self.Tcounter,
                              min_value=1, max_value=60000000, step=100)
            dpg.add_text(default_value="Tpump [nsec]", parent="Integration_Controls",
                         tag="text_Tpump", indent=-1)
            dpg.add_input_int(label="", tag="inInt_Tpump", indent=-1, parent="Integration_Controls",
                              width=item_width, callback=self.UpdateTpump,
                              default_value=self.Tpump,
                              min_value=1, max_value=60000000, step=100)
            dpg.add_text(default_value="TcounterPulsed [nsec]", parent="Integration_Controls",
                         tag="text_TcounterPulsed", indent=-1)
            dpg.add_input_int(label="", tag="inInt_TcounterPulsed", indent=-1, parent="Integration_Controls",
                              width=item_width, callback=self.UpdateTcounterPulsed,
                              default_value=self.TcounterPulsed,
                              min_value=1, max_value=60000000, step=100)
            dpg.add_text(default_value="Tsettle [nsec]", parent="Integration_Controls", tag="text_measure_time",
                         indent=-1)
            dpg.add_input_int(label="", tag="inInt_Tsettle", indent=-1, parent="Integration_Controls",
                              width=item_width, callback=self.UpdateTsettle,
                              default_value=self.Tsettle,
                              min_value=1, max_value=60000000, step=1)
            dpg.add_text(default_value="total integration time [msec]", parent="Integration_Controls",
                         tag="text_total_integration_time", indent=-1)
            dpg.add_input_int(label="", tag="inInt_total_integration_time", indent=-1, parent="Integration_Controls",
                              width=item_width, callback=self.UpdateCounterIntegrationTime,
                              default_value=self.total_integration_time,
                              min_value=1, max_value=1000, step=1)

            dpg.add_child_window(label="", tag="child_Freq_Controls", parent="Params_Controls", horizontal_scrollbar=True,
                          width=child_width, height=child_height)
            dpg.add_group(tag="Freq_Controls", parent="child_Freq_Controls", horizontal=True)  #, before="Graph_group")

            dpg.add_text(default_value="MW res [GHz]", parent="Freq_Controls", tag="text_mwResonanceFreq",
                         indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mwResonanceFreq", indent=-1, parent="Freq_Controls",
                                 format="%.9f",
                                 width=item_width, callback=self.Update_mwResonanceFreq,
                                 default_value=self.mw_freq_resonance,
                                 min_value=0.001, max_value=6, step=0.001)
            dpg.add_text(default_value="MW 2nd_res [GHz]", parent="Freq_Controls", tag="text_mw2ndResonanceFreq",
                         indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mw_2ndfreq_resonance", indent=-1, parent="Freq_Controls",
                                 format="%.9f",
                                 width=item_width, callback=self.Update_mw_2ndfreq_resonance,
                                 default_value=self.mw_2ndfreq_resonance,
                                 min_value=0.001, max_value=6, step=0.001)
            dpg.add_text(default_value="MW freq [GHz] (base)", parent="Freq_Controls", tag="text_mwFreq", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mwFreq", indent=-1, parent="Freq_Controls", format="%.9f",
                                 width=item_width, callback=self.Update_mwFreq,
                                 default_value=self.mw_freq,
                                 min_value=0.001, max_value=6, step=0.001)
            dpg.add_text(default_value="range [MHz]", parent="Freq_Controls", tag="text_mwScanRange", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mwScanRange", indent=-1, parent="Freq_Controls",
                                 width=item_width, callback=self.UpdateScanRange,
                                 default_value=self.mw_freq_scan_range,
                                 min_value=1, max_value=400, step=1)
            dpg.add_text(default_value="df [MHz]", parent="Freq_Controls", tag="text_mw_df", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mw_df", indent=-1, parent="Freq_Controls", format="%.5f",
                                 width=item_width, callback=self.Update_df,
                                 default_value=self.mw_df,
                                 min_value=0.000001, max_value=500, step=0.1)
            dpg.add_text(default_value="Power [dBm]", parent="Freq_Controls", tag="text_mw_pwr", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_mw_pwr", indent=-1, parent="Freq_Controls",
                                 width=item_width, callback=self.UpdateMWpwr,
                                 default_value=self.mw_Pwr,
                                 min_value=0.01, max_value=500, step=0.1)

            dpg.add_child_window(label="", tag="child_rf_Controls", parent="Params_Controls", horizontal_scrollbar=True,
                          width=child_width, height=child_height)
            dpg.add_group(tag="rf_Controls", parent="child_rf_Controls", horizontal=True)  #, before="Graph_group")

            dpg.add_text(default_value="RF resonance freq [MHz]", parent="rf_Controls", tag="text_rf_resonance_Freq",
                         indent=-1)
            dpg.add_input_double(label="", tag="inDbl_rf_resonance_freq", indent=-1, parent="rf_Controls",
                                 format="%.9f",
                                 width=item_width, callback=self.Update_rf_resonance_Freq,
                                 default_value=self.rf_resonance_freq,
                                 min_value=0.001, max_value=6, step=0.001)

            dpg.add_text(default_value="RF freq [MHz]", parent="rf_Controls", tag="text_rf_Freq", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_rf_freq", indent=-1, parent="rf_Controls", format="%.9f",
                                 width=item_width, callback=self.Update_rf_Freq,
                                 default_value=self.rf_freq,
                                 min_value=0.001, max_value=6, step=0.001)
            dpg.add_text(default_value="range [kHz]", parent="rf_Controls", tag="text_rfScanRange", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_rf_ScanRange", indent=-1, parent="rf_Controls",
                                 width=item_width, callback=self.Update_rf_ScanRange,
                                 default_value=self.rf_freq_scan_range_gui,
                                 min_value=1, max_value=400, step=1)
            dpg.add_text(default_value="df [kHz]", parent="rf_Controls", tag="text_rf_df", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_rf_df", indent=-1, parent="rf_Controls", format="%.5f",
                                 width=item_width, callback=self.Update_rf_df,
                                 default_value=self.rf_df_gui,
                                 min_value=0.00001, max_value=500, step=0.1)
            dpg.add_text(default_value="Power [V]", parent="rf_Controls", tag="text_rf_pwr", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_rf_pwr", indent=-1, parent="rf_Controls",
                                 width=item_width, callback=self.Update_rf_pwr,
                                 default_value=self.rf_Pwr,
                                 min_value=0.01, max_value=500, step=0.1)

            dpg.add_child_window(label="", tag="child_Time_Scan_Controls", parent="Params_Controls", horizontal_scrollbar=True,
                          width=child_width, height=child_height)
            dpg.add_group(tag="Time_Scan_Controls", parent="child_Time_Scan_Controls",
                          horizontal=True)  #, before="Graph_group")
            dpg.add_text(default_value="scan t start [ns]", parent="Time_Scan_Controls", tag="text_scan_time_start",
                         indent=-1)
            dpg.add_input_int(label="", tag="inInt_scan_t_start", indent=-1, parent="Time_Scan_Controls",
                              width=item_width, callback=self.UpdateScanTstart,
                              default_value=self.scan_t_start,
                              min_value=0, max_value=50000, step=1)
            dpg.add_text(default_value="dt [ns]", parent="Time_Scan_Controls", tag="text_scan_time_dt", indent=-1)
            dpg.add_input_int(label="", tag="inInt_scan_t_dt", indent=-1, parent="Time_Scan_Controls",
                              width=item_width, callback=self.UpdateScanT_dt,
                              default_value=self.scan_t_dt,
                              min_value=0, max_value=50000, step=1)
            dpg.add_text(default_value="t end [ns]", parent="Time_Scan_Controls", tag="text_scan_time_end", indent=-1)
            dpg.add_input_int(label="", tag="inInt_scan_t_end", indent=-1, parent="Time_Scan_Controls",
                              width=item_width, callback=self.UpdateScanTend,
                              default_value=self.scan_t_end,
                              min_value=0, max_value=50000, step=1)

            dpg.add_child_window(label="", tag="child_Time_delay_Controls", parent="Params_Controls",
                          horizontal_scrollbar=True, width=child_width, height=child_height)
            dpg.add_group(tag="Time_delay_Controls", parent="child_Time_delay_Controls",
                          horizontal=True)  #, before="Graph_group")

            dpg.add_text(default_value="t_mw [ns]", parent="Time_delay_Controls", tag="text_t_mw", indent=-1)
            dpg.add_input_int(label="", tag="inInt_t_mw", indent=-1, parent="Time_delay_Controls",
                              width=item_width, callback=self.UpdateT_mw,
                              default_value=self.t_mw,
                              min_value=0, max_value=50000, step=1)
            dpg.add_text(default_value="rf_pulse_time [ns]", parent="Time_delay_Controls", tag="text_rf_pulse_time",
                         indent=-1)
            dpg.add_input_int(label="", tag="inInt_rf_pulse_time", indent=-1, parent="Time_delay_Controls",
                              width=item_width, callback=self.UpdateT_rf_pulse_time,
                              default_value=self.rf_pulse_time,
                              min_value=0, max_value=500000, step=1)
            dpg.add_text(default_value="tGetTrackingSignalEveryTime [sec]", parent="Time_delay_Controls", tag="text_tGetTrackingSignalEveryTime", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_tGetTrackingSignalEveryTime", indent=-1, parent="Time_delay_Controls", format="%.3f",
                                 width=item_width, callback=self.Update_tGetTrackingSignalEveryTime,
                                 default_value=self.tGetTrackingSignalEveryTime,
                                 min_value=0.001, max_value=10, step=0.1)
            
            dpg.add_text(default_value="tTrackingSignaIntegrationTime [msec]", parent="Time_delay_Controls", tag="text_tTrackingSignaIntegrationTime", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_tTrackingSignaIntegrationTime", indent=-1, parent="Time_delay_Controls", format="%.0f",
                                 width=item_width, callback=self.Update_tTrackingSignaIntegrationTime,
                                 default_value=self.tTrackingSignaIntegrationTime,
                                 min_value=1, max_value=500000, step=10.0)
            

            dpg.add_child_window(label="", tag="child_Repetitions_Controls", parent="Params_Controls",
                          horizontal_scrollbar=True, width=child_width, height=child_height)
            dpg.add_group(tag="Repetitions_Controls", parent="child_Repetitions_Controls",
                          horizontal=True)  #, before="Graph_group")

            dpg.add_text(default_value="N nuc pump", parent="Repetitions_Controls", tag="text_N_nuc_pump", indent=-1)
            dpg.add_input_int(label="", tag="inInt_N_nuc_pump", indent=-1, parent="Repetitions_Controls",
                              width=item_width, callback=self.UpdateN_nuc_pump,
                              default_value=self.n_nuc_pump,
                              min_value=0, max_value=50000, step=1)

            dpg.add_text(default_value="N CPMG", parent="Repetitions_Controls", tag="text_N_CPMG", indent=-1)
            dpg.add_input_int(label="", tag="inInt_N_CPMG", indent=-1, parent="Repetitions_Controls",
                              width=item_width, callback=self.UpdateN_CPMG,
                              default_value=self.n_CPMG,
                              min_value=0, max_value=50000, step=1)

            dpg.add_text(default_value="N avg", parent="Repetitions_Controls", tag="text_n_avg", indent=-1)
            dpg.add_input_int(label="", tag="inInt_n_avg", indent=-1, parent="Repetitions_Controls",
                              width=item_width, callback=self.UpdateNavg,
                              default_value=self.n_avg,
                              min_value=0, max_value=50000, step=1)
            dpg.add_text(default_value="TrackingThreshold", parent="Repetitions_Controls", tag="text_TrackingThreshold", indent=-1)
            dpg.add_input_double(label="", tag="inDbl_TrackingThreshold", indent=-1, parent="Repetitions_Controls", format="%.2f",
                                 width=item_width, callback=self.Update_TrackingThreshold,
                                 default_value=self.TrackingThreshold,
                                 min_value=0, max_value=1, step=0.01)
            dpg.add_text(default_value="N search (Itracking)", parent="Repetitions_Controls", tag="text_N_tracking_search", indent=-1)
            dpg.add_input_int(label="", tag="inInt_N_tracking_search", indent=-1, parent="Repetitions_Controls",
                              width=item_width, callback=self.UpdateN_tracking_search,
                              default_value=self.N_tracking_search,
                              min_value=0, max_value=50000, step=1)

            dpg.add_group(tag="chkbox_group", parent="Params_Controls", horizontal=True)
            dpg.add_checkbox(label="Intensity Correction", tag="chkbox_intensity_correction", parent="chkbox_group",
                             callback=self.Update_Intensity_Tracking_state, indent=-1,
                             default_value=self.bEnableSignalIntensityCorrection)
            dpg.add_checkbox(label="QUA shuffle", tag="chkbox_QUA_shuffle", parent="chkbox_group",
                             callback=self.Update_QUA_Shuffle_state, indent=-1,
                             default_value=self.bEnableShuffle)
            dpg.add_checkbox(label="QUA simulate", tag="chkbox_QUA_simulate", parent="chkbox_group",
                             callback=self.Update_QUA_Simulate_state, indent=-1,
                             default_value=self.bEnableSimulate)
            dpg.add_checkbox(label="Scan XYZ", tag="chkbox_scan", parent="chkbox_group", indent=-1,
                             callback=self.Update_scan, default_value=self.bScanChkbox)
            dpg.add_checkbox(label="Scan XYZ Fast", tag="chkbox_scan_fast", parent="chkbox_group", indent=-1,
                             callback=self.Update_scan_fast, default_value=self.fast_scan_enabled)

            dpg.add_group(tag="Buttons_Controls", parent="Graph_group",
                          horizontal=False)  # parent="Params_Controls",horizontal=False)
            _width = 300 # was 220
            dpg.add_button(label="Counter", parent="Buttons_Controls", tag="btnOPX_StartCounter",
                           callback=self.btnStartCounterLive, indent=-1, width=_width)
            dpg.add_button(label="ODMR_CW", parent="Buttons_Controls", tag="btnOPX_StartODMR",
                           callback=self.btnStartODMR_CW, indent=-1, width=_width)
            dpg.add_button(label="Start Pulsed ODMR", parent="Buttons_Controls", tag="btnOPX_StartPulsedODMR",
                           callback=self.btnStartPulsedODMR, indent=-1, width=_width)
            dpg.add_button(label="RABI", parent="Buttons_Controls", tag="btnOPX_StartRABI", callback=self.btnStartRABI,
                           indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear RABI", parent="Buttons_Controls", tag="btnOPX_StartNuclearRABI",
                           callback=self.btnStartNuclearRABI, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear MR", parent="Buttons_Controls", tag="btnOPX_StartNuclearMR",
                           callback=self.btnStartNuclearMR, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear PolESR", parent="Buttons_Controls", tag="btnOPX_StartNuclearPolESR",
                           callback=self.btnStartNuclearPolESR, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear lifetime S0", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS0",
                           callback=self.btnStartNuclearSpinLifetimeS0, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear lifetime S1", parent="Buttons_Controls", tag="btnOPX_StartNuclearLifetimeS1",
                           callback=self.btnStartNuclearSpinLifetimeS1, indent=-1, width=_width)
            dpg.add_button(label="Start Nuclear Ramsay", parent="Buttons_Controls", tag="btnOPX_StartNuclearRamsay",
                           callback=self.btnStartNuclearRamsay, indent=-1, width=_width)
            dpg.add_button(label="Start Hahn", parent="Buttons_Controls", tag="btnOPX_StartHahn",
                           callback=self.btnStartHahn, indent=-1, width=_width)
            dpg.add_button(label="Start Electron Lifetime", parent="Buttons_Controls", tag="btnOPX_StartElectronLifetime",
                           callback=self.btnStartElectronLifetime, indent=-1, width=_width)
            dpg.add_button(label="Start Electron Coherence", parent="Buttons_Controls", tag="btnOPX_StartElectronCoherence",
                           callback=self.btnStartElectron_Coherence, indent=-1, width=_width)
            
            # save exp data
            dpg.add_group(tag="Save_Controls", parent="Params_Controls", horizontal=True)
            dpg.add_input_text(label="", parent="Save_Controls", tag="inTxtOPX_expText", indent=-1,
                               callback=self.saveExperimentsNotes)
            dpg.add_button(label="Save", parent="Save_Controls", tag="btnOPX_save", callback=self.btnSave, indent=-1) # remove save btn, it should save automatically

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
            dpg.add_group(tag="Params_Controls", before="Graph_group", parent="OPX Window", horizontal=True)
            dpg.add_button(label="Stop", parent="Params_Controls", tag="btnOPX_Stop", callback=self.btnStop, indent=-1)
            dpg.bind_item_theme(item="btnOPX_Stop", theme="btnRedTheme")
    def GUI_ScanControls(self):
        self.Calc_estimatedScanTime()
        self.maintain_aspect_ratio = True

        win_size = [int(self.viewport_width*0.6), int(self.viewport_height*0.3)]
        win_pos = [int(self.viewport_width*0.05)*0, int(self.viewport_height*0.02)]
        scan_time_in_seconds = self.estimatedScanTime * 60

        item_width = int(200* self.window_scale_factor)
        if self.bScanChkbox:

            # Check if the handler_registry already exists
            if not dpg.does_item_exist("handler_registry"):
                with dpg.handler_registry(tag="handler_registry"):
                    dpg.add_mouse_click_handler(callback=self.map_click_callback)

            with dpg.window(label="Scan Window", tag="Scan_Window", no_title_bar=True, height=-1, width=win_size[0]/2,
                            pos=win_pos):
                with dpg.group(horizontal=True):
                    # Left side: Scan settings and controls
                    with dpg.group(tag="Scan_Range", horizontal=False):
                        with dpg.group(tag="Scan_Parameters", horizontal=False):
                            with dpg.group(tag="X_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bX_Scan", indent=-1,
                                                 callback=self.Update_bX_Scan, default_value=self.b_Scan[0])
                                dpg.add_text(default_value="dx [nm]", tag="text_dx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dx_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dX_Scan, default_value=self.dL_scan[0],
                                                  min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lx [nm]", tag="text_Lx_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lx_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lx_Scan, default_value=self.L_scan[0],
                                                  min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Y_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bY_Scan", indent=-1,
                                                 callback=self.Update_bY_Scan, default_value=self.b_Scan[1])
                                dpg.add_text(default_value="dy [nm]", tag="text_dy_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dy_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dY_Scan, default_value=self.dL_scan[1],
                                                  min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Ly [nm]", tag="text_Ly_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Ly_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Ly_Scan, default_value=self.L_scan[1],
                                                  min_value=0, max_value=500000, step=1)

                            with dpg.group(tag="Z_Scan_Range", horizontal=True):
                                dpg.add_checkbox(label="", tag="chkbox_bZ_Scan", indent=-1,
                                                 callback=self.Update_bZ_Scan, default_value=self.b_Scan[2])
                                dpg.add_text(default_value="dz [nm]", tag="text_dz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_dz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_dZ_Scan, default_value=self.dL_scan[2],
                                                  min_value=0, max_value=500000, step=1)
                                dpg.add_text(default_value="Lz [nm]", tag="text_Lz_scan", indent=-1)
                                dpg.add_input_int(label="", tag="inInt_Lz_scan", indent=-1, width=item_width,
                                                  callback=self.Update_Lz_Scan, default_value=self.L_scan[2],
                                                  min_value=0, max_value=500000, step=1)

                            with dpg.group(horizontal=True):
                                dpg.add_input_text(label="", tag="inTxtScan_expText", indent=-1, width=200,
                                                   callback=self.saveExperimentsNotes)

                                dpg.add_text(default_value=f"~scan time: {self.format_time(scan_time_in_seconds)}",
                                             tag="text_expectedScanTime", indent=-1)

                            with dpg.group(horizontal=True):
                                dpg.add_text(label="Message: ", tag="Scan_Message")
                                dpg.add_checkbox(label="", tag="chkbox_Zcorrection", indent=-1,
                                                 callback=self.Update_bZcorrection, default_value=self.b_Zcorrection)
                                dpg.add_text(default_value="Use Z Correction", tag="text_Zcorrection", indent=-1)

                    with dpg.group(tag="start_Scan_btngroup", horizontal=False):
                            dpg.add_button(label="Start Scan", tag="btnOPX_StartScan", callback=self.btnStartScan,
                                           indent=-1, width=130)
                            dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")
                            dpg.add_button(label="Load Scan", tag="btnOPX_LoadScan", callback=self.btnLoadScan,
                                           indent=-1, width=130)
                            dpg.bind_item_theme(item="btnOPX_LoadScan", theme="btnGreenTheme")
                            dpg.add_button(label="Update images", tag="btnOPX_UpdateImages",
                                           callback=self.btnUpdateImages, indent=1, width=130)
                            dpg.bind_item_theme(item="btnOPX_UpdateImages", theme="btnGreenTheme")
                            dpg.add_button(label="Find Peak", tag="btnOPX_FindPeak", callback=self.btnFindPeak,
                                           indent=-1, width=130)
                            dpg.bind_item_theme(item="btnOPX_FindPeak", theme="btnYellowTheme")
                            dpg.add_button(label="Get Log", tag="btnOPX_GetLoggedPoint",
                                           callback=self.btnGetLoggedPoints, indent=-1, width=130)

                    # Right side: Map display
                    image_path = "Sample_map.png"
                    # Check if the file exists before loading the image
                    if os.path.exists(image_path):
                        with dpg.group(horizontal=False):
                            with dpg.texture_registry(tag="Sample_map_registry"):
                                width, height, channels, data = dpg.load_image("Sample_map.png")
                                dpg.add_static_texture(width, height, data, tag="map_texture")
                                self.Map_aspect_ratio = width / height

                            with dpg.window(label="Map Resizer", width=win_size[0], height=win_size[1]*3, tag="Map_window",
                                            pos=[700, 5], horizontal_scrollbar=True):
                                child_width=win_size[0]*0.45
                                child_height=win_size[1]*0.5
                                # Main horizontal group to separate controls and map
                                with dpg.group(horizontal=True):
                                    # Left-hand side: Control panels
                                    with dpg.group(horizontal=False):
                                        # Group for map controls: Width, Height, and Aspect Ratio
                                        with dpg.child_window(width=child_width, height=child_height):
                                            dpg.add_text("Map Size & Aspect Ratio Controls", bullet=True)
                                            dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                                            with dpg.group(horizontal=True):
                                                dpg.add_slider_int(label="Width", min_value=100, max_value=width * 3,
                                                                   default_value=width, id="width_slider",
                                                                   callback=self.resize_image, width=200)
                                                dpg.add_input_int(label="", default_value=width, id="width_input",
                                                                  callback=self.resize_from_input, width=100)
                                                dpg.add_text("A.ratio")

                                            with dpg.group(horizontal=True):
                                                dpg.add_slider_int(label="Height", min_value=100, max_value=height * 3,
                                                                   default_value=height, id="height_slider",
                                                                   callback=self.resize_image, width=200)
                                                dpg.add_input_int(label="", default_value=height, id="height_input",
                                                                  callback=self.resize_from_input, width=100)
                                                dpg.add_button(label="ON", callback=self.toggle_aspect_ratio)

                                        # Group for Offset Controls
                                        with dpg.child_window(width=child_width, height=child_height*1.2):
                                            dpg.add_text("Offset Controls", bullet=True)
                                            dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                            with dpg.group(horizontal=True):
                                                dpg.add_input_float(label="OffsetX", tag="MapOffsetX", indent=-1,
                                                                    width=150, default_value=0, step=0.01, step_fast=1)
                                                dpg.add_input_float(label="OffsetY", tag="MapOffsetY", indent=-1,
                                                                    width=150, default_value=0, step=0.01, step_fast=1)
                                                dpg.add_button(label="Set 0", callback=self.set_marker_coord_to_zero)

                                            with dpg.group(horizontal=True):
                                                dpg.add_input_float(label="FactorX", tag="MapFactorX", indent=-1,
                                                                    width=150, default_value=1, step=0.01, step_fast=1)
                                                dpg.add_input_float(label="FactorY", tag="MapFactorY", indent=-1,
                                                                    width=150, default_value=1, step=0.01, step_fast=1)

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="Set Gap", callback=self.map_set_gap)
                                                dpg.add_input_int(label="", tag="MapSetGap", indent=-1, width=130,
                                                                  min_value=1, default_value=10, step=10, step_fast=100)
                                                dpg.add_button(label="x", callback=self.toggle_set_x_or_y,
                                                               tag="toggle_set_x_or_y")
                                                dpg.add_input_float(label="Move Step", tag="MapMoveStep", indent=-1,
                                                                    width=150, default_value=1, step=1, step_fast=100)
                                            dpg.add_text("Click map for coordinates", tag="coordinates_text")
                                            dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                                        # Group for marking points, areas, and update scan
                                        with dpg.child_window(width=child_width, height=child_height):
                                            dpg.add_text("Marker & Scan Controls", bullet=True)
                                            dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="Mark Point", callback=self.mark_point_on_map)
                                                dpg.add_button(label="Mark Area", callback=partial(self.start_rectangle_query, False))
                                                dpg.add_button(label="Area + Center", callback=partial(self.start_rectangle_query, True))
                                                dpg.add_button(label="Find Middle", callback=self.find_middle)                                                
                                                dpg.add_button(label="Black", tag="toggle_text_color",callback=self.toggle_text_color)

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="Delete Last Mark", callback=self.delete_last_mark)
                                                dpg.add_button(label="Delete All Markers",
                                                               callback=self.delete_all_markers)
                                                dpg.add_button(label="Delete All Except Active",
                                                               callback=self.delete_all_except_active)

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="Break area to ",
                                                               callback=self.break_area)
                                                dpg.add_input_int(label="", tag="BreakAreaSize", indent=-1,
                                                                  width=150, min_value=50, default_value=60, step=1, step_fast=10)
                                                dpg.add_button(label="Scan All Area Markers", callback=self.scan_all_area_markers)
                                                dpg.bind_item_theme(dpg.last_item(), theme="btnYellowTheme")
                                                dpg.add_checkbox(label="Picomotor", tag="chkbox_use_picomotor", indent=-1,
                                                                 callback=self.toggle_use_picomotor, default_value=self.use_picomotor)

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="Save", callback=self.save_map_parameters)
                                                dpg.add_button(label="Load", callback=self.load_map_parameters)
                                                dpg.add_input_int(label="# digits", tag="MapNumOfDigits", indent=-1,
                                                                  width=150, min_value=0, default_value=1, step=1,
                                                                  step_fast=100, callback=self.btn_num_of_digits_change)
                                                dpg.add_button(label="Fix area", callback=self.fix_area)

                                        # Group for marker movement buttons
                                        with dpg.child_window(width=child_width, height=child_height):
                                            dpg.add_text("Marker Movement Controls", bullet=True)
                                            dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="move marker", callback=self.toggle_marker_area,tag="toggle_marker_area")
                                                dpg.add_button(label="Map Keys: Enabled", tag="toggle_map_keyboard",
                                                               callback=self.toggle_map_keyboard)

                                                with dpg.collapsing_header(label="Keyboard Shortcuts", default_open=False):
                                                    dpg.add_text(
                                                        "The following keys can be used to interact with markers and area markers:")
                                                    dpg.add_separator()
                                                    dpg.add_text("Ctrl + M : Enable/disable map keyboard shortcuts")
                                                    dpg.add_text(
                                                        "M(Coarse) / N(Fine) + arrow keys: Shift marker/area marker")
                                                    dpg.add_text(
                                                        "M/N + PageDown: Stretch vertically (Y-axis) - Coarse mode is supported")
                                                    dpg.add_text(
                                                        "M/N + PageUp: Squeeze vertically (Y-axis) - Coarse mode is supported")
                                                    dpg.add_text(
                                                        "M/N + Home: Squeeze horizontally (X-axis) - Coarse mode is supported")
                                                    dpg.add_text(
                                                        "M/N + End: Stretch horizontally (X-axis) - Coarse mode is supported")
                                                    dpg.add_text("Del: Delete active marker or area marker")
                                                    dpg.add_text(
                                                        "M + Insert: Insert a new marker or area marker near the active marker")
                                                    dpg.add_text("N + Insert: insert an area marker.")
                                                    dpg.add_text("M/N + Del : Delete active marker or area marker")
                                                    dpg.add_text("M + K : move marker")
                                                    dpg.add_text("M + A : move area")
                                                    dpg.add_text("M + + : Activate marker/area marker above current active")
                                                    dpg.add_text("M + - : Activate marker/area marker below6 current active")
                                                    dpg.add_text("M/N + U : Update scan area from active area")
                                                    dpg.add_text("M/N + P : Mark point on map")
                                                    dpg.add_text("M + G : Go")
                                                    dpg.add_text("N + G : Go & activate next")

                                            with dpg.group(horizontal=True):
                                                width = 50
                                                height = 60
                                                dpg.add_button(label="^", width=width, height=height,
                                                               callback=lambda: self.move_active_marker("up"))
                                                dpg.add_button(label="^^", width=width, height=height,
                                                               callback=lambda: self.move_active_marker("up up"))
                                                dpg.add_button(label="vv", width=width, height=height,
                                                               callback=lambda: self.move_active_marker("down down"))
                                                dpg.add_button(label="<<", width=width, height=height,
                                                               callback=lambda: self.move_active_marker("left left"))
                                                dpg.add_button(label="<---> X", width=120, height=height,
                                                               callback=lambda: self.stretch_squeeze_area_marker("stretch_x"))
                                                dpg.add_button(label="-> <- X", width=120, height=height,
                                                               callback=lambda: self.stretch_squeeze_area_marker("squeeze_x"))

                                            with dpg.group(horizontal=True):
                                                dpg.add_button(label="<", width=width, height=round(height),
                                                               callback=lambda: self.move_active_marker("left"))
                                                dpg.add_button(label="v", width=width, height=round(height),
                                                               callback=lambda: self.move_active_marker("down"))
                                                dpg.add_button(label=">", width=width, height=round(height),
                                                               callback=lambda: self.move_active_marker("right"))
                                                dpg.add_button(label=">>", width=width, height=round(height),
                                                               callback=lambda: self.move_active_marker("right right"))
                                                dpg.add_button(label=" ^  Y\n v ", width=120, height=round(height),
                                                               callback=lambda: self.stretch_squeeze_area_marker("stretch_y"))
                                                dpg.add_button(label=" v  Y\n ^", width=120, height=round(height),
                                                               callback=lambda: self.stretch_squeeze_area_marker("squeeze_y"))

                                    # Table for displaying markers
                                        with dpg.child_window(width=child_width, height=900):

                                            with dpg.group(horizontal=True):
                                                dpg.add_text("Markers Table   ", bullet=True)
                                                dpg.bind_item_theme(dpg.last_item(), "highlighted_header_theme")
                                                dpg.add_button(label="Marker Up", callback=self.shift_marker_up)
                                                dpg.add_button(label="Marker Down", callback=self.shift_marker_down)
                                                dpg.add_button(label="Area Up", callback=self.shift_area_marker_up)
                                                dpg.add_button(label="Area Down", callback=self.shift_area_marker_down)

                                            with dpg.table(header_row=True, tag="markers_table", width=child_width-20):
                                                dpg.add_table_column(label="ID")
                                                dpg.add_table_column(label="rel X")
                                                dpg.add_table_column(label="rel Y")
                                                dpg.add_table_column(label="rel Z")
                                                dpg.add_table_column(label="")
                                                dpg.add_table_column(label="")
                                                dpg.add_table_column(label="Action")
                                                dpg.add_table_column(label="")
                                                dpg.add_table_column(label="")

                                    # Right-hand side: Map display
                                    with dpg.group(horizontal=False):
                                        # Display the map image
                                        dpg.add_image("map_texture", width=width, height=height, tag="map_image")
                                        dpg.add_draw_layer(tag="map_draw_layer", parent="Map_window")

                    else:
                        print("Sample_map.png does not exist")
                    self.btnGetLoggedPoints()  # get logged points
                    self.load_map_parameters() # load map parameters
                    self.move_mode = "marker"
        else:
            self.delete_all_markers()
            dpg.delete_item("Scan_Window")
            dpg.delete_item("Sample_map_registry")
            dpg.delete_item("Map_window")

    def fix_area(self):
        try:

            # Get the break_size from the input field
            break_size = dpg.get_value("BreakAreaSize")

            if break_size <= 0:
                print("Invalid break area size.")
                return

            if self.active_area_marker_index is None or self.active_area_marker_index >= len(self.area_markers):
                print("No active area marker to fix.")
                return

            # Get the active rectangle (relative coordinates and Z scan info)
            active_rectangle = self.area_markers[self.active_area_marker_index]
            min_x, min_y, max_x, max_y, z_scan_info = active_rectangle[:5]

            # Calculate the current width and height
            width = max_x - min_x
            height = max_y - min_y

            # Calculate the number of full squares needed to cover the rectangle
            num_hor_squares = math.ceil(width / break_size)
            num_ver_squares = math.ceil(height / break_size)

            # Calculate the new width and height
            new_width = num_hor_squares * break_size
            new_height = num_ver_squares * break_size

            # Adjust max_x and max_y to get the new dimensions
            max_x = min_x + new_width
            max_y = min_y + new_height

            # Update the rectangle in area_markers
            self.area_markers[self.active_area_marker_index] = (min_x, min_y, max_x, max_y, z_scan_info)

            # Remove the existing rectangle from the map
            tag = f"query_rectangle_{self.active_area_marker_index}"
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)

            # Convert the relative coordinates to absolute for drawing on the map
            min_x_abs = min_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value("MapOffsetX")
            max_x_abs = max_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value("MapOffsetX")
            min_y_abs = min_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value("MapOffsetY")
            max_y_abs = max_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value("MapOffsetY")

            # Draw the new rectangle on the map
            dpg.draw_rectangle(pmin=(min_x_abs, min_y_abs), pmax=(max_x_abs, max_y_abs),
                               color=(0, 255, 0, 255),
                               thickness=2, parent="map_draw_layer", tag=tag)

            # Update markers table and highlight the active rectangle
            self.update_markers_table()
            self.highlight_active_rectangle()

            print(f"Active area marker adjusted to integer multiples of break size {break_size}.")

        except Exception as e:
            print(f"Error fixing area: {e}")

    def toggle_text_color(self, sender):
        """Toggle between cyan and black for marker text color."""
        current_label = dpg.get_item_label(sender)

        if current_label == "Cyan":
            dpg.configure_item(sender, label="Black")
            self.text_color = (0, 0, 0, 255)  # Set color to black
        else:
            dpg.configure_item(sender, label="Cyan")
            self.text_color = (0, 255, 255, 255)  # Set color to cyan

        self.update_marker_texts()

    def toggle_map_keyboard(self):
        """Toggle between enable and disable using tag instead of sender."""
        current_label = dpg.get_item_label("toggle_map_keyboard")

        if current_label == "Map Keys: Disabled":
            dpg.configure_item("toggle_map_keyboard", label="Map Keys: Enabled")
            self.map_keyboard_enable = True
        else:
            dpg.configure_item("toggle_map_keyboard", label="Map Keys: Disabled")
            self.map_keyboard_enable = False

    def start_rectangle_query(self,add_center_point_marker=False):
        if len(self.markers) < 2:
            print("Not enough markers to create a rectangle.")
            return

        # Determine which markers to use for the rectangle
        if self.active_marker_index is not None and 0 <= self.active_marker_index < len(self.markers):
            # Use the active marker and the one above it if it exists, otherwise the one below it
            active_marker_pos = self.markers[self.active_marker_index][3]  # Get clicked position of active marker
            if self.active_marker_index > 0:
                second_marker_pos = self.markers[self.active_marker_index - 1][3]  # Marker above the active one
            else:
                second_marker_pos = self.markers[self.active_marker_index + 1][3]  # Marker below the active one
        else:
            # No active marker, use the last two markers as before
            active_marker_pos = self.markers[-1][3]
            second_marker_pos = self.markers[-2][3]

        # Calculate the min and max positions for the rectangle
        min_x = min(active_marker_pos[0], second_marker_pos[0])
        min_y = min(active_marker_pos[1], second_marker_pos[1])
        max_x = max(active_marker_pos[0], second_marker_pos[0])
        max_y = max(active_marker_pos[1], second_marker_pos[1])

        # Use the relative coordinates directly from the markers
        relative_min_x = min(self.markers[self.active_marker_index][2][0], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][0])
        relative_min_y = min(self.markers[self.active_marker_index][2][1], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][1])
        relative_max_x = max(self.markers[self.active_marker_index][2][0], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][0])
        relative_max_y = max(self.markers[self.active_marker_index][2][1], self.markers[
            self.active_marker_index - 1 if self.active_marker_index > 0 else self.active_marker_index + 1][2][1])

        # Store the rectangle in self.area_markers with Z scan disabled by default
        rectangle = (relative_min_x, relative_min_y, relative_max_x, relative_max_y, "Z scan disabled")

        # Check if the rectangle already exists
        for existing_rectangle in self.area_markers:
            if all(abs(existing_rectangle[i] - rectangle[i]) < 1e-6 for i in range(4)):
                print("Rectangle already exists.")
                return 1  # Prevent adding a duplicate rectangle

        # If not, append the new rectangle
        self.area_markers.append(rectangle)

        # Get the index of the last rectangle added (zero-based indexing)
        rect_index = len(self.area_markers) - 1

        # Remove any existing rectangle with the same tag
        tag = f"query_rectangle_{rect_index}"

        # If the tag exists, delete the previous rectangle
        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)
            print(f"Existing rectangle with tag {tag} deleted.")

        # Set the newly created rectangle as the active one
        self.active_area_marker_index = rect_index

        # Draw a rectangle based on the two marker positions
        dpg.draw_rectangle(pmin=(min_x, min_y), pmax=(max_x, max_y), color=(0, 255, 0, 255), thickness=2,
                           parent="map_draw_layer", tag=tag)

        # Highlight the active rectangle (change color to magenta)
        self.highlight_active_rectangle()

        # Update the table to reflect the new rectangle
        self.update_markers_table()

        self.move_mode = "area_marker"
        # Update the button label to indicate the current state
        dpg.set_item_label("toggle_marker_area", "move area")

        print(f"Rectangle {rect_index} drawn and added to area_markers.")

        # --- ADDING CENTER POINT MARKER ---
        if add_center_point_marker:            
            # Calculate the center of the rectangle (absolute coordinates)
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
    
            # Convert the absolute coordinates to relative coordinates
            relative_center_x = (center_x - self.map_item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
            relative_center_y = (center_y - self.map_item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
    
            # Calculate Z value (if needed, otherwise set to 0)
            z_center = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_center_x * 1e6)),
                                                int(relative_center_y * 1e6))) / 1e6
    
            # Mark the center point on the map using absolute coordinates
            self.clicked_position = (center_x, center_y)  # Use absolute coordinates for clicked position
            self.click_coord = (relative_center_x, relative_center_y, z_center)  # Store relative coordinates
            self.mark_point_on_map()  # Call the existing function to mark the point

    def break_area(self):
        try:
            # Get the size of the smaller squares from the input field
            break_size = dpg.get_value("BreakAreaSize")

            if self.active_area_marker_index is None or self.active_area_marker_index >= len(self.area_markers):
                print("No active area marker to break.")
                return

            # Get the active rectangle (relative coordinates and Z scan info)
            active_rectangle = self.area_markers[self.active_area_marker_index]
            min_x, min_y, max_x, max_y, z_scan_info = active_rectangle[:5]

            # Calculate the width and height of the rectangle
            width = max_x - min_x
            height = max_y - min_y

            if break_size <= 0:
                print("Invalid break area size.")
                return

            # Calculate the number of full horizontal and vertical squares
            num_hor_squares = width // break_size
            num_ver_squares = height // break_size

            # Break the rectangle into smaller squares
            for i in range(int(num_hor_squares) + 1):  # +1 to handle edge cases
                for j in range(int(num_ver_squares) + 1):  # +1 to handle edge cases
                    # Calculate the small rectangle boundaries
                    small_min_x = min_x + i * break_size
                    small_max_x = min(small_min_x + break_size, max_x)  # Ensure it doesn't go past max_x
                    small_min_y = min_y + j * break_size
                    small_max_y = min(small_min_y + break_size, max_y)  # Ensure it doesn't go past max_y

                    # Create the smaller rectangle with the same Z scan value as the original area marker
                    small_rectangle = (small_min_x, small_min_y, small_max_x, small_max_y, z_scan_info)

                    # Check if the smaller rectangle already exists
                    if any(all(abs(existing_rectangle[k] - small_rectangle[k]) < 1e-6 for k in range(4)) for
                           existing_rectangle in self.area_markers):
                        print(f"Small rectangle ({i},{j}) already exists.")
                        continue

                    # Add the new smaller rectangle to area_markers
                    self.area_markers.append(small_rectangle)

                    # Convert the relative coordinates to absolute for drawing on the map
                    min_x_abs = small_min_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value(
                        "MapOffsetX")
                    max_x_abs = small_max_x / dpg.get_value("MapFactorX") + self.map_item_x + dpg.get_value(
                        "MapOffsetX")
                    min_y_abs = small_min_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value(
                        "MapOffsetY")
                    max_y_abs = small_max_y / dpg.get_value("MapFactorY") + self.map_item_y + dpg.get_value(
                        "MapOffsetY")

                    # Draw the smaller rectangle on the map
                    tag = f"query_rectangle_{len(self.area_markers) - 1}"
                    dpg.draw_rectangle(pmin=(min_x_abs, min_y_abs), pmax=(max_x_abs, max_y_abs),
                                       color=(0, 255, 0, 255),
                                       thickness=2, parent="map_draw_layer", tag=tag)

            # Update the markers table and active area marker state
            self.update_markers_table()
            print(
                f"Rectangle split into {int(num_hor_squares) + 1}x{int(num_ver_squares) + 1} smaller rectangles with Z scan: {z_scan_info}.")

        except Exception as e:
            print(f"Error breaking area: {e}")

    def update_scan_area_marker(self, index):
        """Update scan parameters based on the selected area marker."""
        if index < len(self.area_markers):
            # Get the selected rectangle from area_markers by index, including Z scan state
            selected_rectangle = self.area_markers[index]
            min_x, min_y, max_x, max_y, z_scan_state = selected_rectangle

            # Calculate the width and height of the rectangle
            Lx_scan = int(max_x - min_x) * 1e3  # Convert to micrometers
            Ly_scan = int(max_y - min_y) * 1e3  # Convert to micrometers
            X_pos = (max_x + min_x) / 2
            Y_pos = (max_y + min_y) / 2

            # Calculate the Z evaluation
            z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array([int(X_pos * 1e6)]),
                                                    int(Y_pos * 1e6))) / 1e6

            # Call Update_Lx_Scan and Update_Ly_Scan with the calculated values
            self.Update_Lx_Scan(app_data=None, user_data=Lx_scan)
            self.Update_Ly_Scan(app_data=None, user_data=Ly_scan)

            # Update MCS fields with the new absolute positions
            point = (X_pos * 1e6, Y_pos * 1e6, z_evaluation * 1e6)
            for ch, value in enumerate(point):
                dpg.set_value(f"mcs_ch{ch}_ABS", value / 1e6)

            # Toggle Z scan state based on z_scan_state
            self.Update_bZ_Scan(app_data=None, user_data=(z_scan_state == "Z scan enabled"))

            # Recalculate the estimated scan time based on the new scan parameters
            self.Calc_estimatedScanTime()

            # Update the GUI with the estimated scan time and relevant messages
            dpg.set_value(item="text_expectedScanTime",
                          value=f"~scan time: {self.format_time(self.estimatedScanTime * 60)}")
            dpg.set_value("Scan_Message", "Please press GO ABS in Smaract GUI")
        else:
            print("Invalid area marker index or no area markers available.")

    def toggle_aspect_ratio(self, sender, app_data, user_data):
        self.maintain_aspect_ratio = not self.maintain_aspect_ratio

        # Update the button label to indicate the current state
        if self.maintain_aspect_ratio:
            dpg.set_item_label(sender, "ON")
        else:
            dpg.set_item_label(sender, "OFF")

    def toggle_marker_area(self, sender):
        """Toggle between moving markers and area markers."""
        if not hasattr(self, 'move_mode'):
            self.move_mode = "marker"  # Initialize with marker mode
        self.move_mode = "area_marker" if self.move_mode == "marker" else "marker"
        print(f"Mode switched to {self.move_mode}")

        # Update the button label to indicate the current state
        if self.move_mode == "area_marker":
            dpg.set_item_label(sender, "move area")
        else:
            dpg.set_item_label(sender, "move marker")

    def move_active_marker(self, direction):
        """Move the active marker or area marker in a given direction."""
        try:
            move_step = dpg.get_value("MapMoveStep")  # Define the movement step size

            print(self.move_mode)

            # Check if there is a map image and get its position
            if dpg.does_item_exist("map_image"):
                item_x, item_y = dpg.get_item_pos("map_image")
            else:
                print("map_image does not exist")
                item_x = 0
                item_y = 0

            # Check which mode is active: marker or area_marker
            if self.move_mode == "marker":
                # Check if there is an active marker
                if not hasattr(self, 'active_marker_index') or self.active_marker_index < 0:
                    print("No active marker to move.")
                    return

                if len(self.markers) == 0:
                    print("No markers to move.")
                    return

                # Get the active marker and its associated text and coordinates
                marker_tag, text_tag, relative_coords, clicked_position = self.markers[self.active_marker_index]
                abs_x, abs_y = clicked_position

            elif self.move_mode == "area_marker":
                # Check if there is an active area marker
                if not hasattr(self, 'active_area_marker_index') or self.active_area_marker_index < 0:
                    print("No active area marker to move.")
                    return

                if len(self.area_markers) == 0:
                    print("No area markers to move.")
                    return

                # Get the active area marker's relative coordinates
                rel_min_x, rel_min_y, rel_max_x, rel_max_y, z_enable = self.area_markers[self.active_area_marker_index]

                # Calculate absolute coordinates based on relative coordinates, item position, and map factors
                abs_min_x = rel_min_x / dpg.get_value("MapFactorX") + dpg.get_value("MapOffsetX") + item_x
                abs_min_y = rel_min_y / dpg.get_value("MapFactorY") + dpg.get_value("MapOffsetY") + item_y
                abs_max_x = rel_max_x / dpg.get_value("MapFactorX") + dpg.get_value("MapOffsetX") + item_x
                abs_max_y = rel_max_y / dpg.get_value("MapFactorY") + dpg.get_value("MapOffsetY") + item_y

                abs_x, abs_y = abs_min_x, abs_min_y  # Use absolute coordinates for movement

            # Move the marker or area marker based on the direction
            if direction == "up":
                abs_y -= move_step
            elif direction == "up up":
                abs_y -= move_step * 10
            elif direction == "down":
                abs_y += move_step
            elif direction == "down down":
                abs_y += move_step * 10
            elif direction == "left":
                abs_x -= move_step
            elif direction == "left left":
                abs_x -= move_step * 10
            elif direction == "right":
                abs_x += move_step
            elif direction == "right right":
                abs_x += move_step * 10

            if self.move_mode == "marker":
                # Update the marker's position on the map
                dpg.configure_item(marker_tag, center=(abs_x, abs_y))

                if self.ZCalibrationData is None:
                    print("No Z calibration data.")
                    return 1

                # Calculate the relative position of the click on the map
                relative_x = (abs_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                relative_y = (abs_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
                z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x * 1e6)),
                                                        int(relative_y * 1e6))) / 1e6

                # Retrieve the number of digits from the input field
                num_of_digits = dpg.get_value("MapNumOfDigits")

                # Update the format string to use the retrieved number of digits
                coord_text = f"({relative_x:.{num_of_digits}f}, {relative_y:.{num_of_digits}f}, {z_evaluation:.{num_of_digits}f})"

                dpg.configure_item(text_tag, pos=(abs_x, abs_y), text=coord_text)

                # Update the stored relative coordinates for the marker
                self.markers[self.active_marker_index] = (
                    marker_tag, text_tag, (relative_x, relative_y, z_evaluation), (abs_x, abs_y))

            elif self.move_mode == "area_marker":
                # Update the area marker's absolute position
                new_abs_min_x = abs_x
                new_abs_min_y = abs_y
                new_abs_max_x = abs_max_x + (abs_x - abs_min_x)
                new_abs_max_y = abs_max_y + (abs_y - abs_min_y)

                # Recalculate relative coordinates for storage
                new_rel_min_x = (new_abs_min_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                new_rel_min_y = (new_abs_min_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")
                new_rel_max_x = (new_abs_max_x - item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                new_rel_max_y = (new_abs_max_y - item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

                # Update the area marker in the area_markers list with relative coordinates
                self.area_markers[self.active_area_marker_index] = (
                new_rel_min_x, new_rel_min_y, new_rel_max_x, new_rel_max_y,z_enable)

                # Update the drawn rectangle
                dpg.configure_item(f"query_rectangle_{self.active_area_marker_index}",
                                   pmin=(new_abs_min_x, new_abs_min_y), pmax=(new_abs_max_x, new_abs_max_y))

            # Update the table after moving
            self.update_markers_table()

        except Exception as ex:
            self.error = f"Unexpected error: {ex}, {type(ex)} in line: {sys.exc_info()[-1].tb_lineno}"
            print(self.error)

    def stretch_squeeze_area_marker(self, direction, is_coarse=False):
        """Stretch or squeeze the active area marker in X or Y direction, with coarse option."""
        # Automatically switch to area_marker mode
        self.move_mode = "area_marker"

        # Update the button label to indicate the current state
        if dpg.does_item_exist("toggle_marker_area"):
            dpg.set_item_label("toggle_marker_area", "move area")

        if not hasattr(self, 'active_area_marker_index') or self.active_area_marker_index < 0:
            print("No active area marker to stretch or squeeze.")
            return

        if len(self.area_markers) == 0:
            print("No area markers to modify.")
            return

        # Get the active area marker's relative coordinates
        rel_min_x, rel_min_y, rel_max_x, rel_max_y,z_enable = self.area_markers[self.active_area_marker_index]

        move_step = dpg.get_value("MapMoveStep")  # Define the movement step size for stretching/squeezing
        if is_coarse:
            move_step *= 10  # Coarse movement is 10 times bigger

        # Stretch or squeeze the area marker based on the direction
        if direction == "stretch_x":
            rel_max_x += move_step  # Stretch horizontally by increasing max_x
        elif direction == "squeeze_x":
            rel_max_x -= move_step  # Squeeze horizontally by decreasing max_x
        elif direction == "stretch_y":
            rel_max_y += move_step  # Stretch vertically by increasing max_y
        elif direction == "squeeze_y":
            rel_max_y -= move_step  # Squeeze vertically by decreasing max_y

        # Update the area marker's relative coordinates
        self.area_markers[self.active_area_marker_index] = (rel_min_x, rel_min_y, rel_max_x, rel_max_y, z_enable)

        # Recalculate absolute coordinates for rendering
        if dpg.does_item_exist("map_image"):
            item_x, item_y = dpg.get_item_pos("map_image")
        else:
            item_x, item_y = 0, 0

        abs_min_x = rel_min_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
        abs_min_y = rel_min_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")
        abs_max_x = rel_max_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
        abs_max_y = rel_max_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")

        # Update the drawn rectangle on the map
        dpg.configure_item(f"query_rectangle_{self.active_area_marker_index}",
                           pmin=(abs_min_x, abs_min_y), pmax=(abs_max_x, abs_max_y))

        # Update the table after modifying the area marker
        self.update_markers_table()

        print(f"Active area marker {direction} in {'coarse' if is_coarse else 'fine'} mode.")

    def save_map_parameters(self):
        try:
            # Try to read the existing file content, if it doesn't exist, create an empty list
            try:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
            except FileNotFoundError:
                lines = []

            # Create a list to store the new content
            new_content = []
            device_section = False  # Flag to track the device states section

            # Iterate through the existing lines and skip the map-related parameters
            for line in lines:
                if any(param in line for param in
                       ["OffsetX", "OffsetY", "FactorX", "FactorY", "MoveStep", "NumOfDigits", "ImageWidth",
                        "ImageHeight", "Exp_notes", "LoggedPoint", "Marker", "Rectangle"]):
                    # Skip lines that will be replaced by the new map parameters, points, and markers
                    continue
                new_content.append(line)

            # Add new map parameters, point markers, and rectangles
            new_content.append(f"OffsetX: {dpg.get_value('MapOffsetX')}\n")
            new_content.append(f"OffsetY: {dpg.get_value('MapOffsetY')}\n")
            new_content.append(f"FactorX: {dpg.get_value('MapFactorX')}\n")
            new_content.append(f"FactorY: {dpg.get_value('MapFactorY')}\n")
            new_content.append(f"MoveStep: {dpg.get_value('MapMoveStep')}\n")
            new_content.append(f"NumOfDigits: {dpg.get_value('MapNumOfDigits')}\n")
            new_content.append(f"ImageWidth: {dpg.get_value('width_slider')}\n")
            new_content.append(f"ImageHeight: {dpg.get_value('height_slider')}\n")

            # Save experimental notes
            new_content.append(f"Exp_notes: {self.expNotes}\n")

            # Save LoggedPoints from self.positioner
            for point in self.positioner.LoggedPoints:
                new_content.append(f"LoggedPoint: {point[0]}, {point[1]}, {point[2]}\n")

            # Save point markers data with both clicked position and relative coordinates
            for marker in self.markers:
                marker_tag, text_tag, relative_coords, clicked_position = marker
                new_content.append(
                    f"Marker: {relative_coords[0]}, {relative_coords[1]}, {relative_coords[2]}, {clicked_position[0]}, {clicked_position[1]}\n")

            # Save rectangles from self.area_markers
            for rect in self.area_markers:
                new_content.append(f"Rectangle: {rect[0]}, {rect[1]}, {rect[2]}, {rect[3]}, {rect[4]}\n")

            # Write back the updated content to the file
            with open("map_config.txt", "w") as file:
                file.writelines(new_content)

            print("Map parameters, point markers, and rectangles saved without touching device states.")

        except Exception as e:
            print(f"Error saving map parameters: {e}")

    def load_map_parameters(self):
        try:
            if not dpg.does_item_exist("map_image"):
                print("map image does not exist.")
            else:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
                    for line in lines:
                        # Split the line and check if it has the correct format
                        parts = line.split(": ")
                        if len(parts) < 2:
                            continue  # Skip lines that don't have the expected format

                        key = parts[0]
                        value = parts[1].strip()  # Remove any extra whitespace

                        if key == "OffsetX":
                            dpg.set_value("MapOffsetX", float(value))
                        elif key == "OffsetY":
                            dpg.set_value("MapOffsetY", float(value))
                        elif key == "FactorX":
                            dpg.set_value("MapFactorX", float(value))
                        elif key == "FactorY":
                            dpg.set_value("MapFactorY", float(value))
                        elif key == "MoveStep":
                            dpg.set_value("MapMoveStep", float(value))
                        elif key == "NumOfDigits":
                            dpg.set_value("MapNumOfDigits", int(value))
                        elif key == "ImageWidth":
                            dpg.set_value("width_slider", int(value))
                        elif key == "ImageHeight":
                            dpg.set_value("height_slider", int(value))
                            self.resize_image(sender=None, app_data=None, user_data=None)
                        elif key == "Marker":
                            # Ensure there are 5 coordinates for markers
                            coords = value.split(", ")
                            if len(coords) == 5:
                                relative_x, relative_y, z_evaluation = float(coords[0]), float(coords[1]), float(coords[2])
                                clicked_x, clicked_y = float(coords[3]), float(coords[4])
                                new_coords = (relative_x, relative_y, z_evaluation)
                                new_clicked_position = (clicked_x, clicked_y)

                                if not self.marker_exists(new_coords):
                                    self.click_coord = new_coords
                                    self.clicked_position = new_clicked_position
                                    self.mark_point_on_map()

                        elif key == "Rectangle":
                            # Ensure there are 5 values for rectangles (4 coordinates + Z scan state)
                            rect_coords = value.split(", ")
                            if len(rect_coords) == 5:
                                relative_min_x, relative_min_y, relative_max_x, relative_max_y = float(
                                    rect_coords[0]), float(rect_coords[1]), float(rect_coords[2]), float(rect_coords[3])
                                z_scan_state = rect_coords[4]

                                # Convert relative coordinates to absolute for drawing purposes
                                if dpg.does_item_exist("map_image"):
                                    item_x, item_y = dpg.get_item_pos("map_image")
                                    if item_x == 0:
                                        dpg.render_dearpygui_frame()  # Render a frame to ensure the map image position is ready
                                        item_x, item_y = dpg.get_item_pos("map_image")
                                else:
                                    print("map_image does not exist")
                                    item_x = 0
                                    item_y = 0

                                min_x = relative_min_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
                                min_y = relative_min_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")
                                max_x = relative_max_x / dpg.get_value("MapFactorX") + item_x + dpg.get_value("MapOffsetX")
                                max_y = relative_max_y / dpg.get_value("MapFactorY") + item_y + dpg.get_value("MapOffsetY")

                                # Store the rectangle with relative coordinates and Z scan state
                                new_rectangle = (
                                relative_min_x, relative_min_y, relative_max_x, relative_max_y, z_scan_state)
                                if new_rectangle not in self.area_markers:
                                    self.area_markers.append(new_rectangle)
                                    rect_index = len(self.area_markers) - 1  # Index of the new rectangle
                                    # Draw the rectangle on the map with absolute coordinates
                                    dpg.draw_rectangle(pmin=(min_x, min_y), pmax=(max_x, max_y),
                                                       color=(0, 255, 0, 255),
                                                       thickness=2, parent="map_draw_layer",
                                                       tag=f"query_rectangle_{rect_index}")
                                else:
                                    print("Rectangle already exists")
                            else:
                                print(len(rect_coords))
                                print("Rectangle should have 5 values (4 coordinates and Z scan state)")

                        # Load experimental notes
                        elif key == "Exp_notes":
                            self.expNotes = value
                            dpg.set_value("inTxtScan_expText", value)  # Update the input text widget with the loaded notes

            print("Map parameters and markers loaded.")

            # Activate the last marker and area marker after loading
            if self.markers:
                self.active_marker_index = len(self.markers) - 1
                self.act_marker(self.active_marker_index)  # Activate the last marker

            if self.area_markers:
                self.active_area_marker_index = len(self.area_markers) - 1
                self.act_area_marker(self.active_area_marker_index)  # Activate the last area marker

            self.update_markers_table()

        except FileNotFoundError:
            print("map_config.txt not found.")
        except Exception as e:
            print(f"Error loading map parameters: {e}")

    def update_markers_table(self):
        """Rebuild the table rows to show both markers and area markers."""
        table_id = "markers_table"

        # Ensure the table exists before attempting to access its children
        if not dpg.does_item_exist(table_id):
            print(f"Table {table_id} does not exist.")
            return  # Exit the function if the table does not exist

        # Get the number of digits from the input field
        num_of_digits = dpg.get_value("MapNumOfDigits")

        # Create a dynamic format string based on the number of digits
        format_str = f"{{:.{num_of_digits}f}}"

        # Delete only the rows, keep the table headers intact
        for child in dpg.get_item_children(table_id, 1):
            if dpg.does_item_exist(child):  # Check if the item exists before deleting it
                dpg.delete_item(child)

        # Helper function to format numbers with a variable number of decimal places and strip trailing zeros
        def format_value(val):
            return format_str.format(val).rstrip('0').rstrip('.') if '.' in format_str.format(
                val) else format_str.format(val)

        # Add markers to the table
        for i, (marker_tag, text_tag, relative_coords, clicked_position) in enumerate(self.markers):
            with dpg.table_row(parent=table_id):
                # If this is the active marker, add an asterisk (*) next to the ID
                active_indicator = "*" if i == self.active_marker_index else ""

                dpg.add_text(f"{i}{active_indicator}")  # Add the marker ID with an asterisk if active
                dpg.add_text(format_value(relative_coords[0]))
                dpg.add_text(format_value(relative_coords[1]))
                dpg.add_text(format_value(relative_coords[2]))
                dpg.add_text("")
                dpg.add_text("")
                dpg.add_button(label="Del", width=-1,
                               callback=partial(self.delete_marker, i))  # Use zero-based index
                dpg.add_button(label="Go", width=-1, callback=partial(self.go_to_marker, i))
                dpg.add_button(label="*", width=-1,
                               callback=partial(self.act_marker, i))  # Use zero-based index

        # Only add the area markers section if there are any area markers
        if self.area_markers:
            with dpg.table_row(parent=table_id):
                dpg.add_text("ID ---")
                dpg.add_text("Min X")
                dpg.add_text("Max X")
                dpg.add_text("Min Y")
                dpg.add_text("Max Y")
                dpg.add_text("--------")
                dpg.add_text("Action")
                dpg.add_text("--------")
                dpg.add_text("--------")

        # Add area markers (rectangles) to the table with relative positions
        marker_count = len(self.markers)
        for i, (min_x, min_y, max_x, max_y, z_scan_state) in enumerate(self.area_markers):
            # If this is the active area marker, add an asterisk (*) next to the ID
            active_area_indicator = "*" if i == self.active_area_marker_index else ""

            # Add "Z" next to the ID if Z scan is enabled
            z_indicator = "z" if z_scan_state == "Z scan enabled" else ""

            # Add the area marker row to the table with relative positions
            with dpg.table_row(parent=table_id):
                dpg.add_text(f"A{z_indicator}{i}{active_area_indicator}")
                dpg.add_text(format_value(min_x))
                dpg.add_text(format_value(max_x))
                dpg.add_text(format_value(min_y))
                dpg.add_text(format_value(max_y))

                dpg.add_button(label="Del", width=-1, callback=partial(self.delete_area_marker, i))
                dpg.add_button(label="Updt", width=-1, callback=partial(self.update_scan_area_marker, i))
                dpg.add_button(label="z", width=-1, callback=partial(self.toggle_z_scan, i))
                dpg.add_button(label="*", width=-1, callback=partial(self.act_area_marker, i))

        print("Markers and area markers table updated.")

    def toggle_z_scan(self, index):
        """Toggle Z scan for the selected area marker."""
        if 0 <= index < len(self.area_markers):
            # Assuming area_markers have an additional field for Z scan state (True/False)
            area_marker = self.area_markers[index]

            # Check if Z scan is enabled and toggle the state
            if len(area_marker) == 5 and area_marker[4] == "Z scan enabled":
                # Disable Z scan
                self.area_markers[index] = (
                area_marker[0], area_marker[1], area_marker[2], area_marker[3], "Z scan disabled")
                print(f"Z scan disabled for area marker {index}.")
            else:
                # Enable Z scan
                self.area_markers[index] = (
                area_marker[0], area_marker[1], area_marker[2], area_marker[3], "Z scan enabled")
                print(f"Z scan enabled for area marker {index}.")
        else:
            print("Invalid area marker index.")

        self.update_markers_table()

    def delete_marker(self, index):
        """Delete a specific marker by index."""
        if 0 <= index < len(self.markers):
            # Get the marker details at the given index
            marker_tag, text_tag, _, _ = self.markers[index]

            # Delete the marker and text from the GUI if they exist
            if dpg.does_item_exist(marker_tag):
                dpg.delete_item(marker_tag)
            if dpg.does_item_exist(text_tag):
                dpg.delete_item(text_tag)

            # Remove the marker from the list
            self.markers.pop(index)

            # Update the table after deletion
            self.update_markers_table()

            # Activate the next marker or the previous one if no next marker exists
            if self.markers:
                if index >= len(self.markers):
                    # If the deleted marker was the last one, activate the new last marker
                    self.active_marker_index = len(self.markers) - 1
                else:
                    # Otherwise, activate the marker at the same index
                    self.active_marker_index = index
                self.act_marker(self.active_marker_index)
            else:
                print("No more markers to activate, switching to area markers.")
                self.move_mode = "area_marker"
                # Update the button label to indicate the current state
                dpg.set_item_label("toggle_marker_area", "move area")

            print(f"Marker {index + 1} deleted.")
        else:
            print(f"Invalid marker index: {index}")

    def delete_area_marker(self, index):
        """Delete a specific area marker (rectangle) by index."""
        if 0 <= index < len(self.area_markers):
            # Construct the tag for the rectangle based on its index
            rectangle_tag = f"query_rectangle_{index}"

            # Delete the rectangle from the GUI if it exists
            if dpg.does_item_exist(rectangle_tag):
                dpg.delete_item(rectangle_tag)

            # Remove the area marker from the list
            self.area_markers.pop(index)

            # Update the combined table after deletion
            self.update_markers_table()

            # Activate the next area marker or the previous one if no next area marker exists
            if self.area_markers:
                if index >= len(self.area_markers):
                    # If the deleted area marker was the last one, activate the new last area marker
                    self.active_area_marker_index = len(self.area_markers) - 1
                else:
                    # Otherwise, activate the area marker at the same index
                    self.active_area_marker_index = index
                self.act_area_marker(self.active_area_marker_index)
            else:
                print("No more area markers to activate, switching to point markers.")
                self.move_mode = "marker"
                # Update the button label to indicate the current state
                dpg.set_item_label("toggle_marker_area", "move marker")

            print(f"Area marker {index + 1} deleted.")
        else:
            print(f"Invalid area marker index: {index}")

    def resize_image(self, sender, app_data, user_data):
        # Get the values from the sliders or input fields
        new_width = dpg.get_value("width_slider")
        new_height = dpg.get_value("height_slider")

        # Check which slider (width or height) triggered the callback
        if sender == "width_slider":
            print("Width slider was changed.")
            # Adjust height to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_height = int(new_width / self.Map_aspect_ratio)
                dpg.set_value("height_slider", new_height)

        elif sender == "height_slider":
            print("Height slider was changed.")
            # Adjust width to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_width = int(new_height * self.Map_aspect_ratio)
                dpg.set_value("width_slider", new_width)

        # Update input fields when sliders change
        dpg.set_value("width_input", new_width)
        dpg.set_value("height_input", new_height)

        # Only update the image if the new width and height are reasonable
        if new_width >= 100 and new_height >= 100:
            dpg.configure_item("map_image", width=new_width, height=new_height)

    def resize_from_input(self,sender, app_data, user_data):
        # Get the values from the input fields
        new_width = dpg.get_value("width_input")
        new_height = dpg.get_value("height_input")

        # Check which slider (width or height) triggered the callback
        if sender == "width_input":
            print("Width input was changed.")
            # Adjust height to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_height = int(new_width / self.Map_aspect_ratio)
                dpg.set_value("height_input", new_height)

        elif sender == "height_input":
            print("Height input was changed.")
            # Adjust width to maintain aspect ratio if needed
            if self.maintain_aspect_ratio:
                new_width = int(new_height * self.Map_aspect_ratio)
                dpg.set_value("width_input", new_width)

        # Update sliders when input fields change
        dpg.set_value("width_slider", new_width)
        dpg.set_value("height_slider", new_height)

        # Resize the image
        if new_width >= 100 and new_height >= 100:
            dpg.configure_item("map_image", width=new_width, height=new_height)

    def map_click_callback(self, app_data):
        # Get the mouse position relative to the map widget
        try:
            mouse_pos = dpg.get_mouse_pos(local=True)

            if mouse_pos is None:
                print("Mouse position not available.")
                return 1
            
            mouse_x, mouse_y = mouse_pos

            if dpg.does_item_exist("map_image"):
                self.map_item_x, self.map_item_y = dpg.get_item_pos("map_image")
            else:
                print("map_image does not exist")
                return 1

            if mouse_x<self.map_item_x or mouse_y<self.map_item_y:
                # print("click outside the map region")
                return 0 # click outside the map region

            if self.ZCalibrationData is None:
                print("No Z calibration data.")
                return 1

            # Calculate the relative position of the click on the map
            relative_x = (mouse_x - self.map_item_x - dpg.get_value("MapOffsetX"))*dpg.get_value("MapFactorX")
            relative_y = (mouse_y - self.map_item_y - dpg.get_value("MapOffsetY"))*dpg.get_value("MapFactorY")
            z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x*1e6)), int(relative_y*1e6)))/1e6
            # Update the text with the coordinates
            dpg.set_value("coordinates_text", f"x = {relative_x:.1f}, y = {relative_y:.1f}, z = {z_evaluation:.2f}")
            # Check if the current clicked_position is equal to the previous clicked position

            if self.marker_exists((relative_x, relative_y)):
                print("A marker with the same relative coordinates already exists.")
                return 1  # Prevent creating a new marker

            if self.click_coord == (relative_x, relative_y, z_evaluation):
                # Do something when the positions are equal
                print("Current click position is the same as the previous click.")
                self.mark_point_on_map()
            else:
                # Store the coordinates for the mark
                self.clicked_position = (mouse_x, mouse_y)
                self.click_coord = (relative_x, relative_y, z_evaluation)

        except Exception as e:
            print(f"Error in map_click_callback: {e}")

    def delete_all_markers(self):
        # Delete all point markers and their associated text
        for marker_tag, text_tag, relative_coords, clicked_position in self.markers:
            if dpg.does_item_exist(marker_tag):
                dpg.delete_item(marker_tag)
            if dpg.does_item_exist(text_tag):
                dpg.delete_item(text_tag)

        # Delete all area markers (rectangles)
        for i, rectangle in enumerate(self.area_markers):
            rectangle_tag = f"query_rectangle_{i}"
            if dpg.does_item_exist(rectangle_tag):
                dpg.delete_item(rectangle_tag)

        # Clear both markers and area_markers lists
        self.markers = []
        self.area_markers = []
        self.update_markers_table() # Update the table after deletion
        print("All markers and rectangles have been deleted.")

    def delete_all_except_active(self):
        """Delete all markers and area markers except the active ones."""

        # Delete all non-active point markers and their associated text
        for i, (marker_tag, text_tag, relative_coords, clicked_position) in enumerate(self.markers):
            if i != self.active_marker_index:  # Skip the active marker
                if dpg.does_item_exist(marker_tag):
                    dpg.delete_item(marker_tag)
                if dpg.does_item_exist(text_tag):
                    dpg.delete_item(text_tag)

        # Remove non-active markers from the list
        self.markers = [self.markers[self.active_marker_index]] if self.active_marker_index is not None else []
        self.active_marker_index=0

        # Delete all non-active area markers (rectangles)
        for i in range(len(self.area_markers)):
            if i != self.active_area_marker_index:  # Skip the active area marker
                rectangle_tag = f"query_rectangle_{i}"
                if dpg.does_item_exist(rectangle_tag):
                    dpg.delete_item(rectangle_tag)

        # Remove non-active area markers from the list
        self.area_markers = [
            self.area_markers[self.active_area_marker_index]] if self.active_area_marker_index is not None else []
        self.active_area_marker_index=0

        # Update the table after deletion
        self.update_markers_table()
        print("All markers and rectangles except active ones have been deleted.")

    def mark_point_on_map(self):
        if hasattr(self, 'clicked_position'):
            x_pos, y_pos = self.clicked_position

            marker_tag = f"marker_{len(self.markers)}"
            text_tag = f"text_{len(self.markers)}"

            # Retrieve the number of digits from the input field
            num_of_digits = dpg.get_value("MapNumOfDigits")

            # Update the format string to use the retrieved number of digits
            coord_text = f"({self.click_coord[0]:.{num_of_digits}f}, {self.click_coord[1]:.{num_of_digits}f}, {self.click_coord[2]:.{num_of_digits}f})"

            # Add a circle at the clicked position
            dpg.draw_circle(center=(x_pos, y_pos), radius=2, color=(255, 0, 0, 255), fill=(255, 0, 0, 100), parent="map_draw_layer", tag=marker_tag)

            # Add text next to the marker showing the 3 coordinates, using the selected text color
            dpg.draw_text(pos=(x_pos, y_pos), text=coord_text, color=self.text_color, size=14 + num_of_digits * 2,
                          parent="map_draw_layer", tag=text_tag)

            print(coord_text)

            # Store the marker and text tags, along with the relative and clicked positions
            self.markers.append((marker_tag, text_tag, self.click_coord, self.clicked_position))

            # Activate the newly added marker by setting it as the active marker
            self.active_marker_index = len(self.markers) - 1

            self.update_markers_table()
            self.update_marker_texts()

    def update_marker_texts(self, full=1):
        # Retrieve the updated number of digits
        num_of_digits = dpg.get_value("MapNumOfDigits")
        if num_of_digits < 0:
            num_of_digits = 0
            dpg.set_value("MapNumOfDigits", num_of_digits)

        # Loop through all markers and update the text
        for i, (marker_tag, text_tag, click_coord, clicked_position) in enumerate(self.markers):
            x_pos, y_pos = clicked_position

            # If full == 1, recalculate the relative positions and Z values
            if full == 1:
                # clicked_position provides the absolute position of the click
                abs_x, abs_y = x_pos, y_pos

                # Calculate relative X and Y positions based on offsets and factors
                relative_x = (abs_x - self.map_item_x - dpg.get_value("MapOffsetX")) * dpg.get_value("MapFactorX")
                relative_y = (abs_y - self.map_item_y - dpg.get_value("MapOffsetY")) * dpg.get_value("MapFactorY")

                # Recalculate Z based on the updated relative coordinates
                z_evaluation = float(calculate_z_series(self.ZCalibrationData, np.array(int(relative_x * 1e6)),
                                                        int(relative_y * 1e6))) / 1e6

                # Update click_coord with the new calculated relative X, Y, and Z values
                click_coord = [relative_x, relative_y, z_evaluation]

            # Update the format string for the current marker
            coord_text = f"({click_coord[0]:.{num_of_digits}f}, {click_coord[1]:.{num_of_digits}f}, {click_coord[2]:.{num_of_digits}f})"

            # Determine the color (magenta for active marker, self.text_color for others)
            text_color = (255, 0, 255) if i == self.active_marker_index else self.text_color

            # Delete the old text and redraw with updated coordinates
            dpg.delete_item(text_tag)
            dpg.draw_text(pos=(x_pos + 10, y_pos), text=coord_text, color=text_color, size=14 + num_of_digits * 2,
                          parent="map_draw_layer", tag=text_tag)

    def btn_num_of_digits_change(self, sender, app_data):
        self.update_marker_texts()
        self.update_markers_table()

    def marker_exists(self, coords):
        for _, _, existing_relative_coords, _ in self.markers:
            # Compare relative coordinates with a small tolerance for floating point values
            if all(abs(existing_relative_coords[i] - coords[i]) < 1e-6 for i in range(2)):
                print("Marker already exists")
                return True
        return False

    def delete_last_mark(self):
        if self.markers:
            # Unpack the four elements returned by pop: marker tag, text tag, relative coordinates, and clicked position
            last_marker, last_text, _, _ = self.markers.pop()

            # Delete both the marker and the associated text
            dpg.delete_item(last_marker)
            dpg.delete_item(last_text)

            self.update_markers_table()  # Update the table after deletion
            print("marker has been deleted.")

    def find_middle(self):
        try:
            # Try to get the current position from the positioner
            self.positioner.GetPosition()
            Center = list(self.positioner.AxesPositions)  # Ensure that Center is properly retrieved

            # Initialize P1 and P2 lists
            P1 = []
            P2 = []

            # Calculate the lower and upper bounds
            for ch in range(2):
                P1.append((Center[ch] - self.L_scan[ch] * 1e3 / 2) * 1e-6)
                P2.append((Center[ch] + self.L_scan[ch] * 1e3 / 2) * 1e-6)

            # Print the calculated values
            print(f"Center = {[c * 1e-6 for c in Center]}")
            print(f"P1 = {P1}, P2 = {P2}")
            print(f"L_scan = {self.L_scan}")

        except AttributeError as e:
            print(f"Attribute error: {e}")
        except IndexError as e:
            print(f"Index error: {e}")
        except TypeError as e:
            print(f"Type error: {e}")
        except Exception as e:
            # Catch all other exceptions
            print(f"An unexpected error occurred: {e}")

    def act_marker(self, index):
        """Activate a specific marker by its index."""
        if 0 <= index < len(self.markers):
            self.active_marker_index = index  # Store the active marker's index
            print(f"Marker {index + 1} activated.")
            self.update_markers_table() # Update the table to visually highlight the active marker
            self.update_marker_texts()
        else:
            print("Invalid marker index.")

    def act_area_marker(self, index):
        """Activate a specific area marker by its index."""
        if 0 <= index < len(self.area_markers):
            self.active_area_marker_index = index  # Store the active area marker's index
            print(f"Area marker {index} activated.")  # Zero-based index
            self.highlight_active_rectangle()  # Change rectangle color to magenta
        else:
            print("Invalid area marker index.")

    def set_marker_coord_to_zero(self):
        """Set the map offsets such that the active marker's relative coordinates become (0,0)."""
        if self.active_marker_index is not None and self.active_marker_index >= 0:
            marker_tag, text_tag, relative_coords, clicked_position = self.markers[self.active_marker_index]

            # Get the absolute clicked position for the active marker
            abs_x, abs_y = clicked_position

            # Calculate the new offsets to make the active marker's relative position (0,0)
            # Keep the marker's visual position unchanged but reset its relative coordinates
            new_offset_x = abs_x - self.map_item_x
            new_offset_y = abs_y - self.map_item_y

            # Update the offsets in the UI
            dpg.set_value("MapOffsetX", new_offset_x)
            dpg.set_value("MapOffsetY", new_offset_y)

            # Recalculate relative coordinates of all markers based on the new offsets and factors
            self.update_marker_texts(full=1)

            print(f"Offsets updated: MapOffsetX={new_offset_x}, MapOffsetY={new_offset_y}")

    def toggle_set_x_or_y(self, sender):
        """Toggle between setting the gap for X or Y axis."""
        current_label = dpg.get_item_label(sender)

        if current_label == "x":
            dpg.configure_item(sender, label="y")
            print("Toggled to Y axis.")
        else:
            dpg.configure_item(sender, label="x")
            print("Toggled to X axis.")

    def map_set_gap(self, sender, app_data, user_data):
        """Set FactorX or FactorY such that the gap between the active marker and the previous marker equals the gap_value."""
        if not hasattr(self, 'active_marker_index') or self.active_marker_index < 0:
            print("No marker is activated. Please activate a marker first.")
            return

        if len(self.markers) < 2:
            print("Need at least two markers to calculate the gap.")
            return

        # Get the active marker's coordinates
        active_marker_tag, active_text_tag, active_relative_coords, active_clicked_position = self.markers[
            self.active_marker_index]

        # Get the previous marker's coordinates (the one before the active marker)
        if self.active_marker_index > 0:
            previous_marker_tag, previous_text_tag, previous_relative_coords, previous_clicked_position = self.markers[
                self.active_marker_index - 1]
        else:  # (the one after the active marker)
            previous_marker_tag, previous_text_tag, previous_relative_coords, previous_clicked_position = self.markers[
                self.active_marker_index + 1]

        # Get the gap value from the input field
        gap_value = dpg.get_value("MapSetGap")

        # Check whether we are adjusting "x" or "y" axis
        axis = dpg.get_item_label("toggle_set_x_or_y")  # Assuming 'X' or 'Y' is passed as label
        print(f"Axis selected: {axis}")

        if axis == "x":
            # Consider the current MapFactorX for delta_x calculation
            current_factor_x = dpg.get_value("MapFactorX")

            # Calculate delta_x between active and previous marker, considering the current MapFactorX
            delta_x = abs((active_relative_coords[0] - previous_relative_coords[0]) / current_factor_x)

            # Calculate FactorX so that the gap between the markers becomes equal to gap_value
            factor_x = gap_value / delta_x if delta_x != 0 else 1  # Prevent division by zero

            # Update the FactorX value in the UI
            dpg.set_value("MapFactorX", factor_x)
            print(f"FactorX updated based on gap value {gap_value}: FactorX = {factor_x}")

        elif axis == "y":
            # Consider the current MapFactorY for delta_y calculation
            current_factor_y = dpg.get_value("MapFactorY")

            # Calculate delta_y between active and previous marker, considering the current MapFactorY
            delta_y = abs((active_relative_coords[1] - previous_relative_coords[1]) / current_factor_y)

            # Calculate FactorY so that the gap between the markers becomes equal to gap_value
            factor_y = gap_value / delta_y if delta_y != 0 else 1  # Prevent division by zero

            # Update the FactorY value in the UI
            dpg.set_value("MapFactorY", factor_y)
            print(f"FactorY updated based on gap value {gap_value}: FactorY = {factor_y}")

        else:
            print("Invalid axis input. Use 'X' or 'Y'.")

        # Recalculate marker positions with updated factors
        self.update_marker_texts(full=1)

        # Ensure that the new gap is set properly by recalculating and updating the positions
        print(f"Markers updated. New gap set to {gap_value} on the {axis} axis.")

    def shift_marker_up(self):
        """Shift the active marker up in the list."""
        if hasattr(self, 'active_marker_index') and self.active_marker_index > 0:
            # Swap the active marker with the one above it
            self.markers[self.active_marker_index], self.markers[self.active_marker_index - 1] = \
                self.markers[self.active_marker_index - 1], self.markers[self.active_marker_index]
            self.active_marker_index -= 1  # Update active marker index
            print(f"Marker shifted up to position {self.active_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift up, already at the top.")

    def shift_marker_down(self):
        """Shift the active marker down in the list."""
        if hasattr(self, 'active_marker_index') and self.active_marker_index < len(self.markers) - 1:
            # Swap the active marker with the one below it
            self.markers[self.active_marker_index], self.markers[self.active_marker_index + 1] = \
                self.markers[self.active_marker_index + 1], self.markers[self.active_marker_index]
            self.active_marker_index += 1  # Update active marker index
            print(f"Marker shifted down to position {self.active_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift down, already at the bottom.")

    def shift_area_marker_up(self):
        """Shift the active area marker up in the list."""
        if hasattr(self, 'active_area_marker_index') and self.active_area_marker_index > 0:
            # Swap the active area marker with the one above it
            self.area_markers[self.active_area_marker_index], self.area_markers[self.active_area_marker_index - 1] = \
                self.area_markers[self.active_area_marker_index - 1], self.area_markers[self.active_area_marker_index]
            self.active_area_marker_index -= 1  # Update active area marker index
            print(f"Area marker shifted up to position {self.active_area_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift up, already at the top or no area markers active.")

    def shift_area_marker_down(self):
        """Shift the active area marker down in the list."""
        if hasattr(self, 'active_area_marker_index') and self.active_area_marker_index < len(self.area_markers) - 1:
            # Swap the active area marker with the one below it
            self.area_markers[self.active_area_marker_index], self.area_markers[self.active_area_marker_index + 1] = \
                self.area_markers[self.active_area_marker_index + 1], self.area_markers[self.active_area_marker_index]
            self.active_area_marker_index += 1  # Update active area marker index
            print(f"Area marker shifted down to position {self.active_area_marker_index + 1}.")
            self.update_markers_table()
        else:
            print("Cannot shift down, already at the bottom or no area markers active.")

    def highlight_active_rectangle(self):
        """Change the color of the active rectangle to magenta and reset others to green.
           If Z scan is enabled, use cyan color."""
        for i, (min_x, min_y, max_x, max_y, z_scan_state) in enumerate(self.area_markers):
            # Determine the color: magenta for active, green for others, cyan if Z scan is enabled
            if i == self.active_area_marker_index:
                rect_color = (255, 0, 255, 255)  # Active rectangle color (magenta)
            elif z_scan_state == "Z scan enabled":
                rect_color = (0, 255, 255, 255)  # Z scan enabled (cyan)
            else:
                rect_color = (0, 255, 0, 255)  # Default color for other rectangles (green)

            # Check if the rectangle item exists before trying to update it
            rect_tag = f"query_rectangle_{i}"  # Use consistent tag indexing
            if dpg.does_item_exist(rect_tag):
                # Update the existing rectangle color
                dpg.configure_item(rect_tag, color=rect_color)
            else:
                print(f"Rectangle with tag {rect_tag} does not exist.")

        self.update_markers_table()

    def scan_all_area_markers(self):
        """Automatically scan all area markers sequentially without user interaction, handling errors and skipping problematic markers."""
        if len(self.area_markers) == 0:
            print("No area markers available for scanning.")
            return

        print(f"Starting scan for {len(self.area_markers)} area markers.")

        # Iterate over all area markers
        for index in range(len(self.area_markers)):
            try:
                print(f"Activating area marker {index + 1}/{len(self.area_markers)}.")

                # Activate the area marker before scanning
                self.act_area_marker(index)

                print(f"Updating scan parameters for area marker {index + 1}.")
                # Update the scan parameters for the selected area marker
                self.update_scan_area_marker(index)

                # After updating, the start scan position (point) is already calculated in the update function
                point = [
                    dpg.get_value("mcs_ch0_ABS") * 1e6,  # X position in micrometers
                    dpg.get_value("mcs_ch1_ABS") * 1e6,  # Y position in micrometers
                    dpg.get_value("mcs_ch2_ABS") * 1e6  # Z position in micrometers
                ]

                # Move to the calculated scan start position for each axis
                for ch in range(3):
                    if self.use_picomotor:
                        self.pico.MoveABSOLUTE(ch+1, int(point[ch]))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm, by picomotor.")
                    else:
                        self.positioner.MoveABSOLUTE(ch, int(point[ch]))  # Move absolute to start location
                        print(f"Moved to start position for channel {ch} at {point[ch]} µm.")

                # Ensure the stage has reached its position
                time.sleep(0.005)  # Allow motion to start
                for ch in range(3):
                    res = self.readInpos(ch)  # Wait for motion to complete
                    if res:
                        print(f"Axis {ch} in position at {self.positioner.AxesPositions[ch]}.")
                    else:
                        print(f"Failed to move axis {ch} to position.")

                # Start the scan automatically
                print(f"Starting scan for area marker {index + 1}.")
                self.StartScan3D()

                # Halt if the scan is stopped manually
                if self.stopScan:
                    print(f"Scan stopped manually after scanning {index + 1} area markers.")
                    return

            except Exception as e:
                print(f"An error occurred while scanning area marker {index + 1}: {e}")
                # Skip to the next area marker if an error occurs
                continue

        print("Completed scanning all area markers.")

    def go_to_marker(self):
        """Move to the absolute coordinates of the active marker."""

        # Ensure that there is an active marker
        if self.active_marker_index is None or self.active_marker_index >= len(self.markers):
            print("No active marker selected.")
            return

        # Get the absolute coordinates of the active marker (stored in self.click_coord)
        marker = self.markers[self.active_marker_index]
        absolute_coords = marker[2]  # self.click_coord is stored here

        print(
            f"Moving to marker at (X: {absolute_coords[0]} µm, Y: {absolute_coords[1]} µm, Z: {absolute_coords[2]} µm)")

        # Move the positioner to the stored absolute positions for each axis
        for ch in range(3):
            try:
                self.positioner.MoveABSOLUTE(ch, int(absolute_coords[ch]*1e6))  # Move absolute to marker position
                print(f"Moved to position for channel {ch} at {absolute_coords[ch]} µm.")
            except Exception as e:
                print(f"Failed to move channel {ch} to {absolute_coords[ch]} µm: {e}")
                return

        # Ensure the stage has reached its position
        time.sleep(0.005)  # Allow motion to start
        for ch in range(3):
            try:
                res = self.readInpos(ch)  # Wait for motion to complete
                if res:
                    print(f"Axis {ch} in position at {self.positioner.AxesPositions[ch]}.")
                else:
                    print(f"Failed to move axis {ch} to position.")
            except Exception as e:
                print(f"Error while waiting for channel {ch} to reach position: {e}")
                return

        print("Reached the active marker position.")

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
        start_Plot_time = time.time()
       
        plot_size = [int(self.viewport_width*0.3), int(self.viewport_height*0.4)]
                
        arrYZ = np.flipud(self.scan_data[:,:,self.idx_scan[Axis.X.value]])
        arrXZ = np.flipud(self.scan_data[:,self.idx_scan[Axis.Y.value],:])
        arrXY = np.flipud(self.scan_data[self.idx_scan[Axis.Z.value],:,:])

        result_arrayXY = (arrXY*255/arrXY.max())
        result_arrayXY_ = []
        result_arrayXZ = (arrXZ*255/arrXZ.max())
        result_arrayXZ_ = []
        result_arrayYZ = (arrYZ*255/arrYZ.max())
        result_arrayYZ_ = []
        
        if use_fast_rgb:
            result_arrayXY_ = self.fast_rgb_convert(result_arrayXY)
            result_arrayXZ_ = self.fast_rgb_convert(result_arrayXZ)
            result_arrayYZ_ = self.fast_rgb_convert(result_arrayYZ)
        else:
            for i in range(arrXY.shape[0]):
                for j in range(arrXY.shape[1]):
                    res = self.intensity_to_rgb_heatmap(result_arrayXY.astype(np.uint8)[i][j]/255)
                    result_arrayXY_.append(res[0] / 255)
                    result_arrayXY_.append(res[1] / 255)
                    result_arrayXY_.append(res[2] / 255)
                    result_arrayXY_.append(res[3] / 255)

            for i in range(arrXZ.shape[0]):
                for j in range(arrXZ.shape[1]):
                    res = self.intensity_to_rgb_heatmap(result_arrayXZ.astype(np.uint8)[i][j]/255)
                    result_arrayXZ_.append(res[0] / 255)
                    result_arrayXZ_.append(res[1] / 255)
                    result_arrayXZ_.append(res[2] / 255)
                    result_arrayXZ_.append(res[3] / 255)

            for i in range(arrYZ.shape[0]):
                for j in range(arrYZ.shape[1]):
                    res = self.intensity_to_rgb_heatmap(result_arrayYZ.astype(np.uint8)[i][j]/255)
                    result_arrayYZ_.append(res[0] / 255)
                    result_arrayYZ_.append(res[1] / 255)
                    result_arrayYZ_.append(res[2] / 255)
                    result_arrayYZ_.append(res[3] / 255)

        # Generate image graph

        # Delete previous items
        dpg.delete_item("scan_group")
        dpg.delete_item("texture_reg")
        dpg.delete_item("textureXY_tag")
        dpg.delete_item("textureXZ_tag")
        dpg.delete_item("textureYZ_tag")

        # Add textures
        dpg.add_texture_registry(show=False,tag="texture_reg")
        dpg.add_dynamic_texture(width=arrXY.shape[1], height=arrXY.shape[0], default_value=result_arrayXY_, tag="textureXY_tag",parent="texture_reg")
        dpg.add_dynamic_texture(width=arrXZ.shape[1], height=arrXZ.shape[0], default_value=result_arrayXZ_, tag="textureXZ_tag",parent="texture_reg")
        dpg.add_dynamic_texture(width=arrYZ.shape[1], height=arrYZ.shape[0], default_value=result_arrayYZ_, tag="textureYZ_tag",parent="texture_reg")
        

        # Plot scan
        dpg.add_group(horizontal=True, tag="scan_group",parent="Scan_Window") 

        # XY plot
        dpg.add_plot(parent="scan_group",tag="plotImaga",width = plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True, query=True,callback=self.queryXY_callback)
        dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z="+"{0:.2f}".format(self.Zv[self.idx_scan[Axis.Z.value]]),parent="plotImaga")
        dpg.add_plot_axis(dpg.mvYAxis, label="y axis",parent="plotImaga",tag="plotImaga_Y")
        dpg.add_image_series("textureXY_tag",bounds_min = [self.startLoc[0], self.startLoc[1]], bounds_max = [self.endLoc[0], self.endLoc[1]], label="Scan data",parent="plotImaga_Y")#, source = self.image_path)
        dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(arrXY),
                               max_scale=np.max(arrXY), colormap=dpg.mvPlotColormap_Jet)
         # Update width
        item_width = dpg.get_item_width("plotImaga")
        item_height = dpg.get_item_height("plotImaga")
        if (item_width is None) or (item_height is None):
            raise Exception("Window does not exist")
      
        if len(arrYZ) == 1:
            dpg.set_item_width("Scan_Window",item_width+50)
        else :
            dpg.set_item_width("Scan_Window",item_width*3+50)    
            dpg.add_plot(parent="scan_group",tag="plotImagb",width = plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True, query=True,callback=self.queryXZ_callback)
            dpg.add_plot_axis(dpg.mvXAxis, label="x (um), y="+"{0:.2f}".format(self.Yv[self.idx_scan[Axis.Y.value]]),parent="plotImagb")
            dpg.add_plot_axis(dpg.mvYAxis, label="z (um)",parent="plotImagb",tag="plotImagb_Y")
            dpg.add_image_series(f"textureXZ_tag",bounds_min = [self.startLoc[0], self.startLoc[2]], bounds_max = [self.endLoc[0], self.endLoc[2]], label="Scan data",parent="plotImagb_Y")#, source = self.image_path)

            dpg.add_plot(parent="scan_group",tag="plotImagc",width = plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True, query=True,callback=self.queryYZ_callback)
            dpg.add_plot_axis(dpg.mvXAxis, label="y (um), x="+"{0:.2f}".format(self.Xv[self.idx_scan[Axis.X.value]]),parent="plotImagc")
            dpg.add_plot_axis(dpg.mvYAxis, label="z (um)",parent="plotImagc",tag="plotImagc_Y")
            dpg.add_image_series(f"textureYZ_tag",bounds_min = [self.startLoc[1], self.startLoc[2]], bounds_max = [self.endLoc[1], self.endLoc[2]], label="Scan data",parent="plotImagc_Y")#, source = self.image_path)

        dpg.set_item_height("Scan_Window",item_height+150)
                          
        end_Plot_time = time.time()
        print(f"time to plot scan: {end_Plot_time - start_Plot_time}")

    def Plot_Scan(self,Nx = 250 ,Ny = 250, array_2d=[], startLoc=[], endLoc=[], switchAxes = False): # switchAxes = workaround. need to be fixed
        start_Plot_time = time.time()

        plot_size = [int(self.viewport_width*0.4), int(self.viewport_height*0.4)]

        result_array = (array_2d*255/array_2d.max())
        result_array_ = []
        for i in range(array_2d.shape[0]):
            for j in range(array_2d.shape[1]):
                if switchAxes: # switchAxes = workaround. need to be fixed
                    res = self.intensity_to_rgb_heatmap(result_array.astype(np.uint8)[i][j]/255)
                    result_array_.append(res[0] / 255)
                    result_array_.append(res[1] / 255)
                    result_array_.append(res[2] / 255)
                    result_array_.append(res[3] / 255)
                else:
                    result_array_.append(result_array[i][j] / 255)
                    result_array_.append(result_array[i][j] / 255)
                    result_array_.append(result_array[i][j] / 255)
                    result_array_.append(255 / 255)

        # Plot XY graph (image)
        dpg.delete_item("scan_group")
        dpg.delete_item("texture_reg")
        dpg.delete_item("texture_tag")
        time.sleep(0)
        dpg.add_texture_registry(show=False,tag="texture_reg")
        if switchAxes: # switchAxes = workaround. need to be fixed
            dpg.add_dynamic_texture(width=array_2d.shape[1], height=array_2d.shape[0], default_value=result_array_, tag="texture_tag",parent="texture_reg")
        else:
            dpg.add_dynamic_texture(width=array_2d.shape[0], height=array_2d.shape[1], default_value=result_array_, tag="texture_tag",parent="texture_reg")

        # plot scan
        dpg.add_group(horizontal=True, tag="scan_group",parent="Scan_Window")
        dpg.add_plot(parent="scan_group",tag="plotImaga",width = plot_size[0], height=plot_size[1], equal_aspects=True, crosshairs=True)
        # dpg.add_plot_legend(parent="plotImaga")
        dpg.add_plot_axis(dpg.mvXAxis, label="x axis [um]",parent="plotImaga")
        dpg.add_plot_axis(dpg.mvYAxis, label="y axis [um]",parent="plotImaga",tag="plotImaga_Y")
        dpg.add_image_series(f"texture_tag",bounds_min = [startLoc[0], startLoc[1]], bounds_max = [endLoc[0], endLoc[1]], label="Scan data",parent="plotImaga_Y")#, source = self.image_path)
        # dpg.fit_axis_data("x axis")
        # dpg.fit_axis_data("y axis")
        dpg.add_colormap_scale(show = True, parent="scan_group", tag="colormapXY",min_scale=np.min(array_2d), max_scale=np.max(array_2d),colormap=dpg.mvPlotColormap_Jet )

        # update width
        item_width = dpg.get_item_width("plotImaga")
        item_height = dpg.get_item_height("plotImaga")
        dpg.set_item_width("Scan_Window",item_width+150)
        dpg.set_item_height("Scan_Window",item_height+200)

        end_Plot_time = time.time()
        print(f"time to plot scan: {end_Plot_time - start_Plot_time}")

        dpg.set_value("texture_tag", result_array_)

    def UpdateGuiDuringScan(self,Array2D, use_fast_rgb: bool = False):
        val = Array2D.reshape(-1)
        idx = np.where(val != 0)[0]
        minI = val[idx].min()

        result_array_ = self.fast_rgb_convert(np.flipud(Array2D.T))

        dpg.set_value("texture_tag", result_array_)
        dpg.delete_item("colormapXY")
        dpg.add_colormap_scale(show = True, parent="scan_group", tag="colormapXY",min_scale=minI, max_scale=Array2D.max(),colormap=dpg.mvPlotColormap_Jet )

    def UpdateGuiDuringScan_____(self, Array2D: np.ndarray): #$$$
        # todo: remove loops keep only when an imgae is needed
        start_updatePlot_time = time.time()
        result_array_ = []

        Array2D=Array2D*255/Array2D.max() #BBB
        Array2D=np.fliplr(Array2D)

        for i in range(Array2D.shape[0]):  # Y
            for j in range(Array2D.shape[1]):  # X
                res = self.intensity_to_rgb_heatmap(Array2D.astype(np.uint8)[j,i]/255) 
                result_array_.append(res[0] / 255) # shai 30-7-24
                result_array_.append(res[1] / 255)
                result_array_.append(res[2] / 255)
                result_array_.append(res[3] / 255)

        # dpg.set_value("textureXY_tag", result_array_) # 444
        dpg.set_value("texture_tag", result_array_) # 444

    def Update_scan(sender, app_data, user_data):
        sender.bScanChkbox = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_scan", value=sender.bScanChkbox)
        print("Set bScan to: " + str(sender.bScanChkbox))
        sender.GUI_ScanControls()

    def Update_scan_fast(sender, app_data, user_data):
        sender.fast_scan_enabled = user_data
        # time.sleep(0.001)
        # dpg.set_value(item = "chkbox_scan_fast",value=sender.fast_scan_enabled)
        print("Set fast scan to: " + str(sender.fast_scan_enabled))
        # sender.GUI_ScanControls()

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

    def toggle_use_picomotor(sender, app_data, user_data):
        sender.use_picomotor = user_data
        time.sleep(0.001)
        dpg.set_value(item="chkbox_use_picomotor", value=sender.use_picomotor)
        print("Set use_picomotor to: " + str(sender.use_picomotor))

    # QUA
    def QUA_shuffle(self, array, array_len):
        temp = declare(int)
        j = declare(int)
        i = declare(int)
        with for_(i, 0, i < array_len, i + 1):
            assign(j, Random().rand_int(array_len - i))
            assign(temp, array[j])
            assign(array[j], array[array_len - 1 - i])
            assign(array[array_len - 1 - i], temp)
    def initQUA_gen(self, n_count=1, num_measurement_per_array=1):
        if self.exp == Experimet.COUNTER:
            self.counter_QUA_PGM(n_count=int(n_count))
        if self.exp == Experimet.ODMR_CW:
            self.ODMR_CW_QUA_PGM()
        if self.exp == Experimet.RABI:
            self.RABI_QUA_PGM()
        if self.exp == Experimet.PULSED_ODMR:
            self.PulsedODMR_QUA_PGM()
        if self.exp == Experimet.NUCLEAR_RABI:
            self.NuclearRABI_QUA_PGM()
        if self.exp == Experimet.NUCLEAR_POL_ESR:
            self.NuclearSpinPolarization_pulsedODMR_QUA_PGM()
        if self.exp == Experimet.NUCLEAR_MR:
            self.NuclearMR_QUA_PGM()
        if self.exp == Experimet.Nuclear_spin_lifetimeS0:
            self.Nuclear_spin_lifetimeS0_QUA_PGM()
        if self.exp == Experimet.Nuclear_spin_lifetimeS1:
            self.Nuclear_spin_lifetimeS1_QUA_PGM()
        if self.exp == Experimet.Nuclear_Ramsay:
            self.Nuclear_Ramsay_QUA_PGM()
        if self.exp == Experimet.Hahn:
            self.Hahn_QUA_PGM()
        if self.exp == Experimet.Electron_lifetime:
            self.Electron_lifetime_QUA_PGM()
        if self.exp == Experimet.Electron_Coherence:
            self.Electron_Coherence_QUA_PGM()
        if self.exp == Experimet.FAST_SCAN: # triggered scan current arbitrarly crash
            self.counter_array_QUA_PGM(num_bins_per_measurement=int(n_count),
                                       num_measurement_per_array=int(num_measurement_per_array))
        if self.exp == Experimet.SCAN: # ~ 35 msec per measurement for on average for larage scans
            self.MeasureByTrigger_QUA_PGM(num_bins_per_measurement=int(n_count),
                                       num_measurement_per_array=int(num_measurement_per_array))
    def QUA_execute(self, closeQM = False, quaPGM = None,QuaCFG = None):
        if QuaCFG == None:
            QuaCFG = self.quaCFG
        
        if self.bEnableSimulate:
            sourceFile = open('debug.py', 'w')
            print(generate_qua_script(self.quaPGM, QuaCFG), file=sourceFile) 
            sourceFile.close()
            simulation_config = SimulationConfig(duration=28000) # clock cycles
            job_sim = self.qmm.simulate(QuaCFG, self.quaPGM, simulation_config)
            # Simulate blocks python until the simulation is done
            job_sim.get_simulated_samples().con1.plot()
            plt.show()

            return None,None
        else:
            if closeQM:
                self.qmm.close_all_quantum_machines()
            # self.qmm.close_all_quantum_machines() # todo:AmirBoaz

            if quaPGM is None:
                quaPGM = self.quaPGM

            qm = self.qmm.open_qm(config = QuaCFG,close_other_machines=closeQM)
            job = qm.execute(quaPGM)
            
            return qm, job
    
    def verify_insideQUA_FreqValues(self, freq ,min = 0, max = 400): # [MHz]
        if freq < min* self.u.MHz or freq > max* self.u.MHz:
            raise Exception('freq is out of range. verify base freq is up to 400 MHz relative to resonance')

    def Electron_lifetime_QUA_PGM(self): #T1
        # sequence parameters
        tMeasureProcess = self.MeasProcessTime
        tPump = self.time_in_multiples_cycle_time(self.Tpump)
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+tScan_max/2+tMW+tLaser)*array_length*2 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()
                        #play MW
                        play("cw", "MW", duration=tMW//4)  
                        wait(t)
                        align()
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+tScan_max/2+tMW+tLaser)*array_length*2 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle)//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        align("Laser","MW") 
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle)//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser","MW") 
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        align("MW","Detector_OPD") 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)

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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+2*tMW+tScan_max/2+tLaser)*array_length*2 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4)

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle)//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res1)
                        # play MW
                        align("Laser","MW") 
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4) 

                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play Laser
                        play("Turn_ON", "Laser", duration=(tSettle)//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser","MW") 
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+2*tMW+tRF+tScan_max/2+tLaser)*array_length*2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4)
                        # play RF pi/2
                        align("MW","RF")
                        play("const" * amp(p), "RF",duration=(tRF/2) // 4)
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi/2
                        play("const" * amp(p), "RF",duration=(tRF/2) // 4)
                        # play Laser
                        align("RF","Laser") 
                        play("Turn_ON", "Laser", duration=tSettle//4)

                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser","MW")
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4)
                        # do not play RF
                        wait(t + tRF//4)
                        # play Laser
                        play("Turn_ON", "Laser", duration=tSettle//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("Laser","MW") 
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tStart = self.time_in_multiples_cycle_time(self.scan_t_start) # [nsec]
        if Ncpmg>0:
            if ((tStart/(2*Ncpmg) - tMW/2) <=20): # [nsec]
                tStart = (40+tMW)*Ncpmg
        tScan_min = tStart//4 if tStart//4 > 0 else 1     # in [cycles]
        self.scan_t_start = tScan_min*4

        tEnd = self.time_in_multiples_cycle_time(self.scan_t_end)
        tScan_max = tEnd//4 if tEnd//4 > 0 else 1         # in [cycles]
        if tScan_max<tScan_min+self.scan_t_dt // 4:
            tScan_max = tScan_min + self.scan_t_dt // 4
        
        self.scan_t_end = tScan_max*4

        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = (tMW+tScan_max/2+tLaser)*array_length*2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            tWait = declare(int)         # [cycles] time variable which we change during scan


            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                        
                        with if_(Ncpmg>0):
                            assign(t, tWait/(2*Ncpmg)-(tMW/2)//4)  
                        
                        # signal
                        update_frequency("MW", 0) # const I&Q
                        # play MW (I=1,Q=0) @ Pi/2
                        play("xPulse", "MW", duration=(tMW/2)//4)  # xPulse I = 0.5V, Q = zero
                        # wait t unit
                        with if_(Ncpmg==0):
                            wait(tWait)
                        
                        # "CPMG section" I=0, Q=1 @ Pi
                        with for_(m, 0, m < Ncpmg, m + 1):
                            wait(t)
                            #play MW
                            update_frequency("MW", 0)
                            play("xPulse", "MW", duration=tMW//4) # yPulse I = zero, Q = 0.5V
                            # wait t unit
                            wait(t)
                        # align()

                        # play MW (I=1,Q=0) @ Pi/2
                        play("xPulse", "MW", duration=(tMW/2)//4)  

                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference 
                        # wait Tmw + Twait
                        wait(tWait+tMW//4)
                        # play laser
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        tScan_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tScan_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tScan_min, tScan_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tScan_min, tScan_max + dt/10, dt)            # in [cycles]

        # length and idx vector
        array_length = len(self.t_vec)
        # array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tRF+tPump)*Npump+2*tMW+2*tRF+tScan_max+tLaser)*array_length*2
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)         # frequency variable which we change during scan
            t = declare(int)         # [cycles] time variable which we change during scan

            n = declare(int)         # iteration variable
            m = declare(int)         # number of pumping iterations
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

            # # Shuffle parameters - freq
            # val_vec_qua = declare(int, value=np.array([int(i) for i in self.f_vec]))    # frequencies QUA vector
            # idx_vec_qua = declare(int, value=idx_vec_ini)                               # indexes QUA vector
            # idx = declare(int)                                                          # index variable to sweep over all indexes

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4)
                        # play RF pi/2
                        align("MW","RF")
                        play("const" * amp(p), "RF",duration=(tRF/2) // 4)  
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi
                        play("const" * amp(p), "RF",duration=tRF // 4)
                        # Twait, note: t is already in cycles!
                        wait(t)
                        # play RF pi/2
                        play("const" * amp(p), "RF",duration=(tRF/2) // 4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        align("RF","MW")
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # measure signal 
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        # polarize (@fMW_res @ fRF_res)
                        with for_(m, 0, m < Npump, m + 1):
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res1)
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to pump
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        #play MW
                        play("cw", "MW", duration=tMW//4)
                        # do not play RF
                        wait(2*t + (2*tRF)//4)
                        # set MW frequency to resonance
                        update_frequency("MW", fMW_res2)
                        # play MW
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle)
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
        array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = ((tMW+tLaser)*(Npump+2)+tRF*Npump)*array_length 
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
            m = declare(int)         # number of pumping iterations
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
            counts_st = declare_stream()        # experiment signal
            counts_ref_st = declare_stream()    # reference signal

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
                            # set MW frequency to resonance
                            update_frequency("MW", fMW_res)
                            #play MW
                            play("cw", "MW", duration=tMW//4)  
                            # play RF (@resonance freq & pulsed time)
                            align("MW","RF")
                            play("const" * amp(p), "RF",duration=tRF // 4)
                            # turn on laser to polarize
                            align("RF","Laser")
                            play("Turn_ON", "Laser", duration=tPump//4)
                        align()
                        
                        # update MW frequency
                        update_frequency("MW", f)
                        # play MW
                        play("cw", "MW", duration=tMW//4) 
                        # play Laser
                        align("MW","Laser") 
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # play Laser
                        align("MW","Detector_OPD")
                        # measure signal 
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times,tMeasure ,counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference
                        wait(tMW//4) # don't Play MW
                        # Play laser
                        play("Turn_ON", "Laser", duration=(tLaser+tMeasureProcess)//4)
                        # Measure ref
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times_ref,tMeasure ,counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle+tMeasueProcess)
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
        tSequencePeriod = (tMW*2+tRF+tLaser)*2*array_length 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            f = declare(int)
            p = declare(fixed)  # fixed is similar to float 4bit.28bit

            n = declare(int)  # iteration variable
            n_st = declare_stream()  # stream iteration number

            counts_tmp = declare(int)  # temporary variable for number of counts
            counts_ref_tmp = declare(int)  # temporary variable for number of counts reference

            runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)         # iteration variable
            tracking_signal_tmp = declare(int)                # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)                # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int,value=0)

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
                #reset
                with for_(idx, 0, idx < array_length, idx + 1):
                    assign(counts_ref[idx], 0)  # shuffle - assign new val from randon index
                    assign(counts[idx], 0)  # shuffle - assign new val from randon index

                #shuffle
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
                        play("cw", "MW", duration=tMW//4) 
                        # play RF after MW
                        align("MW","RF")
                        play("const" * amp(p), "RF", duration=tRF//4) # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF","MW")
                        play("cw", "MW", duration=tMW//4)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()
                        
                        # reference
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW//4) 
                        # Don't play RF after MW just wait
                        wait(tRF//4)
                        # play MW
                        play("cw", "MW", duration=tMW//4)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        tMW = self.t_mw
        
        # time scan vector
        tRabi_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tRabi_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tRabi_min, tRabi_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt/10, dt)            # in [cycles]

        # indexes vector
        array_length = len(self.t_vec)
        idx_vec_ini = np.arange(0, array_length, 1)

        # tracking signal
        tSequencePeriod = (tMW*2 + tRabi_max + tLaser)*2*array_length 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            t = declare(int)                                    # time variable which we change during scan
            p = declare(fixed)                                  # fixed is similar to float 4bit.28bit

            n = declare(int)                                    # iteration variable
            n_st = declare_stream()                             # stream iteration number

            counts_tmp = declare(int)                           # temporary variable for number of counts
            counts_ref_tmp = declare(int)                       # temporary variable for number of counts reference

            runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)         # iteration variable
            tracking_signal_tmp = declare(int)                # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)                # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int,value=0)

            counts = declare(int, size=array_length)            # experiment signal (vector)
            counts_ref = declare(int, size=array_length)        # reference signal (vector)

            # Shuffle parameters
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()                            # experiment signal
            counts_ref_st = declare_stream()                        # reference signal

            # Set RF frequency to resonance
            update_frequency("RF",self.rf_resonance_freq*self.u.MHz)# updates RF frerquency
            p = self.rf_proportional_pwr                            # p should be between 0 to 1

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
                        play("cw", "MW", duration=tMW//4) 
                        # play RF after MW
                        align("MW","RF")
                        play("const" * amp(p), "RF", duration=t) # t already devide by four when creating the time vector
                        # play MW after RF
                        align("RF","MW")
                        play("cw", "MW", duration=tMW//4)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()


                        # reference
                        # play MW for time Tmw
                        play("cw", "MW", duration=tMW//4) 
                        # Don't play RF after MW just wait
                        wait(t) # t already devide by four
                        # play MW
                        play("cw", "MW", duration=tMW//4)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tMW = self.t_mw
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
        tSequencePeriod = (tMW+tLaser)*2*array_length 
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
                        play("cw", "MW", duration=tMW//4)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # don't play MW for time t
                        wait(tMW//4)
                        # play laser after MW
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
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
        tLaser = self.time_in_multiples_cycle_time(self.TcounterPulsed+self.Tsettle+tMeasueProcess)
        tMeasure = self.time_in_multiples_cycle_time(self.TcounterPulsed)
        
        # time scan vector
        tRabi_min = self.scan_t_start//4 if self.scan_t_start//4 > 0 else 1     # in [cycles]
        tRabi_max = self.scan_t_end//4 if self.scan_t_end//4 > 0 else 1         # in [cycles]
        dt = self.scan_t_dt // 4                                                # in [cycles]
        self.t_vec = [i*4 for i in range(tRabi_min, tRabi_max + 1, dt)]         # in [nsec], used to plot the graph
        self.t_vec_ini = np.arange(tRabi_min, tRabi_max + dt/10, dt)            # in [cycles]

        # indexes vector
        array_length = len(self.t_vec)
        idx_vec_ini = np.arange(0, array_length, 1)

        # tracking signal
        tSequencePeriod = (tRabi_max+tLaser)*2*array_length 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//self.time_in_multiples_cycle_time(self.Tcounter)
        trackingNumRepeatition = tGetTrackingSignalEveryTime//(tSequencePeriod) if tGetTrackingSignalEveryTime//(tSequencePeriod) > 1 else 1

        with program() as self.quaPGM:
            # QUA program parameters
            times = declare(int, size=100)
            times_ref = declare(int, size=100)

            t = declare(int)                                    # time variable which we change during scan

            n = declare(int)                                    # iteration variable
            n_st = declare_stream()                             # stream iteration number

            counts_tmp = declare(int)                           # temporary variable for number of counts
            counts_ref_tmp = declare(int)                       # temporary variable for number of counts reference

            runTracking = declare(bool,value=self.bEnableSignalIntensityCorrection)
            track_idx = declare(int, value=0)         # iteration variable
            tracking_signal_tmp = declare(int)                # temporary variable for number of counts reference
            tracking_signal = declare(int, value=0)                # temporary variable for number of counts reference
            tracking_signal_st = declare_stream()
            sequenceState = declare(int,value=0)

            counts = declare(int, size=array_length)            # experiment signal (vector)
            counts_ref = declare(int, size=array_length)        # reference signal (vector)

            # Shuffle parameters - time
            val_vec_qua = declare(int, value=np.array([int(i) for i in self.t_vec_ini]))    # time QUA vector
            idx_vec_qua = declare(int, value=idx_vec_ini)                                   # indexes QUA vector
            idx = declare(int)                                                              # index variable to sweep over all indexes

            # stream parameters
            counts_st = declare_stream()                            # experiment signal
            counts_ref_st = declare_stream()                        # reference signal
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
                with for_(idx, 0, idx < array_length, idx + 1): # range over Tmw
                    assign(sequenceState, IO1)
                    with if_(sequenceState == 0):
                        # set new random TmW
                        assign(t, val_vec_qua[idx_vec_qua[idx]])  # shuffle - assign new val from randon index

                        # play MW for time t
                        play("cw", "MW", duration=t)
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
                        align("MW","Detector_OPD")
                        measure("readout", "Detector_OPD", None,time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # don't play MW for time t
                        wait(t) 
                        # play laser after MW
                        align("MW","Laser")
                        play("Turn_ON", "Laser", duration=tLaser//4)
                        # play measure after MW
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
                    with for_(idx, 0, idx < array_length, idx + 1): # in shuffle all elements need to be saved later to send to the stream
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
        tLaser = self.time_in_multiples_cycle_time(self.Tcounter+self.Tsettle+tMeasueProcess)
        tMW = tLaser
        tMeasure = self.time_in_multiples_cycle_time(self.Tcounter)
        tSettle = self.time_in_multiples_cycle_time(self.Tsettle)
        
        # MW frequency scan vector
        f_min = 0 * self.u.MHz                              # [Hz], start of freq sweep
        f_max = self.mw_freq_scan_range * self.u.MHz        # [Hz] end of freq sweep
        df = self.mw_df * self.u.MHz                        # [Hz], freq step
        self.f_vec = np.arange(f_min, f_max + df/10, df)    # [Hz], frequencies vector

        # length and idx vector
        array_length = len(self.f_vec)                      # frquencies vector size
        idx_vec_ini = np.arange(0, array_length, 1)         # indexes vector

        # tracking signal
        tSequencePeriod = tLaser*2*array_length 
        tGetTrackingSignalEveryTime = int(self.tGetTrackingSignalEveryTime * 1e9) # [nsec]
        tTrackingSignaIntegrationTime = int(self.tTrackingSignaIntegrationTime * 1e6)
        tTrackingIntegrationCycles = tTrackingSignaIntegrationTime//tMeasure
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
                        wait(tSettle//4,"Detector_OPD")
                        measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure, counts_tmp))
                        assign(counts[idx_vec_qua[idx]], counts[idx_vec_qua[idx]] + counts_tmp)
                        align()

                        # reference sequence
                        # don't play MW
                        play("Turn_ON", "Laser", duration=tLaser // 4)
                        wait(tSettle//4,"Detector_OPD")
                        measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, counts_ref_tmp))
                        assign(counts_ref[idx_vec_qua[idx]], counts_ref[idx_vec_qua[idx]] + counts_ref_tmp)
                        align()
                    with else_():
                        assign(tracking_signal, 0)
                        with for_(idx, 0, idx < tTrackingIntegrationCycles, idx + 1):
                            play("Turn_ON", "Laser", duration=tLaser // 4)
                            measure("min_readout", "Detector_OPD", None, time_tagging.digital(times_ref, tMeasure, tracking_signal_tmp))
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
    def TrackingCounterSignal_QUA_PGM(self): # obsolete. keep in order to learn on how to swithc between two PGM
        # integration time for single loop
        tTrackingSignaIntegrationTime_nsec = self.tTrackingSignaIntegrationTime*1e6
        tMeasure = self.time_in_multiples_cycle_time(50000 if tTrackingSignaIntegrationTime_nsec>50000 else tTrackingSignaIntegrationTime_nsec) # 50000 [nsec]
        # number of repeatitions
        n_count = tTrackingSignaIntegrationTime_nsec//tMeasure if tTrackingSignaIntegrationTime_nsec//tMeasure>1 else 1
        # total integration time
        self.tTrackingSignaIntegrationTime = n_count * tMeasure/1e6 #[msec]

        with program() as self.quaTrackingPGM:
            times = declare(int, size=100)
            n = declare(int)  
            counts_tracking = declare(int)
            total_counts_tracking = declare(int,value=0) 
            counts_tracking_st = declare_stream()  # stream for counts
            
            pause()
            with infinite_loop_():
                assign(total_counts_tracking,0)
                with for_(n, 0, n < n_count, n + 1):  # number of averages / total integation time
                    play("Turn_ON", "Laser", duration=tMeasure//4)
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(times, tMeasure), counts_tracking)
                    assign(total_counts_tracking,total_counts_tracking+counts_tracking)

                save(total_counts_tracking, counts_tracking_st)

            with stream_processing():
                counts_tracking_st.save("counts_tracking")

        self.qmTracking, self.job_Tracking = self.QUA_execute(closeQM=False,quaPGM=self.quaTrackingPGM)    

    def counter_QUA_PGM(self, n_count=1):
        with program() as self.quaPGM:
            self.times = declare(int, size=1000)
            self.times_ref = declare(int, size=1000)
            self.counts = declare(int)  # apd1
            self.total_counts = declare(int,value=0)  # apd1
            self.n = declare(int)  #
            self.counts_st = declare_stream()
            self.counts_ref_st = declare_stream()  # stream for counts
            self.n_st = declare_stream()  # stream for number of iterations

            with infinite_loop_():
                with for_(self.n, 0, self.n < n_count, self.n + 1):  # number of averages / total integation time
                    play("Turn_ON", "Laser", duration=int(self.Tcounter * self.u.ns // 4))  #
                    # measure("readout", "Detector_OPD", None, time_tagging.digital(self.times, int(self.Tcounter * self.u.us), self.counts))
                    measure("readout", "Detector_OPD", None,
                           time_tagging.digital(self.times, int(self.Tcounter * self.u.ns),
                                                self.counts))
                    
                    assign(self.total_counts, self.total_counts + self.counts)  # assign is equal in qua language
                    # align()

                save(self.total_counts, self.counts_st)
                # save(self.total_counts, self.counts_ref_st) # only to keep on convention
                assign(self.total_counts, 0)
                save(self.n, self.n_st)  # save number of iteration inside for_loop

            with stream_processing():
                self.counts_st.with_timestamps().save("counts")
                self.counts_st.with_timestamps().save("counts_reg")
                self.n_st.save("iteration")

        self.qm, self.job = self.QUA_execute()
    def MeasureByTrigger_QUA_PGM(self, num_bins_per_measurement: int = 1, num_measurement_per_array: int = 1):
        # MeasureByTrigger_QUA_PGM function measures counts.
        # It will run a single measurement every trigger.
        # each measurement will be append to buffer.
        laser_on_duration = int(self.Tcounter * self.u.ns // 4)
        single_integration_time = int(self.Tcounter * self.u.ns)
        smaract_ttl_duration = int(self.smaract_ttl_duration * self.u.ms // 4)

        with program() as self.quaPGM:
            times = declare(int, size=1000) #maximum number of counts allowed per measurements
            counts = declare(int)  # apd1
            total_counts = declare(int,value=0)  # apd1
            n = declare(int)  #
            meas_idx = declare(int,value=0)
            counts_st = declare_stream()
            meas_idx_st = declare_stream()

            pulsesTriggerDelay = 5000000//4

            with infinite_loop_():
                wait_for_trigger("Laser") # wait for smaract trigger
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
                wait(pulsesTriggerDelay,"SmaractTrigger")
                play("Turn_ON", "SmaractTrigger", duration=smaract_ttl_duration)
                align()
                assign(meas_idx, meas_idx + 1)
                save(meas_idx, meas_idx_st)

            with stream_processing():
                meas_idx_st.save("meas_idx_scanLine")
                counts_st.buffer(num_measurement_per_array).save("counts_scanLine")

        self.qm, self.job = self.QUA_execute()
    def counter_array_QUA_PGM(self, num_bins_per_measurement: int = 1, num_measurement_per_array: int = 1):
        # Calculate values outside the FPGA to save FPGA compute time
        laser_on_duration = int(self.Tcounter * self.u.ns // 4)
        single_integration_time = int(self.Tcounter * self.u.ns)
        smaract_ttl_duration = int(self.smaract_ttl_duration * self.u.ms // 4)

        with program() as self.quaPGM:
            times = declare(int, size=1000)#num_measurement_per_array)
            counts = declare(int)  # apd1
            total_counts = declare(int,value=0)  # apd1
            n = declare(int)  #
            x_loop_counter = declare(int)
            counts_st = declare_stream()

            with infinite_loop_():
                pause()
                with for_ (x_loop_counter, 0, x_loop_counter<num_measurement_per_array, x_loop_counter + 1):
                    play("Turn_ON", "SmaractTrigger", duration=smaract_ttl_duration)
                    wait_for_trigger("Laser") # wait for smaract trigger
                    align("Laser","Detector_OPD","SmaractTrigger")
                    # wait(int(15 * self.u.ms //4))
                    with for_(n, 0, n < num_bins_per_measurement, n + 1):
                        play("Turn_ON", "Laser", duration=laser_on_duration)
                        measure("readout", "Detector_OPD", None, time_tagging.digital(times, single_integration_time, counts))
                        assign(total_counts, total_counts + counts)
                        # align()
                    save(total_counts, counts_st)
                    assign(total_counts, 0)
                # play("Turn_ON", "SmaractTrigger", duration=smaract_ttl_duration)
                # align()
                # wait(int(15 * self.u.ms //4), "SmaractTrigger")
                # play("Turn_ON", "SmaractTrigger", duration=smaract_ttl_duration)

            with stream_processing():
                counts_st.buffer(num_measurement_per_array).save("counts_fastscan")

        # set,open and execute the program
        self.qm = self.qmm.open_qm(self.quaCFG)
        self.job = self.qm.execute(self.quaPGM)
    
    def Common_updateGraph(self,_xLabel = "?? [??],",_yLabel = "I [kCounts/sec]"):
        # todo: use this function as general update graph for all experiments
        dpg.set_item_label("graphXY",f"{self.exp.name}, iteration = {self.iteration}, tracking_ref = {self.tracking_ref: .1f}, ref Threshold = {self.refSignal},shuffle = {self.bEnableShuffle}, Tracking = {self.bEnableSignalIntensityCorrection}")
        dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
        dpg.set_value("series_counts_ref", [self.X_vec, self.Y_vec_ref])
        dpg.set_item_label("y_axis", _yLabel)
        dpg.set_item_label("x_axis", _xLabel)
        dpg.fit_axis_data('x_axis')
        dpg.fit_axis_data('y_axis')
    
    def FastScan_updateGraph(self):
        # Update the graph label with the current experiment name, iteration, and last Y value
        dpg.set_item_label("graphXY",
                           f"{self.exp.name}, iteration = {self.iteration}, lastVal = {round(self.Y_vec[-1], 0)}")

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
        if self.bEnableSignalIntensityCorrection: # prepare search maxI thread
            self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)

        # verify job has started
        while not self.job._is_job_running:
            time.sleep(0.1)
        time.sleep(0.1)

        # fetch right parameters
        if self.exp == Experimet.COUNTER:
            self.results = fetching_tool(self.job, data_list=["counts", "iteration"], mode="live")
        else:
            self.results = fetching_tool(self.job, data_list=["counts", "counts_ref", "iteration","tracking_ref"], mode="live")

        self.X_vec = []
        self.Y_vec = []
        self.Y_vec_ref = []
        self.iteration = 0
        self.counter = -10

        dpg.bind_item_theme("series_counts", "LineYellowTheme")
        dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")

        
        lastTime = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6
        while self.results.is_processing():
            self.GlobalFetchData()

            if self.exp == Experimet.COUNTER:
                dpg.set_item_label("graphXY",
                           f"{self.exp.name}, iteration = {self.iteration}, lastVal = {round(self.Y_vec[-1], 0)}")
                dpg.set_value("series_counts", [self.X_vec, self.Y_vec])
                dpg.set_value("series_counts_ref", [[], []])
                dpg.set_item_label("y_axis", "I [kCounts/sec]")
                dpg.set_item_label("x_axis", "time [sec]")
                dpg.fit_axis_data('x_axis')
                dpg.fit_axis_data('y_axis')

                dpg.bind_item_theme("series_counts", "LineYellowTheme")
                dpg.bind_item_theme("series_counts_ref", "LineMagentaTheme")
                # self.Counter_updateGraph()
            if self.exp == Experimet.ODMR_CW:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experimet.RABI:  # time
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experimet.PULSED_ODMR:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experimet.NUCLEAR_RABI:  #time
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [nsec]")
            if self.exp == Experimet.NUCLEAR_MR:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [MHz]")
            if self.exp == Experimet.NUCLEAR_POL_ESR:  #freq
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="freq [GHz]")
            if self.exp == Experimet.Nuclear_spin_lifetimeS0:  
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experimet.Nuclear_spin_lifetimeS1:  
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experimet.Nuclear_Ramsay:  
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experimet.Hahn:  
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experimet.Electron_lifetime:  
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            if self.exp == Experimet.Electron_Coherence:
                self.SearchPeakIntensity()
                self.Common_updateGraph(_xLabel="time [msec]")
            
            current_time = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6
            if not(self.exp == Experimet.COUNTER) and (current_time-lastTime)>self.tGetTrackingSignalEveryTime:
                self.btnSave(folder= "d:/temp/")
                lastTime = datetime.now().hour*3600+datetime.now().minute*60+datetime.now().second+datetime.now().microsecond/1e6

            if self.StopFetch:
                break
        
        1
    def GlobalFetchData(self):
        if self.exp == Experimet.COUNTER:
            self.lock.acquire()
            self.counter_Signal, self.iteration = self.results.fetch_all()
            self.lock.release()
        else:
            self.lock.acquire()
            self.signal, self.ref_signal, self.iteration, self.tracking_ref_signal = self.results.fetch_all()  # grab/fetch new data from stream
            self.lock.release()

        if self.exp == Experimet.COUNTER:
            if len(self.X_vec) > self.NumOfPoints:
                self.Y_vec = self.Y_vec[-self.NumOfPoints:]  # get last NumOfPoint elements from end
                self.X_vec = self.X_vec[-self.NumOfPoints:]

            self.Y_vec.append(
                self.counter_Signal[0] / int(self.total_integration_time * self.u.ms) * 1e9 / 1e3)  # counts/second
            self.X_vec.append(self.counter_Signal[1] / self.u.s)  # Convert timestamps to seconds

        if self.exp == Experimet.ODMR_CW:  #freq
            self.X_vec = self.f_vec / self.u.MHz / 1e3 + self.mw_freq  #[GHz]
            self.Y_vec = self.signal / 1000 / (self.Tcounter * 1e-9)  
            self.Y_vec_ref = self.ref_signal / 1000 / (self.Tcounter * 1e-9)
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.RABI:  # time
            self.X_vec = self.t_vec  # [nsec]]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.PULSED_ODMR:  #freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.NUCLEAR_RABI:  #time
            self.X_vec = self.t_vec  # [nsec]]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.NUCLEAR_MR:  #freq
            self.X_vec = self.f_vec / float(1e6)  # [MHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.NUCLEAR_POL_ESR:  #freq
            self.X_vec = self.f_vec / float(1e9) + self.mw_freq  # [GHz]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        
        if self.exp == Experimet.Nuclear_spin_lifetimeS0:  #time
            self.X_vec = [e/1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        
        if self.exp == Experimet.Nuclear_spin_lifetimeS1:  #time
            self.X_vec = [e/1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        
        if self.exp == Experimet.Nuclear_Ramsay or self.exp == Experimet.Electron_Coherence:  #time
            self.X_vec = [e/1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)
        
        if self.exp == Experimet.Hahn:  #time
            self.X_vec = [e/1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

        if self.exp == Experimet.Electron_lifetime: # time
            self.X_vec = [e/1e6 for e in self.t_vec]  # [msec]
            self.Y_vec = self.signal / (self.TcounterPulsed * 1e-9) / 1e3  
            self.Y_vec_ref = self.ref_signal / (self.TcounterPulsed * 1e-9) / 1e3
            self.tracking_ref = self.tracking_ref_signal / 1000 / (self.tTrackingSignaIntegrationTime * 1e6 * 1e-9)

    def StartFetch(self, _target):
        self.to_xml()  # write class parameters to XML
        self.timeStamp = self.getCurrentTimeStamp()

        self.StopFetch = False
        self.fetchTh = threading.Thread(target=_target)
        self.fetchTh.start()

    def btnStartCounterLive(self, b_startFetch=True):
        self.exp = Experimet.COUNTER
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)
        # TODO: Boaz - Check for edge cases in number of measurements per array
        self.initQUA_gen(
            n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
            num_measurement_per_array=int(self.L_scan[0] / self.dL_scan[0]) if self.dL_scan[0] != 0 else 1)

        if b_startFetch and not self.bEnableSimulate:
            self.StartFetch(_target=self.FetchData)
    def btnStartODMR_CW(self):
        self.exp = Experimet.ODMR_CW
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
        self.exp = Experimet.RABI
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
    def btnStartPulsedODMR(self):
        self.exp = Experimet.PULSED_ODMR
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
        self.exp = Experimet.NUCLEAR_RABI
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
    def btnStartNuclearPolESR(self):
        self.exp = Experimet.NUCLEAR_POL_ESR
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
        self.exp = Experimet.NUCLEAR_MR
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
        self.exp = Experimet.Nuclear_spin_lifetimeS0
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
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
        self.exp = Experimet.Nuclear_spin_lifetimeS1
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
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
        self.exp = Experimet.Nuclear_Ramsay
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
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
        self.exp = Experimet.Electron_Coherence
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
        self.exp = Experimet.Hahn
        self.GUI_ParametersControl(isStart=self.bEnableSimulate)

        self.mw_freq = min(self.mw_freq_resonance,self.mw_2ndfreq_resonance)-0.001 # [GHz]
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
        self.exp = Experimet.Electron_lifetime
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

    def StopJob(self,job,qm):
        job.halt()
        report = job.execution_report()
        print(report)
        qm.close()
        return report
    def btnStop(self):  # Stop Exp
        #todo: creat methode that handle OPX close job and instances
        self.stopScan = True
        self.StopFetch = True
        if not self.exp == Experimet.FAST_SCAN and not self.exp == Experimet.SCAN:
            if self.bEnableSignalIntensityCorrection:
                if self.MAxSignalTh.is_alive():
                    self.MAxSignalTh.join()
        else:
            dpg.set_item_label("btnOPX_StartScan", "Start Scan")
            dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme") 

        self.GUI_ParametersControl(True)
        if not self.exp == Experimet.FAST_SCAN and not self.exp == Experimet.SCAN:
            if (self.fetchTh.is_alive()):
                self.fetchTh.join()
        
        if (self.job):
            self.StopJob(self.job,self.qm)

        if self.exp == Experimet.COUNTER or self.exp == Experimet.SCAN:
            pass
        else:
            self.mwModule.Get_RF_state()
            if self.mwModule.RFstate:
                self.mwModule.Turn_RF_OFF()

        if self.exp not in [Experimet.COUNTER, Experimet.FAST_SCAN , Experimet.SCAN]:
            self.btnSave()
    def btnSave(self, folder=None):  # save data
        try:

            # file name
            # timeStamp = self.getCurrentTimeStamp()  # get current time stamp
            if folder == None:
                folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + '/'
            else:
                folder_path = folder + self.exp.name + '/'
            if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
                os.makedirs(folder_path)
            fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)

            # parameters + note        
            self.writeParametersToXML(fileName + ".xml")

            # raw data
            RawData_to_save = {
                'X': self.X_vec,
                'Y': self.Y_vec,
                'Y_ref': self.Y_vec_ref
            }

            self.saveToCSV(fileName + ".csv", RawData_to_save)

            # save data as image (using matplotlib)
            if folder == None:
                width = 1920  # Set the width of the image
                height = 1080  # Set the height of the image
                # Create a blank figure with the specified width and height, Convert width and height to inches
                fig, ax = plt.subplots(figsize=(width / 100, height / 100),
                                    visible=True)
                plt.plot(self.X_vec, self.Y_vec, label='data')  # Plot Y_vec
                plt.plot(self.X_vec, self.Y_vec_ref, label='ref')  # Plot reference

                # Adjust axes limits (optional)
                # ax.set_xlim(0, 10)
                # ax.set_ylim(-1, 1)

                # Add legend
                plt.legend()

                # Save the figure as a PNG file
                plt.savefig(fileName + '.png', format='png', dpi=300, bbox_inches='tight')

                #close figure
                plt.close(fig)

            dpg.set_value("inTxtOPX_expText", "data saved to: " + fileName + ".csv")


        except Exception as ex:
            self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))
            # raise
    def btnStartScan(self):
        self.ScanTh = threading.Thread(target=self.StartScan)
        self.ScanTh.start()
    def btnFindPeak(self):
        self.ScanTh = threading.Thread(target=self.FindPeak)
        self.ScanTh.start()
    def FindPeak(self): # finds peak count
        if self.stopScan == False:
            self.stopScan = True
            dpg.set_item_label("btnOPX_FindPeak", "Find Peak")
            dpg.bind_item_theme(item = "btnOPX_FindPeak", theme = "btnYellowTheme")
            return
        print(chr(27) + "[2J") # Clear terminal
        isDebug=True
        CurrentCount=float(0)
        PreviousCount=float(0)
        Diff=float(0)
        Increment=0
        Step=100
        Switch_Counter=0
        self.stopScan = False
        # convert Find Peak to Stop Search
        dpg.set_item_label("btnOPX_FindPeak", "Stop Search")
        dpg.bind_item_theme(item="btnOPX_FindPeak", theme="btnRedTheme")
         # prepare counter fetch data
        self.btnStartCounterLive(b_startFetch=False)
        time.sleep(2)
        self.results = fetching_tool(self.job, data_list=["counts","iteration"], mode="live")
         # get current (initial) position
        for ch in range(3):
            res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = list(self.positioner.AxesPosUnits)  # includes offset
        self.initial_scan_Location = list(self.positioner.AxesPositions)  # includes offset
        for ch in range(3):
            if isDebug:
                print(f"ch{ch}: in position = {res}, position = {self.initial_scan_Location[ch]} {self.positioner.AxesPosUnits[ch]}")
        self.expected_pos = [0, 0, 0]
        for ch in range(3):
            Switch_Counter=0
            Step=100
            # ch=0
            self.scan_Log_measurement()
            CurrentCount1 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount2 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount3 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount4 = self.scan_Out[-1][3]
            PreviousCount = CurrentCount1/4 + CurrentCount2/4 + CurrentCount3/4 + CurrentCount4/4

            self.positioner.MoveRelative(ch,100000)

            self.scan_Log_measurement()
            CurrentCount1 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount2 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount3 = self.scan_Out[-1][3]
            time.sleep(.2)
            self.scan_Log_measurement()
            CurrentCount4 = self.scan_Out[-1][3]
            CurrentCount = CurrentCount1/4 + CurrentCount2/4 + CurrentCount3/4 + CurrentCount4/4

            while Switch_Counter<5:
                if self.stopScan:
                    dpg.set_item_label("btnOPX_FindPeak", "Find Peak")
                    dpg.bind_item_theme(item = "btnOPX_FindPeak", theme = "btnYellowTheme")
                    return
                Diff = (CurrentCount-PreviousCount)/CurrentCount*100
                if Switch_Counter==0:
                    Increment = int(10000*Step)
                    print(str(Increment)+",ch"+str(ch))
                    Step=Step*0.7
                    Switch_Counter=1
                elif Diff<0:
                    Step=-Step*0.9
                    Switch_Counter=0
                    print(str(Switch_Counter)+",ch"+str(ch)+","+str(Step))
                    if abs(Step)<10:
                        Switch_Counter=5


                self.positioner.MoveRelative(ch,Increment)
                PreviousCount = CurrentCount
                time.sleep(.5)

                self.scan_Log_measurement()
                CurrentCount1 = self.scan_Out[-1][3]
                time.sleep(.2)
                self.scan_Log_measurement()
                CurrentCount2 = self.scan_Out[-1][3]
                time.sleep(.2)
                self.scan_Log_measurement()
                CurrentCount3 = self.scan_Out[-1][3]
                time.sleep(.2)
                self.scan_Log_measurement()
                CurrentCount4 = self.scan_Out[-1][3]
                CurrentCount = CurrentCount1/4 + CurrentCount2/4 + CurrentCount3/4 + CurrentCount4/4


        self.stopScan = True
        dpg.set_item_label("btnOPX_FindPeak", "Find Peak")
        dpg.bind_item_theme(item = "btnOPX_FindPeak", theme = "btnYellowTheme")
    def StartScan(self):
        self.positioner.KeyboardEnabled = False # TODO: Update the check box in the gui!!
        if not self.fast_scan_enabled:
            self.StartScan3D()
        else:
            self.StartFastScan()
        self.positioner.KeyboardEnabled = True

    def StartScan3D(self):  # currently flurascence scan
        print("start scan steps")
        start_time = time.time()
        print(f"start_time: {self.format_time(start_time)}")

        #init
        self.exp = Experimet.SCAN
        self.GUI_ParametersControl(isStart=False)
        self.to_xml()  # save last params to xml
        self.writeParametersToXML(self.create_scan_file_name(local=True) + ".xml") # moved near end of scan
               
        try:
            # Define the source files and destinations
            file_mappings = [
                {
                    "src": 'Q:/QT-Quantum_Optic_Lab/expData/Images/Zelux_Last_Image.png',
                    "dest_local": self.create_scan_file_name(local=True) + "_ZELUX.png",
                    "dest_remote": self.create_scan_file_name(local=False) + "_ZELUX.png"
                },
                {
                    "src": 'D:/HotSysSW/map_config.txt',
                    "dest_local": self.create_scan_file_name(local=True) + "_map_config.txt",
                    "dest_remote": self.create_scan_file_name(local=False) + "_map_config.txt"
                }
            ]
            
            # Move each file for both local and remote
            for file_map in file_mappings:
                for dest in [file_map["dest_local"], file_map["dest_remote"]]:
                    if os.path.exists(file_map["src"]):
                        shutil.move(file_map["src"], dest)
                        print(f"File moved to {dest}")
                    else:
                        print(f"Source file {file_map['src']} does not exist.")

        except Exception as e:
            print(f"Error occurred: {e}")

        self.stopScan = False
        isDebug = True
        self.scan_Out = []
        self.scan_intensities = []

        # reset stage motion parameters (stream, motion delays, mav velocity)
        self.positioner.set_in_position_delay(0,delay=0) # reset delays yo minimal 
        self.positioner.DisablePositionTrigger(0) # disable triggers
        self.positioner.SetVelocity(0,0) # set max velocity (ch 0)
        self.positioner.setIOmoduleEnable(dev=0) 
        self.positioner.set_Channel_Constant_Mode_State(channel=0)
        
        # GUI - convert Start Scan to Stop scan
        dpg.set_item_label("btnOPX_StartScan", "Stop Scan")
        dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnRedTheme")

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
        for ch in range(3): # verify in postion
            res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = list(self.positioner.AxesPosUnits)
        self.initial_scan_Location = list(self.positioner.AxesPositions)
        for ch in range(3):
            if isDebug:
                print(f"ch{ch}: in position = {res}, position = {self.initial_scan_Location[ch]} {self.positioner.AxesPosUnits[ch]}")

        # goto scan start location
        for ch in range(3):
            V_scan = []
            if self.b_Scan[ch]:
                self.ini_scan_pos[ch] = self.initial_scan_Location[ch] - self.L_scan[ch] * 1e3 / 2  # [pm]
                self.positioner.MoveABSOLUTE(ch, int(self.ini_scan_pos[ch]))  # move absolute to start location
                N[ch] = (int(self.L_scan[ch] / self.dL_scan[ch]))
                for i in range(N[ch]):
                    V_scan.append(i * self.dL_scan[ch] * 1e3 + self.ini_scan_pos[ch])

                time.sleep(t_wait_motionStart)  # allow motion to start
                res = self.readInpos(ch)  # wait motion ends
                if isDebug:
                    print(f"ch{ch} at initial scan position")

            else:
                self.ini_scan_pos[ch] = self.initial_scan_Location[ch]
                V_scan.append(self.initial_scan_Location[ch])

            self.V_scan.append(V_scan)
        self.positioner.GetPosition()
        if isDebug:
            for i in range(3):
                print(f"ch[{i}] Pos = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        Nx = len(self.V_scan[0])
        Ny = len(self.V_scan[1])
        Nz = len(self.V_scan[2])
        self.scan_intensities = np.zeros((Nx, Ny, Nz))
        self.scan_data = self.scan_intensities
        self.idx_scan = [0, 0, 0]

        self.startLoc = [self.V_scan[0][0]/1e6, self.V_scan[1][0]/1e6, self.V_scan[2][0]/1e6]
        self.endLoc = [self.V_scan[0][-1]/1e6,self.V_scan[1][-1]/1e6,self.V_scan[2][-1]/1e6]
        
        self.Plot_Scan(Nx = Nx, Ny = Ny, array_2d=self.scan_intensities[:,:,0], startLoc = self.startLoc, endLoc = self.endLoc)

        # Start Qua PGM
        self.initQUA_gen(
                    n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                    num_measurement_per_array=Nx)
        res_handles = self.job.result_handles
        self.counts_handle = res_handles.get("counts_scanLine")
        self.meas_idx_handle = res_handles.get("meas_idx_scanLine")
        
        # offset in X start point from 
        x_channel = 0
        scanPx_Start = int(list(self.V_scan[0])[0]-self.dL_scan[x_channel]*1e3)
        self.positioner.MoveABSOLUTE(channel= x_channel, newPosition=scanPx_Start) 
        time.sleep(0.005)  # allow motion to start
        for q in range(3):
            self.readInpos(q)  # wait motion ends

        self.dir = 1
        self.scanFN = self.create_scan_file_name(local = True)

        # init measurements index
        previousMeas_idx = 0 # used as workaround to reapet line if an error occur in number of measurements
        meas_idx = 0

        # Calculate the z calibration offset at the origin of the scan
        if self.b_Zcorrection and not self.ZCalibrationData is None:
            z_calibration_offset = int(calculate_z_series(self.ZCalibrationData,
                                                          np.array([self.initial_scan_Location[0]]),
                                                          self.initial_scan_Location[1])[0])
        z_correction_previous = 0
        for i in range(N[2]):  # Z
            if self.stopScan:
                break
            self.positioner.MoveABSOLUTE(2, int(self.V_scan[2][i]))

            j = 0
            # for j in range(N[1]):  # Y
            while j < N[1]:  # Y
                if self.stopScan:
                    break
                self.positioner.MoveABSOLUTE(1, int(self.V_scan[1][j]))
                self.dir = self.dir * -1  # change direction to create S shape scan
                V = []

                for k in range(N[0]):
                    if self.stopScan:
                        break

                    if k == 0:
                        V = list(self.V_scan[0])
                    
                    #Z correction
                    new_z_pos = int(self.V_scan[2][i])
                    if self.b_Zcorrection and not self.ZCalibrationData is None:
                        z_correction_new = int(calculate_z_series(self.ZCalibrationData,
                                               np.array([int(V[k])]),
                                               int(self.V_scan[1][j]))[0] - z_calibration_offset)
                        if abs(z_correction_new - z_correction_previous) > self.z_correction_threshold:
                            new_z_pos = int(self.V_scan[2][i] + z_correction_new)
                            z_correction_previous = z_correction_new
                            self.positioner.MoveABSOLUTE(2, new_z_pos)
                        else:
                            new_z_pos = new_z_pos + z_correction_previous

                    # move to next X - when trigger the OPX will measure and append the results
                    self.positioner.MoveABSOLUTE(0, int(V[k]))
                    time.sleep(5e-3)
                    for q in range(3):
                        self.readInpos(q)  # wait motion ends
                    self.positioner.generatePulse(channel=0) # should triggere measurement
                    # self.positioner.generatePulse(channel=0) # should triggere measurement
                    time.sleep(self.total_integration_time*1e-3 + 1e-3) # wait for measurement do occur

                    elapsed_time = time.time() - start_time
                    estimated_time_left = self.estimatedScanTime*60 - elapsed_time
                    dpg.set_value("Scan_Message",f"time left: {self.format_time(estimated_time_left)}")

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
                    self.scan_intensities[:,j,i] = counts / self.total_integration_time # counts/ms = Kcounts/s
                    self.UpdateGuiDuringScan(self.scan_intensities[:, :, i],use_fast_rgb=True)

                if (meas_idx-previousMeas_idx)%counts.size ==0: # if no skips in measurements
                    j = j+1
                    self.prepare_scan_data(self.endLoc[0]*1e6+self.dL_scan[0]*1e3,self.startLoc[0]*1e6)
                    self.save_scan_data(Nx = Nx, Ny = Ny, Nz = Nz ,fileName=self.scanFN)
                else:
                    print("****** error: ******\nNumber of measurements is not consistent with excpected.\nthis line will be repeated.")
                    pass
                
                previousMeas_idx = meas_idx

                # offset in X start point from 
                self.positioner.MoveABSOLUTE(channel= x_channel, newPosition=scanPx_Start) 
                time.sleep(0.005)  # allow motion to start
                for q in range(3):
                    self.readInpos(q)  # wait motion ends

        # back to start position
        for i in range(3):
            self.positioner.MoveABSOLUTE(i, self.initial_scan_Location[i])
            res = self.readInpos(i)
            self.positioner.GetPosition()
            print(
                f"ch{i}: in position = {res}, position = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        fn = self.save_scan_data(Nx, Ny, Nz,self.create_scan_file_name(local=False)) # 333
        self.writeParametersToXML(fn + ".xml")

        if not(self.stopScan):
            self.btnStop()
        # else:
        # self.stopScan = True
        
        end_time = time.time()
        print(f"end_time: {end_time}")
        elapsed_time = end_time - start_time
        print(f"number of points ={N[0] * N[1] * N[2]}")
        print(f"Elapsed time: {elapsed_time} seconds")

    def StartFastScan(self):  # currently flurascence scan
        # todo: verify all axes are in closed loop

        if self.stopScan == False:
            self.stopScan = True
            # self.btnStop()
            return

        #init
        # self.logger = create_logger(f"{self.create_scan_file_name()}_log.txt")
        self.positioner.SetVelocity(0,0)
        self.positioner.DisablePositionTrigger(0)
        self.positioner.set_in_position_delay(0,delay=0)
        # self.positioner.stream_manager.close_stream()
        triggerMode = ctl.StreamTriggerMode.EXTERNAL
        t_wait_motionStart = 5e-3
        self.to_xml()  # save last params to xml
        self.stopScan = False
        isDebug = True
        self.scan_Out = []
        self.scan_intensities = []
        self.scanFN = self.create_scan_file_name(local = True)

        # convert Start Scan to Stop scan
        dpg.set_item_label("btnOPX_StartScan", "Stop Scan")
        dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnRedTheme")

        self.exp = Experimet.FAST_SCAN
        self.GUI_ParametersControl(isStart=False)

        self.Xv = [0]
        self.Yv = [0]
        self.Zv = [0]
        self.Y_vec_ref = []
        self.initial_scan_Location = []
        self.V_scan = []

        x_channel = 0
        y_channel = 1
        z_channel = 2
        motion_buffer = 10000  # pm

        Nx = int(self.L_scan[x_channel] / self.dL_scan[x_channel]) if (self.dL_scan[x_channel] > 0 and self.b_Scan[x_channel]) else 1
        Ny = int(self.L_scan[y_channel] / self.dL_scan[y_channel]) if (self.dL_scan[y_channel] > 0 and self.b_Scan[y_channel]) else 1
        Nz = int(self.L_scan[z_channel] / self.dL_scan[z_channel]) if (self.dL_scan[z_channel] > 0 and self.b_Scan[z_channel]) else 1

        # get current (initial) position
        for ch in range(3):
            res = self.readInpos(ch)
        self.positioner.GetPosition()
        self.absPosunits = list(self.positioner.AxesPosUnits)  # includes offset
        self.initial_scan_Location = list(self.positioner.AxesPositions)  # includes offset
        for ch in range(3):
            if isDebug:
                print(f"ch{ch}: in position = {res}, position = {self.initial_scan_Location[ch]} {self.positioner.AxesPosUnits[ch]}")

        # goto scan start location
        for ch in range(3):
            if self.b_Scan[ch]:
                self.ini_scan_pos[ch] = self.initial_scan_Location[ch] - self.L_scan[ch] * 1e3 / 2  # [pm]
                self.positioner.MoveABSOLUTE(ch, int(self.ini_scan_pos[ch]))  # move absolute to start location
                time.sleep(t_wait_motionStart)  # allow motion to start
                res = self.readInpos(ch)  # wait motion ends
                if isDebug:
                    print(f"ch{ch} at initial scan position")  
            else:
                self.ini_scan_pos[ch] = self.initial_scan_Location[ch]

        self.positioner.GetPosition()

        if isDebug:
            for i in range(3):
                print(f"ch[{i}] Pos = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        min_position_x_scan = self.ini_scan_pos[x_channel]
        max_position_x_scan = self.ini_scan_pos[x_channel] + self.L_scan[x_channel] * 1e3

        x_vec = np.linspace(min_position_x_scan,max_position_x_scan,Nx,endpoint=False)
        y_vec = np.linspace(self.ini_scan_pos[y_channel],self.ini_scan_pos[y_channel] + self.L_scan[y_channel]*1e3,Ny,endpoint=False)
        z_vec = np.linspace(self.ini_scan_pos[z_channel],self.ini_scan_pos[z_channel] + self.L_scan[z_channel]*1e3,Nz,endpoint=False)
        motion_stream_points = [(x_channel, int(x)) for x in x_vec]
        # x_motion_stream_points += [(x_channel, int(max_position_x_scan + motion_buffer))] + [(x_channel, int(min_position_x_scan - motion_buffer))]


        self.scan_intensities = np.zeros((Nx, Ny, Nz))
        self.scan_data = self.scan_intensities
        self.idx_scan = [0, 0, 0]

        self.startLoc = [self.ini_scan_pos[0]/1e6, self.ini_scan_pos[1]/1e6, self.ini_scan_pos[2]/1e6]
        self.endLoc = [self.startLoc[0]+self.dL_scan[0]*(Nx-1)/1e3,self.startLoc[1]+self.dL_scan[1]*(Ny-1)/1e3,self.startLoc[2]+self.dL_scan[2]*(Nz-1)/1e3]

        # self.Plot_Scan() #000
        self.Plot_Scan(Nx = Nx, Ny = Ny, array_2d=self.scan_intensities[:,:,0], startLoc = self.startLoc, endLoc = self.endLoc)
        #tic
        if isDebug:
            print("start scan steps")
        start_time = time.time()
        if isDebug:
            print(f"start_time: {self.format_time(start_time)}")

        self.positioner.MoveABSOLUTE(x_channel, int(min_position_x_scan - motion_buffer))
        time.sleep(t_wait_motionStart)
        for ch in range(3):
            res = self.readInpos(ch)

        self.positioner.SetPositionTrigger(x_channel,
                                            min_position_x_scan-1000,
                                            max_position_x_scan-self.dL_scan[x_channel]*1e3-1000,
                                            self.dL_scan[x_channel]*1e3,
                                            1,  # Trigger on increasing values
                                            50000,  # pulse width in ns
                                            min_position_x_scan-1000,
                                            True)

        self.positioner.set_in_position_delay(x_channel,delay=0) # todo:  tried both 0,2 and 10 however no effect on total scan time. why?
        self.positioner.set_in_position_delay(z_channel,delay=0) # todo:  tried both 0,2 and 10 however no effect on total scan time. why?
        # [nm/ms] = 1e6 [pm/s]
        # scanning_velocity = self.dL_scan[x_channel] / (self.total_integration_time + self.smaract_ttl_duration) * 0.2 * 1e6
        # self.positioner.SetVelocity(x_channel, scanning_velocity)

        self.qmm.clear_all_job_results()
        self.initQUA_gen(
                    n_count=int(self.total_integration_time * self.u.ms / self.Tcounter / self.u.ns),
                    num_measurement_per_array=Nx)
        res_handles = self.job.result_handles
        counts_handle = res_handles.get("counts_fastscan")
        # self.logger.stdin.write(f"Starting scan\n".encode())
        z_calibration_offset = int(calculate_z_series(self.ZCalibrationData,
                                                          np.array([self.initial_scan_Location[0]]),
                                                          self.initial_scan_Location[1])[0])
        
        
        stream_config_points = [(x_channel,1,z_channel,1)] if self.b_Zcorrection and not self.ZCalibrationData is None else [(x_channel,1)]
        self.positioner.confingure_stream_params(points = stream_config_points, pulse_width=50000, verbose=True)

        for i in range(Nz):  # Z
            if self.stopScan:
                # self.logger.stdin.write(f"Scan stopped by user at z index {i}".encode())
                break

            # self.logger.stdin.write(f"Moving to Z position {z_vec[i]}\n".encode())
            self.positioner.MoveABSOLUTE(2, int(z_vec[i]))
            time.sleep(t_wait_motionStart)
            self.readInpos(z_channel)

            for j in range(Ny):  # Y
                if self.stopScan:
                    break
                if j>0:
                    self.prepare_scan_data(max_position_x_scan, min_position_x_scan)
                    self.save_scan_data(Nx, Ny, Nz, self.scanFN)

                slice_start_time = time.time()
                self.positioner.MoveABSOLUTE(y_channel, int(y_vec[j]))         
                if self.b_Zcorrection and not self.ZCalibrationData is None:                    
                    z_vec_corrected = calculate_z_series(self.ZCalibrationData, x_vec, int(y_vec[j])) - z_calibration_offset + z_vec[i]
                    motion_stream_points = [(x_channel, int(x), z_channel, int(z)) for x, z in zip(x_vec, z_vec_corrected)]
                # self.logger.stdin.write(b"Preparing and saving scan data\n")

                time.sleep(t_wait_motionStart)
                self.readInpos(y_channel)
                self.positioner.GetPosition()
                print(f"Standing in position {self.positioner.AxesPositions[x_channel]}")

                # start line scan in X direction (ch = 0)
                # time.sleep(1) # unknown sleep
                # self.positioner.DisablePositionTrigger(0)
                # self.logger.stdin.write(f"Standing in position {self.positioner.AxesPositions}\n".encode())

                # time.sleep(0.2)
                self.positioner.DisablePositionTrigger(0)
                self.positioner.SetPositionTrigger(x_channel,
                                            min_position_x_scan-1000,
                                            max_position_x_scan-self.dL_scan[x_channel]*1e3-1000,
                                            self.dL_scan[x_channel]*1e3,
                                            1,  # Trigger on increasing values
                                            50000,  # pulse width in ns
                                            min_position_x_scan-1000,
                                            True)
                              
                self.positioner.SetUpStream(points=motion_stream_points, trigger_mode=triggerMode)                            
                while (not self.positioner.is_streaming_active(x_channel)):
                    time.sleep(5e-3) 
                while not self.job.is_paused():
                    time.sleep(5e-3)
                self.job.resume()
                # while (self.positioner.is_streaming_active(x_channel)):
                #     time.sleep(5e-3)    
                while not self.job.is_paused():
                    time.sleep(5e-3)
                print('Waiting for motion end')
                
                # init strip
                self.positioner.DisablePositionTrigger(0)
                self.readInpos(x_channel)
                self.positioner.MoveABSOLUTE(x_channel,int(max_position_x_scan + motion_buffer))
                time.sleep(t_wait_motionStart)
                self.readInpos(x_channel)
                self.positioner.MoveABSOLUTE(x_channel,int(min_position_x_scan - motion_buffer))
                time.sleep(t_wait_motionStart)
                self.readInpos(x_channel)
                # Wait for data to be available
                if counts_handle.is_processing():
                    print('Waiting for QUA counts')
                    counts_handle.wait_for_values(1)
                    counts = counts_handle.fetch_all()
                    self.qmm.clear_all_job_results()
                    self.scan_intensities[:,j,i] = counts / self.total_integration_time # counts/ms = Kcounts/s
                    self.UpdateGuiDuringScan(self.scan_intensities[:, :, i],use_fast_rgb=True)

                else:
                    print('The OPX counts stream is inactive. Aborting scan')
                    self.stopScan = True
                    break
                print(f"Time to scan one slice in X: {np.round(time.time() - slice_start_time,2)} ")

        # back to start position
        for i in range(3):
            self.positioner.MoveABSOLUTE(i, self.initial_scan_Location[i])
            res = self.readInpos(i)
            self.positioner.GetPosition()
            print(
                f"ch{i}: in position = {res}, position = {self.positioner.AxesPositions[i]} [{self.positioner.AxesPosUnits[i]}]")

        end_time = time.time()
        print(f"end_time: {end_time}")
        elapsed_time = end_time - start_time
        print(f"number of points ={Nx*Ny*Nz}")
        print(f"Elapsed time: {elapsed_time} seconds")

        self.prepare_scan_data(max_position_x_scan, min_position_x_scan)
        self.save_scan_data(Nx, Ny, Nz, self.create_scan_file_name(local=False)) # 333
        self.stopScan = True

        # convert Stop Scan to Start scan
        dpg.set_item_label("btnOPX_StartScan", "Start Scan")
        dpg.bind_item_theme(item="btnOPX_StartScan", theme="btnYellowTheme")

        self.positioner.set_in_position_delay(x_channel,delay=10)

    def prepare_scan_data(self, max_position_x_scan, min_position_x_scan):
        # Create object to be saved in excel
        self.scan_Out = []
        # probably unit issue
        x_vec = np.linspace(min_position_x_scan, max_position_x_scan, np.size(self.scan_intensities, 0), endpoint=False)
        y_vec = np.linspace(self.ini_scan_pos[1], self.ini_scan_pos[1] + self.L_scan[1] * 1e3,
                            np.size(self.scan_intensities, 1), endpoint=False)
        z_vec = np.linspace(self.ini_scan_pos[2], self.ini_scan_pos[2] + self.L_scan[2] * 1e3,
                            np.size(self.scan_intensities, 2), endpoint=False)
        for i in range(np.size(self.scan_intensities, 2)):
            for j in range(np.size(self.scan_intensities, 1)):
                for k in range(np.size(self.scan_intensities, 0)):
                    x = x_vec[k]
                    y = y_vec[j]
                    z = z_vec[i]
                    I = self.scan_intensities[k, j, i]
                    self.scan_Out.append([x, y, z, I, x, y, z])

    def OpenDialog(self):  # move to common
        root = tk.Tk()  # Create the root window
        root.withdraw()  # Hide the main window
        file_path = filedialog.askopenfilename()  # Open a file dialog

        if file_path:  # Check if a file was selected
            print(f"Selected file: {file_path}")  # add to logger
        else:
            print("No file selected")  # add to logger

        root.destroy()  # Close the main window if your application has finished using it

        return file_path
    
    def btnUpdateImages(self):
        self.Plot_Loaded_Scan(use_fast_rgb=True)
    
    def Plot_data(self,data, bLoad = False):
        np_array = np.array(data)
        # Nx = int(np_array[1,10])
        # Ny = int(np_array[1,11])
        # Nz = int(np_array[1,12])
        allPoints = np_array[0:,3]
        self.Xv = np_array[0:,4].astype(float)/1e6
        self.Yv = np_array[0:,5].astype(float)/1e6
        self.Zv = np_array[0:,6].astype(float)/1e6

        allPoints = allPoints.astype(float) # intensities
        Nx = int(round((self.Xv[-1]-self.Xv[0])/(self.Xv[1]-self.Xv[0])) + 1)
        if self.Yv[Nx]-self.Yv[0]==0:
            if bLoad:
                dpg.set_value("Scan_Message","Stopped in the middle of a frame")
                Nx, allPoints = self.attempt_to_display_unfinished_frame(allPoints=allPoints)
            else:
                return 0 # Running mode

        Ny = int(round((self.Yv[-1]-self.Yv[0])/(self.Yv[Nx]-self.Yv[0])) + 1) #777
        if Nx*Ny<len(self.Zv) and self.Zv[Ny*Nx]-self.Zv[0]>0:#Z[Ny*Nx]-Z[0] > 0:
            Nz = int(round((self.Zv[-1]-self.Zv[0])/(self.Zv[Ny*Nx]-self.Zv[0])) + 1)
            res = np.reshape(allPoints,(Nz,Ny,Nx))
            dpg.set_value("Scan_Message",f"Number of Z slices is {Nz}")
        else:
            Nz = 1
            res = np.reshape(allPoints[0:Nx*Ny],(Nz,Ny,Nx))
            dpg.set_value("Scan_Message",f"Number of Z slices is {Nz}")
              
        self.scan_data=res
        
        self.Xv=self.Xv[0:Nx] 
        self.Yv=self.Yv[0:Nx*Ny:Nx] 
        self.Zv=self.Zv[0:-1:Nx*Ny] 
        #xy
        self.startLoc = [int(np_array[1,4].astype(float)/1e6), int(np_array[1,5].astype(float)/1e6), int(np_array[1,6].astype(float)/1e6)] #um
        self.endLoc =  [int(np_array[-1,4].astype(float)/1e6),int(np_array[-1,5].astype(float)/1e6), int(np_array[-1,6].astype(float)/1e6)] #um

        # todo align image (camera) with xy grap (scan output)

        if bLoad:
            self.Plot_Loaded_Scan(use_fast_rgb=True) ### HERE
            print("Done.")
        else:
            self.Plot_Scan(Nx=Nx, Ny=Ny, array_2d=np.flipud(res[0, :, :]), startLoc=self.startLoc, endLoc=self.endLoc,
                           switchAxes=bLoad)

    import numpy as np

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
        if len(self.positioner.LoggedPoints) < 3:
            try:
                with open("map_config.txt", "r") as file:
                    lines = file.readlines()
                    # Clear the existing LoggedPoints
                    self.positioner.LoggedPoints = []
                    for line in lines:
                        # Start loading points after finding "LoggedPoint"
                        if line.startswith("LoggedPoint"):
                            coords = line.split(": ")[1].split(", ")  # Process the logged point line
                            if len(coords) == 3:  # Ensure we have 3 coordinates
                                logged_point = (float(coords[0]), float(coords[1]), float(coords[2]))
                                self.positioner.LoggedPoints.append(logged_point)
                        # Stop processing points if another section starts (e.g., "Marker" or "Rectangle")
                        elif line.startswith("Marker") or line.startswith("Rectangle"):
                            break
                    print("Logged points loaded but not into the Smaract GUI.")
                    self.ZCalibrationData = np.array(self.positioner.LoggedPoints[:3])  # Take the first three rows
                    self.to_xml()
                    dpg.set_value("Scan_Message", "Logged points loaded but not into the Smaract GUI.")
            except FileNotFoundError:
                print("map_config.txt not found.")
            except Exception as e:
                print(f"Error loading logged points: {e}")
                error_message = "Error: Less than three points are logged. Please log more points."
                print(error_message)
                dpg.set_value("Scan_Message", error_message)  # Set the error message in the text widget
        else:
            print("Calibration points loaded from positioner")
            self.ZCalibrationData = np.array(self.positioner.LoggedPoints[:3])  # Take the first three rows
            self.to_xml()
            dpg.set_value("Scan_Message", "Calibration points successfully loaded.")

    def btnLoadScan(self): #111
        fn = self.OpenDialog()
        data = self.loadFromCSV(fn)
        self.Plot_data(data,True)
        
    def save_scan_data(self, Nx, Ny, Nz, fileName = None):
        if fileName == None:
            fileName = self.create_scan_file_name()

        # parameters + note --- cause crash during scan. no need to update every slice.
        # self.writeParametersToXML(fileName + ".xml")

        # raw data
        Scan_array = np.array(self.scan_Out)
        RawData_to_save = {
            'X': Scan_array[:, 0].tolist(),
            'Y': Scan_array[:, 1].tolist(),
            'Z': Scan_array[:, 2].tolist(),
            'Intensity': Scan_array[:, 3].tolist(),
            'Xexpected': Scan_array[:, 4].tolist(),
            'Yexpected': Scan_array[:, 5].tolist(),
            'Zexpected': Scan_array[:, 6].tolist(),
        }
        #     'dx': self.dL_scan[0],  # shai 30-7-24
        #     'dy': self.dL_scan[1],
        #     'dz': self.dL_scan[2],
        #     'Nx': Nx,
        #     'Ny': Ny,
        #     'Nz': Nz,
        # }
        self.saveToCSV(fileName + ".csv", RawData_to_save)

        if self.stopScan != True:
            # prepare image for plot
            self.Scan_intensity = Scan_array[:, 3]
            # self.Scan_matrix = np.reshape(self.Scan_intensity,
            #                               (len(self.V_scan[2]), len(self.V_scan[1]), len(self.V_scan[0])))
            self.Scan_matrix = np.reshape(self.scan_intensities,
                                          (Nz, Ny, Nx)) # shai 30-7-24
            # Nz = int(len(self.V_scan[2]) / 2)
            slice2D = self.Scan_matrix[int(Nz / 2), :, :]  # ~ middle layer
            self.Save_2D_matrix2IMG(slice2D)

            # Convert the NumPy array to an image
            image = Image.fromarray(slice2D.astype(np.uint8))
            self.image_path = fileName + ".jpg"  # Save the image to a file
            image.save(self.image_path)

            self.scan_data = self.Scan_matrix
            self.idx_scan = [Nz,0,0] 
            
            self.startLoc = [Scan_array[1, 4]/1e6, Scan_array[1, 5]/1e6, Scan_array[1, 6]/1e6]
            if Nz==0:
                self.endLoc =  [self.startLoc[0]+self.dL_scan[0]*(Nx-1)/1e3,self.startLoc[1]+self.dL_scan[1]*(Ny-1)/1e3,0]
            else:
                self.endLoc =  [self.startLoc[0]+self.dL_scan[0]*(Nx-1)/1e3,self.startLoc[1]+self.dL_scan[1]*(Ny-1)/1e3,self.startLoc[2]+self.dL_scan[2]*(Nz-1)/1e3]

            #self.Plot_Scan()
        
        return fileName

    def create_scan_file_name(self, local =False):
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
                time.sleep(self.tTrackingSignaIntegrationTime*1e-3 + 0.001) # [sec]
                self.GlobalFetchData()
                while (last_iteration == self.iteration): # wait for new data
                    time.sleep(0.01)  # according to OS priorities
                    self.GlobalFetchData()
                self.lock.acquire()
                lastRef = self.tracking_ref
                last_iteration = self.iteration
                self.lock.release()

                # Log data                
                self.coordinate.append(i * self.trackStep + self.absPos) # Log axis position
                self.track_X.append(lastRef)# Loa signal to array

                # move to next location (relative move)
                self.positioner.MoveRelative(ch, self.trackStep)
                res = self.positioner.ReadIsInPosition(ch)
                while not (res):
                    res = self.positioner.ReadIsInPosition(ch)
                # print(f"i = {i}, ch = {ch}, is in position = {res}")

            
            print(f"x(ch={ch}): ", end="")
            for i in range(len(self.coordinate)):
                print(f", {self.coordinate[i]: .3f}", end="")
            print("")
            print(f"y(ch={ch}): ", end="")
            for i in range(len(self.track_X)):
                print(f", {self.track_X[i]: .3f}", end="")
            print("")

            # optional: fit to parabula
            if True:
                coefficients = np.polyfit(self.coordinate, self.track_X, 2)
                a, b, c = coefficients
                maxPos_parabula = int(-b/(2*a))
                print(f"ch = {ch}: a = {a}, b = {b}, c = {c}, maxPos_parabula={maxPos_parabula}")

            # find max signal
            maxPos = self.coordinate[self.track_X.index(max(self.track_X))]
            print(f"maxPos={maxPos}")

            # move to max signal position
            self.positioner.MoveABSOLUTE(ch, maxPos)

        # update new ref signal
        self.refSignal = max(self.track_X)
        print(f"new ref Signal = {self.refSignal}")

        # get new val for comparison
        time.sleep(self.tTrackingSignaIntegrationTime*1e-3 + 0.001 + 0.1) # [sec]
        self.GlobalFetchData()
        print(f"self.tracking_ref = {self.tracking_ref}")
        
        # shift back tp experiment sequence
        self.qm.set_io1_value(0) 
        time.sleep(0.1)

    def SearchPeakIntensity(self):
        if self.bEnableSignalIntensityCorrection:
            if (self.refSignal == 0) and (not (self.MAxSignalTh.is_alive())):
                self.refSignal = self.tracking_ref#round(sum(self.Y_Last_ref) / len(self.Y_Last_ref))
            elif (self.refSignal * self.TrackingThreshold > self.tracking_ref) and (not (self.MAxSignalTh.is_alive())):
                self.qm.set_io1_value(1) # shift to reference only
                self.MAxSignalTh = threading.Thread(target=self.FindMaxSignal)
                self.MAxSignalTh.start()
            elif (not (self.MAxSignalTh.is_alive())):
                self.refSignal = self.refSignal if self.refSignal>self.tracking_ref else self.tracking_ref

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
                if (list_elem.tag != "scan_Out" and
                        list_elem.tag != "X_vec" and list_elem.tag != "Y_vec" and list_elem.tag != "Z_vec" and
                        list_elem.tag != "X_vec_ref" and list_elem.tag != "Y_vec_ref" and list_elem.tag != "Z_vec_ref" and
                        list_elem.tag != "V_scan" and list_elem.tag != "expected_pos"):
                    for item in value:
                        item_elem = ET.SubElement(list_elem, "item")
                        item_elem.text = str(item)
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

    def fast_rgb_convert(self,Array2D):
        # Mask for non-zero values
        mask_non_zero = Array2D > 0

        # Normalize non-zero values to stretch across the entire color scale
        normalized_array = np.zeros_like(Array2D, dtype=float)
        normalized_array[mask_non_zero] = Array2D[mask_non_zero] / Array2D[mask_non_zero].max()

        # Generate the RGB heatmap, ignoring zeros
        result_array_ = intensity_to_rgb_heatmap_normalized(normalized_array)

        # Add the alpha channel: 1 for non-zero values, 0 for zero values
        alpha_channel = mask_non_zero.astype(float)

        return np.dstack((result_array_,alpha_channel))

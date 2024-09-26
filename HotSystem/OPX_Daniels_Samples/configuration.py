import numpy as np
from qualang_tools.units import unit
from qualang_tools.plot import interrupt_on_close
from qualang_tools.results import progress_counter, fetching_tool

#######################
# AUXILIARY FUNCTIONS #
#######################

# IQ imbalance matrix
def IQ_imbalance(g, phi):
    """
    Creates the correction matrix for the mixer imbalance caused by the gain and phase imbalances, more information can
    be seen here:
    https://docs.qualang.io/libs/examples/mixer-calibration/#non-ideal-mixer

    :param g: relative gain imbalance between the I & Q ports (unit-less). Set to 0 for no gain imbalance.
    :param phi: relative phase imbalance between the I & Q ports (radians). Set to 0 for no phase imbalance.
    """
    c = np.cos(phi)
    s = np.sin(phi)
    N = 1 / ((1 - g**2) * (2 * c**2 - 1))
    return [float(N * x) for x in [(1 - g) * c, (1 + g) * s, (1 - g) * s, (1 + g) * c]]


#############
# VARIABLES #
#############
u = unit()
# opx_ip = '192.168.79.67' # old
opx_ip = '192.168.101.60'
opx_port = 80

# Frequencies
NV_IF_freq = 124e6  # in units of Hz
NV_LO_freq = 2.7e9  # in units of Hz (Omega_0, not relevant when using calibrated oscillator e.g R&S)

# Pulses lengths
initialization_len = 5000  # in ns
meas_len = 300  # in ns
long_meas_len = 5e3  # in ns

# MW parameters
mw_amp_NV = 0.2  # in units of volts
mw_len_NV = 100  # in units of ns

pi_amp_NV = 0.5  # in units of volts
pi_len_NV = 16  # in units of ns

pi_half_amp_NV = pi_amp_NV / 2  # in units of volts
pi_half_len_NV = pi_len_NV  # in units of ns

# MW Switch parameters
switch_delay = 410  # in ns add delay of 94 ns to the digital signal
switch_buffer = 10  # in ns add extra 10 ns at the beginning and end of the digital pulse
switch_len = 100  # in ns

# Readout parameters
signal_threshold = -400  # in ADC units #12bit signal -0.5 to +0.5 ==> 4096/1 (bits/volt)
signal_threshold_OPD = 0.1  # in voltage

# Delays
detection_delay = 112 # ns (mod4 > 36)
detection_delay_OPD = 160
mw_delay = 300 # ns
laser_delay = 0

# RF parameters
rf_frequency = 10 * u.MHz
rf_amp = 0.1
rf_length = 1000
rf_delay = 0 * u.ns    

config = {
    "version": 1,

    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {  # OPX outputs
                1: {"offset": 0.0, "shareable": True, "delay": mw_delay},  # NV I, offset = amplitude (v), delay = time (ns)
                2: {"offset": 0.0, "shareable": True, "delay": mw_delay},  # NV Q
                3: {"offset": 0.0, "shareable": True, "delay": rf_delay},  # RF 
            },
            "digital_outputs": {  # OPX outputs
                1: {"shareable": True},  # AOM/Laser
                2: {"shareable": True},  # MW switch
                3: {"shareable": True},  # Photo diode - indicator
            },
            "analog_inputs": {  # OPX inputs
                1: {"offset": 0.00979, 'gain_db': 0, "shareable": True},  # SPCM, use 02_raw_adc_traces.py to calc the offset
            },
            'digital_inputs': { #OPD inputs
                1: {'polarity': 'RISING', 'deadtime': 4, "threshold": signal_threshold_OPD, "shareable": True},
            },
        }
    },

    "elements": {  # OPX output will be written here as input and vice versa
        
        "RF": {
            "singleInput": {"port": ("con1", 3)},
            "intermediate_frequency": rf_frequency,
            "operations": {
                "const": "const_pulse_single",
            },
        },

        "NV": {  # example how to write inside program: play("cw", "NV")
            "mixInputs": {"I": ("con1", 1), "Q": ("con1", 2), "lo_frequency": NV_LO_freq, "mixer": "mixer_NV"}, # mixInputs specifically for i&q
            "intermediate_frequency": NV_IF_freq,
            "digitalInputs": {  # RF switch (ON/OFF
                "marker": {
                    "port": ("con1", 2),
                    "delay": switch_delay,
                    "buffer": switch_buffer,
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

        "AOM": { # AOM is arbitrary name, in our system it is just LASER
            "digitalInputs": { # for the OPX it is digital outputs
                "marker": { # marker is arbitrary name
                    "port": ("con1", 1), # CH NUM
                    "delay": laser_delay,
                    "buffer": 0, # buffer <= laser_delay, amir: TBD to understand it
                },
            },
            "operations": {
                "laser_ON": "laser_ON",
            },
        },

        "MW_switch": {
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 2),
                    "delay": switch_delay,
                    "buffer": switch_buffer,
                },
            },
            "operations": {
                "ON": "switch_ON",
            },
        },

        "SPCM": {
            "singleInput": {"port": ("con1", 1)},  # not used but must stay here
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 3),
                    "delay": detection_delay, # what exactly does it means
                    "buffer": 0,
                },
            },
            "operations": {
                "readout": "readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {"out1": ("con1", 1)},
            "outputPulseParameters": {
                "signalThreshold": signal_threshold,
                "signalPolarity": "Descending",
                "derivativeThreshold": 1023,
                "derivativePolarity": "Descending",
            },
            "time_of_flight": detection_delay,
            "smearing": 0,
        },

        "SPCM_OPD": {
            "singleInput": {"port": ("con1", 1)},  # not used
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 3),
                    "delay": detection_delay_OPD,
                    "buffer": 0,
                },
            },
            'digitalOutputs': {
                'out1': ('con1', 1)
            },
            "outputs": {"out1": ("con1", 1)},
            "operations": {
                "readout": "readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "time_of_flight": detection_delay_OPD,
            "smearing": 0,
        },
    },

    "pulses": {
        "const_pulse_single": {
            "operation": "control",
            "length": rf_length,  # in ns
            "waveforms": {"single": "rf_const_wf"},
        },
        "const_pulse": {
            "operation": "control",
            "length": mw_len_NV,
            "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
            "digital_marker": "ON",   # 'ON' is digital waveform name
        },
        "x180_pulse": {
            "operation": "control",
            "length": pi_len_NV,
            "waveforms": {"I": "pi_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "x90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "pi_half_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "-x90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "-pi_half_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "y180_pulse": {
            "operation": "control",
            "length": pi_len_NV,
            "waveforms": {"I": "zero_wf" , "Q": "pi_wf"},
            "digital_marker": "ON",
        },
        "y90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "zero_wf", "Q": "pi_half_wf"},
            "digital_marker": "ON",
        },
        "laser_ON": {
            "operation": "control",
            "length": initialization_len,
            "digital_marker": "ON",
        },
        "switch_ON": {
            "operation": "control",
            "length": switch_len,
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "operation": "measurement",
            "length": meas_len,
            "digital_marker": "ON",
            "waveforms": {"single": "zero_wf"},
        },
        "long_readout_pulse": {
            "operation": "measurement",
            "length": long_meas_len,
            "digital_marker": "ON",
            "waveforms": {"single": "zero_wf"},
        },
    },

    "waveforms": {
        "rf_const_wf": {"type": "constant", "sample": rf_amp},
        "cw_wf": {"type": "constant", "sample": mw_amp_NV},
        "pi_wf": {"type": "constant", "sample": pi_amp_NV},
        "pi_half_wf": {"type": "constant", "sample": pi_half_amp_NV},
        "-pi_half_wf": {"type": "constant", "sample": -pi_half_amp_NV},
        "zero_wf": {"type": "constant", "sample": 0.0},
    },

    "digital_waveforms": {
        "ON": {"samples": [(1, 0)]},  # [(on/off, ns)]
        "test": {"samples": [(1, 4), (0, 8), (1, 12)]},  # [(on/off, ns)] arbitrary example digital waveform total length /4 shoult be integer
        "OFF": {"samples": [(0, 0)]},  # [(on/off, ns)]
    },

    "mixers": {
        "mixer_NV": [
            {"intermediate_frequency": NV_IF_freq, "lo_frequency": NV_LO_freq, "correction": IQ_imbalance(0.0, 0.0)},
        ],
    },

}




config1 = {
    "version": 1,

    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {  # OPX outputs
                1: {"offset": 0.0, "shareable": True, "delay": mw_delay},  # NV I, offset = amplitude (v), delay = time (ns)
                2: {"offset": 0.0, "shareable": True, "delay": mw_delay},  # NV Q
                3: {"offset": 0.0, "shareable": True, "delay": rf_delay},  # RF 
            },
            "digital_outputs": {  # OPX outputs
                1: {"shareable": True},  # AOM/Laser
                2: {"shareable": True},  # MW switch
                3: {"shareable": True},  # Photo diode - indicator
            },
            "analog_inputs": {  # OPX inputs
                1: {"offset": 0.00979, 'gain_db': 0, "shareable": True},  # SPCM, use 02_raw_adc_traces.py to calc the offset
            },
            'digital_inputs': { #OPD inputs
                1: {'polarity': 'RISING', 'deadtime': 4, "threshold": signal_threshold_OPD, "shareable": True},
            },
        }
    },

    "elements": {  # OPX output will be written here as input and vice versa
        
        "RF": {
            "singleInput": {"port": ("con1", 3)},
            "intermediate_frequency": rf_frequency,
            "operations": {
                "const": "const_pulse_single",
            },
        },

        "NV": {  # example how to write inside program: play("cw", "NV")
            "mixInputs": {"I": ("con1", 1), "Q": ("con1", 2), "lo_frequency": NV_LO_freq, "mixer": "mixer_NV"}, # mixInputs specifically for i&q
            "intermediate_frequency": NV_IF_freq,
            "digitalInputs": {  # RF switch (ON/OFF
                "marker": {
                    "port": ("con1", 2),
                    "delay": switch_delay,
                    "buffer": switch_buffer,
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

        "AOM": { # AOM is arbitrary name, in our system it is just LASER
            "digitalInputs": { # for the OPX it is digital outputs
                "marker": { # marker is arbitrary name
                    "port": ("con1", 1), # CH NUM
                    "delay": laser_delay,
                    "buffer": 0, # buffer <= laser_delay, amir: TBD to understand it
                },
            },
            "operations": {
                "laser_ON": "laser_ON",
            },
        },

        "MW_switch": {
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 2),
                    "delay": switch_delay,
                    "buffer": switch_buffer,
                },
            },
            "operations": {
                "ON": "switch_ON",
            },
        },

        "SPCM": {
            "singleInput": {"port": ("con1", 1)},  # not used but must stay here
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 3),
                    "delay": detection_delay, # what exactly does it means
                    "buffer": 0,
                },
            },
            "operations": {
                "readout": "readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {"out1": ("con1", 1)},
            "outputPulseParameters": {
                "signalThreshold": signal_threshold,
                "signalPolarity": "Descending",
                "derivativeThreshold": 1023,
                "derivativePolarity": "Descending",
            },
            "time_of_flight": detection_delay,
            "smearing": 0,
        },

        "SPCM_OPD": {
            "singleInput": {"port": ("con1", 1)},  # not used
            "digitalInputs": {
                "marker": {
                    "port": ("con1", 3),
                    "delay": detection_delay_OPD,
                    "buffer": 0,
                },
            },
            'digitalOutputs': {
                'out1': ('con1', 1)
            },
            "outputs": {"out1": ("con1", 1)},
            "operations": {
                "readout": "readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "time_of_flight": detection_delay_OPD,
            "smearing": 0,
        },
    },

    "pulses": {
        "const_pulse_single": {
            "operation": "control",
            "length": rf_length,  # in ns
            "waveforms": {"single": "rf_const_wf"},
        },
        "const_pulse": {
            "operation": "control",
            "length": mw_len_NV,
            "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
            "digital_marker": "ON",   # 'ON' is digital waveform name
        },
        "x180_pulse": {
            "operation": "control",
            "length": pi_len_NV,
            "waveforms": {"I": "pi_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "x90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "pi_half_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "-x90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "-pi_half_wf", "Q": "zero_wf"},
            "digital_marker": "ON",
        },
        "y180_pulse": {
            "operation": "control",
            "length": pi_len_NV,
            "waveforms": {"I": "zero_wf" , "Q": "pi_wf"},
            "digital_marker": "ON",
        },
        "y90_pulse": {
            "operation": "control",
            "length": pi_half_len_NV,
            "waveforms": {"I": "zero_wf", "Q": "pi_half_wf"},
            "digital_marker": "ON",
        },
        "laser_ON": {
            "operation": "control",
            "length": initialization_len,
            "digital_marker": "ON",
        },
        "switch_ON": {
            "operation": "control",
            "length": switch_len,
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "operation": "measurement",
            "length": meas_len,
            "digital_marker": "ON",
            "waveforms": {"single": "zero_wf"},
        },
        "long_readout_pulse": {
            "operation": "measurement",
            "length": long_meas_len,
            "digital_marker": "ON",
            "waveforms": {"single": "zero_wf"},
        },
    },

    "waveforms": {
        "rf_const_wf": {"type": "constant", "sample": rf_amp},
        "cw_wf": {"type": "constant", "sample": mw_amp_NV},
        "pi_wf": {"type": "constant", "sample": pi_amp_NV},
        "pi_half_wf": {"type": "constant", "sample": pi_half_amp_NV},
        "-pi_half_wf": {"type": "constant", "sample": -pi_half_amp_NV},
        "zero_wf": {"type": "constant", "sample": 0.0},
    },

    "digital_waveforms": {
        "ON": {"samples": [(1, 0)]},  # [(on/off, ns)]
        "test": {"samples": [(1, 4), (0, 8), (1, 12)]},  # [(on/off, ns)] arbitrary example digital waveform total length /4 shoult be integer
        "OFF": {"samples": [(0, 0)]},  # [(on/off, ns)]
    },

    "mixers": {
        "mixer_NV": [
            {"intermediate_frequency": NV_IF_freq, "lo_frequency": NV_LO_freq, "correction": IQ_imbalance(0.0, 0.0)},
        ],
    },

}

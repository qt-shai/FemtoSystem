
# Single QUA script generated at 2025-03-13 16:57:19.936331
# QUA library version: 1.2.2a2

from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    a1 = declare(int, size=1000)
    a2 = declare(int, size=1000)
    v1 = declare(int, )
    v2 = declare(int, )
    v3 = declare(int, value=0)
    v4 = declare(int, value=0)
    v5 = declare(int, )
    v6 = declare(bool, value=False)
    with infinite_loop_():
        with for_(v5,0,(v5<500),(v5+1)):
            play("Turn_ON", "Resonant_Laser", duration=2500)
            measure("min_readout", "Detector_OPD", None, time_tagging.digital(a1, 10000, v1, ""))
            measure("min_readout", "Detector2_OPD", None, time_tagging.analog(a2, 10000, v2, ""))
        r1 = declare_stream()
        save(v3, r1)
        r2 = declare_stream()
        save(v4, r2)
        assign(v3, 0)
        assign(v4, 0)
    with stream_processing():
        r1.with_timestamps().save("counts")
        r2.with_timestamps().save("counts_ref")


config = {
    "version": 1,
    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {
                "4": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
                "5": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
                "6": {
                    "offset": 0.0,
                    "delay": 8,
                    "shareable": False,
                },
                "9": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
            },
            "digital_outputs": {
                "4": {
                    "shareable": False,
                },
                "5": {
                    "shareable": False,
                },
                "7": {
                    "shareable": False,
                },
            },
            "analog_inputs": {
                "1": {
                    "offset": 0.00979,
                    "gain_db": 0,
                    "shareable": False,
                },
            },
            "digital_inputs": {
                "4": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1,
                    "shareable": False,
                },
                "5": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1,
                    "shareable": False,
                },
            },
        },
    },
    "elements": {
        "RF": {
            "singleInput": {
                "port": ('con1', 6),
            },
            "intermediate_frequency": 3030000.0,
            "operations": {
                "const": "const_pulse_single",
            },
        },
        "MW": {
            "mixInputs": {
                "I": ('con1', 4),
                "Q": ('con1', 5),
                "lo_frequency": 2700000000.0,
                "mixer": "mixer_NV",
            },
            "intermediate_frequency": 124000000.0,
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 5),
                    "delay": 122,
                    "buffer": 0,
                },
            },
            "operations": {
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
        "Resonant_Laser": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 7),
                    "delay": 120,
                    "buffer": 0,
                },
            },
            "operations": {
                "Turn_ON": "laser_ON",
            },
        },
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 4),
                    "delay": 120,
                    "buffer": 0,
                },
            },
            "operations": {
                "Turn_ON": "laser_ON",
            },
        },
        "MW_switch": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 5),
                    "delay": 122,
                    "buffer": 0,
                },
            },
            "operations": {
                "ON": "switch_ON",
            },
        },
        "Detector_OPD": {
            "singleInput": {
                "port": ('con1', 4),
            },
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 4),
            },
            "outputs": {
                "out1": ('con1', 1),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
                "very_long_readout": "very_long_readout_pulse",
            },
            "time_of_flight": 308,
            "smearing": 0,
        },
        "Detector2_OPD": {
            "singleInput": {
                "port": ('con1', 4),
            },
            "digitalInputs": {},
            "outputs": {
                "out1": ('con1', 1),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
                "very_long_readout": "very_long_readout_pulse",
            },
            "time_of_flight": 308,
            "smearing": 0,
        },
    },
    "pulses": {
        "const_pulse_single": {
            "operation": "control",
            "length": 1000,
            "waveforms": {
                "single": "rf_const_wf",
            },
        },
        "x_pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "I": "cw_wf",
                "Q": "zero_wf",
            },
            "digital_marker": "ON",
        },
        "y_pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "I": "zero_wf",
                "Q": "cw_wf",
            },
            "digital_marker": "ON",
        },
        "const_pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "I": "cw_wf",
                "Q": "zero_wf",
            },
            "digital_marker": "ON",
        },
        "x180_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "I": "pi_wf",
                "Q": "zero_wf",
            },
            "digital_marker": "ON",
        },
        "x90_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "I": "pi_half_wf",
                "Q": "zero_wf",
            },
            "digital_marker": "ON",
        },
        "-x90_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "I": "-pi_half_wf",
                "Q": "zero_wf",
            },
            "digital_marker": "ON",
        },
        "y180_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "I": "zero_wf",
                "Q": "pi_wf",
            },
            "digital_marker": "ON",
        },
        "y90_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "I": "zero_wf",
                "Q": "pi_half_wf",
            },
            "digital_marker": "ON",
        },
        "laser_ON": {
            "operation": "control",
            "length": 5000,
            "digital_marker": "ON",
        },
        "switch_ON": {
            "operation": "control",
            "length": 100,
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "operation": "measurement",
            "length": 300,
            "digital_marker": "ON",
            "waveforms": {
                "single": "zero_wf",
            },
        },
        "min_readout_pulse": {
            "operation": "measurement",
            "length": 16,
            "digital_marker": "ON",
            "waveforms": {
                "single": "zero_wf",
            },
        },
        "long_readout_pulse": {
            "operation": "measurement",
            "length": 5000.0,
            "digital_marker": "ON",
            "waveforms": {
                "single": "zero_wf",
            },
        },
        "very_long_readout_pulse": {
            "operation": "measurement",
            "length": 25000.0,
            "digital_marker": "ON",
            "waveforms": {
                "single": "zero_wf",
            },
        },
        "atto_set_voltage_pulse": {
            "operation": "control",
            "length": 16,
            "waveforms": {
                "single": "zero_wf",
            },
        },
    },
    "waveforms": {
        "rf_const_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "cw_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "pi_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "pi_half_wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "-pi_half_wf": {
            "type": "constant",
            "sample": -0.25,
        },
        "zero_wf": {
            "type": "constant",
            "sample": 0.0,
        },
    },
    "digital_waveforms": {
        "ON": {
            "samples": [(1, 0)],
        },
        "test": {
            "samples": [(1, 4), (0, 8), (1, 12)],
        },
        "OFF": {
            "samples": [(0, 0)],
        },
    },
    "mixers": {
        "mixer_NV": [{'intermediate_frequency': 124000000.0, 'lo_frequency': 2700000000.0, 'correction': [1.0, 0.0, 0.0, 1.0]}],
    },
}

loaded_config = {
    "version": 1,
    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {
                "4": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
                "5": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
                "6": {
                    "offset": 0.0,
                    "delay": 8,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
                "9": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
            },
            "analog_inputs": {
                "1": {
                    "offset": 0.00979,
                    "gain_db": 0,
                    "shareable": False,
                    "sampling_rate": 1000000000.0,
                },
            },
            "digital_outputs": {
                "4": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "5": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "7": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
            },
            "digital_inputs": {
                "4": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1.0,
                    "shareable": False,
                },
                "5": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1.0,
                    "shareable": False,
                },
            },
        },
    },
    "oscillators": {},
    "elements": {
        "RF": {
            "digitalInputs": {},
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "const": "const_pulse_single",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
            "singleInput": {
                "port": ('con1', 1, 6),
            },
            "intermediate_frequency": 3030000.0,
        },
        "MW": {
            "digitalInputs": {
                "marker": {
                    "delay": 122,
                    "buffer": 0,
                    "port": ('con1', 1, 5),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
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
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
            "mixInputs": {
                "I": ('con1', 1, 4),
                "Q": ('con1', 1, 5),
                "mixer": "mixer_NV",
                "lo_frequency": 2700000000.0,
            },
            "intermediate_frequency": 124000000.0,
        },
        "Resonant_Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 120,
                    "buffer": 0,
                    "port": ('con1', 1, 7),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "Turn_ON": "laser_ON",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
        },
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 120,
                    "buffer": 0,
                    "port": ('con1', 1, 4),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "Turn_ON": "laser_ON",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
        },
        "MW_switch": {
            "digitalInputs": {
                "marker": {
                    "delay": 122,
                    "buffer": 0,
                    "port": ('con1', 1, 5),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "ON": "switch_ON",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
        },
        "Detector_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 1, 4),
            },
            "outputs": {
                "out1": ('con1', 1, 1),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
                "very_long_readout": "very_long_readout_pulse",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
            "singleInput": {
                "port": ('con1', 1, 4),
            },
            "smearing": 0,
            "time_of_flight": 308,
        },
        "Detector2_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {},
            "outputs": {
                "out1": ('con1', 1, 1),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
                "very_long_readout": "very_long_readout_pulse",
            },
            "hold_offset": {
                "duration": 0,
            },
            "sticky": {
                "analog": False,
                "digital": False,
                "duration": 4,
            },
            "thread": "",
            "singleInput": {
                "port": ('con1', 1, 4),
            },
            "smearing": 0,
            "time_of_flight": 308,
        },
    },
    "pulses": {
        "const_pulse_single": {
            "length": 1000,
            "waveforms": {
                "single": "rf_const_wf",
            },
            "integration_weights": {},
            "operation": "control",
        },
        "x_pulse": {
            "length": 100,
            "waveforms": {
                "I": "cw_wf",
                "Q": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "y_pulse": {
            "length": 100,
            "waveforms": {
                "I": "zero_wf",
                "Q": "cw_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "const_pulse": {
            "length": 100,
            "waveforms": {
                "I": "cw_wf",
                "Q": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "x180_pulse": {
            "length": 16,
            "waveforms": {
                "I": "pi_wf",
                "Q": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "x90_pulse": {
            "length": 16,
            "waveforms": {
                "I": "pi_half_wf",
                "Q": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "-x90_pulse": {
            "length": 16,
            "waveforms": {
                "I": "-pi_half_wf",
                "Q": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "y180_pulse": {
            "length": 16,
            "waveforms": {
                "I": "zero_wf",
                "Q": "pi_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "y90_pulse": {
            "length": 16,
            "waveforms": {
                "I": "zero_wf",
                "Q": "pi_half_wf",
            },
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "laser_ON": {
            "length": 5000,
            "waveforms": {},
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "switch_ON": {
            "length": 100,
            "waveforms": {},
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "length": 300,
            "waveforms": {
                "single": "zero_wf",
            },
            "integration_weights": {},
            "operation": "measurement",
            "digital_marker": "ON",
        },
        "min_readout_pulse": {
            "length": 16,
            "waveforms": {
                "single": "zero_wf",
            },
            "integration_weights": {},
            "operation": "measurement",
            "digital_marker": "ON",
        },
        "long_readout_pulse": {
            "length": 5000,
            "waveforms": {
                "single": "zero_wf",
            },
            "integration_weights": {},
            "operation": "measurement",
            "digital_marker": "ON",
        },
        "very_long_readout_pulse": {
            "length": 25000,
            "waveforms": {
                "single": "zero_wf",
            },
            "integration_weights": {},
            "operation": "measurement",
            "digital_marker": "ON",
        },
        "atto_set_voltage_pulse": {
            "length": 16,
            "waveforms": {
                "single": "zero_wf",
            },
            "integration_weights": {},
            "operation": "control",
        },
    },
    "waveforms": {
        "rf_const_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "cw_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "pi_wf": {
            "type": "constant",
            "sample": 0.5,
        },
        "pi_half_wf": {
            "type": "constant",
            "sample": 0.25,
        },
        "-pi_half_wf": {
            "type": "constant",
            "sample": -0.25,
        },
        "zero_wf": {
            "type": "constant",
            "sample": 0.0,
        },
    },
    "digital_waveforms": {
        "ON": {
            "samples": [(1, 0)],
        },
        "test": {
            "samples": [(1, 4), (0, 8), (1, 12)],
        },
        "OFF": {
            "samples": [(0, 0)],
        },
    },
    "integration_weights": {},
    "mixers": {
        "mixer_NV": [{'intermediate_frequency': 124000000.0, 'lo_frequency': 2700000000.0, 'correction': (1.0, 0.0, 0.0, 1.0)}],
    },
}



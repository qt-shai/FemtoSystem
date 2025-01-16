
# Single QUA script generated at 2025-01-13 13:18:19.819840
# QUA library version: 1.2.1

from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    a1 = declare(int, size=1000)
    v1 = declare(int, )
    v2 = declare(int, value=0)
    v3 = declare(int, )
    v4 = declare(int, value=0)
    v5 = declare(int, value=0)
    v6 = declare(int, value=10001)
    assign(IO2, 0)
    with infinite_loop_():
        assign(v5, IO2)
        with if_(((v6<(v5+1))&(v6>(v5-1)))):
            assign(IO2, 0)
            assign(v5, 0)
            align()
            align()
            with for_(v3,0,(v3<500),(v3+1)):
                play("Turn_ON", "Laser", duration=2500)
                measure("readout", "Detector_OPD", None, time_tagging.analog(a1, 10000, v1, ""))
                assign(v2, (v2+v1))
            r1 = declare_stream()
            save(v2, r1)
            assign(v2, 0)
            align()
            wait(1250000, )
            align()
            assign(v4, (v4+1))
            r2 = declare_stream()
            save(v4, r2)
    with stream_processing():
        r2.save("meas_idx_scanLine")
        r1.buffer(100).save("counts_scanLine")


config = {
    "version": 1,
    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {
                "1": {
                    "offset": 0.0,
                    "delay": 8,
                    "shareable": True,
                },
            },
            "digital_outputs": {
                "5": {
                    "shareable": True,
                },
            },
            "analog_inputs": {
                "1": {
                    "offset": 0.00979,
                    "gain_db": 0,
                    "shareable": True,
                },
                "2": {
                    "offset": 0.00979,
                    "gain_db": -12,
                    "shareable": True,
                },
            },
        },
    },
    "elements": {
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 5),
                    "delay": 120,
                    "buffer": 0,
                },
            },
            "operations": {
                "Turn_ON": "laser_ON",
            },
        },
        "Detector_OPD": {
            "singleInput": {
                "port": ('con1', 1),
            },
            "digitalInputs": {},
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {
                "out1": ('con1', 2),
            },
            "outputPulseParameters": {
                "signalThreshold": -500,
                "signalPolarity": "below",
                "derivativeThreshold": 1023,
                "derivativePolarity": "below",
            },
            "time_of_flight": 112,
            "smearing": 0,
        },
        "Detector2_OPD": {
            "singleInput": {
                "port": ('con1', 1),
            },
            "digitalInputs": {},
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {
                "out1": ('con1', 2),
            },
            "outputPulseParameters": {
                "signalThreshold": -350,
                "signalPolarity": "below",
                "derivativeThreshold": 1023,
                "derivativePolarity": "below",
            },
            "time_of_flight": 112,
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
                "1": {
                    "offset": 0.0,
                    "delay": 8,
                    "shareable": True,
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
                    "shareable": True,
                    "sampling_rate": 1000000000.0,
                },
                "2": {
                    "offset": 0.00979,
                    "gain_db": -12,
                    "shareable": True,
                    "sampling_rate": 1000000000.0,
                },
            },
            "digital_outputs": {
                "5": {
                    "shareable": True,
                    "inverted": False,
                    "level": "LVTTL",
                },
            },
            "digital_inputs": {},
        },
    },
    "oscillators": {},
    "elements": {
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 120,
                    "buffer": 0,
                    "port": ('con1', 1, 5),
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
        "Detector_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {},
            "outputs": {
                "out1": ('con1', 1, 2),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
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
                "port": ('con1', 1, 1),
            },
            "smearing": 0,
            "time_of_flight": 112,
        },
        "Detector2_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {},
            "outputs": {
                "out1": ('con1', 1, 2),
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
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
                "port": ('con1', 1, 1),
            },
            "smearing": 0,
            "time_of_flight": 112,
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




# Single QUA script generated at 2025-02-02 14:04:51.902896
# QUA library version: 1.2.1

from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    v1 = declare(bool, )
    v2 = declare(int, )
    a1 = declare(int, size=100)
    a2 = declare(int, size=100)
    a3 = declare(int, size=100)
    v3 = declare(int, )
    v4 = declare(int, )
    v5 = declare(fixed, )
    v6 = declare(int, )
    v7 = declare(int, )
    v8 = declare(int, )
    v9 = declare(int, )
    v10 = declare(int, )
    v11 = declare(int, )
    v12 = declare(int, )
    v13 = declare(int, )
    v14 = declare(int, )
    v15 = declare(int, )
    v16 = declare(int, )
    v17 = declare(bool, value=True)
    v18 = declare(int, value=0)
    v19 = declare(int, )
    v20 = declare(int, value=0)
    v21 = declare(int, value=0)
    a4 = declare(int, size=1)
    a5 = declare(int, size=1)
    a6 = declare(int, size=1)
    a7 = declare(int, value=[0, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000, 900000, 1000000, 1100000, 1200000, 1300000, 1400000, 1500000, 1600000, 1700000, 1800000, 1900000, 2000000, 2100000, 2200000, 2300000, 2400000, 2500000, 2600000, 2700000, 2800000, 2900000, 3000000, 3100000, 3200000, 3300000, 3400000, 3500000, 3600000, 3700000, 3800000, 3900000, 4000000, 4100000, 4200000, 4300000, 4400000, 4500000, 4600000, 4700000, 4800000, 4900000, 5000000, 5100000, 5200000, 5300000, 5400000, 5500000, 5600000, 5700000, 5800000, 5900000, 6000000, 6100000, 6200000, 6300000, 6400000, 6500000, 6600000, 6700000, 6800000, 6900000, 7000000, 7100000, 7200000, 7300000, 7400000, 7500000, 7600000, 7700000, 7800000, 7900000, 8000000, 8100000, 8200000, 8300000, 8400000, 8500000, 8600000, 8700000, 8800000, 8900000, 9000000, 9100000, 9200000, 9300000, 9400000, 9500000, 9600000, 9700000, 9800000, 9900000, 10000000])
    a8 = declare(int, value=[0])
    v22 = declare(int, )
    v23 = declare(int, )
    v24 = declare(int, )
    v25 = declare(int, )
    v26 = declare(int, value=111542575)
    assign(v1, True)
    with for_(v2,0,(v2<1000000),(v2+1)):
        with for_(v22,0,(v22<1),(v22+1)):
            assign(a4[v22], 0)
            assign(a5[v22], 0)
            assign(a1[v22], 0)
        with if_(False):
            with for_(v25,0,(v25<1),(v25+1)):
                assign(v24, call_library_function('random', 'rand_int', [v26,(1-v25)]))
                assign(v23, a8[v24])
                assign(a8[v24], a8[(0-v25)])
                assign(a8[(0-v25)], v23)
        with for_(v22,0,(v22<1),(v22+1)):
            assign(v21, IO1)
            with if_((v21==0)):
                update_frequency("MW", v3, "Hz", False)
                play("Turn_ON", "Laser", duration=1250)
                play("Turn_ON", "Blinding", duration=1258)
                align("Laser", "MW")
                play("xPulse"*amp(1.0), "MW", duration=4)
                align("MW", "Resonant_Laser")
                play("Turn_ON", "Resonant_Laser", duration=4)
                with if_(v1):
                    assign(a4[v22], 2)
                    with for_(v8,0,(v8<a4[v22]),(v8+1)):
                        assign(a1[v8], (v8*10))
                    assign(a5[v22], 15)
                with else_():
                    align("Resonant_Laser", "Detector_OPD")
                    measure("readout", "Detector_OPD", None, time_tagging.analog(a1, 24, v13, ""))
                    assign(a4[v22], (a4[v22]+v13))
                    align("Resonant_Laser", "Blinding")
                    wait(18, )
                    play("Turn_ON", "Blinding", duration=9)
                    align("Resonant_Laser", "MW")
                    play("xPulse"*amp(1.0), "MW", duration=5)
                    align("MW", "Resonant_Laser")
                    play("Turn_ON", "Resonant_Laser", duration=4)
                    align()
                    play("Turn_ON", "Blinding", duration=4)
                    play("xPulse"*amp(1.0), "MW", duration=4)
                    align("MW", "Resonant_Laser")
                    play("Turn_ON", "Resonant_Laser", duration=25)
                    align("MW", "Detector2_OPD")
                    measure("min_readout", "Detector2_OPD", None, time_tagging.analog(a2, 25, v14, ""))
                    assign(a5[v22], (a5[v22]+v14))
        with if_((v21==0)):
            with for_(v22,0,(v22<1),(v22+1)):
                r3 = declare_stream()
                save(a4[v22], r3)
                r5 = declare_stream()
                save(a5[v22], r5)
            with for_(v22,0,(v22<a4[0]),(v22+1)):
                r4 = declare_stream()
                save(a1[v22], r4)
        r1 = declare_stream()
        save(v2, r1)
        r2 = declare_stream()
        save(v20, r2)
    with stream_processing():
        r1.save_all("iteration")
        r4.save_all("times")
        r3.save_all("counts")
        r5.save_all("statistics_counts")


config = {
    "version": 1,
    "controllers": {
        "con1": {
            "type": "opx1",
            "analog_outputs": {
                "1": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
                "2": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
                "3": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                },
            },
            "digital_outputs": {
                "1": {
                    "shareable": False,
                },
                "2": {
                    "shareable": False,
                },
                "3": {
                    "shareable": False,
                },
                "6": {
                    "shareable": False,
                },
                "8": {
                    "shareable": False,
                },
            },
            "analog_inputs": {
                "1": {
                    "offset": 0.00979,
                    "gain_db": 0,
                    "shareable": False,
                },
                "2": {
                    "offset": 0.00979,
                    "gain_db": -12,
                    "shareable": False,
                },
            },
        },
    },
    "elements": {
        "MW": {
            "mixInputs": {
                "I": ('con1', 2),
                "Q": ('con1', 3),
                "lo_frequency": 2700000000.0,
                "mixer": "mixer_NV",
            },
            "intermediate_frequency": 124000000.0,
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 2),
                    "delay": 0,
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
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 1),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            "operations": {
                "Turn_ON": "laser_ON",
            },
        },
        "Resonant_Laser": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 8),
                    "delay": 0,
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
                    "port": ('con1', 2),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            "operations": {
                "ON": "switch_ON",
            },
        },
        "Detector_OPD": {
            "singleInput": {
                "port": ('con1', 1),
            },
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 3),
                    "delay": 28,
                    "buffer": 0,
                },
            },
            "operations": {
                "readout": "readout_pulse",
                "min_readout": "min_readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {
                "out1": ('con1', 1),
            },
            "outputPulseParameters": {
                "signalThreshold": -500,
                "signalPolarity": "below",
                "derivativeThreshold": 1023,
                "derivativePolarity": "below",
            },
            "time_of_flight": 28,
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
            "time_of_flight": 28,
            "smearing": 0,
        },
        "Blinding": {
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 6),
                    "delay": 0,
                    "buffer": 0,
                },
            },
            "operations": {
                "Turn_ON": "blinding_ON",
            },
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
            "length": 16,
            "digital_marker": "ON",
        },
        "blinding_ON": {
            "operation": "control",
            "length": 24,
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "operation": "measurement",
            "length": 96,
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
                    "delay": 0,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
                "2": {
                    "offset": 0.0,
                    "delay": 0,
                    "shareable": False,
                    "filter": {
                        "feedforward": [],
                        "feedback": [],
                    },
                    "crosstalk": {},
                },
                "3": {
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
                "2": {
                    "offset": 0.00979,
                    "gain_db": -12,
                    "shareable": False,
                    "sampling_rate": 1000000000.0,
                },
            },
            "digital_outputs": {
                "1": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "2": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "3": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "6": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
                "8": {
                    "shareable": False,
                    "inverted": False,
                    "level": "LVTTL",
                },
            },
            "digital_inputs": {},
        },
    },
    "oscillators": {},
    "elements": {
        "MW": {
            "digitalInputs": {
                "marker": {
                    "delay": 0,
                    "buffer": 0,
                    "port": ('con1', 1, 2),
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
                "I": ('con1', 1, 2),
                "Q": ('con1', 1, 3),
                "mixer": "mixer_NV",
                "lo_frequency": 2700000000.0,
            },
            "intermediate_frequency": 124000000.0,
        },
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 0,
                    "buffer": 0,
                    "port": ('con1', 1, 1),
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
        "Resonant_Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 0,
                    "buffer": 0,
                    "port": ('con1', 1, 8),
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
                    "delay": 0,
                    "buffer": 0,
                    "port": ('con1', 1, 2),
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
            "digitalInputs": {
                "marker": {
                    "delay": 28,
                    "buffer": 0,
                    "port": ('con1', 1, 3),
                },
            },
            "digitalOutputs": {},
            "outputs": {
                "out1": ('con1', 1, 1),
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
            "time_of_flight": 28,
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
            "time_of_flight": 28,
        },
        "Blinding": {
            "digitalInputs": {
                "marker": {
                    "delay": 0,
                    "buffer": 0,
                    "port": ('con1', 1, 6),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "Turn_ON": "blinding_ON",
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
            "length": 16,
            "waveforms": {},
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "blinding_ON": {
            "length": 24,
            "waveforms": {},
            "integration_weights": {},
            "operation": "control",
            "digital_marker": "ON",
        },
        "readout_pulse": {
            "length": 96,
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



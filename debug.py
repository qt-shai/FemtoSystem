
# Single QUA script generated at 2025-02-26 10:09:48.067401
# QUA library version: 1.2.1

from qm import CompilerOptionArguments
from qm.qua import *

with program() as prog:
    v1 = declare(int, )
    a1 = declare(int, size=100)
    a2 = declare(int, size=100)
    v2 = declare(int, )
    v3 = declare(int, )
    v4 = declare(fixed, )
    v5 = declare(int, )
    v6 = declare(int, )
    v7 = declare(int, )
    v8 = declare(int, )
    v9 = declare(int, )
    v10 = declare(int, )
    v11 = declare(int, )
    v12 = declare(int, )
    v13 = declare(int, )
    v14 = declare(bool, value=True)
    v15 = declare(int, value=0)
    v16 = declare(int, )
    v17 = declare(int, value=0)
    v18 = declare(int, value=0)
    a3 = declare(int, size=15)
    a4 = declare(int, size=15)
    a5 = declare(int, size=15)
    a6 = declare(int, size=15)
    a7 = declare(int, value=[0, 200000, 400000, 600000, 800000, 1000000, 1200000, 1400000, 1600000, 1800000, 2000000, 2200000, 2400000, 2600000, 2800000, 3000000, 3200000, 3400000, 3600000, 3800000, 4000000, 4200000, 4400000, 4600000, 4800000, 5000000, 5200000, 5400000, 5600000, 5800000, 6000000])
    a8 = declare(int, value=[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14])
    v19 = declare(int, )
    v20 = declare(int, )
    v21 = declare(int, )
    v22 = declare(int, )
    v23 = declare(int, value=127847534)
    with for_(v1,0,(v1<10000000),(v1+1)):
        with for_(v19,0,(v19<15),(v19+1)):
            assign(a5[v19], 0)
            assign(a4[v19], 0)
            assign(a3[v19], 0)
            assign(a6[v19], 0)
        with if_(False):
            with for_(v22,0,(v22<1),(v22+1)):
                assign(v21, call_library_function('random', 'rand_int', [v23,(1-v22)]))
                assign(v20, a8[v21])
                assign(a8[v21], a8[(0-v22)])
                assign(a8[(0-v22)], v20)
        with for_(v19,0,(v19<1),(v19+1)):
            assign(v18, IO1)
            with if_((v18==0)):
                with for_(v9,4,(v9<5),(v9+1)):
                    with for_(v7,0,(v7<15),(v7+1)):
                        assign(v6, ((v9*0)+v7))
                        align()
                        play("Turn_ON", "Laser", duration=100)
                        align()
                        wait(12, )
                        with if_((v9==0)):
                            with for_(v5,0,(v5<1),(v5+1)):
                                align()
                                update_frequency("MW", 979999.9999997588, "Hz", False)
                                update_frequency("RF", 3018230.0, "Hz", False)
                                play("xPulse"*amp(0.72), "MW", duration=58)
                                align("MW", "RF")
                                play("const"*amp(0.12), "RF", duration=12250)
                                align("RF", "Laser")
                                play("Turn_ON", "Laser", duration=100)
                                align()
                                wait(12, )
                            align()
                            wait(58, )
                        with if_((v9==1)):
                            with for_(v5,0,(v5<1),(v5+1)):
                                align()
                                update_frequency("MW", 4020000.0000001346, "Hz", False)
                                update_frequency("RF", 3018230.0, "Hz", False)
                                play("xPulse"*amp(0.72), "MW", duration=58)
                                align("MW", "RF")
                                play("const"*amp(0.12), "RF", duration=12250)
                                align("RF", "Laser")
                                play("Turn_ON", "Laser", duration=100)
                                align()
                                wait(12, )
                            align()
                            wait(58, )
                        with if_((v9==2)):
                            with for_(v5,0,(v5<1),(v5+1)):
                                align()
                                update_frequency("MW", 979999.9999997588, "Hz", False)
                                update_frequency("RF", 3018230.0, "Hz", False)
                                play("xPulse"*amp(0.72), "MW", duration=58)
                                align("MW", "RF")
                                play("const"*amp(0.12), "RF", duration=12250)
                                align("RF", "Laser")
                                play("Turn_ON", "Laser", duration=100)
                                align()
                                wait(12, )
                            align()
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_((v9==3)):
                            with for_(v5,0,(v5<1),(v5+1)):
                                align()
                                update_frequency("MW", 4020000.0000001346, "Hz", False)
                                update_frequency("RF", 3018230.0, "Hz", False)
                                play("xPulse"*amp(0.72), "MW", duration=58)
                                align("MW", "RF")
                                play("const"*amp(0.12), "RF", duration=12250)
                                align("RF", "Laser")
                                play("Turn_ON", "Laser", duration=100)
                                align()
                                wait(12, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_((v9==4)):
                            with for_(v5,0,(v5<1),(v5+1)):
                                align()
                                update_frequency("MW", 979999.9999997588, "Hz", False)
                                update_frequency("RF", 3018230.0, "Hz", False)
                                play("xPulse"*amp(0.72), "MW", duration=58)
                                align("MW", "RF")
                                play("const"*amp(0.12), "RF", duration=12250)
                                align("RF", "Laser")
                                play("Turn_ON", "Laser", duration=100)
                                align()
                                wait(12, )
                            align()
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            frame_rotation_2pi(0.25, "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            frame_rotation_2pi(-0.25, "RF")
                        align()
                        wait(58, )
                        align()
                        with if_(((v7+1)==1)):
                            wait(12366, )
                        with if_(((v7+1)==2)):
                            wait(12308, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==3)):
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            play("const"*amp(0.12), "RF", duration=12250)
                            align("RF", "MW")
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==4)):
                            update_frequency("MW", 2499999.999999947, "Hz", False)
                            play("yPulse"*amp(1.0), "MW", duration=32.0)
                            play("-yPulse"*amp(1.0), "MW", duration=32.0)
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            wait(12244, )
                        with if_(((v7+1)==5)):
                            update_frequency("MW", 2499999.999999947, "Hz", False)
                            play("yPulse"*amp(1.0), "MW", duration=32.0)
                            play("-yPulse"*amp(1.0), "MW", duration=32.0)
                            wait(12302, )
                        with if_(((v7+1)==6)):
                            update_frequency("MW", 2499999.999999947, "Hz", False)
                            play("xPulse"*amp(1.0), "MW", duration=32.0)
                            play("-xPulse"*amp(1.0), "MW", duration=32.0)
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            wait(12244, )
                        with if_(((v7+1)==7)):
                            update_frequency("MW", 2499999.999999947, "Hz", False)
                            play("xPulse"*amp(1.0), "MW", duration=32.0)
                            play("-xPulse"*amp(1.0), "MW", duration=32.0)
                            wait(12302, )
                        with if_(((v7+1)==8)):
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            wait(6183, )
                            align("RF", "MW")
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==9)):
                            frame_rotation_2pi(0.25, "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            frame_rotation_2pi(-0.25, "RF")
                            align("RF", "MW")
                            wait(6183, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==10)):
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            align("RF", "MW")
                            wait(6067, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==11)):
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            frame_rotation_2pi(0.25, "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            frame_rotation_2pi(-0.25, "RF")
                            align("RF", "MW")
                            wait(6067, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==12)):
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            wait(6125, )
                            align("RF", "MW")
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==13)):
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            frame_rotation_2pi(0.25, "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            frame_rotation_2pi(-0.25, "RF")
                            align("RF", "MW")
                            wait(6125, )
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==14)):
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            align("RF", "MW")
                            wait(6125, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        with if_(((v7+1)==15)):
                            update_frequency("MW", 4020000.0000001346, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                            align("MW", "RF")
                            frame_rotation_2pi(0.25, "RF")
                            play("const"*amp(0.12), "RF", duration=6125.0)
                            frame_rotation_2pi(-0.25, "RF")
                            align("RF", "MW")
                            wait(6125, )
                            update_frequency("MW", 979999.9999997588, "Hz", False)
                            play("xPulse"*amp(0.72), "MW", duration=29.0)
                            play("-xPulse"*amp(0.72), "MW", duration=29.0)
                        align()
                        play("Turn_ON", "Laser", duration=100)
                        measure("readout", "Detector_OPD", None, time_tagging.digital(a2, 300, v11, ""))
                        assign(a3[v6], (a3[v6]+v11))
                        align()
                        wait(12320, )
                        play("Turn_ON", "Laser", duration=100)
                        align()
                        wait(18619, )
                        align()
                        play("Turn_ON", "Laser", duration=100)
                        measure("readout", "Detector_OPD", None, time_tagging.digital(a2, 300, v12, ""))
                        assign(a4[v6], (a4[v6]+v12))
                        align()
                        wait(12320, )
                        play("Turn_ON", "Laser", duration=100)
                        align()
                        wait(18555, )
                        align()
                        update_frequency("MW", 979999.9999997588, "Hz", False)
                        play("xPulse"*amp(0.72), "MW", duration=32)
                        play("-xPulse"*amp(0.72), "MW", duration=32)
                        update_frequency("MW", 4020000.0000001346, "Hz", False)
                        play("xPulse"*amp(0.72), "MW", duration=32)
                        play("-xPulse"*amp(0.72), "MW", duration=32)
                        align()
                        play("Turn_ON", "Laser", duration=100)
                        measure("readout", "Detector_OPD", None, time_tagging.digital(a2, 300, v13, ""))
                        assign(a5[v6], (a5[v6]+v13))
                with for_(v6,0,(v6<15),(v6+1)):
                    assign(a6[v6], (((a3[v6]-a5[v6])*1000000)/(a5[v6]-a4[v6])))
            with else_():
                assign(v17, 0)
                with for_(v19,0,(v19<5000),(v19+1)):
                    play("Turn_ON", "Laser", duration=2500)
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(a2, 10000, v16, ""))
                    assign(v17, (v17+v16))
                align()
        with if_(v14):
            assign(v15, (v15+1))
            with if_((v15>101558)):
                assign(v17, 0)
                with for_(v19,0,(v19<5000),(v19+1)):
                    play("Turn_ON", "Laser", duration=2500)
                    measure("min_readout", "Detector_OPD", None, time_tagging.digital(a2, 10000, v16, ""))
                    assign(v17, (v17+v16))
                assign(v15, 0)
        with if_((v18==0)):
            with for_(v19,0,(v19<15),(v19+1)):
                r3 = declare_stream()
                save(a3[v19], r3)
                r4 = declare_stream()
                save(a4[v19], r4)
                r5 = declare_stream()
                save(a5[v19], r5)
                r6 = declare_stream()
                save(a6[v19], r6)
        r1 = declare_stream()
        save(v1, r1)
        r2 = declare_stream()
        save(v17, r2)
    with stream_processing():
        r3.buffer(15).average().save("counts")
        r4.buffer(15).average().save("counts_ref")
        r5.buffer(15).average().save("counts_ref2")
        r6.buffer(15).average().save("resCalculated")
        r1.save("iteration")
        r2.save("tracking_ref")


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
                    "delay": 8,
                    "shareable": False,
                },
            },
            "digital_outputs": {
                "2": {
                    "shareable": False,
                },
                "3": {
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
                "1": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1,
                    "shareable": False,
                },
                "2": {
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
                "port": ('con1', 3),
            },
            "intermediate_frequency": 3030000.0,
            "operations": {
                "const": "const_pulse_single",
            },
        },
        "MW": {
            "mixInputs": {
                "I": ('con1', 1),
                "Q": ('con1', 2),
                "lo_frequency": 2700000000.0,
                "mixer": "mixer_NV",
            },
            "intermediate_frequency": 124000000.0,
            "digitalInputs": {
                "marker": {
                    "port": ('con1', 2),
                    "delay": 94,
                    "buffer": 0,
                },
            },
            "operations": {
                "xPulse": "x_pulse",
                "-xPulse": "-x_pulse",
                "yPulse": "y_pulse",
                "-yPulse": "-y_pulse",
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
                    "port": ('con1', 3),
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
                    "port": ('con1', 2),
                    "delay": 94,
                    "buffer": 0,
                },
            },
            "operations": {
                "ON": "switch_ON",
            },
        },
        "Detector": {
            "singleInput": {
                "port": ('con1', 1),
            },
            "digitalInputs": {},
            "operations": {
                "readout": "readout_pulse",
                "long_readout": "long_readout_pulse",
            },
            "outputs": {
                "out1": ('con1', 1),
            },
            "outputPulseParameters": {
                "signalThreshold": -400,
                "signalPolarity": "Descending",
                "derivativeThreshold": 1023,
                "derivativePolarity": "Descending",
            },
            "time_of_flight": 112,
            "smearing": 0,
        },
        "Detector_OPD": {
            "singleInput": {
                "port": ('con1', 1),
            },
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 1),
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
                "port": ('con1', 1),
            },
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 2),
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
        "-x_pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "I": "-cw_wf",
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
        "-y_pulse": {
            "operation": "control",
            "length": 100,
            "waveforms": {
                "I": "zero_wf",
                "Q": "-cw_wf",
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
        "-cw_wf": {
            "type": "constant",
            "sample": -0.5,
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
                    "delay": 8,
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
            },
            "digital_inputs": {
                "1": {
                    "polarity": "RISING",
                    "deadtime": 4,
                    "threshold": 1.0,
                    "shareable": False,
                },
                "2": {
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
                "port": ('con1', 1, 3),
            },
            "intermediate_frequency": 3030000.0,
        },
        "MW": {
            "digitalInputs": {
                "marker": {
                    "delay": 94,
                    "buffer": 0,
                    "port": ('con1', 1, 2),
                },
            },
            "digitalOutputs": {},
            "outputs": {},
            "operations": {
                "xPulse": "x_pulse",
                "-xPulse": "-x_pulse",
                "yPulse": "y_pulse",
                "-yPulse": "-y_pulse",
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
                "I": ('con1', 1, 1),
                "Q": ('con1', 1, 2),
                "mixer": "mixer_NV",
                "lo_frequency": 2700000000.0,
            },
            "intermediate_frequency": 124000000.0,
        },
        "Laser": {
            "digitalInputs": {
                "marker": {
                    "delay": 120,
                    "buffer": 0,
                    "port": ('con1', 1, 3),
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
                    "delay": 94,
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
        "Detector": {
            "digitalInputs": {},
            "digitalOutputs": {},
            "outputs": {
                "out1": ('con1', 1, 1),
            },
            "operations": {
                "readout": "readout_pulse",
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
        "Detector_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 1, 1),
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
                "port": ('con1', 1, 1),
            },
            "smearing": 0,
            "time_of_flight": 308,
        },
        "Detector2_OPD": {
            "digitalInputs": {},
            "digitalOutputs": {
                "out1": ('con1', 1, 2),
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
                "port": ('con1', 1, 1),
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
        "-x_pulse": {
            "length": 100,
            "waveforms": {
                "I": "-cw_wf",
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
        "-y_pulse": {
            "length": 100,
            "waveforms": {
                "I": "zero_wf",
                "Q": "-cw_wf",
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
        "-cw_wf": {
            "type": "constant",
            "sample": -0.5,
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



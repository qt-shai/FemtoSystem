from typing import Dict, Any
from SystemConfig import SystemType
from SystemConfig.QuaConfigs import QUAConfigBase


class AttoQuaConfig(QUAConfigBase):
    """
    Configuration class for the Atto system, which replicates all the capabilities of the HotSystem
    using new channels that have not been used before, and adds three additional analog channels
    for controlling the x, y, z voltages of the atto_scanner.

    This class ensures that only new channels are used, up to the total of 10 analog channels
    and 10 digital channels. The SmaractTrigger and the regular Detector have been dropped,
    and only Detector_OPD is retained as per the latest requirements.
    """

    def __init__(self) -> None:
        """
        Initialize the AttoQuaConfig with default parameters.
        """
        super().__init__()
        # todo: updates parameters (delays, wave forums, ...) per CFG
        self.scannerX_delay = 0
        self.scannerY_delay = 0
        self.phaseEOM_delay = 0
        self.system_name:str = SystemType.ATTO.value

    def get_controllers(self) -> Dict[str, Any]:
        """
        Returns the controller configuration for the Atto system.

        :return: Dictionary containing controller configurations.
        """
        controllers = {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    4: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW I
                    5: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW Q
                    6: {"offset": 0.0, "delay": self.rf_delay, "shareable": False},  # RF
                    9: {"offset": 0.0, "delay": self.phaseEOM_delay, "shareable": False},              # Phase EOM
                },
                "digital_outputs": {
                    3: {"shareable": False},  # trigger AWG
                    4: {"shareable": False},  # trigger Laser (Cobolt)
                    5: {"shareable": False},  # trigger MW (Rohde Schwarz)
                    7: {"shareable": False},  # trigger Resonant Laser
                },
                "analog_inputs": {
                    2: {"offset": 0.00979, "gain_db": 0, "shareable": False}, # QM: why? because
                },
                "digital_inputs": { # counter 1
                    4: {
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": False,
                    },
                    5: { # counter 2
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": False,
                    },

                },
            }
        }
        return controllers

    def get_elements(self) -> Dict[str, Any]:
        """
        Returns the elements configuration for the Atto system.

        :return: Dictionary containing element configurations.
        """
        elements = {
            self.Elements.RF.value: {
                "singleInput": {"port": ("con1", 6)},  # Analog output 6
                "intermediate_frequency": self.rf_frequency,
                "operations": {"const": "const_pulse_single"},
            },
            self.Elements.MW.value: {
                "mixInputs": {
                    "I": ("con1", 4),  # Analog output 4
                    "Q": ("con1", 5),  # Analog output 5
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": { # 'digitalInputs' is actually 'digital_outputs'. MW switch (ON/OFF)
                    "marker": {
                        "port": ("con1", 5),  # Digital output 9
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
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
            self.Elements.AWG_TRigger.value: {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 3),  # Digital output 4
                        "delay": 0,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.RESONANT_LASER.value: {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 7),  # Digital output 4
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.LASER.value: {
                "digitalInputs": { # here it is actually outputs
                    "marker": {
                        "port": ("con1", 4),  # Digital output 4
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.MW_SWITCH.value: {
                "digitalInputs": { # here it is actually outputs
                    "marker": {
                        "port": ("con1", 5),  # Digital output 5
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {"ON": "switch_ON"},
            },
            # "Amplitude_EOM": {
            #     "digitalInputs": { # here it is actually outputs
            #         "marker": {
            #             "port": ("con1", 8),  # Digital output 8
            #             "delay": self.switch_delay,
            #             "buffer": self.switch_buffer,
            #         },
            #     },
            #     "operations": {"ON": "switch_ON"},
            # },
            self.Elements.DETECTOR_OPD.value: {
                "singleInput": {"port": ("con1", 4)},  # analoge outputs, not used
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 10),  # Digital output 10
                    #     "delay": self.detection_delay_OPD,
                    #     "buffer": 0,
                    # },
                },
                "digitalOutputs": {"out1": ("con1", 4)},  # 'digitalOutputs' here is actually 'digital input' of OPD
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
            self.Elements.DETECTOR2_OPD.value: {
                "singleInput": {"port": ("con1", 4)},  # not used
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 10),  # Digital output 10
                    #     "delay": self.detection_delay_OPD,
                    #     "buffer": 0,
                    # },
                },
                "digitalOutputs": {"out1": ("con1", 5)},  # 'digitalOutputs' here is actually 'digital input' of OPD
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
            # Atto scanner control elements
            # "atto_scanner_x": {
            #     "singleInput": {"port": ("con1", 7)},  # actually analog output 7
            #     "operations": {"set_voltage": "atto_set_voltage_pulse"},
            # },
            # "atto_scanner_y": {
            #     "singleInput": {"port": ("con1", 8)},  # actually analog output 8
            #     "operations": {"set_voltage": "atto_set_voltage_pulse"},
            # },
        }
        return elements

    def get_pulses(self) -> Dict[str, Any]:
        """
        Returns the pulses configuration for the Atto system.

        :return: Dictionary containing pulse configurations.
        """
        pulses = super().get_pulses()
        pulses["atto_set_voltage_pulse"] = {
            "operation": "control",
            "length": 16,  # Minimal pulse length
            "waveforms": {"single": "zero_wf"},
        }
        return pulses

from typing import Dict, Any
import SystemConfig.QuaConfigs as configs
from SystemConfig import SystemType


class SimulatorQuaConfig(configs.QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()
        # Readout parameters
        self.resonant_laser_delay = 0  # Todo: change to physical number
        self.scannerX_delay = 0
        self.scannerY_delay = 0
        self.phaseEOM_delay = 0

    def get_controllers(self) -> Dict[str, Any]:
        """
        Returns the controller configuration for the Atto system.

        :return: Dictionary containing controller configurations.
        """
        controllers = {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    2: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW I
                    3: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW Q
                },
                "digital_outputs": {
                    1: {"shareable": False},  # trigger Laser (Cobolt)
                    2: {"shareable": False},  # trigger MW (Rohde Schwarz)
                    8: {"shareable": False},  # trigger for the Resonant Laser
                },
                "analog_inputs": {
                    #Not used, so can be in everyone configuration file
                    2: {"offset": 0.00979, "gain_db": 0, "shareable": False},# QM: why? because
                },
                "digital_inputs": {  # counter 1
                    4: {
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": False,
                    },
                    5: {  # counter 2
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
            "MW": {
                "mixInputs": {
                    "I": ("con1", 2),  # Analog output 4
                    "Q": ("con1", 3),  # Analog output 5
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": {  # 'digitalInputs' is actually 'digital_outputs'. MW switch (ON/OFF)
                    "marker": {
                        "port": ("con1", 3),  # Digital output 9
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
            "Laser": {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 1),  # Digital output 4
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            "resonant_laser": {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 8),  # Digital output 4
                        "delay": self.resonant_laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            "MW_switch": {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 2),  # Digital output 5
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {"ON": "switch_ON"},
            },
            "Detector_OPD": {
                "singleInput": {"port": ("con1", 4)},  # analog outputs, not used
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
            "Detector2_OPD": {
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

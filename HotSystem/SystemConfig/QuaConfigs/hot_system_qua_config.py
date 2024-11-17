from typing import Dict, Any
from SystemConfig.QuaConfigs import QUAConfigBase


class HotSystemQuaConfig(QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()


    def get_controllers(self) -> Dict[str, Any]:
        return {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    1: {"offset": 0.0, "delay": self.mw_delay, "shareable": True}, # MW I, for unknonw reason need to be in all system
                    2: {"offset": 0.0, "delay": self.mw_delay, "shareable": False}, # MW Q
                    3: {"offset": 0.0, "delay": self.rf_delay, "shareable": False}, # RF
                },
                "digital_outputs": {
                    1: {"shareable": True}, # laser 520nm
                    2: {"shareable": True}, # trigger MW
                },
                "analog_inputs": {
                    1: {"offset": 0.00979, "gain_db": 0, "shareable": False}, # for unknonw reason need to be in all system
                },
                "digital_inputs": {
                    1: {
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": True,
                    },
                    3: {
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": True,
                    },
                },
            }
        }

    def get_elements(self) -> Dict[str, Any]:
        return {
            "RF": {
                "singleInput": {"port": ("con1", 3)}, # analog out
                "intermediate_frequency": self.rf_frequency,
                "operations": {
                    "const": "const_pulse_single",
                },
            },
            "MW": {
                "mixInputs": {
                    "I": ("con1", 1), # analog out
                    "Q": ("con1", 2), # analog out
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": { # 'digitalInputs' is actually 'digital_outputs'. MW switch (ON/OFF)
                    "marker": {
                        "port": ("con1", 2), # digital out
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
                "digitalInputs": { # actually outputs
                    "marker": {
                        "port": ("con1", 1), # digital out
                        "delay": self.laser_delay,
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
                        "port": ("con1", 2), # digital out
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {
                    "ON": "switch_ON",
                },
            },
            "Detector": {
                "singleInput": {"port": ("con1", 1)}, # unknown why needed?
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 3),
                    #     "delay": self.detection_delay,
                    #     "buffer": 0,
                    # },
                },
                "operations": {
                    "readout": "readout_pulse",
                    "long_readout": "long_readout_pulse",
                },
                "outputs": {"out1": ("con1", 1)}, # analoge in
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
                "singleInput": {"port": ("con1", 1)}, # unknown why needed?
                "digitalInputs": {
                },
                "digitalOutputs": {"out1": ("con1", 1)}, # 'digital input' of OPD
                "outputs": {"out1": ("con1", 1)}, # unknown why needed?
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
                "singleInput": {"port": ("con1", 1)},  # unknown why needed?
                "digitalInputs": {
                },
                "digitalOutputs": {"out1": ("con1", 3)},  # 'digital input' of OPD
                "outputs": {"out1": ("con1", 1)}, # unknown why needed?
                "operations": {
                    "readout": "readout_pulse",
                    "min_readout": "min_readout_pulse",
                    "long_readout": "long_readout_pulse",
                    "very_long_readout": "very_long_readout_pulse",
                },
                "time_of_flight": self.detection_delay_OPD,
                "smearing": 0,
            },
        }
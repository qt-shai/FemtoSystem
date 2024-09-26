from typing import Dict, Any
from SystemConfig.QuaConfigs import QUAConfigBase


class HotSystemQuaConfig(QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()

        # Frequencies
        self.NV_IF_freq = 124e6  # in units of Hz
        self.NV_LO_freq = 2.7e9  # in units of Hz

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
        self.switch_delay = 94  # in ns
        self.switch_buffer = 0  # in ns
        self.switch_len = 100  # in ns

        # Readout parameters
        self.signal_threshold = -400  # in ADC units
        self.signal_threshold_OPD = 0.1  # in voltage

        # Delays
        self.detection_delay = 112  # ns
        self.detection_delay_OPD = 308
        self.mw_delay = 0  # ns
        self.laser_delay = 120  # ns

        # RF parameters
        self.rf_frequency = 3.03 * self.u.MHz
        self.rf_amp = 0.1
        self.rf_length = 1000
        self.rf_delay = 8  # ns

    def get_controllers(self) -> Dict[str, Any]:
        return {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    1: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},
                    2: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},
                    3: {"offset": 0.0, "delay": self.rf_delay, "shareable": True},
                },
                "digital_outputs": {
                    1: {"shareable": True},
                    2: {"shareable": True},
                    3: {"shareable": True},
                    4: {"shareable": True},
                },
                "analog_inputs": {
                    1: {"offset": 0.00979, "gain_db": 0, "shareable": True},
                },
                "digital_inputs": {
                    1: {
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
                "singleInput": {"port": ("con1", 3)},
                "intermediate_frequency": self.rf_frequency,
                "operations": {
                    "const": "const_pulse_single",
                },
            },
            "MW": {
                "mixInputs": {
                    "I": ("con1", 1),
                    "Q": ("con1", 2),
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 2),
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {
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
                        "port": ("con1", 1),
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {
                    "Turn_ON": "laser_ON",
                },
            },
            "SmaractTrigger": {
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 4),
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
                        "port": ("con1", 2),
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {
                    "ON": "switch_ON",
                },
            },
            "Detector": {
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 3),
                        "delay": self.detection_delay,
                        "buffer": 0,
                    },
                },
                "operations": {
                    "readout": "readout_pulse",
                    "long_readout": "long_readout_pulse",
                },
                "outputs": {"out1": ("con1", 1)},
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
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 3),
                        "delay": self.detection_delay_OPD,
                        "buffer": 0,
                    },
                },
                "digitalOutputs": {"out1": ("con1", 1)},
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
        }
from typing import Dict, Any
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

    def get_controllers(self) -> Dict[str, Any]:
        """
        Returns the controller configuration for the Atto system.

        :return: Dictionary containing controller configurations.
        """
        controllers = {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    4: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},  # MW I
                    5: {"offset": 0.0, "delay": self.mw_delay, "shareable": True},  # MW Q
                    6: {"offset": 0.0, "delay": self.rf_delay, "shareable": True},  # RF
                    7: {"offset": 0.0, "delay": 0, "shareable": True},              # Atto scanner X
                    8: {"offset": 0.0, "delay": 0, "shareable": True},              # Atto scanner Y
                    9: {"offset": 0.0, "delay": 0, "shareable": True},              # Atto scanner Z
                    # Analog output 10 is still available
                },
                "digital_outputs": {
                    5: {"shareable": True},  # Laser
                    9: {"shareable": True},  # MW_switch
                    10: {"shareable": True},  # Detector_OPD marker
                    # Digital outputs 1-4 and 6-8 are used by other systems
                },
                "analog_inputs": {
                    3: {"offset": 0.00979, "gain_db": 0, "shareable": True},  # Detector_OPD
                    # Analog inputs 1 and 2 are used by other systems
                },
                "digital_inputs": {
                    3: {
                        "polarity": "RISING",
                        "deadtime": 4,
                        "threshold": self.signal_threshold_OPD,
                        "shareable": True,
                    },
                    # Digital inputs 1 and 2 are used by other systems
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
            "RF": {
                "singleInput": {"port": ("con1", 6)},  # Analog output 6
                "intermediate_frequency": self.rf_frequency,
                "operations": {"const": "const_pulse_single"},
            },
            "MW": {
                "mixInputs": {
                    "I": ("con1", 4),  # Analog output 4
                    "Q": ("con1", 5),  # Analog output 5
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 9),  # Digital output 9
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
                        "port": ("con1", 5),  # Digital output 5
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            "MW_switch": {
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 9),  # Digital output 9
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {"ON": "switch_ON"},
            },
            "Detector_OPD": {
                "singleInput": {"port": ("con1", 3)},  # Analog input 3
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 10),  # Digital output 10
                        "delay": self.detection_delay_OPD,
                        "buffer": 0,
                    },
                },
                "digitalOutputs": {"out1": ("con1", 3)},  # Digital input/output 3
                "outputs": {"out1": ("con1", 3)},  # Analog input 3
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
            "atto_scanner_x": {
                "singleInput": {"port": ("con1", 7)},  # Analog output 7
                "operations": {"set_voltage": "atto_set_voltage_pulse"},
            },
            "atto_scanner_y": {
                "singleInput": {"port": ("con1", 8)},  # Analog output 8
                "operations": {"set_voltage": "atto_set_voltage_pulse"},
            },
            "atto_scanner_z": {
                "singleInput": {"port": ("con1", 9)},  # Analog output 9
                "operations": {"set_voltage": "atto_set_voltage_pulse"},
            },
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

    def get_waveforms(self) -> Dict[str, Any]:
        """
        Returns the waveforms configuration for the Atto system.

        :return: Dictionary containing waveform configurations.
        """
        waveforms = super().get_waveforms()
        # No new waveforms needed; use existing zero_wf
        return waveforms

    def get_config(self) -> Dict[str, Any]:
        """
        Returns the full configuration dictionary for the Atto system.

        :return: Dictionary containing the full configuration.
        """
        config = {
            "version": self.get_version(),
            "controllers": self.get_controllers(),
            "elements": self.get_elements(),
            "pulses": self.get_pulses(),
            "waveforms": self.get_waveforms(),
            "digital_waveforms": self.get_digital_waveforms(),
            "mixers": self.get_mixers(),
        }
        return config

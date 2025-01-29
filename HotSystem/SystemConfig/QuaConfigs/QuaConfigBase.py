from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, Any, Optional
from qualang_tools.units import unit
from enum import Enum
from typing import Dict, Any

class QUAConfigBase(ABC):
    class Elements(Enum):
        RF = "RF"
        MW = "MW"
        LASER = "Laser"
        MW_SWITCH = "MW_switch"
        DETECTOR_OPD = "Detector_OPD"
        DETECTOR2_OPD = "Detector2_OPD"
        AMPLITUDE_EOM = "Amplitude_EOM"
        RESONANT_LASER = "Resonant_Laser"
        BLINDING = "Blinding"
        
    def __init__(self):
        # connect     
        self.system_name: Optional[str] = None
        self.u = unit()
        
        # Frequencies
        self.NV_IF_freq = 124e6  # in units of Hz
        self.NV_LO_freq = 2.7e9  # in units of Hz

        # Pulses lengths
        self.initialization_len = 5000  # in ns
        self.meas_len = 300  # in ns
        self.minimal_meas_len = 16  # in ns
        self.long_meas_len = 5e3  # in ns
        self.very_long_meas_len = 25e3  # in ns
        self.blinding_length = 24 # in ns

        # MW parameters
        self.mw_amp_NV = 0.5  # in units of volts
        self.mw_len_NV = 100  # in units of ns

        self.pi_amp_NV = 0.5  # in units of volts
        self.pi_len_NV = 16  # in units of ns

        self.pi_half_amp_NV = self.pi_amp_NV / 2  # in units of volts
        self.pi_half_len_NV = self.pi_len_NV  # in units of ns

        # MW Switch parameters
        self.switch_delay = 122  # in ns
        self.switch_buffer = 0  # in ns
        self.switch_len = 100  # in ns

        # Readout parameters
        self.signal_threshold = -400  # in ADC units 
        self.signal_threshold_OPD = 1 # in voltage (with 20dB attenuation it was 0.1)

        # Delays
        self.detection_delay = 28 # ns
        self.detection_delay_OPD = 308
        self.mw_delay = 0  # ns
        self.laser_delay = 120  # ns

        # RF parameters
        self.rf_frequency = 3.03 * self.u.MHz
        self.rf_amp = 0.5
        self.rf_length = 1000
        self.rf_delay = 8  # ns


    @staticmethod
    def iq_imbalance(g, phi):
        """
        Creates the correction matrix for the mixer imbalance caused by the gain and phase imbalances.

        :param g: relative gain imbalance between the "I" & "Q" ports (unit-less). Set to 0 for no gain imbalance.
        :param phi: relative phase imbalance between the "I" & "Q" ports (radians). Set to 0 for no phase imbalance.
        """
        c = np.cos(phi)
        s = np.sin(phi)
        n = 1 / ((1 - g ** 2) * (2 * c ** 2 - 1))
        return [float(n * x) for x in [(1 - g) * c, (1 + g) * s, (1 - g) * s, (1 + g) * c]]

    @staticmethod
    def get_version() -> int:
        return 1

    @abstractmethod
    def get_controllers(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_elements(self) -> Dict[str, Any]:
        pass

    def get_pulses(self) -> Dict[str, Any]:
        return {
            "const_pulse_single": {
                "operation": "control",
                "length": self.rf_length,  # in ns
                "waveforms": {"single": "rf_const_wf"},
            },
            "x_pulse": {
                "operation": "control",
                "length": self.mw_len_NV,
                "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
                "digital_marker": "ON",  # 'ON' is digital waveform name
            },
            "y_pulse": {
                "operation": "control",
                "length": self.mw_len_NV,
                "waveforms": {"I": "zero_wf", "Q": "cw_wf"},  # 'cw_wf' is analog waveform name
                "digital_marker": "ON",  # 'ON' is digital waveform name
            },
            "const_pulse": {
                "operation": "control",
                "length": self.mw_len_NV,
                "waveforms": {"I": "cw_wf", "Q": "zero_wf"},  # 'cw_wf' is analog waveform name
                "digital_marker": "ON",  # 'ON' is digital waveform name
            },
            "x180_pulse": {
                "operation": "control",
                "length": self.pi_len_NV,
                "waveforms": {"I": "pi_wf", "Q": "zero_wf"},
                "digital_marker": "ON",
            },
            "x90_pulse": {
                "operation": "control",
                "length": self.pi_half_len_NV,
                "waveforms": {"I": "pi_half_wf", "Q": "zero_wf"},
                "digital_marker": "ON",
            },
            "-x90_pulse": {
                "operation": "control",
                "length": self.pi_half_len_NV,
                "waveforms": {"I": "-pi_half_wf", "Q": "zero_wf"},
                "digital_marker": "ON",
            },
            "y180_pulse": {
                "operation": "control",
                "length": self.pi_len_NV,
                "waveforms": {"I": "zero_wf", "Q": "pi_wf"},
                "digital_marker": "ON",
            },
            "y90_pulse": {
                "operation": "control",
                "length": self.pi_half_len_NV,
                "waveforms": {"I": "zero_wf", "Q": "pi_half_wf"},
                "digital_marker": "ON",
            },
            "laser_ON": {
                "operation": "control",
                "length": self.initialization_len,
                "digital_marker": "ON",
            },                
            "switch_ON": {
                "operation": "control",
                "length": self.switch_len,
                "digital_marker": "ON",
            },
            "blinding_ON": {
                "operation": "control",
                "length": self.blinding_length,
                "digital_marker": "ON",
            },
            "readout_pulse": {
                "operation": "measurement",
                "length": self.meas_len,
                "digital_marker": "ON",
                "waveforms": {"single": "zero_wf"},
            },
            "min_readout_pulse": {
                "operation": "measurement",
                "length": self.minimal_meas_len,
                "digital_marker": "ON",
                "waveforms": {"single": "zero_wf"},
            },
            "long_readout_pulse": {
                "operation": "measurement",
                "length": self.long_meas_len,
                "digital_marker": "ON",
                "waveforms": {"single": "zero_wf"},
            },
            "very_long_readout_pulse": {
                "operation": "measurement",
                "length": self.very_long_meas_len,
                "digital_marker": "ON",
                "waveforms": {"single": "zero_wf"},
            },                
        }

    def get_waveforms(self) -> Dict[str, Any]:
        return {
            "rf_const_wf": {"type": "constant", "sample": self.rf_amp},
            "cw_wf": {"type": "constant", "sample": self.mw_amp_NV},
            "pi_wf": {"type": "constant", "sample": self.pi_amp_NV},
            "pi_half_wf": {"type": "constant", "sample": self.pi_half_amp_NV},
            "-pi_half_wf": {"type": "constant", "sample": -self.pi_half_amp_NV},
            "zero_wf": {"type": "constant", "sample": 0.0},
        }

    def get_digital_waveforms(self) -> Dict[str, Any]:
        return {
            "ON": {"samples": [(1, 0)]},  # [(on/off, ns)]
            "test": {"samples": [(1, 4), (0, 8), (1, 12)]}, # [(on/off, ns)] arbitrary example digital waveform total length /4 shoult be integer
            "OFF": {"samples": [(0, 0)]},  # [(on/off, ns)]
        }

    def get_mixers(self) -> Dict[str, Any]:
        return {
            "mixer_NV": [
                {"intermediate_frequency": self.NV_IF_freq, "lo_frequency": self.NV_LO_freq,
                    "correction": self.iq_imbalance(0.0, 0.0)},
            ],
        }

    def get_config(self) -> Dict[str, Any]:
        return {
            "version": self.get_version(),
            "controllers": self.get_controllers(),
            "elements": self.get_elements(),
            "pulses": self.get_pulses(),
            "waveforms": self.get_waveforms(),
            "digital_waveforms": self.get_digital_waveforms(),
            "mixers": self.get_mixers(),
        }
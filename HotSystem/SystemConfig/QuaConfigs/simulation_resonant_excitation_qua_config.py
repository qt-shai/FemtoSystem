from typing import Dict, Any
from SystemConfig import SystemType
from SystemConfig.QuaConfigs import QUAConfigBase


class SimulationResonantExQuaConfig(QUAConfigBase):
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
        self.signal_threshold = -500  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_2 = -350  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_OPD = 1  # in voltage (with 20dB attenuation it was 0.1)
        self.system_name:str = SystemType.ICE.value

    def get_controllers(self) -> Dict[str, Any]:
        """
        Returns the controller configuration for the Atto system.

        :return: Dictionary containing controller configurations.
        """
        controllers = {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    1: {"offset": 0.0, "delay": self.rf_delay, "shareable": False},  # only for detector
                },
                "digital_outputs": {
                    5: {"shareable": False},  # Marker
                },
                "analog_inputs": {
                    1: {"offset": 0.00979, "gain_db": 0, "shareable": False}, # 20db 0.2V electrical
                    2: {"offset": 0.00979, "gain_db": -12, "shareable": False}, # 6db 1V -->~0.25V
                },
                # "digital_inputs": {
                #     2: {'polarity': 'RISING', 'deadtime': 4, "threshold": self.signal_threshold_OPD, "shareable": False},  #4 to 16nsec,
                # },
            }

        }
        return controllers

    def get_elements(self) -> Dict[str, Any]:
        """
        Returns the elements configuration for the Atto system.

        :return: Dictionary containing element configurations.
        """
        elements = {
            self.Elements.RESONANT_LASER.value: {
                "digitalInputs": { # here it is actually outputs
                    "marker": {
                        "port": ("con1", 5),  # Digital output 4
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.DETECTOR_OPD.value: {  # actual analog
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 3),
                    #     "delay": self.detection_delay,
                    #     "buffer": 0,
                    # },
                },
                "operations": {
                    "readout": "readout_pulse",
                    "min_readout": "min_readout_pulse",
                    "long_readout": "long_readout_pulse",
                },
                "outputs": {"out1": ("con1", 2)},
                "outputPulseParameters": {
                    "signalThreshold": self.signal_threshold,
                    "signalPolarity": "below",
                    "derivativeThreshold": 1023,
                    "derivativePolarity": "below",
                },
                "time_of_flight": self.detection_delay,
                "smearing": 0,
            },
            self.Elements.DETECTOR2_OPD.value: {  # actual analog
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 4),
                    #     "delay": self.detection_delay,
                    #     "buffer": 0,
                    # },
                },
                "operations": {
                    "readout": "readout_pulse",
                    "min_readout": "min_readout_pulse",
                    "long_readout": "long_readout_pulse",
                },
                "outputs": {"out1": ("con1", 2)},
                "outputPulseParameters": {
                    "signalThreshold": self.signal_threshold_2,
                    "signalPolarity": "below",
                    "derivativeThreshold": 1023,
                    "derivativePolarity": "below",
                },
                "time_of_flight": self.detection_delay,
                "smearing": 0,
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

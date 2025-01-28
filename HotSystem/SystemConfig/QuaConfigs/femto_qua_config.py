from typing import Dict, Any
import SystemConfig.QuaConfigs as configs
from SystemConfig import SystemType


class FemtoQuaConfig(configs.QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()
        # Readout parameters
        self.signal_threshold = -500  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_2 = -350  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_OPD = 1 # in voltage (with 20dB attenuation it was 0.1)
        self.system_name = SystemType.FEMTO.value

        # Delays
        self.detection_delay = 100  # ns
        self.detection2_delay = 100  # ns
        self.mw_delay = 0  # ns
        self.laser_delay = 116 # ns

    def get_controllers(self) -> Dict[str, Any]:
        return {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    1: {"offset": 0.0, "delay": self.rf_delay, "shareable": False},  # only for detector
                    7: {"offset": 0.0, "delay": self.rf_delay, "shareable": False},  # only for detector
                },
                "digital_outputs": {
                    3: {"shareable": False},  # Marker
                    4: {"shareable": False},  # Marker 2
                    6: {"shareable": False},  # Smaract TTL
                    7: {"shareable": False},  # Laser 520nm cobolt
                    9: {"shareable": False},  # red laser
                    10: {"shareable": False},  # pharos trigger
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

    def get_elements(self) -> Dict[str, Any]:
        return {
            "Laser": {  # Laser is arbitrary name, in our system it is just LASER
                "digitalInputs": {  # for the OPX it is digital outputs
                    "marker": {  # marker is arbitrary name
                        "port": ("con1", 7),  # CH NUM
                        "delay": self.laser_delay,
                        "buffer": 0,  # buffer <= laser_delay
                    },
                },
                "operations": {
                    # "laser_ON": "laser_ON",
                    "Turn_ON": "laser_ON",
                },
            },
            "Detector_OPD": { # actual analog
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
                    "min_readout": "min_readout_pulse",
                    "long_readout": "long_readout_pulse",
                },
                "outputs": {"out1": ("con1", 1)},
                "outputPulseParameters": {
                    "signalThreshold": self.signal_threshold,
                    "signalPolarity": "below",
                    "derivativeThreshold": 1023,
                    "derivativePolarity": "below",
                },
                "time_of_flight": self.detection_delay,
                "smearing": 0,
            },

            "Detector2_OPD": { # actual analog
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 4),
                        "delay": self.detection2_delay,
                        "buffer": 0,
                    },
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
                "time_of_flight": self.detection2_delay,
                "smearing": 0,
            },

            "SmaractTrigger": {  # Send trigger to Smaract to go to next point in motion stream
                "digitalInputs": {  # for the OPX it is digital outputs
                    "marker": {  # marker is arbitrary name
                        "port": ("con1", 6),  # CH NUM
                        "delay": 0,
                        "buffer": 0,  # buffer <= laser_delay, amir: TBD to understand it
                    },
                },
                "operations": {
                    "Turn_ON": "laser_ON",
                },
            },
        }

    
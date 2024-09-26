from typing import Dict, Any
import SystemConfig.QuaConfigs as configs 


class FemtoQuaConfig(configs.QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()

    def get_controllers(self) -> Dict[str, Any]:
        return {
            "con1": {
                "type": "opx1",
                "analog_outputs": {
                    1: {"offset": 0.0, "delay": self.rf_delay, "shareable": True},   
                },
                "digital_outputs": {
                    6: {"shareable": True},  # Smaract TTL 
                    7: {"shareable": True},  # Laser 
                    8: {"shareable": True},  # Photo diode marker. Actual cable is not connected (kind of virtual, however we cannot use this channel when in use)
                },
                "analog_inputs": {
                    1: {"offset": 0.00979, "gain_db": 0, "shareable": True},
                    2: {"offset": 0.00979, 'gain_db': 0, "shareable": True},
                },
                "digital_inputs": {
                    2: {'polarity': 'RISING', 'deadtime': 4, "threshold": self.signal_threshold_OPD, "shareable": True},  #4 to 16nsec,
                },
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

            "Detector_OPD": {
                "singleInput": {"port": ("con1", 1)},  # not used
                "digitalInputs": {
                    # "marker": {
                    #     "port": ("con1", 8),
                    #     "delay": self.detection_delay_OPD,
                    #     "buffer": 0,
                    # },
                },
                'digitalOutputs': {  # 'digitalOutputs' here is actually 'digital input' of OPD
                    'out1': ('con1', 2)
                },
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

    
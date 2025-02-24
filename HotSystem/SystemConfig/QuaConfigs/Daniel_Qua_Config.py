from typing import Dict, Any
import SystemConfig.QuaConfigs as configs
from SystemConfig import SystemType


class DanielQuaConfig(configs.QUAConfigBase):
    def __init__(self) -> None:
        super().__init__()
        # Readout parameters
        self.NV_IF_freq = 124e6  # in units of Hz
        self.NV_LO_freq = 2.7e9  # in units of Hz

        # Pulses lengths
        self.initialization_len = 5000  # in ns
        self.meas_len = 28*3 + 2*2 + 16+32 + 16  # in ns
        self.minimal_meas_len = 16  # in ns
        self.long_meas_len = 5e3  # in ns
        self.very_long_meas_len = 25e3  # in ns

        self.pi_amp_NV = 0.5  # in units of volts
        self.pi_len_NV = 16  # in units of ns

        self.pi_half_amp_NV = self.pi_amp_NV / 2  # in units of volts
        self.pi_half_len_NV = self.pi_len_NV  # in units of ns

        # MW Switch parameters
        self.switch_delay = 0  # in ns
        self.switch_buffer = 0  # in ns
        self.switch_len = 16  # in ns

        # Readout parameters
        self.signal_threshold = -400  # in ADC units
        self.signal_threshold_OPD = 1 # in voltage (with 20dB attenuation it was 0.1)

        # Delays
        self.detection_delay_OPD = 308
        self.mw_delay = 0  # ns
        self.laser_delay = 0  # ns

        # RF parameters
        self.rf_frequency = 3.03 * self.u.MHz
        self.rf_amp = 0.5
        self.rf_length = 1000
        self.rf_delay = 0  # ns

        self.resonant_laser_delay = 0  # Todo: change to physical number
        self.blinding_delay = 0
        self.scannerX_delay = 0
        self.scannerY_delay = 0
        self.phaseEOM_delay = 0
        self.detection_delay = 28  # ns

        self.signal_threshold = -500  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_2 = -350  # in ADC units with 20dB attenuation we measured 0.2V on the oscilloscope
        self.signal_threshold_OPD = 1  # in voltage (with 20dB attenuation it was 0.1)
        self.system_name = SystemType.DANIEL.value

        # self.gaussian_amplitude = 0.2  # Amplitude of the Gaussian pulse
        # self.gaussian_mu = 0          # Mean of the Gaussian (centered at 0)
        # self.gaussian_sigma = 0.5     # Standard deviation of the Gaussian
        # self.gaussian_length = 16     # Length of the pulse in ns

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
                    2: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW I
                    3: {"offset": 0.0, "delay": self.mw_delay, "shareable": False},  # MW Q
                },
                "digital_outputs": {
                    1: {"shareable": False},  # trigger Laser (Cobolt)
                    2: {"shareable": False},  # trigger MW (Rohde Schwarz)
                    3: {"shareable": False},  # Marker for the detector
                    6: {"shareable": False},  # Trigger for blinding the detector
                    8: {"shareable": False},  # trigger for the Resonant Laser
                },
                "analog_inputs": {
                    #Not used, so can be in everyone configuration file
                    1: {"offset": 0.00979, "gain_db": 0, "shareable": False},  # 20db 0.2V electrical # counter1
                },
                # "digital_inputs": {  # counter 1
                #     1: {
                #         "polarity": "RISING",
                #         "deadtime": 4,
                #         "threshold": self.signal_threshold_OPD,
                #         "shareable": False,
                #     },
                #     2: {  # counter 2
                #         "polarity": "RISING",
                #         "deadtime": 4,
                #         "threshold": self.signal_threshold_OPD,
                #         "shareable": False,
                #     },

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
            self.Elements.MW.value: {
                "mixInputs": {
                    "I": ("con1", 2),  # Analog output 2
                    "Q": ("con1", 3),  # Analog output 3
                    "lo_frequency": self.NV_LO_freq,
                    "mixer": "mixer_NV",
                },
                "intermediate_frequency": self.NV_IF_freq,
                "digitalInputs": { # 'digitalInputs' is actually 'digital_outputs'. MW switch (ON/OFF)
                    "marker": {
                        "port": ("con1", 2),  # Digital output 2
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
            self.Elements.LASER.value: {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 1),  # Digital output 1
                        "delay": self.laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.RESONANT_LASER.value: {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 8),  # Digital output 8
                        "delay": self.resonant_laser_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "laser_ON"},
            },
            self.Elements.MW_SWITCH.value: {
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 2),  # Digital output 5
                        "delay": self.switch_delay,
                        "buffer": self.switch_buffer,
                    },
                },
                "operations": {"ON": "switch_ON"},
            },

            self.Elements.DETECTOR_OPD.value: {  # actual analog
                "singleInput": {"port": ("con1", 1)},
                "digitalInputs": {
                    "marker": {
                        "port": ("con1", 3),
                        "delay": 0,
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

            # self.Elements.DETECTOR2_OPD.value: {  # actual analog
            #     "singleInput": {"port": ("con1", 1)},
            #     "digitalInputs": {
            #         # "marker": {
            #         #     "port": ("con1", 4),
            #         #     "delay": self.detection_delay,
            #         #     "buffer": 0,
            #         # },
            #     },
            #     "operations": {
            #         "readout": "readout_pulse",
            #         "min_readout": "min_readout_pulse",
            #         "long_readout": "long_readout_pulse",
            #     },
            #     "outputs": {"out1": ("con1", 2)},
            #     "outputPulseParameters": {
            #         "signalThreshold": self.signal_threshold_2,
            #         "signalPolarity": "below",
            #         "derivativeThreshold": 1023,
            #         "derivativePolarity": "below",
            #     },
            #     "time_of_flight": self.detection_delay,
            #     "smearing": 0,
            # },
            self.Elements.BLINDING.value:{
                "digitalInputs": {  # here it is actually outputs
                    "marker": {
                        "port": ("con1", 6),  # Digital output 6
                        "delay": self.blinding_delay,
                        "buffer": 0,
                    },
                },
                "operations": {"Turn_ON": "blinding_ON"},
            }
            # self.Elements.DETECTOR_OPD.value: {
            #     "singleInput": {"port": ("con1", 1)},  # analog outputs, not used
            #     "digitalInputs": {
            #         # "marker": {
            #         #     "port": ("con1", 2),  # Digital output 10
            #         #     "delay": self.detection_delay_OPD,
            #         #     "buffer": 0,
            #         # },
            #     },
            #     "digitalOutputs": {"out1": ("con1", 1)},  # 'digitalOutputs' here is actually 'digital input' of OPD
            #     "outputs": {"out1": ("con1", 2)},
            #     "operations": {
            #         "readout": "readout_pulse",
            #         "min_readout": "min_readout_pulse",
            #         "long_readout": "long_readout_pulse",
            #         "very_long_readout": "very_long_readout_pulse",
            #     },
            #     "time_of_flight": self.detection_delay_OPD,
            #     "smearing": 0,
            # },
            # self.Elements.DETECTOR2_OPD.value: {
            #     "singleInput": {"port": ("con1", 4)},  # not used
            #     "digitalInputs": {
            #         # "marker": {
            #         #     "port": ("con1", 10),  # Digital output 10
            #         #     "delay": self.detection_delay_OPD,
            #         #     "buffer": 0,
            #         # },
            #     },
            #     "digitalOutputs": {"out1": ("con1", 5)},  # 'digitalOutputs' here is actually 'digital input' of OPD
            #     "outputs": {"out1": ("con1", 2)},
            #     "operations": {
            #         "readout": "readout_pulse",
            #         "min_readout": "min_readout_pulse",
            #         "long_readout": "long_readout_pulse",
            #         "very_long_readout": "very_long_readout_pulse",
            #     },
            #     "time_of_flight": self.detection_delay_OPD,
            #     "smearing": 0,
            # },
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
        blinding_ops = elements["Blinding"].get("operations", {})
        #MW_ops = elements["MW"].get("operations", {})
        ops_16 = self.get_extra_operations_16ns()
        ops_32 = self.get_extra_operations_32ns()
        ops_both_sides = self.get_extra_operations_left_side()
        blinding_ops.update(ops_16)
        blinding_ops.update(ops_32)
        blinding_ops.update(ops_both_sides)
        #MW_ops.update()
        elements["Blinding"]["operations"] = blinding_ops
        #elements["MW"]["operations"] = blinding_ops
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

        # pulses["gaussian_waveform_pulse"] = {
        #     "operation": "control",
        #     "length": self.gaussian_length,
        #     "waveforms": "gaussian_waveform",
        # }
        return pulses

    # def get_waveforms(self) -> Dict[str, Any]:
    #     gaussian_waveform_data = self.gauss(
    #         amplitude=self.gaussian_amplitude,
    #         mu=self.gaussian_mu,
    #         sigma=self.gaussian_sigma,
    #         length=self.gaussian_length,
    #     )
    #
    #     waveforms = super().get_waveforms()
    #     waveforms["gaussian_waveform"] = {
    #             'type': "arbitrary",
    #             'samples': gaussian_waveform_data
    #     }
    #     return waveforms

    def get_extra_operations_16ns(self) -> Dict[str, str]:
        ops = {}
        for t in range(16):
            ops[f"opr_{t}"] = f"d_pulse_{t}"
        return ops

    def get_extra_operations_32ns(self) -> Dict[str, str]:
        ops = {}
        for t in range(4):
            ops[f"opr2_{t}"] = f"d_pulse2_{t}"
        return ops

    def get_extra_operations_left_side(self) -> Dict[str, str]:
        ops = {}
        for t in range(16):
            ops[f"opr_left_{t}"] = f"d_pulse_left_{t}"
        return ops

from threading import Thread
from typing import Any, Optional

from moku.instruments import MultiInstrument, LockInAmp, PIDController

class Moku:

    def __init__(self, mokugo_ip: str) -> None:

        self._mokugo_ip = mokugo_ip

        # MIM instrument
        self._mim = MultiInstrument(
            ip=self._mokugo_ip, force_connect=True, platform_id=2
        )
        # MIM config
        self._lock_in_amp, self._pid_controller = self._mim_config(mim=self._mim)

        # Lock-In Amplifier config
        self._config_lock_in_amplifier(lock_in_amp=self._lock_in_amp)

        # PID Controller config
        self._config_pid_controller(pid_controller=self._pid_controller)

    def print_device_info(self) -> None:

        print(f"Moku calibration date: {self._mim.calibration_date()}")
        print(f"Moku device description: {self._mim.describe()}")
        print(f"Moku device name: {self._mim.name()}")
        print(f"Moku device serial number: {self._mim.serial_number()}")

    @staticmethod
    def _config_lock_in_amplifier(lock_in_amp: LockInAmp) -> None:

        # Lock-In Amplifier config

        lock_in_amp.set_outputs(main="X", aux="Aux")

        lock_in_amp.set_demodulation(mode="External")

        lock_in_amp.set_filter(
            corner_frequency=100, slope="Slope24dB"
        )  # corner frequency in Hz units

        lock_in_amp.set_gain(main=0.0, aux=0.0, main_invert=False, aux_invert=False)

    @staticmethod
    def _config_pid_controller(pid_controller: PIDController) -> None:

        # PID Controller config
        pid_controller.enable_input(channel=1, enable=True)
        # pid_controller.enable_input(channel=2, enable=False)

        pid_controller.enable_output(channel=1, signal=True, output=True)
        pid_controller.enable_output(channel=2, signal=False, output=False)

        pid_controller.set_control_matrix(channel=1, input_gain1=1, input_gain2=0)
        pid_controller.set_control_matrix(channel=2, input_gain1=0, input_gain2=1)

        pid_controller.set_input_offset(channel=1, offset=0.0)

        pid_controller.set_output_limit(
            channel=1, enable=True, low_limit=0.0, high_limit=5.0
        )

        pid_controller.set_output_offset(channel=1, offset=2.5)

        pid_controller.set_by_frequency(channel=1, prop_gain=20.0, int_crossover=10.0)

        # Setup Monitors
        pid_controller.set_monitor(monitor_channel=1, source="Output1")

    @staticmethod
    def _mim_config(mim: MultiInstrument) -> (LockInAmp, PIDController):

        # Lock-In Amplifier - Slot 1
        lock_in_amp = mim.set_instrument(1, LockInAmp)
        # PID Controller - Slot 2
        pid_controller = mim.set_instrument(2, PIDController)

        # MIM connectors
        mim_connections = mim.set_connections(
            [
                {"source": "Input1", "destination": "Slot1InA"},
                {"source": "Input2", "destination": "Slot1InB"},
                {"source": "Slot1OutA", "destination": "Slot2InA"},
                {"source": "Slot2OutA", "destination": "Output1"},
            ]
        )

        mim.set_frontend(channel=1, impedance="1MOhm", coupling="DC", attenuation="0dB")
        mim.set_frontend(channel=2, impedance="1MOhm", coupling="DC", attenuation="0dB")

        return lock_in_amp, pid_controller

    def reset_pid_windup(self) -> None:
        # disable output signal on channel 1
        self._pid_controller.enable_output(channel=1, signal=False, output=True)
        # enable output signal on channel 1
        self._pid_controller.enable_output(channel=1, signal=True, output=True)

    def get_existing_instruments(self) -> Any:
        instruments = self._mim.get_instruments()
        return instruments

    def get_threaded_pid_output_data(self) -> None:
        thread = Thread(target=self.get_pid_output_value, args=())
        thread.start()
        # thread.join()

    from typing import List, Dict

    def get_pid_output_value(self) -> List[Dict[str, float]]:
        """
        Retrieves a fixed set of PID output stream data.

        :return: A list of dictionaries containing the streamed data.
        """
        # Start streaming
        data = self._pid_controller.get_data()

        return data

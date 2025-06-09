import pdb
from typing import Optional, Callable, Dict, DefaultDict
import threading

from Common import KeyboardKeys
from HW_wrapper import (AttoDry800, ALR3206T, RS_SGS100a, smaractMCS2, Zelux, HighlandT130, newportPicomotor,
    SirahMatisse, Keysight33500B, MotorStage, ArduinoController, Motor, FilterFlipperController,
                        SirahMatisse, Keysight33500B, ArduinoController, NI_DAQ_Controller, LightFieldSpectrometer)
from HW_wrapper.Attocube import Anc300Wrapper
from HW_wrapper.SRS_PID.wrapper_sim960_pid import SRSsim960
from HW_wrapper.SRS_PID.wrapper_sim900_mainframe import SRSsim900
from HW_wrapper.Wrapper_Cobolt import CoboltLaser, Cobolt06MLD
from HW_wrapper.Wrapper_CLD1011 import ThorlabsCLD1011LP
from HW_wrapper.wrapper_wavemeter import HighFinesseWLM
from HW_wrapper.Wrapper_moku import Moku

from SystemConfig import SystemConfig, Instruments, SystemType, run_system_config_gui, load_system_config, InstrumentsAddress, Device
from Utils import ObservableField

class HW_devices:
    """
    Singleton class for managing hardware devices, with optional simulation mode.
    """
    _instance = None
    _lock = threading.Lock()


    def __init__(self):

        if not getattr(self, 'initialized', False):
            self.elc_power_supply: Optional[ALR3206T] = None
            self.highland_eom_driver: Optional[list[HighlandT130]]  = []
            self.microwave: Optional[RS_SGS100a] = None
            self.positioner: Optional[smaractMCS2|AttoDry800] = None
            self.camera: Optional[Zelux] = None
            self.atto_positioner: Optional[AttoDry800] = None
            self.picomotor:Optional[newportPicomotor] = None
            self.cobolt:Optional[CoboltLaser] = None
            self.matisse_device: Optional[SirahMatisse] = None
            self.wavemeter:Optional[HighFinesseWLM] = None
            self.moku: Optional[Moku] = None
            self.atto_scanner: Optional[Anc300Wrapper] = None
            self.keysight_awg_device: Optional[Keysight33500B] = None
            self.SRS_PID_list: Optional[list[SRSsim960]] = None
            self.arduino: Optional[ArduinoController] = None  # Add Arduino
            self.CLD1011LP: Optional[ThorlabsCLD1011LP] = None
            self.arduino: Optional[ArduinoController] = None
            self.kdc_101: Optional[MotorStage] = None
            self.mff_101_list: Optional[list[FilterFlipperController]] = []
            self.hrs_500: Optional[LightFieldSpectrometer] = None
            self._keyboard_movement_callbacks = Dict[KeyboardKeys, Optional[Callable[[int, float], None]]]
            self.ni_daq_controller: Optional[NI_DAQ_Controller]= None
            self._initialize()

    def __new__(cls) -> 'HW_devices':
        """
        Create or the singleton instance of the class.
        :return: The singleton instance of the HW_devices class.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HW_devices, cls).__new__(cls)
                cls._instance.__init__()
            return cls._instance

    def _initialize(self) -> None:
        """
        Initialize the singleton instance with hardware configuration.
        """
        if not hasattr(self, 'initialized'):  # Ensure initialization runs only once
            try:
                self.config: SystemConfig = load_system_config()
            except ValueError:
                run_system_config_gui()
            if not self.config:
                run_system_config_gui()
                self.config = load_system_config()

            if not self.config:
                raise Exception("No system config")

            self.system_type: SystemType = self.config.system_type
            self.setup_instruments()

    def setup_instruments(self):
        """Load specific instruments based on the system configuration."""
        for device in self.config.devices:
            instrument = device.instrument
            print(f"Setting instrument {instrument.name}")
            try:
                if instrument == Instruments.ROHDE_SCHWARZ:
                    # Initialize Rohde & Schwarz Microwave
                    self.microwave = RS_SGS100a(f'TCPIP0::{device.ip_address}::inst0::INSTR',
                                                          simulation=device.simulation)
                    self.microwave.Get_deviceID()
                    if "SGT" in self.microwave.ID:
                        self.microwave.set_connector_mode(2)
                        self.microwave.set_iq_modulation_state(True)
                        self.microwave.set_iq_source_to_analog()
                        self.microwave.set_iq_mod_to_wide(True)
                        self.microwave.set_bb_impairment_state(False)

                elif instrument in [Instruments.SMARACT_SLIP, Instruments.SMARACT_SCANNER]:
                    # Initialize SmarAct Slip Stick Positioner
                    self.positioner = smaractMCS2(simulation=device.simulation)

                elif instrument == Instruments.COBOLT:
                    cobolt_config: Device = [x for x in self.config.devices if x.instrument is Instruments.COBOLT][0]
                    self.cobolt = CoboltLaser(port=cobolt_config.com_port,simulation=device.simulation)

                elif instrument == Instruments.CLD1011LP:
                    CLD1011LP_config: Device = [x for x in self.config.devices if x.instrument is Instruments.CLD1011LP][0]
                    self.CLD1011LP = ThorlabsCLD1011LP(simulation=device.simulation)

                elif instrument == Instruments.PICOMOTOR:
                    self.picomotor = newportPicomotor(device.simulation)

                elif instrument == Instruments.ZELUX:
                    # Initialize Zelux Camera
                    self.camera = Zelux(simulation=device.simulation)

                elif instrument == Instruments.ATTO_POSITIONER:
                    # Initialize Atto Positioner
                    self.atto_positioner = AttoDry800(address=SystemConfig.atto_positioner_ip, name="atto_positioner",
                                                      simulation=device.simulation)

                elif instrument == Instruments.ATTO_SCANNER:
                    self.atto_scanner = Anc300Wrapper(conn= InstrumentsAddress.atto_scanner.value,
                                                      simulation=device.simulation)

                elif instrument == Instruments.MATTISE:
                    self.matisse_device = SirahMatisse(addr="127.0.0.1:30000", simulation=device.simulation)

                elif instrument == Instruments.WAVEMETER:
                    # Initialize the HighFinesse WLM
                    self.wavemeter = HighFinesseWLM(index=0, simulation=device.simulation)

                elif instrument == Instruments.HIGHLAND:
                    # Initialize Highland Electronics Device
                    self.highland_eom_driver.append(HighlandT130(address=device.com_port, simulation=device.simulation, serial_number = device.serial_number))


                elif instrument == Instruments.SMARACT_SCANNER:
                    # Initialize SmarAct Scanner
                    # self.smaract_scanner = stage.SmaractScanner(simulation=device.simulation)
                    pass

                elif instrument == Instruments.OPX:
                    # Initialize OPX Quantum Controller
                    self.config.opx_ip = device.ip_address
                    self.config.opx_cluster = device.misc

                elif instrument == Instruments.ELC_POWER_SUPPLY:
                    # Initialize ELC Power Supply
                    self.elc_power_supply = ALR3206T(simulation=device.simulation)

                elif instrument == Instruments.SIM960:
                    # Initialize SRS SIM960 PID controller
                    # pdb.set_trace()
                    sim900_config: list[Device] = [x for x in self.config.devices if x.instrument is Instruments.SIM960]
                    mainframe = SRSsim900(sim900_config[0].com_port)
                    if sim900_config[0].simulation:
                        print("SIM960 in simulation mode skipping connection")
                        sim900_config[0].ip_address = '0'
                    else:
                        mainframe.connect()
                        mainframe.initialize()

                    self.SRS_PID_list = [SRSsim960(
                        mainframe = mainframe,
                        slot = int(dev.ip_address),
                        simulation = dev.simulation
                    ) for dev in sim900_config]

                elif instrument == Instruments.ARDUINO:
                    # Initialize ArduinoController
                    self.arduino = ArduinoController(
                        address= f"ASRL{device.com_port}::INSTR" if device.com_port != "N/A" else None,
                        baudrate=9600,
                        timeout=1000,
                        simulation=device.simulation
                    )
                    if not device.simulation:
                        self.arduino.connect()
                    print(f"Arduino {'(Simulated)' if device.simulation else 'Connected'} at {device.com_port}")

                elif instrument == Instruments.MOKU:
                    self.moku = Moku(mokugo_ip=InstrumentsAddress.moku_ip.value)

                elif instrument == Instruments.KEYSIGHT_AWG:
                    self.keysight_awg_device = Keysight33500B(address=f'TCPIP::{device.ip_address.replace(":","::")}::SOCKET',
                                                              simulation=device.simulation)
                    self.keysight_awg_device.connect()

                elif instrument == Instruments.NI_DAQ:
                    config = {
                        "apd_input": f"{device.com_port}/ai0",
                        "sample_clk": "PFI1",
                        "start_trig": "PFI0",
                        "max_samp_rate": 50e3,
                        "min_voltage": -10.0,
                        "max_voltage": 10.0,
                        "number_measurements": 10,
                        "time_interval_us": 1000,
                        "pulse_width_us": 1000,
                        "pulse_spacing_us": 5000,
                    }
                    self.ni_daq_controller = NI_DAQ_Controller(configuration=config)

                elif instrument == Instruments.KDC_101:
                    # # KDC_101 Rotational Stage for the Lambda/2 Plate
                    # # TODO: Make serial number into an input to the Motor Stage
                    self.kdc_101 = MotorStage(device.serial_number)
                    self.kdc_101.connect()
                    pass

                elif instrument == Instruments.MFF_101:
                    current_flipper = FilterFlipperController(device.serial_number)
                    current_flipper.connect()
                    self.mff_101_list.append(current_flipper)
                    pass

                elif instrument == Instruments.HRS_500:
                    # Defined to load Experiment2 by default
                    self.hrs_500 = LightFieldSpectrometer(visible = True)
                    self.hrs_500.connect()
                    #self.hrs_500 = None
                    pass

                elif instrument == Instruments.ARDUINO:
                    # Initialize ArduinoController
                    self.arduino = ArduinoController(
                        address=f"ASRL{device.com_port}::INSTR" if device.com_port != "N/A" else None,
                        baudrate=9600,
                        timeout=1000,
                        simulation=self.simulation
                    )


                else:
                    # Handle unknown instrument case
                    print(f"Unknown instrument: {instrument}")

            except Exception as e:
                print(f"Failed to connect to instrument {instrument} with error: {e}")

        self.initialized = True  # Mark the instance as init
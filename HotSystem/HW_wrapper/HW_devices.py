import pdb
from typing import Optional
import threading

from HW_wrapper import AttoDry800, ALR3206T, RS_SGS100a, smaractMCS2, Zelux, HighlandT130, newportPicomotor, \
    SirahMatisse, Keysight33500B, AttoScannerWrapper
from HW_wrapper.Attocube import Anc300Wrapper
from HW_wrapper.SRS_PID.wrapper_sim960_pid import SRSsim960
from HW_wrapper.SRS_PID.wrapper_sim900_mainframe import SRSsim900
from HW_wrapper.Wrapper_Cobolt import CoboltLaser, Cobolt06MLD
from SystemConfig import SystemConfig, Instruments, SystemType, run_system_config_gui, load_system_config, InstrumentsAddress, Device


class HW_devices:

    _instance = None
    _lock = threading.Lock()


    def __init__(self):


        if not getattr(self, 'initialized', False):
            self.elc_power_supply: Optional[ALR3206T] = None
            self.highland_eom_driver: Optional[HighlandT130]  = None
            self.microwave: Optional[RS_SGS100a] = None
            self.positioner: Optional[smaractMCS2|AttoScannerWrapper|AttoDry800] = None
            self.camera: Optional[Zelux] = None
            self.atto_positioner: Optional[AttoDry800] = None
            self.picomotor:Optional[newportPicomotor] = None
            self.cobolt:Optional[CoboltLaser] = None
            self.matisse_device: Optional[SirahMatisse] = None
            self.atto_scanner: Optional[Anc300Wrapper] = None
            self.keysight_awg_device: Optional[Keysight33500B] = None
            self.SRS_PID_list: Optional[SRSsim960] = None

    def __new__(cls) -> 'HW_devices':
        """
        Create or the singleton instance of the class.
        :return: The singleton instance of the HW_devices class.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HW_devices, cls).__new__(cls)
                cls._instance.__init__()
                cls._instance._initialize()
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
                self.cobolt = Cobolt06MLD(com_port=cobolt_config.com_port,simulation=device.simulation)

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
                # self.keysight_awg_device = Keysight33500B(address=InstrumentsAddress.KEYSIGHT_AWG.value, simulation=device.simulation)  # Replace with actual address
                self.atto_scanner = Anc300Wrapper(conn= InstrumentsAddress.atto_scanner.value,
                                                  simulation=device.simulation)

            elif instrument == Instruments.MATTISE:
                self.matisse_device = SirahMatisse(addr=InstrumentsAddress.MATTISE.value, simulation=device.simulation)

            elif instrument == Instruments.HIGHLAND:
                # Initialize Highland Electronics Device
                highland_config: Device = [x for x in self.config.devices if x.instrument is Instruments.HIGHLAND][0]
                self.highland_eom_driver = HighlandT130(address=highland_config.com_port, simulation=device.simulation)

            elif instrument == Instruments.SMARACT_SCANNER:
                # Initialize SmarAct Scanner
                # self.smaract_scanner = stage.SmaractScanner(simulation=device.simulation)
                pass

            elif instrument == Instruments.OPX:
                # Initialize OPX Quantum Controller
                pass

            elif instrument == Instruments.ELC_POWER_SUPPLY:
                # Initialize ELC Power Supply
                self.elc_power_supply = ALR3206T(simulation=device.simulation)

            elif instrument == Instruments.SIM960:
                # Initialize SRS SIM960 PID controller
                # pdb.set_trace()
                sim900_config: list[Device] = [x for x in self.config.devices if x.instrument is Instruments.SIM960]
                mainframe = SRSsim900(f"ASRL{sim900_config[0].com_port[-1]}::INSTR")
                mainframe.connect()
                mainframe.initialize()
                self.SRS_PID_list = [SRSsim960(
                    mainframe = mainframe,
                    slot = int(dev.ip_address),
                    simulation = dev.simulation
                ) for dev in sim900_config]

            else:
                # Handle unknown instrument case
                print(f"Unknown instrument: {instrument}")

        self.initialized = True  # Mark the instance as init
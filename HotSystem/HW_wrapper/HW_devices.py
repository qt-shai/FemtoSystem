
from typing import Optional
import threading

from HW_wrapper import AttoDry800, ALR3206T, RS_SGS100a, smaractMCS2, Zelux, HighlandT130, newportPicomotor, \
    SirahMatisse, Keysight33500B, AttoScannerWrapper
from HW_wrapper.Attocube import Anc300Wrapper
from HW_wrapper.Wrapper_Cobolt import CoboltLaser, Cobolt06MLD
from HW_wrapper.Wrapper_CLD1011 import ThorlabsCLD1011LP

from SystemConfig import SystemConfig, Instruments, SystemType, run_system_config_gui, load_system_config, InstrumentsAddress, Device

class HW_devices:
    """
    Singleton class for managing hardware devices, with optional simulation mode.
    """
    _instance = None
    _lock = threading.Lock()


    def __init__(self, simulation:bool =False):
        """
        Initialize the HW_devices instance.

        :param simulation: A boolean flag indicating if the simulation mode is enabled.
        """

        if not getattr(self, 'initialized', False):
            self.simulation = simulation
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
            self.CLD1011LP: Optional[ThorlabsCLD1011LP] = None

    def __new__(cls, simulation:bool = False) -> 'HW_devices':
        """
        Create or the singleton instance of the class.
        :return: The singleton instance of the HW_devices class.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(HW_devices, cls).__new__(cls)
                cls._instance.__init__(simulation)
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
                                                      simulation=self.simulation)
                self.microwave.Get_deviceID()
                if "SGT" in self.microwave.ID:
                    self.microwave.set_connector_mode(2)
                    self.microwave.set_iq_modulation_state(True)
                    self.microwave.set_iq_source_to_analog()
                    self.microwave.set_iq_mod_to_wide(True)
                    self.microwave.set_bb_impairment_state(False)

            elif instrument in [Instruments.SMARACT_SLIP, Instruments.SMARACT_SCANNER]:
                # Initialize SmarAct Slip Stick Positioner
                self.positioner = smaractMCS2(simulation=self.simulation)

            elif instrument == Instruments.COBOLT:
                cobolt_config: Device = [x for x in self.config.devices if x.instrument is Instruments.COBOLT][0]
                self.cobolt = CoboltLaser(port=cobolt_config.com_port,simulation=self.simulation)
            
            elif instrument == Instruments.CLD1011LP:
                CLD1011LP_config: Device = [x for x in self.config.devices if x.instrument is Instruments.CLD1011LP][0]
                self.CLD1011LP = ThorlabsCLD1011LP(simulation=self.simulation)

            elif instrument == Instruments.PICOMOTOR:
                self.picomotor = newportPicomotor(self.simulation)

            elif instrument == Instruments.ZELUX:
                # Initialize Zelux Camera
                self.camera = Zelux(simulation=self.simulation)

            elif instrument == Instruments.ATTO_POSITIONER:
                # Initialize Atto Positioner
                self.atto_positioner = AttoDry800(address=SystemConfig.atto_positioner_ip, name="atto_positioner",
                                                  simulation=self.simulation)

            elif instrument == Instruments.ATTO_SCANNER:
                # self.keysight_awg_device = Keysight33500B(address=InstrumentsAddress.KEYSIGHT_AWG.value, simulation=self.simulation)  # Replace with actual address
                self.atto_scanner = Anc300Wrapper(conn= InstrumentsAddress.atto_scanner.value,
                                                  simulation=self.simulation)

            elif instrument == Instruments.MATTISE:
                self.matisse_device = SirahMatisse(addr=InstrumentsAddress.MATTISE.value, simulation=self.simulation)

            elif instrument == Instruments.HIGHLAND:
                # Initialize Highland Electronics Device
                self.highland_eom_driver = HighlandT130(address="ASRL5::INSTR", simulation=self.simulation)

            elif instrument == Instruments.SMARACT_SCANNER:
                # Initialize SmarAct Scanner
                # self.smaract_scanner = stage.SmaractScanner(simulation=self.simulation)
                pass

            elif instrument == Instruments.OPX:
                # Initialize OPX Quantum Controller
                pass

            elif instrument == Instruments.ELC_POWER_SUPPLY:
                # Initialize ELC Power Supply
                self.elc_power_supply = ALR3206T(simulation=self.simulation)

            else:
                # Handle unknown instrument case
                print(f"Unknown instrument: {instrument}")

        self.initialized = True  # Mark the instance as init
from typing import Dict, Any, Optional
import SystemConfig as config 

# SystemType, QUAConfigBase, HotSystemQuaConfig, FemtoQuaConfig
class QuaConfigSelector:
    """
    This class selects and returns the correct QUA configuration class
    based on the given SystemType.
    """

    @staticmethod
    def get_qua_config(system_type: config.SystemType) -> Dict[str, Any]:
        """
        Dynamically selects and returns the appropriate QUA config
        based on the system type's string representation.

        :param system_type: Enum value representing the system type.
        :return: Instance of QUAConfigBase subclass corresponding to the system type.
        """
        config_instance: Optional[config.QUAConfigBase] = None

        if system_type == config.SystemType.HOT_SYSTEM:
            config_instance = config.HotSystemQuaConfig()
        elif system_type == config.SystemType.FEMTO:
            config_instance = config.FemtoQuaConfig()
        elif system_type == config.SystemType.ATTO:
            config_instance = config.AttoQuaConfig()
        elif system_type == config.SystemType.ICE:
            config_instance = config.SimulationResonantExQuaConfig()
        return config_instance.get_config() if config_instance else None  # Return an instance of the found class
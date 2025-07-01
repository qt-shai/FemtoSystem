import requests

class PharosLaserAPI:
    """
    A Python wrapper for all PHAROS REST API commands.
    Adjust the PUT/POST data payloads if your actual API
    requires a specific JSON structure.
    """

    def __init__(self, host: str, port: int = 20022):
        """
        :param host: IP address or hostname of the PHAROS laser (e.g., '192.168.1.100').
        :param port: Port number for the REST API (default: 80). see Pharos documentation sometime the use 20026 port.
        """
        "http://192.168.101.58:20022/v0/basic"
        self.base_url = f"http://{host}:{port}/v0"

    # --------------------------------------------------------------------------
    # Internal helper methods
    # --------------------------------------------------------------------------

    def _get(self, endpoint: str):
        """Send a GET request to the specified endpoint and return JSON."""
        url = f"{self.base_url}{endpoint}"
        r = requests.get(url)
        r.raise_for_status()  # Raises an exception for 4xx/5xx responses
        return r.json()

    def _post(self, endpoint: str, data=None):
        """
        Send a POST request to the specified endpoint.
        `data` can be a dict (JSON) or any structure your API expects.
        """
        url = f"{self.base_url}{endpoint}"
        r = requests.post(url, json=data)
        r.raise_for_status()
        return r.json() if r.text else None

    def _put(self, endpoint: str, data=None):
        """
        Send a PUT request to the specified endpoint.
        `data` can be a dict (JSON) or any structure your API expects.
        """
        url = f"{self.base_url}{endpoint}"
        r = requests.put(url, json=data)
        r.raise_for_status()
        return r.json() if r.text else None

    # --------------------------------------------------------------------------
    # 1. Basic Usage
    # --------------------------------------------------------------------------

    def getBasic(self):
        return self._get("/Basic")

    def getBasicActualOutputPower(self):
        return self._get("/Basic/ActualOutputPower")

    def getBasicActualRaPower(self):
        return self._get("/Basic/ActualRaPower")

    def getBasicActualPpDivider(self):
        return self._get("/Basic/ActualPpDivider")

    def getBasicTargetPpDivider(self):
        return self._get("/Basic/TargetPpDivider")

    def setBasicTargetPpDivider(self, value):
        # Adjust the JSON key if needed
        return self._put("/Basic/TargetPpDivider", data={"TargetPpDivider": value})

    def getBasicActualAttenuatorPercentage(self):
        return self._get("/Basic/ActualAttenuatorPercentage")

    def getBasicTargetAttenuatorPercentage(self):
        return self._get("/Basic/TargetAttenuatorPercentage")

    def setBasicTargetAttenuatorPercentage(self, value):
        # Adjust the JSON key if needed
        return self._put("/Basic/TargetAttenuatorPercentage", data=value)
        # return self._put("/Basic/TargetAttenuatorPercentage", data={"TargetAttenuatorPercentage": value})

    def getBasicActualOutputEnergy(self):
        return self._get("/Basic/ActualOutputEnergy")

    def getBasicActualOutputFrequency(self):
        return self._get("/Basic/ActualOutputFrequency")

    def getBasicActualRaFrequency(self):
        return self._get("/Basic/ActualRaFrequency")

    def getBasicActualStateName2(self):
        return self._get("/Basic/ActualStateName2")

    def getBasicGeneralStatus(self):
        return self._get("/Basic/GeneralStatus")

    def getBasicActualHarmonic(self):
        return self._get("/Basic/ActualHarmonic")

    def getBasicIsEmissionWarningActive(self):
        return self._get("/Basic/IsEmissionWarningActive")

    def getBasicIsOutputEnabled(self):
        return self._get("/Basic/IsOutputEnabled")

    def enableOutput(self):
        return self._post("/Basic/EnableOutput")

    def closeOutput(self):
        return self._post("/Basic/CloseOutput")

    def getBasicIsOutputOpen(self):
        return self._get("/Basic/IsOutputOpen")

    def getBasicSelectedPresetIndex(self):
        return self._get("/Basic/SelectedPresetIndex")

    def setBasicSelectedPresetIndex(self, value):
        # Adjust the JSON key if needed
        return self._put("/Basic/SelectedPresetIndex", data={"SelectedPresetIndex": value})

    def applySelectedPreset(self):
        return self._post("/Basic/ApplySelectedPreset")

    def turnOn(self):
        return self._post("/Basic/TurnOn")

    def turnOff(self):
        return self._post("/Basic/TurnOff")

    def goToStandby(self):
        return self._post("/Basic/GoToStandby")

    def getBasicErrors(self):
        return self._get("/Basic/Errors")

    def getBasicWarnings(self):
        return self._get("/Basic/Warnings")

    # --------------------------------------------------------------------------
    # 2. Advanced Usage
    # --------------------------------------------------------------------------

    def getAdvanced(self):
        return self._get("/Advanced")

    def getAdvancedActualStateId(self):
        return self._get("/Advanced/ActualStateId")

    def getAdvancedIsPpEnabled(self):
        return self._get("/Advanced/IsPpEnabled")

    def enablePp(self):
        return self._post("/Advanced/EnablePp")

    def disablePp(self):
        return self._post("/Advanced/DisablePp")

    def getAdvancedPresets(self):
        return self._get("/Advanced/Presets")

    def setAdvancedPresets(self, presets_data):
        """
        Example usage: setAdvancedPresets({"Presets": [...]})
        Adjust payload to match actual API requirements.
        """
        return self._put("/Advanced/Presets", data=presets_data)

    def createPresetFromActualState(self):
        return self._post("/Advanced/CreatePresetFromActualState")

    def getAdvancedIsRemoteInterlockActive(self):
        return self._get("/Advanced/IsRemoteInterlockActive")

    def resetRemoteInterlock(self):
        return self._post("/Advanced/ResetRemoteInterlock")

    def getAdvancedAvailableFeatures(self):
        return self._get("/Advanced/AvailableFeatures")

    def getAdvancedActualPulseCount(self):
        return self._get("/Advanced/ActualPulseCount")

    def getAdvancedTargetPulseCount(self):
        return self._get("/Advanced/TargetPulseCount")

    def setAdvancedTargetPulseCount(self, value):
        return self._put("/Advanced/TargetPulseCount", data=value)
        # return self._put("/Advanced/TargetPulseCount", data={"TargetPulseCount": value})

    # --------------------------------------------------------------------------
    # 3. Stretcher-Compressor Control
    # --------------------------------------------------------------------------

    def getStretcherCompressor(self):
        return self._get("/StretcherCompressor")

    def getStretcherCompressorActualPosition(self):
        return self._get("/StretcherCompressor/ActualPosition")

    def getStretcherCompressorTargetPosition(self):
        return self._get("/StretcherCompressor/TargetPosition")

    def setStretcherCompressorTargetPosition(self, value):
        return self._put("/StretcherCompressor/TargetPosition", 
                         data={"TargetPosition": value})

    # --------------------------------------------------------------------------
    # 4. External Control
    # --------------------------------------------------------------------------

    def getExternalControl(self):
        return self._get("/ExternalControl")

    def getExternalControlPpTriggerSource(self):
        return self._get("/ExternalControl/PpTriggerSource")

    def setExternalControlPpTriggerSource(self, value):
        return self._put("/ExternalControl/PpTriggerSource", 
                         data={"PpTriggerSource": value})

    def getExternalControlPpVoltageControlSource(self):
        return self._get("/ExternalControl/PpVoltageControlSource")

    def setExternalControlPpVoltageControlSource(self, value):
        return self._put("/ExternalControl/PpVoltageControlSource", 
                         data={"PpVoltageControlSource": value})

    def getExternalControlRaSyncSource(self):
        return self._get("/ExternalControl/RaSyncSource")

    def setExternalControlRaSyncSource(self, value):
        return self._put("/ExternalControl/RaSyncSource", 
                         data={"RaSyncSource": value})

    def getExternalControlActualExternalRaFrequency(self):
        return self._get("/ExternalControl/ActualExternalRaFrequency")

    def getExternalControlTargetExternalRaFrequency(self):
        return self._get("/ExternalControl/TargetExternalRaFrequency")

    def setExternalControlTargetExternalRaFrequency(self, value):
        return self._put("/ExternalControl/TargetExternalRaFrequency", 
                         data={"TargetExternalRaFrequency": value})

    def getExternalControlFecControlSource(self):
        return self._get("/ExternalControl/FecControlSource")

    def setExternalControlFecControlSource(self, value):
        return self._put("/ExternalControl/FecControlSource", 
                         data={"FecControlSource": value})

    # --------------------------------------------------------------------------
    # 5. Burst Operation (if available)
    # --------------------------------------------------------------------------

    def getBurst(self):
        return self._get("/Burst")

    def getBurstActualParameterP(self):
        return self._get("/Burst/ActualParameterP")

    def getBurstActualParameterN(self):
        return self._get("/Burst/ActualParameterN")

    def getBurstActualParameterMode(self):
        return self._get("/Burst/ActualParameterMode")

    def getBurstActualEnvelopeControlParameter(self):
        return self._get("/Burst/ActualEnvelopeControlParameter")

    def getBurstTargetEnvelopeControlParameter(self):
        return self._get("/Burst/TargetEnvelopeControlParameter")

    def setBurstTargetEnvelopeControlParameter(self, value):
        return self._put("/Burst/TargetEnvelopeControlParameter", 
                         data={"TargetEnvelopeControlParameter": value})

    # --------------------------------------------------------------------------
    # 6. Oscillator Output (if available)
    # --------------------------------------------------------------------------

    def getOscillatorOutput(self):
        return self._get("/OscillatorOutput")

    def getOscillatorOutputActualAttenuatorPercentage(self):
        return self._get("/OscillatorOutput/ActualAttenuatorPercentage")

    def getOscillatorOutputTargetAttenuatorPercentage(self):
        return self._get("/OscillatorOutput/TargetAttenuatorPercentage")

    def setOscillatorOutputTargetAttenuatorPercentage(self, value):
        return self._put("/OscillatorOutput/TargetAttenuatorPercentage", 
                         data={"TargetAttenuatorPercentage": value})

    def enableOscillatorOutput(self):
        return self._post("/OscillatorOutput/Enable")

    # --------------------------------------------------------------------------
    # 7. Chiller Control (if available)
    # --------------------------------------------------------------------------

    def getChiller(self):
        return self._get("/Chiller")

    def getChillerIsOn(self):
        return self._get("/Chiller/IsOn")

    def getChillerActualTemperature(self):
        return self._get("/Chiller/ActualTemperature")

    def getChillerTargetTemperature(self):
        return self._get("/Chiller/TargetTemperature")

    def setChillerTargetTemperature(self, value):
        return self._put("/Chiller/TargetTemperature", 
                         data={"TargetTemperature": value})

    def turnOnChiller(self):
        return self._post("/Chiller/TurnOn")

    def turnOffChiller(self):
        return self._post("/Chiller/TurnOff")

    # --------------------------------------------------------------------------
    # 8. Custom Functionality
    # --------------------------------------------------------------------------

    def getCustom(self):
        return self._get("/Custom")

    def executeCustomCommand(self, command_data=None):
        """
        Execute a custom command. The payload (command_data) depends on 
        what the device expects.
        """
        return self._post("/Custom/ExecuteCommand", data=command_data)

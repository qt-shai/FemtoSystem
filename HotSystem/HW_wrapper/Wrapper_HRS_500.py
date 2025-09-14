import clr
import sys
import time
import inspect
from System.IO import *
import subprocess
import importlib

# Import C compatible List and String
from System import *
from System import String
from System.Collections.Generic import List
import spe_loader as sl

from Utils.Common import loadFromCSV, open_file_dialog
import os

sys.path.append(os.environ['LIGHTFIELD_ROOT'])
sys.path.append(os.environ['LIGHTFIELD_ROOT'] + "\\AddInViews")
clr.AddReference('PrincetonInstruments.LightFieldViewV5')
clr.AddReference('PrincetonInstruments.LightField.AutomationV5')
clr.AddReference('PrincetonInstruments.LightFieldAddInSupportServices')

# PI imports
from PrincetonInstruments.LightField.Automation import Automation
from PrincetonInstruments.LightField.AddIns import SpectrometerSettings
from PrincetonInstruments.LightField.AddIns import CameraSettings
from PrincetonInstruments.LightField.AddIns import DeviceType
from PrincetonInstruments.LightField.AddIns import ExperimentSettings


class LightFieldSpectrometer:

    def __init__(self, visible: bool = True, file_path: str = r"C:\\Users\\Femto\\Work Folders\\Documents\\LightField\\Experiments\\ProEM_shai.lfe") -> None: # ProEM_shai.lfe Experiment2.lfe
        """
            Minimal wrapper for a **single** connected LightField spectrometer.

            Parameters
            ----------
            visible : bool, optional
                If *True*, launches the full LightField UI so that the user can
                follow what the code is doing.  If *False*, LightField runs
                head‑less in the background.  Default is ``True``.
            file_path : str, optional
                Path to a “*.lfe*” experiment file that will be opened
                automatically after connecting.  This lets you pre‑configure all
                instrumental settings in LightField’s GUI and then automate only
                the steps you need (file naming, acquisition, …).  A sensible
                default is provided.

            Notes
            -----
            Exactly **one** spectrometer must be connected when the object is
            instantiated; otherwise :data:`None` is stored in :pyattr:`_device`
            and :py:meth:`is_connected` returns ``False``.
            """

        self.last_saved_csv = None
        self.visible = visible
        self.file_path = file_path
        self._auto = None
        self._exp = None
        self._device = None
        self.proEM_mode = True
        self.save_directory = r"C:\Users\Femto\Work Folders\Documents\LightField"

    # def __del__(self):
    #     self.close()
    #     os.system("taskkill /im AddInProcess.exe")

    def connect(self, new_exp = False) -> None:
        self._auto = Automation(self.visible, List[String]())
        self._exp = self._auto.LightFieldApplication.Experiment
        self._device = self._find_connected_spectrometer()
        if not new_exp:
            self.load_experiment()
            # print(self.get_exposure_time())
        self.wait_until_ready()

    def is_connected(self) -> bool:
        """Return ``True`` if a spectrometer is physically attached *and*
        recognised by LightField."""
        return bool(self._device and self._device.IsConnected)

    def _is_ready(self) -> bool:
        """
        Check readiness. Prefer a device‑level IsReady if it exists;
        otherwise fall back to the experiment’s flag.
        """
        # Todo: Check if there an issues with acquiring multiple frames
        ready_or_not = self._exp.IsRunning
        return bool(ready_or_not)

    def get_exposure_time(self):
        if not self._exp.Exists(CameraSettings.ShutterTimingExposureTime):
            raise RuntimeError(
                f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}]"
                "Exposure‑time setting is not available for the current device."
            )
        return float(
            self._exp.GetValue(CameraSettings.ShutterTimingExposureTime)
        )

    # def set_grating(self, grating: int = 2):
    #     """Sets spectrometer grating.
    #     Args:
    #         grating (int, optional): 0 for 'Mirror', 1 for 'Density: 900g/mm, Blaze: 550 nm', 2 for 'Density: 300g/mm, Blaze: 750 nm'. Defaults to 2.
    #     """
    #
    #     if grating == 0:
    #         self.set_value(SpectrometerSettings.Grating,'[Mirror,1200][0][0]')
    #     elif grating == 1:
    #         self.set_value(SpectrometerSettings.Grating,'[550nm,900][1][0]')
    #     elif grating == 2:
    #         self.set_value(SpectrometerSettings.Grating,'[750nm,300][2][0]')

    def set_value(self, setting, value):
        """Check for existence before setting and set provided value to setting.
        Should be used mostly as an internal function as the setting parameter is not very readable.
        Args:
            setting (Settings): camera, spectrometer, experiment settings you want to set up.
            value (_type_): the new value to provide.
        """

        if self._exp.Exists(setting):
            self._exp.SetValue(setting, value)
            print(f'{setting} set to {value}.')
        else:
            print(f'Error in setting {setting} to value: {value}.')

    def get_full_sensor_size(self):
        """Gives the full sensor dimensions (number of pixels).
        Returns:
            int: X position of the left border.
            int: Y position of the up border.
            int: Width of the region.
            int: Heigth of the region.
            int: XBinning, binning of the x axis.
            int: YBinning, binning of the y axis.
        """
        dimensions = self._exp.FullSensorRegion
        return dimensions.X, dimensions.Y, dimensions.Width, dimensions.Height, dimensions.XBinning, dimensions.YBinning

    def set_sensor_mode(self, mode: int = 1.0):
        """Set the sensor mode.
        Args:
            mode (int, optional): 1 for the entire area of the sensor, 2 rows binned , 3 only one row, 4 custom ROI. Defaults to 4.0.
        """
        self.set_value(CameraSettings.ReadoutControlRegionsOfInterestSelection, float(mode))

    def spectrometer_info(self) -> None:
        """Return key settings for the current spectrometer."""
        if not self.is_connected:
            raise RuntimeError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Spectrometer not connected.")

    def print_spectrometer_info(self) -> None:
        """Pretty‑print spectrometer settings to stdout."""
        for device in self._exp.ExperimentDevices:
            if (device.IsConnected == True):
                info = self.spectrometer_info()
                print(info)

    def load_experiment(self, manual_load = False) -> None:
        """Load a previously configured experiment."""
        if manual_load:
            file_path = open_file_dialog()
        else:
            file_path = self.file_path

        # LightField will close the current experiment and load the new one
        self._exp.Load(file_path)

    def wait_until_ready(self, timeout = 120.0, interval = 0.5) -> None:
        """
        Busy‑wait until IsReady is True or until *timeout* expires.
        """
        # Todo: Update timeout based on acquire time and number of frames
        start = time.monotonic()
        print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Waiting until IsReady is True.")
        while self._is_ready():
            if time.monotonic() - start > timeout:
                raise TimeoutError(
                    f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}]"
                    f"Spectrometer not ready after {timeout:.1f} s."
                )
            time.sleep(interval)
        print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Finished waiting.")

    def close(self) -> None:
        """Release LightField Automation resources."""
        """This function work well in the wrapper, however issues arose with automatic disconnect when GUI is closed."""
        self.wait_until_ready()
        if self._auto is not None:
            self._auto.Dispose()
            self._auto = None

    def disconnect(self):
        """This function enables to close properly the lightfield app running. Always use this function, otherwise it can break lightfield and make it crash later on.
        """
        subprocess.run(["taskkill", "/IM", "AddInProcess.exe"])
        print("Lightfield disconnected.")

    def _find_connected_spectrometer(self):
        """Return the first connected spectrometer device, or None."""
        for dev in self._exp.ExperimentDevices:
            if dev.IsConnected:
                return dev
            else:
                return None

    def acquire_Data(self) -> None:
        """Requires Lightfield to save a csv file"""

        before = self.get_list_of_files()
        self.wait_until_ready()
        self._exp.Acquire()
        time.sleep(0.5)
        print(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Acquired data")
        self.wait_until_ready()
        after = self.get_list_of_files()
        new_file = self.find_new_file(before, after)
        if new_file:
            self.last_saved_csv = new_file[0]
            print(f"New data file: {self.last_saved_csv}")
        else:
            self.last_saved_csv = None
            print("No new file found!")
        try:
            spe_file_data = loadFromCSV(self.last_saved_csv) if self.last_saved_csv else None
        except Exception as e:
            print(f"Error loading CSV '{self.last_saved_csv}': {e}")
            spe_file_data = None

        return spe_file_data  # NumPy array (frames, roiY, roiX)

    def _get_save_directory(self) -> str:
        """The directory LightField currently writes data to."""
        return self._exp.GetValue(ExperimentSettings.FileNameGenerationDirectory)

    def set_save_directory(self, directory: str, create: bool = True) -> None:
        if not os.path.isdir(directory):
            raise ValueError(f"[{self.__class__.__name__}.{inspect.currentframe().f_code.co_name}] Directory does not exist: {directory}")
        try:
            self._exp.SetValue(ExperimentSettings.FileNameGenerationDirectory, directory)
            print(f"Set saved directory to {directory}")
        except Exception as e:
            print(e)

    def get_list_of_files(self):
        files = []
        dir = self._get_save_directory()
        for file in os.listdir(dir):
            if file.endswith(".csv"):
                files.append(os.path.join(dir, file))
        return files

    def find_new_file(self, before, after):
        new_file = [f for f in after if f not in before]
        return new_file

    def set_filename(self, filename: str):
        # Set the base file name
        self._exp.SetValue(
            ExperimentSettings.FileNameGenerationBaseFileName,
            filename)

        # Option to Increment, set to false will not increment
        self._exp.SetValue(
            ExperimentSettings.FileNameGenerationAttachIncrement,
            False)

        # Option to add date
        self._exp.SetValue(
            ExperimentSettings.FileNameGenerationAttachDate,
            True)

        # Option to add time
        self._exp.SetValue(
            ExperimentSettings.FileNameGenerationAttachTime,
            True)

    # --- ROI helpers (ProEM rectangle) ------------------------------------------
    def _roi_to_tuple(self, roi):
        """
        Convert a LightField RegionOfInterest object to a pixel-space tuple:
        (x_min, y_min, x_max, y_max, x_binning, y_binning)
        """
        x0 = int(roi.X)
        y0 = int(roi.Y)
        w = int(roi.Width)
        h = int(roi.Height)
        xb = int(roi.XBinning)
        yb = int(roi.YBinning)
        return (x0, y0, x0 + max(0, w), y0 + max(0, h), xb, yb)

    def get_selected_regions_pixels(self):
        """
        Return a list of currently-selected ROI(s) as pixel-space tuples:
          [(x_min, y_min, x_max, y_max, x_binning, y_binning), ...]
        If LightField is in a single-region mode, this will still return a list of length 1.
        """
        if self._exp is None:
            raise RuntimeError("LightField experiment not connected.")

        # SelectedRegions = the regions that would be returned on the next acquire
        rois = list(getattr(self._exp, "SelectedRegions", []) or [])
        if not rois:
            # Fallback to the full sensor region if nothing is explicitly selected
            roi = getattr(self._exp, "FullSensorRegion", None)
            rois = [roi] if roi is not None else []

        if not rois:
            return []

        return [self._roi_to_tuple(r) for r in rois]

    def get_current_roi_pixels(self):
        """
        Convenience: if there is exactly one selected region, return it as a tuple.
        Otherwise, return None (use get_selected_regions_pixels() instead).
        """
        regions = self.get_selected_regions_pixels()
        return regions[0] if len(regions) == 1 else None


if __name__ == "__main__":
    lf_spec = LightFieldSpectrometer(visible=True, file_path = "C:\\Users\\Femto\\Work Folders\\Documents\\LightField\\Experiments\\Daniel_exp.lfe")
    lf_spec.connect()
    print(lf_spec.is_connected())
    lf_spec.set_save_directory("C:\\temp\\Spectrometer_Data")
    lf_spec.set_filename(filename = "test_Daniel_2025_06_03")
    lf_spec.acquire_Data()
    lf_spec.close()
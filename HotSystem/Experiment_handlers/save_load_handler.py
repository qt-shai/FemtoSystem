import os
import csv
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Union
import sys
import json
from PIL import Image

def save_to_cvs(self, file_name, data, to_append: bool = False, header: str = None):
    print("Starting to save data to CSV.")

    # Ensure data is a dictionary
    if not isinstance(data, dict) or not all(isinstance(v, list) for v in data.values()):
        raise ValueError("Data must be a dictionary with list-like values.")

    # Find the length of the longest list
    max_length = max(len(values) for values in data.values())

    # Pad shorter lists with None
    for key in data:
        while len(data[key]) < max_length:
            data[key].append(None)

    # Check if file exists (to avoid rewriting headers when appending)
    file_exists = os.path.exists(file_name)

    try:
        # Open the file in append or write mode
        with open(file_name, mode='a' if to_append else 'w', newline='') as file:
            writer = csv.writer(file)

            # If writing a fresh file and header is provided → write header line first
            if not to_append and not file_exists and header:
                print("Writing custom header line...")
                file.write(header + "\n")

            # Write headers if not appending or file doesn't exist
            if not to_append or not file_exists:
                # print("Writing headers...")
                writer.writerow(data.keys())

            # Write data rows
            # print("Preparing to write rows...")
            zipped_rows = list(zip(*data.values()))
            print(f"Number of rows to write: {len(zipped_rows)}")

            writer.writerows(zipped_rows)
            # print("Rows written successfully.")

        print(f"Data successfully saved to {file_name}.")
        self.last_loaded_file = file_name

    except Exception as e:
        # Log the error with a timestamp
        error_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{error_time}] Error while writing to '{file_name}': {e}")

        # Fallback: Save to a new file location
        self.scanFN = self.create_scan_file_name(local=True)
        try:
            print(f"Attempting to save to fallback location: {self.scanFN}")
            with open(self.scanFN, mode='w', newline='') as fallback_file:
                writer = csv.writer(fallback_file)
                writer.writerow(data.keys())
                writer.writerows(zip(*data.values()))
            print(f"Data successfully saved to fallback location: {self.scanFN}")
        except Exception as fallback_error:
            fallback_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"[{fallback_time}] Critical error: Unable to save data to fallback location. Error: {fallback_error}")

def writeParametersToXML(self, fileName):
    self.to_xml(fileName)
    print("Parameters has been saved to", fileName)

def to_xml(self, filename="OPX_params.xml"):
    root = ET.Element("Parameters")

    for key, value in self.__dict__.items():
        if isinstance(value, (int, float, str, bool)):
            param = ET.SubElement(root, key)
            param.text = str(value)
            if False:
                print(str(key))

        elif isinstance(value, list):
            list_elem = ET.SubElement(root, key)
            if (list_elem.tag not in ["scan_Out", "X_vec", "Y_vec", "Z_vec", "X_vec_ref", "Y_vec_ref", "Z_vec_ref",
                                      "V_scan", "expected_pos", "t_vec",
                                      "startLoc", "endLoc", "Xv", "Yv", "Zv", "viewport_width", "viewport_height",
                                      "window_scale_factor",
                                      "timeStamp", "counter", "maintain_aspect_ratio", "scan_intensities",
                                      "V_scan",
                                      "absPosunits", "Scan_intensity", "Scan_matrix", "image_path", "f_vec",
                                      "signal", "ref_signal", "tracking_ref", "t_vec", "t_vec_ini"]
            ):
                for item in value:
                    item_elem = ET.SubElement(list_elem, "item")
                    item_elem.text = str(item)
            else:
                1
        elif isinstance(value, (np.ndarray)):
            list_elem = ET.SubElement(root, key)
            if list_elem.tag == "ZCalibrationData":
                for item in value:
                    item_elem = ET.SubElement(list_elem, "item")
                    for sub_item in item:
                        item_sub_elem = ET.SubElement(item_elem, "item")
                        item_sub_elem.text = str(sub_item)

    tree = ET.ElementTree(root)
    with open(filename, "wb") as f:
        tree.write(f)

def update_from_xml(self, filename="OPX_params.xml"):
    try:
        tree = ET.parse(filename)
        root = tree.getroot()

        # Get only the properties of the class
        properties = vars(self).keys()

        for param in root:
            # Update only if the parameter is a property of the class
            if param.tag in properties:

                if isinstance(getattr(self, param.tag), Union[list, np.ndarray]):
                    list_items = []
                    counter = 0
                    for item in param:
                        converted_item = self.convert_to_correct_type(attribute=param.tag, value=item.text,
                                                                      idx=counter)
                        list_items.append(converted_item)
                        counter += 1
                    setattr(self, param.tag,
                            list_items if isinstance(getattr(self, param.tag), list) else np.array(list_items))
                else:
                    # Convert text value from XML to appropriate type
                    value = self.convert_to_correct_type(param.tag, param.text)
                    setattr(self, param.tag, value)

    except Exception as ex:
        self.error = ("Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))

def saveExperimentsNotes(self, appdata=None, note=None):
    # dpg.set_value("text item", f"Mouse Button ID: {app_data}")
    self.expNotes = note
    self.HW.camera.imageNotes = note
    # if self.added_comments is not None:
    self.added_comments = note

def save_scan_data(self, Nx, Ny, Nz, fileName=None, to_append: bool = False):
    if fileName == None:
        fileName = self.create_scan_file_name()

    # parameters + note --- cause crash during scan. no need to update every slice.
    # self.writeParametersToXML(fileName + ".xml")

    # raw data
    Scan_array = np.array(self.scan_Out)
    if to_append:
        RawData_to_save = {'X': Scan_array[-Nx:, 0].tolist(), 'Y': Scan_array[-Nx:, 1].tolist(),
                           'Z': Scan_array[-Nx:, 2].tolist(),
                           'Intensity': Scan_array[-Nx:, 3].tolist(), 'Xexpected': Scan_array[-Nx:, 4].tolist(),
                           'Yexpected': Scan_array[-Nx:, 5].tolist(),
                           'Zexpected': Scan_array[-Nx:, 6].tolist(), }
        if np.shape(Scan_array)[1] > 7:
            RawData_to_save['Ref_signal'] = Scan_array[-Nx:, 7].tolist()
    else:
        RawData_to_save = {'X': Scan_array[:, 0].tolist(), 'Y': Scan_array[:, 1].tolist(),
                           'Z': Scan_array[:, 2].tolist(),
                           'Intensity': Scan_array[:, 3].tolist(), 'Xexpected': Scan_array[:, 4].tolist(),
                           'Yexpected': Scan_array[:, 5].tolist(),
                           'Zexpected': Scan_array[:, 6].tolist(), }

    self.save_to_cvs(fileName + ".csv", RawData_to_save, to_append)

    if self.stopScan != True:
        # prepare image for plot
        self.Scan_intensity = Scan_array[:, 3]
        # self.Scan_matrix = np.reshape(self.Scan_intensity,
        #                               (len(self.V_scan[2]), len(self.V_scan[1]), len(self.V_scan[0])))
        self.Scan_matrix = np.reshape(self.scan_intensities, (Nz, Ny, Nx))  # shai 30-7-24
        # Nz = int(len(self.V_scan[2]) / 2)
        slice2D = self.Scan_matrix[int(Nz / 2), :, :]  # ~ middle layer
        self.Save_2D_matrix2IMG(slice2D)

        # Convert the NumPy array to an image
        image = Image.fromarray(slice2D.astype(np.uint8))
        self.image_path = fileName + ".jpg"  # Save the image to a file
        image.save(self.image_path)

        self.scan_data = self.Scan_matrix
        self.idx_scan = [Nz - 1, 0, 0]

        if Scan_array.shape[0] > 1:
            self.startLoc = [Scan_array[1, 4] / 1e6,Scan_array[1, 5] / 1e6,Scan_array[1, 6] / 1e6]
        else:
            self.startLoc = [Scan_array[0, 4] / 1e6,Scan_array[0, 5] / 1e6,Scan_array[0, 6] / 1e6]

        if Nz == 0:
            self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3,
                           self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3, 0]
        else:
            self.endLoc = [self.startLoc[0] + self.dL_scan[0] * (Nx - 1) / 1e3,
                           self.startLoc[1] + self.dL_scan[1] * (Ny - 1) / 1e3,
                           self.startLoc[2] + self.dL_scan[2] * (Nz - 1) / 1e3]

        # self.Plot_Scan()

    return fileName

def btnLoadScan(self, sender=None, app_data=None, user_data=None):
    fn = None

    # 1) If a valid CSV filepath is passed
    if isinstance(app_data, str) and app_data.endswith(".csv"):
        fn = app_data

    # 2) If app_data is "last", try loading from last_scan_dir.txt
    elif app_data == "last":
        try:
            with open("last_scan_dir.txt", "r") as f:
                last_scan_dir = f.read().strip()
            if not last_scan_dir or not os.path.isdir(last_scan_dir):
                print(f"Invalid last scan dir: {last_scan_dir}")
                return
            csv_files = [
                os.path.join(last_scan_dir, f)
                for f in os.listdir(last_scan_dir)
                if f.lower().endswith(".csv") and not f.lower().endswith("_pulse_data.csv")
            ]
            if not csv_files:
                print("No valid CSVs in last scan dir.")
                return
            csv_files.sort(key=os.path.getmtime, reverse=True)
            fn = csv_files[0]
            print(f"Loaded from last dir: {fn}")
        except Exception as e:
            print(f"Failed loading from last dir: {e}")
            return

    # 3) Open dialog from last_scan_dir
    elif app_data == "open_from_last":
        try:
            initial_dir = "."
            if os.path.exists("last_scan_dir.txt"):
                with open("last_scan_dir.txt", "r") as f:
                    last_dir = f.read().strip()
                    if os.path.isdir(last_dir):
                        initial_dir = last_dir
            fn = open_file_dialog(
                filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
                initial_folder=initial_dir
            )
        except Exception as e:
            print(f"Failed to open dialog from last dir: {e}")
            return

    # 3) Else open dialog
    else:
        fn = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])

    if not fn:
        print("No file selected.")
        return

    # Save directory
    last_dir = os.path.dirname(fn)
    with open("last_scan_dir.txt", "w") as f:
        f.write(last_dir)

    # Load and plot
    data = loadFromCSV(fn)
    Scan_array = np.array(data, dtype=np.float64)

    x_unique = np.unique(Scan_array[:, 0])
    y_unique = np.unique(Scan_array[:, 1])
    z_unique = np.unique(Scan_array[:, 2])

    dx = x_unique[1] - x_unique[0] if len(x_unique) > 1 else 1
    dy = y_unique[1] - y_unique[0] if len(y_unique) > 1 else 1
    dz = z_unique[1] - z_unique[0] if len(z_unique) > 1 else 1

    Nx = int(round((x_unique[-1] - x_unique[0]) / dx)) + 1
    Ny = int(round((y_unique[-1] - y_unique[0]) / dy)) + 1
    Nz = int(round((z_unique[-1] - z_unique[0]) / dz)) + 1

    self.N_scan = [Nx, Ny, Nz]
    self.dL_scan = [dx * 1e-3, dy * 1e-3, dz * 1e-3]

    start_pos = [x_unique[0], y_unique[0], z_unique[0]]
    self.prepare_scan_data(x_unique[-1], x_unique[0], start_pos, Scan_array)

    self.idx_scan = [0, 0, 0]
    self.Plot_data(data, True)
    self.last_loaded_file = fn
    print(f"Loaded: {fn}")

def prepare_scan_data(self, max_position_x_scan, min_position_x_scan, start_pos, Scan_array = None):
        """
            Prepare self.scan_Out from raw Scan_array loaded from CSV or just scanned.
        """
        self.scan_Out = []

        if Scan_array is not None:
            x_vec = np.unique(Scan_array[:, 0])
            y_vec = np.unique(Scan_array[:, 1])
            z_vec = np.unique(Scan_array[:, 2])

            Nx = len(x_vec)
            Ny = len(y_vec)
            Nz = len(z_vec)

            for i in range(len(Scan_array)):
                x, y, z, I = Scan_array[i, 0], Scan_array[i, 1], Scan_array[i, 2], Scan_array[i, 3]
                self.scan_Out.append([x, y, z, I, x, y, z])
        else:
            x_vec = np.linspace(min_position_x_scan, max_position_x_scan, np.size(self.scan_intensities, 0), endpoint=False)
            y_vec = np.linspace(start_pos[1], start_pos[1] + self.L_scan[1] * 1e3, np.size(self.scan_intensities, 1), endpoint=False)
            z_vec = np.linspace(start_pos[2], start_pos[2] + self.L_scan[2] * 1e3, np.size(self.scan_intensities, 2), endpoint=False)
            for i in range(np.size(self.scan_intensities, 2)):
                for j in range(np.size(self.scan_intensities, 1)):
                    for k in range(np.size(self.scan_intensities, 0)):
                        x = x_vec[k]
                        y = y_vec[j]
                        z = z_vec[i]
                        I = self.scan_intensities[k, j, i]
                        self.scan_Out.append([x, y, z, I, x, y, z])
#New
def save_scan_parameters(self):
        data = {
            "dx": self.dL_scan[0],
            "dy": self.dL_scan[1],
            "dz": self.dL_scan[2],
            "Lx": self.L_scan[0],
            "Ly": self.L_scan[1],
            "Lz": self.L_scan[2]
        }
        with open("scan_parameters.json", "w") as f:
            json.dump(data, f)

def load_scan_parameters(self):
    try:
        with open("scan_parameters.json", "r") as f:
            data = json.load(f)
            self.dL_scan[0] = data.get("dx", self.dL_scan[0])
            self.dL_scan[1] = data.get("dy", self.dL_scan[1])
            self.dL_scan[2] = data.get("dz", self.dL_scan[2])
            self.L_scan[0] = data.get("Lx", self.L_scan[0])
            self.L_scan[1] = data.get("Ly", self.L_scan[1])
            self.L_scan[2] = data.get("Lz", self.L_scan[2])
    except FileNotFoundError:
        pass  # Use defaults if file doesn't exist

def move_last_saved_files(self, sender=None, app_data=None, user_data=None):
        try:
            files_to_move = []
            extensions = [".jpg", ".xml", ".png", ".csv"]

            if not hasattr(self, 'timeStamp') or not self.timeStamp:
                if hasattr(self, 'last_loaded_file') and self.last_loaded_file:
                    base, ext = os.path.splitext(self.last_loaded_file)
                    for extra_ext in extensions:
                        files_to_move.append(base + extra_ext)
                    print(f"Using last loaded file base: {base} -> with extensions: {extensions}")

                    # ✅ Add _pulse_data.csv, keep its unique name
                    base_with_notes = f"{base}_{self.expNotes}" if self.expNotes else base
                    pulse_data_file = base_with_notes + "_pulse_data.csv"
                    files_to_move.append(pulse_data_file)

                else:
                    print("No loaded file to move.")
                    return
            else:
                if self.survey:
                    folder_path = f"Q:/QT-Quantum_Optic_Lab/expData/Survey{self.HW.config.system_type}/scan"
                else:
                    folder_path = f"Q:/QT-Quantum_Optic_Lab/expData/scan/{self.HW.config.system_type}"

                base_file = os.path.join(folder_path, f"{self.timeStamp}_SCAN_{self.expNotes}")
                for ext in extensions:
                    files_to_move.append(base_file + ext)

                # ✅ Add _pulse_data.csv, keep suffix
                pulse_data_file = base_file + "_pulse_data.csv"
                files_to_move.append(pulse_data_file)

            subfolder = dpg.get_value("MoveSubfolderInput")
            if not subfolder:
                print("Subfolder name is empty.")
                return

            if self.survey:
                folder_path = f"Q:/QT-Quantum_Optic_Lab/expData/Survey{self.HW.config.system_type}/scan"
            else:
                folder_path = f"Q:/QT-Quantum_Optic_Lab/expData/scan/{self.HW.config.system_type}"

            new_folder = os.path.join(folder_path, subfolder)
            if not os.path.exists(new_folder):
                os.makedirs(new_folder)

            moved_any = False

            for src in files_to_move:
                dst = os.path.join(new_folder, os.path.basename(src))
                if os.path.exists(src):
                    shutil.move(src, dst)
                    print(f"Moved {src} → {dst}")
                    moved_any = True
                elif hasattr(self, 'timeStamp'):
                    # print(f"{src} does not exist.")
                    folder = os.path.dirname(src)
                    base_pattern = f"{self.timeStamp}_SCAN_"
                    found = False
                    for f in os.listdir(folder):
                        if f.startswith(base_pattern) and os.path.splitext(f)[1] == os.path.splitext(src)[1]:
                            old_src = os.path.join(folder, f)

                            # ✅ Special: do NOT rename if this is a _pulse_data.csv
                            if f.endswith("_pulse_data.csv"):
                                new_name = f  # Keep as is
                            else:
                                new_name = f"{self.timeStamp}_SCAN_{self.expNotes}{os.path.splitext(f)[1]}"

                            dst = os.path.join(new_folder, new_name)
                            shutil.copy(old_src, dst)
                            print(f"Copied {old_src} -> {dst} with new notes.")
                            moved_any = True
                            found = True
                    # if not found:
                    #     print(f"No alternative files found for {src}")
            if not moved_any:
                temp_folder = "C:/temp/TempScanData"
                if not os.path.exists(temp_folder):
                    print(f"Temp folder does not exist. Creating: {temp_folder}")
                    os.makedirs(temp_folder)
                for filename in os.listdir(temp_folder):
                    if hasattr(self, 'timeStamp') and self.timeStamp and filename.startswith(self.timeStamp):
                        src = os.path.join(temp_folder, filename)
                        dst = os.path.join(new_folder, filename)
                        shutil.move(src, dst)
                        print(f"Moved {src} -> {dst}")
                        moved_any = True

            # ✅ Fallback: Move last_loaded_file if nothing was moved
            if not moved_any and hasattr(self, 'last_loaded_file') and self.last_loaded_file:
                if os.path.exists(self.last_loaded_file):
                    base_name = os.path.basename(self.last_loaded_file)
                    name, ext = os.path.splitext(base_name)
                    new_name = f"{name}_{self.expNotes}{ext}" if self.expNotes else base_name
                    dst = os.path.join(new_folder, new_name)
                    shutil.copy(self.last_loaded_file, dst)
                    print(f"Copied last loaded file to {dst} with updated name.")
                    moved_any = True
                else:
                    print(f"Last loaded file does not exist: {self.last_loaded_file}")

            try:
                with open("last_scan_dir.txt", "w") as lf:
                    lf.write(new_folder)
                print(f"Updated last_scan_dir.txt -> {new_folder}")
            except Exception as e:
                print(f"Failed to update last_scan_dir.txt: {e}")

        except Exception as e:
            print(f"Error moving files: {e}")

# not done need to be tested and verify bugs free
def Save_2D_matrix2IMG(self, array_2d, fileName="fileName", img_format='png'):
        image = Image.fromarray(array_2d.astype(np.uint8))  # Convert the NumPy array to an image
        self.image_path = fileName + "." + img_format  # Save the image to a file
        image.save(self.image_path)

def Plot_Loaded_Scan(self, use_fast_rgb: bool = False,show_only_xy: bool = True):
        try:
            start_Plot_time = time.time()

            plot_size = [int(self.viewport_width * 0.2), int(self.viewport_height * 0.4)]

            # Check if scan_data and idx_scan are available
            if self.scan_data is None or self.idx_scan is None:
                raise ValueError("Scan data or index scan is not available.")

            # Prepare scan data arrays
            arrYZ = np.flipud(self.scan_data[:, :, self.idx_scan[Axis.X.value]])
            arrXZ = np.flipud(self.scan_data[:, self.idx_scan[Axis.Y.value], :])
            arrXY = np.flipud(self.scan_data[self.idx_scan[Axis.Z.value], :, :])

            if self.limit:
                limit = dpg.get_value("inInt_limit")
                arrXY = np.where(arrXY > limit, limit, arrXY)

            def safe_normalize(arr):
                max_val = np.nanmax(arr)
                return (arr * 255 / max_val) if max_val > 0 else np.zeros_like(arr)

            result_arrayXY = safe_normalize(arrXY)
            result_arrayXZ = safe_normalize(arrXZ)
            result_arrayYZ = safe_normalize(arrYZ)

            result_arrayXY_ = []
            result_arrayXZ_ = []
            result_arrayYZ_ = []

            # Convert intensity values to RGB
            if use_fast_rgb:
                result_arrayXY_ = self.fast_rgb_convert(result_arrayXY)
                result_arrayXZ_ = self.fast_rgb_convert(result_arrayXZ)
                result_arrayYZ_ = self.fast_rgb_convert(result_arrayYZ)
            else:
                for arr, result_array in zip([arrXY, arrXZ, arrYZ],
                                             [result_arrayXY_, result_arrayXZ_, result_arrayYZ_]):
                    for i in range(arr.shape[0]):
                        for j in range(arr.shape[1]):
                            res = self.intensity_to_rgb_heatmap(arr.astype(np.uint8)[i][j] / 255)
                            result_array.extend([res[0] / 255, res[1] / 255, res[2] / 255, res[3] / 255])

            # Delete previous items if they exist
            for item in ["scan_group", "texture_reg", "textureXY_tag", "textureXZ_tag", "textureYZ_tag"]:
                if dpg.does_item_exist(item):
                    dpg.delete_item(item)

            # Add textures
            dpg.add_texture_registry(show=False, tag="texture_reg")
            dpg.add_dynamic_texture(width=arrXY.shape[1], height=arrXY.shape[0], default_value=result_arrayXY_,
                                    tag="textureXY_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrXZ.shape[1], height=arrXZ.shape[0], default_value=result_arrayXZ_,
                                    tag="textureXZ_tag",
                                    parent="texture_reg")
            dpg.add_dynamic_texture(width=arrYZ.shape[1], height=arrYZ.shape[0], default_value=result_arrayYZ_,
                                    tag="textureYZ_tag",
                                    parent="texture_reg")

            # Plot scan
            dpg.add_group(horizontal=True, tag="scan_group", parent="Scan_Window")

            # XY plot
            dpg.add_plot(parent="scan_group", tag="plotImaga", width=plot_size[0], height=plot_size[1],
                         equal_aspects=True, crosshairs=True,
                         query=True, callback=self.queryXY_callback)
            dpg.add_plot_axis(dpg.mvXAxis, label="x axis, z=" + "{0:.2f}".format(self.Zv[self.idx_scan[Axis.Z.value]]),
                              parent="plotImaga",tag="plotImaga_X")
            dpg.add_plot_axis(dpg.mvYAxis, label="y axis", parent="plotImaga", tag="plotImaga_Y")

            if self.system_name == SystemType.FEMTO.value:
                bounds_min_xy = [float(self.startLoc[0]) / 1e6, float(self.startLoc[1]) / 1e6]
                bounds_max_xy = [float(self.endLoc[0]) / 1e6, float(self.endLoc[1]) / 1e6]
            else:
                bounds_min_xy = [float(self.startLoc[0]), float(self.startLoc[1])]
                bounds_max_xy = [float(self.endLoc[0]), float(self.endLoc[1])]

            dpg.add_image_series(texture_tag="textureXY_tag",
                                 bounds_min=bounds_min_xy,
                                 bounds_max=bounds_max_xy,
                                 label="Scan data",
                                 parent="plotImaga_Y")

            dpg.add_colormap_scale(show=True, parent="scan_group", tag="colormapXY", min_scale=np.min(arrXY),
                                   max_scale=np.max(arrXY),
                                   colormap=dpg.mvPlotColormap_Jet)

            # ✅ Apply persistent graph size override if exists
            if hasattr(self, "graph_size_override") and self.graph_size_override:
                w, h = self.graph_size_override
                dpg.set_item_width("plotImaga", w)
                dpg.set_item_height("plotImaga", h)
                print(f"Graph resized to override: {w}×{h}")

            # Update width based on conditions
            item_width = dpg.get_item_width("plotImaga")
            item_height = dpg.get_item_height("plotImaga")
            if (item_width is None) or (item_height is None):
                raise Exception("Window does not exist")

            end_Plot_time = time.time()
            print(f"time to plot scan: {end_Plot_time - start_Plot_time}")
        except Exception as e:
            print(f"An error occurred while plotting the scan: {e}")

def btnSave(self, folder=None):  # save data
        print("Saving data...")
        try:
            # file name
            # timeStamp = self.getCurrentTimeStamp()  # get current time stamp
            self.timeStamp = self.getCurrentTimeStamp()

            if folder is None:
                # folder_path = 'Q:/QT-Quantum_Optic_Lab/expData/' + (fr'Survey{self.HW.config.system_type}/' if self.survey else '') + self.exp.name + '/'
                folder_path = f'Q:/QT-Quantum_Optic_Lab/expData/' + self.exp.name + f'/{self.HW.config.system_type}'
            else:
                folder_path = folder + (fr'Survey{self.HW.config.system_type}/' if self.survey else '') + self.exp.name + '/'

            if not os.path.exists(folder_path):  # Ensure the folder exists, create if not
                os.makedirs(folder_path)
            if self.exp == Experiment.RandomBenchmark:
                #self.added_comments = dpg.get_value("inTxtOPX_expText")
                if self.added_comments is not None:
                    fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name + '_' + self.added_comments)
                else:
                    fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name)
            else:
                fileName = os.path.join(folder_path, self.timeStamp + '_' + self.exp.name+ '_' + self.expNotes)
            # fileName = os.path.join(folder_path, self.timeStamp + self.exp.name)

            # parameters + note
            self.writeParametersToXML(fileName + ".xml")
            print(f'XML file saved to {fileName}.xml')
            self.to_xml()

            # raw data
            if self.exp == Experiment.RandomBenchmark:
                RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y_ref2': self.Y_vec_ref2,'Gate_Order': self.benchmark_number_order, 'Y_vec_squared': self.Y_vec_squared, 'Y_ref3': self.Y_vec_ref3}
            elif self.exp == Experiment.NUCLEAR_MR:
                RawData_to_save = {'X': self.X_vec, 'Y': self.Y_vec, 'Y_ref': self.Y_vec_ref, 'Y2': self.Y_vec2, 'Y_ref2': self.Y_vec_ref2}
            elif self.exp == Experiment.TIME_BIN_ENTANGLEMENT:
                # Modify below to have some pre-post-processed data for further data analysis
                if self.simulation:
                    RawData_to_save = {'Iteration': self.iteration_list.tolist(), 'Times': self.times_by_measurement,
                                       'Total_Counts': self.signal.tolist(),
                                       'Counts_stat': self.Y_vec_2.tolist(), f'Counts_Bin_1_{self.bin_times[0][0]}:{self.bin_times[0][1]}': self.counts_in_bin1,
                                       f'Counts_Bin_2_{self.bin_times[1][0]}:{self.bin_times[1][1]}': self.counts_in_bin2, f'Counts_Bin_3_{self.bin_times[2][0]}:{self.bin_times[2][1]}': self.counts_in_bin3,
                                       'Pulse_type': self.list_of_pulse_type, 'awg_freq': self.awg_freq_list}
                else:
                    RawData_to_save = {'Iteration': self.iteration_list.tolist(), 'Times': self.times_by_measurement,
                                       'Total_Counts': self.signal.tolist(),
                                       'Counts_stat': self.Y_vec_2.tolist(),
                                       f'Counts_Bin_1_{self.bin_times[0][0]}:{self.bin_times[0][1]}': self.counts_in_bin1,
                                       f'Counts_Bin_2_{self.bin_times[1][0]}:{self.bin_times[1][1]}': self.counts_in_bin2,
                                       f'Counts_Bin_3_{self.bin_times[2][0]}:{self.bin_times[2][1]}': self.counts_in_bin3,
                                       'Pulse_type': self.list_of_pulse_type}
            else:
                RawData_to_save = {
                    'X': self.X_vec if isinstance(self.X_vec, list) else list(self.X_vec),
                    'Y': self.Y_vec if isinstance(self.Y_vec, list) else list(self.Y_vec),
                    'Y_ref': self.Y_vec_ref if isinstance(self.Y_vec_ref, list) else list(self.Y_vec_ref),
                    'Y_ref2': self.Y_vec_ref2 if isinstance(self.Y_vec_ref2, list) else list(self.Y_vec_ref2),
                    'Y_resCalc': self.Y_resCalculated if isinstance(self.Y_resCalculated, list) else list(self.Y_resCalculated)
                }

            self.save_to_cvs(fileName + ".csv", RawData_to_save, to_append=True)
            if self.exp == Experiment.AWG_FP_SCAN:
                RawData_to_save['Y_Aggregated'] = self.Y_vec_aggregated

            self.save_to_cvs(fileName + ".csv", RawData_to_save)
            print(f"CSV file saved to {fileName}.csv")

            # save data as image (using matplotlib)
            if folder is None and self.exp != Experiment.TIME_BIN_ENTANGLEMENT:
                width = 1920  # Set the width of the image
                height = 1080  # Set the height of the image
                # Create a blank figure with the specified width and height, Convert width and height to inches
                fig, ax = plt.subplots(figsize=(width / 100, height / 100), visible=True)
                plt.plot(self.X_vec, self.Y_vec, label='data')  # Plot Y_vec
                plt.plot(self.X_vec, self.Y_vec_ref, label='ref')  # Plot reference

                # Adjust axes limits (optional)
                # ax.set_xlim(0, 10)
                # ax.set_ylim(-1, 1)

                # Add legend
                plt.legend()

                # Save the figure as a PNG file
                plt.savefig(fileName + '.png', format='png', dpi=300, bbox_inches='tight')
                print(f"Figure saved to {fileName}.png")
                # close figure
                plt.close(fig)

                dpg.set_value("inTxtOPX_expText", "data saved to: " + fileName + ".csv")

        except Exception as ex:
            self.error = (
                "Unexpected error: {}, {} in line: {}".format(ex, type(ex), (sys.exc_info()[-1].tb_lineno)))  # raise
            print(f"Error while saving data: {ex}")
import time
from abc import ABC
from typing import Any, Callable, Generic, TypeVar, Optional

from numpy import ndarray

T = TypeVar('T')
import serial
from serial.tools import list_ports
import math
import tkinter as tk
import csv
from tkinter import filedialog
import numpy as np
import pandas as pd
from typing import Tuple, Union, List
from matplotlib import pyplot as plt
import os
from tkinter import Tk
from tkinter.filedialog import askopenfilename


def load_scan_plane_calibration_data(file_path: str) -> np.ndarray:
    """
    Load the calibration matrix from a CSV file.

    :param file_path: Path to the CSV file containing the calibration matrix.
    :return: A 3x3 numpy array representing the calibration matrix.
    """
    calibration_matrix = pd.read_csv(file_path, header=None).values
    if calibration_matrix.shape != (3, 3):
        raise ValueError("Calibration matrix must be 3x3.")
    return calibration_matrix


def save_scan_plane_calibration_data(file_path: str, plane_calibration_matrix: np.ndarray) -> None:
    """
    Save the calibration matrix to a CSV file.

    :param file_path: Path to the CSV file where the calibration matrix will be saved.
    :param plane_calibration_matrix: A 3x3 numpy array representing the calibration matrix.
    """
    if plane_calibration_matrix.shape != (3, 3):
        raise ValueError("Calibration matrix must be 3x3.")
    pd.DataFrame(plane_calibration_matrix).to_csv(file_path, header=False, index=False)


def calculate_plane_normal(plane_calibration_matrix: np.ndarray) -> Tuple[np.ndarray, float]:
    """
    Calculate the normal vector to the plane defined by the calibration matrix and the plane constant d.

    :param plane_calibration_matrix: A 3x3 numpy array representing the calibration matrix.
    :return: A tuple containing the normalized normal vector and the plane constant d.
    """
    p1 = plane_calibration_matrix[0,:].astype(float)
    p2 = plane_calibration_matrix[1,:].astype(float)
    p3 = plane_calibration_matrix[2,:].astype(float)
    v1 = p2 - p1
    v2 = p3 - p1

    print((v1, v2))

    normal = np.cross(v1, v2) # cross product not normalized to unit vector

    if np.linalg.norm(normal) == 0:
        #raise ValueError("Normal vector cannot be zero.")
        print("Normal vector is zero.")
        return normal, 0

    normal = normal / np.linalg.norm(normal)  # Normalize the vector

    d = np.dot(normal, p1)  # note: Plane equation is  Ax + By + Cz = d
    return normal, d

    # x, y, z = plane_calibration_matrix[:, 0], plane_calibration_matrix[:, 1], plane_calibration_matrix[:, 2]
    # v1 = np.array([float(x[1] - x[0]), float(y[1] - y[0]), float(z[1] - z[0])])
    # v2 = np.array([float(x[2] - x[0]), float(y[2] - y[0]), float(z[2] - z[0])])

    # normal = np.cross(v1, v2) # cross product not normalized to unit vector
    # if np.linalg.norm(normal) == 0:
    #     raise ValueError("Normal vector cannot be zero.")
    # normal = normal / np.linalg.norm(normal)  # Normalize the vector

    # d = np.dot(normal, np.array([x[0], y[0], z[0]]))  # Plane equation constant
    # return normal, d

def generate_z_series(normal: np.ndarray, d: float, x_series: np.ndarray, y_const: float) -> np.ndarray:
    """
    Generate the z values along the x-axis for a given plane.

    :param normal: The normalized normal vector of the plane.
    :param d: The plane constant d.
    :param x_series: Array of x-coordinates along the x-axis.
    :param y_const: Constant y-coordinate.
    :return: Array of corresponding z values along the x-axis.
    """
    a, b, c = normal
    # Avoid division by zero by checking if c is zero
    if c == 0:
        print("Warning: 'c' value is zero. Returning zero array for z-series.")
        return np.zeros_like(x_series)  # Return a zero array with the same shape as x_series

    # Calculate z values based on the plane equation: Ax + By + Cz = d
    z_series = (d - a * x_series.astype(float) - b * y_const) / c
    return z_series



def calculate_z_series(calibration_matrix: np.ndarray, x_series: np.ndarray, y_const: float) -> np.ndarray:
    """
    Calculate the z values along the x-axis for the plane defined by the calibration matrix.

    :param calibration_matrix: A 3x3 numpy array representing the calibration matrix.
    :param x_series: Array of x-coordinates along the x-axis.
    :param y_const: Constant y-coordinate for the x-axis points.
    :return: Array of corresponding z values along the x-axis.
    """
    # pdb.set_trace()  # Insert a manual breakpoint
    normal, d = calculate_plane_normal(calibration_matrix)
    z_series = generate_z_series(normal, d, x_series, y_const)
    return z_series


def generate_scan_points(step_size_nm: float = 200, block_size_um: float = 100,
                         block_spacing_x_um: float = 300, block_spacing_y_um: float = 300,
                         matrix_size: int = 5, buffer_um: float = 5) -> np.ndarray:
    """
    Generate an X, Y point array for a scan within a matrix of blocks including a buffer.

    :param step_size_nm: The step size in nanometers.
    :param block_size_um: The size of each block in micrometers.
    :param block_spacing_x_um: Spacing between blocks along the X axis in micrometers.
    :param block_spacing_y_um: Spacing between blocks along the Y axis in micrometers.
    :param matrix_size: The number of blocks along each axis.
    :param buffer_um: The buffer/margin around each block to be included in the scan.
    :return: A numpy array of scan points [N, 2] where N is the total number of points.
    """
    step_size_um = step_size_nm / 1000  # Convert step size to micrometers

    # Adjust block size to include the buffer
    total_block_size_um = block_size_um + 2 * buffer_um

    # Number of steps within the block + buffer
    num_steps_per_block = int(total_block_size_um / step_size_um)

    # Generate points within a single block including buffer
    x_points_within_block = np.arange(-buffer_um, block_size_um + buffer_um, step_size_um)
    y_points_within_block = np.arange(-buffer_um, block_size_um + buffer_um, step_size_um)

    # Generate grid points within a block
    x_grid, y_grid = np.meshgrid(x_points_within_block, y_points_within_block)
    block_points = np.vstack([x_grid.ravel(), y_grid.ravel()]).T

    all_points = []

    # Iterate through the matrix to position each block
    for i in range(matrix_size):
        for j in range(matrix_size):
            x_offset = i * (block_size_um + block_spacing_x_um)
            y_offset = j * (block_size_um + block_spacing_y_um)

            # Translate the block points
            translated_points = block_points + np.array([x_offset, y_offset])
            all_points.append(translated_points)

    # Combine all points into a single array
    all_points = np.array(np.vstack(all_points)) * 1e6  # 1[µm] = 1e6[pm]

    return all_points


def generate_scan_vectors(step_size_nm: float = 200, block_size_um: float = 100,
                          block_spacing_x_um: float = 300, block_spacing_y_um: float = 300,
                          matrix_size: int = 5, buffer_um: float = 10) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate X and Y vectors for a scan within a matrix of blocks including a buffer.
    The points are arranged so that each block's points are stored together in the vectors.

    :param step_size_nm: The step size in nanometers.
    :param block_size_um: The size of each block in micrometers.
    :param block_spacing_x_um: Spacing between blocks along the X axis in micrometers.
    :param block_spacing_y_um: Spacing between blocks along the Y axis in micrometers.
    :param matrix_size: The number of blocks along each axis.
    :param buffer_um: The buffer/margin around each block to be included in the scan.
    :return: Two numpy arrays, x_vec and y_vec, containing all X and Y coordinates of the scan points in pm.
    """
    step_size_um = step_size_nm / 1000  # Convert step size to micrometers

    # Adjust block size to include the buffer
    total_block_size_um = block_size_um + 2 * buffer_um

    # Generate points within a single block including buffer
    x_points_within_block = np.arange(-buffer_um, block_size_um + buffer_um, step_size_um)
    y_points_within_block = np.arange(-buffer_um, block_size_um + buffer_um, step_size_um)

    all_x_points = []
    all_y_points = []

    # Iterate through the matrix to position each block
    for i in range(matrix_size):
        for j in range(matrix_size):
            x_offset = i * (block_size_um + block_spacing_x_um)
            y_offset = j * (block_size_um + block_spacing_y_um)

            # Translate the block points and append to the lists
            all_x_points.extend(x_points_within_block + x_offset)
            all_y_points.extend(y_points_within_block + y_offset)

    # Convert the lists to numpy arrays
    x_vec = np.array(all_x_points)*1e6  # 1[µm] = 1e6[pm]
    y_vec = np.array(all_y_points)*1e6  # 1[µm] = 1e6[pm]

    return x_vec, y_vec


def scatter_scan_points(scan_points: np.ndarray, title: str = "Scan Points") -> None:
    """
    Scatter plots the given scan points.

    :param scan_points: A numpy array of scan points [N, 2] where N is the total number of points.
    :param title: The title of the plot.
    """
    plt.figure(figsize=(8, 8))
    plt.scatter(scan_points[:, 0]*1e-6, scan_points[:, 1]*1e-6, s=1, color='red')
    plt.title(title)
    plt.xlabel("X (µm)")
    plt.ylabel("Y (µm)")
    plt.grid(True)
    plt.gca().set_aspect('equal', adjustable='box')
    plt.show()


def intensity_to_rgb_heatmap_normalized(intensities: Union[float, np.ndarray], cmap=plt.get_cmap('jet')) -> np.ndarray:
    """
    Convert intensity values to RGB colors using a heatmap.

    :param intensities: A float or a NumPy array (1D, 2D, or 3D) of intensity values.
    :param cmap: The colormap to use (default is 'jet').
    :return: A NumPy array of RGB colors.
    """
    # Ensure intensities are within the range [0, 1)
    intensities = np.clip(intensities, 0, 0.99999999)

    # Map the intensity values to RGBA colors using the colormap
    rgba_colors = cmap(intensities)

    # Convert RGBA to RGB by discarding the alpha channel and scaling
    rgb_colors = (rgba_colors[..., :3])

    return rgb_colors


def get_available_xml_files(folder_path: str) -> List[str]:
    """
    Get a list of all XML files in the specified folder.

    :param folder_path: The path to the folder containing XML files.
    :return: A list of XML file paths.
    """
    # List all XML files in the specified folder
    xml_files = [file for file in os.listdir(folder_path) if file.endswith(".xml")]
    if not xml_files:
        raise FileNotFoundError(f"No XML files found in the specified folder: {folder_path}")
    return xml_files

def get_square_matrix_size(num_items):
    """
    Calculate the size of the square matrix needed to accommodate the given number of items.

    :param num_items: Total number of items to accommodate.
    :return: Number of rows and columns for the square matrix.
    """
    size = math.ceil(math.sqrt(num_items))
    return size


def open_file_dialog(initial_folder: str = "", title: str = "", filetypes=None, select_folder: bool = False) -> str:
    """
    Open a file dialog to select an XML file or a folder.

    :param initial_folder: The initial folder path to open in the dialog.
    :param title: The title of the dialog.
    :param filetypes: A tuple of file types to open in the dialog (ignored if select_folder is True).
    :param select_folder: If True, open a folder selection dialog instead of a file selection dialog.
    :return: The selected file or folder path, or an empty string if nothing is selected.
    """
    import tkinter as tk
    from tkinter import filedialog

    if filetypes is None:
        filetypes = [("All Files", "*.*")]

    root = tk.Tk()  # Create the root window
    root.withdraw()  # Hide the main window

    if select_folder:
        path = filedialog.askdirectory(initialdir=initial_folder, title=title)
    else:
        path = filedialog.askopenfilename(initialdir=initial_folder, title=title, filetypes=filetypes)

    if path:
        print(f"Selected {'folder' if select_folder else 'file'}: {path}")
    else:
        print(f"No {'folder' if select_folder else 'file'} selected")

    root.destroy()  # Close the main window

    return path


def remove_overlap_from_string(left_string: str, right_string: str) -> str:
    """
    Remove the overlapping part of the right string that matches the suffix of the left string.

    :param left_string: The left string from which to find the overlapping suffix.
    :param right_string: The right string from which to remove the overlapping prefix.
    :return: The right string with the overlapping part removed.
    """
    # Find the maximum possible overlap
    max_overlap_len = min(len(left_string), len(right_string))

    # Find the longest overlapping suffix in left_string and prefix in right_string
    for i in range(max_overlap_len, 0, -1):
        if left_string[-i:] == right_string[:i]:
            # Return the right_string with the overlapping part removed
            return right_string[i:]

    # If no overlap is found, return the right string as-is
    return right_string
def open_dialog():  # move to common
    root = tk.Tk()  # Create the root window
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename()  # Open a file dialog

    if file_path:  # Check if a file was selected
        print(f"Selected file: {file_path}")  # add to logger
    else:
        print("No file selected")  # add to logger

    root.destroy()  # Close the main window if your application has finished using it

    return file_path

def loadFromCSV(file_name):
    data = []
    with open(file_name, 'r', newline='') as file:
        reader = csv.reader(file)
        for row in reader:
            data.append(row)
    del data[0]
    return data

def fast_rgb_convert(array2d):
    # Mask for non-zero values
    mask_non_zero = array2d > 0
    normalized_array = np.zeros_like(array2d, dtype=float)

    if np.any(mask_non_zero):
        # Normalize non-zero values to stretch across the entire color scale
        normalized_array[mask_non_zero] = array2d[mask_non_zero] / array2d[mask_non_zero].max()
    # Generate the RGB heatmap, ignoring zeros
    result_array_ = intensity_to_rgb_heatmap_normalized(normalized_array.T)
    # Add the alpha channel: 1 for non-zero values, 0 for zero values
    alpha_channel = mask_non_zero.T.astype(float)
    # Concatenate the alpha channel
    result_array_ = np.concatenate([result_array_, alpha_channel[..., np.newaxis]], axis=-1)
    result_array_ = np.flipud(result_array_)
    # Reshape to the desired format
    result_array_ = result_array_.reshape(-1)
    return result_array_

def select_csv_file() -> str:
    """
    Open a file dialog to select a CSV file.

    :return: Path to the selected CSV file.
    """
    Tk().withdraw()
    file_path = askopenfilename(filetypes=[("CSV files", "*.csv")])
    return file_path





def scan_com_ports(baudrate=9600, timeout=1, query_command="*IDN?\r\n"):
    """
    Scans all available COM ports, attempts to query each device for an IDN,
    and returns a dictionary of {port: IDN response} for ports that respond successfully.

    Parameters
    ----------
    baudrate : int
        The baud rate for the serial communication. Default is 9600.
    timeout : float
        The read/write timeout (in seconds). Default is 1 second.
    query_command : str
        The SCPI or other command to send to the device to request its identity.
        By default, '*IDN?' with CR-LF newline is used.

    Returns
    -------
    dict
        A dictionary where keys are the port names (e.g., 'COM3', '/dev/ttyUSB0')
        and values are the device IDN strings, or an error message if something went wrong.
    """
    print("Scanning for COM ports")
    # Dictionary to store results: {port: <idn_or_error>}
    results = {}

    # List all possible serial ports
    available_ports = list_ports.comports()
    print(f"Found {len(available_ports)} COM ports: {[port.device for port in available_ports]}")
    if not available_ports:
        # If no COM ports are found, return an empty dictionary or handle as needed
        return results

    # Iterate over each detected port
    for port_info in available_ports:
        port_name = port_info.device
        port_description = port_info.description
        print(f"Testing COM port {port_name}")
        # Initialize the result with a default message in case something fails
        results[port_name] = "No response or error occurred" if "Bluetooth" not in port_description else "Bluetooth device found"

        if "Bluetooth" in port_description:
            continue

        try:
            with serial.Serial(port=port_name, baudrate=baudrate, timeout=timeout, write_timeout=timeout) as ser:
                # Clear buffers before use
                ser.reset_input_buffer()
                ser.reset_output_buffer()


                time.sleep(50e-3)
                # Send the query command
                ser.write(query_command.encode("utf-8"))

                time.sleep(50e-3)
                # Read the response (try reading one line or up to a certain size)
                response = ser.readline().decode(errors="ignore").strip()

                # If no response, keep the default
                if response:
                    results[port_name] = response
                    print(f"Established connection with port {port_name}")

        except serial.SerialException as e:
            # Catch any serial-related errors (e.g., access denied, device removal, etc.)
            results[port_name] = f"SerialException: {str(e)}"
        except UnicodeDecodeError as e:
            # Catch issues decoding response
            results[port_name] = f"UnicodeDecodeError: {str(e)}"
        except Exception as e:
            # Catch-all for any other unforeseen exceptions
            results[port_name] = f"Exception: {str(e)}"

    print(results)
    return results

class ObserverInterface(ABC):
    """
    An interface for managing observers and notifying them of updates.
    """

    def __init__(self) -> None:
        self._observers: List[Callable[[Any], None]] = []

    def add_observer(self, observer: Callable[[Any], None]) -> None:
        """
        Add an observer callback.

        :param observer: A callable accepting a single argument (data).
        """
        if not callable(observer):
            raise ValueError("Observer must be callable.")
        self._observers.append(observer)

    def remove_observer(self, observer: Callable[[Any], None]) -> None:
        """
        Remove a previously registered observer callback.

        :param observer: The observer to remove.
        """
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, data: Any) -> None:
        """
        Notify all observers with the provided data.

        :param data: The data to pass to all registered observers.
        """
        for callback in self._observers:
            try:
                callback(data)
            except Exception as e:
                print(f"Error notifying observer: {e}")



class ObservableField(Generic[T], ObserverInterface):
    """
    A field that notifies observers on changes and integrates with the ObserverInterface.
    """

    def __init__(self, initial_value: T):
        """
        Initialize the observable field with an initial value.

        :param initial_value: The initial value of the field.
        """
        super().__init__()
        self._value = initial_value

    def get(self) -> T:
        """Retrieve the value."""
        return self._value

    def set(self, value: T) -> None:
        """
        Set the value and notify observers.

        :param value: The new value to set.
        """
        self._value = value
        self.notify_observers(value)

def is_within_bounds(value: float, bounds: tuple[float, float]) -> bool:
    """
    Checks if a given value is within the specified bounds.

    :param value: The value to check.
    :param bounds: A tuple containing the lower and upper bounds (inclusive).
    :return: True if the value is within bounds, False otherwise.
    """
    if not isinstance(bounds, tuple) or len(bounds) != 2:
        raise ValueError("Bounds must be a tuple with two elements: (lower_bound, upper_bound).")
    lower_bound, upper_bound = bounds
    if lower_bound > upper_bound:
        raise ValueError("Invalid bounds: lower_bound must be less than or equal to upper_bound.")
    return lower_bound <= value <= upper_bound

def fit_parabola(x_data: np.ndarray, y_data: np.ndarray) -> Tuple[float, float, float]:
    """
    Fit a parabola (quadratic polynomial) to the given x_data and y_data.
    Returns the polynomial coefficients (a, b, c) for ax^2 + bx + c.

    :param x_data: NumPy array of x-values.
    :param y_data: NumPy array of y-values.
    :return: (a, b, c) polynomial coefficients.
    """
    if len(x_data) < 3 or len(y_data) < 3:
        raise ValueError("At least 3 points are required to fit a parabola.")

    if len(x_data) != len(y_data):
        raise ValueError("x_data and y_data must have the same length.")

    # Fit a quadratic polynomial (2nd-degree) to the data
    coeffs = np.polyfit(x_data, y_data, 2)  # Returns [a, b, c] for ax^2 + bx + c
    return coeffs[0], coeffs[1], coeffs[2]


def find_parabola_minimum(a: float, b: float, c: float) -> Optional[float]:
    """
    Find the x-position of the minimum of a parabola described by ax^2 + bx + c.
    If the parabola has a maximum (a < 0), return None.

    :param a: Quadratic coefficient.
    :param b: Linear coefficient.
    :param c: Constant term.
    :return: The x-coordinate of the parabola's minimum, or None if the parabola has a maximum.
    """
    if a == 0:
        raise ValueError("Coefficient 'a' cannot be zero for a parabola.")

    if a < 0:
        return None  # Parabola has a maximum, not a minimum

    return -b / (2.0 * a)

def create_gaussian_vector(nx: int, center: float = 2, width: float = 4) -> np.ndarray:
    """
    Create a NumPy vector with Nx points, with a Gaussian centered at Nx/center and a width of Nx/width.

    :param nx: Number of points in the vector.
    :param center: Factor to determine the center of the Gaussian as Nx/center. Default is 2.
    :param width: Factor to determine the width of the Gaussian as Nx/width. Default is 4.
    :return: NumPy array containing the Gaussian vector.
    """
    if nx <= 0:
        raise ValueError("Number of points (nx) must be a positive integer.")

    x = np.linspace(0, nx - 1, nx)  # Create an array of Nx points
    center_value = nx / center  # Gaussian center
    width_value = nx / width  # Gaussian width (standard deviation)

    gaussian = np.exp(-((x - center_value) ** 2) / (2 * (width_value ** 2)))  # Gaussian formula
    return gaussian

def create_counts_vector(vector_size: int) -> np.ndarray:
    # Define the valid indices where 1 can appear:
    valid_indices = list(range(0, 26)) + list(range(46, 72)) + list(range(71, 96))

    # Initialize a 2D NumPy array of zeros (num_vectors rows, k columns)
    counts = np.zeros((vector_size), dtype=int)
    if np.random.rand() < 0.5:
        # Pick one random valid index
        i = np.random.choice(valid_indices)
        counts[i] = 1
    return counts

def reshape_and_pad_scan_counts(scan_counts: np.ndarray, Nx: int, Ny: int, Nz: int) -> np.ndarray:
    """
    Reshape and pad a partially filled 1D array into a 3D array with dimensions (Nx, Ny, Nz).

    :param scan_counts: Flattened array of scan counts (partially filled).
    :param Nx: Target size of the X-dimension.
    :param Ny: Nominal size of the Y-dimension.
    :param Nz: Target size of the Z-dimension.
    :return: Reshaped and padded 3D array of scan counts.
    """
    # Flatten the input array to ensure compatibility
    flattened_data = np.array(scan_counts).flatten()

    # Calculate the total number of elements in a single XY slice
    slice_size = Nx * Nz

    # Calculate the total number of required elements for the full 3D array
    total_required_elements = Nx * Ny * Nz

    # Pad the flattened array to match the total required elements
    if len(flattened_data) < total_required_elements:
        padding_size = total_required_elements - len(flattened_data)
        flattened_data = np.pad(flattened_data, (0, padding_size), constant_values=0)
    elif len(flattened_data) > total_required_elements:
        flattened_data = flattened_data[:total_required_elements]

    # Reshape the padded array into the desired 3D shape
    reshaped_data = flattened_data.reshape(Nx, Ny, Nz)

    return reshaped_data

def test_reshape_and_pad_scan_counts():
    """Run a series of tests on the reshape_and_pad_scan_counts function."""
    # Test case 1: Perfectly filled array
    scan_counts = np.arange(50)  # 10x5x1
    Nx, Ny, Nz = 10, 5, 1
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (10, 5, 1), f"Unexpected shape: {result.shape}"

    # Test case 2: Incomplete array requiring padding
    scan_counts = np.arange(48)  # 10x5x1 with padding needed
    Nx, Ny, Nz = 10, 5, 1
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (10, 5, 1), f"Unexpected shape: {result.shape}"
    assert result[-1, -1, -1] == 0, "Padding not applied correctly"

    # Test case 3: Empty array
    scan_counts = np.array([])  # No elements
    Nx, Ny, Nz = 10, 5, 1
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (10, 0, 1), f"Unexpected shape: {result.shape}"

    # Test case 4: Single element array
    scan_counts = np.array([42])  # One element
    Nx, Ny, Nz = 2, 2, 2
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (2, 1, 2), f"Unexpected shape: {result.shape}"
    assert result[0, 0, 0] == 42, "Element not placed correctly"

    # Test case 5: Uneven elements
    scan_counts = np.arange(23)  # Incomplete last slice
    Nx, Ny, Nz = 3, 3, 3
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (3, 3, 3), f"Unexpected shape: {result.shape}"
    assert result[-1, -1, -1] == 0, "Padding not applied correctly"

    # Test case 6: Large array with multiple slices
    scan_counts = np.arange(120)  # 10x6x2
    Nx, Ny, Nz = 10, 6, 2
    result = reshape_and_pad_scan_counts(scan_counts, Nx, Ny, Nz)
    assert result.shape == (10, 6, 2), f"Unexpected shape: {result.shape}"

    print("All tests passed!")


import csv
import os
import matplotlib.pyplot as plt
from typing import List, Tuple

def generate_survey_csv(first_position: Tuple[float, float], dx: float, dy: float, nx: int, ny: int) -> List[Tuple[float, float]]:
    """
    Generate a CSV file containing survey points for an S-shaped scan and plot the trajectory.

    The function computes survey points starting at 'first_position' with displacements 'dx' and 'dy'
    over 'nx' columns and 'ny' rows. Points are sorted in a serpentine (S-shape) order for efficient scanning.
    It then prompts the user for a file path using open_file_dialog, writes the points to the file,
    and plots the resulting trajectory.

    :param first_position: A tuple (x, y) representing the starting coordinates.
    :param dx: Displacement in the x direction between adjacent points.
    :param dy: Displacement in the y direction between adjacent rows.
    :param nx: Number of points in the x direction (columns).
    :param ny: Number of rows in the y direction.
    :return: A list of (x, y) tuples representing the survey points.
    """
    try:
        # Generate survey points in serpentine (S-shape) order.
        points: List[Tuple[float, float]] = []
        start_x, start_y = first_position
        for row in range(ny):
            row_points = []
            for col in range(nx):
                x = start_x + col * dx
                y = start_y + row * dy
                row_points.append((x, y))
            # Reverse every other row for S-shape scanning
            if row % 2 == 1:
                row_points.reverse()
            points.extend(row_points)

        # Prompt user for a file path to save the CSV file using the existing open_file_dialog function.
        folder_path = open_file_dialog(filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")], select_folder=True)
        if not folder_path:
            print("No folder selected. Aborting CSV generation.")
            return points
        # Ensure the file name ends with .csv
        file_path = os.path.join(folder_path, "survey_g2_point_map.csv")
        if os.path.exists(file_path):
            base = os.path.join(folder_path, "survey_g2_point_map")
            ext = ".csv"
            counter = 1
            while os.path.exists(f"{base}_{counter:03d}{ext}"):
                counter += 1
            file_path = f"{base}_{counter:03d}{ext}"

        # Write the survey points to the CSV file.
        with open(file_path, mode='w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            for pt in points:
                writer.writerow(pt)
        print(f"CSV file successfully saved to: {file_path}")

        # Plot the survey trajectory.
        xs = [pt[0] for pt in points]
        ys = [pt[1] for pt in points]
        plt.figure()
        plt.plot(xs, ys, marker='o', linestyle='-')
        plt.title("Survey Trajectory (S-Shape Scan)")
        plt.xlabel("X Position")
        plt.ylabel("Y Position")
        plt.grid(False)
        plt.show()

        return points

    except Exception as e:
        print(f"An error occurred during CSV generation: {e}")
        return []


# Run tests
if __name__ == "__main__":
    survey_points = generate_survey_csv((2000, 2000), 2, 2, 20, 20)


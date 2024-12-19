import math
import pdb
import tkinter as tk
import csv
from tkinter import filedialog
import numpy as np
import pandas as pd
from typing import Tuple, Union, List, Optional
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

def open_file_dialog(initial_folder: str ="", title:str = "", filetypes=None) -> str:
    """
    Open a file dialog to select an XML file.

    :param initial_folder: The initial folder path to open in the file dialog.
    :param title: The title of the dialog.
    :param filetypes: A tuple of file types to open in the dialog.
    :return: The selected file path or None if no file is selected.
    """
    if filetypes is None:
        filetypes = [("All Files", "*.*")]
    root = tk.Tk()  # Create the root window
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename(
        initialdir=initial_folder,  # Set the initial directory
        title=title,
        filetypes=filetypes
    )  # Open a file dialog

    if file_path:  # Check if a file was selected
        print(f"Selected file: {file_path}")  # Log the selected file
    else:
        print("No file selected")  # Log if no file was selected

    root.destroy()  # Close the main window

    return file_path

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

def load_from_csv(file_name):
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
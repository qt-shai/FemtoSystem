import os
import shutil
import time
from itertools import product
from typing import Callable, Any
from typing import List, Tuple

import numpy as np
import plotly.graph_objects as go


def copy_files(
    create_scan_file_name_func: Callable[[bool], str],
    verbose: bool = False
) -> None:
    """
    Copy necessary files to local and remote destinations before scanning.

    Args:
        create_scan_file_name_func (Callable[[bool], str]): Function to create scan file names.
        verbose (bool): If True, print detailed progress information.
    """
    try:
        file_mappings = [
            {
                "source": 'Q:/QT-Quantum_Optic_Lab/expData/Images/Zelux_Last_Image.png',
                "destinations": [
                    create_scan_file_name_func(local=True) + "_ZELUX.png",
                    create_scan_file_name_func(local=False) + "_ZELUX.png"
                ]
            },
            {
                "source": 'C:/WC/HotSystem/map_config.txt',
                "destinations": [
                    create_scan_file_name_func(local=True) + "_map_config.txt",
                    create_scan_file_name_func(local=False) + "_map_config.txt"
                ]
            }
        ]
        for file_map in file_mappings:
            source = file_map["source"]
            for destination in file_map["destinations"]:
                if os.path.exists(source):
                    shutil.copy(source, destination)
                    if verbose:
                        print(f"File copied from {source} to {destination}")
                else:
                    if verbose:
                        print(f"Source file {source} does not exist.")
    except Exception as e:
        print(f"Error occurred during file copying: {e}")

def format_time(timestamp: float) -> str:
    """
    Format a timestamp into a human-readable string.

    Args:
        timestamp (float): The timestamp to format.

    Returns:
        str: The formatted time string.
    """
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

def read_in_position(positioner: Any, channel: int, verbose: bool = False) -> None:
    """
    Wait until the specified axis has reached its target position.

    Args:
        positioner (Any): The positioner object.
        channel (int): Axis index.
        verbose (bool): If True, print detailed progress information.
    """
    # Replace with the actual method to read in-position status
    positioner.readInpos(channel)
    if verbose:
        current_position = positioner.AxesPositions[channel]
        unit = positioner.AxesPosUnits[channel]
        print(f"Axis {channel} reached position {current_position} {unit}")

def move_to_positions(
    positioner: Any,
    positions: List[float],
    verbose: bool = False
) -> None:
    """
    Move the positioner to the specified positions on all axes.

    Args:
        positioner (Any): The positioner object.
        positions (List[float]): Target positions for each axis.
        verbose (bool): If True, print detailed progress information.
    """
    for axis, position in enumerate(positions):
        positioner.MoveABSOLUTE(axis, int(position))
        if verbose:
            print(f"Moving axis {axis} to position {position}")

def generate_scan_vectors(
    positioner: Any,
    scan_enabled: List[bool],
    scan_length: List[float],
    scan_step_size: List[float],
    initial_positions: List[float],
    wait_time_motion_start: float,
    verbose: bool = False
) -> Tuple[List[List[float]], List[int]]:
    """
    Generate scan vectors for each axis based on scan parameters.

    Args:
        positioner (Any): The positioner object.
        scan_enabled (List[bool]): Flags indicating which axes are to be scanned.
        scan_length (List[float]): Total scan length for each axis.
        scan_step_size (List[float]): Step size for each axis.
        initial_positions (List[float]): Initial positions for each axis.
        wait_time_motion_start (float): Time to wait after starting motion.
        verbose (bool): If True, print detailed progress information.

    Returns:
        Tuple[List[List[float]], List[int]]: Scan vectors and number of steps for each axis.
    """
    scan_vectors = []
    num_steps = []
    for channel in range(len(scan_enabled)):
        scan_vector = []
        if scan_enabled[channel]:
            initial_position = initial_positions[channel] - scan_length[channel] * 1e3 / 2  # [pm]
            positioner.MoveABSOLUTE(channel, int(initial_position))
            steps = int(scan_length[channel] / scan_step_size[channel])
            for step in range(steps):
                position = step * scan_step_size[channel] * 1e3 + initial_position
                scan_vector.append(position)
            time.sleep(wait_time_motion_start)
            read_in_position(positioner, channel, verbose)
            if verbose:
                print(f"Channel {channel} moved to initial scan position.")
        else:
            initial_position = initial_positions[channel]
            scan_vector.append(initial_position)
            steps = 1
        scan_vectors.append(scan_vector)
        num_steps.append(steps)
    positioner.GetPosition()
    if verbose:
        for channel in range(len(scan_vectors)):
            position = positioner.AxesPositions[channel]
            unit = positioner.AxesPosUnits[channel]
            print(f"Channel {channel} position: {position} [{unit}]")
    return scan_vectors, num_steps

def generate_scan_indices(scan_vectors: List[List[float]]) -> Tuple[int, ...]:
    """
    Generate indices for scanning over all axes.

    Args:
        scan_vectors (List[List[float]]): The scan vectors for each axis.

    Yields:
        Tuple[int, ...]: A tuple of indices representing the current position in each axis.
    """
    axes_ranges = [range(len(scan_vector)) for scan_vector in scan_vectors]
    total_axes = len(scan_vectors)

    if total_axes == 1:
        for idx in axes_ranges[0]:
            yield (idx,)
    elif total_axes == 2:
        num_y, num_x = len(scan_vectors[1]), len(scan_vectors[0])
        for i in range(num_y):
            x_indices = range(num_x) if i % 2 == 0 else reversed(range(num_x))
            for j in x_indices:
                yield (j, i)
    else:
        # For higher dimensions, use default order
        yield from product(*axes_ranges)

def fetch_measurement(
    counts_handle: Any,
    qmm: Any,
    total_integration_time: float,
    verbose: bool = False
) -> float:
    """
    Fetch the measurement from the measurement system.

    Args:
        counts_handle (Any): Handle to the counts data.
        qmm (Any): Quantum Machine Manager or similar object.
        total_integration_time (float): Total integration time in ms.
        verbose (bool): If True, print detailed progress information.

    Returns:
        float: The measured counts normalized by total integration time.
    """
    if counts_handle.is_processing():
        if verbose:
            print('Waiting for measurement counts...')
        counts_handle.wait_for_values(1)
        time.sleep(0.1)
        counts = counts_handle.fetch_all()
        qmm.clear_all_job_results()
        measurement = counts[0] / total_integration_time  # counts/ms
        if verbose:
            print(f"Fetched measurement: {measurement}")
        return measurement
    else:
        return 0.0

def save_scan_data(
    scan_intensities: np.ndarray,
    filename: str,
    verbose: bool = False
) -> None:
    """
    Save the current scan data to a file.

    Args:
        scan_intensities (np.ndarray): The array of scan intensities.
        filename (str): The file name to save the data.
        verbose (bool): If True, print detailed progress information.
    """
    np.save(filename, scan_intensities)
    if verbose:
        print(f"Data saved to {filename}")

def plot_scan(
    dimensions: List[int],
    scan_data: np.ndarray,
    start_locations: List[float],
    end_locations: List[float],
    verbose: bool = False
) -> None:
    """
    Plot the scan data.

    Args:
        dimensions (List[int]): The dimensions of the scan.
        scan_data (np.ndarray): The N-dimensional array of scan data.
        start_locations (List[float]): The starting positions for each axis.
        end_locations (List[float]): The ending positions for each axis.
        verbose (bool): If True, print detailed progress information.
    """
    # Implement plotting logic appropriate for N-dimensional data
    if verbose:
        print("Plotting scan data...")
    pass  # Replace with actual plotting code

def format_elapsed_time(elapsed_time: float) -> str:
    """
    Format elapsed time into a human-readable string.

    Args:
        elapsed_time (float): The elapsed time in seconds.

    Returns:
        str: The formatted elapsed time string.
    """
    hours, rem = divmod(elapsed_time, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

def save_scan_stack_visualization(volume_data: np.ndarray, output_file: str) -> None:
    """
    Visualize 4D data (3D spatial data with intensity as the 4th dimension) in an interactive 3D scatter plot
    and save it to an HTML file.

    :param volume_data: 4D numpy array (shape: [z, y, x, intensity]) representing the 3D scan with intensities.
    :param output_file: Path to save the interactive HTML file.
    :raises ValueError: If output_file is not a string.
    :raises FileNotFoundError: If the directory in output_file does not exist.
    :raises PermissionError: If the program lacks permission to write to the specified location.
    :return: None
    """
    if not isinstance(output_file, str):
        raise ValueError("The output_file parameter must be a string representing the file path.")

    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        raise FileNotFoundError(f"The directory '{output_dir}' does not exist.")

    try:
        # Extract dimensions
        z_size, y_size, x_size, _ = volume_data.shape
        z_coords, y_coords, x_coords = np.mgrid[0:z_size, 0:y_size, 0:x_size]
        intensities = volume_data[:, :, :, 0].flatten()

        fig = go.Figure(
            data=go.Scatter3d(
                x=x_coords.flatten(),
                y=y_coords.flatten(),
                z=z_coords.flatten(),
                mode='markers',
                marker=dict(
                    size=5,
                    color=intensities,  # Intensity as the color dimension
                    colorscale='Viridis',  # Choose a colorscale
                    colorbar=dict(title='Intensity'),
                    opacity=0.8
                )
            )
        )

        fig.update_layout(
            title="3D Scatter Plot with Intensity",
            scene=dict(
                xaxis_title="X",
                yaxis_title="Y",
                zaxis_title="Z"
            )
        )

        fig.write_html(output_file)
        print(f"Visualization saved to {output_file}")

    except PermissionError:
        raise PermissionError(f"Permission denied. Cannot write to '{output_file}'.")

# # Example Usage
# if __name__ == "__main__":
#     # Generate random 4D data (50x50x10 with random intensity values)
#     volume_data = np.random.rand(10, 50, 50, 1) * 100  # Intensity values scaled to 0-100
#
#     # Output file path
#     output_file = "random_3d_visualization.html"
#
#     # Visualize and save
#     save_microscope_stack_visualization(volume_data, output_file)


def create_scan_vectors(initial_scan_location: List[float], l_scan: List[float], step_sizes: List[float],
                        bounds: Tuple[List[float], List[float]]) -> Tuple[List[float], List[float], List[float]]:
    """
    Create x, y, and z vectors for a scan based on initial location, scan dimensions, step sizes, and bounds.

    :param initial_scan_location: Initial scan location as a list [x, y, z].
    :param l_scan: Scan dimensions (half-lengths) as a list [Lx, Ly, Lz].
    :param step_sizes: Step sizes for each dimension as a list [step_x, step_y, step_z].
    :param bounds: Tuple of two lists [lower_bounds, upper_bounds] defining the clipping bounds for each axis.
    :return: Tuple containing x, y, and z vectors for the scan.
    """
    if not (len(initial_scan_location) == len(l_scan) == len(step_sizes) == len(bounds[0]) == len(bounds[1]) == 3):
        raise ValueError("All input lists must have a length of 3.")

    def calculate_vector(center: float, half_length: float, step_size: float, lower_bound: float, upper_bound: float) -> List[float]:
        """
        Calculate a vector for a single axis.

        :param center: Center coordinate for the axis.
        :param half_length: Half-length of the scan region for the axis.
        :param step_size: Step size for the axis.
        :param lower_bound: Lower bound for the axis.
        :param upper_bound: Upper bound for the axis.
        :return: A list representing the vector for the axis, clipped within bounds.
        """
        if step_size <= 0:
            raise ValueError("Step size must be positive.")

        if half_length <= 0:
            return [max(lower_bound, min(center, upper_bound))]  # Single point if no scan length

        num_points = max(int((2 * half_length) / step_size) + 1, 2)  # At least 2 points if scanning
        vector = [np.clip(v,lower_bound, upper_bound) for v in np.linspace(center - half_length, center + half_length, num_points)]
        return list(np.unique(vector))

    # Generate scan vectors for each dimension
    x_vec = calculate_vector(initial_scan_location[0], l_scan[0], step_sizes[0], bounds[0][0], bounds[1][0])
    y_vec = calculate_vector(initial_scan_location[1], l_scan[1], step_sizes[1], bounds[0][1], bounds[1][1])
    z_vec = calculate_vector(initial_scan_location[2], l_scan[2], step_sizes[2], bounds[0][2], bounds[1][2])

    return x_vec, y_vec, z_vec

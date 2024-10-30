import os
import shutil
import time
import numpy as np
from typing import List, Tuple, Callable, Any
from itertools import product

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

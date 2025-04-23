from typing import Callable, Tuple, Dict, Optional
from enum import Enum
import time
import warnings
import numpy as np
from matplotlib import pyplot as plt
from scipy.optimize import minimize, basinhopping, differential_evolution, OptimizeWarning

class OptimizerMethod(Enum):
    NELDER_MEAD = "Nelder-Mead"
    BFGS = "BFGS"
    POWELL = "Powell"
    BASINHOPPING = "Basinhopping"
    DIFFERENTIAL_EVOLUTION = "DifferentialEvolution"
    ADAM = "Adam"
    CG = "CG"
    CMA_ES = "CMA"
    DIRECTIONAL = "Directional"
    SEQUENTIAL = "Sequential"

def directional_climbing_optimize(
    move_abs_fn: Callable[[int, float], None],
    read_in_pos_fn: Callable[[int], bool],
    fetch_data_fn: Callable[[], None],
    get_signal_fn: Callable[[], float],
    get_positions_fn: Callable[[], Tuple[float, float, float]],
    bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
    step_size: list[float],
    improvement_threshold: float = 1.02,
    max_axis_attempts: int = 3,
    run_stats: bool = False,
    verbose: bool = False,
    to_plot: bool = False,
) -> tuple[float, float, float, float, int]:
    """
    Improved directional climbing optimizer to converge faster and reach a higher maximum:
    1. Start at current position.
    2. Try ±3 steps along X and Y to find best initial direction. If found, follow it.
    3. If no strong improvement via direction, try single-axis climbs (X, Y, then Z).
    4. After achieving a good point, do a local verification around the global best.
    5. If a strong local maximum is found, reduce step_size and try a small refinement.

    Enhancements:
    - Track global best position at all times.
    - If direction approach fails to yield 10% improvement, revert to global best and attempt single-axis climbs.
    - After main climbing steps, refine locally by decreasing step_size and re-checking around global best.
    - Early stopping conditions when no improvement is found.
    - Additional if verbose: prints to track progress and decision points.
    """

    # Track global best
    global_best_pos = None
    global_best_sig = -np.inf

    # Trajectory storage
    x_history = []
    y_history = []
    intensity_history = []

    measure_count = 0

    def record_measure(x: float, y: float, intensity: float):
        nonlocal global_best_pos, global_best_sig
        x_history.append(x)
        y_history.append(y)
        intensity_history.append(intensity)
        if intensity > global_best_sig:
            global_best_sig = intensity
            if len(bounds) == 3:
                z_current = get_positions_fn()[2]
                global_best_pos = (x, y, z_current)
            else:
                global_best_pos = (x, y)
    def move_and_measure(x: float, y: float, z: Optional[float] = None) -> float:
        nonlocal measure_count
        # Clamp to bounds
        x = np.clip(x, bounds[0][0], bounds[0][1])
        y = np.clip(y, bounds[1][0], bounds[1][1])
        if z:
            z = np.clip(z, bounds[2][0], bounds[2][1])
        move_abs_fn(0, x)
        move_abs_fn(1, y)
        if z:
            move_abs_fn(2, z)
        while not (read_in_pos_fn(0) and read_in_pos_fn(1)):
            time.sleep(5e-3)
        if z:
            while not read_in_pos_fn(2):
                time.sleep(5e-3)
        fetch_data_fn()
        sig = get_signal_fn()
        record_measure(x, y, sig)
        measure_count += 1
        return sig

    def test_direction(base_pos: Tuple[float, ...], axis_vec: Tuple[float, float], steps: int = 3) -> Tuple[float, ...]:
        """
        Test movement in a given direction from a base position over a specified number of steps.

        Supports both 2-axis and 3-axis systems. For a 2-axis base_pos (x, y), the function uses move_and_measure(x, y).
        For a 3-axis base_pos (x, y, z), it uses move_and_measure(x, y, z) and maintains z constant.

        :param base_pos: The starting position as a tuple (x, y) or (x, y, z).
        :param axis_vec: A tuple (dx, dy) representing the direction to move in the XY plane.
        :param steps: Number of steps to move along the direction.
        :return: A tuple representing the best position and its signal, i.e., (x, y, sig) for 2-axis, or (x, y, z, sig) for 3-axis.
        """
        num_axes = len(base_pos)
        if num_axes == 3:
            x0, y0, z0 = base_pos
            best_sig = move_and_measure(x0, y0, z0)
            best_pos = (x0, y0, z0)
        elif num_axes == 2:
            x0, y0 = base_pos
            best_sig = move_and_measure(x0, y0)
            best_pos = (x0, y0)
        else:
            raise ValueError("base_pos must be a tuple with 2 or 3 elements.")

        for i in range(1, steps + 1):
            # Compute the test coordinates using the global step_size tuple.
            x_test = x0 + axis_vec[0] * i * step_size[0]
            y_test = y0 + axis_vec[1] * i * step_size[1]
            if num_axes == 3:
                sig = move_and_measure(x_test, y_test, z0)
                test_pos = (x_test, y_test, z0)
            else:
                sig = move_and_measure(x_test, y_test)
                test_pos = (x_test, y_test)
            if sig > best_sig:
                best_sig = sig
                best_pos = test_pos

        # Return the best position along with its signal measurement.
        if num_axes == 3:
            return (*best_pos, best_sig)
        else:
            return (*best_pos, best_sig)

    def try_axes(base_pos: Tuple[float, ...]) -> Tuple[float, ...]:
        if verbose:
            print(f"Trying axes directions along X and Y from base position: {base_pos}")

        directions = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        num_axes = len(base_pos)

        if num_axes == 3:
            x0, y0, z0 = base_pos
            base_sig = move_and_measure(x0, y0, z0)
            best_overall = (x0, y0, z0, base_sig)
            signal_index = 3
        elif num_axes == 2:
            x0, y0 = base_pos
            base_sig = move_and_measure(x0, y0)
            best_overall = (x0, y0, base_sig)
            signal_index = 2
        else:
            raise ValueError("base_pos must be a tuple with 2 or 3 elements.")

        for d in directions:
            if num_axes == 3:
                res = test_direction((x0, y0, z0), d)
            else:
                res = test_direction((x0, y0), d)
            if res[signal_index] > best_overall[signal_index]:
                best_overall = res

        if best_overall[signal_index] > base_sig:
            if verbose:
                print(
                    f"Found better direction along XY: {best_overall[:num_axes]} intensity={best_overall[signal_index]:.4f}")
        else:
            if verbose:
                print("No improvement found along X/Y directions.")
        return best_overall

    def follow_direction(base_pos: Tuple[float, ...], dx: float, dy: float) -> Tuple[float, ...]:
        """
        Follow a specified direction from a base position until no further improvement is observed.

        Supports both 2-axis and 3-axis systems. For a 3-axis base_pos (x, y, z), the function keeps z constant.
        For a 2-axis base_pos (x, y), it only operates in the XY plane.

        :param base_pos: The starting position as a tuple (x, y) or (x, y, z).
        :param dx: Direction multiplier along the x-axis.
        :param dy: Direction multiplier along the y-axis.
        :return: For a 3-axis system, returns (x, y, z, current_sig). For a 2-axis system, returns (x, y, current_sig).
        """
        num_axes = len(base_pos)
        if num_axes == 3:
            x, y, z = base_pos
            current_sig = move_and_measure(x, y, z)
        elif num_axes == 2:
            x, y = base_pos
            current_sig = move_and_measure(x, y)
        else:
            raise ValueError("base_pos must be a tuple with 2 or 3 elements.")

        initial_sig = current_sig
        if verbose:
            print(f"Following direction dx={dx}, dy={dy} from {base_pos}...")
        improved = True
        steps_taken = 0
        max_steps = 5  # Limit how far we go in this direction

        while improved and steps_taken < max_steps:
            new_x = x + dx * step_size[0]
            new_y = y + dy * step_size[1]
            if num_axes == 3:
                new_sig = move_and_measure(new_x, new_y, z)
            else:
                new_sig = move_and_measure(new_x, new_y)
            steps_taken += 1
            if new_sig > current_sig:
                x, y = new_x, new_y
                current_sig = new_sig
                # Check if we got at least the improvement threshold (e.g., 10% improvement from start)
                if current_sig >= initial_sig * improvement_threshold:
                    if verbose:
                        print(f"Direction gave >=10% improvement. Current intensity={current_sig:.4f}")
                    break
            else:
                if verbose:
                    print("No further improvement along this direction.")
                improved = False

        if num_axes == 3:
            return x, y, z, current_sig
        else:
            return x, y, current_sig

    def axis_climb(base_pos: Tuple[float, float, float], axis: int) -> Tuple[float, float, float, float]:
        # Axis: 0=X, 1=Y, 2=Z
        x0, y0, z0 = base_pos
        base_sig = move_and_measure(x0, y0, z0)
        axes = ["X", "Y", "Z"]
        if verbose: print(f"Attempting climb along {axes[axis]} axis from {base_pos}...")

        if axis == 2:
            # Z axis
            z_best = z0
            best_sig = base_sig
            # Positive direction
            for i in range(1, max_axis_attempts+1):
                z_test = z0 + i*step_size[2]
                sig = move_and_measure(x0, y0, z_test)
                if sig > best_sig:
                    best_sig = sig
                    z_best = z_test
                else:
                    break
            # Negative direction
            for i in range(1, max_axis_attempts+1):
                z_test = z0 - i*step_size[2]
                sig = move_and_measure(x0, y0, z_test)
                if sig > best_sig:
                    best_sig = sig
                    z_best = z_test
                else:
                    break
            if best_sig > base_sig:
                if verbose: print(f"Improvement found along Z: pos={(x0,y0,z_best)} intensity={best_sig:.4f}")
            else:
                if verbose: print("No improvement found along Z axis.")
            return x0, y0, z_best, best_sig
        else:
            # X or Y axis
            if axis == 0:
                directions = [(1,0),(-1,0)]
            else:
                directions = [(0,1),(0,-1)]

            best_overall = (x0, y0, z0, base_sig)
            for d in directions:
                cur_x, cur_y, cur_z = x0, y0, z0
                cur_sig = base_sig
                for _ in range(max_axis_attempts):
                    new_x = cur_x + d[0]*step_size[0]
                    new_y = cur_y + d[1]*step_size[1]
                    new_sig = move_and_measure(new_x, new_y, cur_z)
                    if new_sig > cur_sig:
                        cur_x, cur_y, cur_z = new_x, new_y, cur_z
                        cur_sig = new_sig
                    else:
                        break
                if cur_sig > best_overall[3]:
                    best_overall = (cur_x, cur_y, cur_z, cur_sig)

            if best_overall[3] > base_sig:
                if verbose: print(f"Improvement found along {axes[axis]}: pos={best_overall[:3]} intensity={best_overall[3]:.4f}")
            else:
                if verbose: print(f"No improvement found along {axes[axis]} axis.")
            return best_overall

    def local_verify(base_pos: Tuple[float, float, float], local_step_factor: int = 3) -> Tuple[float, float, float, float]:
        if verbose: print(f"Performing local verification around the best position: {base_pos}")
        x0, y0, z0 = base_pos
        best_sig = move_and_measure(x0, y0, z0)
        best_pos = (x0, y0, z0)
        # Check small neighborhood
        for dx in [-local_step_factor,0,local_step_factor]:
            for dy in [-local_step_factor,0,local_step_factor]:
                for dz in [-local_step_factor,0,local_step_factor]:
                    # Skip cases where more than one of dx, dy, dz are nonzero
                    if (dx != 0) + (dy != 0) + (dz != 0) > 1:
                        continue
                    x_test = x0 + dx*step_size[0]
                    y_test = y0 + dy*step_size[1]
                    z_test = z0 + dz*step_size[2]
                    sig = move_and_measure(x_test, y_test, z_test)
                    if sig > best_sig:
                        best_sig = sig
                        best_pos = (x_test, y_test, z_test)
        if verbose: print(f"Local verification done. Best: {best_pos} intensity={best_sig:.4f}")
        return (*best_pos, best_sig)

    # Start
    start_pos = get_positions_fn()
    base_sig = move_and_measure(*start_pos)
    if verbose: print(f"Starting optimization at {start_pos} with intensity {base_sig:.4f}")

    # Step 1: Find best direction in XY
    x_best, y_best, z_best, sig_best = try_axes(start_pos)

    # Decide next steps
    if sig_best < global_best_sig * improvement_threshold:
        # If no good direction improvement, revert to global best and single-axis climb
        if verbose: print("XY directions not sufficient, switching to single-axis approach from global best.")
        if global_best_pos is not None:
            move_abs_fn(0, global_best_pos[0])
            move_abs_fn(1, global_best_pos[1])
            move_abs_fn(2, global_best_pos[2])
        # Try single axes
        x_best, y_best, z_best, sig_best = axis_climb(global_best_pos, 0)
        x_best, y_best, z_best, sig_best = axis_climb((x_best, y_best, z_best), 1)
        x_best, y_best, z_best, sig_best = axis_climb((x_best, y_best, z_best), 2)
    else:
        # Got a decent XY direction
        dx = (x_best - start_pos[0])/(3*step_size[0]) if x_best != start_pos[0] else 0
        dy = (y_best - start_pos[1])/(3*step_size[1]) if y_best != start_pos[1] else 0
        x_best, y_best, z_best, sig_best = follow_direction((x_best,y_best,z_best), dx, dy)
        if sig_best < global_best_sig * improvement_threshold:
            if verbose: print("Direction approach insufficient. Reverting to global best and trying axes separately.")
            if global_best_pos is not None:
                move_abs_fn(0, global_best_pos[0])
                move_abs_fn(1, global_best_pos[1])
                move_abs_fn(2, global_best_pos[2])
            x_best, y_best, z_best, sig_best = axis_climb(global_best_pos, 0)
            x_best, y_best, z_best, sig_best = axis_climb((x_best, y_best, z_best), 1)
            x_best, y_best, z_best, sig_best = axis_climb((x_best, y_best, z_best), 2)

    # Move to global best before local verification
    if global_best_pos is not None:
        move_abs_fn(0, global_best_pos[0])
        move_abs_fn(1, global_best_pos[1])
        move_abs_fn(2, global_best_pos[2])
        x_best, y_best, z_best = global_best_pos
        sig_best = global_best_sig

    # Perform local verification
    # x_best, y_best, z_best, sig_best = local_verify((x_best,y_best,z_best))

    # Try a refinement step by reducing step_size if needed
    # If we see room for improvement, do a finer local scan with smaller steps
    for axis in range(len(step_size)):
        refined_step = step_size[axis]/2
        if refined_step >= 100 and (sig_best < global_best_sig * improvement_threshold):
            if verbose: print("Attempting refinement with smaller step size...")
            old_step_size = step_size[axis]
            step_size[axis] = refined_step
            x_best, y_best, z_best, sig_best = local_verify((x_best,y_best,z_best), local_step_factor=2)
            # Restore step_size
            step_size[axis] = old_step_size

    if verbose: print(f"Optimization complete. Best position: ({x_best:.2f}, {y_best:.2f}, {z_best:.2f}) with intensity {sig_best:.4f}")
    if verbose: print(f"Total measurements: {measure_count}")

    if to_plot:
        # Plot trajectory
        fig = plt.figure()
        ax = fig.add_subplot(111, projection='3d')
        ax.plot(x_history, y_history, intensity_history, '-o', ms=2)
        ax.plot(x_history[0], y_history[0], intensity_history[0], '*', ms=5)
        ax.set_xlabel('X')
        ax.set_ylabel('Y')
        ax.set_zlabel('Intensity')
        plt.title('Trajectory of the Optimizer')
        plt.show()

    if run_stats:
        if verbose: print(f"Run stats: Steps taken {measure_count}, final intensity {sig_best:.4f}")

    return x_best, y_best, z_best, sig_best, measure_count


def sequential_scan(
        move_abs_fn: Callable[[int, float], None],
        read_in_pos_fn: Callable[[int], bool],
        fetch_data_fn: Callable[[], None],
        get_signal_fn: Callable[[], float],
        bounds: Tuple[Tuple[float, float], ...],
        step_size: float = 10000.0
) -> Tuple[float, ...]:
    """
    Perform a sequential scan on 2 or 3 axes.

    For a 3-axis system, the scanning order is Z, then Y, then X (i.e., axis indices 2, 1, 0).
    For a 2-axis system, the scanning order is Y then X (i.e., axis indices 1, 0).
    Each axis scan is performed around the best position found so far.

    :param move_abs_fn: Function to move a given axis to an absolute position.
                        Accepts an axis index and a position value.
    :param read_in_pos_fn: Function to check if an axis is in position.
                           Accepts an axis index.
    :param fetch_data_fn: Function to fetch the latest measurement data.
    :param get_signal_fn: Function to get the current signal value.
    :param bounds: Bounds for the axes as ((x_low, x_high), (y_low, y_high)) for 2-axis or
                   ((x_low, x_high), (y_low, y_high), (z_low, z_high)) for 3-axis.
    :param step_size: Step size for the scans.
    :return: The position (as a tuple) with the highest signal.
    """

    num_axes = len(bounds)
    if num_axes not in [2, 3]:
        raise ValueError("Bounds must be provided for either 2 or 3 axes.")

    # Compute the initial position as the midpoint of each bound.
    initial_position = tuple((b[0] + b[1]) / 2 for b in bounds)

    def scan_axis(axis: int, start_pos: Tuple[float, ...]) -> Tuple[float, ...]:
        """
        Scan along a single axis while keeping the other axes fixed.

        :param axis: The axis index to scan.
        :param start_pos: The current position for all axes.
        :return: The best position (as a tuple) after scanning the given axis.
        """
        best_signal = float('-inf')
        best_position = start_pos
        axis_range = np.arange(bounds[axis][0], bounds[axis][1] + step_size, step_size)
        for pos in axis_range:
            # Move the target axis to the new position.
            move_abs_fn(axis, pos)
            # Wait until all axes are in position.
            while not read_in_pos_fn(axis):
                time.sleep(0.001)
            # Fetch data and measure the signal.
            fetch_data_fn()
            signal = get_signal_fn()
            print(f"Scanning axis {axis} at position {pos}: Signal = {signal}")
            if signal > best_signal:
                best_signal = signal
                best_position = tuple(pos if i == axis else start_pos[i] for i in range(num_axes))
        print(f"Best position after scanning axis {axis}: {best_position} with signal = {best_signal}")
        move_abs_fn(axis, best_position[axis])
        return *best_position,best_signal

    # Define the scanning order: for 3 axes, scan Z, Y, then X; for 2 axes, scan Y then X.
    scan_order = [2, 1, 0] if num_axes == 3 else [1, 0]

    best_position = initial_position
    for axis in scan_order:
        best_position = scan_axis(axis, best_position)

    print(f"Best position after sequential scan: {best_position}")
    return best_position


def coarse_scan(
    move_abs_fn: Callable[[int, int], None],
    read_in_pos_fn: Callable[[int], bool],
    fetch_data_fn: Callable[[], None],
    get_signal_fn: Callable[[], float],
    bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
    step_size: float = 10000.0
) -> Tuple[float, float, float]:
    """
    Perform a coarse scan over the bounds to find the position with the highest signal.
    :param move_abs_fn: Function to move a given axis to an absolute position.
    :param read_in_pos_fn: Function to check if an axis is in position.
    :param fetch_data_fn: Function to fetch the latest measurement data.
    :param get_signal_fn: Function to get the current signal value.
    :param bounds: Bounds for (x, y, z) as ((x_low, x_high), (y_low, y_high), (z_low, z_high)).
    :param step_size: Step size for the coarse scan.
    :return: The (x, y, z) position with the highest signal.
    """
    best_signal = float('-inf')
    best_position = (0.0, 0.0, 0.0)

    x_range = np.arange(bounds[0][0], bounds[0][1] + step_size, step_size)
    y_range = np.arange(bounds[1][0], bounds[1][1] + step_size, step_size)
    z_range = np.arange(bounds[2][0], bounds[2][1] + step_size, step_size)

    for x in x_range:
        for y in y_range:
            for z in z_range:
                # Move to the current position
                move_abs_fn(0, x)
                move_abs_fn(1, y)
                move_abs_fn(2, z)

                # Wait for all axes to be in position
                while not (read_in_pos_fn(0) and read_in_pos_fn(1) and read_in_pos_fn(2)):
                    time.sleep(0.001)

                # Fetch new data and read signal
                fetch_data_fn()
                signal = get_signal_fn()

                print(f"Coarse scan position ({x}, {y}, {z}): Signal = {signal}")

                # Update the best position if the current signal is higher
                if signal > best_signal:
                    best_signal = signal
                    best_position = (x, y, z)

    print(f"Best coarse scan position: {best_position} with signal = {best_signal}")
    return best_position

def adam_optimize(neg_intensity: Callable[[np.ndarray], float],
                  initial_guess: Tuple[float,float,float],
                  bounds: Tuple[Tuple[float,float],Tuple[float,float],Tuple[float,float]],
                  max_iter: int = 1000,
                  lr: float = 2000.0) -> Tuple[float,float,float,float,int]:
    """
    Adam-based optimizer to maximize intensity (minimize neg_intensity).
    """
    def grad(f, x):
        eps = 1e-3
        g = np.zeros_like(x)
        for i in range(len(x)):
            x_up = x.copy()
            x_down = x.copy()
            x_up[i] += eps
            x_down[i] -= eps
            g[i] = (f(x_up)-f(x_down)) / (2*eps)
        return g

    x = np.array(initial_guess, dtype=float)
    beta1, beta2 = 0.9, 0.999
    m = np.zeros_like(x)
    v = np.zeros_like(x)
    epsilon = 1e-8
    eval_count = 0

    def clipped_f(pos):
        nonlocal eval_count
        for i, (low, high) in enumerate(bounds):
            if pos[i] < low or pos[i] > high:
                return 1e6
        eval_count += 1
        return neg_intensity(pos)

    for t in range(1, max_iter+1):
        g = grad(clipped_f, x)
        m = beta1*m + (1-beta1)*g
        v = beta2*v + (1-beta2)*(g*g)
        m_hat = m/(1-beta1**t)
        v_hat = v/(1-beta2**t)
        x = x - lr*m_hat/(np.sqrt(v_hat)+epsilon)
        # Clamp positions
        for i, (low, high) in enumerate(bounds):
            x[i] = np.clip(x[i], low, high)

    intensity = -clipped_f(x)
    return x[0], x[1], x[2], intensity, eval_count


def find_max_signal(
    move_abs_fn: Callable[[int, float], None] | Callable[[int, int], None],
    read_in_pos_fn: Callable[[int], bool],
    get_positions_fn: Callable[[], Tuple[float,float,float]]|Callable[[], Tuple[float,float]],
    fetch_data_fn: Callable[[], None],
    get_signal_fn: Callable[[], float],
    bounds: Tuple[Tuple[float,float],Tuple[float,float],Tuple[float,float]],
    method: OptimizerMethod,
    initial_guess: Optional[Tuple[float,float,float]]|Optional[Tuple[float,float]] = None,
    max_iter: int = 1000,
    use_coarse_scan: bool = False,
) -> Tuple[float,float,Optional[float],float]:
    """
    A generalized peak finding function.
    :param move_abs_fn: A function to move a given axis to an absolute position: move_abs_fn(axis:int, position:float).
    :param read_in_pos_fn: A function to check if an axis is in position: read_in_pos_fn(axis:int)->bool.
    :param get_positions_fn: A function to get current (x,y,z) positions.
    :param fetch_data_fn: A function to fetch the latest measurement data.
    :param get_signal_fn: A function to get the current measured signal (light intensity).
    :param bounds: Bounds for (x,y,z) as ((x_low,x_high),(y_low,y_high),(z_low,z_high)).
    :param method: Which optimizer method to use.
    :param initial_guess: Optional initial guess for (x,y,z). If None, use current positions.
    :param max_iter: Maximum iterations for optimizers.
    :return: (x_opt, y_opt, z_opt, max_intensity)
    """

    # Perform coarse scan if no initial guess is provided
    if initial_guess is None:
        if not use_coarse_scan:
            initial_guess = get_positions_fn()
        else:
            print("Performing coarse scan...")
            # initial_guess = coarse_scan(move_abs_fn, read_in_pos_fn, fetch_data_fn, get_signal_fn, bounds)
            initial_guess = sequential_scan(move_abs_fn, read_in_pos_fn, fetch_data_fn, get_signal_fn, bounds, step_size=3000)
            print('Moving to position {x}, {y}, {z}')
            for ch in range(3):
                move_abs_fn(ch, initial_guess[ch])
                time.sleep(0.01)
            return initial_guess[0], initial_guess[1], initial_guess[2], 1000

    if method == OptimizerMethod.SEQUENTIAL:
        step_size_val: float = 1  # or any desired value
        best_position = sequential_scan(move_abs_fn, read_in_pos_fn, fetch_data_fn, get_signal_fn, bounds,
                                        step_size=step_size_val)
        print(f"Best position found: {best_position}")
        # Return based on the number of axes
        if len(bounds) == 3:
            x_best, y_best, z_best, max_signal = best_position
            for ch in range(3):
                move_abs_fn(ch, best_position[ch])
                time.sleep(0.01)
            return x_best, y_best, z_best, max_signal
        else:
            x_best, y_best, max_signal = best_position
            for ch in range(2):
                move_abs_fn(ch, best_position[ch])
                time.sleep(0.01)
            return x_best, y_best, None, max_signal

    if method == OptimizerMethod.DIRECTIONAL:
        step_size: list[float] = [np.abs(bounds[axis][1] - bounds[axis][0])/10 for axis in range(len(bounds))]
        improvement_threshold: float = 1.10
        max_axis_attempts:int = 3
        run_stats:bool = False
        verbose:bool  = True
        to_plot:bool  = False
        x_best, y_best, z_best, sig_best, measure_count = directional_climbing_optimize(move_abs_fn,
                                                                                        read_in_pos_fn,
                                                                                        fetch_data_fn,
                                                                                        get_signal_fn,
                                                                                        get_positions_fn,
                                                                                        bounds,
                                                                                        step_size,
                                                                                        improvement_threshold,
                                                                                        max_axis_attempts,
                                                                                        run_stats,
                                                                                        verbose,
                                                                                        to_plot)
        return x_best, y_best, z_best, sig_best

    print(f"Using initial guess: {initial_guess}")

    def measure_intensity(x: float, y: float, z: float) -> float:
        # Move to given coordinates (clamped to bounds)
        x = np.clip(x, bounds[0][0], bounds[0][1])
        y = np.clip(y, bounds[1][0], bounds[1][1])
        z = np.clip(z, bounds[2][0], bounds[2][1])

        print(f"Moving to position {x}, {y}, {z}")
        move_abs_fn(0, x)
        move_abs_fn(1, y)
        move_abs_fn(2, z)

        # Wait until all axes are in position
        while not (read_in_pos_fn(0) and read_in_pos_fn(1) and read_in_pos_fn(2)):
            time.sleep(0.001)

        # Fetch new data
        last_signal = get_signal_fn()
        last_iter_signal = last_signal
        old_signal = last_signal

        # Attempt to fetch new data until it changes (if fetch_data_fn updates signal)
        # If not guaranteed to change every time, remove this wait.
        fetch_data_fn()
        new_signal = get_signal_fn()
        count = 0
        while new_signal == old_signal and count < 100:
            time.sleep(0.01)
            fetch_data_fn()
            new_signal = get_signal_fn()
            count += 1

        print(f"New signal: {new_signal}")
        return new_signal

    eval_count = 0
    def neg_intensity(pos: np.ndarray) -> float:
        nonlocal eval_count
        # Check bounds
        for i, (low, high) in enumerate(bounds):
            if pos[i] < low or pos[i] > high:
                return 1e6
        eval_count += 1
        return -measure_intensity(pos[0], pos[1], pos[2])

    x_guess = np.array(initial_guess, dtype=float)

    # Choose and run the optimizer
    if method == OptimizerMethod.ADAM:
        x_opt, y_opt, z_opt, intensity, steps = adam_optimize(neg_intensity, x_guess, bounds, max_iter=max_iter)
    elif method == OptimizerMethod.CMA_ES:
        # CMA-ES via SciPy's 'CMA' method (available in scipy >= 1.9)
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', OptimizeWarning)
            res = minimize(neg_intensity, x_guess, method='CMA', options={'maxiter':max_iter})
            if any(issubclass(x.category, OptimizeWarning) for x in w):
                print(f"Warning: CMA-ES did not fully converge. Using the best found solution.")
        x_opt, y_opt, z_opt = res.x
        intensity = -res.fun
        steps = eval_count
    elif method == OptimizerMethod.BASINHOPPING:
        res = basinhopping(neg_intensity, x_guess, niter=max_iter)
        x_opt, y_opt, z_opt = res.x
        intensity = -res.fun
        steps = eval_count
    elif method == OptimizerMethod.DIFFERENTIAL_EVOLUTION:
        res = differential_evolution(neg_intensity, bounds, maxiter=max_iter)
        x_opt, y_opt, z_opt = res.x
        intensity = -res.fun
        steps = eval_count
    else:
        # Methods handled by minimize: NELDER_MEAD, BFGS, POWELL, CG
        scipy_method = method.value  # direct mapping from enum to method string
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter('always', OptimizeWarning)
            res = minimize(neg_intensity, x_guess, method=scipy_method, bounds=bounds, options={'maxiter':max_iter})
            if any(issubclass(x.category, OptimizeWarning) for x in w):
                print(f"Warning: {scipy_method} did not fully converge. Using the best found solution.")
        x_opt, y_opt, z_opt = res.x
        intensity = -res.fun
        steps = eval_count

    # Move to the found maximum position
    print('Moving to position {x}, {y}, {z}')
    move_abs_fn(0, x_opt)
    move_abs_fn(1, y_opt)
    move_abs_fn(2, z_opt)
    while not (read_in_pos_fn(0) and read_in_pos_fn(1) and read_in_pos_fn(2)):
        time.sleep(0.001)

    print(f"Found peak at ({x_opt:.3f}, {y_opt:.3f}, {z_opt:.3f}) with intensity = {intensity:.3f} after {steps} steps.")
    return x_opt, y_opt, z_opt, intensity

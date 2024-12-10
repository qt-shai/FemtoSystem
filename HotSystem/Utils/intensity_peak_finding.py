from typing import Callable, Tuple, Dict, Optional
from enum import Enum
import time
import warnings
import numpy as np
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

def sequential_scan(
    move_abs_fn: Callable[[int, int], None],
    read_in_pos_fn: Callable[[int], bool],
    fetch_data_fn: Callable[[], None],
    get_signal_fn: Callable[[], float],
    bounds: Tuple[Tuple[float, float], Tuple[float, float], Tuple[float, float]],
    step_size: float = 10000.0
) -> Tuple[float, float, float]:
    """
    Perform a sequential scan: first Z, then Y, and finally X.
    Each axis scan is performed around the best position found so far.
    :param move_abs_fn: Function to move a given axis to an absolute position.
    :param read_in_pos_fn: Function to check if an axis is in position.
    :param fetch_data_fn: Function to fetch the latest measurement data.
    :param get_signal_fn: Function to get the current signal value.
    :param bounds: Bounds for (x, y, z) as ((x_low, x_high), (y_low, y_high), (z_low, z_high)).
    :param step_size: Step size for the scans.
    :return: The (x, y, z) position with the highest signal.
    """
    def scan_axis(axis: int, start_pos: Tuple[float, float, float]) -> Tuple[float, float, float]:
        """
        Perform a scan along a single axis while keeping other axes fixed.
        :param axis: Axis index (0 for X, 1 for Y, 2 for Z).
        :param start_pos: Current (x, y, z) position.
        :return: Best (x, y, z) position after the scan.
        """
        best_signal = float('-inf')
        best_position = start_pos
        axis_range = np.arange(bounds[axis][0], bounds[axis][1] + step_size, step_size)

        for pos in axis_range:
            # Move only the specified axis
            move_abs_fn(axis, pos)


            # Keep other axes fixed at their current positions
            for other_axis in range(3):
                if other_axis != axis:
                    move_abs_fn(other_axis, start_pos[other_axis])

            # Wait until all axes are in position
            while not all(read_in_pos_fn(i) for i in range(3)):
                time.sleep(0.001)

            # Fetch new data and read the signal
            fetch_data_fn()
            signal = -get_signal_fn()

            print(f"Scanning axis {axis} at position {pos}: Signal = {signal}")

            # Update the best position if the current signal is higher
            if signal > best_signal:
                best_signal = signal
                best_position = (
                    pos if axis == 0 else start_pos[0],
                    pos if axis == 1 else start_pos[1],
                    pos if axis == 2 else start_pos[2],
                )

        print(f"Best position after scanning axis {axis}: {best_position} with signal = {best_signal}")
        return best_position

    # Initial starting position (default to the middle of the bounds)
    initial_position = (0,0,0)

    # Sequentially scan Z, Y, then X
    best_position = scan_axis(0, initial_position)  # Scan Z
    best_position = scan_axis(1, best_position)    # Scan Y
    best_position = scan_axis(2, best_position)    # Scan X

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
    move_abs_fn: Callable[[int, int], None],
    read_in_pos_fn: Callable[[int], bool],
    get_positions_fn: Callable[[], Tuple[float,float,float]],
    fetch_data_fn: Callable[[], None],
    get_signal_fn: Callable[[], float],
    bounds: Tuple[Tuple[float,float],Tuple[float,float],Tuple[float,float]],
    method: OptimizerMethod,
    initial_guess: Optional[Tuple[float,float,float]] = None,
    max_iter: int = 1000,
    use_coarse_scan: bool = False,
) -> Tuple[float,float,float,float]:
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

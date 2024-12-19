import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit
from tkinter import Tk
from tkinter.filedialog import askopenfilename


def select_csv_file() -> str:
    """
    Open a file dialog to select a CSV file.

    :return: Path to the selected CSV file.
    """
    Tk().withdraw()
    file_path = askopenfilename(filetypes=[("CSV files", "*.csv")])
    return file_path


# Define Hahn echo fitting function
def hahn_echo_fit(t: np.ndarray, A: float, tau: float, alpha: float, offset: float) -> np.ndarray:
    """
    Hahn echo signal fit function (stretched Gaussian).

    :param t: Time array in seconds.
    :param A: Amplitude of the signal.
    :param tau: Decay time constant in seconds.
    :param alpha: Stretching exponent (1 <= alpha <= 2).
    :param offset: Offset of the signal.
    :return: The Hahn echo signal model.
    """
    return A * np.exp(-(t / tau) ** alpha) + offset

# Hahn echo analysis
def analyze_hahn_echo(file_path: str):
    """
    Analyze Hahn echo signal from a CSV file.

    :param file_path: Path to the CSV file.
    """
    data = pd.read_csv(file_path)
    time = data['X'].values * 1e-3  # Convert ms to seconds
    signal = data['Y'].values

    # Hahn echo signal fitting
    initial_guess = [np.max(signal), 1e-3, 1.5, np.mean(signal)]  # Initial parameter guess
    params, _ = curve_fit(hahn_echo_fit, time, signal, p0=initial_guess)

    # Plot Hahn echo signal
    plt.figure(figsize=(10, 6))
    plt.scatter(time * 1e3, signal, color='black', label='Data', s=10)
    plt.plot(time * 1e3, hahn_echo_fit(time, *params), color='red', label='Fit', linewidth=2)
    plt.xlabel("Time (ms)", fontsize=14)
    plt.ylabel("Signal", fontsize=14)
    plt.title("Hahn Echo Measurement", fontsize=16)
    plt.legend(fontsize=12)
    plt.grid(True)
    plt.show()

    # Extract decay time and alpha, print
    decay_time = params[1] * 1e6  # Convert to microseconds
    alpha = params[2]
    print(f"Hahn echo decay time: {decay_time:.2f} μs")
    print(f"Stretching exponent (alpha): {alpha:.2f}")


def find_tail(signal: np.ndarray, threshold: float = 0.001) -> float:
    """
    Estimate the tail (constant offset) by averaging the signal in the flat region.

    :param signal: Signal array.
    :param threshold: Threshold for detecting flat regions (based on signal derivative).
    :return: Tail value (average of the flat region).
    """
    # derivative = np.abs(np.diff(signal))
    # flat_indices = np.where(derivative < threshold)[0]
    # tail_indices = flat_indices[int(len(flat_indices) * 0.8):]  # Use the last 20% of flat indices
    # return np.mean(signal[tail_indices])
    return np.mean(signal[-10:])

def find_amplitude(signal: np.ndarray, time: np.ndarray, window: float = 0.0002) -> float:
    """
    Estimate the amplitude of the peak by averaging over a small window around the maximum.

    :param signal: Signal array.
    :param time: Time array (corresponding to the signal).
    :param window: Time window around the peak for averaging (ms).
    :return: Estimated amplitude.
    """
    peak_index = np.argmax(signal)
    peak_time = time[peak_index]
    nearby_indices = np.where(np.abs(time - peak_time) < window)[0]
    return np.mean(signal[nearby_indices]) - np.min(signal)


def simplified_ramsey_fit(time: np.ndarray, signal: np.ndarray):
    """
    Fit the Ramsey signal with a simplified model focusing on decay rate and a single frequency.

    :param time: Array of time values (ms).
    :param signal: Array of signal values.
    :return: Fit parameters and their covariance.
    """
    # Fixed parameters
    tail_avg = find_tail(signal)
    amplitude = find_amplitude(signal, time)

    # Define simplified model
    def simplified_ramsey_model(t, f, tau):
        return amplitude * np.exp(-t / tau) *np.cos(2 * np.pi * f * t) + tail_avg

    # Initial guesses for free parameters
    p0 = [1e6, 1e-3]  # Frequency (MHz) and decay time (ms)
    params, cov = curve_fit(simplified_ramsey_model, time, signal, p0=p0, bounds=([0,1e-8],[20e6,1]))
    return params, cov, simplified_ramsey_model, tail_avg, amplitude


def plot_simplified_ramsey_fit(time: np.ndarray, signal: np.ndarray, params: np.ndarray, model, tail_avg: float,
                               amplitude: float):
    """
    Plot the Ramsey data with the simplified fit model and display fit parameters on the graph.

    :param time: Array of time values.
    :param signal: Array of signal values.
    :param params: Fit parameters.
    :param model: Simplified Ramsey model function.
    :param tail_avg: Fixed offset value used in the fit.
    :param amplitude: Fixed amplitude value used in the fit.
    """
    plt.figure(figsize=(10, 6))
    plt.scatter(time*1e6, signal, color='black', label='Data', s=10)
    plt.plot(time*1e6, model(time, *params), color='red', label='Fit', linewidth=2)

    # Write fit parameters on the plot
    fit_text = (
        f"Frequency: {params[0]/1e6:.3f} MHz\n"
        f"Decay Time: {params[1]*1e6:.3f} ns\n"  # Convert decay time to microseconds
        f"Fixed Offset: {tail_avg:.3f}\n"
        f"Fixed Amplitude: {amplitude:.3f}"
    )
    print(fit_text)
    plt.text(0.6 * max(time*1e6), 0.8 * max(signal), fit_text, fontsize=10, color='blue')

    plt.xlabel('Time (ns)', fontsize=14)
    plt.ylabel('Signal', fontsize=14)
    plt.title("Simplified Ramsey Measurement", fontsize=16)
    plt.legend(fontsize=12)
    plt.grid(True)
    # plt.tight_layout(pad=2.0)  # Adjust padding to avoid layout issues
    plt.show()


def wrapper():
    file_path = select_csv_file()
    if not file_path:
        print("No file selected.")
        return

    # Read data
    data = pd.read_csv(file_path)
    time = data['X'].values[2:]
    signal = data['Y'].values[2:]
    # signal_ref = data['Y_ref'].values
    # ignore_ref = input("Ignore reference column? (yes/no): ").strip().lower() == 'yes'
    signal_to_analyze = signal # if ignore_ref else signal - signal_ref

    # Fit and plot
    params, cov, model, tail_avg, amplitude = simplified_ramsey_fit(time, signal_to_analyze)
    plot_simplified_ramsey_fit(time, signal_to_analyze, params, model, tail_avg, amplitude)

if __name__ == "__main__":
    wrapper()
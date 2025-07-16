import numpy as np
import matplotlib.pyplot as plt
import scipy as sc
import pandas as pd
from Utils.Common import loadFromCSV

class ODMR_analysis():
    def __init__(self, intensity, frequency):
        self.intensity = intensity
        self.frequency = frequency
        if self.intensity.shape != self.frequency.shape:
            raise ValueError("intensity and frequency arrays must have identical shape")

    def Lorentzian(self, x, y0, amp, cen, wid):
        return (y0 + amp * wid ** 2 / ((x - cen) ** 2 + wid ** 2))

    def _guess_params(self, x, y):
        y0 = np.max(y)
        amp = y.min() - y0
        cen = x[np.argmin(y)]
        half = y0 + amp / 2

        # locate half‑maximum crossings
        crossings = np.where(np.diff(np.sign(y - half)))[0]
        if len(crossings) >= 2:
            wid = abs(x[crossings[-1]] - x[crossings[0]]) / 2
        else:
            wid = (x.max() - x.min()) / 10  # safe fallback
        return y0, amp, cen, wid

    def fit_odmr_lorentzian(self, freq, intensity):
        # intensity = sc.signal.savgol_filter(intensity, sg_window, sg_poly, pre_smooth)
        _, baseline = self._remove_baseline(intensity)
        self._smooth(intensity)
        p0 = self._guess_params(freq, intensity)
        fit, fit_cov = sc.optimize.curve_fit(self.Lorentzian, freq, intensity, p0=p0, maxfev=5000)
        y0, amp, center, width = fit
        y_fit = self.Lorentzian(freq, *fit)
        ss_res = np.sum((intensity - y_fit) ** 2)
        ss_tot = np.sum((intensity - intensity.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot else np.nan
        print(f"Center frequency = {center:.6f} GHz, width = {width:.6f} GHz, , R²={r2:.4f}")
        return fit, fit_cov, baseline

    def _remove_baseline(self, y: np.ndarray, detrend = True, baseline_order = 1):
        """Polynomial detrend; returns y if detrend=False."""
        if not detrend:
            return y
        coeff = np.polyfit(self.frequency, y, baseline_order)
        baseline = np.polyval(coeff, self.frequency)
        return y - baseline, baseline

    def _smooth(self, y: np.ndarray, pre_smooth = True, sg_window = 1, sg_poly = 3) -> np.ndarray:
        """Savitzky–Golay smoothing; returns y if pre_smooth=False."""
        if not pre_smooth:
            return y

        # adapt window if too long for dataset
        wl = min(sg_window, len(y) if len(y) % 2 == 1 else len(y) - 1)
        if wl < sg_poly + 2:
            wl = sg_poly + 2 + (sg_poly + 2) % 2

        return sc.signal.savgol_filter(y, window_length=wl, polyorder=sg_poly)


class Rabi_analysis():
    def __init__(self):
        self.intensity = None
        self.frequency = None

    def _guess_params(self, x, y):
        x = np.asarray(x, dtype=float)
        y = np.asarray(y, dtype=float)

        # ----- baseline and amplitude ---------------------------------
        y_max, y_min = y.max(), y.min()
        y0 = 0.5 * (y_max + y_min)  # mid-line
        amp = 0.5 * (y_max - y_min)  # peak-to-trough / 2

        # ----- dominant oscillation frequency via FFT -----------------
        # Works best when x is (roughly) evenly spaced
        dx = np.median(np.diff(x))
        y_detr = y - y0
        spec = np.fft.rfft(y_detr)
        freqs = np.fft.rfftfreq(len(x), d=dx)

        # ignore DC component at index 0
        idx_peak = np.argmax(np.abs(spec[1:])) + 1
        freq = freqs[idx_peak]  # cycles per x-unit

        # ----- phase estimate from first point ------------------------
        # sin(2π f x0 + φ) = (y0_sub) / amp  ⇒  φ ≈ arcsin(...)
        # Clamp argument to [-1, 1] to avoid NaN in noisy data
        arg = np.clip(y_detr[0] / amp, -1.0, 1.0)
        phase = np.arcsin(arg) - 2 * np.pi * freq * x[0]

        return y0, amp, freq, phase

    def load_actual_data(self, path = 'Q:\\QT-Quantum_Optic_Lab\\expData\\RABI\\2024_5_19_11_37_30RABI.csv'):
        data = loadFromCSV(file_name=path)
        data = np.asarray(data, dtype = float)
        x = data[:, 0]
        y = data[:, 1]
        return x, y

    def plot_actual_data(self):
        plt.figure()
        x, y = self.load_actual_data()
        self.frequency, self.intensity = x, y
        plt.plot(x,y)
        plt.xlabel("Frequency (GHz)")
        plt.ylabel("Intensity (arb. u.)")
        plt.legend()
        plt.tight_layout()
        plt.show()

    def sin_function(self, x, y0, amp, freq, phase):
        return y0 + amp * np.sin(2 * np.pi * freq * x + phase)

    def plot_with_fit(self, refine=True, n_dense=4001, label_data="data",
                      label_fit="fit", **plot_kwargs):

        # 1) Use instance arrays if already present, otherwise load CSV
        if self.intensity is not None and self.frequency is not None:
            x, y = self.frequency, self.intensity
        else:
            x, y = self.load_actual_data()

        # 2) Initial parameter guesses
        p0 = self._guess_params(x, y)  # y0, amp, freq, phase

        # 3) Optional nonlinear least-squares refinement
        if refine:
            try:
                popt, pcov = sc.optimize.curve_fit(self.sin_function, x, y, p0=p0, maxfev=6000)
            except RuntimeError:  # convergence failed
                popt = p0
        else:
            popt = p0

        y_fit = self.sin_function(x, *popt)
        ss_res = np.sum((y - y_fit) ** 2)
        ss_tot = np.sum((y - y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot else np.nan

        # 4) Prepare smooth curve
        dense_x = np.linspace(x.min(), x.max(), n_dense)
        model = self.sin_function(dense_x, *popt)

        # 5) Plot
        plt.figure()
        plt.plot(x, y, ms=4, label=label_data)
        plt.plot(dense_x, model, '-', **plot_kwargs, label=label_fit)

        # Axes labels (adjust if x is not in GHz!)
        plt.xlabel("Pulse length (arb. u.)")
        plt.ylabel("Intensity (arb. u.)")

        # Fit parameter annotation
        y0, amp, freq, phase = popt
        subtitle = (f"fit: y0={y0:.3g}, amp={amp:.3g}, "
                    f"freq={freq:.3g}, phase={phase:.3g}, R²={r2:.4f}")
        plt.title(subtitle, fontsize=10)

        plt.legend()
        plt.tight_layout()
        plt.show()


class FakeODMR:
    def __init__(self, center, width, amp, baseline=0.0,
                 freq_span=None, n_points=501, noise_sd=None, rng=None):
        self.center    = float(center)
        self.width     = float(width)
        self.amp       = float(amp)
        self.baseline  = float(baseline)
        self.freq_span = 20*width if freq_span is None else float(freq_span)
        self.n_points  = int(n_points)
        self.noise_sd  = abs(self.amp)*0.01 if noise_sd is None else float(noise_sd)
        self.rng       = np.random.default_rng() if rng is None else rng

    def lorentzian(self, x, y0, amp, cen, wid):
        return (y0 + amp * wid ** 2 / ((x - cen) ** 2 + wid ** 2))

    def _lorentzian(self, x):
        return self.lorentzian(x, self.baseline, self.amp, self.center, self.width)

    def generate(self, return_clean=False):
        half = self.freq_span/2
        freq  = np.linspace(self.center - half - 10, self.center + half, self.n_points)
        clean = self._lorentzian(freq)
        noise = self.rng.normal(scale=self.noise_sd, size=self.n_points)
        signal = clean + noise
        return (freq, signal, clean) if return_clean else (freq, signal)

class odmr_plot():
    def __init__(self):
        self.GHz = 1e9
        self.MHz = 1e6

    def generate_problematic_cases(self):
        cases = [
            ("Low amp, moderate noise",
             dict(center=2.87 * self.GHz, width=4 * self.MHz, amp=-0.005, baseline=1.0,
                  n_points=801, noise_sd=0.003)),
            ("High noise",
             dict(center=2.87 * self.GHz, width=4 * self.MHz, amp=-0.05, baseline=1.0,
                  n_points=801, noise_sd=0.03)),
            ("Very narrow, coarse sampling",
             dict(center=2.87 * self.GHz, width=0.5 * self.MHz, amp=-0.05, baseline=1.0,
                  n_points=201, noise_sd=0.002)),
            ("Very broad, edges truncated",
             dict(center=2.87 * self.GHz, width=30 * self.MHz, amp=-0.05, baseline=1.0,
                  freq_span=40 * self.MHz, n_points=801, noise_sd=0.004)),
            ("Sloping baseline",
             dict(center=2.87 * self.GHz, width=4 * self.MHz, amp=-0.05, baseline=1.0,
                  n_points=801, noise_sd=0.004)),
            ("Few points (sparse sampling)",
             dict(center=2.87 * self.GHz, width=4 * self.MHz, amp=-0.05, baseline=1.0,
                  n_points=51, noise_sd=0.003)),
            ("Peak near edge (off‑centre)",
             dict(center=2.87 * self.GHz, width=3 * self.MHz, amp=-0.05, baseline=1.0,
                  n_points=801, noise_sd=0.004))
        ]
        return cases

    def run(self):
        cases = self.generate_problematic_cases()
        summary = []

        # ------------------------------------------------------------
        # Loop through cases: generate → fit → plot
        # ------------------------------------------------------------
        for label, params in cases:
            # create synthetic data
            freq, signal, _ = FakeODMR(**params).generate(return_clean=True)

            # introduce sloped baseline for that one case
            if label == "Sloping baseline":
                slope = 0.05  # 5 % change across span
                signal += slope * (freq - freq.mean()) / freq.ptp()

            # attempt Lorentzian fit
            try:
                analysis = ODMR_analysis(intensity=signal, frequency=freq)  # note: (intensity, frequency)
                p0 = analysis._guess_params(freq, signal)
                popt, pcov, baseline = analysis.fit_odmr_lorentzian(freq, signal)
                center, width = popt[2], popt[3]
                fit_success = True
            except RuntimeError:
                popt, pcov = None, None
                center, width = np.nan, np.nan
                fit_success = False

            # prepare smooth curve for plotting if fit succeeded
            dense = np.linspace(freq.min(), freq.max(), 4001)
            if fit_success:
                fit_curve = analysis.Lorentzian(dense, *popt)

                # ----------- figure (one per trace) ----------------------
                plt.figure()
                plt.plot(freq / 1e9, signal, ms=3, alpha=0.8, label="data")
                if fit_success:
                    plt.plot(dense / 1e9, fit_curve, '-', lw=2, label="Lorentzian fit")
                    subtitle = (f"center = {center / 1e9:.6f} GHz  ·  "
                                f"width = {width / self.MHz:.3f} MHz")
                    #plt.plot(freq / 1e9, baseline)
                else:
                    subtitle = "FIT FAILED"

                plt.xlabel("Frequency (GHz)")
                plt.ylabel("Intensity (arb. u.)")
                plt.title(f"{label}\n{subtitle}")
                plt.legend()
                plt.tight_layout()
                plt.show()

                # ----------- collect summary row ------------------------
                summary.append({
                    "case": label,
                    "n_points": params["n_points"],
                    "amp": params["amp"],
                    "width (MHz)": params["width"] / self.MHz,
                    "noise_sd": params["noise_sd"],
                    "fit_ok": fit_success,
                    "fit_center (GHz)": None if not fit_success else center / 1e9,
                    "fit_width (MHz)": None if not fit_success else width / self.MHz
                })
            else:
                print("Fitting failed")

        # ------------------------------------------------------------
        # Print final table
        # ------------------------------------------------------------
        print("\n=== Summary of generated cases and fit results ===")
        print(pd.DataFrame(summary).to_string(index=False))


if __name__ == "__main__":
    a = Rabi_analysis()
    a.load_actual_data()
    a.plot_actual_data()
    a.plot_with_fit()
    # odmr_plot = odmr_plot()
    # odmr_plot.run()



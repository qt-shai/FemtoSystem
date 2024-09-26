import unittest
import numpy as np
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog
import csv
import time
from Common import intensity_to_rgb_heatmap_normalized, load_from_csv, open_dialog, fast_rgb_convert

class TestFastRGBPlot(unittest.TestCase):
    def setUp(self):
        # Initialize test environment variables
        viewport_width = 800
        viewport_height = 600
        # Simulated scan data for testing purposes
        scan_data = np.random.rand(100, 100, 100) * 255

    def test_fast_rgb_plot(self):

        idx_scan = [1, 3, 0]

        # file = r"Q:\QT-Quantum_Optic_Lab\expData\scan\2024_9_11_3_43_58scan__.csv"
        file = r"Q:\QT-Quantum_Optic_Lab\expData\scan\2024_7_7_22_19_48scan elect grade.csv"
        data = load_from_csv(file)
        np_array = np.array(data)
        allPoints = np_array[0:, 3]
        self.Xv = np_array[0:, 4].astype(float) / 1e6
        self.Yv = np_array[0:, 5].astype(float) / 1e6
        self.Zv = np_array[0:, 6].astype(float) / 1e6

        allPoints = allPoints.astype(float)  # intensities
        Nx = int(round((self.Xv[-1] - self.Xv[0]) / (self.Xv[1] - self.Xv[0])) + 1)
        if self.Yv[Nx] - self.Yv[0] == 0:
            Nx, allPoints = self.attempt_to_display_unfinished_frame(allPoints=allPoints)

        Ny = int(round((self.Yv[-1] - self.Yv[0]) / (self.Yv[Nx] - self.Yv[0])) + 1)  # 777
        if Nx * Ny < len(self.Zv) and self.Zv[Ny * Nx] - self.Zv[0] > 0:  # Z[Ny*Nx]-Z[0] > 0:
            Nz = int(round((self.Zv[-1] - self.Zv[0]) / (self.Zv[Ny * Nx] - self.Zv[0])) + 1)
            res = np.reshape(allPoints, (Nz, Ny, Nx))
        else:
            Nz = 1
            res = np.reshape(allPoints[0:Nx * Ny], (Nz, Ny, Nx))

        scan_data = res

        self.Xv = self.Xv[0:Nx]
        self.Yv = self.Yv[0:Nx * Ny:Nx]
        self.Zv = self.Zv[0:-1:Nx * Ny]
        # xy
        startLoc = [int(np_array[1, 4].astype(float) / 1e6), int(np_array[1, 5].astype(float) / 1e6),
                         int(np_array[1, 6].astype(float) / 1e6)]  # um
        endLoc = [int(np_array[-1, 4].astype(float) / 1e6), int(np_array[-1, 5].astype(float) / 1e6),
                       int(np_array[-1, 6].astype(float) / 1e6)]  # um




        arrYZ = np.flipud(scan_data[:, :, idx_scan[0]])
        arrXZ = np.flipud(scan_data[:, idx_scan[1], :])
        arrXY = np.flipud(scan_data[idx_scan[2], :, :])

        # result_arrayXY_ = fast_rgb_convert(arrYZ).reshape(Nx, Ny)
        # result_arrayXZ_ = fast_rgb_convert(arrXZ).reshape(Nx, Nz)
        # result_arrayYZ_ = fast_rgb_convert(arrXY).reshape(Ny, Nz)

        result_arrayXY_ = fast_rgb_convert(arrXY)
        result_arrayXZ_ = fast_rgb_convert(arrXZ)
        result_arrayYZ_ = fast_rgb_convert(arrYZ)

        # Plotting the results
        plt.figure(figsize=(10, 10))

        plt.subplot(131)
        plt.title('XY Plane')
        plt.imshow(result_arrayXY_.reshape(Ny,Nx,4), cmap='viridis')

        plt.subplot(132)
        plt.title('XZ Plane')
        plt.imshow(result_arrayXZ_.reshape(Nz,Nx,4), cmap='viridis')

        plt.subplot(133)
        plt.title('YZ Plane')
        plt.imshow(result_arrayYZ_.reshape(Ny,Nz,4), cmap='viridis')

        plt.show()

    def attempt_to_display_unfinished_frame(self, allPoints):
        # Check and remove incomplete repetition if needed
        self.Xv, self.Yv, self.Zv, allPoints, Nx = self.check_last_period(self.Xv, self.Yv, self.Zv, allPoints)
        return Nx, allPoints

    def check_last_period(self, x, y, z, allPoints):
        X_length = len(x)
        tolerance = 1e-10  # Set tolerance for floating point comparisons

        # Find the difference between the last two elements
        last_diff = x[-1] - x[-2]

        # Find the maximum value and its last occurrence using NumPy
        max_x = np.max(x)
        LastIdx = X_length - np.argmax(x[::-1] == max_x)  # Index of the last occurrence of max_x

        # Remove the incomplete section at the end based on LastIdx
        x_fixed = x[:LastIdx]
        y_fixed = y[:LastIdx]
        z_fixed = z[:LastIdx]
        allPoints_fixed = allPoints[:LastIdx]

        # Calculate the pattern length
        if len(x_fixed) > 1:
            pattern_length = int(np.ceil((x_fixed[-1] - x_fixed[0]) / last_diff) + 1)  # Round up
        else:
            pattern_length = 0  # Handle edge case where pattern cannot be calculated

        print(f'Pattern length: {pattern_length}')
        print(f'LastIdx: {LastIdx}')

        return x_fixed, y_fixed, z_fixed, allPoints_fixed, pattern_length

if __name__ == "__main__":
    unittest.main()

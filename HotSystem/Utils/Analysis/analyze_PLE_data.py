import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

from Utils import open_file_dialog

# Load the CSV file
file_path = open_file_dialog("Select PLE data file")
df = pd.read_csv(file_path, delimiter='\t')

# Extract X and Intensity columns
x_values = df["X"]
intensity_values = df["Intensity"]

# Define the number of bins
num_bins = 100

# Bin the X values and compute the average intensity for each bin
bins = np.linspace(x_values.min(), x_values.max(), num_bins + 1)
bin_indices = np.digitize(x_values, bins)
binned_intensity = [intensity_values[bin_indices == i].mean() for i in range(1, num_bins + 1)]

# Compute bin centers for plotting
bin_centers = (bins[:-1] + bins[1:]) / 2

# Plot the data
plt.figure(figsize=(10, 6))
plt.plot(bin_centers, binned_intensity, marker='o', linestyle='-', markersize=3)
plt.xlabel("X")
plt.ylabel("Intensity")
plt.title("Binned Intensity vs X")
plt.grid(True)

# Show the plot
plt.show()

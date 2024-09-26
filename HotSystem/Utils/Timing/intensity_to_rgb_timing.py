import matplotlib.pyplot as plt
import numpy as np
from typing import Union
import timeit


def intensity_to_rgb_heatmap(intensities: Union[float, np.ndarray], cmap=plt.get_cmap('jet')) -> np.ndarray:
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
    rgb_colors = (rgba_colors[..., :3] * 255).astype(np.uint8)

    return rgb_colors


def intensity_to_rgb_manual(intensities: Union[float, np.ndarray]) -> np.ndarray:
    """
    Convert intensity values to RGB colors using a custom gradient.

    :param intensities: A float or a NumPy array (1D, 2D, or 3D) of intensity values.
    :return: A NumPy array of RGB colors.
    """
    # Ensure intensities are within the range [0, 1)
    intensities = np.clip(intensities, 0, 0.99999999)

    # Define a custom gradient: from blue (low) to red (high)
    # Adjust these arrays to create different gradients
    r = intensities * 255
    g = (1 - np.abs(intensities - 0.5) * 2) * 255
    b = (1 - intensities) * 255

    # Stack the channels together to form an RGB image
    rgb_colors = np.stack([r, g, b], axis=-1).astype(np.uint8)

    return rgb_colors

def intensity_to_rgb_heatmap_v1(intensity: float) -> tuple:
    cmap = plt.get_cmap('jet')
    intensity = max(0, min(0.99999999, intensity))
    rgba_color = cmap(intensity)
    rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))
    return rgb_color

def intensity_to_rgb_heatmap_v2(intensity: float, cmap=plt.get_cmap('jet')) -> tuple:
    intensity = max(0, min(0.99999999, intensity))
    rgba_color = cmap(intensity)
    rgb_color = tuple(int(rgba_color[i] * 255) for i in range(4))
    return rgb_color

def intensity_to_rgb_heatmap_v3(intensity: float, cmap=plt.get_cmap('jet')) -> tuple:
    intensity = max(0, min(0.99999999, intensity))
    rgba_color = cmap(intensity)
    rgb_color = tuple(int(v * 255) for v in rgba_color[:3])
    return rgb_color

intensity = 0.5

# Time the original function
time_v1 = timeit.timeit(lambda: intensity_to_rgb_heatmap_v1(intensity), number=10000)

# Time the precomputed colormap function
time_v2 = timeit.timeit(lambda: intensity_to_rgb_heatmap_v2(intensity), number=10000)

# Time the optimized RGB conversion function
time_v3 = timeit.timeit(lambda: intensity_to_rgb_heatmap_v3(intensity), number=10000)

print(f"Original Function Time: {time_v1:.6f} seconds")
print(f"Precomputed Colormap Time: {time_v2:.6f} seconds")
print(f"Optimized RGB Conversion Time: {time_v3:.6f} seconds")

# Generate test data (e.g., a 3D array of intensities)


# Function to time the point-by-point processing
def time_function(function, intensities):
    for i in range(intensities.shape[0]):
        for j in range(intensities.shape[1]):
            # for k in range(intensities.shape[2]):
            function(intensities[i, j])


print("Testing array speed for 100X100")

intensities = np.random.rand(100, 100)
# Timing for the first function
# time_v1 = timeit.timeit(lambda: time_function(intensity_to_rgb_heatmap_v1, intensities), number=3)

# # Timing for the second function
# time_v2 = timeit.timeit(lambda: time_function(intensity_to_rgb_heatmap_v2, intensities), number=3)
#
# # Timing for the third function
# time_v3 = timeit.timeit(lambda: time_function(intensity_to_rgb_heatmap_v3, intensities), number=3)
#
# print(f"Original Function Time: {time_v1:.6f} seconds")
# print(f"Precomputed Colormap Time: {time_v2:.6f} seconds")
# print(f"Optimized RGB Conversion Time: {time_v3:.6f} seconds")

# Time the optimized function
time_optimized = timeit.timeit(lambda: intensity_to_rgb_heatmap(intensities), number=100)
# time_manual = timeit.timeit(lambda: intensity_to_rgb_manual(intensities), number=100)

# Time the array functions
print(f"Optimized array Function Time: {time_optimized:.6f} seconds")
# print(f"Manual array Function Time: {time_manual:.6f} seconds")

intensities = np.random.rand(10, 10)

print("Testing array speed for 10X10")
# Time the optimized function
time_optimized = timeit.timeit(lambda: intensity_to_rgb_heatmap(intensities), number=100)
# time_manual = timeit.timeit(lambda: intensity_to_rgb_manual(intensities), number=100)
time_v1 = timeit.timeit(lambda: time_function(intensity_to_rgb_heatmap_v1, intensities), number=3)
print(f"Original Function Time: {time_v1:.6f} seconds")
# Time the array functions
print(f"Optimized array Function Time: {time_optimized:.6f} seconds")
# print(f"Manual array Function Time: {time_manual:.6f} seconds")

def compare_functions(intensities: np.ndarray) -> bool:
    """
    Compare the results of intensity_to_rgb_heatmap_v1 with intensity_to_rgb_manual.

    :param intensities: A NumPy array (1D, 2D, or 3D) of intensity values.
    :return: True if the results are identical, False otherwise.
    """
    # Apply the original function point by point
    original_results = np.zeros((*intensities.shape, 3), dtype=np.uint8)
    for idx, intensity in np.ndenumerate(intensities):
        original_results[idx] = intensity_to_rgb_heatmap_v1(intensity)[:3]  # Ignore the alpha channel

    # Apply the manual function
    optimzied_results = intensity_to_rgb_heatmap(intensities)

    # Compare the results
    identical = np.array_equal(original_results, optimzied_results)

    if not identical:
        print("Differences found:")
        differences = np.where(original_results != optimzied_results)
        for idx in zip(*differences):
            print(f"Index: {idx}, Original: {original_results[idx]}, Optimal: {optimzied_results[idx]}")

    return identical


intensities = np.array(np.meshgrid(np.linspace(0, 1, 100), np.linspace(0, 1, 100)))[0,:,:]
result = compare_functions(intensities)
print(f"Are the results identical? {result}")


def method_1_loop_based(intensities: np.ndarray) -> np.ndarray:
    """
    Loop-based method: Converts the intensity array to RGBA and appends the alpha channel using loops.
    """
    result_array_ = []
    for j in range(intensities.shape[1]):
        for i in range(intensities.shape[0]):
            res = intensity_to_rgb_heatmap(intensities.astype(np.uint8)[i][j] / 255.0)
            result_array_.append(res[0] / 255)
            result_array_.append(res[1] / 255)
            result_array_.append(res[2] / 255)
            result_array_.append(1)
    return np.array(result_array_)


def method_2_vectorized(intensities: np.ndarray) -> np.ndarray:
    """
    Vectorized method: Converts the entire intensity array to RGBA in one go using NumPy's vectorized operations.
    """
    rgb_colors = intensity_to_rgb_heatmap(intensities / 255.0)
    rgba_colors = np.concatenate([rgb_colors / 255.0, np.ones((*rgb_colors.shape[:-1], 1))], axis=-1)
    return rgba_colors.reshape(-1)


print("Testing iteration times")

# Timing the loop-based method
loop_time = timeit.timeit(lambda: method_1_loop_based(intensities), number=10)

# Timing the vectorized method
vector_time = timeit.timeit(lambda: method_2_vectorized(intensities), number=10)

print(f"Loop-based Method Time: {loop_time:.6f} seconds")
print(f"Vectorized Method Time: {vector_time:.6f} seconds")


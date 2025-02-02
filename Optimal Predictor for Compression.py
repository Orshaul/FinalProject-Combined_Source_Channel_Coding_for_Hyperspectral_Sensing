import numpy as np
import warnings
import spectral
from collections import Counter
import huffman
import time
import matplotlib.pyplot as plt
import pandas as pd
warnings.filterwarnings("ignore")



# Define the G and H matrices for (7,4) Hamming code
G = np.array([[1, 0, 0, 0, 1, 1, 0],
              [0, 1, 0, 0, 1, 0, 1],
              [0, 0, 1, 0, 1, 1, 1],
              [0, 0, 0, 1, 0, 1, 1]])

H = np.array([[1, 1, 1, 0, 1, 0, 0],
              [1, 0, 1, 1, 0, 1, 0],
              [0, 1, 1, 1, 0, 0, 1]])


# Predictor functions
# This function predicts each pixel's value using the value of its right neighbor.
# At the image's right edge, the last column is filled with the value from the second-to-last column.
def predictor_right_neighbor(image):
    predictor = np.roll(image[:, :, :5], shift=-1, axis=1)
    predictor[:, -1, :] = predictor[:, -2, :]
    return predictor

# This function predicts each pixel's value using the value of its left neighbor.
# At the image's left edge, the first column is filled with the value from the second column.
def predictor_left_neighbor(image):
    predictor = np.roll(image[:, :, :5], shift=1, axis=1)
    predictor[:, 0, :] = predictor[:, 1, :]
    return predictor

# This function predicts each pixel's value using the value of its top neighbor.
# At the image's top edge, the first row is filled with the value from the second row.
def predictor_top_neighbor(image):
    predictor = np.roll(image[:, :, :5], shift=-1, axis=0)
    predictor[-1, :, :] = predictor[-2, :, :]
    return predictor

# This function predicts each pixel's value using the value of its bottom neighbor.
# At the image's bottom edge, the last row is filled with the value from the second-to-last row.
def predictor_bottom_neighbor(image):
    predictor = np.roll(image[:, :, :5], shift=1, axis=0)
    predictor[0, :, :] = predictor[1, :, :]
    return predictor

# This function predicts each pixel's value as the average of its four spatial neighbors (top, bottom, left, right).
# At the edges of the image, the nearest valid neighbor values are used to compute the average.
def predictor_average_neighbors(image):
    predictor = (
        np.roll(image[:, :, :5], shift=-1, axis=1) +  # Right
        np.roll(image[:, :, :5], shift=1, axis=1) +   # Left
        np.roll(image[:, :, :5], shift=-1, axis=0) +  # Top
        np.roll(image[:, :, :5], shift=1, axis=0)     # Bottom
    ) / 4
    predictor[:, -1, :] = predictor[:, -2, :]
    predictor[:, 0, :] = predictor[:, 1, :]
    predictor[-1, :, :] = predictor[-2, :, :]
    predictor[0, :, :] = predictor[1, :, :]
    return predictor

# This function uses a custom logic to predict each pixel's value based on its spatial neighbors
# (top, left, top-left, top-right) and its spectral neighbor in the previous band.
def predictor_custom(image):
    rows, cols, bands = image.shape
    predictor = np.zeros((rows, cols, bands), dtype=np.int32)

    for band in range(bands):
        for i in range(1, rows):
            for j in range(1, cols):
                neighbors = []

                # Add spatial neighbors within bounds
                if i - 1 >= 0:
                    neighbors.append(image[i-1, j, band])  # Top neighbor
                if j - 1 >= 0:
                    neighbors.append(image[i, j-1, band])  # Left neighbor
                if i - 1 >= 0 and j - 1 >= 0:
                    neighbors.append(image[i-1, j-1, band])  # Top-left neighbor
                if i - 1 >= 0 and j + 1 < cols:
                    neighbors.append(image[i-1, j+1, band])  # Top-right neighbor

                # Add spectral neighbor only if band > 0
                if band > 0:
                    neighbors.append(image[i, j, band-1])

                # Compute the predictor as the average of the neighbors
                if neighbors:
                    predictor[i, j, band] = sum(neighbors) // len(neighbors)
    return predictor[:, :, :5]

# This function uses an advanced method to predict pixel values based on both spatial neighbors
# (left, top-left, top, top-right) and spectral neighbors (previous bands with linear weighting).
def predictor_advanced(image):
    rows, cols, bands = image.shape
    predictor = np.zeros((rows, cols, bands), dtype=np.int32)

    # Loop over the bands
    for band in range(bands):
        for i in range(1, rows):
            for j in range(1, cols):
                residual_sum = 0
                weight_sum = 0

                # 1. Spatial neighbors in the same band
                spatial_neighbors = []
                if j - 1 >= 0:
                    spatial_neighbors.append(image[i, j-1, band])       # Left neighbor
                if i - 1 >= 0 and j - 1 >= 0:
                    spatial_neighbors.append(image[i-1, j-1, band])     # Top-left neighbor
                if i - 1 >= 0:
                    spatial_neighbors.append(image[i-1, j, band])       # Top neighbor
                if i - 1 >= 0 and j + 1 < cols:
                    spatial_neighbors.append(image[i-1, j+1, band])      # Right neighbor

                if spatial_neighbors:
                    local_mean = sum(spatial_neighbors) / len(spatial_neighbors)

                    # Calculate residuals for spatial neighbors and add to weighted sum
                    for neighbor in spatial_neighbors:
                        residual = neighbor - local_mean  # Calculate residual
                        residual_sum += residual  # Add residual (weight = 1 for spatial neighbors)
                        weight_sum += 1  # Equal weighting for spatial neighbors

                    # 3. Spectral neighbors in previous bands (apply linear weighting)
                    for z in range(1, 3):
                        if band - z >= 0:  # Check spectral neighbor bounds
                            weight = 1.0 / z  # Linear decreasing weight for spectral neighbors
                            residual = image[i, j, band - z] - local_mean  # Residual with spectral neighbor
                            residual_sum += weight * residual  # Add weighted residual
                            weight_sum += weight

                    # 4. Final weighted predictor is based on weighted residuals
                    predictor[i, j, band] = (residual_sum / weight_sum)

    return predictor[:, :, :5]

# List of predictors
predictors = {
    "Right Neighbor": predictor_right_neighbor,
    "Left Neighbor": predictor_left_neighbor,
    "Top Neighbor": predictor_top_neighbor,
    "Bottom Neighbor": predictor_bottom_neighbor,
    "Average of Neighbors": predictor_average_neighbors,
    "Custom Predictor": predictor_custom,
    "Advanced Predictor": predictor_advanced
}

# Function to perform Huffman encoding on the flattened differences
def huffman_encode_bitstring(flat_differences, huffman_tree):
    encoded_bits = []
    for symbol in flat_differences:
        encoded_bits.extend(list(map(int, huffman_tree[symbol])))
    return np.array(encoded_bits)

# Load the image using the spectral library
try:
    image = spectral.open_image('92AV3C.lan').load()
    print(f"Data type: {image.dtype}")        
    print(f"Size in bits per pixel: {image.dtype.itemsize * 8}")
    print(f"Image dimensions: {image.shape}")
except Exception as e:
    print(f"Error loading image: {e}")
    exit(1)

# Table to store results
results = []

# Iterate over each predictor
for predictor_name, predictor_func in predictors.items():
    # Step 1: Calculate the predictor using the current function
    predictor = predictor_func(image)

    # Step 2: Compute the differences between the image and predictor
    differences = image[:, :, :5] - predictor
    differences = differences.astype(np.int32)
    flat_differences = differences.flatten()

    # Step 3: Perform Huffman encoding on the flattened differences
    frequency = Counter(flat_differences)
    huffman_tree = huffman.codebook(frequency.items())
    encoded_data = huffman_encode_bitstring(flat_differences, huffman_tree)

    # Step 4: Calculate the compression ratio
    bits_per_value = differences.dtype.itemsize * 8
    original_size = len(flat_differences) * bits_per_value
    compressed_size = len(encoded_data)
    compression_ratio = original_size / compressed_size

    # Add the result to the table
    results.append({
        "Predictor": predictor_name,
        "Compression Ratio": f"1:{compression_ratio:.2f}"
    })

# Create a DataFrame to display results
df_results = pd.DataFrame(results)
print(df_results)

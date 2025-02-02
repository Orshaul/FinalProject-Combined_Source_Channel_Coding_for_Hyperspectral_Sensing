import numpy as np
import warnings
import random
import time
from collections import Counter
import matplotlib.pyplot as plt
import spectral
import huffman
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, font
from tabulate import tabulate


# Suppress warnings
warnings.filterwarnings("ignore")


# Constants for CRC
CRC_POLY = 0b1011
CRC_BITS = 3


# Hamming matrices for (7,4) code
G = np.array([[1, 0, 0, 0, 1, 1, 0],
              [0, 1, 0, 0, 1, 0, 1],
              [0, 0, 1, 0, 1, 1, 1],
              [0, 0, 0, 1, 0, 1, 1]])

H = np.array([[1, 1, 1, 0, 1, 0, 0],
              [1, 0, 1, 1, 0, 1, 0],
              [0, 1, 1, 1, 0, 0, 1]])



# CRC Encoding function
def crc_encode(data):
    data = np.concatenate([data, [0] * CRC_BITS])  # This prepares the data for CRC calculation by appending 3 zeros for CRC bits.
    for i in range(len(data) - CRC_BITS):
        if data[i]:
            for j in range(CRC_BITS + 1):
                data[i + j] ^= (CRC_POLY >> (CRC_BITS - j)) & 1
    return data[-CRC_BITS:]



# CRC Check function
def crc_check(data): # Checks whether the CRC bits in the data are valid
    check = np.copy(data)
    for i in range(len(check) - CRC_BITS):
        if check[i]:
            for j in range(CRC_BITS + 1):
                check[i + j] ^= (CRC_POLY >> (CRC_BITS - j)) & 1
    return not any(check[-CRC_BITS:])



# Hamming Encoding function
def hamming_encode_vectorized(bitstring):
    bitstring = np.pad(bitstring, (0, (4 - len(bitstring) % 4) % 4), 'constant')
    bitstring = np.reshape(bitstring, (-1, 4))
    encoded_bitstring = (np.dot(bitstring, G) % 2).reshape(-1)
    return encoded_bitstring



# Hamming Decoding function
def hamming_decode_7bit(received_block):
    syndrome = np.dot(received_block, H.T) % 2
    if np.any(syndrome):
        error_position = np.where((H.T == syndrome).all(axis=1))[0][0]
        received_block[error_position] ^= 1
    return received_block[:4]



# Function to encode using CRC and Hamming
def crc_hamming_encode(bitstring):
    # Step 1: Pad the bitstring to make its length a multiple of 13
    padding_length = (13 - len(bitstring) % 13) % 13     
    bitstring = np.pad(bitstring, (0, padding_length), 'constant')
 
    # Step 2: Split the bitstring into blocks of 13 bits and extend them for CRC
    blocks = bitstring.reshape(-1, 13)
    extended_blocks = np.pad(blocks, ((0, 0), (0, CRC_BITS)), constant_values=0)

    # Step 3: Calculate the CRC for each block using the CRC polynomial
    for i in range(13):
        mask = extended_blocks[:, i] == 1
        for j in range(CRC_BITS + 1):
            extended_blocks[mask, i + j] ^= (CRC_POLY >> (CRC_BITS - j)) & 1
   
    # Step 4: Append the calculated CRC bits to the original blocks
    crc = extended_blocks[:, -CRC_BITS:]
    combined_blocks = np.hstack((blocks, crc))
    
    # Step 5: Reshape the combined blocks into 4-bit groups and encode with Hamming (7,4)
    reshaped_blocks = combined_blocks.reshape(-1, 4)
    encoded_blocks = np.dot(reshaped_blocks, G) % 2

    return encoded_blocks.flatten()  # Return the flattened encoded bitstring




# Function to decode the data after CRC and Hamming decoding
def crc_hamming_decode_and_validate(received_bitstring):
    # Initialize variables for decoded data and block validation tracking
    decoded_blocks = [] # Stores the decoded bits from valid blocks
    valid_indices = [] # List to store the indices of valid blocks' bits
    valid_blocks = 0 # Counter to track the number of valid blocks
    invalid_blocks = 0 # Counter to track the number of invalid blocks
    current_index = 0 # Tracks the starting index for each block in the original bitstring
    
    # Process the received bitstring in chunks of 28 bits (size of one block with Hamming and CRC
    for i in range(0, len(received_bitstring), 28):
        received_block = received_bitstring[i:i+28] # Extract the current block
        if len(received_block) != 28:
            continue  # Skip incomplete blocks

        # Decode each 7-bit segment within the 28-bit block using Hamming
        decoded_block = [] # Store the 4-bit decoded outputs for this block
        for j in range(0, 28, 7):
            decoded_block.extend(hamming_decode_7bit(received_block[j:j+7]))

        # Check CRC for the decoded block
        if crc_check(np.array(decoded_block)):
            # If the block is valid, exclude the CRC bits and add the data bits to the result
            decoded_blocks.extend(decoded_block[:-CRC_BITS]) # Add the first 13 bits (data) to the result
            # Track the indices of the valid bits in the original data
            valid_indices.extend(range(current_index, current_index + 13))
            valid_blocks += 1 # Increment the valid block counter
        else:
            invalid_blocks += 1 # Increment the invalid block counter

        # Update the starting index for the next block
        current_index += 13

    # Return the decoded data, indices of valid bits, and block statistics
    return np.array(decoded_blocks), valid_indices, valid_blocks, invalid_blocks



# Function to introduce random errors
def introduce_errors(encoded_bitstring, error_rate):
    received_bitstring = np.copy(encoded_bitstring)  # Create a copy of the bitstring to avoid modifying the original
    if error_rate == 0:
        return received_bitstring  # No errors injected
    
    # Inject errors into the bitstring randomly at intervals determined by the error rate
    for i in range(0, len(received_bitstring), error_rate):
        block_start = i # Start of the current block
        block_end = min(i + error_rate, len(received_bitstring)) # End of the current block
        error_index = random.randint(block_start, block_end - 1) # Select a random bit to flip
        received_bitstring[error_index] ^= 1 # Flip the selected bit
    return received_bitstring

    

# Function to calculate BER before and after correction
def Calculate_Ber_NO_CRC(original, received):
    errors = np.sum(original != received)
    total_bits = len(original)
    return errors / total_bits


# Function to calculate the BER after CRC validation
def Calculate_Ber_After_CRC(original, received, valid_indices):
    original = np.array(original)
    received = np.array(received)
    # Filter the original bitstring to include only valid bits
    original_filtered = np.array([original[idx] for idx in valid_indices if idx < len(original)])
    # Filter the received bitstring to match the length of the valid original bitstring
    received_filtered = received[:len(original_filtered)]
    # Calculate the number of bit errors using XOR
    errors = np.sum(np.array(original_filtered, dtype=np.uint8) ^ np.array(received_filtered, dtype=np.uint8))
    # Calculate BER as the number of errors divided by the number of valid bits
    ber = errors / len(original_filtered) if len(original_filtered) > 0 else 0
    return ber



# Predictor Calculation
def calculate_predictor(image):
    # creates the Predictor for each pixel based on its right neighbor in the same row for the first 5 spectral bands.
    predictor = np.roll(image[:, :, :5], shift=-1, axis=1)
    #For the last column we creates the Predictor for each pixel based on its left neighbor to handle the missing right neighbor.
    predictor[:, -1, :] = predictor[:, -2, :]
    return predictor



# Hamming Decode Bitstring function
def hamming_decode_bitstring(received_bitstring, original_length):
    decoded_bitstring = [] # Initialize an empty list to store decoded bits
    # Iterate through the received bitstring in chunks of 7 bits (Hamming block size)
    for i in range(0, len(received_bitstring), 7):
        received_block = received_bitstring[i:i+7] # Extract the current 7-bit block
        decoded_block = hamming_decode_7bit(received_block) # Decode the 7-bit block into 4 bits
        decoded_bitstring.extend(decoded_block) # Add the decoded bits to the result
    return np.array(decoded_bitstring[:original_length])




# Huffman Encoding function
def huffman_encode_bitstring(flat_differences, huffman_tree):
    encoded_bits = []  # Initialize an empty list to store the encoded bits
    # Iterate through each symbol in the input sequence
    for symbol in flat_differences:
        # Retrieve the Huffman code for the current symbol from the Huffman tree
        # Convert the Huffman code (string) into a list of integers (binary digits)
        encoded_bits.extend(list(map(int, huffman_tree[symbol])))
    return np.array(encoded_bits)



# Function to decode Huffman encoded bit sequence
def huffman_decode_bitstring(encoded_data, huffman_tree):
    decoded_data = []  # Initialize the list to store the decoded symbols
    buffer = ""
    inverse_huffman_tree = {v: k for k, v in huffman_tree.items()} # Create an inverse Huffman tree to map Huffman codes back to their corresponding symbols
    # Iterate through each bit in the encoded data
    for bit in encoded_data:
        buffer += str(bit)  # Convert bit to string explicitly
        if buffer in inverse_huffman_tree:
            # Decode the symbol and add it to the decoded data
            decoded_data.append(int(inverse_huffman_tree[buffer]))  # Ensure decoded values are integers
            buffer = ""
    return decoded_data




# GUI Functions

def load_image():
    global image, choice
    choice = 1 # Indicate that the image is being loaded (choice 1)
    try:
        # Load the hyperspectral image using the spectral library
        image = spectral.open_image('92AV3C.lan').load()
        # Log metadata about the loaded image (data type, size, dimensions)
        log_output(f"Data type: {image.dtype}\nSize in bits per pixel: {image.dtype.itemsize * 8}\nImage dimensions: {image.shape}", bold=True)
        update_status("Loaded IAN image successfully.", bold=True) # Update the status bar to indicate successful loading
        spectral.view_cube(image, shape=[144, 144, 219]) # Display the hyperspectral image cube for visualization
    except Exception as e:
        # Show an error message box if the image fails to load
        messagebox.showerror("Error", f"Failed to load image: {e}")




def create_custom_image():
    global image, choice
    choice = 2  # Indicate that the custom image option is selected
    try:
        # Get the dimensions from the GUI entry (expected format: "x,y,z")
        dims = dimensions_entry.get()
        x, y, z = map(int, dims.split(','))
        # Validate dimensions (spatial dimensions must be at least 2x2)
        if x < 2 or y < 2:
            raise ValueError("Dimensions must be at least 2x2 in the first two axes.")

        # Create a base spatial gradient
        base_pattern = np.outer(np.linspace(0, 1, x), np.linspace(0, 1, y))

        # Create a hyperspectral image with spectral variatio
        hyperspectral_image = np.zeros((x, y, z), dtype=np.float32)
        for band in range(z):
            spectral_variation = np.sin(2 * np.pi * band / z)  # שונות ספקטרלית
            hyperspectral_image[:, :, band] = base_pattern + spectral_variation

        # Add random noise to the image
        noise_level = 0.1  # רמת רעש
        noise = np.random.normal(loc=0, scale=noise_level, size=(x, y, z))
        hyperspectral_image += noise

        # Normalize and clip the values to a realistic range
        hyperspectral_image = np.clip(hyperspectral_image * 17736, 0, 17736).astype(np.float32)

        # Update the global image variable
        image = hyperspectral_image
        # Log image metadata and dimensions
        log_output(f"Created Created custom image with dimensions: {image.shape}", bold=True)
        log_output(f"Data type: {image.dtype}\nSize in bits per pixel: {image.dtype.itemsize * 8}\n", bold=True)
        # Update the status bar to indicate successful creation
        update_status(f"Created custom image with dimensions: {image.shape}", bold=True)
    except Exception as e:
        # Display an error message if the image creation fails
        messagebox.showerror("Error", f"Failed to create image: {e}")



# System Run Function
def run_process():
    try:
        global image
        # Retrieve user-selected options and parameters
        use_crc = crc_var.get()
        error_rate = int(error_rate_entry.get())

        # Predictor Calculation
        start_time = time.time()
        predictor = calculate_predictor(image) # Calculate the predictor on the first 5 bands

        differences = image[:, :, :5] - predictor
        differences = differences.astype(np.float32)
        flat_differences = differences.flatten()
        log_output(f"Differences shape: {differences.shape}", bold=True)
        log_output("-" * 50)
        
        
        # Huffman Encoding
        frequency = Counter(flat_differences) # Count the frequency of each symbol in the differences
        huffman_tree = huffman.codebook(frequency.items()) # Build the Huffman tree
        encoded_data = huffman_encode_bitstring(flat_differences, huffman_tree) # Encode data
        Process_neto_time = time.time() - start_time # Record process time up to this point

        

        # Encoding with CRC or without CRC
        if use_crc == 'YES':
            log_output("Using CRC and Hamming encoding...")
            log_output('')
            encoded_bitstring = crc_hamming_encode(encoded_data)  # Apply CRC and Hamming (7,4) encoding to the data
        else:
            log_output("Using Hamming encoding without CRC...")
            log_output('')
            encoded_bitstring = hamming_encode_vectorized(encoded_data) # Encode with Hamming only


        # Error Injection
        received_with_errors = introduce_errors(encoded_bitstring, error_rate)
        ber_before_correction = Calculate_Ber_NO_CRC(encoded_bitstring, received_with_errors)
        

        # Decoding and BER Calculation
        if use_crc == 'YES':
            
            # Decode the received bitstring using CRC and Hamming decoding
            decoded_bitstring, valid_indices, valid_blocks, invalid_blocks = crc_hamming_decode_and_validate(received_with_errors)
            decoded_differences_list = huffman_decode_bitstring(decoded_bitstring, huffman_tree)
           
            # Check and adjust the size of the decoded data before reshaping
            expected_size = np.prod(differences.shape) # Calculate the expected size of the data based on the original differences array
            actual_size = len(decoded_differences_list) # Actual size of the decoded data
 
            log_output(f"Expected size: {expected_size}, Actual size: {actual_size}", bold=True)

            # Handle size mismatch: pad with zeros or truncate excess values
            if actual_size < expected_size:
                decoded_differences_list += [0] * (expected_size - actual_size) # Pad with zeros
            elif actual_size > expected_size:
                decoded_differences_list = decoded_differences_list[:expected_size] # Truncate excess data

            # Reshape the decoded differences to match the original dimensions
            decoded_differences = np.array(decoded_differences_list).astype(np.int32).reshape(differences.shape)
            
            # Reconstruct the decompressed image by adding the predictor to the decoded differences
            decompressed_image = predictor + decoded_differences
            
            # Display the original image, compressed differences, and the reconstructed decompressed image
            display_images(image, differences, decompressed_image)
            
            # Calculate BER after correction
            ber_after_correction = Calculate_Ber_After_CRC(encoded_data, decoded_bitstring, valid_indices)
            
            # Log the number of valid and invalid blocks
            log_output(f"*** Number of Valid Blocks: {valid_blocks} ***", bold=True, italic=True, color="green")
            log_output(f"*** Invalid Removed Blocks: {invalid_blocks} ***", bold=True, italic=True, color="red")
            log_output('')
            
            # Check whether the decompressed image matches the original first 5 bands of the original image
            if np.array_equal(image[:, :, :5], decompressed_image):
                log_output("*** Decompressed image matches the original image ***", bold=True, italic=True, color="green", font_size=16)
                log_output('')

            else:
                log_output("*** Decompressed image does not match the original image ***", bold=True, italic=True, color="red", font_size=16)
            
        else:
            # Decode the received bitstring using Hamming decoding without CRC
            decoded_bitstring = hamming_decode_bitstring(received_with_errors, len(encoded_data))
            decoded_differences_list = huffman_decode_bitstring(decoded_bitstring, huffman_tree)  # Using the inverse Huffman tree
            # Check and adjust the size of the decoded data before reshaping
            expected_size = np.prod(differences.shape) # Expected size based on the original differences
            actual_size = len(decoded_differences_list) # Actual size of the decoded data


            # Handle size mismatch: pad with zeros or truncate excess values
            if actual_size < expected_size:
                decoded_differences_list += [0] * (expected_size - actual_size) # Add zeros for missing data
            elif actual_size > expected_size:
                decoded_differences_list = decoded_differences_list[:expected_size] # Truncate extra data
             
             # Rebuild the decompressed image by adding the predictor to the decoded difference
            decoded_differences = np.array(decoded_differences_list).astype(np.int32).reshape(differences.shape) 
            decompressed_image = predictor + decoded_differences
            # Display the original image, compressed data (differences), and the reconstructed decompressed image
            display_images(image, differences, decompressed_image)
            ber_after_correction = Calculate_Ber_NO_CRC(encoded_data, decoded_bitstring) # Calculate BER after correction



            # Check if the decompressed image matches the original image
            if np.array_equal(image[:, :, :5], decompressed_image):
                log_output("*** Decompressed image matches the original image ***", bold=True, italic=True, color="green", font_size=16)
                log_output('')

            else:
                log_output("*** Decompressed image does not match the original image ***", bold=True, italic=True, color="red", font_size=16)




     # Compression Ratio
        bits_per_value = differences.dtype.itemsize * 8
        original_size = len(flat_differences) * bits_per_value
        compressed_size = len(encoded_data)
        compression_ratio = original_size / compressed_size

        # Results
        total_bits = (image.shape[0] * image.shape[1] * image.shape[2])
        time_per_pixel_ns = (Process_neto_time / total_bits) * 1e9
        computational_complexity = (1/total_bits) * 1e9

        # Generate textual result
        results = (
            f"Compression Ratio: 1:{compression_ratio:.2f}\n"
            f"BER Before: {ber_before_correction:.10f}\n"
            f"BER After: {ber_after_correction:.10f}\n"
            f"Compression Time: {Process_neto_time:.6f} seconds\n"
            f"Time Per Pixel: {time_per_pixel_ns:.2f} ns"
        )
        
        log_output("Quantitative Requirements:", bold=True, italic=True, font_size=18)
        log_output(results, bold=True)


        # Condition checks and logging
        log_output("\u2500" * 50)

        if compression_ratio > 4.0:
            log_output("Meets the compression ratio requirement: compression ratio > 1:4", italic=True)
        else:
            log_output("Does not meet the compression ratio requirement: compression ratio ≤ 1:4", italic=True)

        log_output("\u2500" * 50)

        if ber_after_correction < 1e-5:
            log_output("Meets BER requirement: BER after < 10^-5", italic=True)
        else:
            log_output("Does not meet BER requirement: BER after ≥ 10^-5", italic=True)

        log_output("\u2500" * 50)

        if time_per_pixel_ns <= 216:
            log_output(f"Meets computational complexity requirement: time per pixel ≤ {computational_complexity:.2f} ns", italic=True)
        else:
            log_output(f"Does not meet computational complexity requirement: time per pixel > {computational_complexity:.2f} ns", italic=True)

        log_output("\u2500" * 50)
        
        
        # Final success check
        if compression_ratio > 4.0 and ber_after_correction < 1e-5 and time_per_pixel_ns <= 216:
            success_message = "*** The decoder has successfully decoded according to all required conditions! ***"
            log_output(success_message, bold=True, italic=True, color="green")
            update_status("Decoding Successful!", bold=True)
        else:
            failure_message = "*** The decoder does not meet all the required conditions for successful decoding ***."
            log_output(failure_message, bold=True, italic=True, color="red")
            update_status("Decoding may lead to incorrect results. Consider adjusting the parameters.", bold=True)

        
        
        # Summary Table of Quantitative Requirements
        log_output('\nSummary Table of Quantitative Requirements:', bold=True, font_size=18, font_name="Courier", italic=True)
        data = [
            ["Compression Ratio", f"1:{compression_ratio:.2f}"],
            ["BER after correction", f"{ber_after_correction:.10f}"],
            ["Compression Time (seconds)", f"{Process_neto_time:.6f}"],
            ["Time per pixel (ns)", f"{time_per_pixel_ns:.2f}"]
        ]

        table = tabulate(data, headers=["Quantitative Requirement", "Value"], tablefmt="grid")
        log_output(table, bold=True)
        log_output('-' * 172, bold=True)

    except Exception as e:
        import tkinter.messagebox as messagebox
        messagebox.showerror("Error", str(e))
    

# GUI Window
root = tk.Tk() # Initialize the main GUI window
root.title("FINAL PROJECT: Combined Source/Channel Coding for Hyperspectral Sensing") # Set the window title
root.geometry("900x800")  # Set the dimensions of the window
root.configure(bg="#4a4a4a")  # Background color

# Logging Window

# Create a frame for the logging window
log_frame = tk.Frame(root, bg="#ffffff", bd=2, relief=tk.SUNKEN)
log_frame.pack(pady=10, fill=tk.BOTH, expand=True)

# Create a text widget for logging messages
log_text = tk.Text(log_frame, wrap='word', height=12, font=("Courier", 14), bg="#ffffff", fg="black")
log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add a vertical scrollbar for the log window
scrollbar = tk.Scrollbar(log_frame, command=log_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Link the scrollbar to the text widget
log_text.config(yscrollcommand=scrollbar.set)

# Labels and Inputs Frame
frame_inputs = tk.Frame(root, bg="#f7f7f7")
frame_inputs.pack(pady=20)


label_font = ("Arial", 12)
button_font = ("Arial", 12)


# Create a labeled frame for the "Input Image" choose section
input_frame = tk.LabelFrame(frame_inputs, text="Input Image", padx=20, pady=15, font=("Arial", 14, "bold"), bg="#f7f7f7")
input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
input_frame.columnconfigure(1, weight=1)

# Add a label and button for loading the IAN image
tk.Label(input_frame, text="Choose Input Image:", anchor='w', width=25, bg="#f7f7f7", font=label_font).grid(row=0, column=0, padx=5)
load_button = tk.Button(input_frame, text="Load IAN Image", command=load_image, font=(button_font,12), bg="gray", fg="white", relief="raised")
load_button.grid(row=0, column=1, padx=5)

# Add a label, entry field, and button for creating a custom image
tk.Label(input_frame, text="Or Create Custom Image:", anchor='w', width=25, bg="#f7f7f7", font=label_font).grid(row=1, column=0, padx=5)
dimensions_entry = tk.Entry(input_frame, font=label_font)
dimensions_entry.grid(row=1, column=1, padx=5, pady=5)
create_button = tk.Button(input_frame, text="Create Image", command=create_custom_image, font=button_font, bg="#ff9800", fg="white", relief="raised")
create_button.grid(row=2, column=1, padx=5, pady=5)

# Create a labeled frame for CRC selection
crc_frame = tk.LabelFrame(frame_inputs, text="CRC Settings", padx=20, pady=20, font=("Arial", 14, "bold"), bg="#f7f7f7")
crc_frame.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
crc_frame.columnconfigure(1, weight=1)

# Add a dropdown menu for selecting CRC usage
crc_var = tk.StringVar(value='NO') # Default value is 'NO'
tk.Label(crc_frame, text="Use CRC:", anchor='w', width=25, bg="#f7f7f7", font=label_font).grid(row=0, column=0, padx=5)
crc_dropdown = ttk.Combobox(crc_frame, textvariable=crc_var, values=['YES', 'NO'], state="readonly", font=label_font)
crc_dropdown.grid(row=0, column=1, padx=5, pady=5)
crc_dropdown.current(1)

# Create a labeled frame for entering the error rate
error_frame = tk.LabelFrame(frame_inputs, text="Error Rate Entry", padx=20, pady=20, font=("Arial", 14, "bold"), bg="#f7f7f7")
error_frame.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
error_frame.columnconfigure(1, weight=1)

# Add a label and entry field for the error rate
tk.Label(error_frame, text="Error Rate:", anchor='w', width=25, bg="#f7f7f7", font=label_font).grid(row=0, column=0, padx=5)
error_rate_entry = tk.Entry(error_frame, font=label_font)
error_rate_entry.grid(row=0, column=1, padx=5, pady=5)




# Define hover effect for the "Run Process" button
def on_enter(event):
    event.widget.config(bg="#45a049") # Change button background color when the mouse hovers over it


def on_leave(event):
    event.widget.config(bg="#4CAF50") # Revert button background color when the mouse leaves

# Create a frame for the Run button
run_button_frame = tk.Frame(frame_inputs, bg="#f7f7f7") # Frame to organize the "Run Process" button
run_button_frame.grid(row=3, column=0, padx=10, pady=20, sticky="ew") # Place the frame in the grid layout

# Add the "Run Process" button
run_button = tk.Button(run_button_frame, text="Run Process", command=run_process, font=button_font, bg="#4CAF50", fg="white", relief="raised")
run_button.grid(row=0, column=0, padx=5, pady=5)
run_button.bind("<Enter>", on_enter)
run_button.bind("<Leave>", on_leave)


# Create a status label to display the current process status
status_label = tk.Label(root, text="Status: Ready", fg="green", bg="#f7f7f7", font=label_font)
status_label.pack(pady=10)



# Dedicated Display Window
def display_images(image, differences, decompressed_image):
    bands_to_show = [0, 1, 2, 3, 4] # Select the first 5 spectral bands for visualization
    plt.figure(figsize=(12, 8)) # Create a figure with the specified size

    for i, band in enumerate(bands_to_show):
        # Display the original image for the current band
        plt.subplot(3, 5, i + 1)
        plt.imshow(image[:, :, band], cmap='gray')
        plt.title(f'Original (Band {band})', fontsize=10)

        plt.subplot(3, 5, i + 6)
        plt.imshow(differences[:, :, band], cmap='gray')
        plt.title(f'Compressed (Band {band})', fontsize=10)

        plt.subplot(3, 5, i + 11)
        plt.imshow(decompressed_image[:, :, band], cmap='gray')
        plt.title(f'Decompressed (Band {band})', fontsize=10)

    plt.tight_layout()
    plt.draw()  # Render the plot without blocking the program
    plt.pause(0.001)  # Pause briefly to allow the GUI to remain responsive



# Function to reset the interface
def restart_process():
    log_text.delete(1.0, tk.END) # Clear all text from the log widget
    update_status("Ready", bold=False) # Reset the status label to "Ready"


# Add a "Clear" button next to the "Run Process" button
Clear_button = tk.Button(run_button_frame, text="Clear", command=restart_process, font=button_font, bg="#f44336", fg="white", relief="flat")
Clear_button.grid(row=0, column=1, padx=5, pady=5)



# Function to update the status label with a given message
def update_status(message, bold=False):
    if bold:
        font_style = font.Font(family="Helvetica", size=12, weight="bold")
        status_label.config(text=f"Status: {message}", font=font_style, fg="green")
    else:
        status_label.config(text=f"Status: {message}")
        
        
# Function to log a message with custom formatting in the log text widget       
def log_output(message, bold=False, italic=False, color="black", font_name="Courier", font_size=14):
    # Create a unique tag name based on the style parameters
    tag_name = f"style_{color}_{font_name}_{font_size}_{'bold' if bold else ''}{'italic' if italic else ''}"
    
    # Configure the tag for the specified style if it doesn't already exist
    if tag_name not in log_text.tag_names():
        font_style = (font_name, font_size, "bold italic" if bold and italic else "bold" if bold else "italic" if italic else "normal")
        log_text.tag_configure(tag_name, font=font_style, foreground=color)

    # Insert the message into the log text widget with the specified style
    log_text.insert(tk.END, message + "\n", tag_name)
    log_text.see(tk.END) # Automatically scroll to the end of the log



# Start the GUI Main Loop
root.mainloop()




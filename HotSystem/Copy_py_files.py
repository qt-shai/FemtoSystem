import os
import shutil
import time
from datetime import datetime

def copy_files(source_dir, destination_dirs):
    """
    Copies all *.py and *.xml files from source_dir and its subdirectories to multiple destination directories,
    creating subfolders with the current date and time and skipping files in 'venv', '__pycache__', and other excluded folders.

    Args:
        source_dir (str): The directory to copy files from.
        destination_dirs (list): A list of directories to copy files to.
    """
    start_time = time.time()

    try:
        # Get current date and time
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        for destination_dir in destination_dirs:
            # Check if the directory exists
            if not os.path.exists(destination_dir):
                # Fallback logic
                alternative_dir = "C:\\Users\\Femto\\Work Folders\\Documents"
                print(f"{destination_dir} does not exist. Falling back to {alternative_dir}.")
                destination_dir = alternative_dir

            base_dest_folder = os.path.join(destination_dir, f"HotSystem{timestamp}")
            os.makedirs(base_dest_folder, exist_ok=True)

            # Iterate over all directories and subdirectories in the source directory
            for root, dirs, files in os.walk(source_dir):
                dirs[:] = [d for d in dirs if d not in {'.idea', '.venv', '__pycache__', '.vscode','venv','dlls'}]

                for file_name in files:
                    if file_name.endswith(('.py', '.xml')):  # Check for .py and .xml files
                        # Construct full paths for source and destination
                        source_path = os.path.join(root, file_name)
                        relative_path = os.path.relpath(root, source_dir)
                        dest_folder = os.path.join(base_dest_folder, relative_path)
                        destination_path = os.path.join(dest_folder, file_name)

                        # Ensure destination subdirectory exists
                        os.makedirs(dest_folder, exist_ok=True)

                        # Copy file
                        shutil.copy2(source_path, destination_path)
                        print(f"Copied: {source_path} -> {destination_path}")

        elapsed_time = time.time() - start_time
        print(f"All .py and .xml files have been successfully copied in {elapsed_time:.2f} seconds.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    source_directory = "C:\\WC\\HotSystem"
    destination_directories = [
        "Q:\\QT-Quantum_Optic_Lab\\Shai-OpticsLab",
        "C:\\Users\\shai\\Work Folders\\Documents"
    ]

    copy_files(source_directory, destination_directories)

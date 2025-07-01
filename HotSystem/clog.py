import shutil
import sys
import os

# Usage:
# python clog.py e
# python clog.py o
# python clog.py p

def copy_logged_points(short_code: str):
    base_dir = os.getcwd()  # Change to a specific directory if needed

    mapping = {
        "e": "logged_points_elsc.txt",
        "o": "logged_points_omri.txt",
        "p": "logged_points_prawer.txt",
        "m": "logged_points_mdm.txt",
    }

    short_code = short_code.lower()

    # Determine source file
    if short_code in mapping:
        src_filename = mapping[short_code]
    else:
        src_filename = f"logged_points_{short_code}.txt"

    src_file = os.path.join(base_dir, src_filename)
    dst_file = os.path.join(base_dir, "logged_points.txt")

    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {src_file} → {dst_file}")
    else:
        print(f"Source file not found: {src_file}")

if __name__ == "__main__":
    # Default to 'e' if no input is provided (e.g. run from PyCharm)
    if len(sys.argv) == 1:
        print("No argument provided. Defaulting to 'e'.")
        copy_logged_points('e')
    elif len(sys.argv) == 2:
        copy_logged_points(sys.argv[1])
    else:
        print("Usage: python clog.py [e|o|p|m|<custom_name>]")
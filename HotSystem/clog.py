import shutil
import sys
import os

def copy_logged_points(short_code: str):
    base_dir = os.getcwd()

    mapping = {
        "e": "logged_points_elsc.txt",
        "o": "logged_points_omri.txt",
        "p": "logged_points_prawer.txt",
        "m": "logged_points_mdm.txt",
    }

    short_code = short_code.lower().strip()
    is_reverse = short_code.startswith("!")
    code = short_code[1:] if is_reverse else short_code

    if is_reverse:
        src_file = os.path.join(base_dir, "logged_points.txt")
        dst_filename = mapping.get(code, f"logged_points_{code}.txt")
        dst_file = os.path.join(base_dir, dst_filename)
    else:
        src_filename = mapping.get(code, f"logged_points_{code}.txt")
        src_file = os.path.join(base_dir, src_filename)
        dst_file = os.path.join(base_dir, "logged_points.txt")

    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {src_file} -> {dst_file}")
    else:
        print(f"Source file not found: {src_file}")

def copy_query_file(tag: str):
    base_dir = os.getcwd()
    tag = tag.strip()
    is_reverse = tag.startswith("!")
    key = tag[1:] if is_reverse else tag

    if is_reverse:
        src_file = os.path.join(base_dir, f"saved_query_points_{key}.txt")
        dst_file = os.path.join(base_dir, "saved_query_points.txt")
    else:
        src_file = os.path.join(base_dir, "saved_query_points.txt")
        dst_file = os.path.join(base_dir, f"saved_query_points_{key}.txt")

    if os.path.exists(src_file):
        shutil.copyfile(src_file, dst_file)
        print(f"Copied {src_file} -> {dst_file}")
    else:
        print(f"Source file not found: {src_file}")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("No argument provided. Defaulting to 'e'.")
        copy_logged_points('e')
    elif len(sys.argv) == 2:
        arg = sys.argv[1].strip().lower()
        if arg.startswith("q"):
            copy_query_file(arg[1:])  # e.g., 'q39' → '39' is tag
        else:
            copy_logged_points(arg)
    else:
        print("Usage: python clog.py [e|o|p|m|!e|q39|!q39|...]")

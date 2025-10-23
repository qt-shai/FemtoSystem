# generate_carrier_sequence.py
# Create a sequence of SLM BMPs from either:
#   (A) a "zero carrier" BMP (chosen by index)  OR
#   (B) a correction BMP (chosen by index or given full path)
# Output directory: C:\WC\SLM_bmp
#
# Default carrier mesh (periods across aperture):
#   X: -200 .. 200  (step 50)
#   Y: -200 .. 200  (step 50)
#   Total frames = 9 * 9 = 81  (named 1.bmp .. 81.bmp)
#
# Usage examples:
#   python generate_carrier_sequence.py                    # interactive zero-carrier pick
#   python generate_carrier_sequence.py --idx 3            # zero-carrier index 3
#   python generate_carrier_sequence.py --source corr      # interactive correction BMP pick
#   python generate_carrier_sequence.py --source corr --idx 2
#   python generate_carrier_sequence.py --source corr --corr "Q:\...path...\MY_CORR.bmp"
#   python generate_carrier_sequence.py --force
#
# Override mesh if desired:
#   python generate_carrier_sequence.py --x0 -300 --x1 300 --xs 30 --y0 -300 --y1 300 --ys 30

import os
import sys
import argparse
import glob
import json
import numpy as np
import cv2

# ---------- CONSTANTS ----------
ZERO_DIR = r"C:\WC\SLM_bmp\zero_carrier"
OUT_DIR  = r"C:\WC\SLM_bmp"

# Your default correction file from the app; used to find the corrections directory
DEFAULT_CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
DEFAULT_CORR_DIR = os.path.dirname(DEFAULT_CORR_BMP)

# Default mesh (inclusive), periods across the aperture
DEFAULT_X0 = -200
DEFAULT_X1 =  200
DEFAULT_XS =  50

DEFAULT_Y0 = -200
DEFAULT_Y1 =  200
DEFAULT_YS =  50
# --------------------------------

def u8_to_phase(u8):
    return (u8.astype(np.float32) / 255.0) * (2.0 * np.pi)

def phase_to_u8(phase):
    phase = np.mod(phase, 2.0 * np.pi)
    return np.uint8(np.round(phase * (255.0 / (2.0 * np.pi))))

def read_u8_gray(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    return img

def list_bmps(folder):
    os.makedirs(folder, exist_ok=True)
    return sorted(glob.glob(os.path.join(folder, "*.bmp")))

def list_zero_files():
    return list_bmps(ZERO_DIR)

def list_corr_files():
    if not os.path.isdir(DEFAULT_CORR_DIR):
        return []
    return list_bmps(DEFAULT_CORR_DIR)

def ensure_out_dir():
    os.makedirs(OUT_DIR, exist_ok=True)

def write_sequence_params_default():
    """Create sequence_display_parameters.json if missing (frame_time_ms=30)."""
    params_path = os.path.join(OUT_DIR, "sequence_display_parameters.json")
    if not os.path.exists(params_path):
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump({"frame_time_ms": 30}, f, indent=2)

def generate_mesh(start, stop, step):
    """Inclusive int mesh: start..stop with 'step'."""
    if step == 0:
        return [start]
    # Ensure the stop is included if it lands exactly on the grid
    sign = 1 if step > 0 else -1
    return list(range(int(start), int(stop) + sign, int(step)))

def choose_by_index(paths, prompt):
    if not paths:
        return None
    print(prompt)
    for i, p in enumerate(paths, 1):
        try:
            img = cv2.imread(p, cv2.IMREAD_UNCHANGED)
            shape = None if img is None else img.shape
        except Exception:
            shape = None
        print(f"  [{i:2d}] {os.path.basename(p)}  {shape if shape else ''}")
    try:
        sel = int(input(f"Choose index (1..{len(paths)}): ").strip())
    except Exception:
        return None
    if sel < 1 or sel > len(paths):
        return None
    return paths[sel - 1]

def main():
    parser = argparse.ArgumentParser(description="Generate SLM BMP sequence by adding carriers to a source phase (zero-carrier or correction BMP).")
    parser.add_argument("--source", choices=["zero", "corr"], default="zero",
                        help="Source image type: zero-carrier BMP from zero_carrier dir (default) or correction BMP (corr).")
    parser.add_argument("--idx", type=int, default=None, help="Index for the chosen source (1-based; shown in list).")
    parser.add_argument("--corr", type=str, default=None, help="Full path to a specific correction BMP (overrides --idx for corr).")
    parser.add_argument("--force", action="store_true", help="Overwrite existing numbered BMPs without prompt.")

    # --- argparse additions/changes ---
    parser.add_argument("--no-shuffle", action="store_true",
                        help="Disable random permutation; generate frames in raster order.")
    parser.add_argument("--seed", type=int, default=None,
                        help="Seed for the random permutation (set for reproducible order).")
    parser.add_argument("--no-manifest", action="store_true",
                        help="Do not write sequence_manifest.json.")

    # Mesh overrides (default set by constants above)
    parser.add_argument("--x0", type=int, default=DEFAULT_X0)
    parser.add_argument("--x1", type=int, default=DEFAULT_X1)
    parser.add_argument("--xs", type=int, default=DEFAULT_XS)
    parser.add_argument("--y0", type=int, default=DEFAULT_Y0)
    parser.add_argument("--y1", type=int, default=DEFAULT_Y1)
    parser.add_argument("--ys", type=int, default=DEFAULT_YS)
    args = parser.parse_args()

    # Pick source path
    src_path = None
    src_kind = args.source  # "zero" or "corr"

    def _print_with_shape(paths):
        for i, p in enumerate(paths, 1):
            try:
                im = cv2.imread(p, cv2.IMREAD_UNCHANGED)
                shape = None if im is None else im.shape
            except Exception:
                shape = None
            print(f"  [{i:2d}] {os.path.basename(p)}  {shape if shape else ''}")

    if src_kind == "zero":
        zeros = list_zero_files()
        if not zeros:
            print(f"No BMPs found in {ZERO_DIR}")
            return 1

        # If the user passes idx=0 → use correction BMP
        if args.idx == 0:
            if not os.path.isfile(DEFAULT_CORR_BMP):
                print(f"Correction BMP not found: {DEFAULT_CORR_BMP}")
                return 3
            src_path = DEFAULT_CORR_BMP
            src_kind = "corr"
        elif args.idx is not None:
            # 1-based selection from zero-carrier list
            if 1 <= args.idx <= len(zeros):
                src_path = zeros[args.idx - 1]
            else:
                print(f"Invalid --idx for zero list: {args.idx} (valid: 0..{len(zeros)})")
                return 2
        else:
            # Interactive: show [0] option for correction + the zero list
            print(f"Zero-carrier files in {ZERO_DIR}:")
            print(f"  [ 0] (use correction BMP)  {os.path.basename(DEFAULT_CORR_BMP)}")
            _print_with_shape(zeros)
            try:
                sel = int(input(f"Choose index (0..{len(zeros)}): ").strip())
            except Exception:
                return 2
            if sel == 0:
                if not os.path.isfile(DEFAULT_CORR_BMP):
                    print(f"Correction BMP not found: {DEFAULT_CORR_BMP}")
                    return 3
                src_path = DEFAULT_CORR_BMP
                src_kind = "corr"
            elif 1 <= sel <= len(zeros):
                src_path = zeros[sel - 1]
            else:
                print("Invalid selection.")
                return 2

    else:  # src_kind == "corr"
        # If a path is given, use it; else list directory, with 0 meaning default correction
        if args.corr:
            if not os.path.isfile(args.corr):
                print(f"Correction BMP not found: {args.corr}")
                return 3
            src_path = args.corr
        else:
            corrs = list_corr_files()
            # Ensure DEFAULT_CORR_BMP is visible even if not in the dir listing
            if DEFAULT_CORR_BMP and os.path.isfile(DEFAULT_CORR_BMP) and DEFAULT_CORR_BMP not in corrs:
                corrs = [DEFAULT_CORR_BMP] + corrs

            if args.idx == 0:
                if not os.path.isfile(DEFAULT_CORR_BMP):
                    print(f"Correction BMP not found: {DEFAULT_CORR_BMP}")
                    return 3
                src_path = DEFAULT_CORR_BMP
            elif args.idx is not None:
                if 1 <= args.idx <= len(corrs):
                    src_path = corrs[args.idx - 1]
                else:
                    print(f"Invalid --idx for correction list: {args.idx} (valid: 0..{len(corrs)})")
                    return 5
            else:
                print(f"Correction BMPs in {DEFAULT_CORR_DIR}:")
                print(f"  [ 0] {os.path.basename(DEFAULT_CORR_BMP)} (default)")
                _print_with_shape(corrs)
                try:
                    sel = int(input(f"Choose index (0..{len(corrs)}): ").strip())
                except Exception:
                    return 5
                if sel == 0:
                    if not os.path.isfile(DEFAULT_CORR_BMP):
                        print(f"Correction BMP not found: {DEFAULT_CORR_BMP}")
                        return 3
                    src_path = DEFAULT_CORR_BMP
                elif 1 <= sel <= len(corrs):
                    src_path = corrs[sel - 1]
                else:
                    print("Invalid selection.")
                    return 5

    print(f"Using {'zero-carrier' if src_kind=='zero' else 'correction'} source: {src_path}")

    # Load source → phase
    src_u8 = read_u8_gray(src_path)
    H, W = src_u8.shape
    base_phase = u8_to_phase(src_u8)

    ensure_out_dir()
    write_sequence_params_default()

    # --- always overwrite: silently remove any existing BMPs in OUT_DIR ---
    for _old in glob.glob(os.path.join(OUT_DIR, "*.bmp")):
        try:
            os.remove(_old)
        except Exception:
            pass

    # Carrier grids (inclusive)
    xs = generate_mesh(args.x0, args.x1, args.xs)
    ys = generate_mesh(args.y0, args.y1, args.ys)

    # Build full list of (Cx, Cy) carriers, SKIP (0,0)
    pairs = [(Cx, Cy) for Cy in ys for Cx in xs if not (Cx == 0 and Cy == 0)]
    total = len(pairs)

    # --- DEFAULT: shuffle unless user asked not to ---
    shuffled = not args.no_shuffle
    if shuffled:
        rng = np.random.default_rng(args.seed)
        rng.shuffle(pairs)

    print(f"Generating {total} frames into {OUT_DIR} "
          f"(X: {xs[0]}..{xs[-1]} step {args.xs}; Y: {ys[0]}..{ys[-1]} step {args.ys})")
    if (0 in xs) and (0 in ys):
        print("Note: skipping (Cx=0, Cy=0) frame.")
    print("Order:", "SHUFFLED" + (f" (seed={args.seed})" if args.seed is not None else "")
    if shuffled else "RASTER")

    # Pre-allocate normalized coordinate grids once
    yy, xx = np.mgrid[0:H, 0:W]
    xx = xx.astype(np.float32) / float(W)
    yy = yy.astype(np.float32) / float(H)

    # Generate frames by the chosen order
    manifest = {
        "source_kind": src_kind,
        "source_path": src_path,
        "out_dir": OUT_DIR,
        "x_mesh": {"start": args.x0, "stop": args.x1, "step": args.xs, "values": xs},
        "y_mesh": {"start": args.y0, "stop": args.y1, "step": args.ys, "values": ys},
        "skip_zero": (0 in xs) and (0 in ys),
        "shuffled": bool(shuffled),
        "seed": args.seed,
        "frames": []
    }

    for n, (Cx, Cy) in enumerate(pairs, start=1):
        ramp = 2.0 * np.pi * (Cx * xx + Cy * yy)  # periods across aperture
        out_phase = np.mod(base_phase + ramp, 2.0 * np.pi)
        out_u8 = phase_to_u8(out_phase)

        out_path = os.path.join(OUT_DIR, f"{n}.bmp")
        ok = cv2.imwrite(out_path, out_u8)
        if not ok:
            print(f"Failed to write {out_path}")
            return 6

        if (n % 25) == 0 or n == 1 or n == total:
            print(f"  [{n:4d}/{total}] Cx={Cx:+.0f}, Cy={Cy:+.0f} -> {os.path.basename(out_path)}")

        # record manifest info
        manifest["frames"].append({"n": n, "Cx": int(Cx), "Cy": int(Cy), "file": f"{n}.bmp"})

    print("Done.")
    print(f"Wrote frames 1.bmp .. {total}.bmp in {OUT_DIR}")

    # Write manifest (unless disabled)
    if not args.no_manifest:
        with open(os.path.join(OUT_DIR, "sequence_manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print("Saved sequence_manifest.json")
    return 0

if __name__ == "__main__":
    sys.exit(main())

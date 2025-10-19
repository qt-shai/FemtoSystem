# I — do 10 more GS steps and update the SLM instantly
#
# S — save current CGH to C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp
#
# F/H/V — toggle display flips (Full reset / Horizontal / Vertical) if your optics need it
#
# Q/ESC — quit

# Flips/orientation: If the measured move is opposite to the steering ramp, toggle your display flips (H/V) or swap ramp sign.
# APOD_SIGMA: If you see ringing, increase to 0.15–0.18.
# INNER_GS / OUTER_ITERS: Try INNER_GS=25–40, OUTER_ITERS=25–40
# Use raw camera for measurement: If possible, save a raw frame (no cross/text) for the algorithm to read; overlays can bias centroid/MSE slightly.
# Correction map orientation: If things look warped, confirm the correction BMP is not flipped relative to display. If needed, corr_u8 = cv2.flip(corr_u8, 0/1) once.

import os, sys, time
import numpy as np
import cv2

# ------- USER PATHS -------
CORR_BMP   = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"     # used only in Internal mode
WATCH_PATH = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"  # Zelux writes here
SAVE_BMP   = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"  # S key saves here too

# ------- DISPLAY / UI -------
MONITOR_NUM   = 3     # 1-based Windows “Identify” number of the SLM monitor
WATCH_POLL_MS = 120   # poll interval
FLIP_H = False
FLIP_V = False

# ------- (Optional) INTERNAL MODE ONLY -------
# You can ignore these if you never press 'G'
X_SHIFT, Y_SHIFT, ROT_DEG = -17, 114, 0.0
GS_STEPS_INIT = 60
GS_STEPS_MORE = 10
APOD_SIGMA    = 0.12

# ------- Helpers -------
def ensure_dir(p):
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def read_gray(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def load_u8_panel(path, expected_wh):
    """Read 8-bit panel image (BMP/PNG). Resize to panel with NEAREST if needed."""
    W, H = expected_wh
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
    if img.shape[::-1] != (W, H):
        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)
    return img

def find_monitor_origins():
    try:
        from screeninfo import get_monitors
        mons = get_monitors()
        return [(m.x, m.y, m.width, m.height) for m in mons]
    except Exception:
        return [(0, 0, 1920, 1080)]

def move_window_to_monitor(win_name, monitor_index):
    mons = find_monitor_origins()
    idx = max(0, min(monitor_index-1, len(mons)-1))  # MONITOR_NUM is 1-based
    x0, y0, *_ = mons[idx]
    try:
        cv2.moveWindow(win_name, x0, y0)
    except Exception:
        pass

# ---------- INTERNAL MODE (optional) ----------
def u8_to_phase(u8): return (u8.astype(np.float32)/255.0) * 2*np.pi
def phase_to_u8(phase): return np.uint8(np.round(np.mod(phase, 2*np.pi) * (255.0/(2*np.pi))))
def apply_correction(phase_slm, corr_u8): return np.mod(phase_slm + u8_to_phase(corr_u8), 2*np.pi)

def preprocess_target_to_panel(target_gray, panel_wh):
    W, H = panel_wh
    tgt = cv2.resize(target_gray, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
    if tgt.max() > 0: tgt /= tgt.max()

    # rotation then translation
    Mrot = cv2.getRotationMatrix2D((W/2, H/2), ROT_DEG, 1.0)
    tgt = cv2.warpAffine(tgt, Mrot, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    Mtran = np.float32([[1, 0, X_SHIFT], [0, 1, Y_SHIFT]])
    tgt = cv2.warpAffine(tgt, Mtran, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # apodization
    yy, xx = np.mgrid[0:H, 0:W]
    x = (xx - W/2)/(W/2); y = (yy - H/2)/(H/2)
    r2 = x*x + y*y
    apod = np.exp(-r2/(2*APOD_SIGMA*APOD_SIGMA)).astype(np.float32)
    tgt *= apod
    tgt /= (tgt.max() + 1e-8)
    return tgt

def gs_farfield(target_amp, steps, phase_init=None, rng_seed=1):
    H, W = target_amp.shape
    if phase_init is None:
        phase = np.random.default_rng(rng_seed).uniform(0, 2*np.pi, size=(H, W)).astype(np.float32)
    else:
        phase = phase_init.copy()
    for _ in range(steps):
        field_s = np.exp(1j * phase)
        field_f = np.fft.fftshift(np.fft.fft2(field_s))
        phase_f = np.angle(field_f)
        field_f_new = target_amp * np.exp(1j * phase_f)
        field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))
        phase = np.angle(field_s_back).astype(np.float32)
    return np.mod(phase, 2*np.pi)

# ---------- MAIN ----------
def main():
    # Panel size from correction map (only to size the window correctly)
    corr = read_gray(CORR_BMP)
    H, W = corr.shape
    print(f"Panel from correction: {W}x{H}")

    # Window on the SLM monitor
    win = "SLM CGH"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    move_window_to_monitor(win, MONITOR_NUM)
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # Start in EXTERNAL mode (pure listener)
    external_mode = True
    print("➡ External mode ON (listener). G=toggle to Internal, H/V flips, S save, Q/Esc quit")
    print("   Watching:", WATCH_PATH)

    # Display buffer (start black)
    img_u8 = np.zeros((H, W), np.uint8)

    # Track changes robustly (mtime + size)
    last_sig = None  # (mtime, size)

    # Internal mode state (only used if toggled)
    current_phase = None
    target_amp = None

    flip_h, flip_v = FLIP_H, FLIP_V

    while True:
        if external_mode:
            try:
                if os.path.exists(WATCH_PATH):
                    st = os.stat(WATCH_PATH)
                    sig = (st.st_mtime, st.st_size)
                    if sig != last_sig:
                        # retry loop to avoid half-written file
                        for _ in range(6):  # up to ~0.6s
                            try:
                                img_u8 = load_u8_panel(WATCH_PATH, (W, H))
                                last_sig = sig
                                print(f"[External] Reloaded CGH @ {time.strftime('%H:%M:%S')}  "
                                      f"(size={st.st_size})")
                                break
                            except Exception:
                                time.sleep(0.1)
                # else: keep showing previous frame
            except Exception:
                pass

        # Render (with flips)
        show = img_u8
        if flip_h: show = cv2.flip(show, 1)
        if flip_v: show = cv2.flip(show, 0)
        cv2.imshow(win, show)

        key = cv2.waitKey(WATCH_POLL_MS) & 0xFF
        if key in (ord('q'), 27):
            break

        elif key == ord('h'):
            flip_h = not flip_h; print(f"Flip H = {flip_h}")
        elif key == ord('v'):
            flip_v = not flip_v; print(f"Flip V = {flip_v}")
        elif key == ord('f'):
            flip_h = flip_v = False; print("Flips reset.")
        elif key == ord('s'):
            ensure_dir(SAVE_BMP)
            ok = cv2.imwrite(SAVE_BMP, img_u8)
            print(("Saved " + SAVE_BMP) if ok else "Save failed!")

        elif key == ord('g'):
            external_mode = not external_mode
            if external_mode:
                print("➡ External mode ON (listener).")
                last_sig = None
            else:
                print("➡ Internal mode ON (GS). I=iterate, S=save, G=back to external")
                # lazy init internal state here
                desired = read_gray(TARGET_BMP)
                target_amp = preprocess_target_to_panel(desired, (W, H))
                print("Running initial GS…")
                phase = gs_farfield(target_amp, GS_STEPS_INIT, phase_init=None, rng_seed=1)
                phase_corr = apply_correction(phase, corr)
                img_u8 = phase_to_u8(phase_corr)
                current_phase = phase

        elif key == ord('i') and (not external_mode):
            # internal-only
            current_phase = gs_farfield(target_amp, GS_STEPS_MORE, phase_init=current_phase, rng_seed=None)
            phase_corr = apply_correction(current_phase, corr)
            img_u8 = phase_to_u8(phase_corr)
            print(f"Added {GS_STEPS_MORE} GS steps.")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

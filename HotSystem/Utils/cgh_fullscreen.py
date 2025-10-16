import os, sys, time, pathlib
import numpy as np
import cv2

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

# ------- USER PATHS -------
CORR_BMP = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"
SAVE_BMP   = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"

# ------- TRANSFORMS from your SLM UI -------
X_SHIFT, Y_SHIFT, ROT_DEG = -17, 114, 0.0   # pixels

# ------- GS / DISPLAY PARAMS -------
GS_STEPS_INIT = 60        # initial GS steps before first display
GS_STEPS_MORE = 10        # steps when you press 'I'
APOD_SIGMA    = 0.12      # edge taper to reduce ringing
MONITOR_NUM  = 3  # 1-based Windows “Identify” number of the SLM monitor

# External control: Zelux writes here; SLM app watches and reloads
WATCH_EXTERNAL = True
WATCH_PATH = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"
WATCH_POLL_MS = 120  # how often to check for changes (milliseconds)

# Optional flips (if your optical train mirrors axes):
FLIP_H = False
FLIP_V = False

# ------- Helpers -------
def u8_to_phase(u8): return (u8.astype(np.float32)/255.0) * 2*np.pi
def phase_to_u8(phase): return np.uint8(np.round(np.mod(phase, 2*np.pi) * (255.0/(2*np.pi))))

def read_gray(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img

def preprocess_target_to_panel(target_gray, panel_wh):
    W, H = panel_wh
    tgt = cv2.resize(target_gray, (W, H), interpolation=cv2.INTER_AREA).astype(np.float32)
    if tgt.max() > 0: tgt /= tgt.max()

    # rotation then translation (match your SLM UI semantics)
    Mrot = cv2.getRotationMatrix2D((W/2, H/2), ROT_DEG, 1.0)
    tgt = cv2.warpAffine(tgt, Mrot, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    Mtran = np.float32([[1, 0, X_SHIFT], [0, 1, Y_SHIFT]])
    tgt = cv2.warpAffine(tgt, Mtran, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)

    # apodization to reduce ringing
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
        field_s = np.exp(1j * phase)                      # unit amplitude at SLM
        field_f = np.fft.fftshift(np.fft.fft2(field_s))   # far-field
        phase_f = np.angle(field_f)
        field_f_new = target_amp * np.exp(1j * phase_f)   # impose target amplitude
        field_s_back = np.fft.ifft2(np.fft.ifftshift(field_f_new))
        phase = np.angle(field_s_back).astype(np.float32) # keep phase only
    return np.mod(phase, 2*np.pi)

def apply_correction(phase_slm, corr_u8):
    return np.mod(phase_slm + u8_to_phase(corr_u8), 2*np.pi)

def find_monitor_origins():
    """
    Returns a list of monitor origins [(x0,y0,width,height), ...]
    Requires screeninfo if available; otherwise falls back to primary only.
    pip install screeninfo
    """
    try:
        from screeninfo import get_monitors
        mons = get_monitors()
        return [(m.x, m.y, m.width, m.height) for m in mons]
    except Exception:
        # Fallback: primary screen only
        w = cv2.getWindowImageRect("tmp")[2] if cv2.getWindowProperty("tmp", 0) >= 0 else 1920
        h = cv2.getWindowImageRect("tmp")[3] if cv2.getWindowProperty("tmp", 0) >= 0 else 1080
        return [(0, 0, w, h)]

def move_window_to_monitor(win_name, monitor_index):
    mons = find_monitor_origins()
    if not mons:
        return
    idx = max(0, min(monitor_index, len(mons)-1))
    x0, y0, w, h = mons[idx]
    try:
        cv2.moveWindow(win_name, x0, y0)
    except Exception:
        pass

def ensure_dir(p):
    d = os.path.dirname(p)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def load_u8_panel(path, expected_wh):
    """Read 8-bit grayscale BMP/PNG; resize if needed (nearest)."""
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

# ------- Main -------
def main():
    # 1) Load correction (panel size)
    corr = read_gray(CORR_BMP)
    H, W = corr.shape
    print(f"Panel from correction: {W}x{H}")

    # 2) Load desired image and make target amplitude on panel
    desired = read_gray(TARGET_BMP)
    target_amp = preprocess_target_to_panel(desired, (W, H))

    # 3) Initial phase (internal GS) and first image (we may override with external)
    print("Running initial GS...")
    phase_slm = gs_farfield(target_amp, GS_STEPS_INIT, phase_init=None, rng_seed=1)
    phase_corr = apply_correction(phase_slm, corr)
    img_u8 = phase_to_u8(phase_corr)

    # Local flip state
    flip_h = False
    flip_v = False

    # 4) Window to SLM monitor (MONITOR_NUM is 1-based)
    win = "SLM CGH"
    cv2.namedWindow(win, cv2.WINDOW_NORMAL)
    move_window_to_monitor(win, MONITOR_NUM)  # <-- 1-based
    cv2.setWindowProperty(win, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

    # 5) External mode init
    external_mode = bool(WATCH_EXTERNAL)
    last_mtime = None
    if external_mode:
        try:
            if os.path.exists(WATCH_PATH):
                last_mtime = os.path.getmtime(WATCH_PATH)
                img_u8 = load_u8_panel(WATCH_PATH, (W, H))
                print(f"[External] Loaded initial CGH: {WATCH_PATH}")
            else:
                print(f"[External] Waiting for file to appear: {WATCH_PATH}")
        except Exception as e:
            print(f"[External] Load failed ({e}); staying with internal image.")

    print("\nControls: G=toggle external/internal  S=save BMP  H/V=flip  F=reset flips  Q/Esc=quit")
    if not external_mode:
        print("Internal mode: I=iterate (+10 GS)")
    else:
        print("External mode: listening for Zelux updates… (I is disabled)")

    current_phase = phase_slm.copy()

    # 6) Main loop
    while True:
        # External watcher: hot-reload when timestamp changes
        if external_mode:
            try:
                if os.path.exists(WATCH_PATH):
                    mtime = os.path.getmtime(WATCH_PATH)
                    if last_mtime is None or mtime > last_mtime:
                        img_u8 = load_u8_panel(WATCH_PATH, (W, H))
                        last_mtime = mtime
                        # Optional: print once per change
                        print(f"[External] Reloaded CGH @ {time.strftime('%H:%M:%S')}")
            except Exception as e:
                # Non-fatal; keep old image
                pass

        # Show (with optional flips)
        show = img_u8
        if flip_h: show = cv2.flip(show, 1)
        if flip_v: show = cv2.flip(show, 0)

        cv2.imshow(win, show)
        key = cv2.waitKey(WATCH_POLL_MS) & 0xFF

        if key in (ord('q'), 27):   # q or ESC
            break

        elif key == ord('g'):
            external_mode = not external_mode
            if external_mode:
                print("➡ External mode ON (I disabled). Watching:", WATCH_PATH)
                last_mtime = None  # force reload on next loop
            else:
                print("➡ Internal mode ON (I enabled).")

        elif key == ord('i') and not external_mode:
            # Internal GS iteration only when external is OFF
            current_phase = gs_farfield(target_amp, GS_STEPS_MORE, phase_init=current_phase, rng_seed=None)
            phase_corr = apply_correction(current_phase, corr)
            img_u8 = phase_to_u8(phase_corr)
            print(f"Added {GS_STEPS_MORE} GS steps.")

        elif key == ord('s'):
            ensure_dir(SAVE_BMP)
            ok = cv2.imwrite(SAVE_BMP, img_u8)
            print(("Saved " + SAVE_BMP) if ok else "Save failed!")

        elif key == ord('h'):
            flip_h = not flip_h
            print(f"Flip H = {flip_h}")

        elif key == ord('v'):
            flip_v = not flip_v
            print(f"Flip V = {flip_v}")

        elif key == ord('f'):
            flip_h = False; flip_v = False
            print("Flips reset.")

    cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

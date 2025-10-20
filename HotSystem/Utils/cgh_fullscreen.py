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
import json, glob, re

# ------- USER PATHS -------
CORR_BMP   = r"Q:\QT-Quantum_Optic_Lab\Lab notebook\Devices\SLM\Hamamatsu disk\LCOS-SLM_Control_software_LSH0905586\corrections\CAL_LSH0905586_532nm.bmp"
TARGET_BMP = r"C:\WC\HotSystem\Utils\Desired_image.bmp"     # used only in Internal mode
WATCH_PATH = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"  # Zelux writes here
SAVE_BMP   = r"C:\WC\HotSystem\Utils\SLM_pattern_iter.bmp"  # S key saves here too
INDEX_BMP_DIR = r"C:\WC\SLM_bmp"
# Map shifted number keys to frame indices
SHIFT_KEY_TO_INDEX = {
    ord('!'): 1,   # Shift+1
    ord('@'): 2,   # Shift+2
    ord('#'): 3,   # Shift+3
    ord('$'): 4,   # Shift+4
    ord('%'): 5,   # Shift+5
    ord('^'): 6,   # Shift+6
    ord('&'): 7,   # Shift+7
    ord('*'): 8,   # Shift+8
    ord('('): 9,   # Shift+9
    ord(')'): 10,  # Shift+0
}

# ------- DISPLAY / UI -------
MONITOR_NUM   = 2     # 1-based Windows “Identify” number of the SLM monitor
MONITOR_HELP_NUM = 1 if MONITOR_NUM != 1 else 2   # pick 2 if your SLM is #1, etc.
HELP_WIN_NAME = "SLM – Help & Status"
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
def next_numbered_path(directory, ext=".bmp"):
    """Return the first path like <directory>/1.bmp, 2.bmp, ... that doesn't exist."""
    i = 1
    os.makedirs(directory, exist_ok=True)
    while True:
        candidate = os.path.join(directory, f"{i}{ext}")
        if not os.path.exists(candidate):
            return candidate
        i += 1
def load_sequence_params(directory):
    """Return frame_time_ms from l; create with default if missing."""
    os.makedirs(directory, exist_ok=True)
    params_path = os.path.join(directory, "sequence_display_parameters.json")
    if not os.path.exists(params_path):
        data = {"frame_time_ms": 30}
        with open(params_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return 30
    try:
        with open(params_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        ft = int(data.get("frame_time_ms", 30))
        return max(1, ft)
    except Exception:
        return 30
def read_sequence_params_json(dir_path):
    import json
    cfg_path = os.path.join(dir_path, "sequence_display_parameters.json")
    frame_time_ms = 30
    try:
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                d = json.load(f)
                frame_time_ms = int(d.get("frame_time_ms", frame_time_ms))
        else:
            with open(cfg_path, "w") as f:
                json.dump({"frame_time_ms": frame_time_ms}, f, indent=2)
    except Exception:
        pass
    return frame_time_ms
def count_bmps(dir_path):
    try:
        return len([f for f in os.listdir(dir_path) if f.lower().endswith(".bmp")])
    except Exception:
        return 0
def _numeric_sort_key(path):
    """Sort '1.bmp','2.bmp',...'10.bmp' numerically; fallback to lexical."""
    name = os.path.basename(path)
    m = re.search(r"(\d+)", name)
    return (int(m.group(1)) if m else float("inf"), name.lower())
def list_sequence_bmps(directory):
    """List .bmp frames sorted. Supports 1.bmp, 2.bmp, ... or any *.bmp."""
    paths = glob.glob(os.path.join(directory, "*.bmp"))
    paths.sort(key=_numeric_sort_key)
    return paths
def overlay_ms_text(gray_u8, ms):
    """Render '<ms>[ms]' onto a copy of the image, bottom-left."""
    if gray_u8.ndim != 2:
        img = gray_u8.copy()
    else:
        img = cv2.cvtColor(gray_u8, cv2.COLOR_GRAY2BGR)
    txt = f"{int(ms)}[ms]"
    h, w = img.shape[:2]
    org = (10, h - 10)
    # stroke + fill for visibility
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,0), 3, cv2.LINE_AA)
    cv2.putText(img, txt, org, cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 1, cv2.LINE_AA)
    # return single-channel if your window shows grayscale; else keep BGR
    try:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception:
        return img
def load_u8_noresize(path):
    """Load an 8-bit BMP exactly as stored (no resizing)."""
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(path)
    # to 8-bit single channel
    if img.ndim == 3:
        if img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2GRAY)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if img.dtype != np.uint8:
        img = np.clip(img, 0, 255).astype(np.uint8)
    return img
def play_sequence_on_window(win_name, panel_wh, flip_h=False, flip_v=False, ignore_keys=None):
    """
    Plays BMP frames from INDEX_BMP_DIR with 'xxx[ms]' overlay.
    Runs forever (no key stops). Keeps the UI responsive via waitKey(1).
    """
    import time

    W, H = panel_wh
    frame_time_ms = load_sequence_params(INDEX_BMP_DIR)
    frames = list_sequence_bmps(INDEX_BMP_DIR)
    if not frames:
        print(f"[Sequence] No *.bmp frames in {INDEX_BMP_DIR}")
        return

    print(f"[Sequence] Playing {len(frames)} frame(s) @ {frame_time_ms} ms each from {INDEX_BMP_DIR} (endless loop)")

    # Ensure window exists (cv2.imshow will also auto-create, but this avoids flicker)
    try:
        cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    except Exception:
        pass

    i = 0
    next_switch = time.monotonic()  # seconds
    last_shown_idx = -1

    while True:
        # (Optional) if you want hot-reload of frame_time_ms, uncomment this block every ~1s:
        # if int(time.monotonic()) % 1 == 0:
        #     frame_time_ms = load_sequence_params(INDEX_BMP_DIR)

        now = time.monotonic()
        if now >= next_switch or i != last_shown_idx:
            path = frames[i]
            try:
                img = load_u8_noresize(path)
                if img.shape[::-1] != (W, H):
                    img = cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)
                img_disp = overlay_ms_text(img, frame_time_ms)
                if flip_h: img_disp = cv2.flip(img_disp, 1)
                if flip_v: img_disp = cv2.flip(img_disp, 0)
                cv2.imshow(win_name, img_disp)
                last_shown_idx = i
                next_switch = now + max(1, int(frame_time_ms)) / 1000.0
                i = (i + 1) % len(frames)
            except Exception as e:
                print(f"[Sequence] Failed to load '{path}': {e}")
                # Skip this frame quickly
                next_switch = now + 0.05
                i = (i + 1) % len(frames)

        # Pump HighGUI so the window repaints and stays interactive.
        # We ignore the key value and never stop here.
        _ = cv2.waitKey(1)  # DO NOT check/branch on this

def human_bool(b): return "ON" if b else "OFF"
def build_help_image(state, width=1100, height=680, dpi_scale=10):
    """
    Render a crisp help/status panel by drawing at 'dpi_scale'× resolution
    and downscaling with INTER_AREA. Returns a BGR image.

    Expected keys in `state` (subset is fine):
      external_mode, flip_h, flip_v, W, H, WATCH_PATH, last_reload,
      SAVE_BMP, INDEX_BMP_DIR, seq_count, frame_time_ms,
      MONITOR_NUM, MONITOR_HELP_NUM,
      # playback extras (shown only when playing):
      playing (bool), current_frame (str), seq_index (int, 1-based), seq_total (int)
    """
    import datetime as _dt
    import numpy as np, cv2, os

    # Hi-res canvas
    Ww, Hw = int(width*dpi_scale), int(height*dpi_scale)
    S = float(dpi_scale)
    img = np.full((Hw, Ww, 3), 255, np.uint8)

    def put(txt, xy, fs=0.62, color=(0,0,0), thick=2, aa=True):
        cv2.putText(
            img, txt,
            (int(xy[0]*S), int(xy[1]*S)),
            cv2.FONT_HERSHEY_SIMPLEX,
            fs*S,
            color,
            max(1, int(round(thick*S))),
            cv2.LINE_AA if aa else cv2.LINE_8
        )

    # Title bar
    cv2.rectangle(img, (0, 0), (Ww, int(54*S)), (32, 32, 32), -1)
    put("SLM CGH – Help & Status", (18, 36), fs=0.95, color=(255,255,255), thick=2)

    # Left column: keys
    xL, y = 22, 92
    lines = [
        "Keys:",
        "  Esc .......... Quit program",
        "  q ............ Return to External (listening) mode",
        "  g ............ Toggle External/Internal (GS) mode",
        "  i ............ (Internal) +10 GS steps",
        "  s ............ Save current CGH to SAVE_BMP",
        "  n ............ Save numbered CGH to INDEX_BMP_DIR",
        "  p ............ Play numbered sequence from INDEX_BMP_DIR",
        "  l ............ Toggle this Help window",
        "  F/H/V ........ Reset flips / Flip Horizontal / Flip Vertical",
        "  Shift+1..9 ... Copy 1.bmp..9.bmp → SAVE_BMP",
        "  Shift+0 ...... Copy 10.bmp → SAVE_BMP",
    ]
    for k, line in enumerate(lines):
        fs = 0.70 if k == 0 else 0.62
        put(line, (xL, y), fs=fs, thick=2)
        y += 28

    # Right column: status
    now = _dt.datetime.now().strftime("%H:%M:%S")
    mode_str = 'External' if state.get('external_mode') else 'Internal (GS)'
    if state.get('playing'):
        mode_str += ' (playing)'

    status = [
        f"Now ............ {now}",
        f"Mode ........... {mode_str}",
        f"Flips .......... H={'ON' if state.get('flip_h', False) else 'OFF'}  "
        f"V={'ON' if state.get('flip_v', False) else 'OFF'}",
        f"Panel size ..... {state.get('W', '?')} x {state.get('H', '?')}",
        f"Watch path ..... {os.path.basename(state.get('WATCH_PATH', ''))}",
        f"Last reload .... {state.get('last_reload', '—')}",
        f"Save BMP ....... {os.path.basename(state.get('SAVE_BMP', ''))}",
        f"Index dir ...... {state.get('INDEX_BMP_DIR', '')}",
        f"Seq frames ..... {state.get('seq_count', '?')}  @ {state.get('frame_time_ms', '?')} ms",
        f"SLM monitor .... #{state.get('MONITOR_NUM', '?')}",
        f"Help monitor ... #{state.get('MONITOR_HELP_NUM', '?')}",
    ]

    # If sequence is playing, append the current frame info
    if state.get("playing"):
        cf = state.get("current_frame") or ""
        cf_name = os.path.basename(cf)
        idx = state.get("seq_index")
        tot = state.get("seq_total") or state.get("seq_count")
        if idx is not None and tot is not None:
            status.append(f"Now playing .... {cf_name}  ({idx}/{tot})")
        else:
            status.append(f"Now playing .... {cf_name}")

    xR, yR = 700, 92
    for line in status:
        put(line, (xR, yR), fs=0.62, thick=2)
        yR += 28

    # Footer
    put("Tips: If ramp direction looks inverted, toggle H/V flips.",
        (22, height-40), fs=0.55, color=(64,64,64), thick=1)

    # Downscale to final size with AA
    out = cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)
    return out

# Numeric filename helpers (used by help/status & sequence tools)
_num_re = re.compile(r"(\d+)")

def list_numbered_bmps(dir_path: str):
    """
    Return a sorted list of (path, n) for files like '123.bmp' in dir_path.
    Non-numeric filenames are ignored.
    """
    if not os.path.isdir(dir_path):
        return []
    items = []
    for p in glob.glob(os.path.join(dir_path, "*.bmp")):
        m = _num_re.search(os.path.basename(p))
        if not m:
            continue
        try:
            n = int(m.group(1))
        except ValueError:
            continue
        items.append((p, n))
    items.sort(key=lambda t: t[1])  # sort by numeric index
    return items

def count_bmps(dir_path: str):
    """
    Return (count, first_index, last_index). If no files, returns (0, None, None).
    """
    items = list_numbered_bmps(dir_path)
    if not items:
        return 0, None, None
    return len(items), items[0][1], items[-1][1]

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

    help_visible = False
    last_reload_str = "—"
    # --- playback state (safe defaults) ---
    playing = False  # currently playing a sequence?
    frames = []  # list of .bmp paths
    seq_idx = -1  # current index (0-based), -1 means none
    current_frame_path = ""  # path of the current frame
    frame_time_ms = load_sequence_params(INDEX_BMP_DIR)  # default frame time
    last_reload_str = "—"  # shown in help

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
                                last_reload_str = time.strftime('%H:%M:%S')
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

        if help_visible:
            state = {
                "external_mode": external_mode,
                "flip_h": flip_h,
                "flip_v": flip_v,
                "W": W, "H": H,
                "WATCH_PATH": WATCH_PATH,
                "last_reload": last_reload_str,
                "SAVE_BMP": SAVE_BMP,
                "INDEX_BMP_DIR": INDEX_BMP_DIR,
                "seq_count": len(frames),  # safe: frames is always defined
                "frame_time_ms": frame_time_ms,  # always defined
                "MONITOR_NUM": MONITOR_NUM,
                "MONITOR_HELP_NUM": MONITOR_HELP_NUM,
                # playback extras
                "playing": playing,
                "current_frame": current_frame_path,  # "" when not playing
                "seq_index": (seq_idx + 1) if playing else None,
                "seq_total": len(frames) if playing else None,
            }
            help_img = build_help_image(state)
            cv2.imshow(HELP_WIN_NAME, help_img)

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
        elif key == ord('n'):
            # Save the current CGH to C:\WC\SLM_bmp\1.bmp, 2.bmp, ...
            numbered_path = next_numbered_path(INDEX_BMP_DIR, ext=".bmp")
            # If you want the exact displayed orientation (with flips), save `show`; otherwise save `img_u8`
            ok = cv2.imwrite(numbered_path, show)  # or img_u8
            print(("Saved " + numbered_path) if ok else "Numbered save failed!")
        elif key == ord('p'):
            frames = list_sequence_bmps(INDEX_BMP_DIR)
            if not frames:
                print(f"[Sequence] No *.bmp frames in {INDEX_BMP_DIR}")
            else:
                playing = True
                seq_idx = 0
                current_frame_path = frames[seq_idx]
                # (Optionally set a timer to advance frames every frame_time_ms)
                print(f"[Sequence] Playing {len(frames)} frame(s) @ {frame_time_ms} ms each")
                # Play numbered sequence from INDEX_BMP_DIR with overlayed frame time from JSON.
                play_sequence_on_window(win, (W, H), flip_h=flip_h, flip_v=flip_v, ignore_keys={ord('l')})
        elif key == ord('q'):
            # Force return to External listening mode (default)
            external_mode = True
            # If you have sequence playback state, stop it:
            try:
                playing = False
            except NameError:
                pass
            last_sig = None  # force a reload on next file change
            print("External mode ON (listener). G=toggle to Internal, H/V flips, S save, Esc quit")
        elif key == ord('l'):  # VK_F1
            help_visible = not help_visible
            if help_visible:
                cv2.namedWindow(HELP_WIN_NAME, cv2.WINDOW_NORMAL)
                move_window_to_monitor(HELP_WIN_NAME, MONITOR_HELP_NUM)
                cv2.resizeWindow(HELP_WIN_NAME, 960, 720)
                print(f"Help window ON (monitor #{MONITOR_HELP_NUM}).")
            else:
                try:
                    cv2.destroyWindow(HELP_WIN_NAME)
                except Exception:
                    pass
        elif key in SHIFT_KEY_TO_INDEX:
            idx = SHIFT_KEY_TO_INDEX[key]
            try:
                src = os.path.join(INDEX_BMP_DIR, f"{idx}.bmp")
                if not os.path.exists(src):
                    print(f"[!] '{src}' not found.")
                else:
                    img = load_u8_noresize(src)
                    # resize to panel if needed (NEAREST preserves LUT indices)
                    if img.shape[::-1] != (W, H):
                        img = cv2.resize(img, (W, H), interpolation=cv2.INTER_NEAREST)
                    ensure_dir(SAVE_BMP)
                    ok = cv2.imwrite(SAVE_BMP, img)
                    if ok:
                        print(f"[!] Copied {idx}.bmp → {SAVE_BMP}")
                        img_u8 = img.copy()  # show immediately
                    else:
                        print("[!] Failed to write SAVE_BMP.")
            except Exception as e:
                print(f"[!] Error copying {idx}.bmp → SAVE_BMP: {e}")

    cv2.destroyAllWindows()

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)

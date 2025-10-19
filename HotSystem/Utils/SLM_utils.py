import time, cv2, numpy as np

def phase_to_u8(phase_rad):
    ph = np.mod(phase_rad, 2 * np.pi)
    return np.uint8(np.round(ph * (255.0 / (2 * np.pi))))


def u8_to_phase(u8):
    return (u8.astype(np.float32) / 255.0) * 2 * np.pi

def detect_dc_center(g, guess=None, win_frac=0.30):
    """
    Return (dcx, dcy) in image coords.
    Assumes DC is a BRIGHT spot.
    Searches around 'guess' (defaults to image center),
    then refines with a 5×5 weighted centroid (sub-pixel).
    """
    import numpy as np, cv2

    H, W = g.shape[:2]
    if guess is None:
        guess = (W * 0.5, H * 0.5)
    cxg, cyg = map(float, guess)

    # --- search window around guess (clamped) ---
    rx = int(max(24, win_frac * W * 0.5))
    ry = int(max(24, win_frac * H * 0.5))
    x0, x1 = max(0, int(cxg - rx)), min(W, int(cxg + rx))
    y0, y1 = max(0, int(cyg - ry)), min(H, int(cyg + ry))
    if (x1 - x0) < 6 or (y1 - y0) < 6:
        return float(W * 0.5), float(H * 0.5)

    roi = g[y0:y1, x0:x1].astype(np.float32).copy()

    # --- smooth & normalize locally ---
    roi = cv2.GaussianBlur(roi, (0, 0), 1.2)
    m, M = float(roi.min()), float(roi.max())
    if M > m:
        roi_n = (roi - m) / (M - m + 1e-12)
    else:
        return float(W * 0.5), float(H * 0.5)

    # --- coarse BRIGHT peak (DC) ---
    _, _, _, max_loc = cv2.minMaxLoc(roi_n)  # (x, y) in ROI coords
    x_coarse, y_coarse = max_loc

    # --- sub-pixel refinement via weighted centroid in 5×5 patch ---
    x_c = int(np.clip(x_coarse, 2, roi_n.shape[1] - 3))
    y_c = int(np.clip(y_coarse, 2, roi_n.shape[0] - 3))
    patch = roi_n[y_c - 2:y_c + 3, x_c - 2:x_c + 3].copy()

    # weights: brighten the peak and square to sharpen
    patch_w = np.clip(patch - patch.min(), 0.0, None)
    patch_w **= 2.0
    s = float(patch_w.sum())

    if s > 1e-12:
        py, px = np.mgrid[-2:3, -2:3]
        dx = float((patch_w * px).sum() / s)
        dy = float((patch_w * py).sum() / s)
    else:
        dx = dy = 0.0

    x_sub = x_c + dx
    y_sub = y_c + dy

    # --- map back to full image and clamp ---
    dcx = float(np.clip(x0 + x_sub, 0, W - 1))
    dcy = float(np.clip(y0 + y_sub, 0, H - 1))

    dcx = W * 0.5
    dcy = H * 0.5
    return dcx, dcy

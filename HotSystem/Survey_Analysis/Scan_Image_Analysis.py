import numpy as np
import matplotlib.pyplot as plt
import cv2
import warnings
from scipy.ndimage import gaussian_filter
from Utils.Common import loadFromCSV
from matplotlib import patches


class ScanImageAnalysis:
    """Process and inspect 2‑D fluorescence‑scan CSV data.

    *All* numerical work lives in methods prefixed with **compute_…** that return
    NumPy objects (and optionally cache them).  *All* visualisation lives in
    methods prefixed with **plot_…**; they never mutate state or perform any
    calculations heavier than formatting.
    """

    # ---------------------------------------------------------------------
    # I/O & basic structure helpers
    # ---------------------------------------------------------------------
    def __init__(self):
        self.image = None           # raw (x, y, intensity) triplets                    (N×3)
        self._grid = None           # intensity grid                                   (Ny×Nx)
        self._xu = self._yu = None  # unique x / y coordinate vectors                  (Nx, Ny)
        # caches for derived data --------------------------------------------------
        self._hp_grid = None        # high‑pass filtered grid
        self._bp_grid = None        # band‑pass filtered grid

    # .....................................................................
    def load_image(self, path: str, scale: float = 1e6):
        """Read CSV, build regular grid, return x, y, intensity arrays."""
        data = np.asarray(loadFromCSV(path))
        x = data[:, 4].astype(float) / scale
        y = data[:, 5].astype(float) / scale
        intensity = data[:, 3]
        self.image = np.column_stack((x, y, intensity)).astype(float)
        self._build_grid()
        # invalidate caches ------------------------------------------------
        self._hp_grid = None
        self._bp_grid = None
        return x, y, intensity

    # .....................................................................
    def _build_grid(self):
        """Convert scattered triplets → dense matrix with NaNs for gaps."""
        if self.image is None:
            raise ValueError("No image loaded – call load_image() first.")
        x, y, z = self.image.T
        self._xu, self._yu = np.unique(x), np.unique(y)
        grid = np.full((self._yu.size, self._xu.size), np.nan, dtype=float)
        xi = {v: i for i, v in enumerate(self._xu)}
        yi = {v: i for i, v in enumerate(self._yu)}
        for xx, yy, zz in zip(x, y, z):
            grid[yi[yy], xi[xx]] = zz
        self._grid = grid

    # ---------------------------------------------------------------------
    # Numerical operations (compute_*)
    # ---------------------------------------------------------------------
    def compute_highpass(self, sigma: float = 3.0, rescale_0_1: bool = False):
        """Gaussian high‑pass; cache result in `_hp_grid`."""
        if self._grid is None:
            raise ValueError("Load image first.")
        low = gaussian_filter(self._grid, sigma=sigma, mode="nearest")
        hp = self._grid - low
        if rescale_0_1:
            vmin, vmax = np.nanmin(hp), np.nanmax(hp)
            hp = (hp - vmin) / (vmax - vmin) if vmax > vmin else hp
        self._hp_grid = hp
        return hp

    # .....................................................................
    def compute_bandpass(self, pct_low: float = 0.05, pct_high: float = 0.95):
        """Band‑pass filter in the Fourier domain; cache in `_bp_grid`."""
        if self._grid is None:
            raise ValueError("Load image first.")
        if not (0.0 < pct_low < pct_high < 1.0):
            raise ValueError("Percentiles must satisfy 0 < low < high < 1.")

        grid = self._grid
        mask_nan = np.isnan(grid)
        filled = grid.copy()
        filled[mask_nan] = np.nanmean(filled)

        F = np.fft.fftshift(np.fft.fft2(filled))
        power = np.abs(F) ** 2
        ny, nx = grid.shape
        cy, cx = (ny - 1) / 2.0, (nx - 1) / 2.0
        yy, xx = np.indices(grid.shape)
        radius = np.hypot(yy - cy, xx - cx)
        flat_r, flat_p = radius.ravel(), power.ravel()
        idx = np.argsort(flat_r)
        cum_pow = np.cumsum(flat_p[idx])
        cum_pow /= cum_pow[-1]
        r_low = flat_r[idx][np.searchsorted(cum_pow, pct_low)]
        r_high = flat_r[idx][np.searchsorted(cum_pow, pct_high)]
        mask = (radius >= r_low) & (radius <= r_high)
        F[~mask] = 0.0
        bp = np.real(np.fft.ifft2(np.fft.ifftshift(F)))
        bp[mask_nan] = np.nan
        self._bp_grid = bp
        return bp

    # .....................................................................
    def compute_canny_edges(self, low: float = 12, high: float = 25, clim_max: float = 15):
        """Canny edge detector on the clipped intensity grid."""
        if self._grid is None:
            raise ValueError("Load image first.")
        img = self._grid.copy()
        img[img > clim_max] = clim_max
        edges = cv2.Canny(np.uint8(img), low, high, apertureSize=3, L2gradient=False)
        return edges

    def compute_pillar_mask(self, im, clim_max: float = 70.0, thresh_frac: float = 0.21):
        """Binary mask of pixels above `thresh_frac * clim_max`."""
        # img = self._grid.copy()
        img = im.copy()
        img[img > clim_max] = clim_max
        filled = np.where(np.isnan(img), 0.0, img)
        return (filled > thresh_frac * clim_max).astype(np.uint8)

    def compute_pillar_contours(self, im, clim_max: float = 70.0, thresh_frac: float = 0.21):
        """Return list of external contours for bright pillars."""
        mask = self.compute_pillar_mask(im, clim_max, thresh_frac)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        return contours

    # .....................................................................
    def compute_circle_fit(self, contours, min_dist: float = 16.0):
        """
        Fit min-enclosing circles to *contours*, then remove overlapping circles:
        if two centres are closer than `min_dist`, keep the one with higher grid intensity.
        """
        if self._grid is None:
            raise ValueError("Load image first.")
        # candidate list: (intensity, x, y, radius)
        cands = []
        for cnt in contours:
            pts = cnt.squeeze()
            if pts.ndim!=2:
                continue
            (x_c,y_c),r = cv2.minEnclosingCircle(pts.astype(np.float32))
            ix, iy = int(round(x_c)), int(round(y_c))
            if 0<=iy<self._grid.shape[0] and 0<=ix<self._grid.shape[1]:
                inten = self._grid[iy,ix]
                cands.append((float(inten), x_c, y_c, float(r)))
        # build keep mask
        n = len(cands)
        keep = [True]*n
        for i in range(n):
            for j in range(i+1, n):
                if keep[i] and keep[j]:
                    xi, yi = cands[i][1], cands[i][2]
                    xj, yj = cands[j][1], cands[j][2]
                    if np.hypot(xi-xj, yi-yj) < min_dist:
                        # drop lower-intensity
                        if cands[i][0] >= cands[j][0]:
                            keep[j] = False
                        else:
                            keep[i] = False
        centres, radii = [], []
        for k in range(n):
            if keep[k]:
                _, x_c, y_c, r = cands[k]
                centres.append((x_c, y_c))
                radii.append(r)
        return centres, radii

    # .....................................................................
    def compute_background(self, n: int = 1, agg: str = "mean"):
        """Return background estimate from *n×n* corner patches."""
        if self._grid is None:
            raise ValueError("Load image first.")
        reducer = np.nanmean if agg == "mean" else np.nanmedian
        ny, nx = self._grid.shape
        ul = self._grid[ny - n: ny, 0: n]
        br = self._grid[0: n, nx - n: nx]
        return reducer(ul), reducer(br)

    def compute_hough_circles(self,
                               img: np.ndarray | None = None,
                               dp: float = 1.2,
                               min_dist: float = 1,
                               param1: float = 50,
                               param2: float = 30,
                               min_radius: int = 1,
                               max_radius: int = 100,
                               clim_max: float = 70.0):
        """Detect circles via Hough gradient directly on a grayscale image.

        If `img` is None, uses the clipped intensity grid (`self._grid`).
        Returns list of (x_center, y_center, radius) in pixel coords."""
        # prepare input image
        if img is None:
            if self._grid is None:
                raise ValueError("Load image first or provide `img`.")
            # clip and normalize to 0–255
            tmp = self._grid.copy()
            tmp[tmp > clim_max] = clim_max
            norm = 255.0 / clim_max
            img_u8 = np.uint8(np.nan_to_num(tmp) * norm)
        else:
            # assume user gave a uint8 or grayscale array
            img_u8 = np.uint8(img)

        # optional pre-blur helps Hough detection
        img_blur = cv2.GaussianBlur(img_u8, (9, 9), sigmaX=2)
        circles = cv2.HoughCircles(img_blur,
                                   cv2.HOUGH_GRADIENT,
                                   dp,
                                   min_dist,
                                   param1=param1,
                                   param2=param2,
                                   minRadius=min_radius,
                                   maxRadius=max_radius)
        if circles is None:
            return []
        circles = np.round(circles[0]).astype(int)
        return [(int(x), int(y), int(r)) for x, y, r in circles]

    @staticmethod
    def _prep_ax(ax=None):
        if ax is None:
            fig, ax = plt.subplots()
        else:
            fig = ax.figure
        return fig, ax

    # .....................................................................
    def plot_image(self, img, *, ax=None, cmap="rainbow", clim=(0, 70), cbar_label="Intensity"):
        """Generic imshow wrapper."""
        fig, ax = self._prep_ax(ax)
        im = ax.imshow(img, origin="lower", cmap=cmap, aspect="auto")
        im.set_clim(*clim)
        ax.axis("off")
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=cbar_label)
        fig.tight_layout()
        return ax

    # .....................................................................
    def plot_contours(self, contours, *, ax=None, outline_color="white", outline_width=1.0):
        """Overlay raw contour paths."""
        if not contours:
            warnings.warn("No contours to display.")
            return ax
        fig, ax = self._prep_ax(ax)
        for cnt in contours:
            pts = cnt.squeeze()
            if pts.ndim == 2:
                ax.plot(pts[:, 0], pts[:, 1], color=outline_color, linewidth=outline_width)
        return ax

    # .....................................................................
    def plot_circles(self, centres, radii, *, ax=None, outline_color="white", outline_width=1.0, fixed_radius=None):
        """Overlay circles – *fixed_radius* can be scalar or 'median'."""
        if not centres:
            warnings.warn("No circles to display.")
            return ax
        fig, ax = self._prep_ax(ax)
        if fixed_radius == "median":
            fixed_radius = float(np.median(radii))
        for (x_c, y_c), r in zip(centres, radii):
            rr = fixed_radius if fixed_radius is not None else r
            circ = patches.Circle((x_c, y_c), rr, fill=False, edgecolor=outline_color, linewidth=outline_width)
            ax.add_patch(circ)
        return ax

    def plot_hough_circles(self, circles, *, ax=None,
                           outline_color: str = "white",
                           outline_width: float = 1.0):
        """Overlay Hough-detected circles (x,y,r triplets)."""
        fig, ax = self._prep_ax(ax)
        for x, y, r in circles:
            circ = patches.Circle((x, y), r,
                                  fill=False,
                                  edgecolor=outline_color,
                                  linewidth=outline_width)
            ax.add_patch(circ)
        ax.axis("off")
        return ax

    def show_pillars(self, *, clim_max=70.0, thresh_frac=0.21, cmap="rainbow", circle_mode="median"):
        """Quick one‑liner: show clipped image + fitted pillar circles."""
        contours = self.compute_pillar_contours(self._grid, clim_max, thresh_frac)
        centres, radii = self.compute_circle_fit(contours)
        ax = self.plot_image(self._grid.copy(), cmap=cmap, clim=(0, clim_max))
        self.plot_circles(centres, radii, ax=ax, fixed_radius=circle_mode)
        plt.show()

# image = ScanImageAnalysis()
# path = "C:\\users\\Daniel\\Work Folders\\Documents\\2025_5_6_4_2_49_SCAN_Pillar4.5_array4.csv"
# image.load_image(path)
# image._grid[image._grid > 70] = 70
# # ax = image.plot_image(image._grid, clim=(0,70))
# # circles = image.compute_hough_circles()
# # image.plot_hough_circles(circles, ax=ax)
# # plt.show()
#
# contours = image.compute_pillar_contours(im = image._grid, clim_max=70.0, thresh_frac=0.21)
# # ax = image.plot_image(image._grid, clim=(0, 70), cmap="rainbow")  # background
# # image.plot_contours(contours, ax=ax, outline_color="white", outline_width=1.2)
#
# # image.plot_contours(contours)
# # centres, radii = image.compute_circle_fit(contours)
# image.show_pillars()
# plt.show()

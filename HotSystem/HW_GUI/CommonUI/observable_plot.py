from __future__ import annotations

import logging
import os.path
import threading
import time
from pathlib import Path
from typing import Optional, Callable, Dict, List, Sequence, Any, Final
import dearpygui.dearpygui as dpg
import numpy as np

from Utils import ObservableField, open_file_dialog

_logger: Final = logging.getLogger(__name__)

class LiveObservablePlot:
    """A self-contained live plot driven by an `ObservableField[float]`."""

    def __init__(
        self,
        observable: ObservableField[Any],
        *,
        title: str = "Live Plot",
        parent: Optional[str] = None,
        transform: Optional[Callable[[float, float], float]] = None,
        units: Optional[Dict[str, float]] = None,
        max_points: Optional[int] = None,
        width: int = -1,
        height: int = 350,
        axis_bounds: Optional[List[List[float]]] = None,
    ) -> None:
        self.axis_bounds: Optional[List[List[float]]] = axis_bounds
        self._lock: threading.Lock = threading.Lock()
        if units is None:
            units = {"raw": 1.0}
        if not units:
            raise ValueError("`units` cannot be empty")

        self._observable = observable
        self._transform = transform
        self._units = units
        self._max = max_points

        # Data buffers
        self._start = time.time()
        self._base: float | None = None
        self._ts: List[float] = []
        self._ys: List[float] = []
        self._series: dict[str, str] = {}  # label -> dpg series tag
        self._bufs: dict[str, list[list[float]]] = {}  # label -> [ts[], ys[]]

        # Unique tag prefix
        pref = f"plot_{id(self):x}"
        self._unit_combo = f"{pref}_unit"
        self._series_tag = f"{pref}_series"
        self._plot_tag = f"{pref}_plot"
        self._x_axis = f"{pref}_x"
        self._y_axis = f"{pref}_y"


        # Build UI
        self._build_ui(title, parent, width, height)

        # Attach observer last (UI exists now)
        self._observable.add_observer(self._on_sample)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_ui(self, title: str, parent: Optional[str], w: int, h: int) -> None:
        container = dpg.window(label=title) if parent is None else dpg.group(parent=parent)
        with container:
            if len(self._units) > 1:
                dpg.add_combo(
                    items=list(self._units),
                    default_value=list(self._units)[0],
                    label="Units",
                    tag=self._unit_combo,
                    width=120,
                )
            # self._base_lbl = dpg.add_text("Base: –", bullet=True)
            with dpg.plot(label=title, width=w, height=h, tag=self._plot_tag):
                dpg.add_plot_legend()
                dpg.add_plot_axis(dpg.mvXAxis, label="t [s]", tag=self._x_axis, lock_min=False, lock_max = False)
                dpg.add_plot_axis(dpg.mvYAxis, label=list(self._units)[0], tag=self._y_axis, lock_min=False, lock_max = False)

                if self.axis_bounds:
                    dpg.set_axis_limits(self._x_axis, self.axis_bounds[0][0], self.axis_bounds[0][1])
                    dpg.set_axis_limits(self._y_axis,self.axis_bounds[1][0],self.axis_bounds[1][1])

            dpg.add_button(label="Save CSV", callback=self._save_csv, width=120)

    # --- helper -----------------------------------------------------------
    def _update_line(self, label: str, xs: list[float], ys: list[float]) -> None:
        """Create or update a DPG line series for *label*."""
        if label not in self._series:
            tag = f"{label}_{id(self):x}"
            dpg.add_line_series(xs, ys, label=label, parent=self._y_axis, tag=tag)
            self._series[label] = tag
            self._bufs[label] = [xs, ys]
        else:
            self._bufs[label][0][:] = xs
            self._bufs[label][1][:] = ys
            dpg.set_value(self._series[label], self._bufs[label])

    def set_x_axis_units(self, x_units):
        dpg.configure_item(item=self._x_axis, label = x_units)
    def set_axis_bounds(self,bounds):
        self.axis_bounds = bounds
    # ------------------------------------------------------------------
    # Graph Reset
    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Clear history and reset base-frequency (call from GUI button)."""
        self._start = time.time()
        self._ts.clear()
        self._ys.clear()
        for lbl, tag in self._series.items():
            if dpg.does_item_exist(tag):
                dpg.set_value(tag, [[], []])
            self._bufs[lbl] = [[], []]
            self._update_line(lbl, [], [])


        # wipe graph & labels
        if dpg.does_item_exist(self._series_tag):
            dpg.set_value(self._series_tag, [[], []])
        # dpg.set_value(self._base_lbl, "Base: –")
        _logger.info("Graph was reset successfully")

    # ------------------------------------------------------------------
    # Observable callback
    # ------------------------------------------------------------------

    def _on_sample(self, raw_value) -> None:  # type: ignore[override]
        """
        Callback registered with ``ObservableField.add_observer``.

        Parameters
        ----------
        raw_value :
            • *float*  → scalar update (accumulate – original behaviour)
            • 1-D *Sequence/ndarray*  → vector update (replace view entirely)
              If the sequence has length 2 and the first element is itself a
              sequence, it is interpreted as ``(x, y)`` data.
        """
        if isinstance(raw_value, dict):  # multi-line payload
            payload = raw_value  # type: dict[str, Any]
        else:  # single-line → wrap in dict
            payload = {"default": raw_value}
        # -----------------------------------------------------------------
        # Resolve unit scale
        # -----------------------------------------------------------------
        unit_name = dpg.get_value(self._unit_combo) or list(self._units)[0] or "raw"
        scale = self._units.get(unit_name,1.0)

        # -----------------------------------------------------------------
        # Decide whether we got a vector or a scalar
        # -----------------------------------------------------------------
        def _is_vector(val) -> bool:
            """True for 1-D array / list / tuple with >1 element."""
            if isinstance(val, np.ndarray):
                return val.ndim == 1 and val.size > 1
            return (
                    isinstance(val, Sequence)
                    and not isinstance(val, (str, bytes, np.generic))
                    and len(val) > 1
            )


        # ---------------------------------------------------------------
        # Vector-mode  ➜  REPLACE data
        # ---------------------------------------------------------------
        for label, val in payload.items():
            vector_update = _is_vector(val)
            if vector_update:
                # Accept (y,)   or   (x, y) pairs
                if len(val) == 2 and isinstance(val[0], Sequence):
                    x_vals, y_vals = val  # type: ignore[misc]
                else:
                    y_vals = val  # type: ignore[assignment]
                    # Generate a synthetic x-axis [0 … N-1] · dt
                    dt = 1.0 / max(len(y_vals) - 1, 1)
                    x_vals = np.linspace(0, dt * (len(y_vals) - 1), len(y_vals))

                # Apply scaling / transform
                if self._transform:
                    y_vals = [self._transform(v * scale, self._base) for v in y_vals]
                else:
                    y_vals = [v * scale for v in y_vals]

                # Replace internal buffers (keep max size constraint)
                with self._lock:
                    self._ts = list(x_vals)[-self._max:] if self._max else list(x_vals)
                    self._ys = list(y_vals)[-self._max:] if self._max else list(y_vals)
                self._update_line(label, x_vals, y_vals)
            else: # Scalar-mode
                raw_val = float(val)
                y_val = (
                    self._transform(raw_val * scale, self._base)
                    if self._transform
                    else raw_val * scale
                )

                # Rolling buffer
                if self._max and len(self._ts) >= self._max:
                    self._ts.pop(0)
                    self._ys.pop(0)

                self._ts.append(time.time() - self._start)
                self._ys.append(y_val)
                self._update_line(label, self._ts, self._ys)



        # ---------------------------------------------------------------
        # Refresh plot
        # ---------------------------------------------------------------
        dpg.configure_item(self._y_axis, label=unit_name)
        if self.axis_bounds:
            dpg.set_axis_limits_auto(self._x_axis)
            dpg.set_axis_limits_auto(self._y_axis)
        else:
            dpg.fit_axis_data(self._x_axis)
            dpg.fit_axis_data(self._y_axis)



    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def _save_csv(self) -> None:
        """
        Export the current plot data to *<tag>.csv*.

        • **Scalar mode** – two-column file: ``t_s,value``
        • **Vector / multi-series mode** – one ``<label>_x,<label>_y`` column
          pair per series; shorter series are left blank-padded so all rows
          have equal length.
        """
        # Take an atomic snapshot to avoid races with the GUI thread
        with self._lock:
            buf = {lbl: (xs.copy(), ys.copy()) for lbl, (xs, ys) in self._bufs.items()}
            ts  = self._ts.copy()
            ys  = self._ys.copy()

        out_path = open_file_dialog(Path.cwd().as_posix(),title= "CSV export", select_folder=True)
        out_path = os.path.join(out_path, f"{self._series_tag}.csv")

        # ── Scalar ───────────────────────────────────────────────────────
        if not buf or all(len(xs) <= 1 for xs, _ in buf.values()):
            if not ts:
                _logger.info(f"CSV file Not saved because there is no data to export.")
                return  # nothing to write
            with open(out_path,"w", encoding="utf-8", newline="") as fh:
                fh.write("t_s,value\n")
                for t, v in zip(ts, ys, strict=False):
                    fh.write(f"{t:.6f},{v:.9f}\n")
            _logger.info(f"CSV file saves successfully to {out_path}")
            return

        # ── Vector / multi-series ───────────────────────────────────────
        with open(out_path,"w", encoding="utf-8", newline="") as fh:
            # header: <label>_x,<label>_y for every active series
            cols: list[str] = []
            for lbl in buf:
                cols.extend((f"{lbl}_x", f"{lbl}_y"))
            fh.write(",".join(cols) + "\n")

            # write rows (pad blanks where a series is shorter)
            max_len = max(len(xs) for xs, _ in buf.values())
            for i in range(max_len):
                row: list[str] = []
                for xs, ys_ in buf.values():
                    if i < len(xs):
                        row.append(f"{xs[i]:.6f}")
                        row.append(f"{ys_[i]:.9f}")
                    else:
                        row.extend(("", ""))         # keep column count
                fh.write(",".join(row) + "\n")
        _logger.info(f"CSV file saves successfully to {out_path}")

    # ------------------------------------------------------------------
    # Detach (optional)
    # ------------------------------------------------------------------
    def detach(self) -> None:
        """Stop receiving updates (call if you destroy the GUI manually)."""
        # noinspection PyBroadException
        try:
            self._observable.remove_observer(self._on_sample)
        except Exception:
            pass
        _logger.info(f"{self} : Graph was detached successfully")


    def __del__(self) -> None:  # noqa: D401
        self.detach()
"""
core/perf_monitor.py — Monitor ligero de rendimiento para diagnóstico y benchmarking de pyDCE.

Se activa estableciendo la variable de entorno PYDCE_PERF=1 o mediante PerfMonitor.instance().set_enabled(True).
Cuando esta desactivado, el impacto en rendimiento es nulo (una comprobacion booleana simple).
"""
import os
import time
from collections import deque


class PerfMonitor:
    """Recolector ligero de metricas de renderizado, entrada y UI."""

    _instance = None

    def __init__(self):
        self.enabled = os.environ.get("PYDCE_PERF", "").strip().lower() in ("1", "true", "yes", "on")
        self._window = 240
        self.reset()

    @classmethod
    def instance(cls) -> "PerfMonitor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def set_enabled(self, enabled: bool):
        self.enabled = bool(enabled)

    def reset(self):
        self.render_times_ms = deque(maxlen=self._window)
        self.mouse_move_times_ms = deque(maxlen=self._window)
        self.thumbnail_times_ms = deque(maxlen=self._window)
        self.paint_count = 0
        self.mouse_move_count = 0
        self.thumbnail_calls = 0
        self.full_composites = 0
        self.partial_composites = 0
        self._last_report_ts = time.perf_counter()
        self._paints_since_report = 0

    def record_render(self, elapsed_ms: float):
        if not self.enabled:
            return
        self.render_times_ms.append(elapsed_ms)
        self.paint_count += 1
        self._paints_since_report += 1
        self._maybe_log_periodic()

    def record_mouse_move(self, elapsed_ms: float):
        if not self.enabled:
            return
        self.mouse_move_times_ms.append(elapsed_ms)
        self.mouse_move_count += 1

    def record_thumbnail_update(self, elapsed_ms: float):
        if not self.enabled:
            return
        self.thumbnail_times_ms.append(elapsed_ms)
        self.thumbnail_calls += 1

    def record_composite(self, partial: bool = False):
        if not self.enabled:
            return
        if partial:
            self.partial_composites += 1
        else:
            self.full_composites += 1

    def get_summary(self) -> dict:
        def _stats(samples):
            if not samples:
                return {"count": 0, "avg_ms": 0.0, "p95_ms": 0.0, "max_ms": 0.0, "total_ms": 0.0}
            s = sorted(samples)
            n = len(s)
            p95_idx = min(n - 1, int(n * 0.95))
            return {
                "count": n,
                "avg_ms": sum(s) / n,
                "p95_ms": s[p95_idx],
                "max_ms": s[-1],
                "total_ms": sum(s),
            }

        return {
            "paint_count": self.paint_count,
            "render": _stats(self.render_times_ms),
            "mouse_move_count": self.mouse_move_count,
            "mouse_move": _stats(self.mouse_move_times_ms),
            "thumbnail_calls": self.thumbnail_calls,
            "thumbnails": _stats(self.thumbnail_times_ms),
            "full_composites": self.full_composites,
            "partial_composites": self.partial_composites,
        }

    def _maybe_log_periodic(self):
        if os.environ.get("PYDCE_PERF", "").strip().lower() not in ("1", "true", "yes", "on"):
            return
        now = time.perf_counter()
        dt = now - self._last_report_ts
        if dt >= 2.0 and self._paints_since_report > 0:
            fps = self._paints_since_report / dt
            summary = self.get_summary()
            r = summary["render"]
            print(
                f"[PYDCE_PERF] paint_fps={fps:.1f} render_avg={r['avg_ms']:.2f}ms "
                f"render_p95={r['p95_ms']:.2f}ms thumbs={self.thumbnail_calls} "
                f"comp_full={self.full_composites} comp_partial={self.partial_composites}"
            )
            self._last_report_ts = now
            self._paints_since_report = 0


perf_monitor = PerfMonitor.instance()

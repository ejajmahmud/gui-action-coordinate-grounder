"""Multi-monitor DPI, taskbar-inset, and scroll-aware coordinate grounder."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Insets:
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0

    def __post_init__(self) -> None:
        if min(self.top, self.right, self.bottom, self.left) < 0:
            raise ValueError("Insets must be non-negative")


@dataclass
class DisplayMonitor:
    monitor_id: str
    logical_x: int
    logical_y: int
    physical_width: int
    physical_height: int
    dpi_scale: float = 1.0
    insets: Insets = field(default_factory=Insets)
    is_primary: bool = False

    def __post_init__(self) -> None:
        if not self.monitor_id:
            raise ValueError("monitor_id is required")
        if self.physical_width <= 0 or self.physical_height <= 0:
            raise ValueError("Display physical dimensions must be positive")
        if self.dpi_scale <= 0:
            raise ValueError("dpi_scale must be positive")

    @property
    def logical_width(self) -> int:
        return int(round(self.physical_width / self.dpi_scale))

    @property
    def logical_height(self) -> int:
        return int(round(self.physical_height / self.dpi_scale))


@dataclass
class ViewportContext:
    scroll_x: float = 0.0
    scroll_y: float = 0.0
    zoom_factor: float = 1.0
    crop_box: Optional[Tuple[int, int, int, int]] = None  # physical (x, y, w, h) relative to monitor

    def __post_init__(self) -> None:
        if self.zoom_factor <= 0:
            raise ValueError("zoom_factor must be positive")
        if self.crop_box is not None and (self.crop_box[2] <= 0 or self.crop_box[3] <= 0):
            raise ValueError("crop_box width and height must be positive")


@dataclass
class GroundedPoint:
    monitor_id: str
    physical_x: int
    physical_y: int
    logical_x: int
    logical_y: int
    document_x: float
    document_y: float
    clamped: bool


@dataclass
class DragPlan:
    start: GroundedPoint
    end: GroundedPoint
    delta_logical_x: int
    delta_logical_y: int


class CoordinateGrounder:
    """Translates [0..norm_max] VLM coordinates to OS physical/logical and document spaces."""

    def __init__(self, monitors: List[DisplayMonitor], norm_max: float = 1000.0) -> None:
        if not monitors:
            raise ValueError("At least one monitor is required")
        if norm_max <= 0:
            raise ValueError("norm_max must be positive")
        self.norm_max = norm_max
        self._monitors: Dict[str, DisplayMonitor] = {m.monitor_id: m for m in monitors}
        self._default_id = next((m.monitor_id for m in monitors if m.is_primary), monitors[0].monitor_id)

    def _get_monitor(self, monitor_id: Optional[str]) -> DisplayMonitor:
        mid = monitor_id or self._default_id
        if mid not in self._monitors:
            raise KeyError(f"Unknown monitor_id: {mid}")
        return self._monitors[mid]

    def ground_point(
        self,
        norm_x: float,
        norm_y: float,
        monitor_id: Optional[str] = None,
        viewport: Optional[ViewportContext] = None,
        avoid_insets: bool = True,
        strict_bounds: bool = True,
    ) -> GroundedPoint:
        if strict_bounds and not (0.0 <= norm_x <= self.norm_max and 0.0 <= norm_y <= self.norm_max):
            raise ValueError(f"Normalized coordinate ({norm_x}, {norm_y}) outside [0, {self.norm_max}]")
        mon = self._get_monitor(monitor_id)
        vp = viewport or ViewportContext()

        nx = min(max(norm_x, 0.0), self.norm_max) / self.norm_max
        ny = min(max(norm_y, 0.0), self.norm_max) / self.norm_max

        if vp.crop_box is not None:
            cx, cy, cw, ch = vp.crop_box
            local_px_x = cx + nx * (cw - 1)
            local_px_y = cy + ny * (ch - 1)
        else:
            local_px_x = nx * (mon.physical_width - 1)
            local_px_y = ny * (mon.physical_height - 1)

        min_x = mon.insets.left if avoid_insets else 0
        max_x = max(min_x, mon.physical_width - 1 - (mon.insets.right if avoid_insets else 0))
        min_y = mon.insets.top if avoid_insets else 0
        max_y = max(min_y, mon.physical_height - 1 - (mon.insets.bottom if avoid_insets else 0))

        rx = int(round(local_px_x))
        ry = int(round(local_px_y))
        clamped_x = min(max(rx, min_x), max_x)
        clamped_y = min(max(ry, min_y), max_y)
        was_clamped = (clamped_x != rx) or (clamped_y != ry)

        logical_x = mon.logical_x + int(round(clamped_x / mon.dpi_scale))
        logical_y = mon.logical_y + int(round(clamped_y / mon.dpi_scale))

        doc_x = vp.scroll_x + (clamped_x / mon.dpi_scale) / vp.zoom_factor
        doc_y = vp.scroll_y + (clamped_y / mon.dpi_scale) / vp.zoom_factor

        return GroundedPoint(
            monitor_id=mon.monitor_id,
            physical_x=clamped_x,
            physical_y=clamped_y,
            logical_x=logical_x,
            logical_y=logical_y,
            document_x=round(doc_x, 2),
            document_y=round(doc_y, 2),
            clamped=was_clamped,
        )

    def ground_drag(
        self,
        start_norm: Tuple[float, float],
        end_norm: Tuple[float, float],
        monitor_id: Optional[str] = None,
        viewport: Optional[ViewportContext] = None,
    ) -> DragPlan:
        start = self.ground_point(start_norm[0], start_norm[1], monitor_id=monitor_id, viewport=viewport)
        end = self.ground_point(end_norm[0], end_norm[1], monitor_id=monitor_id, viewport=viewport)
        return DragPlan(
            start=start,
            end=end,
            delta_logical_x=end.logical_x - start.logical_x,
            delta_logical_y=end.logical_y - start.logical_y,
        )

    def normalize_logical(self, logical_x: int, logical_y: int, monitor_id: Optional[str] = None) -> Tuple[float, float]:
        mon = self._get_monitor(monitor_id)
        local_px_x = (logical_x - mon.logical_x) * mon.dpi_scale
        local_px_y = (logical_y - mon.logical_y) * mon.dpi_scale
        nx = (local_px_x / max(mon.physical_width - 1, 1)) * self.norm_max
        ny = (local_px_y / max(mon.physical_height - 1, 1)) * self.norm_max
        return round(min(max(nx, 0.0), self.norm_max), 2), round(min(max(ny, 0.0), self.norm_max), 2)

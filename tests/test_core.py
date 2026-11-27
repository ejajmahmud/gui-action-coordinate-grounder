"""Unit tests for GUI Action Coordinate Grounder."""
import unittest
from gui_action_coordinate_grounder.core import (
    CoordinateGrounder,
    DisplayMonitor,
    Insets,
    ViewportContext,
)


class TestCoordinateGrounder(unittest.TestCase):
    def setUp(self):
        self.grounder = CoordinateGrounder([
            DisplayMonitor("main", 0, 0, 3840, 2160, dpi_scale=2.0, insets=Insets(bottom=100), is_primary=True),
            DisplayMonitor("right", 1920, 0, 1920, 1080, dpi_scale=1.0),
        ])

    def test_hidpi_secondary_monitor_and_roundtrip(self):
        pt = self.grounder.ground_point(500, 500, monitor_id="right")
        self.assertEqual(pt.logical_x, 1920 + 960)
        self.assertEqual(pt.logical_y, 540)
        nx, ny = self.grounder.normalize_logical(pt.logical_x, pt.logical_y, monitor_id="right")
        self.assertAlmostEqual(nx, 500.0, delta=1.5)
        self.assertAlmostEqual(ny, 500.0, delta=1.5)

    def test_taskbar_inset_clamping(self):
        pt = self.grounder.ground_point(500, 998, monitor_id="main", avoid_insets=True)
        self.assertTrue(pt.clamped)
        self.assertEqual(pt.physical_y, 2160 - 1 - 100)
        self.assertEqual(pt.logical_y, 1030)

    def test_crop_box_scroll_and_drag(self):
        vp = ViewportContext(scroll_x=100.0, scroll_y=400.0, zoom_factor=2.0, crop_box=(200, 200, 1000, 800))
        drag = self.grounder.ground_drag((0, 0), (1000, 1000), monitor_id="main", viewport=vp)
        self.assertEqual(drag.start.physical_x, 200)
        self.assertEqual(drag.end.physical_x, 1199)
        self.assertGreater(drag.delta_logical_x, 450)
        self.assertEqual(drag.start.document_y, 450.0)

    def test_error_paths(self):
        with self.assertRaises(ValueError):
            self.grounder.ground_point(1200, 500, strict_bounds=True)
        with self.assertRaises(KeyError):
            self.grounder.ground_point(500, 500, monitor_id="missing")
        with self.assertRaises(ValueError):
            DisplayMonitor("bad", 0, 0, 1920, 1080, dpi_scale=0.0)

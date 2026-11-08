"""
Workstation GUI and Interactive Canvas test suite.
"""

import os
import unittest
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPainter

from gui.main_window import MainWindow
from gui.preview_canvas import BootPreviewCanvas, ThemeState
from gui.widgets import DragDropZone, TelemetryBadge, CollapsibleSection, ColorPickerButton
from backend.theme_engine import PRESETS

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestWorkstationGUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_main_window_init(self):
        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertIn("GRUB Forge", window.windowTitle())
        self.assertIsNotNone(window.canvas)
        self.assertIsNotNone(window.drawer)
        self.assertIsNotNone(window.inspector_panel)
        self.assertIsNotNone(window.top_bar)
        window.close()

    def test_canvas_offscreen_render(self):
        canvas = BootPreviewCanvas(resolution=(1920, 1080))
        state = ThemeState(
            resolution=(1920, 1080),
            colors=PRESETS["cyber_glow"].colors,
            entries=["Arch Linux", "Debian GNU/Linux", "Windows 11"]
        )
        canvas.apply_state(state)
        canvas.resize(960, 540)

        # Render onto an off-screen QImage
        image = QImage(960, 540, QImage.Format.Format_ARGB32_Premultiplied)
        painter = QPainter(image)
        canvas.render(painter)
        painter.end()

        self.assertFalse(image.isNull())
        self.assertEqual(image.width(), 960)
        self.assertEqual(image.height(), 540)

    def test_widgets_instantiation(self):
        badge = TelemetryBadge("🐧", "Distro", "Arch Linux", "#a6e3a1")
        self.assertEqual(badge.val_lbl.text(), "Arch Linux")

        btn = ColorPickerButton("#89b4fa")
        self.assertEqual(btn.color_hex, "#89b4fa")
        btn.set_color("#a6e3a1")
        self.assertEqual(btn.color_hex, "#a6e3a1")

        zone = DragDropZone()
        self.assertTrue(zone.acceptDrops())

        section = CollapsibleSection("Test Section", starts_expanded=True)
        self.assertTrue(section._is_expanded)
        self.assertFalse(section.content_widget.isHidden())
        section.toggle()
        self.assertFalse(section._is_expanded)
        self.assertTrue(section.content_widget.isHidden())


if __name__ == "__main__":
    unittest.main()

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


    def test_kali_preset_selection(self):
        window = MainWindow()
        window._on_preset_selected("kali_dragon")
        self.assertEqual(window.theme_state.title_text, "Kali GNU/Linux (Rolling)")
        self.assertIsNotNone(window.theme_state.wallpaper_path)
        self.assertTrue(window.theme_state.wallpaper_path.is_file())
        self.assertIn("kali", str(window.theme_state.wallpaper_path).lower())
        self.assertEqual(window.theme_state.colors.title_color, "#00f5d4")
        window.close()

    def test_distro_icons_resolution(self):
        canvas = BootPreviewCanvas(resolution=(1920, 1080))
        self.assertIsNotNone(canvas.get_distro_icon("Kali GNU/Linux (linux 6.12)"))
        self.assertIsNotNone(canvas.get_distro_icon("Arch Linux default"))
        self.assertIsNotNone(canvas.get_distro_icon("Debian GNU/Linux 13"))
        self.assertIsNotNone(canvas.get_distro_icon("Fedora 41 Workstation"))
        self.assertIsNotNone(canvas.get_distro_icon("Ubuntu 24.04 LTS"))
        self.assertIsNotNone(canvas.get_distro_icon("Windows Boot Manager (/dev/nvme0n1p1)"))
        self.assertIsNotNone(canvas.get_distro_icon("UEFI Firmware Settings"))

    def test_studio_workspace_navigation(self):
        window = MainWindow()
        self.assertEqual(window.stacked_inspector.count(), 5)
        # Test switching pages
        window.stacked_inspector.setCurrentIndex(1)
        self.assertEqual(window.stacked_inspector.currentIndex(), 1)
        window.stacked_inspector.setCurrentIndex(2)
        self.assertEqual(window.stacked_inspector.currentIndex(), 2)
        window.close()


if __name__ == "__main__":
    unittest.main()

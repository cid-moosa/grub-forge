"""
GRUB Forge - Reusable Workstation Widgets
Custom components: DragDropZone, ColorPickerButton, TelemetryBadge,
CollapsibleSection, and PresetCards.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, List, Tuple
from PIL import Image

from PyQt6.QtCore import Qt, pyqtSignal, QSize, QRectF
from PyQt6.QtGui import (
    QColor, QPainter, QBrush, QPen, QFont, QDragEnterEvent,
    QDropEvent, QPixmap, QPainterPath, QCursor
)
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QColorDialog, QFrame, QFileDialog, QSizePolicy
)


class TelemetryBadge(QFrame):
    """
    Status chip displaying system state (Distro, UEFI/BIOS, /boot partition).
    """

    def __init__(
        self,
        icon_text: str,
        title: str,
        value: str,
        status_color: str = "#89b4fa",
        tooltip: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setToolTip(tooltip)
        self.setObjectName("telemetryChip")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 12, 4)
        layout.setSpacing(8)

        # Icon or symbol badge
        self.icon_lbl = QLabel(icon_text)
        self.icon_lbl.setStyleSheet(f"color: {status_color}; font-size: 13px; font-weight: bold;")
        layout.addWidget(self.icon_lbl)

        # Title (subtle)
        self.title_lbl = QLabel(f"{title}:")
        self.title_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 500;")
        layout.addWidget(self.title_lbl)

        # Value
        self.val_lbl = QLabel(value)
        self.val_lbl.setStyleSheet(
            f"color: #cdd6f4; font-size: 11px; font-weight: 700; font-family: 'JetBrains Mono', monospace;"
        )
        layout.addWidget(self.val_lbl)

        self.setStyleSheet(f"""
            QFrame#telemetryChip {{
                background-color: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 14px;
            }}
            QFrame#telemetryChip:hover {{
                border-color: {status_color};
            }}
        """)

    def set_value(self, val: str):
        self.val_lbl.setText(val)


class ColorPickerButton(QPushButton):
    """
    Workstation-style color picker button with live preview swatch.
    """
    colorChanged = pyqtSignal(str)

    def __init__(self, initial_hex: str = "#89b4fa", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color_hex = initial_hex
        self.setFixedHeight(28)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clicked.connect(self._choose_color)
        self._update_appearance()

    @property
    def color_hex(self) -> str:
        return self._color_hex

    def set_color(self, hex_val: str):
        if not hex_val.startswith("#"):
            hex_val = f"#{hex_val}"
        self._color_hex = hex_val
        self._update_appearance()
        self.colorChanged.emit(self._color_hex)

    def _update_appearance(self):
        col = QColor(self._color_hex)
        contrast_text = "#11111b" if col.lightness() > 140 else "#ffffff"
        self.setText(f"  {self._color_hex.upper()}  ")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color_hex};
                color: {contrast_text};
                border: 1px solid #45475a;
                border-radius: 6px;
                font-weight: 700;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 11px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                border: 1px solid #ffffff;
            }}
        """)

    def _choose_color(self):
        col = QColorDialog.getColor(QColor(self._color_hex), self, "Select Color")
        if col.isValid():
            self.set_color(col.name())


class DragDropZone(QFrame):
    """
    Interactive drag-and-drop wallpaper dropzone with file inspection metadata overlay.
    """
    fileDropped = pyqtSignal(Path)
    cleared = pyqtSignal()

    SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".tga"}

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(110)

        self._current_file: Optional[Path] = None
        self._is_drag_active = False

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(14, 12, 14, 12)
        self._layout.setSpacing(6)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_lbl = QLabel("📁")
        self.icon_lbl.setStyleSheet("font-size: 24px; color: #89b4fa;")
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.icon_lbl)

        self.prompt_lbl = QLabel("Drop background image here, or click to browse")
        self.prompt_lbl.setStyleSheet("color: #a6adc8; font-size: 12px; font-weight: 500;")
        self.prompt_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.prompt_lbl)

        self.meta_lbl = QLabel("Supports .png, .jpg, .tga")
        self.meta_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        self.meta_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.addWidget(self.meta_lbl)

        self._update_style()

    def _update_style(self):
        border_color = "#89b4fa" if self._is_drag_active else "#313244"
        bg_color = "#232338" if self._is_drag_active else "#181825"
        self.setStyleSheet(f"""
            DragDropZone {{
                background-color: {bg_color};
                border: 2px dashed {border_color};
                border-radius: 8px;
            }}
            DragDropZone:hover {{
                border-color: #89b4fa;
                background-color: #1e1e2e;
            }}
        """)

    def set_file(self, path: Optional[Path]):
        self._current_file = path
        if path and path.is_file():
            try:
                size_mb = path.stat().st_size / (1024 * 1024)
                with Image.open(path) as img:
                    w, h = img.size
                    fmt = img.format or path.suffix.lstrip(".").upper()
                self.icon_lbl.setText("🖼")
                self.prompt_lbl.setText(f"<b>{path.name}</b>")
                self.meta_lbl.setText(f"{w} × {h} px  •  {size_mb:.2f} MB  •  {fmt}")
                self.meta_lbl.setStyleSheet("color: #a6e3a1; font-size: 11px; font-weight: 600;")
            except Exception:
                self.prompt_lbl.setText(path.name)
                self.meta_lbl.setText("Valid image asset")
        else:
            self.icon_lbl.setText("📁")
            self.prompt_lbl.setText("Drop background image here, or click to browse")
            self.meta_lbl.setText("Supports .png, .jpg, .tga")
            self.meta_lbl.setStyleSheet("color: #6c7086; font-size: 11px;")
        self._update_style()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            f, _ = QFileDialog.getOpenFileName(
                self,
                "Select Wallpaper Image",
                "",
                "Image Files (*.png *.jpg *.jpeg *.tga);;All Files (*)"
            )
            if f:
                p = Path(f)
                self.set_file(p)
                self.fileDropped.emit(p)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in self.SUPPORTED_EXTS:
                    self._is_drag_active = True
                    self._update_style()
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dragLeaveEvent(self, event):
        self._is_drag_active = False
        self._update_style()
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self._is_drag_active = False
        self._update_style()
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in self.SUPPORTED_EXTS and p.is_file():
                    self.set_file(p)
                    self.fileDropped.emit(p)
                    event.acceptProposedAction()
                    return
        event.ignore()


class CollapsibleSection(QFrame):
    """
    Modern accordion card with smooth collapsible body.
    """

    def __init__(self, title: str, parent: Optional[QWidget] = None, starts_expanded: bool = True):
        super().__init__(parent)
        self.setObjectName("accordionCard")
        self._is_expanded = starts_expanded
        self._title_str = title

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Toggle Button
        self.toggle_btn = QPushButton(self._get_header_text())
        self.toggle_btn.setObjectName("accordionToggle")
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        main_layout.addWidget(self.toggle_btn)

        # Content container
        self.content_widget = QFrame()
        self.content_widget.setObjectName("accordionContent")
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 12, 12, 12)
        self.content_layout.setSpacing(10)
        main_layout.addWidget(self.content_widget)

        self.content_widget.setVisible(self._is_expanded)

    def _get_header_text(self) -> str:
        arrow = "▼" if self._is_expanded else "▶"
        return f"{arrow}  {self._title_str}"

    def toggle(self):
        self._is_expanded = not self._is_expanded
        self.toggle_btn.setText(self._get_header_text())
        self.content_widget.setVisible(self._is_expanded)

    def add_widget(self, widget: QWidget):
        self.content_layout.addWidget(widget)

    def add_layout(self, layout):
        self.content_layout.addLayout(layout)


class PresetCard(QFrame):
    """
    Selectable theme preset tile with thumbnail artwork, color badges, and metadata.
    """
    selected = pyqtSignal(str)

    def __init__(
        self,
        preset_id: str,
        name: str,
        description: str,
        primary_color: str,
        accent_color: str,
        is_active: bool = False,
        wallpaper_path: Optional[Path] = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.preset_id = preset_id
        self._is_active = is_active
        self.primary_color = primary_color
        self.accent_color = accent_color
        self.wallpaper_path = wallpaper_path
        self.setObjectName("presetCardFrame")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(12)

        # Thumbnail or color preview
        self.thumb_lbl = QLabel()
        self.thumb_lbl.setFixedSize(54, 38)
        self.thumb_lbl.setStyleSheet(f"""
            background-color: {primary_color};
            border: 1px solid #45475a;
            border-radius: 5px;
        """)
        self._load_thumbnail()
        layout.addWidget(self.thumb_lbl)

        # Labels
        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.title_lbl = QLabel(name)
        self.title_lbl.setStyleSheet("color: #cdd6f4; font-weight: 700; font-size: 13px; background: transparent;")
        text_layout.addWidget(self.title_lbl)

        self.desc_lbl = QLabel(description)
        self.desc_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; background: transparent;")
        self.desc_lbl.setWordWrap(True)
        text_layout.addWidget(self.desc_lbl)
        layout.addLayout(text_layout, stretch=1)

        # Active indicator badge
        self.badge_lbl = QLabel("ACTIVE" if is_active else "")
        self.badge_lbl.setStyleSheet("""
            color: #89b4fa;
            font-size: 10px;
            font-weight: 800;
            font-family: 'JetBrains Mono', monospace;
            background: rgba(137, 180, 250, 0.12);
            border: 1px solid #89b4fa;
            border-radius: 4px;
            padding: 3px 6px;
        """)
        self.badge_lbl.setVisible(is_active)
        layout.addWidget(self.badge_lbl)

        self._update_style()

    def _load_thumbnail(self):
        if self.wallpaper_path and self.wallpaper_path.is_file():
            try:
                pix = QPixmap(str(self.wallpaper_path))
                if not pix.isNull():
                    scaled = pix.scaled(54, 38, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    # Crop to exact 54x38
                    ox = max(0, (scaled.width() - 54) // 2)
                    oy = max(0, (scaled.height() - 38) // 2)
                    cropped = scaled.copy(ox, oy, 54, 38)
                    self.thumb_lbl.setPixmap(cropped)
                    return
            except Exception:
                pass
        self.thumb_lbl.setStyleSheet(f"""
            background-color: {self.primary_color};
            border: 2px solid {self.accent_color};
            border-radius: 5px;
        """)

    def set_active(self, active: bool):
        self._is_active = active
        self.badge_lbl.setText("ACTIVE" if active else "")
        self.badge_lbl.setVisible(active)
        self._update_style()

    def _update_style(self):
        border_col = "#89b4fa" if self._is_active else "#313244"
        bg_col = "#1e1e2e" if self._is_active else "#181825"
        self.setStyleSheet(f"""
            QFrame#presetCardFrame {{
                background-color: {bg_col};
                border: 1px solid {border_col};
                border-radius: 8px;
            }}
            QFrame#presetCardFrame:hover {{
                border-color: #89b4fa;
                background-color: #232338;
            }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self.preset_id)
        super().mousePressEvent(event)

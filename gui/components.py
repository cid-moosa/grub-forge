"""
GRUB Forge - Reusable UI Components
Custom badges, interactive color picker swatches, preset cards,
and collapsible streaming console drawer.
"""

from __future__ import annotations

from typing import Optional, Callable
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QBrush, QPen, QFont
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton,
    QColorDialog, QFrame, QPlainTextEdit, QSizePolicy
)


class StatusPill(QFrame):
    """A compact cyber status badge with an indicator light and label."""

    def __init__(
        self,
        text: str,
        color_hex: str = "#89b4fa",
        status_dot: str = "#a6e3a1",
        tooltip: str = "",
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setToolTip(tooltip)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 10, 4)
        layout.setSpacing(6)

        # Indicator dot
        self.dot = QLabel()
        self.dot.setFixedSize(8, 8)
        self.set_dot_color(status_dot)
        layout.addWidget(self.dot)

        # Label text
        self.lbl = QLabel(text)
        self.lbl.setStyleSheet(f"color: {color_hex}; font-size: 11px; font-weight: 600;")
        layout.addWidget(self.lbl)

        self.setStyleSheet(
            f"QFrame {{ background-color: #11111b; border: 1px solid #313244; border-radius: 12px; }}"
        )

    def set_dot_color(self, color_hex: str):
        self.dot.setStyleSheet(
            f"background-color: {color_hex}; border-radius: 4px;"
        )

    def set_text(self, text: str):
        self.lbl.setText(text)


class ColorPickerButton(QPushButton):
    """
    Button displaying a color swatch preview that opens QColorDialog on click.
    """
    colorChanged = pyqtSignal(str)

    def __init__(self, initial_hex: str = "#89b4fa", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._color_hex = initial_hex
        self.setFixedHeight(30)
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
        self.setText(f"  {self._color_hex.upper()}  ")
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {self._color_hex};
                color: {'#11111b' if QColor(self._color_hex).lightness() > 140 else '#ffffff'};
                border: 1px solid #585b70;
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


class CollapsibleConsole(QFrame):
    """
    Collapsible streaming terminal console for command execution output.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.is_expanded = True

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header Bar
        header = QFrame()
        header.setStyleSheet("background-color: #181825; border-bottom: 1px solid #313244;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(12, 6, 12, 6)
        h_layout.setSpacing(10)

        title_lbl = QLabel("SYSTEM CONSOLE")
        title_lbl.setStyleSheet("color: #89b4fa; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        h_layout.addWidget(title_lbl)

        self.status_pill = StatusPill("IDLE", "#a6adc8", "#6c7086")
        h_layout.addWidget(self.status_pill)

        h_layout.addStretch()

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("padding: 2px 10px; font-size: 11px;")
        self.clear_btn.clicked.connect(self.clear)
        h_layout.addWidget(self.clear_btn)

        self.toggle_btn = QPushButton("Collapse ▼")
        self.toggle_btn.setStyleSheet("padding: 2px 10px; font-size: 11px;")
        self.toggle_btn.clicked.connect(self.toggle_expanded)
        h_layout.addWidget(self.toggle_btn)

        main_layout.addWidget(header)

        # Terminal text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setObjectName("terminalEdit")
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(2000)
        self.text_edit.setFixedHeight(140)
        main_layout.addWidget(self.text_edit)

        self.setStyleSheet("QFrame { background-color: #11111b; border: 1px solid #313244; border-radius: 6px; }")

    def toggle_expanded(self):
        self.is_expanded = not self.is_expanded
        self.text_edit.setVisible(self.is_expanded)
        self.toggle_btn.setText("Collapse ▼" if self.is_expanded else "Expand ▲")

    def set_status(self, status: str, color_hex: str):
        self.status_pill.set_text(status)
        self.status_pill.set_dot_color(color_hex)

    def append_line(self, line: str):
        # Format prefixes with terminal aesthetic
        if line.startswith("[+]"):
            prefix = "<b><font color='#a6e3a1'>[+]</font></b> "
            content = line[3:].strip()
            self.text_edit.appendHtml(f"{prefix}<font color='#cdd6f4'>{content}</font>")
        elif line.startswith("[*]"):
            prefix = "<b><font color='#89b4fa'>[*]</font></b> "
            content = line[3:].strip()
            self.text_edit.appendHtml(f"{prefix}<font color='#b4befe'>{content}</font>")
        elif line.startswith("[✓]"):
            prefix = "<b><font color='#a6e3a1'>[✓]</font></b> "
            content = line[3:].strip()
            self.text_edit.appendHtml(f"{prefix}<font color='#a6e3a1'>{content}</font>")
        elif line.startswith("[!]") or "error" in line.lower():
            prefix = "<b><font color='#f38ba8'>[!]</font></b> "
            content = line[3:].strip() if line.startswith("[!]") else line
            self.text_edit.appendHtml(f"{prefix}<font color='#f38ba8'>{content}</font>")
        else:
            self.text_edit.appendPlainText(line)

        # Auto-scroll to bottom
        sb = self.text_edit.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def clear(self):
        self.text_edit.clear()

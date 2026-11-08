"""
GRUB Forge - Bottom Action & Animated Execution Drawer
Provides a persistent collapsed footer (48px) with status indicators, emergency
rescue triggers, and primary apply action, expanding to 220px with a smooth
slide-up animation for real-time streaming terminal diagnostics.
"""

from __future__ import annotations

from typing import Optional
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPropertyAnimation, QEasingCurve, QRect
)
from PyQt6.QtGui import QFont, QGuiApplication
from PyQt6.QtWidgets import (
    QWidget, QFrame, QHBoxLayout, QVBoxLayout, QPushButton,
    QLabel, QPlainTextEdit, QMessageBox, QSizePolicy
)

from gui.widgets import TelemetryBadge


class TerminalDrawer(QFrame):
    """
    Bottom collapsible console drawer with animated height expansion.
    """
    applyRequested = pyqtSignal()
    emergencyRequested = pyqtSignal()
    rollbackRequested = pyqtSignal()
    qemuRequested = pyqtSignal()

    COLLAPSED_HEIGHT = 50
    EXPANDED_HEIGHT = 220

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.is_expanded = False
        self.setObjectName("terminalDrawer")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 1. Persistent Top Header Bar (Height: 50px)
        self.header_frame = QFrame()
        self.header_frame.setObjectName("drawerHeader")
        self.header_frame.setFixedHeight(self.COLLAPSED_HEIGHT)

        h_layout = QHBoxLayout(self.header_frame)
        h_layout.setContentsMargins(16, 8, 16, 8)
        h_layout.setSpacing(12)

        # Toggle Button
        self.toggle_btn = QPushButton("Show Console Output ▲")
        self.toggle_btn.setObjectName("secondaryBtn")
        self.toggle_btn.setFixedWidth(170)
        self.toggle_btn.clicked.connect(self.toggle)
        h_layout.addWidget(self.toggle_btn)

        # Status Pill
        self.status_badge = TelemetryBadge("●", "Status", "IDLE", "#a6e3a1")
        h_layout.addWidget(self.status_badge)

        h_layout.addStretch()

        # Emergency Rescue Button
        self.emergency_btn = QPushButton("🛡 Emergency Restore")
        self.emergency_btn.setObjectName("dangerBtn")
        self.emergency_btn.setToolTip("Show self-contained emergency recovery script for live USB / chroot")
        self.emergency_btn.clicked.connect(self.emergencyRequested.emit)
        h_layout.addWidget(self.emergency_btn)

        # Rollback to snapshot button
        self.rollback_btn = QPushButton("↺ Rollback")
        self.rollback_btn.setObjectName("secondaryBtn")
        self.rollback_btn.setToolTip("Revert bootloader to the latest backup snapshot")
        self.rollback_btn.clicked.connect(self.rollbackRequested.emit)
        h_layout.addWidget(self.rollback_btn)

        # Test in Virtual Machine Button
        self.qemu_btn = QPushButton("🖥 Test in Virtual Machine")
        self.qemu_btn.setObjectName("secondaryBtn")
        self.qemu_btn.setToolTip("Launch staged theme in an emulated QEMU virtual machine")
        self.qemu_btn.clicked.connect(self.qemuRequested.emit)
        h_layout.addWidget(self.qemu_btn)

        # Primary Apply Button
        self.apply_btn = QPushButton("⚡ Apply & Rebuild GRUB")
        self.apply_btn.setObjectName("primaryActionBtn")
        self.apply_btn.clicked.connect(self.applyRequested.emit)
        h_layout.addWidget(self.apply_btn)

        self.main_layout.addWidget(self.header_frame)

        # 2. Expandable Console Body
        self.body_frame = QFrame()
        self.body_frame.setObjectName("drawerBody")
        self.body_frame.setFixedHeight(0)
        self.body_frame.setVisible(False)

        b_layout = QVBoxLayout(self.body_frame)
        b_layout.setContentsMargins(0, 0, 0, 0)
        b_layout.setSpacing(0)

        # Control mini-bar
        mini_bar = QFrame()
        mini_bar.setStyleSheet("background-color: #11111b; border-bottom: 1px solid #232338;")
        m_layout = QHBoxLayout(mini_bar)
        m_layout.setContentsMargins(14, 4, 14, 4)
        m_layout.setSpacing(10)

        console_title = QLabel("LIVE PROCESS OUTPUT PIPELINE")
        console_title.setStyleSheet("color: #89b4fa; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        m_layout.addWidget(console_title)

        m_layout.addStretch()

        copy_btn = QPushButton("Copy Logs")
        copy_btn.setObjectName("iconBtn")
        copy_btn.clicked.connect(self._copy_logs)
        m_layout.addWidget(copy_btn)

        clear_btn = QPushButton("Clear")
        clear_btn.setObjectName("iconBtn")
        clear_btn.clicked.connect(self.clear_logs)
        m_layout.addWidget(clear_btn)

        b_layout.addWidget(mini_bar)

        # Terminal text area
        self.terminal = QPlainTextEdit()
        self.terminal.setObjectName("terminalView")
        self.terminal.setReadOnly(True)
        self.terminal.setMaximumBlockCount(3000)
        b_layout.addWidget(self.terminal, stretch=1)

        self.main_layout.addWidget(self.body_frame)

        # Animation setup
        self._anim = QPropertyAnimation(self.body_frame, b"maximumHeight")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_running_state(self, is_running: bool):
        self.apply_btn.setEnabled(not is_running)
        self.rollback_btn.setEnabled(not is_running)
        if is_running:
            self.apply_btn.setText("⚡ Applying Changes...")
            self.status_badge.set_value("RUNNING")
            # Automatically expand drawer if running
            if not self.is_expanded:
                self.expand()
        else:
            self.apply_btn.setText("⚡ Apply & Rebuild GRUB")

    def set_status(self, text: str, color_hex: str):
        self.status_badge.set_value(text)
        self.status_badge.icon_lbl.setStyleSheet(f"color: {color_hex}; font-size: 13px; font-weight: bold;")

    def toggle(self):
        if self.is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        self.is_expanded = True
        self.toggle_btn.setText("Hide Console Output ▼")
        self.body_frame.setVisible(True)
        target_h = self.EXPANDED_HEIGHT - self.COLLAPSED_HEIGHT
        self._anim.stop()
        self._anim.setStartValue(self.body_frame.height())
        self._anim.setEndValue(target_h)
        self._anim.start()

    def collapse(self):
        self.is_expanded = False
        self.toggle_btn.setText("Show Console Output ▲")
        self._anim.stop()
        self._anim.setStartValue(self.body_frame.height())
        self._anim.setEndValue(0)
        self._anim.finished.connect(self._on_collapse_finished)
        self._anim.start()

    def _on_collapse_finished(self):
        if not self.is_expanded:
            self.body_frame.setVisible(False)
        try:
            self._anim.finished.disconnect(self._on_collapse_finished)
        except Exception:
            pass

    def append_log(self, text: str):
        # Format prefixes with high-contrast colors
        if text.startswith("[+]"):
            prefix = "<b><font color='#a6e3a1'>[+]</font></b> "
            content = text[3:].strip()
            self.terminal.appendHtml(f"{prefix}<font color='#cdd6f4'>{content}</font>")
        elif text.startswith("[*]"):
            prefix = "<b><font color='#89b4fa'>[*]</font></b> "
            content = text[3:].strip()
            self.terminal.appendHtml(f"{prefix}<font color='#b4befe'>{content}</font>")
        elif text.startswith("[✓]"):
            prefix = "<b><font color='#a6e3a1'>[✓]</font></b> "
            content = text[3:].strip()
            self.terminal.appendHtml(f"{prefix}<font color='#a6e3a1'><b>{content}</b></font>")
        elif text.startswith("[!]") or "error" in text.lower():
            prefix = "<b><font color='#f38ba8'>[!]</font></b> "
            content = text[3:].strip() if text.startswith("[!]") else text
            self.terminal.appendHtml(f"{prefix}<font color='#f38ba8'><b>{content}</b></font>")
        elif text.startswith("[~]"):
            prefix = "<b><font color='#f9e2af'>[~]</font></b> "
            content = text[3:].strip()
            self.terminal.appendHtml(f"{prefix}<font color='#f9e2af'>{content}</font>")
        else:
            self.terminal.appendPlainText(text)

        sb = self.terminal.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())

    def clear_logs(self):
        self.terminal.clear()

    def _copy_logs(self):
        txt = self.terminal.toPlainText()
        if txt:
            QGuiApplication.clipboard().setText(txt)
            self.append_log("[✓] Console output copied to clipboard.")

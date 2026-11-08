"""
GRUB Forge - Snapshot & Rollback History Manager
GUI dialog allowing users to inspect past immutable snapshots, view side-by-side
configuration diffs, and restore historical bootloader states.
"""

from __future__ import annotations

import difflib
import json
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
    QListWidgetItem, QLabel, QPushButton, QTextEdit, QFrame,
    QMessageBox, QFileDialog, QSplitter
)

from backend.fs_detector import GrubPaths, GrubTools, DistroInfo
from backend.safety import SafetyManager
from gui.styles import MAIN_STYLESHEET
from gui.widgets import TelemetryBadge


class SnapshotManagerDialog(QDialog):
    """
    Dialog for viewing, comparing, and restoring historical bootloader backups.
    """
    snapshotRestored = pyqtSignal(str)

    def __init__(
        self,
        paths: GrubPaths,
        tools: GrubTools,
        distro: DistroInfo,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("GRUB Forge — Snapshot History & Configuration Diffs")
        self.resize(920, 600)
        self.setStyleSheet(MAIN_STYLESHEET)

        self.paths = paths
        self.tools = tools
        self.distro = distro
        self.safety = SafetyManager(paths, tools, distro)

        self._snapshots: List[Path] = []
        self._init_ui()
        self._load_snapshots()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Header
        h_layout = QHBoxLayout()
        title_lbl = QLabel("Immutable Backup Snapshots")
        title_lbl.setStyleSheet("color: #89b4fa; font-size: 16px; font-weight: 700;")
        h_layout.addWidget(title_lbl)

        h_layout.addStretch()

        self.refresh_btn = QPushButton("Refresh ⟳")
        self.refresh_btn.setObjectName("secondaryBtn")
        self.refresh_btn.clicked.connect(self._load_snapshots)
        h_layout.addWidget(self.refresh_btn)

        layout.addLayout(h_layout)

        # Splitter (List on left, Details & Diff on right)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Snapshot List
        left_frame = QFrame()
        left_frame.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px;")
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(8, 8, 8, 8)
        l_layout.setSpacing(6)

        list_lbl = QLabel("AVAILABLE SNAPSHOTS")
        list_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 700;")
        l_layout.addWidget(list_lbl)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #11111b;
                border: 1px solid #313244;
                border-radius: 4px;
                color: #cdd6f4;
            }
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #232338;
            }
            QListWidget::item:selected {
                background-color: #313244;
                color: #89b4fa;
                font-weight: bold;
            }
        """)
        self.list_widget.currentRowChanged.connect(self._on_snapshot_selected)
        l_layout.addWidget(self.list_widget)
        splitter.addWidget(left_frame)

        # Right: Diff & Actions
        right_frame = QFrame()
        right_frame.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px;")
        r_layout = QVBoxLayout(right_frame)
        r_layout.setContentsMargins(12, 10, 12, 10)
        r_layout.setSpacing(10)

        self.detail_lbl = QLabel("Select a snapshot on the left to inspect configuration diffs.")
        self.detail_lbl.setStyleSheet("color: #a6adc8; font-size: 12px;")
        r_layout.addWidget(self.detail_lbl)

        # Diff View
        diff_title = QLabel("CONFIGURATION DELTA (/etc/default/grub vs Snapshot):")
        diff_title.setStyleSheet("color: #89b4fa; font-size: 11px; font-weight: 700;")
        r_layout.addWidget(diff_title)

        self.diff_view = QTextEdit()
        self.diff_view.setReadOnly(True)
        self.diff_view.setFont(QFont("JetBrains Mono", 10))
        self.diff_view.setStyleSheet("background-color: #0c0c14; border: 1px solid #313244; color: #cdd6f4;")
        r_layout.addWidget(self.diff_view, stretch=1)

        # Action Buttons
        btn_bar = QHBoxLayout()
        self.export_btn = QPushButton("Export Snapshot...")
        self.export_btn.setObjectName("secondaryBtn")
        self.export_btn.clicked.connect(self._export_snapshot)
        btn_bar.addWidget(self.export_btn)

        btn_bar.addStretch()

        self.restore_btn = QPushButton("↺ Restore Selected Snapshot")
        self.restore_btn.setObjectName("primaryActionBtn")
        self.restore_btn.clicked.connect(self._restore_selected)
        btn_bar.addWidget(self.restore_btn)

        r_layout.addLayout(btn_bar)
        splitter.addWidget(right_frame)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 5)
        layout.addWidget(splitter, stretch=1)

    def _load_snapshots(self):
        self.list_widget.clear()
        self._snapshots.clear()

        if not self.paths.backup_dir.is_dir():
            self.detail_lbl.setText("No backups directory found on disk.")
            return

        candidates = sorted(
            [p for p in self.paths.backup_dir.glob("backup_*") if p.is_dir()],
            key=os.path.getmtime,
            reverse=True
        )

        self._snapshots = candidates

        for snap in candidates:
            # Parse timestamp from name backup_YYYYMMDD_HHMMSS
            name = snap.name.replace("backup_", "")
            display_str = name
            if len(name) == 15 and "_" in name:
                d_part, t_part = name.split("_")
                display_str = f"{d_part[:4]}-{d_part[4:6]}-{d_part[6:]} {t_part[:2]}:{t_part[2:4]}:{t_part[4:]}"

            meta_file = snap / "meta.json"
            distro_id = "Linux"
            if meta_file.is_file():
                try:
                    data = json.loads(meta_file.read_text(encoding="utf-8"))
                    distro_id = data.get("distro_id", "Linux").capitalize()
                except Exception:
                    pass

            item = QListWidgetItem(f"📅 {display_str} ({distro_id})")
            item.setData(Qt.ItemDataRole.UserRole, str(snap))
            self.list_widget.addItem(item)

        if candidates:
            self.list_widget.setCurrentRow(0)
        else:
            self.detail_lbl.setText("No snapshot archives located.")
            self.diff_view.setPlainText("No snapshots available.")

    def _on_snapshot_selected(self, row: int):
        if row < 0 or row >= len(self._snapshots):
            return

        snap_path = self._snapshots[row]
        snap_default = snap_path / "grub"
        active_default = self.paths.default_config

        # Build details text
        details = [f"Snapshot Path: <b>{snap_path.name}</b>"]
        meta_file = snap_path / "meta.json"
        if meta_file.is_file():
            try:
                m = json.loads(meta_file.read_text(encoding="utf-8"))
                details.append(f"Distro: <b>{m.get('distro_id')}</b>")
                details.append(f"Update Command: <code>{' '.join(m.get('update_command', []))}</code>")
            except Exception:
                pass
        self.detail_lbl.setText("  •  ".join(details))

        # Build Diff View
        snap_lines = []
        if snap_default.is_file():
            snap_lines = snap_default.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

        active_lines = []
        if active_default.is_file():
            active_lines = active_default.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            active_lines,
            snap_lines,
            fromfile=f"Current ({active_default.name})",
            tofile=f"Snapshot ({snap_path.name}/grub)",
            n=3
        ))

        if not diff:
            self.diff_view.setHtml("<font color='#a6e3a1'>Configuration is identical to current /etc/default/grub.</font>")
        else:
            formatted_diff = []
            for line in diff:
                line_str = line.rstrip()
                if line.startswith("+") and not line.startswith("+++"):
                    formatted_diff.append(f"<font color='#a6e3a1'>{line_str}</font>")
                elif line.startswith("-") and not line.startswith("---"):
                    formatted_diff.append(f"<font color='#f38ba8'>{line_str}</font>")
                elif line.startswith("@"):
                    formatted_diff.append(f"<font color='#89b4fa'><b>{line_str}</b></font>")
                else:
                    formatted_diff.append(f"<font color='#a6adc8'>{line_str}</font>")
            self.diff_view.setHtml("<br>".join(formatted_diff))

    def _restore_selected(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._snapshots):
            return

        target_snap = self._snapshots[row]
        confirm = QMessageBox.question(
            self,
            "Confirm Snapshot Restore",
            f"Are you sure you want to restore the system to snapshot:\n\n{target_snap.name}\n\n"
            "This will revert /etc/default/grub and re-run your bootloader generator.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # Restore snapshot
        backup_default = target_snap / "grub"
        if backup_default.is_file():
            shutil.copy2(backup_default, self.paths.default_config)

        backup_cfg = target_snap / "grub.cfg"
        if backup_cfg.is_file():
            shutil.copy2(backup_cfg, self.paths.active_grub_cfg)

        self.snapshotRestored.emit(target_snap.name)
        QMessageBox.information(self, "Restored", f"Restored configuration from {target_snap.name}.")
        self.accept()

    def _export_snapshot(self):
        row = self.list_widget.currentRow()
        if row < 0 or row >= len(self._snapshots):
            return

        target_snap = self._snapshots[row]
        dest_folder = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if dest_folder:
            dest_path = Path(dest_folder) / target_snap.name
            try:
                shutil.copytree(target_snap, dest_path, dirs_exist_ok=True)
                QMessageBox.information(self, "Exported", f"Snapshot exported successfully to:\n{dest_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to export snapshot: {e}")

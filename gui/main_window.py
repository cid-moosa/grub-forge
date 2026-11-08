"""
GRUB Forge - Main Window Workstation Architecture
Modern Blender/DaVinci Resolve-inspired interface coupling top telemetry,
scrollable accordion inspector, central interactive WYSIWYG canvas, and
an animated terminal execution drawer.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional, Tuple, List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QIcon, QFont, QPixmap, QColor
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QSplitter,
    QFrame, QLabel, QPushButton, QComboBox, QSlider, QSpinBox,
    QDoubleSpinBox, QScrollArea, QFileDialog, QMessageBox, QDialog,
    QTextEdit, QCheckBox, QSizePolicy
)

from backend.fs_detector import FSDetector, SystemTelemetry
from backend.safety import SafetyManager
from backend.theme_engine import ThemeEngine, ThemeColors, PRESETS, AssetProcessor
from backend.theme_scanner import ThemeScanner, DiscoveredTheme
from backend.staging import StagingManager
from backend.executor import CommandExecutor
from backend.qemu_runner import QemuRunner
from gui.styles import MAIN_STYLESHEET
from gui.widgets import (
    TelemetryBadge, ColorPickerButton, DragDropZone, CollapsibleSection, PresetCard
)
from gui.preview_canvas import BootPreviewCanvas, ThemeState, GrubMenuParser
from gui.terminal_drawer import TerminalDrawer
from gui.snapshot_manager import SnapshotManagerDialog


class EmergencyDialog(QDialog):
    """Modal displaying self-contained recovery script instructions."""

    def __init__(self, script_path: Path, script_content: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("GRUB Forge - Emergency Recovery Protocol")
        self.resize(680, 520)
        self.setStyleSheet(MAIN_STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("Zero-Brick Standalone Emergency Rescue Protocol")
        header.setStyleSheet("color: #89b4fa; font-size: 16px; font-weight: 700;")
        layout.addWidget(header)

        info = QLabel(
            "If your system fails to boot after manual changes, boot into any Linux Live USB / rescue medium,\n"
            "mount your root partition, and execute the self-contained rescue script generated below:"
        )
        info.setStyleSheet("color: #a6adc8; font-size: 12px;")
        layout.addWidget(info)

        loc_label = QLabel(f"Script Path on Host: <b>{script_path}</b>")
        loc_label.setStyleSheet("color: #a6e3a1; font-family: 'JetBrains Mono', monospace; font-size: 12px;")
        layout.addWidget(loc_label)

        self.code_view = QTextEdit()
        self.code_view.setReadOnly(True)
        self.code_view.setFont(QFont("JetBrains Mono", 10))
        self.code_view.setPlainText(script_content)
        self.code_view.setStyleSheet("background-color: #0c0c14; border: 1px solid #313244; color: #a6adc8;")
        layout.addWidget(self.code_view)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("Export Script to USB / File...")
        export_btn.clicked.connect(self._export_script)
        btn_layout.addWidget(export_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)
        self.script_content = script_content

    def _export_script(self):
        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Emergency Recovery Script", "grub_emergency_restore.sh", "Shell Scripts (*.sh)"
        )
        if dest:
            try:
                Path(dest).write_text(self.script_content, encoding="utf-8")
                QMessageBox.information(self, "Exported", f"Emergency script successfully exported to:\n{dest}")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", f"Failed to save script: {e}")


class MainWindow(QMainWindow):
    """
    Main workstation window integrating telemetry, the accordion inspector,
    interactive WYSIWYG canvas, and streaming execution drawer.
    """

    def __init__(self, root_prefix: str = ""):
        super().__init__()
        self.setWindowTitle("GRUB Forge — Professional Bootloader Customizer")
        self.resize(1360, 880)
        self.setMinimumSize(1100, 720)
        self.setStyleSheet(MAIN_STYLESHEET)

        # 1. System Discovery & Backend Initialization
        self.fs_detector = FSDetector(root_prefix=root_prefix)
        self.telemetry = self.fs_detector.inspect()
        self.safety = SafetyManager(self.telemetry.paths, self.telemetry.tools, self.telemetry.distro)
        self.theme_engine = ThemeEngine(self.telemetry.paths.theme_dir)
        self.executor = CommandExecutor(self)
        self.qemu_runner = QemuRunner()

        # 2. Central State Model
        self.theme_state = ThemeState()
        self.theme_state.colors = PRESETS["cyber_glow"].colors

        # Parse real entries
        self.theme_state.entries = GrubMenuParser.parse_entries(
            self.telemetry.paths.active_grub_cfg,
            fallback_distro=self.telemetry.distro.name
        )

        # 3. Assemble UI Structure
        self._preset_cards: List[PresetCard] = []
        self._init_ui()

        # 4. Wire signals & initial state push
        self._wire_signals()
        self._sync_state_to_canvas()
        self._log_initial_diagnostics()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # A. Top Navigation & Telemetry Bar (52px)
        self.top_bar = self._build_top_bar()
        root_layout.addWidget(self.top_bar)

        # B. Central Workspace Splitter (Inspector on Left, Viewport on Right)
        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setChildrenCollapsible(False)

        self.inspector_panel = self._build_inspector_panel()
        self.viewport_container = self._build_viewport_container()

        self.workspace_splitter.addWidget(self.inspector_panel)
        self.workspace_splitter.addWidget(self.viewport_container)
        self.workspace_splitter.setStretchFactor(0, 0)
        self.workspace_splitter.setStretchFactor(1, 1)

        root_layout.addWidget(self.workspace_splitter, stretch=1)

        # C. Bottom Action & Execution Drawer (48px collapsed, 220px expanded)
        self.drawer = TerminalDrawer(self)
        root_layout.addWidget(self.drawer)

    # =========================================================================
    # A. TOP NAVIGATION BAR
    # =========================================================================
    def _build_top_bar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("topNavFrame")
        bar.setFixedHeight(52)

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(14)

        # Left: App Title badge & version
        brand_layout = QHBoxLayout()
        brand_layout.setSpacing(8)

        logo_icon = QLabel("⚡")
        logo_icon.setStyleSheet("color: #89b4fa; font-size: 18px;")
        brand_layout.addWidget(logo_icon)

        title_lbl = QLabel("GRUB FORGE")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 800; color: #cdd6f4; letter-spacing: 0.8px;")
        brand_layout.addWidget(title_lbl)

        ver_badge = QLabel("v1.0.0")
        ver_badge.setStyleSheet(
            "background-color: #1e1e2e; color: #89b4fa; border: 1px solid #313244; "
            "border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        brand_layout.addWidget(ver_badge)
        layout.addLayout(brand_layout)

        layout.addSpacing(16)

        # Center: Telemetry Chips
        # 1. Distro Chip
        distro_dot = "#a6e3a1" if not self.telemetry.distro.is_mock else "#f9e2af"
        distro_name = self.telemetry.distro.name + (" (Simulated)" if self.telemetry.distro.is_mock else "")
        self.chip_distro = TelemetryBadge(
            "🐧", "Distro", distro_name, distro_dot,
            tooltip=f"ID: {self.telemetry.distro.distro_id}\nID_LIKE: {', '.join(self.telemetry.distro.id_like)}"
        )
        layout.addWidget(self.chip_distro)

        # 2. Boot Environment Chip
        boot_env = "UEFI (x86_64)" if self.telemetry.fs.efi_mounted else "BIOS / MBR"
        boot_dot = "#a6e3a1" if self.telemetry.fs.efi_mounted else "#fab387"
        self.chip_boot = TelemetryBadge(
            "⚙", "Boot", boot_env, boot_dot,
            tooltip=f"EFI Path: {self.telemetry.fs.efi_path or 'Not mounted'}"
        )
        layout.addWidget(self.chip_boot)

        # 3. Filesystem Chip
        fs_str = self.telemetry.fs.fstype.upper()
        if self.telemetry.fs.is_separate_boot:
            fs_str += " [Sep /boot]"
        if self.telemetry.fs.is_btrfs and self.telemetry.fs.subvolume:
            fs_str += f" ({self.telemetry.fs.subvolume})"
        self.chip_fs = TelemetryBadge(
            "💾", "/boot", fs_str, "#89b4fa",
            tooltip=f"Mount: {self.telemetry.fs.boot_target}\nOptions: {', '.join(self.telemetry.fs.options)}"
        )
        layout.addWidget(self.chip_fs)

        layout.addStretch()

        # Right: Target Screen Resolution Selector
        res_lbl = QLabel("Resolution:")
        res_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600;")
        layout.addWidget(res_lbl)

        self.res_combo = QComboBox()
        self.res_combo.setFixedWidth(190)
        self.res_combo.addItem("1920x1080 (16:9 FHD)", (1920, 1080))
        self.res_combo.addItem("2560x1440 (16:9 2K)", (2560, 1440))
        self.res_combo.addItem("1366x768 (16:9 HD)", (1366, 768))
        self.res_combo.addItem("1024x768 (4:3 XGA)", (1024, 768))
        layout.addWidget(self.res_combo)

        return bar

    # =========================================================================
    # B. LEFT INSPECTOR PANEL (380px)
    # =========================================================================
    def _build_inspector_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("inspectorPanel")
        container.setFixedWidth(380)

        panel_layout = QVBoxLayout(container)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # Inspector Title Header
        header = QFrame()
        header.setStyleSheet("background-color: #181825; border-bottom: 1px solid #28293d; padding: 12px 16px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        insp_title = QLabel("INSPECTOR & SETTINGS")
        insp_title.setStyleSheet("color: #89b4fa; font-weight: 700; font-size: 11px; letter-spacing: 0.8px;")
        h_layout.addWidget(insp_title)
        panel_layout.addWidget(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        scroll_content = QWidget()
        layout = QVBoxLayout(scroll_content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # --- Accordion 1: Theme Discovery & Presets ---
        sec_themes = CollapsibleSection("Theme Discovery & Presets", starts_expanded=True)
        self._preset_cards.clear()

        # Preset Cards Grid
        for p_id, p_obj in PRESETS.items():
            card = PresetCard(
                preset_id=p_id,
                name=p_obj.name,
                description=p_obj.description,
                primary_color=p_obj.colors.desktop_background,
                accent_color=p_obj.colors.highlight_border,
                is_active=(p_id == "cyber_glow")
            )
            card.selected.connect(self._on_preset_selected)
            self._preset_cards.append(card)
            sec_themes.add_widget(card)

        # Scan and list installed system themes on disk
        theme_scanner = ThemeScanner(
            search_paths=[
                self.telemetry.paths.theme_dir,
                self.telemetry.paths.fallback_theme_dir
            ]
        )
        for disc in theme_scanner.scan_installed_themes():
            card = PresetCard(
                preset_id=disc.id,
                name=disc.name,
                description=f"Installed Theme ({disc.directory.name})",
                primary_color=disc.colors.desktop_background,
                accent_color=disc.colors.highlight_border,
                is_active=False
            )
            card.selected.connect(lambda pid, d=disc: self._on_discovered_theme_selected(d))
            self._preset_cards.append(card)
            sec_themes.add_widget(card)

        # Create Custom Blank Theme Button
        self.btn_new_theme = QPushButton("＋ Create Custom Theme Blueprint")
        self.btn_new_theme.setObjectName("secondaryBtn")
        self.btn_new_theme.clicked.connect(self._reset_to_custom_blueprint)
        sec_themes.add_widget(self.btn_new_theme)
        layout.addWidget(sec_themes)

        # --- Accordion 2: Background & Wallpaper Management ---
        sec_bg = CollapsibleSection("Background & Wallpaper Management", starts_expanded=True)

        self.drop_zone = DragDropZone()
        self.drop_zone.fileDropped.connect(self._on_wallpaper_selected)
        sec_bg.add_widget(self.drop_zone)

        # Scale Mode
        scale_row = QHBoxLayout()
        scale_lbl = QLabel("Scaling Mode:")
        scale_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Center Crop (Fill)", "crop")
        self.scale_combo.addItem("Fit with Letterbox", "fit")
        self.scale_combo.addItem("Stretch to Resolution", "stretch")
        scale_row.addWidget(scale_lbl)
        scale_row.addWidget(self.scale_combo)
        sec_bg.add_layout(scale_row)

        # Dimming Overlay Slider
        dim_row = QHBoxLayout()
        dim_lbl = QLabel("Dim Background:")
        dim_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.dim_slider = QSlider(Qt.Orientation.Horizontal)
        self.dim_slider.setRange(0, 80)
        self.dim_slider.setValue(self.theme_state.dim_pct)
        self.dim_val_lbl = QLabel(f"{self.theme_state.dim_pct}%")
        self.dim_val_lbl.setStyleSheet("color: #89b4fa; font-family: monospace; font-size: 11px; min-width: 30px;")
        dim_row.addWidget(dim_lbl)
        dim_row.addWidget(self.dim_slider)
        dim_row.addWidget(self.dim_val_lbl)
        sec_bg.add_layout(dim_row)

        # Blur Level Slider
        blur_row = QHBoxLayout()
        blur_lbl = QLabel("Fast Blur:")
        blur_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.blur_slider = QSlider(Qt.Orientation.Horizontal)
        self.blur_slider.setRange(0, 10)
        self.blur_slider.setValue(0)
        self.blur_val_lbl = QLabel("0px")
        self.blur_val_lbl.setStyleSheet("color: #89b4fa; font-family: monospace; font-size: 11px; min-width: 30px;")
        blur_row.addWidget(blur_lbl)
        blur_row.addWidget(self.blur_slider)
        blur_row.addWidget(self.blur_val_lbl)
        sec_bg.add_layout(blur_row)

        # Solid Fallback Color
        solid_row = QHBoxLayout()
        solid_lbl = QLabel("Solid Desktop Color:")
        solid_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.solid_color_picker = ColorPickerButton(self.theme_state.colors.desktop_background)
        solid_row.addWidget(solid_lbl)
        solid_row.addStretch()
        solid_row.addWidget(self.solid_color_picker)
        sec_bg.add_layout(solid_row)

        layout.addWidget(sec_bg)

        # --- Accordion 3: Menu Geometry & Alignment ---
        sec_geo = CollapsibleSection("Menu Geometry & Alignment", starts_expanded=True)

        # Free Drag Mode Checkbox
        self.chk_free_drag = QCheckBox("Enable Interactive Viewport Drag")
        self.chk_free_drag.setStyleSheet("color: #89b4fa; font-weight: 600; font-size: 12px;")
        sec_geo.add_widget(self.chk_free_drag)

        def add_spin_row(title: str, val: float, min_v: float, max_v: float, step: float = 1.0):
            r = QHBoxLayout()
            lbl = QLabel(title)
            lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
            spin = QDoubleSpinBox()
            spin.setRange(min_v, max_v)
            spin.setValue(val)
            spin.setSingleStep(step)
            spin.setFixedWidth(80)
            r.addWidget(lbl)
            r.addStretch()
            r.addWidget(spin)
            sec_geo.add_layout(r)
            return spin

        self.spin_left = add_spin_row("Left Offset (%):", self.theme_state.menu_left_pct, 0.0, 90.0)
        self.spin_top = add_spin_row("Top Offset (%):", self.theme_state.menu_top_pct, 5.0, 85.0)
        self.spin_width = add_spin_row("Menu Width (%):", self.theme_state.menu_width_pct, 20.0, 95.0)
        self.spin_height = add_spin_row("Menu Height (%):", self.theme_state.menu_height_pct, 20.0, 80.0)

        # Item padding & spacing
        pad_row = QHBoxLayout()
        pad_lbl = QLabel("Item Padding / Spacing:")
        pad_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.spin_padding = QSpinBox()
        self.spin_padding.setRange(2, 30)
        self.spin_padding.setValue(self.theme_state.item_padding)
        self.spin_spacing = QSpinBox()
        self.spin_spacing.setRange(0, 20)
        self.spin_spacing.setValue(self.theme_state.item_spacing)
        pad_row.addWidget(pad_lbl)
        pad_row.addStretch()
        pad_row.addWidget(self.spin_padding)
        pad_row.addWidget(self.spin_spacing)
        sec_geo.add_layout(pad_row)

        layout.addWidget(sec_geo)

        # --- Accordion 4: Typography & Color Engine ---
        sec_color = CollapsibleSection("Typography & Color Engine", starts_expanded=True)

        def add_color_row(title: str, initial_hex: str):
            r = QHBoxLayout()
            lbl = QLabel(title)
            lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
            picker = ColorPickerButton(initial_hex)
            r.addWidget(lbl)
            r.addStretch()
            r.addWidget(picker)
            sec_color.add_layout(r)
            return picker

        self.col_title = add_color_row("Title Header Color:", self.theme_state.colors.title_color)
        self.col_item = add_color_row("Menu Item Text:", self.theme_state.colors.item_color)
        self.col_selected = add_color_row("Selected Item Text:", self.theme_state.colors.selected_item_color)
        self.col_hl_bg = add_color_row("Highlight Fill:", self.theme_state.colors.highlight_background)
        self.col_hl_border = add_color_row("Highlight Border Glow:", self.theme_state.colors.highlight_border)

        # Highlight Box Style selector
        hl_style_row = QHBoxLayout()
        hl_lbl = QLabel("Highlight Box Style:")
        hl_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.combo_hl_style = QComboBox()
        self.combo_hl_style.addItem("Custom Soft Gradient", "gradient")
        self.combo_hl_style.addItem("Flat Solid Pill", "flat")
        hl_style_row.addWidget(hl_lbl)
        hl_style_row.addWidget(self.combo_hl_style)
        sec_color.add_layout(hl_style_row)

        layout.addWidget(sec_color)

        # --- Accordion 5: Boot Sequence Settings ---
        sec_boot = CollapsibleSection("Boot Sequence Settings", starts_expanded=True)

        # Timeout Duration Slider & Numeric Badge
        t_row = QHBoxLayout()
        t_lbl = QLabel("Timeout Duration:")
        t_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.slider_timeout = QSlider(Qt.Orientation.Horizontal)
        self.slider_timeout.setRange(0, 30)
        self.slider_timeout.setValue(self.theme_state.timeout_seconds)
        self.badge_timeout = QLabel(f"{self.theme_state.timeout_seconds}s")
        self.badge_timeout.setStyleSheet(
            "background-color: #1e1e2e; color: #89b4fa; border: 1px solid #313244; "
            "border-radius: 4px; padding: 2px 6px; font-weight: 700; font-family: monospace;"
        )
        t_row.addWidget(t_lbl)
        t_row.addWidget(self.slider_timeout)
        t_row.addWidget(self.badge_timeout)
        sec_boot.add_layout(t_row)

        # Default OS dropdown
        os_lbl = QLabel("Default Boot OS Entry:")
        os_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; margin-top: 4px;")
        sec_boot.add_widget(os_lbl)

        self.combo_default_os = QComboBox()
        for idx, entry in enumerate(self.theme_state.entries):
            self.combo_default_os.addItem(entry, idx)
        sec_boot.add_widget(self.combo_default_os)

        # Dual-Boot & os-prober Protection
        self.chk_os_prober = QCheckBox("Detect Dual-Boot OSes (os-prober)")
        self.chk_os_prober.setChecked(True)
        self.chk_os_prober.setStyleSheet("color: #89b4fa; font-weight: 600; font-size: 12px; margin-top: 10px;")
        sec_boot.add_widget(self.chk_os_prober)

        self.lbl_os_prober_sub = QLabel("Keep Windows and other Linux installations in the boot menu.")
        self.lbl_os_prober_sub.setStyleSheet("color: #a6adc8; font-size: 10px; margin-left: 20px;")
        self.lbl_os_prober_sub.setWordWrap(True)
        sec_boot.add_widget(self.lbl_os_prober_sub)

        # Warning badge if os-prober binary missing on host
        has_os_prober = StagingManager.check_os_prober_installed()
        self.lbl_prober_warn = QLabel("⚠️ os-prober binary not found. Install it: sudo apt/pacman/dnf install os-prober")
        self.lbl_prober_warn.setStyleSheet("color: #f9e2af; font-size: 10px; margin-left: 20px; font-weight: bold;")
        self.lbl_prober_warn.setVisible(not has_os_prober)
        sec_boot.add_widget(self.lbl_prober_warn)

        layout.addWidget(sec_boot)

        layout.addStretch()
        scroll.setWidget(scroll_content)
        panel_layout.addWidget(scroll)

        return container

    # =========================================================================
    # C. CENTRAL VIEWPORT CONTAINER
    # =========================================================================
    def _build_viewport_container(self) -> QWidget:
        container = QFrame()
        container.setObjectName("viewportContainer")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Viewport Header Toolbar
        v_toolbar = QFrame()
        v_toolbar.setStyleSheet("background-color: #181825; border: 1px solid #313244; border-radius: 6px; padding: 6px 12px;")
        t_layout = QHBoxLayout(v_toolbar)
        t_layout.setContentsMargins(0, 0, 0, 0)
        t_layout.setSpacing(10)

        v_title = QLabel("LIVE WYSIWYG RUNTIME SIMULATOR")
        v_title.setStyleSheet("color: #89b4fa; font-weight: 700; font-size: 11px; letter-spacing: 0.6px;")
        t_layout.addWidget(v_title)

        t_layout.addStretch()

        self.btn_play_preview = QPushButton("▶ Play Boot Timer")
        self.btn_play_preview.setObjectName("secondaryBtn")
        self.btn_play_preview.clicked.connect(self._toggle_preview_playback)
        t_layout.addWidget(self.btn_play_preview)

        self.btn_reset_preview = QPushButton("↺ Reset")
        self.btn_reset_preview.setObjectName("secondaryBtn")
        self.btn_reset_preview.clicked.connect(self._reset_preview)
        t_layout.addWidget(self.btn_reset_preview)

        self.btn_reload_cfg = QPushButton("⟳ Reload grub.cfg")
        self.btn_reload_cfg.setObjectName("secondaryBtn")
        self.btn_reload_cfg.clicked.connect(self._reload_grub_cfg)
        t_layout.addWidget(self.btn_reload_cfg)

        layout.addWidget(v_toolbar)

        # Core QGraphicsView Preview Canvas
        self.canvas = BootPreviewCanvas(self)
        layout.addWidget(self.canvas, stretch=1)

        return container

    # =========================================================================
    # SIGNAL WIRING & STATE SYNCHRONIZATION
    # =========================================================================
    def _wire_signals(self):
        # Resolution changed
        self.res_combo.currentIndexChanged.connect(self._on_resolution_changed)

        # Wallpaper & Scaling
        self.scale_combo.currentIndexChanged.connect(self._on_scale_mode_changed)
        self.dim_slider.valueChanged.connect(self._on_dim_changed)
        self.blur_slider.valueChanged.connect(self._on_blur_changed)
        self.solid_color_picker.colorChanged.connect(self._on_solid_color_changed)

        # Geometry Controls
        self.chk_free_drag.toggled.connect(self._on_free_drag_toggled)
        self.spin_left.valueChanged.connect(self._on_geometry_spin_changed)
        self.spin_top.valueChanged.connect(self._on_geometry_spin_changed)
        self.spin_width.valueChanged.connect(self._on_geometry_spin_changed)
        self.spin_height.valueChanged.connect(self._on_geometry_spin_changed)
        self.spin_padding.valueChanged.connect(self._on_padding_spacing_changed)
        self.spin_spacing.valueChanged.connect(self._on_padding_spacing_changed)

        # Canvas Free-Drag Sync back to Sidebar
        self.canvas.geometrySyncRequested.connect(self._on_canvas_geometry_synced)
        self.canvas.fileDropped.connect(self._on_wallpaper_selected)
        self.canvas.osSelectionChanged.connect(self._on_canvas_os_selected)

        # Colors & Style
        self.col_title.colorChanged.connect(self._on_title_color_changed)
        self.col_item.colorChanged.connect(self._on_item_color_changed)
        self.col_selected.colorChanged.connect(self._on_selected_color_changed)
        self.col_hl_bg.colorChanged.connect(self._on_hl_bg_changed)
        self.col_hl_border.colorChanged.connect(self._on_hl_border_changed)
        self.combo_hl_style.currentIndexChanged.connect(self._on_hl_style_changed)

        # Boot Settings
        self.slider_timeout.valueChanged.connect(self._on_timeout_slider_changed)
        self.combo_default_os.currentIndexChanged.connect(self._on_default_os_combo_changed)

        # Bottom Drawer Actions
        self.drawer.applyRequested.connect(self._execute_apply_and_rebuild)
        self.drawer.emergencyRequested.connect(self._show_emergency_dialog)
        self.drawer.rollbackRequested.connect(self._show_snapshot_history)
        self.drawer.qemuRequested.connect(self._launch_qemu_test)

        # Executor Output & Progress Piped to Drawer
        self.executor.output_line.connect(self.drawer.append_log)
        self.executor.progress_changed.connect(self._on_worker_progress)
        self.executor.operation_finished.connect(self._on_execution_finished)

    def _sync_state_to_canvas(self):
        """Dispatches active ThemeState to canvas for a smooth virtual redraw."""
        self.canvas.apply_state(self.theme_state)

    def _log_initial_diagnostics(self):
        self.drawer.append_log("[*] GRUB Forge Workstation v1.0.0 initialized.")
        self.drawer.append_log(f"[*] Target Distribution: {self.telemetry.distro.name} ({self.telemetry.distro.distro_id})")
        self.drawer.append_log(f"[*] /boot Filesystem Topology: {self.telemetry.fs.fstype.upper()} (Mount: {self.telemetry.fs.boot_target})")
        if self.telemetry.fs.is_btrfs:
            self.drawer.append_log(f"[*] Btrfs Subvolume: {self.telemetry.fs.subvolume or 'root'}")
        self.drawer.append_log(f"[*] Active grub.cfg: {self.telemetry.paths.active_grub_cfg}")
        self.drawer.append_log(f"[*] Generator Command: {' '.join(self.telemetry.tools.update_command)}")
        self.drawer.append_log(f"[*] Pre-flight Syntax Tool: {self.telemetry.tools.script_check_tool or 'Internal Linter'}")
        self.drawer.append_log("[✓] Zero-brick guardrails armed: Automated snapshots, atomic updates & emergency rescue ready.")

    # =========================================================================
    # EVENT HANDLERS
    # =========================================================================

    def _on_resolution_changed(self, index: int):
        res = self.res_combo.currentData()
        if res:
            self.theme_state.resolution = res
            self._sync_state_to_canvas()
            self.drawer.append_log(f"[*] Virtual canvas resolution changed to {res[0]}x{res[1]}")

    def _on_preset_selected(self, preset_id: str):
        preset = PRESETS.get(preset_id)
        if not preset:
            return

        for card in self._preset_cards:
            card.set_active(card.preset_id == preset_id)

        self.theme_state.colors = ThemeColors(
            desktop_background=preset.colors.desktop_background,
            title_color=preset.colors.title_color,
            item_color=preset.colors.item_color,
            selected_item_color=preset.colors.selected_item_color,
            highlight_background=preset.colors.highlight_background,
            highlight_border=preset.colors.highlight_border,
            timeout_color=preset.colors.timeout_color,
            menu_box_background=preset.colors.menu_box_background,
            menu_box_border=preset.colors.menu_box_border
        )

        # Update controls
        self.solid_color_picker.set_color(self.theme_state.colors.desktop_background)
        self.col_title.set_color(self.theme_state.colors.title_color)
        self.col_item.set_color(self.theme_state.colors.item_color)
        self.col_selected.set_color(self.theme_state.colors.selected_item_color)
        self.col_hl_bg.set_color(self.theme_state.colors.highlight_background)
        self.col_hl_border.set_color(self.theme_state.colors.highlight_border)

        self._sync_state_to_canvas()
        self.drawer.append_log(f"[+] Loaded preset: {preset.name}")

    def _reset_to_custom_blueprint(self):
        for card in self._preset_cards:
            card.set_active(False)
        self.theme_state.wallpaper_path = None
        self.drop_zone.set_file(None)
        self.theme_state.colors = ThemeColors()
        self.solid_color_picker.set_color(self.theme_state.colors.desktop_background)
        self._sync_state_to_canvas()
        self.drawer.append_log("[*] Reset to blank custom blueprint.")

    def _on_wallpaper_selected(self, path: Path):
        self.theme_state.wallpaper_path = path
        self.drop_zone.set_file(path)
        self._sync_state_to_canvas()
        self.drawer.append_log(f"[+] Loaded wallpaper asset: {path.name}")

    def _on_scale_mode_changed(self, index: int):
        self.theme_state.scale_mode = self.scale_combo.currentData()
        self._sync_state_to_canvas()

    def _on_dim_changed(self, val: int):
        self.theme_state.dim_pct = val
        self.dim_val_lbl.setText(f"{val}%")
        self._sync_state_to_canvas()

    def _on_blur_changed(self, val: int):
        self.theme_state.blur_level = val
        self.blur_val_lbl.setText(f"{val}px")
        self._sync_state_to_canvas()

    def _on_solid_color_changed(self, hex_val: str):
        self.theme_state.colors.desktop_background = hex_val
        self._sync_state_to_canvas()

    def _on_free_drag_toggled(self, checked: bool):
        self.theme_state.free_drag = checked
        self.canvas.menu_item.state = self.theme_state
        self.canvas.menu_item.update_position()
        self.drawer.append_log(f"[*] Interactive Viewport Drag: {'ENABLED' if checked else 'DISABLED'}")

    def _on_geometry_spin_changed(self):
        self.theme_state.menu_left_pct = self.spin_left.value()
        self.theme_state.menu_top_pct = self.spin_top.value()
        self.theme_state.menu_width_pct = self.spin_width.value()
        self.theme_state.menu_height_pct = self.spin_height.value()
        self.canvas.menu_item.update_position()
        self.canvas._scene.update()

    def _on_padding_spacing_changed(self):
        self.theme_state.item_padding = self.spin_padding.value()
        self.theme_state.item_spacing = self.spin_spacing.value()
        self.canvas._scene.update()

    def _on_canvas_geometry_synced(self, l_pct, t_pct, w_pct, h_pct):
        self.spin_left.blockSignals(True)
        self.spin_top.blockSignals(True)
        self.spin_left.setValue(l_pct)
        self.spin_top.setValue(t_pct)
        self.spin_left.blockSignals(False)
        self.spin_top.blockSignals(False)

    def _on_title_color_changed(self, hex_val: str):
        self.theme_state.colors.title_color = hex_val
        self._sync_state_to_canvas()

    def _on_item_color_changed(self, hex_val: str):
        self.theme_state.colors.item_color = hex_val
        self._sync_state_to_canvas()

    def _on_selected_color_changed(self, hex_val: str):
        self.theme_state.colors.selected_item_color = hex_val
        self._sync_state_to_canvas()

    def _on_hl_bg_changed(self, hex_val: str):
        self.theme_state.colors.highlight_background = hex_val
        self._sync_state_to_canvas()

    def _on_hl_border_changed(self, hex_val: str):
        self.theme_state.colors.highlight_border = hex_val
        self.theme_state.colors.timeout_color = hex_val
        self._sync_state_to_canvas()

    def _on_hl_style_changed(self, index: int):
        self.theme_state.highlight_style = self.combo_hl_style.currentData()
        self._sync_state_to_canvas()

    def _on_timeout_slider_changed(self, val: int):
        self.theme_state.timeout_seconds = val
        self.badge_timeout.setText(f"{val}s")
        self.canvas.reset_preview()

    def _on_default_os_combo_changed(self, index: int):
        self.theme_state.default_os_index = index
        self._sync_state_to_canvas()

    def _on_canvas_os_selected(self, index: int):
        self.combo_default_os.blockSignals(True)
        self.combo_default_os.setCurrentIndex(index)
        self.combo_default_os.blockSignals(False)

    def _toggle_preview_playback(self):
        playing = self.canvas.toggle_preview_playback()
        self.btn_play_preview.setText("⏸ Pause Timer" if playing else "▶ Play Boot Timer")

    def _reset_preview(self):
        self.canvas.reset_preview()
        self.btn_play_preview.setText("▶ Play Boot Timer")

    def _reload_grub_cfg(self):
        entries = GrubMenuParser.parse_entries(
            self.telemetry.paths.active_grub_cfg,
            fallback_distro=self.telemetry.distro.name
        )
        self.theme_state.entries = entries
        self.combo_default_os.clear()
        for idx, entry in enumerate(entries):
            self.combo_default_os.addItem(entry, idx)
        self._sync_state_to_canvas()
        self.drawer.append_log(f"[+] Loaded {len(entries)} entries from {self.telemetry.paths.active_grub_cfg.name}")

    # =========================================================================
    # TRANSACTIONAL EXECUTION & SAFETY WORKFLOWS
    # =========================================================================

    def _show_emergency_dialog(self):
        try:
            script_path = self.safety.generate_recovery_script()
            content = script_path.read_text(encoding="utf-8")
            dlg = EmergencyDialog(script_path, content, self)
            dlg.exec()
            self.drawer.append_log(f"[✓] Standalone emergency script verified at: {script_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to generate recovery script: {e}")

    def _execute_rollback(self):
        confirm = QMessageBox.question(
            self,
            "Confirm Snapshot Rollback",
            "Revert GRUB configuration and theme to the last known good snapshot?\n\n"
            "This will restore /etc/default/grub, active grub.cfg, and re-run your bootloader generator.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.drawer.set_status("ROLLING BACK", "#fab387")
        self.drawer.append_log("[*] Rollback initiated...")
        success, log = self.safety.rollback()
        self.drawer.append_log(log)

        if success:
            self.drawer.set_status("RESTORED", "#a6e3a1")
            QMessageBox.information(self, "Rollback Complete", "System GRUB configuration was successfully restored.")
        else:
            self.drawer.set_status("ERROR", "#f38ba8")
            QMessageBox.critical(self, "Rollback Error", f"Rollback failed:\n{log}")

    def _on_worker_progress(self, progress: int, message: str):
        self.drawer.set_status(f"RUNNING ({progress}%)", "#89b4fa")

    def _on_discovered_theme_selected(self, disc: DiscoveredTheme):
        for card in self._preset_cards:
            card.set_active(card.preset_id == disc.id)

        self.theme_state.colors = disc.colors
        self.theme_state.title_text = disc.title_text
        if disc.wallpaper_path and disc.wallpaper_path.is_file():
            self._on_wallpaper_selected(disc.wallpaper_path)
        else:
            self._clear_wallpaper()

        self.solid_color_picker.set_color(disc.colors.desktop_background)
        self.col_title.set_color(disc.colors.title_color)
        self.col_item.set_color(disc.colors.item_color)
        self.col_selected.set_color(disc.colors.selected_item_color)
        self.col_hl_bg.set_color(disc.colors.highlight_background)
        self.col_hl_border.set_color(disc.colors.highlight_border)

        self._sync_state_to_canvas()
        self.drawer.append_log(f"[+] Loaded installed theme: {disc.name}")

    def _show_snapshot_history(self):
        """Displays interactive snapshot history dialog with configuration diffs."""
        dlg = SnapshotManagerDialog(self.telemetry.paths, self.telemetry.tools, self.telemetry.distro, self)
        dlg.snapshotRestored.connect(lambda name: self.drawer.append_log(f"[✓] Restored configuration snapshot: {name}"))
        dlg.exec()

    def _launch_qemu_test(self):
        """Prepares virtual disk and launches emulated QEMU boot testbench."""
        self.drawer.append_log("[*] Preparing virtual boot environment for QEMU emulation...")
        staging_mgr = StagingManager()
        staged_dir = staging_mgr.prepare_staged_payload(
            telemetry=self.telemetry,
            theme_name="grub_forge_theme",
            colors=self.theme_state.colors,
            wallpaper_source=self.theme_state.wallpaper_path,
            resolution=self.theme_state.resolution,
            title_text=self.theme_state.title_text,
            timeout_seconds=self.theme_state.timeout_seconds,
            default_os_index=self.theme_state.default_os_index,
            enable_os_prober=self.chk_os_prober.isChecked(),
            dry_run=True
        )

        v_disk = self.qemu_runner.prepare_virtual_disk(
            staged_dir=staged_dir,
            menu_entries=self.theme_state.entries,
            resolution=self.theme_state.resolution,
            timeout_seconds=self.theme_state.timeout_seconds
        )

        ok, msg = self.qemu_runner.launch(v_disk, resolution=self.theme_state.resolution)
        if ok:
            self.drawer.append_log(f"[✓] {msg}")
        else:
            self.drawer.append_log(f"[!] {msg}")
            QMessageBox.information(
                self,
                "QEMU Virtual Testbench",
                f"Could not launch QEMU:\n\n{msg}\n\n"
                "Install QEMU to enable virtual boot testing:\n"
                "Debian/Ubuntu: sudo apt install qemu-system-x86 ovmf\n"
                "Arch Linux:    sudo pacman -S qemu-desktop edk2-ovmf\n"
                "Fedora:        sudo dnf install qemu-system-x86 edk2-ovmf"
            )

    def closeEvent(self, event):
        """Ensures background virtual test processes are cleanly terminated."""
        if hasattr(self, "qemu_runner"):
            self.qemu_runner.terminate()
        super().closeEvent(event)

    def _execute_apply_and_rebuild(self):
        """
        Elevated Privilege Separation Pipeline:
        1. Unprivileged user space staging (~/.cache/grub-forge/staged/)
        2. Execution of elevated worker via pkexec /usr/libexec/grub-forge-worker
        3. Real-time streaming IPC to terminal drawer
        """
        confirm = QMessageBox.question(
            self,
            "Apply & Rebuild GRUB",
            "GRUB Forge will execute the following transactional steps:\n\n"
            "1. Stage verified 8-bit assets & configuration in user cache\n"
            "2. Request elevated privileges via Polkit (pkexec)\n"
            "3. Verify /boot mount & storage headroom (>= 25 MB)\n"
            "4. Create immutable snapshot in /boot/grub/grub_forge_backups/\n"
            "5. Generate standalone rescue script at /boot/grub_emergency_restore.sh\n"
            "6. Atomically update /etc/default/grub & enforce permissions (755/644)\n"
            "7. Run pre-flight dry-run syntax verification\n"
            "8. Rebuild bootloader via distro generator (update-grub / grub-mkconfig)\n\n"
            "Do you want to proceed?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self.drawer.set_running_state(True)
        self.drawer.append_log("\n=== [TRANSACTION INITIATED: PRIVILEGE SEPARATION WORKER] ===")

        dry_run = self.telemetry.distro.is_mock or not sys.platform.startswith("linux")

        try:
            # 1. Unprivileged user-space staging
            self.drawer.append_log("[*] Phase 1/2: Preparing assets and configuration in user space (~/.cache/grub-forge/staged/)...")
            staging_mgr = StagingManager()
            staged_dir = staging_mgr.prepare_staged_payload(
                telemetry=self.telemetry,
                theme_name="grub_forge_theme",
                colors=self.theme_state.colors,
                wallpaper_source=self.theme_state.wallpaper_path,
                resolution=self.theme_state.resolution,
                title_text=self.theme_state.title_text,
                timeout_seconds=self.theme_state.timeout_seconds,
                default_os_index=self.theme_state.default_os_index,
                enable_os_prober=self.chk_os_prober.isChecked(),
                dry_run=dry_run
            )
            self.drawer.append_log(f"[✓] User-space assets staged with SHA256 checksums at: {staged_dir}")

            # 2. Trigger Elevated Worker via pkexec
            self.drawer.append_log("[*] Phase 2/2: Launching isolated root deployment worker via pkexec...")
            self.executor.execute_staged_deployment(
                staged_dir=staged_dir,
                use_pkexec=True,
                dry_run=dry_run
            )

        except Exception as e:
            self.drawer.append_log(f"[!] Staging exception: {e}")
            self.drawer.set_status("FAILED", "#f38ba8")
            self.drawer.set_running_state(False)
            QMessageBox.critical(self, "Staging Error", f"Failed to prepare staged assets:\n{e}")
            self.drawer.set_running_state(False)
            QMessageBox.critical(self, "Execution Error", f"Failed to apply GRUB theme:\n{e}\nConfiguration has been automatically restored.")

    def _on_execution_finished(self, success: bool, output: str):
        self.drawer.set_running_state(False)
        if success:
            self.drawer.set_status("SUCCESS", "#a6e3a1")
            self.drawer.append_log("[✓] === [TRANSACTION COMPLETED SUCCESSFULLY] ===")

            reboot_box = QMessageBox(self)
            reboot_box.setWindowTitle("GRUB Forge - Success")
            reboot_box.setText(
                "<h3>GRUB successfully configured and verified!</h3>"
                "<p>Your new bootloader theme is active for the next boot.<br>"
                "Would you like to restart the computer now to verify changes?</p>"
            )
            reboot_box.setIcon(QMessageBox.Icon.Information)
            reboot_btn = reboot_box.addButton("Reboot Now", QMessageBox.ButtonRole.AcceptRole)
            later_btn = reboot_box.addButton("Reboot Later", QMessageBox.ButtonRole.RejectRole)
            reboot_box.exec()

            if reboot_box.clickedButton() == reboot_btn:
                self.drawer.append_log("[*] Triggering system restart...")
                if not CommandExecutor.trigger_reboot():
                    QMessageBox.warning(
                        self, "Reboot", "Automatic reboot request was not handled by system manager. Please reboot manually."
                    )
        else:
            self.drawer.set_status("FAILED", "#f38ba8")
            self.drawer.append_log("[!] Bootloader update command returned an error.")
            self.drawer.append_log("[*] Reverting to last known good snapshot...")
            self.safety.rollback()
            QMessageBox.warning(
                self,
                "Update Command Failed",
                "The bootloader update command returned an error code.\n\n"
                "Guardrail triggered: System was automatically rolled back to the previous snapshot."
            )

"""
GRUB Forge - Main Window Workstation Architecture
Modern Blender/DaVinci Resolve-inspired interface coupling top telemetry,
segmented studio workspace tabs, central interactive WYSIWYG canvas, and
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
    QTextEdit, QCheckBox, QSizePolicy, QStackedWidget, QButtonGroup
)

from backend.fs_detector import FSDetector, SystemTelemetry
from backend.safety import SafetyManager
from backend.theme_engine import ThemeEngine, ThemeColors, PRESETS, AssetProcessor
from backend.theme_scanner import ThemeScanner, DiscoveredTheme
from backend.staging import StagingManager
from backend.executor import CommandExecutor
from backend.qemu_runner import QemuRunner
from backend.theme_packager import ThemePackager
from backend.font_manager import FontManager, GrubFont
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
        self.code_view.setText(script_content)
        self.code_view.setStyleSheet("""
            background-color: #0c0c14;
            color: #a6adc8;
            border: 1px solid #313244;
            border-radius: 6px;
            padding: 8px;
        """)
        layout.addWidget(self.code_view)

        btn_row = QHBoxLayout()
        btn_copy = QPushButton("📋 Copy Script to Clipboard")
        btn_copy.setObjectName("secondaryBtn")
        btn_copy.clicked.connect(self._copy_to_clipboard)
        btn_row.addWidget(btn_copy)

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        btn_row.addWidget(btn_close)
        layout.addLayout(btn_row)

    def _copy_to_clipboard(self):
        from PyQt6.QtGui import QGuiApplication
        clipboard = QGuiApplication.clipboard()
        if clipboard:
            clipboard.setText(self.code_view.toPlainText())
            QMessageBox.information(self, "Copied", "Rescue script copied to clipboard.")


class MainWindow(QMainWindow):
    """
    Main workstation window integrating top telemetry, segmented studio workspace tabs,
    an interactive WYSIWYG canvas, and an animated streaming execution drawer.
    """

    def __init__(self, root_prefix: str = ""):
        super().__init__()
        self.setWindowTitle("GRUB Forge — Professional Bootloader Customizer")
        self.resize(1400, 900)
        self.setMinimumSize(1120, 720)
        self.setStyleSheet(MAIN_STYLESHEET)

        # 1. System Discovery & Backend Initialization
        self.fs_detector = FSDetector(root_prefix=root_prefix)
        self.telemetry = self.fs_detector.inspect()
        self.safety = SafetyManager(self.telemetry.paths, self.telemetry.tools, self.telemetry.distro)
        self.theme_engine = ThemeEngine(self.telemetry.paths.theme_dir)
        self.font_manager = FontManager(root_prefix=root_prefix)
        self.theme_scanner = ThemeScanner(
            search_paths=[
                self.telemetry.paths.theme_dir,
                self.telemetry.paths.fallback_theme_dir,
                Path("/boot/grub/themes"),
                Path("/boot/grub2/themes"),
                Path("/usr/share/grub/themes"),
                Path("/usr/share/desktop-base/active-theme/grub"),
                Path("/usr/share/desktop-base/kali-theme/grub"),
            ],
            root_prefix=root_prefix
        )
        self.executor = CommandExecutor(self)
        self.qemu_runner = QemuRunner()

        # 2. Fetch and Load Current Active Boot Theme Directly from System Files
        self.current_system_theme = self.theme_scanner.detect_active_system_theme(
            default_grub_path=self.telemetry.paths.default_config,
            distro_id=self.telemetry.distro.distro_id
        )

        self.theme_state = ThemeState()

        d_id = (self.telemetry.distro.distro_id or "").lower()
        if "kali" in d_id:
            default_preset_id = "kali_dragon"
        elif "arch" in d_id:
            default_preset_id = "arch_minimal"
        elif "fedora" in d_id or "rhel" in d_id:
            default_preset_id = "fedora_blue"
        elif "debian" in d_id:
            default_preset_id = "debian_crimson"
        elif "ubuntu" in d_id:
            default_preset_id = "ubuntu_yaru"
        elif "suse" in d_id:
            default_preset_id = "emerald_matrix"
        else:
            default_preset_id = "kali_dragon"

        distro_preset = PRESETS.get(default_preset_id, PRESETS["kali_dragon"])

        if self.current_system_theme:
            self.init_preset_id = self.current_system_theme.id
            self.theme_state.colors = self.current_system_theme.colors
            self.theme_state.title_text = self.current_system_theme.title_text
            self.theme_state.theme_source_dir = self.current_system_theme.directory
            self.theme_state.all_theme_images = list(self.current_system_theme.all_images)
            if self.current_system_theme.wallpaper_path and self.current_system_theme.wallpaper_path.is_file():
                self.theme_state.wallpaper_path = self.current_system_theme.wallpaper_path
            elif distro_preset.wallpaper_path and distro_preset.wallpaper_path.is_file():
                self.theme_state.wallpaper_path = distro_preset.wallpaper_path
        else:
            self.init_preset_id = default_preset_id
            self.theme_state.colors = distro_preset.colors
            self.theme_state.title_text = distro_preset.title_text
            self.theme_state.theme_source_dir = distro_preset.wallpaper_path.parent if distro_preset.wallpaper_path else None
            if distro_preset.wallpaper_path and distro_preset.wallpaper_path.is_file():
                self.theme_state.wallpaper_path = distro_preset.wallpaper_path
                self.theme_state.all_theme_images = [distro_preset.wallpaper_path]

        # Parse authentic boot menu entries
        self.theme_state.entries = GrubMenuParser.parse_entries(
            self.telemetry.paths.active_grub_cfg,
            fallback_distro=self.telemetry.distro.name
        )

        # 3. Assemble UI Structure
        self._preset_cards: List[PresetCard] = []
        self._init_ui()

        # 4. Wire signals & initial state push
        self._wire_signals()
        if self.current_system_theme and self.current_system_theme.directory:
            self.canvas.load_slices_from_dir(self.current_system_theme.directory)
        self._sync_state_to_canvas()
        self._refresh_artwork_gallery()
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

        # C. Bottom Action & Execution Drawer (50px collapsed, 220px expanded)
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

        ver_badge = QLabel("STUDIO v1.0")
        ver_badge.setStyleSheet(
            "background-color: #1e1e2e; color: #89b4fa; border: 1px solid #313244; "
            "border-radius: 10px; padding: 2px 8px; font-size: 10px; font-weight: 700;"
        )
        brand_layout.addWidget(ver_badge)
        layout.addLayout(brand_layout)

        layout.addSpacing(16)

        # Center: Telemetry Chips
        distro_dot = "#a6e3a1" if not self.telemetry.distro.is_mock else "#f9e2af"
        distro_name = self.telemetry.distro.name + (" (Simulated)" if self.telemetry.distro.is_mock else "")
        self.chip_distro = TelemetryBadge(
            "🐧", "Distro", distro_name, distro_dot,
            tooltip=f"ID: {self.telemetry.distro.distro_id}\nID_LIKE: {', '.join(self.telemetry.distro.id_like)}"
        )
        layout.addWidget(self.chip_distro)

        boot_env = "UEFI (x86_64)" if self.telemetry.fs.efi_mounted else "BIOS / MBR"
        boot_dot = "#a6e3a1" if self.telemetry.fs.efi_mounted else "#fab387"
        self.chip_boot = TelemetryBadge(
            "⚙", "Boot", boot_env, boot_dot,
            tooltip=f"EFI Path: {self.telemetry.fs.efi_path or 'Not mounted'}"
        )
        layout.addWidget(self.chip_boot)

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
    # B. LEFT INSPECTOR PANEL (420px SEGMENTED STUDIO WORKSPACE)
    # =========================================================================
    def _build_inspector_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("inspectorPanel")
        container.setFixedWidth(420)

        panel_layout = QVBoxLayout(container)
        panel_layout.setContentsMargins(0, 0, 0, 0)
        panel_layout.setSpacing(0)

        # 1. Inspector Title Header
        header = QFrame()
        header.setStyleSheet("background-color: #181825; border-bottom: 1px solid #28293d; padding: 12px 16px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        insp_title = QLabel("STUDIO WORKSPACE")
        insp_title.setStyleSheet("color: #89b4fa; font-weight: 800; font-size: 11px; letter-spacing: 0.8px;")
        h_layout.addWidget(insp_title)
        h_layout.addStretch()

        mode_badge = QLabel("LIVE SYNC")
        mode_badge.setStyleSheet(
            "background-color: rgba(166, 227, 161, 0.12); color: #a6e3a1; border: 1px solid #a6e3a1; "
            "border-radius: 4px; padding: 2px 6px; font-size: 9px; font-weight: 800;"
        )
        h_layout.addWidget(mode_badge)
        panel_layout.addWidget(header)

        # 2. Segmented Studio Navigation Tab Bar
        tab_bar = QFrame()
        tab_bar.setStyleSheet("background-color: #181825; border-bottom: 1px solid #313244;")
        tab_layout = QHBoxLayout(tab_bar)
        tab_layout.setContentsMargins(6, 4, 6, 0)
        tab_layout.setSpacing(2)

        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)

        tabs_info = [
            ("🎨 Presets", 0),
            ("🖼 Artwork", 1),
            ("📐 Layout", 2),
            ("🔤 Styling", 3),
            ("⚙️ Boot", 4)
        ]

        self.tab_buttons: List[QPushButton] = []
        for label, idx in tabs_info:
            btn = QPushButton(label)
            btn.setObjectName("studioTabBtn")
            btn.setCheckable(True)
            if idx == 0:
                btn.setChecked(True)
            btn.clicked.connect(lambda _, i=idx: self.stacked_inspector.setCurrentIndex(i))
            self.tab_group.addButton(btn, idx)
            tab_layout.addWidget(btn)
            self.tab_buttons.append(btn)

        panel_layout.addWidget(tab_bar)

        # 3. Stacked Studio Pages
        self.stacked_inspector = QStackedWidget()

        self.page_presets = self._build_page_presets()
        self.stacked_inspector.addWidget(self.page_presets)

        self.page_artwork = self._build_page_artwork()
        self.stacked_inspector.addWidget(self.page_artwork)

        self.page_layout = self._build_page_geometry()
        self.stacked_inspector.addWidget(self.page_layout)

        self.page_typography = self._build_page_typography()
        self.stacked_inspector.addWidget(self.page_typography)

        self.page_boot = self._build_page_boot()
        self.stacked_inspector.addWidget(self.page_boot)

        panel_layout.addWidget(self.stacked_inspector)
        return container

    def _build_page_presets(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        hdr = QLabel("DISTRO THEME PRESETS & GALLERY")
        hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

        self._preset_cards.clear()
        self.themes_container_layout = QVBoxLayout()
        self.themes_container_layout.setSpacing(8)

        # 1. Highlight active system theme if present
        if self.current_system_theme:
            active_card = PresetCard(
                preset_id="current_system_active",
                name=f"⭐ {self.current_system_theme.name}",
                description=f"Active System Theme: {self.current_system_theme.directory.name}",
                primary_color=self.current_system_theme.colors.desktop_background,
                accent_color=self.current_system_theme.colors.highlight_border,
                is_active=True,
                wallpaper_path=self.current_system_theme.wallpaper_path
            )
            active_card.selected.connect(lambda pid, d=self.current_system_theme: self._on_discovered_theme_selected(d))
            self._preset_cards.append(active_card)
            self.themes_container_layout.addWidget(active_card)

        # 2. Preset Cards Grid
        for p_id, p_obj in PRESETS.items():
            is_active = (not self.current_system_theme and p_id == self.init_preset_id)
            card = PresetCard(
                preset_id=p_id,
                name=p_obj.name,
                description=p_obj.description,
                primary_color=p_obj.colors.desktop_background,
                accent_color=p_obj.colors.highlight_border,
                is_active=is_active,
                wallpaper_path=p_obj.wallpaper_path
            )
            card.selected.connect(self._on_preset_selected)
            self._preset_cards.append(card)
            self.themes_container_layout.addWidget(card)

        # Installed themes on disk
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
                is_active=False,
                wallpaper_path=disc.wallpaper_path
            )
            card.selected.connect(lambda pid, d=disc: self._on_discovered_theme_selected(d))
            self._preset_cards.append(card)
            self.themes_container_layout.addWidget(card)

        layout.addLayout(self.themes_container_layout)

        layout.addSpacing(6)
        self.btn_new_theme = QPushButton("＋ Create Custom Theme Blueprint")
        self.btn_new_theme.setObjectName("secondaryBtn")
        self.btn_new_theme.clicked.connect(self._reset_to_custom_blueprint)
        layout.addWidget(self.btn_new_theme)

        pkg_row = QHBoxLayout()
        self.btn_export_theme = QPushButton("📤 Export Archive (.tar.gz)")
        self.btn_export_theme.setObjectName("secondaryBtn")
        self.btn_export_theme.clicked.connect(self._export_theme_archive)

        self.btn_import_theme = QPushButton("📥 Import Theme (.zip/.tar.gz)")
        self.btn_import_theme.setObjectName("secondaryBtn")
        self.btn_import_theme.clicked.connect(self._import_theme_archive)

        pkg_row.addWidget(self.btn_export_theme)
        pkg_row.addWidget(self.btn_import_theme)
        layout.addLayout(pkg_row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_page_artwork(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        hdr = QLabel("BACKGROUND ARTWORK & NORMALIZATION")
        hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

        self.drop_zone = DragDropZone()
        self.drop_zone.fileDropped.connect(self._on_wallpaper_selected)
        if self.theme_state.wallpaper_path:
            self.drop_zone.set_file(self.theme_state.wallpaper_path)
        layout.addWidget(self.drop_zone)

        quick_lbl = QLabel("Quick Wallpaper Presets:")
        quick_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600;")
        layout.addWidget(quick_lbl)

        q_grid1 = QHBoxLayout()
        btn_q_kali = QPushButton("🐉 Kali Dragon")
        btn_q_kali.setObjectName("secondaryBtn")
        btn_q_kali.clicked.connect(lambda: self._apply_quick_wallpaper("kali/background.png"))
        btn_q_arch = QPushButton("⚡ Arch Minimal")
        btn_q_arch.setObjectName("secondaryBtn")
        btn_q_arch.clicked.connect(lambda: self._apply_quick_wallpaper("arch/background.png"))
        q_grid1.addWidget(btn_q_kali)
        q_grid1.addWidget(btn_q_arch)
        layout.addLayout(q_grid1)

        q_grid2 = QHBoxLayout()
        btn_q_deb = QPushButton("🌀 Debian Cosmos")
        btn_q_deb.setObjectName("secondaryBtn")
        btn_q_deb.clicked.connect(lambda: self._apply_quick_wallpaper("debian/background.png"))
        btn_q_fed = QPushButton("💎 Fedora Horizon")
        btn_q_fed.setObjectName("secondaryBtn")
        btn_q_fed.clicked.connect(lambda: self._apply_quick_wallpaper("fedora/background.png"))
        q_grid2.addWidget(btn_q_deb)
        q_grid2.addWidget(btn_q_fed)
        layout.addLayout(q_grid2)

        q_grid3 = QHBoxLayout()
        btn_q_ubu = QPushButton("🟠 Ubuntu Yaru")
        btn_q_ubu.setObjectName("secondaryBtn")
        btn_q_ubu.clicked.connect(lambda: self._apply_quick_wallpaper("ubuntu/background.png"))
        btn_q_cyb = QPushButton("💠 Catppuccin")
        btn_q_cyb.setObjectName("secondaryBtn")
        btn_q_cyb.clicked.connect(lambda: self._apply_quick_wallpaper("cyber_glow/background.png"))
        q_grid3.addWidget(btn_q_ubu)
        q_grid3.addWidget(btn_q_cyb)
        layout.addLayout(q_grid3)

        layout.addSpacing(6)

        scale_row = QHBoxLayout()
        scale_lbl = QLabel("Scaling Mode:")
        scale_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.scale_combo = QComboBox()
        self.scale_combo.addItem("Center Crop (Fill)", "crop")
        self.scale_combo.addItem("Fit with Letterbox", "fit")
        self.scale_combo.addItem("Stretch to Resolution", "stretch")
        scale_row.addWidget(scale_lbl)
        scale_row.addWidget(self.scale_combo)
        layout.addLayout(scale_row)

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
        layout.addLayout(dim_row)

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
        layout.addLayout(blur_row)

        solid_row = QHBoxLayout()
        solid_lbl = QLabel("Solid Desktop Color:")
        solid_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.solid_color_picker = ColorPickerButton(self.theme_state.colors.desktop_background)
        solid_row.addWidget(solid_lbl)
        solid_row.addStretch()
        solid_row.addWidget(self.solid_color_picker)
        layout.addLayout(solid_row)

        self.btn_clear_bg = QPushButton("✕ Clear Wallpaper (Use Solid Color)")
        self.btn_clear_bg.setObjectName("secondaryBtn")
        self.btn_clear_bg.clicked.connect(self._clear_wallpaper)
        layout.addWidget(self.btn_clear_bg)

        # Section: All Discovered Theme Assets (Wallpapers, 9-Slices, Frames, Icons)
        layout.addSpacing(10)
        gallery_hdr = QLabel("THEME ASSET GALLERY & ALL FETCHED IMAGES")
        gallery_hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(gallery_hdr)

        self.gallery_status_lbl = QLabel("Scanning theme images...")
        self.gallery_status_lbl.setStyleSheet("color: #6c7086; font-size: 11px; font-style: italic;")
        layout.addWidget(self.gallery_status_lbl)

        self.gallery_container = QWidget()
        self.gallery_layout = QVBoxLayout(self.gallery_container)
        self.gallery_layout.setContentsMargins(0, 0, 0, 0)
        self.gallery_layout.setSpacing(6)
        layout.addWidget(self.gallery_container)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_page_geometry(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        hdr = QLabel("CONTAINER GEOMETRY & ALIGNMENT")
        hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

        self.chk_free_drag = QCheckBox("Enable Interactive Viewport Drag")
        self.chk_free_drag.setStyleSheet("color: #89b4fa; font-weight: 600; font-size: 12px;")
        layout.addWidget(self.chk_free_drag)

        align_lbl = QLabel("Quick Layout Presets:")
        align_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600;")
        layout.addWidget(align_lbl)

        a_row1 = QHBoxLayout()
        btn_cen = QPushButton("Center (Default)")
        btn_cen.setObjectName("secondaryBtn")
        btn_cen.clicked.connect(lambda: self._apply_layout_preset(20.0, 25.0, 60.0, 48.0))
        btn_tl = QPushButton("Top-Left Corner")
        btn_tl.setObjectName("secondaryBtn")
        btn_tl.clicked.connect(lambda: self._apply_layout_preset(6.0, 15.0, 50.0, 50.0))
        a_row1.addWidget(btn_cen)
        a_row1.addWidget(btn_tl)
        layout.addLayout(a_row1)

        a_row2 = QHBoxLayout()
        btn_bot = QPushButton("Bottom Dock")
        btn_bot.setObjectName("secondaryBtn")
        btn_bot.clicked.connect(lambda: self._apply_layout_preset(15.0, 45.0, 70.0, 38.0))
        btn_hero = QPushButton("Wide Hero")
        btn_hero.setObjectName("secondaryBtn")
        btn_hero.clicked.connect(lambda: self._apply_layout_preset(10.0, 20.0, 80.0, 55.0))
        a_row2.addWidget(btn_bot)
        a_row2.addWidget(btn_hero)
        layout.addLayout(a_row2)

        layout.addSpacing(6)

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
            layout.addLayout(r)
            return spin

        self.spin_left = add_spin_row("Left Offset (%):", self.theme_state.menu_left_pct, 0.0, 90.0)
        self.spin_top = add_spin_row("Top Offset (%):", self.theme_state.menu_top_pct, 5.0, 85.0)
        self.spin_width = add_spin_row("Menu Width (%):", self.theme_state.menu_width_pct, 20.0, 95.0)
        self.spin_height = add_spin_row("Menu Height (%):", self.theme_state.menu_height_pct, 20.0, 80.0)

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
        layout.addLayout(pad_row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_page_typography(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        hdr = QLabel("TYPOGRAPHY, COLOR PALETTE & HIGHLIGHTS")
        hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

        f_lbl = QLabel("GRUB Bitmap Font (.pf2):")
        f_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; font-weight: 600;")
        layout.addWidget(f_lbl)

        self.combo_font = QComboBox()
        self._populate_fonts()
        layout.addWidget(self.combo_font)

        self.btn_convert_font = QPushButton("🔤 Convert TrueType/OpenType to .pf2")
        self.btn_convert_font.setObjectName("secondaryBtn")
        self.btn_convert_font.clicked.connect(self._convert_custom_font)
        layout.addWidget(self.btn_convert_font)

        layout.addSpacing(6)

        def add_color_row(title: str, initial_hex: str):
            r = QHBoxLayout()
            lbl = QLabel(title)
            lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
            picker = ColorPickerButton(initial_hex)
            r.addWidget(lbl)
            r.addStretch()
            r.addWidget(picker)
            layout.addLayout(r)
            return picker

        self.col_title = add_color_row("Title Header Color:", self.theme_state.colors.title_color)
        self.col_item = add_color_row("Menu Item Text:", self.theme_state.colors.item_color)
        self.col_selected = add_color_row("Selected Item Text:", self.theme_state.colors.selected_item_color)
        self.col_hl_bg = add_color_row("Highlight Fill:", self.theme_state.colors.highlight_background)
        self.col_hl_border = add_color_row("Highlight Border Glow:", self.theme_state.colors.highlight_border)

        hl_style_row = QHBoxLayout()
        hl_lbl = QLabel("Highlight Box Style:")
        hl_lbl.setStyleSheet("color: #a6adc8; font-size: 11px;")
        self.combo_hl_style = QComboBox()
        self.combo_hl_style.addItem("Custom Soft Gradient", "gradient")
        self.combo_hl_style.addItem("Flat Solid Pill", "flat")
        hl_style_row.addWidget(hl_lbl)
        hl_style_row.addWidget(self.combo_hl_style)
        layout.addLayout(hl_style_row)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

    def _build_page_boot(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        hdr = QLabel("BOOT SEQUENCE, TIMEOUT & DUAL-BOOT")
        hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(hdr)

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
        layout.addLayout(t_row)

        os_lbl = QLabel("Default Boot OS Entry:")
        os_lbl.setStyleSheet("color: #a6adc8; font-size: 11px; margin-top: 4px;")
        layout.addWidget(os_lbl)

        self.combo_default_os = QComboBox()
        for idx, entry in enumerate(self.theme_state.entries):
            self.combo_default_os.addItem(entry, idx)
        layout.addWidget(self.combo_default_os)

        layout.addSpacing(6)

        self.chk_os_prober = QCheckBox("Detect Dual-Boot OSes (os-prober)")
        self.chk_os_prober.setChecked(True)
        self.chk_os_prober.setStyleSheet("color: #89b4fa; font-weight: 600; font-size: 12px; margin-top: 4px;")
        layout.addWidget(self.chk_os_prober)

        self.lbl_os_prober_sub = QLabel("Keep Windows Boot Manager and secondary Linux distributions visible in the GRUB menu.")
        self.lbl_os_prober_sub.setStyleSheet("color: #a6adc8; font-size: 10px; margin-left: 20px;")
        self.lbl_os_prober_sub.setWordWrap(True)
        layout.addWidget(self.lbl_os_prober_sub)

        has_os_prober = StagingManager.check_os_prober_installed()
        self.lbl_prober_warn = QLabel("⚠️ os-prober binary not found. Install it: sudo apt/pacman/dnf install os-prober")
        self.lbl_prober_warn.setStyleSheet("color: #f9e2af; font-size: 10px; margin-left: 20px; font-weight: bold;")
        self.lbl_prober_warn.setVisible(not has_os_prober)
        layout.addWidget(self.lbl_prober_warn)

        layout.addSpacing(12)

        safe_hdr = QLabel("SAFETY & EMERGENCY RESCUE")
        safe_hdr.setStyleSheet("color: #a6adc8; font-weight: 700; font-size: 11px; letter-spacing: 0.5px;")
        layout.addWidget(safe_hdr)

        self.btn_hist = QPushButton("📋 Configuration Snapshot History & Diffs")
        self.btn_hist.setObjectName("secondaryBtn")
        self.btn_hist.clicked.connect(self._show_snapshot_history)
        layout.addWidget(self.btn_hist)

        self.btn_emg = QPushButton("🛡 Standalone Emergency Rescue Script")
        self.btn_emg.setObjectName("dangerBtn")
        self.btn_emg.clicked.connect(self._show_emergency_dialog)
        layout.addWidget(self.btn_emg)

        self.btn_roll = QPushButton("↺ Rollback to Previous Snapshot")
        self.btn_roll.setObjectName("secondaryBtn")
        self.btn_roll.clicked.connect(self._execute_rollback)
        layout.addWidget(self.btn_roll)

        layout.addStretch()
        scroll.setWidget(content)
        return scroll

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

        # Prominent Primary Action Buttons in Viewport
        self.btn_qemu_top = QPushButton("🖥 Test in VM")
        self.btn_qemu_top.setObjectName("secondaryBtn")
        self.btn_qemu_top.setToolTip("Test active theme in virtual QEMU bootloader")
        self.btn_qemu_top.clicked.connect(self._launch_qemu_test)
        t_layout.addWidget(self.btn_qemu_top)

        self.btn_apply_top = QPushButton("⚡ Apply & Rebuild")
        self.btn_apply_top.setObjectName("primaryActionBtn")
        self.btn_apply_top.setToolTip("Stage and deploy theme to host GRUB bootloader")
        self.btn_apply_top.clicked.connect(self._execute_apply_and_rebuild)
        t_layout.addWidget(self.btn_apply_top)

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
        self.drawer.append_log("[*] GRUB Forge Studio v1.0.0 initialized.")
        self.drawer.append_log(f"[*] Target Distribution: {self.telemetry.distro.name} ({self.telemetry.distro.distro_id})")
        self.drawer.append_log(f"[*] /boot Filesystem Topology: {self.telemetry.fs.fstype.upper()} (Mount: {self.telemetry.fs.boot_target})")
        if self.telemetry.fs.is_btrfs:
            self.drawer.append_log(f"[*] Btrfs Subvolume: {self.telemetry.fs.subvolume or 'root'}")
        self.drawer.append_log(f"[*] Active grub.cfg: {self.telemetry.paths.active_grub_cfg}")
        self.drawer.append_log(f"[*] Generator Command: {' '.join(self.telemetry.tools.update_command)}")
        self.drawer.append_log(f"[*] Pre-flight Syntax Tool: {self.telemetry.tools.script_check_tool or 'Internal Linter'}")
        self.drawer.append_log("[✓] Zero-brick guardrails armed: Automated snapshots, atomic updates & emergency rescue ready.")

    # =========================================================================
    # EVENT HANDLERS & QUICK ACTIONS
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

        if hasattr(preset, "title_text") and preset.title_text:
            self.theme_state.title_text = preset.title_text

        if preset.wallpaper_path and preset.wallpaper_path.is_file():
            self.theme_state.theme_source_dir = preset.wallpaper_path.parent
            self.theme_state.all_theme_images = [f for f in sorted(preset.wallpaper_path.parent.glob("*.png")) if f.is_file()]
            self._on_wallpaper_selected(preset.wallpaper_path)
            self.canvas.load_slices_from_dir(preset.wallpaper_path.parent)
        else:
            self.theme_state.theme_source_dir = None
            self.theme_state.all_theme_images = []
            self._clear_wallpaper()

        # Update controls
        self.solid_color_picker.set_color(self.theme_state.colors.desktop_background)
        self.col_title.set_color(self.theme_state.colors.title_color)
        self.col_item.set_color(self.theme_state.colors.item_color)
        self.col_selected.set_color(self.theme_state.colors.selected_item_color)
        self.col_hl_bg.set_color(self.theme_state.colors.highlight_background)
        self.col_hl_border.set_color(self.theme_state.colors.highlight_border)

        self._sync_state_to_canvas()
        self._refresh_artwork_gallery()
        self.drawer.append_log(f"[+] Loaded preset: {preset.name}")

    def _reset_to_custom_blueprint(self):
        for card in self._preset_cards:
            card.set_active(False)
        self._clear_wallpaper()
        self.theme_state.colors = ThemeColors()
        self.theme_state.title_text = "GRUB Boot Menu"
        self.solid_color_picker.set_color(self.theme_state.colors.desktop_background)
        self.col_title.set_color(self.theme_state.colors.title_color)
        self.col_item.set_color(self.theme_state.colors.item_color)
        self.col_selected.set_color(self.theme_state.colors.selected_item_color)
        self.col_hl_bg.set_color(self.theme_state.colors.highlight_background)
        self.col_hl_border.set_color(self.theme_state.colors.highlight_border)
        self._sync_state_to_canvas()
        self.drawer.append_log("[*] Reset to blank custom blueprint.")

    def _on_wallpaper_selected(self, path: Path):
        self.theme_state.wallpaper_path = path
        self.drop_zone.set_file(path)
        self._sync_state_to_canvas()
        self.drawer.append_log(f"[+] Loaded wallpaper artwork: {path.name}")

    def _apply_quick_wallpaper(self, rel_subpath: str):
        p = Path(__file__).resolve().parent.parent / "data" / "themes" / rel_subpath
        if p.is_file():
            self._on_wallpaper_selected(p)
        else:
            self.drawer.append_log(f"[!] Wallpaper not found at: {p}")

    def _clear_wallpaper(self):
        self.theme_state.wallpaper_path = None
        self.drop_zone.set_file(None)
        self._sync_state_to_canvas()
        self.drawer.append_log("[*] Wallpaper cleared. Solid background active.")

    def _refresh_artwork_gallery(self):
        """Renders live visual cards for ALL images discovered in the active theme directory."""
        if not hasattr(self, "gallery_layout"):
            return

        while self.gallery_layout.count() > 0:
            item = self.gallery_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        images = list(self.theme_state.all_theme_images)
        if not images and self.theme_state.theme_source_dir and self.theme_state.theme_source_dir.is_dir():
            for f in sorted(self.theme_state.theme_source_dir.iterdir()):
                if f.is_file() and f.suffix.lower() in (".png", ".jpg", ".jpeg", ".tga"):
                    images.append(f)

        if not images and self.theme_state.wallpaper_path and self.theme_state.wallpaper_path.is_file():
            images = [self.theme_state.wallpaper_path]

        if not images:
            self.gallery_status_lbl.setText("No additional theme images found.")
            return

        self.gallery_status_lbl.setText(f"📸 {len(images)} Theme Assets Fetched from Filesystem:")
        self.gallery_status_lbl.setStyleSheet("color: #a6e3a1; font-weight: 600; font-size: 11px;")

        for img_path in images:
            card = QFrame()
            card.setStyleSheet("background: #181825; border: 1px solid #313244; border-radius: 6px;")
            c_layout = QHBoxLayout(card)
            c_layout.setContentsMargins(8, 6, 8, 6)
            c_layout.setSpacing(10)

            # Mini preview thumbnail
            thumb_lbl = QLabel()
            thumb_lbl.setFixedSize(40, 40)
            thumb_lbl.setStyleSheet("background: #11111b; border-radius: 4px; border: 1px solid #232338;")
            thumb_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            try:
                pix = QPixmap(str(img_path))
                if not pix.isNull():
                    scaled = pix.scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    thumb_lbl.setPixmap(scaled)
            except Exception:
                thumb_lbl.setText("🖼")
            c_layout.addWidget(thumb_lbl)

            # File info
            info_layout = QVBoxLayout()
            info_layout.setSpacing(2)
            name_lbl = QLabel(img_path.name)
            name_lbl.setStyleSheet("color: #cdd6f4; font-weight: 600; font-size: 11px;")

            # Purpose tag
            fn_low = img_path.name.lower()
            if any(k in fn_low for k in ("background", "grub-16x9", "grub-4x3", "desktop")):
                tag = "Wallpaper / Canvas"
            elif any(k in fn_low for k in ("select", "highlight")):
                tag = "Highlight Slice"
            elif any(k in fn_low for k in ("box", "frame", "terminal")):
                tag = "9-Slice Window Frame"
            elif "bar" in fn_low or "progress" in fn_low:
                tag = "Progress Bar Slice"
            elif "icon" in str(img_path).lower():
                tag = "OS Menu Icon"
            else:
                tag = "Theme Asset"

            try:
                sz_kb = round(img_path.stat().st_size / 1024, 1)
                meta_str = f"{tag} • {sz_kb} KB"
            except Exception:
                meta_str = tag

            meta_lbl = QLabel(meta_str)
            meta_lbl.setStyleSheet("color: #a6adc8; font-size: 10px;")
            info_layout.addWidget(name_lbl)
            info_layout.addWidget(meta_lbl)
            c_layout.addLayout(info_layout, stretch=1)

            # Action button
            if any(k in fn_low for k in ("background", "grub", "bg", "wallpaper", "desktop", ".png", ".jpg")):
                btn_set_bg = QPushButton("Set Active")
                btn_set_bg.setObjectName("secondaryBtn")
                btn_set_bg.setFixedHeight(24)
                btn_set_bg.setStyleSheet("font-size: 10px; padding: 2px 8px;")
                btn_set_bg.clicked.connect(lambda checked, p=img_path: self._on_wallpaper_selected(p))
                c_layout.addWidget(btn_set_bg)

            self.gallery_layout.addWidget(card)

    def _apply_layout_preset(self, left: float, top: float, width: float, height: float):
        self.spin_left.setValue(left)
        self.spin_top.setValue(top)
        self.spin_width.setValue(width)
        self.spin_height.setValue(height)
        self._on_geometry_spin_changed()
        self.drawer.append_log(f"[*] Applied layout preset: X={left}%, Y={top}%, W={width}%, H={height}%")

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
        self.canvas.menu_item.state = self.theme_state
        self.canvas.menu_item.update_position()
        self.canvas._scene.update()

    def _on_padding_spacing_changed(self):
        self.theme_state.item_padding = self.spin_padding.value()
        self.theme_state.item_spacing = self.spin_spacing.value()
        self._sync_state_to_canvas()

    def _on_canvas_geometry_synced(self, l_pct, t_pct, w_pct, h_pct):
        self.spin_left.blockSignals(True)
        self.spin_top.blockSignals(True)
        self.spin_left.setValue(l_pct)
        self.spin_top.setValue(t_pct)
        self.spin_left.blockSignals(False)
        self.spin_top.blockSignals(False)

    def _on_canvas_os_selected(self, index: int):
        self.combo_default_os.blockSignals(True)
        self.combo_default_os.setCurrentIndex(index)
        self.combo_default_os.blockSignals(False)

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
        self._sync_state_to_canvas()

    def _on_hl_style_changed(self, index: int):
        self.theme_state.highlight_style = self.combo_hl_style.currentData()
        self._sync_state_to_canvas()

    def _on_timeout_slider_changed(self, val: int):
        self.theme_state.timeout_seconds = val
        self.badge_timeout.setText(f"{val}s")
        self._sync_state_to_canvas()

    def _on_default_os_combo_changed(self, index: int):
        self.theme_state.default_os_index = index
        self._sync_state_to_canvas()

    def _populate_fonts(self):
        self.combo_font.clear()
        fonts = self.font_manager.discover_pf2_fonts()
        for f in fonts:
            self.combo_font.addItem(f"{f.name} (GRUB .pf2)", str(f.path))

    def _convert_custom_font(self):
        ttf_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select TrueType or OpenType Font",
            "",
            "Font Files (*.ttf *.otf);;All Files (*)"
        )
        if not ttf_path:
            return

        src = Path(ttf_path)
        dest_dir = Path.home() / ".cache" / "grub-forge" / "fonts"
        dest_pf2 = dest_dir / f"{src.stem}_16.pf2"
        ok, msg = self.font_manager.convert_ttf_to_pf2(src, dest_pf2, size_pt=16)
        if ok:
            self.drawer.append_log(f"[✓] {msg}")
            self._populate_fonts()
            idx = self.combo_font.findText(f"{src.stem}_16 (GRUB .pf2)")
            if idx >= 0:
                self.combo_font.setCurrentIndex(idx)
            QMessageBox.information(self, "Font Converted", f"Successfully converted {src.name} to GRUB .pf2 format:\n{dest_pf2}")
        else:
            self.drawer.append_log(f"[!] Font conversion failed: {msg}")
            QMessageBox.warning(
                self,
                "Font Conversion",
                f"Could not convert font:\n{msg}\n\nEnsure grub-mkfont or grub2-mkfont is installed."
            )

    def _export_theme_archive(self):
        dest_file, _ = QFileDialog.getSaveFileName(
            self,
            "Export Theme Package",
            str(Path.home() / f"{self.theme_state.title_text.lower().replace(' ', '_')}.tar.gz"),
            "Gzip Tar Archive (*.tar.gz);;Zip Archive (*.zip)"
        )
        if not dest_file:
            return

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
            source_theme_dir=self.theme_state.theme_source_dir,
            dry_run=True
        )

        try:
            exported_path = ThemePackager.export_theme(
                theme_dir=staged_dir / "theme",
                output_archive=Path(dest_file),
                author="GRUB Forge User"
            )
            self.drawer.append_log(f"[✓] Successfully exported theme package to: {exported_path}")
            QMessageBox.information(self, "Export Complete", f"Theme package successfully exported to:\n{exported_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export theme package:\n{e}")

    def _import_theme_archive(self):
        archive_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import GRUB Theme Archive",
            "",
            "Theme Archives (*.tar.gz *.tgz *.zip);;All Files (*)"
        )
        if not archive_path:
            return

        dest_dir = Path.home() / ".cache" / "grub-forge" / "imported_themes"
        ok, disc, msg = ThemePackager.import_theme(Path(archive_path), dest_dir)
        if ok and disc:
            self.drawer.append_log(f"[✓] {msg}")
            card = PresetCard(
                preset_id=disc.id,
                name=disc.name,
                description=f"Imported Theme ({disc.directory.name})",
                primary_color=disc.colors.desktop_background,
                accent_color=disc.colors.highlight_border,
                is_active=True,
                wallpaper_path=disc.wallpaper_path
            )
            card.selected.connect(lambda pid, d=disc: self._on_discovered_theme_selected(d))
            self._preset_cards.append(card)
            self.themes_container_layout.insertWidget(0, card)
            self._on_discovered_theme_selected(disc)
            QMessageBox.information(self, "Theme Imported", f"Successfully imported and activated theme:\n{disc.name}")
        else:
            self.drawer.append_log(f"[!] Theme import failed: {msg}")
            QMessageBox.critical(self, "Import Error", f"Could not import theme:\n{msg}")

    # =========================================================================
    # VIEWPORT TOOLBAR ACTIONS
    # =========================================================================

    def _toggle_preview_playback(self):
        is_playing = self.canvas.toggle_preview_playback()
        if is_playing:
            self.btn_play_preview.setText("⏸ Pause Timer")
            self.drawer.append_log("[*] Simulating boot timeout countdown...")
        else:
            self.btn_play_preview.setText("▶ Play Boot Timer")

    def _reset_preview(self):
        self.canvas.reset_preview()
        self.btn_play_preview.setText("▶ Play Boot Timer")
        self.drawer.append_log("[*] Reset preview canvas state.")

    def _reload_grub_cfg(self):
        self.drawer.append_log("[*] Reloading active boot entries from grub.cfg...")
        entries = GrubMenuParser.parse_entries(
            self.telemetry.paths.active_grub_cfg,
            fallback_distro=self.telemetry.distro.name
        )
        self.theme_state.entries = entries
        self.combo_default_os.clear()
        for idx, entry in enumerate(entries):
            self.combo_default_os.addItem(entry, idx)
        self._sync_state_to_canvas()
        self.drawer.append_log(f"[✓] Loaded {len(entries)} bootloader entries.")

    # =========================================================================
    # ELEVATED EXECUTION PIPELINE & SAFETY ACTIONS
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

        self.theme_state.theme_source_dir = disc.directory
        self.theme_state.all_theme_images = list(disc.all_images)
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

        if disc.directory and disc.directory.is_dir():
            self.canvas.load_slices_from_dir(disc.directory)

        self._sync_state_to_canvas()
        self._refresh_artwork_gallery()
        self.drawer.append_log(f"[+] Loaded installed theme: {disc.name} ({len(disc.all_images)} assets)")

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
            source_theme_dir=self.theme_state.theme_source_dir,
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
                source_theme_dir=self.theme_state.theme_source_dir,
                dry_run=dry_run
            )

            self.drawer.append_log(f"[✓] Payload staged at: {staged_dir}")

            self.drawer.append_log("[*] Phase 2/2: Launching isolated elevated worker...")
            self.executor.apply_staged_theme(staged_dir=staged_dir, dry_run=dry_run)

        except Exception as e:
            self.drawer.set_running_state(False)
            self.drawer.set_status("ERROR", "#f38ba8")
            self.drawer.append_log(f"[!] Staging failed: {e}")
            QMessageBox.critical(self, "Staging Error", f"Failed to prepare staged payload:\n{e}")

    def _on_execution_finished(self, success: bool, message: str):
        self.drawer.set_running_state(False)
        if success:
            self.drawer.set_status("READY", "#a6e3a1")
            self.drawer.append_log(f"\n[✓] Transaction completed successfully: {message}")
            QMessageBox.information(
                self,
                "GRUB Rebuilt Successfully",
                "Your GRUB bootloader configuration and theme were updated.\n\n"
                "A recovery snapshot was archived in /boot/grub/grub_forge_backups/.\n"
                "You can test the changes immediately with 'Test in Virtual Machine' or reboot."
            )
        else:
            self.drawer.set_status("ERROR", "#f38ba8")
            self.drawer.append_log(f"\n[!] Transaction failed: {message}")
            QMessageBox.critical(
                self,
                "Bootloader Update Failed",
                f"An error occurred while updating GRUB:\n\n{message}\n\n"
                "System guardrails automatically engaged. Your previous configuration remains safe."
            )

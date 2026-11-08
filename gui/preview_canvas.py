"""
GRUB Forge - Interactive WYSIWYG Boot Simulator Canvas
Built on QGraphicsView and QGraphicsScene with a virtual resolution coordinate
system, interactive draggable/resizable menu bounding box, smooth aspect ratio
letterboxing, and real-time live preview rendering.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageFilter

from PyQt6.QtCore import (
    Qt, QRectF, QPointF, QTimer, pyqtSignal, QObject
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPixmap, QImage, QPen, QBrush,
    QLinearGradient, QPainterPath, QKeyEvent, QDragEnterEvent,
    QDropEvent
)
from PyQt6.QtWidgets import (
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsObject,
    QStyleOptionGraphicsItem, QWidget, QSizePolicy
)

from backend.theme_engine import ThemeColors


@dataclass
class ThemeState:
    """Central transactional state for the active GRUB visual theme."""
    resolution: Tuple[int, int] = (1920, 1080)
    scale_mode: str = "crop"  # "crop", "fit", "stretch"
    dim_pct: int = 15          # 0 to 80% dimming
    blur_level: int = 0        # 0 to 10 blur
    menu_left_pct: float = 20.0
    menu_top_pct: float = 25.0
    menu_width_pct: float = 60.0
    menu_height_pct: float = 48.0
    item_padding: int = 8
    item_spacing: int = 6
    highlight_style: str = "gradient"  # "flat", "gradient"
    colors: ThemeColors = field(default_factory=ThemeColors)
    title_text: str = "GRUB Boot Menu"
    timeout_seconds: int = 5
    default_os_index: int = 0
    wallpaper_path: Optional[Path] = None
    free_drag: bool = False
    entries: List[str] = field(default_factory=list)


class GrubMenuParser:
    """
    Parses active bootloader entries from grub.cfg.
    """

    @staticmethod
    def parse_entries(cfg_path: Optional[Path], fallback_distro: str = "Linux") -> List[str]:
        entries: List[str] = []
        if cfg_path and cfg_path.is_file():
            try:
                content = cfg_path.read_text(encoding="utf-8", errors="replace")
                pattern = r"menuentry\s+['\"]([^'\"]+)['\"]"
                matches = re.findall(pattern, content)
                for entry in matches:
                    clean = entry.strip()
                    if clean and clean not in entries:
                        entries.append(clean)
            except Exception:
                pass

        if not entries:
            d_name = fallback_distro or "Linux"
            entries = [
                f"{d_name} (linux 6.12.1-default)",
                f"Advanced options for {d_name}",
                f"{d_name} (recovery mode)",
                "UEFI Firmware Settings"
            ]

        return entries


class GrubMenuGraphicItem(QGraphicsObject):
    """
    QGraphicsItem rendering the boot menu container box and OS entries.
    Supports free drag positioning when enabled.
    """
    geometryChanged = pyqtSignal(float, float, float, float)  # left_pct, top_pct, width_pct, height_pct
    entryClicked = pyqtSignal(int)

    def __init__(self, state: ThemeState, parent: Optional[QGraphicsItem] = None):
        super().__init__(parent)
        self.state = state
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self._update_flags()

    def _update_flags(self):
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, self.state.free_drag)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, self.state.free_drag)

    def boundingRect(self) -> QRectF:
        vw, vh = self.state.resolution
        w = (self.state.menu_width_pct / 100.0) * vw
        h = (self.state.menu_height_pct / 100.0) * vh
        return QRectF(0, 0, w, h)

    def update_position(self):
        vw, vh = self.state.resolution
        x = (self.state.menu_left_pct / 100.0) * vw
        y = (self.state.menu_top_pct / 100.0) * vh
        self.setPos(x, y)
        self._update_flags()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and self.state.free_drag:
            new_pos = value
            vw, vh = self.state.resolution
            left_pct = max(0.0, min(100.0, (new_pos.x() / vw) * 100.0))
            top_pct = max(0.0, min(100.0, (new_pos.y() / vh) * 100.0))
            self.geometryChanged.emit(left_pct, top_pct, self.state.menu_width_pct, self.state.menu_height_pct)
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None):
        rect = self.boundingRect()
        vw, vh = self.state.resolution
        scale_ref = vw / 1920.0

        # Draw Menu Box Container
        menu_bg = QColor(24, 24, 37, 215)
        border_col = QColor(self.state.colors.menu_box_border)
        painter.setPen(QPen(border_col, 1.5))
        painter.setBrush(QBrush(menu_bg))
        painter.drawRoundedRect(rect, 8 * scale_ref, 8 * scale_ref)

        if self.state.free_drag:
            # Draw draggable indicator border
            painter.setPen(QPen(QColor("#89b4fa"), 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect, 8 * scale_ref, 8 * scale_ref)

        # Draw Entries
        entries = self.state.entries or ["No Bootloader Entries Found"]
        padding = self.state.item_padding * scale_ref
        spacing = self.state.item_spacing * scale_ref
        item_h = 36 * scale_ref

        start_y = 12 * scale_ref
        font_size = max(10, int(15 * scale_ref))
        item_font = QFont("Unifont", font_size, QFont.Weight.Normal)
        selected_font = QFont("Unifont", font_size, QFont.Weight.Bold)

        # Check for slice pixmaps from parent view if available
        canvas_view: Optional[BootPreviewCanvas] = self.scene().views()[0] if self.scene() and self.scene().views() else None
        hl_w = canvas_view._slice_hl_w if canvas_view else None
        hl_c = canvas_view._slice_hl_c if canvas_view else None
        hl_e = canvas_view._slice_hl_e if canvas_view else None

        for idx, entry_text in enumerate(entries):
            item_y = start_y + (idx * (item_h + spacing))
            if item_y + item_h > rect.height() - (8 * scale_ref):
                break

            entry_rect = QRectF(padding, item_y, rect.width() - (padding * 2), item_h)
            is_selected = (idx == self.state.default_os_index)

            if is_selected:
                if hl_w and hl_c and hl_e and not hl_w.isNull():
                    # Authentic GRUB2 3-slice bitmap highlight rendering
                    cap_w = hl_w.width() * scale_ref
                    # Left cap
                    painter.drawPixmap(QRectF(entry_rect.x(), entry_rect.y(), cap_w, entry_rect.height()).toRect(), hl_w)
                    # Center stretched
                    mid_w = max(0.0, entry_rect.width() - (cap_w * 2))
                    painter.drawPixmap(QRectF(entry_rect.x() + cap_w, entry_rect.y(), mid_w, entry_rect.height()).toRect(), hl_c)
                    # Right cap
                    painter.drawPixmap(QRectF(entry_rect.right() - cap_w, entry_rect.y(), cap_w, entry_rect.height()).toRect(), hl_e)
                else:
                    # Clean Catppuccin vector fallback
                    hl_path = QPainterPath()
                    hl_path.addRoundedRect(entry_rect, 6 * scale_ref, 6 * scale_ref)

                    if self.state.highlight_style == "gradient":
                        grad = QLinearGradient(entry_rect.topLeft(), entry_rect.bottomLeft())
                        grad.setColorAt(0, QColor(self.state.colors.highlight_background).lighter(115))
                        grad.setColorAt(1, QColor(self.state.colors.highlight_background))
                        painter.setBrush(QBrush(grad))
                    else:
                        painter.setBrush(QBrush(QColor(self.state.colors.highlight_background)))

                    painter.setPen(QPen(QColor(self.state.colors.highlight_border), 1.5))
                    painter.drawPath(hl_path)

                painter.setFont(selected_font)
                painter.setPen(QColor(self.state.colors.selected_item_color))
            else:
                painter.setFont(item_font)
                painter.setPen(QColor(self.state.colors.item_color))

            # Distro Icon Rendering (Kali, Arch, Debian, Fedora, Ubuntu, Windows, Linux)
            icon_pix = canvas_view.get_distro_icon(entry_text) if canvas_view else None
            text_x_offset = 14 * scale_ref
            if icon_pix and not icon_pix.isNull():
                icon_size = max(16, int(22 * scale_ref))
                icon_y = entry_rect.y() + (entry_rect.height() - icon_size) / 2.0
                icon_rect = QRectF(entry_rect.x() + (12 * scale_ref), icon_y, icon_size, icon_size)
                painter.drawPixmap(icon_rect.toRect(), icon_pix)
                text_x_offset = (12 * scale_ref) + icon_size + (10 * scale_ref)

            # Entry label text
            text_rect = QRectF(entry_rect.x() + text_x_offset, entry_rect.y(), entry_rect.width() - text_x_offset - (10 * scale_ref), entry_rect.height())
            metrics = painter.fontMetrics()
            elided = metrics.elidedText(entry_text, Qt.TextElideMode.ElideRight, int(text_rect.width()))
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, elided)


class BootPreviewCanvas(QGraphicsView):
    """
    Central Viewport QGraphicsView simulating the GRUB bootloader runtime screen.
    Maintains virtual aspect ratio and handles drop & keyboard navigation.
    """
    fileDropped = pyqtSignal(Path)
    geometrySyncRequested = pyqtSignal(float, float, float, float)
    osSelectionChanged = pyqtSignal(int)

    def __init__(self, parent: Optional[QWidget] = None, resolution: Optional[Tuple[int, int]] = None):
        super().__init__(parent)
        self.state = ThemeState()
        if resolution:
            self.state.resolution = resolution
        self.setAcceptDrops(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing |
            QPainter.RenderHint.SmoothPixmapTransform |
            QPainter.RenderHint.TextAntialiasing
        )
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background-color: #0c0c14; border: none;")

        # Virtual Scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Menu Box Graphics Item
        self.menu_item = GrubMenuGraphicItem(self.state)
        self.menu_item.geometryChanged.connect(self._on_item_geometry_changed)
        self._scene.addItem(self.menu_item)

        # Wallpaper Cache
        self._cached_bg_pixmap: Optional[QPixmap] = None
        self._cached_raw_img: Optional[Image.Image] = None

        # Distro icons cache
        self._distro_icons: dict[str, QPixmap] = {}
        self._load_distro_icons()

        # Authentic GRUB Bitmap Slices
        self._slice_hl_w: Optional[QPixmap] = None
        self._slice_hl_c: Optional[QPixmap] = None
        self._slice_hl_e: Optional[QPixmap] = None
        self._slice_bar_w: Optional[QPixmap] = None
        self._slice_bar_c: Optional[QPixmap] = None
        self._slice_bar_e: Optional[QPixmap] = None

        # Timeout Animation Simulation
        self.timeout_remaining = self.state.timeout_seconds
        self.is_preview_playing = False
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(100)
        self._anim_timer.timeout.connect(self._on_anim_tick)
        self._elapsed_ms = 0

        self.apply_state(self.state)

    def _load_distro_icons(self):
        icons_dir = Path(__file__).resolve().parent.parent / "data" / "icons" / "distros"
        if icons_dir.is_dir():
            for p in icons_dir.glob("*.png"):
                pix = QPixmap(str(p))
                if not pix.isNull():
                    self._distro_icons[p.stem.lower()] = pix

    def get_distro_icon(self, entry_text: str) -> Optional[QPixmap]:
        t = entry_text.lower()
        if "kali" in t:
            return self._distro_icons.get("kali")
        elif "arch" in t:
            return self._distro_icons.get("arch")
        elif "debian" in t:
            return self._distro_icons.get("debian")
        elif "fedora" in t:
            return self._distro_icons.get("fedora")
        elif "ubuntu" in t:
            return self._distro_icons.get("ubuntu")
        elif "windows" in t:
            return self._distro_icons.get("windows")
        elif any(k in t for k in ("uefi", "firmware", "setup", "settings", "bios")):
            return self._distro_icons.get("gear")
        return self._distro_icons.get("linux")

    def load_slices_from_dir(self, theme_dir: Path):
        """Loads optional GRUB bitmap slices for highlights and progress bars."""
        if not theme_dir.is_dir():
            return

        # Slices for highlights
        for name_prefix in ("highlight", "select"):
            w_file = theme_dir / f"{name_prefix}_w.png"
            c_file = theme_dir / f"{name_prefix}_c.png"
            e_file = theme_dir / f"{name_prefix}_e.png"
            if w_file.is_file() and c_file.is_file() and e_file.is_file():
                self._slice_hl_w = QPixmap(str(w_file))
                self._slice_hl_c = QPixmap(str(c_file))
                self._slice_hl_e = QPixmap(str(e_file))
                break

        # Slices for progress bar
        bw_file = theme_dir / "bar_w.png"
        bc_file = theme_dir / "bar_c.png"
        be_file = theme_dir / "bar_e.png"
        if bw_file.is_file() and bc_file.is_file() and be_file.is_file():
            self._slice_bar_w = QPixmap(str(bw_file))
            self._slice_bar_c = QPixmap(str(bc_file))
            self._slice_bar_e = QPixmap(str(be_file))
        self._scene.update()

    def apply_state(self, new_state: ThemeState):
        """Applies updated ThemeState and triggers scene redraw."""
        self.state = new_state
        vw, vh = self.state.resolution
        self._scene.setSceneRect(0, 0, vw, vh)

        # Reload wallpaper if changed
        if self.state.wallpaper_path and self.state.wallpaper_path.is_file():
            self._process_wallpaper(self.state.wallpaper_path)
        else:
            self._cached_bg_pixmap = None
            self._cached_raw_img = None

        self.menu_item.state = self.state
        self.menu_item.update_position()
        self.fit_virtual_canvas()
        self._scene.update()

    def _process_wallpaper(self, path: Path):
        """Loads and applies blur/dim effects onto the virtual resolution background."""
        try:
            with Image.open(path) as img:
                img = img.convert("RGB")
                target_w, target_h = self.state.resolution
                src_w, src_h = img.size

                # Scale Modes
                if self.state.scale_mode == "stretch":
                    resized = img.resize((target_w, target_h), Image.Resampling.BILINEAR)
                elif self.state.scale_mode == "fit":
                    # Letterbox within target
                    scale = min(target_w / src_w, target_h / src_h)
                    nw, nh = int(src_w * scale), int(src_h * scale)
                    scaled = img.resize((nw, nh), Image.Resampling.BILINEAR)
                    resized = Image.new("RGB", (target_w, target_h), (17, 17, 27))
                    ox, oy = (target_w - nw) // 2, (target_h - nh) // 2
                    resized.paste(scaled, (ox, oy))
                else:  # Center Crop (default)
                    scale = max(target_w / src_w, target_h / src_h)
                    nw, nh = int(src_w * scale), int(src_h * scale)
                    scaled = img.resize((nw, nh), Image.Resampling.BILINEAR)
                    ox, oy = (nw - target_w) // 2, (nh - target_h) // 2
                    resized = scaled.crop((ox, oy, ox + target_w, oy + target_h))

                # Apply fast blur if requested
                if self.state.blur_level > 0:
                    resized = resized.filter(ImageFilter.GaussianBlur(radius=self.state.blur_level))

                # Convert to QPixmap
                data = resized.tobytes("raw", "RGB")
                qimg = QImage(data, target_w, target_h, 3 * target_w, QImage.Format.Format_RGB888)
                self._cached_bg_pixmap = QPixmap.fromImage(qimg)
        except Exception:
            self._cached_bg_pixmap = None

    def fit_virtual_canvas(self):
        """Scales virtual canvas to fit within viewport while preserving aspect ratio."""
        if self.width() <= 0 or self.height() <= 0:
            return
        vw, vh = self.state.resolution
        self.fitInView(0, 0, vw, vh, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.fit_virtual_canvas()

    def drawBackground(self, painter: QPainter, rect: QRectF):
        """Draws virtual canvas background, title, and bottom timeout bar."""
        vw, vh = self.state.resolution
        canvas_rect = QRectF(0, 0, vw, vh)
        scale_ref = vw / 1920.0

        # 1. Base Layer (Wallpaper or Solid)
        if self._cached_bg_pixmap and not self._cached_bg_pixmap.isNull():
            painter.drawPixmap(canvas_rect.toRect(), self._cached_bg_pixmap)
        else:
            painter.fillRect(canvas_rect, QColor(self.state.colors.desktop_background))

        # 2. Dimming Overlay
        if self.state.dim_pct > 0:
            alpha = int((self.state.dim_pct / 100.0) * 255)
            painter.fillRect(canvas_rect, QColor(0, 0, 0, alpha))

        # 3. Title Header
        title_size = max(12, int(22 * scale_ref))
        painter.setFont(QFont("Unifont", title_size, QFont.Weight.Bold))
        painter.setPen(QColor(self.state.colors.title_color))
        title_y = vh * 0.12
        painter.drawText(QRectF(0, title_y, vw, 40 * scale_ref), Qt.AlignmentFlag.AlignCenter, self.state.title_text)

        # 4. Timeout Countdown Label & Progress Bar
        bar_w = (self.state.menu_width_pct / 100.0) * vw * 0.7
        bar_h = 6 * scale_ref
        bar_x = (vw - bar_w) / 2
        bar_y = vh * 0.82

        label_font = QFont("Unifont", max(9, int(13 * scale_ref)))
        painter.setFont(label_font)
        painter.setPen(QColor(self.state.colors.timeout_color))

        if self.is_preview_playing and self.timeout_remaining > 0:
            msg = f"The highlighted entry will be executed automatically in {int(self.timeout_remaining)}s."
        elif self.timeout_remaining <= 0:
            msg = "Booting selected operating system..."
        else:
            msg = f"The highlighted entry will be executed automatically in {self.state.timeout_seconds}s."

        painter.drawText(QRectF(0, bar_y - (24 * scale_ref), vw, 20 * scale_ref), Qt.AlignmentFlag.AlignCenter, msg)

        # Progress bar track
        painter.fillRect(QRectF(bar_x, bar_y, bar_w, bar_h), QColor("#313244"))
        # Progress bar fill (Slice or Vector)
        if self.state.timeout_seconds > 0:
            fill_pct = max(0.0, min(1.0, self.timeout_remaining / self.state.timeout_seconds))
            fill_width = bar_w * fill_pct

            if self._slice_bar_w and self._slice_bar_c and self._slice_bar_e and not self._slice_bar_w.isNull() and fill_width > 4:
                # 3-slice bitmap progress bar
                cap_w = self._slice_bar_w.width() * scale_ref
                # West cap
                painter.drawPixmap(QRectF(bar_x, bar_y, cap_w, bar_h).toRect(), self._slice_bar_w)
                # Center stretch
                center_w = max(0.0, fill_width - (cap_w * 2))
                if center_w > 0:
                    painter.drawPixmap(QRectF(bar_x + cap_w, bar_y, center_w, bar_h).toRect(), self._slice_bar_c)
                # East cap
                painter.drawPixmap(QRectF(bar_x + cap_w + center_w, bar_y, cap_w, bar_h).toRect(), self._slice_bar_e)
            else:
                # Vector fallback
                painter.fillRect(QRectF(bar_x, bar_y, fill_width, bar_h), QColor(self.state.colors.highlight_border))

        # 5. Hotkey hint footer
        footer_font = QFont("Unifont", max(8, int(11 * scale_ref)))
        painter.setFont(footer_font)
        painter.setPen(QColor("#6c7086"))
        painter.drawText(
            QRectF(0, vh - (32 * scale_ref), vw, 20 * scale_ref),
            Qt.AlignmentFlag.AlignCenter,
            "Use the ↑ and ↓ keys to select an option, then press Enter to boot. Press 'e' to edit, 'c' for command line."
        )

    def _on_item_geometry_changed(self, l_pct, t_pct, w_pct, h_pct):
        self.state.menu_left_pct = l_pct
        self.state.menu_top_pct = t_pct
        self.geometrySyncRequested.emit(l_pct, t_pct, w_pct, h_pct)

    # ---------------- Interactions & Preview Play ----------------

    def toggle_preview_playback(self) -> bool:
        self.is_preview_playing = not self.is_preview_playing
        if self.is_preview_playing:
            self.timeout_remaining = float(self.state.timeout_seconds)
            self._elapsed_ms = 0
            self._anim_timer.start()
        else:
            self._anim_timer.stop()
            self.timeout_remaining = float(self.state.timeout_seconds)
            self._scene.update()
        return self.is_preview_playing

    def reset_preview(self):
        self.timeout_remaining = float(self.state.timeout_seconds)
        self._elapsed_ms = 0
        self._scene.update()

    def _on_anim_tick(self):
        if self.is_preview_playing and self.timeout_remaining > 0:
            self.timeout_remaining -= 0.1
            if self.timeout_remaining <= 0:
                self.timeout_remaining = 0.0
                QTimer.singleShot(1500, self.reset_preview)
            self._scene.update()

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        count = len(self.state.entries)
        if count == 0:
            super().keyPressEvent(event)
            return

        if key in (Qt.Key.Key_Up, Qt.Key.Key_K):
            self.state.default_os_index = (self.state.default_os_index - 1) % count
            self.reset_preview()
            self.osSelectionChanged.emit(self.state.default_os_index)
            self._scene.update()
        elif key in (Qt.Key.Key_Down, Qt.Key.Key_J):
            self.state.default_os_index = (self.state.default_os_index + 1) % count
            self.reset_preview()
            self.osSelectionChanged.emit(self.state.default_os_index)
            self._scene.update()
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.timeout_remaining = 0
            self._scene.update()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                ext = Path(url.toLocalFile()).suffix.lower()
                if ext in {".png", ".jpg", ".jpeg", ".tga"}:
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                p = Path(url.toLocalFile())
                if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".tga"} and p.is_file():
                    self.fileDropped.emit(p)
                    event.acceptProposedAction()
                    return
        event.ignore()

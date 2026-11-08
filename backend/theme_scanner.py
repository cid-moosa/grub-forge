"""
GRUB Forge - Theme Discovery & Metadata Scanner
Discovers installed GRUB themes across system directories (/boot/grub/themes/,
/boot/grub2/themes/, /usr/share/grub/themes/), parses theme.txt specifications,
and extracts visual attributes and thumbnails.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
from PIL import Image

from backend.theme_engine import ThemeColors, ThemePreset


@dataclass
class DiscoveredTheme:
    id: str
    name: str
    directory: Path
    theme_txt: Path
    colors: ThemeColors
    wallpaper_path: Optional[Path] = None
    thumbnail_path: Optional[Path] = None
    is_system: bool = True
    author: str = "System"
    title_text: str = "GRUB Boot Menu"


class ThemeScanner:
    """
    Scans host filesystem for existing GRUB themes and parses their definitions.
    """

    DEFAULT_THEME_PATHS = [
        Path("/boot/grub/themes"),
        Path("/boot/grub2/themes"),
        Path("/usr/share/grub/themes"),
        Path("/usr/local/share/grub/themes"),
    ]

    def __init__(self, search_paths: Optional[List[Path]] = None, root_prefix: str = ""):
        self.root_prefix = root_prefix
        if search_paths:
            self.search_paths = search_paths
        else:
            self.search_paths = [self._apply_prefix(p) for p in self.DEFAULT_THEME_PATHS]

    def _apply_prefix(self, p: Path) -> Path:
        if not self.root_prefix:
            return p
        clean = str(p).lstrip("/\\")
        return Path(self.root_prefix) / clean

    def scan_installed_themes(self) -> List[DiscoveredTheme]:
        """Scans all configured theme root paths and returns parsed DiscoveredTheme items."""
        discovered: Dict[str, DiscoveredTheme] = {}

        for root in self.search_paths:
            if not root.is_dir():
                continue

            try:
                for entry in root.iterdir():
                    if entry.is_dir():
                        theme_file = entry / "theme.txt"
                        if theme_file.is_file():
                            theme_id = entry.name.lower()
                            if theme_id not in discovered:
                                parsed = self.parse_theme_txt(entry, theme_file)
                                if parsed:
                                    discovered[theme_id] = parsed
            except Exception:
                pass

        return list(discovered.values())

    def parse_theme_txt(self, theme_dir: Path, theme_txt: Path) -> Optional[DiscoveredTheme]:
        """Parses key attributes from a GRUB theme.txt file."""
        try:
            content = theme_txt.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return None

        # Extract basic global properties
        title_text = "GRUB Boot Menu"
        desktop_img_name = None
        desktop_color = "#1e1e2e"
        title_color = "#cdd6f4"
        item_color = "#a6adc8"
        selected_item_color = "#ffffff"
        highlight_bg = "#313244"
        highlight_border = "#89b4fa"

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ":" in line and not line.startswith("+"):
                k, v = line.split(":", 1)
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                if k == "title-text":
                    title_text = v
                elif k == "desktop-image":
                    desktop_img_name = v
                elif k == "desktop-color":
                    desktop_color = v
                elif k == "title-color":
                    title_color = v
            elif "=" in line:
                k, v = line.split("=", 1)
                k = k.strip().lower()
                v = v.strip().strip('"').strip("'")
                if k == "item_color":
                    item_color = v
                elif k == "selected_item_color":
                    selected_item_color = v

        wallpaper_path = None
        if desktop_img_name:
            cand = theme_dir / desktop_img_name
            if cand.is_file():
                wallpaper_path = cand
        if not wallpaper_path:
            # Fallback search for common names
            for name in ("background.png", "background.jpg", "bg.png", "bg.jpg"):
                cand = theme_dir / name
                if cand.is_file():
                    wallpaper_path = cand
                    break

        colors = ThemeColors(
            desktop_background=desktop_color if desktop_color.startswith("#") else "#1e1e2e",
            title_color=title_color if title_color.startswith("#") else "#cdd6f4",
            item_color=item_color if item_color.startswith("#") else "#a6adc8",
            selected_item_color=selected_item_color if selected_item_color.startswith("#") else "#ffffff",
            highlight_background=highlight_bg,
            highlight_border=highlight_border
        )

        display_name = theme_dir.name.replace("_", " ").replace("-", " ").title()

        return DiscoveredTheme(
            id=theme_dir.name,
            name=display_name,
            directory=theme_dir,
            theme_txt=theme_txt,
            colors=colors,
            wallpaper_path=wallpaper_path,
            title_text=title_text
        )

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
            if not line or line.startswith("#") or line.startswith("+") or line.startswith("}"):
                continue

            delimiter = ":" if ":" in line else ("=" if "=" in line else None)
            if delimiter:
                k, v = line.split(delimiter, 1)
                k = k.strip().lower().replace("-", "_")
                v = v.strip().strip('"').strip("'")
                if k in ("title_text", "title"):
                    title_text = v
                elif k in ("desktop_image", "desktop_image_path"):
                    desktop_img_name = v
                elif k == "desktop_color":
                    desktop_color = v
                elif k == "title_color":
                    title_color = v
                elif k == "item_color":
                    item_color = v
                elif k in ("selected_item_color", "selected_color"):
                    selected_item_color = v

        wallpaper_path = None
        if desktop_img_name:
            cand = theme_dir / desktop_img_name
            if cand.is_file():
                wallpaper_path = cand
            else:
                # Case-insensitive lookup
                for f in theme_dir.iterdir():
                    if f.name.lower() == desktop_img_name.lower() and f.is_file():
                        wallpaper_path = f
                        break

        if not wallpaper_path:
            # Fallback search for common background image filenames
            for pattern in ("*background*", "*bg*", "*wallpaper*", "*.png", "*.jpg", "*.jpeg", "*.tga"):
                matches = [f for f in theme_dir.glob(pattern) if f.is_file() and not f.name.startswith("bar_") and not f.name.startswith("highlight_") and not f.name.startswith("select_")]
                if matches:
                    wallpaper_path = matches[0]
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

    def detect_active_system_theme(
        self,
        default_grub_path: Optional[Path] = None,
        distro_id: str = ""
    ) -> Optional[DiscoveredTheme]:
        """
        Fetches the current active GRUB boot theme from the system files:
        1. Checks GRUB_THEME or GRUB_BACKGROUND in /etc/default/grub.
        2. Scans system theme directories (/boot/grub/themes, /usr/share/grub/themes) for distro themes.
        3. Returns the active theme with its real background image, colors, and layout.
        """
        # 1. Inspect /etc/default/grub for GRUB_THEME
        if default_grub_path and default_grub_path.is_file():
            try:
                content = default_grub_path.read_text(encoding="utf-8", errors="replace")
                theme_val = None
                bg_val = None
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith("#"):
                        continue
                    if line.startswith("GRUB_THEME=") or line.startswith("GRUB_THEME "):
                        _, val = line.split("=", 1)
                        theme_val = val.strip().strip('"').strip("'")
                    elif line.startswith("GRUB_BACKGROUND=") or line.startswith("GRUB_BACKGROUND "):
                        _, val = line.split("=", 1)
                        bg_val = val.strip().strip('"').strip("'")

                if theme_val:
                    t_path = self._apply_prefix(Path(theme_val))
                    if t_path.is_file():
                        theme = self.parse_theme_txt(t_path.parent, t_path)
                        if theme:
                            theme.name = f"{theme.name} (Active System Theme)"
                            return theme
                    elif t_path.is_dir() and (t_path / "theme.txt").is_file():
                        theme = self.parse_theme_txt(t_path, t_path / "theme.txt")
                        if theme:
                            theme.name = f"{theme.name} (Active System Theme)"
                            return theme

                if bg_val:
                    b_path = self._apply_prefix(Path(bg_val))
                    if b_path.is_file():
                        return DiscoveredTheme(
                            id="custom_background",
                            name="Current GRUB Background",
                            directory=b_path.parent,
                            theme_txt=b_path.parent / "theme.txt",
                            colors=ThemeColors(),
                            wallpaper_path=b_path,
                            title_text="GRUB Boot Menu"
                        )
            except Exception:
                pass

        # 2. Check installed distro themes in search paths
        installed = self.scan_installed_themes()
        if installed:
            d_clean = (distro_id or "").lower()
            if d_clean:
                # Look for matching distro theme first (e.g. kali, arch, debian, fedora)
                for t in installed:
                    t_id = t.id.lower()
                    if d_clean in t_id or t_id in d_clean:
                        t.name = f"{t.name} (Installed Distro Theme)"
                        return t

            # Fallback to the first installed theme found on disk
            first_theme = installed[0]
            first_theme.name = f"{first_theme.name} (Installed Theme)"
            return first_theme

        # 3. Fallback to bundled authentic distro assets in data/themes
        bundled_dir = Path(__file__).resolve().parent.parent / "data" / "themes"
        d_key = distro_id.lower() if distro_id else "kali"
        target_dir = bundled_dir / d_key
        if not target_dir.is_dir():
            target_dir = bundled_dir / "kali"

        bg_file = target_dir / "background.png"
        if bg_file.is_file():
            from backend.theme_engine import PRESETS
            preset = PRESETS.get(f"{d_key}_dragon") or PRESETS.get(f"{d_key}_minimal") or PRESETS.get(f"{d_key}_blue") or PRESETS.get("kali_dragon")
            colors = preset.colors if preset else ThemeColors()
            title_text = preset.title_text if preset else f"{d_key.capitalize()} Linux"
            return DiscoveredTheme(
                id=f"{d_key}_default",
                name=f"{d_key.capitalize()} Boot Theme",
                directory=target_dir,
                theme_txt=target_dir / "theme.txt",
                colors=colors,
                wallpaper_path=bg_file,
                title_text=title_text
            )

        return None

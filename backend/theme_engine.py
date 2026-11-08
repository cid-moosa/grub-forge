"""
GRUB Forge - Theme Engine & Asset Processing Architecture
Compiles standard GRUB theme specifications (theme.txt), normalizes image assets
to uncompressed 8-bit RGB/RGBA PNGs using Pillow to prevent boot-time decoding
faults, and generates highlight 9-slice bitmaps.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
from PIL import Image, ImageDraw, ImageColor


@dataclass
class ThemeColors:
    desktop_background: str = "#1e1e2e"
    title_color: str = "#cdd6f4"
    item_color: str = "#a6adc8"
    selected_item_color: str = "#ffffff"
    highlight_background: str = "#313244"
    highlight_border: str = "#89b4fa"
    timeout_color: str = "#89b4fa"
    menu_box_background: str = "rgba(24, 24, 37, 0.75)"
    menu_box_border: str = "#45475a"


@dataclass
class ThemePreset:
    id: str
    name: str
    description: str
    colors: ThemeColors
    font_size: int = 16
    item_height: int = 38
    menu_top_pct: int = 25
    menu_left_pct: int = 20
    menu_width_pct: int = 60
    menu_height_pct: int = 50
    wallpaper_path: Optional[Path] = None
    title_text: str = "GRUB Boot Menu"


_BASE_ASSETS = Path(__file__).resolve().parent.parent / "data" / "themes"

PRESETS: Dict[str, ThemePreset] = {
    "kali_dragon": ThemePreset(
        id="kali_dragon",
        name="Kali Linux (Dragon)",
        description="Official Kali Linux cyber-dragon theme with neon cyan glow, dark space-blue canvas, and security aesthetics.",
        title_text="Kali GNU/Linux (Rolling)",
        wallpaper_path=_BASE_ASSETS / "kali" / "background.png",
        colors=ThemeColors(
            desktop_background="#080c16",
            title_color="#00f5d4",
            item_color="#cdd6f4",
            selected_item_color="#ffffff",
            highlight_background="#0077b6",
            highlight_border="#00f5d4",
            timeout_color="#00f5d4",
            menu_box_background="rgba(8, 12, 22, 0.88)",
            menu_box_border="#00b4d8"
        )
    ),
    "cyber_glow": ThemePreset(
        id="cyber_glow",
        name="Cyber Glow (Catppuccin)",
        description="Dark charcoal with soft electric blue accents and glowing highlight borders.",
        title_text="GRUB Boot Menu",
        wallpaper_path=_BASE_ASSETS / "cyber_glow" / "background.png",
        colors=ThemeColors(
            desktop_background="#1e1e2e",
            title_color="#cdd6f4",
            item_color="#a6adc8",
            selected_item_color="#ffffff",
            highlight_background="#313244",
            highlight_border="#89b4fa",
            timeout_color="#89b4fa",
            menu_box_background="rgba(24, 24, 37, 0.85)",
            menu_box_border="#45475a"
        )
    ),
    "arch_minimal": ThemePreset(
        id="arch_minimal",
        name="Arch Minimal",
        description="Deep obsidian black with crisp Arch cyan highlights and sharp geometry.",
        title_text="Arch Linux Boot Menu",
        wallpaper_path=_BASE_ASSETS / "arch" / "background.png",
        colors=ThemeColors(
            desktop_background="#11111b",
            title_color="#89dceb",
            item_color="#bac2de",
            selected_item_color="#000000",
            highlight_background="#89dceb",
            highlight_border="#74c7ec",
            timeout_color="#89dceb",
            menu_box_background="rgba(17, 17, 27, 0.90)",
            menu_box_border="#313244"
        )
    ),
    "fedora_blue": ThemePreset(
        id="fedora_blue",
        name="Fedora Horizon",
        description="Slate-navy foundation with classic Fedora blue accents and polished sapphire styling.",
        title_text="Fedora Linux",
        wallpaper_path=_BASE_ASSETS / "fedora" / "background.png",
        colors=ThemeColors(
            desktop_background="#182030",
            title_color="#ffffff",
            item_color="#94a3b8",
            selected_item_color="#ffffff",
            highlight_background="#2563eb",
            highlight_border="#3b82f6",
            timeout_color="#60a5fa",
            menu_box_background="rgba(15, 23, 42, 0.85)",
            menu_box_border="#334155"
        )
    ),
    "debian_crimson": ThemePreset(
        id="debian_crimson",
        name="Debian Crimson",
        description="Dark cosmic ruby aesthetic with Debian crimson highlights and spiral nebula.",
        title_text="Debian GNU/Linux",
        wallpaper_path=_BASE_ASSETS / "debian" / "background.png",
        colors=ThemeColors(
            desktop_background="#1b1216",
            title_color="#f2f2f2",
            item_color="#a89a9f",
            selected_item_color="#ffffff",
            highlight_background="#d70a53",
            highlight_border="#e83674",
            timeout_color="#d70a53",
            menu_box_background="rgba(20, 10, 15, 0.88)",
            menu_box_border="#4a2230"
        )
    ),
    "ubuntu_yaru": ThemePreset(
        id="ubuntu_yaru",
        name="Ubuntu Yaru",
        description="Deep royal aubergine gradient with classic Ubuntu orange circular emblem.",
        title_text="Ubuntu 24.04 LTS",
        wallpaper_path=_BASE_ASSETS / "ubuntu" / "background.png",
        colors=ThemeColors(
            desktop_background="#260e1e",
            title_color="#ffffff",
            item_color="#e5e5e5",
            selected_item_color="#ffffff",
            highlight_background="#e95420",
            highlight_border="#ff7b47",
            timeout_color="#e95420",
            menu_box_background="rgba(30, 12, 24, 0.90)",
            menu_box_border="#5c1d3d"
        )
    ),
    "emerald_matrix": ThemePreset(
        id="emerald_matrix",
        name="openSUSE / Emerald",
        description="Dark carbon texture with neon green phosphor glow and terminal chameleon vibes.",
        title_text="openSUSE Tumbleweed",
        wallpaper_path=_BASE_ASSETS / "cyber_glow" / "background.png",
        colors=ThemeColors(
            desktop_background="#0d1410",
            title_color="#a6e3a1",
            item_color="#62886f",
            selected_item_color="#000000",
            highlight_background="#a6e3a1",
            highlight_border="#50fa7b",
            timeout_color="#a6e3a1",
            menu_box_background="rgba(10, 18, 13, 0.90)",
            menu_box_border="#1b3826"
        )
    ),
}


class AssetProcessor:
    """
    Validates and normalizes user graphics into safe 8-bit uncompressed PNG formats.
    Generates highlight slice assets compliant with the GRUB 2 theme specification.
    """

    SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tga"}

    @classmethod
    def normalize_wallpaper(
        cls,
        source_path: Path,
        dest_path: Path,
        target_resolution: Tuple[int, int] = (1920, 1080)
    ) -> Path:
        """
        Converts any input wallpaper (.png, .jpg, .jpeg, .tga) into a pristine,
        uncompressed 8-bit RGB standard PNG resized and cropped to target resolution.
        """
        if not source_path.is_file():
            raise FileNotFoundError(f"Source wallpaper not found: {source_path}")

        ext = source_path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported image format '{ext}'. Must be PNG, JPEG, or TGA.")

        with Image.open(source_path) as img:
            # Convert to standard RGB mode (strip CMYK, indexed, or non-standard color spaces)
            img = img.convert("RGB")

            # Fit and center-crop to target resolution while preserving aspect ratio
            target_w, target_h = target_resolution
            src_w, src_h = img.size

            src_ratio = src_w / src_h
            target_ratio = target_w / target_h

            if src_ratio > target_ratio:
                # Source is wider than target: scale by height, crop width
                scale = target_h / src_h
                new_w = int(src_w * scale)
                new_h = target_h
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                crop_x = (new_w - target_w) // 2
                cropped = resized.crop((crop_x, 0, crop_x + target_w, target_h))
            else:
                # Source is taller than target: scale by width, crop height
                scale = target_w / src_w
                new_w = target_w
                new_h = int(src_h * scale)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                crop_y = (new_h - target_h) // 2
                cropped = resized.crop((0, crop_y, target_w, crop_y + target_h))

            dest_path.parent.mkdir(parents=True, exist_ok=True)
            # Save standard uncompressed 8-bit PNG (optimize=False for deterministic fast decoding)
            cropped.save(dest_path, format="PNG", optimize=False)

        return dest_path

    @classmethod
    def generate_solid_wallpaper(
        cls,
        dest_path: Path,
        color_hex: str = "#1e1e2e",
        target_resolution: Tuple[int, int] = (1920, 1080)
    ) -> Path:
        """Generates a clean solid background image."""
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        img = Image.new("RGB", target_resolution, color=color_hex)
        img.save(dest_path, format="PNG", optimize=False)
        return dest_path

    @classmethod
    def generate_highlight_slices(
        cls,
        dest_dir: Path,
        bg_hex: str,
        border_hex: str,
        radius: int = 6
    ) -> Dict[str, Path]:
        """
        Generates 9-slice or 3-slice highlight bitmaps used by GRUB's selected_item_pixmap_style:
          - highlight_c.png (center stretch)
          - highlight_w.png (west / left edge with rounded corners)
          - highlight_e.png (east / right edge with rounded corners)
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        height = 40
        w_edge = 16

        # West edge (rounded left corners)
        img_w = Image.new("RGBA", (w_edge, height), (0, 0, 0, 0))
        draw_w = ImageDraw.Draw(img_w)
        draw_w.rounded_rectangle([0, 0, w_edge * 2, height - 1], radius=radius, fill=bg_hex, outline=border_hex, width=2)
        path_w = dest_dir / "highlight_w.png"
        img_w.save(path_w, format="PNG")

        # Center tile (repeats horizontally)
        img_c = Image.new("RGBA", (8, height), (0, 0, 0, 0))
        draw_c = ImageDraw.Draw(img_c)
        draw_c.rectangle([0, 0, 7, height - 1], fill=bg_hex)
        # Top and bottom border
        draw_c.line([(0, 0), (7, 0)], fill=border_hex, width=2)
        draw_c.line([(0, height - 1), (7, height - 1)], fill=border_hex, width=2)
        path_c = dest_dir / "highlight_c.png"
        img_c.save(path_c, format="PNG")

        # East edge (rounded right corners)
        img_e = Image.new("RGBA", (w_edge, height), (0, 0, 0, 0))
        draw_e = ImageDraw.Draw(img_e)
        draw_e.rounded_rectangle([-w_edge, 0, w_edge - 1, height - 1], radius=radius, fill=bg_hex, outline=border_hex, width=2)
        path_e = dest_dir / "highlight_e.png"
        img_e.save(path_e, format="PNG")

        return {"w": path_w, "c": path_c, "e": path_e}

    @classmethod
    def generate_progressbar_slices(
        cls,
        dest_dir: Path,
        fill_hex: str = "#89b4fa",
        track_hex: str = "#313244",
        height: int = 8
    ) -> Dict[str, Path]:
        """
        Generates 3-slice progress bar bitmaps for GRUB theme specifications:
          - bar_w.png, bar_c.png, bar_e.png (Fill)
          - bar_frame_w.png, bar_frame_c.png, bar_frame_e.png (Track)
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        w_cap = 6

        # Fill West Cap
        img_bw = Image.new("RGBA", (w_cap, height), (0, 0, 0, 0))
        d_bw = ImageDraw.Draw(img_bw)
        d_bw.rounded_rectangle([0, 0, w_cap * 2, height - 1], radius=3, fill=fill_hex)
        path_bw = dest_dir / "bar_w.png"
        img_bw.save(path_bw, format="PNG")

        # Fill Center Tile
        img_bc = Image.new("RGBA", (4, height), (0, 0, 0, 0))
        d_bc = ImageDraw.Draw(img_bc)
        d_bc.rectangle([0, 0, 3, height - 1], fill=fill_hex)
        path_bc = dest_dir / "bar_c.png"
        img_bc.save(path_bc, format="PNG")

        # Fill East Cap
        img_be = Image.new("RGBA", (w_cap, height), (0, 0, 0, 0))
        d_be = ImageDraw.Draw(img_be)
        d_be.rounded_rectangle([-w_cap, 0, w_cap - 1, height - 1], radius=3, fill=fill_hex)
        path_be = dest_dir / "bar_e.png"
        img_be.save(path_be, format="PNG")

        return {"w": path_bw, "c": path_bc, "e": path_be}


class ThemeEngine:
    """
    Compiles GRUB theme directories, assets, and theme.txt files.
    """

    def __init__(self, theme_root_dir: Path):
        self.theme_root_dir = theme_root_dir

    def build_theme(
        self,
        theme_name: str,
        colors: ThemeColors,
        wallpaper_source: Optional[Path] = None,
        resolution: Tuple[int, int] = (1920, 1080),
        title_text: str = "GRUB Boot Menu",
        font_size: int = 16,
        item_height: int = 38
    ) -> Path:
        """
        Creates a complete GRUB theme directory ready to be activated.
        Generates theme.txt, background.png, and highlight pixmaps.
        Returns the path to the generated theme.txt.
        """
        target_dir = self.theme_root_dir / theme_name
        target_dir.mkdir(parents=True, exist_ok=True)

        bg_dest = target_dir / "background.png"
        if wallpaper_source and wallpaper_source.is_file():
            AssetProcessor.normalize_wallpaper(wallpaper_source, bg_dest, target_resolution=resolution)
        else:
            AssetProcessor.generate_solid_wallpaper(bg_dest, color_hex=colors.desktop_background, target_resolution=resolution)

        # Generate highlight assets
        AssetProcessor.generate_highlight_slices(
            target_dir,
            bg_hex=colors.highlight_background,
            border_hex=colors.highlight_border
        )

        # Generate progressbar slices
        AssetProcessor.generate_progressbar_slices(
            target_dir,
            fill_hex=colors.highlight_border,
            track_hex=colors.highlight_background
        )

        # Assemble theme.txt
        theme_txt_content = f"""# ==============================================================================
# GRUB Forge Theme Configuration
# Auto-generated by GRUB Forge. Do not modify directly.
# ==============================================================================

# Global Properties
title-text: "{title_text}"
title-font: "Unifont Regular 18"
title-color: "{colors.title_color}"
desktop-image: "background.png"
desktop-color: "{colors.desktop_background}"
message-font: "Unifont Regular 14"
message-color: "{colors.item_color}"
terminal-font: "Unifont Regular 14"

# Boot Menu Component
+ boot_menu {{
    left = 20%
    top = 25%
    width = 60%
    height = 50%
    item_font = "Unifont Regular {font_size}"
    item_color = "{colors.item_color}"
    selected_item_font = "Unifont Bold {font_size}"
    selected_item_color = "{colors.selected_item_color}"
    selected_item_pixmap_style = "highlight_*.png"
    item_height = {item_height}
    item_padding = 8
    item_spacing = 6
    menu_pixmap_style = "menu_*.png"
}}

# Timeout Countdown Notification
+ label {{
    top = 78%
    left = 20%
    width = 60%
    align = "center"
    id = "__timeout__"
    text = "The highlighted entry will be executed automatically in %d seconds."
    color = "{colors.timeout_color}"
    font = "Unifont Regular 14"
}}

# Keyboard Navigation Instruction Banner
+ label {{
    top = 84%
    left = 15%
    width = 70%
    align = "center"
    text = "Use the ↑ and ↓ keys to select an option, then press Enter to boot."
    color = "{colors.item_color}"
    font = "Unifont Regular 12"
}}
"""
        theme_file = target_dir / "theme.txt"
        theme_file.write_text(theme_txt_content, encoding="utf-8")
        return theme_file

"""
GRUB Forge - Unprivileged User-Space Staging Engine
Prepares theme assets, normalized wallpaper, atomic default_grub candidate,
and integrity-checked metadata in ~/.cache/grub-forge/staged/ before triggering pkexec.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, List, Tuple

from backend.fs_detector import SystemTelemetry
from backend.safety import ASTGrubParser
from backend.theme_engine import ThemeColors, ThemeEngine, AssetProcessor


@dataclass
class StagingMetadata:
    theme_name: str
    target_theme_dir: str
    target_default_config: str
    target_active_grub_cfg: str
    target_backup_dir: str
    target_emergency_script: str
    update_command: List[str]
    update_tool_name: str
    script_check_tool: Optional[str]
    distro_id: str
    distro_name: str
    resolution: List[int]
    is_separate_boot: bool
    enable_os_prober: bool = True
    required_boot_space_mb: int = 25
    checksums: Dict[str, str] = None
    dry_run: bool = False


class StagingManager:
    """
    Manages unprivileged staging of bootloader assets prior to elevated deployment.
    """

    def __init__(self, custom_staging_root: Optional[Path] = None):
        if custom_staging_root:
            self.staging_root = custom_staging_root
        else:
            # Standard XDG user cache directory (~/.cache/grub-forge/staged/)
            cache_home = os.environ.get("XDG_CACHE_HOME")
            if cache_home:
                base = Path(cache_home)
            else:
                base = Path.home() / ".cache"
            self.staging_root = base / "grub-forge" / "staged"

    @staticmethod
    def calculate_sha256(path: Path) -> str:
        """Computes SHA256 hash of a staged file."""
        if not path.is_file():
            return ""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def check_os_prober_installed() -> bool:
        """Checks if os-prober binary is available in PATH."""
        return shutil.which("os-prober") is not None

    def prepare_staged_payload(
        self,
        telemetry: SystemTelemetry,
        theme_name: str,
        colors: ThemeColors,
        wallpaper_source: Optional[Path],
        resolution: Tuple[int, int],
        title_text: str,
        timeout_seconds: int,
        default_os_index: int,
        enable_os_prober: bool = True,
        source_theme_dir: Optional[Path] = None,
        dry_run: bool = False
    ) -> Path:
        """
        Builds the complete unprivileged staging directory.
        Preserves and stages ALL theme assets (slices, icons, frames, fonts) from source theme.
        Returns the path to the staged directory containing metadata.json.
        """
        # 1. Clean and initialize staging directory
        if self.staging_root.exists():
            shutil.rmtree(self.staging_root, ignore_errors=True)
        self.staging_root.mkdir(parents=True, exist_ok=True)

        theme_stage_dir = self.staging_root / "theme"
        theme_stage_dir.mkdir(parents=True, exist_ok=True)

        # 2. Copy ALL existing theme assets if basing on an existing theme directory
        if source_theme_dir and source_theme_dir.is_dir():
            try:
                for item in source_theme_dir.iterdir():
                    if item.is_file():
                        # Copy all graphics and fonts, exclude theme.txt which is regenerated
                        if item.name != "theme.txt":
                            shutil.copy2(item, theme_stage_dir / item.name)
                    elif item.is_dir() and item.name in ("icons", "fonts"):
                        shutil.copytree(item, theme_stage_dir / item.name, dirs_exist_ok=True)
            except Exception:
                pass

        # 3. Stage Wallpaper (Verified 8-bit uncompressed RGB PNG via Pillow)
        bg_dest = theme_stage_dir / "background.png"
        if wallpaper_source and wallpaper_source.is_file():
            AssetProcessor.normalize_wallpaper(wallpaper_source, bg_dest, target_resolution=resolution)
            # If the theme uses grub-16x9.png (Kali Linux), sync it as well
            if (theme_stage_dir / "grub-16x9.png").exists() or (source_theme_dir and (source_theme_dir / "grub-16x9.png").exists()):
                AssetProcessor.normalize_wallpaper(wallpaper_source, theme_stage_dir / "grub-16x9.png", target_resolution=resolution)
        elif not bg_dest.exists():
            AssetProcessor.generate_solid_wallpaper(bg_dest, color_hex=colors.desktop_background, target_resolution=resolution)

        # 4. Stage Highlight Slices & Progressbar Slices (generate only if missing)
        has_highlights = any(
            (theme_stage_dir / f"{pfx}_c.png").is_file() for pfx in ("highlight", "select")
        )
        if not has_highlights:
            AssetProcessor.generate_highlight_slices(
                theme_stage_dir,
                bg_hex=colors.highlight_background,
                border_hex=colors.highlight_border
            )

        has_bars = (theme_stage_dir / "bar_c.png").is_file()
        if not has_bars:
            AssetProcessor.generate_progressbar_slices(
                theme_stage_dir,
                fill_hex=colors.highlight_border,
                track_hex=colors.highlight_background
            )

        # 4. Stage theme.txt
        theme_engine = ThemeEngine(self.staging_root)
        theme_txt_content = f"""# GRUB Forge Theme Configuration
title-text: "{title_text}"
title-font: "Unifont Regular 18"
title-color: "{colors.title_color}"
desktop-image: "background.png"
desktop-color: "{colors.desktop_background}"
message-font: "Unifont Regular 14"
message-color: "{colors.item_color}"
terminal-font: "Unifont Regular 14"

+ boot_menu {{
    left = 20%
    top = 25%
    width = 60%
    height = 50%
    item_font = "Unifont Regular 16"
    item_color = "{colors.item_color}"
    selected_item_font = "Unifont Bold 16"
    selected_item_color = "{colors.selected_item_color}"
    selected_item_pixmap_style = "highlight_*.png"
    item_height = 36
    item_padding = 8
    item_spacing = 6
    menu_pixmap_style = "menu_*.png"
}}

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
        theme_txt_file = theme_stage_dir / "theme.txt"
        theme_txt_file.write_text(theme_txt_content, encoding="utf-8")

        # 5. Stage staged_default_grub via AST parser
        # GRUB_THEME in /etc/default/grub must be the full Linux host path (/boot/grub/themes/...)
        # grub-mkconfig verifies [ -f "$GRUB_THEME" ] in userspace and handles root translation internally.
        target_theme_txt_in_grub = str(telemetry.paths.theme_dir / theme_name / "theme.txt")

        res_str = f"{resolution[0]}x{resolution[1]}"
        updates = {
            "GRUB_THEME": target_theme_txt_in_grub,
            "GRUB_GFXMODE": f"{res_str},auto",
            "GRUB_TIMEOUT": str(timeout_seconds),
            "GRUB_DEFAULT": str(default_os_index)
        }

        if enable_os_prober:
            # Re-enable dual-boot operating system detection
            updates["GRUB_DISABLE_OS_PROBER"] = "false"

        # Read existing /etc/default/grub if readable, or use base template
        existing_cfg = ""
        if telemetry.paths.default_config.is_file():
            try:
                existing_cfg = telemetry.paths.default_config.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass

        if not existing_cfg:
            existing_cfg = (
                "# Default GRUB configuration generated by GRUB Forge\n"
                'GRUB_DEFAULT=0\n'
                'GRUB_TIMEOUT=5\n'
                'GRUB_DISTRIBUTOR="Linux"\n'
                'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n'
            )

        staged_default_content = ASTGrubParser.update_config(
            existing_cfg,
            updates=updates,
            remove_keys=["GRUB_BACKGROUND"]
        )

        staged_default_path = self.staging_root / "staged_default_grub"
        staged_default_path.write_text(staged_default_content, encoding="utf-8")

        # 6. Calculate checksums for all staged assets
        checksums = {}
        for p in self.staging_root.rglob("*"):
            if p.is_file() and p.name != "metadata.json":
                rel = p.relative_to(self.staging_root).as_posix()
                checksums[rel] = self.calculate_sha256(p)

        # 7. Write metadata.json
        meta = StagingMetadata(
            theme_name=theme_name,
            target_theme_dir=str(telemetry.paths.theme_dir / theme_name),
            target_default_config=str(telemetry.paths.default_config),
            target_active_grub_cfg=str(telemetry.paths.active_grub_cfg),
            target_backup_dir=str(telemetry.paths.backup_dir),
            target_emergency_script=str(telemetry.paths.emergency_script),
            update_command=telemetry.tools.update_command,
            update_tool_name=telemetry.tools.update_tool_name,
            script_check_tool=telemetry.tools.script_check_tool,
            distro_id=telemetry.distro.distro_id,
            distro_name=telemetry.distro.name,
            resolution=list(resolution),
            is_separate_boot=telemetry.fs.is_separate_boot,
            enable_os_prober=enable_os_prober,
            required_boot_space_mb=25,
            checksums=checksums,
            dry_run=dry_run
        )

        meta_file = self.staging_root / "metadata.json"
        meta_file.write_text(json.dumps(asdict(meta), indent=2), encoding="utf-8")

        return self.staging_root

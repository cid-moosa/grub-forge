"""
GRUB Forge - Theme Export & Import Packager
Packages customized themes into distributable .tar.gz / .zip archives
and securely imports third-party theme archives with path traversal protection.
"""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from backend.theme_scanner import DiscoveredTheme, ThemeScanner


class ThemePackager:
    """
    Handles export and safe import of portable GRUB theme archives.
    """

    @staticmethod
    def export_theme(
        theme_dir: Path,
        output_archive: Path,
        author: str = "GRUB Forge User"
    ) -> Path:
        """
        Compresses a theme directory into a .tar.gz or .zip archive.
        Injects a manifest.json with metadata if missing.
        """
        if not theme_dir.is_dir():
            raise FileNotFoundError(f"Theme directory does not exist: {theme_dir}")

        manifest_path = theme_dir / "manifest.json"
        if not manifest_path.is_file():
            manifest = {
                "name": theme_dir.name,
                "author": author,
                "created_at": datetime.now().isoformat(),
                "packaged_by": "GRUB Forge v1.0.0"
            }
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        output_archive.parent.mkdir(parents=True, exist_ok=True)
        ext = output_archive.name.lower()

        if ext.endswith(".zip"):
            with zipfile.ZipFile(output_archive, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in theme_dir.rglob("*"):
                    if file_path.is_file():
                        rel = file_path.relative_to(theme_dir)
                        zf.write(file_path, arcname=str(Path(theme_dir.name) / rel))
        else:
            # Default to .tar.gz
            if not ext.endswith(".tar.gz") and not ext.endswith(".tgz"):
                output_archive = output_archive.with_suffix(".tar.gz")
            with tarfile.open(output_archive, "w:gz") as tf:
                tf.add(theme_dir, arcname=theme_dir.name)

        return output_archive

    @staticmethod
    def import_theme(
        archive_path: Path,
        destination_dir: Path
    ) -> Tuple[bool, Optional[DiscoveredTheme], str]:
        """
        Safely extracts an imported theme archive (.tar.gz, .tgz, .zip),
        enforcing strict path traversal defense, and parses its theme.txt.
        """
        if not archive_path.is_file():
            return False, None, f"Archive not found: {archive_path}"

        destination_dir.mkdir(parents=True, exist_ok=True)
        temp_extract = destination_dir / f"import_tmp_{os.getpid()}"
        if temp_extract.exists():
            shutil.rmtree(temp_extract, ignore_errors=True)
        temp_extract.mkdir(parents=True, exist_ok=True)

        try:
            name_lower = archive_path.name.lower()
            if name_lower.endswith(".zip"):
                with zipfile.ZipFile(archive_path, "r") as zf:
                    for member in zf.infolist():
                        # Path traversal guard
                        target = (temp_extract / member.filename).resolve()
                        if not str(target).startswith(str(temp_extract.resolve())):
                            return False, None, "Archive security failure: Path traversal detected in zip."
                        zf.extract(member, temp_extract)
            elif name_lower.endswith(".tar.gz") or name_lower.endswith(".tgz") or name_lower.endswith(".tar"):
                with tarfile.open(archive_path, "r:*") as tf:
                    for member in tf.getmembers():
                        # Path traversal guard
                        target = (temp_extract / member.name).resolve()
                        if not str(target).startswith(str(temp_extract.resolve())):
                            return False, None, "Archive security failure: Path traversal detected in tar."
                    tf.extractall(temp_extract)
            else:
                return False, None, "Unsupported archive format. Please use .tar.gz or .zip."

            # Locate extracted theme directory (looking for theme.txt)
            theme_txt_candidates = list(temp_extract.rglob("theme.txt"))
            if not theme_txt_candidates:
                shutil.rmtree(temp_extract, ignore_errors=True)
                return False, None, "Invalid theme archive: 'theme.txt' not found inside archive."

            theme_txt = theme_txt_candidates[0]
            extracted_theme_dir = theme_txt.parent

            # Move to final location inside destination_dir
            final_theme_dir = destination_dir / extracted_theme_dir.name
            if final_theme_dir.exists():
                shutil.rmtree(final_theme_dir, ignore_errors=True)

            shutil.move(str(extracted_theme_dir), str(final_theme_dir))
            shutil.rmtree(temp_extract, ignore_errors=True)

            # Parse theme
            scanner = ThemeScanner(search_paths=[destination_dir])
            parsed = scanner.parse_theme_txt(final_theme_dir, final_theme_dir / "theme.txt")
            if not parsed:
                return False, None, "Failed to parse imported theme.txt."

            return True, parsed, f"Successfully imported theme '{parsed.name}' into {final_theme_dir.name}"

        except Exception as e:
            if temp_extract.exists():
                shutil.rmtree(temp_extract, ignore_errors=True)
            return False, None, f"Import extraction failed: {e}"

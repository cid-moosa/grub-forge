"""
Unit tests for GRUB Forge Theme Packager & Font Manager.
"""

import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from backend.font_manager import FontManager, GrubFont
from backend.theme_packager import ThemePackager


class TestThemePackagerAndFontManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.root = Path(self.temp_dir)

    def test_theme_export_tar_gz(self):
        theme_dir = self.root / "cyber_theme"
        theme_dir.mkdir(parents=True)
        (theme_dir / "theme.txt").write_text("title-text: \"Cyber\"", encoding="utf-8")
        (theme_dir / "background.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")

        out_archive = self.root / "exports" / "cyber_theme.tar.gz"
        exported = ThemePackager.export_theme(theme_dir, out_archive, author="Tester")

        self.assertTrue(exported.exists())
        self.assertTrue(tarfile.is_tarfile(exported))

        # Verify manifest injection
        manifest_path = theme_dir / "manifest.json"
        self.assertTrue(manifest_path.exists())
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(data["author"], "Tester")
        self.assertEqual(data["name"], "cyber_theme")

    def test_theme_export_and_import_zip(self):
        theme_dir = self.root / "zip_theme"
        theme_dir.mkdir(parents=True)
        (theme_dir / "theme.txt").write_text("title-text: \"ZipTheme\"", encoding="utf-8")

        out_zip = self.root / "zip_theme.zip"
        ThemePackager.export_theme(theme_dir, out_zip)
        self.assertTrue(out_zip.exists())

        dest_dir = self.root / "imported_themes"
        success, theme, msg = ThemePackager.import_theme(out_zip, dest_dir)
        self.assertTrue(success, f"Import failed: {msg}")
        self.assertIsNotNone(theme)
        self.assertEqual(theme.name, "Zip Theme")
        self.assertTrue(theme.directory.is_dir())
        self.assertTrue((theme.directory / "theme.txt").exists())

    def test_theme_import_rejects_path_traversal(self):
        malicious_tar = self.root / "evil.tar.gz"
        with tarfile.open(malicious_tar, "w:gz") as tar:
            info = tarfile.TarInfo(name="../escape.txt")
            content = b"malicious content"
            info.size = len(content)
            import io
            tar.addfile(info, io.BytesIO(content))

        dest_dir = self.root / "safe_dest"
        success, theme, msg = ThemePackager.import_theme(malicious_tar, dest_dir)
        self.assertFalse(success)
        self.assertIn("Path traversal", msg)

    def test_font_manager_discovery(self):
        # Create mock system font structure
        mock_font_dir = self.root / "boot" / "grub" / "fonts"
        mock_font_dir.mkdir(parents=True)
        (mock_font_dir / "unicode.pf2").write_bytes(b"DATA\x00\x00")
        (mock_font_dir / "dejavu_16.pf2").write_bytes(b"DATA\x00\x00")

        fm = FontManager(root_prefix=str(self.root))
        fonts = fm.discover_pf2_fonts()
        font_names = [f.name for f in fonts]

        self.assertIn("unicode", font_names)
        self.assertIn("dejavu_16", font_names)


if __name__ == "__main__":
    unittest.main()

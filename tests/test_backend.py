"""
Unit test suite for GRUB Forge backend and parsing engine.
"""

import os
import tempfile
import unittest
from pathlib import Path

from backend.fs_detector import DistroInfo, FSDetector, GrubPaths, GrubTools
from backend.safety import ASTGrubParser, SafetyManager
from backend.theme_engine import ThemeColors, ThemeEngine, AssetProcessor, PRESETS
from gui.preview_canvas import GrubMenuParser


class TestFSDetector(unittest.TestCase):
    def test_distro_family_flags(self):
        debian = DistroInfo("debian", "Debian GNU/Linux", ["debian"])
        self.assertTrue(debian.is_debian_like)
        self.assertFalse(debian.is_arch_like)

        arch = DistroInfo("arch", "Arch Linux", ["arch"])
        self.assertTrue(arch.is_arch_like)
        self.assertFalse(arch.is_fedora_like)

        fedora = DistroInfo("fedora", "Fedora Linux", ["fedora", "rhel"])
        self.assertTrue(fedora.is_fedora_like)

        suse = DistroInfo("opensuse-tumbleweed", "openSUSE Tumbleweed", ["opensuse", "suse"])
        self.assertTrue(suse.is_suse_like)

    def test_os_release_parsing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            etc_dir = Path(tmpdir) / "etc"
            etc_dir.mkdir()
            os_rel = etc_dir / "os-release"
            os_rel.write_text(
                'NAME="Debian GNU/Linux"\n'
                'VERSION_ID="12"\n'
                'ID=debian\n'
                'ID_LIKE=debian\n'
            )
            detector = FSDetector(root_prefix=tmpdir)
            distro = detector.detect_distro()
            self.assertEqual(distro.distro_id, "debian")
            self.assertEqual(distro.name, "Debian GNU/Linux")
            self.assertTrue(distro.is_debian_like)

    def test_path_resolution_fedora(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fedora = DistroInfo("fedora", "Fedora", ["fedora", "rhel"])
            detector = FSDetector(root_prefix=tmpdir)
            paths = detector.resolve_paths(fedora)
            self.assertTrue("grub2" in str(paths.active_grub_cfg))
            self.assertTrue("grub2" in str(paths.theme_dir))


class TestASTParserAndSafety(unittest.TestCase):
    def test_ast_comment_and_custom_cmdline_preservation(self):
        sample_config = (
            "# Global GRUB Configuration\n"
            'GRUB_DEFAULT=0\n'
            'GRUB_TIMEOUT=5\n'
            '# Kernel arguments\n'
            'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nvidia-drm.modeset=1"\n'
            'GRUB_BACKGROUND="/old/image.png"\n'
        )

        updates = {
            "GRUB_THEME": "/boot/grub/themes/my_theme/theme.txt",
            "GRUB_GFXMODE": "1920x1080,auto",
            "GRUB_TIMEOUT": "10"
        }

        updated = ASTGrubParser.update_config(
            sample_config,
            updates,
            remove_keys=["GRUB_BACKGROUND"]
        )

        # Check that original comments are preserved
        self.assertIn("# Global GRUB Configuration", updated)
        self.assertIn("# Kernel arguments", updated)

        # Check that custom kernel params were untouched
        self.assertIn('GRUB_CMDLINE_LINUX_DEFAULT="quiet splash nvidia-drm.modeset=1"', updated)

        # Check that timeout updated
        self.assertIn('GRUB_TIMEOUT="10"', updated)

        # Check that GRUB_THEME and GRUB_GFXMODE were added
        self.assertIn('GRUB_THEME="/boot/grub/themes/my_theme/theme.txt"', updated)
        self.assertIn('GRUB_GFXMODE="1920x1080,auto"', updated)

        # Check that conflicting GRUB_BACKGROUND was safely commented out
        self.assertIn("# Commented out by GRUB Forge to prevent conflicts:", updated)

    def test_snapshot_and_recovery_script(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            etc_dir = root / "etc" / "default"
            etc_dir.mkdir(parents=True)
            default_grub = etc_dir / "grub"
            default_grub.write_text('GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\n')

            boot_grub = root / "boot" / "grub"
            boot_grub.mkdir(parents=True)
            active_cfg = boot_grub / "grub.cfg"
            active_cfg.write_text("menuentry 'Linux' { echo 'booting' }\n")

            paths = GrubPaths(
                default_config=default_grub,
                grub_dir=boot_grub,
                active_grub_cfg=active_cfg,
                theme_dir=boot_grub / "themes",
                fallback_theme_dir=root / "usr" / "share" / "grub" / "themes",
                backup_dir=boot_grub / "grub_forge_backups",
                emergency_script=root / "boot" / "grub_emergency_restore.sh"
            )
            tools = GrubTools(
                update_command=["update-grub"],
                update_tool_name="update-grub",
                script_check_tool=None
            )
            distro = DistroInfo("debian", "Debian", ["debian"])

            safety = SafetyManager(paths, tools, distro)

            # Test snapshot creation
            snap_dir = safety.create_snapshot()
            self.assertTrue(snap_dir.is_dir())
            self.assertTrue((snap_dir / "grub").is_file())
            self.assertTrue((snap_dir / "grub.cfg").is_file())
            self.assertTrue((snap_dir / "meta.json").is_file())

            # Test emergency recovery script generation
            rec_script = safety.generate_recovery_script()
            self.assertTrue(rec_script.is_file())
            content = rec_script.read_text()
            self.assertIn("#!/bin/sh", content)
            self.assertIn("update-grub", content)
            self.assertIn("LATEST_DIR", content)


class TestThemeEngine(unittest.TestCase):
    def test_theme_compilation_and_assets(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            theme_root = Path(tmpdir) / "themes"
            engine = ThemeEngine(theme_root)

            preset = PRESETS["cyber_glow"]
            theme_txt = engine.build_theme(
                theme_name="test_theme",
                colors=preset.colors,
                wallpaper_source=None,
                resolution=(1920, 1080),
                title_text="Test Bootloader"
            )

            self.assertTrue(theme_txt.is_file())
            theme_content = theme_txt.read_text()
            self.assertIn('title-text: "Test Bootloader"', theme_content)
            self.assertIn("+ boot_menu {", theme_content)
            self.assertIn('id = "__timeout__"', theme_content)

            # Check that background.png and highlight slices exist
            theme_dir = theme_txt.parent
            self.assertTrue((theme_dir / "background.png").is_file())
            self.assertTrue((theme_dir / "highlight_w.png").is_file())
            self.assertTrue((theme_dir / "highlight_c.png").is_file())
            self.assertTrue((theme_dir / "highlight_e.png").is_file())


class TestGrubMenuParser(unittest.TestCase):
    def test_menu_entry_regex(self):
        sample_grub_cfg = """
        set default="0"
        menuentry 'Arch Linux (linux 6.12.1)' --class arch --class gnu-linux {
            load_video
            linux /vmlinuz-linux root=/dev/sda2 rw
        }
        menuentry 'Arch Linux (fallback initramfs)' {
            initrd /initramfs-linux-fallback.img
        }
        menuentry "Windows Boot Manager (on /dev/nvme0n1p1)" --class windows {
            chainloader +1
        }
        """
        with tempfile.NamedTemporaryFile("w+", suffix=".cfg", delete=False) as f:
            f.write(sample_grub_cfg)
            f.flush()
            temp_path = Path(f.name)

        try:
            entries = GrubMenuParser.parse_entries(temp_path)
            self.assertEqual(len(entries), 3)
            self.assertEqual(entries[0], "Arch Linux (linux 6.12.1)")
            self.assertEqual(entries[1], "Arch Linux (fallback initramfs)")
            self.assertEqual(entries[2], "Windows Boot Manager (on /dev/nvme0n1p1)")
        finally:
            if temp_path.exists():
                temp_path.unlink()


if __name__ == "__main__":
    unittest.main()

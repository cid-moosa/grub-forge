"""
Unit and integration tests for QEMU virtual boot harness, os-prober dual-boot
preservation, and FreeDesktop packaging artifacts.
"""

import os
import tempfile
import unittest
from pathlib import Path

from backend.fs_detector import FSDetector
from backend.qemu_runner import QemuRunner, QemuCapabilities
from backend.staging import StagingManager
from backend.theme_engine import PRESETS


class TestQemuAndPackaging(unittest.TestCase):

    def test_qemu_command_construction(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            v_disk = Path(tmpdir) / "v_disk"
            v_disk.mkdir()

            runner = QemuRunner(workspace_dir=v_disk)

            # Test KVM command
            cmd_kvm = runner.build_qemu_command(v_disk, resolution=(1920, 1080), force_tcg=False)
            self.assertIn("-m", cmd_kvm)
            self.assertIn("512M", cmd_kvm)
            self.assertIn("-vga", cmd_kvm)
            self.assertTrue(any(f"file=fat:rw:{v_disk}" in arg for arg in cmd_kvm))

            # Test forced TCG command (no hardware virtualization)
            cmd_tcg = runner.build_qemu_command(v_disk, resolution=(1024, 768), force_tcg=True)
            self.assertIn("-cpu", cmd_tcg)
            self.assertIn("qemu64", cmd_tcg)
            self.assertNotIn("-enable-kvm", cmd_tcg)

    def test_qemu_virtual_disk_preparation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            staged = tmp / "staged"
            theme_dir = staged / "theme"
            theme_dir.mkdir(parents=True)
            (theme_dir / "theme.txt").write_text("title-text: 'Test'\n")
            (theme_dir / "background.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            runner = QemuRunner(workspace_dir=tmp / "v_disk")
            v_disk = runner.prepare_virtual_disk(
                staged_dir=staged,
                menu_entries=["Arch Linux", "Windows 11"],
                resolution=(1920, 1080),
                timeout_seconds=10
            )

            self.assertTrue(v_disk.is_dir())
            cfg_file = v_disk / "boot" / "grub" / "grub.cfg"
            self.assertTrue(cfg_file.is_file())
            content = cfg_file.read_text(encoding="utf-8")
            self.assertIn('set timeout="10"', content)
            self.assertIn('menuentry "Arch Linux"', content)
            self.assertIn('menuentry "Windows 11"', content)
            self.assertIn('set gfxmode="1920x1080,auto"', content)
            self.assertTrue((v_disk / "boot" / "grub" / "themes" / "grub_forge_theme" / "theme.txt").is_file())

    def test_os_prober_staging_preservation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stage_root = Path(tmpdir) / "staged"
            staging_mgr = StagingManager(custom_staging_root=stage_root)

            detector = FSDetector()
            telemetry = detector.inspect()
            preset = PRESETS["cyber_glow"]

            # 1. Test staging with os-prober enabled
            staged_path = staging_mgr.prepare_staged_payload(
                telemetry=telemetry,
                theme_name="test_prober",
                colors=preset.colors,
                wallpaper_source=None,
                resolution=(1920, 1080),
                title_text="Dual Boot Title",
                timeout_seconds=5,
                default_os_index=0,
                enable_os_prober=True,
                dry_run=True
            )

            staged_default = (staged_path / "staged_default_grub").read_text(encoding="utf-8")
            self.assertIn('GRUB_DISABLE_OS_PROBER="false"', staged_default)

            # Ensure no duplication if run again
            staged_path2 = staging_mgr.prepare_staged_payload(
                telemetry=telemetry,
                theme_name="test_prober",
                colors=preset.colors,
                wallpaper_source=None,
                resolution=(1920, 1080),
                title_text="Dual Boot Title",
                timeout_seconds=5,
                default_os_index=0,
                enable_os_prober=True,
                dry_run=True
            )
            staged_default2 = (staged_path2 / "staged_default_grub").read_text(encoding="utf-8")
            self.assertEqual(staged_default2.count('GRUB_DISABLE_OS_PROBER="false"'), 1)

    def test_freedesktop_specification_compliance(self):
        project_root = Path(__file__).resolve().parent.parent
        desktop_file = project_root / "data" / "grub-forge.desktop"
        self.assertTrue(desktop_file.is_file())

        content = desktop_file.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

        # Check section header
        self.assertIn("[Desktop Entry]", lines)

        # Parse key-values
        keys = {}
        for line in lines:
            if "=" in line and not line.startswith("["):
                k, v = line.split("=", 1)
                keys[k.strip()] = v.strip()

        # Required FreeDesktop keys
        self.assertEqual(keys.get("Type"), "Application")
        self.assertEqual(keys.get("Name"), "GRUB Forge")
        self.assertEqual(keys.get("Terminal"), "false")
        self.assertIn("grub-forge", keys.get("Exec", ""))
        self.assertEqual(keys.get("Icon"), "grub-forge")
        self.assertIn("System", keys.get("Categories", ""))

    def test_scalable_icon_validity(self):
        project_root = Path(__file__).resolve().parent.parent
        icon_file = project_root / "data" / "icons" / "grub-forge.svg"
        self.assertTrue(icon_file.is_file())

        content = icon_file.read_text(encoding="utf-8")
        self.assertIn("<svg", content)
        self.assertIn("</svg>", content)
        self.assertIn('viewBox="0 0 256 256"', content)


if __name__ == "__main__":
    unittest.main()

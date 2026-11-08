"""
Unit tests for privilege separation pipeline: unprivileged staging,
elevated root worker, and theme discovery scanner.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from backend.fs_detector import FSDetector
from backend.staging import StagingManager
from backend.theme_engine import PRESETS
from backend.theme_scanner import ThemeScanner
from backend.worker import RootWorker, IPCReporter


class TestPrivilegePipeline(unittest.TestCase):

    def test_unprivileged_staging_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stage_root = Path(tmpdir) / "staged"
            staging_mgr = StagingManager(custom_staging_root=stage_root)

            detector = FSDetector()
            telemetry = detector.inspect()

            preset = PRESETS["cyber_glow"]
            staged_path = staging_mgr.prepare_staged_payload(
                telemetry=telemetry,
                theme_name="test_staged_theme",
                colors=preset.colors,
                wallpaper_source=None,
                resolution=(1920, 1080),
                title_text="Staged Test Title",
                timeout_seconds=7,
                default_os_index=1,
                dry_run=True
            )

            self.assertTrue(staged_path.is_dir())
            self.assertTrue((staged_path / "metadata.json").is_file())
            self.assertTrue((staged_path / "staged_default_grub").is_file())
            self.assertTrue((staged_path / "theme" / "theme.txt").is_file())
            self.assertTrue((staged_path / "theme" / "background.png").is_file())
            self.assertTrue((staged_path / "theme" / "highlight_w.png").is_file())

            # Verify metadata.json contents
            meta = json.loads((staged_path / "metadata.json").read_text())
            self.assertEqual(meta["theme_name"], "test_staged_theme")
            self.assertEqual(meta["resolution"], [1920, 1080])
            self.assertTrue(meta["dry_run"])
            self.assertIn("theme/theme.txt", meta["checksums"])
            self.assertIn("theme/background.png", meta["checksums"])

    def test_worker_preflight_and_atomic_deploy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            stage_root = root / "user_staged"
            target_boot = root / "boot"
            target_etc = root / "etc" / "default"
            target_boot.mkdir(parents=True)
            target_etc.mkdir(parents=True)

            staging_mgr = StagingManager(custom_staging_root=stage_root)
            detector = FSDetector(root_prefix=tmpdir)
            telemetry = detector.inspect()

            # Prepare staged payload
            preset = PRESETS["cyber_glow"]
            staged_path = staging_mgr.prepare_staged_payload(
                telemetry=telemetry,
                theme_name="test_worker_theme",
                colors=preset.colors,
                wallpaper_source=None,
                resolution=(1920, 1080),
                title_text="Worker Test",
                timeout_seconds=5,
                default_os_index=0,
                dry_run=True
            )

            # Execute root worker
            messages = []
            class TestIPC(IPCReporter):
                def emit(self, tag, message, progress=None):
                    messages.append((tag, message))

            ipc = TestIPC(use_json=False)
            worker = RootWorker(staged_path, ipc)

            # Test A: Pre-Flight
            self.assertTrue(worker.verify_preflight_mount_and_space())

            # Test B: Snapshot
            snap_dir = worker.create_immutable_snapshot()
            self.assertTrue(snap_dir.is_dir())
            self.assertTrue((snap_dir / "meta.json").is_file())

            # Test C: Deploy
            self.assertTrue(worker.deploy_staged_assets())
            self.assertTrue((worker.target_theme_dir / "theme.txt").is_file())
            self.assertTrue(worker.target_default_cfg.is_file())

            # Test D: Validate Syntax
            self.assertTrue(worker.validate_syntax())

            # Test E: Execution in dry-run
            self.assertTrue(worker.execute_bootloader_rebuild())

            # Check messages received
            self.assertTrue(any("Phase 1" in m[1] for m in messages))
            self.assertTrue(any("Phase 2" in m[1] for m in messages))
            self.assertTrue(any("Phase 3" in m[1] for m in messages))

    def test_theme_scanner(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            themes_root = Path(tmpdir) / "themes"
            theme_a = themes_root / "breeze_grub"
            theme_a.mkdir(parents=True)
            (theme_a / "theme.txt").write_text(
                'title-text: "Breeze Dark"\n'
                'desktop-color: "#232629"\n'
                'title-color: "#eff0f1"\n'
                'item_color: "#bdc3c7"\n'
            )

            scanner = ThemeScanner(search_paths=[themes_root])
            discovered = scanner.scan_installed_themes()
            self.assertEqual(len(discovered), 1)
            self.assertEqual(discovered[0].id, "breeze_grub")
            self.assertEqual(discovered[0].name, "Breeze Grub")
            self.assertEqual(discovered[0].colors.desktop_background, "#232629")


if __name__ == "__main__":
    unittest.main()

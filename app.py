#!/usr/bin/env python3
"""
GRUB Forge - Main Application Entry Point
Native desktop bootloader architect for Linux systems.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="grub-forge",
        description="GRUB Forge: Non-Destructive Multi-Distro GRUB Architect"
    )
    parser.add_argument(
        "--mock",
        type=str,
        default="",
        help="Simulate a target Linux distribution (e.g. 'arch', 'debian', 'fedora', 'opensuse')"
    )
    parser.add_argument(
        "--root-prefix",
        type=str,
        default="",
        help="Prefix path for sandbox testing or chroot environment"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Perform system discovery and telemetry inspection in CLI mode without launching GUI"
    )
    args = parser.parse_args()

    # Pass mock distro via environment if specified
    if args.mock:
        os.environ["GRUB_FORGE_MOCK_DISTRO"] = args.mock

    # CLI check mode
    if args.check:
        from backend.fs_detector import FSDetector
        detector = FSDetector(root_prefix=args.root_prefix)
        telemetry = detector.inspect()

        print("=" * 60)
        print("          GRUB FORGE - SYSTEM DISCOVERY TELEMETRY")
        print("=" * 60)
        print(f"Distribution:      {telemetry.distro.name} (ID: {telemetry.distro.distro_id})")
        print(f"Family/ID_LIKE:    {', '.join(telemetry.distro.id_like) or 'None'}")
        print(f"Kernel Version:    {telemetry.kernel_version}")
        print(f"GRUB Engine:       {telemetry.grub_version}")
        print(f"/boot Target:      {telemetry.fs.boot_target}")
        print(f"/boot Filesystem:  {telemetry.fs.fstype} (Separate partition: {telemetry.fs.is_separate_boot})")
        if telemetry.fs.is_btrfs:
            print(f"Btrfs Subvolume:   {telemetry.fs.subvolume or 'default'}")
        print(f"EFI Mounted:       {telemetry.fs.efi_mounted} ({telemetry.fs.efi_path or 'N/A'})")
        print(f"Default Config:    {telemetry.paths.default_config}")
        print(f"Active grub.cfg:   {telemetry.paths.active_grub_cfg}")
        print(f"Theme Directory:   {telemetry.paths.theme_dir}")
        print(f"Update Command:    {' '.join(telemetry.tools.update_command)}")
        print(f"Syntax Check Tool: {telemetry.tools.script_check_tool or 'Not installed (fallback internal linter)'}")
        print("=" * 60)
        return 0

    # Launch GUI
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("GRUB Forge")
    app.setApplicationDisplayName("GRUB Forge")
    app.setOrganizationName("GRUB Forge Project")

    window = MainWindow(root_prefix=args.root_prefix)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
GRUB Forge - Privileged Transaction Worker
Dedicated CLI script executed via pkexec during the final application phase.
Executes the full transactional pipeline: immutable snapshots, emergency rescue script,
theme compilation, atomic configuration update, pre-flight syntax check, and update execution.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.fs_detector import GrubPaths, GrubTools, DistroInfo
from backend.safety import SafetyManager
from backend.theme_engine import ThemeEngine, ThemeColors


def run_transaction(payload_path: Path) -> int:
    try:
        data = json.loads(payload_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] ERROR: Failed to read transaction payload: {e}", flush=True)
        return 1

    print("=== [GRUB FORGE PRIVILEGED TRANSACTION INITIATED] ===", flush=True)

    # Reconstruct data classes
    paths = GrubPaths(
        default_config=Path(data["default_config"]),
        grub_dir=Path(data["grub_dir"]),
        active_grub_cfg=Path(data["active_grub_cfg"]),
        theme_dir=Path(data["theme_dir"]),
        fallback_theme_dir=Path(data.get("fallback_theme_dir", "/usr/share/grub/themes")),
        backup_dir=Path(data["backup_dir"]),
        emergency_script=Path(data["emergency_script"])
    )

    tools = GrubTools(
        update_command=data["update_command"],
        update_tool_name=data.get("update_tool_name", "grub-mkconfig"),
        script_check_tool=data.get("script_check_tool")
    )

    distro = DistroInfo(
        distro_id=data.get("distro_id", "linux"),
        name=data.get("distro_name", "Linux")
    )

    safety = SafetyManager(paths, tools, distro)
    theme_engine = ThemeEngine(paths.theme_dir)
    dry_run = data.get("dry_run", False)

    try:
        # 1. Snapshot Backup
        print("[*] Phase 1/6: Securing immutable snapshot backup...", flush=True)
        snap_dir = safety.create_snapshot()
        print(f"[✓] Snapshot created at: {snap_dir}", flush=True)

        # 2. Standalone Emergency Rescue Script
        print("[*] Phase 2/6: Generating standalone emergency rescue script...", flush=True)
        rec_script = safety.generate_recovery_script()
        print(f"[✓] Emergency recovery script active at: {rec_script}", flush=True)

        # 3. Theme Compilation
        print("[*] Phase 3/6: Compiling theme assets and theme.txt...", flush=True)
        colors_dict = data.get("colors", {})
        colors = ThemeColors(**colors_dict)
        wp_src = Path(data["wallpaper_source"]) if data.get("wallpaper_source") else None
        res = tuple(data.get("resolution", [1920, 1080]))

        theme_txt = theme_engine.build_theme(
            theme_name=data.get("theme_name", "grub_forge_theme"),
            colors=colors,
            wallpaper_source=wp_src,
            resolution=res,
            title_text=data.get("title_text", "GRUB Boot Menu")
        )
        print(f"[✓] Theme compiled successfully: {theme_txt}", flush=True)

        # 4. Atomic /etc/default/grub Rewrite
        print("[*] Phase 4/6: Atomically updating /etc/default/grub...", flush=True)
        updates = data.get("updates", {})
        safety.atomic_update_default_grub(updates, remove_conflicts=True)
        print("[✓] Configuration rewritten atomically with zero syntax corruption.", flush=True)

        # 5. Pre-flight Syntax Verification
        print("[*] Phase 5/6: Executing pre-flight dry-run syntax verification...", flush=True)
        if not dry_run:
            valid, msg = safety.preflight_syntax_check(theme_path=theme_txt)
            if not valid:
                print(f"[!] Pre-flight syntax validation failed: {msg}", flush=True)
                print("[*] Aborting and executing immediate rollback...", flush=True)
                safety.rollback()
                return 1
            print(f"[✓] {msg}", flush=True)
        else:
            print("[~] Dry-run mode: Syntax check simulated.", flush=True)

        # 6. Rebuilding Bootloader
        print(f"[*] Phase 6/6: Rebuilding bootloader with {' '.join(tools.update_command)}...", flush=True)
        if dry_run:
            print("[~] Dry-run mode: Simulated grub rebuild complete.", flush=True)
            print("[✓] === [TRANSACTION COMPLETED WITH ZERO ERRORS] ===", flush=True)
            return 0

        import subprocess
        proc = subprocess.Popen(
            tools.update_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        if proc.stdout:
            for line in iter(proc.stdout.readline, ""):
                print(line.rstrip(), flush=True)
        proc.wait()

        if proc.returncode != 0:
            print(f"[!] Rebuild command exited with code {proc.returncode}. Initiating rollback...", flush=True)
            safety.rollback()
            return proc.returncode

        print("[✓] === [TRANSACTION COMPLETED WITH ZERO ERRORS] ===", flush=True)
        return 0

    except Exception as e:
        print(f"[!] Critical exception during transaction: {e}", flush=True)
        print("[*] Initiating automatic rollback guardrail...", flush=True)
        safety.rollback()
        return 1


def main():
    parser = argparse.ArgumentParser(description="GRUB Forge Privileged Apply Worker")
    parser.add_argument("--payload", type=str, required=True, help="Path to JSON payload file")
    args = parser.parse_args()

    payload_file = Path(args.payload)
    if not payload_file.is_file():
        print(f"[!] Payload file does not exist: {payload_file}", flush=True)
        sys.exit(1)

    code = run_transaction(payload_file)
    sys.exit(code)


if __name__ == "__main__":
    main()

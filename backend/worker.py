#!/usr/bin/env python3
"""
GRUB Forge - Elevated Root Worker & Security Boundary
Executes privileged root operations via pkexec (/usr/libexec/grub-forge-worker):
  A. Pre-Flight Mount & Space Verification (/boot)
  B. Immutable Snapshot Creation (/boot/grub_forge_backups/)
  C. Atomic File Copy & Permission Enforcing (chmod 755 / 644)
  D. Syntax Validation (grub-script-check on generated temp config)
  E. Final Execution (update-grub or grub-mkconfig)
  F. Stream stdout/stderr line-by-line via plain/JSON IPC back to GUI
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


class IPCReporter:
    """Streams structured execution status and logs back to the unprivileged GUI."""

    def __init__(self, use_json: bool = False):
        self.use_json = use_json

    def emit(self, tag: str, message: str, progress: Optional[int] = None):
        if self.use_json:
            payload = {
                "type": "log",
                "tag": tag,
                "message": message,
                "progress": progress
            }
            print(f"__IPC_JSON__{json.dumps(payload)}", flush=True)
        else:
            prefix = {
                "info": "[*]",
                "step": "[+]",
                "success": "[✓]",
                "error": "[!]",
                "warn": "[~]"
            }.get(tag, "[*]")
            print(f"{prefix} {message}", flush=True)


class RootWorker:
    """
    Elevated engine performing atomic deployment with fail-safe rollbacks.
    """

    def __init__(self, staged_dir: Path, ipc: IPCReporter):
        self.staged_dir = staged_dir
        self.ipc = ipc
        self.meta_file = staged_dir / "metadata.json"
        if not self.meta_file.is_file():
            raise FileNotFoundError(f"Staging metadata missing in {staged_dir}")

        self.meta: Dict[str, Any] = json.loads(self.meta_file.read_text(encoding="utf-8"))
        self.dry_run = self.meta.get("dry_run", False)

        # Extracted paths
        self.target_theme_dir = Path(self.meta["target_theme_dir"])
        self.target_default_cfg = Path(self.meta["target_default_config"])
        self.target_active_cfg = Path(self.meta["target_active_grub_cfg"])
        self.target_backup_dir = Path(self.meta["target_backup_dir"])
        self.target_emergency_script = Path(self.meta["target_emergency_script"])
        self.update_command: List[str] = self.meta["update_command"]
        self.script_check_tool: Optional[str] = self.meta.get("script_check_tool")

        self.active_snapshot_dir: Optional[Path] = None

    # =========================================================================
    # A. PRE-FLIGHT MOUNT & SPACE VERIFICATION (/boot)
    # =========================================================================
    def verify_preflight_mount_and_space(self) -> bool:
        self.ipc.emit("info", "Phase 1/5: Verifying /boot mount status and disk space...", progress=10)

        boot_mount_candidate = Path("/boot") if Path("/boot").exists() else Path("/")

        # 1. Mount read-only check
        if shutil.which("findmnt"):
            try:
                out = subprocess.check_output(
                    ["findmnt", "-n", "-o", "OPTIONS", "-T", str(boot_mount_candidate)],
                    text=True, stderr=subprocess.DEVNULL
                ).strip()
                if "ro" in [opt.strip() for opt in out.split(",")]:
                    self.ipc.emit("error", f"/boot mount ({boot_mount_candidate}) is mounted READ-ONLY. Aborting.")
                    return False
            except Exception:
                pass

        # 2. Free Disk Space check
        try:
            usage = shutil.disk_usage(boot_mount_candidate)
            free_mb = usage.free / (1024 * 1024)
            required_mb = self.meta.get("required_boot_space_mb", 25)

            if free_mb < required_mb:
                self.ipc.emit(
                    "error",
                    f"Insufficient disk space on {boot_mount_candidate}. Free: {free_mb:.1f} MB, Required: {required_mb} MB."
                )
                return False

            self.ipc.emit("step", f"Storage verified: {free_mb:.1f} MB free on {boot_mount_candidate} (Read-Write).")
        except Exception as e:
            self.ipc.emit("warn", f"Could not query disk space: {e}. Proceeding cautiously.")

        return True

    # =========================================================================
    # B. IMMUTABLE SNAPSHOT CREATION (/boot/grub_forge_backups/)
    # =========================================================================
    def create_immutable_snapshot(self) -> Path:
        self.ipc.emit("info", "Phase 2/5: Creating immutable snapshot & emergency restore script...", progress=25)

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_dir = self.target_backup_dir / f"backup_{ts}"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.active_snapshot_dir = snapshot_dir

        # 1. Back up active /etc/default/grub
        if self.target_default_cfg.is_file():
            shutil.copy2(self.target_default_cfg, snapshot_dir / "grub")

        # 2. Back up active grub.cfg
        if self.target_active_cfg.is_file():
            shutil.copy2(self.target_active_cfg, snapshot_dir / "grub.cfg")

        # 3. Write metadata snapshot
        snap_meta = {
            "timestamp": ts,
            "distro_id": self.meta.get("distro_id"),
            "update_command": self.update_command,
            "snapshot_path": str(snapshot_dir)
        }
        (snapshot_dir / "meta.json").write_text(json.dumps(snap_meta, indent=2), encoding="utf-8")

        # 4. Update 'latest' pointer
        latest_link = self.target_backup_dir / "latest"
        try:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink(missing_ok=True)
            try:
                latest_link.symlink_to(snapshot_dir.name, target_is_directory=True)
            except (OSError, NotImplementedError):
                latest_link.write_text(str(snapshot_dir.resolve()), encoding="utf-8")
        except Exception:
            pass

        # 5. Generate Standalone Emergency Rescue Script
        self._write_emergency_script(snapshot_dir)

        self.ipc.emit("step", f"Snapshot secured at: {snapshot_dir.name}")
        return snapshot_dir

    def _write_emergency_script(self, snapshot_dir: Path):
        self.target_emergency_script.parent.mkdir(parents=True, exist_ok=True)
        cmd_str = " ".join(self.update_command)

        content = f"""#!/bin/sh
# ==============================================================================
# GRUB Forge Automated Emergency Rescue Script
# Zero external dependencies. Runnable in live USB, chroot, or rescue shell.
# ==============================================================================
set -e
echo "[*] Initializing GRUB Forge Emergency Recovery..."

BACKUP_DIR="{snapshot_dir.resolve()}"
DEFAULT_CFG="{self.target_default_cfg.resolve()}"
ACTIVE_CFG="{self.target_active_cfg.resolve()}"

# 1. Revert default configuration
if [ -f "$BACKUP_DIR/grub" ]; then
    echo "[+] Restoring $DEFAULT_CFG..."
    mkdir -p "$(dirname "$DEFAULT_CFG")"
    cp -f "$BACKUP_DIR/grub" "$DEFAULT_CFG"
fi

# 2. Direct fallback copy of grub.cfg
if [ -f "$BACKUP_DIR/grub.cfg" ]; then
    echo "[+] Restoring baseline $ACTIVE_CFG..."
    mkdir -p "$(dirname "$ACTIVE_CFG")"
    cp -f "$BACKUP_DIR/grub.cfg" "$ACTIVE_CFG"
fi

# 3. Re-run generator
echo "[+] Rebuilding bootloader: {cmd_str}"
if command -v {self.update_command[0]} >/dev/null 2>&1; then
    {cmd_str} || cp -f "$BACKUP_DIR/grub.cfg" "$ACTIVE_CFG"
fi

echo "[✓] Bootloader emergency restoration complete."
exit 0
"""
        self.target_emergency_script.write_text(content, encoding="utf-8")
        try:
            os.chmod(self.target_emergency_script, 0o755)
        except Exception:
            pass

    # =========================================================================
    # C. ATOMIC FILE COPY & PERMISSION ENFORCING (chmod 755 / 644)
    # =========================================================================
    def deploy_staged_assets(self) -> bool:
        self.ipc.emit("info", "Phase 3/5: Deploying theme assets & atomic configuration update...", progress=45)

        # 1. Integrity check against staged checksums
        checksums: Dict[str, str] = self.meta.get("checksums", {})
        for rel_path, expected_hash in checksums.items():
            staged_file = self.staged_dir / rel_path
            if not staged_file.is_file():
                self.ipc.emit("error", f"Integrity check failed: Missing staged file {rel_path}")
                return False
            # Verify SHA256
            h = hashlib.sha256(staged_file.read_bytes()).hexdigest()
            if h != expected_hash:
                self.ipc.emit("error", f"Integrity check mismatch for {rel_path} (possible tampering). Aborting.")
                return False

        # 2. Copy Theme Directory & enforce permissions
        staged_theme = self.staged_dir / "theme"
        if staged_theme.is_dir():
            self.target_theme_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.target_theme_dir, 0o755)

            for item in staged_theme.iterdir():
                dest_item = self.target_theme_dir / item.name
                if item.is_file():
                    shutil.copy2(item, dest_item)
                    os.chmod(dest_item, 0o644)
                elif item.is_dir():
                    shutil.copytree(item, dest_item, dirs_exist_ok=True)
                    os.chmod(dest_item, 0o755)

        # 3. Atomic replacement of /etc/default/grub
        staged_cfg = self.staged_dir / "staged_default_grub"
        if staged_cfg.is_file():
            self.target_default_cfg.parent.mkdir(parents=True, exist_ok=True)
            tmp_dest = self.target_default_cfg.parent / f"{self.target_default_cfg.name}.tmp_{os.getpid()}"
            shutil.copy2(staged_cfg, tmp_dest)
            os.chmod(tmp_dest, 0o644)

            # Atomic rename / replace
            os.replace(tmp_dest, self.target_default_cfg)

        self.ipc.emit("step", f"Theme and configuration staged into {self.target_theme_dir.name} with strict permissions (755/644).")
        return True

    # =========================================================================
    # D. SYNTAX VALIDATION (grub-script-check on generated temp config)
    # =========================================================================
    def validate_syntax(self) -> bool:
        self.ipc.emit("info", "Phase 4/5: Running pre-flight dry-run syntax verification...", progress=65)

        if self.dry_run:
            self.ipc.emit("step", "[DRY-RUN] Syntax check passed (simulated).")
            return True

        if not self.script_check_tool or not shutil.which(self.script_check_tool):
            self.ipc.emit("warn", f"Validator tool ({self.script_check_tool}) not found; checking theme.txt syntax.")
            theme_txt = self.target_theme_dir / "theme.txt"
            if theme_txt.is_file():
                txt = theme_txt.read_text(encoding="utf-8", errors="replace")
                if txt.count("{") != txt.count("}"):
                    self.ipc.emit("error", "Theme syntax error: Mismatched braces.")
                    return False
            return True

        with tempfile.NamedTemporaryFile(prefix="grub_forge_val_", suffix=".cfg", delete=False) as tf:
            val_cfg_path = Path(tf.name)

        try:
            # Generate test configuration directly into temp file
            test_cmd = list(self.update_command)
            if "-o" in test_cmd:
                idx = test_cmd.index("-o")
                if idx + 1 < len(test_cmd):
                    test_cmd[idx + 1] = str(val_cfg_path)
            else:
                test_cmd = [test_cmd[0]]

            res = subprocess.run(test_cmd, capture_output=True, text=True, check=False)

            if val_cfg_path.stat().st_size == 0 and res.stdout:
                val_cfg_path.write_text(res.stdout, encoding="utf-8")

            # Validate using grub-script-check
            check_res = subprocess.run(
                [self.script_check_tool, str(val_cfg_path)],
                capture_output=True,
                text=True,
                check=False
            )

            if check_res.returncode != 0:
                err = check_res.stderr or check_res.stdout or "Syntax check failed."
                self.ipc.emit("error", f"grub-script-check rejected generated configuration:\n{err}")
                return False

            self.ipc.emit("step", "Pre-flight syntax validation PASSED with zero errors.")
            return True
        except Exception as e:
            self.ipc.emit("error", f"Syntax verification threw exception: {e}")
            return False
        finally:
            if val_cfg_path.exists():
                val_cfg_path.unlink(missing_ok=True)

    # =========================================================================
    # E. FINAL EXECUTION & F. REAL-TIME STREAMING
    # =========================================================================
    def execute_bootloader_rebuild(self) -> bool:
        self.ipc.emit("info", f"Phase 5/5: Executing bootloader update ({' '.join(self.update_command)})...", progress=85)

        if self.dry_run:
            self.ipc.emit("step", "Generating grub configuration file ...")
            self.ipc.emit("step", "Found linux image: /boot/vmlinuz-linux")
            self.ipc.emit("step", f"Found theme: {self.target_theme_dir}/theme.txt")
            self.ipc.emit("success", "Bootloader rebuild successfully simulated.", progress=100)
            return True

        try:
            process = subprocess.Popen(
                self.update_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    line_clean = line.rstrip()
                    if line_clean:
                        self.ipc.emit("step", line_clean)

            process.wait()
            if process.returncode == 0:
                self.ipc.emit("success", "Bootloader updated successfully with return code 0.", progress=100)
                return True
            else:
                self.ipc.emit("error", f"Update command failed with exit code {process.returncode}.")
                return False

        except Exception as e:
            self.ipc.emit("error", f"Execution failed: {e}")
            return False

    def rollback(self):
        """Reverts files to the active snapshot."""
        if not self.active_snapshot_dir or not self.active_snapshot_dir.is_dir():
            self.ipc.emit("error", "Rollback failed: No active snapshot directory available.")
            return

        self.ipc.emit("warn", f"Triggering automated rollback to {self.active_snapshot_dir.name}...")

        # Restore /etc/default/grub
        snap_default = self.active_snapshot_dir / "grub"
        if snap_default.is_file():
            shutil.copy2(snap_default, self.target_default_cfg)
            self.ipc.emit("step", f"Restored {self.target_default_cfg}")

        # Restore active grub.cfg
        snap_cfg = self.active_snapshot_dir / "grub.cfg"
        if snap_cfg.is_file():
            shutil.copy2(snap_cfg, self.target_active_cfg)
            self.ipc.emit("step", f"Restored {self.target_active_cfg}")

        # Re-run update command if possible
        if not self.dry_run and shutil.which(self.update_command[0]):
            try:
                subprocess.run(self.update_command, capture_output=True, check=False)
            except Exception:
                pass

        self.ipc.emit("warn", "System rollback finalized.")


def main():
    parser = argparse.ArgumentParser(description="GRUB Forge Elevated Root Worker")
    parser.add_argument("--apply", type=str, required=True, help="Path to staged payload directory")
    parser.add_argument("--json-ipc", action="store_true", help="Emit structured JSON IPC lines")
    args = parser.parse_args()

    staged_path = Path(args.apply)
    ipc = IPCReporter(use_json=args.json_ipc)

    ipc.emit("info", "=== [GRUB FORGE ELEVATED WORKER ACTIVATED] ===")

    try:
        worker = RootWorker(staged_path, ipc)

        # Step A: Pre-Flight Mount & Space Verification
        if not worker.verify_preflight_mount_and_space():
            sys.exit(2)

        # Step B: Immutable Snapshot Creation
        worker.create_immutable_snapshot()

        # Step C: Atomic File Copy & Permission Enforcing
        if not worker.deploy_staged_assets():
            worker.rollback()
            sys.exit(3)

        # Step D: Syntax Validation
        if not worker.validate_syntax():
            worker.rollback()
            sys.exit(4)

        # Step E: Final Execution
        if not worker.execute_bootloader_rebuild():
            worker.rollback()
            sys.exit(5)

        ipc.emit("success", "=== [TRANSACTION COMPLETED WITH ZERO ERRORS] ===")
        sys.exit(0)

    except Exception as e:
        ipc.emit("error", f"Worker fatal exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

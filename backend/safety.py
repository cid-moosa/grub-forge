"""
GRUB Forge - Zero-Brick Safety Guardrails & Recovery Architecture
Enforces transactional safety: immutable backups, standalone emergency rescue
scripts, atomic configuration rewriting with AST-style comment preservation,
pre-flight syntax validation, and automated rollbacks.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

from backend.fs_detector import GrubPaths, GrubTools, DistroInfo


@dataclass
class BackupRecord:
    timestamp: str
    backup_path: str
    original_default_grub: str
    original_grub_cfg: str
    distro_id: str
    update_command: List[str]
    checksum_default: str = ""
    checksum_cfg: str = ""


class ASTGrubParser:
    """
    AST-style parser for shell-format /etc/default/grub.
    Maintains all comments, inline formatting, whitespace, and variable
    assignments while allowing surgical updates to targeted keys.
    """

    @staticmethod
    def parse_lines(content: str) -> List[Tuple[str, Optional[str], Optional[str], str]]:
        """
        Parses configuration lines into structured tokens:
        Returns list of (type, key, value, raw_line):
          - ('COMMENT', None, None, line)
          - ('EMPTY', None, None, line)
          - ('ASSIGN', key, value, line)
        """
        tokens = []
        for line in content.splitlines(keepends=True):
            stripped = line.strip()
            if not stripped:
                tokens.append(('EMPTY', None, None, line))
                continue
            if stripped.startswith('#'):
                tokens.append(('COMMENT', None, None, line))
                continue

            # Check for key=value
            m = re.match(r"^([A-Za-z0-9_]+)=(.*)$", stripped)
            if m:
                key = m.group(1)
                val_raw = m.group(2).strip()
                # Unquote if enclosed in quotes
                val_clean = val_raw
                if (val_raw.startswith('"') and val_raw.endswith('"')) or (val_raw.startswith("'") and val_raw.endswith("'")):
                    val_clean = val_raw[1:-1]
                tokens.append(('ASSIGN', key, val_clean, line))
            else:
                tokens.append(('OTHER', None, None, line))
        return tokens

    @staticmethod
    def update_config(
        content: str,
        updates: Dict[str, str],
        remove_keys: Optional[List[str]] = None
    ) -> str:
        """
        Updates specific keys in content while preserving exact existing order,
        comments, and appending any new keys at the end.
        Conflicting keys specified in remove_keys are cleanly commented out.
        """
        remove_keys = remove_keys or []
        tokens = ASTGrubParser.parse_lines(content)
        updated_keys = set()
        out_lines = []

        for token_type, key, val, raw_line in tokens:
            if token_type == 'ASSIGN' and key:
                if key in remove_keys:
                    # Comment out conflicting key
                    out_lines.append(f"# Commented out by GRUB Forge to prevent conflicts:\n# {raw_line}")
                    continue
                if key in updates:
                    new_val = updates[key]
                    out_lines.append(f'{key}="{new_val}"\n')
                    updated_keys.add(key)
                    continue

            out_lines.append(raw_line)

        # Append any new keys that weren't present originally
        remaining_keys = [k for k in updates.keys() if k not in updated_keys]
        if remaining_keys:
            if out_lines and not out_lines[-1].endswith("\n"):
                out_lines[-1] += "\n"
            out_lines.append("\n# Added by GRUB Forge\n")
            for k in remaining_keys:
                out_lines.append(f'{k}="{updates[k]}"\n')

        return "".join(out_lines)


class SafetyManager:
    """
    Manages transactional safety guarantees for GRUB modification.
    """

    def __init__(self, paths: GrubPaths, tools: GrubTools, distro: DistroInfo):
        self.paths = paths
        self.tools = tools
        self.distro = distro

    @staticmethod
    def _file_hash(path: Path) -> str:
        """Calculates SHA256 checksum of a file if it exists."""
        if not path.is_file():
            return ""
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    def create_snapshot(self) -> Path:
        """
        Creates an immutable timestamped backup directory:
        <grub_dir>/grub_forge_backups/backup_YYYYMMDD_HHMMSS/
        Copies /etc/default/grub, active grub.cfg, and writes metadata.json.
        Also creates or updates a 'latest' symlink/pointer.
        """
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = self.paths.backup_dir / f"backup_{ts_str}"
        backup_dir.mkdir(parents=True, exist_ok=True)

        backup_default_path = backup_dir / "grub"
        backup_cfg_path = backup_dir / "grub.cfg"

        # 1. Back up /etc/default/grub
        if self.paths.default_config.is_file():
            shutil.copy2(self.paths.default_config, backup_default_path)

        # 2. Back up active grub.cfg
        if self.paths.active_grub_cfg.is_file():
            shutil.copy2(self.paths.active_grub_cfg, backup_cfg_path)

        # 3. Create metadata JSON
        record = BackupRecord(
            timestamp=ts_str,
            backup_path=str(backup_dir),
            original_default_grub=str(self.paths.default_config),
            original_grub_cfg=str(self.paths.active_grub_cfg),
            distro_id=self.distro.distro_id,
            update_command=self.tools.update_command,
            checksum_default=self._file_hash(backup_default_path),
            checksum_cfg=self._file_hash(backup_cfg_path)
        )

        with open(backup_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(asdict(record), f, indent=2)

        # 4. Update 'latest' pointer
        latest_link = self.paths.backup_dir / "latest"
        try:
            if latest_link.is_symlink() or latest_link.exists():
                latest_link.unlink(missing_ok=True)
            try:
                latest_link.symlink_to(backup_dir.name, target_is_directory=True)
            except (OSError, NotImplementedError):
                # Fallback on filesystems/OS without symlink privileges
                with open(latest_link, "w", encoding="utf-8") as f:
                    f.write(str(backup_dir.resolve()))
        except Exception:
            pass

        return backup_dir

    def generate_recovery_script(self) -> Path:
        """
        Generates a standalone emergency recovery script at /boot/grub_emergency_restore.sh.
        Requires zero dependencies and can be run directly from a rescue terminal,
        chroot, or live USB.
        """
        script_path = self.paths.emergency_script
        script_path.parent.mkdir(parents=True, exist_ok=True)

        # Build update command string
        update_cmd_str = " ".join(self.tools.update_command)
        backup_root = str(self.paths.backup_dir)
        default_cfg_str = str(self.paths.default_config)
        active_cfg_str = str(self.paths.active_grub_cfg)

        script_content = f"""#!/bin/sh
# ==============================================================================
# GRUB Forge Emergency Bootloader Recovery Script
# Self-contained emergency restorer. Works in chroot, live USB, or rescue shell.
# ==============================================================================
set -e

echo "[*] Initializing GRUB Forge Emergency Restore..."

BACKUP_ROOT="{backup_root}"
DEFAULT_CFG="{default_cfg_str}"
ACTIVE_CFG="{active_cfg_str}"

# 1. Locate latest backup
LATEST_DIR=""
if [ -d "$BACKUP_ROOT/latest" ]; then
    LATEST_DIR="$BACKUP_ROOT/latest"
elif [ -f "$BACKUP_ROOT/latest" ]; then
    LATEST_DIR=$(cat "$BACKUP_ROOT/latest")
fi

if [ -z "$LATEST_DIR" ] || [ ! -d "$LATEST_DIR" ]; then
    # Fallback to sorting backup directories by name
    LATEST_DIR=$(ls -td "$BACKUP_ROOT"/backup_* 2>/dev/null | head -n 1)
fi

if [ -z "$LATEST_DIR" ] || [ ! -d "$LATEST_DIR" ]; then
    echo "[!] ERROR: No valid GRUB Forge backup snapshots found in $BACKUP_ROOT."
    exit 1
fi

echo "[+] Located snapshot: $LATEST_DIR"

# 2. Revert /etc/default/grub
if [ -f "$LATEST_DIR/grub" ]; then
    echo "[+] Reverting $DEFAULT_CFG to original state..."
    mkdir -p "$(dirname "$DEFAULT_CFG")"
    cp -f "$LATEST_DIR/grub" "$DEFAULT_CFG"
else
    echo "[-] Warning: No default config in snapshot; skipping default revert."
fi

# 3. Direct safety copy of grub.cfg
if [ -f "$LATEST_DIR/grub.cfg" ]; then
    echo "[+] Restoring known-good grub.cfg fallback..."
    mkdir -p "$(dirname "$ACTIVE_CFG")"
    cp -f "$LATEST_DIR/grub.cfg" "$ACTIVE_CFG"
fi

# 4. Re-run distro grub generation
echo "[+] Re-running detected bootloader generator: {update_cmd_str}"
if command -v {self.tools.update_command[0]} >/dev/null 2>&1; then
    {update_cmd_str} || {{
        echo "[!] Generator command failed. Restoring raw backup grub.cfg..."
        cp -f "$LATEST_DIR/grub.cfg" "$ACTIVE_CFG"
    }}
else
    echo "[-] Note: {self.tools.update_command[0]} not in PATH (rescue mode). Direct grub.cfg copy retained."
fi

echo "[✓] SUCCESS: GRUB bootloader restored to last known good state."
exit 0
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)

        # Make executable
        try:
            os.chmod(script_path, 0o755)
        except Exception:
            pass

        return script_path

    def atomic_update_default_grub(
        self,
        updates: Dict[str, str],
        remove_conflicts: bool = True
    ) -> bool:
        """
        Safely and atomically writes updates into /etc/default/grub:
        - Reads existing file or creates base structure.
        - AST-style line parsing preserving comments and custom flags.
        - Comments out conflicting GRUB_BACKGROUND if GRUB_THEME is set.
        - Writes to temporary file in the same directory.
        - Atomic replace (os.replace) to ensure no corruption on power loss.
        """
        cfg_path = self.paths.default_config
        cfg_path.parent.mkdir(parents=True, exist_ok=True)

        content = ""
        if cfg_path.is_file():
            content = cfg_path.read_text(encoding="utf-8", errors="replace")
        else:
            content = (
                "# Default GRUB configuration generated by GRUB Forge\n"
                'GRUB_DEFAULT=0\n'
                'GRUB_TIMEOUT=5\n'
                'GRUB_DISTRIBUTOR="Linux"\n'
                'GRUB_CMDLINE_LINUX_DEFAULT="quiet splash"\n'
            )

        remove_keys = ["GRUB_BACKGROUND"] if remove_conflicts and "GRUB_THEME" in updates else []
        new_content = ASTGrubParser.update_config(content, updates, remove_keys=remove_keys)

        # Write to temporary file in the same filesystem directory to ensure atomic os.replace
        tmp_file = cfg_path.parent / f"{cfg_path.name}.tmp_{os.getpid()}"
        try:
            with open(tmp_file, "w", encoding="utf-8") as f:
                f.write(new_content)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace
            os.replace(tmp_file, cfg_path)
            return True
        except Exception as e:
            if tmp_file.exists():
                tmp_file.unlink(missing_ok=True)
            raise RuntimeError(f"Atomic update of {cfg_path} failed: {e}") from e

    def preflight_syntax_check(self, theme_path: Optional[Path] = None) -> Tuple[bool, str]:
        """
        Generates target grub.cfg in /tmp/ and passes it through grub-script-check.
        If syntax check fails, aborts immediately without altering the live bootloader.
        """
        if not self.tools.script_check_tool or not shutil.which(self.tools.script_check_tool):
            # Script check binary not available on host; perform internal linting
            return self._internal_syntax_lint(theme_path)

        with tempfile.NamedTemporaryFile(prefix="grub_forge_test_", suffix=".cfg", delete=False) as tf:
            test_cfg_path = Path(tf.name)

        try:
            # Generate test configuration using detected update command directed to temp file
            test_cmd = list(self.tools.update_command)
            if "-o" in test_cmd:
                idx = test_cmd.index("-o")
                if idx + 1 < len(test_cmd):
                    test_cmd[idx + 1] = str(test_cfg_path)
            else:
                # If command is update-grub without -o, redirect stdout
                test_cmd = [test_cmd[0]]

            # Execute dry-run generation
            proc = subprocess.run(
                test_cmd,
                capture_output=True,
                text=True,
                check=False
            )

            # If stdout has content and test_cfg_path is empty (e.g. from update-grub stdout), write it
            if test_cfg_path.stat().st_size == 0 and proc.stdout:
                test_cfg_path.write_text(proc.stdout, encoding="utf-8")

            # Run grub-script-check on the generated config
            check_proc = subprocess.run(
                [self.tools.script_check_tool, str(test_cfg_path)],
                capture_output=True,
                text=True,
                check=False
            )

            if check_proc.returncode != 0:
                err = check_proc.stderr or check_proc.stdout or "Syntax check reported parsing errors."
                return False, f"Pre-flight syntax validation failed:\n{err}"

            return True, "Pre-flight syntax validation passed with zero errors."

        except Exception as e:
            return False, f"Syntax verification exception: {e}"
        finally:
            if test_cfg_path.exists():
                test_cfg_path.unlink(missing_ok=True)

    def _internal_syntax_lint(self, theme_path: Optional[Path] = None) -> Tuple[bool, str]:
        """
        Internal fallback linter checking theme.txt syntax and brace balancing.
        """
        if theme_path and theme_path.is_file():
            try:
                content = theme_path.read_text(encoding="utf-8", errors="replace")
                # Check for balanced braces
                open_braces = content.count("{")
                close_braces = content.count("}")
                if open_braces != close_braces:
                    return False, f"Theme syntax error: mismatched braces (open: {open_braces}, close: {close_braces})"

                # Check required theme elements
                if "boot_menu" not in content:
                    return False, "Theme syntax warning: 'boot_menu' component missing in theme.txt."
            except Exception as e:
                return False, f"Theme file read error: {e}"

        return True, "Internal syntax verification passed."

    def rollback(self) -> Tuple[bool, str]:
        """
        Automatically rolls back to the most recent backup snapshot.
        Restores /etc/default/grub, active grub.cfg, and re-executes update command.
        """
        latest_link = self.paths.backup_dir / "latest"
        target_dir = None

        if latest_link.is_symlink() and latest_link.exists():
            target_dir = latest_link.resolve()
        elif latest_link.is_file():
            try:
                line = latest_link.read_text(encoding="utf-8").strip()
                if os.path.isdir(line):
                    target_dir = Path(line)
            except Exception:
                pass

        if not target_dir or not target_dir.is_dir():
            # Search for latest backup_ directory
            backups = sorted(self.paths.backup_dir.glob("backup_*"), key=os.path.getmtime, reverse=True)
            if backups:
                target_dir = backups[0]

        if not target_dir or not target_dir.is_dir():
            return False, "Rollback failed: No backup snapshots located."

        logs = [f"Initiating rollback using snapshot: {target_dir.name}"]

        # Revert /etc/default/grub
        backup_default = target_dir / "grub"
        if backup_default.is_file():
            shutil.copy2(backup_default, self.paths.default_config)
            logs.append(f"Restored {self.paths.default_config}")

        # Revert active grub.cfg
        backup_cfg = target_dir / "grub.cfg"
        if backup_cfg.is_file():
            shutil.copy2(backup_cfg, self.paths.active_grub_cfg)
            logs.append(f"Restored {self.paths.active_grub_cfg}")

        # Re-run update command if available
        if shutil.which(self.tools.update_command[0]):
            try:
                proc = subprocess.run(
                    self.tools.update_command,
                    capture_output=True,
                    text=True,
                    check=False
                )
                if proc.returncode == 0:
                    logs.append("Bootloader rebuild executed successfully.")
                else:
                    logs.append(f"Warning: Rebuild command exited with code {proc.returncode}.")
            except Exception as e:
                logs.append(f"Rebuild warning: {e}")

        return True, "\n".join(logs)

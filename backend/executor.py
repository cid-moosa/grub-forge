"""
GRUB Forge - Privilege Escalation & Staged Execution Runner
Launches the elevated worker (backend/worker.py or /usr/libexec/grub-forge-worker)
via Polkit (pkexec) inside a non-blocking QThread, streaming line-by-line IPC back to the GUI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class ElevatedWorkerThread(QThread):
    """
    Non-blocking worker thread executing pkexec /usr/libexec/grub-forge-worker --apply <staged_dir>
    and parsing line-by-line streaming IPC.
    """
    line_received = pyqtSignal(str)
    progress_updated = pyqtSignal(int, str)
    finished = pyqtSignal(int, str)

    SYSTEM_WORKER_PATH = Path("/usr/libexec/grub-forge-worker")

    def __init__(self, staged_dir: Path, use_pkexec: bool = True, dry_run: bool = False):
        super().__init__()
        self.staged_dir = staged_dir
        self.use_pkexec = use_pkexec
        self.dry_run = dry_run
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def _resolve_worker_command(self) -> List[str]:
        # 1. Check system installed worker
        if self.SYSTEM_WORKER_PATH.is_file() and os.access(self.SYSTEM_WORKER_PATH, os.X_OK):
            worker_cmd = [str(self.SYSTEM_WORKER_PATH)]
        else:
            # 2. Local module fallback
            local_worker = Path(__file__).resolve().parent / "worker.py"
            worker_cmd = [sys.executable, str(local_worker)]

        worker_args = ["--apply", str(self.staged_dir)]

        # 3. Add pkexec if not running as root on Linux
        is_linux = sys.platform.startswith("linux")
        is_root = False
        if is_linux and hasattr(os, "geteuid"):
            is_root = (os.geteuid() == 0)

        if self.use_pkexec and is_linux and not is_root and not self.dry_run:
            if shutil.which("pkexec"):
                return ["pkexec"] + worker_cmd + worker_args
            elif shutil.which("sudo"):
                return ["sudo"] + worker_cmd + worker_args

        return worker_cmd + worker_args

    def run(self):
        cmd = self._resolve_worker_command()
        cmd_display = " ".join(cmd)
        self.line_received.emit(f"[*] Invoking privilege boundary: {cmd_display}")

        combined_lines = []
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    if self._is_cancelled:
                        process.terminate()
                        break
                    line_clean = line.rstrip()
                    if not line_clean:
                        continue

                    # Handle IPC JSON payloads if emitted
                    if line_clean.startswith("__IPC_JSON__"):
                        try:
                            payload = json.loads(line_clean[len("__IPC_JSON__"):])
                            msg = payload.get("message", "")
                            prog = payload.get("progress")
                            if prog is not None:
                                self.progress_updated.emit(prog, msg)
                            self.line_received.emit(msg)
                            combined_lines.append(msg)
                            continue
                        except Exception:
                            pass

                    combined_lines.append(line_clean)
                    self.line_received.emit(line_clean)

            process.wait()
            exit_code = process.returncode
            if exit_code == 0:
                self.line_received.emit(f"[✓] Elevated worker succeeded with exit code 0.")
            else:
                self.line_received.emit(f"[!] Elevated worker terminated with error code {exit_code}.")

            self.finished.emit(exit_code, "\n".join(combined_lines))

        except FileNotFoundError as e:
            err = f"Worker binary not found: {e}"
            self.line_received.emit(f"[!] {err}")
            self.finished.emit(127, err)
        except Exception as e:
            err = f"Worker execution exception: {e}"
            self.line_received.emit(f"[!] {err}")
            self.finished.emit(1, err)


class CommandExecutor(QObject):
    """
    High-level facade coordinating unprivileged staging and elevated execution.
    """
    output_line = pyqtSignal(str)
    progress_changed = pyqtSignal(int, str)
    operation_finished = pyqtSignal(bool, str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._current_worker: Optional[ElevatedWorkerThread] = None

    def execute_staged_deployment(self, staged_dir: Path, use_pkexec: bool = True, dry_run: bool = False):
        """Launches the elevated worker thread on the staged directory."""
        if self._current_worker and self._current_worker.isRunning():
            self.output_line.emit("[!] An elevated task is already active.")
            return

        self._current_worker = ElevatedWorkerThread(staged_dir, use_pkexec=use_pkexec, dry_run=dry_run)
        self._current_worker.line_received.connect(self.output_line)
        self._current_worker.progress_updated.connect(self.progress_changed)
        self._current_worker.finished.connect(self._on_worker_completed)
        self._current_worker.start()

    def apply_staged_theme(self, staged_dir: Path, use_pkexec: bool = True, dry_run: bool = False):
        """Alias for execute_staged_deployment called by GUI main window."""
        self.execute_staged_deployment(staged_dir=staged_dir, use_pkexec=use_pkexec, dry_run=dry_run)

    def _on_worker_completed(self, exit_code: int, logs: str):
        success = (exit_code == 0)
        self.operation_finished.emit(success, logs)

    @staticmethod
    def trigger_reboot() -> bool:
        """Invokes systemctl reboot."""
        for cmd in (["systemctl", "reboot"], ["shutdown", "-r", "now"]):
            if shutil.which(cmd[0]):
                try:
                    subprocess.run(cmd, check=False)
                    return True
                except Exception:
                    pass
        return False

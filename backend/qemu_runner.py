"""
GRUB Forge - QEMU Virtual Boot Harness
Provides an isolated, emulated test environment to preview staged GRUB themes
in an emulated virtual machine window prior to live bootloader deployment.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple


@dataclass
class QemuCapabilities:
    has_qemu: bool
    qemu_bin: Optional[str]
    has_kvm: bool
    ovmf_bios: Optional[Path]
    ovmf_vars: Optional[Path]


class QemuRunner:
    """
    Constructs an ephemeral virtual boot medium and spawns QEMU to preview
    the staged GRUB theme in real time.
    """

    OVMF_CODE_PATHS = [
        Path("/usr/share/OVMF/OVMF_CODE.fd"),
        Path("/usr/share/ovmf/x64/OVMF_CODE.fd"),
        Path("/usr/share/edk2-ovmf/x64/OVMF_CODE.fd"),
        Path("/usr/share/edk2/ovmf/OVMF_CODE.fd"),
        Path("/usr/share/qemu/ovmf-x86_64-code.bin"),
    ]

    OVMF_VARS_PATHS = [
        Path("/usr/share/OVMF/OVMF_VARS.fd"),
        Path("/usr/share/ovmf/x64/OVMF_VARS.fd"),
        Path("/usr/share/edk2-ovmf/x64/OVMF_VARS.fd"),
        Path("/usr/share/edk2/ovmf/OVMF_VARS.fd"),
        Path("/usr/share/qemu/ovmf-x86_64-vars.bin"),
    ]

    def __init__(self, workspace_dir: Optional[Path] = None):
        self._custom_workspace = workspace_dir
        self._active_process: Optional[subprocess.Popen] = None
        self.capabilities = self.detect_capabilities()

    @classmethod
    def detect_capabilities(cls) -> QemuCapabilities:
        """Inspects host system for QEMU binary, KVM acceleration, and OVMF UEFI firmware."""
        qemu_bin = None
        for candidate in ("qemu-system-x86_64", "qemu-kvm"):
            if shutil.which(candidate):
                qemu_bin = candidate
                break

        has_kvm = False
        if sys.platform.startswith("linux"):
            has_kvm = os.path.exists("/dev/kvm") and os.access("/dev/kvm", os.R_OK | os.W_OK)

        ovmf_code = None
        for p in cls.OVMF_CODE_PATHS:
            if p.is_file():
                ovmf_code = p
                break

        ovmf_vars = None
        for p in cls.OVMF_VARS_PATHS:
            if p.is_file():
                ovmf_vars = p
                break

        return QemuCapabilities(
            has_qemu=(qemu_bin is not None),
            qemu_bin=qemu_bin,
            has_kvm=has_kvm,
            ovmf_bios=ovmf_code,
            ovmf_vars=ovmf_vars
        )

    def prepare_virtual_disk(
        self,
        staged_dir: Path,
        menu_entries: List[str],
        resolution: Tuple[int, int] = (1024, 768),
        timeout_seconds: int = 5
    ) -> Path:
        """
        Creates an ephemeral directory structured as a FAT virtual disk
        containing GRUB core, the staged theme assets, and an emulated grub.cfg.
        """
        base_dir = self._custom_workspace or (Path(tempfile.gettempdir()) / "grub_forge_qemu")
        if base_dir.exists():
            shutil.rmtree(base_dir, ignore_errors=True)
        base_dir.mkdir(parents=True, exist_ok=True)

        boot_dir = base_dir / "boot" / "grub"
        theme_dest_dir = boot_dir / "themes" / "grub_forge_theme"
        theme_dest_dir.mkdir(parents=True, exist_ok=True)

        # 1. Copy staged theme assets into virtual disk
        staged_theme = staged_dir / "theme"
        if staged_theme.is_dir():
            for item in staged_theme.iterdir():
                if item.is_file():
                    shutil.copy2(item, theme_dest_dir / item.name)

        # 2. Build test grub.cfg simulating runtime bootloader menu
        entries_block = []
        for idx, name in enumerate(menu_entries or ["Test Linux OS", "Advanced Recovery", "UEFI Settings"]):
            entries_block.append(f"""
menuentry "{name}" --class gnu-linux {{
    echo "Simulated boot: {name}"
    echo "Press ESC or wait to return to menu..."
    sleep 2
}}""")

        cfg_content = f"""# GRUB Forge Virtual QEMU Test Configuration
set default="0"
set timeout="{timeout_seconds}"

# Load video and graphical environment
insmod all_video
insmod gfxterm
insmod png
insmod jpeg
terminal_output gfxterm

set gfxmode="{resolution[0]}x{resolution[1]},auto"

# Load Staged Theme
set theme="/boot/grub/themes/grub_forge_theme/theme.txt"
export theme

# Menu Entries
{"".join(entries_block)}
"""
        (boot_dir / "grub.cfg").write_text(cfg_content, encoding="utf-8")

        # 3. Create simulated EFI boot stub if on EFI systems
        efi_dir = base_dir / "EFI" / "BOOT"
        efi_dir.mkdir(parents=True, exist_ok=True)

        # Check if host has an existing grubx64.efi or bootx64.efi to use
        host_efi_candidates = [
            Path("/boot/efi/EFI/BOOT/BOOTX64.EFI"),
            Path("/boot/efi/EFI/boot/bootx64.efi"),
            Path("/usr/lib/grub/x86_64-efi/monolithic/grubx64.efi"),
            Path("/usr/lib/grub/x86_64-efi/grub.efi"),
        ]
        found_efi = False
        for cand in host_efi_candidates:
            if cand.is_file():
                try:
                    shutil.copy2(cand, efi_dir / "bootx64.efi")
                    found_efi = True
                    break
                except Exception:
                    pass

        if not found_efi:
            (efi_dir / "bootx64.efi").write_bytes(b"GRUB_FORGE_VIRTUAL_EFI_STUB")

        return base_dir

    def build_qemu_command(
        self,
        virtual_disk_dir: Path,
        resolution: Tuple[int, int] = (1024, 768),
        force_tcg: bool = False
    ) -> List[str]:
        """Constructs the QEMU command line with optimal acceleration and display parameters."""
        qemu_bin = self.capabilities.qemu_bin or "qemu-system-x86_64"

        cmd = [
            qemu_bin,
            "-m", "512M",
            "-vga", "std",
            "-name", f"GRUB Forge Virtual Testbench ({resolution[0]}x{resolution[1]})",
            "-drive", f"file=fat:rw:{virtual_disk_dir},format=raw",
            "-boot", "order=d,menu=on"
        ]

        # KVM hardware acceleration check
        if self.capabilities.has_kvm and not force_tcg:
            cmd.extend(["-enable-kvm", "-cpu", "host"])
        else:
            cmd.extend(["-cpu", "qemu64"])

        # UEFI OVMF firmware if available
        if self.capabilities.ovmf_bios and self.capabilities.ovmf_bios.is_file():
            cmd.extend([
                "-drive", f"if=pflash,format=raw,readonly=on,file={self.capabilities.ovmf_bios}"
            ])

        return cmd

    def launch(
        self,
        virtual_disk_dir: Path,
        resolution: Tuple[int, int] = (1024, 768),
        force_tcg: bool = False
    ) -> Tuple[bool, str]:
        """Launches QEMU in a detached non-blocking child process."""
        if not self.capabilities.has_qemu and not shutil.which("qemu-system-x86_64"):
            return False, "QEMU binary (qemu-system-x86_64) is not installed on this system."

        if self._active_process and self._active_process.poll() is None:
            return False, "A virtual machine preview session is already active."

        cmd = self.build_qemu_command(virtual_disk_dir, resolution=resolution, force_tcg=force_tcg)

        try:
            self._active_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True
            )
            return True, f"Virtual testbench started (PID {self._active_process.pid})."
        except Exception as e:
            return False, f"Failed to launch QEMU: {e}"

    def terminate(self):
        """Cleanly terminates the QEMU child process if running."""
        if self._active_process and self._active_process.poll() is None:
            try:
                self._active_process.terminate()
                self._active_process.wait(timeout=2)
            except Exception:
                try:
                    self._active_process.kill()
                except Exception:
                    pass
            self._active_process = None

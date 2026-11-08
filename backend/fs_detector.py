"""
GRUB Forge - Filesystem & Distro Discovery Engine
Provides dynamic runtime resolution of Linux distributions, partition topologies,
mount attributes, theme directories, target grub.cfg locations, and toolchains.
Hardcoded paths are strictly avoided.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict, Tuple


@dataclass
class DistroInfo:
    """Fingerprint of the host operating system."""
    distro_id: str
    name: str
    id_like: List[str] = field(default_factory=list)
    version_id: str = ""
    is_mock: bool = False

    @property
    def is_debian_like(self) -> bool:
        family = [self.distro_id] + self.id_like
        return any(d in family for d in ("debian", "ubuntu", "linuxmint", "pop", "kali"))

    @property
    def is_arch_like(self) -> bool:
        family = [self.distro_id] + self.id_like
        return any(d in family for d in ("arch", "manjaro", "endeavouros", "artix", "garuda"))

    @property
    def is_fedora_like(self) -> bool:
        family = [self.distro_id] + self.id_like
        return any(d in family for d in ("fedora", "rhel", "centos", "rocky", "alma"))

    @property
    def is_suse_like(self) -> bool:
        family = [self.distro_id] + self.id_like
        return any(d in family for d in ("opensuse", "opensuse-tumbleweed", "opensuse-leap", "suse", "sles"))


@dataclass
class FilesystemInfo:
    """Mount and filesystem attributes for /boot."""
    boot_target: str
    fstype: str
    is_separate_boot: bool
    is_btrfs: bool
    subvolume: Optional[str] = None
    is_read_only: bool = False
    options: List[str] = field(default_factory=list)
    efi_mounted: bool = False
    efi_path: Optional[str] = None
    relative_grub_prefix: str = "/boot"


@dataclass
class GrubPaths:
    """Resolved file and directory paths for GRUB customization."""
    default_config: Path
    grub_dir: Path
    active_grub_cfg: Path
    theme_dir: Path
    fallback_theme_dir: Path
    backup_dir: Path
    emergency_script: Path
    efi_stub_cfg: Optional[Path] = None


@dataclass
class GrubTools:
    """Resolved command strings and validation binaries."""
    update_command: List[str]
    update_tool_name: str
    script_check_tool: Optional[str]
    has_script_check: bool = False


@dataclass
class SystemTelemetry:
    """Comprehensive system inspection state."""
    distro: DistroInfo
    fs: FilesystemInfo
    paths: GrubPaths
    tools: GrubTools
    kernel_version: str = "Unknown"
    grub_version: str = "GRUB 2.x"


class FSDetector:
    """
    Dynamic discovery engine for multi-distro and filesystem topologies.
    """

    def __init__(self, root_prefix: str = ""):
        self.root_prefix = root_prefix

    def _apply_prefix(self, path_str: str) -> Path:
        """Appends an optional testing root prefix to standard system paths."""
        if not self.root_prefix:
            return Path(path_str)
        clean = path_str.lstrip("/\\")
        return Path(self.root_prefix) / clean

    def detect_distro(self) -> DistroInfo:
        """
        Fingerprints the running distribution by parsing /etc/os-release,
        falling back to lsb_release, or falling back to environment mock.
        """
        mock_env = os.environ.get("GRUB_FORGE_MOCK_DISTRO")
        os_release = self._apply_prefix("/etc/os-release")
        alt_os_release = self._apply_prefix("/usr/lib/os-release")

        target_release = None
        if os_release.is_file():
            target_release = os_release
        elif alt_os_release.is_file():
            target_release = alt_os_release

        if target_release:
            distro_id = ""
            name = ""
            id_like: List[str] = []
            version_id = ""

            try:
                with open(target_release, "r", encoding="utf-8", errors="replace") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k == "ID":
                            distro_id = v.lower()
                        elif k == "NAME":
                            name = v
                        elif k == "ID_LIKE":
                            id_like = [x.strip().lower() for x in v.split()]
                        elif k == "VERSION_ID":
                            version_id = v

                if not name and distro_id:
                    name = distro_id.capitalize()

                if distro_id:
                    return DistroInfo(
                        distro_id=distro_id,
                        name=name,
                        id_like=id_like,
                        version_id=version_id,
                        is_mock=False
                    )
            except Exception:
                pass

        # Fallback to lsb_release command if available
        if shutil.which("lsb_release"):
            try:
                out = subprocess.check_output(["lsb_release", "-a"], text=True, stderr=subprocess.DEVNULL)
                distro_id = ""
                name = ""
                for line in out.splitlines():
                    if ":" in line:
                        k, v = line.split(":", 1)
                        k, v = k.strip(), v.strip()
                        if "Distributor ID" in k:
                            distro_id = v.lower()
                        elif "Description" in k:
                            name = v
                if distro_id:
                    return DistroInfo(
                        distro_id=distro_id,
                        name=name or distro_id.capitalize(),
                        id_like=[distro_id],
                        is_mock=False
                    )
            except Exception:
                pass

        # Mock fallback for development / non-Linux host testing
        mock_id = mock_env.lower() if mock_env else "arch"
        mock_names = {
            "debian": ("Debian GNU/Linux 12 (bookworm)", ["debian"]),
            "arch": ("Arch Linux", ["arch"]),
            "fedora": ("Fedora Linux 41 (Workstation Edition)", ["fedora", "rhel"]),
            "opensuse": ("openSUSE Tumbleweed", ["opensuse", "suse"]),
            "ubuntu": ("Ubuntu 24.04.1 LTS", ["ubuntu", "debian"]),
        }
        name, id_like = mock_names.get(mock_id, (f"{mock_id.capitalize()} Linux", [mock_id]))

        return DistroInfo(
            distro_id=mock_id,
            name=name,
            id_like=id_like,
            version_id="rolling" if "arch" in mock_id or "tumbleweed" in mock_id else "12",
            is_mock=True
        )

    def detect_filesystem(self) -> FilesystemInfo:
        """
        Analyzes mount layout and filesystem of /boot via findmnt or /proc/mounts.
        """
        boot_path = self._apply_prefix("/boot")
        target = "/boot"
        fstype = "ext4"
        options: List[str] = ["rw", "relatime"]
        is_separate_boot = False
        is_btrfs = False
        subvolume: Optional[str] = None
        is_ro = False
        efi_mounted = False
        efi_path = None

        # Check findmnt
        if shutil.which("findmnt"):
            try:
                # Query target and fstype and options for /boot
                cmd = ["findmnt", "-n", "-o", "TARGET,FSTYPE,OPTIONS", "-T", str(boot_path)]
                res = subprocess.run(cmd, capture_output=True, text=True, check=False)
                if res.returncode == 0 and res.stdout.strip():
                    parts = res.stdout.strip().split(None, 2)
                    if len(parts) >= 2:
                        target = parts[0]
                        fstype = parts[1].lower()
                        if len(parts) >= 3:
                            options = [opt.strip() for opt in parts[2].split(",")]

                # Check EFI mount
                efi_cmd = ["findmnt", "-n", "-o", "TARGET", str(self._apply_prefix("/boot/efi"))]
                efi_res = subprocess.run(efi_cmd, capture_output=True, text=True, check=False)
                if efi_res.returncode == 0 and efi_res.stdout.strip():
                    efi_mounted = True
                    efi_path = efi_res.stdout.strip()
            except Exception:
                pass
        else:
            # Fallback to inspecting /proc/mounts if on Linux
            proc_mounts = Path("/proc/mounts")
            if proc_mounts.is_file():
                try:
                    with open(proc_mounts, "r", encoding="utf-8") as f:
                        for line in f:
                            fields = line.split()
                            if len(fields) >= 4:
                                m_point, m_fs, m_opts = fields[1], fields[2], fields[3].split(",")
                                if m_point == "/boot":
                                    target = "/boot"
                                    fstype = m_fs.lower()
                                    options = m_opts
                                elif m_point == "/boot/efi":
                                    efi_mounted = True
                                    efi_path = "/boot/efi"
                except Exception:
                    pass

        is_separate_boot = (target == "/boot")
        is_btrfs = ("btrfs" in fstype)
        is_ro = ("ro" in options)

        # Detect Btrfs subvolume if applicable
        if is_btrfs:
            for opt in options:
                if opt.startswith("subvol="):
                    subvolume = opt.split("=", 1)[1]
                    break

        # If /boot is a separate partition, GRUB relative prefix within grub.cfg is "/"
        relative_grub_prefix = "" if is_separate_boot else "/boot"

        return FilesystemInfo(
            boot_target=target,
            fstype=fstype,
            is_separate_boot=is_separate_boot,
            is_btrfs=is_btrfs,
            subvolume=subvolume,
            is_read_only=is_ro,
            options=options,
            efi_mounted=efi_mounted,
            efi_path=efi_path,
            relative_grub_prefix=relative_grub_prefix
        )

    def resolve_paths(self, distro: DistroInfo) -> GrubPaths:
        """
        Resolves the configuration file, theme directory, and grub.cfg path
        according to distribution convention and existing system files.
        """
        # 1. Config file (/etc/default/grub vs alternatives)
        default_cfg = self._apply_prefix("/etc/default/grub")
        sysconfig_bootloader = self._apply_prefix("/etc/sysconfig/bootloader")
        resolved_default = default_cfg
        if not default_cfg.exists() and sysconfig_bootloader.exists():
            resolved_default = sysconfig_bootloader

        # 2. Theme Directory Hierarchy
        # Debian/Arch: /boot/grub/themes/
        # Fedora/RHEL/openSUSE: /boot/grub2/themes/
        # Fallback: /usr/share/grub/themes/
        grub_dir = self._apply_prefix("/boot/grub")
        grub2_dir = self._apply_prefix("/boot/grub2")

        if distro.is_fedora_like or distro.is_suse_like or grub2_dir.is_dir():
            active_grub_dir = grub2_dir
            theme_dir = grub2_dir / "themes"
        else:
            active_grub_dir = grub_dir
            theme_dir = grub_dir / "themes"

        fallback_theme_dir = self._apply_prefix("/usr/share/grub/themes")

        # 3. Target grub.cfg Path Discovery
        grub_cfg = active_grub_dir / "grub.cfg"
        alt_grub_cfg = (grub_dir if active_grub_dir == grub2_dir else grub2_dir) / "grub.cfg"

        # Check existing existence
        if not grub_cfg.exists() and alt_grub_cfg.exists():
            active_grub_cfg = alt_grub_cfg
        else:
            active_grub_cfg = grub_cfg

        # 4. Handle EFI stubs (Fedora/openSUSE legacy UEFI paths)
        efi_stub_cfg: Optional[Path] = None
        efi_base = self._apply_prefix("/boot/efi/EFI")
        if efi_base.is_dir():
            distro_candidates = [distro.distro_id] + distro.id_like + ["fedora", "opensuse", "centos", "redhat", "debian", "arch", "BOOT"]
            for cand in distro_candidates:
                cand_cfg = efi_base / cand / "grub.cfg"
                if cand_cfg.is_file():
                    # Inspect if it is a stub or full config
                    try:
                        content = cand_cfg.read_text(encoding="utf-8", errors="replace")
                        if "configfile" in content or "search --file" in content:
                            efi_stub_cfg = cand_cfg
                        elif not active_grub_cfg.exists():
                            active_grub_cfg = cand_cfg
                    except Exception:
                        pass
                    break

        backup_dir = active_grub_dir / "grub_forge_backups"
        emergency_script = self._apply_prefix("/boot/grub_emergency_restore.sh")

        return GrubPaths(
            default_config=resolved_default,
            grub_dir=active_grub_dir,
            active_grub_cfg=active_grub_cfg,
            theme_dir=theme_dir,
            fallback_theme_dir=fallback_theme_dir,
            backup_dir=backup_dir,
            emergency_script=emergency_script,
            efi_stub_cfg=efi_stub_cfg
        )

    def resolve_tools(self, paths: GrubPaths) -> GrubTools:
        """
        Dynamically detects grub update commands and script validation tools.
        Precedence:
          1. update-grub
          2. grub2-mkconfig -o <active_grub_cfg>
          3. grub-mkconfig -o <active_grub_cfg>
        """
        cfg_path_str = str(paths.active_grub_cfg)

        update_cmd: List[str] = []
        tool_name = ""

        if shutil.which("update-grub"):
            update_cmd = ["update-grub"]
            tool_name = "update-grub"
        elif shutil.which("grub2-mkconfig"):
            update_cmd = ["grub2-mkconfig", "-o", cfg_path_str]
            tool_name = "grub2-mkconfig"
        elif shutil.which("grub-mkconfig"):
            update_cmd = ["grub-mkconfig", "-o", cfg_path_str]
            tool_name = "grub-mkconfig"
        else:
            # Fallback mock command for systems without GRUB tools installed
            tool_name = "grub-mkconfig (simulated)"
            update_cmd = ["grub-mkconfig", "-o", cfg_path_str]

        # Validation tool detection
        script_check = None
        if shutil.which("grub2-script-check"):
            script_check = "grub2-script-check"
        elif shutil.which("grub-script-check"):
            script_check = "grub-script-check"

        return GrubTools(
            update_command=update_cmd,
            update_tool_name=tool_name,
            script_check_tool=script_check,
            has_script_check=(script_check is not None)
        )

    def inspect(self) -> SystemTelemetry:
        """Performs a comprehensive telemetry pass on the system."""
        distro = self.detect_distro()
        fs = self.detect_filesystem()
        paths = self.resolve_paths(distro)
        tools = self.resolve_tools(paths)

        # Query kernel version
        kernel = "Linux (Mock/Simulated)"
        try:
            kernel = subprocess.check_output(["uname", "-r"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass

        # Query GRUB version
        grub_ver = "GRUB 2.12"
        for candidate in ("grub-install", "grub2-install", "grub-mkconfig", "grub2-mkconfig"):
            if shutil.which(candidate):
                try:
                    out = subprocess.check_output([candidate, "--version"], text=True, stderr=subprocess.DEVNULL)
                    m = re.search(r"GRUB\)?\s+([0-9\.]+)", out, re.IGNORECASE)
                    if m:
                        grub_ver = f"GRUB {m.group(1)}"
                        break
                except Exception:
                    pass

        return SystemTelemetry(
            distro=distro,
            fs=fs,
            paths=paths,
            tools=tools,
            kernel_version=kernel,
            grub_version=grub_ver
        )

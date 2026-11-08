# GRUB Forge

> Fail-safe, non-destructive GRUB bootloader customizer, live WYSIWYG simulator, and theme workstation for modern Linux distributions.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org)
[![GUI](https://img.shields.io/badge/GUI-PyQt6-green?logo=qt&logoColor=white)](https://riverbankcomputing.com/software/pyqt/)
[![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20Windows%20(Studio)-orange?logo=linux&logoColor=white)](https://kernel.org)
[![Security](https://img.shields.io/badge/Privilege-Polkit%20pkexec-red)](https://gitlab.freedesktop.org/polkit/polkit)

---

## Overview

Bootloader misconfiguration is one of the leading causes of unbootable Linux systems. **GRUB Forge** eliminates this hazard with digital forensics discipline: transactional immutable backups, dry-run syntax verification via `grub-script-check`, self-contained rescue scripts, unprivileged user-space staging with Polkit privilege separation, and an emulated QEMU virtual boot environment for zero-risk pre-testing.

---

## Key Features

- **Multi-Distro & Filesystem Discovery:** Dynamically fingerprints Kali Linux, Debian, Arch, Fedora, openSUSE, RHEL, and Ubuntu. Automatically maps dedicated `/boot` partitions, XFS, and Btrfs subvolumes (`@`, `@boot`) with runtime tool resolution (`update-grub`, `grub2-mkconfig`, `grub-mkconfig`).
- **Authentic Distro Themes & 1080p Artwork:** Includes official themes and authentic 1080p wallpapers for **Kali Linux (Dragon Cyberpunk)**, Arch Linux, Debian Cosmos, Fedora Horizon, Ubuntu Yaru, and Catppuccin Cyber Glow.
- **Distro Icon Menu Simulation:** Automatically detects operating systems in your bootloader menu entries and renders real brand icons (`kali.png`, `arch.png`, `debian.png`, `fedora.png`, `ubuntu.png`, `windows.png`, `gear.png`, `linux.png`) inside the live WYSIWYG canvas.
- **Segmented Studio Workspace:** Tabbed inspector architecture (`🎨 Presets`, `🖼 Artwork`, `📐 Layout`, `🔤 Styling`, `⚙️ Boot & Safety`) with 1-click layout presets, wallpaper shortcuts, font converter, and theme archive packaging (.tar.gz / .zip).
- **Zero-Brick Transactional Safety:** Creates immutable snapshot archives in `/boot/grub/grub_forge_backups/` and generates `/boot/grub_emergency_restore.sh`—a self-contained, standalone shell script runnable from any live rescue media without Python or Qt.
- **Unprivileged Polkit Separation:** The GUI runs entirely as an unprivileged user process. Atomic root operations are isolated to `/usr/libexec/grub-forge-worker` with SHA256 integrity checks, mount/space headroom enforcement (>= 25 MB), and line-by-line IPC status streaming.
- **QEMU Virtual Boot Harness:** Test staged themes and boot configurations inside an emulated VM with hardware KVM acceleration and TCG fallback before writing to physical NVMe/SATA drives.
- **Dual-Boot & `os-prober` Protection:** AST-style configuration writer safely injects and preserves `GRUB_DISABLE_OS_PROBER=false` with host binary verification, preventing secondary Linux and Windows installations from disappearing from the boot menu.

---

## Step-by-Step Running Guide

### 🐧 Option 1: Run on Linux (Quickstart)

```bash
# 1. Clone the repository
git clone https://github.com/cid-moosa/grub-forge.git
cd grub-forge

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install required dependencies
pip install -r requirements.txt

# 4. Launch the application
python3 app.py
```

---

### 🪟 Option 2: Run on Windows (Preview & Design Studio Mode)

```powershell
# 1. Clone the repository
git clone https://github.com/cid-moosa/grub-forge.git
cd grub-forge

# 2. Create and activate a virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch GRUB Forge Studio
python app.py
```

---

### 🚀 Option 3: Full Linux Desktop Installation (Recommended for Daily Use)

Installs the executable CLI wrapper to `/usr/local/bin/grub-forge`, deploys Polkit security policies to `/usr/share/polkit-1/actions/`, registers the root worker at `/usr/libexec/grub-forge-worker`, and creates desktop application menu shortcuts:

```bash
cd grub-forge
chmod +x install.sh
sudo ./install.sh

# Run from terminal or application launcher
grub-forge
```

---

## Usage Examples

### 1. Launch with Mock Distro Theme Simulation
Design and test bootloader themes for other Linux distributions on any machine:
```bash
# Test Kali Linux Cyber-Dragon Theme
python app.py --mock kali

# Test Arch Linux Minimal Theme
python app.py --mock arch

# Test Fedora Sapphire Horizon Theme
python app.py --mock fedora

# Test Debian Crimson Cosmic Theme
python app.py --mock debian

# Test Ubuntu Yaru Theme
python app.py --mock ubuntu
```

### 2. Headless CLI System Discovery & Diagnostics
Audit distribution fingerprinting, partition topology, EFI mounts, and tooling without launching the GUI:
```bash
python app.py --check
```

### 3. Emergency Restore from Live Media
If an external tool corrupts your bootloader:
```bash
# Mount your root filesystem from any Live USB
sudo mount /dev/sdXn /mnt

# If separate /boot partition exists:
sudo mount /dev/sdXm /mnt/boot

# Run the self-contained rescue script generated by GRUB Forge
sudo sh /mnt/boot/grub_emergency_restore.sh
```

---

## Tech Stack

- **Core & GUI:** Python 3, PyQt6 (`QGraphicsView`, `QGraphicsScene`, `QStackedWidget`, `QPropertyAnimation`, `QThread`)
- **Graphics & Assets:** Pillow (PIL) for 8-bit uncompressed RGBA normalization and authentic 1080p wallpaper rendering
- **Privilege Separation:** Polkit (`pkexec`), FreeDesktop policy specifications (`org.grubforge.policy`)
- **Virtualization:** QEMU (`qemu-system-x86_64`), KVM acceleration, OVMF UEFI firmware
- **Bootloader Tooling:** GRUB2 (`update-grub`, `grub2-mkconfig`, `grub-mkconfig`, `grub-script-check`, `grub-mkfont`, `os-prober`)

---

## Testing

Run the full automated test suite (25 tests covering backend discovery, AST safety, QEMU runner, packager, fonts, and GUI):

```bash
python -m unittest discover -s tests
```

---

## License

This project is licensed under the [MIT License](LICENSE).

---

Developed with precision by [cid-moosa](https://github.com/cid-moosa).

#!/bin/bash
# ==============================================================================
# GRUB Forge - Production Uninstallation Script
# Safely purges deployed launchers, desktop entries, icons, and Polkit policies
# while strictly preserving user bootloader snapshots in /boot/grub_forge_backups/.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${CYAN}================================================================${NC}"
echo -e "${BLUE}          GRUB Forge - System Uninstallation Engine             ${NC}"
echo -e "${CYAN}================================================================${NC}"

# 1. System-wide purge if running as root
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${YELLOW}[*] Purging system-wide installation artifacts...${NC}"

    rm -f "/usr/local/bin/grub-forge"
    rm -f "/usr/libexec/grub-forge-worker"
    rm -f "/usr/share/polkit-1/actions/org.grubforge.policy"
    rm -f "/usr/share/applications/grub-forge.desktop"
    rm -f "/usr/share/icons/hicolor/scalable/apps/grub-forge.svg"

    echo -e "${GREEN}[✓] Removed system binaries, desktop entry, icon, and Polkit policies.${NC}"

    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
    fi
else
    echo -e "${YELLOW}[*] Purging user-space installation artifacts...${NC}"

    rm -f "${HOME}/.local/bin/grub-forge"
    rm -f "${HOME}/.local/share/applications/grub-forge.desktop"
    rm -f "${HOME}/.local/share/icons/hicolor/scalable/apps/grub-forge.svg"

    echo -e "${GREEN}[✓] Removed user binaries, desktop entry, and icon.${NC}"
    echo -e "${YELLOW}[!] Note: If you installed system-wide components with sudo, run 'sudo ./uninstall.sh'.${NC}"
fi

echo -e "${BLUE}[*] Note: User snapshot backups in /boot/ are safely preserved.${NC}"
echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}[✓] GRUB Forge uninstallation complete.${NC}"
echo -e "${GREEN}================================================================${NC}"

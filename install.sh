#!/bin/bash
# ==============================================================================
# GRUB Forge - Production Installation & System Integration Script
# Deploys FreeDesktop entries, scalable icons, Polkit security policies,
# privileged root workers, and the CLI wrapper.
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${CYAN}================================================================${NC}"
echo -e "${BLUE}        GRUB Forge - System Integration & Deployment Engine      ${NC}"
echo -e "${CYAN}================================================================${NC}"

# Resolve repository root
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo -e "${GREEN}[+] Source directory: ${APP_DIR}${NC}"

# 1. Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${RED}[!] Python 3 is required but not installed. Aborting.${NC}"
    exit 1
fi

# 2. Check / Install Python dependencies
echo -e "${BLUE}[*] Verifying Python dependencies (PyQt6, Pillow)...${NC}"
if python3 -c "import PyQt6, PIL" 2>/dev/null; then
    echo -e "${GREEN}[✓] PyQt6 and Pillow are installed.${NC}"
else
    echo -e "${CYAN}[*] Installing dependencies from requirements.txt...${NC}"
    if python3 -m pip --version >/dev/null 2>&1; then
        python3 -m pip install -r "${APP_DIR}/requirements.txt" || {
            echo -e "${YELLOW}[~] Pip install failed. Please install package manager equivalents:${NC}"
            echo -e "    Debian/Ubuntu: sudo apt install python3-pyqt6 python3-pil"
            echo -e "    Arch Linux:    sudo pacman -S python-pyqt6 python-pillow"
            echo -e "    Fedora:        sudo dnf install python3-pyqt6 python3-pillow"
        }
    fi
fi

# Ensure bin/grub-forge is executable
chmod +x "${APP_DIR}/bin/grub-forge"
chmod +x "${APP_DIR}/backend/worker.py"

# 3. System vs User Installation Paths
if [ "$(id -u)" -eq 0 ]; then
    echo -e "${CYAN}[*] Performing System-Wide Root Installation...${NC}"

    BIN_DEST="/usr/local/bin/grub-forge"
    WORKER_DEST="/usr/libexec/grub-forge-worker"
    DESKTOP_DEST="/usr/share/applications/grub-forge.desktop"
    ICON_DEST="/usr/share/icons/hicolor/scalable/apps/grub-forge.svg"
    POLKIT_DEST="/usr/share/polkit-1/actions/org.grubforge.policy"

    # Deploy CLI wrapper
    mkdir -p "/usr/local/bin"
    ln -sf "${APP_DIR}/bin/grub-forge" "$BIN_DEST"
    echo -e "${GREEN}[✓] Installed CLI wrapper: ${BIN_DEST}${NC}"

    # Deploy Root Worker
    mkdir -p "/usr/libexec"
    cat << EOF > "$WORKER_DEST"
#!/bin/sh
exec python3 "${APP_DIR}/backend/worker.py" "\$@"
EOF
    chmod 755 "$WORKER_DEST"
    echo -e "${GREEN}[✓] Installed privileged worker: ${WORKER_DEST}${NC}"

    # Deploy Polkit Policy
    mkdir -p "/usr/share/polkit-1/actions"
    if [ -f "${APP_DIR}/org.grubforge.policy" ]; then
        cp -f "${APP_DIR}/org.grubforge.policy" "$POLKIT_DEST"
        chmod 644 "$POLKIT_DEST"
        echo -e "${GREEN}[✓] Installed Polkit security policy: ${POLKIT_DEST}${NC}"
    fi

    # Deploy FreeDesktop .desktop file
    mkdir -p "/usr/share/applications"
    cp -f "${APP_DIR}/data/grub-forge.desktop" "$DESKTOP_DEST"
    chmod 644 "$DESKTOP_DEST"
    echo -e "${GREEN}[✓] Installed desktop launcher: ${DESKTOP_DEST}${NC}"

    # Deploy Scalable SVG Icon
    mkdir -p "/usr/share/icons/hicolor/scalable/apps"
    cp -f "${APP_DIR}/data/icons/grub-forge.svg" "$ICON_DEST"
    chmod 644 "$ICON_DEST"
    echo -e "${GREEN}[✓] Installed application icon: ${ICON_DEST}${NC}"

    # Update system desktop & icon caches
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database /usr/share/applications || true
    fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true
    fi

else
    echo -e "${CYAN}[*] Non-root detected: Performing User-Space Installation...${NC}"

    USER_BIN="${HOME}/.local/bin"
    USER_DESKTOP="${HOME}/.local/share/applications"
    USER_ICONS="${HOME}/.local/share/icons/hicolor/scalable/apps"

    mkdir -p "$USER_BIN" "$USER_DESKTOP" "$USER_ICONS"

    # User launcher
    ln -sf "${APP_DIR}/bin/grub-forge" "${USER_BIN}/grub-forge"
    echo -e "${GREEN}[✓] Installed user wrapper: ${USER_BIN}/grub-forge${NC}"

    # User desktop entry
    cp -f "${APP_DIR}/data/grub-forge.desktop" "${USER_DESKTOP}/grub-forge.desktop"
    echo -e "${GREEN}[✓] Installed user desktop entry: ${USER_DESKTOP}/grub-forge.desktop${NC}"

    # User icon
    cp -f "${APP_DIR}/data/icons/grub-forge.svg" "${USER_ICONS}/grub-forge.svg"
    echo -e "${GREEN}[✓] Installed user icon: ${USER_ICONS}/grub-forge.svg${NC}"

    echo -e "${YELLOW}[!] Note: Run 'sudo ./install.sh' to install system-wide Polkit policies and root workers.${NC}"
fi

echo -e "${GREEN}================================================================${NC}"
echo -e "${GREEN}[✓] GRUB Forge deployment completed successfully!${NC}"
echo -e "    Launch via desktop menu or run: ${CYAN}grub-forge${NC}"
echo -e "${GREEN}================================================================${NC}"

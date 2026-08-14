#!/usr/bin/env bash
set -euo pipefail

install_root="${BOARD_IDENTIFY_INSTALL_ROOT:-/opt/board-identify}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this uninstaller as root: sudo ./scripts/uninstall.sh" >&2
    exit 1
fi

case "$install_root" in
    /|/usr|/etc|/opt|/var|"")
        echo "Refusing to remove $install_root" >&2
        exit 1
        ;;
esac

rm -f /etc/udev/rules.d/90-board-identify.rules
rm -f /etc/systemd/system/board-identify@.service
rm -f /etc/systemd/system/board-identify-cleanup.service
rm -rf "$install_root"
rm -rf /run/board-identify

systemctl daemon-reload
udevadm control --reload-rules

echo "Uninstalled board-identify"

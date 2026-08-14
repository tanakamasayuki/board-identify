#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install_root="${BOARD_IDENTIFY_INSTALL_ROOT:-/opt/board-identify}"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this installer as root: sudo ./scripts/install.sh" >&2
    exit 1
fi

if [[ "$root" == "$install_root" ]]; then
    echo "Run the installer from a source checkout, not from $install_root." >&2
    exit 1
fi

uv_bin="${UV_BIN:-$(command -v uv || true)}"
if [[ -z "$uv_bin" ]]; then
    echo "uv was not found. Install uv or set UV_BIN=/path/to/uv." >&2
    exit 1
fi

install -d -m 0755 "$install_root"

# Copy only what the installed environment needs; the checkout may also hold a
# .git directory, a development .venv, and tool caches.
for entry in pyproject.toml uv.lock README.md LICENSE src udev systemd scripts; do
    if [[ -e "$root/$entry" ]]; then
        cp -a "$root/$entry" "$install_root/"
    fi
done

cd "$install_root"
"$uv_bin" sync --no-dev --frozen

install -m 0644 "$install_root/udev/90-board-identify.rules" /etc/udev/rules.d/
install -m 0644 "$install_root/systemd/board-identify@.service" /etc/systemd/system/
install -m 0644 "$install_root/systemd/board-identify-cleanup.service" /etc/systemd/system/

systemctl daemon-reload
udevadm control --reload-rules

echo "Installed board-identify under $install_root"
echo "Reconnect a serial device or run:"
echo "  udevadm trigger --subsystem-match=tty"

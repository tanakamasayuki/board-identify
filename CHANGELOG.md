# Changelog

*[English](CHANGELOG.md) | [日本語](CHANGELOG.ja.md)*

## Unreleased

- Add initial Espressif identification scaffold.
- Add udev and systemd integration examples.
- Add a `remove` subcommand and a global `--runtime-dir` option.
- Follow the esptool 4/5 subcommand rename and force plain, unwrapped tool output.
- Prefer the `MAC:` line over `BASE MAC:` when reading the target MAC.
- Drop the previously published link when a port is republished under a new board ID.
- Remove the matching link together with the state of a disconnected port.
- Publish English and Japanese documentation side by side.
- Document the standard alternatives (`/dev/serial/by-id`, `by-path`, udev rules) and
  when to prefer them.
- Document the WSL + USB/IP target environment, where the Windows bus ID is invisible to
  Linux and `by-path` follows the attach order.
- State that probing resets the board and that this is a development-environment tool.

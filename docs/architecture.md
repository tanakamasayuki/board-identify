# Architecture

`board-identify` separates three identities:

- **Port**: the transient kernel node, such as `/dev/ttyUSB2`.
- **Transport**: the USB interface or USB-UART bridge, such as CH340 or FTDI.
- **Target**: the microcontroller board behind the transport.

A target probe produces a stable board identifier. The publisher then creates an atomic symlink in `/run/board-identify/by-id/` and stores state keyed by the transient port name.

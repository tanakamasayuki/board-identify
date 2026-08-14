"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from board_identify import __version__
from board_identify.cleanup import cleanup
from board_identify.identify import identify_port, publish, remove_port
from board_identify.paths import RUNTIME_DIR

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UNIDENTIFIED = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="board-identify",
        description="Identify a microcontroller board on a serial port.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=RUNTIME_DIR,
        help=f"directory holding by-id links and state (default: {RUNTIME_DIR})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    identify_parser = subparsers.add_parser("identify", help="identify a port and publish a link")
    identify_parser.add_argument("port", type=Path)
    identify_parser.add_argument("--json", action="store_true", dest="as_json")
    identify_parser.add_argument("--no-publish", action="store_true")

    remove_parser = subparsers.add_parser("remove", help="drop the link and state of one port")
    remove_parser.add_argument("port_name", help="kernel port name, for example ttyUSB0")

    subparsers.add_parser("cleanup", help="remove stale links and state")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    runtime_dir: Path = args.runtime_dir

    if args.command == "identify":
        return _identify(args, runtime_dir)

    if args.command == "remove":
        removed = remove_port(args.port_name, runtime_dir=runtime_dir)
        if not removed:
            print(f"no state for port: {args.port_name}", file=sys.stderr)
            return EXIT_ERROR
        print(f"removed {args.port_name}")
        return EXIT_OK

    if args.command == "cleanup":
        for path in cleanup(runtime_dir=runtime_dir):
            print(f"removed {path}")
        return EXIT_OK

    return EXIT_ERROR


def _identify(args: argparse.Namespace, runtime_dir: Path) -> int:
    try:
        result = identify_port(args.port)
    except FileNotFoundError:
        print(f"device does not exist: {args.port}", file=sys.stderr)
        return EXIT_ERROR

    if result is None:
        print(f"unable to identify: {args.port}", file=sys.stderr)
        return EXIT_UNIDENTIFIED

    link = None if args.no_publish else publish(result, runtime_dir=runtime_dir)
    if args.as_json:
        output: dict[str, object] = dict(result.to_dict())
        output["link"] = str(link) if link else None
        print(json.dumps(output, indent=2, sort_keys=True))
    elif link:
        print(f"{link} -> {result.port}")
    else:
        print(result.board_id)
    return EXIT_OK

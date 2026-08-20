"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from board_identify import __version__
from board_identify.cleanup import cleanup
from board_identify.identify import default_probes, identify_port, publish, remove_port
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
    identify_parser.add_argument(
        "--no-target-probe",
        action="store_true",
        help="stay on USB descriptors instead of talking to the board behind a debug probe",
    )

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
    probes = default_probes(probe_target=not args.no_target_probe)
    try:
        results = identify_port(args.port, probes=probes)
    except FileNotFoundError:
        print(f"device does not exist: {args.port}", file=sys.stderr)
        return EXIT_ERROR

    if not results:
        print(f"unable to identify: {args.port}", file=sys.stderr)
        return EXIT_UNIDENTIFIED

    links = [] if args.no_publish else publish(results, runtime_dir=runtime_dir)
    by_board_id = {link.name: link for link in links}

    if args.as_json:
        output: dict[str, object] = {
            "port": str(args.port),
            "identifications": [
                {**result.to_dict(), "link": _link_for(result.board_id, by_board_id)}
                for result in results
            ],
        }
        print(json.dumps(output, indent=2, sort_keys=True))
    elif links:
        for link in links:
            print(f"{link} -> {link.readlink()}")
    else:
        for result in results:
            print(result.board_id)
    return EXIT_OK


def _link_for(board_id: str, links: dict[str, Path]) -> str | None:
    link = links.get(board_id)
    return str(link) if link is not None else None

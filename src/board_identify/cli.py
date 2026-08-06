import argparse
import json
import sys
from pathlib import Path

from board_identify.identify import identify_port, publish, remove_port
from board_identify.cleanup import cleanup

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="board-identify",
        description="Identify a microcontroller board on a serial port.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    identify_parser = subparsers.add_parser("identify")
    identify_parser.add_argument("port", type=Path)
    identify_parser.add_argument("--json", action="store_true", dest="as_json")
    identify_parser.add_argument("--no-publish", action="store_true")

    cleanup_parser = subparsers.add_parser("cleanup")
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.command == "identify":
        try:
            result = identify_port(args.port)
        except FileNotFoundError:
            print(f"device does not exist: {args.port}", file=sys.stderr)
            return 1

        if result is None:
            print(f"unable to identify: {args.port}", file=sys.stderr)
            return 2

        link = None if args.no_publish else publish(result)
        if args.as_json:
            output = result.to_dict()
            output["link"] = str(link) if link else None
            print(json.dumps(output, indent=2, sort_keys=True))
        elif link:
            print(f"{link} -> {result.port}")
        else:
            print(result.board_id)
        return 0

    if args.command == "cleanup":
        removed = cleanup()

        for path in removed:
            print(f"removed {path}")

        return 0

    return 1

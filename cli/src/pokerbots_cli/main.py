import argparse
import sys

from pokerbots_cli import __version__
from pokerbots_cli.api import ApiError
from pokerbots_cli.commands import MODULES


def parser():
    p = argparse.ArgumentParser(prog="pb", description="pokerbots.dev")
    p.add_argument("--version", action="version", version=f"pb {__version__}")
    sub = p.add_subparsers(metavar="command")
    for module in MODULES:
        module.register(sub)
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if not hasattr(args, "run"):
        p.print_help()
        return 0
    try:
        return args.run(args) or 0
    except (ApiError, ValueError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    raise SystemExit(main())

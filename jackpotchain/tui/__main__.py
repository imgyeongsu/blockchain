"""
TUI 엔트리포인트

python -m jackpotchain.tui
"""

import argparse
from .app import run_tui


def main():
    parser = argparse.ArgumentParser(description="JackpotChain TUI")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="RPC server host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9776,
        help="RPC server port (default: 9776)"
    )
    args = parser.parse_args()

    run_tui(host=args.host, port=args.port)


if __name__ == "__main__":
    main()

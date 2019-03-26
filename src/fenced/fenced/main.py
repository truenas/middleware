#!/usr/bin/env python3
import argparse

from fenced.fence import Fence
from fenced.logging import setup_logging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='Do not check existing disk reservations',
    )
    parser.add_argument(
        '--foreground', '-F',
        action='store_true',
        help='Run in foreground mode',
    )
    parser.add_argument(
        '--interval', '-i',
        default=5,
        type=int,
        help='Time in seconds between each SCSI reservation set/check',
    )
    args = parser.parse_args()

    setup_logging(args.foreground)

    fence = Fence(args.interval, args.force)
    fence.run()


if __name__ == '__main__':
    main()

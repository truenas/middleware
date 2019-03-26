#!/usr/bin/env python3
import argparse
import fcntl
import logging
import os
import sys

from fenced.fence import Fence
from fenced.logging import setup_logging

logger = logging.getLogger(__name__)
LOCK_FILE = '/tmp/.fenced-lock'


def is_running():
    """
	Use lock file to prevent duplicate fenced's from starting
	because fenced can and will panic the box when this happens.
	Ticket #48031
    """

    lock_fd = os.open(LOCK_FILE, os.O_RDWR | os.O_CREAT)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    return False


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

    if is_running():
        logger.error('fenced already running.')
        sys.exit(1)

    fence = Fence(args.interval, args.force)
    fence.run()


if __name__ == '__main__':
    main()

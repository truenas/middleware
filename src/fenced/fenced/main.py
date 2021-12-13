import argparse
import logging
import os
import signal
import struct
import subprocess
import sys
import time
import contextlib

from fenced.exceptions import PanicExit, ExcludeDisksError
from fenced.fence import Fence, ExitCode
from fenced.logging import setup_logging
from middlewared.client import Client

logger = logging.getLogger(__name__)
ALERT_FILE = '/data/sentinels/.fenced-alert'
PID_FILE = '/var/run/.fenced-pid'


def is_running():
    """
    Check if there is a currently running fenced process.
    Multiple fenced processes running on the same system will
    clobber one another and, ultimately, cause a panic.
    Ticket #48031
    """
    running = False
    with contextlib.suppress(Exception):
        with Client() as c:
            data = c.call('failover.fenced.run_info')
            if data['running'] and data['pid']:
                if data['pid'] != os.getpid():
                    running = True

    return running


def update_pid_file():
    """
    We call tihs method after we have fork()'ed
    """
    with contextlib.suppress(Exception):
        with open(PID_FILE, 'w+') as f:
            f.write(str(os.getpid()))


def panic(reason):
    """
    An unclean reboot is going to occur.
    Try to create this file and write epoch time to it. After we panic,
    middlewared will check for this file, read the epoch time in the file
    and will send an appropriate email and then remove it.
    Ticket #39114
    """
    try:
        with open(ALERT_FILE, 'wb') as f:
            epoch = int(time.time())
            b = struct.pack('@i', epoch)
            f.write(b)
            f.flush()
            os.fsync(f.fileno())  # Be extra sure
    except EnvironmentError as e:
        logger.debug('Failed to write alert file: %s', e)

    logger.error('FATAL: %s', reason)
    logger.error('FATAL: issuing an immediate panic.')
    subprocess.run(['watchdog', '-t', '1'], check=False)
    subprocess.run(['sysctl', 'debug.kdb.panic=1'], check=False)
    subprocess.run(['shutdown', '-p', 'now'], check=False)


def format_args():
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
        '--no-panic', '-np',
        action='store_true',
        help='Do not panic in case of a fatal error',
    )
    parser.add_argument(
        '--interval', '-i',
        default=5,
        type=int,
        help='Time in seconds between each SCSI reservation set/check',
    )
    parser.add_argument(
        '--exclude-disks', '-ed',
        default=[],
        help='List of disks to be excluded from SCSI reservations.'
             ' (THIS CAN CAUSE PROBLEMS IF YOU DONT KNOW WHAT YOURE DOING)',
    )
    return parser.parse_args()


def main():
    args = format_args()

    setup_logging(args.foreground)

    if is_running():
        logger.error('fenced already running.')
        sys.exit(ExitCode.ALREADY_RUNNING.value)

    fence = Fence(args.interval, args.exclude_disks)
    newkey = fence.init(args.force)

    if not args.foreground:
        logger.info('Entering in daemon mode.')
        if os.fork() != 0:
            sys.exit(0)
        os.setsid()
        if os.fork() != 0:
            sys.exit(0)
        os.closerange(0, 3)
    else:
        logger.info('Running in foreground mode.')

    update_pid_file()

    signal.signal(signal.SIGHUP, fence.sighup_handler)

    try:
        fence.loop(newkey)
    except PanicExit as e:
        if args.no_panic:
            logger.info('Fatal error: %s', e)
            sys.exit(ExitCode.UNKNOWN.value)
        else:
            logger.info('Panic %s', e)
            panic(e)
    except ExcludeDisksError as e:
        logger.info(f'{e}')
        sys.exit(ExitCode.EXCLUDE_DISKS_ERROR.value)
    except Exception:
        logger.error('Unexpected exception', exc_info=True)
        sys.exit(ExitCode.UNKNOWN.value)


if __name__ == '__main__':
    main()

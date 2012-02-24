#!/usr/bin/env python
"""
A test daemon that prints out a message every 5 seconds and exits via a handler for SIGTERM.

All messages are printed to syslog by design.

Please read PEP-3143 and visit http://pypi.python.org/pypi/python-daemon if you're more
interested in reading up on what one can do with the daemon module.

Requires:

- devel/py-daemon, devel/py-lockfile
- Running `mkdir -p /tmp/test-daemon/wd' ;)..

Garrett Cooper, December 2011
"""

import atexit
import os
import signal
import sys
import syslog
import time

import daemon
import lockfile

def initial_setup():
    """Initial setup for the daemon."""

    # NOTE: Beware the documentation in the atexit module about function
    #       callback ordering.
    atexit.register(exit_handler)
    progname = os.path.basename(os.path.splitext(sys.argv[0])[0])
    syslog.openlog(progname, syslog.LOG_PID)

def exit_handler():
    """An exit handler for the daemon."""

    syslog.syslog(syslog.LOG_WARNING, 'Closing log')
    syslog.closelog()

def sighandler(sig, stack):
    """A signal handler for the daemon."""

    syslog.syslog(syslog.LOG_WARNING, 'Exiting on signal = %d..' % (sig, ))
    sys.exit(128 + signal.SIGTERM)

def main_loop():
    """A loop that never exits."""

    while True:
        syslog.syslog(syslog.LOG_WARNING, 'In main')
        time.sleep(5)

def main(argv):
    """Our friendly neighborhood main function."""

    context = daemon.DaemonContext(
        working_directory='/tmp/test-daemon/wd',
        umask=0o002,
        pidfile=lockfile.FileLock('/tmp/test-daemon/test-daemon.pid'),
    )

    context.signal_map = {
        signal.SIGTERM: sighandler,
        signal.SIGHUP:  'terminate',
        }

    initial_setup()

    with context:
        main_loop()

if __name__ == '__main__':
    main(sys.argv[1:])

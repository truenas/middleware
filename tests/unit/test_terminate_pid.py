from os import kill
from subprocess import Popen
from textwrap import dedent
from time import sleep

from middlewared.utils.os import terminate_pid


def test_sigterm():
    p = Popen(['python', '-c', 'import time; time.sleep(60)'])
    # Allow process to start
    sleep(0.2)

    # Call terminate_pid with timeout
    terminate_pid(p.pid, timeout=5)
    # Wait a bit to ensure process has time to terminate
    sleep(0.5)

    # Check if process has terminated
    try:
        kill(p.pid, 0)
        assert False, f"{p.pid!r} still running"
    except ProcessLookupError:
        # Process has terminated
        pass


def test_sigkill():
    script = dedent("""
        import signal
        import os
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        max_sleep = 60
        slept_time = 0
        while slept_time < max_sleep:
            time.sleep(1)
            slept_time += 1
    """)
    p = Popen(['python', '-c', script])

    # Call terminate_pid with short timeout
    terminate_pid(p.pid, timeout=1)
    # Wait a bit to ensure process has time to terminate
    sleep(0.5)

    # Check if process has terminated
    try:
        kill(p.pid, 0)
        assert False, f"{p.pid!r} still running"
    except ProcessLookupError:
        # Process has terminated
        pass

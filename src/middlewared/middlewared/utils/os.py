from collections.abc import Generator
from dataclasses import dataclass
from functools import cached_property
from os import closerange, getpgid, kill, killpg, scandir
from resource import getrlimit, RLIMIT_NOFILE, RLIM_INFINITY
from signal import SIGKILL, SIGTERM
from time import sleep, time

__all__ = ['close_fds', 'get_pids', 'terminate_pid']

ALIVE_SIGNAL = 0


@dataclass(frozen=True, kw_only=True)
class PidEntry:
    cmdline: bytes
    pid: int

    @cached_property
    def name(self) -> bytes:
        """The name of process as described in man 2 PR_SET_NAME"""
        with open(f'/proc/{self.pid}/status', 'rb') as f:
            # first line in this file is name of process
            # and this is in procfs, which is considered
            # part of linux's ABI and is stable
            return f.readline().split(b'\t', 1)[-1].strip()

    def send_signal(self, sig: int) -> None:
        kill(self.pid, sig)

    def terminate(self, timeout: int = 10) -> bool:
        return terminate_pid(self.pid, timeout=timeout)


def close_fds(low_fd: int, max_fd: int | None = None) -> None:
    if max_fd is None:
        max_fd = getrlimit(RLIMIT_NOFILE)[1]
        if max_fd == RLIM_INFINITY:
            # Avoid infinity as thats not practical
            max_fd = 8192

    closerange(low_fd, max_fd)


def terminate_pid(pid: int, timeout: int = 10, use_pgid: bool = False) -> bool:
    """
    Send SIGTERM to `pid` and wait `timeout` seconds for the process to terminate.
    If the process is still alive after `timeout`, proceed to send SIGKILL to the
    process.

    `pid`: integer represents the PID to terminate.
    `timeout`: integer represents the total time (in seconds) to wait
        before sending SIGKILL to `pid` if the process doesn't honor
        SIGTERM or takes longer than `timeout` seconds to terminate.
    `use_pgid`: boolean, if true will lookup the process group id of
        `pid` and apply the same logic.
    """
    pid_or_pgid, method = pid, kill
    if use_pgid:
        method = killpg
        pid_or_pgid = getpgid(pid)

    # Send SIGTERM to request the process (group) to terminate
    method(pid_or_pgid, SIGTERM)

    try:
        method(pid_or_pgid, ALIVE_SIGNAL)
    except ProcessLookupError:
        # SIGTERM was honored
        return True

    # process still alive (could take awhile)
    start_time = time()
    while True:
        try:
            method(pid_or_pgid, ALIVE_SIGNAL)
        except ProcessLookupError:
            # SIGTERM was honored (eventually)
            return True

        if time() - start_time >= timeout:
            # Timeout reached; break out of the loop to send SIGKILL
            break

        # Wait a bit before checking again
        sleep(0.1)

    try:
        # Send SIGKILL to forcefully terminate the process
        method(pid_or_pgid, SIGKILL)
        return False
    except ProcessLookupError:
        # Process may have terminated between checks
        return True


def get_pids() -> Generator[PidEntry, None, None]:
    """Get the currently running processes on the OS"""
    with scandir("/proc/") as sdir:
        for i in filter(lambda x: x.name.isdigit(), sdir):
            try:
                with open(f'{i.path}/cmdline', 'rb') as f:
                    cmdline = f.read().replace(b'\x00', b' ')
                yield PidEntry(cmdline=cmdline, pid=int(i.name))
            except FileNotFoundError:
                # process could have gone away
                pass

from collections.abc import Generator
from dataclasses import dataclass
from os import closerange, kill, scandir
from resource import getrlimit, RLIMIT_NOFILE, RLIM_INFINITY
from signal import SIGKILL, SIGTERM
from time import sleep, time

__all__ = ['close_fds', 'get_pids', 'PidEntry', 'terminate_pid']

ALIVE_SIGNAL = 0


@dataclass(slots=True, frozen=True, kw_only=True)
class PidEntry:
    cmdline: bytes
    pid: int


def close_fds(low_fd, max_fd=None):
    if max_fd is None:
        max_fd = getrlimit(RLIMIT_NOFILE)[1]
        if max_fd == RLIM_INFINITY:
            # Avoid infinity as thats not practical
            max_fd = 8192

    closerange(low_fd, max_fd)


def terminate_pid(pid: int, timeout: int = 10) -> bool:
    # Send SIGTERM to request the process to terminate
    kill(pid, SIGTERM)

    try:
        kill(pid, ALIVE_SIGNAL)
    except ProcessLookupError:
        # SIGTERM was honored
        return True

    # process still alive (could take awhile)
    start_time = time()
    while True:
        try:
            kill(pid, ALIVE_SIGNAL)
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
        kill(pid, SIGKILL)
        return False
    except ProcessLookupError:
        # Process may have terminated between checks
        return True


def get_pids(pid: int | None = None) -> Generator[PidEntry] | PidEntry | None:
    spid = str(pid) if pid is not None else None
    with scandir("/proc/") as sdir:
        for i in filter(lambda x: x.name.isdigit(), sdir):
            try:
                with open(f'{i.path}/cmdline', 'rb') as f:
                    cmdline = f.read().replace(b'\x00', b' ')
            except FileNotFoundError:
                # process could have gone away
                pass
            else:
                if spid == i.name:
                    return PidEntry(cmdline=cmdline, pid=pid)
                else:
                    yield PidEntry(cmdline=cmdline, pid=int(i.name))

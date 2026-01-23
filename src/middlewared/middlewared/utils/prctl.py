import ctypes
import signal
import threading

__all__ = ['set_name', 'set_cmdline', 'set_pdeath_sig']

# from linux/prctl.h
PR_SET_PDEATHSIG = 1


def set_name(name: str) -> None:
    """
    Set the calling thread's comm name shown in `ps -e`, `top`, and `htop`.

    This writes to /proc/self/task/<tid>/comm for the calling thread.
    The kernel enforces a 15-character limit (TASK_COMM_LEN - 1); longer
    names are silently truncated.

    For the main thread (where tid == pid), this also sets the process name.

    Args:
        name: The comm name to set (max 15 characters effective).
    """
    tid = threading.get_native_id()
    with open(f"/proc/self/task/{tid}/comm", "w") as f:
        f.write(name[:15])


def set_cmdline(cmdline: str) -> None:
    """
    Set the full command line shown in `ps aux` and `ps -f`.

    This overwrites the original argv buffer in process memory. The buffer
    size is determined by the original command line length at process start.
    We read arg_start and arg_end from /proc/self/stat to determine the safe
    writable region and prevent buffer overflow.

    Args:
        cmdline: The command line string to set. Will be truncated if it
                 exceeds the original buffer size.
    """
    with open("/proc/self/stat", "r") as f:
        stat = f.read()

    # Parse stat to get arg_start and arg_end memory addresses
    # Format: pid (comm) state ppid ... [field 48]=arg_start [field 49]=arg_end
    # We find the closing paren of comm (which may contain spaces) then split
    comm_end = stat.rfind(")")
    fields = stat[comm_end + 2:].split()
    arg_start = int(fields[45])
    arg_end = int(fields[46])
    available = arg_end - arg_start

    encoded = cmdline.encode("utf-8")
    if len(encoded) >= available:
        encoded = encoded[:available - 1]

    ctypes.memmove(arg_start, encoded, len(encoded))
    ctypes.memset(arg_start + len(encoded), 0, available - len(encoded))


def set_pdeath_sig(sig: signal.Signals = signal.SIGKILL) -> None:
    libc = ctypes.CDLL("libc.so.6")
    libc.prctl(PR_SET_PDEATHSIG, signal.Signals(sig).value, 0, 0, 0)


def die_with_parent() -> None:
    set_pdeath_sig()

import logging
import subprocess
from typing import Any, Callable

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context"]


def run_command_with_user_context(
    commandline: str, user: str, *, output: bool = True, callback: Callable[[bytes], Any] | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[bytes]:
    if output or callback:
        stdout = subprocess.PIPE
        stderr = subprocess.STDOUT
    else:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL
    timeout_args = ["timeout", "-k", str(timeout), str(timeout)] if timeout else []
    p = subprocess.Popen(timeout_args + ["sudo", "-H", "-u", user, "sh", "-c", commandline], stdout=stdout,
                         stderr=stderr)

    result = b""
    if output or callback:
        assert p.stdout is not None

        while True:
            line = p.stdout.readline()
            if not line:
                break

            if output:
                result += line
            if callback:
                callback(line)

    p.communicate()
    return subprocess.CompletedProcess(commandline, stdout=result, returncode=p.returncode)

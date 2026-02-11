import concurrent.futures
import functools
import logging
import os
import subprocess
from typing import Any, Callable

import middlewared.api

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context", "run_with_user_context", "set_user_context"]


def set_user_context(user_details: dict[str, Any]) -> None:
    if os.geteuid() != 0:
        # We need to reset to UID 0 before setgroups is called
        os.seteuid(0)

    os.setgroups(user_details['grouplist'])

    # We must preserve the saved uid of zero so that we can call this multiple times
    # in same child process.
    gids = (user_details['pw_gid'], user_details['pw_gid'], 0)
    uids = (user_details['pw_uid'], user_details['pw_uid'], 0)

    os.setresgid(*gids)
    os.setresuid(*uids)

    new_gids = os.getresgid()
    new_uids = os.getresuid()

    if new_gids != gids:
        raise Exception(f'{user_details["pw_name"]}: Unable to set gids for user context received {new_gids}, expected {gids}')

    if new_uids != uids:
        raise Exception(f'{user_details["pw_name"]}: Unable to set uids for user context received {new_uids}, expected {uids}')

    try:
        os.chdir(user_details['pw_dir'])
    except Exception:
        os.chdir('/var/empty')

    os.environ.update({
        'HOME': user_details['pw_dir'],
        'PATH': '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin',
    })


def run_with_user_context_initializer(user_details: dict[str, Any]) -> None:
    middlewared.api.API_LOADING_FORBIDDEN = True
    set_user_context(user_details)


def run_with_user_context[T](
    func: Callable[..., T], user_details: dict[str, Any], func_args: list[Any] | None = None
) -> T:
    assert {'pw_uid', 'pw_gid', 'pw_dir', 'pw_name', 'grouplist'} - set(user_details) == set()

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1, initializer=functools.partial(run_with_user_context_initializer, user_details)
    ) as exc:
        return exc.submit(func, *(func_args or [])).result()


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

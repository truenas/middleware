# -*- coding=utf-8 -*-
import concurrent.futures
import functools
import logging
import os
import subprocess

from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context", "run_with_user_context", "set_user_context"]


def set_user_context(user_details: dict) -> None:
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


def run_with_user_context(func: Callable, user_details: dict, func_args: Optional[list] = None) -> Any:
    assert {'pw_uid', 'pw_gid', 'pw_dir', 'pw_name', 'grouplist'} - set(user_details) == set()

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=1, initializer=functools.partial(set_user_context, user_details)
    ) as exc:
        return exc.submit(func, *(func_args or [])).result()


def run_command_with_user_context(
    commandline: str, user: str, *, output: bool = True, callback: Optional[Callable] = None,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    if output or callback:
        kwargs = {"stdout": subprocess.PIPE, "stderr": subprocess.STDOUT}
    else:
        kwargs = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    timeout_args = ["timeout", "-k", str(timeout), str(timeout)] if timeout else []
    p = subprocess.Popen(timeout_args + ["sudo", "-H", "-u", user, "sh", "-c", commandline], **kwargs)

    stdout = b""
    if output or callback:
        while True:
            line = p.stdout.readline()
            if not line:
                break

            if output:
                stdout += line
            if callback:
                callback(line)

    p.communicate()
    return subprocess.CompletedProcess(commandline, stdout=stdout, returncode=p.returncode)

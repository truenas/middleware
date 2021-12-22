# -*- coding=utf-8 -*-
import logging
import os
import pwd
import queue
import subprocess

from multiprocessing import Process, Queue, Value
from typing import Callable, Optional

logger = logging.getLogger(__name__)

__all__ = ['run_command_with_user_context', 'run_function_with_user_context']


def set_user_context(user: str) -> None:
    user_details = pwd.getpwnam(user)
    os.setgroups(os.getgrouplist(user, user_details.pw_gid))
    os.setresgid(user_details.pw_gid, user_details.pw_gid, user_details.pw_gid)
    os.setresuid(user_details.pw_uid, user_details.pw_uid, user_details.pw_uid)

    if any(
        c() != v for c, v in (
            (os.getuid, user_details.pw_uid),
            (os.geteuid, user_details.pw_uid),
            (os.getgid, user_details.pw_gid),
            (os.getegid, user_details.pw_gid),
        )
    ):
        raise Exception(f'Unable to set user context to {user!r} user')

    try:
        os.chdir(user_details.pw_dir)
    except Exception:
        os.chdir('/')

    os.environ['HOME'] = user_details.pw_dir
    os.environ.update({
        'HOME': user_details.pw_dir,
        'PATH': '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin',
    })


def _run_command(user: str, commandline: list, q: Queue, rv: Value) -> None:
    set_user_context(user)

    proc = subprocess.Popen(
        commandline, shell=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )

    while True:
        line = proc.stdout.readline()
        if line == b'':
            break

        try:
            q.put(line, False)
        except queue.Full:
            pass
    proc.communicate()
    rv.value = proc.returncode
    q.put(None)


def _run_function(callable: Callable, user: str, shared_queue: Queue, callable_args: Optional[list]) -> None:
    set_user_context(user)
    shared_queue.put(callable(*(callable_args or [])))


def run_function_with_user_context(callable: Callable, user: str, callable_args: Optional[list] = None) -> None:
    shared_queue = Queue()
    p = Process(
        target=_run_function, args=(callable, user, shared_queue, callable_args),
        daemon=True
    )
    p.start()
    p.join()
    return shared_queue.get()


def run_command_with_user_context(
    commandline: list, user: str, callback: Optional[Callable]
) -> subprocess.CompletedProcess:
    q = Queue(maxsize=100)
    rv = Value('i')
    stdout = b''
    p = Process(
        target=_run_command, args=(user, commandline, q, rv),
        daemon=True
    )
    p.start()
    while p.is_alive() or not q.empty():
        try:
            get = q.get(True, 2)
            if get is None:
                break
            stdout += get
            if callback:
                callback(get)
        except queue.Empty:
            pass
        except Exception:
            logger.error('Unhandled exception', exc_info=True)
            p.kill()
            raise

    p.join()

    return subprocess.CompletedProcess(commandline, stdout=stdout, returncode=rv.value)

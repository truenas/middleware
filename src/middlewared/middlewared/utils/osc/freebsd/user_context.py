# -*- coding=utf-8 -*-
import ctypes
import ctypes.util
import logging
from multiprocessing import Process, Queue, Value
import os
import pwd
import queue
import subprocess

logger = logging.getLogger(__name__)

__all__ = ["run_command_with_user_context"]


def setusercontext(user):
    libc = ctypes.cdll.LoadLibrary(ctypes.util.find_library('c'))
    libutil = ctypes.cdll.LoadLibrary(ctypes.util.find_library('util'))
    libc.getpwnam.restype = ctypes.POINTER(ctypes.c_void_p)
    pwnam = libc.getpwnam(user)
    passwd = pwd.getpwnam(user)

    libutil.login_getpwclass.restype = ctypes.POINTER(ctypes.c_void_p)
    lc = libutil.login_getpwclass(pwnam)
    os.setgid(passwd.pw_gid)
    if lc and lc[0]:
        libc.initgroups(user.encode('ascii'), passwd.pw_gid)
        libutil.setusercontext(
            lc, pwnam, passwd.pw_uid, ctypes.c_uint(0x07ff)  # 0x07ff LOGIN_SETALL
        )
        libutil.login_close(lc)
    else:
        os.setgid(passwd.pw_gid)
        libc.setlogin(user)
        libc.initgroups(user.encode('ascii'), passwd.pw_gid)
        os.setuid(passwd.pw_uid)

    try:
        os.chdir(passwd.pw_dir)
    except Exception:
        os.chdir('/')

    os.environ['HOME'] = passwd.pw_dir


def _run_command(user, commandline, q, rv):
    setusercontext(user)

    os.environ['PATH'] = (
        '/bin:/sbin:/usr/bin:/usr/sbin:/usr/local/bin:/usr/local/sbin:/root/bin'
    )
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


def run_command_with_user_context(commandline, user, callback):
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
            callback(get)
        except queue.Empty:
            pass
        except Exception:
            logger.error('Unhandled exception', exc_info=True)
            p.kill()
            raise

    p.join()

    return subprocess.CompletedProcess(
        commandline, stdout=stdout, returncode=rv.value
    )

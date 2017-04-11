# Copyright 2011 iXsystems, Inc.
# All rights reserved
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted providing that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
#####################################################################

from shlex import split as shlex_split
from subprocess import Popen, PIPE
from os import system as __system
import ctypes
import logging
import os
import signal
import threading


logging.NOTICE = 60
logging.addLevelName(logging.NOTICE, "NOTICE")
logging.ALERT = 70
logging.addLevelName(logging.ALERT, "ALERT")
log = logging.getLogger('common.pipesubr')

SIG_BLOCK = 1
SIG_UNBLOCK = 2
SIG_SETMASK = 3


def unblock_sigchld():
    libc = ctypes.cdll.LoadLibrary("libc.so.7")
    mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
    pmask = ctypes.pointer(mask)
    libc.sigprocmask(SIG_BLOCK, 0, pmask)
    libc.sigdelset(pmask, signal.SIGCHLD)
    libc.sigprocmask(SIG_SETMASK, pmask, None)


#
# Allow closing of file descriptors on exec
#
# https://bugs.freenas.org/issues/15817
#
def pipeopen(command, important=True, logger=log, allowfork=False, quiet=True, close_fds=True, env=None, stdout=PIPE, stderr=PIPE, start_new_session=False):
    print(stdout, stderr)
    if not quiet:
        logger.log(
            logging.NOTICE if important else logging.DEBUG,
            "Popen()ing: " + command
        )
    args = shlex_split(str(command))

    preexec_fn = None
    if allowfork:
        preexec_fn = unblock_sigchld

    return Popen(
        args, stdin=PIPE, stdout=stdout, stderr=stderr,
        close_fds=close_fds, preexec_fn=preexec_fn,
        env=env, encoding='utf8', start_new_session=start_new_session,
    )


class Command(object):
    def __init__(self, command):
        self.command = command
        self.process = None
        self.stdout = None
        self.stderr = None

    @property
    def returncode(self):
        ret = -1
        if self.process:
            ret = self.process.returncode
        return ret

    def run(self, important=True, logger=log, allowfork=False, quiet=False, timeout=None):
        def target():
            self.process = pipeopen(self.command, important, logger, allowfork, quiet)
            (self.stdout, self.stderr) = self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self.process.terminate()
            thread.join()

        return (self.returncode, self.stdout, self.stderr)


def run(command, important=True, logger=log, allowfork=False, quiet=False, timeout=-1):
    try:
        timeout = float(timeout)
    except:
        timeout = 0

    if timeout <= 0:
        timeout = None

    c = Command(command)

    return c.run(important, logger, allowfork, quiet, timeout)


def system(command, important=True, logger=log):
    logger.log(
        logging.NOTICE if important else logging.DEBUG,
        "Executing: " + command
    )
    __system("(" + command + ") 2>&1 | logger -p daemon.notice -t %s" % (
        logger.name, ))
    logger.log(
        logging.INFO if important else logging.DEBUG,
        "Executed: " + command
    )

#!/usr/bin/env python
# Copyright (c) 2013 iXsystems, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS ``AS IS'' AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#

import ctypes
import os
import re
import signal
import subprocess
import tempfile
import threading
import time
import middlewared.logger

log = middlewared.logger.Logger('middleware.encryption')

PROGRESS = 0.0


class RandomWorker(threading.Thread):

    def __init__(self, dev):
        self._dev = dev
        self._pid = None
        self._exit = None
        self._tmp = tempfile.mktemp(dir='/tmp')
        self._stderr = open(self._tmp, 'w')

        pipe = subprocess.Popen([
            "/usr/sbin/diskinfo",
            dev,
        ], stdout=subprocess.PIPE)
        output = pipe.communicate()[0]
        self._size = output.split()[2]

        super(RandomWorker, self).__init__()

    def run(self):

        libc = ctypes.cdll.LoadLibrary("libc.so.7")
        omask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        mask = (ctypes.c_uint32 * 4)(0, 0, 0, 0)
        pmask = ctypes.pointer(mask)
        pomask = ctypes.pointer(omask)
        libc.sigprocmask(signal.SIGQUIT, pmask, pomask)

        proc = subprocess.Popen(
            [
                "dd",
                "if=/dev/random",
                "of=%s" % self._dev,
                "bs=1m",
            ],
            stdout=subprocess.PIPE,
            stderr=self._stderr,
        )

        self._pid = proc.pid

        proc.communicate()
        self._exit = proc.returncode

        libc.sigprocmask(signal.SIGQUIT, pomask, None)

    def progress(self):
        with open(self._tmp, 'r') as f:
            read = f.read()

        transf = re.findall(
            r'^(?P<bytes>\d+) bytes transferred.*',
            read,
            re.M)
        if not transf:
            return 0
        received = transf[-1]
        prog = (float(received) / float(self._size) * 100)
        return prog


class RandomSentinel(threading.Thread):

    def __init__(self, worker):
        self._worker = worker
        super(RandomSentinel, self).__init__()

    def run(self):
        while self._worker.is_alive():
            if self._worker._pid is not None:
                os.kill(self._worker._pid, signal.SIGINFO)
            time.sleep(1)


def random_wipe(devs):
    """
    Concurrently wipe devs using /dev/random
    """
    # FIXME: yuck, global, not thread-safe, etc.
    global PROGRESS
    PROGRESS = 0.0

    threads = []
    sentinels = []
    for dev in devs:
        thread = RandomWorker(dev)
        thread.start()
        threads.append(thread)
        sentinel = RandomSentinel(worker=thread)
        sentinel.start()
        sentinels.append(sentinel)

    tobreak = False
    while not tobreak:
        progress = 0
        numthreads = len(threads)
        tobreak = True
        for thread in threads:
            tobreak &= not thread.is_alive()

            progress += thread.progress()
        progress /= numthreads
        PROGRESS = progress
        time.sleep(1)

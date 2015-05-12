#!/usr/local/bin/python2.7
#
# Copyright (c) 2015 iXsystems, Inc.
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

import cPickle as pickle
import os

from lockfile import LockFile, LockTimeout

SMART_FILE = '/tmp/.smartalert'


def main():

    lock = LockFile(SMART_FILE)
    while not lock.i_am_locking():
        try:
            lock.acquire(timeout=5)
        except LockTimeout:
            lock.break_lock()

    data = {}
    if os.path.exists(SMART_FILE):
        with open(SMART_FILE, 'rb') as f:
            try:
                data = pickle.loads(f.read())
            except:
                pass

    device = os.environ.get('SMARTD_DEVICE')
    if device is None:
        lock.release()
        return

    if device not in data:
        data[device] = []

    message = os.environ.get('SMARTD_MESSAGE')
    if message is None:
        lock.release()
        return
    if message not in data[device]:
        data[device].append(message)

    with open(SMART_FILE, 'wb') as f:
        f.write(pickle.dumps(data))

    lock.release()


if __name__ == '__main__':
    main()

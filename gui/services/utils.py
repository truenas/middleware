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

import pickle as pickle
import os

from lockfile import LockFile, LockTimeout


class SmartAlert(object):

    SMART_FILE = '/tmp/.smartalert'

    def __init__(self):
        self.data = {}
        self.lock = LockFile(self.SMART_FILE)

    def __enter__(self):
        while not self.lock.i_am_locking():
            try:
                self.lock.acquire(timeout=5)
            except LockTimeout:
                self.lock.break_lock()

        if os.path.exists(self.SMART_FILE):
            with open(self.SMART_FILE, 'rb') as f:
                try:
                    self.data = pickle.loads(f.read())
                except:
                    pass
        return self

    def __exit__(self, typ, value, traceback):
        with open(self.SMART_FILE, 'wb') as f:
            f.write(pickle.dumps(self.data))

        self.lock.release()
        if typ is not None:
            raise

    def message_add(self, dev, message):
        if dev not in self.data:
            self.data[dev] = []
        if message not in self.data[dev]:
            self.data[dev].append(message)

    def device_delete(self, dev):
        self.data.pop(dev, None)

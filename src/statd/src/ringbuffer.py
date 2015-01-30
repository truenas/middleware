#+
# Copyright 2014 iXsystems, Inc.
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


import time
import numpy as np
import pandas as pd


class MemoryRingBuffer(object):
    def __init__(self, size):
        self.store = np.zeros(size, dtype='M8[s],f8')
        self.store.dtype.names = ('timestamp', 'value')
        self.size = size
        self.head = 0
        self.tail = 0

    @property
    def empty(self):
        return self.head == self.tail

    @property
    def used_count(self):
        if self.empty:
            return 0

        if self.tail > self.head:
            return self.tail - self.head - 1

        if self.head > self.tail:
            return (self.size - self.head) + self.tail - 1

    @property
    def data(self):
        if self.empty:
            return []

        if self.tail > self.head:
            return self.store[self.head:self.tail]

        if self.head > self.tail:
            return np.concatenate((self.store[self.head:], self.store[:self.tail]))

    @property
    def df(self):
        if self.empty:
            return None

        return pd.DataFrame(index=self.data['timestamp'], data=self.data['value'])

    def push(self, timestamp, value):
        self.store[self.tail] = (timestamp, value)
        self.tail = (self.tail + 1) % self.size
        if self.head == self.tail:
            self.head = (self.head + 1) % self.size

    def pop(self):
        pass


class PersistentRingBuffer(object):
    def __init__(self, table, size):
        self.table = table
        self.size = size

        if not hasattr(self.table.attrs, 'tail'):
            self.table.attrs.tail = 0
            self.table.attrs.head = 0
            self.fill_initial()

    @property
    def empty(self):
        return self.table.attrs.head == self.table.attrs.tail

    @property
    def used_count(self):
        if self.empty:
            return 0

        if self.table.attrs.tail > self.table.attrs.head:
            return self.table.attrs.tail - self.table.attrs.head - 1

        if self.table.attrs.head > self.table.attrs.tail:
            return (self.size - self.table.attrs.head) + self.table.attrs.tail - 1

    @property
    def data(self):
        if self.empty:
            return None

        if self.table.attrs.tail > self.table.attrs.head:
            return self.table[self.table.attrs.head:self.table.attrs.tail]

        if self.table.attrs.head > self.table.attrs.tail:
            return np.concatenate((self.table[self.table.attrs.head:], self.table[:self.table.attrs.tail]))

    @property
    def df(self):
        if self.empty:
            return None

        return pd.DataFrame(index=pd.to_datetime(self.data['timestamp'], unit='s'), data=self.data['value'])

    def fill_initial(self):
        self.table.truncate(self.size)
        self.table.flush()

    def push(self, timestamp, value):
        self.table[self.table.attrs.tail] = (timestamp, value)
        self.table.attrs.tail = (self.table.attrs.tail + 1) % self.size
        if self.table.attrs.head == self.table.attrs.tail:
            self.table.attrs.head = (self.table.attrs.head + 1) % self.size

        self.table.flush()

    def pop(self):
        pass

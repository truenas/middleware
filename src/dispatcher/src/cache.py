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

from gevent.event import Event


class CacheStore(object):
    class CacheItem(object):
        def __init__(self):
            self.valid = Event()
            self.data = None

    def __init__(self):
        self.store = {}

    def put(self, key, data):
        item = self.store[key] if key in self.store else self.CacheItem()
        item.data = data
        item.valid.set()

        if key not in self.store:
            self.store[key] = item

    def get(self, key, default=None, timeout=None):
        item = self.store.get(key)
        if item:
            item.valid.wait(timeout)
            return item.data

        return default

    def remove(self, key):
        if key in self.store:
            del self.store[key]

    def exists(self, key):
        return key in self.store

    def is_valid(self, key):
        item = self.store.get(key)
        if item:
            return item.valid.is_set()

        return False

    def invalidate(self, key):
        item = self.store.get(key)
        if item:
            item.valid.clear()

    def itervalid(self):
        for key, value in self.store.items():
            if value.valid.is_set():
                yield (key, value.data)

    def validvalues(self):
        for value in self.store.values():
            if value.valid.is_set():
                yield value.data


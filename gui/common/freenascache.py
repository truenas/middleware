#+
# Copyright 2010 iXsystems, Inc.
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
# $FreeBSD$
#####################################################################
from freenasUI.common.system import get_freenas_var

import os
import cPickle as pickle
import syslog
import time
import bsddb3

from bsddb3 import db
from syslog import syslog, LOG_DEBUG

FREENAS_CACHEDIR = get_freenas_var("FREENAS_CACHEDIR", "/var/tmp/.cache")
FREENAS_CACHEEXPIRE = int(get_freenas_var("FREENAS_CACHEEXPIRE", 60))

class FreeNAS_BaseCache(object):
    def __init__(self, cachedir = FREENAS_CACHEDIR):
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: enter")

        self.cachedir = cachedir 
        self.__cachefile = os.path.join(self.cachedir, ".cache.db")

        if not self.__dir_exists(self.cachedir):
            os.makedirs(self.cachedir)

        self.__dbenv = db.DBEnv()
        self.__dbenv.open(self.cachedir, db.DB_INIT_CDB|db.DB_INIT_MPOOL|db.DB_CREATE, 0700)

        self.__cache = db.DB(self.__dbenv)
        self.__cache.open(self.__cachefile, None, db.DB_BTREE, db.DB_CREATE)

        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: cachedir = %s" % self.cachedir)
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: cachefile = %s" % self.__cachefile)
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: leave")


    def __dir_exists(self, path):
        path_exists = False
        try:
            st = os.stat(path)
            path_exists = True

        except OSError, e:
            path_exists = False

        return path_exists

    def __len__(self):
        return len(self.__cache)

    def __iter__(self):
        for key in sorted(self.__cache.keys()):
            obj = pickle.loads(self.__cache[key])
            yield obj

    def __getitem__(self, key):
        return pickle.loads(self.__cache.get(key))

    def __setitem__(self, key, value, overwrite=False):
        haskey = self.__cache.has_key(key)
        if (haskey and overwrite) or (not haskey):
            self.__cache[key] = pickle.dumps(value)

    def has_key(self, key):
        return self.__cache.has_key(key)

    def keys(self):
        return self.__cache.keys()

    def values(self):
        cache_values = []
        for key in self.__cache.keys():
            cache_values.append(pickle.loads(self.__cache[key]))
        return cache_values

    def items(self):
        cache_items = []
        for key in self.__cache.keys():
            cache_items.append((key, pickle.loads(self.__cache[key])))
        return cache_items

    def empty(self):
        return (len(self.__cache) == 0)

    def expire(self):
        for key in self.__cache.keys():
            self.__cache.delete(key)
        self.__cache.close()
        os.unlink(self.__cachefile)

    def read(self, key):
        if not key:
            return None

        pobj = pickle.loads(self.__cache[key])
        return pobj

    def write(self, key, entry, overwrite=False):
        if not key:
            return False

        haskey = self.__cache.has_key(key)
        if (haskey and overwrite) or (not haskey):
            self.__cache[key] = pickle.dumps(value)
      
        return True

    def delete(self, key):
        if not key:
            return False

        self.__cache.delete(key)
        return True

    def close(self):
        self.__cache.close() 

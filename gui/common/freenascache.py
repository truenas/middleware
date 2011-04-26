#+
# Copyright 2010 iXsystems
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
import shelve 
import syslog
import time

from syslog import syslog, LOG_DEBUG

FREENAS_CACHEDIR = get_freenas_var("FREENAS_CACHEDIR", "/var/tmp/.cache")
FREENAS_CACHEEXPIRE = int(get_freenas_var("FREENAS_CACHEEXPIRE", 60))

class FreeNAS_BaseCache:
    def __init__(self, cachedir = FREENAS_CACHEDIR):
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: enter")

        self.__cachedir = cachedir 
        self.__index = os.path.join(self.__cachedir, ".index")
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: cachedir = %s" % self.__cachedir)
        syslog(LOG_DEBUG, "FreeNAS_BaseCache._init__: index = %s" % self.__index)

        #st = os.stat(self.__index + ".db") 
        #print st.st_ctime
        #print st

        #now = time.mktime(time.localtime())
        #print now

        #diffsec = int(now) - int(st.st_ctime)
        #print "diffsec = %d" % diffsec

        #diffmin  = diffsec / 60
        #print "diffmin = %d" % diffmin

        #if diffmin >= FREENAS_LDAP_CACHE_EXPIRE:
        #    print "PLEASE EXPIRE THE CACHE"

        if not self.__dir_exists(self.__cachedir):
            os.makedirs(self.__cachedir)

        self.__shelve = shelve.open(self.__index)
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
        return len(self.__shelve)

    def __iter__(self):
        for key in sorted(self.__shelve.keys()):
            obj = pickle.loads(self.__shelve[key])
            yield obj

    def __getitem__(self, key):
        return pickle.loads(self.__shelve[key])

    def __setitem__(self, key, value):
        self.__shelve[key] = pickle.dumps(value)

    def has_key(self, key):
        return self.__shelve.has_key(key)

    def keys(self):
        return self.__shelve.keys()

    def values(self):
        shelve_values = []
        for key in self.__shelve.keys():
            shelve_values.append(pickle.loads(self.__shelve[key]))
        return shelve_values

    def items(self):
        shelve_items = []
        for key in self.__shelve.keys():
            shelve_items.append((key, pickle.loads(self.__shelve[key])))
        return shelve_items

    def empty(self):
        return (len(self.__shelve) == 0)

    def expire(self):
        for key in self.__shelve.keys():
            del self.__shelve[key]
        self.__shelve.close()
        os.unlink(self.__index + ".db")

    def read(self, key):
        if not key:
            return None

        pobj = pickle.loads(self.__shelve[key])
        return pobj

    def write(self, key, entry):
        if not key:
            return False

        self.__shelve[key] = pickle.dumps(entry)
        return True

    def delete(self, key):
        if not key:
            return False

        del self.__shelve[key]
        return True

    def close(self):
        self.__shelve.close() 

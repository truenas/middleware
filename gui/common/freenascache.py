# Copyright 2013 iXsystems, Inc.
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

import os
import logging
import pickle as pickle

from bsddb3 import db
from freenasUI.common.system import (
    get_freenas_var,
    ldap_enabled,
    activedirectory_enabled,
    domaincontroller_enabled,
    nt4_enabled,
    nis_enabled
)

log = logging.getLogger('common.frenascache')

FREENAS_CACHEDIR = get_freenas_var("FREENAS_CACHEDIR", "/var/tmp/.cache")
FREENAS_CACHEEXPIRE = int(get_freenas_var("FREENAS_CACHEEXPIRE", 60))

FREENAS_USERCACHE = os.path.join(FREENAS_CACHEDIR, ".users")
FREENAS_GROUPCACHE = os.path.join(FREENAS_CACHEDIR, ".groups")

FREENAS_LDAP_CACHEROOT = os.path.join(FREENAS_CACHEDIR, ".ldap")
FREENAS_LDAP_QUERYCACHE = os.path.join(FREENAS_CACHEDIR, ".query")

FREENAS_LDAP_CACHEDIR = os.path.join(FREENAS_LDAP_CACHEROOT, ".ldap")
FREENAS_LDAP_USERCACHE = os.path.join(FREENAS_LDAP_CACHEDIR, ".users")
FREENAS_LDAP_GROUPCACHE = os.path.join(FREENAS_LDAP_CACHEDIR, ".groups")
FREENAS_LDAP_LOCALDIR = os.path.join(FREENAS_LDAP_CACHEDIR, ".local")
FREENAS_LDAP_LOCAL_USERCACHE = os.path.join(FREENAS_LDAP_LOCALDIR, ".users")
FREENAS_LDAP_LOCAL_GROUPCACHE = os.path.join(FREENAS_LDAP_LOCALDIR, "groups")

FREENAS_AD_CACHEDIR = os.path.join(FREENAS_LDAP_CACHEROOT, ".activedirectory")
FREENAS_AD_USERCACHE = os.path.join(FREENAS_AD_CACHEDIR, ".users")
FREENAS_AD_GROUPCACHE = os.path.join(FREENAS_AD_CACHEDIR, ".groups")
FREENAS_AD_LOCALDIR = os.path.join(FREENAS_AD_CACHEDIR, ".local")
FREENAS_AD_LOCAL_USERCACHE = os.path.join(FREENAS_AD_LOCALDIR, ".users")
FREENAS_AD_LOCAL_GROUPCACHE = os.path.join(FREENAS_AD_LOCALDIR, ".groups")

FREENAS_NT4_CACHEDIR = os.path.join(FREENAS_CACHEDIR, ".nt4")
FREENAS_NT4_USERCACHE = os.path.join(FREENAS_NT4_CACHEDIR, ".users")
FREENAS_NT4_GROUPCACHE = os.path.join(FREENAS_NT4_CACHEDIR, ".groups")
FREENAS_NT4_LOCALDIR = os.path.join(FREENAS_NT4_CACHEDIR, ".local")
FREENAS_NT4_LOCAL_USERCACHE = os.path.join(FREENAS_NT4_LOCALDIR, ".users")
FREENAS_NT4_LOCAL_GROUPCACHE = os.path.join(FREENAS_NT4_LOCALDIR, ".groups")

FREENAS_NIS_CACHEDIR = os.path.join(FREENAS_CACHEDIR, ".nis")
FREENAS_NIS_USERCACHE = os.path.join(FREENAS_NIS_CACHEDIR, ".users")
FREENAS_NIS_GROUPCACHE = os.path.join(FREENAS_NIS_CACHEDIR, ".groups")
FREENAS_NIS_LOCALDIR = os.path.join(FREENAS_NIS_CACHEDIR, ".local")
FREENAS_NIS_LOCAL_USERCACHE = os.path.join(FREENAS_NIS_LOCALDIR, ".users")
FREENAS_NIS_LOCAL_GROUPCACHE = os.path.join(FREENAS_NIS_LOCALDIR, ".groups")

FREENAS_DC_CACHEDIR = os.path.join(FREENAS_CACHEDIR, ".nis")
FREENAS_DC_USERCACHE = os.path.join(FREENAS_DC_CACHEDIR, ".users")
FREENAS_DC_GROUPCACHE = os.path.join(FREENAS_DC_CACHEDIR, ".groups")
FREENAS_DC_LOCALDIR = os.path.join(FREENAS_DC_CACHEDIR, ".local")
FREENAS_DC_LOCAL_USERCACHE = os.path.join(FREENAS_DC_LOCALDIR, ".users")
FREENAS_DC_LOCAL_GROUPCACHE = os.path.join(FREENAS_DC_LOCALDIR, ".groups")

FLAGS_CACHE_READ_USER = 0x00000001
FLAGS_CACHE_WRITE_USER = 0x00000002
FLAGS_CACHE_READ_GROUP = 0x00000004
FLAGS_CACHE_WRITE_GROUP = 0x00000008
FLAGS_CACHE_READ_QUERY = 0x00000010
FLAGS_CACHE_WRITE_QUERY = 0x00000020


class FreeNAS_BaseCache(object):
    def __init__(self, cachedir=FREENAS_CACHEDIR):
        log.debug("FreeNAS_BaseCache._init__: enter")

        self.cachedir = cachedir
        self.__cachefile = os.path.join(self.cachedir, ".cache.db")

        if not self.__dir_exists(self.cachedir):
            os.makedirs(self.cachedir)

        flags = db.DB_CREATE | db.DB_THREAD | db.DB_INIT_LOCK | db.DB_INIT_LOG | \
            db.DB_INIT_MPOOL | db.DB_THREAD | db.DB_INIT_TXN

        self.__dbenv = db.DBEnv()
        self.__dbenv.open(
            self.cachedir,
            flags,
            0o700
        )

        self.__cache = db.DB(self.__dbenv)
        self.__cache.open(self.__cachefile, None, db.DB_HASH, db.DB_CREATE)

        log.debug("FreeNAS_BaseCache._init__: cachedir = %s", self.cachedir)
        log.debug(
            "FreeNAS_BaseCache._init__: cachefile = %s",
            self.__cachefile
        )
        log.debug("FreeNAS_BaseCache._init__: leave")

    def __dir_exists(self, path):
        path_exists = False
        try:
            os.stat(path)
            path_exists = True

        except OSError:
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
        if isinstance(key, str):
            key = key.encode('utf8')
        haskey = key in self.__cache
        if (haskey and overwrite) or (not haskey):
            self.__cache[key] = pickle.dumps(value)

    def has_key(self, key):
        return key in self.__cache

    def keys(self):
        return list(self.__cache.keys())

    def values(self):
        cache_values = []
        for key in list(self.__cache.keys()):
            cache_values.append(pickle.loads(self.__cache[key]))
        return cache_values

    def items(self):
        cache_items = []
        for key in list(self.__cache.keys()):
            cache_items.append((key, pickle.loads(self.__cache[key])))
        return cache_items

    def empty(self):
        return (len(self.__cache) == 0)

    def expire(self):
        for key in list(self.__cache.keys()):
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

        haskey = key in self.__cache
        if (haskey and overwrite) or (not haskey):
            self.__cache[key] = pickle.dumps(entry)

        return True

    def delete(self, key):
        if not key:
            return False

        self.__cache.delete(key)
        return True

    def close(self):
        self.__cache.close()


class FreeNAS_LDAP_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_UserCache, self).__init__(cachedir)

        log.debug("FreeNAS_LDAP_UserCache.__init__: leave")


class FreeNAS_LDAP_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_GroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_LDAP_GroupCache.__init__: leave")


class FreeNAS_LDAP_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_LocalUserCache, self).__init__(cachedir)

        log.debug("FreeNAS_LDAP_LocalUserCache.__init__: leave")


class FreeNAS_LDAP_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_LocalGroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_LDAP_LocalGroupCache.__init__: leave")


class FreeNAS_ActiveDirectory_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_UserCache, self).__init__(cachedir)

        log.debug("FreeNAS_ActiveDirectory_UserCache.__init__: leave")


class FreeNAS_ActiveDirectory_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_GroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_ActiveDirectory_GroupCache.__init__: leave")


class FreeNAS_ActiveDirectory_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_LocalUserCache, self).__init__(cachedir)

        log.debug("FreeNAS_ActiveDirectory_LocalUserCache.__init__: leave")


class FreeNAS_ActiveDirectory_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_LocalGroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_ActiveDirectory_LocalGroupCache.__init__: leave")


class FreeNAS_LDAP_QueryCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_QueryCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_QUERYCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_QueryCache, self).__init__(cachedir)

        log.debug("FreeNAS_LDAP_QueryCache.__init__: leave")


class FreeNAS_NT4_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NT4_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NT4_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NT4_UserCache, self).__init__(cachedir)

        log.debug("FreeNAS_NT4_UserCache.__init__: leave")


class FreeNAS_NT4_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NT4_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NT4_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NT4_GroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_NT4_GroupCache.__init__: leave")


class FreeNAS_NT4_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NT4_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NT4_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NT4_LocalUserCache, self).__init__(cachedir)

        log.debug("FreeNAS_NT4_LocalUserCache.__init__: leave")


class FreeNAS_NT4_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NT4_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NT4_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NT4_LocalGroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_NT4_LocalGroupCache.__init__: leave")


class FreeNAS_NIS_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NIS_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NIS_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NIS_UserCache, self).__init__(cachedir)

        log.debug("FreeNAS_NIS_UserCache.__init__: leave")


class FreeNAS_NIS_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NIS_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NIS_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NIS_GroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_NIS_GroupCache.__init__: leave")


class FreeNAS_NIS_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NIS_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NIS_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NIS_LocalUserCache, self).__init__(cachedir)

        log.debug("FreeNAS_NIS_LocalUserCache.__init__: leave")


class FreeNAS_NIS_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_NIS_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_NIS_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_NIS_LocalGroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_NIS_LocalGroupCache.__init__: leave")


class FreeNAS_DomainController_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_DC_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_DomainController_UserCache, self).__init__(cachedir)

        log.debug("FreeNAS_DomainController_UserCache.__init__: leave")


class FreeNAS_DomainController_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_DC_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_DomainController_GroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_DomainController_GroupCache.__init__: leave")


class FreeNAS_DomainController_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_DC_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_DomainController_LocalUserCache, self).__init__(cachedir)

        log.debug("FreeNAS_DomainController_LocalUserCache.__init__: leave")


class FreeNAS_DomainController_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_DC_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_DomainController_LocalGroupCache, self).__init__(cachedir)

        log.debug("FreeNAS_DomainController_LocalGroupCache.__init__: leave")


class FreeNAS_Directory_UserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_UserCache.__new__: enter")

        obj = None
        if ldap_enabled():
            obj = FreeNAS_LDAP_UserCache(**kwargs)

        elif activedirectory_enabled():
            obj = FreeNAS_ActiveDirectory_UserCache(**kwargs)

        elif nt4_enabled():
            obj = FreeNAS_NT4_UserCache(**kwargs)

        elif nis_enabled():
            obj = FreeNAS_NIS_UserCache(**kwargs)

        elif domaincontroller_enabled():
            obj = FreeNAS_DomainController_UserCache(**kwargs)

        log.debug("FreeNAS_Directory_UserCache.__new__: leave")
        return obj


class FreeNAS_Directory_GroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_GroupCache.__new__: enter")

        obj = None
        if ldap_enabled():
            obj = FreeNAS_LDAP_GroupCache(**kwargs)

        elif activedirectory_enabled():
            obj = FreeNAS_ActiveDirectory_GroupCache(**kwargs)

        elif nt4_enabled():
            obj = FreeNAS_NT4_GroupCache(**kwargs)

        elif nis_enabled():
            obj = FreeNAS_NIS_GroupCache(**kwargs)

        elif domaincontroller_enabled():
            obj = FreeNAS_DomainController_GroupCache(**kwargs)

        log.debug("FreeNAS_Directory_GroupCache.__new__: leave")
        return obj


class FreeNAS_Directory_LocalUserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_LocalUserCache.__new__: enter")

        obj = None
        if ldap_enabled():
            obj = FreeNAS_LDAP_LocalUserCache(**kwargs)

        elif activedirectory_enabled():
            obj = FreeNAS_ActiveDirectory_LocalUserCache(**kwargs)

        elif nt4_enabled():
            obj = FreeNAS_NT4_LocalUserCache(**kwargs)

        elif nis_enabled():
            obj = FreeNAS_NIS_LocalUserCache(**kwargs)

        elif domaincontroller_enabled():
            obj = FreeNAS_DomainController_LocalUserCache(**kwargs)

        log.debug("FreeNAS_Directory_LocalUserCache.__new__: leave")
        return obj


class FreeNAS_Directory_LocalGroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_LocalGroupCache.__new__: enter")

        obj = None
        if ldap_enabled():
            obj = FreeNAS_LDAP_LocalGroupCache(**kwargs)

        elif activedirectory_enabled():
            obj = FreeNAS_ActiveDirectory_LocalGroupCache(**kwargs)

        elif nt4_enabled():
            obj = FreeNAS_NT4_LocalGroupCache(**kwargs)

        elif nis_enabled():
            obj = FreeNAS_NIS_LocalGroupCache(**kwargs)

        elif domaincontroller_enabled():
            obj = FreeNAS_DomainController_LocalGroupCache(**kwargs)

        log.debug("FreeNAS_Directory_LocalGroupCache.__new__: leave")
        return obj


class FreeNAS_UserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_UserCache.__new__: enter")

        obj = None
        if (
            ldap_enabled() or activedirectory_enabled() or
            nt4_enabled() or nis_enabled() or
            domaincontroller_enabled() or nis_enabled()
        ):
            obj = FreeNAS_Directory_LocalUserCache(**kwargs)

        else:
            obj = FreeNAS_BaseCache(**kwargs)

        log.debug("FreeNAS_UserCache.__new__: leave")
        return obj


class FreeNAS_GroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_GroupCache.__new__: enter")

        obj = None
        if (
            ldap_enabled() or activedirectory_enabled() or
            nt4_enabled() or nis_enabled() or
            domaincontroller_enabled() or nis_enabled()
        ):
            obj = FreeNAS_Directory_LocalGroupCache(**kwargs)

        else:
            obj = FreeNAS_BaseCache(**kwargs)

        log.debug("FreeNAS_GroupCache.__new__: leave")
        return obj

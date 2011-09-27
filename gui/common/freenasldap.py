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
from freenasUI.common.freenascache import FreeNAS_BaseCache, FREENAS_CACHEDIR
from freenasUI.common.system import get_freenas_var, service_enabled

import os
import grp
import pwd
import types
import ldap
import syslog
import time
import hashlib
import sqlite3

from syslog import syslog, LOG_DEBUG
from ldap.controls import SimplePagedResultsControl
from dns import resolver


FREENAS_LDAP_NOSSL = 0
FREENAS_LDAP_USESSL = 1
FREENAS_LDAP_USETLS = 2

FREENAS_LDAP_PORT = get_freenas_var("FREENAS_LDAP_PORT", 389)
FREENAS_LDAP_SSL_PORT = get_freenas_var("FREENAS_LDAP_SSL_PORT", 636)

FREENAS_USERCACHE = os.path.join(FREENAS_CACHEDIR, ".users")
FREENAS_GROUPCACHE = os.path.join(FREENAS_CACHEDIR, ".groups")

FREENAS_LDAP_CACHEROOT = os.path.join(FREENAS_CACHEDIR, ".ldap")
FREENAS_LDAP_QUERYCACHE	= os.path.join(FREENAS_CACHEDIR, ".query")

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

FREENAS_AD_SEPARATOR = get_freenas_var("FREENAS_AD_SEPARATOR", '\\')

FREENAS_LDAP_CACHE_EXPIRE = get_freenas_var("FREENAS_LDAP_CACHE_EXPIRE", 60)
FREENAS_LDAP_CACHE_ENABLE = get_freenas_var("FREENAS_LDAP_CACHE_ENABLE", 1)

FREENAS_LDAP_VERSION = ldap.VERSION3
FREENAS_LDAP_REFERRALS = get_freenas_var("FREENAS_LDAP_REFERRALS", 0)
FREENAS_LDAP_CACERTFILE = get_freenas_var("CERT_FILE")

FREENAS_LDAP_PAGESIZE = get_freenas_var("FREENAS_LDAP_PAGESIZE", 8192)

FREENAS_DATABASE = get_freenas_var("FREENAS_DATABASE", "/data/freenas-v1.db")

ldap.protocol_version = FREENAS_LDAP_VERSION
ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

FLAGS_CACHE_READ_USER    = 0x00000001
FLAGS_CACHE_WRITE_USER   = 0x00000002
FLAGS_CACHE_READ_GROUP   = 0x00000004
FLAGS_CACHE_WRITE_GROUP  = 0x00000008
FLAGS_CACHE_READ_QUERY   = 0x00000010
FLAGS_CACHE_WRITE_QUERY  = 0x00000020

FLAGS_DBINIT             = 0x00010000


def LDAPEnabled():
    return service_enabled('ldap')

def LDAP_objects():
    h = sqlite3.connect(FREENAS_DATABASE)
    h.row_factory = sqlite3.Row
    c = h.cursor()

    results = c.execute("SELECT * FROM services_ldap ORDER BY -id")

    objects = []
    for row in results:
        obj = {}
        for key in row.keys():
            obj[key] = row[key]
        objects.append(obj)

    c.close()
    h.close()
    return objects
    

def ActiveDirectoryEnabled():
    return service_enabled('activedirectory')

def ActiveDirectory_objects():
    h = sqlite3.connect(FREENAS_DATABASE)
    h.row_factory = sqlite3.Row
    c = h.cursor()

    results = c.execute("SELECT * FROM services_activedirectory ORDER BY -id")

    objects = []
    for row in results:
        obj = {}
        for key in row.keys():
            obj[key] = row[key]
        objects.append(obj)

    c.close()
    h.close()
    return objects


class FreeNAS_LDAP_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_USERCACHE)
        dir = kwargs.get('dir', None)
        
        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_UserCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_UserCache.__init__: leave")


class FreeNAS_LDAP_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_GroupCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_GroupCache.__init__: leave")


class FreeNAS_LDAP_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_LocalUserCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_LocalUserCache.__init__: leave")


class FreeNAS_LDAP_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_LocalGroupCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_LocalGroupCache.__init__: leave")


class FreeNAS_ActiveDirectory_UserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_UserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_UserCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_UserCache.__init__: leave")


class FreeNAS_ActiveDirectory_GroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_GroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_GroupCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_GroupCache.__init__: leave")


class FreeNAS_ActiveDirectory_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_LocalUserCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_LOCAL_USERCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_LocalUserCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_LocalUserCache.__init__: leave")


class FreeNAS_ActiveDirectory_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_LocalGroupCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_AD_LOCAL_GROUPCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_ActiveDirectory_LocalGroupCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_LocalGroupCache.__init__: leave")


class FreeNAS_LDAP_QueryCache(FreeNAS_BaseCache):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_QueryCache.__init__: enter")

        cachedir = kwargs.get('cachedir', FREENAS_LDAP_QUERYCACHE)
        dir = kwargs.get('dir', None)

        cachedir = cachedir if not dir else os.path.join(cachedir, dir)
        super(FreeNAS_LDAP_QueryCache, self).__init__(cachedir)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_QueryCache.__init__: leave")


class FreeNAS_Directory_UserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_UserCache.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_UserCache(**kwargs)
 
        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_UserCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_UserCache.__new__: leave")
        return obj


class FreeNAS_Directory_GroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_GroupCache.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_GroupCache(**kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_GroupCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_GroupCache.__new__: leave")
        return obj


class FreeNAS_Directory_LocalUserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_LocalUserCache.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_LocalUserCache(**kwargs)
 
        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_LocalUserCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_LocalUserCache.__new__: leave")
        return obj


class FreeNAS_Directory_LocalGroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_LocalGroupCache.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_LocalGroupCache(**kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_LocalGroupCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_LocalGroupCache.__new__: leave")
        return obj


class FreeNAS_UserCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_UserCache.__new__: enter")

        obj = None
        if LDAPEnabled() or ActiveDirectoryEnabled():
            obj = FreeNAS_Directory_LocalUserCache(**kwargs)

        else:
            obj = FreeNAS_BaseCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_UserCache.__new__: leave")
        return obj


class FreeNAS_GroupCache(FreeNAS_BaseCache):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_GroupCache.__new__: enter")

        obj = None
        if LDAPEnabled() or ActiveDirectoryEnabled():
            obj = FreeNAS_Directory_LocalGroupCache(**kwargs)

        else:
            obj = FreeNAS_BaseCache(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_GroupCache.__new__: leave")
        return obj


# Fill these in!
class FreeNAS_LDAP_Directory_Exception(Exception):
    pass
class FreeNAS_ActiveDirectory_Exception(FreeNAS_LDAP_Directory_Exception):
    pass
class FreeNAS_LDAP_Exception(FreeNAS_LDAP_Directory_Exception):
    pass


class FreeNAS_LDAP_Directory(object):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.__init__: enter")

        self.host = kwargs['host'] if kwargs.has_key('host') else None

        self.port = None
        if kwargs.has_key('port') and kwargs['port'] is not None: 
            self.port = long(kwargs['port']) 

        self.binddn = kwargs['binddn'] if kwargs.has_key('binddn') else None
        self.bindpw = kwargs['bindpw'] if kwargs.has_key('bindpw') else None
        self.basedn = kwargs['basedn'] if kwargs.has_key('basedn') else None

        self.ssl = FREENAS_LDAP_NOSSL
        if kwargs.has_key('ssl') and kwargs['ssl'] is not None:
            self.ssl = self._setssl(kwargs['ssl'])
            if self.ssl is FREENAS_LDAP_USESSL and self.port is None:
                self.port = FREENAS_LDAP_SSL_PORT
     
        if self.port is None:
            self.port = FREENAS_LDAP_PORT

        self.scope = ldap.SCOPE_SUBTREE
        if kwargs.has_key('scope') and kwargs['scope'] is not None:
            self.scope = kwargs['scope']

        self.filter = kwargs['filter'] if kwargs.has_key('filter') else None
        self.attributes = kwargs['attributes'] if kwargs.has_key('attributes') else None

        self.pagesize = 0
        if kwargs.has_key('pagesize') and kwargs['pagesize'] is not None:
            self.pagesize = kwargs['pagesize']

        self.flags = 0
        if kwargs.has_key('flags') and kwargs['flags'] is not None:
            self.flags = kwargs['flags']

        self._handle = None
        self._isopen = False
        self._cache = FreeNAS_LDAP_QueryCache()
        self._settings = []

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.__init__: "
            "host = %s, port = %ld, binddn = %s, basedn = %s, ssl = %d" %
            (self.host, self.port, self.binddn, self.basedn, self.ssl))
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.__init__: leave")

    def _save(self):
        _s = {}
        _s.update(self.__dict__)
        self._settings.append(_s)

    def _restore(self):
        if self._settings:
            _s = self._settings.pop()
            self.__dict__.update(_s)


    def _logex(self, ex):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory[ERROR]: An LDAP Exception occured")
        for e in ex:
            if e.has_key('info'):
                syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory[ERROR]: info: '%s'" % e['info'])
            if e.has_key('desc'):
                syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory[ERROR]: desc: '%s'" % e['desc'])

    def isOpen(self):
        return self._isopen

    def _setssl(self, ssl):
        tok = FREENAS_LDAP_NOSSL

        if type(ssl) in (types.IntType, types.LongType) or ssl.isdigit():
            ssl = int(ssl)
            if ssl not in (FREENAS_LDAP_NOSSL,
                FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                tok = FREENAS_LDAP_NOSSL

        else:
            if ssl == "start_tls":
                tok = FREENAS_LDAP_USETLS
            elif ssl == "on":
                tok = FREENAS_LDAP_USESSL

        return tok

    def _geturi(self):
        if self.host is None:
            return None

        uri = None
        if self.ssl in (FREENAS_LDAP_NOSSL, FREENAS_LDAP_USETLS):
            proto = "ldap"

        elif self.ssl == FREENAS_LDAP_USESSL:
            proto = "ldaps"

        else:
            proto = "ldap"

        uri = "%s://%s:%d" % (proto, self.host, self.port)
        return uri

    def open(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: enter")

        if self._isopen:
            return True

        if self.host:
            uri = self._geturi()
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: uri = %s" % uri)

            self._handle = ldap.initialize(self._geturi())
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: initialized")
       
        if self._handle:
            res = None
            self._handle.protocol_version = FREENAS_LDAP_VERSION
            self._handle.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

            if self.ssl in (FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                self._handle.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                self._handle.set_option(ldap.OPT_X_TLS_CACERTFILE, FREENAS_LDAP_CACERTFILE)
                self._handle.set_option(ldap.OPT_X_TLS_NEWCTX, ldap.OPT_X_TLS_DEMAND)

            if self.ssl == FREENAS_LDAP_USETLS:
                try:
                    self._handle.start_tls_s() 
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: started TLS")

                except ldap.LDAPError, e:
                    self._logex(e)
                    pass

            if self.binddn and self.bindpw:
                try:
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: "
                        "trying to bind to %s:%d" % (self.host, self.port))
                    res = self._handle.simple_bind_s(self.binddn, self.bindpw)
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: binded")

                except ldap.LDAPError, e:
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: "
                        "coud not bind to %s:%d" % (self.host, self.port))
                    self._logex(e)
                    res = None
            else:
                try:
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: "
                        "trying to bind to %s:%d" % (self.host, self.port))
                    res = self._handle.simple_bind_s()
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: binded")

                except ldap.LDAPError, e:
                    syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: "
                        "coud not bind to %s:%d" % (self.host, self.port))
                    self._logex(e)
                    res = None

            if res:
                self._isopen = True
                syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: connection open")

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.open: leave")
        return (self._isopen == True)

    def unbind(self):
        if self._handle:
            self._handle.unbind()
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.unbind: unbind")

    def close(self):
        if self._isopen:
            self.unbind()
            self._handle = None
            self._isopen = False
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.close: connection closed")

    def _search(self, basedn="", scope=ldap.SCOPE_SUBTREE, filter=None, attributes=None,
        attrsonly=0, serverctrls=None, clientctrls=None, timeout=-1, sizelimit=0):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: basedn = '%s', filter = '%s'" % (basedn, filter))
        if not self._isopen:
            return None

        m = hashlib.sha256()
        m.update(filter + self.host + str(self.port) + (basedn if basedn else ''))
        key = m.hexdigest()
        m = None

        if filter is not None and self._cache.has_key(key):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: query in cache")
            return self._cache[key]

        result = []
        results = []
        paged = SimplePagedResultsControl(
            True,
            size=self.pagesize,
            cookie=''
        )

        paged_ctrls = { SimplePagedResultsControl.controlType:SimplePagedResultsControl, }

        if self.pagesize > 0:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: pagesize = %d" % self.pagesize)

            page = 0
            while True:
                syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: getting page %d" % page)
                serverctrls = [paged]

                id = self._handle.search_ext(
                   basedn,
                   scope,
                   filterstr=filter,
                   attrlist=attributes,
                   attrsonly=attrsonly,
                   serverctrls=serverctrls,
                   clientctrls=clientctrls,
                   timeout=timeout,
                   sizelimit=sizelimit
                )

                (rtype, rdata, rmsgid, serverctrls) = self._handle.result3(
                    id, resp_ctrl_classes=paged_ctrls
                )

                for entry in rdata:
                    result.append(entry)

                cookie = None
                for sc in serverctrls:
                    if sc.controlType == SimplePagedResultsControl.controlType:
                        cookie = sc.cookie 
                        if cookie:
                            paged.cookie = cookie
                            paged.size = self.pagesize

                        break

                if not cookie:
                    break

                page += 1 
        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: pagesize = 0")

            id = self._handle.search_ext(
                basedn,
                scope,
                filterstr=filter,
                attrlist=attributes,
                attrsonly=attrsonly,
                serverctrls=serverctrls,
                clientctrls=clientctrls,
                timeout=timeout,
                sizelimit=sizelimit
            )

            type = ldap.RES_SEARCH_ENTRY
            while type != ldap.RES_SEARCH_RESULT:
                try:
                    type, data = self._handle.result(id, 0)

                except ldap.LDAPError, e:
                    self._logex(e)
                    break

                results.append(data)

            for i in range(len(results)):
                for entry in results[i]:
                    result.append(entry)

            self._cache[key] = result

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: %d results" % len(result))
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory._search: leave")
        return result

    def search(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Directory.search: enter")
        isopen = self._isopen
        self.open()

        results = self._search(self.basedn, self.scope, self.filter, self.attributes)
        if not isopen:
            self.close()

        return results


class FreeNAS_LDAP_Base(FreeNAS_LDAP_Directory):
    def __db_init__(self, **kwargs): 
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__db_init__: enter")

        ldap = LDAP_objects()[0]

        host = port = None
        tmphost = ldap['ldap_hostname']
        if tmphost:
            parts = tmphost.split(':')
            host = parts[0]
            if len(parts) > 1 and parts[1]:
                port = long(parts[1])

        binddn = ldap['ldap_rootbasedn']
        bindpw = ldap['ldap_rootbindpw']
        basedn = ldap['ldap_basedn']

        ssl = FREENAS_LDAP_NOSSL
        if ldap.has_key('ldap_ssl') and ldap['ldap_ssl']:
            ssl = ldap['ldap_ssl']

        args = {'binddn': binddn, 'bindpw': bindpw, 'basedn': basedn, 'ssl': ssl }
        if host:
            args['host'] = host
            if port:
                args['port'] = port

        super(FreeNAS_LDAP_Base, self).__init__(**args)

        self.rootbasedn = ldap['ldap_rootbasedn']
        self.rootbindpw = ldap['ldap_rootbindpw']
        self.usersuffix = ldap['ldap_usersuffix']
        self.groupsuffix = ldap['ldap_groupsuffix']
        self.machinesuffix = ldap['ldap_machinesuffix']
        self.passwordsuffix = ldap['ldap_passwordsuffix']
        self.pwencryption = ldap['ldap_pwencryption']
        self.anonbind = ldap['ldap_anonbind']

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__db_init__: leave")

    def __no_db_init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__no_db_init__: enter")

        host = None
        tmphost = kwargs['host'] if kwargs.has_key('host') else None
        if tmphost:
            host = tmphost.split(':')[0]
            port = long(kwargs['port']) if kwargs.has_key('port') else None 
            if port == None:
                tmp = tmphost.split(':') 
                if len(tmp) > 1:
                    port = long(tmp[1])  
        
        if kwargs.has_key('port') and kwargs['port'] and not port:  
            port = long(kwargs['port'])

        binddn = kwargs['binddn'] if kwargs.has_key('binddn') else None
        bindpw = kwargs['bindpw'] if kwargs.has_key('bindpw') else None
        basedn = kwargs['basedn'] if kwargs.has_key('basedn') else None

        ssl = FREENAS_LDAP_NOSSL
        if kwargs.has_key('ssl') and kwargs['ssl']:
            ssl = kwargs['ssl']

        args = {'binddn': binddn, 'bindpw': bindpw, 'basedn': basedn, 'ssl': ssl }
        if host:
            args['host'] = host
            if port:
                args['port'] = port

        super(FreeNAS_LDAP_Base, self).__init__(**args)

        self.rootbasedn = kwargs['rootbasedn'] if kwargs.has_key('rootbasedn') else None
        self.rootbindpw = kwargs['rootbindpw'] if kwargs.has_key('rootbindpw') else None
        self.usersuffix = kwargs['usersuffix'] if kwargs.has_key('usersuffix') else None
        self.groupsuffix = kwargs['groupsuffix'] if kwargs.has_key('groupsuffix') else None
        self.machinesuffix = kwargs['machinesuffix'] if kwargs.has_key('machinesuffix') else None
        self.passwordsuffix = kwargs['passwordsuffix'] if kwargs.has_key('passwordsuffix') else None
        self.pwencryption = kwargs['pwencryption'] if kwargs.has_key('pwencryption') else None
        self.anonbind = kwargs['anonbind'] if kwargs.has_key('anonbind') else None

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__no_db_init__: leave")

    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__init__: enter")

        __initfunc__ = self.__no_db_init__
        if kwargs.has_key('flags') and (kwargs['flags'] & FLAGS_DBINIT):
            __initfunc__ = self.__db_init__

        __initfunc__(**kwargs)
        self.ucount = 0
        self.gcount = 0

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.__init__: leave")

    def get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_user: user = %s" % user)
        isopen = self._isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        if type(user) in (types.IntType, types.LongType):
            filter = '(&(|(objectclass=person)(objectclass=account))(uidnumber=%d))' % user

        elif user.isdigit():

            filter = '(&(|(objectclass=person)(objectclass=account))(uidnumber=%s))' % user
        else:
            filter = '(&(|(objectclass=person)(objectclass=account))(|(uid=%s)(cn=%s)))' % (user, user)

        basedn = None
        if self.usersuffix and self.basedn:
            basedn = "%s,%s" % (self.usersuffix, self.basedn)

        args = { 'scope':scope, 'filter':filter }
        if basedn:
            args['basedn'] = basedn
        if self.attributes:
            args['attributes'] = self.attributes

        results = self._search(**args)
        if results:
            for r in results:
                if r[0]:
                    ldap_user = r
                    break

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_user: leave")
        return ldap_user

    def get_users(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_users: enter")
        isopen = self._isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=person)(objectclass=account))(uid=*))'

        basedn = "%s,%s" % (self.usersuffix, self.basedn)
        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    users.append(r)

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_users: leave")
        return users

    def get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_group: group = %s" % group)
        isopen = self._isopen
        self.open()

        ldap_group = None
        scope = ldap.SCOPE_SUBTREE

        if type(group) in (types.IntType, types.LongType):
            filter = '(&(objectclass=posixgroup)(gidnumber=%d))' % group
        elif group.isdigit():
            filter = '(&(objectclass=posixgroup)(gidnumber=%s))' % group
        else:
            filter = '(&(objectclass=posixgroup)(cn=%s))' % group

        basedn = "%s,%s" % (self.groupsuffix, self.basedn)
        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ldap_group = r
                    break

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_group: leave")
        return ldap_group

    def get_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_groups: enter")
        isopen = self._isopen
        self.open()

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=posixgroup)(gidnumber=*))'

        basedn = "%s,%s" % (self.groupsuffix, self.basedn)
        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    groups.append(r)

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Base.get_groups: leave")
        return groups


class FreeNAS_LDAP(FreeNAS_LDAP_Base):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__init__: enter")

        super(FreeNAS_LDAP, self).__init__(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_LDAP.__init__: leave")


class FreeNAS_ActiveDirectory_Base(FreeNAS_LDAP_Directory):

    @staticmethod 
    def get_domain_controllers(domain):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain_controllers: enter")
        dcs = [] 
        
        if not domain:
            return dcs

        host = "_ldap._tcp.%s" % domain

        try:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain_controllers: "
                "looking up SRV records for %s" % host)
            answers = resolver.query(host, 'SRV')
            dcs = sorted(answers, key=lambda a: (int(a.priority), int(a.weight)))

        except:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain_controllers: "
                "no SRV records for %s found, fail!" % host)
            dcs = [] 

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain_controllers: leave")
        return dcs

    @staticmethod
    def get_global_catalogs(domain):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_global_catalogs: enter")
        gcs = []

        if not domain:
            return gcs

        host = "_gc._tcp.%s" % domain

        try:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_global_catalogs: "
                "looking up SRV records for %s" % host)
            answers = resolver.query(host, 'SRV')
            gcs = sorted(answers, key=lambda a: (int(a.priority), int(a.weight)))

        except:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_global_catalogs: "
                "no SRV records for %s found, fail!" % host)
            gcs = []

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_global_catalogs: leave")
        return gcs

    @staticmethod
    def dc_connect(domain, binddn, bindpw):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.dc_connect: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.dc_connect: domain = %s" % domain)

        ret = False
        args = { 'binddn': binddn, 'bindpw': bindpw }

        host = port = None
        dcs = FreeNAS_ActiveDirectory_Base.get_domain_controllers(domain)
        for dc in dcs:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.dc_connect: "
                "trying [%s]..." % dc)

            args['domain'] = domain
            args['host'] = dc.target.to_text(True)
            args['port'] = long(dc.port)

            ad = FreeNAS_ActiveDirectory_Base(**args)

            ret = ad.open()
            if ret == True:
                host = ad.host
                port = ad.port
                ret = (host, port)
                break

            ad.close()

   
        if not ret:
            ret = (None, None)
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.dc_connect: "
                "unable to connect to a domain controller")

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.dc_connect: leave")
        return ret

    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__new__: enter")

        obj = None
        if kwargs:
            obj = super(FreeNAS_ActiveDirectory_Base, cls).__new__(cls, **kwargs) 

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__new__: leave")
        return obj

    def __db_init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__db_init__: enter")

        ad = ActiveDirectory_objects()[0]

        self.domain = ad['ad_domainname']
        self.netbiosname = ad['ad_workgroup']
        self.binddn = ad['ad_adminname'] + '@' + self.domain.upper()
        self.bindpw = ad['ad_adminpw']

        host = port = None
        args = { 'binddn': self.binddn, 'bindpw': self.bindpw }

        (host, port) = self.dc_connect(self.domain, self.binddn, self.bindpw)
        args['host'] = host
        args['port'] = port

        if kwargs.has_key('flags'): 
            args['flags'] = kwargs['flags']

        super(FreeNAS_ActiveDirectory_Base, self).__init__(**args)

        self.basedn = self.get_baseDN()
        self.netbiosname = self.get_netbios_name()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__db_init__: leave")

    def __no_db_init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__no_db_init__: enter")

        host = port = None 
        self.domain = kwargs['domain'] if kwargs.has_key('domain') else None
        self.netbiosname = kwargs['netbiosname'] if kwargs.has_key('netbiosname') else None

        tmphost = kwargs['host'] if kwargs.has_key('host') else None
        if tmphost:
            host = tmphost.split(':')[0]
            port = long(kwargs['port']) if kwargs.has_key('port') else None
            if port == None:
                tmp = tmphost.split(':')
                if len(tmp) > 1:
                    port = long(tmp[1])

        if kwargs.has_key('port') and kwargs['port'] and not port:
            port = long(kwargs['port'])

        self.binddn = kwargs['binddn'] if kwargs.has_key('binddn') else None
        self.bindpw = kwargs['bindpw'] if kwargs.has_key('bindpw') else None

        args = { 'binddn': self.binddn, 'bindpw': self.bindpw }
        if host:
            args['host'] = host
            if port:
                args['port'] = port

        if not host and not self.domain:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__no_db_init__: "
                "neither host nor domain specified, nothing will work, #fail.")

        if not host:
            (host, port) = self.dc_connect(self.domain, self.binddn, self.bindpw)
            args['host'] = host
            args['port'] = port

        if kwargs.has_key('flags'): 
            args['flags'] = kwargs['flags']

        super(FreeNAS_ActiveDirectory_Base, self).__init__(**args)

        self.basedn = self.get_baseDN()
        self.netbiosname = self.get_netbios_name()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__no_db_init__: leave")

    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__init__: enter")
        
        __initfunc__ = self.__no_db_init__
        if kwargs.has_key('flags') and (kwargs['flags'] & FLAGS_DBINIT):
            __initfunc__ = self.__db_init__
        
        __initfunc__(**kwargs)
        self.ucount = 0
        self.gcount = 0

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.__init__: leave")

    def get_rootDSE(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_rootDSE: enter")
        isopen = self._isopen
        self.open()

        results = self._search('', ldap.SCOPE_BASE, "(objectclass=*)")
        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_rootDSE: leave")
        return results

    def get_rootDN(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_rootDN: enter")
        isopen = self._isopen
        self.open()

        results = self.get_rootDSE()
        try:
            results = results[0][1]['rootDomainNamingContext'][0]

        except:
            results = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_rootDN: leave")
        return results

    def get_baseDN(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_baseDN: enter")
        isopen = self._isopen
        self.open()

        results = self.get_rootDSE()
        try:
            results = results[0][1]['defaultNamingContext'][0]

        except:
            results = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_baseDN: leave")
        return results

    def get_config(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_config: enter")
        isopen = self._isopen
        self.open()

        results = self.get_rootDSE()
        try:
            results = results[0][1]['configurationNamingContext'][0]

        except:
            results = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_config: leave")
        return results

    def get_netbios_name(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_netbios_name: enter")
        isopen = self._isopen
        self.open()

        basedn = self.get_baseDN()
        config = self.get_config()
        filter = "(&(objectcategory=crossref)(nCName=%s))" % basedn

        netbios_name = None
        results = self._search(config, ldap.SCOPE_SUBTREE, filter)
        try:
            netbios_name = results[0][1]['nETBIOSName'][0]

        except:
            netbios_name = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_netbios_name: leave")
        return netbios_name

    def get_partitions(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_partition: enter")
        isopen = self._isopen
        self.open()

        config = self.get_config()
        basedn = "CN=Partitions,%s" % config

        filter = None
        keys = ['netbiosname', 'name', 'cn', 'dn', 'distinguishedname', 'ncname'] 
        for k in keys:
            if kwargs.has_key(k):
                filter = "(%s=%s)" % (k, kwargs[k])
                break

        if filter is None:
            filter = "(cn=*)"

        partitions = []
        results = self._search(basedn, ldap.SCOPE_SUBTREE, filter)
        if results:
            for r in results:
                if r[0]:
                    partitions.append(r) 
                    
        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_partition: leave")
        return partitions

    def get_root_domain(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_root_domain: enter")
        isopen = self._isopen
        self.open() 

        rootDSE = self.get_rootDSE()
        rdnc = rootDSE[0][1]['rootDomainNamingContext'][0]

        domain = None
        results = self.get_partitions(ncname=rdnc)
        try:
            domain = results[0][1]['dnsRoot'][0]

        except:
            domain = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_root_domain: leave")
        return domain

    def get_domain(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain: enter")
        isopen = self._isopen
        self.open() 

        domain = None
        results = self.get_partitions(**kwargs)
        try:
            domain = results[0][1]['dnsRoot'][0]

        except:
            domain = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domain: leave")
        return domain

    def get_domains(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domains: enter")
        isopen = self._isopen
        self.open() 

        gc = None
        gc_args = { 'binddn': self.binddn, 'bindpw': self.bindpw }

        root = self.get_root_domain()
        gcs = self.get_global_catalogs(root)

        for g in gcs:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domains: trying [%s]..." % g)

            gc_args['host'] = g.target.to_text(True)
            gc_args['port'] = long(g.port)

            gc = FreeNAS_LDAP_Directory(**gc_args)
            gc.open()

            if gc._isopen:
                break

            gc.close()
            gc = None

        domains = [] 
        if gc and gc._isopen:
            results = gc._search("", ldap.SCOPE_SUBTREE, '(objectclass=domain)', ['dn'])
            if not results:
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domains: no domain objects found")
                results = []

            for r in results:
                domains.append(r[0])

            gc.close()

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domains: "
                "unable to connect to a global catalog server")

        rootDSE = self.get_rootDSE()
        basedn = rootDSE[0][1]['configurationNamingContext'][0]
        config = rootDSE[0][1]['defaultNamingContext'][0]

        result = []
        haskey = False
        for d in domains:
            filter = None
            if len(kwargs) > 0:
                haskey = True
                keys = ['netbiosname', 'name', 'cn', 'dn', 'distinguishedname', 'ncname'] 
                for k in keys:
                    if kwargs.has_key(k):
                        filter = "(&(objectcategory=crossref)(%s=%s))" % (k, kwargs[k])
                        break

            if filter is None:
                filter = "(&(objectcategory=crossref)(nCName=%s))" % d

            results = self._search(basedn, ldap.SCOPE_SUBTREE, filter)
            if results and results[0][0]:
                r = {}
                for k in results[0][1].keys():
                    r[k] = results[0][1][k][0]
                result.append(r)

            if haskey:
                break

        if not isopen:
            self.close() 

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_domains: leave")
        return result

    def get_userDN(self, user):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_userDN: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_userDN: user = %s" % user)
        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        isopen = self._isopen
        self.open()

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))(sAMAccountName=%s))' % user
        attributes = ['distinguishedName']
        results = self._search(self.basedn, scope, filter, attributes)
        try:
            results = results[0][1][attributes[0]][0]

        except:
            results = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_userDN: leave")
        return results

    def get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_user: user = %s" % user)
        isopen = self._isopen
        self.open()

        ad_user = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))(sAMAccountName=%s))' % user
        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_user = r
                    break

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_user: leave")
        return ad_user

    def get_users(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_users: enter")
        isopen = self._isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))(sAMAccountName=*))'
        if self.attributes and 'sAMAccountType' not in self.attributes:
            self.attributes.append('sAMAccountType')

        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['sAMAccountType'][0])
                    if not (type & 0x1):
                        users.append(r)

        if not isopen:
            self.close()

        self.ucount = len(users)
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_users: leave")
        return users

    def get_groupDN(self, group):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_groupDN: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_groupDN: group = %s" % group)
        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        isopen = self._isopen
        self.open()

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % group
        attributes = ['distinguishedName']
        results = self._search(self.basedn, scope, filter, attributes)
        try:
            results = results[0][1][attributes[0]][0]

        except:
            results = None

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_groupDN: leave")
        return results

    def get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_group: group = %s" % group)
        isopen = self._isopen
        self.open()

        ad_group = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % group
        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_group = r
                    break

        if not isopen:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_group: leave")
        return ad_group

    def get_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_groups: enter")
        isopen = self._isopen
        self.open()

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=*))'
        if self.attributes and 'groupType' not in self.attributes:
            self.attributes.append('groupType')

        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['groupType'][0])
                    if not (type & 0x1):
                        groups.append(r)

        if not isopen:
            self.close()

        self.ucount = len(groups)
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Base.get_groups: leave")
        return groups

    def get_user_count(self):
        count = 0

        if self.ucount > 0:
            count = self.ucount

        else:
            pagesize = self.pagesize
            self.pagesize = 32768

            users = self.get_users()

            self.pagesize = pagesize
            count = self.ucount

        return count

    def get_group_count(self):
        count = 0

        if self.gcount > 0:
            count = self.gcount
        
        else:
            pagesize = self.pagesize
            self.pagesize = 32768

            groups = self.get_groups()

            self.pagesize = pagesize
            count = self.gcount 

        return count


class FreeNAS_ActiveDirectory(FreeNAS_ActiveDirectory_Base):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory.__init__: enter")

        super(FreeNAS_ActiveDirectory, self).__init__(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory.__init__: leave")



class FreeNAS_LDAP_Users(FreeNAS_LDAP):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__init__: enter")

        super(FreeNAS_LDAP_Users, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache()

        self.__users = []
        self.__get_users()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__init__: leave")

    def __loaded(self, index, write=False):
        ret = False

        ucachedir = self.__ucache.cachedir
        ducachedir = self.__ducache.cachedir

        paths = {}
        paths['u'] = os.path.join(ucachedir, ".ul")
        paths['du'] = os.path.join(ducachedir, ".dul")
   
        file = None
        try:
            file = paths[index]

        except:
            pass

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True 

            except:
                ret = False

        elif file:
            if os.access(file, os.F_OK):
                ret = True

        return ret

    def __len__(self):
        return len(self.__users)

    def __iter__(self):
        for user in self.__users:
            yield user

    def __get_users(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: enter")

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('u'):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: users in cache")
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: leave")
            self.__users = self.__ucache
            return

        self.attributes = ['uid']
        self.pagesize = FREENAS_LDAP_PAGESIZE

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('du'):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: LDAP users in cache")
            ldap_users = self.__ducache

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: LDAP users not in cache")
            ldap_users = self.get_users()

        for u in ldap_users:
            CN = str(u[0])
            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__ducache[CN] = u

            u = u[1]
            uid = str(u['uid'][0])
            try:
                pw = pwd.getpwnam(uid)

            except:
                continue

            self.__users.append(pw)
            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__ucache[uid] = pw

            pw = None

        if self.flags & FLAGS_CACHE_WRITE_USER:
            self.__loaded('u', True)
            self.__loaded('du', True)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: leave")


class FreeNAS_ActiveDirectory_Users(FreeNAS_ActiveDirectory):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__init__: enter")

        super(FreeNAS_ActiveDirectory_Users, self).__init__(**kwargs)

        self.__users = {}
        self.__ucache = {}
        self.__ducache = {}

        if kwargs.has_key('netbiosname') and kwargs['netbiosname']:
            self.__domains = self.get_domains(netbiosname=kwargs['netbiosname'])
        else:
            self.__domains = self.get_domains()

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            for d in self.__domains:
                n = d['nETBIOSName']
                self.__ucache[n] = FreeNAS_UserCache(dir=n)
                self.__ducache[n] = FreeNAS_Directory_UserCache(dir=n)

        self.__get_users()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__init__: leave")

    def __loaded(self, index, netbiosname, write=False):
        ret = False

        paths = {}
        ucachedir = self.__ucache[netbiosname].cachedir
        paths['u'] = os.path.join(ucachedir, ".ul")

        ducachedir = self.__ducache[netbiosname].cachedir 
        paths['du'] = os.path.join(ducachedir, ".dul")
   
        file = None
        try:
            file = paths[index]

        except:
            file = None

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True 

            except:
                ret = False

        elif file:
            if os.access(file, os.F_OK):
                ret = True

        return ret

    def __len__(self):
        length = 0 
        for d in self.__domains:
            length += len(self.__users[d['nETBIOSName']])
        return length

    def __iter__(self):
        for d in self.__domains:
            for user in self.__users[d['nETBIOSName']]:
                yield user

    def __get_users(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: enter")

        if (self.flags & FLAGS_CACHE_READ_USER):
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                n = d['nETBIOSName']
                if self.__loaded('u', n):
                    self.__users[n] = self.__ucache[n]
                    count += 1

            if count == dcount:
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: users in cache")
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: leave")
                return
        

        self._save()
        for d in self.__domains:
            n = d['nETBIOSName']
            self.__users[n] = []

            self.host = d['dnsRoot']
            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            self.close()
            self.open()

            if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('du', n):
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users in cache" % n)
                ad_users = self.__ducache[n]

            else:
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users not in cache" % n)
                ad_users = self.get_users()

            for u in ad_users:
                CN = str(u[0])

                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ducache[n][CN] = u

                u = u[1]
                sAMAccountName = str("%s%s%s" % (n, FREENAS_AD_SEPARATOR, u['sAMAccountName'][0]))

                try:
                    pw = pwd.getpwnam(sAMAccountName)

                except Exception, e:
                    continue

                self.__users[n].append(pw)
                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ucache[n][sAMAccountName] = pw 

                pw = None

            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__loaded('u', n, True)
                self.__loaded('du', n, True)
          
        self._restore()
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: leave")


class FreeNAS_Directory_Users(object):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_Users.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_Users(**kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_Users(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_Users.__new__: leave")
        return obj


class FreeNAS_LDAP_Groups(FreeNAS_LDAP):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__init__: enter")

        super(FreeNAS_LDAP_Groups, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache()

        self.__groups = []
        self.__get_groups()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__init__: leave")

    def __loaded(self, index, write=False):
        ret = False

        gcachedir = self.__gcache.cachedir
        dgcachedir = self.__dgcache.cachedir

        paths = {}
        paths['g'] = os.path.join(gcachedir, ".gl")
        paths['dg'] = os.path.join(dgcachedir, ".dgl")
   
        file = None
        try:
            file = paths[index]

        except:
            pass

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True 

            except:
                ret = False

        elif file:
            if os.access(file, os.F_OK):
                ret = True

        return ret

    def __len__(self):
        return len(self.__groups)

    def __iter__(self):
        for group in self.__groups:
            yield group

    def __get_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: enter")

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('g'):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: groups in cache")
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: leave")
            self.__groups = self.__gcache
            return

        self.attributes = ['cn']

        ldap_groups = None
        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('dg'):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: LDAP groups in cache")
            ldap_groups = self.__dgcache

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: LDAP groups not in cache")
            ldap_groups = self.get_groups()
        
        groups = []
        for g in ldap_groups:
            CN = str(g[0])
            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__dgcache[CN] = g

            g = g[1]
            cn = str(g['cn'][0])
            try:
                gr = grp.getgrnam(cn)

            except:
                continue

            self.__groups.append(gr)

            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__gcache[cn] = gr

            gr = None

        if self.flags & FLAGS_CACHE_WRITE_GROUP:
            self.__loaded('g', True)
            self.__loaded('dg', True)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: leave")


class FreeNAS_ActiveDirectory_Groups(FreeNAS_ActiveDirectory):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__init__: enter")

        super(FreeNAS_ActiveDirectory_Groups, self).__init__(**kwargs)

        self.__groups = {}
        self.__gcache = {}
        self.__dgcache = {}

        if kwargs.has_key('netbiosname') and kwargs['netbiosname']:
            self.__domains = self.get_domains(netbiosname=kwargs['netbiosname'])
        else:
            self.__domains = self.get_domains()

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            for d in self.__domains:
                n = d['nETBIOSName']
                self.__gcache[n] = FreeNAS_GroupCache(dir=n)
                self.__dgcache[n] = FreeNAS_Directory_GroupCache(dir=n)

        self.__get_groups()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__init__: leave")

    def __loaded(self, index, netbiosname=None, write=False):
        ret = False

        paths = {}
        gcachedir = self.__gcache[netbiosname].cachedir
        paths['g'] = os.path.join(gcachedir, ".gl")

        dgcachedir = self.__dgcache[netbiosname].cachedir 
        paths['dg'] = os.path.join(dgcachedir, ".dgl")
   
        file = None
        try:
            file = paths[index]

        except:
            file = None

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True 

            except:
                ret = False

        elif file:
            if os.access(file, os.F_OK):
                ret = True

        return ret

    def __len__(self):
        length = 0
        for d in self.__domains:
            length += len(self.__groups[d['nETBIOSName']])
        return length

    def __iter__(self):
        for d in self.__domains:
            for group in self.__groups[d['nETBIOSName']]:
                yield group

    def __get_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: enter")

        if (self.flags & FLAGS_CACHE_READ_GROUP):
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                n = d['nETBIOSName']
                if self.__loaded('u', n):
                    self.__groups[n] = self.__gcache[n]
                    count += 1

            if count == dcount:
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: groups in cache")
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: leave")
                return

        self._save()
        for d in self.__domains:
            n = d['nETBIOSName']
            self.__groups[n] = []

            self.host = d['dnsRoot']
            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            self.close()
            self.open()

            if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('dg', n):
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups in cache" % n)
                ad_groups = self.__dgcache[n]

            else:
                syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups not in cache" % n)
                ad_groups = self.get_groups()

            for g in ad_groups:
                sAMAccountName = g[1]['sAMAccountName'][0]
                sAMAccountName = str("%s%s%s" % (n, FREENAS_AD_SEPARATOR, sAMAccountName))

                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__dgcache[n][sAMAccountName.upper()] = g

                try:
                    gr = grp.getgrnam(sAMAccountName)

                except:
                    continue

                self.__groups[n].append(gr)
                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__gcache[n][sAMAccountName.upper()] = gr

                gr = None

            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__loaded('g', n, True)
                self.__loaded('dg', n, True)

        self._restore()
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: leave")


class FreeNAS_Directory_Groups(object):
    def __new__(cls, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_Groups.__new__: enter")

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_Groups(**kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_Groups(**kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Directory_Groups.__new__: leave")
        return obj


class FreeNAS_LDAP_Group(FreeNAS_LDAP):
    def __init__(self, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: group = %s" % group)
        group = str(group)

        super(FreeNAS_LDAP_Group, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache()
            if self.groupsuffix and self.basedn:
                self.__key = str("cn=%s,%s,%s" % (group, self.groupsuffix, self.basedn))

        self._gr = None
        if group:
            self.__get_group(group)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: leave")

    def __get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: group = %s" % group)

        gr = cn = None
        self.attributes = ['cn']

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__gcache.has_key(group):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: group in cache")
            return self.__gcache[group]

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__dgcache.has_key(self.__key):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: LDAP group in cache")
            ldap_group = self.__dgcache[self.__key]

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: LDAP group not in cache")
            ldap_group = self.get_group(group)

        if ldap_group:
            try:
                gr = grp.getgrnam(ldap_group[1]['cn'][0])

            except:
                gr = None

        else:
            if type(group) in (types.IntType, types.LongType) or group.isdigit():
                try:
                    gr = grp.getgrgid(group)

                except:
                    gr = None

            else:
                try:
                    gr = grp.getgrnam(group)

                except:
                    gr = None

        if (self.flags & FLAGS_CACHE_WRITE_GROUP) and gr:
            self.__gcache[group] = gr
            self.__dgcache[self.__key] = ldap_group

        self._gr = gr
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: leave")


class FreeNAS_ActiveDirectory_Group(FreeNAS_ActiveDirectory):
    def __new__(cls, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__new__: group = %s" % group)

        obj = None
        group = str(group)
        if group is not None:
            parts = group.split(FREENAS_AD_SEPARATOR)
            if len(parts) > 1 and parts[1]:
                obj = super(FreeNAS_ActiveDirectory_Group, cls).__new__(cls, **kwargs)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__new__: leave")
        return obj

    def __init__(self, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: group = %s" % group)

        parts = group.split(FREENAS_AD_SEPARATOR)
        netbiosname = parts[0]
        group = parts[1]

        self._gr = None

        kwargs['netbiosname'] = netbiosname
        super(FreeNAS_ActiveDirectory_Group, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache(dir=netbiosname)
            self.__key = str(("%s%s%s" % (netbiosname, FREENAS_AD_SEPARATOR, group)).upper())

        self.__get_group(group, netbiosname)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: leave")

    def __get_group(self, group, netbiosname):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: group = %s" % group)
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: netbiosname = %s" % netbiosname)

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__gcache.has_key(group):
             syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_group: group in cache")
             return self.__gcache[group] 

        g = gr = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__dgcache.has_key(self.__key):
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: AD group in cache")
            ad_group = self.__dgcache[self.__key]

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: AD group not in cache")
            ad_group = self.get_group(group)

        g = "%s%s%s" % (netbiosname, FREENAS_AD_SEPARATOR,
            ad_group[1]['sAMAccountName'][0] if ad_group else group)

        try: 
            gr = grp.getgrnam(g)

        except:
            gr = None

        if (self.flags & FLAGS_CACHE_WRITE_GROUP) and gr:
            self.__gcache[group] = gr
            self.__dgcache[self.__key] = ad_group

        self._gr = gr
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: leave")


class FreeNAS_Directory_Group(object):
    def __new__(cls, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_Group.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Directory_Group.__new__: group = %s" % group)

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_Group(group, **kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_Group(group, **kwargs)

        if obj and obj._gr is None:
            obj = None

        syslog(LOG_DEBUG, "FreeNAS_Directory_Group.__new__: leave")
        return obj


class FreeNAS_LDAP_User(FreeNAS_LDAP):
    def __init__(self, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: user = %s" % user)
        user = str(user)

        super(FreeNAS_LDAP_User, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache()
            if self.usersuffix and self.basedn:
                self.__key = str("uid=%s,%s,%s" % (user, self.usersuffix, self.basedn))

        self._pw = None
        if user:
            self.__get_user(user)

        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: leave")

    def __get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: user = %s" % user)

        pw = None
        self.attributes = ['uid']

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ucache.has_key(user):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: user in cache")
            return self.__ucache[user]

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ducache.has_key(self.__key):
            syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: LDAP user in cache")
            ldap_user = self.__ducache[self.__key] 

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: LDAP user not in cache")
            ldap_user = self.get_user(user)
        
        if ldap_user:
            self.__CN = ldap_user[0]
            uid = ldap_user[1]['uid'][0]
            try:
                pw = pwd.getpwnam(uid)

            except:
                pw = None

        else:
            if type(user) in (types.IntType, types.LongType) or user.isdigit():
                try:
                    pw = pwd.getpwuid(user)

                except:
                    pw = None

            else:
                try:
                    pw = pwd.getpwnam(user)

                except:
                    pw = None

        if (self.flags & FLAGS_CACHE_WRITE_USER) and pw:
            self.__ucache[user] = pw
            self.__ducache[self.__key] = ldap_user

        self._pw = pw
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: leave")


class FreeNAS_ActiveDirectory_User(FreeNAS_ActiveDirectory):
    def __new__(cls, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__new__: user = %s" % user)

        obj = None
        user = str(user)
        if user is not None:
            parts = user.split(FREENAS_AD_SEPARATOR)
            if len(parts) > 1 and parts[1]:
                obj = super(FreeNAS_ActiveDirectory_User, cls).__new__(cls, **kwargs)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__new__: leave")
        return obj

    def __init__(self, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: user = %s" % user)

        parts = user.split(FREENAS_AD_SEPARATOR)
        netbiosname = parts[0]
        user = parts[1]

        self._pw = None

        kwargs['netbiosname'] = netbiosname
        super(FreeNAS_ActiveDirectory_User, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache(dir=netbiosname)
            self.__key = str(("%s%s%s" % (netbiosname, FREENAS_AD_SEPARATOR, user)).upper())

        self.__get_user(user, netbiosname)

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: leave")

    def __get_user(self, user, netbiosname):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: user = %s" % user)
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: netbiosname = %s" % netbiosname)

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ucache.has_key(user):
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: user in cache")
            return self.__ucache[user]

        pw = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ducache.has_key(self.__key):
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: AD user in cache")
            ad_user = self.__ducache[self.__key] 

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: AD user not in cache")
            ad_user = self.get_user(user)

        u = "%s%s%s" % (netbiosname, FREENAS_AD_SEPARATOR,
            ad_user[1]['sAMAccountName'][0] if ad_user else user) 

        try: 
            pw = pwd.getpwnam(u)

        except:
            pw = None

        if (self.flags & FLAGS_CACHE_WRITE_USER) and pw:
            self.__ucache[user] = pw
            self.__ducache[self.__key] = ad_user

        self._pw = pw
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: leave")


class FreeNAS_Directory_User(object):
    def __new__(cls, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Directory_User.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Directory_User.__new__: user = %s" % user)

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_User(user, **kwargs)

        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_User(user, **kwargs)
        
        if obj and obj._pw is None:
            obj = None

        syslog(LOG_DEBUG, "FreeNAS_Directory_User.__new__: leave")
        return obj

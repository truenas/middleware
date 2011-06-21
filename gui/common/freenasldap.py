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
from freenasUI.services.models import services, LDAP, ActiveDirectory
from freenasUI.account.models import bsdUsers, bsdGroups
from freenasUI.common.freenascache import FreeNAS_BaseCache, FREENAS_CACHEDIR
from freenasUI.common.system import get_freenas_var

import os
import grp
import pwd
import types
import ldap
import syslog
import time
import hashlib

from syslog import syslog, LOG_DEBUG


FREENAS_LDAP_NOSSL = 0
FREENAS_LDAP_USESSL = 1
FREENAS_LDAP_USETLS = 2

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

FREENAS_LDAP_CACHE_EXPIRE = get_freenas_var("FREENAS_LDAP_CACHE_EXPIRE", 60)
FREENAS_LDAP_CACHE_ENABLE = get_freenas_var("FREENAS_LDAP_CACHE_ENABLE", 1)

FREENAS_LDAP_VERSION = ldap.VERSION3
FREENAS_LDAP_REFERRALS = get_freenas_var("FREENAS_LDAP_REFERRALS", 0)
FREENAS_LDAP_CACERTFILE = get_freenas_var("CERT_FILE")

FREENAS_LDAP_PAGESIZE = get_freenas_var("FREENAS_LDAP_PAGESIZE", 8192)

ldap.protocol_version = FREENAS_LDAP_VERSION
ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)


def LDAPEnabled():
    try:
        s = services.objects.get(srv_service = 'ldap')
        return (True if s.srv_enable != 0 else False)
    except services.DoesNotExist:
        return False

def ActiveDirectoryEnabled():
    try:
        s = services.objects.get(srv_service = 'activedirectory')
        return (True if s.srv_enable != 0 else False)
    except services.DoesNotExist:
        return False


class FreeNAS_LDAP_UserCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_LDAP_USERCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_LDAP_GroupCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_LDAP_GROUPCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_LDAP_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_LDAP_LOCAL_USERCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_LDAP_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_LDAP_LOCAL_GROUPCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_ActiveDirectory_UserCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_AD_USERCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_ActiveDirectory_GroupCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_AD_GROUPCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_ActiveDirectory_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_AD_LOCAL_USERCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_ActiveDirectory_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_AD_LOCAL_GROUPCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_LDAP_QueryCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_LDAP_QUERYCACHE):
        FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_Directory_UserCache(FreeNAS_BaseCache):
    def __init__(self):
        if LDAPEnabled():
            self.__class__ = FreeNAS_LDAP_UserCache
            FreeNAS_LDAP_UserCache.__init__(self)
 
        elif ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_ActiveDirectory_UserCache
            FreeNAS_ActiveDirectory_UserCache.__init__(self)


class FreeNAS_Directory_GroupCache(FreeNAS_BaseCache):
    def __init__(self):
        if LDAPEnabled():
            self.__class__ = FreeNAS_LDAP_GroupCache
            FreeNAS_LDAP_GroupCache.__init__(self)

        elif ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_ActiveDirectory_GroupCache
            FreeNAS_ActiveDirectory_GroupCache.__init__(self)


class FreeNAS_Directory_LocalUserCache(FreeNAS_BaseCache):
    def __init__(self):
        if LDAPEnabled():
            self.__class__ = FreeNAS_LDAP_LocalUserCache
            FreeNAS_LDAP_LocalUserCache.__init__(self)
 
        elif ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_ActiveDirectory_LocalUserCache
            FreeNAS_ActiveDirectory_LocalUserCache.__init__(self)


class FreeNAS_Directory_LocalGroupCache(FreeNAS_BaseCache):
    def __init__(self):
        if LDAPEnabled():
            self.__class__ = FreeNAS_LDAP_LocalGroupCache
            FreeNAS_LDAP_LocalGroupCache.__init__(self)

        elif ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_ActiveDirectory_LocalGroupCache
            FreeNAS_ActiveDirectory_LocalGroupCache.__init__(self)


class FreeNAS_UserCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_USERCACHE):
        if LDAPEnabled() or ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_Directory_LocalUserCache 
            FreeNAS_Directory_LocalUserCache.__init__(self)

        else:
            FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_GroupCache(FreeNAS_BaseCache):
    def __init__(self, cachedir = FREENAS_GROUPCACHE):
        if LDAPEnabled() or ActiveDirectoryEnabled():
            self.__class__ = FreeNAS_Directory_LocalGroupCache 
            FreeNAS_Directory_LocalGroupCache.__init__(self)

        else:
            FreeNAS_BaseCache.__init__(self, cachedir)


class FreeNAS_LDAP(object):
    def __init__(self, host = None, binddn = None, bindpw = None,
        basedn = None, ssl = FREENAS_LDAP_NOSSL, scope = None,
        filter = None, attributes = None, pagesize = 0):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__init__: enter")

        self.host = host
        self.binddn = binddn
        self.bindpw = bindpw
        self.basedn = basedn
        self.ssl = self.__setssl(ssl)
        self.scope = scope
        self.filter = filter
        self.attributes = attributes
        self.pagesize = pagesize
        self.__handle = None
        self.__isopen = 0
        self.__cache = FreeNAS_LDAP_QueryCache()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.__init__: "
            "host = %s, binddn = %s, bindpw = %s, basedn = %s, ssl = %d" %
            (self.host, self.binddn, self.bindpw, self.basedn, self.ssl))
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__init__: leave")

    def isOpen(self):
        return self.__isopen == 1

    def __setssl(self, ssl):
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

    def __geturi(self):
        if self.host is None:
            return None

        uri = None
        if self.ssl in (FREENAS_LDAP_NOSSL, FREENAS_LDAP_USETLS):
            uri = "ldap://%s" % self.host
        elif self.ssl == FREENAS_LDAP_USESSL:
            uri = "ldaps://%s" % self.host
        else:
            uri = "ldap://%s" % self.host

        return uri

    def open(self):
        if self.__isopen == 1:
            return

        if self.host:
            self.__handle = ldap.initialize(self.__geturi())
            syslog(LOG_DEBUG, "FreeNAS_LDAP.open: initialized")
       
        if self.__handle:
            res = None
            self.__handle.protocol_version = FREENAS_LDAP_VERSION
            self.__handle.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

            if self.ssl in (FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                self.__handle.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                self.__handle.set_option(ldap.OPT_X_TLS_CACERTFILE, FREENAS_LDAP_CACERTFILE)
                self.__handle.set_option(ldap.OPT_X_TLS_NEWCTX, ldap.OPT_X_TLS_DEMAND)

            if self.ssl == FREENAS_LDAP_USETLS:
                try:
                    self.__handle.start_tls_s() 
                    syslog(LOG_DEBUG, "FreeNAS_LDAP.open: started TLS")

                except:
                    pass

            if self.binddn and self.bindpw:
                try:
                    res = self.__handle.simple_bind_s(self.binddn, self.bindpw)
                    syslog(LOG_DEBUG, "FreeNAS_LDAP.open: binded")

                except:
                    res = None
            else:
                try:
                    res = self.__handle.simple_bind_s()
                    syslog(LOG_DEBUG, "FreeNAS_LDAP.open: binded")

                except:
                    res = None

            if res:
                self.__isopen = 1
                syslog(LOG_DEBUG, "FreeNAS_LDAP.open: connection open")

    def unbind(self):
        if self.__handle:
            self.__handle.unbind()
            syslog(LOG_DEBUG, "FreeNAS_LDAP.unbind: unbind")

    def close(self):
        if self.__isopen == 1:
            self.unbind()
            self.__handle = None
            self.__isopen = 0
            syslog(LOG_DEBUG, "FreeNAS_LDAP.close: connection closed")

    def __search(self, basedn, scope=ldap.SCOPE_SUBTREE, filter=None, attributes=None,
        attrsonly=0, serverctrls=None, clientctrls=None, timeout=-1, sizelimit=0):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: basedn = '%s', filter = '%s'" % (basedn, filter))
        if self.__isopen == 0:
            return None

        m = hashlib.sha256()
        m.update(filter)
        key = m.hexdigest()
        m = None

        if filter is not None and self.__cache.has_key(key):
            syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: query in cache")
            return self.__cache[key]

        result = []
        results = []
        paged = ldap.controls.SimplePagedResultsControl(
            ldap.LDAP_CONTROL_PAGE_OID,
            True,
            (self.pagesize, '')
        )

        if self.pagesize > 0:
            syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: pagesize = %d" % self.pagesize)

            page = 0
            while True:
                syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: getting page %d" % page)

                if self.pagesize > 0:
                    serverctrls = [paged]
                else:
                    serverctrls = None

                id = self.__handle.search_ext(
                   basedn,
                   scope,
                   filterstr=filter,
                   attrlist=attributes,
                   attrsonly=attrsonly,
                   serverctrls=serverctrls
                )

                (rtype, rdata, rmsgid, serverctrls) = self.__handle.result3(id)
                for entry in rdata:
                    result.append(entry)

                cookie = None
                for sc in serverctrls:
                    if sc.controlType == ldap.LDAP_CONTROL_PAGE_OID:
                        est, cookie = sc.controlValue
                        if cookie:
                            paged.controlValue = (self.pagesize, cookie)

                        break

                if not cookie:
                    break

                page += 1 
        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: pagesize = 0")

            id = self.__handle.search_ext(
                basedn,
                scope,
                filterstr=filter,
                attrlist=attributes,
                attrsonly=attrsonly,
                serverctrls=serverctrls
            )

            type = ldap.RES_SEARCH_ENTRY
            while type != ldap.RES_SEARCH_RESULT:
                try:
                    type, data = self.__handle.result(id, 0)

                except:
                    break

                results.append(data)

            for i in range(len(results)):
                for entry in results[i]:
                    result.append(entry)

            self.__cache[key] = result

        syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: %d results" % len(result))
        syslog(LOG_DEBUG, "FreeNAS_LDAP.__search: leave")
        return result

    def search(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.search: enter")
        isopen = self.__isopen
        self.open()

        results = self.__search(self.basedn, self.scope, self.filter, self.attributes)
        if isopen == 0:
            self.close()

        return results

    def get_ldap_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_user: user = %s" % user)
        isopen = self.__isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        if type(user) in (types.IntType, types.LongType):
            filter = '(&(|(objectclass=person)(objectclass=account))(uidnumber=%d))' % user
        elif user.isdigit():
            filter = '(&(|(objectclass=person)(objectclass=account))(uidnumber=%s))' % user
        else:
            filter = '(&(|(objectclass=person)(objectclass=account))(|(uid=%s)(cn=%s)))' % (user, user)

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ldap_user = r
                    break

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_user: leave")
        return ldap_user

    def get_ldap_users(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_users: enter")
        isopen = self.__isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=person)(objectclass=account))(uid=*))'

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    users.append(r)

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_users: leave")
        return users

    def get_ldap_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_group: group = %s" % group)
        isopen = self.__isopen
        self.open()

        ldap_group = None
        scope = ldap.SCOPE_SUBTREE

        if type(group) in (types.IntType, types.LongType):
            filter = '(&(objectclass=posixgroup)(gidnumber=%d))' % group
        elif group.isdigit():
            filter = '(&(objectclass=posixgroup)(gidnumber=%s))' % group
        else:
            filter = '(&(objectclass=posixgroup)(cn=%s))' % group

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ldap_group = r
                    break

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_group: leave")
        return ldap_group

    def get_ldap_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_groups: enter")
        isopen = self.__isopen
        self.open()

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=posixgroup)(gidnumber=*))'

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    groups.append(r)

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_ldap_groups: leave")
        return groups

    def get_active_directory_rootDSE(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_rootDSE: enter")
        isopen = self.__isopen
        self.open()

        results = self.__search("", ldap.SCOPE_BASE, "(objectclass=*)")
        if isopen == 0:
            self.close()

        return results

    def get_active_directory_baseDN(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_baseDN: enter")
        results = self.get_active_directory_rootDSE()
        try:
            results = results[0][1]['defaultNamingContext'][0]
        except:
            results = None

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_baseDN: leave")
        return results

    def get_active_directory_userDN(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_userDN: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_userDN: user = %s" % user)
        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        isopen = self.__isopen
        self.open()

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=user)(sAMAccountName=%s))' % user
        attributes = ['distinguishedName']
        results = self.__search(self.basedn, scope, filter, attributes)
        try:
            results = results[0][1][attributes[0]][0]
        except:
            results = None

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_userDN: leave")
        return results

    def get_active_directory_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_user: user = %s" % user)
        isopen = self.__isopen
        self.open()

        ad_user = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=user)(|(sAMAccountName=%s)(cn=%s)))' % (user, user)
        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_user = r
                    break

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_user: leave")
        return ad_user

    def get_active_directory_users(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_users: enter")
        isopen = self.__isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=user)(sAMAccountName=*))'
        if self.attributes and 'sAMAccountType' not in self.attributes:
            self.attributes.append('sAMAccountType')

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['sAMAccountType'][0])
                    if not (type & 0x1):
                        users.append(r)

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_users: leave")
        return users

    def get_active_directory_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_group: group = %s" % group)
        isopen = self.__isopen
        self.open()

        ad_group = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % group
        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_group = r
                    break

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_group: leave")
        return ad_group

    def get_active_directory_groups(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_groups: enter")
        isopen = self.__isopen
        self.open()

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=*))'
        if self.attributes and 'groupType' not in self.attributes:
            self.attributes.append('groupType')

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['groupType'][0])
                    if not (type & 0x1):
                        groups.append(r)

        if isopen == 0:
            self.close()

        syslog(LOG_DEBUG, "FreeNAS_LDAP.get_active_directory_groups: leave")
        return groups


class FreeNAS_LDAP_Users:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__init__: enter")

        self.__users = []
        self.__groups = {}
        self.__index = 0
        self.__ucache = FreeNAS_UserCache()
        self.__gcache = FreeNAS_GroupCache()
        self.__ducache = FreeNAS_Directory_UserCache()
        self.__dgcache = FreeNAS_Directory_GroupCache()
        self.__get_users()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__init__: leave")

    def __len__(self):
        return len(self.__users)

    def __iter__(self):
        for user in self.__users:
            yield user

    def __get_groups(self, l=None, f=None):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: enter")
        if l is None:
            l = LDAP.objects.all().order_by('-id')[0]

        if not self.__gcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: groups in cache")
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: leave")
            self.__groups = self.__gcache
            return

        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['cn']

        write_cache = False
        if not self.__dgcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: LDAP groups in cache")
            ldap_groups = self.__lgcache

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: LDAP groups not in cache")
            ldap_groups = f.get_ldap_groups()
            write_cache = True

        self.__groups = {}
        for g in ldap_groups:
            CN = g[0]
            if write_cache:
                self.__dgcache[CN] = g

            g = g[1]
            cn = g['cn'][0]
            try:
                gr = grp.getgrnam(cn)

            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)

            self.__groups[gr.gr_name] = bg
            if write_cache:
                self.__gcache[cn] = bg

            gr = None

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_groups: leave")

    def __get_users(self, l=None, f=None):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: enter")
        if l is None:
            l = LDAP.objects.all().order_by('-id')[0]

        if not self.__ucache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: users in cache")
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: leave")
            self.__users = self.__ucache
            return

        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        self.__get_groups(l, f)

        f.basedn = l.ldap_usersuffix + "," + l.ldap_basedn;
        f.attributes = ['uid']

        write_cache = False 
        if not self.__ducache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: LDAP users in cache")
            ldap_users = self.__ducache

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: LDAP users not in cache")
            ldap_users = f.get_ldap_users()
            write_cache = True

        f = l = None
        self.__users = [] 
        for u in ldap_users:
            CN = u[0]
            if write_cache:
                self.__ducache[CN] = u

            u = u[1]
            uid = u['uid'][0]
            try:
                pw = pwd.getpwnam(uid)

            except:
                continue

            bu = bsdUsers()
            bu.bsdusr_username = unicode(pw.pw_name)
            bu.bsdusr_uid = pw.pw_uid
            try:
                gr = grp.getgrgid(pw.pw_gid)
                bu.bsdusr_group = self.__groups[gr.gr_name]

            except:
                pass
            bu.bsdusr_full_name = unicode(pw.pw_gecos)
            bu.bsdusr_home = unicode(pw.pw_dir)
            bu.bsdusr_shell = unicode(pw.pw_shell)
            pw = None

            self.__users.append(bu)
            if write_cache:
                self.__ucache[uid] = bu

            pw = None

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Users.__get_users: leave")


class FreeNAS_ActiveDirectory_Users:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__init__: enter")

        self.__users = []
        self.__groups = {}
        self.__index = 0
        self.__ucache = FreeNAS_UserCache()
        self.__gcache = FreeNAS_GroupCache()
        self.__ducache = FreeNAS_Directory_UserCache()
        self.__dgcache = FreeNAS_Directory_GroupCache()
        self.__get_users()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__init__: leave")

    def __len__(self):
        return len(self.__users)

    def __iter__(self):
        for user in self.__users:
            yield user

    def __get_groups(self, ad=None, f=None):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: enter")
        if ad is None:
            ad = ActiveDirectory.objects.all().order_by('-id')[0]

        if not self.__gcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: groups in cache")
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: leave")
            self.__groups = self.__gcache
            return

        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)

        f.host = ad.ad_dcname
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']
        f.pagesize = FREENAS_LDAP_PAGESIZE

        write_cache = False
        if not self.__dgcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: AD groups in cache")
            ad_groups = self.__dgcache

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: AD groups not in cache")
            ad_groups = f.get_active_directory_groups()
            write_cache = True
 
        self.__groups = {}
        for g in ad_groups:
            CN = g[0]
            if write_cache:
                self.__dgcache[CN] = g
         
            g = g[1]
            sAMAccountName = g['sAMAccountName'][0]
            try:
                gr = grp.getgrnam(sAMAccountName)

            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)

            self.__groups[gr.gr_name] = bg
            if write_cache:
                self.__gcache[sAMAccountName] = bg

            gr = None

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_groups: leave")

    def __get_users(self, ad=None, f=None):  
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: enter")
        if ad is None:
            ad = ActiveDirectory.objects.all().order_by('-id')[0]

        if not self.__ucache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: users in cache")
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: leave")
            self.__users = self.__ucache
            return
       
        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)

        self.__get_groups(ad, f)

        f.host = ad.ad_dcname
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']
        f.pagesize = FREENAS_LDAP_PAGESIZE

        write_cache = False
        if not self.__ducache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: AD users in cache")
            ad_users = self.__ducache

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: AD users not in cache")
            ad_users = f.get_active_directory_users()
            write_cache = True

        self.__users = []
        for u in ad_users:
            CN =  u[0]
            if write_cache:
                self.__ducache[CN] = u

            u = u[1]
            sAMAccountName = u['sAMAccountName'][0]
            try:
                pw = pwd.getpwnam(sAMAccountName)

            except Exception, e:
                continue

            bu = bsdUsers()
            bu.bsdusr_username = unicode(pw.pw_name)
            bu.bsdusr_uid = pw.pw_uid
            try:
                gr = grp.getgrgid(pw.pw_gid)
                bu.bsdusr_group = self.__groups[gr.gr_name]

            except:
                pass
            bu.bsdusr_full_name = unicode(pw.pw_gecos)
            bu.bsdusr_home = unicode(pw.pw_dir)
            bu.bsdusr_shell = unicode(pw.pw_shell)
            pw = None

            self.__users.append(bu)
            if write_cache:
                self.__ucache[sAMAccountName] = bu
          
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Users.__get_users: leave")


class FreeNAS_Users:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_Users.__init__: enter")
        self.__users = []

        self.__bsd_users = bsdUsers.objects.all()
        if LDAPEnabled():
            self.__users = FreeNAS_LDAP_Users()

        elif ActiveDirectoryEnabled():
            self.__users = FreeNAS_ActiveDirectory_Users()

        syslog(LOG_DEBUG, "FreeNAS_Users.__init__: leave")

    def __len__(self):
        return len(self.__bsd_users) + len(self.__users)

    def __iter__(self):
        for user in self.__bsd_users:
            yield user
        for user in self.__users:
            yield user


class FreeNAS_LDAP_Groups:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__init__: enter")

        self.__groups = []
        self.__index = 0
        self.__gcache = FreeNAS_GroupCache()
        self.__dgcache = FreeNAS_Directory_GroupCache()
        self.__get_groups()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__init__: leave")

    def __len__(self):
        return len(self.__groups)

    def __iter__(self):
        for group in self.__groups:
            yield group

    def __get_groups(self, l=None, f=None):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: enter")
        if l is None:
            l = LDAP.objects.all().order_by('-id')[0]

        if not self.__gcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: groups in cache")
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: leave")
            self.__groups = self.__gcache
            return

        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['cn']

        write_cache = False
        if not self.__dgcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: LDAP groups in cache")
            ldap_groups = self.__dgcache

        else:
            syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: LDAP groups not in cache")
            ldap_groups = f.get_ldap_groups()
            write_cache = True
        
        groups = []
        for g in ldap_groups:
            CN = g[0]
            if write_cache:
                self.__dgcache[CN] = g

            g = g[1]
            cn = g['cn'][0]
            try:
                gr = grp.getgrnam(cn)

            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)
            self.__groups.append(bg)
            if write_cache:
                self.__gcache[cn] = bg

            gr = None

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Groups.__get_groups: leave")


class FreeNAS_ActiveDirectory_Groups:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__init__: enter")

        self.__groups = []
        self.__index = 0
        self.__gcache = FreeNAS_GroupCache()
        self.__dgcache = FreeNAS_Directory_GroupCache()
        self.__get_groups()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__init__: leave")

    def __len__(self):
        return len(self.__groups)

    def __iter__(self):
        for group in self.__groups:
            yield group

    def __get_groups(self, ad=None, f=None):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: enter")
        if ad is None:
            ad = ActiveDirectory.objects.all().order_by('-id')[0]

        if not self.__gcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: groups in cache")
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: leave")
            self.__groups = self.__gcache
            return

        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)

        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']

        write_cache = False
        if not self.__dgcache.empty():
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: AD groups in cache")
            ad_groups = self.__dgcache

        else:
            syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: AD groups not in cache")
            ad_groups = f.get_active_directory_groups()
            write_cache = True
 
        self.__groups = []
        for g in ad_groups:
            g = g[1]
            sAMAccountName = g['sAMAccountName'][0]
            if write_cache:
                self.__dgcache[sAMAccountName] = g

            try:
                gr = grp.getgrnam(sAMAccountName)

            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)
            self.__groups.append(bg)
            if write_cache:
                self.__gcache[sAMAccountName] = bg

            gr = None

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Groups.__get_groups: leave")


class FreeNAS_Groups:
    def __init__(self):
        syslog(LOG_DEBUG, "FreeNAS_Groups.__init__: enter")
        self.__groups = []

        self.__bsd_groups = bsdGroups.objects.all()
        if LDAPEnabled():
            self.__groups = FreeNAS_LDAP_Groups()

        elif ActiveDirectoryEnabled():
            self.__groups = FreeNAS_ActiveDirectory_Groups()

        syslog(LOG_DEBUG, "FreeNAS_Groups.__init__: leave")

    def __len__(self):
        return len(self.__bsd_groups) + len(self.__groups)

    def __iter__(self):
        for group in self.__bsd_groups:
            yield group
        for group in self.__groups:
            yield group


class FreeNAS_LDAP_User(bsdUsers):
    def __init__(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: user = %s" % user)

        super(FreeNAS_LDAP_User, self).__init__()

        self.__pw = None
        self.__get_user(user)
        if self.__pw:
            self.__pw_to_self()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__init__: leave")

    def __get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: user = %s" % user)

        l = LDAP.objects.all()[0]
        f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
            l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_usersuffix + "," + l.ldap_basedn;
        f.attributes = ['uid']
        
        pw = None
        ldap_user = f.get_ldap_user(user)
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
                    pw = pw.getpwuid(user)

                except:
                    pw = None

            else:
                try:
                    pw = pw.getpwnam(user)

                except:
                    pw = None

        self.__pw = pw
        syslog(LOG_DEBUG, "FreeNAS_LDAP_User.__get_user: leave")

    def __pw_to_self(self):
        if self.__pw:
            self.bsdusr_uid = self.__pw.pw_uid
            self.bsdusr_username = unicode(self.__pw.pw_name)
            self.bsdusr_group = FreeNAS_Group(self.__pw.pw_gid)
            self.bsdusr_home = unicode(self.__pw.pw_dir)
            self.bsdusr_shell = unicode(self.__pw.pw_shell)
            self.bsdusr_full_name = unicode(self.__pw.pw_gecos)


class FreeNAS_ActiveDirectory_User(bsdUsers):
    def __init__(self, user):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: user = %s" % user)

        super(FreeNAS_ActiveDirectory_User, self).__init__()

        self.__pw = None
        self.__get_user(user)
        if self.__pw:
            self.__pw_to_self()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__init__: leave")

    def __get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: user = %s" % user)

        ad = ActiveDirectory.objects.all()[0]
        f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']

        pw = None
        ad_user = f.get_active_directory_user(user)
        if ad_user:
            self.__CN = ad_user[0]
            sAMAccountName = ad_user[1]['sAMAccountName'][0]
            try: 
                pw = pwd.getpwnam(sAMAccountName)

            except:
                pw = None

        else:
            if type(user) in (types.IntType, types.LongType) or user.isdigit():
                try:
                    pw = pw.getpwuid(user)

                except:
                    pw = None

            else:
                try:
                    pw = pw.getpwnam(user)

                except:
                    pw = None

        self.__pw = pw
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_User.__get_user: leave")

    def __pw_to_self(self):
        if self.__pw:
            self.bsdusr_uid = self.__pw.pw_uid
            self.bsdusr_username = unicode(self.__pw.pw_name)
            self.bsdusr_group = FreeNAS_Group(self.__pw.pw_gid)
            self.bsdusr_home = unicode(self.__pw.pw_dir)
            self.bsdusr_shell = unicode(self.__pw.pw_shell)
            self.bsdusr_full_name = unicode(self.__pw.pw_gecos)


class FreeNAS_Local_User(bsdUsers):
    def __init__(self, user):
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: user = %s" % user)

        super(FreeNAS_Local_User, self).__init__()

        self.__pw = None
        self.__get_user(user)
        if self.__pw:
            self.__pw_to_self()

        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: leave")

    def __get_user(self, user):
        if type(user) in (types.IntType, types.LongType):
            bsdUser = bsdUsers.objects.filter(bsdusr_uid = user)

        elif user.isdigit():
            user = int(user)
            bsdUser = bsdUsers.objects.filter(bsdusr_uid = user)

        else:
            bsdUser = bsdUsers.objects.filter(bsdusr_username = user)

        if bsdUser:
            try:
                self.__pw = pwd.getpwnam(bsdUser[0].bsdusr_username)

            except:
                self.__pw = None

    def __pw_to_self(self):
        if self.__pw:
            self.bsdusr_uid = self.__pw.pw_uid
            self.bsdusr_username = unicode(self.__pw.pw_name)
            self.bsdusr_group = FreeNAS_Group(self.__pw.pw_gid)
            self.bsdusr_home = unicode(self.__pw.pw_dir)
            self.bsdusr_shell = unicode(self.__pw.pw_shell)
            self.bsdusr_full_name = unicode(self.__pw.pw_gecos)


class FreeNAS_User(object):
    def __new__(cls, user):
        syslog(LOG_DEBUG, "FreeNAS_User.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_User.__new__: user = %s" % user)

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_User(user)
        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_User(user)

        if obj is None or obj.bsdusr_uid is None:
            obj = FreeNAS_Local_User(user)

        if obj.bsdusr_uid is None:
            return None

        syslog(LOG_DEBUG, "FreeNAS_User.__new__: leave")
        return obj


class FreeNAS_LDAP_Group(bsdGroups):
    def __init__(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: group = %s" % group)

        super(FreeNAS_LDAP_Group, self).__init__()

        self.__gr = None
        self.__get_group(group)
        if self.__gr:
            self.__gr_to_self()

        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__init__: leave")

    def __get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: group = %s" % group)

        l = LDAP.objects.all()[0]
        f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
            l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['cn']
        
        gr = None
        ldap_group = f.get_ldap_group(group)
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

        self.__gr = gr
        syslog(LOG_DEBUG, "FreeNAS_LDAP_Group.__get_group: leave")

    def __gr_to_self(self):
        if self.__gr:
            self.bsdgrp_gid = self.__gr.gr_gid
            self.bsdgrp_group = unicode(self.__gr.gr_name)


class FreeNAS_ActiveDirectory_Group(bsdGroups):
    def __init__(self, group):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: group = %s" % group)

        super(FreeNAS_ActiveDirectory_Group, self).__init__()

        self.__gr = None
        self.__get_group(group)
        if self.__gr:
            self.__gr_to_self()

        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__init__: leave")

    def __get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: user = %s" % group)

        ad = ActiveDirectory.objects.all()[0]
        f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']

        gr = None
        ad_group = f.get_active_directory_group(group)
        if ad_group:
            try: 
                gr = grp.getgrnam(ad_group[1]['sAMAccountName'][0])

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

        self.__gr = gr
        syslog(LOG_DEBUG, "FreeNAS_ActiveDirectory_Group.__get_group: leave")

    def __gr_to_self(self):
        if self.__gr:
            self.bsdgrp_gid = self.__gr.gr_gid
            self.bsdgrp_group = unicode(self.__gr.gr_name)


class FreeNAS_Local_Group(bsdGroups):
    def __init__(self, group):
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: group = %s" % group)

        super(FreeNAS_Local_Group, self).__init__()

        self.__gr = None
        self.__get_group(group)
        if self.__gr:
            self.__gr_to_self()

        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: leave")

    def __get_group(self, group):
        if type(group) in (types.IntType, types.LongType):
            bsdGroup = bsdGroups.objects.filter(bsdgrp_gid = group)

        elif group.isdigit():
            group = int(group)
            bsdGroup = bsdGroups.objects.filter(bsdgrp_gid = group)

        else:
            bsdGroup = bsdGroups.objects.filter(bsdgrp_group = group)

        if bsdGroup:
            try:
                self.__gr = grp.getgrnam(bsdGroup[0].bsdgrp_group)

            except:
                self.__gr = None

    def __gr_to_self(self):
        if self.__gr:
            self.bsdgrp_gid = self.__gr.gr_gid
            self.bsdgrp_group = unicode(self.__gr.gr_name)


class FreeNAS_Group(object):
    def __new__(cls, group):
        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: group = %s" % group)

        obj = None
        if LDAPEnabled():
            obj = FreeNAS_LDAP_Group(group)
        elif ActiveDirectoryEnabled():
            obj = FreeNAS_ActiveDirectory_Group(group)

        if obj is None or obj.bsdgrp_gid is None:
            obj = FreeNAS_Local_Group(group)

        if obj.bsdgrp_gid is None:
            return None

        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: leave")
        return obj

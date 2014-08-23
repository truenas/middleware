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
#####################################################################
import asyncore
import grp
import hashlib
import ldap
import logging
import os
import pwd
import socket
import sqlite3
import time
import types

from dns import resolver
from ldap.controls import SimplePagedResultsControl

from freenasUI.common.system import (
    get_freenas_var,
    get_freenas_var_by_file,
    ldap_objects,
    activedirectory_objects,
)
from freenasUI.common.freenascache import *

log = logging.getLogger('common.freenasldap')

FREENAS_LDAP_NOSSL = " off"
FREENAS_LDAP_USESSL = "on"
FREENAS_LDAP_USETLS = "start_tls"

FREENAS_LDAP_PORT = get_freenas_var("FREENAS_LDAP_PORT", 389)
FREENAS_LDAP_SSL_PORT = get_freenas_var("FREENAS_LDAP_SSL_PORT", 636)

FREENAS_AD_SEPARATOR = get_freenas_var("FREENAS_AD_SEPARATOR", '\\')
FREENAS_AD_CONFIG_FILE = get_freenas_var("AD_CONFIG_FILE",
    "/etc/directoryservice/ActiveDirectory/config")

FREENAS_LDAP_CACHE_EXPIRE = get_freenas_var("FREENAS_LDAP_CACHE_EXPIRE", 60)
FREENAS_LDAP_CACHE_ENABLE = get_freenas_var("FREENAS_LDAP_CACHE_ENABLE", 1)

FREENAS_LDAP_VERSION = ldap.VERSION3
FREENAS_LDAP_REFERRALS = get_freenas_var("FREENAS_LDAP_REFERRALS", 0)

FREENAS_LDAP_PAGESIZE = get_freenas_var("FREENAS_LDAP_PAGESIZE", 1024)

ldap.protocol_version = FREENAS_LDAP_VERSION
ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

FLAGS_DBINIT		= 0x00010000
FLAGS_AD_ENABLED	= 0x00000001
FLAGS_LDAP_ENABLED	= 0x00000002

class FreeNAS_LDAP_Directory_Exception(Exception):
    pass
class FreeNAS_ActiveDirectory_Exception(FreeNAS_LDAP_Directory_Exception):
    pass
class FreeNAS_LDAP_Exception(FreeNAS_LDAP_Directory_Exception):
    pass

class FreeNAS_LDAP_Directory(object):
    @staticmethod
    def validate_credentials(hostname, port=389, binddn=None, bindpw=None, errors=[]):
        ret = None
        f = FreeNAS_LDAP(host=hostname, port=port,
            binddn=binddn, bindpw=bindpw)

        try:
            f.open()
            ret = True

        except Exception as e:
            for error in e:
                errors.append(error['desc'])
            ret = False

        return ret

    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Directory.__init__: enter")

        self.host = kwargs.get('host', None)

        self.port = None
        if kwargs.has_key('port') and kwargs['port'] is not None:
            self.port = long(kwargs['port'])

        self.binddn = kwargs.get('binddn', None)
        self.bindpw = kwargs.get('bindpw', None)
        self.basedn = kwargs.get('basedn', None)

        self.ssl = FREENAS_LDAP_NOSSL
        if kwargs.has_key('ssl') and kwargs['ssl'] is not None:
            self.ssl = kwargs['ssl'] 
            if self.ssl == FREENAS_LDAP_USESSL and self.port is None:
                self.port = FREENAS_LDAP_SSL_PORT
        self.certfile = kwargs.get('certfile', None)

        if self.port is None:
            self.port = FREENAS_LDAP_PORT

        self.scope = ldap.SCOPE_SUBTREE
        if kwargs.has_key('scope') and kwargs['scope'] is not None:
            self.scope = kwargs['scope']

        self.filter = kwargs.get('filter', None)
        self.attributes = kwargs.get('attributes', None)

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

        log.debug("FreeNAS_LDAP_Directory.__init__: "
            "host = %s, port = %ld, binddn = %s, basedn = %s, ssl = %s",
            self.host, self.port, self.binddn, self.basedn, self.ssl)
        log.debug("FreeNAS_LDAP_Directory.__init__: leave")

    def _save(self):
        _s = {}
        _s.update(self.__dict__)
        self._settings.append(_s)

    def _restore(self):
        if self._settings:
            _s = self._settings.pop()
            self.__dict__.update(_s)

    def _logex(self, ex):
        log.debug("FreeNAS_LDAP_Directory[ERROR]: An LDAP Exception occured")
        for e in ex:
            if e.has_key('info'):
                log.debug("FreeNAS_LDAP_Directory[ERROR]: info: '%s'",
                    e['info'])
            if e.has_key('desc'):
                log.debug("FreeNAS_LDAP_Directory[ERROR]: desc: '%s'",
                    e['desc'])

    def isOpen(self):
        return self._isopen

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
        log.debug("FreeNAS_LDAP_Directory.open: enter")

        if self._isopen:
            return True

        if self.host:
            uri = self._geturi()
            log.debug("FreeNAS_LDAP_Directory.open: uri = %s", uri)

            self._handle = ldap.initialize(self._geturi())
            log.debug("FreeNAS_LDAP_Directory.open: initialized")

        if self._handle:
            res = None
            self._handle.protocol_version = FREENAS_LDAP_VERSION
            self._handle.set_option(ldap.OPT_REFERRALS,
                FREENAS_LDAP_REFERRALS)
            self._handle.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)

            if self.ssl in (FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                self._handle.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                self._handle.set_option(ldap.OPT_X_TLS_CACERTFILE,
                    self.certfile)
                self._handle.set_option(ldap.OPT_X_TLS_REQUIRE_CERT,
                    ldap.OPT_X_TLS_DEMAND)
                self._handle.set_option(ldap.OPT_X_TLS_NEWCTX,
                    ldap.OPT_X_TLS_DEMAND)

            if self.ssl == FREENAS_LDAP_USETLS:
                try:
                    self._handle.start_tls_s()
                    log.debug("FreeNAS_LDAP_Directory.open: started TLS")

                except ldap.LDAPError, e:
                    print 'fuck me running: ', e
                    self._logex(e)
                    raise e

            if self.binddn and self.bindpw:
                try:
                    log.debug("FreeNAS_LDAP_Directory.open: "
                        "trying to bind to %s:%d", self.host, self.port)
                    res = self._handle.simple_bind_s(self.binddn, self.bindpw)
                    log.debug("FreeNAS_LDAP_Directory.open: binded")

                except ldap.LDAPError as e:
                    log.debug("FreeNAS_LDAP_Directory.open: "
                        "coud not bind to %s:%d (%s)",
                        self.host, self.port, e)
                    self._logex(e)
                    res = None
                    raise e
            else:
                try:
                    log.debug("FreeNAS_LDAP_Directory.open: "
                        "(anonymous bind) trying to bind to %s:%d",
                        self.host, self.port)
                    res = self._handle.simple_bind_s()
                    log.debug("FreeNAS_LDAP_Directory.open: binded")

                except ldap.LDAPError as e:
                    log.debug("FreeNAS_LDAP_Directory.open: "
                        "coud not bind to %s:%d", self.host, self.port)

                    self._logex(e)
                    res = None
                    raise e

            if res:
                self._isopen = True
                log.debug("FreeNAS_LDAP_Directory.open: connection open")

        log.debug("FreeNAS_LDAP_Directory.open: leave")
        return (self._isopen == True)

    def unbind(self):
        if self._handle:
            self._handle.unbind()
            log.debug("FreeNAS_LDAP_Directory.unbind: unbind")

    def close(self):
        if self._isopen:
            self.unbind()
            self._handle = None
            self._isopen = False
            log.debug("FreeNAS_LDAP_Directory.close: connection closed")

    def _search(self, basedn="", scope=ldap.SCOPE_SUBTREE, filter=None,
        attributes=None, attrsonly=0, serverctrls=None, clientctrls=None,
        timeout=-1, sizelimit=0):
        log.debug("FreeNAS_LDAP_Directory._search: enter")
        log.debug("FreeNAS_LDAP_Directory._search: basedn = '%s', " \
            "filter = '%s'", basedn, filter)
        if not self._isopen:
            return None

        #
        # XXX
        # For some reason passing attributes causes paged search results
        # to hang/fail after a a certain numbe of pages. I can't figure
        # out why. This is a workaround.
        # XXX
        #
        attributes = None

        if not filter: 
            filter = ''

        m = hashlib.sha256()
        m.update(repr(filter) + self.host + str(self.port) +
            (basedn if basedn else ''))
        key = m.hexdigest()
        m = None

        if filter is not None and self._cache.has_key(key):
            log.debug("FreeNAS_LDAP_Directory._search: query in cache")
            return self._cache[key]

        result = []
        results = []
        paged = SimplePagedResultsControl(
            True,
            size=self.pagesize,
            cookie=''
        )

        paged_ctrls = {
            SimplePagedResultsControl.controlType: SimplePagedResultsControl,
        }

        if self.pagesize > 0:
            log.debug("FreeNAS_LDAP_Directory._search: pagesize = %d",
                self.pagesize)

            page = 0
            while True:
                log.debug("FreeNAS_LDAP_Directory._search: getting page %d",
                    page)
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

                result.extend(rdata)

                paged.size = 0
                paged.cookie = cookie = None
                for sc in serverctrls:
                    if sc.controlType == \
                        SimplePagedResultsControl.controlType:
                        cookie = sc.cookie
                        if cookie:
                            paged.cookie = cookie
                            paged.size = self.pagesize

                        break

                if not cookie:
                    break

                page += 1
        else:
            log.debug("FreeNAS_LDAP_Directory._search: pagesize = 0")

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

                except ldap.LDAPError as e:
                    self._logex(e)
                    break

                results.append(data)

            for i in range(len(results)):
                for entry in results[i]:
                    result.append(entry)

            self._cache[key] = result

        log.debug("FreeNAS_LDAP_Directory._search: %d results", len(result))
        log.debug("FreeNAS_LDAP_Directory._search: leave")
        return result

    def search(self):
        log.debug("FreeNAS_LDAP_Directory.search: enter")
        isopen = self._isopen
        self.open()

        results = self._search(self.basedn, self.scope,
            self.filter, self.attributes)
        if not isopen:
            self.close()

        return results


class FreeNAS_LDAP_Base(FreeNAS_LDAP_Directory):

    def __keys(self):
        return [
            'host',
            'port',
            'anonbind',
            'binddn',
            'bindpw',
            'basedn',
            'ssl',
            'usersuffix',
            'groupsuffix',
            'machinesuffix',
            'passwordsuffix',
            'certfile',
            'use_default_domain'
        ]

    def __db_init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Base.__db_init__: enter")

        ldap = ldap_objects()[0]

        host = port = None
        tmphost = ldap['ldap_hostname']
        if tmphost:
            parts = tmphost.split(':')
            host = parts[0]
            if len(parts) > 1 and parts[1]:
                port = long(parts[1])

        binddn = bindpw = None
        anonbind = ldap['ldap_anonbind']
        if not anonbind:
            binddn = ldap['ldap_binddn']
            bindpw = ldap['ldap_bindpw']
        basedn = ldap['ldap_basedn']

        ssl = FREENAS_LDAP_NOSSL
        if ldap.has_key('ldap_ssl') and ldap['ldap_ssl']:
            ssl = ldap['ldap_ssl']

        args = {
            'binddn': binddn,
            'bindpw': bindpw,
            'basedn': basedn,
            'ssl': ssl,
            }
        if host:
            args['host'] = host
            if port:
                args['port'] = port

        if kwargs.has_key('flags'):
            args['flags'] = kwargs['flags']

        super(FreeNAS_LDAP_Base, self).__init__(**args)

        self.binddn = ldap['ldap_binddn']
        self.bindpw = ldap['ldap_bindpw']
        self.usersuffix = ldap['ldap_usersuffix']
        self.groupsuffix = ldap['ldap_groupsuffix']
        self.machinesuffix = ldap['ldap_machinesuffix']
        self.passwordsuffix = ldap['ldap_passwordsuffix']
        self.anonbind = ldap['ldap_anonbind']

        log.debug("FreeNAS_LDAP_Base.__db_init__: leave")

    def __no_db_init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Base.__no_db_init__: enter")

        host = None
        tmphost = kwargs.get('host', None)
        if tmphost:
            host = tmphost.split(':')[0]
            port = long(kwargs['port']) if kwargs.has_key('port') else None
            if port == None:
                tmp = tmphost.split(':')
                if len(tmp) > 1:
                    port = long(tmp[1])

        if kwargs.has_key('port') and kwargs['port'] and not port:
            port = long(kwargs['port'])

        binddn = bindpw = None
        anonbind = kwargs.get('anonbind', None)
        if not anonbind:
            binddn = kwargs.get('binddn', None)
            bindpw = kwargs.get('bindpw', None)
        basedn = kwargs.get('basedn', None)

        ssl = FREENAS_LDAP_NOSSL
        if kwargs.has_key('ssl') and kwargs['ssl']:
            ssl = kwargs['ssl']

        args = {
            'binddn': binddn,
            'bindpw': bindpw,
            'basedn': basedn,
            'ssl': ssl,
            }
        if host:
            args['host'] = host
            if port:
                args['port'] = port

        if kwargs.has_key('flags'):
            args['flags'] = kwargs['flags']

        super(FreeNAS_LDAP_Base, self).__init__(**args)

        self.binddn = kwargs.get('binddn', None)
        self.bindpw = kwargs.get('bindpw', None)
        self.usersuffix = kwargs.get('usersuffix', None)
        self.groupsuffix = kwargs.get('groupsuffix', None)
        self.machinesuffix = kwargs.get('machinesuffix', None)
        self.passwordsuffix = kwargs.get('passwordsuffix', None)
        self.pwencryption = kwargs.get('pwencryption', None)
        self.anonbind = kwargs.get('anonbind', None)

        log.debug("FreeNAS_LDAP_Base.__no_db_init__: leave")

    def __old_init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Base.__init__: enter")

        __initfunc__ = self.__no_db_init__
        if kwargs.has_key('flags') and (kwargs['flags'] & FLAGS_DBINIT):
            __initfunc__ = self.__db_init__

        __initfunc__(**kwargs)
        self.ucount = 0
        self.gcount = 0

        log.debug("FreeNAS_LDAP_Base.__init__: leave")

    def __set_defaults(self): 
        log.debug("FreeNAS_LDAP_Base.__set_defaults: enter")

        for key in self.__keys():
            if key in ('anonbind', 'use_default_domain'):
                self.__dict__[key] = False
            else:
                self.__dict__[key] = None

        self.flags = 0

        log.debug("FreeNAS_LDAP_Base.__set_defaults: leave")

    def __name_to_host(self, name):
        host = None
        port = 389
        if name:
            parts = name.split(':')
            host = parts[0]
            if len(parts) > 1:
                port = long(parts[1])
        return (host, port)

    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Base.__init__: enter")

        self.kwargs = kwargs
        self.__set_defaults()

        if kwargs.has_key('flags') and (kwargs['flags'] & FLAGS_DBINIT):
            ldap = ldap_objects()[0]
            for key in ldap.keys():
                newkey = key.replace("ldap_", "")
                if newkey == 'hostname':
                    (host, port) = self.__name_to_host(ldap[key])
                    if not 'host' in kwargs:
                        kwargs['host'] = host 
                    if not 'port' in kwargs:
                        kwargs['port'] = port

                elif newkey == 'anonbind':
                    if not 'anonbind' in kwargs:
                        kwargs[newkey] = \
                             False if long(ldap[key]) == 0 else True
 
                elif newkey == 'use_default_domain':
                    if not 'use_default_domain' in kwargs:
                        kwargs[newkey] = \
                             False if long(ldap[key]) == 0 else True

                else:
                    if not newkey in kwargs:
                        kwargs[newkey] = ldap[key] if ldap[key] else None
    
        for key in kwargs:
            if key in self.__keys():
                self.__dict__[key] = kwargs[key]

        super(FreeNAS_LDAP_Base, self).__init__(**kwargs)

        self.ucount = 0
        self.gcount = 0

        log.debug("FreeNAS_LDAP_Base.__init__: leave")

    def get_user(self, user):
        log.debug("FreeNAS_LDAP_Base.get_user: enter")
        log.debug("FreeNAS_LDAP_Base.get_user: user = %s", user)

        if user is None:
            raise AssertionError('user is None')

        isopen = self._isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        if type(user) in (types.IntType, types.LongType):
            filter = '(&(|(objectclass=person)(objectclass=account))' \
                '(uidnumber=%d))' % user.encode('utf-8')

        elif user.isdigit():

            filter = '(&(|(objectclass=person)(objectclass=account))' \
                '(uidnumber=%s))' % user.encode('utf-8')
        else:
            filter = '(&(|(objectclass=person)(objectclass=account))' \
                '(|(uid=%s)(cn=%s)))' % (user.encode('utf-8'),
                user.encode('utf-8'))

        basedn = None
        if self.usersuffix and self.basedn:
            basedn = "%s,%s" % (self.usersuffix, self.basedn)
        elif self.basedn:
            basedn = "%s" % self.basedn

        args = {'scope': scope, 'filter': filter}
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

        log.debug("FreeNAS_LDAP_Base.get_user: leave")
        return ldap_user

    def get_users(self):
        log.debug("FreeNAS_LDAP_Base.get_users: enter")
        isopen = self._isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=person)(objectclass=account))(uid=*))'

        if self.usersuffix:
            basedn = "%s,%s" % (self.usersuffix, self.basedn)
        else:
            basedn = "%s" % self.basedn
	
        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    users.append(r)

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Base.get_users: leave")
        return users

    def get_group(self, group):
        log.debug("FreeNAS_LDAP_Base.get_group: enter")
        log.debug("FreeNAS_LDAP_Base.get_group: group = %s", group)

        if group is None:
            raise AssertionError('group is None')

        isopen = self._isopen
        self.open()

        ldap_group = None
        scope = ldap.SCOPE_SUBTREE

        if type(group) in (types.IntType, types.LongType):
            filter = '(&(objectclass=posixgroup)(gidnumber=%d))' % \
                group.encode('utf-8')
        elif group.isdigit():
            filter = '(&(objectclass=posixgroup)(gidnumber=%s))' % \
                group.encode('utf-8')
        else:
            filter = '(&(objectclass=posixgroup)(cn=%s))' % \
                group.encode('utf-8')

        if self.groupsuffix:
            basedn = "%s,%s" % (self.groupsuffix, self.basedn)
        else:
            basedn = "%s" % self.basedn

        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ldap_group = r
                    break

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Base.get_group: leave")
        return ldap_group

    def get_groups(self):
        log.debug("FreeNAS_LDAP_Base.get_groups: enter")
        isopen = self._isopen
        self.open()

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=posixgroup)(gidnumber=*))'

        if self.groupsuffix:
            basedn = "%s,%s" % (self.groupsuffix, self.basedn)
        else:
            basedn = "%s" % self.basedn
	
        results = self._search(basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    groups.append(r)

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Base.get_groups: leave")
        return groups

    def get_domains(self):
        log.debug("FreeNAS_LDAP_Base.get_domains: enter")
        isopen = self._isopen
        self.open()

        domains = []
        scope = ldap.SCOPE_SUBTREE

        filter = '(objectclass=sambaDomain)'
        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            domains = results

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Base.get_domains: leave")
        return domains

    def get_domain_names(self):
        log.debug("FreeNAS_LDAP_Base.get_domain_names: enter")

        domain_names = []
        domains = self.get_domains()
        if domains:
            for d in domains: 
                domain_names.append(d[1]['sambaDomainName'][0])

        log.debug("FreeNAS_LDAP_Base.get_domain_names: enter")
        return domain_names


class FreeNAS_LDAP(FreeNAS_LDAP_Base):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP.__init__: enter")

        super(FreeNAS_LDAP, self).__init__(**kwargs)

        log.debug("FreeNAS_LDAP.__init__: leave")


class FreeNAS_ActiveDirectory_Base(object):
    class AsyncConnect(asyncore.dispatcher):
        def __init__(self, host, port, callback):
            asyncore.dispatcher.__init__(self)  
            self._host = host
            self._port = port
            self._callback = callback
            self._start_time = time.time()
            self.buffer = ""  

            self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                self.connect((self._host, self._port))  
            except socket.gaierror:
                callback(self._host, self._port, 1000)
                self.close()

        def handle_connect(self):
            pass
        def handle_read(self):
            pass
        def handle_error(self):
            pass

        def handle_write(self):
            duration = time.time() - self._start_time
            self._callback(self._host, self._port, duration)
            self.close()

    @staticmethod
    def get_best_host(srv_hosts):
        if not srv_hosts:
            return None

        best_host = None
        latencies = {}

        def callback(host, port, duration):
            latencies.setdefault(host, 0)
            latencies[host] += duration

        for srv_host in srv_hosts:
            host = srv_host.target.to_text(True)
            port = long(srv_host.port)
            FreeNAS_ActiveDirectory_Base.AsyncConnect(host,
                long(port), callback)

        count = len(srv_hosts)
        asyncore.loop(timeout=1, count=count)
        if not latencies:
            asyncore.loop(timeout=60)

        asyncore.close_all()
        latency_list = sorted(latencies.iteritems(), key=lambda (a,b): (b,a))
        if latency_list:
            best_host = map(lambda x: (x.target.to_text(True), long(x.port)) \
                if x.target.to_text(True) == latency_list[0][0] \
                    else None, srv_hosts)[0]

        return best_host

    @staticmethod
    def get_SRV_records(host):
        srv_records = []

        if not host:
            return srv_records
  
        try:
            log.debug("FreeNAS_ActiveDirectory_Base.get_SRV_records: "
                "looking up SRV records for %s", host)
            answers = resolver.query(host, 'SRV')
            srv_records = sorted(answers, key=lambda a: (int(a.priority),
                int(a.weight)))

        except:
            log.debug("FreeNAS_ActiveDirectory_Base.get_SRV_records: "
                "no SRV records for %s found, fail!", host)
            srv_records = []

        return srv_records

    @staticmethod
    def get_ldap_servers(domain, site=None):
        dcs = []
        if not domain:
            return dcs

        host = "_ldap._tcp.%s" % domain
        if site:
            host = "_ldap._tcp.%s._sites.%s" % (site, domain)

        dcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return dcs

    @staticmethod
    def get_domain_controllers(domain, site=None):
        dcs = []
        if not domain:
            return dcs

        host = "_ldap._tcp.dc._msdcs.%s" % domain
        if site:
            host = "_ldap._tcp.%s._sites.dc._msdcs.%s" % (site, domain)

        dcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return dcs

    @staticmethod
    def get_primary_domain_controllers(domain):
        pdcs = []
        if not domain:
            return pdcs

        host = "_ldap._tcp.pdc._msdcs.%s"

        pdcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return pdcs

    @staticmethod
    def get_global_catalog_servers(domain, site=None):
        gcs = []
        if not domain:
            return gcs

        host = "_gc._tcp.%s" % domain
        if site:
            host = "_gc._tcp.%s._sites.%s" % (site, domain)

        gcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return gcs

    @staticmethod
    def get_forest_global_catalog_servers(forest, site=None):
        fgcs = []
        if not forest:
            return fgcs

        host = "_ldap._tcp.gc._msdcs.%s" % forest
        if site:
            host = "_ldap._tcp.%s._sites.gc._msdcs.%s" % (site, forest)

        fgcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return fgcs

    @staticmethod
    def get_kerberos_servers(domain, site=None):
        kdcs = []
        if not domain:
            return kdcs

        host = "_kerberos._tcp.%s" % domain
        if site:
            host = "_kerberos._tcp.%s._sites.%s" % (site, domain)

        kdcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return kdcs

    @staticmethod
    def get_kerberos_domain_controllers(domain, site=None):
        kdcs = []
        if not domain:
            return kdcs

        host = "_kerberos._tcp.dc._msdcs.%s" % domain
        if site:
            host = "_kerberos._tcp.%s._sites.dc._msdcs.%s" % (site, domain)

        kdcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return kdcs

    @staticmethod
    def get_kpasswd_servers(domain):
        kpws = []
        if not domain:
            return kpws

        host = "_kpasswd._tcp.%s" % domain

        kpws = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        return kpws

    @staticmethod
    def validate_credentials(domain, site=None, binddn=None, bindpw=None, errors=[]):
        ret = None
        best_host = None 

        dcs = FreeNAS_ActiveDirectory_Base.get_domain_controllers(domain, site)
        if not dcs:
            raise FreeNAS_ActiveDirectory_Exception(
                "Unable to find domain controllers for %s" % domain)

        best_host = FreeNAS_ActiveDirectory_Base.get_best_host(dcs) 
        if best_host:
            (dchost, dcport) = best_host
            f = FreeNAS_LDAP(host=dchost, port=dcport,
                binddn=binddn, bindpw=bindpw)

            try:
                f.open()
                ret = True

            except Exception as e:
                for error in e:
                    errors.append(error['desc'])
                ret = False

        return ret

    @staticmethod
    def adset(val, default=None):
        ret = default
        if val:
            ret = val
        return ret

    def __keys(self):
        return [
            'domainname',
            'netbiosname',
            'bindname',
            'bindpw',
            'use_keytab',
            'keytab',
            'ssl',
            'certfile',
            'verbose_logging',
            'unix_extensions',
            'allow_trusted_doms',
            'use_default_domain',
            'dcname',
            'gcname',
            'krbname',
            'kpwdname',
            'timeout',
            'dns_timeout',
            'basedn',
            'binddn',
            'dchost',
            'dcport',
            'gchost',
            'gcport',
            'krbhost',
            'krbport',
            'kpwdhost',
            'kpwdport',
            'dchandle',
            'gchandle',
            'site',
            'flags'
        ]

    def __set_defaults(self):
        log.debug("FreeNAS_ActiveDirectory_Base.__set_defaults: enter")

        for key in self.__keys():
            if key in ('use_keytab', 'verbose_logging', 'unix_extensions',
                'allow_trusted_doms', 'use_default_domain'):
                 self.__dict__[key] = False
            elif key in ('timeout', 'dns_timeout'):
                 self.__dict__[key] = 10
            else:
                 self.__dict__[key] = None

            self.flags = 0

        log.debug("FreeNAS_ActiveDirectory_Base.__set_defaults: leave")

    def __name_to_host(self, name):
        host = None  
        port = None  
        if name:
            parts = name.split(':')
            host = parts[0]
            if len(parts) > 1:
                port = long(parts[1])
        return (host, port)

    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.__init__: enter")

        self.kwargs = kwargs
        self.__set_defaults()

        super(FreeNAS_ActiveDirectory_Base, self).__init__()

        if kwargs.has_key('flags') and (kwargs['flags'] & FLAGS_DBINIT):
            ad = activedirectory_objects()[0]
            for key in ad.keys():
                newkey = key.replace("ad_", "")
                if newkey in ('use_keytab', 'verbose_logging',
                    'unix_extensions', 'allow_trusted_doms',
                    'use_default_domain'):
                    self.__dict__[newkey] = \
                        False if long(ad[key]) == 0 else True
                else:
                    self.__dict__[newkey] = ad[key] if ad[key] else None

        for key in kwargs:
            if key in self.__keys():
                self.__dict__[key] = kwargs[key]

        if self.bindname and self.domainname:  
            self.binddn = self.adset(self.binddn,
                self.bindname + '@' + self.domainname.upper())

        host = port = None
        args = {'binddn': self.binddn, 'bindpw': self.bindpw}

        if self.dcname:
            (self.dchost, self.dcport) = self.__name_to_host(self.dcname)
        if not self.dchost:
            dcs = self.get_domain_controllers(self.domainname, site=self.site)
            if not dcs:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % self.domainname)
            (self.dchost, self.dcport) = self.get_best_host(dcs)
            self.dcname = "%s:%d" % (self.dchost, self.dcport)

        if self.gcname:
            (self.gchost, self.gcport) = self.__name_to_host(self.gcname)
        if not self.gchost:
            gcs = self.get_global_catalog_servers(self.domainname, site=self.site)
            if not gcs: 
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find global catalog servers for %s" % self.domainname)
            (self.gchost, self.gcport) = self.get_best_host(gcs)
            self.gcname = "%s:%d" % (self.gchost, self.gcport)

        if self.krbname:
            (self.krbhost, self.krbport) = self.__name_to_host(self.krbname)
        if not self.krbhost:
            krbs = self.get_kerberos_servers(self.domainname, site=self.site)
            if not krbs: 
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find kerberos servers for %s" % self.domainname)
            (self.krbhost, self.krbport) = self.get_best_host(krbs)
            self.krbname = "%s:%d" % (self.krbhost, self.krbport)

        if self.kpwdname:
            (self.kpwdhost, self.kpwdport) = self.__name_to_host(
                self.kpwdname)
        if not self.kpwdhost:
            kpwds = self.get_kpasswd_servers(self.domainname)
            if not kpwds: 
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find kerberos password servers for %s" % self.domainname)
            (self.kpwdhost, self.kpwdport) = self.get_best_host(kpwds)
            self.kpwdname = "%s:%d" % (self.kpwdhost, self.kpwdport)

        self.dchandle = FreeNAS_LDAP_Directory(
            binddn=self.binddn, bindpw=self.bindpw,
            host=self.dchost, port=self.dcport, flags=self.flags)
        self.dchandle.open()

        self.gchandle = FreeNAS_LDAP_Directory(
            binddn=self.binddn, bindpw=self.bindpw,
            host=self.gchost, port=self.gcport, flags=self.flags)
        self.gchandle.open()

        self.basedn = self.adset(self.basedn, self.get_baseDN())
        self.netbiosname = self.get_netbios_name()
        self.ucount = 0
        self.gcount = 0

        log.debug("FreeNAS_ActiveDirectory_Base.__init__: leave")

    def connected(self):
        return self.validate_credentials(self.domainname, site=self.site,
            binddn=self.binddn, bindpw=self.bindpw)

    def reload(self, **kwargs):
        self.kwargs.update(kwargs)
        self.__init__(**self.kwargs)

    def _search(self, handle, basedn="", scope=ldap.SCOPE_SUBTREE,
        filter=None, attributes=None, attrsonly=0, serverctrls=None,
        clientctrls=None, timeout=-1, sizelimit=0):
        return handle._search(basedn, scope, filter, attributes, attrsonly,
            serverctrls, clientctrls, timeout, sizelimit)

    def get_rootDSE(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_rootDSE: enter")

        results = self._search(self.dchandle, '', ldap.SCOPE_BASE,
            "(objectclass=*)")

        log.debug("FreeNAS_ActiveDirectory_Base.get_rootDSE: leave")
        return results

    def get_rootDN(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_rootDN: enter")

        results = self.get_rootDSE()
        try:
            results = results[0][1]['rootDomainNamingContext'][0]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_rootDN: leave")
        return results

    def get_baseDN(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_baseDN: enter")

        results = self.get_rootDSE()
        try:
            results = results[0][1]['defaultNamingContext'][0]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_baseDN: leave")
        return results

    def get_config(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_config: enter")

        results = self.get_rootDSE()
        try:
            results = results[0][1]['configurationNamingContext'][0]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_config: leave")
        return results

    def get_netbios_name(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_netbios_name: enter")

        basedn = self.get_baseDN()
        config = self.get_config()
        filter = "(&(objectcategory=crossref)(nCName=%s))" % \
            basedn.encode('utf-8')

        netbios_name = None
        results = self._search(self.dchandle, config,
            ldap.SCOPE_SUBTREE, filter)
        try:
            netbios_name = results[0][1]['nETBIOSName'][0]

        except:
            netbios_name = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_netbios_name: leave")
        return netbios_name

    def get_partitions(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_partition: enter")

        config = self.get_config()
        basedn = "CN=Partitions,%s" % config

        filter = None
        keys = ['netbiosname', 'name', 'cn', 'dn',
            'distinguishedname', 'ncname']
        for k in keys:
            if kwargs.has_key(k):
                filter = "(%s=%s)" % (k, kwargs[k].encode('utf-8'))
                break

        if filter is None:
            filter = "(cn=*)"

        partitions = []
        results = self._search(self.dchandle, basedn,
            ldap.SCOPE_SUBTREE, filter)
        if results:
            for r in results:
                if r[0]:
                    partitions.append(r)

        log.debug("FreeNAS_ActiveDirectory_Base.get_partition: leave")
        return partitions

    def get_root_domain(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_root_domain: enter")

        rootDSE = self.get_rootDSE()
        rdnc = rootDSE[0][1]['rootDomainNamingContext'][0]

        domain = None
        results = self.get_partitions(ncname=rdnc)
        try:
            domain = results[0][1]['dnsRoot'][0]

        except:
            domain = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_root_domain: leave")
        return domain

    def get_domain(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_domain: enter")

        domain = None
        results = self.get_partitions(**kwargs)
        try:
            domain = results[0][1]['dnsRoot'][0]

        except:
            domain = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_domain: leave")
        return domain

    def get_domains(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_domains: enter")

        domains = []
        results = self._search(self.gchandle, "", ldap.SCOPE_SUBTREE,
            '(objectclass=domain)', ['dn'])
        if not results:
            log.debug("FreeNAS_ActiveDirectory_Base.get_domains: " \
                "no domain objects found")
            results = []

        for r in results:
            domains.append(r[0])

        rootDSE = self.get_rootDSE()
        basedn = rootDSE[0][1]['configurationNamingContext'][0]
        #config = rootDSE[0][1]['defaultNamingContext'][0]

        if not self.allow_trusted_doms and self.netbiosname:
            kwargs['netbiosname'] = self.netbiosname

        result = []
        haskey = False
        for d in domains:
            filter = None
            if len(kwargs) > 0:
                haskey = True
                keys = ['netbiosname', 'name', 'cn', 'dn',
                    'distinguishedname', 'ncname']
                for k in keys:
                    if kwargs.has_key(k):
                        filter = "(&(objectcategory=crossref)(%s=%s))" % \
                            (k, kwargs[k].encode('utf-8'))
                        break

            if filter is None:
                filter = "(&(objectcategory=crossref)(nCName=%s))" % \
                    d.encode('utf-8')

            results = self._search(self.dchandle, basedn,
                ldap.SCOPE_SUBTREE, filter)
            if results and results[0][0]:
                r = {}
                for k in results[0][1].keys():
                    r[k] = results[0][1][k][0]
                result.append(r)

            if haskey:
                break

        log.debug("FreeNAS_ActiveDirectory_Base.get_domains: leave")
        return result

    def get_userDN(self, user):
        log.debug("FreeNAS_ActiveDirectory_Base.get_userDN: enter")
        log.debug("FreeNAS_ActiveDirectory_Base.get_userDN: user = %s", user)

        if user is None:
            raise AssertionError('user is None')

        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))' \
            '(sAMAccountName=%s))' % user.encode('utf-8')
        attributes = ['distinguishedName']
        results = self._search(self.dchandle, self.basedn, scope,
            filter, attributes)
        try:
            results = results[0][1][attributes[0]][0]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_userDN: leave")
        return results

    def get_user(self, user):
        log.debug("FreeNAS_ActiveDirectory_Base.get_user: enter")
        log.debug("FreeNAS_ActiveDirectory_Base.get_user: user = %s", user)

        if user is None:
            raise AssertionError('user is None')

        ad_user = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))' \
            '(sAMAccountName=%s))' % user.encode('utf-8')
        results = self._search(self.dchandle, self.basedn, scope,
            filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_user = r
                    break

        log.debug("FreeNAS_ActiveDirectory_Base.get_user: leave")
        return ad_user

    def get_users(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_users: enter")

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))' \
            '(sAMAccountName=*))'
        if self.attributes and 'sAMAccountType' not in self.attributes:
            self.attributes.append('sAMAccountType')

        results = self._search(self.dchandle, self.basedn, scope,
            filter, self.attributes)
        if results:
            for r in results:
                if r[0] and r[1] and r[1].has_key('sAMAccountType'):
                    type = int(r[1]['sAMAccountType'][0])
                    if not (type & 0x1):
                        users.append(r)

        self.ucount = len(users)
        log.debug("FreeNAS_ActiveDirectory_Base.get_users: leave")
        return users

    def get_groupDN(self, group):
        log.debug("FreeNAS_ActiveDirectory_Base.get_groupDN: enter")
        log.debug("FreeNAS_ActiveDirectory_Base.get_groupDN: group = %s",
            group)

        if group is None:
            raise AssertionError('group is None')

        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % \
            group.encode('utf-8')
        attributes = ['distinguishedName']
        results = self._search(self.dchandle, self.basedn, scope,
            filter, attributes)
        try:
            results = results[0][1][attributes[0]][0]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_groupDN: leave")
        return results

    def get_group(self, group):
        log.debug("FreeNAS_ActiveDirectory_Base.get_group: enter")
        log.debug("FreeNAS_ActiveDirectory_Base.get_group: group = %s", group)

        if group is None:
            raise AssertionError('group is None')

        ad_group = None
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % \
            group.encode('utf-8')
        results = self._search(self.dchandle, self.basedn, scope,
            filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ad_group = r
                    break

        log.debug("FreeNAS_ActiveDirectory_Base.get_group: leave")
        return ad_group

    def get_groups(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_groups: enter")

        groups = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=*))'
        if self.attributes and 'groupType' not in self.attributes:
            self.attributes.append('groupType')

        results = self._search(self.dchandle, self.basedn, scope,
            filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['groupType'][0])
                    if not (type & 0x1):
                        groups.append(r)

        self.ucount = len(groups)
        log.debug("FreeNAS_ActiveDirectory_Base.get_groups: leave")
        return groups

    def get_user_count(self):
        count = 0

        if self.ucount > 0:
            count = self.ucount

        else:
            pagesize = self.pagesize
            self.pagesize = 32768

            self.get_users()

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

            self.get_groups()

            self.pagesize = pagesize
            count = self.gcount

        return count


class FreeNAS_ActiveDirectory(FreeNAS_ActiveDirectory_Base):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory.__init__: enter")

        super(FreeNAS_ActiveDirectory, self).__init__(**kwargs)

        log.debug("FreeNAS_ActiveDirectory.__init__: leave")


class FreeNAS_LDAP_Users(FreeNAS_LDAP):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Users.__init__: enter")

        super(FreeNAS_LDAP_Users, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache()

        self.__users = []
        self.__usernames = []
        self.__get_users()

        log.debug("FreeNAS_LDAP_Users.__init__: leave")

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

    def _get_uncached_usernames(self):
        return self.__usernames

    def __get_users(self):
        log.debug("FreeNAS_LDAP_Users.__get_users: enter")

        self.__usernames = []

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('u'):
            log.debug("FreeNAS_LDAP_Users.__get_users: users in cache")
            log.debug("FreeNAS_LDAP_Users.__get_users: leave")
            self.__users = self.__ucache
            return

        self.attributes = ['uid']
        self.pagesize = FREENAS_LDAP_PAGESIZE

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('du'):
            log.debug("FreeNAS_LDAP_Users.__get_users: LDAP users in cache")
            ldap_users = self.__ducache

        else:
            log.debug("FreeNAS_LDAP_Users.__get_users: " \
                "LDAP users not in cache")
            ldap_users = self.get_users()

        parts = self.host.split('.')
        host = parts[0].upper()
        for u in ldap_users:
            CN = str(u[0])
            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__ducache[CN] = u

            u = u[1]
            if self.use_default_domain:
                uid = u['uid'][0]
            else:
                uid = "{}{}{}".format(
                    host,
                    FREENAS_AD_SEPARATOR,
                    u['uid'][0]
                )

            self.__usernames.append(uid)

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

        log.debug("FreeNAS_LDAP_Users.__get_users: leave")


class FreeNAS_ActiveDirectory_Users(FreeNAS_ActiveDirectory):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Users.__init__: enter")

        super(FreeNAS_ActiveDirectory_Users, self).__init__(**kwargs)

        self.__users = {}
        self.__usernames = []
        self.__ucache = {}
        self.__ducache = {}

        if kwargs.has_key('netbiosname') and kwargs['netbiosname']:
            self.__domains = self.get_domains(
                netbiosname=kwargs['netbiosname'])
        else:
            self.__domains = self.get_domains()

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            for d in self.__domains:
                n = d['nETBIOSName']
                self.__ucache[n] = FreeNAS_UserCache(dir=n)
                self.__ducache[n] = FreeNAS_Directory_UserCache(dir=n)

        self.__get_users()

        log.debug("FreeNAS_ActiveDirectory_Users.__init__: leave")

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

    def _get_uncached_usernames(self):
        return self.__usernames

    def __get_users(self):
        log.debug("FreeNAS_ActiveDirectory_Users.__get_users: enter")

        self.__usernames = []

        if (self.flags & FLAGS_CACHE_READ_USER):
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                n = d['nETBIOSName']
                if self.__loaded('u', n):
                    self.__users[n] = self.__ucache[n]
                    count += 1

            if count == dcount:
                log.debug("FreeNAS_ActiveDirectory_Users.__get_users: " \
                    "users in cache")
                log.debug("FreeNAS_ActiveDirectory_Users.__get_users: leave")
                return

        for d in self.__domains:
            n = d['nETBIOSName']
            self.__users[n] = []

            dcs = self.get_domain_controllers(d['dnsRoot'])
            if not dcs: 
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % d['dnsRoot'])
            (self.host, self.port) = self.get_best_host(dcs)

            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            if (self.flags & FLAGS_CACHE_READ_USER) \
                and self.__loaded('du', n):
                log.debug("FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users in cache" % n)
                ad_users = self.__ducache[n]

            else:
                log.debug("FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users not in cache" % n)
                ad_users = self.get_users()

            for u in ad_users:
                CN = str(u[0])

                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ducache[n][CN] = u

                u = u[1]
                if self.use_default_domain:
                    sAMAccountName = u['sAMAccountName'][0]
                else:
                    sAMAccountName = "{}{}{}".format(
                        n,
                        FREENAS_AD_SEPARATOR,
                        u['sAMAccountName'][0]
                    )

                self.__usernames.append(sAMAccountName)

                try:
                    pw = pwd.getpwnam(sAMAccountName)

                except Exception, e:
                    log.debug("Error on getpwnam: %s", e)
                    continue

                self.__users[n].append(pw)
                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ucache[n][sAMAccountName] = pw

                pw = None

            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__loaded('u', n, True)
                self.__loaded('du', n, True)

        log.debug("FreeNAS_ActiveDirectory_Users.__get_users: leave")


class FreeNAS_Directory_Users(object):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_Users.__new__: enter")

        dflags = 0
        if kwargs.has_key('dflags'):
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Users(**kwargs)

        elif dflags & FLAGS_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_Users(**kwargs)

        log.debug("FreeNAS_Directory_Users.__new__: leave")
        return obj


class FreeNAS_LDAP_Groups(FreeNAS_LDAP):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Groups.__init__: enter")

        super(FreeNAS_LDAP_Groups, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache()

        self.__groups = []
        self.__groupnames = []
        self.__get_groups()

        log.debug("FreeNAS_LDAP_Groups.__init__: leave")

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

    def _get_uncached_groupnames(self):
        return self.__groupnames

    def __get_groups(self):
        log.debug("FreeNAS_LDAP_Groups.__get_groups: enter")

        self.__groupnames = []

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('g'):
            log.debug("FreeNAS_LDAP_Groups.__get_groups: groups in cache")
            log.debug("FreeNAS_LDAP_Groups.__get_groups: leave")
            self.__groups = self.__gcache
            return

        self.attributes = ['cn']

        ldap_groups = None
        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('dg'):
            log.debug("FreeNAS_LDAP_Groups.__get_groups: " \
                "LDAP groups in cache")
            ldap_groups = self.__dgcache

        else:
            log.debug("FreeNAS_LDAP_Groups.__get_groups: " \
                "LDAP groups not in cache")
            ldap_groups = self.get_groups()

        parts = self.host.split('.') 
        host = parts[0].upper()
        for g in ldap_groups:
            CN = str(g[0])
            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__dgcache[CN] = g

            g = g[1]
            if self.use_default_domain:
                cn = g['cn'][0]
            else:
                cn = "{}{}{}".format(
                    host,
                    FREENAS_AD_SEPARATOR,
                    g['cn'][0]
                )

            self.__groupnames.append(cn)

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

        log.debug("FreeNAS_LDAP_Groups.__get_groups: leave")


class FreeNAS_ActiveDirectory_Groups(FreeNAS_ActiveDirectory):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Groups.__init__: enter")

        super(FreeNAS_ActiveDirectory_Groups, self).__init__(**kwargs)

        self.__groups = {}
        self.__groupnames = []
        self.__gcache = {}
        self.__dgcache = {}

        if kwargs.has_key('netbiosname') and kwargs['netbiosname']:
            self.__domains = self.get_domains(
                netbiosname=kwargs['netbiosname'])
        else:
            self.__domains = self.get_domains()

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            for d in self.__domains:
                n = d['nETBIOSName']
                self.__gcache[n] = FreeNAS_GroupCache(dir=n)
                self.__dgcache[n] = FreeNAS_Directory_GroupCache(dir=n)

        self.__get_groups()

        log.debug("FreeNAS_ActiveDirectory_Groups.__init__: leave")

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

    def _get_uncached_groupnames(self):
        return self.__groupnames

    def __get_groups(self):
        log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: enter")

        self.__groupnames = []

        if (self.flags & FLAGS_CACHE_READ_GROUP):
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                n = d['nETBIOSName']
                if self.__loaded('u', n):
                    self.__groups[n] = self.__gcache[n]
                    count += 1

            if count == dcount:
                log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: " \
                    "groups in cache")
                log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: " \
                    "leave")
                return

        for d in self.__domains:
            n = d['nETBIOSName']
            self.__groups[n] = []

            dcs = self.get_domain_controllers(d['dnsRoot'])
            if not dcs: 
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % d['dnsRoot'])
            (self.host, self.port) = self.get_best_host(dcs)

            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            if (self.flags & FLAGS_CACHE_READ_GROUP) \
                and self.__loaded('dg', n):
                log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups in cache", n)
                ad_groups = self.__dgcache[n]

            else:
                log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups not in cache", n)
                ad_groups = self.get_groups()

            for g in ad_groups:
                CN = str(g[0])

                if self.use_default_domain:
                    sAMAccountName = g[1]['sAMAccountName'][0]
                else:  
                    sAMAccountName = "{}{}{}".format(
                        n,
                        FREENAS_AD_SEPARATOR,
                        g[1]['sAMAccountName'][0]
                    )

                self.__groupnames.append(sAMAccountName)

                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__dgcache[n][CN] = g

                try:
                    gr = grp.getgrnam(sAMAccountName)

                except Exception as e:
                    log.debug("Error on getgrnam: %s", e)
                    continue

                self.__groups[n].append(gr)
                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__gcache[n][sAMAccountName] = gr

                gr = None

            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__loaded('g', n, True)
                self.__loaded('dg', n, True)

        log.debug("FreeNAS_ActiveDirectory_Groups.__get_groups: leave")


class FreeNAS_Directory_Groups(object):
    def __new__(cls, **kwargs):
        log.debug("FreeNAS_Directory_Groups.__new__: enter")

        dflags = 0
        if kwargs.has_key('dflags'):
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Groups(**kwargs)

        elif dflags & FLAGS_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_Groups(**kwargs)

        log.debug("FreeNAS_Directory_Groups.__new__: leave")
        return obj


class FreeNAS_LDAP_Group(FreeNAS_LDAP):
    def __init__(self, group, **kwargs):
        log.debug("FreeNAS_LDAP_Group.__init__: enter")
        log.debug("FreeNAS_LDAP_Group.__init__: group = %s", group)

        super(FreeNAS_LDAP_Group, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache()
            if self.groupsuffix and self.basedn:
                self.__key = str("cn=%s,%s,%s" % \
                    (group, self.groupsuffix, self.basedn))
            elif self.basedn:
                self.__key = str("cn=%s,%s" % (group, self.basedn))

        self._gr = None
        if group:
            if isinstance(group, str):
                group = group.decode('utf-8')
            self.__get_group(group)

        log.debug("FreeNAS_LDAP_Group.__init__: leave")

    def __get_group(self, group):
        log.debug("FreeNAS_LDAP_Group.__get_group: enter")
        log.debug("FreeNAS_LDAP_Group.__get_group: group = %s", group)

        gr = None
        self.attributes = ['cn']

        if (self.flags & FLAGS_CACHE_READ_GROUP) \
            and self.__gcache.has_key(group):
            log.debug("FreeNAS_LDAP_Group.__get_group: group in cache")
            return self.__gcache[group]

        if (self.flags & FLAGS_CACHE_READ_GROUP) \
            and self.__dgcache.has_key(self.__key):
            log.debug("FreeNAS_LDAP_Group.__get_group: LDAP group in cache")
            ldap_group = self.__dgcache[self.__key]

        else:
            log.debug("FreeNAS_LDAP_Group.__get_group: " \
                "LDAP group not in cache")
            ldap_group = self.get_group(group)

        if ldap_group:
            parts = self.host.split('.')
            host = parts[0].upper()

            if self.use_default_domain:
                cn = ldap_group[1]['cn'][0]
            else:
                cn = "{}{}{}".format(
                    host,
                    FREENAS_AD_SEPARATOR,
                    ldap_group[1]['cn'][0]
                )

            try:
                gr = grp.getgrnam(cn)

            except:
                gr = None

        else:
            if type(group) in (types.IntType, types.LongType) \
                or group.isdigit():
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
        log.debug("FreeNAS_LDAP_Group.__get_group: leave")


class FreeNAS_ActiveDirectory_Group(FreeNAS_ActiveDirectory):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Group.__new__: enter")
        log.debug("FreeNAS_ActiveDirectory_Group.__new__: group = %s", group)

        obj = None
        if group:
            obj = super(FreeNAS_ActiveDirectory_Group, cls).__new__(cls)

        log.debug("FreeNAS_ActiveDirectory_Group.__new__: leave")
        return obj

    def __init__(self, group, **kwargs):
        if isinstance(group, str):
            group = group.decode('utf-8')

        log.debug("FreeNAS_ActiveDirectory_Group.__init__: enter")
        log.debug("FreeNAS_ActiveDirectory_Group.__init__: group = %s", group)

        netbiosname = None
        self.__group = group
        parts = group.split(FREENAS_AD_SEPARATOR)
        if len(parts) > 1 and parts[1]:
            netbiosname = parts[0]
            kwargs['netbiosname'] = netbiosname
            group = parts[1]

        self._gr = None

        super(FreeNAS_ActiveDirectory_Group, self).__init__(**kwargs)
        if not netbiosname:
            netbiosname = self.netbiosname

        if (self.flags & FLAGS_CACHE_READ_GROUP) or \
            (self.flags & FLAGS_CACHE_WRITE_GROUP):
            self.__gcache = FreeNAS_GroupCache(dir=netbiosname)
            self.__gkey = self.__group.encode('utf-8')
            self.__dgcache = FreeNAS_Directory_GroupCache(dir=netbiosname)
            self.__dgkey = self.get_groupDN(group)

        self.__get_group(group, netbiosname)

        log.debug("FreeNAS_ActiveDirectory_Group.__init__: leave")

    def __get_group(self, group, netbiosname):
        log.debug("FreeNAS_ActiveDirectory_Group.__get_group: enter")
        log.debug("FreeNAS_ActiveDirectory_Group.__get_group: group = %s",
            group)
        log.debug("FreeNAS_ActiveDirectory_Group.__get_group: " \
            "netbiosname = %s", netbiosname)

        if (self.flags & FLAGS_CACHE_READ_GROUP) \
            and self.__gcache.has_key(self.__gkey):
            log.debug("FreeNAS_ActiveDirectory_User.__get_group: " \
                "group in cache")
            self._gr = self.__gcache[self.__gkey]
            return self.__gcache[self.__gkey]

        g = gr = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (self.flags & FLAGS_CACHE_READ_GROUP) \
            and self.__dgcache.has_key(self.__dgkey):
            log.debug("FreeNAS_ActiveDirectory_Group.__get_group: " \
                "AD group in cache")
            ad_group = self.__dgcache[self.__dgkey]

        else:
            log.debug("FreeNAS_ActiveDirectory_Group.__get_group: " \
                "AD group not in cache")
            ad_group = self.get_group(group)

        if self.use_default_domain:
            g = "{}".format(ad_group[1]['sAMAccountName'][0] \
                if ad_group else group)
        elif not ad_group:
            g = group
        else:
            g = "{}{}{}".format(
                netbiosname,
                FREENAS_AD_SEPARATOR,
                ad_group[1]['sAMAccountName'][0] if ad_group else group
            )

        try:
            gr = grp.getgrnam(g)

        except:
            gr = None

        if (self.flags & FLAGS_CACHE_WRITE_GROUP) and gr:
            self.__gcache[self.__gkey] = gr
            self.__dgcache[self.__dgkey] = ad_group

        self._gr = gr
        log.debug("FreeNAS_ActiveDirectory_Group.__get_group: leave")


class FreeNAS_Directory_Group(object):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_Directory_Group.__new__: enter")
        log.debug("FreeNAS_Directory_Group.__new__: group = %s", group)

        dflags = 0
        if kwargs.has_key('dflags'):
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Group(group, **kwargs)

        elif dflags & FLAGS_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_Group(group, **kwargs)

        if obj and obj._gr is None:
            obj = None

        log.debug("FreeNAS_Directory_Group.__new__: leave")
        return obj


class FreeNAS_LDAP_User(FreeNAS_LDAP):
    def __init__(self, user, **kwargs):
        log.debug("FreeNAS_LDAP_User.__init__: enter")
        log.debug("FreeNAS_LDAP_User.__init__: user = %s", user)

        super(FreeNAS_LDAP_User, self).__init__(**kwargs)

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache()
            if self.usersuffix and self.basedn:
                self.__key = str("uid=%s,%s,%s" % (user,
                    self.usersuffix, self.basedn))
            elif self.basedn:
                self.__key = str("uid=%s,%s" % (user, self.basedn))

        self._pw = None
        if user:
            if isinstance(user, str):
                user = user.decode('utf-8')
            self.__get_user(user)

        log.debug("FreeNAS_LDAP_User.__init__: leave")

    def __get_user(self, user):
        log.debug("FreeNAS_LDAP_User.__get_user: enter")
        log.debug("FreeNAS_LDAP_User.__get_user: user = %s", user)

        pw = None
        self.attributes = ['uid']

        if (self.flags & FLAGS_CACHE_READ_USER) \
            and self.__ucache.has_key(user):
            log.debug("FreeNAS_LDAP_User.__get_user: user in cache")
            return self.__ucache[user]

        if (self.flags & FLAGS_CACHE_READ_USER) \
            and self.__ducache.has_key(self.__key):
            log.debug("FreeNAS_LDAP_User.__get_user: LDAP user in cache")
            ldap_user = self.__ducache[self.__key]

        else:
            log.debug("FreeNAS_LDAP_User.__get_user: LDAP user not in cache")
            ldap_user = self.get_user(user)

        if ldap_user:
            self.__CN = ldap_user[0]

            parts = self.host.split('.')
            host = parts[0].upper()

            if self.use_default_domain:
                uid = ldap_user[1]['uid'][0]
            else:
                uid = "{}{}{}".format(
                    host,
                    FREENAS_AD_SEPARATOR,
                    ldap_user[1]['uid'][0]
                )

            try:
                pw = pwd.getpwnam(uid)

            except:
                pw = None

        else:
            if type(user) in (types.IntType, types.LongType) \
                or user.isdigit():
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
        log.debug("FreeNAS_LDAP_User.__get_user: leave")


class FreeNAS_ActiveDirectory_User(FreeNAS_ActiveDirectory):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_User.__new__: enter")
        log.debug("FreeNAS_ActiveDirectory_User.__new__: user = %s", user)

        obj = None
        if user:
            obj = super(FreeNAS_ActiveDirectory_User, cls).__new__(cls)

        log.debug("FreeNAS_ActiveDirectory_User.__new__: leave")
        return obj

    def __init__(self, user, **kwargs):
        if isinstance(user, str):
            user = user.decode('utf-8')

        log.debug("FreeNAS_ActiveDirectory_User.__init__: enter")
        log.debug("FreeNAS_ActiveDirectory_User.__init__: user = %s", user)

        netbiosname = None
        self.__user = user
        parts = user.split(FREENAS_AD_SEPARATOR)
        if len(parts) > 1 and parts[1]:
            netbiosname = parts[0]
            kwargs['netbiosname'] = netbiosname
            user = parts[1]

        self._pw = None

        super(FreeNAS_ActiveDirectory_User, self).__init__(**kwargs)
        if not netbiosname:
            netbiosname = self.netbiosname

        if (self.flags & FLAGS_CACHE_READ_USER) or \
            (self.flags & FLAGS_CACHE_WRITE_USER):
            self.__ucache = FreeNAS_UserCache(dir=netbiosname)
            self.__ukey = self.__user.encode('utf-8')
            self.__ducache = FreeNAS_Directory_UserCache(dir=netbiosname)
            self.__dukey = self.get_userDN(user)

        self.__get_user(user, netbiosname)

        log.debug("FreeNAS_ActiveDirectory_User.__init__: leave")

    def __get_user(self, user, netbiosname):
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: enter")
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: user = %s", user)
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: " \
            "netbiosname = %s", netbiosname)

        if (self.flags & FLAGS_CACHE_READ_USER) \
            and self.__ucache.has_key(self.__ukey):
            log.debug("FreeNAS_ActiveDirectory_User.__get_user: " \
                "user in cache")
            self._pw = self.__ucache[self.__ukey]
            return self.__ucache[self.__ukey]

        pw = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (self.flags & FLAGS_CACHE_READ_USER) \
            and self.__ducache.has_key(self.__dukey):
            log.debug("FreeNAS_ActiveDirectory_User.__get_user: " \
                "AD user in cache")
            ad_user = self.__ducache[self.__dukey]

        else:
            log.debug("FreeNAS_ActiveDirectory_User.__get_user: " \
                "AD user not in cache")
            ad_user = self.get_user(user)

        if self.use_default_domain:
            u = "{}".format(ad_user[1]['sAMAccountName'][0] \
                if ad_user else user)
        elif not ad_user:
            u = user
        else:
            u = "{}{}{}".format(
                netbiosname,
                FREENAS_AD_SEPARATOR,
               ad_user[1]['sAMAccountName'][0] if ad_user else user
            )

        try:
            pw = pwd.getpwnam(u)

        except:
            pw = None

        if (self.flags & FLAGS_CACHE_WRITE_USER) and pw:
            self.__ucache[self.__ukey] = pw
            self.__ducache[self.__dukey] = ad_user

        self._pw = pw
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: leave")


class FreeNAS_Directory_User(object):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_Directory_User.__new__: enter")
        log.debug("FreeNAS_Directory_User.__new__: user = %s", user)

        dflags = 0
        if kwargs.has_key('dflags'):
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_User(user, **kwargs)

        elif dflags & FLAGS_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_User(user, **kwargs)

        if obj and obj._pw is None:
            obj = None

        log.debug("FreeNAS_Directory_User.__new__: leave")
        return obj

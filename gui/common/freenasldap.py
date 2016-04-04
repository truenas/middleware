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
import ldap
import ldap.sasl
import logging
import os
import pwd
import socket
import string
import tempfile
import time
import types

from dns import resolver
from ldap.controls import SimplePagedResultsControl
from .log import log_traceback

from freenasUI.common.pipesubr import (
    pipeopen,
    run
)

from freenasUI.common.ssl import get_certificateauthority_path
from freenasUI.common.system import (
    get_freenas_var,
    get_freenas_var_by_file,
    ldap_objects,
    activedirectory_objects,
    get_hostname
)
from freenasUI.common.freenascache import (
    FreeNAS_UserCache,
    FreeNAS_GroupCache,
    FreeNAS_LDAP_QueryCache,
    FreeNAS_Directory_UserCache,
    FreeNAS_Directory_GroupCache,
    FLAGS_CACHE_READ_USER,
    FLAGS_CACHE_READ_GROUP,
    FLAGS_CACHE_WRITE_USER,
    FLAGS_CACHE_WRITE_GROUP
)

log = logging.getLogger('common.freenasldap')

FREENAS_LDAP_NOSSL = " off"
FREENAS_LDAP_USESSL = "on"
FREENAS_LDAP_USETLS = "start_tls"

FREENAS_LDAP_PORT = get_freenas_var("FREENAS_LDAP_PORT", 389)
FREENAS_LDAP_SSL_PORT = get_freenas_var("FREENAS_LDAP_SSL_PORT", 636)

FREENAS_AD_SEPARATOR = get_freenas_var("FREENAS_AD_SEPARATOR", '\\')
FREENAS_AD_CONFIG_FILE = get_freenas_var(
    "AD_CONFIG_FILE",
    "/etc/directoryservice/ActiveDirectory/config"
)

FREENAS_LDAP_CACHE_EXPIRE = get_freenas_var("FREENAS_LDAP_CACHE_EXPIRE", 60)
FREENAS_LDAP_CACHE_ENABLE = get_freenas_var("FREENAS_LDAP_CACHE_ENABLE", 1)

FREENAS_LDAP_VERSION = ldap.VERSION3
FREENAS_LDAP_REFERRALS = get_freenas_var("FREENAS_LDAP_REFERRALS", 0)

FREENAS_LDAP_PAGESIZE = get_freenas_var("FREENAS_LDAP_PAGESIZE", 1024)

ldap.protocol_version = FREENAS_LDAP_VERSION
ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

FLAGS_DBINIT = 0x00010000
FLAGS_AD_ENABLED = 0x00100000
FLAGS_LDAP_ENABLED = 0x00200000
FLAGS_PREFER_IPv6 = 0x00400000
FLAGS_SASL_GSSAPI = 0x00800000


class FreeNAS_LDAP_Directory_Exception(Exception):
    pass


class FreeNAS_ActiveDirectory_Exception(FreeNAS_LDAP_Directory_Exception):
    pass


class FreeNAS_LDAP_Exception(FreeNAS_LDAP_Directory_Exception):
    pass


class FreeNAS_LDAP_Directory(object):
    @staticmethod
    def validate_credentials(
        hostname, port=389, basedn=None, binddn=None, bindpw=None, ssl='off',
        certfile=None, errors=[]
    ):
        ret = None

        f = FreeNAS_LDAP(
            host=hostname, port=port, binddn=binddn, bindpw=bindpw,
            basedn=basedn, certfile=certfile, ssl=ssl
        )
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
        if 'port' in kwargs and kwargs['port'] is not None:
            self.port = long(kwargs['port'])

        self.binddn = kwargs.get('binddn', None)
        self.bindpw = kwargs.get('bindpw', None)
        self.basedn = kwargs.get('basedn', None)
        self.anonbind = kwargs.get('anonbind', False)

        self.ssl = FREENAS_LDAP_NOSSL
        if 'ssl' in kwargs and kwargs['ssl'] is not None:
            self.ssl = kwargs['ssl']
            if self.ssl == FREENAS_LDAP_USESSL and self.port is None:
                self.port = FREENAS_LDAP_SSL_PORT
        self.certfile = kwargs.get('certfile', None)

        if self.port is None:
            self.port = FREENAS_LDAP_PORT

        self.scope = ldap.SCOPE_SUBTREE
        if 'scope' in kwargs and kwargs['scope'] is not None:
            self.scope = kwargs['scope']

        self.filter = kwargs.get('filter', None)
        self.attributes = kwargs.get('attributes', None)

        self.pagesize = 0
        if 'pagesize' in kwargs and kwargs['pagesize'] is not None:
            self.pagesize = kwargs['pagesize']

        self.flags = 0
        if 'flags' in kwargs and kwargs['flags'] is not None:
            self.flags = kwargs['flags']

        self._handle = None
        self._isopen = False
        self._cache = FreeNAS_LDAP_QueryCache()
        self._settings = []

        log.debug(
            "FreeNAS_LDAP_Directory.__init__: "
            "host = %s, port = %ld, binddn = %s, basedn = %s, ssl = %s",
            self.host, self.port, self.binddn, self.basedn, self.ssl
        )
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
                log.debug(
                    "FreeNAS_LDAP_Directory[ERROR]: info: '%s'",
                    e['info']
                )
            if e.has_key('desc'):
                log.debug(
                    "FreeNAS_LDAP_Directory[ERROR]: desc: '%s'",
                    e['desc']
                )

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

    def _do_authenticated_bind(self):
        log.debug(
            "FreeNAS_LDAP_Directory.open: "
            "(authenticated bind) trying to bind to %s:%d",
            self.host, self.port
        )
        return self._handle.simple_bind_s(self.binddn, self.bindpw)

    def _do_anonymous_bind(self):
        log.debug(
            "FreeNAS_LDAP_Directory.open: "
            "(anonymous bind) trying to bind to %s:%d",
            self.host, self.port
        )
        return self._handle.simple_bind_s()

    def _do_sasl_gssapi_bind(self):
        log.debug(
            "FreeNAS_LDAP_Directory.open: "
            "(sasl gssapi bind) trying to bind to %s:%d",
            self.host, self.port
        )
        auth_tokens = ldap.sasl.gssapi()

        res = self._handle.sasl_interactive_bind_s('', auth_tokens)
        if res == 0:
            log.debug(
                "FreeNAS_LDAP_Directory.open: (sasl gssapi bind) successful"
            )
            return True

        log.debug(
            "FreeNAS_LDAP_Directory.open: "
            "SASL/GSSAPI bind failed, trying simple bind"
        )

        if self.binddn and self.bindpw:
            res = self._do_authenticated_bind()
            if res:
                return res

            log.debug(
                "FreeNAS_LDAP_Directory.open: "
                "authenticated bind failed, trying simple bind"
            )

        return self._do_anonymous_bind()

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
            self._handle.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)
            self._handle.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)

            if self.ssl in (FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                self._handle.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                if self.certfile:
                    self._handle.set_option(
                        ldap.OPT_X_TLS_CACERTFILE,
                        self.certfile
                    )
                self._handle.set_option(
                    ldap.OPT_X_TLS_REQUIRE_CERT,
                    ldap.OPT_X_TLS_DEMAND
                )
                self._handle.set_option(
                    ldap.OPT_X_TLS_NEWCTX,
                    ldap.OPT_X_TLS_DEMAND
                )

            if self.ssl == FREENAS_LDAP_USETLS:
                try:
                    self._handle.start_tls_s()
                    log.debug("FreeNAS_LDAP_Directory.open: started TLS")

                except ldap.LDAPError as e:
                    self._logex(e)
                    raise e

            bind_method = None
            if self.anonbind:
                bind_method = self._do_anonymous_bind
            elif self.flags & FLAGS_SASL_GSSAPI:
                bind_method = self._do_sasl_gssapi_bind
            elif self.binddn and self.bindpw:
                bind_method = self._do_authenticated_bind
            else:
                bind_method = self._do_anonymous_bind

            try:
                log.debug("FreeNAS_LDAP_Directory.open: trying to bind")
                res = bind_method()
                log.debug("FreeNAS_LDAP_Directory.open: binded")

            except ldap.LDAPError as e:
                log.debug(
                    "FreeNAS_LDAP_Directory.open: "
                    "could not bind to %s:%d (%s)",
                    self.host, self.port, e
                )
                self._logex(e)
                res = None
                raise e

            if res:
                self._isopen = True
                log.debug("FreeNAS_LDAP_Directory.open: connection open")

        log.debug("FreeNAS_LDAP_Directory.open: leave")
        return (self._isopen is True)

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

    def _search(
        self, basedn="", scope=ldap.SCOPE_SUBTREE, filter=None,
        attributes=None, attrsonly=0, serverctrls=None, clientctrls=None,
        timeout=-1, sizelimit=0
    ):
        log.debug("FreeNAS_LDAP_Directory._search: enter")
        log.debug(
            "FreeNAS_LDAP_Directory._search: basedn = '%s', filter = '%s'",
            basedn, filter
        )
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

        result = []
        results = []
        paged = SimplePagedResultsControl(
            criticality=False,
            size=self.pagesize,
            cookie=''
        )

        paged_ctrls = {
            SimplePagedResultsControl.controlType: SimplePagedResultsControl,
        }

        if self.pagesize > 0:
            log.debug(
                "FreeNAS_LDAP_Directory._search: pagesize = %d",
                self.pagesize
            )

            page = 0
            while True:
                log.debug(
                    "FreeNAS_LDAP_Directory._search: getting page %d",
                    page
                )
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

        log.debug("FreeNAS_LDAP_Directory._search: %d results", len(result))
        log.debug("FreeNAS_LDAP_Directory._search: leave")
        return result

    def search(self):
        log.debug("FreeNAS_LDAP_Directory.search: enter")
        isopen = self._isopen
        self.open()

        results = self._search(
            self.basedn, self.scope, self.filter, self.attributes
        )
        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Directory.search: leave")
        return results

    def _modify(self, dn, modlist):
        log.debug("FreeNAS_LDAP_Directory._modify: enter")
        if not self._isopen:
            return None

        res = self._handle.modify_ext_s(dn, modlist)

        log.debug("FreeNAS_LDAP_Directory._modify: leave")
        return res

    def modify(self, dn, modlist):
        log.debug("FreeNAS_LDAP_Directory.modify: enter")
        isopen = self._isopen
        self.open()

        res = self._modify(dn, modlist)

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Directory.modify: leave")
        return res


class FreeNAS_LDAP_Base(FreeNAS_LDAP_Directory):

    def __keys(self):
        return [
            'hostname',
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
            'sudosuffix',
            'certfile',
            'use_default_domain',
            'has_samba_schema',
            'kerberos_realm',
            'krb_realm',
            'krb_kdc',
            'krb_admin_server',
            'krb_kpasswd_server',
            'kerberos_keytab',
            'keytab_principal',
            'keytab_file',
            'idmap_backend',
            'timeout',
            'dns_timeout'
        ]

    def __set_defaults(self):
        log.debug("FreeNAS_LDAP_Base.__set_defaults: enter")

        for key in self.__keys():
            if key in ('anonbind', 'use_default_domain'):
                self.__dict__[key] = False
            elif key in ('timeout', 'dns_timeout'):
                self.__dict__[key] = 10
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

        if 'flags' in kwargs and (kwargs['flags'] & FLAGS_DBINIT):
            ldap = ldap_objects()[0]

            for key in ldap.__dict__.keys():
                if not key.startswith("ldap_"):
                    continue

                newkey = key.replace("ldap_", "")
                if newkey == 'hostname':
                    (host, port) = self.__name_to_host(ldap.__dict__[key])
                    if 'host' not in kwargs:
                        kwargs['host'] = host
                    if 'port' not in kwargs:
                        kwargs['port'] = port
                    kwargs[newkey] = ldap.__dict__[key]
                    if ldap.__dict__['ldap_ssl'] == FREENAS_LDAP_USESSL:
                        kwargs['port'] = 636

                elif newkey in (
                    'anonbind', 'use_default_domain', 'has_samba_schema'
                ):
                    if 'anonbind' not in kwargs:
                        kwargs[newkey] = (
                            False if long(ldap.__dict__[key]) == 0 else True
                        )
                    elif 'use_default_domain' not in kwargs:
                        kwargs[newkey] = (
                            False if long(ldap.__dict__[key]) == 0 else True
                        )
                    elif 'has_samba_schema' not in kwargs:
                        kwargs[newkey] = (
                            False if long(ldap.__dict__[key]) == 0 else True
                        )

                elif newkey == 'certificate_id':
                    cert = get_certificateauthority_path(ldap.ldap_certificate)
                    kwargs['certfile'] = cert

                elif newkey == 'kerberos_realm_id':
                    kr = ldap.ldap_kerberos_realm

                    if kr:
                        kwargs['kerberos_realm'] = kr
                        kwargs['krb_realm'] = kr.krb_realm
                        kwargs['krb_kdc'] = kr.krb_kdc
                        kwargs['krb_admin_server'] = kr.krb_admin_server
                        kwargs['krb_kpasswd_server'] = kr.krb_kpasswd_server

                elif newkey == 'kerberos_principal_id':
                    kp = ldap.ldap_kerberos_principal

                    if kp:
                        kwargs['kerberos_principal'] = kp
                        kwargs['keytab_principal'] = kp.principal_name
                        kwargs['keytab_file'] = '/etc/kerberos/%s' % kp.principal_keytab.keytab_name

                else:
                    if newkey not in kwargs:
                        kwargs[newkey] = (
                            ldap.__dict__[key] if ldap.__dict__[key] else None
                        )

        for key in kwargs:
            if key == 'flags':
                flags = self.flags
                flags |= long(kwargs[key])
                self.__dict__[key] = flags

            elif key in self.__keys():
                self.__dict__[key] = kwargs[key]

        super(FreeNAS_LDAP_Base, self).__init__(**kwargs)

        if self.kerberos_realm or self.keytab_principal:
            self.get_kerberos_ticket()
            self.flags |= FLAGS_SASL_GSSAPI

        self.ucount = 0
        self.gcount = 0

        log.debug("FreeNAS_LDAP_Base.__init__: leave")

    def kerberos_cache_has_ticket(self):
        res = False

        p = pipeopen("/usr/bin/klist -t")
        p.communicate()
        if p.returncode == 0:
            res = True

        return res

    def get_kerberos_principal_from_cache(self):
        principal = None

        p = pipeopen("klist")
        klist_out = p.communicate()
        if p.returncode != 0:
            return None

        klist_out = klist_out[0]
        lines = klist_out.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("Principal"):
                parts = line.split(':')
                if len(parts) > 1:
                    principal = parts[1].strip()

        return principal

    def get_kerberos_ticket(self):
        res = False
        kinit = False

        if self.keytab_principal:
            krb_principal = self.get_kerberos_principal_from_cache()
            if (
                krb_principal and
                krb_principal.upper() == self.keytab_principal.upper()
            ):
                return True

            args = [
                "/usr/bin/kinit",
                "--renewable",
                "-k",
                "-t",
                self.keytab_file,
                self.keytab_principal
            ]

            (returncode, stdout, stderr) = run(string.join(args, ' '), timeout=self.timeout)
            if returncode == 0:
                kinit = True
                res = True

        elif self.krb_realm and self.binddn and self.bindpw:
            user = self.get_user_by_DN(self.binddn)
            uid = user[1]['uid'][0]

            krb_principal = self.get_kerberos_principal_from_cache()
            principal = "%s@%s" % (uid, self.krb_realm)

            if krb_principal and krb_principal.upper() == principal.upper():
                return True

            (fd, tmpfile) = tempfile.mkstemp(dir="/tmp")
            os.fchmod(fd, 0600)
            os.write(fd, self.bindpw)
            os.close(fd)

            args = [
                "/usr/bin/kinit",
                "--renewable",
                "--password-file=%s" % tmpfile,
                "%s" % principal
            ]

            (returncode, stdout, stderr) = run(string.join(args, ' '), timeout=self.timeout)
            if returncode == 0:
                kinit = True
                res = True

            os.unlink(tmpfile)

        if kinit:
            i = 0
            while i < self.timeout:
                if self.kerberos_cache_has_ticket():
                    res = True
                    break

                time.sleep(1)
                i += 1

        return res

    def get_user_by_DN(self, DN):
        log.debug("FreeNAS_LDAP_Base.get_user_by_DN: enter")
        log.debug("FreeNAS_LDAP_Base.get_user_by_DN: DN = %s", DN)

        if DN is None:
            raise AssertionError('DN is None')

        isopen = self._isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        basedn = DN
        args = {'scope': scope, 'filter': '(objectclass=*)'}
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

        log.debug("FreeNAS_LDAP_Base.get_user_by_DN: leave")
        return ldap_user

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
            filter = '(&(|(objectclass=person)' \
                '(objectclass=posixaccount)' \
                '(objectclass=account))' \
                '(uidnumber=%d))' % user.encode('utf-8')

        elif user.isdigit():
            filter = '(&(|(objectclass=person)' \
                '(objectclass=posixaccount)' \
                '(objectclass=account))' \
                '(uidnumber=%s))' % user.encode('utf-8')
        else:
            filter = (
                '(&(|(objectclass=person)'
                '(objectclass=posixaccount)'
                '(objectclass=account))'
                '(|(uid=%s)(cn=%s)))'
            ) % (user.encode('utf-8'), user.encode('utf-8'))

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
        filter = '(&(|(objectclass=person)' \
            '(objectclass=posixaccount)' \
            '(objectclass=account))(uid=*))'

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
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(gidnumber=%d))' % group.encode('utf-8')

        elif group.isdigit():
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(gidnumber=%s))' % group.encode('utf-8')
        else:
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(cn=%s))' % group.encode('utf-8')

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
        filter = '(&(|(objectclass=posixgroup)' \
            '(objectclass=group))' \
            '(gidnumber=*))'

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

    def has_samba_schema(self):
        log.debug("FreeNAS_LDAP_Base.has_samba_schema: enter")
        isopen = self._isopen
        self.open()

        ret = False
        scope = ldap.SCOPE_SUBTREE

        filter = '(objectclass=sambaDomain)'
        results = self._search(self.basedn, scope, filter, self.attributes)
        if results:
            ret = True

        if not isopen:
            self.close()

        log.debug("FreeNAS_LDAP_Base.has_samba_schema: leave")
        return ret


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

        if len(srv_hosts) == 1:
            for s in srv_hosts:
                host = s.target.to_text(True)
                port = long(s.port)
                return (host, port)

        best_host = None
        latencies = {}

        def callback(host, port, duration):
            latencies.setdefault(host, 0)
            latencies[host] += duration

        for srv_host in srv_hosts:
            host = srv_host.target.to_text(True)
            port = long(srv_host.port)

            try:
                FreeNAS_ActiveDirectory_Base.AsyncConnect(
                    host, long(port), callback)
            except:
                log.debug(
                    "get_best_host: Unable to connect to %s:%d",
                    host, long(port)
                )

        count = len(srv_hosts)
        asyncore.loop(timeout=1, count=count)
        if not latencies:
            asyncore.loop(timeout=60)

        asyncore.close_all()
        latency_list = sorted(latencies.iteritems(), key=lambda (a, b): (b, a))
        if latency_list:
            for s in srv_hosts:
                host = s.target.to_text(True)
                port = long(s.port)
                if host.lower() == latency_list[0][0].lower():
                    best_host = (host, port)
                    break

        return best_host

    @staticmethod
    def get_A_records(host):
        A_records = []

        if not host:
            return A_records

        try:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_A_records: "
                "looking up A records for %s",
                host
            )
            A_records = resolver.query(host, 'A')

        except:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_A_records: "
                "no A records for %s found, fail!",
                host
            )
            A_records = []

        return A_records

    @staticmethod
    def get_AAAA_records(host):
        AAAA_records = []

        if not host:
            return AAAA_records

        try:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_AAAA_records: "
                "looking up AAAA records for %s",
                host
            )
            AAAA_records = resolver.query(host, 'AAAA')

        except:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_AAAA_records: "
                "no AAAA records for %s found, fail!",
                host
            )
            AAAA_records = []

        return AAAA_records

    @staticmethod
    def get_SRV_records(host):
        srv_records = []

        if not host:
            return srv_records

        try:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_SRV_records: "
                "looking up SRV records for %s",
                host
            )
            answers = resolver.query(host, 'SRV')
            srv_records = sorted(
                answers,
                key=lambda a: (int(a.priority), int(a.weight))
            )

        except:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_SRV_records: "
                "no SRV records for %s found, fail!",
                host
            )
            log_traceback(log=log)
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
    def get_domain_controllers(domain, site=None, ssl=FREENAS_LDAP_NOSSL):
        dcs = []
        if not domain:
            return dcs

        host = "_ldap._tcp.dc._msdcs.%s" % domain
        if site:
            host = "_ldap._tcp.%s._sites.dc._msdcs.%s" % (site, domain)

        dcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        if ssl == FREENAS_LDAP_USESSL:
            for dc in dcs:
                dc.port = 636

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
    def get_global_catalog_servers(domain, site=None, ssl=FREENAS_LDAP_NOSSL):
        gcs = []
        if not domain:
            return gcs

        host = "_gc._tcp.%s" % domain
        if site:
            host = "_gc._tcp.%s._sites.%s" % (site, domain)

        gcs = FreeNAS_ActiveDirectory_Base.get_SRV_records(host)
        if ssl == FREENAS_LDAP_USESSL:
            for gc in gcs:
                gc.port = 3269

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
    def validate_credentials(
        domain, site=None, binddn=None, bindpw=None, ssl='off', certfile=None,
        errors=[]
    ):
        ret = None
        best_host = None

        dcs = FreeNAS_ActiveDirectory_Base.get_domain_controllers(domain, site, ssl)
        if not dcs:
            raise FreeNAS_ActiveDirectory_Exception(
                "Unable to find domain controllers for %s" % domain
            )

        best_host = FreeNAS_ActiveDirectory_Base.get_best_host(dcs)
        if best_host:
            (dchost, dcport) = best_host
            f = FreeNAS_LDAP(
                host=dchost, port=dcport, binddn=binddn, bindpw=bindpw,
                ssl=ssl, certfile=certfile
            )
            try:
                f.open()
                ret = True

            except Exception as e:
                for error in e:
                    if isinstance(e, dict):
                        errors.append(error['desc'])
                    else:
                        errors.append(error)
                ret = False

        return ret

    @staticmethod
    def port_is_listening(host, port, errors=[]):
        ret = False

        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((host, port))
            ret = True

        except Exception as e:
            errors.append(e)
            ret = False

        s.close()
        return ret

    @staticmethod
    def get_workgroup_name(
        domain, site=None, binddn=None, bindpw=None, ssl='off', certfile=None,
        keytab_principal=None, keytab_file=None, errors=[]
    ):

        f = FreeNAS_ActiveDirectory(
            domainname=domain, site=site, binddn=binddn, bindpw=bindpw,
            ssl=ssl, certfile=certfile, keytab_principal=keytab_principal,
            keytab_file=keytab_file
        )
        return f.get_netbios_name()

    @staticmethod
    def adset(val, default=None):
        ret = default
        if val:
            ret = val
        return ret

    def __keys(self):
        return [
            'machine',
            'domainname',
            'netbiosname',
            'bindname',
            'bindpw',
            'ssl',
            'certfile',
            'verbose_logging',
            'unix_extensions',
            'allow_trusted_doms',
            'use_default_domain',
            'disable_freenas_cache',
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
            'kerberos_realm',
            'krb_realm',
            'kerberos_keytab',
            'keytab_principal',
            'keytab_file',
            'dchandle',
            'gchandle',
            'site',
            'flags'
        ]

    def __set_defaults(self):
        log.debug("FreeNAS_ActiveDirectory_Base.__set_defaults: enter")

        self.__dcname = None
        self.__gcname = None
        self.__krbname = None
        self.__kpwdname = None

        for key in self.__keys():
            if key in (
                'verbose_logging',
                'unix_extensions',
                'allow_trusted_doms',
                'use_default_domain',
                'disable_freenas_cache',
            ):
                self.__dict__[key] = False
            elif key in ('timeout', 'dns_timeout'):
                self.__dict__[key] = 10
            else:
                self.__dict__[key] = None

        if self.dcname:
            self.__dcname = self.dcname
        if self.gcname:
            self.__gcname = self.gcname
        if self.krbname:
            self.__krbname = self.krbname
        if self.kpwdname:
            self.__kpwdname = self.kpwdname

        self.pagesize = FREENAS_LDAP_PAGESIZE
        self.machine = "%s$" % get_hostname()

        # self.flags = FLAGS_SASL_GSSAPI
        self.flags = 0

        log.debug("FreeNAS_ActiveDirectory_Base.__set_defaults: leave")

    def __name_to_host(self, name, default_port=None):
        host = None
        port = None
        if name:
            parts = name.split(':')
            host = parts[0]
            if len(parts) > 1:
                port = long(parts[1])
        if not port:
            port = default_port
        return (host, port)

    def kerberos_cache_has_ticket(self):
        res = False

        p = pipeopen("/usr/bin/klist -t")
        p.communicate()
        if p.returncode == 0:
            res = True

        return res

    def get_kerberos_principal_from_cache(self):
        principal = None

        p = pipeopen("klist")
        klist_out = p.communicate()
        if p.returncode != 0:
            return None

        klist_out = klist_out[0]
        lines = klist_out.splitlines()
        for line in lines:
            line = line.strip()
            if line.startswith("Principal"):
                parts = line.split(':')
                if len(parts) > 1:
                    principal = parts[1].strip()

        return principal

    def get_kerberos_ticket(self):
        res = False
        kinit = False

        if self.keytab_principal:
            krb_principal = self.get_kerberos_principal_from_cache()
            if (
                krb_principal and
                krb_principal.upper() == self.keytab_principal.upper()
            ):
                return True

            args = [
                "/usr/bin/kinit",
                "--renewable",
                "-k",
                "-t",
                self.keytab_file,
                self.keytab_principal
            ]

            (returncode, stdout, stderr) = run(string.join(args, ' '), timeout=self.timeout)
            if returncode != 0:
                res = False

            if res is not False:
                kinit = True

        elif self.krb_realm and self.bindname and self.bindpw:
            krb_principal = self.get_kerberos_principal_from_cache()
            principal = "%s@%s" % (self.bindname, self.krb_realm)

            if krb_principal and krb_principal.upper() == principal.upper():
                return True

            (fd, tmpfile) = tempfile.mkstemp(dir="/tmp")
            os.fchmod(fd, 0600)
            os.write(fd, self.bindpw)
            os.close(fd)

            args = [
                "/usr/bin/kinit",
                "--renewable",
                "--password-file=%s" % tmpfile,
                "%s" % principal
            ]

            (returncode, stdout, stderr) = run(string.join(args, ' '), timeout=self.timeout)
            if returncode != 0:
                res = False

            if res is not False:
                kinit = True

            os.unlink(tmpfile)

        if kinit:
            i = 0
            while i < self.timeout:
                if self.kerberos_cache_has_ticket():
                    res = True
                    break

                time.sleep(1)
                i += 1

        return res

    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.__init__: enter")

        self.kwargs = kwargs
        self.__set_defaults()

        super(FreeNAS_ActiveDirectory_Base, self).__init__()

        self.set_kwargs()

        if self.bindname and self.domainname:
            self.binddn = self.adset(
                self.binddn,
                self.bindname + '@' + self.domainname.upper()
            )

        self.load_config()

        # here we open a connection
        self.get_kerberos_ticket()
        self.set_servers()

        # get_baseDN() requires an open connection
        self.basedn = self.adset(self.basedn, self.get_baseDN())
        self.netbiosname = self.get_netbios_name()

        self.ucount = 0
        self.gcount = 0

        if not self.site:

            # locate_site() requires an open connection
            self.site = self.locate_site()
            if self.site:

                # requires an open connection
                self.reset_servers()
                self.set_servers()

        log.debug("FreeNAS_ActiveDirectory_Base.__init__: leave")

    def set_kwargs(self):
        kwargs = self.kwargs

        if 'flags' in kwargs and (kwargs['flags'] & FLAGS_DBINIT):
            ad = activedirectory_objects()[0]
            for key in ad.__dict__.keys():
                if not key.startswith("ad_"):
                    continue

                newkey = key.replace("ad_", "")
                if newkey in (
                    'verbose_logging',
                    'unix_extensions',
                    'allow_trusted_doms',
                    'use_default_domain',
                    'disable_freenas_cache',
                ):
                    kwargs[newkey] = (
                        False if long(ad.__dict__[key]) == 0 else True
                    )

                elif newkey == 'certificate_id':
                    cert = get_certificateauthority_path(ad.ad_certificate)
                    kwargs['certfile'] = cert

                elif newkey == 'kerberos_realm_id':
                    kr = ad.ad_kerberos_realm

                    if kr:
                        kwargs['kerberos_realm'] = kr
                        kwargs['krb_realm'] = kr.krb_realm
                        # self.flags |= FLAGS_SASL_GSSAPI

                elif newkey == 'kerberos_principal_id':
                    kp = ad.ad_kerberos_principal

                    if kp:
                        kwargs['kerberos_principal'] = kp
                        kwargs['keytab_principal'] = kp.principal_name
                        kwargs['keytab_file'] = '/etc/kerberos/%s' % kp.principal_keytab.keytab_name
                        # self.flags |= FLAGS_SASL_GSSAPI

                else:
                    kwargs[newkey] = ad.__dict__[key] \
                        if ad.__dict__[key] else None

            from freenasUI.services.models import CIFS
            cifs = CIFS.objects.latest('id')
            if not cifs:
                cifs = CIFS.objects.create()
            kwargs['machine'] = "%s$" % cifs.get_netbiosname()

        for key in kwargs:
            if key == 'flags':
                flags = self.flags
                flags |= long(kwargs[key])
                self.__dict__[key] = flags

            elif key in self.__keys():
                self.__dict__[key] = kwargs[key]

    def configval(self, var):
        return get_freenas_var_by_file(FREENAS_AD_CONFIG_FILE, var)

    def load_config(self):
        if not os.path.exists(FREENAS_AD_CONFIG_FILE):
            return

        for var in self.__keys():
            val = self.configval("ad_%s" % var)
            if val:
                setattr(self, var, val)

    def set_domain_controller(self):
        if self.dcname:
            (self.dchost, self.dcport) = self.__name_to_host(self.dcname, 389)
        if not self.dchost:
            dcs = self.get_domain_controllers(self.domainname, site=self.site, ssl=self.ssl)
            if not dcs:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % self.domainname)
            (self.dchost, self.dcport) = self.get_best_host(dcs)
            self.dcname = "%s:%d" % (self.dchost, self.dcport)

    def set_global_catalog_server(self):
        if self.gcname:
            (self.gchost, self.gcport) = self.__name_to_host(self.gcname, 3268)
        if not self.gchost:
            root = self.get_root_domain()
            if root:
                gcs = self.get_global_catalog_servers(root, site=self.site, ssl=self.ssl)
                if not gcs:
                    raise FreeNAS_ActiveDirectory_Exception(
                        "Unable to find global catalog servers for %s" % root
                    )
                (self.gchost, self.gcport) = self.get_best_host(gcs)
                self.gcname = "%s:%d" % (self.gchost, self.gcport)

    def set_kerberos_server(self):
        if self.krbname:
            (self.krbhost, self.krbport) = self.__name_to_host(self.krbname, 88)
        if not self.krbhost:
            krbs = self.get_kerberos_servers(self.domainname, site=self.site)
            if not krbs:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find kerberos servers for %s" % self.domainname
                )
            (self.krbhost, self.krbport) = self.get_best_host(krbs)
            self.krbname = "%s:%d" % (self.krbhost, self.krbport)

    def set_kpasswd_server(self):
        if self.kpwdname:
            (self.kpwdhost, self.kpwdport) = self.__name_to_host(
                self.kpwdname, 464)
        if not self.kpwdhost:
            kpwds = self.get_kpasswd_servers(self.domainname)
            if not kpwds:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find kerberos password servers for %s" % self.domainname)
            (self.kpwdhost, self.kpwdport) = self.get_best_host(kpwds)
            self.kpwdname = "%s:%d" % (self.kpwdhost, self.kpwdport)

    def set_servers(self):
        self.set_domain_controller()
        self.set_kerberos_server()
        self.set_kpasswd_server()

        flags = self.flags & ~ FLAGS_SASL_GSSAPI
        if self.keytab_principal:
            flags |= FLAGS_SASL_GSSAPI

        self.dchandle = FreeNAS_LDAP_Directory(
            binddn=self.binddn, bindpw=self.bindpw,
            host=self.dchost, port=self.dcport,
            ssl=self.ssl, certfile=self.certfile, flags=flags)
        self.dchandle.open()
        self.dchandle.pagesize = self.pagesize

        self.set_global_catalog_server()

        self.gchandle = FreeNAS_LDAP_Directory(
            binddn=self.binddn, bindpw=self.bindpw,
            host=self.gchost, port=self.gcport,
            ssl=self.ssl, certfile=self.certfile, flags=flags)
        self.gchandle.open()
        self.gchandle.pagesize = self.pagesize

    def reset_servers(self):
        self.dcname = self.dchost = self.dcport = None
        self.gcname = self.gchost = self.gcport = None
        self.krbname = self.krbhost = self.krbport = None
        self.kpwdname = self.kpwdhost = self.pwdport = None
        self.dchandle = self.gchandle = None

    def locate_site(self):
        from freenasUI.choices import NICChoices
        from freenasUI.middleware.notifier import notifier
        from freenasUI.common.sipcalc import sipcalc_type

        subnets = self.get_subnets()
        if not subnets:
            return None

        ipv4_candidates = {}
        ipv6_candidates = {}

        nics = NICChoices(exclude_configured=False)
        for n in nics:
            nic = n[0]
            iinfo = notifier().get_interface_info(nic)

            if iinfo['ipv4']:
                for i in iinfo['ipv4']:
                    nic_ipv4_st = sipcalc_type(i['inet'], i['netmask'])

                    for s in subnets:
                        if not s or len(s) < 2:
                            continue

                        network = site_dn = None
                        if 'cn' in s[1]:
                            network = s[1]['cn'][0]
                        if 'siteObject' in s[1]:
                            site_dn = s[1]['siteObject'][0]

                        st = sipcalc_type(network)
                        if st.is_ipv4():
                            if st.in_network(nic_ipv4_st):
                                if nic not in ipv4_candidates:
                                    ipv4_candidates[nic] = (site_dn, s, iinfo)

            if iinfo['ipv6']:
                for i in iinfo['ipv6']:
                    nic_ipv6_st = sipcalc_type("%s/%s" % (i['inet6'], i['prefixlen']))

                    for s in subnets:
                        if not s or len(s) < 2:
                            continue
                        network = site_dn = None

                        if 'cn' in s[1]:
                            network = s[1]['cn'][0]
                        if 'siteObject' in s[1]:
                            site_dn = s[1]['siteObject'][0]

                        st = sipcalc_type(network)
                        if st.is_ipv6():
                            if st.in_network(nic_ipv6_st):
                                if nic not in ipv6_candidates:
                                    ipv6_candidates[nic] = (site_dn, s, iinfo)

        ipv4_site = None
        ipv6_site = None

        for c in ipv4_candidates:
            (site_dn, s, iinfo) = ipv4_candidates[c]
            sinfo = self.get_sites(distinguishedname=site_dn)[0]
            if sinfo and len(sinfo) > 1:
                ipv4_site = sinfo[1]['cn'][0]
                break

        for c in ipv6_candidates:
            (site_dn, s, iinfo) = ipv6_candidates[c]
            sinfo = self.get_sites(distinguishedname=site_dn)[0]
            if sinfo and len(sinfo) > 1:
                ipv6_site = sinfo[1]['cn'][0]
                break

        if ipv4_site and ipv6_site and ipv4_site == ipv6_site:
            return ipv4_site

        if not ipv6_site and ipv4_site:
            return ipv4_site

        if not ipv4_site and ipv6_site:
            return ipv6_site

        return None

    def connected(self):
        return self.validate_credentials(
            self.domainname, site=self.site, ssl=self.ssl,
            certfile=self.certfile, binddn=self.binddn, bindpw=self.bindpw
        )

    def reload(self, **kwargs):
        self.kwargs.update(kwargs)
        self.__init__(**self.kwargs)

    def _search(
        self, handle, basedn="", scope=ldap.SCOPE_SUBTREE,
        filter=None, attributes=None, attrsonly=0, serverctrls=None,
        clientctrls=None, timeout=-1, sizelimit=0
    ):
        return handle._search(
            basedn, scope, filter, attributes, attrsonly, serverctrls,
            clientctrls, timeout, sizelimit
        )

    def _modify(self, handle, dn, modlist):
        return handle._modify(dn, modlist)

    def get_rootDSE(self):
        log.debug("FreeNAS_ActiveDirectory_Base.get_rootDSE: enter")

        results = self._search(
            self.dchandle, '', ldap.SCOPE_BASE, "(objectclass=*)"
        )

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
        results = self._search(
            self.dchandle, config, ldap.SCOPE_SUBTREE, filter
        )
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
        keys = [
            'netbiosname', 'name', 'cn', 'dn', 'distinguishedname', 'ncname'
        ]
        for k in keys:
            if k in kwargs:
                filter = "(%s=%s)" % (k, kwargs[k].encode('utf-8'))
                break

        if filter is None:
            filter = "(cn=*)"

        partitions = []
        results = self._search(
            self.dchandle, basedn, ldap.SCOPE_SUBTREE, filter
        )
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
        results = self._search(
            self.gchandle, "", ldap.SCOPE_SUBTREE, '(objectclass=domain)',
            ['dn']
        )
        if not results:
            log.debug(
                "FreeNAS_ActiveDirectory_Base.get_domains: "
                "no domain objects found"
            )
            results = []

        for r in results:
            domains.append(r[0])

        rootDSE = self.get_rootDSE()
        basedn = rootDSE[0][1]['configurationNamingContext'][0]
        # config = rootDSE[0][1]['defaultNamingContext'][0]

        if not self.allow_trusted_doms and self.netbiosname:
            kwargs['netbiosname'] = self.netbiosname

        result = []
        haskey = False
        for d in domains:
            filter = None
            if len(kwargs) > 0:
                haskey = True
                keys = [
                    'netbiosname', 'name', 'cn', 'dn', 'distinguishedname',
                    'ncname'
                ]
                for k in keys:
                    if k in kwargs:
                        filter = "(&(objectcategory=crossref)(%s=%s))" % \
                            (k, kwargs[k].encode('utf-8'))
                        break

            if filter is None:
                filter = "(&(objectcategory=crossref)(nCName=%s))" % \
                    d.encode('utf-8')

            results = self._search(
                self.dchandle, basedn, ldap.SCOPE_SUBTREE, filter
            )
            if results and results[0][0]:
                r = {}
                for k in results[0][1].keys():
                    r[k] = results[0][1][k][0]
                result.append(r)

            if haskey:
                break

        log.debug("FreeNAS_ActiveDirectory_Base.get_domains: leave")
        return result

    def get_subnets(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_subnets: enter")

        config = self.get_config()
        basedn = "CN=Subnets,CN=Sites,%s" % config
        filter = '(objectClass=subnet)'

        keys = ['distinguishedname', 'cn', 'name', 'siteobjectbl']
        for k in keys:
            if k in kwargs and kwargs[k]:
                filter = "(&%s(%s=%s))" % (filter, k, kwargs[k])

        subnets = []
        results = self._search(
            self.dchandle, basedn, ldap.SCOPE_SUBTREE, filter
        )
        if results:
            for r in results:
                if r[0]:
                    subnets.append(r)

        log.debug("FreeNAS_ActiveDirectory_Base.get_subnets: leave")
        return subnets

    def get_sites(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory_Base.get_sites: enter")

        config = self.get_config()
        basedn = "CN=Sites,%s" % config
        filter = '(objectClass=site)'

        keys = ['distinguishedname', 'cn', 'name', 'siteobjectbl']
        for k in keys:
            if k in kwargs and kwargs[k]:
                filter = "(&%s(%s=%s))" % (filter, k, kwargs[k])

        sites = []
        results = self._search(
            self.dchandle, basedn, ldap.SCOPE_SUBTREE, filter
        )
        if results:
            for r in results:
                if r[0]:
                    sites.append(r)

        log.debug("FreeNAS_ActiveDirectory_Base.get_sites: leave")
        return sites

    def get_machine_account(self, machine=None):
        log.debug("FreeNAS_ActiveDirectory_Base.get_machine_account: enter")
        log.debug("FreeNAS_ActiveDirectory_Base.get_machine_account: user = %s", machine)

        if machine is None:
            machine = self.machine
        if not machine:
            raise AssertionError('machine is None')

        filter = '(&(objectClass=computer)(sAMAccountName=%s))' % machine
        results = self._search(
            self.dchandle, self.basedn, ldap.SCOPE_SUBTREE, filter
        )

        try:
            results = results[0][1]

        except:
            results = None

        log.debug("FreeNAS_ActiveDirectory_Base.get_machine_account: leave")
        return results

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
        results = self._search(
            self.dchandle, self.basedn, scope, filter, attributes
        )
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
        results = self._search(
            self.dchandle, self.basedn, scope, filter, self.attributes
        )
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
        if self.disable_freenas_cache:
            self.ucount = 0
            log.debug("FreeNAS_ActiveDirectory_Base.get_users: leave")
            return users
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(|(objectclass=user)(objectclass=person))' \
            '(sAMAccountName=*))'
        if self.attributes and 'sAMAccountType' not in self.attributes:
            self.attributes.append('sAMAccountType')

        results = self._search(
            self.dchandle, self.basedn, scope, filter, self.attributes
        )
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
        log.debug(
            "FreeNAS_ActiveDirectory_Base.get_groupDN: group = %s",
            group
        )

        if group is None:
            raise AssertionError('group is None')

        if not self.binddn or not self.bindpw or not self.basedn:
            return None

        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=%s))' % \
            group.encode('utf-8')
        attributes = ['distinguishedName']
        results = self._search(
            self.dchandle, self.basedn, scope, filter, attributes
        )
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
        results = self._search(
            self.dchandle, self.basedn, scope, filter, self.attributes
        )
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
        if self.disable_freenas_cache:
            self.gcount = 0
            log.debug("FreeNAS_ActiveDirectory_Base.get_groups: leave")
            return groups
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=group)(sAMAccountName=*))'
        if self.attributes and 'groupType' not in self.attributes:
            self.attributes.append('groupType')

        results = self._search(
            self.dchandle, self.basedn, scope, filter, self.attributes
        )
        if results:
            for r in results:
                if r[0]:
                    type = int(r[1]['groupType'][0])
                    if not (type & 0x1):
                        groups.append(r)

        self.gcount = len(groups)
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

    def disable_machine_account(self, machine=None):
        log.debug("FreeNAS_ActiveDirectory_Base.disable_machine_account: enter")
        log.debug(
            "FreeNAS_ActiveDirectory_Base.disable_machine_account: machine = %s",
            machine
        )

        res = False
        results = self.get_machine_account(machine)
        if not results:
            return res

        userAccountControl = 0
        distinguishedName = None

        try:
            userAccountControl = long(results['userAccountControl'][0])
            distinguishedName = results['distinguishedName'][0]

        except:
            userAccountControl = 0
            distinguishedName = None

        if not distinguishedName:
            return res

        if not (userAccountControl & 0x2):
            userAccountControl |= 0x2
            try:
                ret = self._modify(
                    self.dchandle,
                    distinguishedName,
                    [(
                        ldap.MOD_REPLACE,
                        'userAccountControl',
                        str(userAccountControl)
                    )]
                )
                if ret:
                    res = True

            except Exception as e:
                log.debug("ldap modify error: %s", e)
                res = False

        log.debug("FreeNAS_ActiveDirectory_Base.disable_machine_account: leave")
        return res

    def enable_machine_account(self, machine=None):
        log.debug("FreeNAS_ActiveDirectory_Base.enable_machine_account: enter")
        log.debug(
            "FreeNAS_ActiveDirectory_Base.enable_machine_account: machine = %s",
            machine
        )

        res = False
        results = self.get_machine_account(machine)
        if not results:
            return res

        userAccountControl = 0
        distinguishedName = None

        try:
            userAccountControl = long(results['userAccountControl'][0])
            distinguishedName = results['distinguishedName'][0]

        except:
            userAccountControl = 0
            distinguishedName = None

        if not distinguishedName:
            return res

        if userAccountControl & 0x2:
            userAccountControl &= ~0x2
            try:
                ret = self._modify(
                    self.dchandle,
                    distinguishedName,
                    [(ldap.MOD_REPLACE, 'userAccountControl', str(userAccountControl))]
                )
                if ret:
                    res = True

            except Exception as e:
                log.debug("ldap modify error: %s", e)
                res = False

        log.debug("FreeNAS_ActiveDirectory_Base.enable_machine_account: leave")
        return res

    def joined(self):
        log.debug("FreeNAS_ActiveDirectory_Base.joined: enter")

        res = False
        results = self.get_machine_account()
        if not results:
            return res

        distinguishedName = None

        try:
            distinguishedName = results['distinguishedName'][0]

        except:
            distinguishedName = None

        if not distinguishedName:
            return res

        args = [
            "/usr/local/bin/net",
            "ads",
            "dn",
            distinguishedName,
            "-P",
            "-l"
        ]

        (returncode, stdout, stderr) = run(string.join(args, ' '), timeout=self.timeout)
        if returncode == 0:
            res = True

        log.debug("FreeNAS_ActiveDirectory_Base.joined: leave")
        return res


class FreeNAS_ActiveDirectory(FreeNAS_ActiveDirectory_Base):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_ActiveDirectory.__init__: enter")

        super(FreeNAS_ActiveDirectory, self).__init__(**kwargs)

        log.debug("FreeNAS_ActiveDirectory.__init__: leave")


class FreeNAS_LDAP_Users(FreeNAS_LDAP):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_LDAP_Users.__init__: enter")

        super(FreeNAS_LDAP_Users, self).__init__(**kwargs)

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
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
            log.debug(
                "FreeNAS_LDAP_Users.__get_users: LDAP users not in cache"
            )
            ldap_users = self.get_users()

        # parts = self.host.split('.')
        # host = parts[0].upper()
        for u in ldap_users:
            CN = str(u[0])
            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__ducache[CN] = u

            u = u[1]
            if u.has_key('sAMAccountName'):
                uid = u['sAMAccountName'][0]
            elif u.has_key('uid'):
                uid = u['uid'][0]
            else:
                uid = u['cn'][0]

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

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
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
                log.debug(
                    "FreeNAS_ActiveDirectory_Users.__get_users: users in cache"
                )
                log.debug("FreeNAS_ActiveDirectory_Users.__get_users: leave")
                return

        for d in self.__domains:
            n = d['nETBIOSName']
            self.__users[n] = []

            dcs = self.get_domain_controllers(d['dnsRoot'], ssl=self.ssl)
            if not dcs:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % d['dnsRoot'])
            (self.host, self.port) = self.get_best_host(dcs)

            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            if (
                (self.flags & FLAGS_CACHE_READ_USER) and
                self.__loaded('du', n)
            ):
                log.debug(
                    "FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users in cache",
                    n
                )
                ad_users = self.__ducache[n]

            else:
                log.debug(
                    "FreeNAS_ActiveDirectory_Users.__get_users: "
                    "AD [%s] users not in cache",
                    n
                )
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

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
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
            log.debug(
                "FreeNAS_LDAP_Groups.__get_groups: LDAP groups in cache"
            )
            ldap_groups = self.__dgcache

        else:
            log.debug(
                "FreeNAS_LDAP_Groups.__get_groups: LDAP groups not in cache"
            )
            ldap_groups = self.get_groups()

        # parts = self.host.split('.')
        # host = parts[0].upper()
        for g in ldap_groups:
            CN = str(g[0])
            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__dgcache[CN] = g

            g = g[1]
            if g.has_key('sAMAccountName'):
                cn = g['sAMAccountName'][0]
            else:
                cn = g['cn'][0]

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

        if 'netbiosname' in kwargs and kwargs['netbiosname']:
            self.__domains = self.get_domains(
                netbiosname=kwargs['netbiosname'])
        else:
            self.__domains = self.get_domains()

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
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
                log.debug(
                    "FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "groups in cache"
                )
                log.debug(
                    "FreeNAS_ActiveDirectory_Groups.__get_groups: leave"
                )
                return

        for d in self.__domains:
            n = d['nETBIOSName']
            self.__groups[n] = []

            dcs = self.get_domain_controllers(d['dnsRoot'], ssl=self.ssl)
            if not dcs:
                raise FreeNAS_ActiveDirectory_Exception(
                    "Unable to find domain controllers for %s" % d['dnsRoot'])
            (self.host, self.port) = self.get_best_host(dcs)

            self.basedn = d['nCName']
            self.attributes = ['sAMAccountName']
            self.pagesize = FREENAS_LDAP_PAGESIZE

            if (
                (self.flags & FLAGS_CACHE_READ_GROUP) and
                self.__loaded('dg', n)
            ):
                log.debug(
                    "FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups in cache",
                    n
                )
                ad_groups = self.__dgcache[n]

            else:
                log.debug(
                    "FreeNAS_ActiveDirectory_Groups.__get_groups: "
                    "AD [%s] groups not in cache",
                    n
                )
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
        if 'dflags' in kwargs:
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

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_Directory_GroupCache()
            if self.groupsuffix and self.basedn:
                self.__key = str("cn=%s,%s,%s" % (
                    group, self.groupsuffix, self.basedn
                ))
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

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            self.__gcache.has_key(group)
        ):
            log.debug("FreeNAS_LDAP_Group.__get_group: group in cache")
            return self.__gcache[group]

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            self.__dgcache.has_key(self.__key)
        ):
            log.debug("FreeNAS_LDAP_Group.__get_group: LDAP group in cache")
            ldap_group = self.__dgcache[self.__key]

        else:
            log.debug(
                "FreeNAS_LDAP_Group.__get_group: LDAP group not in cache"
            )
            ldap_group = self.get_group(group)

        if ldap_group:
            # parts = self.host.split('.')
            # host = parts[0].upper()

            cn = ldap_group[1]['cn'][0]
            try:
                gr = grp.getgrnam(cn)

            except:
                gr = None

        else:
            if type(group) in (
                types.IntType, types.LongType
            ) or group.isdigit():
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

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
            self.__gcache = FreeNAS_GroupCache(dir=netbiosname)
            self.__gkey = self.__group.encode('utf-8')
            self.__dgcache = FreeNAS_Directory_GroupCache(dir=netbiosname)
            self.__dgkey = self.get_groupDN(group)

        self.__get_group(group, netbiosname)

        log.debug("FreeNAS_ActiveDirectory_Group.__init__: leave")

    def __get_group(self, group, netbiosname):
        log.debug("FreeNAS_ActiveDirectory_Group.__get_group: enter")
        log.debug(
            "FreeNAS_ActiveDirectory_Group.__get_group: group = %s",
            group
        )
        log.debug(
            "FreeNAS_ActiveDirectory_Group.__get_group: netbiosname = %s",
            netbiosname
        )

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            self.__gcache.has_key(self.__gkey)
        ):
            log.debug(
                "FreeNAS_ActiveDirectory_User.__get_group: group in cache"
            )
            self._gr = self.__gcache[self.__gkey]
            return self.__gcache[self.__gkey]

        g = gr = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            self.__dgcache.has_key(self.__dgkey)
        ):
            log.debug(
                "FreeNAS_ActiveDirectory_Group.__get_group: "
                "AD group in cache"
            )
            ad_group = self.__dgcache[self.__dgkey]

        else:
            log.debug(
                "FreeNAS_ActiveDirectory_Group.__get_group: "
                "AD group not in cache"
            )
            ad_group = self.get_group(group)

        if not ad_group:
            g = group
        elif self.use_default_domain:
            g = "{}".format(
                ad_group[1]['sAMAccountName'][0] if ad_group else group
            )
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
        if 'dflags' in kwargs:
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

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_Directory_UserCache()
            if self.usersuffix and self.basedn:
                self.__key = str("uid=%s,%s,%s" % (
                    user, self.usersuffix, self.basedn
                ))
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

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            self.__ucache.has_key(user)
        ):
            log.debug("FreeNAS_LDAP_User.__get_user: user in cache")
            return self.__ucache[user]

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            self.__ducache.has_key(self.__key)
        ):
            log.debug("FreeNAS_LDAP_User.__get_user: LDAP user in cache")
            ldap_user = self.__ducache[self.__key]

        else:
            log.debug("FreeNAS_LDAP_User.__get_user: LDAP user not in cache")
            ldap_user = self.get_user(user)

        if ldap_user:
            self.__CN = ldap_user[0]

            # parts = self.host.split('.')
            # host = parts[0].upper()

            if ldap_user[1].has_key('sAMAccountName'):
                uid = ldap_user[1]['sAMAccountName'][0]
            elif ldap_user[1].has_key('uid'):
                uid = ldap_user[1]['uid'][0]
            else:
                uid = ldap_user[1]['cn'][0]

            try:
                pw = pwd.getpwnam(uid)

            except:
                pw = None

        else:
            if type(user) in (
                types.IntType, types.LongType
            ) or user.isdigit():
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

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
            self.__ucache = FreeNAS_UserCache(dir=netbiosname)
            self.__ukey = self.__user.encode('utf-8')
            self.__ducache = FreeNAS_Directory_UserCache(dir=netbiosname)
            self.__dukey = self.get_userDN(user)

        self.__get_user(user, netbiosname)

        log.debug("FreeNAS_ActiveDirectory_User.__init__: leave")

    def __get_user(self, user, netbiosname):
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: enter")
        log.debug("FreeNAS_ActiveDirectory_User.__get_user: user = %s", user)
        log.debug(
            "FreeNAS_ActiveDirectory_User.__get_user: netbiosname = %s",
            netbiosname
        )

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            self.__ucache.has_key(self.__ukey)
        ):
            log.debug(
                "FreeNAS_ActiveDirectory_User.__get_user: user in cache"
            )
            self._pw = self.__ucache[self.__ukey]
            return self.__ucache[self.__ukey]

        pw = None
        self.basedn = self.get_baseDN()
        self.attributes = ['sAMAccountName']

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            self.__ducache.has_key(self.__dukey)
        ):
            log.debug(
                "FreeNAS_ActiveDirectory_User.__get_user: AD user in cache"
            )
            ad_user = self.__ducache[self.__dukey]

        else:
            log.debug(
                "FreeNAS_ActiveDirectory_User.__get_user: "
                "AD user not in cache"
            )
            ad_user = self.get_user(user)

        if not ad_user:
            u = user
        elif self.use_default_domain:
            u = "{}".format(
                ad_user[1]['sAMAccountName'][0] if ad_user else user
            )
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

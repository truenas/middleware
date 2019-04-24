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
import grp
import ldap
import ldap.sasl
import logging
import os
import pwd
import tempfile
import time

from ldap.controls import SimplePagedResultsControl

from freenasUI.common.pipesubr import (
    pipeopen,
    run
)

from freenasUI.common.system import (
    get_freenas_var,
    ldap_objects,
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

from freenasUI.middleware.client import client

log = logging.getLogger('common.freenasldap')

FREENAS_LDAP_NOSSL = " off"
FREENAS_LDAP_USESSL = "on"
FREENAS_LDAP_USETLS = "start_tls"

FREENAS_LDAP_PORT = get_freenas_var("FREENAS_LDAP_PORT", 389)
FREENAS_LDAP_SSL_PORT = get_freenas_var("FREENAS_LDAP_SSL_PORT", 636)

FREENAS_LDAP_CACHE_EXPIRE = get_freenas_var("FREENAS_LDAP_CACHE_EXPIRE", 60)
FREENAS_LDAP_CACHE_ENABLE = get_freenas_var("FREENAS_LDAP_CACHE_ENABLE", 1)

FREENAS_LDAP_VERSION = ldap.VERSION3
FREENAS_LDAP_REFERRALS = get_freenas_var("FREENAS_LDAP_REFERRALS", 0)

FREENAS_LDAP_PAGESIZE = get_freenas_var("FREENAS_LDAP_PAGESIZE", 1024)

DS_DEBUG = False

ldap.protocol_version = FREENAS_LDAP_VERSION
ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)

FLAGS_DBINIT = 0x00010000
FLAGS_LDAP_ENABLED = 0x00200000
FLAGS_PREFER_IPv6 = 0x00400000
FLAGS_SASL_GSSAPI = 0x00800000


class FreeNAS_LDAP_Directory_Exception(Exception):
    pass


class FreeNAS_LDAP_Exception(FreeNAS_LDAP_Directory_Exception):
    pass


class FreeNAS_LDAP_Directory(object):
    @staticmethod
    def validate_credentials(
        hostname, port=389, basedn=None, binddn=None, bindpw=None, ssl='off',
        certfile=None, errors=[]
    ):
        FreeNAS_LDAP(
            host=hostname,
            port=port,
            binddn=binddn,
            bindpw=bindpw,
            basedn=basedn,
            certfile=certfile,
            ssl=ssl
        ).open()

    def __init__(self, **kwargs):
        self.host = kwargs.get('host', None)

        self.port = None
        if 'port' in kwargs and kwargs['port'] is not None:
            self.port = int(kwargs['port'])

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

        if DS_DEBUG:
            log.debug(
                "FreeNAS_LDAP_Directory.__init__: "
                "host = %s, port = %ld, binddn = %s, basedn = %s, ssl = %s",
                self.host, self.port, self.binddn, self.basedn, self.ssl
            )

    def _save(self):
        _s = {}
        _s.update(self.__dict__)
        self._settings.append(_s)

    def _restore(self):
        if self._settings:
            _s = self._settings.pop()
            self.__dict__.update(_s)

    def _logex(self, ex):
        log.debug("FreeNAS_LDAP_Directory[ERROR]: An LDAP Exception occured", exc_info=True)
        if not hasattr(ex, '__iter__'):
            log.debug('FreeNAS_LDAP_Directory[ERROR]: %s', ex, exc_info=True)
            return
        for e in ex:
            if 'info' in e:
                log.debug(
                    "FreeNAS_LDAP_Directory[ERROR]: info: '%s'",
                    e['info']
                )
            if 'desc' in e:
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
        if DS_DEBUG:
            log.debug(
                "FreeNAS_LDAP_Directory.open: "
                "(authenticated bind) trying to bind to %s:%d",
                self.host, self.port
            )
        return self._handle.simple_bind_s(self.binddn, self.bindpw)

    def _do_anonymous_bind(self):
        if DS_DEBUG:
            log.debug(
                "FreeNAS_LDAP_Directory.open: "
                "(anonymous bind) trying to bind to %s:%d",
                self.host, self.port
            )
        return self._handle.simple_bind_s()

    def _do_sasl_gssapi_bind(self):
        if DS_DEBUG:
            log.debug(
                "FreeNAS_LDAP_Directory.open: "
                "(sasl gssapi bind) trying to bind to %s:%d",
                self.host, self.port
            )
        auth_tokens = ldap.sasl.gssapi()

        res = self._handle.sasl_interactive_bind_s('', auth_tokens)
        if res == 0:
            if DS_DEBUG:
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
        if self._isopen:
            return True

        if self.host:
            uri = self._geturi()
            if DS_DEBUG:
                log.debug("FreeNAS_LDAP_Directory.open: uri = %s", uri)

            self._handle = ldap.initialize(self._geturi())
            if DS_DEBUG:
                log.debug("FreeNAS_LDAP_Directory.open: initialized")

        if self._handle:
            res = None
            ldap.protocol_version = FREENAS_LDAP_VERSION
            ldap.set_option(ldap.OPT_REFERRALS, FREENAS_LDAP_REFERRALS)
            ldap.set_option(ldap.OPT_NETWORK_TIMEOUT, 10.0)

            if self.ssl in (FREENAS_LDAP_USESSL, FREENAS_LDAP_USETLS):
                ldap.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                if self.certfile:
                    ldap.set_option(
                        ldap.OPT_X_TLS_CACERTFILE,
                        self.certfile
                    )
                ldap.set_option(
                    ldap.OPT_X_TLS_REQUIRE_CERT,
                    ldap.OPT_X_TLS_ALLOW
                )

            if self.ssl == FREENAS_LDAP_USETLS:
                try:
                    self._handle.start_tls_s()
                    if DS_DEBUG:
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
                if DS_DEBUG:
                    log.debug("FreeNAS_LDAP_Directory.open: trying to bind")
                res = bind_method()
                if DS_DEBUG:
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

        return (self._isopen is True)

    def unbind(self):
        if self._handle:
            self._handle.unbind()
            if DS_DEBUG:
                log.debug("FreeNAS_LDAP_Directory.unbind: unbind")

    def close(self):
        if self._isopen:
            self.unbind()
            self._handle = None
            self._isopen = False
            if DS_DEBUG:
                log.debug("FreeNAS_LDAP_Directory.close: connection closed")

    def _search(
        self, basedn="", scope=ldap.SCOPE_SUBTREE, filter=None,
        attributes=None, attrsonly=0, serverctrls=None, clientctrls=None,
        timeout=-1, sizelimit=0
    ):
        if DS_DEBUG:
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
            if DS_DEBUG:
                log.debug(
                    "FreeNAS_LDAP_Directory._search: pagesize = %d",
                    self.pagesize
                )

            page = 0
            while True:
                if DS_DEBUG:
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
            if DS_DEBUG:
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

        if DS_DEBUG:
            log.debug("FreeNAS_LDAP_Directory._search: %d results", len(result))
        return result

    def search(self):
        isopen = self._isopen
        self.open()

        results = self._search(
            self.basedn, self.scope, self.filter, self.attributes
        )
        if not isopen:
            self.close()

        return results

    def _modify(self, dn, modlist):
        if not self._isopen:
            return None

        res = self._handle.modify_ext_s(dn, modlist)

        return res

    def modify(self, dn, modlist):
        isopen = self._isopen
        self.open()

        res = self._modify(dn, modlist)

        if not isopen:
            self.close()

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
        for key in self.__keys():
            if key in ('anonbind', 'use_default_domain'):
                self.__dict__[key] = False
            elif key in ('timeout', 'dns_timeout'):
                self.__dict__[key] = 10
            else:
                self.__dict__[key] = None

        self.flags = 0

    def __name_to_host(self, name):
        host = None
        port = 389
        if name:
            parts = name.split(':')
            host = parts[0]
            if len(parts) > 1:
                port = int(parts[1])
        return (host, port)

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.__set_defaults()

        if 'flags' in kwargs and (kwargs['flags'] & FLAGS_DBINIT):
            ldap = ldap_objects()[0]

            for key in list(ldap.__dict__.keys()):
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
                            False if int(ldap.__dict__[key]) == 0 else True
                        )
                    elif 'use_default_domain' not in kwargs:
                        kwargs[newkey] = (
                            False if int(ldap.__dict__[key]) == 0 else True
                        )
                    elif 'has_samba_schema' not in kwargs:
                        kwargs[newkey] = (
                            False if int(ldap.__dict__[key]) == 0 else True
                        )

                elif newkey == 'certificate_id':
                    cert = None
                    if ldap.ldap_certificate:
                        with client as c:
                            cert = c.call(
                                'certificate.query',
                                [['id', '=', ldap.ldap_certificate.id]],
                                {'get': True}
                            )
                    kwargs['certfile'] = cert['certificate_path'] if cert else cert

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
                flags |= int(kwargs[key])
                self.__dict__[key] = flags

            elif key in self.__keys():
                self.__dict__[key] = kwargs[key]

        super(FreeNAS_LDAP_Base, self).__init__(**kwargs)

        if self.kerberos_realm or self.keytab_principal:
            self.get_kerberos_ticket()
            self.flags |= FLAGS_SASL_GSSAPI

        self.ucount = 0
        self.gcount = 0

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

            (returncode, stdout, stderr) = run(' '.join(args), timeout=self.timeout)
            if returncode == 0:
                kinit = True
                res = True

        elif self.krb_realm and self.binddn and self.bindpw:
            user = self.get_user_by_DN(self.binddn)

            try:
                uid = user[1]['uid'][0].decode('utf-8')
            except Exception:
                uid = user[1]['uid'][0]

            try:
                bindpw = self.bindpw.encode('utf-8')
            except Exception:
                bindpw = self.bindpw

            krb_principal = self.get_kerberos_principal_from_cache()
            principal = "%s@%s" % (uid, self.krb_realm)

            if krb_principal and krb_principal.upper() == principal.upper():
                return True

            (fd, fname) = tempfile.mkstemp(dir="/tmp", text=True)
            os.write(fd, bindpw)
            os.fchmod(fd, 0o777)
            os.close(fd)

            args = [
                "/usr/bin/kinit",
                "--renewable",
                "--password-file=%s" % fname,
                "%s" % principal
            ]

            (returncode, stdout, stderr) = run(' '.join(args), timeout=self.timeout)
            if returncode == 0:
                kinit = True
                res = True

            os.unlink(fname)

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
        if DS_DEBUG:
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

        return ldap_user

    def get_user(self, user):
        log.debug("FreeNAS_LDAP_Base.get_user: user = %s", user)

        if user is None:
            raise AssertionError('user is None')

        isopen = self._isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        if isinstance(user, int):
            filter = '(&(|(objectclass=person)' \
                '(objectclass=posixaccount)' \
                '(objectclass=account))' \
                '(uidnumber=%d))' % user

        elif user.isdigit():
            filter = '(&(|(objectclass=person)' \
                '(objectclass=posixaccount)' \
                '(objectclass=account))' \
                '(uidnumber=%s))' % user
        else:
            filter = (
                '(&(|(objectclass=person)'
                '(objectclass=posixaccount)'
                '(objectclass=account))'
                '(|(uid=%s)(cn=%s)))'
            ) % (user, user)

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

        return ldap_user

    def get_users(self):
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

        return users

    def get_group(self, group):
        log.debug("FreeNAS_LDAP_Base.get_group: group = %s", group)

        if group is None:
            raise AssertionError('group is None')

        isopen = self._isopen
        self.open()

        ldap_group = None
        scope = ldap.SCOPE_SUBTREE

        if isinstance(group, int):
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(gidnumber=%d))' % group

        elif group.isdigit():
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(gidnumber=%s))' % group
        else:
            filter = '(&(|(objectclass=posixgroup)' \
                '(objectclass=group))' \
                '(cn=%s))' % group

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

        return ldap_group

    def get_groups(self):
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

        return groups

    def get_domains(self):
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

        return domains

    def get_domain_names(self):
        domain_names = []
        domains = self.get_domains()
        if domains:
            for d in domains:
                domain_names.append(d[1]['sambaDomainName'][0])

        return domain_names

    def has_samba_schema(self):
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

        return ret


class FreeNAS_LDAP(FreeNAS_LDAP_Base):
    def __init__(self, **kwargs):
        super(FreeNAS_LDAP, self).__init__(**kwargs)


class FreeNAS_LDAP_Users(FreeNAS_LDAP):
    def __init__(self, **kwargs):
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

        except Exception:
            pass

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True

            except Exception:
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
        self.__usernames = []

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('u'):
            log.debug("FreeNAS_LDAP_Users.__get_users: users in cache")
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
            if 'sAMAccountName' in u:
                uid = u['sAMAccountName'][0].decode()
            elif 'uid' in u:
                uid = u['uid'][0].decode()
            else:
                uid = u['cn'][0].decode()

            self.__usernames.append(uid)

            try:
                pw = pwd.getpwnam(uid)
            except Exception:
                continue

            self.__users.append(pw)
            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__ucache[uid] = pw

            pw = None

        if self.flags & FLAGS_CACHE_WRITE_USER:
            self.__loaded('u', True)
            self.__loaded('du', True)


class FreeNAS_Directory_Users(object):
    def __new__(cls, **kwargs):
        dflags = 0
        if 'dflags' in kwargs:
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Users(**kwargs)

        return obj


class FreeNAS_LDAP_Groups(FreeNAS_LDAP):
    def __init__(self, **kwargs):
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

        except Exception:
            pass

        if file and write:
            try:
                with open(file, 'w+') as f:
                    f.close()
                ret = True

            except Exception:
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
        self.__groupnames = []

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('g'):
            log.debug("FreeNAS_LDAP_Groups.__get_groups: groups in cache")
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
            if 'sAMAccountName' in g:
                cn = g['sAMAccountName'][0].decode('utf8')
            else:
                cn = g['cn'][0].decode('utf8')

            self.__groupnames.append(cn)

            try:
                gr = grp.getgrnam(cn)

            except Exception:
                continue

            self.__groups.append(gr)

            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__gcache[cn] = gr

            gr = None

        if self.flags & FLAGS_CACHE_WRITE_GROUP:
            self.__loaded('g', True)
            self.__loaded('dg', True)


class FreeNAS_Directory_Groups(object):
    def __new__(cls, **kwargs):
        dflags = 0
        if 'dflags' in kwargs:
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Groups(**kwargs)

        return obj


class FreeNAS_LDAP_Group(FreeNAS_LDAP):
    def __init__(self, group, **kwargs):
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
            self.__get_group(group)

    def __get_group(self, group):
        log.debug("FreeNAS_LDAP_Group.__get_group: group = %s", group)

        gr = None
        self.attributes = ['cn']

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            group in self.__gcache
        ):
            log.debug("FreeNAS_LDAP_Group.__get_group: group in cache")
            return self.__gcache[group]

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) and
            self.__key in self.__dgcache
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

            cn = ldap_group[1]['cn'][0].decode('utf8')
            try:
                gr = grp.getgrnam(cn)

            except Exception:
                gr = None

        else:
            if type(group) is int or group.isdigit():
                try:
                    gr = grp.getgrgid(group)
                except Exception:
                    gr = None

            else:
                try:
                    gr = grp.getgrnam(group)

                except Exception:
                    gr = None

        if (self.flags & FLAGS_CACHE_WRITE_GROUP) and gr:
            self.__gcache[group] = gr
            self.__dgcache[self.__key] = ldap_group

        self._gr = gr


class FreeNAS_Directory_Group(object):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_Directory_Group.__new__: group = %s", group)

        dflags = 0
        if 'dflags' in kwargs:
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Group(group, **kwargs)

        if obj and obj._gr is None:
            obj = None

        return obj


class FreeNAS_LDAP_User(FreeNAS_LDAP):
    def __init__(self, user, **kwargs):
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
            self.__get_user(user)

    def __get_user(self, user):
        log.debug("FreeNAS_LDAP_User.__get_user: user = %s", user)

        pw = None
        self.attributes = ['uid']

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            user in self.__ucache
        ):
            log.debug("FreeNAS_LDAP_User.__get_user: user in cache")
            return self.__ucache[user]

        if (
            (self.flags & FLAGS_CACHE_READ_USER) and
            self.__key in self.__ducache
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

            if 'sAMAccountName' in ldap_user[1]:
                uid = ldap_user[1]['sAMAccountName'][0].decode('utf8')
            elif 'uid' in ldap_user[1]:
                uid = ldap_user[1]['uid'][0].decode('utf8')
            else:
                uid = ldap_user[1]['cn'][0].decode('utf8')

            try:
                pw = pwd.getpwnam(uid)
            except Exception:
                pw = None

        else:
            if type(user) is int or user.isdigit():
                try:
                    pw = pwd.getpwuid(user)
                except Exception:
                    pw = None

            else:
                try:
                    pw = pwd.getpwnam(user)

                except Exception:
                    pw = None

        if (self.flags & FLAGS_CACHE_WRITE_USER) and pw:
            self.__ucache[user] = pw
            self.__ducache[self.__key] = ldap_user

        self._pw = pw


class FreeNAS_Directory_User(object):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_Directory_User.__new__: user = %s", user)

        dflags = 0
        if 'dflags' in kwargs:
            dflags = kwargs['dflags']

        obj = None
        if dflags & FLAGS_LDAP_ENABLED:
            obj = FreeNAS_LDAP_User(user, **kwargs)

        if obj and obj._pw is None:
            obj = None

        return obj

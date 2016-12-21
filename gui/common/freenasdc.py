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
import grp
import os
import pwd
import middlewared.logger

from freenasUI.common.freenascache import *
from freenasUI.common.cmd import cmd_pipe

log = middlewared.logger.Logger('common.freenasdc')

WBINFO = "/usr/local/bin/wbinfo"
FREENAS_DOMAINCONTROLLER_SEPARATOR = '\\'


class dc_pipe(cmd_pipe):
    pass


class FreeNAS_DomainController_Base(object):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_Base.__init__: enter")

        self.flags = 0
        if 'flags' in kwargs and kwargs['flags']:
            self.flags = kwargs['flags']

        self.domain = None
        if 'domain' in kwargs and kwargs['domain']:
            self.domain = kwargs['domain']

        self._settings = []
        log.debug("FreeNAS_DomainController_Base.__init__: leave")

    def _save(self):
        _s = {}
        _s.update(self.__dict__)
        self._settings.append(_s)

    def _restore(self):
        if self._settings:
            _s = self._settings.pop()
            self.__dict__.update(_s)

    def _wbinfo(self, args):
        pobj = dc_pipe("%s %s" % (WBINFO, args))
        self._wberror = pobj.error

        return (pobj.returncode, str(pobj))

    def get_domains(self, domainname=None):
        log.debug("FreeNAS_DomainController_Base.get_domains: enter")

        domains = []
        (res, out) = self._wbinfo("--all-domains")
        if res == 0:
            for line in out.splitlines():
                domain = line.strip()
                if domainname:
                    if domain.lower() == domainname.lower():
                        domains.append(domain)
                else:
                    domains.append(domain)

        log.debug("FreeNAS_DomainController_Base.get_domains: leave")
        return domains

    def get_domain(self):
        log.debug("FreeNAS_DomainController_Base.get_domain: enter")

        domain = None
        (res, out) = self._wbinfo("--own-domain")
        if res == 0:
            domain = out.strip()

        log.debug("FreeNAS_DomainController_Base.get_domain: leave")
        return domain

    def get_user(self, who, domain=None):
        log.debug("FreeNAS_DomainController_Base.get_user: enter")
        log.debug("FreeNAS_DomainController_Base.get_user: who = '%s'", who)

        wbargs = "--user-info '%s'" % who
        if domain:
            wbargs += " --domain=%s" % domain

        user = None
        (wbres, wbout) = self._wbinfo(wbargs)
        if wbres == 0:
            parts = wbout.strip().split(':')
            if parts and len(parts) >= 7:
                user = {
                    "name": parts[0],
                    "sAMAccountName": parts[0],
                    "uid": parts[0],
                    "uidNumber": parts[2],
                    "gidNumber": parts[3],
                    "gecos": parts[4],
                    "homeDirectory": parts[5],
                    "loginShell": parts[6]
                }

        log.debug("FreeNAS_DomainController_Base.get_user: leave")
        return user

    def get_users(self, domain=None):
        log.debug("FreeNAS_DomainController_Base.get_users: enter")

        wbargs = "-u"
        if domain:
            wbargs += " --domain=%s" % domain

        users = []
        (wbres, wbout) = self._wbinfo(wbargs)
        if wbres == 0:
            for line in wbout.splitlines():
                (gres, gout) = self._wbinfo("--user-info '%s'" % line.strip())
                parts = gout.strip().split(':')
                if not parts or len(parts) < 7:
                    continue

                user = {
                    "name": parts[0],
                    "sAMAccountName": parts[0],
                    "uid": parts[0],
                    "uidNumber": parts[2],
                    "gidNumber": parts[3],
                    "gecos": parts[4],
                    "homeDirectory": parts[5],
                    "loginShell": parts[6]
                }
                users.append(user)

        log.debug("FreeNAS_DomainController_Base.get_users: leave")
        return users

    def get_group(self, who, domain=None):
        log.debug("FreeNAS_DomainController_Base.get_group: enter")
        log.debug("FreeNAS_DomainController_Base.get_group: who = '%s'", who)

        wbargs = "--group-info '%s'" % who
        if domain:
            wbargs += " --domain=%s" % domain

        group = None
        (wbres, wbout) = self._wbinfo(wbargs)
        if wbres == 0:
            parts = wbout.strip().split(':')
            if parts and len(parts) >= 4:
                group = {
                    "name": parts[0],
                    "sAMAccountName": parts[0],
                    "gidNumber": parts[2],
                    "members": parts[3]
                }

        log.debug("FreeNAS_DomainController_Base.get_group: leave")
        return group

    def get_groups(self, domain=None):
        log.debug("FreeNAS_DomainController_Base.get_groups: enter")

        wbargs = "-g"
        if domain:
            wbargs += " --domain=%s" % domain

        groups = []
        (wbres, wbout) = self._wbinfo(wbargs)
        if wbres == 0:
            for line in wbout.splitlines():
                (gres, gout) = self._wbinfo("--group-info '%s'" % line.strip())
                parts = gout.strip().split(':')
                if not parts or len(parts) < 4:
                    continue
                group = {
                    "name": parts[0],
                    "sAMAccountName": parts[0],
                    "gidNumber": parts[2],
                    "members": parts[3]
                }
                groups.append(group)

        log.debug("FreeNAS_DomainController_Base.get_groups: leave")
        return groups


class FreeNAS_DomainController(FreeNAS_DomainController_Base):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController.__init__: enter")

        super(FreeNAS_DomainController, self).__init__(**kwargs)

        log.debug("FreeNAS_DomainController.__init__: leave")


class FreeNAS_DomainController_Users(FreeNAS_DomainController):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_Users.__init__: enter")

        super(FreeNAS_DomainController_Users, self).__init__(**kwargs)

        self.__users = {}
        self.__ucache = {}
        self.__ducache = {}

        if 'domain' in kwargs and kwargs['domain']:
            self.__domains = self.get_domains(domain=kwargs['domain'])
        else:
            self.__domains = [self.get_domain()]

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
            for d in self.__domains:
                self.__ucache[d] = FreeNAS_UserCache(dir=d)
                self.__ducache[d] = FreeNAS_DomainController_UserCache(dir=d)

        self.__get_users()

        log.debug("FreeNAS_DomainController_Users.__init__: leave")

    def __loaded(self, index, domain, write=False):
        ret = False

        paths = {}
        ucachedir = self.__ucache[domain].cachedir
        paths['u'] = os.path.join(ucachedir, ".ul")

        ducachedir = self.__ducache[domain].cachedir
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

    def __get_users(self):
        log.debug("FreeNAS_DomainController_Users.__get_users: enter")

        if self.flags & FLAGS_CACHE_READ_USER:
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                if self.__loaded('u', d):
                    self.__users[d] = self.__ucache[d]
                    count += 1

            if count == dcount:
                log.debug("FreeNAS_DomainController_Users.__get_users: users in cache")
                log.debug("FreeNAS_DomainController_Users.__get_users: leave")
                return

        self._save()
        for d in self.__domains:
            self.__users[d] = []

            if (self.flags & FLAGS_CACHE_READ_USER) and self.__loaded('du', d):
                log.debug(
                    "FreeNAS_DomainController_Users.__get_users: "
                    "DomainController [%s] users in cache",
                    d
                )
                dc_users = self.__ducache[d]

            else:
                log.debug(
                    "FreeNAS_DomainController_Users.__get_users: "
                    "DomainController [%s] users not in cache",
                    d
                )
                dc_users = self.get_users(domain=d)

            for u in dc_users:
                uid = u['uid']

                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ducache[d][uid] = u

                sAMAccountName = u['sAMAccountName']
                try:
                    pw = pwd.getpwnam(sAMAccountName)

                except Exception, e:
                    log.debug("Error on getpwname: %s", e)
                    continue

                self.__users[d].append(pw)
                if self.flags & FLAGS_CACHE_WRITE_USER:
                    self.__ucache[d][sAMAccountName] = pw

                pw = None

            if self.flags & FLAGS_CACHE_WRITE_USER:
                self.__loaded('u', d, True)
                self.__loaded('du', d, True)

        self._restore()
        log.debug("FreeNAS_DomainController_Users.__get_users: leave")

    def __len__(self):
        length = 0
        for d in self.__domains:
            length += len(self.__users[d])
        return length

    def __iter__(self):
        for d in self.__domains:
            for user in self.__users[d]:
                yield user


class FreeNAS_DomainController_Groups(FreeNAS_DomainController):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_DomainController_Groups.__init__: enter")

        super(FreeNAS_DomainController_Groups, self).__init__(**kwargs)

        self.__groups = {}
        self.__gcache = {}
        self.__dgcache = {}

        if 'domain' in kwargs and kwargs['domain']:
            self.__domains = self.get_domains(domain=kwargs['domain'])
        else:
            self.__domains = [self.get_domain()]

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
            for d in self.__domains:
                self.__gcache[d] = FreeNAS_GroupCache(dir=d)
                self.__dgcache[d] = FreeNAS_DomainController_GroupCache(dir=d)

        self.__get_groups()

        log.debug("FreeNAS_DomainController_Groups.__init__: leave")

    def __loaded(self, index, domain=None, write=False):
        ret = False

        paths = {}
        gcachedir = self.__gcache[domain].cachedir
        paths['g'] = os.path.join(gcachedir, ".gl")

        dgcachedir = self.__dgcache[domain].cachedir
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
            length += len(self.__groups[d])
        return length

    def __iter__(self):
        for d in self.__domains:
            for group in self.__groups[d]:
                yield group

    def __get_groups(self):
        log.debug("FreeNAS_DomainController_Groups.__get_groups: enter")

        if (self.flags & FLAGS_CACHE_READ_GROUP):
            dcount = len(self.__domains)
            count = 0

            for d in self.__domains:
                if self.__loaded('u', d):
                    self.__groups[d] = self.__gcache[d]
                    count += 1

            if count == dcount:
                log.debug("FreeNAS_DomainController_Groups.__get_groups: groups in cache")
                log.debug("FreeNAS_DomainController_Groups.__get_groups: leave")
                return

        self._save()
        for d in self.__domains:
            self.__groups[d] = []

            if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__loaded('dg', d):
                log.debug(
                    "FreeNAS_DomainController_Groups.__get_groups: "
                    "DomainController [%s] groups in cache",
                    d
                )
                dc_groups = self.__dgcache[d]

            else:
                log.debug(
                    "FreeNAS_DomainController_Groups.__get_groups: "
                    "DomainController [%s] groups not in cache",
                    d
                )
                dc_groups = self.get_groups(domain=d)

            for g in dc_groups:
                sAMAccountName = g['sAMAccountName']

                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__dgcache[d][sAMAccountName.upper()] = g

                try:
                    gr = grp.getgrnam(sAMAccountName)

                except:
                    continue

                self.__groups[d].append(gr)
                if self.flags & FLAGS_CACHE_WRITE_GROUP:
                    self.__gcache[d][sAMAccountName.upper()] = gr

                gr = None

            if self.flags & FLAGS_CACHE_WRITE_GROUP:
                self.__loaded('g', d, True)
                self.__loaded('dg', d, True)

        self._restore()
        log.debug("FreeNAS_DomainController_Groups.__get_groups: leave")


class FreeNAS_DomainController_User(FreeNAS_DomainController):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_DomainController_User.__new__: enter")
        log.debug("FreeNAS_DomainController_User.__new__: user = %s", user)

        obj = None
        if user:
            user = user.encode('utf-8')
            parts = user.split(FREENAS_DOMAINCONTROLLER_SEPARATOR)
            if len(parts) > 1 and parts[1]:
                obj = super(FreeNAS_DomainController_User, cls).__new__(cls, **kwargs)

        log.debug("FreeNAS_DomainController_User.__new__: leave")
        return obj

    def __init__(self, user, **kwargs):
        log.debug("FreeNAS_DomainController_User.__init__: enter")
        log.debug("FreeNAS_DomainController_User.__init__: user = %s", user)

        parts = user.split(FREENAS_DOMAINCONTROLLER_SEPARATOR)
        domain = parts[0]

        self._pw = None

        kwargs['domain'] = domain
        super(FreeNAS_DomainController_User, self).__init__(**kwargs)

        if (
            (self.flags & FLAGS_CACHE_READ_USER) or
            (self.flags & FLAGS_CACHE_WRITE_USER)
        ):
            self.__ucache = FreeNAS_UserCache()
            self.__ducache = FreeNAS_DomainController_UserCache(dir=domain)
            self.__key = user

        self.__get_user(user, domain)

        log.debug("FreeNAS_DomainController_User.__init__: leave")

    def __get_user(self, user, domain):
        log.debug("FreeNAS_DomainController_User.__get_user: enter")
        log.debug("FreeNAS_DomainController_User.__get_user: user = %s", user)
        log.debug("FreeNAS_DomainController_User.__get_user: domain = %s", domain)

        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ucache.has_key(user):
            log.debug("FreeNAS_DomainController_User.__get_user: user in cache")
            return self.__ucache[user]

        pw = None
        if (self.flags & FLAGS_CACHE_READ_USER) and self.__ducache.has_key(self.__key):
            log.debug("FreeNAS_DomainController_User.__get_user: DomainController user in cache")
            dc_user = self.__ducache[self.__key]

        else:
            log.debug("FreeNAS_DomainController_User.__get_user: DomainController user not in cache")
            dc_user = self.get_user(user)

        u = dc_user['sAMAccountName']
        try:
            pw = pwd.getpwnam(u)

        except:
            pw = None

        if (self.flags & FLAGS_CACHE_WRITE_USER) and pw:
            self.__ucache[user] = pw
            self.__ducache[self.__key] = dc_user

        self._pw = pw
        log.debug("FreeNAS_DomainController_User.__get_user: leave")


class FreeNAS_DomainController_Group(FreeNAS_DomainController):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_DomainController_Group.__new__: enter")
        log.debug("FreeNAS_DomainController_Group.__new__: group = %s", group)

        obj = None
        if group:
            group = group.encode('utf-8')
            parts = group.split(FREENAS_DOMAINCONTROLLER_SEPARATOR)
            if len(parts) > 1 and parts[1]:
                obj = super(FreeNAS_DomainController_Group, cls).__new__(cls, **kwargs)

        log.debug("FreeNAS_DomainController_Group.__new__: leave")
        return obj

    def __init__(self, group, **kwargs):
        log.debug("FreeNAS_DomainController_Group.__init__: enter")
        log.debug("FreeNAS_DomainController_Group.__init__: group = %s", group)

        parts = group.split(FREENAS_DOMAINCONTROLLER_SEPARATOR)
        domain = parts[0]

        self._gr = None

        kwargs['domain'] = domain
        super(FreeNAS_DomainController_Group, self).__init__(**kwargs)

        if (
            (self.flags & FLAGS_CACHE_READ_GROUP) or
            (self.flags & FLAGS_CACHE_WRITE_GROUP)
        ):
            self.__gcache = FreeNAS_GroupCache()
            self.__dgcache = FreeNAS_DomainController_GroupCache(dir=domain)
            self.__key = group

        self.__get_group(group, domain)

        log.debug("FreeNAS_DomainController_Group.__init__: leave")

    def __get_group(self, group, domain):
        log.debug("FreeNAS_DomainController_Group.__get_group: enter")
        log.debug("FreeNAS_DomainController_Group.__get_group: group = %s", group)
        log.debug("FreeNAS_DomainController_Group.__get_group: domain = %s", domain)

        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__gcache.has_key(group):
            log.debug("FreeNAS_DomainController_User.__get_group: group in cache")
            return self.__gcache[group]

        g = gr = None
        if (self.flags & FLAGS_CACHE_READ_GROUP) and self.__dgcache.has_key(self.__key):
            log.debug("FreeNAS_DomainController_Group.__get_group: AD group in cache")
            dc_group = self.__dgcache[self.__key]

        else:
            log.debug("FreeNAS_DomainController_Group.__get_group: AD group not in cache")
            dc_group = self.get_group(group)

        g = dc_group['sAMAccountName']
        try:
            gr = grp.getgrnam(g)

        except:
            gr = None

        if (self.flags & FLAGS_CACHE_WRITE_GROUP) and gr:
            self.__gcache[group] = gr
            self.__dgcache[self.__key] = dc_group

        self._gr = gr
        log.debug("FreeNAS_DomainController_Group.__get_group: leave")

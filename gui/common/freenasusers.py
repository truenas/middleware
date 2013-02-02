#+
# Copyright 2011 iXsystems, Inc.
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
import logging
import pwd
import sqlite3
import types

from freenasUI.common.system import (activedirectory_enabled,
    ldap_enabled, nis_enabled, nt4_enabled, FREENAS_DATABASE)
from freenasUI.common.freenasldap import (FreeNAS_ActiveDirectory_Group,
    FreeNAS_ActiveDirectory_User, FreeNAS_ActiveDirectory_Groups,
    FreeNAS_ActiveDirectory_Users, FreeNAS_LDAP_Group, FreeNAS_LDAP_User,
    FreeNAS_LDAP_Groups, FreeNAS_LDAP_Users)
from freenasUI.common.freenasnt4 import (FreeNAS_NT4_Group,
    FreeNAS_NT4_User, FreeNAS_NT4_Groups, FreeNAS_NT4_Users)
from freenasUI.common.freenasnis import (FreeNAS_NIS_Group,
    FreeNAS_NIS_User, FreeNAS_NIS_Groups, FreeNAS_NIS_Users)

log = logging.getLogger("common.freenasusers")


U_AD_ENABLED	= 0x00000001
U_NT4_ENABLED	= 0x00000002
U_NIS_ENABLED	= 0x00000004
U_LDAP_ENABLED	= 0x00000008


def _get_dflags():
    dflags = 0

    if activedirectory_enabled():
        dflags |= U_AD_ENABLED
    elif nt4_enabled():
        dflags |= U_NT4_ENABLED
    elif nis_enabled():
        dflags |= U_NIS_ENABLED
    elif ldap_enabled():
        dflags |= U_LDAP_ENABLED

    return dflags


def bsdUsers_objects(**kwargs):
    h = sqlite3.connect(FREENAS_DATABASE)
    h.row_factory = sqlite3.Row
    c = h.cursor()

    sql = """
        SELECT
            bsdgrp_group, *

        FROM
            account_bsdusers

        INNER JOIN
            account_bsdgroups
        ON
            bsdusr_group_id = account_bsdgroups.id
    """

    count = len(kwargs)
    if count > 0:
        sql += " WHERE ("

        i = 0
        for k in kwargs.keys():
            sql += "%s = '%s'" % (k, kwargs[k])
            i += 1

            if i != count:
                sql += " AND "

        sql += ")"

    results = c.execute(sql)

    objects = []
    for row in results:
        obj = {}
        for key in row.keys():
            obj[key] = row[key]
        objects.append(obj)

    c.close()
    h.close()
    return objects


def bsdGroups_objects(**kwargs):
    h = sqlite3.connect(FREENAS_DATABASE)
    h.row_factory = sqlite3.Row
    c = h.cursor()

    sql = "SELECT * FROM account_bsdgroups"

    count = len(kwargs)
    if count > 0:
        sql += " WHERE ("

        i = 0
        for k in kwargs.keys():
            sql += "%s = '%s'" % (k, kwargs[k])
            i += 1

            if i != count:
                sql += " AND "

        sql += ")"

    results = c.execute(sql)

    objects = []
    for row in results:
        obj = {}
        for key in row.keys():
            obj[key] = row[key]
        objects.append(obj)

    c.close()
    h.close()
    return objects


class FreeNAS_Local_Group(object):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_Local_Group.__new__: enter")
        log.debug("FreeNAS_Local_Group.__new__: group = %s", group)

        obj = None
        if group is not None:
            obj = super(FreeNAS_Local_Group, cls).__new__(cls, **kwargs)

        log.debug("FreeNAS_Local_Group.__new__: leave")
        return obj

    def __init__(self, group, **kwargs):
        log.debug("FreeNAS_Local_Group.__init__: enter")
        log.debug("FreeNAS_Local_Group.__init__: group = %s", group)

        super(FreeNAS_Local_Group, self).__init__(**kwargs)

        self._gr = None
        if group is not None:
            self.__get_group(group)

        log.debug("FreeNAS_Local_Group.__init__: leave")

    def __get_group(self, group):
        log.debug("FreeNAS_local_Group.__get_group: enter")
        log.debug("FreeNAS_local_Group.__get_group: group = %s", group)

        grfunc = None
        if type(group) in (types.IntType, types.LongType) or group.isdigit():
            objects = bsdGroups_objects(bsdgrp_gid=group)
            grfunc = grp.getgrgid
            group = int(group)

        else:
            objects = bsdGroups_objects(bsdgrp_group=group)
            grfunc = grp.getgrnam

        if objects:
            group = objects[0]['bsdgrp_group']
            grfunc = grp.getgrnam

        try:
            self._gr = grfunc(group.encode('utf-8'))
        except Exception, e:
            log.debug("Exception on grfunc: %s", e)
            self._gr = None

        log.debug("FreeNAS_local_Group.__get_group: leave")


class FreeNAS_Group(object):
    def __new__(cls, group, **kwargs):
        log.debug("FreeNAS_Group.__new__: enter")
        log.debug("FreeNAS_Group.__new__: group = %s", group)

        dflags = _get_dflags()
        if kwargs.has_key('dflags') and kwargs['dflags']:
            dflags = kwargs['dflags']

        obj = None
        if dflags & U_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_Group(group, **kwargs)
        elif dflags & U_NT4_ENABLED:
            obj = FreeNAS_NT4_Group(group, **kwargs)
        elif dflags & U_NIS_ENABLED:
            obj = FreeNAS_NIS_Group(group, **kwargs)
        elif dflags & U_LDAP_ENABLED:
            obj = FreeNAS_LDAP_Group(group, **kwargs)

        if obj is None:
            obj = FreeNAS_Local_Group(group, **kwargs)

        if not obj or not obj._gr:
            obj = None

        if obj:
            obj = obj._gr

        log.debug("FreeNAS_Group.__new__: leave")
        return obj


class FreeNAS_Groups(object):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_Groups.__init__: enter")
        self.__groups = None

        """
        FreeNAS_Directory_Groups call may fail for several reasons
        For now lets just fail silently until we can come up with
        a better error handling

        TODO: Warn the user in the GUI that "something" happenned
        """

        dir = None
        dflags = _get_dflags()
        if dflags & U_AD_ENABLED:
            dir = FreeNAS_ActiveDirectory_Groups
        elif dflags & U_NT4_ENABLED:
            dir = FreeNAS_NT4_Groups
        elif dflags & U_NIS_ENABLED:
            dir = FreeNAS_NIS_Groups
        elif dflags & U_LDAP_ENABLED:
            dir = FreeNAS_LDAP_Groups

        if dir is not None:
            try:
                self.__groups = dir(**kwargs)

            except Exception, e:
                log.error("Directory Groups could not be retrieved: %s", str(e))
                self.__groups = None

        if self.__groups is None:
            self.__groups = []

        self.__bsd_groups = []
        objects = bsdGroups_objects()
        for obj in objects:
            self.__bsd_groups.append(FreeNAS_Group(obj['bsdgrp_group'], dflags=0))

        log.debug("FreeNAS_Groups.__init__: leave")

    def __len__(self):
        return len(self.__bsd_groups) + len(self.__groups)

    def __iter__(self):
        for gr in self.__bsd_groups:
            yield gr
        for gr in self.__groups:
            yield gr


class FreeNAS_Local_User(object):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_Local_User.__new__: enter")
        log.debug("FreeNAS_Local_User.__new__: user = %s", user)

        obj = None
        if user is not None:
            obj = super(FreeNAS_Local_User, cls).__new__(cls, **kwargs)

        log.debug("FreeNAS_Local_User.__new__: leave")
        return obj

    def __init__(self, user, **kwargs):
        log.debug("FreeNAS_Local_User.__init__: enter")
        log.debug("FreeNAS_Local_User.__init__: user = %s", user)

        super(FreeNAS_Local_User, self).__init__(**kwargs)

        self._pw = None
        if user is not None:
            self.__get_user(user)

        log.debug("FreeNAS_Local_User.__init__: leave")

    def __get_user(self, user):
        log.debug("FreeNAS_local_User.__get_user: enter")
        log.debug("FreeNAS_local_User.__get_user: user = %s", user)

        pwfunc = None
        if type(user) in (types.IntType, types.LongType) or user.isdigit():
            objects = bsdUsers_objects(bsdusr_uid=user)
            pwfunc = pwd.getpwuid
            user = int(user)

        else:
            objects = bsdUsers_objects(bsdusr_username=user)
            pwfunc = pwd.getpwnam

        if objects:
            user = objects[0]['bsdusr_username']
            pwfunc = pwd.getpwnam

        try:
            self._pw = pwfunc(user.encode('utf-8'))

        except Exception, e:
            log.debug("Exception on pwfunc: %s", e)
            self._pw = None

        log.debug("FreeNAS_local_User.__get_user: leave")


class FreeNAS_User(object):
    def __new__(cls, user, **kwargs):
        log.debug("FreeNAS_User.__new__: enter")
        log.debug("FreeNAS_User.__new__: user = %s", user)

        dflags = _get_dflags()
        if kwargs.has_key('dflags') and kwargs['dflags']:
            dflags = kwargs['dflags']

        obj = None
        if dflags & U_AD_ENABLED:
            obj = FreeNAS_ActiveDirectory_User(group, **kwargs)
        elif dflags & U_NT4_ENABLED:
            obj = FreeNAS_NT4_User(user, **kwargs)
        elif dflags & U_NIS_ENABLED:
            obj = FreeNAS_NIS_User(user, **kwargs)
        elif dflags & U_LDAP_ENABLED:
            obj = FreeNAS_LDAP_User(user, **kwargs)

        if not obj:
            obj = FreeNAS_Local_User(user, **kwargs)

        if not obj or not obj._pw:
            obj = None

        if obj:
            obj = obj._pw

        log.debug("FreeNAS_User.__new__: leave")
        return obj


class FreeNAS_Users(object):
    def __init__(self, **kwargs):
        log.debug("FreeNAS_Users.__init__: enter")
        self.__users = None

        """
        FreeNAS_Directory_Users call may fail for several reasons
        For now lets just fail silently until we can come up with
        a better error handling

        TODO: Warn the user in the GUI that "something" happenned
        """
        dir = None
        dflags = _get_dflags()
        if dflags & U_AD_ENABLED:
            dir = FreeNAS_ActiveDirectory_Users
        elif dflags & U_NT4_ENABLED:
            dir = FreeNAS_NT4_Users
        elif dflags & U_NIS_ENABLED:
            dir = FreeNAS_NIS_Users
        elif dflags & U_LDAP_ENABLED:
            dir = FreeNAS_LDAP_Users

        if dir is not None:
            try:
                self.__users = dir(**kwargs)

            except Exception, e:
                log.error("Directory Users could not be retrieved: %s", str(e))
                self.__users = None

        if self.__users is None:
            self.__users = []

        self.__bsd_users = []
        objects = bsdUsers_objects()
        for obj in objects:
            print obj
            self.__bsd_users.append(
                FreeNAS_User(obj['bsdusr_username'], dflags=0))

        log.debug("FreeNAS_Users.__init__: leave")

    def __len__(self):
        return len(self.__bsd_users) + len(self.__users)

    def __iter__(self):
        for pw in self.__bsd_users:
            yield pw
        for pw in self.__users:
            yield pw

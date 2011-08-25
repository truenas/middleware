#+
# Copyright 2011 iXsystems
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
from freenasUI.common.freenasldap import *


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
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__new__: group = %s" % group)

        obj = None
        if group is not None:
            obj = super(FreeNAS_Local_Group, cls).__new__(cls, **kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__new__: leave")
        return obj

    def __init__(self, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: group = %s" % group)

        super(FreeNAS_Local_Group, self).__init__(**kwargs)

        self._gr = None
        if group is not None:
            self.__get_group(group)

        syslog(LOG_DEBUG, "FreeNAS_Local_Group.__init__: leave")

    def __get_group(self, group):
        syslog(LOG_DEBUG, "FreeNAS_local_Group.__get_group: enter")
        syslog(LOG_DEBUG, "FreeNAS_local_Group.__get_group: user = %s" % group)

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
            self._gr = grfunc(group)

        except:
            self._gr = None

        syslog(LOG_DEBUG, "FreeNAS_local_Group.__get_group: leave")


class FreeNAS_Group(object):
    def __new__(cls, group, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: group = %s" % group)

        obj = FreeNAS_Directory_Group(group, **kwargs)
        if obj is None:
            obj = FreeNAS_Local_Group(group, **kwargs)

        if not obj or not obj._gr:
            obj = None

        if obj:
            obj = obj._gr

        syslog(LOG_DEBUG, "FreeNAS_Group.__new__: leave")
        return obj


class FreeNAS_Groups(object):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Groups.__init__: enter")

        self.__groups = FreeNAS_Directory_Groups(**kwargs)
        if self.__groups is None:
            self.__groups = []

        self.__bsd_groups = []
        objects = bsdGroups_objects()
        for obj in objects:
            self.__bsd_groups.append(FreeNAS_Group(obj['bsdgrp_group']))

        syslog(LOG_DEBUG, "FreeNAS_Groups.__init__: leave")

    def __len__(self):
        return len(self.__bsd_groups) + len(self.__groups)

    def __iter__(self):
        for gr in self.__bsd_groups:
            yield gr
        for gr in self.__groups:
            yield gr


class FreeNAS_Local_User(object):
    def __new__(cls, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__new__: user = %s" % user)

        obj = None
        if user is not None:
            obj = super(FreeNAS_Local_User, cls).__new__(cls, **kwargs)

        syslog(LOG_DEBUG, "FreeNAS_Local_User.__new__: leave")
        return obj

    def __init__(self, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: enter")
        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: user = %s" % user)

        super(FreeNAS_Local_User, self).__init__(**kwargs)

        self._pw = None
        if user is not None:
            self.__get_user(user)

        syslog(LOG_DEBUG, "FreeNAS_Local_User.__init__: leave")

    def __get_user(self, user):
        syslog(LOG_DEBUG, "FreeNAS_local_User.__get_user: enter")
        syslog(LOG_DEBUG, "FreeNAS_local_User.__get_user: user = %s" % user)

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
            self._pw = pwfunc(user)

        except:
            self._pw = None

        syslog(LOG_DEBUG, "FreeNAS_local_User.__get_user: leave")


class FreeNAS_User(object):
    def __new__(cls, user, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_User.__new__: enter")
        syslog(LOG_DEBUG, "FreeNAS_User.__new__: user = %s" % user)

        obj = FreeNAS_Directory_User(user, **kwargs)
        if not obj:
            obj = FreeNAS_Local_User(user, **kwargs)

        if not obj or not obj._pw:
            obj = None

        if obj:
            obj = obj._pw

        syslog(LOG_DEBUG, "FreeNAS_User.__new__: leave")
        return obj


class FreeNAS_Users(object):
    def __init__(self, **kwargs):
        syslog(LOG_DEBUG, "FreeNAS_Users.__init__: enter")

        self.__users = FreeNAS_Directory_Users(**kwargs)
        if self.__users is None:
            self.__users = []

        self.__bsd_users = []
        objects = bsdUsers_objects()
        for obj in objects:
            self.__bsd_users.append(FreeNAS_User(obj['bsdusr_username']))

        syslog(LOG_DEBUG, "FreeNAS_Users.__init__: leave")

    def __len__(self):
        return len(self.__bsd_users) + len(self.__users)

    def __iter__(self):
        for pw in self.__bsd_users:
            yield pw
        for pw in self.__users:
            yield pw

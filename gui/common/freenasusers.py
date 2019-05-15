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

from freenasUI.middleware.client import client

from freenasUI.common.system import (
    activedirectory_enabled,
    ldap_enabled,
    nis_enabled
)

log = logging.getLogger("common.freenasusers")


U_AD_ENABLED = 0x00000001
U_NIS_ENABLED = 0x00000004
U_LDAP_ENABLED = 0x00000008
U_DC_ENABLED = 0x00000010


def _get_dflags():
    dflags = 0

    if activedirectory_enabled():
        dflags |= U_AD_ENABLED
    elif nis_enabled():
        dflags |= U_NIS_ENABLED
    elif ldap_enabled():
        dflags |= U_LDAP_ENABLED

    return dflags


def bsdUsers_objects(**kwargs):
    from freenasUI.account.models import bsdUsers

    qs = bsdUsers.objects.select_related('bsdusr_group').filter(**kwargs)

    objects = {}
    for user in qs:
        obj = user.__dict__
        obj['bsdusr_group'] = user.bsdusr_group.bsdgrp_group
        obj.pop('_state', None)
        if 'bsdusr_uid' in kwargs:
            objects[user.bsdusr_uid] = obj
        else:
            objects[user.bsdusr_username] = obj

    return objects


def bsdGroups_objects(**kwargs):
    from freenasUI.account.models import bsdGroups

    qs = bsdGroups.objects.filter(**kwargs)

    objects = {}
    for group in qs:
        obj = group.__dict__
        obj.pop('_state', None)
        if 'bsdgrp_gid' in kwargs:
            objects[group.bsdgrp_gid] = obj
        else:
            objects[group.bsdgrp_group] = obj

    return objects


class FreeNAS_Local_Group(object):
    def __new__(cls, group, **kwargs):

        obj = None
        if group is not None:
            obj = super(FreeNAS_Local_Group, cls).__new__(cls)

        return obj

    def __init__(self, group, **kwargs):
        super(FreeNAS_Local_Group, self).__init__()

        data = kwargs.pop('data', None)

        self._gr = None
        if group is not None:
            self.__get_group(group, data=data)

    def __get_group(self, group, data=None):
        if not data and (
            isinstance(group, int) or (
                isinstance(group, str) and group.isdigit()
            )
        ):
            objects = bsdGroups_objects(bsdgrp_gid=group)
            if objects:
                group = objects[int(group)]['bsdgrp_group']

        try:
            self._gr = grp.getgrnam(group)
        except Exception as e:
            log.debug("Exception on grfunc: {0}".format(e))
            self._gr = None


class FreeNAS_Group(object):
    def __new__(cls, group, **kwargs):

        if 'dflags' in kwargs:
            dflags = kwargs['dflags']
        else:
            dflags = _get_dflags()

        obj = None
        try:
            if dflags & U_AD_ENABLED:
                obj = FreeNAS_DS_Group(group, 'activedirectory', **kwargs)
            elif dflags & U_NIS_ENABLED:
                obj = FreeNAS_DS_Group(group, 'nis', **kwargs)
            elif dflags & U_LDAP_ENABLED:
                obj = FreeNAS_DS_Group(group, 'ldap', **kwargs)

            if dflags & (U_AD_ENABLED|U_NIS_ENABLED|U_LDAP_ENABLED) and not obj._gr:
                obj = None

        except Exception:
            log.debug('Failed to get group from directory service, falling back to local', exc_info=True)

        if obj is None:
            obj = FreeNAS_Local_Group(group, **kwargs)

        if obj is None or not obj._gr:
            obj = None

        if obj:
            obj = obj._gr

        return obj


class FreeNAS_Groups(object):
    def __init__(self, **kwargs):
        self.__groups = None

        """
        FreeNAS_Directory_Groups call may fail for several reasons
        For now lets just fail silently until we can come up with
        a better error handling

        TODO: Warn the user in the GUI that "something" happenned
        """

        dir = None
        dflags = _get_dflags()
        grouplist = []
        with client as c:
            if dflags & U_AD_ENABLED:
                grouplist = (c.call('activedirectory.get_cache'))['groups']
            elif dflags & U_NIS_ENABLED:
                grouplist = (c.call('nis.get_cache'))['groups']
            elif dflags & U_LDAP_ENABLED:
                grouplist = (c.call('ldap.get_cache'))['groups']

        if grouplist:
            self.__groups = []
            for g in grouplist:
                self.__groups.append(
                    grp.struct_group((g['gr_name'], '', g['gr_gid'], []))
                )

        if self.__groups is None:
            self.__groups = []

        self.__bsd_groups = []
        objects = bsdGroups_objects()
        for group, obj in list(objects.items()):
            grpobj = FreeNAS_Group(group, data=obj, dflags=0)
            if grpobj:
                self.__bsd_groups.append(grpobj)

    def __len__(self):
        return len(self.__bsd_groups) + len(self.__groups)

    def __iter__(self):
        for gr in self.__bsd_groups:
            yield gr
        for gr in self.__groups:
            yield gr


class FreeNAS_Local_User(object):
    def __new__(cls, user, **kwargs):
        obj = None
        if user is not None:
            obj = super(FreeNAS_Local_User, cls).__new__(cls)

        return obj

    def __init__(self, user, **kwargs):
        super(FreeNAS_Local_User, self).__init__()

        data = kwargs.pop('data', None)
        self._pw = None
        if user is not None:
            self.__get_user(user, data=data)

    def __get_user(self, user, data=None):
        if not data and (
            isinstance(user, int) or
            (isinstance(user, str) and user.isdigit())
        ):
            objects = bsdUsers_objects(bsdusr_uid=user)
            if objects:
                user = objects[int(user)]['bsdusr_username']

        try:
            self._pw = pwd.getpwnam(user)

        except Exception as e:
            log.debug("Exception on pwfunc: {0}".format(e))
            self._pw = None


class FreeNAS_DS_User(object):
    def __new__(cls, user, dstype, **kwargs):
        obj = None
        if user is not None:
            obj = super(FreeNAS_DS_User, cls).__new__(cls)

        return obj

    def __init__(self, user, dstype, **kwargs):
        super(FreeNAS_DS_User, self).__init__()
        with client as c:
            u = c.call(f'{dstype}.get_userorgroup_legacy', 'users', user)

        if u is None:
            self._pw = None
            return

        self._pw = pwd.struct_passwd((u['pw_name'], '', u['pw_uid'], -1, '', '', ''))


class FreeNAS_DS_Group(object):
    def __new__(cls, group, dstype, **kwargs):
        log.debug('new-group: %s' % group)
        obj = None
        if group is not None:
            obj = super(FreeNAS_DS_Group, cls).__new__(cls)

        return obj

    def __init__(self, group, dstype, **kwargs):
        super(FreeNAS_DS_Group, self).__init__()
        with client as c:
            g = c.call(f'{dstype}.get_userorgroup_legacy', 'groups', group)

        if g is None:
            self._gr = None
            return

        self._gr = grp.struct_group((g['gr_name'], '', g['gr_gid'], []))


class FreeNAS_User(object):
    def __new__(cls, user, **kwargs):

        if 'dflags' in kwargs:
            dflags = kwargs['dflags']
        else:
            dflags = _get_dflags()

        data = kwargs.pop('data', None)

        obj = None
        try:
            if dflags & U_AD_ENABLED:
                obj = FreeNAS_DS_User(user, 'activedirectory', **kwargs)
            elif dflags & U_NIS_ENABLED:
                obj = FreeNAS_DS_User(user, 'nis', **kwargs)
            elif dflags & U_LDAP_ENABLED:
                obj = FreeNAS_DS_User(user, 'ldap', **kwargs)

            if not obj._pw and dflags & (U_AD_ENABLED|U_NIS_ENABLED|U_LDAP_ENABLED):
                obj = None

        except Exception:
            log.debug('Failed to get user from directory service, falling back to local', exc_info=True)

        if obj is None:
            obj = FreeNAS_Local_User(user, data=data, **kwargs)

        if obj is None or not obj._pw:
            obj = None

        if obj:
            obj = obj._pw

        return obj


class FreeNAS_Users(object):
    def __init__(self, **kwargs):
        self.__users = None

        """
        FreeNAS_Directory_Users call may fail for several reasons
        For now lets just fail silently until we can come up with
        a better error handling

        TODO: Warn the user in the GUI that "something" happenned
        New ds_cache only stores username and uid. Set dummy
        values to fill out struct_pwd in this case.
        """
        dir = None
        dflags = _get_dflags()
        userlist = []
        with client as c:
            if dflags & U_AD_ENABLED:
                userlist = (c.call('activedirectory.get_cache'))['users']
            elif dflags & U_NIS_ENABLED:
                userlist = (c.call('nis.get_cache'))['users']
            elif dflags & U_LDAP_ENABLED:
                userlist = (c.call('ldap.get_cache'))['users']

        if userlist:
            self.__users = []
            for user in userlist:
                self.__users.append(
                    pwd.struct_passwd((
                        user['pw_name'], '', user['pw_uid'], -1, user['pw_name'], '', ''
                    ))
                )

        if self.__users is None:
            self.__users = []

        self.__bsd_users = []
        objects = bsdUsers_objects()
        for username, obj in list(objects.items()):
            usrobj = FreeNAS_User(username, data=obj, dflags=0)
            if usrobj:
                self.__bsd_users.append(usrobj)

    def __len__(self):
        return len(self.__bsd_users) + len(self.__users)

    def __iter__(self):
        for pw in self.__bsd_users:
            yield pw
        for pw in self.__users:
            yield pw

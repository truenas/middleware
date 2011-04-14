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
from django.db import models
from freenasUI.services.models import services, LDAP, ActiveDirectory
from freenasUI.account.models import bsdUsers, bsdGroups
from freenasUI.middleware.notifier import notifier

import os
import grp
import pwd
import sys
import types
import ldap


class FreeNAS_LDAP:

    FREENAS_LDAP_NOSSL = 0
    FREENAS_LDAP_USESSL = 1 
    FREENAS_LDAP_USETLS = 2

    FREENAS_CACERTFILE = "/usr/local/etc/certs/cacert.crt"

    def __init__(self, host = None, binddn = None, bindpw = None,
        basedn = None, ssl = FREENAS_LDAP_NOSSL, scope = None,
        filter = None, attributes = None):

        self.host = host
        self.binddn = binddn
        self.bindpw = bindpw
        self.basedn = basedn
        self.ssl = self.__setssl(ssl)
        self.scope = scope
        self.filter = filter
        self.attributes = attributes
        self.__handle = None
        self.__isopen = 0

    def __setssl(self, ssl):
        tok = FreeNAS_LDAP.FREENAS_LDAP_NOSSL

        if type(ssl) in (types.IntType, types.LongType) or ssl.isdigit():
            ssl = int(ssl)
            if ssl not in (FreeNAS_LDAP.FREENAS_LDAP_NOSSL,
                FreeNAS_LDAP.FREENAS_LDAP_USESSL,
                FreeNAS_LDAP.FREENAS_LDAP_USETLS):
                tok = FreeNAS_LDAP.FREENAS_LDAP_NOSSL

        else:
            if ssl == "start_tls":
                tok = FreeNAS_LDAP.FREENAS_LDAP_USETLS
            elif ssl == "on":
                tok = FreeNAS_LDAP.FREENAS_LDAP_USESSL

        return tok


    def __geturi(self):
        if self.host is None:
            return None

        uri = None
        if self.ssl in (FreeNAS_LDAP.FREENAS_LDAP_NOSSL, FreeNAS_LDAP.FREENAS_LDAP_USETLS):
            uri = "ldap://%s" % self.host
        elif self.ssl == FreeNAS_LDAP.FREENAS_LDAP_USESSL:
            uri = "ldaps://%s" % self.host
        else:
            uri = "ldap://%s" % self.host

        return uri

    def open(self):
        if self.__isopen == 1:
            return

        if self.host:
            self.__handle = ldap.initialize(self.__geturi())
       
        if self.__handle:
            res = None
            self.__handle.protocol_version = ldap.VERSION3
            self.__handle.set_option(ldap.OPT_REFERRALS, 0)

            if self.ssl in (FreeNAS_LDAP.FREENAS_LDAP_USESSL, FreeNAS_LDAP.FREENAS_LDAP_USETLS):
                self.__handle.set_option(ldap.OPT_X_TLS_ALLOW, 1)
                self.__handle.set_option(ldap.OPT_X_TLS_CACERTFILE, FreeNAS_LDAP.FREENAS_CACERTFILE)
                self.__handle.set_option(ldap.OPT_X_TLS_NEWCTX, ldap.OPT_X_TLS_DEMAND)

            if self.ssl == FreeNAS_LDAP.FREENAS_LDAP_USETLS:
                try:
                    self.__handle.start_tls_s() 
                except:
                    pass

            if self.binddn and self.bindpw:
                try:
                    res = self.__handle.simple_bind_s(self.binddn, self.bindpw)
                except:
                    res = None
            else:
                try:
                    res = self.__handle.simple_bind_s()
                except:
                    res = None

            if res:
                self.__isopen = 1

    def unbind(self):
        if self.__handle:
            self.__handle.unbind()

    def close(self):
        if self.__isopen == 1:
            self.unbind()
            self.__handle = None
            self.__isopen = 0

    def __search(self, basedn, scope = ldap.SCOPE_SUBTREE, filter = None, attributes = None):
        if self.__isopen == 0:
            return None

        result = []
        results = []
        id = self.__handle.search(basedn, scope, filter, attributes)
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

        return result

    def search(self):
        isopen = self.__isopen
        self.open()

        results = self.__search(self.basedn, self.scope, self.filter, self.attributes)
        if isopen == 0:
            self.close()

        return results

    def get_ldap_user(self, user):
        isopen = self.__isopen
        self.open()

        ldap_user = None
        scope = ldap.SCOPE_SUBTREE

        if type(user) in (types.IntType, types.LongType):
            filter = '(&(objectclass=person)(uidnumber=%d))' % user
        elif user.isdigit():
            filter = '(&(objectclass=person)(uidnumber=%s))' % user
        else:
            filter = '(&(objectclass=person)(!(uid=%s)(cn=%s)))' % (user, user)

        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    ldap_user = r
                    break

        if isopen == 0:
            self.close()

        return ldap_user

    def get_ldap_users(self):
        isopen = self.__isopen
        self.open()

        users = []
        scope = ldap.SCOPE_SUBTREE
        filter = '(&(objectclass=person)(uid=*))'
        results = self.__search(self.basedn, scope, filter, self.attributes)
        if results:
            for r in results:
                if r[0]:
                    users.append(r)

        if isopen == 0:
            self.close()

        return users

    def get_ldap_group(self, group):
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

        return ldap_group

    def get_ldap_groups(self):
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

        return groups

    def get_active_directory_rootDSE(self):
        isopen = self.__isopen
        self.open()

        results = self.__search("", ldap.SCOPE_BASE, "(objectclass=*)")
        if isopen == 0:
            self.close()

        return results

    def get_active_directory_baseDN(self):
        results = self.get_active_directory_rootDSE()
        try:
            results = results[0][1]['defaultNamingContext'][0]
        except:
            results = None

        return results

    def get_active_directory_userDN(self, user):
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

        return results

    def get_active_directory_user(self, user):
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

        return ad_user

    def get_active_directory_users(self):
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

        return users

    def get_active_directory_group(self, group):
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

        return ad_group

    def get_active_directory_groups(self):
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

        return groups
  

class FreeNAS_Users:
    def __init__(self):
        self.__users = []
        self.__index = 0

        ldap_enable = ad_enable = 0
        bsd_users = bsdUsers.objects.all()
        for bu in bsd_users:
            self.__users.append(bu)
        bsd_users = None

        svcs = services.objects.filter(srv_service__in=['activedirectory', 'ldap'])
        for s in svcs:
            if s.srv_service == 'ldap':
                ldap_enable = s.srv_enable
            if s.srv_service == 'activedirectory':
                ad_enable = s.srv_enable
        svcs = None

        if ldap_enable == 1:
            ldap_users = self.__get_ldap_users()
            for lu in ldap_users:
                self.__users.append(lu)
            ldap_users = None

        elif ad_enable == 1:
            ad_users = self.__get_active_directory_users()
            for au in ad_users:
                self.__users.append(au)
            ad_users = None

    def __iter__(self):
        return self

    def next(self):
        if self.__index >= len(self.__users):
            self.__index = 0
            raise StopIteration

        user = self.__users[self.__index]
        self.__index += 1
        return user

    def __get_ldap_groups(self, l = LDAP.objects.all()[0], f = None):
        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['cn']
        
        groups = {}
        ldap_groups = f.get_ldap_groups()
        for g in ldap_groups:
            g = g[1]
            try:
                gr = grp.getgrnam(g['cn'][0])
            except:
                continue

            gu = bsdGroups()
            gu.bsdgrp_gid = gr.gr_gid
            gu.bsdgrp_group = unicode(gr.gr_name)
            groups[str(gr.gr_gid)] = gu
            gr = None

        return groups

    def __get_ldap_users(self, l = LDAP.objects.all()[0], f = None):
        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)
        ldap_groups = self.__get_ldap_groups(l, f)

        f.basedn = l.ldap_usersuffix + "," + l.ldap_basedn;
        f.attributes = ['uid']
        ldap_users = f.get_ldap_users()
        f = l = None

        users = [] 
        for u in ldap_users:
            u = u[1]
            try:
                pw = pwd.getpwnam(u['uid'][0])
            except:
                continue

            bu = bsdUsers()
            bu.bsdusr_username = unicode(pw.pw_name)
            bu.bsdusr_uid = pw.pw_uid
            if str(pw.pw_gid) in ldap_groups:
                bu.bsdusr_group = ldap_groups[str(pw.pw_gid)]
            bu.bsdusr_full_name = unicode(pw.pw_gecos)
            bu.bsdusr_home = unicode(pw.pw_dir)
            bu.bsdusr_shell = unicode(pw.pw_shell)
            users.append(bu)
            pw = None
          
        return users

    def __get_active_directory_groups(self, ad = ActiveDirectory.objects.all()[0], f = None):
        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)

        f.host = ad.ad_dcname
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']
 
        groups = {}
        ad_groups = f.get_active_directory_groups()
        for g in ad_groups:
            g = g[1]
            try:
                gr = grp.getgrnam(g['sAMAccountName'][0])
            except:
                continue

            gu = bsdGroups()
            gu.bsdgrp_gid = gr.gr_gid
            gu.bsdgrp_group = unicode(gr.gr_name)
            groups[str(gr.gr_gid)] = gu
            gr = None

        return groups

    def __get_active_directory_users(self, ad = ActiveDirectory.objects.all()[0], f = None):  
        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)
        ad_groups = self.__get_active_directory_groups(ad, f)

        f.host = ad.ad_dcname
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']
        ad_users = f.get_active_directory_users()

        users = []
        for u in ad_users:
            u = u[1]
            try:
                pw = pwd.getpwnam(u['sAMAccountName'][0])
            except:
                continue

            bu = bsdUsers()
            bu.bsdusr_username = unicode(pw.pw_name)
            bu.bsdusr_uid = pw.pw_uid
            if str(pw.pw_gid) in ad_groups:
                bu.bsdusr_group = ad_groups[str(pw.pw_gid)]
            bu.bsdusr_full_name = unicode(pw.pw_gecos)
            bu.bsdusr_home = unicode(pw.pw_dir)
            bu.bsdusr_shell = unicode(pw.pw_shell)
            users.append(bu)
            pw = None
          
        return users


class FreeNAS_Groups:
    def __init__(self):
        self.__groups = []
        self.__index = 0

        ldap_enable = ad_enable = 0
        bsd_groups = bsdGroups.objects.all()
        for bg in bsd_groups:
            self.__groups.append(bg)
        bsd_groups = None

        svcs = services.objects.filter(srv_service__in=['activedirectory', 'ldap'])
        for s in svcs:
            if s.srv_service == 'ldap':
                ldap_enable = s.srv_enable
            if s.srv_service == 'activedirectory':
                ad_enable = s.srv_enable
        svcs = None

        if ldap_enable == 1:
            ldap_groups = self.__get_ldap_groups()
            for lg in ldap_groups:
                self.__groups.append(lg)
            ldap_groups = None

        elif ad_enable == 1:
            ad_groups = self.__get_active_directory_groups()
            for ag in ad_groups:
                self.__groups.append(ag)
            ad_groups = None

    def __iter__(self):
        return self

    def next(self):
        if self.__index >= len(self.__groups):
            self.__index = 0
            raise StopIteration

        group = self.__groups[self.__index]
        self.__index += 1
        return group

    def __get_ldap_groups(self, l = LDAP.objects.all()[0], f = None):
        if not f:
            f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
                l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['cn']
        
        groups = []
        ldap_groups = f.get_ldap_groups()
        for g in ldap_groups:
            g = g[1]
            try:
                gr = grp.getgrnam(g['cn'][0])
            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)
            groups.append(bg)
            gr = None

        return groups

    def __get_active_directory_groups(self, ad = ActiveDirectory.objects.all()[0], f = None):
        if not f:
            f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)

        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']
 
        groups = []
        ad_groups = f.get_active_directory_groups()
        for g in ad_groups:
            g = g[1]
            try:
                gr = grp.getgrnam(g['sAMAccountName'][0])
            except:
                continue

            bg = bsdGroups()
            bg.bsdgrp_gid = gr.gr_gid
            bg.bsdgrp_group = unicode(gr.gr_name)
            groups.append(bg)
            gr = None

        return groups


class FreeNAS_User(bsdUsers):

    def __init__(self, user):
        super(FreeNAS_User, self).__init__()

        ldap_enable = ad_enable = 0
        if type(user) in (types.IntType, types.LongType):
            bsdUser = bsdUsers.objects.filter(bsdusr_uid = user)
        elif user.isdigit():
            user = int(user)
            bsdUser = bsdUsers.objects.filter(bsdusr_uid = user)
        else:
            bsdUser = bsdUsers.objects.filter(bsdusr_username = user)

        pw = None
        if bsdUser:
            try:
                pw = pwd.getpwnam(bsdUser[0])
            except:
                pw = None

        if pw:
            self.bsdusr_uid = pw.pw_uid
            self.bsdusr_username = unicode(pw.pw_name)
            self.bsdusr_group = FreeNAS_Group(pw.pw_gid)
            self.bsdusr_home = unicode(pw.pw_dir)
            self.bsdusr_shell = unicode(pw.pw_shell)
            self.bsdusr_full_name = unicode(pw.pw_gecos)
            pw = None
            return

        svcs = services.objects.filter(srv_service__in=['activedirectory', 'ldap'])
        for s in svcs:
            if s.srv_service == 'ldap':
                ldap_enable = s.srv_enable
            if s.srv_service == 'activedirectory':
                ad_enable = s.srv_enable
        svcs = None

        pw = None
        if ldap_enable == 1:
            pw = self.__get_ldap_user(user)

        elif ad_enable == 1:
            pw = self.__get_active_directory_user(user)

        if pw:
            self.bsdusr_uid = pw.pw_uid
            self.bsdusr_username = unicode(pw.pw_name)
            self.bsdusr_group = FreeNAS_Group(pw.pw_gid)
            self.bsdusr_home = unicode(pw.pw_dir)
            self.bsdusr_shell = unicode(pw.pw_shell)
            self.bsdusr_full_name = unicode(pw.pw_gecos)
            pw = None

    def __get_ldap_user(self, user):
        l = LDAP.objects.all()[0]
        f = FreeNAS_LDAP(l.ldap_hostname, l.ldap_rootbasedn,
            l.ldap_rootbindpw, l.ldap_basedn, l.ldap_ssl)

        f.basedn = l.ldap_groupsuffix + "," + l.ldap_basedn;
        f.attributes = ['uid']
        
        pw = None
        ldap_user = f.get_ldap_user(user)
        if ldap_user:
            try:
                pw = pwd.getpwnam(ldap_user[1]['uid'][0])
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

        return pw

    def __get_active_directory_user(self, user):
        ad = ActiveDirectory.objects.all()[0]
        f = FreeNAS_LDAP(ad.ad_dcname, ad.ad_adminname + "@" + ad.ad_domainname, ad.ad_adminpw)
        f.basedn = f.get_active_directory_baseDN()
        f.attributes = ['sAMAccountName']

        pw = None
        ad_user = f.get_active_directory_user(user)
        if ad_user:
            try: 
                pw = pwd.getpwnam(ad_user[1]['sAMAccountName'][0])
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

        return pw


class FreeNAS_Group(bsdGroups):

    def __init__(self, group):
        super(FreeNAS_Group, self).__init__()

        ldap_enable = ad_enable = 0
        if type(group) in (types.IntType, types.LongType):
            bsdGroup = bsdGroups.objects.filter(bsdgrp_gid = group)
        elif group.isdigit():
            group = int(group)
            bsdGroup = bsdGroups.objects.filter(bsdgrp_gid = group)
        else:
            bsdGroup = bsdGroups.objects.filter(bsdgrp_group = group)

        gr = None
        if bsdGroup:
            try:
                gr = grp.getgrnam(bsdGroup[0])
            except:
                gr = None

        if gr:
            self.bsdgrp_gid = gr.gr_gid
            self.bsdgrp_group = unicode(gr.gr_name)
            gr = None 

            return

        svcs = services.objects.filter(srv_service__in=['activedirectory', 'ldap'])
        for s in svcs:
            if s.srv_service == 'ldap':
                ldap_enable = s.srv_enable
            if s.srv_service == 'activedirectory':
                ad_enable = s.srv_enable
        svcs = None

        gr = None
        if ldap_enable == 1:
            gr = self.__get_ldap_group(group)

        elif ad_enable == 1:
            gr = self.__get_active_directory_group(group)

        if gr:
            self.bsdgrp_gid = gr.gr_gid
            self.bsdgrp_group = unicode(gr.gr_name)
            gr = None

    def __get_ldap_group(self, group):
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

        return gr

    def __get_active_directory_group(self, group):
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

        return gr



USER_CHOICES = ((x.bsdusr_username, x.bsdusr_username) for x in FreeNAS_Users())
GROUP_CHOICES = ((x.bsdgrp_group, x.bsdgrp_group) for x in FreeNAS_Groups())

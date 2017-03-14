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
from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode


NAME = _('Directory Service')
ICON = 'DirectoryServiceIcon'
BLACKLIST = [
    'ActiveDirectory',
    'LDAP',
    'NIS',
    'NT4',
    'idmap_ad',
    'idmap_adex',
    'idmap_autorid',
    'idmap_hash',
    'idmap_ldap',
    'idmap_nss',
    'idmap_rfc2307',
    'idmap_rid',
    'idmap_tdb',
    'idmap_tdb2',
    'directoryservice_idmap',
    'KerberosKeytab',
    'KerberosRealm'
]
ORDER = 25


class ActiveDirectoryView(TreeNode):

    gname = 'ActiveDirectory'
    name = _('Active Directory')
    app_name = 'activedirectory'
    type = 'opendirectoryservice'
    icon = 'ActiveDirectoryIcon'
    append_to = 'directoryservice'
    order = 0


class NT4View(TreeNode):

    gname = 'NT4'
    name = _('NT4')
    app_name = 'nt4'
    type = 'opendirectoryservice'
    icon = 'NT4Icon'
    append_to = 'directoryservice'
    order = 15


class NISView(TreeNode):

    gname = 'NIS'
    name = _('NIS')
    app_name = 'nis'
    type = 'opendirectoryservice'
    icon = 'NISIcon'
    append_to = 'directoryservice'
    order = 10


class LDAPView(TreeNode):

    gname = 'LDAP'
    name = _('LDAP')
    app_name = 'ldap'
    type = 'opendirectoryservice'
    icon = 'LDAPIcon'
    append_to = 'directoryservice'
    order = 5


class KerberosRealmView(TreeNode):

    gname = 'KerberosRealm'
    name = _('Kerberos Realms')
    app_name = 'kerberosrealm'
    type = 'opendirectoryservice'
    icon = 'KerberosRealmIcon'
    append_to = 'directoryservice'
    order = 20


class KerberosKeytabView(TreeNode):

    gname = 'KerberosKeytab'
    name = _('Kerberos Keytabs')
    app_name = 'kerberoskeytab'
    type = 'opendirectoryservice'
    icon = 'KerberosKeytabIcon'
    append_to = 'directoryservice'
    order = 25


class KerberosSettingsView(TreeNode):

    gname = 'KerberosSettings'
    name = _('Kerberos Settings')
    app_name = 'kerberossettings'
    type = 'opendirectoryservice'
    icon = 'SettingsIcon'
    append_to = 'directoryservice'
    order = 30

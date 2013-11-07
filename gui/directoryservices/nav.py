#+
# Copyright 2013 iXsystems, Inc.
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
import logging

from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode
from freenasUI.directoryservices.models import (
    ActiveDirectory,
    LDAP,
    NIS,
    NT4
)

log = logging.getLogger('directoryservices.nav')

NAME = _('Directory Services')
ICON = u'DirectoryServiceIcon'
BLACKLIST = [ 
    'ActiveDirectory',
    'LDAP',
    'NIS',
    'NT4'
]


#class AddDirectoryService(TreeNode):


class ViewDirectoryService(TreeNode):

    gname = 'DirectoryService.View'
    name = _(u'View Directories')
    icon = u'SettingsIcon'
    type = 'opendirectoryservices'


#class ActiveDirectoryView(TreeNode):
#
#    gname = 'Active Directory'
#    name = _(u'Active Directory')
#    app_name = 'activedirectory'
#    icon = u'ActiveDirectoryIcon'
#
#    try:
#        ad = ActiveDirectory.objects.order_by("-id")[0]
#        kwargs = { 'oid': ad.id }
#        type = 'editobject'
#        view = 'freeadmin_directoryservices_activedirectory_edit'
#
#    except:
#        type = 'object'
#        view = 'freeadmin_directoryservices_activedirectory_add'
#
#
#class LDAPView(TreeNode):
#
#    gname = 'LDAP'
#    name = _(u'LDAP')
#    app_name = 'ldap'
#    icon = u'LDAPIcon'
#
#    try:
#        ldap = LDAP.objects.order_by("-id")[0]
#        kwargs = { 'oid': ldap.id }
#        type = 'editobject'
#        view = 'freeadmin_directoryservices_ldap_edit'
#
#    except:
#        type = 'object'
#        view = 'freeadmin_directoryservices_ldap_add'
#
#
#class NISView(TreeNode):
#
#    gname = 'NIS'
#    name = _(u'NIS')
#    app_name = 'nis'
#    icon = u'NISIcon'
#
#    try:
#        nis = NIS.objects.order_by("-id")[0]
#        kwargs = { 'oid': nis.id }
#        type = 'editobject'
#        view = 'freeadmin_directoryservices_nis_edit'
#
#    except:
#        type = 'object'
#        view = 'freeadmin_directoryservices_nis_add'
#
#
#class NT4View(TreeNode):
#
#    gname = 'NT4'
#    name = _(u'NT4')
#    app_name = 'nt4'
#    icon = u'NT4Icon'
#
#    try:
#        nt4 = NT4.objects.order_by("-id")[0]
#        kwargs = { 'oid': nt4.id }
#        type = 'editobject'
#        view = 'freeadmin_directoryservices_nt4_edit'
#
#    except:
#        type = 'object'
#        view = 'freeadmin_directoryservices_nt4_add'

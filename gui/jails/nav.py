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
from django.utils.translation import ugettext_lazy as _

from . import models
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.common.warden import Warden

NAME = _('Jails')
BLACKLIST = ['JailsManager', 'JailsQuerySet']
ICON = u'ServicesIcon'

#class JailsSettings(TreeNode):
#
#    gname = 'Settings'
#    name = _(u'Settings')
#    type = 'object'
#    icon = u"SettingsIcon"
#    skip = True
#
#    def __init__(self, *args, **kwargs):
#        super(JailsSettings, self).__init__(*args, **kwargs)


#class JailsManagement(TreeNode):
#
#    gname = 'management'
#    name = _(u'Management')
#    icon = u"SettingsIcon"
#    #skip = True
#    #order = -1
#
#    def __init__(self, *args, **kwargs):
#        super(JailsManagement, self).__init__(*args, **kwargs)
#        self.append_children([JailsSettings()])

#class MountPoints(TreeNode):
#
#    gname = 'View'
#    view = 'freeadmin_plugins_nullmountpoint_datagrid'
#    #append_to = 'services.Plugins.NullMountPoint'
#    #append_to = 'services.PluginsJail.management.NullMountPoint'
#    append_to = 'jails.Jails.management.NullMountPoint'


#class MountPoint(TreeNode):
#
#    gname = 'NullMountPoint'
#    name = _(u'NullMountPoint')
#    type = u'nullmountpoint'
#    icon = u"SettingsIcon"

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


from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
from freenasUI.plugins import models

NAME = _('Plugins')
BLACKLIST = ['Plugins']
ICON = u'SettingsIcon'

class EnDisPlugins(TreeNode):

    gname = 'plugins.ControlPlugins'
    name = _(u'Control Plugins')
    type = u'en_dis_plugins'
    icon = u'SettingsIcon'
    order = -1

class ConfigurePlugins(TreeNode):

    gname = 'plugins.ConfigurePlugins'
    name = _('Configure Plugins')
    icon = u'SettingsIcon'

    def __init__(self, *args, **kwargs):
        super(ConfigurePlugins, self).__init__(*args, **kwargs)

        plugins = models.Plugins.objects.order_by("plugin_name")
        if not plugins.exists():
            self.append_app = False

        for p in plugins:
            nav = TreeNode(p.plugin_name)
            nav.name = p.plugin_name
            nav.icon = u'SettingsIcon'
            nav.view = 'plugin_edit'
            nav.kwargs = {'plugin_id': p.id}
            nav.type = 'object'

            self.insert_child(0, nav)

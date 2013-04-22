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
import eventlet
import logging

from eventlet.green import urllib2

from django.utils.translation import ugettext_lazy as _
from django.utils import simplejson

from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.plugins.models import Plugins
from freenasUI.plugins.utils import get_base_url

from freenasUI.jails.models import (
    Jails, JailsConfiguration, NullMountPoint
)

from freenasUI.common.warden import (
    Warden,
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL,
    WARDEN_TYPE_PORTJAIL,
    WARDEN_TYPE_LINUXJAIL
)

from freenasUI.freeadmin.tree import (
    tree_roots, TreeRoot, TreeNode, unserialize_tree
)

NAME = _('Jails')
ICON = u'ServicesIcon'
BLACKLIST = [
    'JailsConfiguration',
    'JailsManager',
    'JailsQuerySet',
    'Jails',
    'NullMountPoint',
    'Mkdir'
]

import logging
log = logging.getLogger('jails.nav')

class ViewJailsConfiguration(TreeNode):

    gname = 'Configuration'
    name  = _(u'Configuration')
    icon = u'SettingsIcon'
    order = 1

    def __init__(self, *args, **kwargs):
        super(ViewJailsConfiguration, self).__init__(*args, **kwargs)

        jc = JailsConfiguration.objects.order_by("-id")
        if jc:
            jc = jc[0]

            jc_node_view = TreeNode("View")
            jc_node_view.name = _(u'Edit Jails Configuration')
            jc_node_view.type = u'editobject'
            jc_node_view.view = 'freeadmin_jails_jailsconfiguration_edit'
            jc_node_view.kwargs = { 'oid': jc.id }
            jc_node_view.model = 'JailsConfiguration'
            jc_node_view.icon = u'SettingsIcon'
            jc_node_view.app_name = 'jails' 

            self.append_children([jc_node_view])
  
        else:  

            jc_node_add = TreeNode("Add")
            jc_node_add.name = _(u'Add Jails Configuration')
            jc_node_add.type = u'object'
            jc_node_add.view = 'freeadmin_jails_jailsconfiguration_add'
            jc_node_add.model = 'JailsConfiguration'
            jc_node_add.icon = u'SettingsIcon'
            jc_node_add.app_name = 'jails' 

            self.append_children([jc_node_add])


class ViewJailsBase(TreeNode):

    gname = 'Base'
    name  = _(u'Base')
    icon = u'SettingsIcon'
    order = -1
    skip = True

    def __init__(self, *args, **kwargs):
        super(ViewJailsBase, self).__init__(*args, **kwargs)

    def new_jail_node(self, jail):
        jail_node = TreeNode()

        jail_node.gname = jail.jail_host
        jail_node.name = jail.jail_host
        jail_node.icon = u'SettingsIcon'

        return jail_node

    def new_jail_node_view(self, jail):
        jail_node_view = TreeNode()

        jail_node_view.name = _('Edit')
        jail_node_view.type = 'editobject'
        jail_node_view.view = 'jail_edit'
        jail_node_view.kwargs = { 'id': jail.id }
        jail_node_view.model = 'Jails'
        jail_node_view.icon = u'SettingsIcon'
        jail_node_view.app_name = 'jails' 

        return jail_node_view

    def new_storage_node(self, jail):
        storage_node = TreeNode()

        storage_node.gname = 'Storage'
        storage_node.name = _(u'Storage')
        storage_node.icon = u'SettingsIcon'

        return storage_node

    def new_storage_node_view(self, nmp, jail):
        storage_node_view = TreeNode()

        storage_node_view.name = _('%s' % nmp.destination)
        storage_node_view.type = 'editobject'
        storage_node_view.view = 'jail_storage'
        storage_node_view.kwargs = { 'id': jail.id }
        storage_node_view.model = 'NullMountPoint'
        storage_node_view.icon = u'SettingsIcon'
        storage_node_view.app_name = 'jails' 

        return storage_node_view

    def new_storage_node_add(self, jail):
        storage_node_add = TreeNode()

        storage_node_add.name = _('Add Storage')
        storage_node_add.type = 'editobject'
        storage_node_add.view = 'jail_storage'
        storage_node_add.kwargs = { 'id': jail.id }
        storage_node_add.model = 'NullMountPoint'
        storage_node_add.icon = u'SettingsIcon'
        storage_node_add.app_name = 'jails' 

        return storage_node_add 

    def new_storage_node_mkdir(self, jail):
        storage_node_add = TreeNode()

        storage_node_add.name = _('Make Directory')
        storage_node_add.type = 'editobject'
        storage_node_add.view = 'jail_mkdir'
        storage_node_add.kwargs = { 'id': jail.id }
        storage_node_add.icon = u'SettingsIcon'
        storage_node_add.app_name = 'jails' 

        return storage_node_add 


class ViewPluginJails(ViewJailsBase):

    gname = 'Plugin Jails'
    name = _(u'Plugin Jails')
    icon = u'SettingsIcon'
    skip = False
    order = 2

    def __init__(self, *args, **kwargs):
        super(ViewPluginJails, self).__init__(*args, **kwargs)
        request = kwargs.get('request')

        host = get_base_url(request)
        jails = Jails.objects.filter(jail_type=WARDEN_TYPE_PLUGINJAIL)

        for jail in jails:
            jail_node = self.new_jail_node(jail)
            self.append_child(jail_node)

            jail_node_view = self.new_jail_node_view(jail)
            jail_node_view.order = 1
            jail_node.append_child(jail_node_view)

            storage_node = self.new_storage_node(jail)
            storage_node.order = 2
            jail_node.append_child(storage_node)

            storage_order = 1
            nmps = NullMountPoint.objects.filter(jail=jail.jail_host)
            for nmp in nmps:
                storage_node_view = self.new_storage_node_view(nmp, jail)
                storage_node_view.order = storage_order
                storage_node.append_child(storage_node_view)
                storage_order += 1

            storage_node_mkdir = self.new_storage_node_mkdir(jail)
            storage_node_mkdir.order = storage_order
            storage_node.append_child(storage_node_mkdir)
            storage_order += 1

            storage_node_add = self.new_storage_node_add(jail)
            storage_node_add.order = storage_order
            storage_node.append_child(storage_node_add)

            plugin_node = TreeNode()
            plugin_node.gname = 'Plugins'
            plugin_node.name = _(u'Plugins')
            plugin_node.icon = u'SettingsIcon'
            plugin_node.order = 3

            args = map(
                lambda y: (y, host, request),
                Plugins.objects.filter(plugin_enabled=True, plugin_jail=jail.jail_host))

            plugin_order = 1
            pool = eventlet.GreenPool(20)
            for plugin, url, data in pool.imap(self.plugin_fetch, args):
                if not data:
                    continue

                try:
                    data = simplejson.loads(data)
                    nodes = unserialize_tree(data)
                    for node in nodes:
                        node.order = plugin_order 
                        plugin_node.append_child(node) 
                        plugin_order += 1

                except Exception, e:
                    log.warn(_(
                         "An error occurred while unserializing from "
                        "%(url)s: %(error)s") % {'url': url, 'error': e})
                    log.debug(_(
                        "Error unserializing %(url)s (%(error)s), data "
                        "retrieved:") % {
                            'url': url,
                            'error': e,
                        })
                    for line in data.splitlines():
                        log.debug(line)

                continue

            plugin_node_add = TreeNode()
            plugin_node_add.name = _('Install Plugin')
            plugin_node_add.type = 'editobject'
            plugin_node_add.view = 'plugin_install'
            plugin_node_add.kwargs = {'jail_id': jail.id }
            plugin_node_add.model = 'Plugins'
            plugin_node_add.icon = u'SettingsIcon'
            plugin_node_add.app_name = 'jails' 
            plugin_node_add.order = plugin_order

            plugin_node.append_child(plugin_node_add)

            jail_node.append_child(plugin_node)

    def plugin_fetch(self, args):
        plugin, host, request = args
        data = None
        url = "%s/plugins/%s/%d/_s/treemenu" % (host, plugin.plugin_name, plugin.id)
        try:
            opener = urllib2.build_opener()
            opener.addheaders = [(
                'Cookie', 'sessionid=%s' % (
                    request.COOKIES.get("sessionid", ''),
                )
            )]
            #TODO: Increase timeout based on number of plugins
            response = opener.open(url, None, 5)
            data = response.read()
            if not data:
                log.warn(_("Empty data returned from %s") % (url,))

        except Exception, e:
            log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
                'url': url,
                'error': e,
            })

        return plugin, url, data


class ViewStandardJails(ViewJailsBase):

    gname = 'Standard Jails'
    name = _(u'Standard Jails')
    icon = u'SettingsIcon'
    skip = False
    order = 3

    def __init__(self, *args, **kwargs):
        super(ViewStandardJails, self).__init__(*args, **kwargs)

        jails = Jails.objects.filter(jail_type=WARDEN_TYPE_STANDARD)
        for jail in jails:
            jail_node = self.new_jail_node(jail)
            self.append_child(jail_node)

            jail_node_view = self.new_jail_node_view(jail)
            jail_node_view.order = 1
            jail_node.append_child(jail_node_view)

            storage_node = self.new_storage_node(jail)
            storage_node.order = 2
            jail_node.append_child(storage_node)

            storage_order = 1
            nmps = NullMountPoint.objects.filter(jail=jail.jail_host)
            for nmp in nmps:

                storage_node_view = self.new_storage_node_view(nmp, jail)
                storage_node_view.order = storage_order
                storage_node.append_child(storage_node_view)
                storage_order += 1

            storage_node_mkdir = self.new_storage_node_mkdir(jail)
            storage_node_mkdir.order = storage_order
            storage_node.append_child(storage_node_mkdir)
            storage_order += 1

            storage_node_add = self.new_storage_node_add(jail)
            storage_node_add.order = storage_order
            storage_node.append_child(storage_node_add)


class ViewPortJails(ViewJailsBase):

    gname = 'Port Jails'
    name = _(u'Port Jails')
    icon = u'SettingsIcon'
    skip = False
    order = 4

    def __init__(self, *args, **kwargs):
        super(ViewPortJails, self).__init__(*args, **kwargs)

        jails = Jails.objects.filter(jail_type=WARDEN_TYPE_PORTJAIL)
        for jail in jails:
            jail_node = self.new_jail_node(jail)
            self.append_child(jail_node)

            jail_node_view = self.new_jail_node_view(jail)
            jail_node_view.order = 1
            jail_node.append_child(jail_node_view)

            storage_node = self.new_storage_node(jail)
            storage_node.order = 2
            jail_node.append_child(storage_node)

            storage_order = 1
            nmps = NullMountPoint.objects.filter(jail=jail.jail_host)
            for nmp in nmps:

                storage_node_view = self.new_storage_node_view(nmp, jail)
                storage_node_view.order = storage_order
                storage_node.append_child(storage_node_view)
                storage_order += 1

            storage_node_mkdir = self.new_storage_node_mkdir(jail)
            storage_node_mkdir.order = storage_order
            storage_node.append_child(storage_node_mkdir)
            storage_order += 1

            storage_node_add = self.new_storage_node_add(jail)
            storage_node_add.order = storage_order
            storage_node.append_child(storage_node_add)


class ViewLinuxJails(ViewJailsBase):

    gname = 'Linux Jails'
    name = _(u'Linux Jails')
    icon = u'SettingsIcon'
    skip = False
    order = 5

    def __init__(self, *args, **kwargs):
        super(ViewLinuxJails, self).__init__(*args, **kwargs)

        jails = Jails.objects.filter(jail_type=WARDEN_TYPE_LINUXJAIL)
        for jail in jails:
            jail_node = self.new_jail_node(jail)
            self.append_child(jail_node)

            jail_node_view = self.new_jail_node_view(jail)
            jail_node_view.order = 1
            jail_node.append_child(jail_node_view)

            storage_node = self.new_storage_node(jail)
            storage_node.order = 2
            jail_node.append_child(storage_node)

            storage_order = 1
            nmps = NullMountPoint.objects.filter(jail=jail.jail_host)
            for nmp in nmps:

                storage_node_view = self.new_storage_node_view(nmp, jail)
                storage_node_view.order = storage_order
                storage_node.append_child(storage_node_view)
                storage_order += 1

            storage_node_mkdir = self.new_storage_node_mkdir(jail)
            storage_node_mkdir.order = storage_order
            storage_node.append_child(storage_node_mkdir)
            storage_order += 1

            storage_node_add = self.new_storage_node_add(jail)
            storage_node_add.order = storage_order
            storage_node.append_child(storage_node_add)


class AddJail(TreeNode):

    gname = 'Add Jails'
    name = _(u'Add Jails')
    icon = u'SettingsIcon'
    type = 'object'
    view = 'freeadmin_jails_jails_add'
    order = 6

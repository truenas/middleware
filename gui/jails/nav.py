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

from eventlet.green import urllib2

from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode
from freenasUI.jails.models import (
    Jails,
    JailsConfiguration,
    NullMountPoint
)
from freenasUI.jails.utils import jail_path_configured
from freenasUI.common.warden import (
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL,
    WARDEN_TYPE_PORTJAIL,
    WARDEN_TYPE_LINUXJAIL,
)

log = logging.getLogger('jails.nav')

NAME = _('Jails')
ICON = u'JailIcon'
BLACKLIST = [
    'JailsManager',
    'JailsQuerySet',
    'Jails',
    'NullMountPoint'
]


def plugin_fetch(args):
    plugin, host, request = args
    data = None
    url = "%s/plugins/%s/%d/_s/treemenu" % (
        host,
        plugin.plugin_name,
        plugin.id
    )
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


def init(tree_roots, nav, request):
    self = Base()
    jails = Jails.objects.all()
    log.debug("jails.... %r", jails)

    for jail in jails:
        if jail.jail_type == WARDEN_TYPE_PLUGINJAIL:
            icon = 'JailPluginIcon'
        elif jail.jail_type == WARDEN_TYPE_STANDARD:
            icon = 'BeastieIcon'
        elif jail.jail_type == WARDEN_TYPE_PORTJAIL:
            icon = 'BobbleIcon'
        elif jail.jail_type == WARDEN_TYPE_LINUXJAIL:
            icon = 'TuxIcon'
        jail_node = self.new_jail_node(jail, icon)
        nav.append_child(jail_node)

        jail_node_view = self.new_jail_node_view(jail)
        jail_node_view.order = 1
        jail_node.append_child(jail_node_view)

        storage_node = self.new_storage_node(jail)
        storage_node.order = 2
        jail_node.append_child(storage_node)

        storage_order = 1
        nmps = NullMountPoint.objects.filter(jail=jail.jail_host)
        for nmp in nmps:
            storage_node_view = self.new_storage_node_view(nmp)
            storage_node_view.order = storage_order
            storage_node.append_child(storage_node_view)
            storage_order += 1

        storage_node_add = self.new_storage_node_add(jail)
        storage_node_add.order = storage_order
        storage_node.append_child(storage_node_add)


class Base(object):

    def new_jail_node(self, jail, icon=u'JailIcon'):
        jail_node = TreeNode()

        jail_node.gname = jail.jail_host
        jail_node.name = jail.jail_host
        jail_node.icon = icon

        return jail_node

    def new_jail_node_view(self, jail):
        jail_node_view = TreeNode()

        jail_node_view.name = _('Edit')
        jail_node_view.type = 'editobject'
        jail_node_view.view = 'jail_edit'
        jail_node_view.kwargs = {'id': jail.id}
        jail_node_view.model = 'Jails'
        jail_node_view.icon = u'SettingsIcon'
        jail_node_view.app_name = 'jails'

        return jail_node_view

    def new_storage_node(self, jail):
        storage_node = TreeNode()

        storage_node.gname = 'Storage'
        storage_node.name = _(u'Storage')
        storage_node.icon = u'JailStorageIcon'

        return storage_node

    def new_storage_node_view(self, nmp):
        storage_node_view = TreeNode()

        storage_node_view.name = _('%s' % nmp.destination)
        storage_node_view.type = 'editobject'
        storage_node_view.view = 'jail_storage_view'
        storage_node_view.kwargs = {'id': nmp.id}
        storage_node_view.model = 'NullMountPoint'
        storage_node_view.icon = u'SettingsIcon'
        storage_node_view.app_name = 'jails'

        return storage_node_view

    def new_storage_node_add(self, jail):
        storage_node_add = TreeNode()

        storage_node_add.name = _('Add Storage')
        storage_node_add.type = 'editobject'
        storage_node_add.view = 'jail_storage_add'
        storage_node_add.kwargs = {'jail_id': jail.id}
        storage_node_add.model = 'NullMountPoint'
        storage_node_add.icon = u'JailStorageIcon'
        storage_node_add.app_name = 'jails'

        return storage_node_add


class AddJail(TreeNode):

    gname = 'Jails.Add'
    name = _(u'Add Jails')
    icon = u'JailAddIcon'
    type = 'object'
    view = 'freeadmin_jails_jails_add'
    order = -1

    def __init__(self, *args, **kwargs):
        super(AddJail, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()


class ViewJailsConfiguration(TreeNode):

    gname = 'JailsConfiguration'
    append_to = 'jails'
    name = _(u'Configuration')
    icon = u'SettingsIcon'
    type = 'openjails'


class ViewJails(TreeNode):

    gname = 'Jails.View'
    name = _(u'View Jails')
    icon = 'JailIcon'
    type = 'openjails'

    def __init__(self, *args, **kwargs):
        super(ViewJails, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()

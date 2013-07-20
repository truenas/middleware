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

from freenasUI.freeadmin.tree import TreeNode, unserialize_tree
from freenasUI.plugins.models import Plugins
from freenasUI.plugins.utils import get_base_url
from freenasUI.jails.models import (
    Jails,
    JailsConfiguration,
    NullMountPoint
)
from freenasUI.common.warden import (
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL,
    WARDEN_TYPE_PORTJAIL,
    WARDEN_TYPE_LINUXJAIL,
    WARDEN_STATUS_RUNNING
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


def jail_path_configured():
    """
    Check if there is the jail system is configured
    by looking at the JailsConfiguration model and
    jc_path field
    Returns: boolean
    """
    try:
        jc = JailsConfiguration.objects.latest('id')
    except JailsConfiguration.DoesNotExist:
        jc = None

    return jc and jc.jc_path


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

        if (
            jail.jail_status == WARDEN_STATUS_RUNNING and
            jail.jail_type == WARDEN_TYPE_PLUGINJAIL
        ):
            plugin_node = TreeNode()
            plugin_node.gname = 'Plugins'
            plugin_node.name = _(u'Plugins')
            plugin_node.icon = u'PluginIcon'
            plugin_node.order = 3

            host = get_base_url(request)

            args = map(
                lambda y: (y, host, request),
                Plugins.objects.filter(
                    plugin_enabled=True,
                    plugin_jail=jail.jail_host
                )
            )

            plugin_order = 1
            pool = eventlet.GreenPool(20)
            for plugin, url, data in pool.imap(plugin_fetch, args):
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

            plugin_node_add = TreeNode()
            plugin_node_add.name = _('Install Plugin')
            plugin_node_add.gname = 'InstallPlugin'
            plugin_node_add.type = 'editobject'
            plugin_node_add.view = 'plugin_install'
            plugin_node_add.kwargs = {'jail_id': jail.id}
            plugin_node_add.model = 'Plugins'
            plugin_node_add.icon = u'PluginInstallIcon'
            plugin_node_add.app_name = 'jails'
            plugin_node_add.order = plugin_order

            plugin_node.append_child(plugin_node_add)

            jail_node.append_child(plugin_node)


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


class ViewNullMountPoint(TreeNode):

    gname = 'NullMountPoint.View'
    name = _(u'View Storage')
    icon = 'ViewMountPointIcon'
    type = 'openjails'

    def __init__(self, *args, **kwargs):
        super(ViewNullMountPoint, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()

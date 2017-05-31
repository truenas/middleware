#
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
import urllib.request

from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode
from freenasUI.jails.models import (
    Jails,
    JailMountPoint
)
from freenasUI.jails.utils import jail_path_configured
from freenasUI.common.warden import (
    WARDEN_TYPE_STANDARD,
    WARDEN_TYPE_PLUGINJAIL,
    WARDEN_TYPE_PORTJAIL
)
from freenasUI.support.utils import jails_enabled

log = logging.getLogger('jails.nav')

NAME = _('Jails')
ICON = 'JailIcon'
BLACKLIST = [
    'JailsManager',
    'JailsQuerySet',
    'Jails',
    'JailTemplate',
    'JailMountPoint'
]
ORDER = 70

O_ADDJAIL = 0
O_ADDJAILTEMPLATE = 1
O_VIEWJAIL = 2
O_VIEWJAILTEMPLATE = 3
O_JAILSCONFIGURATION = 4
O_INDEX = 5


class AddJail(TreeNode):
    global O_ADDJAIL

    gname = 'Jails.Add'
    app_name = 'jails'
    model = 'Jails'
    name = _('Add Jail')
    icon = 'JailAddIcon'
    type = 'object'
    view = 'freeadmin_jails_jails_add'
    order = O_ADDJAIL

    def __init__(self, *args, **kwargs):
        super(AddJail, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()


class AddJailTemplate(TreeNode):
    global O_ADDJAILTEMPLATE

    gname = 'JailTemplate.Add'
    name = _('Add Jail Templates')
    icon = 'JailAddIcon'
    type = 'object'
    view = 'freeadmin_jails_jailtemplate_add'
    order = O_ADDJAILTEMPLATE

    def __init__(self, *args, **kwargs):
        super(AddJailTemplate, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()


class ViewJails(TreeNode):
    global O_VIEWJAIL

    gname = 'Jails.View'
    name = _('View Jails')
    icon = 'JailIcon'
    type = 'openjails'
    order = O_VIEWJAIL

    def __init__(self, *args, **kwargs):
        super(ViewJails, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()


class ViewJailTemplate(TreeNode):
    global O_VIEWJAILTEMPLATE

    gname = 'JailTemplate.View'
    name = _('View Jail Templates')
    icon = 'JailIcon'
    type = 'openjails'
    order = O_VIEWJAILTEMPLATE

    def __init__(self, *args, **kwargs):
        super(ViewJailTemplate, self).__init__(*args, **kwargs)
        self.skip = not jail_path_configured()


class ViewJailsConfiguration(TreeNode):
    global O_JAILSCONFIGURATION

    gname = 'JailsConfiguration'
    append_to = 'jails'
    name = _('Configuration')
    icon = 'SettingsIcon'
    type = 'openjails'
    order = O_JAILSCONFIGURATION


def plugin_fetch(args):
    plugin, host, request = args
    data = None
    url = "%s/plugins/%s/%d/_s/treemenu" % (
        host,
        plugin.plugin_name,
        plugin.id
    )
    try:
        opener = urllib.request.build_opener()
        opener.addheaders = [(
            'Cookie', 'sessionid=%s' % (
                request.COOKIES.get("sessionid", ''),
            )
        )]
        # TODO: Increase timeout based on number of plugins
        response = opener.open(url, None, 5)
        data = response.read()
        if not data:
            log.warn(_("Empty data returned from %s") % (url,))

    except Exception as e:
        log.warn(_("Couldn't retrieve %(url)s: %(error)s") % {
            'url': url,
            'error': e,
        })

    return plugin, url, data


def init(tree_roots, nav, request):

    if not jails_enabled():
        tree_roots.unregister(nav)

    global O_INDEX
    self = Base()
    jails = Jails.objects.all()

    for jail in jails:

        #
        # XXX Revist this... for jail types that don't
        # XXX match a given type, check the template
        # XXX type, otherwise, check OS
        #
        if jail.jail_type == WARDEN_TYPE_PLUGINJAIL:
            icon = 'JailPluginIcon'
        elif jail.jail_type == WARDEN_TYPE_STANDARD:
            icon = 'BeastieIcon'
        elif jail.jail_type == WARDEN_TYPE_PORTJAIL:
            icon = 'BobbleIcon'
        elif jail.is_linux_jail():
            icon = 'TuxIcon'
        else:
            icon = 'BeastieIcon'

        jail_node = self.new_jail_node(jail, icon)
        jail_node.order = O_INDEX
        O_INDEX += 1
        nav.append_child(jail_node)

        jail_node_view = self.new_jail_node_view(jail)
        jail_node_view.order = 1
        jail_node.append_child(jail_node_view)

        storage_node = self.new_storage_node(jail)
        storage_node.order = 2
        jail_node.append_child(storage_node)

        storage_order = 1
        nmps = JailMountPoint.objects.filter(jail=jail.jail_host)
        for nmp in nmps:
            storage_node_view = self.new_storage_node_view(nmp)
            storage_node_view.order = storage_order
            storage_node.append_child(storage_node_view)
            storage_order += 1

        storage_node_add = self.new_storage_node_add(jail)
        storage_node_add.order = storage_order
        storage_node.append_child(storage_node_add)


class Base(object):
    def new_jail_node(self, jail, icon='JailIcon'):
        jail_node = TreeNode()

        jail_node.gname = jail.jail_host
        jail_node.name = jail.jail_host
        jail_node.icon = icon

        return jail_node

    def new_jail_node_view(self, jail):
        jail_node_view = TreeNode()

        jail_node_view.name = _('Edit')
        jail_node_view.gname = 'Edit'
        jail_node_view.type = 'editobject'
        jail_node_view.view = 'jail_edit'
        jail_node_view.kwargs = {'id': jail.id}
        jail_node_view.model = 'Jails'
        jail_node_view.icon = 'SettingsIcon'
        jail_node_view.app_name = 'jails'

        return jail_node_view

    def new_storage_node(self, jail):
        storage_node = TreeNode()

        storage_node.gname = 'Storage'
        storage_node.name = _('Storage')
        storage_node.icon = 'JailStorageIcon'

        return storage_node

    def new_storage_node_view(self, nmp):
        storage_node_view = TreeNode()

        storage_node_view.name = nmp.destination
        storage_node_view.gname = str(nmp.id)
        storage_node_view.type = 'editobject'
        storage_node_view.view = 'freeadmin_jails_jailmountpoint_edit'
        storage_node_view.kwargs = {'oid': nmp.id}
        storage_node_view.model = 'JailMountPoint'
        storage_node_view.icon = 'SettingsIcon'
        storage_node_view.app_name = 'jails'

        return storage_node_view

    def new_storage_node_add(self, jail):
        storage_node_add = TreeNode()

        storage_node_add.name = _('Add Storage')
        storage_node_add.gname = 'Add'
        storage_node_add.type = 'editobject'
        storage_node_add.view = 'jail_storage_add'
        storage_node_add.kwargs = {'jail_id': jail.id}
        storage_node_add.model = 'JailMountPoint'
        storage_node_add.icon = 'JailStorageIcon'
        storage_node_add.app_name = 'jails'

        return storage_node_add

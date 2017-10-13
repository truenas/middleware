from django.utils.translation import ugettext_lazy as _
from freenasUI.choices import LAGGType
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.middleware.client import client
from freenasUI.middleware.notifier import notifier

from . import models

NAME = _('Network')
ICON = 'NetworkIcon'
BLACKLIST = ['LAGGInterfaceMembers', 'Alias', 'LAGGInterface']
ORDER = 10

IPMI_LOADED = None


def is_ipmi_loaded():
    global IPMI_LOADED
    if IPMI_LOADED is None:
        with client as c:
            IPMI_LOADED = c.call('ipmi.is_loaded')
    return IPMI_LOADED


class IPMI(TreeNode):

    gname = 'IPMI'
    name = _('IPMI')
    type = 'opennetwork'
    icon = 'IPMIIcon'
    append_to = 'network'

    def pre_build_options(self):
        if not is_ipmi_loaded():
            raise ValueError


class IPMI_B(TreeNode):

    gname = 'IPMI_B'
    name = _('IPMI')
    type = 'opennetwork'
    icon = 'IPMIIcon'
    append_to = 'network'

    def pre_build_options(self):
        if not is_ipmi_loaded():
            raise ValueError

        _n = notifier()
        if _n.is_freenas():
            raise ValueError

        node = _n.failover_node()
        if node not in ('A', 'B'):
            raise ValueError

        if node == 'A':
            self.name = _('IPMI (Node B)')
        else:
            self.name = _('IPMI (Node A)')


class NetSummary(TreeNode):

    gname = 'NetworkSummary'
    name = _('Network Summary')
    type = 'opennetwork'
    icon = 'SettingsIcon'


class GlobalConf(TreeNode):

    gname = 'GlobalConfiguration'
    name = _('Global Configuration')
    type = 'opennetwork'
    icon = 'SettingsIcon'
    append_to = 'network'


class Linkss(TreeNode):

    gname = 'LAGGInterface'
    model = 'LAGGInterface'
    app_name = 'network'
    name = _('Link Aggregations')
    icon = 'LAGGIcon'

    def __init__(self, *args, **kwargs):

        super(Linkss, self).__init__(*args, **kwargs)

        laggadd = TreeNode('Add')
        laggadd.name = _('Create Link Aggregation')
        laggadd.view = 'freeadmin_network_lagginterface_add'
        laggadd.type = 'object'
        laggadd.icon = 'AddLAGGIcon'
        laggadd.model = 'LAGGInterface'
        laggadd.app_name = 'network'

        laggview = TreeNode('View')
        laggview.gname = 'View'
        laggview.name = _('View Link Aggregations')
        laggview.type = 'opennetwork'
        laggview.icon = 'ViewAllLAGGsIcon'
        laggview.model = 'LAGGInterface'
        laggview.app_name = 'network'
        self.append_children([laggadd, laggview])

        for value, name in LAGGType:

            laggs = models.LAGGInterface.objects.filter(lagg_protocol__exact=value)
            if laggs.count() > 0:
                nav = TreeNode()
                nav.name = name
                nav.icon = 'LAGGIcon'
                nav._children = []
                self.append_child(nav)

            for lagg in laggs:

                subnav = TreeNode()
                subnav.name = lagg.lagg_interface.int_name
                subnav.icon = 'LAGGIcon'
                subnav._children = []
                nav.append_child(subnav)

                laggm = models.LAGGInterfaceMembers.objects.filter(
                    lagg_interfacegroup__exact=lagg.id
                ).order_by('lagg_ordernum')
                for member in laggm:
                    subsubnav = TreeNode()
                    subsubnav.name = member.lagg_physnic
                    subsubnav.type = 'editobject'
                    subsubnav.icon = 'LAGGIcon'
                    subsubnav.view = 'freeadmin_network_lagginterfacemembers_edit'
                    subsubnav.app_name = 'network'
                    subsubnav.model = 'LAGGInterfaceMembers' + lagg.lagg_interface.int_name
                    subsubnav.kwargs = {'oid': member.id}
                    subsubnav.append_url = '?deletable=false'
                    subsubnav._children = []
                    subnav.append_child(subsubnav)


class ViewInterfaces(TreeNode):

    gname = 'View'
    type = 'opennetwork'
    append_to = 'network.Interfaces'


class ViewVLAN(TreeNode):

    gname = 'View'
    type = 'opennetwork'
    append_to = 'network.VLAN'


class ViewSR(TreeNode):

    gname = 'View'
    type = 'opennetwork'
    append_to = 'network.StaticRoute'

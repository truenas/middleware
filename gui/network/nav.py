from django.utils.translation import ugettext_lazy as _
from freenasUI.choices import LAGGType
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.middleware.notifier import notifier

from . import models

NAME = _('Network')
ICON = u'NetworkIcon'
BLACKLIST = ['LAGGInterfaceMembers', 'Alias', 'LAGGInterface']
ORDER = 10


class IPMI(TreeNode):

    gname = u'IPMI'
    name = _(u'IPMI')
    type = 'opennetwork'
    icon = u'IPMIIcon'
    append_to = 'network'

    def pre_build_options(self):
        if not notifier().ipmi_loaded():
            raise ValueError


class NetSummary(TreeNode):

    gname = 'NetworkSummary'
    name = _(u'Network Summary')
    type = 'opennetwork'
    icon = u'SettingsIcon'


class GlobalConf(TreeNode):

    gname = 'GlobalConfiguration'
    name = _(u'Global Configuration')
    type = 'opennetwork'
    icon = u'SettingsIcon'
    append_to = 'network'


class Linkss(TreeNode):

    gname = 'LAGGInterface'
    model = 'LAGGInterface'
    app_name = 'network'
    name = _(u'Link Aggregations')
    icon = u'LAGGIcon'

    def __init__(self, *args, **kwargs):

        super(Linkss, self).__init__(*args, **kwargs)

        laggadd = TreeNode('Add')
        laggadd.name = _(u'Create Link Aggregation')
        laggadd.view = 'freeadmin_network_lagginterface_add'
        laggadd.type = 'object'
        laggadd.icon = u'AddLAGGIcon'
        laggadd.model = 'LAGGInterface'
        laggadd.app_name = 'network'

        laggview = TreeNode('View')
        laggview.gname = 'View'
        laggview.name = _(u'View Link Aggregations')
        laggview.type = 'opennetwork'
        laggview.icon = u'ViewAllLAGGsIcon'
        laggview.model = 'LAGGInterface'
        laggview.app_name = 'network'
        self.append_children([laggadd, laggview])

        for value, name in LAGGType:

            laggs = models.LAGGInterface.objects.filter(lagg_protocol__exact=value)
            if laggs.count() > 0:
                nav = TreeNode()
                nav.name = name
                nav.icon = u'LAGGIcon'
                nav._children = []
                self.append_child(nav)

            for lagg in laggs:

                subnav = TreeNode()
                subnav.name = lagg.lagg_interface.int_name
                subnav.icon = u'LAGGIcon'
                subnav._children = []
                nav.append_child(subnav)

                laggm = models.LAGGInterfaceMembers.objects.filter(\
                        lagg_interfacegroup__exact=lagg.id).order_by('lagg_ordernum')
                for member in laggm:
                    subsubnav = TreeNode()
                    subsubnav.name = member.lagg_physnic
                    subsubnav.type = 'editobject'
                    subsubnav.icon = u'LAGGIcon'
                    subsubnav.view = 'freeadmin_network_lagginterfacemembers_edit'
                    subsubnav.app_name = 'network'
                    subsubnav.model = 'LAGGInterfaceMembers'+lagg.lagg_interface.int_name
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

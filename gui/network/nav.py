from freeadmin.tree import TreeNode
from freenasUI.choices import LAGGType
from django.utils.translation import ugettext as _
import models

ICON = u'NetworkIcon'

class NetSummary(TreeNode):

        name = _(u'Network Summary')
        type = 'network_summary'
        icon = u'SettingsIcon'
        app_name = 'network'

class GlobalConf(TreeNode):

        name = _(u'Global Configuration')
        type = 'network_global'
        model = 'GlobalConfiguration'
        icon = u'SettingsIcon'
        app_name = 'network'

class AddLagg(TreeNode):

        name = _(u'Add Link Aggregation')
        rename = _(u'Create Link Aggregation')
        view = 'network_lagg_add'
        type = 'object'
        icon = u'AddLAGGIcon'
        model = 'LAGGInterface'
        app_name = 'network'
        append_app = False

class ViewLagg(TreeNode):

        name = _(u'View All Link Aggregations')
        type = 'viewlagg'
        icon = u'ViewAllLAGGsIcon'
        model = 'LAGGInterface'
        app_name = 'network'
        append_app = False

class Linkss(TreeNode):

    model = 'LAGGInterface'
    app_name = 'network'
    name = _(u'Link Aggregations')
    icon = u'LAGGIcon'

    def __init__(self, *args, **kwargs):

        #self.name = models.LAGGInterface._meta.verbose_name
        self._children = [AddLagg(),ViewLagg()]

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
                    subsubnav.view = 'freeadmin_model_edit'
                    subsubnav.app_name = 'network'
                    subsubnav.model = 'LAGGInterfaceMembers'+lagg.lagg_interface.int_name
                    subsubnav.kwargs = {'app': 'network', 'model': 'LAGGInterfaceMembers', \
                            'oid': member.id}
                    subsubnav.append_url = '?deletable=false'
                    subsubnav._children = []
                    subnav.append_child(subsubnav)

        laggs = models.LAGGInterface

class ViewInterfaces(TreeNode):

        name = _(u'View All Interfaces')
        type = 'viewinterfaces'
        append_app = False

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.Interfaces._admin.icon_view
            super(ViewInterfaces, self).__init__(*args, **kwargs)

class ViewVLAN(TreeNode):

        name = _(u'View All VLANs')
        type = 'viewvlans'
        append_app = False

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.VLAN._admin.icon_view
            super(ViewVLAN, self).__init__(*args, **kwargs)

class ViewSR(TreeNode):

        name = _(u'View All Static Routes')
        type = 'viewsr'
        append_app = False

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.StaticRoute._admin.icon_view
            super(ViewSR, self).__init__(*args, **kwargs)

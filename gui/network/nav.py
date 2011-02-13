from django_nav import Nav, NavOption
import models

class AddLagg(NavOption):

        name = u'Add Link'
        view = 'network_lagg_add'
        type = 'object'
        icon = u'AddLAGGIcon'
        model = 'LAGGInterface'
        app_name = 'network'
        append_app = False
        options = []

class ViewLagg(NavOption):

        name = u'View All Links'
        type = 'viewlagg'
        icon = u'ViewAllLAGGsIcon'
        model = 'LAGGInterface'
        app_name = 'network'
        append_app = False
        options = []

class ViewInterfaces(NavOption):

        name = u'View All Interfaces'
        type = 'viewinterfaces'
        append_app = False
        options = []

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.Interfaces._admin.icon_view
            super(ViewInterfaces, self).__init__(*args, **kwargs)

class ViewVLAN(NavOption):

        name = u'View All VLANs'
        type = 'viewvlans'
        append_app = False
        options = []

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.VLAN._admin.icon_view
            super(ViewVLAN, self).__init__(*args, **kwargs)

class ViewSR(NavOption):

        name = u'View All Static Routes'
        type = 'viewsr'
        append_app = False
        options = []

        def __init__(self, *args, **kwargs):
            if models.Interfaces._admin.icon_view is not None:
                self.icon = models.StaticRoute._admin.icon_view
            super(ViewSR, self).__init__(*args, **kwargs)

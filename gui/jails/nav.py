from django.utils.translation import ugettext_lazy as _

from . import models
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.common.warden import Warden

NAME = _('Jails')
BLACKLIST = []
ICON = u'ServicesIcon'

class JailsSettings(TreeNode):

    gname = 'Settings'
    name = _(u'Settings')
    type = 'object'
    icon = u"SettingsIcon"
    skip = True

    def __init__(self, *args, **kwargs):
        super(JailsSettings, self).__init__(*args, **kwargs)


class JailsManagement(TreeNode):

    gname = 'management'
    name = _(u'Management')
    icon = u"SettingsIcon"
    #skip = True
    #order = -1

    def __init__(self, *args, **kwargs):
        super(JailsManagement, self).__init__(*args, **kwargs)
        self.append_children([JailsSettings()])

#        jails = Warden().list()
#        for jail in jails:
#            nav = TreeNode()
#            nav.name = jail['host']
#            nav.icon = u'SettingsIcon'
#            nav._children = []
#            self.append_child(nav)

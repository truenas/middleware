from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

BLACKLIST = ['Email', 'Advanced', 'Settings', 'SSL', 'Registration']
NAME = _('System')
ICON = u'SystemIcon'


class Info(TreeNode):

    gname = 'SysInfo'
    name = _(u'System Information')
    view = 'system_info'
    icon = u"InfoIcon"
    type = 'opensystem'


class Settings(TreeNode):

    gname = 'Settings'
    name = _(u'Settings')
    view = 'system_settings'
    icon = u"SettingsIcon"
    type = 'opensystem'

from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

BLACKLIST = [
    'Advanced',
    'Email',
    'NTPServer',
    'Settings',
    'SSL',
    'SystemDataset',
    'Registration',
]
NAME = _('System')
ICON = u'SystemIcon'
ORDER = 1


class Advanced(TreeNode):

    gname = 'Advanced'
    name = _(u'Advanced')
    icon = u"SettingsIcon"
    type = 'opensystem'
    order = -90

class Email(TreeNode):

    gname = 'Email'
    name = _(u'Email')
    icon = 'EmailIcon'
    type = 'opensystem'
    order = -85


class General(TreeNode):

    gname = 'General'
    name = _(u'General')
    icon = u"SettingsIcon"
    type = 'opensystem'
    order = -95


class Info(TreeNode):

    gname = 'SysInfo'
    name = _(u'Information')
    icon = u"InfoIcon"
    type = 'opensystem'
    order = -100


class SystemDataset(TreeNode):

    gname = 'SystemDataset'
    name = _(u'System Dataset')
    icon = u"SysDatasetIcon"
    type = 'opensystem'
    order = -80


class TunableView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.Tunable'

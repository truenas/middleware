from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

BLACKLIST = ['Email', 'Advanced', 'Settings', 'SSL', 'SystemDataset', 'Registration']
NAME = _('System')
ICON = u'SystemIcon'
ORDER = 1


class Advanced(TreeNode):

    gname = 'Advanced'
    name = _(u'Advanced')
    icon = u"SettingsIcon"
    type = 'opensystem'


class Email(TreeNode):

    gname = 'Email'
    name = _(u'Email')
    icon = u"SettingsIcon"
    type = 'opensystem'


class General(TreeNode):

    gname = 'General'
    name = _(u'General')
    icon = u"SettingsIcon"
    type = 'opensystem'


class Info(TreeNode):

    gname = 'SysInfo'
    name = _(u'System Information')
    icon = u"InfoIcon"
    type = 'opensystem'


class SSL(TreeNode):

    gname = 'SSL'
    name = _(u'SSL')
    icon = u"SettingsIcon"
    type = 'opensystem'


class SystemDataset(TreeNode):

    gname = 'SystemDataset'
    name = _(u'System Dataset')
    icon = u"SettingsIcon"
    type = 'opensystem'

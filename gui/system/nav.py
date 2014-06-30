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


class CronJobView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.CronJob'


class Email(TreeNode):

    gname = 'Email'
    name = _(u'Email')
    icon = 'EmailIcon'
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


class InitShutdownView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.InitShutdown'


class NTPServerView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.NTPServer'


class RsyncView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.Rsync'


class SMARTTestView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.SMARTTest'


class SSL(TreeNode):

    gname = 'SSL'
    name = _(u'SSL')
    icon = "SSLIcon"
    type = 'opensystem'


class SysctlView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.Sysctl'


class SystemDataset(TreeNode):

    gname = 'SystemDataset'
    name = _(u'System Dataset')
    icon = u"SysDatasetIcon"
    type = 'opensystem'


class TunableView(TreeNode):

    gname = 'View'
    type = 'opensystem'
    append_to = 'system.Tunable'

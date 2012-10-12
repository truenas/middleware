from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

BLACKLIST = ['Email', 'Advanced', 'Settings', 'SSL']
NAME = _('System')
ICON = u'SystemIcon'


class Reporting(TreeNode):

    gname = 'Reporting'
    name = _(u'Reporting')
    view = 'system_reporting'
    icon = u"ReportingIcon"


class Info(TreeNode):

    gname = 'SysInfo'
    name = _(u'System Information')
    view = 'system_info'
    icon = u"InfoIcon"


class Settings(TreeNode):

    gname = 'Settings'
    name = _(u'Settings')
    view = 'system_settings'
    icon = u"SettingsIcon"


class ViewCron(TreeNode):

    gname = 'View'
    view = 'system_cronjobs'
    append_to = 'system.CronJob'


class ViewRsync(TreeNode):

    gname = 'View'
    view = 'system_rsyncs'
    append_to = 'system.Rsync'


class ViewSmarttest(TreeNode):

    gname = 'View'
    view = 'system_smarttests'
    append_to = 'system.SMARTTest'

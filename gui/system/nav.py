from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

BLACKLIST = ['Email', 'Advanced', 'Settings', 'SSL']
ICON = u'SystemIcon'

class Reporting(TreeNode):

        name = _(u'Reporting')
        view = 'system_reporting'
        icon = u"ReportingIcon"

class Info(TreeNode):

        name = _(u'System Information')
        view = 'system_info'
        icon = u"InfoIcon"

class Settings(TreeNode):

        name = _(u'Settings')
        view = 'system_settings'
        icon = u"SettingsIcon"

class ViewCron(TreeNode):

        gname = 'system.CronJob.View'
        type = 'opencron'
        append_app = False

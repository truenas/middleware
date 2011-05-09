from freeadmin.tree import TreeNode
from django.utils.translation import ugettext as _

BLACKLIST = ['Email', 'Advanced', 'Settings', 'SSL']
ICON = u'SystemIcon'

class Reporting(TreeNode):

        name = _(u'Reporting')
        view = 'system_reporting'
        icon = u"ReportingIcon"
        options = []

class Info(TreeNode):

        name = _(u'System Information')
        view = 'system_info'
        icon = u"InfoIcon"
        options = []

class Settings(TreeNode):

        name = _(u'Settings')
        view = 'system_settings'
        icon = u"SettingsIcon"
        options = []

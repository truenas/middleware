from django_nav import Nav, NavOption
from django.utils.translation import ugettext as _

BLACKLIST = ['Email', 'Advanced', 'Settings']
ICON = u'SystemIcon'

class Reporting(NavOption):

        name = _(u'Reporting')
        view = 'system_reporting'
        icon = u"ReportingIcon"
        options = []

class Info(NavOption):

        name = _(u'System Information')
        view = 'system_info'
        icon = u"InfoIcon"
        options = []

class Settings(NavOption):

        name = _(u'Settings')
        view = 'system_settings'
        icon = u"SettingsIcon"
        options = []

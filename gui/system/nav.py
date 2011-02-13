from django_nav import Nav, NavOption

BLACKLIST = ['Email', 'Advanced', 'Settings']

class Reporting(NavOption):
        """
        This is a Navigation Option, which can be used to build drop down menus
        """
        name = u'Reporting'
        view = 'system_reporting'
        icon = u"ReportingIcon"
        options = []

class Info(NavOption):
        """
        This is a Navigation Option, which can be used to build drop down menus
        """
        name = u'System Information'
        view = 'system_info'
        icon = u"InfoIcon"
        options = []

class Settings(NavOption):
        """
        This is a Navigation Option, which can be used to build drop down menus
        """
        name = u'Settings'
        view = 'system_settings'
        icon = u"SettingsIcon"
        options = []

from django_nav import Nav, NavOption
import models

class Reporting(NavOption):
        """
        This is a Navigation Option, which can be used to build drop down menus
        """
        name = u'Reporting'
        view = 'system_test1'
        options = []


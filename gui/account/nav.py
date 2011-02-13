from django_nav import Nav, NavOption
import models

class ChangePass(NavOption):

        name = u'Change Password'
        type = 'changepass'
        icon = u'ChangePasswordIcon'
        append_app = False
        options = []

class ChangeAdmin(NavOption):

        name = u'Change Admin User'
        type = 'changeadmin'
        icon = u'ChangeAdminIcon'
        append_app = False
        options = []

class Logout(NavOption):

        name = u'Logout'
        type = 'logout'
        icon = u'LogOutIcon'
        append_app = False
        options = []

class MyAccount(NavOption):

        name = u'My Account'
        icon = u'MyAccountIcon'
        order = -1
        options = [ChangePass, ChangeAdmin, Logout]

class ViewUsers(NavOption):

        name = u'View All Users'
        type = 'viewusers'
        icon = u'ViewAllUsersIcon'
        append_app = False
        options = []

        def __init__(self, *args, **kwargs):
            if models.bsdUsers._admin.icon_view is not None:
                icon = models.bsdUsers._admin.icon_view
            super(ViewUsers, self).__init__(*args, **kwargs)

class ViewGroups(NavOption):

        name = u'View All Groups'
        type = 'viewgroups'
        icon = u'ViewAllGroupsIcon'
        append_app = False
        options = []

        def __init__(self, *args, **kwargs):
            if models.bsdGroups._admin.icon_view is not None:
                icon = models.bsdGroups._admin.icon_view
            super(ViewGroups, self).__init__(*args, **kwargs)

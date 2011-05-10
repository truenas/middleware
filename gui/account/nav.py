from freeadmin.tree import TreeNode
from django.utils.translation import ugettext as _
import models

ICON = u'AccountIcon'

class ChangePass(TreeNode):

        name = _('Change Password')
        type = 'changepass'
        icon = u'ChangePasswordIcon'
        append_app = False
        _children = []

class ChangeAdmin(TreeNode):

        name = _('Change Admin User')
        type = 'changeadmin'
        icon = u'ChangeAdminIcon'
        append_app = False
        _children = []

#class Logout(TreeNode):
#
#        name = _('Logout')
#        type = 'logout'
#        icon = u'LogOutIcon'
#        append_app = False
#        _children = []

class MyAccount(TreeNode):

        name = _('My Account')
        icon = u'MyAccountIcon'
        order = -1
        #_children = [ChangePass, ChangeAdmin, Logout]
        #_children = [ChangePass, ChangeAdmin]

class ViewUsers(TreeNode):

        name = _('View All Users')
        type = 'viewusers'
        icon = u'ViewAllUsersIcon'
        append_app = False
        _children = []

        def __init__(self, *args, **kwargs):
            if models.bsdUsers._admin.icon_view is not None:
                self.icon = models.bsdUsers._admin.icon_view
            super(ViewUsers, self).__init__(*args, **kwargs)

class ViewGroups(TreeNode):

        name = _('View All Groups')
        type = 'viewgroups'
        icon = u'ViewAllGroupsIcon'
        append_app = False
        _children = []

        def __init__(self, *args, **kwargs):
            if models.bsdGroups._admin.icon_view is not None:
                self.icon = models.bsdGroups._admin.icon_view
            super(ViewGroups, self).__init__(*args, **kwargs)

from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
import models

NAME = _('Account')
ICON = u'AccountIcon'

class ChangePass(TreeNode):

        gname = 'account.ChangePass'
        name = _('Change Password')
        type = 'openaccount'
        icon = u'ChangePasswordIcon'
        append_app = False

class ChangeAdmin(TreeNode):

        gname = 'account.ChangeAdmin'
        name = _('Change Admin User')
        type = 'openaccount'
        icon = u'ChangeAdminIcon'
        append_app = False

class MyAccount(TreeNode):

        name = _('My Account')
        icon = u'MyAccountIcon'
        order = -1
        def __init__(self, *args, **kwargs):
            super(MyAccount, self).__init__(*args, **kwargs)
            self.append_children([ChangePass(), ChangeAdmin()])

class ViewUsers(TreeNode):

        gname = 'account.bsdUsers.View'
        name = _('View All Users')
        type = 'openaccount'
        append_app = False

class ViewGroups(TreeNode):

        gname = 'account.bsdGroups.View'
        name = _('View All Groups')
        type = 'openaccount'
        append_app = False

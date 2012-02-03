from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
from . import models

NAME = _('Account')
ICON = u'AccountIcon'

class AdminAccount(TreeNode):

    gname = 'AdminAccount'
    name = _('Admin Account')
    icon = u'AdminAccountIcon'
    def __init__(self, *args, **kwargs):
        super(AdminAccount, self).__init__(*args, **kwargs)

        chpw = TreeNode('ChangePass')
        chpw.name = _('Change Password')
        chpw.type = 'openaccount'
        chpw.icon = u'ChangePasswordIcon'

        chad = TreeNode('ChangeAdmin')
        chad.name = _('Change Admin User')
        chad.type = 'openaccount'
        chad.icon = u'ChangeAdminIcon'
        self.append_children([chpw, chad])

class ViewUsers(TreeNode):

    gname = 'account.bsdUsers.View'
    type = 'openaccount'
    append_app = False

class ViewGroups(TreeNode):

    gname = 'account.bsdGroups.View'
    type = 'openaccount'
    append_app = False

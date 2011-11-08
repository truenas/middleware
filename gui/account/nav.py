from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
import models

NAME = _('Account')
ICON = u'AccountIcon'

class MyAccount(TreeNode):

    gname = 'MyAccount'
    name = _('My Account')
    icon = u'MyAccountIcon'
    order = -1
    def __init__(self, *args, **kwargs):
        super(MyAccount, self).__init__(*args, **kwargs)

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
    name = _('View All Users')
    type = 'openaccount'
    append_app = False

class ViewGroups(TreeNode):

    gname = 'account.bsdGroups.View'
    name = _('View All Groups')
    type = 'openaccount'
    append_app = False

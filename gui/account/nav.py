from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

NAME = _('Account')
ICON = u'AccountIcon'
BLACKLIST = ['bsdGroupMembership']


class ViewUsers(TreeNode):

    gname = 'View'
    type = 'openaccount'
    append_to = 'account.bsdUsers'


class ViewGroups(TreeNode):

    gname = 'View'
    type = 'openaccount'
    append_to = 'account.bsdGroups'

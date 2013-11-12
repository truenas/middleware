from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

NAME = _('Sharing')
BLACKLIST = ['NFS_Share_Path']
ICON = u'SharingIcon'
ORDER = 30


class ViewUNIX(TreeNode):

    gname = 'View'
    type = 'opensharing'
    append_to = 'sharing.NFS_Share'


class ViewApple(TreeNode):

    gname = 'View'
    type = 'opensharing'
    append_to = 'sharing.AFP_Share'


class ViewWin(TreeNode):

    gname = 'View'
    type = 'opensharing'
    append_app = False
    append_to = 'sharing.CIFS_Share'

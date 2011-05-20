from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

NAME = _('Sharing')
ICON = u'SharingIcon'

class ViewUNIX(TreeNode):

        gname = 'sharing.NFS_Share.View'
        type = 'opensharing'
        append_app = False

class ViewApple(TreeNode):

        gname = 'sharing.AFP_Share.View'
        type = 'opensharing'
        append_app = False

class ViewWin(TreeNode):

        gname = 'sharing.CIFS_Share.View'
        type = 'opensharing'
        append_app = False

from freeadmin.tree import TreeNode
from django.utils.translation import ugettext as _

ICON = u'SharingIcon'

class ViewUNIX(TreeNode):

        gname = 'sharing.NFS_Share.View'
        name = _(u'View All UNIX Shares')
        type = 'opensharing'
        icon = u'ViewAllUNIXSharesIcon'
        app_name = 'sharing'
        model = 'NFS_Share'
        append_app = False

class ViewApple(TreeNode):

        gname = 'sharing.AFP_Share.View'
        name = _(u'View All Apple Shares')
        type = 'opensharing'
        icon = u'ViewAllAppleSharesIcon'
        app_name = 'sharing'
        model = 'AFP_Share'
        append_app = False

class ViewWin(TreeNode):

        gname = 'sharing.CIFS_Share.View'
        name = _(u'View All Windows Shares')
        type = 'opensharing'
        icon = u'ViewAllWindowsSharesIcon'
        app_name = 'sharing'
        model = 'CIFS_Share'
        append_app = False

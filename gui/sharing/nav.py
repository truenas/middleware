from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode
from freenasUI.support.utils import fc_enabled

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


class ViewWebDAV(TreeNode):

    gname = 'View'
    type = 'opensharing'
    append_app = False
    append_to = 'sharing.WebDAV_Share'


class ISCSI(TreeNode):

    order = 40
    gname = 'ISCSI'
    type = u'iscsi'
    icon = u'iSCSIIcon'

    @property
    def rename(self):
        return u'%s (%s%s)' % (
            _('Block'),
            _('iSCSI'),
            u'/' + unicode(_('FC')) if fc_enabled() else '',
        )

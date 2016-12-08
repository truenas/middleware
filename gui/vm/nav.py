from freenasUI.freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _

NAME = _('VMs')
BLACKLIST = []
ICON = u'VMsIcon'
ORDER = 90


class VMView(TreeNode):

    gname = 'View'
    type = 'openvm'
    append_to = 'vm.VM'

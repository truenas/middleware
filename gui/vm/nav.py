from django.utils.translation import ugettext_lazy as _
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.vm.utils import vm_enabled

NAME = _('VMs')
BLACKLIST = ['Device']
ICON = u'VMsIcon'
ORDER = 90


def init(tree_roots, nav, request):
    if not vm_enabled():
        tree_roots.unregister(nav)


class VMView(TreeNode):

    gname = 'View'
    type = 'openvm'
    append_to = 'vm.VM'

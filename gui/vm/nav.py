from django.utils.translation import ugettext_lazy as _
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.support.utils import vm_enabled

NAME = _('VMs')
BLACKLIST = ['VM', 'Device']
ICON = 'VMIcon'
URL = 'vm_home'
ORDER = 75


def init(tree_roots, nav, request):

    if not vm_enabled():
        tree_roots.unregister(nav)


# TODO: For when we have more than just VM tab
#class VMView(TreeNode):
#
#    gname = 'View'
#    type = 'openvm'
#    append_to = 'vm.VM'

from django.utils.translation import ugettext_lazy as _
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.vm.utils import vm_enabled

NAME = _('VMs')
BLACKLIST = ['VM', 'Device']
ICON = 'VMIcon'
URL = 'vm_home'
ORDER = 75

# TODO: For when we have more than just VM tab
#class VMView(TreeNode):
#
#    gname = 'View'
#    type = 'openvm'
#    append_to = 'vm.VM'

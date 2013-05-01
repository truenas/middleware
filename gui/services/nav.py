from django.utils.translation import ugettext_lazy as _

from . import models
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.services.directoryservice import DirectoryService
from freenasUI.services.models import (
    ActiveDirectory,
    NT4,
    NIS,
    LDAP
)
    
import logging
log = logging.getLogger('services.nav')

NAME = _('Services')
ICON = u'ServicesIcon'
BLACKLIST = [
    'services',
    'iSCSITargetPortalIP',
    'RPCToken',
    'ActiveDirectory',
    'NT4',
    'NIS',
    'LDAP'
]


class EnDisServices(TreeNode):

    gname = 'services.ControlServices'
    name = _(u'Control Services')
    type = u'en_dis_services'
    icon = u'ServicesIcon'
    order = -1


class ISCSITargetAuthorizedInitiatorView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITargetAuthorizedInitiator'


class ISCSITargetAuthCredentialView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITargetAuthCredential'


class ISCSITargetPortalView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITargetPortal'


class ISCSITargetToExtentView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITargetToExtent'


class ISCSITargetView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITarget'


class ISCSITargetExtentView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'services.ISCSI.iSCSITargetExtent'


class ISCSI(TreeNode):

    gname = 'ISCSI'
    name = _(u'iSCSI')
    type = u'iscsi'
    icon = u'iSCSIIcon'


class Rsync(TreeNode):

    gname = 'Rsync'
    name = _(u'Rsync')
    type = u'rsync'
    icon = u'rsyncIcon'


class RsyncModAdd(TreeNode):

    gname = 'Add'
    name = _(u'Add Rsync Module')
    type = u'object'
    view = u'freeadmin_services_rsyncmod_add'
    kwargs = {'mf': 'RsyncModForm'}
    icon = u'AddrsyncModIcon'
    append_to = 'services.Rsync.RsyncMod'


class RsyncModView(TreeNode):

    gname = 'View'
    name = _(u'View Rsync Modules')
    view = u'freeadmin_services_rsyncmod_datagrid'
    icon = u'ViewAllrsyncModIcon'
    append_to = 'services.Rsync.RsyncMod'

class DirectoryServiceView(TreeNode):

    gname = 'Directory Service'
    name = _(u'Directory Service')
    icon = u'DirectoryServiceIcon'

    def __init__(self, *args, **kwargs):
        super(DirectoryServiceView, self).__init__(*args, **kwargs)

        ad_node = self.new_activedirectory_node()
        nt4_node = self.new_nt4_node()
        nis_node = self.new_nis_node()
        ldap_node = self.new_ldap_node()

        self.append_children([ad_node, nt4_node, nis_node, ldap_node])

    def new_activedirectory_node(self):
        ad_node = TreeNode("Active Directory")

        ad_node.name = 'Active Directory'
        ad_node.app_name = 'activedirectory'
        ad_node.icon = u'ActiveDirectoryIcon'

        try:
            ad = ActiveDirectory.objects.order_by("-id")[0]
            ad_node.kwargs = { 'oid': ad.id }
            ad_node.type = 'editobject'
            ad_node.view = 'freeadmin_services_activedirectory_edit'

        except:
            ad_node.type = 'object'
            ad_node.view = 'freeadmin_services_activedirectory_add'

        return ad_node

    def new_nt4_node(self):
        nt4_node = TreeNode("NT4")

        nt4_node.name = 'NT4'
        nt4_node.app_name = 'nt4'
        nt4_node.icon = u'NT4Icon'

        try:
            nt4 = NT4.objects.order_by("-id")[0]
            nt4_node.kwargs = { 'oid': nt4.id }
            nt4_node.type = 'editobject'
            nt4_node.view = 'freeadmin_services_nt4_edit'

        except:
            nt4_node.type = 'object'
            nt4_node.view = 'freeadmin_services_nt4_add'

        return nt4_node

    def new_nis_node(self):
        nis_node = TreeNode("NIS")

        nis_node.name = 'NIS'
        nis_node.app_name = 'nis'
        nis_node.icon = u'NISIcon'

        try:
            nis = NIS.objects.order_by("-id")[0]
            nis_node.kwargs = { 'oid': nis.id }
            nis_node.type = 'editobject'
            nis_node.view = 'freeadmin_services_nis_edit'

        except:
            nis_node.type = 'object'
            nis_node.view = 'freeadmin_services_nis_add'

        return nis_node

    def new_ldap_node(self):
        ldap_node = TreeNode("LDAP")

        ldap_node.name = 'LDAP'
        ldap_node.app_name = 'ldap'
        ldap_node.icon = u'LDAPIcon'

        try:
            ldap = LDAP.objects.order_by("-id")[0]
            ldap_node.kwargs = { 'oid': ldap.id }
            ldap_node.type = 'editobject'
            ldap_node.view = 'freeadmin_services_ldap_edit'

        except:
            ldap_node.type = 'object'
            ldap_node.view = 'freeadmin_services_ldap_add'

        return ldap_node

import logging

from django.utils.translation import ugettext_lazy as _

from freenasUI.freeadmin.tree import TreeNode
from freenasUI.support.utils import fc_enabled

log = logging.getLogger('services.nav')

NAME = _('Services')
ICON = u'ServicesIcon'
BLACKLIST = [
    'services',
    'iSCSITargetPortalIP',
    'iSCSITargetGroups',
    'RPCToken',
    'CIFS',
    'S3',
]
ORDER = 40


class ISCSINameMixin(object):

    @property
    def rename(self):
        if fc_enabled():
            return u'%s (%s)' % (self.name, _('iSCSI'))
        return self.name


class EnDisServices(TreeNode):

    gname = 'services.ControlServices'
    name = _(u'Control Services')
    type = u'en_dis_services'
    icon = u'ServicesIcon'
    order = -1


class CIFSView(TreeNode):

    gname = 'services.CIFS'
    name = _(u'SMB')
    type = u'object'
    view = u'services_cifs'
    icon = u'CIFSIcon'


class ISCSITargetAuthorizedInitiator(TreeNode, ISCSINameMixin):

    gname = 'iSCSITargetAuthorizedInitiator'
    append_to = 'sharing.ISCSI'


class ISCSITargetAuthorizedInitiatorView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITargetAuthorizedInitiator'


class ISCSITargetAuthCredential(TreeNode, ISCSINameMixin):

    gname = 'iSCSITargetAuthCredential'
    append_to = 'sharing.ISCSI'


class ISCSITargetAuthCredentialView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITargetAuthCredential'


class ISCSITargetPortal(TreeNode, ISCSINameMixin):

    gname = 'iSCSITargetPortal'
    append_to = 'sharing.ISCSI'


class ISCSITargetPortalView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITargetPortal'


class ISCSITargetToExtentView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITargetToExtent'


class ISCSITargetView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITarget'


class ISCSITargetExtentView(TreeNode):

    gname = 'View'
    type = u'iscsi'
    append_to = 'sharing.ISCSI.iSCSITargetExtent'


class ISCSI(TreeNode):

    gname = 'ISCSI'
    name = _(u'iSCSI')
    type = u'iscsi'
    icon = u'iSCSIIcon'


class FibreChannelPorts(TreeNode):

    gname = 'FCPorts'
    name = _('Fibre Channel Ports')
    type = u'iscsi'
    icon = u'FibreIcon'
    append_to = 'sharing.ISCSI'
    order = 100

    def pre_build_options(self):
        if not fc_enabled():
            raise ValueError


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


class S3View(TreeNode):

    gname = 'services.S3'
    name = _(u'S3')
    type = u'object'
    view = u'services_s3'
    icon = u'S3Icon'

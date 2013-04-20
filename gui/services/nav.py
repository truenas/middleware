from django.utils.translation import ugettext_lazy as _

from . import models
from freenasUI.middleware.notifier import notifier
from freenasUI.freeadmin.tree import TreeNode

NAME = _('Services')
BLACKLIST = ['services', 'iSCSITargetPortalIP', 'RPCToken']
ICON = u'ServicesIcon'


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

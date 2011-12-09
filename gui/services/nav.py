from django.utils.translation import ugettext_lazy as _

from freenasUI.middleware.notifier import notifier
from freeadmin.tree import TreeNode
from . import models

NAME = _('Services')
BLACKLIST = ['services']
ICON = u'ServicesIcon'

class EnDisServices(TreeNode):

    gname = 'services.ControlServices'
    name = _(u'Control Services')
    type = u'en_dis_services'
    icon = u'ServicesIcon'
    order = -1

class ISCSITargetAuthorizedInitiatorView(TreeNode):

    gname = 'services.ISCSI.iSCSITargetAuthorizedInitiator.View'
    type = u'iscsi'
    append_app = False

class ISCSITargetAuthCredentialView(TreeNode):

    gname = 'services.ISCSI.iSCSITargetAuthCredential.View'
    type = u'iscsi'
    append_app = False

class ISCSITargetPortalView(TreeNode):

    gname = 'services.ISCSI.iSCSITargetPortal.View'
    type = u'iscsi'
    append_app = False

class ISCSITargetToExtentView(TreeNode):

    gname = 'services.ISCSI.iSCSITargetToExtent.View'
    type = u'iscsi'
    append_app = False

class ISCSITargetView(TreeNode):

    gname = 'services.ISCSI.iSCSITarget.View'
    type = u'iscsi'
    append_app = False

class ISCSIDevice(TreeNode):

    gname = 'iSCSITargetDeviceExtent'
    name = _(u'Device Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    append_app = False

    def __init__(self, *args, **kwargs):

        super(ISCSIDevice, self).__init__(*args, **kwargs)
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__in=['Disk','ZVOL']).order_by('-id'):
            nav = TreeNode(ext.id)
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id, 'mf': 'iSCSITargetDeviceExtentForm'}
            nav.icon = u'ExtentIcon'
            self.insert_child(0, nav)

        devadd = TreeNode('Add')
        devadd.name = _(u'Add Device Extent')
        devadd.type = u'object'
        devadd.view = u'freeadmin_model_add'
        devadd.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'mf': 'iSCSITargetDeviceExtentForm'}
        devadd.icon = u'AddExtentIcon'

        devview = TreeNode('View')
        devview.name = _(u'View All Device Extents')
        devview.type = u'iscsi'
        devview.icon = u'ViewAllExtentsIcon'
        devview.append_app = False
        devview.app_name = 'services'
        devview.model = 'DExtents'

        self.append_children([devadd, devview])


class ISCSIExt(TreeNode):

    gname = 'services.ISCSI.iSCSITargetExtent'
    name = _(u'Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    append_app = False

    def __init__(self, *args, **kwargs):

        super(ISCSIExt, self).__init__(*args, **kwargs)
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__exact='File').order_by('-id'):
            nav = TreeNode(ext.id)
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id}
            nav.icon = u'ExtentIcon'
            self.append_child(nav)

        extadd = TreeNode('Add')
        extadd.name = _(u'Add Extent')
        extadd.type = u'object'
        extadd.view = u'freeadmin_model_add'
        extadd.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
        extadd.icon = u'AddExtentIcon'

        extview = TreeNode('View')
        extview.name = _(u'View All Extents')
        extview.type = u'iscsi'
        extview.view = u'freeadmin_model_datagrid'
        extview.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
        extview.icon = u'ViewAllExtentsIcon'
        extview.app_name = 'services'
        extview.model = 'Extents'

        self.append_children([extadd, extview])

class ISCSI(TreeNode):

    gname = 'ISCSI'
    name = _(u'ISCSI')
    type = u'iscsi'
    icon = u'iSCSIIcon'

    def __init__(self, *args, **kwargs):
        super(ISCSI, self).__init__(*args, **kwargs)
        self.append_children([ISCSIDevice()])

class Rsync(TreeNode):

    gname = 'Rsync'
    name = _(u'Rsync')
    type = u'rsync'
    icon = u'rsyncIcon'

class RsyncModAdd(TreeNode):

    gname = 'services.Rsync.RsyncMod.Add'
    name = _(u'Add Rsync Module')
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'RsyncMod', 'mf': 'RsyncModForm'}
    icon = u'AddrsyncModIcon'
    append_app = False

class RsyncModView(TreeNode):

    gname = 'services.Rsync.RsyncMod.View'
    name = _(u'View Rsync Modules')
    view = u'services_rsyncmod'
    icon = u'ViewAllrsyncModIcon'
    append_app = False

class Plugins(TreeNode):

    gname = 'Plugins'
    name = _(u'Plugins')
    type = 'object'

    def __init__(self, *args, **kwargs):
        super(Plugins, self).__init__(*args, **kwargs)
        if notifier().plugins_jail_configured():
            oid = models.Plugins.objects.order_by('-id')[0].id
            self.view = 'freeadmin_model_edit'
            self.kwargs = {'app': 'services', 'model': 'Plugins', 'oid': oid}
        else:
            self.view = 'plugins_jailpbi'

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


class ISCSIDevice(TreeNode):

    gname = 'iSCSITargetDeviceExtent'
    name = _(u'Device Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    skip = True

    def __init__(self, *args, **kwargs):

        super(ISCSIDevice, self).__init__(*args, **kwargs)
        for ext in models.iSCSITargetExtent.objects.filter(
            iscsi_target_extent_type__in=['Disk', 'ZVOL']).order_by(
            'iscsi_target_extent_name'):
            nav = TreeNode(ext.id)
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services',
                'model': 'iSCSITargetExtent',
                'oid': ext.id,
                'mf': 'iSCSITargetDeviceExtentForm'}
            nav.icon = u'ExtentIcon'
            self.insert_child(0, nav)

        devadd = TreeNode('Add')
        devadd.name = _(u'Add Device Extent')
        devadd.type = u'object'
        devadd.order = 100
        devadd.view = u'freeadmin_model_add'
        devadd.kwargs = {'app': 'services',
            'model': 'iSCSITargetExtent',
            'mf': 'iSCSITargetDeviceExtentForm'}
        devadd.icon = u'AddExtentIcon'

        devview = TreeNode('View')
        devview.name = _(u'View Device Extents')
        devview.type = u'iscsi'
        devview.order = 101
        devview.icon = u'ViewAllExtentsIcon'
        devview.append_app = False
        devview.app_name = 'services'
        devview.model = 'DExtents'

        self.append_children([devadd, devview])


class ISCSIExt(TreeNode):

    gname = 'iSCSITargetExtent'
    name = _(u'File Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    append_to = 'services.ISCSI'

    def __init__(self, *args, **kwargs):

        super(ISCSIExt, self).__init__(*args, **kwargs)
        for ext in models.iSCSITargetExtent.objects.filter(
            iscsi_target_extent_type__exact='File').order_by(
            'iscsi_target_extent_name'):
            nav = TreeNode(ext.id)
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services',
                'model': 'iSCSITargetExtent',
                'oid': ext.id}
            nav.icon = u'ExtentIcon'
            self.append_child(nav)

        extadd = TreeNode('Add')
        extadd.name = _(u'Add File Extent')
        extadd.type = u'object'
        extadd.order = 100
        extadd.view = u'freeadmin_model_add'
        extadd.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
        extadd.icon = u'AddExtentIcon'

        extview = TreeNode('View')
        extview.name = _(u'View File Extents')
        extview.type = u'iscsi'
        extview.order = 101
        extview.view = u'freeadmin_model_datagrid'
        extview.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
        extview.icon = u'ViewAllExtentsIcon'
        extview.app_name = 'services'
        extview.model = 'Extents'

        self.append_children([extadd, extview])


class ISCSI(TreeNode):

    gname = 'ISCSI'
    name = _(u'iSCSI')
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

    gname = 'Add'
    name = _(u'Add Rsync Module')
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'RsyncMod', 'mf': 'RsyncModForm'}
    icon = u'AddrsyncModIcon'
    append_to = 'services.Rsync.RsyncMod'


class RsyncModView(TreeNode):

    gname = 'View'
    name = _(u'View Rsync Modules')
    view = u'services_rsyncmod'
    icon = u'ViewAllrsyncModIcon'
    append_to = 'services.Rsync.RsyncMod'


class PluginsSettings(TreeNode):

    gname = 'Settings'
    name = _(u'Settings')
    type = 'object'
    icon = u"SettingsIcon"
    skip = True

    def __init__(self, *args, **kwargs):
        super(PluginsSettings, self).__init__(*args, **kwargs)
        if notifier().plugins_jail_configured():
            oid = models.PluginsJail.objects.order_by('-id')[0].id
            self.view = 'freeadmin_model_edit'
            self.kwargs = {'app': 'services',
                'model': 'PluginsJail',
                'oid': oid}
        else:
            self.view = 'plugins_jailpbi'


class PluginsManagement(TreeNode):

    gname = 'management'
    name = _(u'Management')
    icon = u"SettingsIcon"
    skip = True
    order = -1

    def __init__(self, *args, **kwargs):
        super(PluginsManagement, self).__init__(*args, **kwargs)
        self.append_children([PluginsSettings()])

    def pre_dehydrate(self):
        if notifier().plugins_jail_configured():
            return

        for nav in list(self.option_list):
            if nav.gname == 'NullMountPoint':
                self.option_list.remove(nav)
                break


class MountPoints(TreeNode):

    gname = 'View'
    view = 'plugins_mountpoints'
    append_to = 'services.PluginsJail.management.NullMountPoint'


class Plugins(TreeNode):

    gname = 'PluginsJail'
    name = _(u'Plugins')
    icon = models.PluginsJail._admin.icon_model

    def __init__(self, *args, **kwargs):
        super(Plugins, self).__init__(*args, **kwargs)
        self.append_children([PluginsManagement()])

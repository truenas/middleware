from freeadmin.tree import TreeNode
from django.utils.translation import ugettext as _
import models

BLACKLIST = ['services','UPS']
ICON = u'ServicesIcon'

class EnDisServices(TreeNode):

    name = _(u'Control Services')
    type = u'en_dis_services'
    icon = u'ServicesIcon'
    order = -1

class ISCSIDeviceAdd(TreeNode):

    name = _(u'Add Device Extent')
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'mf': 'iSCSITargetDeviceExtentForm'}
    icon = u'AddExtentIcon'
    append_app = False

class ISCSIDeviceView(TreeNode):

    name = _(u'View All Device Extents')
    type = u'viewmodel'
    view = u'freeadmin_model_datagrid'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
    icon = u'ViewAllExtentsIcon'
    append_app = False
    app_name = 'services'
    model = 'DExtents'

class ISCSIDevice(TreeNode):

    name = _(u'Device Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    append_app = False

    def __init__(self, *args, **kwargs):

        self._children = []
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__exact='Disk').order_by('-id'):
            nav = TreeNode()
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id, 'mf': 'iSCSITargetDeviceExtentForm'}
            nav.icon = u'ExtentIcon'
            self.append_child(nav)
        self._children += [ISCSIDeviceAdd(),ISCSIDeviceView()]

class ISCSIExtAdd(TreeNode):

    name = _(u'Add Extent')
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'mf': 'iSCSITargetFileExtentForm'}
    icon = u'AddExtentIcon'
    append_app = False

class ISCSIExtView(TreeNode):

    gname = 'services.iSCSITargetExtent.View'
    name = _(u'View All Extents')
    type = u'viewmodel'
    view = u'freeadmin_model_datagrid'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
    icon = u'ViewAllExtentsIcon'
    append_app = False
    app_name = 'services'
    model = 'Extents'

class ISCSIExt(TreeNode):

    gname = 'services.iSCSITargetExtent'
    name = _(u'Extents')
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    append_app = False

    def __init__(self, *args, **kwargs):

        self._children = []
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__exact='File').order_by('-id'):
            nav = TreeNode()
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id}
            nav.icon = u'ExtentIcon'
            self.append_child(nav)
        self._children += [ISCSIExtAdd(),ISCSIExtView()]

class ISCSI(TreeNode):

    gname = 'ISCSI'
    name = _(u'ISCSI')
    type = u'iscsi'
    icon = u'iSCSIIcon'

    def __init__(self, *args, **kwargs):
        self._children = [ISCSIDevice()]

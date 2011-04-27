from django_nav import NavOption
from django.utils.translation import ugettext as _
import models

BLACKLIST = ['services','UPS']
ICON = u'ServicesIcon'

class EnDisServices(NavOption):

    name = _(u'Control Services')
    type = u'en_dis_services'
    icon = u'ServicesIcon'
    order = -1
    options = []

class ISCSIDeviceAdd(NavOption):

    name = u'Add Device Extent'
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'mf': 'iSCSITargetDeviceExtentForm'}
    icon = u'AddExtentIcon'
    append_app = False
    options = []

class ISCSIDeviceView(NavOption):

    name = u'View All Device Extents'
    type = u'viewmodel'
    view = u'freeadmin_model_datagrid'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
    icon = u'ViewAllExtentsIcon'
    append_app = False
    app_name = 'services'
    model = 'DExtents'
    options = []

class ISCSIDevice(NavOption):

    name = u'Device Extents'
    type = u'iscsi'
    icon = u'ExtentIcon'
    append_app = False
    options = [NavOption,]

    def __init__(self, *args, **kwargs):

        self.options = []
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__exact='Disk').order_by('-id'):
            nav = NavOption()
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id, 'mf': 'iSCSITargetDeviceExtentForm'}
            nav.icon = u'ExtentIcon'
            self.options.append(nav)
        self.options += [ISCSIDeviceAdd,ISCSIDeviceView]

class ISCSIExtAdd(NavOption):

    name = u'Add Extent'
    type = u'object'
    view = u'freeadmin_model_add'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'mf': 'iSCSITargetFileExtentForm'}
    icon = u'AddExtentIcon'
    append_app = False
    options = []

class ISCSIExtView(NavOption):

    name = u'View All Extents'
    type = u'viewmodel'
    view = u'freeadmin_model_datagrid'
    kwargs = {'app': 'services', 'model': 'iSCSITargetExtent'}
    icon = u'ViewAllExtentsIcon'
    append_app = False
    app_name = 'services'
    model = 'Extents'
    options = []

class ISCSIExt(NavOption):

    name = u'Extents'
    type = u'iscsi'
    icon = u'ExtentIcon'
    order_child = False
    append_app = False
    options = []

    def __init__(self, *args, **kwargs):

        self.options = []
        for ext in models.iSCSITargetExtent.objects.filter(iscsi_target_extent_type__exact='File').order_by('-id'):
            nav = NavOption()
            nav.name = unicode(ext)
            nav.view = u'freeadmin_model_edit'
            nav.type = 'object'
            nav.kwargs = {'app': 'services', 'model': 'iSCSITargetExtent', 'oid': ext.id}
            nav.icon = u'ExtentIcon'
            self.options.append(nav)
        self.options += [ISCSIExtAdd,ISCSIExtView]

class ISCSI(NavOption):

    name = u'ISCSI'
    type = u'iscsi'
    icon = u'iSCSIIcon'
    options = [ISCSIDevice]

    #def __init__(self, *args, **kwargs):

    #    self.options = []

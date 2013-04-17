from collections import OrderedDict

from django.utils.html import escapejs
from django.utils.translation import ugettext as _

#from freenasUI.freeadmin.api.resources import NullMountPointResource
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.plugins import models


#class NullMountPointFAdmin(BaseFreeAdmin):
#
#    menu_child_of = u"services.PluginsJail.management"
#    icon_model = u"MountPointIcon"
#    icon_object = u"MountPointIcon"
#    icon_add = u"AddMountPointIcon"
#    icon_view = u"ViewMountPointIcon"
#
#    resource = NullMountPointResource
#
#    def get_datagrid_columns(self):
#        columns = super(NullMountPointFAdmin, self).get_datagrid_columns()
#        columns.insert(2, {
#            'name': 'mounted',
#            'label': _('Mounted?'),
#            'sortable': False,
#        })
#        return columns
#
#
#site.register(models.NullMountPoint, NullMountPointFAdmin)

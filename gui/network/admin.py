from django.utils.translation import ugettext as _

from freenasUI.freeadmin.api.resources import InterfacesResource
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.network import models


class InterfacesFAdmin(BaseFreeAdmin):

    create_modelform = "InterfacesForm"
    edit_modelform = "InterfacesEditForm"
    icon_object = u"InterfacesIcon"
    icon_model = u"InterfacesIcon"
    icon_add = u"AddInterfaceIcon"
    icon_view = u"ViewAllInterfacesIcon"
    inlines = [
        {
            'form': 'AliasForm',
            'prefix': 'alias_set'
        },
    ]
    resource = InterfacesResource
    exclude_fields = (
        'id',
        'int_ipv4address',
        'int_v4netmaskbit',
        'int_ipv6address',
        'int_v6netmaskbit',
        )

    def get_datagrid_columns(self):
        columns = super(InterfacesFAdmin, self).get_datagrid_columns()
        columns.insert(3, {
            'name': 'ipv4_addresses',
            'label': _('IPv4 Addresses'),
            'sortable': False,
        })
        columns.insert(4, {
            'name': 'ipv6_addresses',
            'label': _('IPv6 Addresses'),
            'sortable': False,
        })
        return columns

site.register(models.Interfaces, InterfacesFAdmin)

from collections import OrderedDict
from django.utils.translation import ugettext as _
from django.utils.html import escapejs

from freenasUI.api.resources import (
    InterfacesResourceMixin, LAGGInterfaceResourceMixin
)
from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models

SW_NAME = get_sw_name()


class InterfacesFAdmin(BaseFreeAdmin):
    icon_object = u"InterfacesIcon"
    icon_model = u"InterfacesIcon"
    icon_add = u"AddInterfaceIcon"
    icon_view = u"ViewAllInterfacesIcon"
    resource_mixin = InterfacesResourceMixin
    exclude_fields = (
        'int_ipv4address',
        'int_ipv4address_b',
        'int_v4netmaskbit',
        'int_ipv6address',
        'int_v6netmaskbit',
        'int_carp',
        'int_vip',
        'int_vhid',
        'int_pass',
        'int_critical',
        'int_group',
    )

    def get_actions(self):
        actions = OrderedDict()
        actions["Edit"] = {
            'button_name': _("Edit"),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._edit_url, [mybtn,]);
                }
            }""" % (escapejs(_('Edit interface')), ),
        }
        return actions

    def get_datagrid_columns(self):
        columns = super(InterfacesFAdmin, self).get_datagrid_columns()
        columns.insert(3, {
            'name': 'int_media_status',
            'label': _('Media Status'),
            'sortable': False,
        })
        columns.insert(4, {
            'name': 'ipv4_addresses',
            'label': _('IPv4 Addresses'),
            'sortable': False,
        })
        columns.insert(5, {
            'name': 'ipv6_addresses',
            'label': _('IPv6 Addresses'),
            'sortable': False,
        })

        return columns

    def get_confirm_message(self, action, **kwargs):
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'MASTER'
        ):
            return _(
                'This change will cause a failover event. '
                'Do you want to proceed?'
            )
        else:
            return _(
                'Network connectivity will be interrupted. '
                'Do you want to proceed?'
            )


class LAGGInterfaceFAdmin(BaseFreeAdmin):

    icon_object = u"VLANIcon"
    icon_model = u"VLANIcon"
    icon_add = u"AddVLANIcon"
    icon_view = u"ViewAllVLANsIcon"
    create_modelform = "LAGGInterfaceForm"
    resource_mixin = LAGGInterfaceResourceMixin

    def get_actions(self):
        actions = super(LAGGInterfaceFAdmin, self).get_actions()
        actions["Edit"] = {
            'button_name': _("Edit"),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('%s', data._edit_url, [mybtn,]);
                }
            }""" % (escapejs(_('Edit LAGG interface')), ),
        }
        return actions

    def get_confirm_message(self, action, **kwargs):
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'MASTER'
        ):
            return _(
                'This change will cause a failover event. '
                'Do you want to proceed?'
            )
        else:
            return _(
                'Network connectivity will be interrupted. '
                'Do you want to proceed?'
            )


site.register(models.Interfaces, InterfacesFAdmin)
site.register(models.LAGGInterface, LAGGInterfaceFAdmin)

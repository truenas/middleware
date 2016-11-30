from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    GlobalConfigurationResourceMixin,
    InterfacesResourceMixin, LAGGInterfaceResourceMixin,
    LAGGInterfaceMembersResourceMixin
)
from freenasUI.common.system import get_sw_name
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.middleware.notifier import notifier
from freenasUI.network import models

SW_NAME = get_sw_name()


class NetworkInterruptMixin(object):

    def get_confirm_message(self, action, **kwargs):
        failover_dis = False
        if (
            hasattr(notifier, 'failover_status') and
            notifier().failover_status() == 'MASTER'
        ):
            failover_dis = True

        if failover_dis:
            return _(
                'Changing this interface will disable HA while the '
                'configuration change completes. Do you wish to proceed?'
            )
        else:
            if action != 'add':
                return _(
                    'Network connectivity will be interrupted. '
                    'Do you want to proceed?'
                )


class GlobalConfigurationFAdmin(BaseFreeAdmin):

    deletable = False
    resource_mixin = GlobalConfigurationResourceMixin


class InterfacesFAdmin(NetworkInterruptMixin, BaseFreeAdmin):

    create_modelform = "InterfacesForm"
    delete_form = "InterfacesDeleteForm"
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
    resource_mixin = InterfacesResourceMixin
    exclude_fields = (
        'id',
        'int_ipv4address',
        'int_ipv4address_b',
        'int_v4netmaskbit',
        'int_ipv6address',
        'int_v6netmaskbit',
        'int_vip',
        'int_vhid',
        'int_pass',
        'int_critical',
        'int_group',
    )

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


class LAGGInterfaceFAdmin(NetworkInterruptMixin, BaseFreeAdmin):

    icon_object = u"VLANIcon"
    icon_model = u"VLANIcon"
    icon_add = u"AddVLANIcon"
    icon_view = u"ViewAllVLANsIcon"
    create_modelform = "LAGGInterfaceForm"
    resource_mixin = LAGGInterfaceResourceMixin

    def get_actions(self):
        actions = super(LAGGInterfaceFAdmin, self).get_actions()
        actions['EditMembers'] = {
            'button_name': _('Edit Members'),
            'on_click': """function() {
              var mybtn = this;
              for (var i in grid.selection) {
                var data = grid.row(i).data;
                var p = dijit.byId('tab_networksettings');

                var c = p.getChildren();
                for(var i=0; i<c.length; i++){
                  if(c[i].title == '%(lagg_members)s ' + data.lagg_interface){
                    p.selectChild(c[i]);
                    return;
                  }
                }

                var pane2 = new dijit.layout.ContentPane({
                  title: '%(lagg_members)s ' + data.lagg_interface,
                  refreshOnShow: true,
                  closable: true,
                  href: data._members_url
                });
                dojo.addClass(pane2.domNode, [
                 "data_network_LAGGInterfaceMembers" + data.int_name,
                 "objrefresh"
                 ]);
                p.addChild(pane2);
                p.selectChild(pane2);

              }
            }""" % {
                'lagg_members': _('LAGG Members'),
            }}
        return actions


class LAGGInterfaceMembersFAdmin(BaseFreeAdmin):

    icon_object = u"LAGGIcon"
    icon_model = u"LAGGIcon"
    resource_mixin = LAGGInterfaceMembersResourceMixin

    def get_datagrid_filters(self, request):
        return {
            "lagg_interfacegroup__id": request.GET.get("id"),
        }


class VLANFAdmin(NetworkInterruptMixin, BaseFreeAdmin):

    icon_object = u"VLANIcon"
    icon_model = u"VLANIcon"
    icon_add = u"AddVLANIcon"
    icon_view = u"ViewAllVLANsIcon"


site.register(models.GlobalConfiguration, GlobalConfigurationFAdmin)
site.register(models.Interfaces, InterfacesFAdmin)
site.register(models.VLAN, VLANFAdmin)
site.register(models.LAGGInterface, LAGGInterfaceFAdmin)
site.register(models.LAGGInterfaceMembers, LAGGInterfaceMembersFAdmin)

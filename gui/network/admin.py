from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    InterfacesResource, LAGGInterfaceResource, LAGGInterfaceMembersResource
)
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


class LAGGInterfaceFAdmin(BaseFreeAdmin):

    icon_object = u"VLANIcon"
    icon_model = u"VLANIcon"
    icon_add = u"AddVLANIcon"
    icon_view = u"ViewAllVLANsIcon"
    create_modelform = "LAGGInterfaceForm"
    resource = LAGGInterfaceResource

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
                  if(c[i].title == '%(lagg_members)s ' + data.int_interface){
                    p.selectChild(c[i]);
                    return;
                  }
                }

                var pane2 = new dijit.layout.ContentPane({
                  title: '%(lagg_members)s ' + data.int_interface,
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
                },
        }
        return actions


class LAGGInterfaceMembersFAdmin(BaseFreeAdmin):

    icon_object = u"LAGGIcon"
    icon_model = u"LAGGIcon"
    resource = LAGGInterfaceMembersResource

    def get_datagrid_filters(self, request):
        return {
            "lagg_interfacegroup__id": request.GET.get("id"),
            }

site.register(models.Interfaces, InterfacesFAdmin)
site.register(models.LAGGInterface, LAGGInterfaceFAdmin)
site.register(models.LAGGInterfaceMembers, LAGGInterfaceMembersFAdmin)

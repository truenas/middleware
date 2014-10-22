import logging

from collections import OrderedDict

from django.conf import settings
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    CertificateAuthorityResourceMixin,
    CertificateResourceMixin,
    UpdateResourceMixin,
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.system import models

log = logging.getLogger('system.admin')

class SettingsFAdmin(BaseFreeAdmin):

    deletable = False

    def get_extra_context(self, action):
        try:
            ssl = models.SSL.objects.order_by("-id")[0]
        except:
            ssl = None
        return {
            'ssl': ssl,
        }


class CertificateAuthorityFAdmin(BaseFreeAdmin):

    icon_object = u"CertificateAuthorityIcon"
    icon_model = u"CertiicateAuthorityIcon"
    icon_add = u"CertificateAuthorityIcon"
    icon_view = u"CertificateAuthorityIcon"

    resource_mixin = CertificateAuthorityResourceMixin

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'cert_name',
            'label': _('Name') 
        }) 

        columns.append({
            'name': 'cert_internal',
            'label': _('Internal') 
        }) 

        columns.append({
            'name': 'cert_issuer',
            'label': _('Issuer') 
        }) 

        columns.append({
            'name': 'cert_ncertificates',
            'label': _('Certificates') 
        }) 

        columns.append({
            'name': 'cert_DN',
            'label': _('Distinguished Name') 
        }) 

        columns.append({
            'name': 'cert_from',
            'label': _('From') 
        }) 

        columns.append({
            'name': 'cert_until',
            'label': _('Until') 
        }) 

        return columns

    def get_actions(self):
        actions = OrderedDict()

        actions['edit'] = {
            'button_name': 'Edit',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('Edit', data._edit_url, [mybtn,]);
                }
            }""",
        }

        actions['export_certificate'] = {
            'button_name': 'Export Certificate',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    location.href=data._export_certificate_url;
                }
            }""",
        }

        actions['export_privatekey'] = {
            'button_name': 'Export Private Key',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    location.href=data._export_privatekey_url;
                }
            }""",
        }

        actions['delete'] = {
            'button_name': 'Delete',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('Delete', data._delete_url, [mybtn,]);
                }  
            }""",
        }

        return actions


class CertificateFAdmin(BaseFreeAdmin):

    icon_object = u"CertificateIcon"
    icon_model = u"CertificateIcon"
    icon_add = u"CertificateIcon"
    icon_view = u"CertificateIcon"

    resource_mixin = CertificateResourceMixin

    def get_datagrid_columns(self):
        columns = []

        columns.append({
            'name': 'cert_name',
            'label': _('Name') 
        }) 

        columns.append({
            'name': 'cert_issuer',
            'label': _('Issuer') 
        }) 

        columns.append({
            'name': 'cert_DN',
            'label': _('Distinguished Name') 
        }) 

        columns.append({
            'name': 'cert_from',
            'label': _('From') 
        }) 

        columns.append({
            'name': 'cert_until',
            'label': _('Until') 
        }) 

        return columns

    def get_actions(self):
        actions = OrderedDict()

	hide_me = """function(evt, actionName, action) {
              for(var i=0;i < evt.rows.length;i++) {
                var row = evt.rows[i];
                if(%s) {
                  query(".grid" + actionName).forEach(function(item, idx) {
                    domStyle.set(item, "display", "none");
                  });
                  break;
                }
              }
            }"""

        actions['edit'] = {
            'button_name': 'View',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('View', data._edit_url, [mybtn,]);
                }
            }""",
            'on_select_after': hide_me % 'row.data.cert_type_CSR',
        }

        actions['export_certificate'] = {
            'button_name': 'Export Certificate',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    location.href=data._export_certificate_url;
                }
            }""",
            'on_select_after': hide_me % 'row.data.cert_type_CSR',
        }
        
        actions['edit_csr'] = {
            'button_name': 'Edit',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('Edit',data._CSR_edit_url, [mybtn,]);
                }
            }""",
            'on_select_after': hide_me % '!row.data.cert_type_CSR',
        }

        actions['export_privatekey'] = {
            'button_name': 'Export Private Key',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    location.href=data._export_privatekey_url;
                }
            }""",
            'on_select_after': hide_me % 'row.data.cert_type_CSR',
        }

#        actions['export_certificate_and_privatekey'] = {
#            'button_name': 'Export Certificate + Private Key',
#            'on_click': """function() {
#                var mybtn = this;
#                for (var i in grid.selection) {
#                    var data = grid.row(i).data;
#                    location.href=data._export_certificate_and_privatekey_url;
#                }
#            }""",
#        }

        actions['delete'] = {
            'button_name': 'Delete',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editObject('Delete', data._delete_url, [mybtn,]);
                }  
            }""",
        }

        return actions

    def get_datagrid_dblclick(self, request=None):
        func = """
            grid.on(".dgrid-row:dblclick", function(evt) {
                var row = grid.row(evt);
                if (row.data.cert_type_CSR) {
                    editObject('Edit', row.data._CSR_edit_url, [this, ]);
                } else {
                    editObject('Edit', row.data._edit_url, [this, ]);
                } 
            });
        """

        return func


class UpdateFAdmin(BaseFreeAdmin):

    deletable = False
    resource_mixin = UpdateResourceMixin


class VMWarePluginFAdmin(BaseFreeAdmin):
    exclude_fields = (
        'password',
    )


site.register(models.CertificateAuthority, CertificateAuthorityFAdmin)
site.register(models.Certificate, CertificateFAdmin)
site.register(models.Settings, SettingsFAdmin)
site.register(models.Update, UpdateFAdmin)
site.register(models.VMWarePlugin, VMWarePluginFAdmin)

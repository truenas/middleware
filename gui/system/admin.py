import logging

from collections import OrderedDict

from django.core.urlresolvers import reverse
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


class BootStatusFAdmin(BaseFreeAdmin):

    app_label = "system"
    double_click = False
    module_name = "bootstatus"
    verbose_name = _("Boot Status")
    resource = False

    def get_resource_url(self, request):
        return "%sstatus/" % (
            reverse('api_dispatch_list', kwargs={
                'api_name': 'v1.0',
                'resource_name': 'system/bootenv',
            }),
        )

    def get_datagrid_columns(self):

        columns = []

        columns.append({
            'name': 'name',
            'label': _('Name'),
            'renderExpando': True,
            'sortable': False,
            'shouldExpand': True,
        })

        columns.append({
            'name': 'read',
            'label': _('Read'),
            'sortable': False,
        })

        columns.append({
            'name': 'write',
            'label': _('Write'),
            'sortable': False,
        })

        columns.append({
            'name': 'cksum',
            'label': _('Checksum'),
            'sortable': False,
        })

        columns.append({
            'name': 'status',
            'label': _('Status'),
            'sortable': False,
        })
        return columns

    def _action_builder(
        self, name, label=None, url=None, func="editObject", show=None
    ):

        if url is None:
            url = "_%s_url" % (name, )

        hide = "row.data.%s === undefined" % url

        on_select_after = """function(evt, actionName, action) {
  for(var i=0;i < evt.rows.length;i++) {
    var row = evt.rows[i];
    if((%(hide)s)) {
      query(".grid" + actionName).forEach(function(item, idx) {
        domStyle.set(item, "display", "none");
      });
      break;
    }
  }
}""" % {
            'hide': hide,
        }

        on_click = """function() {
  var mybtn = this;
  for (var i in grid.selection) {
    var data = grid.row(i).data;
    %(func)s('%(label)s', data.%(url)s, [mybtn,]);
  }
}""" % {
            'func': func,
            'label': escapejs(label),
            'url': url,
        }

        data = {
            'button_name': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):

        actions = OrderedDict()

        actions['Detach'] = self._action_builder("detach", label=_('Detach'))

        actions['Replace'] = self._action_builder(
            'replace', label=_('Replace'),
        )

        actions['Attach'] = self._action_builder(
            'attach', label=_('Attach'),
        )

        actions['Remove'] = self._action_builder("remove", label=_('Remove'))

        return actions


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

        # Commenting this out as it can lead to users corrupting a CA
        # uncomment if the certificate integrity check can be added to this
        # actions['edit'] = {
        #     'button_name': 'Edit',
        #     'on_click': """function() {
        #         var mybtn = this;
        #         for (var i in grid.selection) {
        #             var data = grid.row(i).data;
        #             editObject('Edit', data._edit_url, [mybtn,]);
        #         }
        #     }""",
        # }

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
            'on_select_after': """function(evt, actionName, action) {
                for(var i=0;i < evt.rows.length;i++) {
                    var row = evt.rows[i];
                    if (!row.data.cert_privatekey) {
                        if (actionName == 'export_privatekey') {
                            query(".grid" + actionName).forEach(function(item, idx) {
                                domStyle.set(item, "display", "none");
                            });
                        }
                    }
                }
            }"""
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


class CloudCredentialsFAdmin(BaseFreeAdmin):

    exclude_fields = (
        'id',
        'attributes',
    )

    icon_object = u"CloudCredentialsIcon"
    icon_model = u"CloudCredentialsIcon"
    icon_add = u"CloudCredentialsAddIcon"
    icon_view = u"CloudCredentialsViewIcon"


class UpdateFAdmin(BaseFreeAdmin):

    deletable = False
    resource_mixin = UpdateResourceMixin


site.register(None, BootStatusFAdmin)
site.register(models.CertificateAuthority, CertificateAuthorityFAdmin)
site.register(models.Certificate, CertificateFAdmin)
site.register(models.CloudCredentials, CloudCredentialsFAdmin)
site.register(models.Settings, SettingsFAdmin)
site.register(models.Update, UpdateFAdmin)

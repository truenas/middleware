from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    CertificateAuthorityResourceMixin,
    CertificateResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.system import models


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

    #create_modelform = "CertificateAuthorityEditForm"
    #edit_modelform = "CertificateAuthorityEditForm"
    icon_object = u"SettingsIcon"
    icon_model = u"SettingsIcon"
    icon_add = u"SettingsIcon"
    icon_view = u"SettingsIcon"

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


class CertificateFAdmin(BaseFreeAdmin):

    create_modelform = "CertificateForm"
    edit_modelform = "CertificateForm"
    icon_object = u"SettingsIcon"
    icon_model = u"SettingsIcon"
    icon_add = u"SettingsIcon"
    icon_view = u"SettingsIcon"

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


site.register(models.Settings, SettingsFAdmin)
site.register(models.CertificateAuthority, CertificateAuthorityFAdmin)
site.register(models.Certificate, CertificateFAdmin)

from django.utils.html import escapejs
from django.utils.translation import ugettext as _

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

    create_modelform = "CertificateAuthorityForm"
    edit_modelform = "CertificateAuthorityForm"
    icon_object = u"SettingsIcon"
    icon_model = u"SettingsIcon"
    icon_add = u"SettingsIcon"
    icon_view = u"SettingsIcon"

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
            'name': 'cert_expire',
            'label': _('Expires') 
        }) 

        return columns


site.register(models.Settings, SettingsFAdmin)
site.register(models.CertificateAuthority, CertificateAuthorityFAdmin)

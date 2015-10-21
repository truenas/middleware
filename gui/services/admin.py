from django.conf.urls import patterns, url
from django.http import HttpResponse
from django.utils.translation import ugettext as _

from dojango.forms.formsets import formset_factory
from freenasUI.api.resources import (
    FiberChannelToTargetResourceMixin,
    FTPResourceMixin, ISCSIPortalResourceMixin, ISCSITargetResourceMixin,
    ISCSITargetGroupsResourceMixin,
    ISCSITargetExtentResourceMixin, ISCSITargetToExtentResourceMixin,
    NFSResourceMixin, ServicesResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.services.forms import iSCSITargetAuthGroupUserForm
from freenasUI.services import models


class ServicesFAdmin(BaseFreeAdmin):

    resource_mixin = ServicesResourceMixin


class FiberChannelToTargetFAdmin(BaseFreeAdmin):

    resource_mixin = FiberChannelToTargetResourceMixin


class FTPFAdmin(BaseFreeAdmin):

    resource_mixin = FTPResourceMixin
    deletable = False
    icon_model = "FTPIcon"
    advanced_fields = (
        'ftp_filemask',
        'ftp_dirmask',
        'ftp_fxp',
        'ftp_ident',
        'ftp_passiveportsmin',
        'ftp_passiveportsmax',
        'ftp_localuserbw',
        'ftp_localuserdlbw',
        'ftp_anonuserbw',
        'ftp_anonuserdlbw',
        'ftp_tls',
        'ftp_tls_policy',
        'ftp_tls_opt_allow_client_renegotiations',
        'ftp_tls_opt_allow_dot_login',
        'ftp_tls_opt_allow_per_user',
        'ftp_tls_opt_common_name_required',
        'ftp_tls_opt_enable_diags',
        'ftp_tls_opt_export_cert_data',
        'ftp_tls_opt_no_cert_request',
        'ftp_tls_opt_no_empty_fragments',
        'ftp_tls_opt_no_session_reuse_required',
        'ftp_tls_opt_stdenvvars',
        'ftp_tls_opt_dns_name_required',
        'ftp_tls_opt_ip_address_required',
        'ftp_ssltls_certfile',
        'ftp_options',
    )


class ISCSITargetFAdmin(BaseFreeAdmin):

    menu_child_of = "sharing.ISCSI"
    icon_object = u"TargetIcon"
    icon_model = u"TargetIcon"
    icon_add = u"AddTargetIcon"
    icon_view = u"ViewAllTargetsIcon"
    inlines = [
        {
            'form': 'iSCSITargetGroupsForm',
            'prefix': 'targetgroups_set',
            'formset': 'iSCSITargetGroupsInlineFormSet',
        },
    ]

    exclude_fields = (
        'id',
        'iscsi_target_mode',
    )
    nav_extra = {'order': 10}

    resource_mixin = ISCSITargetResourceMixin


class ISCSITargetGroupsFAdmin(BaseFreeAdmin):
    icon_model = 'SettingsIcon'
    resource_mixin = ISCSITargetGroupsResourceMixin


class ISCSIPortalFAdmin(BaseFreeAdmin):

    menu_child_of = "sharing.ISCSI"
    icon_object = u"PortalIcon"
    icon_model = u"PortalIcon"
    icon_add = u"AddPortalIcon"
    icon_view = u"ViewAllPortalsIcon"
    inlines = [
        {
            'form': 'iSCSITargetPortalIPForm',
            'prefix': 'portalip_set',
        },
    ]
    nav_extra = {'order': -5}

    resource_mixin = ISCSIPortalResourceMixin

    def get_datagrid_columns(self):
        columns = super(ISCSIPortalFAdmin, self).get_datagrid_columns()
        columns.insert(1, {
            'name': 'iscsi_target_portal_ips',
            'label': _('Listen'),
            'sortable': False,
        })
        return columns


class ISCSIAuthGroupFAdmin(BaseFreeAdmin):

    menu_child_of = "sharing.ISCSI"
    icon_object = u"InitiatorIcon"
    icon_model = u"InitiatorIcon"
    icon_add = u"AddInitiatorIcon"
    icon_view = u"ViewAllInitiatorsIcon"
    nav_extra = {'order': 0}
    resource_name = 'services/iscsi/authgroup'

    def get_urls(self):
        urls = super(ISCSIAuthGroupFAdmin, self).get_urls()
        urls += patterns(
            '',
            url(
                r'^empty-formset/user/$',
                self.empty_formset_user,
                name='freeadmin_services_iscsitargetauthgroup_empty_formset_user',
            ),
        )
        return urls

    def empty_formset_user(self, request):
        UserFormset = formset_factory(iSCSITargetAuthGroupUserForm)
        return HttpResponse(UserFormset().empty_form.as_table())

    def add(self, request, mf=None):
        from django.shortcuts import render
        from freenasUI.freeadmin.views import JsonResp
        m = self._model
        app = self._model._meta.app_label
        context = {
            'app': app,
            'model': m,
            'modeladmin': m._admin,
            'mf': mf,
            'verbose_name': m._meta.verbose_name,
            'extra_js': m._admin.extra_js,
        }
        mf = self._get_modelform('create')
        UserFormset = formset_factory(iSCSITargetAuthGroupUserForm, extra=1)

        if request.method == "POST":
            mf = mf(request.POST)
            if mf.is_valid():
                return JsonResp(
                    request,
                    form=mf,
                    message=_('Auth Group successfully added'),
                )
        else:
            mf = mf()
            formset_user = UserFormset()

        context.update({
            'form': mf,
            'formset_user': formset_user,
        })
        return render(request, 'services/iscsitargetauthgroup_add.html', context)


class ISCSIAuthCredentialFAdmin(BaseFreeAdmin):

    menu_child_of = "sharing.ISCSI"
    icon_object = u"AuthorizedAccessIcon"
    icon_model = u"AuthorizedAccessIcon"
    icon_add = u"AddAuthorizedAccessIcon"
    icon_view = u"ViewAllAuthorizedAccessIcon"

    exclude_fields = (
        'id',
        'iscsi_target_auth_secret',
        'iscsi_target_auth_peersecret',
    )
    nav_extra = {'order': 5}

    resource_name = 'services/iscsi/authcredential'


class ISCSITargetToExtentFAdmin(BaseFreeAdmin):

    menu_child_of = "sharing.ISCSI"
    icon_object = u"TargetExtentIcon"
    icon_model = u"TargetExtentIcon"
    icon_add = u"AddTargetExtentIcon"
    icon_view = u"ViewAllTargetExtentsIcon"
    nav_extra = {'order': 20}

    resource_mixin = ISCSITargetToExtentResourceMixin


class ISCSITargetExtentFAdmin(BaseFreeAdmin):

    delete_form = "ExtentDelete"
    delete_form_filter = {'iscsi_target_extent_type__exact': 'File'}
    menu_child_of = "sharing.ISCSI"
    icon_object = u"ExtentIcon"
    icon_model = u"ExtentIcon"
    icon_add = u"AddExtentIcon"
    icon_view = u"ViewAllExtentsIcon"
    nav_extra = {'order': 15}

    resource_mixin = ISCSITargetExtentResourceMixin

    exclude_fields = (
        'id',
        'iscsi_target_extent_filesize',
        'iscsi_target_extent_naa',
    )


class NFSFAdmin(BaseFreeAdmin):

    resource_mixin = NFSResourceMixin
    deletable = False
    icon_model = 'NFSIcon'


site.register(models.FiberChannelToTarget, FiberChannelToTargetFAdmin)
site.register(models.FTP, FTPFAdmin)
site.register(models.iSCSITarget, ISCSITargetFAdmin)
site.register(models.iSCSITargetGroups, ISCSITargetGroupsFAdmin)
site.register(models.iSCSITargetPortal, ISCSIPortalFAdmin)
site.register(models.iSCSITargetAuthGroup, ISCSIAuthGroupFAdmin)
site.register(models.iSCSITargetAuthCredential, ISCSIAuthCredentialFAdmin)
site.register(models.iSCSITargetToExtent, ISCSITargetToExtentFAdmin)
site.register(models.iSCSITargetExtent, ISCSITargetExtentFAdmin)
site.register(models.NFS, NFSFAdmin)
site.register(models.services, ServicesFAdmin)

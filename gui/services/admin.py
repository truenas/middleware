from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    FibreChannelToTargetResourceMixin,
    FTPResourceMixin, ISCSIPortalResourceMixin, ISCSITargetResourceMixin,
    ISCSITargetGroupsResourceMixin,
    ISCSITargetExtentResourceMixin, ISCSITargetToExtentResourceMixin,
    NFSResourceMixin, ServicesResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.services import models


class ServicesFAdmin(BaseFreeAdmin):

    resource_mixin = ServicesResourceMixin


class FibreChannelToTargetFAdmin(BaseFreeAdmin):

    resource_mixin = FibreChannelToTargetResourceMixin


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

    delete_form = "TargetExtentDelete"
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
        globalconf = models.iSCSITargetGlobalConfiguration.objects.latest('id')
        if globalconf.iscsi_alua:
            columns.insert(1, {
                'name': 'iscsi_target_portal_ips_a',
                'label': _('Listen (Node A)'),
                'sortable': False,
            })
            columns.insert(2, {
                'name': 'iscsi_target_portal_ips_b',
                'label': _('Listen (Node B)'),
                'sortable': False,
            })
        else:
            columns.insert(1, {
                'name': 'iscsi_target_portal_ips',
                'label': _('Listen'),
                'sortable': False,
            })
        return columns


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

    delete_form = "TargetExtentDelete"
    menu_child_of = "sharing.ISCSI"
    icon_object = u"TargetExtentIcon"
    icon_model = u"TargetExtentIcon"
    icon_add = u"AddTargetExtentIcon"
    icon_view = u"ViewAllTargetExtentsIcon"
    nav_extra = {'order': 20}

    resource_mixin = ISCSITargetToExtentResourceMixin


class ISCSITargetExtentFAdmin(BaseFreeAdmin):

    delete_form = "ExtentDelete"
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
        'iscsi_target_extent_legacy',
    )


class NFSFAdmin(BaseFreeAdmin):

    resource_mixin = NFSResourceMixin
    deletable = False
    icon_model = 'NFSIcon'


site.register(models.FibreChannelToTarget, FibreChannelToTargetFAdmin)
site.register(models.FTP, FTPFAdmin)
site.register(models.iSCSITarget, ISCSITargetFAdmin)
site.register(models.iSCSITargetGroups, ISCSITargetGroupsFAdmin)
site.register(models.iSCSITargetPortal, ISCSIPortalFAdmin)
site.register(models.iSCSITargetAuthCredential, ISCSIAuthCredentialFAdmin)
site.register(models.iSCSITargetToExtent, ISCSITargetToExtentFAdmin)
site.register(models.iSCSITargetExtent, ISCSITargetExtentFAdmin)
site.register(models.NFS, NFSFAdmin)
site.register(models.services, ServicesFAdmin)

from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    ISCSIPortalResourceMixin, ISCSITargetExtentResourceMixin,
    ISCSITargetToExtentResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.services import models


class ISCSIPortalFAdmin(BaseFreeAdmin):

    menu_child_of = "services.ISCSI"
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

    resource_mixin = ISCSIPortalResourceMixin

    def get_datagrid_columns(self):
        columns = super(ISCSIPortalFAdmin, self).get_datagrid_columns()
        columns.insert(1, {
            'name': 'iscsi_target_portalip_ips',
            'label': _('Listen'),
            'sortable': False,
        })
        return columns


class ISCSIAuthCredentialFAdmin(BaseFreeAdmin):

    menu_child_of = "services.ISCSI"
    icon_object = u"AuthorizedAccessIcon"
    icon_model = u"AuthorizedAccessIcon"
    icon_add = u"AddAuthorizedAccessIcon"
    icon_view = u"ViewAllAuthorizedAccessIcon"

    exclude_fields = (
        'id',
        'iscsi_target_auth_secret',
        'iscsi_target_auth_peersecret',
        )


class ISCSITargetToExtentFAdmin(BaseFreeAdmin):

    menu_child_of = "services.ISCSI"
    icon_object = u"TargetExtentIcon"
    icon_model = u"TargetExtentIcon"
    icon_add = u"AddTargetExtentIcon"
    icon_view = u"ViewAllTargetExtentsIcon"

    resource_mixin = ISCSITargetToExtentResourceMixin


class ISCSITargetExtentFAdmin(BaseFreeAdmin):

    delete_form = "ExtentDelete"
    delete_form_filter = {'iscsi_target_extent_type__exact': 'File'}
    menu_child_of = "services.ISCSI"
    icon_object = u"ExtentIcon"
    icon_model = u"ExtentIcon"
    icon_add = u"AddExtentIcon"
    icon_view = u"ViewAllExtentsIcon"

    resource_mixin = ISCSITargetExtentResourceMixin

    exclude_fields = (
        'id',
        'iscsi_target_extent_filesize',
    )


site.register(models.iSCSITargetPortal, ISCSIPortalFAdmin)
site.register(models.iSCSITargetAuthCredential, ISCSIAuthCredentialFAdmin)
site.register(models.iSCSITargetToExtent, ISCSITargetToExtentFAdmin)
site.register(models.iSCSITargetExtent, ISCSITargetExtentFAdmin)

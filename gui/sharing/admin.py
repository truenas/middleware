from django.utils.translation import ugettext as _

from freenasUI.api.resources import NFSShareResourceMixin
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.sharing import models


class AFPShareFAdmin(BaseFreeAdmin):

    icon_model = "AppleShareIcon"
    icon_add = "AddAppleShareIcon"
    icon_view = "ViewAllAppleSharesIcon"
    icon_object = "AppleShareIcon"
    advanced_fields = (
        'afp_allow',
        'afp_cachecnid',
        'afp_comment',
        'afp_deny',
        'afp_dperm',
        'afp_fperm',
        'afp_hostsallow',
        'afp_hostsdeny',
        'afp_nodev',
        'afp_nofileid',
        'afp_nohex',
        'afp_nostat',
        'afp_prodos',
        'afp_ro',
        'afp_rw',
        'afp_sharecharset',
        'afp_umask',
        'afp_upriv',
    )
    fields = (
        'afp_name',
        'afp_comment',
        'afp_path',
    )
    resource_name = 'sharing/afp'


class CIFSShareFAdmin(BaseFreeAdmin):

    icon_model = "WindowsShareIcon"
    icon_add = "AddWindowsShareIcon"
    icon_view = "ViewAllWindowsSharesIcon"
    icon_object = "WindowsShareIcon"
    advanced_fields = (
        'cifs_auxsmbconf',
        'cifs_browsable',
        'cifs_comment',
        'cifs_guestonly',
        'cifs_hostsallow',
        'cifs_hostsdeny',
        'cifs_recyclebin',
        'cifs_ro',
        'cifs_showhiddenfiles',
        'cifs_vfsobjects',
        'cifs_storage_task',
    )
    fields = (
        'cifs_name',
        'cifs_comment',
        'cifs_path',
        'cifs_ro',
        'cifs_browsable',
        'cifs_guestok'
    )
    resource_name = 'sharing/cifs'

    def get_confirm_message(self, action, **kwargs):
        if action not in ('add', 'edit'):
            return
        form = kwargs['form']
        full_audit_form = 'full_audit' in form.cleaned_data.get('cifs_vfsobjects')
        full_audit_instance = 'full_audit' in form._original_cifs_vfsobjects
        if full_audit_form and not full_audit_instance:
            return _(
                'full_audit VFS object is known to have file transfer issues '
                'with Windows 10. Do you wish to continue?'
            )


class NFSShareFAdmin(BaseFreeAdmin):

    icon_model = "UNIXShareIcon"
    icon_add = "AddUNIXShareIcon"
    icon_view = "ViewAllUNIXSharesIcon"
    icon_object = "UNIXShareIcon"
    inlines = [
        {
            'form': 'NFS_SharePathForm',
            'prefix': 'path_set',
            'position': 'top',
        },
    ]
    resource_mixin = NFSShareResourceMixin
    advanced_fields = (
        'nfs_network',
        'nfs_hosts',
        'nfs_quiet',
        'nfs_maproot_user',
        'nfs_maproot_group',
        'nfs_mapall_user',
        'nfs_mapall_group',
        'nfs_security',
    )
    fields = (
        'nfs_paths',
        'nfs_comment',
        'nfs_alldirs',
        'nfs_ro'
    )

    def get_datagrid_columns(self):
        columns = super(NFSShareFAdmin, self).get_datagrid_columns()
        columns.insert(0, {
            'name': 'nfs_paths',
            'label': _('Paths'),
            'sortable': False,
        })
        return columns

class WebDAVShareFAdmin(BaseFreeAdmin):
  
    icon_model = "WebDAVShareIcon"
    icon_add = "AddWebDAVShareIcon"
    icon_view = "ViewAllWebDAVSharesIcon"
    icon_object = "WebDAVShareIcon"
    fields = (
          'webdav_name',
          'webdav_comment',
          'webdav_path',
          'webdav_ro',
          'webdav_perm',
    )
    resource_name = 'sharing/webdav'

site.register(models.AFP_Share, AFPShareFAdmin)
site.register(models.CIFS_Share, CIFSShareFAdmin)
site.register(models.NFS_Share, NFSShareFAdmin)
site.register(models.WebDAV_Share, WebDAVShareFAdmin)

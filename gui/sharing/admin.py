from django.utils.translation import ugettext as _

from freenasUI.freeadmin.api.resources import NFSShareResource
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.sharing import models


class AFPShareFAdmin(BaseFreeAdmin):

    icon_model = u"AppleShareIcon"
    icon_add = u"AddAppleShareIcon"
    icon_view = u"ViewAllAppleSharesIcon"
    icon_object = u"AppleShareIcon"
    advanced_fields = (
        'afp_cachecnid',
        'afp_sharecharset',
        'afp_nofileid',
        'afp_nodev',
        'afp_nohex',
        'afp_prodos',
        'afp_nostat',
    )
    fields = (
        'afp_name',
        'afp_comment',
        'afp_path',
    )


class NFSShareFAdmin(BaseFreeAdmin):

    icon_model = u"UNIXShareIcon"
    icon_add = u"AddUNIXShareIcon"
    icon_view = u"ViewAllUNIXSharesIcon"
    icon_object = u"UNIXShareIcon"
    inlines = [
        {
            'form': 'NFS_SharePathForm',
            'prefix': 'path_set'
        },
    ]
    resource = NFSShareResource
    exclude_fields = (
        'id',
    )

    def get_datagrid_columns(self):
        columns = super(NFSShareFAdmin, self).get_datagrid_columns()
        columns.insert(0, {
            'name': 'nfs_paths',
            'label': _('Paths'),
            'sortable': False,
        })
        return columns


site.register(models.AFP_Share, AFPShareFAdmin)
site.register(models.NFS_Share, NFSShareFAdmin)

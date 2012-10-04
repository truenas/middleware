from freenasUI.freeadmin.api.resources import DiskResource, VolumeResource
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.storage import models


class DiskFAdmin(BaseFreeAdmin):

    exclude_fields = (
        'id',
        'disk_identifier',
        'disk_multipath_name',
        'disk_multipath_member',
        'disk_enabled',
        )
    resource = DiskResource

    def get_actions(self):
        actions = super(DiskFAdmin, self).get_actions()
        del actions['Delete']
        actions['Wipe'] = {
            'on_select': """function(numrows) {
                if(numrows > 1 || numrows == 0) {
                    query(".gridWipe").forEach(function(item, idx) {
                        domStyle.set(item, "display", "none");
                    });
                } else {
                    query(".gridWipe").forEach(function(item, idx) {
                        domStyle.set(item, "display", "block");
                    });
                }
            }""",
            'button_name': 'Wipe',
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    grid.store.get(i).then(function(data) {
                        editObject('Wipe', data._wipe_url, [mybtn,]);
                    });
                }
            }""",
        }

        return actions


class VolumeFAdmin(BaseFreeAdmin):

    resource = VolumeResource
    exclude_fields = (
        'id',
        'vol_fstype',
        'vol_guid',
        'vol_encrypt',
        'vol_encryptkey',
        )

    def get_datagrid_columns(self):
        columns = super(VolumeFAdmin, self).get_datagrid_columns()

        columns[0]['tree'] = True

        columns.append({
            'name': 'used_si',
            'label': 'Used',
        })

        columns.append({
            'name': 'avail_si',
            'label': 'Available',
        })

        columns.append({
            'name': 'total_si',
            'label': 'Size',
        })

        columns.append({
            'name': 'status',
            'label': 'Status',
        })
        return columns


site.register(models.Disk, DiskFAdmin)
site.register(models.Volume, VolumeFAdmin)

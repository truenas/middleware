from django.conf import settings
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

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
            'button_name': _('Wipe'),
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
        'vol_name',
        'vol_fstype',
        'vol_guid',
        'vol_encrypt',
        'vol_encryptkey',
        )

    def get_datagrid_columns(self):

        columns = []

        columns.append({
            'name': 'name',
            'label': 'Used',
            'tree': True,
            'sortable': False,
            'shouldExpand': True,
        })

        columns.append({
            'name': 'used_si',
            'label': 'Used',
            'sortable': False,
        })

        columns.append({
            'name': 'avail_si',
            'label': 'Available',
            'sortable': False,
        })

        columns.append({
            'name': 'total_si',
            'label': 'Size',
            'sortable': False,
        })

        columns.append({
            'name': 'status',
            'label': 'Status',
            'sortable': False,
        })
        return columns

    def _action_builder(self, name, label=None, url=None, func="editObject", icon=None):

        if url is None:
            url = "_%s_url" % (name, )

        if icon is None:
            icon = name

        on_select_after = """function(evt, actionName, action) {
               for(var i=0;i < evt.rows.length;i++) {
                   var row = evt.rows[i];
                   if(row.data.type !== undefined) {
                       query(".grid" + actionName).forEach(function(item, idx) {
                           domStyle.set(item, "display", "none");
                       });
                       break;
                   }
               }
           }"""

        on_click = """function() {
               var mybtn = this;
               for (var i in grid.selection) {
                   grid.store.get(i).then(function(data) {
                       %(func)s('%(label)s', data.%(url)s, [mybtn,]);
                   });
               }
           }""" % {
                'func': func,
                'label': escapejs(label),
                'url': url,
                }

        data = {
            'button_name': '<img src="%simages/ui/buttons/%s.png" width="18px" height="18px">' % (
                settings.STATIC_URL,
                icon,
                ),
            'tooltip': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):

        actions = {}
        actions['Detach'] = self._action_builder("detach",
            label=_('Detach Volume'),
            func="editScaryObject",
            icon="remove_volume")
        actions['Scrub'] = self._action_builder("scrub", label=_('Scrub Volume'))
        actions['Options'] = self._action_builder("options",
            label=_('Edit ZFS Options'),
            icon="settings")
        actions['NewDataset'] = self._action_builder("add_dataset",
            label=_('Create ZFS Dataset'),
            )
        actions['NewVolume'] = self._action_builder("add_zfs_volume",
            label=_('Create ZFS Volume'),
            )
        actions['ChangePerm'] = self._action_builder("permissions",
            label=_('Change Permissions'),
            )

        return actions


site.register(models.Disk, DiskFAdmin)
site.register(models.Volume, VolumeFAdmin)

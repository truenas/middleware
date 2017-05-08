from collections import OrderedDict

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.html import escapejs
from django.utils.translation import ugettext as _

from freenasUI.api.resources import (
    DiskResourceMixin, ReplicationResourceMixin, ScrubResourceMixin,
    TaskResourceMixin, VolumeResourceMixin
)
from freenasUI.freeadmin.options import BaseFreeAdmin
from freenasUI.freeadmin.site import site
from freenasUI.middleware.notifier import notifier
from freenasUI.storage import models


class DiskFAdmin(BaseFreeAdmin):

    exclude_fields = (
        'disk_identifier',
        'disk_subsystem',
        'disk_number',
        'disk_multipath_name',
        'disk_multipath_member',
        'disk_enabled',
    )
    resource_mixin = DiskResourceMixin

    def get_actions(self):
        actions = super(DiskFAdmin, self).get_actions()
        del actions['Delete']
        actions['Wipe'] = {
            'button_name': _('Wipe'),
            'on_click': """function() {
                var mybtn = this;
                for (var i in grid.selection) {
                    var data = grid.row(i).data;
                    editScaryObject('Wipe', data._wipe_url, [mybtn,]);
                }
            }""",
        }

        actions['EditBulk'] = {
            'button_name': _('Edit In Bulk'),
            'on_click': """function() {
    var mybtn = this;
    var ids = [];
    for (var i in grid.selection) {
        var data = grid.row(i).data;
        ids.push(data.id);
    }
    editObject('Edit In Bulk', data._editbulk_url + '?ids=' + ids.join(","),
        [mybtn,]);
}""",
            'on_select_after': """function(evt, actionName, action) {
    var numrows = 0;
    for(var i in evt.grid.selection) numrows++;
    if(numrows <= 1) {
        query(".grid" + actionName).forEach(function(item, idx) {
            domStyle.set(item, "display", "none");
        });
    } else {
        query(".grid" + actionName).forEach(function(item, idx) {
            domStyle.set(item, "display", "block");
        });
    }
}"""
        }

        return actions


class VolumeFAdmin(BaseFreeAdmin):

    resource_mixin = VolumeResourceMixin
    double_click = False
    exclude_fields = (
        'id',
        'vol_name',
        'vol_fstype',
        'vol_guid',
        'vol_encrypt',
        'vol_encryptkey',
    )

    def get_datagrid_context(self, request):
        has_multipath = models.Disk.objects.exclude(
            disk_multipath_name='').exists()
        return {
            'has_multipath': has_multipath,
        }

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
            'name': 'used',
            'label': _('Used'),
            'sortable': False,
        })

        columns.append({
            'name': 'avail',
            'label': _('Available'),
            'sortable': False,
        })

        columns.append({
            'name': 'compression',
            'label': _('Compression'),
            'sortable': False,
        })

        columns.append({
            'name': 'compressratio',
            'label': _('Compression Ratio'),
            'sortable': False,
        })

        columns.append({
            'name': 'status',
            'label': _('Status'),
            'sortable': False,
        })

        columns.append({
            'name': 'readonly',
            'label': _('Readonly'),
            'sortable': False,
        })

        columns.append({
            'name': 'comments',
            'label': _('Comments'),
            'sortable': False,
        })
        return columns

    def _action_builder(
        self, name, label=None, url=None, func="editObject", icon=None,
        show=None, fstype="ZFS", decrypted=True, has_enc=False, enc_level=None,
        hide_unknown=True,
    ):

        if url is None:
            url = "_%s_url" % (name, )

        if icon is None:
            icon = name

        if show == "ALL":
            hide_cond = "false"
        elif show == "+DATASET":
            hide_cond = (
                "row.data.type != 'dataset' && row.data.type !== undefined"
            )
        elif show == "DATASET":
            hide_cond = "row.data.type != 'dataset'"
        elif show == "ZVOL":
            hide_cond = "row.data.type != 'zvol'"
        else:
            hide_cond = "row.data.type !== undefined"

        if fstype == "ZFS":
            hide_fs = (
                "row.data.vol_fstype !== undefined && "
                "row.data.vol_fstype != 'ZFS'"
            )
        else:
            hide_fs = "false"

        if name == "upgrade":
            hide_cond = "row.data.is_upgraded !== false"

        if decrypted is True:
            hide_enc = (
                "row.data.vol_fstype !== undefined && "
                "row.data.is_decrypted == false"
            )
        elif decrypted is False:
            hide_enc = "row.data.is_decrypted == true"
        elif decrypted is None:
            hide_enc = "false"

        if has_enc is True:
            if enc_level is not None:
                hide_hasenc = "row.data.vol_encrypt != %d" % (enc_level, )
            else:
                hide_hasenc = "row.data.vol_encrypt == 0"
        else:
            hide_hasenc = "false"

        if hide_unknown is True:
            hide_unknown = "row.data.status == 'UNKNOWN'"
        else:
            hide_unknown = "false"

        on_select_after = """function(evt, actionName, action) {
  for(var i=0;i < evt.rows.length;i++) {
    var row = evt.rows[i];
    if((%(hide_unknown)s) || (%(hide)s) || (%(hide_fs)s) || (%(hide_enc)s) || (%(hide_hasenc)s) || !%(hide_url)s) {
      query(".grid" + actionName).forEach(function(item, idx) {
        domStyle.set(item, "display", "none");
      });
      break;
    }
  }
}""" % {
            'hide': hide_cond,
            'hide_fs': hide_fs,
            'hide_enc': hide_enc,
            'hide_hasenc': hide_hasenc,
            'hide_unknown': hide_unknown,
            'hide_url': 'row.data.%s' % url,
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
            'button_name': (
                '<img src="%simages/ui/buttons/%s.png" width="18px" '
                'height="18px">' % (
                    settings.STATIC_URL,
                    icon,
                )
            ),
            'tooltip': label,
            'on_select_after': on_select_after,
            'on_click': on_click,
        }

        return data

    def get_actions(self):

        actions = OrderedDict()
        actions['Detach'] = self._action_builder(
            'detach',
            label=_('Detach Volume'),
            func="editScaryObject",
            icon="remove_volume",
            fstype="ALL",
            decrypted=None,
            hide_unknown=False,
        )
        actions['Scrub'] = self._action_builder(
            'scrub', label=_('Scrub Volume')
        )
        actions['Options'] = self._action_builder(
            'options',
            label=_('Edit Options'),
            icon="settings",
        )
        actions['NewDataset'] = self._action_builder(
            'add_dataset',
            label=_('Create Dataset'),
        )
        actions['NewVolume'] = self._action_builder(
            'add_zfs_volume',
            label=_('Create zvol'),
        )
        actions['ChangePerm'] = self._action_builder(
            'permissions',
            label=_('Change Permissions'),
            show="+DATASET",
            fstype="ALL",
        )
        actions['ManualSnapshot'] = self._action_builder(
            "manual_snapshot",
            label=_('Create Snapshot'),
            icon="create_snapshot",
            show="ALL",
        )
        actions['VolStatus'] = self._action_builder(
            "status",
            label=_('Volume Status'),
            func="viewModel",
            icon="zpool_status",
        )
        actions['VolLock'] = self._action_builder(
            "volume_lock",
            label=_('Lock Volume'),
            icon="lock_volume",
            has_enc=True,
            enc_level=2,
        )
        actions['VolCreatePass'] = self._action_builder(
            "create_passphrase",
            label=_('Create Passphrase'),
            icon="key_change",
            has_enc=True,
            enc_level=1,
        )
        actions['VolChangePass'] = self._action_builder(
            "change_passphrase",
            label=_('Change Passphrase'),
            icon="key_change",
            has_enc=True,
            enc_level=2,
        )
        actions['VolDownloadKey'] = self._action_builder(
            "download_key",
            label=_('Download Key'),
            icon="key_download",
            has_enc=True,
        )
        actions['VolReKey'] = self._action_builder(
            "rekey",
            label=_('Encryption Re-key'),
            icon="key_rekey",
            has_enc=True,
        )
        actions['VolAddRecKey'] = self._action_builder(
            "add_reckey",
            label=_('Add recovery key'),
            icon="key_addrecovery",
            has_enc=True,
        )
        actions['VolRemRecKey'] = self._action_builder(
            "rem_reckey",
            label=_('Remove recovery key'),
            icon="key_removerecovery",
            has_enc=True,
        )
        actions['VolUnlock'] = self._action_builder(
            "unlock",
            label=_('Unlock'),
            icon="key_unlock",
            decrypted=False,
        )

        actions['Upgrade'] = self._action_builder(
            "upgrade",
            label=_('Upgrade'),
            func="editScaryObject",
            icon="upgrade",
        )

        # Dataset actions
        actions['DatasetDelete'] = self._action_builder(
            "dataset_delete",
            label=_('Destroy Dataset'),
            func="editScaryObject",
            icon="remove_dataset",
            show="DATASET",
        )
        actions['DatasetEdit'] = self._action_builder(
            "dataset_edit",
            label=_('Edit Options'),
            icon="settings",
            show="DATASET",
        )
        actions['DatasetCreate'] = self._action_builder(
            "dataset_create",
            label=_('Create Dataset'),
            icon="add_dataset",
            show="DATASET",
        )
        actions['NewDsVolume'] = self._action_builder(
            "add_zfs_volume",
            label=_('Create zvol'),
            show="DATASET",
        )

        # ZVol actions
        actions['ZVolEdit'] = self._action_builder(
            "zvol_edit",
            label=_('Edit zvol'),
            icon="settings",
            show="ZVOL",
        )
        actions['ZVolDelete'] = self._action_builder(
            "zvol_delete",
            label=_('Destroy zvol'),
            func="editScaryObject",
            icon="remove_volume",
            show="ZVOL",
        )

        return actions


class VolumeStatusFAdmin(BaseFreeAdmin):

    app_label = "storage"
    double_click = False
    module_name = "volumestatus"
    verbose_name = _("Volume Status")
    resource = False

    def get_resource_url(self, request):
        return "%s%s/status/" % (
            reverse('api_dispatch_list', kwargs={
                'api_name': 'v1.0',
                'resource_name': 'storage/volume',
            }),
            request.GET.get('id'),
        )

    def get_datagrid_context(self, request):
        volume = models.Volume.objects.get(id=request.GET.get('id'))
        if volume.vol_fstype == 'ZFS':
            pool = notifier().zpool_parse(volume.vol_name)
            return {
                'pool': pool,
            }
        return {}

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

        actions['Disk'] = self._action_builder("disk", label=_('Edit Disk'))

        actions['Offline'] = self._action_builder(
            'offline', label=_('Offline'),
        )

        actions['Online'] = self._action_builder(
            'online', label=_('Online'),
        )

        actions['Detach'] = self._action_builder("detach", label=_('Detach'))

        actions['Replace'] = self._action_builder(
            'replace', label=_('Replace'),
        )

        actions['Remove'] = self._action_builder("remove", label=_('Remove'))

        return actions


class ScrubFAdmin(BaseFreeAdmin):

    icon_model = "cronJobIcon"
    icon_object = "cronJobIcon"
    icon_add = "AddcronJobIcon"
    icon_view = "ViewcronJobIcon"
    resource_mixin = ScrubResourceMixin
    exclude_fields = (
        'id',
    )

    def get_datagrid_columns(self):

        columns = []

        columns.append({
            'name': 'scrub_volume',
            'label': _('Volume'),
        })

        columns.append({
            'name': 'scrub_threshold',
            'label': _('Threshold days'),
        })

        columns.append({
            'name': 'scrub_description',
            'label': _('Description'),
        })

        columns.append({
            'name': 'human_minute',
            'label': _('Minute'),
            'sortable': False,
        })

        columns.append({
            'name': 'human_hour',
            'label': _('Hour'),
            'sortable': False,
        })

        columns.append({
            'name': 'human_daymonth',
            'label': _('Day of month'),
            'sortable': False,
        })

        columns.append({
            'name': 'human_month',
            'label': _('Month'),
            'sortable': False,
        })

        columns.append({
            'name': 'human_dayweek',
            'label': _('Day of week'),
            'sortable': False,
        })

        columns.append({
            'name': 'scrub_enabled',
            'label': _('Enabled'),
            'sortable': False,
        })
        return columns


class TaskFAdmin(BaseFreeAdmin):

    icon_model = "SnapIcon"
    icon_add = "CreatePeriodicSnapIcon"
    icon_view = "ViewAllPeriodicSnapIcon"
    icon_object = "SnapIcon"
    extra_js = "taskrepeat_checkings();"
    composed_fields = (
        ('Snapshot Lifetime', ('task_ret_count', 'task_ret_unit'), 'The amount of time these snapshots are retained before being automatically deleted'),
    )
    resource_mixin = TaskResourceMixin
    exclude_fields = (
        'id',
        'task_ret_count',
        'task_ret_unit',
        'task_begin',
        'task_end',
        'task_interval',
        'task_repeat_unit',
        'task_byweekday',
    )

    def get_datagrid_columns(self):
        columns = super(TaskFAdmin, self).get_datagrid_columns()
        columns.insert(2, {
            'name': 'when',
            'label': _('When'),
            'sortable': False,
        })

        columns.insert(3, {
            'name': 'interv',
            'label': _('Frequency'),
            'sortable': False,
        })

        columns.insert(4, {
            'name': 'keepfor',
            'label': _('Keep snapshot for'),
            'sortable': False,
        })

        columns.insert(5, {
            'name': 'vmwaresync',
            'label': _('VMware Sync'),
            'sortable': False,
        })

        return columns


class ReplicationFAdmin(BaseFreeAdmin):

    icon_model = "ReplIcon"
    icon_add = "AddReplIcon"
    icon_view = "ViewAllReplIcon"
    icon_object = "ReplIcon"
    resource_mixin = ReplicationResourceMixin
    exclude_fields = (
        'id',
        'repl_remote',
        'repl_userepl',
    )
    refresh_time = 12000

    def get_datagrid_columns(self):
        columns = super(ReplicationFAdmin, self).get_datagrid_columns()
        columns.insert(2, {
            'name': 'repl_remote_hostname',
            'label': _('Remote Hostname'),
            'sortable': False,
        })
        columns.insert(3, {
            'name': 'repl_status',
            'label': _('Status'),
            'sortable': False,
        })
        return columns


class VMWarePluginFAdmin(BaseFreeAdmin):
    exclude_fields = (
        'id',
        'password',
    )
    icon_model = 'VMSnapshotIcon'
    icon_object = 'VMSnapshotIcon'
    icon_add = 'VMSnapshotIcon'
    icon_view = 'VMSnapshotIcon'


site.register(models.Disk, DiskFAdmin)
site.register(models.Scrub, ScrubFAdmin)
site.register(models.Task, TaskFAdmin)
site.register(models.Volume, VolumeFAdmin)
site.register(models.Replication, ReplicationFAdmin)
site.register(models.VMWarePlugin, VMWarePluginFAdmin)
site.register(None, VolumeStatusFAdmin)

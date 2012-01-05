from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
import models

NAME = _('Storage')
BLACKLIST = ['Disk','ReplRemote']
ICON = u'StorageIcon'

class ViewRemote(TreeNode):

        gname = 'storage.Replication.View'
        type = 'openstorage'
        append_app = False

class ViewPeriodic(TreeNode):

        gname = 'storage.Task.View'
        type = 'openstorage'
        append_app = False

class ViewSnap(TreeNode):

        gname = 'View'
        name = _(u'View All Snapshots')
        type = 'openstorage'
        icon = u'ViewAllPeriodicSnapIcon'
        app_name = 'storage'
        model = 'Task'
        append_app = False

class AddVolume(TreeNode):

        gname = 'Add'
        name = _(u'Volume Manager')
        view = 'storage_wizard'
        type = 'volumewizard'
        icon = u'AddVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class ImportVolume(TreeNode):

        gname = 'Import'
        name = _(u'Import Volume')
        view = 'storage_import'
        type = 'volumewizard'
        icon = u'ImportVolumeIcon'
        app_name = 'storage'
        model = 'Volume'
        append_app = False

class ViewDisks(TreeNode):

        gname = 'ViewDisks'
        name = _(u'View Disks')
        view = 'storage_datagrid_disks'
        type = 'view'
        icon = u'ViewAllVolumesIcon'
        app_name = 'storage'
        model = 'Disk'
        append_app = False

class AutoImportVolume(TreeNode):

        gname = 'AutoImport'
        name = _(u'Auto Import Volume')
        view = 'storage_autoimport'
        type = 'volumewizard'
        icon = u'ImportVolumeIcon'
        app_name = 'storage'
        model = 'Volume'
        append_app = False

class ViewVolumes(TreeNode):

        gname = 'View'
        name = _(u'View All Volumes')
        view = u'storage_home'
        type = 'openstorage'
        icon = u'ViewAllVolumesIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False


class AddZVol(TreeNode):

        gname = 'storage.ZVol.Add'
        name = _(u'Create ZFS Volume')
        view = 'storage_zvol'
        icon = u'AddZFSVolumeIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class CreatePeriodicSnap(TreeNode):

        gname = 'storage.Task.Add'
        name = _(u'Add Periodic Snapshot')
        view = 'storage_periodicsnap'
        icon = u'CreatePeriodicSnapIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Task'
        append_app = False

class Volumes(TreeNode):

        gname = 'storage.Volume'
        name = _(u'Volumes')
        icon = u'VolumesIcon'

        def __init__(self, *args, **kwargs):

            super(Volumes, self).__init__(*args, **kwargs)
            self.append_children([AddVolume(),
                                    ImportVolume(),
                                    AutoImportVolume(),
                                    ViewVolumes(),
                                    ViewDisks(),
                                 ])
            en_dataset = models.MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0

            mp = models.MountPoint.objects.select_related().order_by('-id')
            for i in mp:
                nav = TreeNode(i.mp_volume.id)
                nav.name = i.mp_path
                nav.order = -i.id
                nav.model = 'Volume'
                nav.kwargs = {'oid': i.mp_volume.id, 'model': 'Volume'}
                nav.icon = u'VolumesIcon'

                if i.mp_volume.vol_fstype == 'ZFS':
                    ds = TreeNode('Dataset')
                    ds.name = _(u'Create ZFS Dataset')
                    ds.view = 'storage_dataset'
                    ds.icon = u'AddDatasetIcon'
                    ds.type = 'object'
                    append_app = False
                    ds.kwargs = {'fs': i.mp_volume.vol_name}
                    nav.append_child(ds)

                    zv = AddZVol()
                    zv.kwargs = {'volume_name': i.mp_volume.vol_name}
                    nav.append_child(zv)

                subnav = TreeNode('ChangePermissions')
                subnav.name = _('Change Permissions')
                subnav.type = 'editobject'
                subnav.view = 'storage_mp_permission'
                subnav.kwargs = {'path': i.mp_path}
                subnav.model = 'Volume'
                subnav.icon = u'ChangePasswordIcon'
                subnav.app_name = 'storage'

                datasets = i.mp_volume.get_datasets()
                if datasets:
                    for name, d in datasets.items():

                        nav2 = TreeNode(name)
                        nav2.name = d.mountpoint
                        nav2.icon = u'VolumesIcon'

                        ds = TreeNode('Dataset')
                        ds.name = _(u'Create ZFS Dataset')
                        ds.view = 'storage_dataset'
                        ds.icon = u'AddDatasetIcon'
                        ds.type = 'object'
                        ds.kwargs = {'fs': d.path}
                        nav2.append_child(ds)

                        subnav2 = TreeNode('ChangePermissions')
                        subnav2.name = _(u'Change Permissions')
                        subnav2.type = 'editobject'
                        subnav2.view = 'storage_mp_permission'
                        subnav2.kwargs = {'path': d.mountpoint}
                        subnav2.model = 'Volumes'
                        subnav2.icon = u'ChangePasswordIcon'
                        subnav2.app_name = 'storage'

                        nav.append_child(nav2)
                        nav2.append_child(subnav2)

                nav.append_child(subnav)
                self.insert_child(0, nav)

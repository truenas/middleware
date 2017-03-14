from django.utils.translation import ugettext_lazy as _
from freenasUI.freeadmin.tree import TreeNode
from freenasUI.middleware.notifier import notifier
from . import models

NAME = _('Storage')
BLACKLIST = ['Disk', 'ReplRemote', 'Volume']
ICON = 'StorageIcon'
ORDER = 20


class ViewRemote(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.Replication'


class ViewPeriodic(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.Task'


class ViewScrub(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.Scrub'


class ViewSnap(TreeNode):

    gname = 'Snapshots.View'
    name = _('Snapshots')
    type = 'openstorage'
    icon = 'ViewAllPeriodicSnapIcon'


class ViewVMWare(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.VMWarePlugin'


class AddVolume(TreeNode):

    gname = 'Add'
    name = _('Volume Manager')
    view = 'storage_volumemanager'
    type = 'volumewizard'
    icon = 'AddVolumeIcon'
    app_name = 'storage'
    model = 'Volumes'
    skip = True
    order = -20


class ImportDisk(TreeNode):

    gname = 'Import'
    name = _('Import Disk')
    view = 'storage_import'
    type = 'volumewizard'
    icon = 'ImportVolumeIcon'
    app_name = 'storage'
    model = 'Volume'
    skip = True


class ViewDisks(TreeNode):

    gname = 'ViewDisks'
    name = _('View Disks')
    view = 'freeadmin_storage_disk_datagrid'
    type = 'view'
    icon = 'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Disk'
    skip = True


class ViewEnclosure(TreeNode):

    gname = 'ViewEnclosure'
    name = _('View Enclosure')
    view = 'storage_enclosure_status'
    type = 'view'
    icon = 'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Disk'
    skip = True


class ViewMultipaths(TreeNode):

    gname = 'storage.View.Multipaths'
    name = _('View Multipaths')
    view = 'storage_multipath_status'
    type = 'view'
    icon = 'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Disk'
    skip = True


class ImportVolume(TreeNode):

    gname = 'ImportVolume'
    name = _('Import Volume')
    view = 'storage_autoimport'
    type = 'volumewizard'
    icon = 'ImportVolumeIcon'
    app_name = 'storage'
    model = 'Volume'
    skip = True


class ViewVolumes(TreeNode):

    gname = 'View'
    name = _('View Volumes')
    view = 'storage_home'
    type = 'openstorage'
    icon = 'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Volumes'
    skip = True


class AddZVol(TreeNode):

    gname = 'storage.ZVol.Add'
    name = _('Create zvol')
    view = 'storage_zvol'
    icon = 'AddZFSVolumeIcon'
    type = 'object'
    app_name = 'storage'
    model = 'Volumes'
    skip = True


class CreatePeriodicSnap(TreeNode):

    gname = 'Add'
    name = _('Add Periodic Snapshot')
    view = 'freeadmin_storage_task_add'
    icon = 'CreatePeriodicSnapIcon'
    type = 'object'
    app_name = 'storage'
    model = 'Task'
    append_to = 'storage.Task'


class Volumes(TreeNode):

    gname = 'Volumes'
    name = _('Volumes')
    icon = 'VolumesIcon'
    order = -1

    def _gen_dataset(self, node, dataset):
        if dataset.name.startswith('.'):
            return

        nav = TreeNode(dataset.name)
        nav.name = dataset.mountpoint
        nav.icon = 'VolumesIcon'

        ds = TreeNode('Dataset')
        ds.name = _('Create Dataset')
        ds.view = 'storage_dataset'
        ds.icon = 'AddDatasetIcon'
        ds.type = 'object'
        ds.kwargs = {'fs': dataset.path}
        nav.append_child(ds)

        subnav = TreeNode('ChangePermissions')
        subnav.name = _('Change Permissions')
        subnav.type = 'editobject'
        subnav.view = 'storage_mp_permission'
        subnav.kwargs = {'path': dataset.mountpoint}
        subnav.model = 'Volumes'
        subnav.icon = 'ChangePasswordIcon'
        subnav.app_name = 'storage'

        zv = AddZVol()
        zv.kwargs = {'parent': dataset.path}

        node.append_child(nav)
        nav.append_child(subnav)
        nav.append_child(zv)
        for child in dataset.children:
            self._gen_dataset(nav, child)

    def __init__(self, *args, **kwargs):

        super(Volumes, self).__init__(*args, **kwargs)
        self.append_children([
            AddVolume(),
            ImportDisk(),
            ImportVolume(),
            ViewVolumes(),
            ViewDisks(),
        ])

        if not notifier().is_freenas():
            self.append_child(ViewEnclosure())

        has_multipath = models.Disk.objects.exclude(
            disk_multipath_name=''
        ).exists()
        if has_multipath:
            self.append_child(ViewMultipaths())

        for i in models.Volume.objects.order_by('-id'):
            nav = TreeNode(i.id)
            nav.name = i.vol_path
            nav.order = -i.id
            nav.model = 'Volume'
            nav.kwargs = {'oid': i.id, 'model': 'Volume'}
            nav.icon = 'VolumesIcon'

            if i.vol_fstype == 'ZFS':
                ds = TreeNode('Dataset')
                ds.name = _('Create Dataset')
                ds.view = 'storage_dataset'
                ds.icon = 'AddDatasetIcon'
                ds.type = 'object'
                ds.kwargs = {'fs': i.vol_name}
                nav.append_child(ds)

                zv = AddZVol()
                zv.kwargs = {'parent': i.vol_name}
                nav.append_child(zv)

            subnav = TreeNode('ChangePermissions')
            subnav.name = _('Change Permissions')
            subnav.type = 'editobject'
            subnav.view = 'storage_mp_permission'
            subnav.kwargs = {'path': i.vol_path}
            subnav.model = 'Volume'
            subnav.icon = 'ChangePasswordIcon'
            subnav.app_name = 'storage'

            datasets = i.get_datasets(hierarchical=True)
            if datasets:
                for name, d in list(datasets.items()):
                    # TODO: non-recursive algo
                    self._gen_dataset(nav, d)

            nav.append_child(subnav)
            self.insert_child(0, nav)

from freeadmin.tree import TreeNode
from django.utils.translation import ugettext_lazy as _
import models

NAME = _('Storage')
BLACKLIST = ['Disk', 'ReplRemote', 'Volume', 'MountPoint']
ICON = u'StorageIcon'

class ViewRemote(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.Replication'

class ViewPeriodic(TreeNode):

    gname = 'View'
    type = 'openstorage'
    append_to = 'storage.Task'

class ViewSnap(TreeNode):

    gname = 'View'
    name = _(u'View Snapshots')
    type = 'openstorage'
    icon = u'ViewAllPeriodicSnapIcon'
    app_name = 'storage'
    model = 'Task'
    skip = True

class ViewScrub(TreeNode):

    gname = 'View'
    name = _('View ZFS Scrubs')
    view = 'storage_scrubs'
    append_to = 'storage.Scrub'

class AddVolume(TreeNode):

    gname = 'Add'
    name = _(u'Volume Manager')
    view = 'storage_wizard'
    type = 'volumewizard'
    icon = u'AddVolumeIcon'
    app_name = 'storage'
    model = 'Volumes'
    skip = True

class ImportVolume(TreeNode):

    gname = 'Import'
    name = _(u'Import Volume')
    view = 'storage_import'
    type = 'volumewizard'
    icon = u'ImportVolumeIcon'
    app_name = 'storage'
    model = 'Volume'
    skip = True

class ViewDisks(TreeNode):

    gname = 'ViewDisks'
    name = _(u'View Disks')
    view = 'storage_datagrid_disks'
    type = 'view'
    icon = u'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Disk'
    skip = True

class ViewMultipaths(TreeNode):

    gname = 'storage.View.Multipaths'
    name = _(u'View Multipaths')
    view = 'storage_multipath_status'
    type = 'view'
    icon = u'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Disk'
    skip = True

class AutoImportVolume(TreeNode):

    gname = 'AutoImport'
    name = _(u'Auto Import Volume')
    view = 'storage_autoimport'
    type = 'volumewizard'
    icon = u'ImportVolumeIcon'
    app_name = 'storage'
    model = 'Volume'
    skip = True

class ViewVolumes(TreeNode):

    gname = 'View'
    name = _(u'View Volumes')
    view = u'storage_home'
    type = 'openstorage'
    icon = u'ViewAllVolumesIcon'
    app_name = 'storage'
    model = 'Volumes'
    skip = True


class AddZVol(TreeNode):

    gname = 'storage.ZVol.Add'
    name = _(u'Create ZFS Volume')
    view = 'storage_zvol'
    icon = u'AddZFSVolumeIcon'
    type = 'object'
    app_name = 'storage'
    model = 'Volumes'
    skip = True

class CreatePeriodicSnap(TreeNode):

    gname = 'Add'
    name = _(u'Add Periodic Snapshot')
    view = 'storage_periodicsnap'
    icon = u'CreatePeriodicSnapIcon'
    type = 'object'
    app_name = 'storage'
    model = 'Task'
    append_to = 'storage.Task'

class Volumes(TreeNode):

    gname = 'Volumes'
    name = _(u'Volumes')
    icon = u'VolumesIcon'

    def _gen_dataset(self, node, dataset):

        nav = TreeNode(dataset.name)
        nav.name = dataset.mountpoint
        nav.icon = u'VolumesIcon'

        ds = TreeNode('Dataset')
        ds.name = _(u'Create ZFS Dataset')
        ds.view = 'storage_dataset'
        ds.icon = u'AddDatasetIcon'
        ds.type = 'object'
        ds.kwargs = {'fs': dataset.path}
        nav.append_child(ds)

        subnav = TreeNode('ChangePermissions')
        subnav.name = _(u'Change Permissions')
        subnav.type = 'editobject'
        subnav.view = 'storage_mp_permission'
        subnav.kwargs = {'path': dataset.mountpoint}
        subnav.model = 'Volumes'
        subnav.icon = u'ChangePasswordIcon'
        subnav.app_name = 'storage'

        node.append_child(nav)
        nav.append_child(subnav)
        for child in dataset.children:
            self._gen_dataset(nav, child)

    def __init__(self, *args, **kwargs):

        super(Volumes, self).__init__(*args, **kwargs)
        self.append_children([AddVolume(),
                                ImportVolume(),
                                AutoImportVolume(),
                                ViewVolumes(),
                                ViewDisks(),
                             ])

        en_dataset = models.MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0

        has_multipath = models.Disk.objects.exclude(disk_multipath_name='').exists()
        if has_multipath:
            self.append_child(ViewMultipaths())

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

            datasets = i.mp_volume.get_datasets(hierarchical=True)
            if datasets:
                for name, d in datasets.items():
                    # TODO: non-recursive algo
                    self._gen_dataset(nav, d)

            nav.append_child(subnav)
            self.insert_child(0, nav)

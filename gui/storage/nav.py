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

        gname = 'storage.Snapshots.View'
        name = _(u'View All Snapshots')
        type = 'openstorage'
        icon = u'ViewAllPeriodicSnapIcon'
        app_name = 'storage'
        model = 'Task'
        append_app = False

class AddVolume(TreeNode):

        gname = 'storage.Volume.Add'
        name = _(u'Create Volume')
        view = 'storage_wizard'
        type = 'volumewizard'
        icon = u'AddVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class ImportVolume(TreeNode):

        gname = 'storage.Volume.Import'
        name = _(u'Import Volume')
        view = 'storage_import'
        type = 'volumewizard'
        icon = u'ImportVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class AutoImportVolume(TreeNode):

        gname = 'storage.Volume.AutoImport'
        name = _(u'Auto Import Volume')
        view = 'storage_autoimport'
        type = 'volumewizard'
        icon = u'ImportVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class ViewVolumes(TreeNode):

        gname = 'storage.Volume.View'
        name = _(u'View All Volumes')
        view = u'storage_home'
        type = 'openstorage'
        icon = u'ViewAllVolumesIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class AddDataset(TreeNode):

        gname = 'storage.Dataset.Add'
        name = _(u'Create ZFS Dataset')
        view = 'storage_dataset'
        icon = u'AddDatasetIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False

class AddZVol(TreeNode):

        gname = 'storage.ZVol.Add'
        name = _(u'Create ZFS Volume')
        view = 'storage_zvol'
        icon = u'AddDatasetIcon'
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
            self.append_children([AddVolume(),ImportVolume(),AutoImportVolume(),ViewVolumes()])
            en_dataset = models.MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0
            if en_dataset:
                self.append_child(AddDataset)
                self.append_child(AddZVol)

            mp = models.MountPoint.objects.filter(mp_ischild=False).exclude(mp_volume__vol_fstype__exact='iscsi').select_related().order_by('-id')
            for i in mp:
                nav = TreeNode()
                nav.name = i.mp_path
                nav.order = -i.id
                nav.model = 'Volume'
                nav.kwargs = {'oid': i.mp_volume.id, 'model': 'Volume'}
                nav.icon = u'VolumesIcon'

                subnav = TreeNode()
                subnav.name = _('Change Permissions')
                subnav.type = 'editobject'
                subnav.view = 'storage_mp_permission'
                subnav.kwargs = {'object_id': i.id}
                subnav.model = 'Volume'
                subnav.icon = u'ChangePasswordIcon'
                subnav.app_name = 'storage'

                datasets = models.MountPoint.objects.filter(mp_path__startswith=i.mp_path,mp_ischild=True)
                for d in datasets:

                    nav2 = TreeNode()
                    nav2.name = d.mp_path
                    nav2.icon = u'VolumesIcon'
                    nav2.model = 'MountPoint'
                    nav2.kwargs = {'oid': d.id, 'model': 'MountPoint'}

                    subnav2 = TreeNode()
                    subnav2.name = _(u'Change Permissions')
                    subnav2.type = 'editobject'
                    subnav2.view = 'storage_mp_permission'
                    subnav2.kwargs = {'object_id': d.id}
                    subnav2.model = 'Volumes'
                    subnav2.icon = u'ChangePasswordIcon'
                    subnav2.app_name = 'storage'

                    nav.append_child(nav2)
                    nav2.append_child(subnav2)

                nav.append_child(subnav)
                self.insert_child(0, nav)

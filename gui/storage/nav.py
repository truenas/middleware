from freeadmin.tree import TreeNode
from django.utils.translation import ugettext as _
import models

BLACKLIST = ['Disk','ReplRemote']
ICON = u'StorageIcon'

class ViewRemote(TreeNode):

        name = _(u'View All Replication Tasks')
        type = 'openreplication'
        icon = u'ViewAllReplIcon'
        app_name = 'storage'
        append_app = False
        options = []

class ViewPeriodic(TreeNode):

        name = _(u'View All Periodic Snapshot Tasks')
        view = u'storage_home'
        type = 'openperiodic'
        icon = u'ViewAllPeriodicSnapIcon'
        app_name = 'storage'
        model = 'Task'
        append_app = False
        options = []

class ViewSnap(TreeNode):

        name = _(u'View All Snapshots')
        type = 'opensnaps'
        icon = u'ViewAllPeriodicSnapIcon'
        app_name = 'storage'
        model = 'Task'
        append_app = False
        options = []

class AddVolume(TreeNode):

        name = _(u'Create Volume')
        view = 'storage_wizard'
        type = 'volumewizard'
        icon = u'AddVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class ImportVolume(TreeNode):

        name = _(u'Import Volume')
        view = 'storage_import'
        type = 'volumewizard'
        icon = u'ImportVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class ViewVolumes(TreeNode):

        name = _(u'View All Volumes')
        view = u'storage_home'
        type = 'openstorage'
        icon = u'ViewAllVolumesIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class AddDataset(TreeNode):

        name = _(u'Create ZFS Dataset')
        view = 'storage_dataset'
        icon = u'AddDatasetIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class CreatePeriodicSnap(TreeNode):

        name = _(u'Add Periodic Snapshot')
        rename = _(u'Create Periodic Snapshot')
        view = 'storage_periodicsnap'
        icon = u'CreatePeriodicSnapIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Task'
        append_app = False
        options = []

class Volumes(TreeNode):

        name = _(u'Volumes')
        icon = u'VolumesIcon'

        def __init__(self, *args, **kwargs):

            #super(Volumes, self).__init__(*args, **kwargs)
            self.options = [AddVolume(),ImportVolume(),ViewVolumes()]
            en_dataset = models.MountPoint.objects.filter(mp_volume__vol_fstype__exact='ZFS').count() > 0
            if en_dataset:
                self.append_child(AddDataset)

            mp = models.MountPoint.objects.filter(mp_ischild=False).exclude(mp_volume__vol_fstype__exact='iscsi').select_related().order_by('-id')
            for i in mp:
                nav = TreeNode()
                nav.name = i.mp_path
                nav.order = -i.id
                nav.model = 'Volume'
                nav.kwargs = {'oid': i.mp_volume.id, 'model': 'Volume'}
                nav.icon = u'VolumesIcon'
                nav.options = []

                subnav = TreeNode()
                subnav.name = _('Change Permissions')
                subnav.type = 'editobject'
                subnav.view = 'storage_mp_permission'
                subnav.kwargs = {'object_id': i.id}
                subnav.model = 'Volume'
                subnav.icon = u'ChangePasswordIcon'
                subnav.app_name = 'storage'
                subnav.options = []

                datasets = models.MountPoint.objects.filter(mp_path__startswith=i.mp_path,mp_ischild=True)
                for d in datasets:

                    nav2 = TreeNode()
                    nav2.name = d.mp_path
                    nav2.icon = u'VolumesIcon'
                    nav2.model = 'MountPoint'
                    nav2.kwargs = {'oid': d.id, 'model': 'MountPoint'}
                    nav2.options = []

                    subnav2 = TreeNode()
                    subnav2.name = _(u'Change Permissions')
                    subnav2.type = 'editobject'
                    subnav2.view = 'storage_mp_permission'
                    subnav2.kwargs = {'object_id': d.id}
                    subnav2.model = 'Volumes'
                    subnav2.icon = u'ChangePasswordIcon'
                    subnav2.app_name = 'storage'
                    subnav2.options = []

                    nav.append_child(nav2)
                    nav2.append_child(subnav2)

                #if i.mp_volume.vol_fstype == 'ZFS':
                
                nav.append_child(subnav)
                self.insert_child(0, nav)

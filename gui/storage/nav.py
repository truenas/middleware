from django_nav import Nav, NavOption
import models

BLACKLIST = ['Disk',]

class AddVolume(NavOption):

        name = u'Add Volume'
        view = 'storage_wizard'
        type = 'volumewizard'
        icon = u'AddVolumeIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class ViewVolumes(NavOption):

        name = u'View All Volumes'
        view = u'storage_home'
        type = 'openstorage'
        icon = u'ViewAllVolumesIcon'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class AddDataset(NavOption):

        name = u'Add Dataset'
        view = 'storage_dataset'
        icon = u'AddDatasetIcon'
        type = 'object'
        app_name = 'storage'
        model = 'Volumes'
        append_app = False
        options = []

class Volumes(NavOption):

        name = u'Volumes'
        icon = u'VolumesIcon'

        def __init__(self, *args, **kwargs):

            self.options = [AddVolume,ViewVolumes, AddDataset]
            #super(Volumes, self).__init__(*args, **kwargs)
            mp = models.MountPoint.objects.filter(mp_ischild=False).select_related().order_by('-id')
            for i in mp:
                nav = NavOption()
                nav.name = i.mp_path
                nav.order = -i.id
                nav.model = 'Volume'
                nav.kwargs = {'oid': i.mp_volume.id, 'model': 'Volume'}
                nav.icon = u'VolumesIcon'
                nav.options = []

                subnav = NavOption()
                subnav.name = 'Change Permissions'
                subnav.type = 'editobject'
                subnav.view = 'storage_mp_permission'
                subnav.kwargs = {'object_id': i.id}
                subnav.model = 'Volume'
                subnav.icon = u'ChangePasswordIcon'
                subnav.app_name = 'storage'
                subnav.options = []

                datasets = models.MountPoint.objects.filter(mp_path__startswith=i.mp_path,mp_ischild=True)
                for d in datasets:

                    nav2 = NavOption()
                    nav2.name = d.mp_path
                    nav2.icon = u'VolumesIcon'
                    nav2.model = 'MountPoint'
                    nav2.kwargs = {'oid': d.id, 'model': 'MountPoint'}
                    nav2.options = []

                    subnav2 = NavOption()
                    subnav2.name = 'Change Permissions'
                    subnav2.type = 'editobject'
                    subnav2.view = 'storage_mp_permission'
                    subnav2.kwargs = {'object_id': d.id}
                    subnav2.model = 'Volumes'
                    subnav2.icon = u'ChangePasswordIcon'
                    subnav2.app_name = 'storage'
                    subnav2.options = []

                    nav.options.append(nav2)
                    nav2.options.append(subnav2)

                #if i.mp_volume.vol_fstype == 'ZFS':
                
                nav.options.append(subnav)
                self.options.insert(0, nav)

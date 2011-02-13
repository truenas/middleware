from django_nav import Nav, NavOption

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
        options = [AddVolume,ViewVolumes, AddDataset]

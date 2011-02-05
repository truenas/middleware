from django_nav import Nav, NavOption
import models

BLACKLIST = ['Disk',]


class AddVolume(NavOption):

        name = u'Add Volume'
        view = 'storage_wizard'
        type = 'volumewizard'
        append_app = False
        options = []

class ViewVolumes(NavOption):

        name = u'View All Volumes'
        view = u'storage_home'
        type = 'openstorage'
        append_app = False
        options = []

class AddDataset(NavOption):

        name = u'Add Dataset'
        view = 'storage_dataset'
        type = 'object'
        append_app = False
        options = []

class Volumes(NavOption):

        name = u'Volumes'
        options = [AddVolume,ViewVolumes, AddDataset]

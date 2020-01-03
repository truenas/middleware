from copy import deepcopy

from middlewared.service import Service

from .mirror_base import DiskMirrorBase


class DiskService(Service, DiskMirrorBase):

    def get_swap_mirrors(self):
        mirrors = []
        return mirrors

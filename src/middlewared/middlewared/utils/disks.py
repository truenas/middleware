import os
import re

from .disks_.disk_class import VALID_WHOLE_DISK

DISKS_TO_IGNORE = ('sr', 'md', 'dm-', 'loop', 'zd')
RE_IS_PART = re.compile(r'p\d{1,3}$')


def get_disk_names() -> list[str]:
    """
    NOTE: The return of this method should match the keys retrieve when running `self.get_disks`.
    """
    disks = []
    with os.scandir('/dev') as sdir:
        for i in filter(lambda x: VALID_WHOLE_DISK.match(x.name), sdir):
            disks.append(i.name)
    return disks

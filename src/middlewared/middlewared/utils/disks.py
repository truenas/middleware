import pathlib
import re


RE_IS_PART = re.compile(r'p\d{1,3}$')


def get_disk_names() -> list[str]:
    """
    NOTE: The return of this method should match the keys retrieve when running `self.get_disks`.
    """
    disks = []
    try:
        for disk in pathlib.Path('/sys/class/block').iterdir():
            if not disk.name.startswith(('sd', 'nvme', 'pmem')):
                continue
            elif RE_IS_PART.search(disk.name):
                # sdap1/nvme0n1p12/pmem0p1/etc
                continue
            elif disk.name[:2] == 'sd' and disk.name[-1].isdigit():
                # sda1/sda2/etc
                continue
            else:
                disks.append(disk.name)
    except FileNotFoundError:
        pass

    return disks

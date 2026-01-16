import itertools
import pathlib
import re
from enum import StrEnum
from time import sleep

HBTL = re.compile('^\\d:\\d:\\d:\\d$')


class IscsiAuthType(StrEnum):
    NONE = 'NONE'
    CHAP = 'CHAP'
    CHAP_MUTUAL = 'CHAP_MUTUAL'


class InverseMap(dict):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @property
    def inv(self):
        return {v: k for k, v in self.items()}


AUTHMETHOD_LEGACY_MAP = InverseMap(**{
    'None': IscsiAuthType.NONE.value,
    'CHAP': IscsiAuthType.CHAP.value,
    'CHAP Mutual': IscsiAuthType.CHAP_MUTUAL.value,
})

# Currently SCST has this limit (scst_vdisk_dev->name)
MAX_EXTENT_NAME_LEN = 64

# We deliberately only support a subset of target parameters
ISCSI_TARGET_PARAMETERS = ['QueuedCommands']
ISCSI_HA_TARGET_PARAMETERS = ['QueuedCommands']


def sanitize_extent(device):
    if HBTL.match(device):
        return device
    return device.replace('.', '_').replace('/', '-')


def chunker(it, size):
    iterator = iter(it)
    while chunk := list(itertools.islice(iterator, size)):
        yield chunk


def delete_scsi_disk(device):
    """Delete the specified device.  Returns True on success, False otherwise."""
    try:
        p = pathlib.Path(f'/sys/class/scsi_disk/{device}/device/delete')
        p.write_text('1\n')
        sleep(1)
        if p.exists():
            return False
        else:
            return True
    except Exception:
        False

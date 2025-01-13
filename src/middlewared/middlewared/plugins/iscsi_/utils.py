from enum import StrEnum


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

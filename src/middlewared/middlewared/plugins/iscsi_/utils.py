from enum import StrEnum

import bidict


class IscsiAuthType(StrEnum):
    NONE = 'NONE'
    CHAP = 'CHAP'
    CHAP_MUTUAL = 'CHAP_MUTUAL'


AUTHMETHOD_LEGACY_MAP = bidict.bidict({
    'None': IscsiAuthType.NONE.value,
    'CHAP': IscsiAuthType.CHAP.value,
    'CHAP Mutual': IscsiAuthType.CHAP_MUTUAL.value,
})

# Currently SCST has this limit (scst_vdisk_dev->name)
MAX_EXTENT_NAME_LEN = 64

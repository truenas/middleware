import pytest

from middlewared.utils import security_descriptor
from samba.dcerpc import security
from samba.ndr import ndr_pack


SAMPLE_DOM_SID = 'S-1-5-21-3510196835-1033636670-2319939847-200108'
SAMPLE_BUILTIN_SID = 'S-1-5-32-544'


@pytest.mark.parametrize('theacl', [
    [
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'},
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'CHANGE', 'ae_type': 'ALLOWED'},
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'READ', 'ae_type': 'ALLOWED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'CHANGE', 'ae_type': 'ALLOWED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'READ', 'ae_type': 'ALLOWED'},
    ],
    [
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'FULL', 'ae_type': 'DENIED'},
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'CHANGE', 'ae_type': 'DENIED'},
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'READ', 'ae_type': 'DENIED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'FULL', 'ae_type': 'DENIED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'CHANGE', 'ae_type': 'DENIED'},
        {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'READ', 'ae_type': 'DENIED'},
    ],
])
def test__convert_share_acl(theacl):
    """ test that converting a share ACL to packed security descriptor and back yields same result """
    sd_bytes = security_descriptor.share_acl_to_sd_bytes(theacl)
    assert security_descriptor.sd_bytes_to_share_acl(sd_bytes) == theacl


@pytest.mark.parametrize('legacy,theacl', [
    [
        (
            f'{SAMPLE_BUILTIN_SID}:ALLOWED/0x0/FULL '
            f'{SAMPLE_DOM_SID}:ALLOWED/0x0/CHANGE '
            f'{SAMPLE_BUILTIN_SID}:ALLOWED/0x0/READ'
        ),
        (
            {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'FULL', 'ae_type': 'ALLOWED'},
            {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'CHANGE', 'ae_type': 'ALLOWED'},
            {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'READ', 'ae_type': 'ALLOWED'},
        )
    ],
    [
        (
            f'{SAMPLE_BUILTIN_SID}:DENIED/0x0/FULL '
            f'{SAMPLE_DOM_SID}:DENIED/0x0/CHANGE '
            f'{SAMPLE_BUILTIN_SID}:DENIED/0x0/READ'
        ),
        (
            {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'FULL', 'ae_type': 'DENIED'},
            {'ae_who_sid': SAMPLE_DOM_SID, 'ae_perm': 'CHANGE', 'ae_type': 'DENIED'},
            {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'READ', 'ae_type': 'DENIED'},
        )
    ],
])
def test__legacy_convert_share_acl(legacy, theacl):
    """ test that converting legacy share acl format to bytes and back produces expected result """
    sd_bytes = security_descriptor.legacy_share_acl_string_to_sd_bytes(legacy)
    share_acl = security_descriptor.sd_bytes_to_share_acl(sd_bytes)
    assert len(share_acl) == len(theacl)

    for idx, entry in enumerate(share_acl):
        assert entry == theacl[idx]


def test__change_without_delete_child_read_as_change():
    """ NAS-139535: CHANGE mask missing SEC_DIR_DELETE_CHILD (0x1301BF) decodes as CHANGE """
    sddl_str = f'D:(A;;{hex(0x1301bf)};;;{SAMPLE_BUILTIN_SID})'
    sd_bytes = ndr_pack(security.descriptor().from_sddl(sddl_str, security.dom_sid()))

    share_acl = security_descriptor.sd_bytes_to_share_acl(sd_bytes)

    assert len(share_acl) == 1
    assert share_acl[0] == {
        'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'CHANGE', 'ae_type': 'ALLOWED'
    }

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


def test__custom_access_mask_rejected_on_write():
    """ test that CUSTOM access mask is rejected when writing share ACL """
    share_acl = [
        {'ae_who_sid': SAMPLE_BUILTIN_SID, 'ae_perm': 'CUSTOM', 'ae_type': 'ALLOWED'}
    ]

    with pytest.raises(ValueError) as exc_info:
        security_descriptor.share_acl_to_sd_bytes(share_acl)

    assert 'CUSTOM perm is not supported for writing an ACL' in str(exc_info.value)


def test__unsupported_access_mask_read_as_custom():
    """ test that unsupported access mask (0x1301bf) is read as CUSTOM """
    # Create a security descriptor with an unsupported access mask manually
    # Using 0x1301bf which is similar to CHANGE (0x1301ff) but not exactly
    unsupported_mask = 0x1301bf

    # Build security descriptor with custom access mask using SDDL
    sddl_str = f'D:(A;;{hex(unsupported_mask)};;;{SAMPLE_BUILTIN_SID})'
    sd_obj = security.descriptor().from_sddl(sddl_str, security.dom_sid())
    sd_bytes = ndr_pack(sd_obj)

    # Convert back to share ACL format
    share_acl = security_descriptor.sd_bytes_to_share_acl(sd_bytes)

    assert len(share_acl) == 1
    assert share_acl[0]['ae_who_sid'] == SAMPLE_BUILTIN_SID
    assert share_acl[0]['ae_perm'] == 'CUSTOM'
    assert share_acl[0]['ae_type'] == 'ALLOWED'

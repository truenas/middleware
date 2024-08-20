import pytest

from middlewared.utils import security_descriptor


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

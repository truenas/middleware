import struct

import pytest

from middlewared.utils.sid import raw_sid_to_str


def _build_raw_sid(revision, authority, sub_auths):
    """Build a raw struct dom_sid (68 bytes) from components."""
    buf = bytearray(68)
    buf[0] = revision
    buf[1] = len(sub_auths)
    # identifier authority is 6 bytes big-endian
    buf[2:8] = authority.to_bytes(6, byteorder='big')
    for i, sa in enumerate(sub_auths):
        struct.pack_into('<I', buf, 8 + i * 4, sa)
    return bytes(buf)


@pytest.mark.parametrize('revision,authority,sub_auths,expected', [
    # Standard domain SID (S-1-5-21-x-y-z)
    (1, 5, [21, 3988175775, 2682076922, 2633271272],
     'S-1-5-21-3988175775-2682076922-2633271272'),
    # Domain SID with RID
    (1, 5, [21, 3988175775, 2682076922, 2633271272, 512],
     'S-1-5-21-3988175775-2682076922-2633271272-512'),
    # Well-known SID: BUILTIN\Administrators
    (1, 5, [32, 544], 'S-1-5-32-544'),
    # Well-known SID: Everyone (S-1-1-0)
    (1, 1, [0], 'S-1-1-0'),
    # Null SID
    (1, 0, [0], 'S-1-0-0'),
    # No sub-authorities
    (1, 5, [], 'S-1-5'),
])
def test__raw_sid_to_str(revision, authority, sub_auths, expected):
    raw = _build_raw_sid(revision, authority, sub_auths)
    assert raw_sid_to_str(raw) == expected


def test__raw_sid_to_str_buffer_too_short():
    with pytest.raises(ValueError, match='too short'):
        raw_sid_to_str(b'\x01\x01\x00\x00')


def test__raw_sid_to_str_invalid_count():
    # num_auths > 15 is invalid per MS-DTYP
    buf = bytearray(68)
    buf[0] = 1
    buf[1] = 16
    with pytest.raises(ValueError, match='Invalid sub-authority count'):
        raw_sid_to_str(bytes(buf))


def test__raw_sid_to_str_truncated_sub_auths():
    # Claims 4 sub-auths but buffer only has room for header
    buf = b'\x01\x04\x00\x00\x00\x00\x00\x05'
    with pytest.raises(ValueError, match='too short'):
        raw_sid_to_str(buf)

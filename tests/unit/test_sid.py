import pytest
import struct

from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID,
    IDType
)
from middlewared.utils.sid import (
    db_id_to_rid,
    get_domain_rid,
    random_sid,
    raw_sid_to_str,
    sid_is_valid,
    BASE_RID_GROUP,
    BASE_RID_USER,
)


@pytest.fixture(scope='module')
def local_sid():
    yield random_sid()


@pytest.mark.parametrize('id_type,db_id,expected_rid,valid', [
    (IDType.USER, 1000, 1000 + BASE_RID_USER, True),
    (IDType.GROUP, 1000, 1000 + BASE_RID_GROUP, True),
    (IDType.USER, 1000 + BASE_SYNTHETIC_DATASTORE_ID, None, False),
])
def test__db_id_to_rid(id_type, db_id, expected_rid, valid):
    if valid:
        assert db_id_to_rid(id_type, db_id) == expected_rid
    else:
        with pytest.raises(ValueError):
            db_id_to_rid(id_type, db_id)


@pytest.mark.parametrize('sid,valid', [
    ('S-1-5-21-3510196835-1033636670-2319939847-200108', True),
    ('S-1-5-32-544', True),
    ('S-1-2-0', False),  # technically valid SID but we don't permit it
    ('S-1-5-21-3510196835-1033636670-2319939847-200108-200108', False),
    ('S-1-5-21-3510196835-200108', False),
    ('S-1-5-21-3510196835-1033636670-231993008847-200108', False),
    ('S-1-5-21-351019683b-1033636670-2319939847-200108', False),
])
def test__sid_is_valid(sid, valid):
    assert sid_is_valid(sid) is valid


@pytest.mark.parametrize('sid,rid,valid', [
    ('S-1-5-21-3510196835-1033636670-2319939847-200108', 200108, True),
    ('S-1-5-21-3510196835-1033636670-2319939847', None, False),
    ('S-1-5-32-544', None, False),
])
def test__get_domain_rid(sid, rid, valid):
    if valid:
        assert get_domain_rid(sid) == rid
    else:
        with pytest.raises(ValueError):
            get_domain_rid(sid)


def test__random_sid_is_valid(local_sid):
    assert sid_is_valid(local_sid)


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

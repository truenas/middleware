import pytest

from middlewared.plugins.idmap_.idmap_constants import (
    BASE_SYNTHETIC_DATASTORE_ID,
    IDType
)
from middlewared.utils.sid import (
    db_id_to_rid,
    get_domain_rid,
    random_sid,
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
    ('S-1-5-21-3510196835-1033636670-231993009847-200108', False),
    ('S-1-5-21-351019683b-1033636670-231993009847-200108', False),
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

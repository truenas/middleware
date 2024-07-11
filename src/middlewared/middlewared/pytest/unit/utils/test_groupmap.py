import os
import pytest

from middlewared.plugins.smb_.util_groupmap import (
    insert_groupmap_entries,
    delete_groupmap_entry,
    list_foreign_group_memberships,
    query_groupmap_entries,
    SMBGroupMap,
    SMBGroupMembership,
    GroupmapEntryType,
    GroupmapFile,
)
from middlewared.service_exception import MatchNotFound
from middlewared.utils.sid import (
    lsa_sidtype,
    random_sid
)
from middlewared.utils.tdb import close_sysdataset_tdb_handles


@pytest.fixture(scope='module')
def groupmap_dir():
    os.makedirs('/var/db/system/samba4', exist_ok=True)


@pytest.fixture(scope='module')
def local_sid():
    try:
        yield random_sid()
    finally:
        # cleanup our tdb handles
        close_sysdataset_tdb_handles()


def test__insert_groupmap(groupmap_dir, local_sid):
    entries = [
        SMBGroupMap(
            sid=f'{local_sid}-2000010',
            gid=3000,
            sid_type=lsa_sidtype.ALIAS,
            name='bob',
            comment=''
        ),
        SMBGroupMap(
            sid=f'{local_sid}-2000011',
            gid=3001,
            sid_type=lsa_sidtype.ALIAS,
            name='larry',
            comment=''
        )
    ]

    insert_groupmap_entries(GroupmapFile.DEFAULT, entries)

    bob = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name],
        ['name', '=', 'bob']
    ], {'get': True})
    assert bob['sid'] == f'{local_sid}-2000010'
    assert bob['gid'] == 3000
    assert bob['sid_type'] == lsa_sidtype.ALIAS
    assert bob['name'] == 'bob'
    assert bob['comment'] == ''

    larry = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name],
        ['name', '=', 'larry']
    ], {'get': True})
    assert larry['sid'] == f'{local_sid}-2000011'
    assert larry['gid'] == 3001
    assert larry['sid_type'] == lsa_sidtype.ALIAS
    assert larry['name'] == 'larry'
    assert larry['comment'] == ''

    delete_groupmap_entry(
        GroupmapFile.DEFAULT,
        GroupmapEntryType.GROUP_MAPPING,
        f'{local_sid}-2000010'
    )

    entry = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name],
    ], {'get': True})

    assert entry['name'] == 'larry'

    delete_groupmap_entry(
        GroupmapFile.DEFAULT,
        GroupmapEntryType.GROUP_MAPPING,
        f'{local_sid}-2000011'
    )

    with pytest.raises(MatchNotFound):
        query_groupmap_entries(GroupmapFile.DEFAULT, [
            ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name],
            ['name', '=', 'larry']
        ], {'get': True})

    groupmaps = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.GROUP_MAPPING.name],
    ], {})

    assert len(groupmaps) == 0


def test__insert_group_membership(groupmap_dir, local_sid):
    entries = [
        SMBGroupMembership(
            sid='S-1-5-32-544',
            members=(f'{local_sid}-2000010', f'{local_sid}-2000011')
        ),
        SMBGroupMembership(
            sid='S-1-5-32-545',
            members=(f'{local_sid}-2000012', f'{local_sid}-2000013')
        ),
    ]
    insert_groupmap_entries(GroupmapFile.DEFAULT, entries)

    res = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
        ['sid', '=', 'S-1-5-32-544']
    ], {'get': True})

    assert res['sid'] == 'S-1-5-32-544'
    assert set(res['members']) == set((f'{local_sid}-2000010', f'{local_sid}-2000011'))

    res = list_foreign_group_memberships(GroupmapFile.DEFAULT, 'S-1-5-32-544')
    assert res.sid == 'S-1-5-32-544'
    assert set(res.members) == set((f'{local_sid}-2000010', f'{local_sid}-2000011'))

    res = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
        ['sid', '=', 'S-1-5-32-545']
    ], {'get': True})

    assert res['sid'] == 'S-1-5-32-545'
    assert set(res['members']) == set((f'{local_sid}-2000012', f'{local_sid}-2000013'))

    delete_groupmap_entry(
        GroupmapFile.DEFAULT,
        GroupmapEntryType.MEMBERSHIP,
        'S-1-5-32-544'
    )

    entry = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
    ], {'get': True})

    assert res['sid'] == 'S-1-5-32-545'

    delete_groupmap_entry(
        GroupmapFile.DEFAULT,
        GroupmapEntryType.MEMBERSHIP,
        'S-1-5-32-545'
    )

    with pytest.raises(MatchNotFound):
        query_groupmap_entries(GroupmapFile.DEFAULT, [
            ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
            ['sid', '=', 'S-1-5-32-544']
        ], {'get': True})

    entries = query_groupmap_entries(GroupmapFile.DEFAULT, [
        ['entry_type', '=', GroupmapEntryType.MEMBERSHIP.name],
    ], {})

    assert len(entries) == 0

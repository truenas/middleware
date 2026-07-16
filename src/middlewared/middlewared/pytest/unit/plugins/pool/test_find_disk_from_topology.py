from middlewared.plugins.pool_.info import PoolService


def make_pool():
    return {
        'topology': {
            'data': [
                {
                    'type': 'RAIDZ2',
                    'guid': '100',
                    'path': None,
                    'children': [
                        {'type': 'DISK', 'guid': '200', 'path': '/dev/sda2', 'children': []},
                        {'type': 'DISK', 'guid': '201', 'path': '/dev/sdb2', 'children': []},
                        # Disk that was missing at pool import time: libzfs reports
                        # the vdev guid as its name so no path is available.
                        {'type': 'DISK', 'guid': '463852628436549533', 'path': None, 'children': []},
                    ],
                },
            ],
        },
    }


def test_find_by_guid_when_path_is_none():
    found = PoolService(None).find_disk_from_topology('463852628436549533', make_pool())
    assert found is not None
    assert found[1]['guid'] == '463852628436549533'


def test_find_by_path():
    found = PoolService(None).find_disk_from_topology('sdb2', make_pool())
    assert found is not None
    assert found[1]['guid'] == '201'


def test_include_siblings_with_missing_disk():
    found = PoolService(None).find_disk_from_topology(
        '463852628436549533', make_pool(), {'include_siblings': True}
    )
    assert found is not None
    assert [c['guid'] for c in found[2]] == ['200', '201', '463852628436549533']


def test_include_top_level_vdev():
    found = PoolService(None).find_disk_from_topology(
        '100', make_pool(), {'include_top_level_vdev': True}
    )
    assert found is not None
    assert found[1]['guid'] == '100'


def test_not_found():
    assert PoolService(None).find_disk_from_topology('nonexistent', make_pool()) is None

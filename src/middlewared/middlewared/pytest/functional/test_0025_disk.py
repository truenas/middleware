import pytest


def test_disk_query(conn):
    req = conn.rest.get('disk')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True


def test_disk_swaps_configure(conn):
    swaps = conn.ws.call('disk.swaps_configure')
    assert isinstance(swaps, list)


def test_disk_swaps_remove_disks(conn):
    disks = [d['name'] for d in conn.ws.call('disk.query')]
    conn.ws.call('disk.swaps_remove_disks', disks)

    swaps = conn.ws.call('disk.swaps_configure')
    assert isinstance(swaps, list)


def test_disk_device_to_identifier(conn):
    for disk in conn.ws.call('disk.query'):
        ident = conn.ws.call('disk.device_to_identifier', disk['name'])
        assert isinstance(ident, str)


def test_disk_sync(conn):
    for disk in conn.ws.call('disk.query'):
        conn.ws.call('disk.sync', disk['name'])


def test_disk_sync_all(conn):
    conn.ws.call('disk.sync_all')


def test_disk_multipath_sync(conn):
    conn.ws.call('disk.multipath_sync')


def test_disk_wipe(conn):

    disks = set()
    for d in conn.ws.call('disk.query'):
        disks.add(d['name'])

    for d in conn.ws.call('boot.get_disks'):
        if d in disks:
            disks.remove(d)

    for v in conn.ws.call('pool.query'):
        for d in conn.ws.call('pool.get_disks', v['id']):
            if d in disks:
                disks.remove(d)

    if len(disks) == 0:
        pytest.skip('No spare disks to test disk wipe')

    conn.ws.call('disk.wipe', disks.pop(), 'QUICK', job=True)

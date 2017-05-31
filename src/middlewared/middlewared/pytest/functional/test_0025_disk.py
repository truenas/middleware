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

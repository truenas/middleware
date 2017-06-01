def test_boot_get_disks(conn):
    req = conn.rest.get('boot/get_disks')
    assert req.status_code == 200
    disks = req.json()
    assert isinstance(disks, list) is True

def test_pool_query(conn):
    req = conn.rest.get('pool')

    assert req.status_code == 200
    assert isinstance(req.json(), list) is True


def test_pool_get_disks(conn):
    req = conn.rest.get('pool')

    for pool in req.json():
        req = conn.rest.post(f'pool/id/{pool["id"]}/get_disks')
        assert req.status_code == 200
        assert isinstance(req.json(), list) is True

def test_version(conn):
    version = conn.rest.get('system/version')

    assert version.status_code == 200
    assert isinstance(version.json(), str) is True


def test_info(conn):
    info = conn.rest.get('system/info')

    assert info.status_code == 200
    assert isinstance(info.json(), dict) is True

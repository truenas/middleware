def test_version(auth_prepare):
    version = auth_prepare.connect.get('system/version')

    assert version.status_code == 200
    assert isinstance(version.json(), str) is True


def test_info(auth_prepare):
    info = auth_prepare.connect.get('system/info')

    assert info.status_code == 200
    assert isinstance(info.json(), dict) is True

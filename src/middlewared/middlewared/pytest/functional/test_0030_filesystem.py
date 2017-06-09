def test_filesystem_listdir(conn):
    req = conn.rest.post('filesystem/listdir', data=['/boot'])

    assert req.status_code == 200
    listdir = req.json()
    assert isinstance(listdir, list) is True
    assert len(listdir) > 0

    for e in listdir:
        if e['path'] == '/boot/kernel':
            assert e['type'] == 'DIRECTORY'
            assert e['uid'] == 0
            assert e['gid'] == 0
            assert e['name'] == 'kernel'
            break
    else:
        raise AssertionError('/boot/kernel not found')


def test_filesystem_stat(conn):
    req = conn.rest.post('filesystem/stat', data=['/data/freenas-v1.db'])

    assert req.status_code == 200
    stat = req.json()
    assert isinstance(stat, dict) is True

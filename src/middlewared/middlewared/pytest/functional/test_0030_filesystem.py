import threading


def test_filesystem_listdir(conn):
    req = conn.rest.post('filesystem/listdir', data={'path': '/boot'})

    assert req.status_code == 200, req.text
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
    req = conn.rest.post('filesystem/stat', data='/data/freenas-v1.db')

    assert req.status_code == 200, req.text
    stat = req.json()
    assert isinstance(stat, dict) is True


def test_filesystem_file_tail_follow(conn):

    event = threading.Event()

    def cb(mtype, **message):
        event.set()

    conn.ws.subscribe('filesystem.file_tail_follow:/var/log/messages', cb)

    assert event.wait(timeout=10) is True

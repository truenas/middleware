import os
from urllib.request import urlretrieve


def test_config_save(conn):
    req = conn.rest.post('core/download', data={'method': 'config.save', 'args': [], 'filename': 'freenas.db'})

    assert req.status_code == 200, req.text
    assert isinstance(req.json(), list) is True

    url = req.json()[1]
    rv = urlretrieve(f'http://{conn.conf.target_hostname()}{url}')
    stat = os.stat(rv[0])
    assert stat.st_size > 0

from urllib.request import urlretrieve


def test_config_save(conn):
    config = conn.rest.post('core/download', data=['config.save', [], 'freenas.db'])

    assert config.status_code == 200
    assert isinstance(config.json(), list) is True

    url = config.json()[1]
    urlretrieve(f'http://{conn.conf.target_hostname()}{url}')

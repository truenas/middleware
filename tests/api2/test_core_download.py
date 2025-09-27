from functions import http_get

from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils import call


def test_get_download_for_config_dot_save():
    # set up core download
    job_id, url = call('core.download', 'config.save', [], 'freenas.db')

    # download from URL
    rv = http_get(f'http://{truenas_server.ip}{url}')
    assert rv.status_code == 200
    assert len(rv.content) > 0

from os import stat

from urllib.request import urlretrieve
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils import call


def test_get_download_for_config_dot_save():
    # ping core for sanity
    assert call('core.ping') == 'pong'


    # set up core download
    job_id, url = call('core.download', 'config.save', [], 'freenas.db')


    # is the job running?
    results = call('core.get_jobs', [['id', '=', job_id]], {"get": True})
    assert results['state'] == 'RUNNING'


    # download from URL
    rv = urlretrieve(f'http://{truenas_server.ip}{url}')
    assert stat(rv[0]).st_size > 0


    # verify success
    results = call('core.get_jobs', [['id', '=', job_id]], {"get": True})
    assert results['state'] == 'SUCCESS'

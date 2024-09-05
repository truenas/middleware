from urllib.request import urlretrieve
from middlewared.test.integration.utils.client import truenas_server
from middlewared.test.integration.utils import call


def test_01_get_core_jobs():
    results = GET('/core/get_jobs/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True


def test_02_get_core_ping():
    results = GET('/core/ping/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), str) is True
    assert results.json() == 'pong'


def test_03_get_download_info_for_config_dot_save():
    payload = {
        'method': 'config.save',
        'args': [],
        'filename': 'freenas.db'
    }
    results = POST('/core/download/', payload)

    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list) is True, results.text
    global url
    url = results.json()[1]
    global job_id
    job_id = results.json()[0]


def test_04_verify_job_id_state_is_running():
    results = GET(f'/core/get_jobs/?id={job_id}')
    assert results.json()[0]['state'] == 'RUNNING', results.text


def test_05_download_from_url():
    rv = urlretrieve(f'http://{truenas_server.ip}{url}')
    stat = os.stat(rv[0])
    assert stat.st_size > 0


def test_06_verify_job_id_state_is_success():
    results = GET(f'/core/get_jobs/?id={job_id}')
    assert results.json()[0]['state'] == 'SUCCESS', results.text

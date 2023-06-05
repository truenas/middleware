
import os
import pytest
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE, PUT, wait_on_job
from auto_config import ha, dev_test

reason = 'Skip for development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

# TODO: why does this not run on HA?
if not ha:
    official_repository = 'https://github.com/truenas/charts.git'
    custom_repository = 'https://github.com/ericbsd/charts-1.git'
    github_official_charts = 'https://api.github.com/repos/truenas/charts/contents/charts/'
    github_custom_charts = 'https://api.github.com/repos/ericbsd/charts-1/contents/charts/'
    official_charts = []
    for chart_dict in GET(github_official_charts).json():
        if chart_dict['type'] == 'dir':
            official_charts.append(chart_dict['name'])

    custom_charts = []
    for chart_dict in GET(github_custom_charts).json():
        if chart_dict['type'] == 'dir':
            custom_charts.append(chart_dict['name'])

    custom_catalog = {
        'label': 'CUSTOMCHART',
        'repository': custom_repository,
        'branch': 'master',
        'builtin': False,
        'preferred_trains': ['charts'],
        'location': '/tmp/ix-applications/catalogs/github_com_ericbsd_charts-1_git_master',
        'id': 'CUSTOMCHART'
    }

    def test_01_get_catalog_list():
        results = GET('/catalog/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    def test_02_search_for_official_catalog_with_the_label():
        results = GET('/catalog/?label=TRUENAS')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert results.json()[0]['id'] == 'TRUENAS', results.text

    def test_03_get_official_catalog_with_id():
        results = GET('/catalog/id/TRUENAS/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['label'] == 'TRUENAS', results.text

    def test_04_verify_official_catalog_repository_with_id():
        results = GET('/catalog/id/TRUENAS/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['repository'] == official_repository, results.text

    def test_05_verify_official_catalog_repository_with_id():
        results = GET('/catalog/id/TRUENAS/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['repository'] == official_repository, results.text

    def test_06_validate_official_catalog():
        results = POST('/catalog/validate/', 'TRUENAS')
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_07_sync_official_catalog():
        results = POST('/catalog/sync/', 'TRUENAS')
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert results is None, results.text

    @pytest.mark.parametrize('chart', official_charts)
    def test_08_get_official_catalog_item(chart):
        payload = {
            'label': 'TRUENAS',
            'options': {
                'cache': True
            }
        }
        results = POST('/catalog/items/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), str(job_status['results'])
        assert chart in results['charts'], str(job_status['results'])

    def test_09_set_custom_catalog():
        global payload, results
        payload = {
            'force': False,
            'preferred_trains': ['charts'],
            'label': 'CUSTOMCHART',
            'repository': custom_repository,
            'branch': 'master'
        }
        results = POST('/catalog/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), results.text

    @pytest.mark.parametrize('key', list(custom_catalog.keys()))
    def test_10_verify_custom_catalog_object(key):
        assert results[key] == custom_catalog[key], str(results)

    @pytest.mark.parametrize('key', list(custom_catalog.keys()))
    def test_11_verify_custom_catalog_object(key):
        results = GET('/catalog/id/CUSTOMCHART/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()[key] == custom_catalog[key], results.text

    def test_12_validate_custom_catalog():
        results = POST('/catalog/validate/', 'CUSTOMCHART')
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_13_sync_custom_catalog():
        results = POST('/catalog/sync/', 'CUSTOMCHART')
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert results is None, results.text

    @pytest.mark.parametrize('chart', custom_charts)
    def test_14_get_custom_catalog_item(chart):
        payload = {
            'label': 'CUSTOMCHART',
            'options': {
                'cache': True,
                'retrieve_all_trains': True,
            },
        }
        results = POST('/catalog/items/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), str(job_status['results'])
        assert chart in results['charts'], str(job_status['results'])

    def test_15_change_custom_preferred_trains():
        payload = {
            'preferred_trains': ['test']
        }
        results = PUT('/catalog/id/CUSTOMCHART/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_16_verify_custom_catalog_preferred_trains():
        results = GET('/catalog/id/CUSTOMCHART/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert 'test' in results.json()['preferred_trains'], results.text

    def test_17_get_custom_catalog_item_test_trains():
        payload = {
            'label': 'CUSTOMCHART',
            'options': {
                'cache': True,
                'retrieve_all_trains': True,
            },
        }
        results = POST('/catalog/items/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results['test'], dict), str(job_status['results'])

    def test_18_sync_all_catalog():
        results = GET('/catalog/sync_all/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 180)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_19_delete_custom_catalog():
        results = DELETE('/catalog/id/CUSTOMCHART/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text
        assert results.json() is True, results.text

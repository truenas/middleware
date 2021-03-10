
import os
import pytest
import sys
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE, PUT, wait_on_job
from auto_config import ha, scale, dev_test

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)

official_repository = 'https://github.com/truenas/charts.git'
truechart_repository = 'https://github.com/ericbsd/charts.git'
github_official_charts = 'https://api.github.com/repos/truenas/charts/contents/charts/'
github_truechart_charts = 'https://api.github.com/repos/ericbsd/charts/contents/charts/'
official_charts = []
for chart_dict in GET(github_official_charts).json():
    if chart_dict['type'] == 'dir':
        official_charts.append(chart_dict['name'])

truechart_charts = []
for chart_dict in GET(github_truechart_charts).json():
    if chart_dict['type'] == 'dir':
        truechart_charts.append(chart_dict['name'])

truechart_catalog = {
    'label': 'TRUECHARTS',
    'repository': truechart_repository,
    'branch': 'master',
    'builtin': False,
    'preferred_trains': ['charts'],
    'location': '/tmp/ix-applications/catalogs/github_com_ericbsd_charts_git_master',
    'id': 'TRUECHARTS'
}


def test_01_get_catalog_list():
    results = GET('/catalog/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_search_for_official_catalog_with_the_label():
    results = GET('/catalog/?label=OFFICIAL')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json()[0]['id'] == 'OFFICIAL', results.text


def test_03_get_official_catalog_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['label'] == 'OFFICIAL', results.text


def test_04_verify_official_catalog_repository_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['repository'] == official_repository, results.text


def test_05_verify_official_catalog_repository_with_id():
    results = GET('/catalog/id/OFFICIAL/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['repository'] == official_repository, results.text


def test_06_validate_official_catalog():
    results = POST('/catalog/validate/', 'OFFICIAL')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_07_sync_official_catalog():
    results = POST('/catalog/sync/', 'OFFICIAL')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


@pytest.mark.parametrize('chart', official_charts)
def test_08_get_official_catalog_item(chart):
    payload = {
        'label': 'OFFICIAL',
        'options': {
            'cache': True
        }
    }
    results = POST('/catalog/items/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert chart in results.json()['charts'], results.text


def test_09_set_truechart_catalog():
    global payload, results
    payload = {
        'force': False,
        'preferred_trains': ['charts'],
        'label': 'TRUECHARTS',
        'repository': truechart_repository,
        'branch': 'master'
    }
    results = POST('/catalog/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('key', list(truechart_catalog.keys()))
def test_10_verify_truechart_catalog_object(key):
    assert results.json()[key] == truechart_catalog[key], results.text


@pytest.mark.parametrize('key', list(truechart_catalog.keys()))
def test_11_verify_truechart_catalog_object(key):
    results = GET('/catalog/id/TRUECHARTS/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()[key] == truechart_catalog[key], results.text


def test_12_validate_truechart_catalog():
    results = POST('/catalog/validate/', 'TRUECHARTS')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_13_sync_truechart_catalog():
    results = POST('/catalog/sync/', 'TRUECHARTS')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


@pytest.mark.parametrize('chart', truechart_charts)
def test_14_get_truechart_catalog_item(chart):
    payload = {
        'label': 'TRUECHARTS'
    }
    results = POST('/catalog/items/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert chart in results.json()['charts'], results.text


def test_15_change_truechart_preferred_trains():
    payload = {
        'preferred_trains': ['test']
    }
    results = PUT('/catalog/id/TRUECHARTS/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_16_verify_truechart_catalog_preferred_trains():
    results = GET('/catalog/id/TRUECHARTS/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'test' in results.json()['preferred_trains'], results.text


def test_17_get_truechart_catalog_item_test_trains():
    payload = {
        'label': 'TRUECHARTS'
    }
    results = POST('/catalog/items/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json()['test'], dict), results.text


def test_18_sync_all_catalog():
    results = GET('/catalog/sync_all/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_19_delete_truechart_catalog():
    results = DELETE('/catalog/id/TRUECHARTS/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), bool), results.text
    assert results.json() is True, results.text

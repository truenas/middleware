import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE, wait_on_job
from auto_config import ha, scale, dev_test

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)


def test_01_get_plex_version():
    global plex_version
    results = POST('/catalog/items/', {'label': 'OFFICIAL'})
    plex_version = list(results.json()['charts']['plex']['versions'].keys())[0]


@pytest.mark.dependency(name='release_plex')
def test_02_create_plex_chart_release(request):
    depends(request, ['setup_kubernetes'], scope='session')
    global plex_id
    payload = {
        'catalog': 'OFFICIAL',
        'item': 'plex',
        'release_name': 'myplex',
        'train': 'charts',
        'version': plex_version
    }
    results = POST('/chart/release/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    plex_id = job_status['results']['result']['id']


@pytest.mark.dependency(name='ix_app_backup')
def test_03_create_kubernetes_backup_chart_releases_for_ix_applications(request):
    depends(request, ['release_plex'])
    global backup_name
    results = POST('/kubernetes/backup_chart_releases/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    backup_name = job_status['results']['result']


def test_04_get_ix_applications_kubernetes_backup(request):
    depends(request, ['ix_app_backup'])
    results = GET('/kubernetes/list_backups/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert backup_name in results.json(), results.text


def test_05_restore_ix_applications_kubernetes_backup(request):
    depends(request, ['ix_app_backup'])
    results = POST('/kubernetes/restore_backup/', backup_name)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_06_verify_plex_chart_release_still_exist(request):
    depends(request, ['release_plex'])
    results = GET(f'/chart/release/id/{plex_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.dependency(name='release_ipfs')
def test_07_create_ipfs_chart_release(request):
    depends(request, ['setup_kubernetes'], scope='session')
    global ipfs_id
    payload = {
        'catalog': 'OFFICIAL',
        'item': 'ipfs',
        'release_name': 'ipfs',
        'train': 'charts'
    }
    results = POST('/chart/release/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    ipfs_id = job_status['results']['result']['id']


@pytest.mark.dependency(name='my_app_backup')
def test_08_create_custom_name_kubernetes_chart_releases_backup(request):
    depends(request, ['release_plex', 'release_ipfs'])
    results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_09_get_custom_name_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = GET('/kubernetes/list_backups/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'mybackup' in results.json(), results.text


def test_10_restore_custom_name_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/restore_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_11_verify_plex_and_ipfs_chart_release_still_exist(request):
    depends(request, ['my_app_backup'])
    results = GET(f'/chart/release/id/{plex_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    results = GET(f'/chart/release/id/{ipfs_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.dependency(name='my_second_backup')
def test_12_create_mysecondbackup_kubernetes_chart_releases_backup(request):
    depends(request, ['release_plex', 'release_ipfs'])
    results = POST('/kubernetes/backup_chart_releases/', 'mysecondbackup')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_13_delete_ipfs_chart_release(request):
    depends(request, ['release_ipfs'])
    results = DELETE(f'/chart/release/id/{ipfs_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_14_restore_custom_name_kubernetes_backup(request):
    depends(request, ['my_second_backup'])
    results = POST('/kubernetes/restore_backup/', 'mysecondbackup')
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_15_verify_plex_chart_still_exist_and_ipfs_does_not_exist(request):
    depends(request, ['my_app_backup'])
    results = GET(f'/chart/release/id/{plex_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    results = GET(f'/chart/release/id/{ipfs_id}/')
    assert results.status_code == 404, results.text
    assert isinstance(results.json(), dict), results.text


def test_16_delete_mybackup_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/delete_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_17_delete_ix_applications_kubernetes_backup(request):
    depends(request, ['ix_app_backup'])
    results = POST('/kubernetes/delete_backup/', backup_name)
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


@pytest.mark.dependency(name='k8s_snapshot_regression')
def test_18_recreate_mybackup_kubernetes_backup_for_snapshots_regression(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_19_delete_mybackup_kubernetes_backup(request):
    depends(request, ['k8s_snapshot_regresion'])
    results = POST('/kubernetes/delete_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_20_delete_mysecondbackup_kubernetes_backup(request):
    depends(request, ['my_second_backup'])
    results = POST('/kubernetes/delete_backup/', 'mysecondbackup')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_21_delete_plex_chart_release(request):
    depends(request, ['release_plex'])
    results = DELETE(f'/chart/release/id/{plex_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

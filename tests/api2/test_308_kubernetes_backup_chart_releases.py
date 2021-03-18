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
    # depends(request, ['setup_kubernetes'], scope='session')
    global release_id
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
    release_id = job_status['results']['result']['id']


@pytest.mark.dependency(name='ix_app_backup')
def test_03_create_kubernetes_backup_chart_releases_for_ix_applications(request):
    depends(request, ['release_plex'])
    global backup_name
    results = POST('/kubernetes/backup_chart_releases/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    print(job_status['results'])
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


@pytest.mark.dependency(name='my_app_backup')
def test_06_create_custom_name_kubernetes_chart_releases_backup(request):
    depends(request, ['release_plex'])
    results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_07_get_custom_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = GET('/kubernetes/list_backups/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert 'mybackup' in results.json(), results.text


def test_08_restore_custom_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/restore_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_09_delete_custom_kubernetes_backup(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/delete_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_10_delete_ix_applications_kubernetes_backup(request):
    depends(request, ['ix_app_backup'])
    results = POST('/kubernetes/delete_backup/', backup_name)
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


@pytest.mark.dependency(name='k8s_snapshot_regresion')
def test_11_create_the_same_custom_kubernetes_backup_for_snapshots_regresion(request):
    depends(request, ['my_app_backup'])
    results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_12_delete_custom_kubernetes_backup(request):
    depends(request, ['k8s_snapshot_regresion'])
    results = POST('/kubernetes/delete_backup/', 'mybackup')
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_13_delete_plex_chart_release(request):
    depends(request, ['release_plex'])
    results = DELETE(f'/chart/release/id/{release_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

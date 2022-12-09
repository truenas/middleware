import os
import pytest
import sys

from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE, SSH_TEST, wait_on_job
from auto_config import ha, dev_test, artifacts, password, ip
from middlewared.test.integration.utils import call


reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

# Read all the test below only on non-HA
if not ha:
    @pytest.mark.dependency(name='plex_version')
    def test_01_get_plex_version():
        global plex_version
        payload = {
            "item_name": "plex",
            "item_version_details": {
                "catalog": "OFFICIAL",
                "train": 'charts'
            }
        }
        results = POST('/catalog/get_item_details/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        plex_version = results.json()['latest_version']

    @pytest.mark.dependency(name='release_plex')
    def test_02_create_plex_chart_release(request):
        depends(request, ['setup_kubernetes', 'plex_version'], scope='session')
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

    @pytest.mark.dependency(name='check_datasets_to_ignore')
    def test_04_check_to_ignore_datasets_exist(request):
        datasets_to_ignore = set(call('kubernetes.to_ignore_datasets_on_backup', call('kubernetes.config')['dataset']))

        assert set(ds['id'] for ds in call(
            'zfs.dataset.query', [['OR', [['id', '=', directory] for directory in datasets_to_ignore]]]
        )) == datasets_to_ignore

    def test_05_backup_chart_release(request):
        depends(request, ['ix_app_backup', 'check_datasets_to_ignore'])
        datasets_to_ignore = set(call('kubernetes.to_ignore_datasets_on_backup', call('kubernetes.config')['dataset']))
        datasets = set(snap['dataset'] for snap in call('zfs.snapshot.query', [['id', 'rin', backup_name]]))

        assert datasets_to_ignore.intersection(datasets) == set()

    def test_06_get_ix_applications_kubernetes_backup(request):
        depends(request, ['ix_app_backup'])
        results = GET('/kubernetes/list_backups/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert backup_name in results.json(), results.text

    @pytest.mark.dependency(name='ix_app_backup_restored')
    def test_07_restore_ix_applications_kubernetes_backup(request):
        depends(request, ['ix_app_backup'])
        payload = {
            "backup_name": backup_name,
            "options": {
                "wait_for_csi": True
            }
        }
        results = POST('/kubernetes/restore_backup/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_08_verify_plex_chart_release_still_exist(request):
        depends(request, ['release_plex', 'ix_app_backup_restored'])
        results = GET(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.dependency(name='release_ipfs')
    def test_09_create_ipfs_chart_release(request):
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
    def test_10_create_custom_name_kubernetes_chart_releases_backup(request):
        depends(request, ['release_plex', 'release_ipfs'])
        results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_11_get_custom_name_kubernetes_backup(request):
        depends(request, ['my_app_backup'])
        results = GET('/kubernetes/list_backups/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert 'mybackup' in results.json(), results.text

    def test_12_restore_custom_name_kubernetes_backup(request):
        depends(request, ['my_app_backup'])
        payload = {
            "backup_name": 'mybackup',
        }
        results = POST('/kubernetes/restore_backup/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_13_verify_plex_and_ipfs_chart_release_still_exist(request):
        depends(request, ['my_app_backup'])
        results = GET(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        results = GET(f'/chart/release/id/{ipfs_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.dependency(name='my_second_backup')
    def test_14_create_mysecondbackup_kubernetes_chart_releases_backup(request):
        depends(request, ['release_plex', 'release_ipfs'])
        results = POST('/kubernetes/backup_chart_releases/', 'mysecondbackup')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_15_delete_ipfs_chart_release(request):
        depends(request, ['release_ipfs'])
        results = DELETE(f'/chart/release/id/{ipfs_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_16_restore_custom_name_kubernetes_backup(request):
        depends(request, ['my_second_backup'])
        payload = {
            "backup_name": 'mysecondbackup',
            "options": {
                "wait_for_csi": False
            }
        }
        results = POST('/kubernetes/restore_backup/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_17_verify_plex_chart_still_exist_and_ipfs_does_not_exist(request):
        depends(request, ['my_app_backup'])
        results = GET(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        results = GET(f'/chart/release/id/{ipfs_id}/')
        assert results.status_code == 404, results.text
        assert isinstance(results.json(), dict), results.text

    def test_18_delete_mybackup_kubernetes_backup(request):
        depends(request, ['my_app_backup'])
        results = POST('/kubernetes/delete_backup/', 'mybackup')
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_19_delete_ix_applications_kubernetes_backup(request):
        depends(request, ['ix_app_backup', 'ix_app_backup_restored'])
        results = POST('/kubernetes/delete_backup/', backup_name)
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    @pytest.mark.dependency(name='k8s_snapshot_regression')
    def test_20_recreate_mybackup_kubernetes_backup_for_snapshots_regression(request):
        depends(request, ['my_app_backup'])
        results = POST('/kubernetes/backup_chart_releases/', 'mybackup')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_21_delete_mybackup_kubernetes_backup(request):
        depends(request, ['k8s_snapshot_regression'])
        results = POST('/kubernetes/delete_backup/', 'mybackup')
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_22_delete_mysecondbackup_kubernetes_backup(request):
        depends(request, ['my_second_backup'])
        results = POST('/kubernetes/delete_backup/', 'mysecondbackup')
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_23_delete_plex_chart_release(request):
        depends(request, ['release_plex'])
        results = DELETE(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_24_get_k3s_logs():
        results = SSH_TEST('journalctl --no-pager -u k3s', 'root', password, ip)
        ks3_logs = open(f'{artifacts}/k3s-scale.log', 'w')
        ks3_logs.writelines(results['output'])
        ks3_logs.close()

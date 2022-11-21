import os
import pytest
import sys
import time
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, PUT, DELETE, wait_on_job
from auto_config import ha, dev_test, interface, pool_name

reason = 'Skipping for test development testing'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason=reason)

updatechart_catalog = {
    'label': 'UPDATECHARTS',
    'repository': 'https://github.com/ericbsd/charts-1.git',
    'branch': 'master',
    'builtin': False,
    'preferred_trains': ['charts'],
    'location': '/mnt/tank/ix-applications/catalogs/github_com_ericbsd_charts-1_git_master',
    'id': 'UPDATECHARTS'
}

# Read all the test below only on non-HA
if not ha:
    def test_01_get_chart_release():
        results = GET('/chart/release/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    def test_02_get_chart_release_certificate_authority_choices():
        results = GET('/chart/release/certificate_authority_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    def test_03_get_chart_release_certificate_choices():
        results = GET('/chart/release/certificate_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text

    def test_04_get_chart_release_nic_choices():
        results = GET('/chart/release/nic_choices/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert interface in results.json(), results.text

    @pytest.mark.dependency(name='ipfs_version')
    def test_05_get_ipfs_version():
        global ipfs_version
        payload = {
            "item_name": "ipfs",
            "item_version_details": {
                "catalog": "OFFICIAL",
                "train": 'charts'
            }
        }
        results = POST('/catalog/get_item_details/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        ipfs_version = list(results.json()['versions'].keys())[0]

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name='release_ipfs')
    def test_06_create_ipfs_chart_release(request):
        depends(request, ['setup_kubernetes', 'ipfs_version'], scope='session')
        global release_id
        payload = {
            'catalog': 'OFFICIAL',
            'item': 'ipfs',
            'release_name': 'ipfs',
            'train': 'charts',
            'version': ipfs_version
        }
        results = POST('/chart/release/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        release_id = job_status['results']['result']['id']

    def test_07_get_ipfs_chart_release_catalog(request):
        depends(request, ['release_ipfs'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['catalog'] == 'OFFICIAL', results.text

    def test_08_get_ipfs_chart_release_catalog_train(request):
        depends(request, ['release_ipfs'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['catalog_train'] == 'charts', results.text

    def test_09_get_ipfs_chart_release_name(request):
        depends(request, ['release_ipfs'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['name'] == 'ipfs', results.text

    def test_10_get_chart_release_scaleable_resources():
        results = GET('/chart/release/scaleable_resources/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.dependency(name='used_ports')
    def test_11_get_chart_release_used_ports(request):
        global port_list
        results = GET('/chart/release/used_ports/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        port_list = results.json()

    def test_12_verify_ipfs_chart_release_used_ports(request):
        depends(request, ['release_ipfs', 'used_ports'])
        results = GET(f'/chart/release/id/{release_id}/')
        for port_dict in results.json()['used_ports']:
            assert port_dict['port'] in port_list, results.text

    def test_13_get_ipfs_chart_release_upgrade_summary(request):
        depends(request, ['release_ipfs'])
        results = POST('/chart/release/upgrade_summary/', {'release_name': 'ipfs'})
        assert results.status_code == 422, results.text
        assert isinstance(results.json(), dict), results.text
        assert 'No update is available' in results.text, results.text

    @pytest.mark.timeout(600)
    def test_14_redeploy_ipfs_chart_release(request):
        depends(request, ['release_ipfs'])
        results = POST('/chart/release/redeploy/', 'ipfs')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_15_get_ipfs_chart_release_events(request):
        depends(request, ['release_ipfs'])
        results = POST('/chart/release/events/', 'ipfs')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert results.json()[0]['involvedObject']['namespace'] == 'ix-ipfs', results.text

    def test_16_set_ipfs_chart_release_scale(request):
        depends(request, ['release_ipfs'])
        payload = {
            'release_name': 'ipfs',
            'scale_options': {
                'replica_count': 1
            }
        }
        results = POST('/chart/release/scale/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), str(job_status['results'])

    def test_17_verify_ipfs_pod_status_desired_is_1(request):
        depends(request, ['release_ipfs'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['pod_status']['desired'] == 1, results.text

    def test_18_set_ipfs_chart_release_scale_workloads(request):
        depends(request, ['release_ipfs'])
        payload = {
            'release_name': 'ipfs',
            'workloads': [
                {
                    'replica_count': 2,
                    'type': 'DEPLOYMENT',
                    'name': 'ipfs'
                }
            ]
        }
        results = POST('/chart/release/scale_workloads/', payload)
        assert results.status_code == 200, results.text
        assert results.json() is None, results.text

    def test_19_verify_ipfs_pod_status_desired_is_2(request):
        depends(request, ['release_ipfs'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['pod_status']['desired'] == 2, results.text

    @pytest.mark.dependency(name='hostPath_dataset')
    def test_20_create_datasets_for_ipfs_hostPath(request):
        depends(request, ['pool_04'], scope='session')
        result = POST('/pool/dataset/', {'name': f'{pool_name}/ipfs-staging'})
        assert result.status_code == 200, result.text
        result = POST('/pool/dataset/', {'name': f'{pool_name}/ipfs-data'})
        assert result.status_code == 200, result.text

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name='ipfs_schema_values')
    def test_21_change_some_ipfs_schema_values(request):
        depends(request, ['release_ipfs', 'hostPath_dataset'])
        global payload
        payload = {
            'values': {
                'updateStrategy': 'RollingUpdate',
                'service': {
                    'swarmPort': 10401,
                    'apiPort': 10501,
                    'gatewayPort': 10880
                },
                'appVolumeMounts': {
                    'staging': {
                        'datasetName': 'ix-ipfs-staging',
                        'mountPath': '/export',
                        'hostPathEnabled': True,
                        'hostPath': f'/mnt/{pool_name}/ipfs-staging'
                    },
                    'data': {
                        'datasetName': 'ix-ipfs-data',
                        'mountPath': '/data/ipfs',
                        'hostPathEnabled': True,
                        'hostPath': f'/mnt/{pool_name}/ipfs-data'
                    }
                }
            }
        }
        results = PUT(f'/chart/release/id/{release_id}/', payload)
        assert results.status_code == 200, results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_22_verify_ipfs_updateStrategy(request):
        depends(request, ['ipfs_schema_values'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['updateStrategy'] == payload['values']['updateStrategy'], results.text

    @pytest.mark.parametrize('key', ['swarmPort', 'apiPort', 'gatewayPort'])
    def test_23_verify_ipfs_service_port(request, key):
        depends(request, ['ipfs_schema_values'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['config']['service'][key] == payload['values']['service'][key], results.text
        assert str(payload['values']['service'][key]) in str(results.json()['used_ports']), results.text

    @pytest.mark.parametrize('key', ['datasetName', 'mountPath', 'hostPathEnabled', 'hostPath'])
    def test_24_verify_ipfs_appVolumeMounts_staging(request, key):
        depends(request, ['ipfs_schema_values'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        staging = results.json()['config']['appVolumeMounts']['staging']
        assert staging[key] == payload['values']['appVolumeMounts']['staging'][key], results.text

    @pytest.mark.parametrize('key', ['datasetName', 'mountPath', 'hostPathEnabled', 'hostPath'])
    def test_25_verify_ipfs_appVolumeMounts_data(request, key):
        depends(request, ['ipfs_schema_values'])
        results = GET(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        data = results.json()['config']['appVolumeMounts']['data']
        assert data[key] == payload['values']['appVolumeMounts']['data'][key], results.text

    def test_26_verify_ipfs_staging_and_data_hostpath_in_resources_host_path_volumes(request):
        depends(request, ['ipfs_schema_values'])
        payload = {
            'query-options': {
                'extra': {
                    'retrieve_resources': True
                }
            },
            'query-filters': [['id', '=', 'ipfs']]}
        results = GET('/chart/release/', payload)
        host_path_volumes = str(results.json()[0]['resources']['host_path_volumes'])
        assert f'/mnt/{pool_name}/ipfs-staging' in host_path_volumes, host_path_volumes
        assert f'/mnt/{pool_name}/ipfs-data' in host_path_volumes, host_path_volumes

    def test_27_get_ipfs_chart_release_pod_console_choices(request):
        depends(request, ['release_ipfs'])
        results = POST('/chart/release/pod_console_choices/', 'ipfs')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    def test_28_get_ipfs_chart_release_pod_logs_choices(request):
        depends(request, ['release_ipfs'])
        results = POST('/chart/release/pod_logs_choices/', 'ipfs')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text

    @pytest.mark.timeout(600)
    def test_29_delete_ipfs_chart_release(request):
        depends(request, ['release_ipfs'])
        results = DELETE(f'/chart/release/id/{release_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_30_delete_datasets_for_ipfs_hostPath(request):
        depends(request, ['hostPath_dataset'])
        result = DELETE(f'/pool/dataset/id/{pool_name}%2Fipfs-staging/', {'recursive': True})
        assert result.status_code == 200, result.text
        result = DELETE(f'/pool/dataset/id/{pool_name}%2Fipfs-data/', {'recursive': True})
        assert result.status_code == 200, result.text

    @pytest.mark.dependency(name='custom_catalog')
    def test_31_set_custom_catalog_for_testing_update(request):
        depends(request, ['setup_kubernetes'], scope='session')
        global results
        payload = {
            'force': False,
            'preferred_trains': ['charts'],
            'label': 'UPDATECHARTS',
            'repository': 'https://github.com/ericbsd/charts-1.git',
            'branch': 'master'
        }
        results = POST('/catalog/', payload)
        assert results.status_code == 200, results.text
        job_id = results.json()
        job_status = wait_on_job(job_id, 300)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        results = job_status['results']['result']
        assert isinstance(results, dict), results.text
        # the sleep is needed or /catalog/items is not ready on time.
        time.sleep(5)

    @pytest.mark.parametrize('key', list(updatechart_catalog.keys()))
    def test_32_verify_updatechart_catalog_object(request, key):
        depends(request, ['custom_catalog'])
        assert results[key] == updatechart_catalog[key], results

    def test_33_verify_updatechart_is_in_catalog_list(request):
        depends(request, ['custom_catalog'])
        results = GET('/catalog/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), list), results.text
        assert 'UPDATECHARTS' in results.text, results.text

    @pytest.mark.parametrize('key', list(updatechart_catalog.keys()))
    def test_34_verify_updatechart_catalog_object(request, key):
        depends(request, ['custom_catalog'])
        results = GET('/catalog/id/UPDATECHARTS/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()[key] == updatechart_catalog[key], results.text

    @pytest.mark.dependency(name='plex_version')
    def test_35_get_plex_old_version(request):
        depends(request, ['custom_catalog'])
        global old_plex_version, new_plex_version
        payload = {
            "item_name": "plex",
            "item_version_details": {
                "catalog": "UPDATECHARTS",
                "train": 'charts'
            }
        }
        results = POST('/catalog/get_item_details/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        old_plex_version = sorted(list(results.json()['versions'].keys()))[0]
        new_plex_version = sorted(list(results.json()['versions'].keys()))[-1]
        time.sleep(1)

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name='release_plex')
    def test_36_create_plex_chart_release_with_old_version(request):
        depends(request, ['setup_kubernetes', 'plex_version'], scope='session')
        global plex_id
        payload = {
            'catalog': 'UPDATECHARTS',
            'item': 'plex',
            'release_name': 'plex',
            'train': 'charts',
            'version': old_plex_version
        }
        results = POST('/chart/release/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        plex_id = job_status['results']['result']['id']
        time.sleep(1)

    def test_37_get_plex_chart_release_upgrade_summary(request):
        depends(request, ['release_plex'])
        global update_version
        results = POST('/chart/release/upgrade_summary/', {'release_name': 'plex'})
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert new_plex_version in results.json()['latest_version'], results.text
        update_version = results.json()['latest_version']

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name='update_plex')
    def test_38_upgrade_plex_to_the_new_version(request):
        depends(request, ['release_plex'])
        payload = {
            'release_name': 'plex',
            'upgrade_options': {
                'item_version': update_version
            }
        }
        results = POST('/chart/release/upgrade/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        time.sleep(5)

    def test_39_verify_plex_new_version(request):
        depends(request, ['update_plex'])
        results = GET(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['chart_metadata']['version'] == new_plex_version, results.text

    @pytest.mark.timeout(600)
    @pytest.mark.dependency(name='rollback_plex')
    def test_40_rollback_plex_to_the_old_version(request):
        depends(request, ['update_plex'])
        payload = {
            'release_name': 'plex',
            'rollback_options': {
                'rollback_snapshot': False,
                'item_version': old_plex_version
            }
        }
        results = POST('/chart/release/rollback/', payload)
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])
        time.sleep(10)

    def test_41_verify_plex_is_at_the_old_version(request):
        depends(request, ['rollback_plex'])
        results = GET(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), dict), results.text
        assert results.json()['chart_metadata']['version'] == old_plex_version, results.text

    @pytest.mark.timeout(600)
    def test_42_delete_plex_chart_release(request):
        depends(request, ['release_plex'])
        results = DELETE(f'/chart/release/id/{plex_id}/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), int), results.text
        job_status = wait_on_job(results.json(), 600)
        assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    def test_43_delete_truechart_catalog(request):
        depends(request, ['custom_catalog'])
        results = DELETE('/catalog/id/UPDATECHARTS/')
        assert results.status_code == 200, results.text
        assert isinstance(results.json(), bool), results.text
        assert results.json() is True, results.text

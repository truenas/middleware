import os
import pytest
import sys
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, DELETE, wait_on_job
from auto_config import ha, scale, dev_test, interface

if dev_test:
    reason = 'Skip for testing'
else:
    reason = 'Skipping test for HA' if ha else 'Skipping test for CORE'
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(ha or not scale or dev_test, reason=reason)


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


def test_05_get_ipfs_version():
    global ipfs_version
    results = POST('/catalog/items/', {'label': 'OFFICIAL'})
    ipfs_version = list(results.json()['charts']['ipfs']['versions'].keys())[0]


@pytest.mark.dependency(name='release_ipfs')
def test_06_create_ipfs_chart_release(request):
    depends(request, ['setup_kubernetes'], scope='session')
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
    job_status = wait_on_job(results.json(), 300)
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


def test_14_redeploy_ipfs_chart_release(request):
    depends(request, ['release_ipfs'])
    results = POST('/chart/release/redeploy/', 'ipfs')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_15_get_ipfs_chart_release_events(request):
    depends(request, ['release_ipfs'])
    results = POST('/chart/release/events/', 'ipfs')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json()[0]['involved_object']['name'] == 'ipfs', results.text


def test_16_get_ipfs_chart_release_pod_console_choices(request):
    depends(request, ['release_ipfs'])
    results = POST('/chart/release/pod_console_choices/', 'ipfs')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_17_get_ipfs_chart_release_pod_logs_choices(request):
    depends(request, ['release_ipfs'])
    results = POST('/chart/release/pod_logs_choices/', 'ipfs')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_18_set_ipfs_chart_release_scale(request):
    depends(request, ['release_ipfs'])
    payload = {
        "release_name": "ipfs",
        "scale_options": {
            "replica_count": 1
        }
    }
    results = POST('/chart/release/scale/', payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


def test_19_verify_ipfs_pod_status_desired_is_1(request):
    depends(request, ['release_ipfs'])
    results = GET(f'/chart/release/id/{release_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pod_status']['desired'] == 1, results.text


def test_20_set_ipfs_chart_release_scale_workloads(request):
    depends(request, ['release_ipfs'])
    payload = {
        "release_name": "ipfs",
        "workloads": [
            {
                "replica_count": 2,
                "type": "DEPLOYMENT",
                "name": "ipfs"
            }
        ]
    }
    results = POST('/chart/release/scale_workloads/', payload)
    assert results.status_code == 200, results.text
    assert results.json() is None, results.text


def test_21_verify_ipfs_pod_status_desired_is_2(request):
    depends(request, ['release_ipfs'])
    results = GET(f'/chart/release/id/{release_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pod_status']['desired'] == 2, results.text


def test_22_delete_ipfs_chart_release(request):
    depends(request, ['release_ipfs'])
    results = DELETE(f'/chart/release/id/{release_id}/')
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 300)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

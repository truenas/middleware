#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import POST, GET, PUT, SSH_TEST, wait_on_job
from auto_config import ha, dev_test, hostname, user, password
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skipping for test development testing')

try:
    from config import AD_DOMAIN, ADPASSWORD, ADUSERNAME, ADNameServer
except ImportError:
    Reason = 'ADNameServer AD_DOMAIN, ADPASSWORD, or/and ADUSERNAME are missing in config.py"'
    ad_test = pytest.mark.skip(reason=Reason)


if ha and "virtual_ip" in os.environ:
    ip = os.environ["controller1_ip"]
else:
    from auto_config import ip


@pytest.fixture(scope='module')
def pool_data():
    return {}


@pytest.fixture(scope='module')
def logs_data():
    return {}


def test_01_verify_system_dataset_is_set_to_boot_pool():
    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'boot-pool', results.text
    assert results.json()['basename'] == 'boot-pool/.system', results.text


def test_02_verify_the_first_pool_created_with_encrypted_root_dataset_is_not_to_the_system_dataset(request, pool_data):
    pool_disk = [POST('/disk/get_unused/').json()[0]['name']]
    payload = {
        'name': 'encrypted',
        'encryption': True,
        'encryption_options': {
            'algorithm': 'AES-128-CCM',
            'passphrase': 'my_pool_passphrase',
        },
        'topology': {
            'data': [
                {'type': 'STRIPE', 'disks': pool_disk}
            ],
        }
    }
    results = POST('/pool/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 240)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_data['encrypted'] = job_status['results']['result']

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'boot-pool', results.text
    assert results.json()['basename'] == 'boot-pool/.system', results.text


def test_03_verify_the_system_dataset_cant_move_to_an_encrypted_root_dataset(request):
    results = PUT("/systemdataset/", {'pool': 'encrypted'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 120)
    assert job_status['state'] == 'FAILED', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'boot-pool', results.text
    assert results.json()['basename'] == 'boot-pool/.system', results.text


def test_04_delete_the_encrypted_pool_and_verify_the_system_dataset(request, pool_data):
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_data["encrypted"]["id"]}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'boot-pool', results.text
    assert results.json()['basename'] == 'boot-pool/.system', results.text


@pytest.mark.dependency(name="first_pool")
def test_05_creating_a_first_pool_and_verify_system_dataset_move_to_the_new_pool(request, pool_data):
    pool_disk = [POST('/disk/get_unused/').json()[0]['name']]
    payload = {
        "name": 'first_pool',
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": pool_disk}
            ],
        },
        "allow_duplicate_serials": True,
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_data['first_pool'] = job_status['results']['result']

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'first_pool', results.text
    assert results.json()['basename'] == 'first_pool/.system', results.text


@pytest.mark.dependency(name="second_pool")
def test_06_creating_a_second_pool_and_verify_system_dataset_does_not_move_to_the_new_pool(request, pool_data):
    depends(request, ["first_pool"])
    pool_disk = [POST('/disk/get_unused/').json()[0]['name']]
    payload = {
        "name": 'second_pool',
        "encryption": False,
        "topology": {
            "data": [
                {"type": "STRIPE", "disks": pool_disk}
            ],
        },
        "allow_duplicate_serials": True,
    }
    results = POST("/pool/", payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])
    pool_data['second_pool'] = job_status['results']['result']

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'first_pool', results.text
    assert results.json()['basename'] == 'first_pool/.system', results.text


def test_07_verify_changing_a_system_dataset_is_impossible_while_AD_is_running(request):
    depends(request, ["second_pool"])

    results = GET("/network/configuration/")
    assert results.status_code == 200, results.text
    nameserver1 = results.json()['nameserver1']
    payload = {
        "nameserver1": ADNameServer,
    }

    results = PUT("/network/configuration/", payload)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text

    payload = {
        "bindpw": ADPASSWORD,
        "bindname": ADUSERNAME,
        "domainname": AD_DOMAIN,
        "netbiosname": hostname,
        "dns_timeout": 15,
        "verbose_logging": True,
        "enable": True
    }
    results = PUT("/activedirectory/", payload)
    assert results.status_code == 200, results.text
    job_status = wait_on_job(results.json()['job_id'], 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET('/activedirectory/get_state/')
    assert results.status_code == 200, results.text
    assert results.json() == 'HEALTHY', results.text

    results = PUT("/systemdataset/", {'pool': 'second_pool'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 120)
    assert job_status['state'] == 'FAILED', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'first_pool', results.text
    assert results.json()['basename'] == 'first_pool/.system', results.text

    leave_payload = {
        "username": ADUSERNAME,
        "password": ADPASSWORD
    }
    results = POST("/activedirectory/leave/", leave_payload)
    assert results.status_code == 200, results.text

    results = PUT("/network/configuration/", {"nameserver1": nameserver1})
    assert results.status_code == 200, results.text


def test_08_get_logs_before_moving_the_system_dataset_to_the_second_pool(logs_data):
    cmd = "cat /var/log/middlewared.log"
    middlewared_log = SSH_TEST(cmd, user, password, ip)
    assert middlewared_log['result'] is True, str(middlewared_log)
    logs_data['middleware_log_4'] = middlewared_log['output'].splitlines()[-1]


def test_09_a_system_dataset_can_be_moved_to_second_pool_root_dataset(request):
    depends(request, ["second_pool"])
    results = PUT("/systemdataset/", {'pool': 'second_pool'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'second_pool', results.text
    assert results.json()['basename'] == 'second_pool/.system', results.text


def test_10_verify_logs_collection_still_work_after_moving_the_system_dataset_to_the_second_pool(logs_data):
    cmd = "cat /var/log/middlewared.log"
    middlewared_log = SSH_TEST(cmd, user, password, ip)
    assert middlewared_log['result'] is True, str(middlewared_log)
    logs_data['middleware_log_5'] = middlewared_log['output'].splitlines()[-1]
    assert logs_data['middleware_log_4'] in middlewared_log['output'], str(middlewared_log['output'])
    assert logs_data['middleware_log_4'] != logs_data['middleware_log_5']


def test_11_system_dataset_can_be_moved_to_another_pool_successfully_when_all_services_running(request):
    depends(request, ["second_pool"])
    services = {i['service']: i for i in GET('/service').json()}
    services_list = list(services.keys())
    services_list.remove('s3')
    for service in services_list:
        results = POST("/service/start/", {"service": service})
        assert results.status_code == 200, results.text

    results = PUT("/systemdataset/", {'pool': 'first_pool'})
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), int), results.text
    job_status = wait_on_job(results.json(), 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'first_pool', results.text
    assert results.json()['basename'] == 'first_pool/.system', results.text

    for service in services_list:
        if service != 'ssh':
            results = POST("/service/stop/", {"service": service})
            assert results.status_code == 200, results.text


def test_12_delete_the_second_pool_and_verify_the_system_dataset(request, pool_data):
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_data["second_pool"]["id"]}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'first_pool', results.text
    assert results.json()['basename'] == 'first_pool/.system', results.text


def test_13_delete_the_firs_pool_and_verify_the_system_dataset_moved_to_the_boot_pool(request, pool_data):
    payload = {
        'cascade': True,
        'restart_services': True,
        'destroy': True
    }
    results = POST(f'/pool/id/{pool_data["first_pool"]["id"]}/export/', payload)
    assert results.status_code == 200, results.text
    job_id = results.json()
    job_status = wait_on_job(job_id, 120)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])

    results = GET("/systemdataset/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert results.json()['pool'] == 'boot-pool', results.text
    assert results.json()['basename'] == 'boot-pool/.system', results.text

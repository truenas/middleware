#!/usr/bin/env python3

# License: BSD

import pytest
import sys
import os
from pytest_dependency import depends
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import DELETE, GET, POST, PUT, wait_on_job
from auto_config import pool_name, scale, dev_test
# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')
dataset = f"{pool_name}/tftproot"
dataset_url = dataset.replace('/', '%2F')
group = 'nogroup' if scale else 'nobody'


@pytest.mark.dependency(name='tftp_dataset')
def test_01_Creating_dataset_tftproot(request):
    depends(request, ["pool_04"], scope="session")
    result = POST('/pool/dataset/', {'name': dataset})
    assert result.status_code == 200, result.text


def test_02_Setting_permissions_for_TFTP_on_mnt_pool_name_tftproot(request):
    depends(request, ['tftp_dataset'])
    payload = {
        'acl': [],
        'mode': '777',
        'group': group,
        'user': 'nobody'
    }
    results = POST(f'/pool/dataset/id/{dataset_url}/permission/', payload)
    assert results.status_code == 200, results.text
    global job_id
    job_id = results.json()


def test_03_verify_the_job_id_is_successfull(request):
    depends(request, ['tftp_dataset'])
    job_status = wait_on_job(job_id, 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


@pytest.mark.dependency(name='configure_tftp')
def test_04_Configuring_TFTP_service(request):
    depends(request, ['tftp_dataset'])
    payload = {
        "directory": f"/mnt/{pool_name}/tftproot",
        "username": "nobody",
        "newfiles": True
    }
    results = PUT("/tftp/", payload)
    assert isinstance(results.json(), dict), results.text


def test_05_Enable_TFTP_service(request):
    depends(request, ['configure_tftp'])
    results = PUT("/service/id/tftp/", {"enable": True})

    assert results.status_code == 200, results.text


def test_06_Start_TFTP_service(request):
    depends(request, ['configure_tftp'])
    results = POST('/service/start/', {'service': 'tftp'})
    assert results.status_code == 200, results.text


def test_07_Checking_to_see_if_TFTP_service_is_enabled(request):
    depends(request, ['configure_tftp'])
    results = GET("/service/?service=tftp")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_08_stop_tftp_service(request):
    depends(request, ['configure_tftp'])
    results = POST('/service/stop/', {'service': 'tftp'})
    assert results.status_code == 200, results.text


def test_09_verify_to_see_if_tftp_service_is_stopped(request):
    depends(request, ['configure_tftp'])
    results = GET("/service/?service=tftp")
    assert results.json()[0]["state"] == "STOPPED", results.text


def test_10_delete_tftp_dataset(request):
    depends(request, ['tftp_dataset'])
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text

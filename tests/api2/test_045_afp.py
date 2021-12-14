#!/usr/bin/env python3

import pytest
import sys
import os
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET, DELETE, wait_on_job
from auto_config import ip, pool_name

dataset = f"{pool_name}/afp"
dataset_url = dataset.replace('/', '%2F')
AFP_NAME = "MyAFPShare"
AFP_PATH = f"/mnt/{dataset}"


def test_01_creating_afp_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = POST("/pool/dataset/", {"name": dataset})
    assert results.status_code == 200, results.text


def test_02_changing__dataset_permissions_of_afp_dataset(request):
    depends(request, ["pool_04"], scope="session")
    payload = {
        "acl": [],
        "mode": "777",
        "user": "root",
        "group": "wheel"
    }
    results = POST(f"/pool/dataset/id/{dataset_url}/permission/", payload)
    assert results.status_code == 200, results.text
    global job_id
    job_status = wait_on_job(results.json(), 180)
    assert job_status['state'] == 'SUCCESS', str(job_status['results'])


def test_03_get_afp_bindip(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/afp/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text
    assert isinstance(results.json()['bindip'], list), results.text


def test_04_setting_afp(request):
    depends(request, ["pool_04"], scope="session")
    global payload, results
    payload = {"guest": True,
               "bindip": [ip]}
    results = PUT("/afp/", payload)
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_05_verify_new_setting_afp_for_(data):
    assert results.json()[data] == payload[data], results.text
    assert isinstance(results.json(), dict), results.text


def test_06_get_new_afp_data(request):
    depends(request, ["pool_04"], scope="session")
    global results
    results = GET("/afp/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), dict), results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_07_verify_new_afp_data_for_(data):
    assert results.json()[data] == payload[data], results.text


def test_08_send_empty_afp_data(request):
    depends(request, ["pool_04"], scope="session")
    global results
    results = PUT("/afp/", {})
    assert results.status_code == 200, results.text


@pytest.mark.parametrize('data', ['guest', 'bindip'])
def test_09_verify_afp_data_did_not_change_for_(data):
    assert results.json()[data] == payload[data], results.text


def test_10_enable_afp_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/afp/", {"enable": True})
    assert results.status_code == 200, results.text


def test_11_checking_afp_enable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] is True, results.text


def test_12_start_afp_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "afp"}
    results = POST("/service/start/", payload)
    assert results.status_code == 200, results.text
    sleep(1)


def test_13_checking_if_afp_is_running(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "RUNNING", results.text


def test_14_creating_a_afp_share_on_afp_path(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"name": AFP_NAME, "path": AFP_PATH}
    results = POST("/sharing/afp/", payload)
    assert results.status_code == 200, results.text


def test_15_updating_the_apf_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"connections_limit": 10}
    results = PUT("/afp/", payload)
    assert results.status_code == 200, results.text


def test_16_update_afp_share(request):
    depends(request, ["pool_04"], scope="session")
    afpid = GET(f'/sharing/afp?name={AFP_NAME}').json()[0]['id']
    payload = {"home": True, "comment": "AFP Test"}
    results = PUT(f"/sharing/afp/id/{afpid}", payload)
    assert results.status_code == 200, results.text


def test_17_checking_to_see_if_afp_service_is_enabled(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=afp")
    assert results.json()[0]["state"] == "RUNNING", results.text


def test_18_delete_afp_share(request):
    depends(request, ["pool_04"], scope="session")
    afpid = GET(f'/sharing/afp?name={AFP_NAME}').json()[0]['id']
    results = DELETE(f"/sharing/afp/id/{afpid}")
    assert results.status_code == 200, results.text


def test_19_stopping_afp_service(request):
    depends(request, ["pool_04"], scope="session")
    payload = {"service": "afp"}
    results = POST("/service/stop/", payload)
    assert results.status_code == 200, results.text


def test_20_checking_if_afp_is_stop(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=afp")
    assert results.json()[0]['state'] == "STOPPED", results.text


def test_21_disable_afp_service_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = PUT("/service/id/afp/", {"enable": False})
    assert results.status_code == 200, results.text


def test_22_checking_afp_disable_at_boot(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/service?service=afp")
    assert results.json()[0]['enable'] is False, results.text


def test_23_destroying_afp_dataset(request):
    depends(request, ["pool_04"], scope="session")
    results = DELETE(f"/pool/dataset/id/{dataset_url}/")
    assert results.status_code == 200, results.text

#!/usr/bin/env python3

import pytest
import os
import sys
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from auto_config import ip, password, user, pool_name, scale, dev_test

# comment pytestmark for development testing with --dev-test
pytestmark = pytest.mark.skipif(dev_test, reason='Skip for testing')


def test_01_get_alert_list():
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text


def test_02_get_alert_list_categories():
    results = GET("/alert/list_categories/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json(), results.json()


def test_03_get_alert_list_policies():
    results = GET("/alert/list_policies/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    assert results.json(), results.json()


def test_04_degrading_a_pool_to_create_an_alert(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    global gptid
    get_pool = GET(f"/pool/?name={pool_name}").json()[0]
    id_path = '/dev/disk/by-partuuid/' if scale else '/dev/'
    gptid = get_pool['topology']['data'][0]['path'].replace(id_path, '')
    cmd = f'zinject -d {gptid} -A fault {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_05_verify_the_pool_is_degraded(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' in results['output'], results['output']


@pytest.mark.timeout(80)
def test_06_wait_for_the_alert(request):
    depends(request, ["pool_04"], scope="session")
    stop = False
    while stop is False:
        for line in GET("/alert/list/").json():
            if line['source'] == 'VolumeStatus':
                stop = True
                assert True
                break
        sleep(1)


def test_07_verify_degraded_pool_alert_list_exist_and_get_id(request):
    depends(request, ["pool_04"], scope="session")
    global alert_id
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['source'] == 'VolumeStatus':
            alert_id = line['id']
            assert line['args']['volume'] == pool_name, results.text
            assert line['args']['state'] == 'DEGRADED', results.text
            assert line['level'] == 'CRITICAL', results.text
            break


def test_08_dimiss_the_alert(request):
    depends(request, ["pool_04"], scope="session")
    results = POST("/alert/dismiss/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_09_verify_the_alert_is_dismissed(request):
    depends(request, ["pool_04"], scope="session")
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is True, results.text
            break


def test_10_restore_the_alert(request):
    depends(request, ["pool_04"], scope="session")
    results = POST("/alert/restore/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_11_verify_the_alert_is_restored(request):
    depends(request, ["pool_04"], scope="session")
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is False, results.text
            break


def test_12_clear_the_pool_degradation(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'zpool clear {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_13_verify_the_pool_is_not_degraded(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' not in results['output'], results['output']


@pytest.mark.timeout(80)
def test_14_wait_for_the_alert_to_dissapear(request):
    depends(request, ["pool_04"], scope="session")
    stop = False
    while stop is False:
        for line in GET("/alert/list/").json():
            if line['source'] == 'VolumeStatus':
                break
        else:
            stop = True
            assert True
        sleep(1)

#!/usr/bin/env python3

import pytest
import os
import sys
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from auto_config import ip, password, user, pool_name, dev_test

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


@pytest.mark.dependency(name='degrade_pool')
def test_04_degrading_a_pool_to_create_an_alert(request):
    depends(request, ["pool_04", "ssh_password"], scope="session")
    global gptid
    get_pool = GET(f"/pool/?name={pool_name}").json()[0]
    id_path = '/dev/disk/by-partuuid/'
    gptid = get_pool['topology']['data'][0]['path'].replace(id_path, '')
    cmd = f'zinject -d {gptid} -A fault {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_05_verify_the_pool_is_degraded(request):
    depends(request, ['degrade_pool'], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' in results['output'], results['output']


@pytest.mark.timeout(80)
def test_06_wait_for_the_alert_and_get_the_id(request):
    depends(request, ["degrade_pool"], scope="session")
    global alert_id
    while True:
        for line in GET("/alert/list/").json():
            if line['source'] == 'VolumeStatus':
                alert_id = line['id']
                assert True
                break
        else:
            continue
        break
        sleep(1)


def test_07_verify_degraded_pool_alert_list_exist(request):
    depends(request, ["degrade_pool"], scope="session")
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if alert_id == line['id']:
            assert line['args']['volume'] == pool_name, results.text
            assert line['args']['state'] == 'DEGRADED', results.text
            assert line['level'] == 'CRITICAL', results.text
            break


def test_08_dimiss_the_alert(request):
    depends(request, ["degrade_pool"], scope="session")
    results = POST("/alert/dismiss/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_09_verify_the_alert_is_dismissed(request):
    depends(request, ["degrade_pool"], scope="session")
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is True, results.text
            break


def test_10_restore_the_alert(request):
    depends(request, ["degrade_pool"], scope="session")
    results = POST("/alert/restore/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_11_verify_the_alert_is_restored(request):
    depends(request, ["degrade_pool"], scope="session")
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is False, results.text
            break


def test_12_clear_the_pool_degradation(request):
    depends(request, ["degrade_pool"], scope="session")
    cmd = f'zpool clear {pool_name}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


def test_13_verify_the_pool_is_not_degraded(request):
    depends(request, ["degrade_pool"], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' not in results['output'], results['output']


@pytest.mark.timeout(80)
def test_14_wait_for_the_alert_to_dissapear(request):
    depends(request, ["degrade_pool"], scope="session")
    while True:
        if alert_id not in GET("/alert/list/").json():
            assert True
            break
        sleep(1)


@pytest.mark.dependency(name='smb_service')
def test_15_start_smb_service():
    results = POST('/service/start/', {'service': 'cifs'})
    assert results.status_code == 200, results.text
    results = GET('/service?service=cifs')
    assert results.json()[0]['state'] == 'RUNNING', results.text


@pytest.mark.dependency(name='corefiles_alert')
def test_16_kill_smbd_with_6_to_triger_a_corefile_allert(request):
    depends(request, ['ssh_password', 'smb_service'], scope='session')
    cmd = 'killall -6 smbd'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.timeout(80)
@pytest.mark.dependency(name='wait_alert')
def test_17_wait_for_the_alert_and_get_the_id(request):
    depends(request, ['corefiles_allert'])
    global alert_id
    while True:
        for line in GET('/alert/list/').json():
            if line['source'] == 'CoreFilesArePresent':
                alert_id = line['id']
                assert True
                break
        else:
            sleep(1)
            continue
        break


def test_18_verify_the_smbd_corefiles_alert_warning(request):
    depends(request, ['wait_alert'])
    global alert_id
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if alert_id == line['id']:
            assert 'smbd' in results.json()[0]['args']['corefiles'], results.text
            assert results.json()[0]['level'] == 'WARNING', results.text
            break


def test_19_dimiss_the_corefiles_alert(request):
    depends(request, ['wait_alert'])
    results = POST('/alert/dismiss/', alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_20_verify_the_corefiles_alert_warning_is_dismissed(request):
    depends(request, ['wait_alert'])
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is True, results.text
            break

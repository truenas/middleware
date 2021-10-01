#!/usr/bin/env python3

import pytest
import os
import sys
from pytest_dependency import depends
from time import sleep
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import GET, POST, SSH_TEST
from auto_config import ip, password, user, pool_name, dev_test, ha

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


@pytest.mark.timeout(120)
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


@pytest.mark.timeout(120)
def test_14_wait_for_the_alert_to_dissapear(request):
    depends(request, ["degrade_pool"], scope="session")
    while True:
        if alert_id not in GET("/alert/list/").text:
            assert True
            break
        sleep(1)


@pytest.mark.skipif(ha, reason='Skipping test for SCALE HA')
@pytest.mark.dependency(name='corefiles_alert')
def test_15_kill_python_with_6_to_triger_a_corefile_allert(request):
    depends(request, ['ssh_password'], scope='session')
    cmd = 'python3 -c "import os; os.abort()"'
    results = SSH_TEST(cmd, user, password, ip)
    # The command will failed since kills a process
    assert results['result'] is False, results['output']


@pytest.mark.skipif(ha, reason='Skipping test for SCALE HA')
@pytest.mark.timeout(120)
@pytest.mark.dependency(name='wait_alert')
def test_16_wait_for_the_alert_and_get_the_id(request):
    depends(request, ['corefiles_alert'])
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


@pytest.mark.skipif(ha, reason='Skipping test for SCALE HA')
def test_17_verify_the_smbd_corefiles_alert_warning(request):
    depends(request, ['wait_alert'])
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if alert_id == line['id']:
            assert 'python' in results.json()[0]['args']['corefiles'], results.text
            assert results.json()[0]['level'] == 'WARNING', results.text
            break


@pytest.mark.skipif(ha, reason='Skipping test for SCALE HA')
def test_18_dimiss_the_corefiles_alert(request):
    depends(request, ['wait_alert'])
    results = POST('/alert/dismiss/', alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


@pytest.mark.skipif(ha, reason='Skipping test for SCALE HA')
def test_19_verify_the_corefiles_alert_warning_is_dismissed(request):
    depends(request, ['wait_alert'])
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is True, results.text
            break


def test_20_restore_corefiles_the_alert(request):
    depends(request, ['wait_alert'])
    results = POST("/alert/restore/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_21_verify_the_corefiles_alert_is_restored(request):
    depends(request, ['wait_alert'])
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is False, results.text
            break


def test_22_remove_the_core_files_in_var_db_system_cores(request):
    depends(request, ['wait_alert'])
    cmd = 'rm -f /var/db/system/cores/*'
    results = SSH_TEST(cmd, user, password, ip)
    assert results['result'] is True, results['output']


@pytest.mark.timeout(120)
def test_22_wait_for_the_corefiles_alert_to_dissapear(request):
    depends(request, ['wait_alert'])
    while True:
        if alert_id not in GET("/alert/list/").text:
            assert True
            break
        sleep(1)

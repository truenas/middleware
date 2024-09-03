from time import sleep

import pytest
from pytest_dependency import depends

from auto_config import password, user, pool_name
from functions import GET, POST, SSH_TEST
from middlewared.test.integration.utils import call


@pytest.mark.dependency(name='degrade_pool')
def test_degrading_a_pool_to_create_an_alert(request):
    global gptid
    get_pool = GET(f"/pool/?name={pool_name}").json()[0]
    id_path = '/dev/disk/by-partuuid/'
    gptid = get_pool['topology']['data'][0]['path'].replace(id_path, '')
    cmd = f'zinject -d {gptid} -A fault {pool_name}'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']


def test_verify_the_pool_is_degraded(request):
    depends(request, ['degrade_pool'], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' in results['output'], results['output']


@pytest.mark.timeout(120)
def test_wait_for_the_alert_and_get_the_id(request):
    depends(request, ["degrade_pool"], scope="session")
    global alert_id
    call("alert.process_alerts")
    while True:
        for line in GET("/alert/list/").json():
            if (
                line['source'] == 'VolumeStatus' and
                line['args']['volume'] == pool_name and
                line['args']['state'] == 'DEGRADED'
            ):
                alert_id = line['id']
                return

        sleep(1)


def test_dimiss_the_alert(request):
    depends(request, ["degrade_pool"], scope="session")
    results = POST("/alert/dismiss/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_verify_the_alert_is_dismissed(request):
    depends(request, ["degrade_pool"], scope="session")
    results = GET("/alert/list/")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is True, results.text
            break


def test_restore_the_alert(request):
    depends(request, ["degrade_pool"], scope="session")
    results = POST("/alert/restore/", alert_id)
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), type(None)), results.text


def test_verify_the_alert_is_restored(request):
    depends(request, ["degrade_pool"], scope="session")
    results = GET(f"/alert/list/?id={alert_id}")
    assert results.status_code == 200, results.text
    assert isinstance(results.json(), list), results.text
    for line in results.json():
        if line['id'] == alert_id:
            assert line['dismissed'] is False, results.text
            break


def test_clear_the_pool_degradation(request):
    depends(request, ["degrade_pool"], scope="session")
    cmd = f'zpool clear {pool_name}'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']


def test_verify_the_pool_is_not_degraded(request):
    depends(request, ["degrade_pool"], scope="session")
    cmd = f'zpool status {pool_name} | grep {gptid}'
    results = SSH_TEST(cmd, user, password)
    assert results['result'] is True, results['output']
    assert 'DEGRADED' not in results['output'], results['output']


@pytest.mark.timeout(120)
def test_wait_for_the_alert_to_disappear(request):
    depends(request, ["degrade_pool"], scope="session")
    while True:
        if alert_id not in GET("/alert/list/").text:
            assert True
            break
        sleep(1)

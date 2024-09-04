from time import sleep

import pytest
from pytest_dependency import depends

from auto_config import pool_name
from middlewared.test.integration.utils import call, ssh


def get_alert_by_id(alert_id):
    results = call("alert.list")
    for alert in results:
        if alert['id'] == alert_id:
            return alert


def alert_exists(alert_id):
    return isinstance(get_alert_by_id(alert_id), dict)


@pytest.mark.dependency(name='degrade_pool')
def test_degrading_a_pool_to_create_an_alert(request):
    global gptid
    get_pool = call("pool.query", [["name", "=", pool_name]])[0]
    id_path = '/dev/disk/by-partuuid/'
    gptid = get_pool['topology']['data'][0]['path'].replace(id_path, '')
    ssh(f'zinject -d {gptid} -A fault {pool_name}')


def test_verify_the_pool_is_degraded(request):
    depends(request, ['degrade_pool'], scope="session")
    stdout = ssh(f'zpool status {pool_name} | grep {gptid}')
    assert 'DEGRADED' in stdout


@pytest.mark.timeout(120)
def test_wait_for_the_alert_and_get_the_id(request):
    depends(request, ["degrade_pool"], scope="session")
    global alert_id
    call("alert.process_alerts")
    while True:
        for line in call("alert.list"):
            if (
                line['source'] == 'VolumeStatus' and
                line['args']['volume'] == pool_name and
                line['args']['state'] == 'DEGRADED'
            ):
                alert_id = line['id']
                return

        sleep(1)


def test_verify_the_alert_is_dismissed(request):
    depends(request, ["degrade_pool"], scope="session")
    call("alert.dismiss", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is True, alert


def test_verify_the_alert_is_restored(request):
    depends(request, ["degrade_pool"], scope="session")
    call("alert.restore", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is False, alert


def test_clear_the_pool_degradation(request):
    depends(request, ["degrade_pool"], scope="session")
    ssh(f'zpool clear {pool_name}')


def test_verify_the_pool_is_not_degraded(request):
    depends(request, ["degrade_pool"], scope="session")
    stdout = ssh(f'zpool status {pool_name} | grep {gptid}')
    assert 'DEGRADED' not in stdout


@pytest.mark.timeout(120)
def test_wait_for_the_alert_to_disappear(request):
    depends(request, ["degrade_pool"], scope="session")
    while alert_exists(alert_id): 
        sleep(1)

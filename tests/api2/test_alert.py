from time import sleep

import pytest

from auto_config import pool_name
from middlewared.test.integration.utils import call, ssh


ID_PATH = "/dev/disk/by-partuuid/"


def get_alert_by_id(alert_id):
    return next(filter(lambda alert: alert["id"] == alert_id, call("alert.list")), None)


@pytest.fixture(scope="module", autouse=True)
def degraded_pool_gptid():
    get_pool = call("pool.query", [["name", "=", pool_name]], {"get": True})
    gptid = get_pool["topology"]["data"][0]["path"].replace(ID_PATH, "")
    ssh(f"zinject -d {gptid} -A fault {pool_name}")
    return gptid


@pytest.fixture(scope="module")
def alert_id(degraded_pool_gptid):
    call("alert.process_alerts")
    while True:
        for alert in call("alert.list"):
            if (
                alert["source"] == "VolumeStatus" and
                alert["args"]["volume"] == pool_name and
                alert["args"]["state"] == "DEGRADED"
            ):
                return alert["id"]
        sleep(1)


def test_verify_the_pool_is_degraded(degraded_pool_gptid):
    status = call("zpool.status", {"name": pool_name})
    disk_status = status[pool_name]["data"][ID_PATH + degraded_pool_gptid]["disk_status"]
    assert disk_status == "DEGRADED"


@pytest.mark.timeout(120)
def test_dismiss_alert(alert_id):
    call("alert.dismiss", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is True, alert


def test_restore_alert(alert_id):
    call("alert.restore", alert_id)
    alert = get_alert_by_id(alert_id)
    assert alert["dismissed"] is False, alert


def test_clear_the_pool_degradation(degraded_pool_gptid):
    ssh(f"zpool clear {pool_name}")
    status = call("zpool.status", {"name": pool_name})
    disk_status = status[pool_name]["data"][ID_PATH + degraded_pool_gptid]["disk_status"]
    assert disk_status != "DEGRADED"


@pytest.mark.timeout(120)
def test_wait_for_the_alert_to_disappear(alert_id):
    while get_alert_by_id(alert_id) is not None: 
        sleep(1)
